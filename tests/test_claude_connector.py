"""The Claude connector: Alice's own OAuth server in front of Entra (FastMCP's OAuth proxy). Runs the whole sign-in as
Claude would (discovery, registration, authorise, consent page, the Entra callback, code exchange with PKCE) against a
stand-in for Microsoft, then uses the token on the MCP endpoint. Every Entra token is checked by Alice's own rules, so a
user who is not allowed, or a token from the wrong app, gets nothing. Nothing contacts Microsoft or Anthropic."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, hashlib, json, os, re, secrets
from urllib.parse import urlparse, parse_qs
import temple, knowledge as K
temple.save_settings(False, 'openai')
K.schedule_background = lambda *a, **k: None
import app as _app, mcp_server as M, external_auth as X
import logging; logging.getLogger('fastmcp').setLevel(logging.CRITICAL)
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from starlette.testclient import TestClient

TEN, APP, ME, OTHER = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333', '44444444-4444-4444-8444-444444444444'
COPILOT, CONNECTOR = '55555555-5555-4555-8555-555555555555', '88888888-8888-4888-8888-888888888888'
BASE = 'https://alice.example.com'
CLAUDE = 'https://claude.ai/api/mcp/auth_callback'
ENV = {'ALICE_EXT_TENANT_ID': TEN, 'ALICE_EXT_APP_ID': APP, 'ALICE_EXT_ALLOWED_USERS': ME,
       'ALICE_EXT_CALLERS': f'{COPILOT}=Microsoft Copilot:copilot', 'ALICE_EXT_BASE_URL': BASE,
       'ALICE_EXT_CONNECTOR_CLIENT_ID': CONNECTOR, 'ALICE_EXT_CONNECTOR_SECRET': 'test-secret-not-real',
       'ALICE_EXT_CONNECTOR_KEY': 'k' * 16 + secrets.token_hex(16),
       'ALICE_EXT_CONNECTOR_STORE': os.path.join(_util.DATA, 'oauth-connector')}   # the throwaway folder, never the real data

# 1. settings
cfg = X.load_config(ENV)
t('connector settings load; Claude is added as a caller', cfg.connector_client_id == CONNECTOR and cfg.callers[CONNECTOR] == X.Caller('Claude', 'claude')
  and cfg.connector_redirects == (CLAUDE,) + X.CHATGPT_CALLBACKS and cfg.connector_store.startswith(_util.DATA))
t('by default sign-ins are kept in the data folder', X.load_config({**ENV, 'ALICE_EXT_CONNECTOR_STORE': '', 'AISUBSTRATE_DATA_DIR': '/mnt/alice'}).connector_store == os.path.join('/mnt/alice', 'oauth-connector'))
t('without connector settings nothing changes', X.load_config({k: v for k, v in ENV.items() if 'CONNECTOR' not in k}).connector_client_id == '')
for label, change in [('only some connector settings refused', {'ALICE_EXT_CONNECTOR_KEY': ''}),
                      ('a short key refused', {'ALICE_EXT_CONNECTOR_KEY': 'short-key'}),
                      ('the API app itself refused as the connector', {'ALICE_EXT_CONNECTOR_CLIENT_ID': APP}),
                      ('a plain-http callback refused', {'ALICE_EXT_CONNECTOR_REDIRECTS': 'http://evil.example.com/cb'})]:
    try: X.load_config({**ENV, **change}); t(label, False)
    except ValueError: t(label, True)

# 2. the endpoint, with a stand-in for Microsoft's token endpoint
keys = RSAKeyPair.generate()
ver = X.EntraVerifier(cfg, public_key=keys.public_key)
def entra_token(**claims):
    c = {'tid': TEN, 'oid': ME, 'azp': CONNECTOR, 'scp': 'access_as_user'}; c.update(claims)
    return keys.create_token(subject=c['oid'], issuer=cfg.issuers[0], audience=APP, expires_in_seconds=3600, additional_claims=c)
NEXT = {'claims': {}}
class FakeEntra:
    def __init__(self): self.calls = []
    async def fetch_token(self, url=None, **params):
        FAKE.calls.append({'url': url, **params})
        return {'access_token': entra_token(**NEXT['claims']), 'token_type': 'Bearer', 'expires_in': 3600, 'refresh_token': 'entra-refresh'}
    async def aclose(self): pass
FAKE = FakeEntra()
M.enable_external(ver)
proxy = M.mcp.auth.server
t('Claude path: Alice runs the OAuth server, direct Entra tokens still accepted', type(M.mcp.auth).__name__ == 'MultiAuth' and proxy._token_validator is ver)
proxy._create_upstream_oauth_client = lambda: FAKE
web = M.mcp.http_app()
H = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
INIT = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'Claude', 'version': '1'}}}

def sign_in(c, client_id, claims=None, cb=None):
    """Claude's side of the flow, then Entra's; returns the token response (or the failing response)."""
    NEXT['claims'] = claims or {}
    CB = cb or CLAUDE
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    r = c.get('/authorize', params={'response_type': 'code', 'client_id': client_id, 'redirect_uri': CB, 'state': 'claude-state',
                                     'code_challenge': challenge, 'code_challenge_method': 'S256', 'scope': ' '.join(SCOPES)},
              follow_redirects=False)
    if r.status_code not in (302, 303, 307): return r
    consent = c.get(r.headers['location'])
    form = dict(re.findall(r'name="(txn_id|csrf_token)" value="([^"]+)"', consent.text))
    r = c.post('/consent', data={**form, 'action': 'approve', 'submit': 'true'}, follow_redirects=False)
    to_entra = urlparse(r.headers['location'])
    q = parse_qs(to_entra.query)
    sign_in.entra = (to_entra, q)
    r = c.get('/auth/callback', params={'code': 'entra-code', 'state': q['state'][0]}, follow_redirects=False)
    back = urlparse(r.headers.get('location', ''))
    if back.scheme + '://' + back.netloc + back.path != CB: return r
    bq = parse_qs(back.query)
    sign_in.state = bq.get('state', [''])[0]
    return c.post('/token', data={'grant_type': 'authorization_code', 'code': bq['code'][0], 'redirect_uri': CB,
                                  'client_id': client_id, 'code_verifier': verifier})

with TestClient(web, base_url=BASE) as c:
    r = c.post('/mcp', json=INIT, headers=H)
    t('no token: 401 that points Claude at the metadata', r.status_code == 401 and 'resource_metadata' in r.headers.get('www-authenticate', ''))
    prm = c.get('/.well-known/oauth-protected-resource/mcp').json()
    t('protected-resource metadata: Alice is the authorisation server for this exact URL', prm['resource'] == BASE + '/mcp'
      and prm['authorization_servers'][0].rstrip('/') == BASE)
    asm = c.get('/.well-known/oauth-authorization-server').json()
    t('authorisation-server metadata: PKCE S256, public clients, Claude\'s published identity (CIMD)', asm.get('code_challenge_methods_supported') == ['S256']
      and 'none' in asm.get('token_endpoint_auth_methods_supported', []) and asm.get('client_id_metadata_document_supported') is True)

    SCOPES = prm['scopes_supported']      # what Claude asks for: exactly what Alice advertises
    t('Claude is told to ask for the Alice scope', SCOPES == ['access_as_user'])
    reg = c.post('/register', json={'redirect_uris': [CLAUDE], 'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token'],
                                    'response_types': ['code'], 'client_name': 'Claude'})
    t('Claude can register (dynamic registration)', reg.status_code in (200, 201) and reg.json().get('client_id'))
    cid = reg.json()['client_id']
    bad = c.post('/register', json={'redirect_uris': ['https://evil.example.com/steal'], 'token_endpoint_auth_method': 'none',
                                    'grant_types': ['authorization_code'], 'response_types': ['code']})
    t('a client with any other callback address is refused', bad.status_code >= 400)

    tokens = sign_in(c, cid)
    to_entra, q = sign_in.entra
    t('approve sends you to YOUR tenant\'s Microsoft sign-in, with the connector app and the Alice scope',
      to_entra.netloc == 'login.microsoftonline.com' and to_entra.path == f'/{TEN}/oauth2/v2.0/authorize' and q['client_id'] == [CONNECTOR]
      and f'api://{APP}/access_as_user' in q['scope'][0])
    t('Alice\'s own address is not sent to Microsoft as the resource (avoids AADSTS9010010)', 'resource' not in q)
    t('Alice swaps the Microsoft code server-side with her secret', FAKE.calls and FAKE.calls[-1]['code'] == 'entra-code'
      and FAKE.calls[-1]['redirect_uri'] == BASE + '/auth/callback')
    t('Claude gets its state back and an access token', sign_in.state == 'claude-state' and tokens.status_code == 200 and tokens.json().get('access_token'))
    at = tokens.json()['access_token']
    t('the token Claude holds is Alice\'s, not Microsoft\'s', at != entra_token() and at.count('.') == 2)

    r = c.post('/mcp', json=INIT, headers={**H, 'Authorization': 'Bearer ' + at})
    t('signed in through Alice: the MCP endpoint answers', r.status_code == 200)
    sid = r.headers.get('mcp-session-id')
    HS = {**H, 'Authorization': 'Bearer ' + at, **({'mcp-session-id': sid} if sid else {})}
    c.post('/mcp', json={'jsonrpc': '2.0', 'method': 'notifications/initialized'}, headers=HS)
    r = c.post('/mcp', json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'propose_record', 'arguments':
               {'title': 'Claude connector test', 'content': 'Proposed from Claude through the connector.', 'source': 'Stefan in Claude'}}}, headers=HS)
    body = r.text
    payload = json.loads(next(l[5:] for l in body.splitlines() if l.startswith('data:'))) if 'data:' in body else r.json()
    res = json.loads(payload['result']['content'][0]['text'])
    import substrate_store as s
    with s.db() as db: src = db.execute('SELECT source, status FROM records WHERE id=?', (res['id'],)).fetchone()
    t('a proposal from Claude is labelled [via Claude] and waits for approval', src and src['source'].endswith('[via Claude]') and src['status'] == 'proposed')

    # ChatGPT on the web signs in the same way, and is named ChatGPT (provider openai), not Claude
    GPT_CB = 'https://chatgpt.com/connector/oauth/abc123'
    greg = c.post('/register', json={'redirect_uris': [GPT_CB], 'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token'],
                                     'response_types': ['code'], 'client_name': 'ChatGPT'})
    t('ChatGPT can register with its per-connection callback', greg.status_code in (200, 201))
    gt = sign_in(c, greg.json()['client_id'], cb=GPT_CB)
    t('ChatGPT gets an access token', gt.status_code == 200 and gt.json().get('access_token'))
    G = {**H, 'Authorization': 'Bearer ' + gt.json()['access_token']}
    r = c.post('/mcp', json=INIT, headers=G); gsid = r.headers.get('mcp-session-id')
    GS = {**G, **({'mcp-session-id': gsid} if gsid else {})}
    c.post('/mcp', json={'jsonrpc': '2.0', 'method': 'notifications/initialized'}, headers=GS)
    r = c.post('/mcp', json={'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'propose_record', 'arguments':
               {'title': 'ChatGPT connector test', 'content': 'Proposed from ChatGPT through the connector.', 'source': 'Stefan in ChatGPT'}}}, headers=GS)
    body = r.text
    gpay = json.loads(next(l[5:] for l in body.splitlines() if l.startswith('data:'))) if 'data:' in body else r.json()
    gres = json.loads(gpay['result']['content'][0]['text'])
    with s.db() as db: gsrc = db.execute('SELECT source FROM records WHERE id=?', (gres['id'],)).fetchone()
    t('a proposal from ChatGPT is labelled [via ChatGPT], not Claude', gsrc and gsrc['source'].endswith('[via ChatGPT]'))
    r = c.post('/mcp', json={'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list'}, headers=GS)
    t('ChatGPT (provider openai) gets the health tools, as Stefan allowed', 'get_health_context' in r.text)
    import agents as AG
    t('ChatGPT is its own app on the Agents page', any(a['name'] == 'ChatGPT' for a in AG.listing()['agents']) if hasattr(AG, 'listing') else True)
    sneaky = c.post('/register', json={'redirect_uris': ['https://chatgpt.com.evil.example/cb'], 'token_endpoint_auth_method': 'none',
                                       'grant_types': ['authorization_code'], 'response_types': ['code']})
    t('a look-alike callback address is refused', sneaky.status_code >= 400)
    t('the Claude sign-in is still named Claude', X.connector_app([CLAUDE]) == X.Caller('Claude', 'claude')
      and X.connector_app(['https://chatgpt.com/connector_platform_oauth_redirect']) == X.Caller('ChatGPT', 'openai')
      and X.connector_app(['https://evil.example/claude.ai']) is None)

    t('direct Microsoft tokens (the Copilot route) still work alongside', c.post('/mcp', json=INIT, headers={**H, 'Authorization': 'Bearer ' + entra_token()}).status_code == 200)

    # someone not on the allowed list gets through Microsoft but not into Alice
    other = sign_in(c, cid, {'oid': OTHER})
    ot = other.json().get('access_token') if other.status_code == 200 else None
    t('a user who is not allowed gets no access, even after signing in at Microsoft',
      ot is None or c.post('/mcp', json=INIT, headers={**H, 'Authorization': 'Bearer ' + ot}).status_code == 401)
    wrong_app = sign_in(c, cid, {'azp': '99999999-9999-4999-8999-999999999999'})
    wt = wrong_app.json().get('access_token') if wrong_app.status_code == 200 else None
    t('a Microsoft token issued to another app is refused', wt is None or c.post('/mcp', json=INIT, headers={**H, 'Authorization': 'Bearer ' + wt}).status_code == 401)

    r = c.get('/authorize', params={'response_type': 'code', 'client_id': cid, 'redirect_uri': 'https://evil.example.com/steal', 'state': 's',
                                     'code_challenge': 'x' * 43, 'code_challenge_method': 'S256'}, follow_redirects=False)
    t('sign-in that tries to return anywhere but Claude is refused', r.status_code >= 400 or 'evil.example.com' not in r.headers.get('location', ''))
    t('a tampered token is refused', c.post('/mcp', json=INIT, headers={**H, 'Authorization': 'Bearer ' + at[:-4] + 'AAAA'}).status_code == 401)

files = [os.path.join(dp, f) for dp, _, fs in os.walk(cfg.connector_store) for f in fs]
blob = b''.join(open(f, 'rb').read() for f in files)
t('sign-ins are stored only encrypted (no Microsoft token or refresh token readable on disk)', files and b'entra-refresh' not in blob
  and entra_token().split('.')[0].encode() not in blob)
