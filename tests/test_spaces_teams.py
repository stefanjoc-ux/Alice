"""Open by default (decision D-0040, design CR-4 phase 1; Stefan, 10 Oct 2026): the Organisation space everyone with an Alice role
reads; team spaces readable across the organisation unless a manager closes them (rule open_spaces); organisations as a shared
directory whose facts from internal sources show only to people who can see their space; Entra group mappings applied at sign-in
and daily, removed on leaving; the "Team member" profile; the move into the Organisation space previewed with counts first;
Temple, search and every connector tool respecting all of it. Every object ID, name and item is fictional. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os
os.environ['ALICE_OWNER_NAME'] = 'Stefan'
import substrate_store as store
import app
import users, spaces, groups, knowledge, memory_tags, temple, assistants, mcp_server, organisations, clients, rules_engine, permissions
from fastapi.testclient import TestClient

OWNER, ADMIN, MIRA, NIA, SAM = ('0000f955-0000-4000-8000-000000000001', '0000e610-0000-4000-8000-000000000002',
                                '0000b1b1-0000-4000-8000-000000000003', '0000c2c2-0000-4000-8000-000000000004',
                                '0000d3d3-0000-4000-8000-000000000005')
G_HR, G_SALES = 'a1a1a1a1-0000-4000-8000-00000000000a', 'b2b2b2b2-0000-4000-8000-00000000000b'
temple.save_settings(False, 'claude')
spaces.BACKGROUND = False
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}
SCREENS = []


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    if workload == 'Temple sharing check':
        SCREENS.append(messages[0]['content'])
        return json.dumps({'finding': False, 'findings': [], 'clear_because': 'Ordinary work content.'})
    raise RuntimeError('no model in tests')


assistants._call = fake_call


def who(oid, email, roles=(), grps=None):
    claims = [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]
    claims += [{'typ': 'groups', 'val': g} for g in (grps or [])]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
E = who(OWNER, 'stefan@example.org', ['Alice.Owner'])
A = who(ADMIN, 'admin@example.org', ['Alice.Admin'])
M = who(MIRA, 'mira@example.org', ['Alice.Member'])
N = who(NIA, 'nia@example.org', ['Alice.Member'])
S = who(SAM, 'sam@example.org', ['Alice.Member'])
for h in (E, A, M, N, S): cl.get('/', headers=h)
users._forget(); spaces.forget()
store.create_category('Work'); memory_tags.set_category_area('Work', 'work')
V = lambda oid: users.viewer_for(oid)


def sees(oid, kind, iid):
    with store.as_viewer(V(oid)): return store.can_see(kind, iid)


def item(title, content, space, cat='Work', viewer=None):
    with store.as_viewer(viewer):
        rid = store.propose(title, content, 'said so')['id']
    store.review(rid, 'approved'); store.set_category([rid], cat)
    spaces._place('record', rid, space)
    return rid


# ---------------- the Organisation space ----------------
O = spaces.ORG
t('the Organisation space exists once, made at start-up', spaces.names().get(O, {}).get('kind') == 'organisation')
note = knowledge.create('note', 'Travel policy', 'Book rail travel through the travel desk at least a week ahead.', 'typed', 'you', category='Work')['id']
spaces._place('file', note, O)
t('every role reads the Organisation space: Owner, Admin and Members', all(sees(x, 'file', note) for x in (OWNER, ADMIN, MIRA, NIA)))
cl.put(f'/admin/api/users/{SAM}', headers=E, json={'status': 'suspended'}); users._forget(); spaces.forget()
t('…but never someone suspended', not sees(SAM, 'file', note))
cl.put(f'/admin/api/users/{SAM}', headers=E, json={'status': 'active'}); users._forget(); spaces.forget()
with store.as_viewer(V(NIA)):
    t('a Member reads it but cannot add to it (the default profile)', spaces.role_in(V(NIA), O) == 'view' and not spaces.may_contribute(V(NIA), O))
    t('Admins manage it', spaces.role_in(V(ADMIN), O) == 'manage')
prof = next(p for p in users.profiles_list() if p['id'] == users.TEAM_PROFILE)
L = prof['levels']['sections']
t('the built-in "Team member" profile: Chat, Knowledge use; Organisations, Memories view; assistants and digital teams to use',
  L['chat'] == 'use' and L['knowledge'] == 'use' and L['organisations'] == 'view' and L['memories'] == 'view'
  and prof['levels']['assistants'].get('*') == 'use' and prof['levels']['teams']['*']['level'] == 'use' and prof['builtin'])
cl.put(f'/admin/api/users/{MIRA}', headers=E, json={'profile': users.TEAM_PROFILE})
users._forget(); spaces.forget()

# ---------------- team spaces: open by default, closed by a manager ----------------
r = cl.post('/admin/api/spaces', headers=E, json={'name': 'Sales', 'description': 'The sales team'})
SALES = r.json()['id']
cl.put(f'/admin/api/spaces/{SALES}/members', headers=E, json={'member': MIRA, 'role': 'manage'})
pitch = item('Pitch deck rule', 'Every pitch deck ends with a one-slide summary of the price.', SALES)
t('with the rule off (as in tests), a team space is its members\' only', sees(MIRA, 'record', pitch) and not sees(NIA, 'record', pitch))
with store.db() as c: c.execute("UPDATE rules SET enabled=1 WHERE id='open_spaces'")
rules_engine._rules_changed(); spaces.forget()
t('the rule on (the default): every team space is readable across the organisation', sees(NIA, 'record', pitch) and sees(ADMIN, 'record', pitch))
with store.as_viewer(V(NIA)):
    t('…to read only: a reader cannot add to it', not spaces.may_contribute(V(NIA), SALES))
t('a Member who does not manage it cannot close it', cl.put(f'/admin/api/spaces/{SALES}/closed', headers=N, json={'closed': True, 'reason': 'x'}).status_code == 403)
t('closing needs a reason', cl.put(f'/admin/api/spaces/{SALES}/closed', headers=M, json={'closed': True}).status_code == 400)
r = cl.put(f'/admin/api/spaces/{SALES}/closed', headers=M, json={'closed': True, 'reason': 'Pricing strategy under negotiation'})
t('its manager closes it, with a reason', r.status_code == 200)
t('a closed space is not readable outside it', not sees(NIA, 'record', pitch) and sees(MIRA, 'record', pitch))
with store.db() as c:
    logged = c.execute("SELECT note, detail FROM activity WHERE action='space_closed' ORDER BY id DESC").fetchone()
t('…and the closing is logged with the reason', logged and 'Pricing strategy' in logged['detail'] and logged['note'])
cl.put(f'/admin/api/spaces/{SALES}/closed', headers=M, json={'closed': False})
t('opened again, everyone reads it', sees(NIA, 'record', pitch))
with store.as_viewer(V(MIRA)): spaces.set_default(spaces.personal_space(MIRA))   # her own choice: nothing queued for her team space
personal = item('Bullet points', 'Mira prefers bullet points in summaries.', spaces.personal_space(MIRA), viewer=V(MIRA))
with store.as_viewer(V(MIRA)): spaces.set_default('')
t('a personal space is never open', not sees(NIA, 'record', personal) and not sees(OWNER, 'record', personal))

# ---------------- organisations: a shared directory, internal facts stay in their space ----------------
organisations.create('Fernley Council', 'council', 'A fictional council.')
t('a new organisation goes into the Organisation space (the directory)', spaces.space_of('organisation', 'Fernley Council') == O)
with store.as_viewer(None):
    pub = organisations.propose_fact('Fernley Council', 'technology', 'Fernley Council runs Microsoft 365 across all departments.',
                                     'Fernley Council website', 'https://fernley.example.org/it', by='you')['id']
with store.as_viewer(V(MIRA)):
    spaces.set_default(SALES)
    internal = organisations.propose_fact('Fernley Council', 'relationship', 'Fernley Council prefers fixed-price bids after the 2025 overspend.',
                                          'Sales meeting notes 3 October', by='you')['id']
    spaces.set_default('')
t('a public fact goes with its organisation; an internal one stays in the space it came from',
  spaces.space_of('org_fact', pub) == spaces.default_space() and spaces.space_of('org_fact', internal) == SALES)
cl.put(f'/admin/api/spaces/{SALES}/closed', headers=M, json={'closed': True, 'reason': 'Bid strategy'})


def facts_for(oid):
    with store.as_viewer(V(oid)): return {f['id'] for f in organisations.facts('Fernley Council', 'all')}


t('the internal fact shows on the profile only to people who can see its space', facts_for(MIRA) == {pub, internal} and facts_for(NIA) == {pub})
r = cl.get('/admin/api/organisations/facts?org=Fernley%20Council', headers=N)
t('…on the Organisations page too (a Member with Organisations at View)', r.status_code in (200, 403) and 'fixed-price' not in r.text)
r = cl.get('/admin/api/organisations/facts?org=Fernley%20Council', headers=M)
t('…and Mira (Team member: Organisations at View) reads the directory with the internal fact', r.status_code == 200 and 'fixed-price' in r.text)

# ---------------- every connector tool, Temple and search ----------------
mcp_server._viewer = lambda: V(NIA)
g = json.dumps(mcp_server.get_organisation('Fernley Council'))
t('get_organisation: the public fact, never the internal one from a closed space', 'Microsoft 365' in g and 'fixed-price' not in g)
t('list_organisations: the directory', 'Fernley Council' in json.dumps(mcp_server.list_organisations()))
t('search_records: the Organisation space and open spaces, never a closed one', pitch not in json.dumps(mcp_server.search_records('pitch')))
t('list_files and search_files: the Organisation space\'s knowledge', note in json.dumps(mcp_server.list_files())
  and note in json.dumps(mcp_server.search_files('travel')))
t('read_file: readable from the Organisation space', 'travel desk' in json.dumps(mcp_server.read_file(note)))
sp = mcp_server.list_spaces()
t('list_spaces: the Organisation space to read, no closed space', O in {x['id'] for x in sp['spaces']} and SALES not in {x['id'] for x in sp['spaces']})
store.VIEWER.set(None)
mcp_server._viewer = lambda: V(MIRA)
t('a member of the closed space still finds it through the connector', pitch in json.dumps(mcp_server.search_records('pitch')))
store.VIEWER.set(None)
with store.as_viewer(V(NIA)):
    mine = store.propose('Nia plan', 'Nia wants every pitch deck checked by a second reader.', 'Nia')['id']
temple.review_record(mine)
with store.db() as c:
    ctx = c.execute('SELECT context FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC', (mine,)).fetchone()[0]
t('Temple compares only with what the person may read: not the closed space', pitch not in ctx)
cl.put(f'/admin/api/spaces/{SALES}/closed', headers=M, json={'closed': False})
temple.review_record(mine)
with store.db() as c:
    ctx = c.execute('SELECT context FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC', (mine,)).fetchone()[0]
t('…and the open space once it is open again', pitch in ctx)

# ---------------- Entra group mappings ----------------
r = cl.post('/admin/api/spaces', headers=A, json={'name': 'HR', 'description': 'HR policy work'})
HR = r.json()['id']
t('a Member cannot map groups', cl.post('/admin/api/groups', headers=N, json={'group_id': G_HR, 'spaces': [{'space': HR, 'role': 'contribute'}]}).status_code == 403)
t('a personal space can never be mapped', cl.post('/admin/api/groups', headers=A, json={'group_id': G_HR, 'spaces': [{'space': spaces.personal_space(NIA), 'role': 'view'}]}).status_code == 400)
r = cl.post('/admin/api/groups', headers=A, json={'group_id': G_HR, 'label': 'HR-Team', 'spaces': [{'space': HR, 'role': 'contribute'}],
                                                  'profile': users.TEAM_PROFILE})
t('an Admin maps an Entra group to a space with a role and a profile', r.status_code == 200 and r.json()['mappings'][0]['label'] == 'HR-Team')
cl.get('/', headers=who(NIA, 'nia@example.org', ['Alice.Member'], [G_HR]))
users._forget(); spaces.forget()
with store.db() as c:
    m = c.execute('SELECT role, via FROM space_members WHERE space_id=? AND member_key=?', (HR, NIA)).fetchone()
t('signing in with the group: she joins the space with that role', m and m['role'] == 'contribute' and m['via'] == 'group:' + G_HR)
t('…and gets the profile', users.person(NIA)['profile'] == users.TEAM_PROFILE)
with store.as_viewer(V(NIA)):
    hr_note = store.propose('Leave policy draft', 'Annual leave requests go through the HR portal two weeks ahead.', 'Nia')['id']
store.review(hr_note, 'approved'); store.set_category([hr_note], 'Work')
spaces._place('record', hr_note, HR)
cl.put(f'/admin/api/spaces/{HR}/members', headers=A, json={'member': SAM, 'role': 'view'})
cl.get('/', headers=who(NIA, 'nia@example.org', ['Alice.Member'], []))
users._forget(); spaces.forget()
with store.db() as c:
    m = c.execute('SELECT 1 FROM space_members WHERE space_id=? AND member_key=?', (HR, NIA)).fetchone()
    sam = c.execute('SELECT via FROM space_members WHERE space_id=? AND member_key=?', (HR, SAM)).fetchone()
t('leaving the group removes the membership it gave', m is None and users.person(NIA)['profile'] == users.DEFAULT_PROFILE)
t('…what she made stays where it is, with her as its author', spaces.space_of('record', hr_note) == HR and store.author_of('record', hr_note) == NIA)
t('…and memberships set by hand are never touched by a group', sam is not None and sam['via'] == '')
with store.db() as c: c.execute('UPDATE users SET groups=?, groups_applied_at=? WHERE oid=?', (json.dumps([G_HR]), '2000-01-01T00:00:00+00:00', NIA))
users._forget()
res = groups.apply_all()
with store.db() as c:
    m = c.execute('SELECT role FROM space_members WHERE space_id=? AND member_key=?', (HR, NIA)).fetchone()
t('the daily pass applies mappings from the groups Alice last saw', res['people'] >= 4 and m and m['role'] == 'contribute')
with store.db() as c:
    acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE rule='users'")}
t('mappings and their effects are logged', {'group_mapping_saved', 'group_access_applied'} <= acts)
cl.put(f'/admin/api/users/{NIA}', headers=E, json={'profile': users.DEFAULT_PROFILE})
cl.get('/', headers=who(NIA, 'nia@example.org', ['Alice.Member'], [G_HR, G_SALES]))
users._forget()
t('a profile set by hand wins over a group\'s', users.person(NIA)['profile'] == users.DEFAULT_PROFILE)

# ---------------- the move into the Organisation space: preview, then exactly that ----------------
W = spaces.WORK
organisations.create('Old Partner Ltd', 'company', 'A fictional partner.')
spaces._place('organisation', 'Old Partner Ltd', W)
gen = knowledge.create('note', 'Expenses guide', 'Claim expenses within thirty days with receipts attached.', 'typed', 'you', category='Work')['id']
loc = knowledge.create('note', 'Internal rate notes', 'Rates for the Fernley bid are under review this quarter.', 'typed', 'you', label='internal', category='Work')['id']
for f in (gen, loc): spaces._place('file', f, W)
with store.as_viewer(None):
    dec = store.propose_decision('Use the travel desk', 'All rail travel is booked through the travel desk.', 'Stefan')['id']
    tagged = store.propose_decision('Fernley pricing', 'Fernley bids are fixed price from now on.', 'Stefan')['id']
for d in (dec, tagged):
    with store.db() as c: c.execute("UPDATE records SET status='approved' WHERE id=?", (d,))
    store.set_category([d], 'Work'); spaces._place('record', d, W)
clients.create_client('Fernley Council') if 'Fernley Council' not in clients.names() else None
clients.tag('memory', [tagged], 'Fernley Council', 'human')
memo = item('Stefan prefers mornings', 'Stefan prefers client calls in the morning.', W)
t('a Member cannot see the preview', cl.get('/admin/api/spaces/organisation/move', headers=N).status_code == 403)
pv = cl.get('/admin/api/spaces/organisation/move', headers=E).json()
ids = lambda k: {x['id'] for x in pv['organisation'][k]}
t('the preview counts what moves (D-0053: everything in the work space is organisational)', pv['counts']['organisations'] >= 1
  and 'Old Partner Ltd' in ids('organisations') and {gen, loc} <= ids('knowledge') and {dec, tagged} <= ids('decisions') and memo in ids('memories')
  and all(pv['counts'][k] == len(pv['organisation'][k]) for k in ('organisations', 'knowledge', 'memories', 'decisions')))
t('…tagged and labelled items are shown with their client and label', any(x['id'] == tagged and x['client'] == 'Fernley Council' for x in pv['organisation']['decisions'])
  and any(x['id'] == loc and x['label'] == 'internal' for x in pv['organisation']['knowledge']))
t('nothing moved by previewing', spaces.space_of('organisation', 'Old Partner Ltd') == W and spaces.space_of('file', gen) == W)
t('confirming with other counts is refused (nothing moves that was not seen)',
  cl.post('/admin/api/spaces/organisation/move', headers=E, json={'counts': {**pv['counts'], 'organisations': 9}}).status_code == 400)
n_screens = len(SCREENS)
r = cl.post('/admin/api/spaces/organisation/move', headers=E, json={'counts': pv['counts']})
st = r.json()
t('the move matches the preview exactly', r.status_code == 200 and st['state'] == 'done' and st['moved'] >= 6
  and spaces.space_of('organisation', 'Old Partner Ltd') == O and spaces.space_of('file', gen) == O and spaces.space_of('record', dec) == O)
t('…each through the sharing check', len(SCREENS) >= n_screens + 6)
t('…client-tagged and internal items move too, keeping their tag and label', spaces.space_of('file', loc) == O and spaces.space_of('record', tagged) == O
  and spaces.space_of('record', memo) == O and clients.client_of('memory', tagged) == 'Fernley Council' and knowledge.meta([loc])[loc]['label'] == 'internal')
t('the internal fact stays pinned to its space when its organisation is in the directory', spaces.space_of('org_fact', internal) == SALES)
with store.db() as c:
    acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE rule='spaces'")}
t('the move is logged with its counts', {'org_migration_started', 'org_migration_done'} <= acts)
t('every role now reads what moved', all(sees(x, 'record', dec) for x in (ADMIN, MIRA, NIA)))
t('the new rule is on the Rules page', any(r_['id'] == 'open_spaces' for r_ in rules_engine.all_rules()))
for k in ('ALICE_TRUST_EASYAUTH', 'ALICE_USE_APP_ROLES', 'ALICE_OWNER_OBJECT_ID'): os.environ.pop(k, None)
