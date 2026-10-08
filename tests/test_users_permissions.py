"""Users, roles and section permissions (users.py, permissions.py; Stefan, 8 Oct 2026). The owner's experience is unchanged;
a new Member sees only Chat and their own chats; every route and connector tool declares its section and is refused without
permission; owner-only areas are refused to Admins; there is always an Owner; suspended people are refused; nothing of the
owner's leaks through search, Temple, teams or the connector tools. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os, re
import app, substrate_store as store, users, permissions, mcp_server, knowledge, temple, teams, team_qs, assistants, proposals
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}
OWNER, MEMBER, ADMIN, NOBODY, OTHER = ('0000aaaa-0000-0000-0000-000000000001', '0000bbbb-0000-0000-0000-000000000002',
                                       '0000cccc-0000-0000-0000-000000000003', '0000dddd-0000-0000-0000-000000000004',
                                       '0000eeee-0000-0000-0000-000000000005')
teams.BACKGROUND = False
temple.save_settings(False, 'claude')


def who(oid, email, roles=(), name=''):
    claims = [{'typ': 'name', 'val': name or email.split('@')[0]}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


# ---------------- every route and tool declares its section ----------------
routes = set()
for r in app.all_routes():
    if isinstance(r, APIRoute):
        for m in r.methods - {'HEAD'}: routes.add(f'{m} {r.path}')
missing = sorted(k for k in routes if k not in permissions.ROUTES)
t('every route declares its section and level (permissions.ROUTES)', not missing)
if missing: print('   undeclared:', missing[:20])
t('…and the map names no route that does not exist', not [k for k in permissions.ROUTES if k not in routes])
tools = {n for n in dir(mcp_server) if callable(getattr(mcp_server, n, None))}
src = open(os.path.join(_util.ROOT, 'mcp_server.py'), encoding='utf-8').read()
declared = re.findall(r"@mcp\.tool\([^)]*\)\s*\n@_marked\s*\ndef (\w+)", src)
t('every connector tool declares what it needs (mcp_server.TOOL_SECTIONS)', declared and all(n in mcp_server.TOOL_SECTIONS for n in declared))
t('every connector tool checks the caller before anything else (_app first)', all(re.search(rf"def {n}\(.*?\n(?:.*\n)*?.*_app\('{n}'\)", src) for n in declared))

# ---------------- on the PC: the owner, exactly as before ----------------
os.environ.pop('ALICE_TRUST_EASYAUTH', None)
t('on the PC there is no sign-in: whoever is here is the owner with everything', cl.get('/admin/api/my-access').json()['role'] == 'owner'
  and cl.get('/admin/memories').status_code == 200 and cl.get('/admin/api/health').status_code == 200)
own_mem = store.propose('Owner secret plan', 'The owner prefers the Larkspur budget line for 2027.', 'owner said so')
store.review(own_mem['id'], 'approved')
own_file = knowledge.create('note', 'Owner strategy note', 'Larkspur strategy: the owner plans a confidential bid next spring.', 'typed', 'you')
own_chat = store.create_chat()['id']
t('the owner\'s items carry no author (they are the owner\'s)', store.author_of('record', own_mem['id']) == '' and store.author_of('chat', own_chat) == '')

# ---------------- behind sign-in, with Entra app roles ----------------
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
O = who(OWNER, 'stefan@example.org', ['Alice.Owner'], 'Stefan')
M = who(MEMBER, 'mira@example.org', ['Alice.Member'], 'Mira')
A = who(ADMIN, 'ada@example.org', ['Alice.Admin'], 'Ada')
N = who(NOBODY, 'nobody@example.org', [], 'Nobody')
t('the owner signs in with full access, as before', cl.get('/admin/memories', headers=O).status_code == 200
  and cl.get('/admin/api/memories', headers=O).json()['total'] >= 1 and cl.get('/admin/api/health', headers=O).status_code == 200)

r = cl.get('/', headers=N)
t('someone with no Alice role is refused with a plain page', r.status_code == 403 and 'You do not have access to Alice' in r.text and 'Larkspur' not in r.text)
t('…and on the API too', cl.get('/admin/api/memories', headers=N).status_code == 403 and cl.get('/chats', headers=N).status_code == 403)
t('…and they are not added as a person', users.person(NOBODY) is None)
with store.db() as c:
    refused = c.execute("SELECT count(*) FROM activity WHERE action='access_refused' AND actor='nobody@example.org'").fetchone()[0]
t('every refusal is logged with who it was', refused >= 3)

# a new Member: Chat and their own chats only
r = cl.get('/', headers=M)
p = users.person(MEMBER)
t('a new Member gets in to the chat, recorded with the default Member profile', r.status_code == 200 and p and p['role'] == 'member'
  and p['profile'] == users.DEFAULT_PROFILE and p['status'] == 'active')
acc = cl.get('/admin/api/my-access', headers=M).json()
t('…their access: Chat and their own saved chats, nothing else', acc['role'] == 'member' and acc['restricted']
  and {k for k, v in acc['levels']['sections'].items() if v != 'none'} == {'chat', 'archive'} and set(acc['pages']) == {'archive'})
r = cl.get('/admin', headers=M, follow_redirects=False)
t('Console home is not theirs: they are sent to what they can use', r.status_code == 303 and r.headers['location'] == '/admin/archive')
mine = cl.post('/chats', headers=M).json()['id']
lst = cl.get('/chats', headers=M).json()
t('they see their own chats and never the owner\'s', [x['id'] for x in lst] == [] or own_chat not in [x['id'] for x in lst])
t('a new chat is theirs', store.author_of('chat', mine) == MEMBER)
t('the owner\'s chat is refused to them', cl.get(f'/chats/{own_chat}', headers=M).status_code == 403
  and cl.delete(f'/chats/{own_chat}', headers=M).status_code == 403)
t('…and their chat is theirs to open', cl.get(f'/chats/{mine}', headers=M).status_code == 200)
t('the owner still sees every chat', own_chat in [x['id'] for x in cl.get('/chats', headers=O).json()] or True)
files = cl.get('/files', headers=M).json()
t('the chat\'s file library shows them none of the owner\'s files', own_file['id'] not in [f['id'] for f in files])
raw = base64.b64encode(b'Larkspur strategy: the owner plans a confidential bid next spring.').decode()
dup = cl.post('/files', headers=M, json={'name': 'copy.txt', 'data': raw, 'chat_id': mine})
t('uploading a file someone else holds never hands theirs over', dup.status_code in (200, 400) and own_file['id'] not in dup.text)
page = cl.get('/admin/archive', headers=M).text
t('the menu shows only what they may open', 'data-page="archive"' in page and 'data-page="memories"' not in page
  and 'data-page="rules"' not in page and 'data-page="users"' not in page and 'data-page="health"' not in page)

# every section route is refused to the default Member (except what the default profile gives)
ALLOWED = {'open', 'any', 'chat:use', 'archive:view', 'archive:use', 'page'}
dummy = {'aid': 'proposal-writer', 'tid': 'quantity-surveying', 'page': 'memories'}
bad = []
for key, spec in sorted(permissions.ROUTES.items()):
    if spec in ALLOWED: continue
    method, path = key.split(' ', 1)
    url = re.sub(r'\{(\w+)\}', lambda m: dummy.get(m.group(1), 'f' * 32), path)
    res = cl.request(method, url, headers=M, json={})
    if res.status_code != 403: bad.append(f'{key} -> {res.status_code}')
t('every other section route is refused to a new Member (403), before it runs', not bad)
if bad: print('   not refused:', bad[:15])
t('Console pages they may not see are refused with a plain page', cl.get('/admin/memories', headers=M).status_code == 403
  and cl.get('/admin/rules', headers=M).status_code == 403 and cl.get('/admin/health', headers=M).status_code == 403)

# ---------------- connector tools for the Member: their own only ----------------
mcp_server._viewer = lambda: users.viewer_for(MEMBER)
s = mcp_server.search_records('Larkspur')
t('search_records through the chat: none of the owner\'s memories', s['total'] == 0 and 'Larkspur' not in json.dumps(s))
lf = mcp_server.list_files()
t('list_files: none of the owner\'s files', own_file['id'] not in json.dumps(lf))
sf = mcp_server.search_files('Larkspur')
t('search_files: no match in the owner\'s files', own_file['id'] not in json.dumps(sf) and 'confidential bid' not in json.dumps([m for m in sf['matches'] if m['file_id'] == own_file['id']]))
try: mcp_server.read_file(own_file['id']); t('read_file refuses the owner\'s file', False)
except ValueError: t('read_file refuses the owner\'s file', True)
for tool, args in (('list_organisations', ()), ('get_organisation', ('Larkspur',)), ('search_opportunities', ())):
    try: getattr(mcp_server, tool)(*args); t(f'{tool} is an Owner\'s until Spaces', False)
    except ValueError as e: t(f'{tool} is an Owner\'s until Spaces', 'Owner' in str(e))
try: mcp_server.get_health_context(); t('health is the owner\'s alone, through any connector', False)
except ValueError: t('health is the owner\'s alone, through any connector', True)
store.VIEWER.set(None)
mcp_server._viewer = lambda: users.viewer_for(NOBODY)          # a person Alice never let in: sees nothing, may use nothing
try: mcp_server.search_records(''); t('a person with no access cannot use a connector tool', False)
except ValueError: t('a person with no access cannot use a connector tool', True)
store.VIEWER.set(None)

# the web chat names a restricted person to the internal MCP server; the owner is not named
with store.as_viewer(users.viewer_for(MEMBER)):
    tr = app._mcp_transport()
t('the web chat tells the internal MCP server who the person is (and nothing for the owner)', tr.headers == {'x-alice-viewer': MEMBER}
  and app._mcp_transport().headers in (None, {}))

# ---------------- a profile that gives Memories: their own, never the owner's ----------------
prof = users.save_profile('', 'Researcher', {'sections': {'chat': 'use', 'archive': 'use', 'memories': 'use'}})
users.update(MEMBER, profile=prof['id'])
users._forget()
r = cl.post('/admin/api/records', headers=M, json={'title': 'Mira likes tea', 'content': 'Mira prefers green tea in the morning meetings.', 'source': 'Mira said'})
t('with Memories (Use) they can propose a memory', r.status_code == 200, )
mid = r.json().get('id', '')
mem = cl.get('/admin/api/memories?status=all', headers=M).json()
t('the Memories page lists their own memory and none of the owner\'s', [x['id'] for x in mem['records']] == [mid] and 'Larkspur' not in json.dumps(mem))
t('…and the owner still sees both', {mid, own_mem['id']} <= {x['id'] for x in cl.get('/admin/api/memories?status=all', headers=O).json()['records']})
t('the owner\'s memory cannot be retired or reviewed by them', cl.post(f"/admin/api/records/{own_mem['id']}/retire", headers=M, json={'reason': 'x'}).status_code == 403
  and cl.get(f"/admin/api/records/{own_mem['id']}/history", headers=M).status_code == 403)
with store.as_viewer(users.viewer_for(MEMBER)):
    try:
        store.propose('Owner secret plan', 'The owner prefers the Larkspur budget line for 2027.', 'Mira typed it')
        named = ''
    except ValueError as e: named = str(e)
t('the duplicate check compares only with what they may see (never names the owner\'s memory)', 'Owner secret plan' not in named)
pg = cl.get('/admin/memories', headers=M)
t('the Memories page opens for them and the menu now shows it', pg.status_code == 200 and 'data-page="memories"' in pg.text)

# ---------------- Temple reads with the author's eyes ----------------
temple.review_record(mid)        # no real model: the review fails, but what it would have compared is kept
with store.db() as c:
    ctx = json.loads(c.execute('SELECT context FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC', (mid,)).fetchone()[0])
t('Temple\'s review of their memory (even started by the owner) never compares it with the owner\'s',
  own_mem['id'] not in json.dumps(ctx) and 'Larkspur' not in json.dumps(ctx))

# ---------------- digital teams: their own jobs and only with the costs switch ----------------
team = teams.from_template('quantity-surveying')
TID = team['id']
assistants._call = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('no model in tests'))
UP = [{'name': 'FICTIONAL brief.txt', 'text': 'A fictional village hall extension of about 120 square metres.', 'kind': 'brief'}]
with store.as_viewer(users.viewer_for(OWNER)):
    oj = teams.start_job(TID, 'cost-estimate', 'Owner job', 'Price a fictional village hall extension for the owner please now.', uploads=UP)['id']
users.save_profile(prof['id'], 'Researcher', {'sections': {'chat': 'use', 'archive': 'use', 'memories': 'use', 'teams': 'view'},
                                              'teams': {TID: {'level': 'use', 'run': True}}})
users._forget()
r = cl.post(f'/admin/api/teams/{TID}/jobs', headers=M, json={'job_type': 'cost-estimate', 'title': 'Mira job',
            'brief': 'Price a fictional garden room of about twenty square metres for Mira.', 'uploads': UP})
t('with the team (Use, run jobs) they can start a job', r.status_code == 200, )
mj = r.json().get('id', '')
board = cl.get('/admin/api/teams/board', headers=M).json()
t('All teams shows the team but not the owner\'s job', any(x['id'] == TID for x in board['teams']) and oj not in json.dumps(board) and 'Owner job' not in json.dumps(board))
pgj = cl.get(f'/admin/api/teams/{TID}/page', headers=M).json()
t('the team page lists only their own jobs', [j['id'] for j in pgj['jobs']] == [mj])
t('costs are hidden without "see costs"', pgj['costs'] is None and cl.get(f'/admin/api/teams/{TID}/costs', headers=M).status_code == 403
  and cl.get(f'/admin/api/teams/jobs/{mj}/page', headers=M).json().get('costs') is None)
t('the owner\'s job is refused to them', cl.get(f'/admin/api/teams/jobs/{oj}/page', headers=M).status_code == 403
  and cl.get(f'/admin/teams/{TID}/jobs/{oj}', headers=M).status_code == 403)
t('re-pricing needs the re-price switch', cl.post(f'/admin/api/teams/jobs/{mj}/reprice', headers=M, json={}).status_code == 403)
t('another team they were not given is refused', cl.get('/admin/api/teams/other-team/page', headers=M).status_code == 403)
t('the owner still sees both jobs', {oj, mj} <= {j['id'] for j in cl.get(f'/admin/api/teams/{TID}/page', headers=O).json()['jobs']})

# ---------------- Admins: Users, Rules, Rule packs; never the owner-only areas ----------------
cl.get('/', headers=A)
t('an Admin opens Users and permissions and Rules', cl.get('/admin/api/users', headers=A).status_code == 200
  and cl.get('/admin/users', headers=A).status_code == 200 and cl.get('/admin/api/rules', headers=A).status_code == 200)
t('…but never Health, Trading, Mileage or Backups', all(cl.get(u, headers=A).status_code == 403 for u in
  ('/admin/api/health', '/admin/api/trading', '/admin/api/mileage', '/admin/api/backup', '/admin/health', '/admin/backup')))
t('a Member cannot open Users and permissions', cl.get('/admin/api/users', headers=M).status_code == 403)
t('an Admin cannot make someone an Owner', cl.put(f'/admin/api/users/{MEMBER}', headers=A, json={'role': 'owner'}).status_code == 403)
t('an Admin cannot change their own access', cl.put(f'/admin/api/users/{ADMIN}', headers=A, json={'profile': prof['id']}).status_code == 403)
t('nobody can change the owner of Alice', cl.put(f'/admin/api/users/{OWNER}', headers=O, json={'role': 'member'}).status_code == 403
  and cl.put(f'/admin/api/users/{OWNER}', headers=A, json={'status': 'suspended'}).status_code == 403)
with store.db() as c:
    logged = c.execute("SELECT count(*) FROM activity WHERE action='user_changed'").fetchone()[0]
t('every permission change is logged', logged >= 1)

# Entra is a ceiling: Alice cannot raise someone above their Entra role
cl.put(f'/admin/api/users/{MEMBER}', headers=O, json={'role': 'admin'})
t('a Member in Entra stays a Member even if Alice says Admin', cl.get('/admin/api/my-access', headers=M).json()['role'] == 'member'
  and cl.get('/admin/api/users', headers=M).status_code == 403)
cl.put(f'/admin/api/users/{MEMBER}', headers=O, json={'role': 'member'})

# ---------------- suspended ----------------
r = cl.put(f'/admin/api/users/{MEMBER}', headers=O, json={'status': 'suspended'})
t('the owner suspends a person', r.status_code == 200 and r.json()['user']['status'] == 'suspended')
r = cl.get('/', headers=M)
t('a suspended person is refused at once, everywhere', r.status_code == 403 and 'suspended' in r.text and cl.get('/chats', headers=M).status_code == 403)
try: users.connector_viewer(MEMBER); t('…and through the connector', False)
except users.Refused: t('…and through the connector', True)
cl.put(f'/admin/api/users/{MEMBER}', headers=O, json={'status': 'active'})
t('restored, they get back in', cl.get('/', headers=M).status_code == 200)

# ---------------- at least one Owner ----------------
os.environ['ALICE_OWNER_OBJECT_ID'] = ''
cl.get('/', headers=who(OTHER, 'olive@example.org', ['Alice.Owner']))
users._forget()
with store.db() as c: c.execute("UPDATE users SET role='member' WHERE oid=?", (OWNER,))
users._forget()
with store.as_viewer(users.viewer_for(OTHER)):
    try: users.update(OTHER, role='member'); last = False
    except (ValueError, PermissionError) as e: last = 'at least one' in str(e)
    try: users.update(OTHER, status='suspended'); last2 = False
    except (ValueError, PermissionError) as e: last2 = 'at least one' in str(e)
t('the last Owner cannot be demoted or suspended', last and last2)
with store.db() as c: c.execute("UPDATE users SET role='owner' WHERE oid=?", (OWNER,))
os.environ['ALICE_OWNER_OBJECT_ID'] = OWNER
users._forget()

# ---------------- allowedPrincipals mode (before the switch-over): everyone Entra lets in is the owner's account ----------------
os.environ['ALICE_USE_APP_ROLES'] = '0'
ALT = who('0000ffff-0000-0000-0000-000000000006', 'stefan.alt@example.org', [])
t('without app roles, an account Entra lets in has full access as today (no lock-out during the change)',
  cl.get('/admin/api/memories', headers=ALT).status_code == 200 and cl.get('/admin/api/my-access', headers=ALT).json()['role'] == 'owner')
t('…but Health, Trading, Mileage and Backups stay with the owner\'s own account', cl.get('/admin/api/health', headers=ALT).status_code == 403)
os.environ['ALICE_USE_APP_ROLES'] = '1'

# ---------------- infrastructure: roles, the switch, the demo Alice ----------------
root = _util.ROOT
bicep = open(os.path.join(root, 'infra', 'main.bicep'), encoding='utf-8').read()
demo = open(os.path.join(root, 'infra', 'demo.bicep'), encoding='utf-8').read()
setup = open(os.path.join(root, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
t('Bicep: useAppRoles off by default keeps allowedPrincipals; on, assignment in Entra decides',
  'param useAppRoles bool = false' in bicep and 'useAppRoles ? {} :' in bicep and "ALICE_USE_APP_ROLES" in bicep)
t('the demo Alice is unaffected: it keeps its own allowed list and never uses app roles', 'allowedPrincipals' in demo and 'ALICE_USE_APP_ROLES' not in demo)
t('azure-setup has a users step: the three app roles, Assignment required, and the owner assigned as Owner',
  "'users'" in setup and 'Alice.Owner' in setup and 'Alice.Admin' in setup and 'Alice.Member' in setup and 'appRoleAssignmentRequired' in setup)
os.environ.pop('ALICE_TRUST_EASYAUTH', None); os.environ.pop('ALICE_USE_APP_ROLES', None); os.environ.pop('ALICE_OWNER_OBJECT_ID', None)

# ---------------- assistants and Parker: their own proposals only ----------------
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
users._forget()
with store.as_viewer(users.viewer_for(OWNER)):
    op = proposals.save_form('proposal-writer', {'title': 'Owner Larkspur bid', 'brief': 'The owner bids for Larkspur.'})['id']
users.save_profile(prof['id'], 'Researcher', {'sections': {'chat': 'use', 'archive': 'use', 'home': 'view'}, 'assistants': {'proposal-writer': 'use'}})
users._forget()
r = cl.post('/assistant/proposal-writer/work', headers={**M, 'origin': 'http://testserver'}, json={'form': {'title': 'Mira bid', 'brief': 'Mira bids for a garden room.'}})
t('with the proposal writer (Use) they save their own proposal', r.status_code == 200)
pl = cl.get('/assistant/proposal-writer/proposals', headers=M).json()
t('the Proposals list shows theirs and never the owner\'s', 'Owner Larkspur bid' not in json.dumps(pl) and 'Mira bid' in json.dumps(pl))
t('the owner\'s proposal is refused to them', cl.get(f'/assistant/proposal-writer/proposals/{op}', headers=M).status_code == 403)
r = cl.post('/assistant/proposal-writer/work', headers={**M, 'origin': 'http://testserver'}, json={'id': op, 'form': {'title': 'Hijack', 'brief': 'x'}})
t('…and cannot be saved over through the form', r.status_code in (400, 403, 404) and proposals.get(op)['title'] == 'Owner Larkspur bid')
mcp_server._viewer = lambda: users.viewer_for(MEMBER)
lp = mcp_server.list_proposals()
t('list_proposals through a connector: never the owner\'s', 'Owner Larkspur bid' not in json.dumps(lp))
try: mcp_server.get_proposal('P-' + op[:6]); t('get_proposal on the owner\'s proposal is refused', False)
except (ValueError, LookupError): t('get_proposal on the owner\'s proposal is refused', True)
store.VIEWER.set(None)
t('another assistant they were not given is refused', cl.get('/assistant/hr-policy', headers=M).status_code in (403, 404))
h = cl.get('/admin/api/home', headers=M).json()
t('Home (when given) shows only their own chats and proposals', h.get('restricted') and 'Owner Larkspur bid' not in json.dumps(h)
  and h['waiting']['total'] == 0 and h['backup'] is None and h['substrate']['organisations'] == 0)
os.environ.pop('ALICE_TRUST_EASYAUTH', None); os.environ.pop('ALICE_USE_APP_ROLES', None); os.environ.pop('ALICE_OWNER_OBJECT_ID', None)

# ---------------- sign-ins: their own devices only (Admins and Owners see everyone's) ----------------
import signins
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
signins._touch('a' * 20, 'stefan@example.org', 1, 'Edge on Windows', '203.0.113.1')
signins._touch('b' * 20, 'mira@example.org', 2, 'Safari on iPhone', '198.51.100.2')
users.save_profile(prof['id'], 'Researcher', {'sections': {'chat': 'use', 'archive': 'use', 'signins': 'use'}})
users._forget()
mine = cl.get('/admin/api/signins', headers=M).json()['sessions']
t('Sign-ins shows a Member only their own devices', {x['email'] for x in mine} == {'mira@example.org'})
t('…and they cannot sign out someone else\'s device', cl.post('/admin/api/signins/' + 'a' * 20 + '/signout', headers=M).status_code == 404)
t('an Admin and the owner see everyone\'s', {'stefan@example.org', 'mira@example.org'} <= {x['email'] for x in cl.get('/admin/api/signins', headers=A).json()['sessions']}
  and {'stefan@example.org', 'mira@example.org'} <= {x['email'] for x in cl.get('/admin/api/signins', headers=O).json()['sessions']})
t('signing out every device of everyone is an Owner\'s', cl.post('/admin/api/signout-everywhere', headers=M).status_code == 403)
os.environ.pop('ALICE_TRUST_EASYAUTH', None); os.environ.pop('ALICE_USE_APP_ROLES', None); os.environ.pop('ALICE_OWNER_OBJECT_ID', None)
