"""The signed-in external endpoint (Microsoft 365 Copilot via Entra ID): settings checks, every token check,
then the real HTTP endpoint: refusals without a valid token, and the external rules for a signed-in caller.
Tokens are signed with a throwaway key; nothing contacts Microsoft."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import asyncio, json, socket, threading, time
import substrate_store as s, temple, knowledge as K, clients as C, rules_engine as R
temple.save_settings(False, 'openai')
K.schedule_background = lambda *a, **k: None
import app, mcp_server as M, external_auth as X
import logging; logging.getLogger('fastmcp').setLevel(logging.CRITICAL)
for h in list(logging.getLogger('fastmcp').handlers): h.setLevel(logging.CRITICAL)
from fastmcp.server.auth.providers.jwt import RSAKeyPair
import httpx, uvicorn

TEN, APP, ME, OTHER = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333', '44444444-4444-4444-8444-444444444444'
COPILOT, ROGUE, OTHER_TEN = '55555555-5555-4555-8555-555555555555', '66666666-6666-4666-8666-666666666666', '77777777-7777-4777-8777-777777777777'
ENV = {'ALICE_EXT_TENANT_ID': TEN, 'ALICE_EXT_APP_ID': APP, 'ALICE_EXT_ALLOWED_USERS': ME,
       'ALICE_EXT_CALLERS': f'{COPILOT}=Microsoft Copilot:copilot', 'ALICE_EXT_BASE_URL': 'https://alice.example.com'}

# 1. settings
cfg = X.load_config(ENV)
t('settings load: tenant issuers, both audiences, scope default', cfg.issuers[0].endswith(TEN + '/v2.0') and cfg.audiences == [APP, 'api://' + APP] and cfg.scope == 'access_as_user')
t('caller parsed with label and provider', cfg.callers[COPILOT] == X.Caller('Microsoft Copilot', 'copilot'))
t('default bind is localhost:8002 behind a proxy', (cfg.host, cfg.port) == ('127.0.0.1', 8002) and 'alice.example.com' in cfg.allowed_hosts)
for label, change in [('missing settings refused', {'ALICE_EXT_ALLOWED_USERS': ''}), ('multi-tenant alias refused', {'ALICE_EXT_TENANT_ID': 'common'}),
                      ('non-GUID user refused', {'ALICE_EXT_ALLOWED_USERS': 'stefan@example.com'}), ('plain http refused', {'ALICE_EXT_BASE_URL': 'http://alice.example.com'}),
                      ('malformed caller refused', {'ALICE_EXT_CALLERS': COPILOT + '=Copilot'}), ('unknown provider refused', {'ALICE_EXT_CALLERS': COPILOT + '=Copilot:bard'})]:
    try: X.load_config({**ENV, **change}); t(label, False)
    except ValueError: t(label, True)

# 2. every token check (signature with a throwaway key; the real endpoint uses the tenant's published keys)
keys, forger = RSAKeyPair.generate(), RSAKeyPair.generate()
ver = X.EntraVerifier(cfg, public_key=keys.public_key)
def tok(key=None, iss=None, aud=APP, exp=3600, **claims):
    c = {'tid': TEN, 'oid': ME, 'azp': COPILOT, 'scp': 'access_as_user'}; c.update(claims)
    return (key or keys).create_token(subject=ME, issuer=iss or cfg.issuers[0], audience=aud, expires_in_seconds=exp,
                                      additional_claims={k: v for k, v in c.items() if v is not None})
ok = lambda token: asyncio.run(ver.load_access_token(token)) is not None
t('valid v2 token accepted', ok(tok()))
t('valid v1 token (sts issuer, api:// audience, appid) accepted', ok(tok(iss=cfg.issuers[1], aud='api://' + APP, azp=None, appid=COPILOT)))
for label, token in [('forged signature', tok(key=forger)), ('expired', tok(exp=-60)), ('another tenant (issuer)', tok(iss=f'https://login.microsoftonline.com/{OTHER_TEN}/v2.0')),
                     ('another tenant (tid claim)', tok(tid=OTHER_TEN)), ('token for another API', tok(aud='api://something-else')),
                     ('another user', tok(oid=OTHER)), ('unknown client app', tok(azp=ROGUE)), ('missing scope', tok(scp='User.Read')),
                     ('app-only token (no user)', tok(scp=None, roles=['Alice.All'])), ('not yet valid', tok(nbf=int(time.time()) + 3600)),
                     ('garbage', 'not.a.token')]:
    t('refused: ' + label, not ok(token))
t('refused: no expiry', ver.check_claims({'tid': TEN, 'oid': ME, 'azp': COPILOT, 'scp': 'access_as_user'}) == 'token has no expiry')
with s.db() as c: n = c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked' AND rule='external_auth'").fetchone()[0]
t('every refusal recorded in the activity log', n == 11)

# 3. data for the endpoint
s.create_category('Work', 'Insight'); s.create_category('Personal', 'Home'); C.create_client('Fife Council', ['Fife'])
def mem(title, cat):
    rid = s.propose(title, title + ' content that is long enough.', 'Stefan said so', cat)['id']; s.review(rid, 'approved'); return rid
work, home = mem('Work fact about migrations', 'Work'), mem('Home fact about the carport', 'Personal')
note = lambda title, **kw: K.create('note', title, title + ' body text that is long enough to save.', 'Written by you', 'you', **kw)['id']
gen, loc, fife = note('General roadmap note'), note('Local only diary note', label='local'), note('Fife council briefing', client='Fife Council')
R.update_rule('provider_allow', new_params={'blocked': {'Work': ['copilot']}, 'labels': {'internal': ['grok']}})
t('internal web-chat path unchanged (no caller)', M._who() is None and gen in [f['id'] for f in M.list_files()['files']])

# 4. the real HTTP endpoint
M.enable_external(ver)
app = M.mcp.http_app(allowed_hosts=['127.0.0.1'])
sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(100):
    if server.started: break
    time.sleep(0.05)
URL = f'http://127.0.0.1:{port}/mcp'
INIT = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}}}
H = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
r = httpx.post(URL, json=INIT, headers=H)
t(f'no token: 401 with a sign-in challenge ({r.status_code})', r.status_code == 401 and 'bearer' in r.headers.get('www-authenticate', '').lower())
for label, token in [('forged', tok(key=forger)), ('expired', tok(exp=-60)), ('wrong user', tok(oid=OTHER)), ('wrong tenant', tok(tid=OTHER_TEN))]:
    r = httpx.post(URL, json=INIT, headers={**H, 'Authorization': 'Bearer ' + token})
    t(f'{label} token: 401 ({r.status_code})', r.status_code == 401)

meta = httpx.get(f'http://127.0.0.1:{port}/.well-known/oauth-protected-resource/mcp').json()
t('protected-resource metadata names the tenant and the Alice scope', meta.get('authorization_servers') == [cfg.issuers[0]]
  and meta.get('scopes_supported') == [f'api://{APP}/access_as_user'])
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
async def signed_in():
    async with Client(StreamableHttpTransport(URL, headers={'Authorization': 'Bearer ' + tok()})) as c:
        names = sorted(x.name for x in await c.list_tools())
        data = lambda res: json.loads(res.content[0].text)
        files = [f['id'] for f in data(await c.call_tool('list_files', {}))['files']]
        recs = data(await c.call_tool('search_records', {'query': 'fact', 'limit': 10}))
        p = data(await c.call_tool('propose_record', {'title': 'Copilot test', 'content': 'Proposed from Copilot in the test.', 'source': 'Stefan in Copilot'}))
        try: await c.call_tool('read_file', {'file_id': loc}); local_read = True
        except Exception: local_read = False
        return names, files, recs, p, local_read
names, files, recs, p, local_read = asyncio.run(signed_in())
t('signed in: all nine tools offered', len(names) == 9 and 'propose_knowledge' in names)
t('General knowledge readable', gen in files)
t('Local only and client-confidential knowledge withheld', loc not in files and fife not in files and not local_read)
ids = [x['id'] for x in recs['records']]
t('Provider allow-list applies to Copilot (Work blocked, Personal allowed)', home in ids and work not in ids and 'withheld_by_provider_rule' in recs)
src = [r for r in s.records('proposed')['records'] if r['id'] == p['id']][0]['source']
t('proposal is tagged [via Microsoft Copilot] and awaits approval', src.endswith('[via Microsoft Copilot]') and p['status'] == 'proposed')
server.should_exit = True
