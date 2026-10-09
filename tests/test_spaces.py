"""Spaces: shared team memory with explicit membership (spaces.py; Stefan, 8 Oct 2026). A new person sees nothing shared;
adding them to a space reveals exactly that space; View cannot add; Temple's sharing gate holds a health detail and a third
person's personal data; unclassified items are never shared; connectors, Temple and teams respect spaces; the migration puts
each item where described and loses nothing. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os
import substrate_store as store
import app                    # creates the tables (and, at start-up, places existing items: none yet)
import knowledge, organisations, assistants, memory_tags, teams, temple, clients, proposals, spaces
# This throwaway database stands for one from before spaces: no spaces yet, so the migration below runs on the items made next.
with store.db() as c:
    for tb in ('spaces', 'space_members', 'item_spaces'): c.execute(f'DELETE FROM {tb}')
    c.execute("DELETE FROM settings WHERE key LIKE 'spaces_%'")
spaces._MIGRATED.clear(); spaces.forget()

temple.save_settings(False, 'claude')
teams.BACKGROUND = False
SCREEN = {'reply': {'personal_data': False, 'special_category': False, 'private': False, 'reasons': []}, 'fail': False, 'calls': []}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    if workload == 'Temple sharing check':
        SCREEN['calls'].append(messages[0]['content'])
        if SCREEN['fail']: raise RuntimeError('Temple is unreachable in this test')
        return json.dumps(SCREEN['reply'])
    raise RuntimeError('no model in tests')


assistants._call = fake_call

# ---------------- the owner's data before spaces ----------------
store.create_category('Work'); store.create_category('Family')
memory_tags.set_category_area('Work', 'work'); memory_tags.set_category_area('Family', 'personal')
def mem(title, content, cat=''):
    r = store.propose(title, content, 'the owner said so')
    store.review(r['id'], 'approved')
    if cat: store.set_category([r['id']], cat)
    return r['id']
m_work = mem('Bid style', 'Bids lead with the outcome for the client, then the method and the team.', 'Work')
m_family = mem('School run', 'The owner does the school run on Tuesdays and Thursdays.', 'Family')
m_uncat = mem('Preferred editor', 'The owner drafts proposals in Word, not Google Docs.')
k_work = knowledge.create('note', 'Rate card notes', 'Our standard day rates are reviewed every April by the bid board.', 'typed', 'you', category='Work')['id']
organisations.create('Acme Ltd', 'other', 'A fictional client', client=True)
team = teams.from_template('quantity-surveying')['id']
with store.db() as c:
    before = {t_: c.execute(f'SELECT count(*) FROM {t_}').fetchone()[0] for t_ in ('records', 'files', 'organisations', 'teams')}

spaces.ensure_migrated()
rep = spaces.migration_report()
P, W = rep['personal'], rep['work']
t('migration: personal-area memories go to the owner\'s personal space', spaces.space_of('record', m_family) == P)
t('migration: everything else goes to "<owner>: work"', all(spaces.space_of('record', x) == W for x in (m_work, m_uncat))
  and spaces.space_of('file', k_work) == W and spaces.space_of('organisation', 'Acme Ltd') == W and spaces.space_of('team', team) == W)
with store.db() as c:
    placed = c.execute("SELECT count(*) FROM item_spaces WHERE placed_by='migration'").fetchone()[0]
    after = {t_: c.execute(f'SELECT count(*) FROM {t_}').fetchone()[0] for t_ in ('records', 'files', 'organisations', 'teams')}
    names = {r[0]: r[1] for r in c.execute('SELECT id, name FROM spaces')}
    members = [tuple(r) for r in c.execute('SELECT space_id, member_key, role FROM space_members')]
t('migration loses nothing: every item kept and placed once, with counts reported', before == after and placed == sum(rep['counts'].values())
  and rep['counts'].get('record:personal') == 1 and rep['counts'].get('record:work') == 2)
t('the work space is called after the owner, and the owner is its only member', names[W].endswith(': work') and members.count((W, 'owner', 'manage')) == 1
  and len([m for m in members if m[0] == W]) == 1)
with store.db() as c:
    logged = c.execute("SELECT detail FROM activity WHERE action='spaces_migrated' ORDER BY id DESC").fetchone()
t('the migration is logged with its counts', logged and 'record → personal' in logged[0])
spaces.ensure_migrated()
with store.db() as c:
    t('it runs once', c.execute("SELECT count(*) FROM spaces").fetchone()[0] == 2)

# ---------------- people ----------------
import users, mcp_server
from fastapi.testclient import TestClient
cl = TestClient(app.app)
OWNER, MIRA, NIA = ('0000aaaa-0000-0000-0000-000000000001', '0000bbbb-0000-0000-0000-000000000002', '0000cccc-0000-0000-0000-000000000003')
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}
def who(oid, email, roles):
    c = {'claims': [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]}
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps(c).encode()).decode(), **TOKEN}
O, M, N = who(OWNER, 'stefan@example.org', ['Alice.Owner']), who(MIRA, 'mira@example.org', ['Alice.Member']), who(NIA, 'nia@example.org', ['Alice.Member'])
for h in (O, M, N): cl.get('/', headers=h)
prof = users.save_profile('', 'Team', {'sections': {'chat': 'use', 'archive': 'use', 'memories': 'use', 'knowledge': 'view', 'teams': 'view'},
                                        'teams': {team: {'level': 'use', 'run': True}}})
for oid in (MIRA, NIA): users.update(oid, profile=prof['id'])
users._forget(); spaces.forget()
as_mira = lambda: users.viewer_for(MIRA)

ids = lambda h: {r['id'] for r in cl.get('/admin/api/memories?status=all', headers=h).json()['records']}
t('the owner still sees all their own items after the migration', {m_work, m_family, m_uncat} <= ids(O))
t('a new person sees nothing shared: only their own personal space', ids(M) == set()
  and [s['kind'] for s in cl.get('/admin/api/spaces', headers=M).json()['spaces']] == ['personal'])
mcp_server._viewer = as_mira
t('…and nothing through the connector', mcp_server.search_records('')['total'] == 0 and 'Rate card' not in json.dumps(mcp_server.list_files()))
store.VIEWER.set(None)

# ---------------- a shared space, deliberately ----------------
r = cl.post('/admin/api/spaces', headers=O, json={'name': 'Bid team', 'description': 'Bids and proposals'})
B = r.json()['id']
t('an Owner creates a shared space; only they are in it', r.status_code == 200 and ids(M) == set())
t('a Member cannot create a shared space', cl.post('/admin/api/spaces', headers=M, json={'name': 'Mine'}).status_code == 403)
r = cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': m_work, 'space': B})
t('sharing a clean, classified memory: Temple checks it, then it moves', r.json()['status'] == 'moved' and spaces.space_of('record', m_work) == B
  and SCREEN['calls'] and 'Bid style' in SCREEN['calls'][-1])
t('…and it is still not visible to anyone who is not in the space', ids(M) == set())
r = cl.put(f'/admin/api/spaces/{B}/members', headers=O, json={'member': MIRA, 'role': 'view'})
t('adding Mira to the space (View) reveals exactly that space', r.status_code == 200 and ids(M) == {m_work})
t('…nothing of the work space or the owner\'s personal space', m_family not in ids(M) and m_uncat not in ids(M))
mcp_server._viewer = as_mira
s = mcp_server.search_records('')
t('the connector returns exactly what is in her spaces', {x['id'] for x in s['records']} == {m_work})
store.VIEWER.set(None)
t('Nia, not added, still sees nothing', ids(N) == set())
t('View cannot add people', cl.put(f'/admin/api/spaces/{B}/members', headers=M, json={'member': NIA, 'role': 'view'}).status_code == 403)
own = cl.post('/admin/api/records', headers=M, json={'title': 'Mira idea', 'content': 'Mira suggests a two-page summary at the front of every bid.', 'source': 'Mira'}).json()['id']
t('a new item goes to her personal space by default', spaces.space_of('record', own) == spaces.personal_space(MIRA))
t('View cannot add items to the space', cl.post('/admin/api/spaces/move', headers=M, json={'item_type': 'record', 'item_id': own, 'space': B}).status_code == 403)
t('the owner cannot see Mira\'s personal item', own not in ids(O))
t('…or open it', cl.get(f'/admin/api/records/{own}/history', headers=O).status_code == 403)
cl.put(f'/admin/api/spaces/{B}/members', headers=O, json={'member': MIRA, 'role': 'contribute'})
t('Contribute still cannot add people (only Manage and Owners)', cl.put(f'/admin/api/spaces/{B}/members', headers=M, json={'member': NIA, 'role': 'view'}).status_code == 403)

# ---------------- the sharing gate ----------------
r = cl.post('/admin/api/spaces/move', headers=M, json={'item_type': 'record', 'item_id': own, 'space': B})
t('an unclassified item never enters a shared space', r.json()['status'] == 'refused' and 'category' in ' '.join(r.json()['reasons'])
  and spaces.space_of('record', own) != B)
health = mem('Team cover', 'Mira has been off on sick leave with depression since March, so cover her bids.', 'Work')
r = cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': health, 'space': B})
t('a health detail is held for its author, with the reason', r.json()['status'] == 'held' and spaces.space_of('record', health) == W
  and any('special category' in x for x in r.json()['reasons']))
contact = mem('Supplier contact', 'Ring John Smith on 07700 900123 about the hall survey.', 'Work')
r = cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': contact, 'space': B})
t('a third person\'s personal data (a phone number) is held', r.json()['status'] == 'held' and any('phone' in x for x in r.json()['reasons']))
SCREEN['reply'] = {'personal_data': True, 'special_category': False, 'private': False, 'reasons': ['It describes a colleague\'s pay.']}
quiet = mem('Pay note', 'The senior bid writer has asked for a review in the spring cycle.', 'Work')
r = cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': quiet, 'space': B})
t('what only Temple spots is held too, in Temple\'s words', r.json()['status'] == 'held' and 'colleague\'s pay' in ' '.join(r.json()['reasons']))
SCREEN['reply'] = {'personal_data': False, 'special_category': False, 'private': False, 'reasons': []}
SCREEN['fail'] = True
other = mem('Bid calendar', 'Bid reviews happen on the second Monday of each month.', 'Work')
r = cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': other, 'space': B})
t('if Temple cannot check, it waits (never shared unchecked)', r.json()['status'] == 'held' and 'could not check' in ' '.join(r.json()['reasons']))
SCREEN['fail'] = False
r = cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': m_family, 'space': B})
t('an item in a personal-area category is marked private: held', r.json()['status'] == 'held' and any('private' in x for x in r.json()['reasons']))
waiting = cl.get('/admin/api/spaces', headers=O).json()['waiting']
t('held items wait for their author on the Spaces page', {w['item_id'] for w in waiting} >= {health, contact, quiet, other, m_family})
hid = next(w['id'] for w in waiting if w['item_id'] == health)
acts_sec = next((x for x in cl.get('/admin/api/actions', headers=O).json()['sections'] if x['key'] == 'shares'), None)
t('…and on Actions, explained, for the author only', acts_sec and acts_sec['count'] >= 5 and hid in [i['id'] for i in acts_sec['items']]
  and 'personal' in acts_sec['note'])
t('…never on someone else\'s Actions', not next((x for x in cl.get('/admin/api/actions', headers=M).json().get('sections', [])
                                                if x['key'] == 'shares' and x['count']), None))
t('only the author decides', cl.post(f'/admin/api/spaces/held/{hid}', headers=M, json={'action': 'share'}).status_code == 403)
cl.post(f'/admin/api/spaces/held/{hid}', headers=O, json={'action': 'keep'})
t('keep personal: it stays where it was', spaces.space_of('record', health) == W and health not in ids(M))
oid_ = next(w['id'] for w in waiting if w['item_id'] == other)
cl.post(f'/admin/api/spaces/held/{oid_}', headers=O, json={'action': 'share'})
t('share anyway: the author\'s deliberate choice', spaces.space_of('record', other) == B and other in ids(M))
with store.db() as c:
    acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE rule IN ('spaces','share_gate')")}
t('every share, hold, refusal and decision is logged', {'space_shared', 'space_share_held', 'space_share_refused', 'space_share_kept', 'space_member_added'} <= acts)

# ---------------- connectors choose a space they may contribute to ----------------
mcp_server._viewer = as_mira
r = mcp_server.propose_record('Mira workflow', 'Mira keeps a running list of bid lessons in a shared note.', 'Mira said so', space=B)
t('a connector proposal into a shared space: unclassified, so it stays in her default space and says why', spaces.space_of('record', r['id']) == spaces.personal_space(MIRA)
  and r['space']['status'] in ('refused', 'not_moved') and 'default space' in r['space']['message'])
r = mcp_server.propose_record('Mira workflow two', 'Mira also tracks every bid deadline in her calendar.', 'Mira said so', space=W)
t('…and a space she is not in is refused', r['space']['status'] == 'not_moved')
sp = mcp_server.list_spaces()
t('list_spaces names her spaces and her role', {x['id'] for x in sp['spaces']} == {B, spaces.personal_space(MIRA)})
store.VIEWER.set(None)

# ---------------- Temple and teams read by space ----------------
with store.as_viewer(users.viewer_for(MIRA)):
    mine = store.propose('Mira dates', 'Mira wants the bid calendar shared with new joiners.', 'Mira')['id']
temple.review_record(mine)
with store.db() as c:
    ctx = c.execute('SELECT context FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC', (mine,)).fetchone()[0]
t('Temple compares her memory only with what is in her spaces', m_work in ctx and other in ctx and m_family not in ctx and m_uncat not in ctx and health not in ctx)
r = cl.get(f'/admin/api/teams/{team}/page', headers=M)
t('a team in the work space is not hers to see, whatever her profile says', r.status_code == 403)
cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'team', 'item_id': team, 'space': B})
t('moved into the Bid team space, she sees it', spaces.space_of('team', team) == B and cl.get(f'/admin/api/teams/{team}/page', headers=M).status_code == 200)
UP = [{'name': 'FICTIONAL brief.txt', 'text': 'A fictional village hall extension of about 120 square metres.', 'kind': 'brief'}]
with store.as_viewer(users.owner_viewer()):
    oj = teams.start_job(team, 'cost-estimate', 'Hall job', 'Price a fictional village hall extension for the bid team please.', uploads=UP)['id']
t('a job started on a team goes into the team\'s space', spaces.space_of('team_job', oj) == B)
t('…so the team\'s members see it', cl.get(f'/admin/api/teams/jobs/{oj}/page', headers=M).status_code == 200
  and cl.get(f'/admin/api/teams/jobs/{oj}/page', headers=N).status_code == 403)

# ---------------- a space tied to a client ----------------
acme = mem('Acme renewal', 'Acme Ltd renews its framework in June.', 'Work')
clients.tag('memory', [acme], 'Acme Ltd', 'human')
cl.post('/admin/api/spaces/move', headers=O, json={'item_type': 'record', 'item_id': acme, 'space': B})
t('client material in a space she is in: visible before any client-tied space exists', acme in ids(M))
r = cl.post('/admin/api/spaces', headers=O, json={'name': 'Acme account', 'client': 'Acme Ltd'})
t('a space tied to a client: only its members see that client\'s material, wherever it sits', r.status_code == 200 and acme not in ids(M) and acme in ids(O))
cl.put(f"/admin/api/spaces/{r.json()['id']}/members", headers=O, json={'member': MIRA, 'role': 'view'})
t('…join it and the client\'s material in your spaces comes back', acme in ids(M))

# ---------------- removing someone, and the owner-only apps ----------------
cl.delete(f'/admin/api/spaces/{B}/members/{MIRA}', headers=O)
t('removed from a space: she stops seeing it at once (her own items stay hers)', not (ids(M) & {m_work, other, acme}) and own in ids(M) and cl.get(f'/admin/api/teams/jobs/{oj}/page', headers=M).status_code == 403)
t('a space keeps at least one manager', cl.delete(f'/admin/api/spaces/{B}/members/owner', headers=O).status_code == 400)
t('a personal space never takes members', cl.put(f'/admin/api/spaces/{P}/members', headers=O, json={'member': MIRA, 'role': 'view'}).status_code == 400)
t('health, trading and mileage stay the owner\'s, spaces or not', all(cl.get(u, headers=M).status_code == 403 for u in ('/admin/api/health', '/admin/api/trading', '/admin/api/mileage')))
pg = cl.get('/admin/spaces', headers=M)
t('everyone has the Spaces page in their menu', pg.status_code == 200 and 'data-page="spaces"' in pg.text)
lst = cl.get('/admin/api/spaces', headers=O).json()
b = next(x for x in lst['spaces'] if x['id'] == B)
t('the Spaces page shows members, roles and item counts', b['members'] and b['counts'].get('memory or decision', 0) >= 2 and lst['migration']['counts'])
os.environ.pop('ALICE_TRUST_EASYAUTH', None); os.environ.pop('ALICE_USE_APP_ROLES', None); os.environ.pop('ALICE_OWNER_OBJECT_ID', None)
