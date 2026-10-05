"""Alice as a Microsoft 365 Copilot agent: the app package (manifest, declarative agent, MCP plugin) built from the tools Alice
really offers, health tools left out, Entra SSO through the Developer Portal registration; and the external endpoint accepting
Copilot's single sign-on tokens (the registration's Application ID URI as audience, Microsoft's token store as the caller).
Tokens are signed with a throwaway key; nothing contacts Microsoft."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import asyncio, io, json, zipfile
import external_auth as X, copilot_package as CP
from fastmcp.server.auth.providers.jwt import RSAKeyPair
import struct, zlib

URL, AUTH = 'https://alice-mcp.example.uksouth.azurecontainerapps.io/mcp', 'ZmFrZS1hdXRoLWNvbmZpZy1pZA=='
raw = CP.build(URL, AUTH)
z = zipfile.ZipFile(io.BytesIO(raw))
names = set(z.namelist())
t('the package holds the five files at its root', names == {'manifest.json', 'declarativeAgent.json', 'alice-plugin.json', 'color.png', 'outline.png'})
man, agent, plug = (json.loads(z.read(n)) for n in ('manifest.json', 'declarativeAgent.json', 'alice-plugin.json'))
t('the manifest declares the agent and its icons', man['copilotAgents']['declarativeAgents'][0]['file'] == 'declarativeAgent.json'
  and man['icons'] == {'color': 'color.png', 'outline': 'outline.png'} and man['id'] == CP.APP_ID_LIVE and man['name']['short'] == 'Alice')
t('the agent uses the plugin, with instructions within the limit', agent['actions'] == [{'id': 'alicePlugin', 'file': 'alice-plugin.json'}]
  and len(agent['instructions']) <= 8000 and 'search_records' in agent['instructions'] and 'approval' in agent['instructions'] and len(agent['conversation_starters']) == 4)
rt = plug['runtimes'][0]
t('the plugin runs on Alice\'s endpoint with Entra SSO', rt['type'] == 'RemoteMCPServer' and rt['spec']['url'] == URL
  and rt['auth'] == {'type': 'OAuthPluginVault', 'reference_id': AUTH} and plug['schema_version'] == 'v2.4')
fn_names = [f['name'] for f in plug['functions']]
tool_names = [x['name'] for x in rt['spec']['mcp_tool_description']['tools']]
t('every function has its tool, and the runtime runs them all', fn_names == tool_names == rt['run_for_functions'] and len(fn_names) >= 10)
t('the tools are Alice\'s own, with their input schemas', {'search_records', 'propose_record', 'propose_decision', 'read_file'} <= set(tool_names)
  and all('inputSchema' in x for x in rt['spec']['mcp_tool_description']['tools']))
t('health tools are left out: health data never goes to Copilot', not ({'get_health_context', 'propose_health_note'} & set(tool_names)))
t('every function has response semantics with a card (Copilot needs one), fixed text only: no placeholders', all(
  f['capabilities']['response_semantics']['data_path'] == '$' and f['capabilities']['response_semantics']['static_template']['body'][0]['text'] == 'From Alice'
  for f in plug['functions']) and '${' not in json.dumps(plug))
def png_info(b):
    assert b[:8] == b'\x89PNG\r\n\x1a\n'
    w, h, depth, colour = struct.unpack('>IIBB', b[16:26]); return w, h, depth, colour
def rgba_pixels(b):     # our own outline PNG: one IDAT, filter 0 on every row
    i, data = 8, b''
    while i < len(b):
        n = struct.unpack('>I', b[i:i + 4])[0]; kind = b[i + 4:i + 8]
        if kind == b'IDAT': data += b[i + 8:i + 8 + n]
        i += 12 + n
    raw, w = zlib.decompress(data), png_info(b)[0]
    rows = [raw[r * (w * 4 + 1) + 1:(r + 1) * (w * 4 + 1)] for r in range(png_info(b)[1])]
    return [tuple(row[k:k + 4]) for row in rows for k in range(0, len(row), 4)]
col, out = z.read('color.png'), z.read('outline.png')
t('icons are the sizes Teams needs', png_info(col)[:2] == (192, 192) and png_info(out)[:2] == (32, 32) and png_info(out)[3] == 6)
px = rgba_pixels(out)
t('the outline icon is white on transparent, with something drawn', all(a == 0 or (r, g, b) == (255, 255, 255) for r, g, b, a in px) and sum(1 for p in px if p[3]) > 60)

d = zipfile.ZipFile(io.BytesIO(CP.build(URL.replace('alice-mcp', 'alice-demo-mcp'), AUTH, demo=True)))
dm, da, dp = (json.loads(d.read(n)) for n in ('manifest.json', 'declarativeAgent.json', 'alice-plugin.json'))
t('live Alice can use your email, chats, meetings, people, files and the web', {c['name'] for c in agent['capabilities']} ==
  {'Email', 'TeamsMessages', 'Meetings', 'People', 'OneDriveAndSharePoint', 'WebSearch'} and 'Never save anything from email' in agent['instructions'])
t('the demo agent never gets them: it is shown to clients', 'capabilities' not in da and 'Never save anything from email' not in da['instructions'])
lite = zipfile.ZipFile(io.BytesIO(CP.build(URL, AUTH, work_data=False, version='1.2.2')))
la, lm = json.loads(lite.read('declarativeAgent.json')), json.loads(lite.read('manifest.json'))
t('--alice-only leaves out Copilot\'s own data (for a user without the full licence), with its own version', 'capabilities' not in la
  and 'Never save anything from email' not in la['instructions'] and lm['version'] == '1.2.2')
try: CP.build(URL, AUTH, version='v2'); t('refused: a version that is not three numbers', False)
except ValueError: t('refused: a version that is not three numbers', True)
t('the demo has its own icon', d.read('color.png') != z.read('color.png') and png_info(d.read('color.png'))[:2] == (192, 192))
t('the demo package is its own app, clearly marked', dm['id'] == CP.APP_ID_DEMO and dm['name']['short'] == 'Alice (demo)'
  and da['instructions'].startswith('THIS IS THE DEMO ALICE') and dp['namespace'] == 'alicedemo' and 'fictional' in dm['description']['full'])

for label, url, auth in [('not https', URL.replace('https', 'http'), AUTH), ('not the /mcp address', URL.replace('/mcp', '/admin'), AUTH),
                         ('no auth config ID', URL, ''), ('auth ID with odd characters', URL, 'x"; drop')]:
    try: CP.build(url, auth); t('refused: ' + label, False)
    except ValueError: t('refused: ' + label, True)

# the endpoint accepts Copilot's SSO tokens
TEN, APP, ME = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333'
STORE, SSO_URI = 'ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b', 'api://auth-0f0e0d0c-1111-2222-3333-444455556666'
ENV = {'ALICE_EXT_TENANT_ID': TEN, 'ALICE_EXT_APP_ID': APP, 'ALICE_EXT_ALLOWED_USERS': ME,
       'ALICE_EXT_CALLERS': f'{STORE}=Microsoft Copilot:copilot', 'ALICE_EXT_BASE_URL': 'https://alice.example.com',
       'ALICE_EXT_AUDIENCES': SSO_URI + ', api://auth-second-registration/' + APP}
cfg = X.load_config(ENV)
t('the SSO registrations\' URIs are accepted audiences, with the usual two', cfg.audiences[:2] == [APP, 'api://' + APP] and SSO_URI in cfg.audiences and len(cfg.audiences) == 4)
t('without the setting nothing changes', X.load_config({k: v for k, v in ENV.items() if k != 'ALICE_EXT_AUDIENCES'}).audiences == [APP, 'api://' + APP])
for bad in ['https://evil.example', 'api://has space', 'api://"quote"']:
    try: X.load_config({**ENV, 'ALICE_EXT_AUDIENCES': bad}); t('refused audience: ' + bad, False)
    except ValueError: t('refused audience: ' + bad, True)
keys = RSAKeyPair.generate()
ver = X.EntraVerifier(cfg, public_key=keys.public_key)
def tok(aud, app_claim=STORE, oid=ME):
    return keys.create_token(subject=oid, issuer=cfg.issuers[1], audience=aud, expires_in_seconds=600,
                             additional_claims={'tid': TEN, 'oid': oid, 'appid': app_claim, 'scp': 'access_as_user'})
ok = lambda token: asyncio.run(ver.load_access_token(token)) is not None
t('a Copilot SSO token (token store, SSO audience) is accepted', ok(tok(SSO_URI)))
t('the caller is labelled Microsoft Copilot', cfg.callers[STORE].label == 'Microsoft Copilot' and cfg.callers[STORE].provider == 'copilot')
t('refused: an audience nobody registered', not ok(tok('api://auth-someone-else')))
t('refused: another user through Copilot', not ok(tok(SSO_URI, oid='44444444-4444-4444-8444-444444444444')))
t('refused: another client app with the SSO audience', not ok(tok(SSO_URI, app_claim='66666666-6666-4666-8666-666666666666')))
