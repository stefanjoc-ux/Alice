"""Fixes found while testing #45 (10 Oct 2026), and decision D-0053.

1. Items approved without a category no longer get stuck: Temple never approves an item with an empty category (it gives one, or holds
   it for a person with the reason "no category", a setting of Approval and library management); a share whose item is approved but has
   no category shows as held for a category, never "waiting for Temple's review"; the Spaces card offers a category picker and Share now,
   and Keep it where it is; approved items with no category are listed on Actions with the same picker, and nothing changes until one
   is picked.
2. No page says sharing is "always deliberate" (the old private-first wording).
3. D-0053: everything in the owner's work space is organisational. The move's preview lists every item per destination (the
   Organisation space; a team space for each digital team with its jobs and pricing templates; personal-area items stay) and nothing
   moves until the Owner confirms; client-tagged items keep their client restrictions; new items then go to the Organisation space; a
   space's managers rename it (others cannot), and the emptied work space can be retired (archived, not deleted).
Every object ID, name and item is fictional. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os, uuid
os.environ['ALICE_OWNER_NAME'] = 'Robin Example'
import substrate_store as store
import app
import users, spaces, knowledge as K, memory_tags, temple, temple_categorise, assistants, rules_engine as R, autoapprove as A
import actions, clients, library, admin_ui, teams, pricing_templates
from fastapi.testclient import TestClient

OWNER, MIRA = '0000f955-0000-4000-8000-0000000000a1', '0000b1b1-0000-4000-8000-0000000000a2'
spaces.BACKGROUND = False
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}

# ---------------- stand-ins for Temple (no model is called) ----------------
CATEGORY = {'value': None}          # what Temple's categorising answers (None: it could not place it)


def fake_categorise(payload):
    return json.dumps({'assignments': [{'id': m['id'], 'category': CATEGORY['value'], 'confidence': 0.9, 'reason': 'Fits.'}
                                       for m in json.loads(payload)['memories']]})


def fake_review(rid):
    with store.db() as c:
        c.execute("INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,finished_at,report,context) VALUES (?,?,?,?,?,?,?,?,?)",
                  (uuid.uuid4().hex, rid, 'complete', 'openai', 'gpt-6-luna', store.now(), store.now(),
                   'Recommendation: approve\nReasons: a new fact.\nImpact: low\nConflict: no', '{}'))
    return {'status': 'complete'}


SCREENS = []


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    if workload == 'Temple sharing check':
        SCREENS.append(messages[0]['content'])
        return json.dumps({'finding': False, 'findings': [], 'clear_because': 'Ordinary work content.'})
    raise RuntimeError('no model in tests')


temple_categorise._ask = fake_categorise
temple.review_record = fake_review
temple.save_settings(True, 'openai')
assistants._call = fake_call
SPAWNED = []
_spawn = store.spawn
def _tracked_spawn(*a, **k):
    th = _spawn(*a, **k); SPAWNED.append(th); return th
store.spawn = _tracked_spawn


def settle():
    while SPAWNED: SPAWNED.pop(0).join(timeout=30)


def who(oid, email, roles=()):
    claims = [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
E = who(OWNER, 'owner@example.org', ['Alice.Owner'])
M = who(MIRA, 'mira@example.org', ['Alice.Member'])
for h in (E, M): cl.get('/', headers=h)
users._forget(); spaces.forget()
spaces.ensure_migrated(); spaces.ensure_org_space()
store.create_category('Work'); memory_tags.set_category_area('Work', 'work')
store.create_category('Family'); memory_tags.set_category_area('Family', 'personal')
OV = users.viewer_for(OWNER)
W, O = spaces.WORK, spaces.ORG
default = next(d for d in json.loads(R.SHIPPED_DEFAULTS.read_text(encoding='utf-8'))['rules'] if d['id'] == 'approval_required')['params']


def status(rid):
    with store.db() as c: return c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]


def category(rid):
    with store.db() as c:
        r = c.execute("SELECT coalesce(category,'') FROM record_meta WHERE record_id=?", (rid,)).fetchone()
    return r[0] if r else ''


# ================= 1a. Temple never approves an item with an empty category =================
with store.as_viewer(OV): R.update_rule('approval_required', new_params=default, reason='Test: the shipped default, Temple approves')
with store.as_viewer(OV): A.set_on(True, 'Test: Temple approves')
t('the rule holds "anything Temple could not give a category" by default', library.holds('no_category')
  and R.rule('approval_required')['params']['hold']['no_category'] is True)
with store.as_viewer(OV):
    m1 = store.propose('Printer codes', 'The third-floor printer releases jobs with your staff card.', 'said so')['id']
settle()
st = A._state('memory', m1)
t('Temple could not give it a category: it is not approved, it is held for a person', status(m1) == 'proposed' and category(m1) == ''
  and st and st['state'] == 'held' and st['reason'].startswith('No category'))
with store.as_viewer(OV):
    d1 = store.propose_decision('Use the shared drive', 'Team files live on the shared drive, not on laptops.', 'said so')['id']
settle()
st = A._state('memory', d1)
t('…the same for a decision Temple manages', status(d1) == 'proposed' and st and st['state'] == 'held' and st['reason'].startswith('No category'))
k1 = K.create('note', 'Kitchen rota', 'The kitchen is tidied by each team in turn on Fridays.', 'typed', 'you', status='draft')['id']
t('…and for a knowledge draft', A.knowledge_draft(k1) == 'held' and A._state('knowledge', k1)['reason'].startswith('No category'))
CATEGORY['value'] = 'Work'
with store.as_viewer(OV):
    m2 = store.propose('Visitor badges', 'Visitors collect a badge from reception and return it on leaving.', 'said so')['id']
settle()
t('when Temple can give one, it categorises first and then approves', status(m2) == 'approved' and category(m2) == 'Work')
CATEGORY['value'] = None
with store.as_viewer(OV): R.update_rule('approval_required', new_params={**default, 'hold': {**default['hold'], 'no_category': False}}, reason='Test: not held')
with store.as_viewer(OV):
    m3 = store.propose('Bike shed', 'The bike shed is unlocked with the building fob.', 'said so')['id']
settle()
t('switched off on the Rules page, it is approved (a setting, not code)', status(m3) == 'approved' and category(m3) == '')
with store.as_viewer(OV): R.update_rule('approval_required', new_params=default, reason='Back to the default')
with store.as_viewer(OV): A.set_on(False, 'Test: approvals by hand from here')
page = cl.get('/admin/rules', headers=E).text
t('the Rules page explains the new hold', 'could not give a category' in page)

# ================= 1b. D-0048: approved with no category, its share waiting for good =================
temple_categorise.schedule = lambda ids: None              # as in D-0048: Temple's categorising never followed through
ops = spaces.create('Operations', 'The operations team.')['id']
spaces.set_capture(default=ops)
with store.as_viewer(OV):
    d48 = store.propose_decision('Weekly stand-up', 'The team meets for a stand-up every Monday at ten.', 'said so')['id']
with store.db() as c:
    mv = c.execute("SELECT * FROM space_moves WHERE item_id=? AND status IN ('waiting','held')", (d48,)).fetchone()
t('a new decision waits to go to the team space', mv and mv['status'] == 'waiting' and mv['to_space'] == ops)
store.review(d48, 'approved')                              # approved with an empty category, as D-0048 was
with store.as_viewer(OV):
    h = next(x for x in spaces.held(OV, waiting=True) if x['item_id'] == d48)
t('approved with no category: shown as held for a category, not "waiting for Temple\'s review"', h['status'] == 'held'
  and h['needs_category'] and 'without a category' in ' '.join(h['reasons']) and 'Temple' not in ' '.join(h['reasons'])[:40])
sp = cl.get('/admin/api/spaces', headers=E).json()
w48 = next(x for x in sp['waiting'] if x['item_id'] == d48)
t('…the Spaces page gets it with the categories to pick from', w48['needs_category'] and 'Work' in sp['categories'])
page = cl.get('/admin/spaces', headers=E).text
t('…and its card offers a category picker, Share now and Keep it where it is', all(x in page for x in ('catPicker(d.categories', "'Share now'", 'Keep it where it is')))
acts = cl.get('/admin/api/actions', headers=E).json()
shares = next((s for s in acts['sections'] if s['key'] == 'shares'), {'items': []})
t('Actions lists it with the same picker', any(i['id'] == w48['id'] and i['type'] == 'share_category' and 'Work' in i['categories'] for i in shares['items']))
r = cl.post(f"/admin/api/spaces/held/{w48['id']}", headers=E, json={'action': 'share', 'category': 'Work'})
t('picking a category moves it to its target space at once (through the sharing check)', r.status_code == 200 and r.json()['status'] == 'moved'
  and spaces.space_of('record', d48) == ops and category(d48) == 'Work' and len(SCREENS) >= 1)
with store.db() as c:
    done = c.execute('SELECT status FROM space_moves WHERE id=?', (w48['id'],)).fetchone()[0]
t('…and the share is closed', done == 'shared')
with store.as_viewer(OV):
    d49 = store.propose_decision('Desk moves', 'Desk moves are booked with facilities a week ahead.', 'said so')['id']
store.review(d49, 'approved')
w49 = next(x for x in cl.get('/admin/api/spaces', headers=E).json()['waiting'] if x['item_id'] == d49)
r = cl.post(f"/admin/api/spaces/held/{w49['id']}", headers=E, json={'action': 'keep'})
t('Keep it where it is still works on one held for a category', r.status_code == 200 and spaces.space_of('record', d49) != ops)
t('a category that does not exist is refused', cl.post(f"/admin/api/spaces/held/{w48['id']}", headers=E, json={'action': 'share', 'category': 'Nope'}).status_code in (400, 404))

# ================= 1c. other approved items with an empty category, listed on Actions =================
old1 = store.propose('Fire drill', 'Fire drills are on the first Tuesday of the quarter.', 'said so')['id']     # from before spaces: no share
store.review(old1, 'approved')
spaces._place('record', old1, W)
kn = K.create('note', 'Parking', 'Visitor parking is on level minus one.', 'typed', 'you')['id']
unc = next(s for s in cl.get('/admin/api/actions', headers=E).json()['sections'] if s['key'] == 'uncategorised')
t('approved items with no category are listed on Actions, each with a category picker', {old1, kn} <= {i['id'] for i in unc['items']}
  and all(i['type'] == 'uncategorised' and 'Work' in i['categories'] for i in unc['items']))
t('…as information (it does not add to the count of what waits), and nothing changed by listing them', unc['info'] and category(old1) == ''
  and K.meta([kn])[kn]['category'] == '')
t('a Member does not get that list', not any(s['key'] == 'uncategorised' and s['items'] for s in cl.get('/admin/api/actions', headers=M).json().get('sections', [])))
cl.post('/admin/api/memories/category', headers=E, json={'ids': [old1], 'category': 'Work'})
unc = next(s for s in cl.get('/admin/api/actions', headers=E).json()['sections'] if s['key'] == 'uncategorised')
t('once the Owner picks one, it leaves the list', old1 not in {i['id'] for i in unc['items']} and category(old1) == 'Work')
spaces.set_capture(default='team')

# ================= 2. no private-first wording left =================
pages = [p for p in admin_ui.PAGES if p not in ('demo',)]
texts = [cl.get('/admin/' + p, headers=E) for p in pages]
t('no page says sharing is "always deliberate"', all('always deliberate' not in r.text for r in texts if r.status_code == 200) and len(texts) > 10)
src = ''.join(open(f, encoding='utf-8').read() for f in os.listdir('.') if f.endswith('.py'))
t('…nor anything else in Alice (pages, tools, connector text)', 'always deliberate' not in src and 'until shared Spaces arrive' not in src)
t('the Spaces page says how it works now: open by default, Temple routes, Entra groups', all(x in admin_ui.PAGES['spaces'][1] for x in (
    'open by default', 'Organisation space', 'restricted space', 'Temple routes', 'Entra groups')))

# ================= 3. D-0053: everything in the work space is organisational =================
team = teams.create('Quantity surveying', 'Cost plans.')
tid = team['id'] if isinstance(team, dict) else team
spaces._place('team', tid, W)
now = store.now()
with store.db() as c:
    c.execute("INSERT INTO team_jobs(id,team_id,job_type,team_version,title,created_at,updated_at,pricing_template) VALUES (?,?,?,?,?,?,?,?)",
              ('J-0001AA', tid, 'cost-estimate', 1, 'Community hall cost plan', now, now, 'Templates/QS/rates.xlsx'))
    c.execute("INSERT INTO pricing_templates(path,updated_at) VALUES (?,?)", ('Templates/QS/rates.xlsx', now))
spaces._place('team_job', 'J-0001AA', W); spaces._place('pricing_template', 'Templates/QS/rates.xlsx', W)
with store.as_viewer(OV):
    mem = store.propose('Office hours', 'The office is open from eight until six.', 'said so')['id']
    dec = store.propose_decision('Rail travel', 'All rail travel is booked through the travel desk.', 'said so')['id']
    fam = store.propose('Family holiday', 'The family holiday is in the second week of August.', 'said so')['id']
for x, cat in ((mem, 'Work'), (dec, 'Work'), (fam, 'Family')):
    store.review(x, 'approved'); store.set_category([x], cat); spaces._place('record', x, W)
clients.create_client('Fernley Council') if 'Fernley Council' not in clients.names() else None
conf = K.create('note', 'Fernley bid notes', 'Fernley bids are fixed price this year.', 'typed', 'you', label='client', category='Work')['id']
clients.tag('file', [conf], 'Fernley Council', 'human')
spaces._place('file', conf, W)
import proposals  # noqa: F401  (creates the proposals table)
pid = uuid.uuid4().hex
with store.db() as c:
    c.execute("INSERT INTO proposals(id,assistant_id,title,brief,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
              (pid, 'proposal-writer', 'Hall refurbishment proposal', 'Refurbish the community hall.', 'form', now, now))
spaces._place('proposal', pid, W)

t('a Member cannot see the preview', cl.get('/admin/api/spaces/organisation/move', headers=M).status_code == 403)
pv = cl.get('/admin/api/spaces/organisation/move', headers=E).json()
org_ids = {k: {x['id'] for x in v} for k, v in pv['organisation'].items()}
qs = next((x for x in pv['teams'] if x['team_id'] == tid), None)
t('the preview lists every item per destination: memories, decisions, knowledge and proposals to the Organisation space',
  mem in org_ids['memories'] and dec in org_ids['decisions'] and conf in org_ids['knowledge'] and pid in org_ids['proposals'])
t('…the digital team, its job and its pricing template to a team space named after the team', qs and qs['space_name'] == 'Quantity surveying'
  and {x['id'] for x in qs['teams']} == {tid} and 'J-0001AA' in {x['id'] for x in qs['team_jobs']}
  and 'Templates/QS/rates.xlsx' in {x['id'] for x in qs['pricing_templates']})
t('…personal-area items stay, and are listed as staying', fam in {x['id'] for x in pv['staying']} and fam not in org_ids['memories'])
t('…client-tagged items are shown with their client', any(x['id'] == conf and x['client'] == 'Fernley Council' for x in pv['organisation']['knowledge']))
t('…with counts per kind', pv['counts']['memories'] == len(pv['organisation']['memories']) and pv['counts']['teams'] >= 1 and pv['counts']['staying'] >= 1)
t('nothing moved by previewing', spaces.space_of('record', mem) == W and spaces.space_of('team', tid) == W and spaces.capture_policy()['default'] != O)
t('confirming with other counts is refused', cl.post('/admin/api/spaces/organisation/move', headers=E, json={'counts': {**pv['counts'], 'memories': 999}}).status_code == 400)
r = cl.post('/admin/api/spaces/organisation/move', headers=E, json={'counts': pv['counts']})
st = r.json()
qs_space = next((sid for sid, s in spaces.names().items() if s['name'] == 'Quantity surveying' and s['kind'] == 'shared'), '')
t('the move runs once confirmed', r.status_code == 200 and st['state'] == 'done' and st['moved'] >= 5)
t('memories, decisions and knowledge are in the Organisation space', spaces.space_of('record', mem) == O and spaces.space_of('record', dec) == O
  and spaces.space_of('file', conf) == O and spaces.space_of('proposal', pid) == O)
t('team material is in the team space for that team', qs_space and spaces.space_of('team', tid) == qs_space
  and spaces.space_of('team_job', 'J-0001AA') == qs_space and spaces.space_of('pricing_template', 'Templates/QS/rates.xlsx') == qs_space)
t('personal-area items did not move', spaces.space_of('record', fam) == W)
pred_other, _ = clients.item_filter('Another Council', client_facing=True)
pred_own, _ = clients.item_filter('Fernley Council', client_facing=True)
t('client-confidential items keep their client restrictions after the move', clients.client_of('file', conf) == 'Fernley Council'
  and K.meta([conf])[conf]['label'] == 'client' and not pred_other(clients.client_of('file', conf)) and pred_own(clients.client_of('file', conf)))
fsp = spaces.create('Fernley account', 'Only the Fernley account team.', 'Fernley Council')['id']
users._forget(); spaces.forget()
with store.as_viewer(users.viewer_for(MIRA)):
    t('…and a client tied to a space is still seen only by that space\'s members, wherever the item sits', not store.can_see('file', conf)
      and store.can_see('record', dec))
with store.as_viewer(OV):
    t('the default capture space is now the Organisation space', spaces.capture_policy()['default'] == O and spaces.default_for(OV) == O
      and spaces.default_space() == O)
with store.db() as c:
    acts_ = {r_[0] for r_ in c.execute("SELECT action FROM activity WHERE rule='spaces'")}
t('the move is logged, and so is the new capture space', {'org_migration_started', 'org_migration_done', 'capture_space_set'} <= acts_)

# ---------------- renaming and retiring ----------------
r = cl.put(f'/admin/api/spaces/{ops}/details', headers=M, json={'name': 'Taken over'})
t('someone who does not manage a space cannot rename it', r.status_code == 403 and spaces.names()[ops]['name'] == 'Operations')
r = cl.put(f'/admin/api/spaces/{ops}/details', headers=E, json={'name': 'Operations and facilities', 'description': 'Buildings, desks and the stand-up.'})
t('its manager renames it and changes its description', r.status_code == 200 and spaces.names()[ops]['name'] == 'Operations and facilities')
with store.db() as c:
    t('…logged', c.execute("SELECT 1 FROM activity WHERE action='space_renamed' AND target=?", (ops,)).fetchone() is not None)
t('a personal space keeps its name', cl.put(f'/admin/api/spaces/{spaces.personal_space("owner")}/details', headers=E, json={'name': 'Mine'}).status_code == 400)
t('a space that still holds items cannot be retired', cl.post(f'/admin/api/spaces/{ops}/retire', headers=E, json={'reason': 'Test'}).status_code == 400)
held_k = [x for x in cl.get('/admin/api/spaces', headers=E).json()['waiting'] if x['from_space'] == W and x['needs_category']]
t('items the move held for want of a category are on the Spaces page with the picker', held_k and st['held'] == len(held_k))
t('…and the work space cannot be retired until they have moved', cl.post(f'/admin/api/spaces/{W}/retire', headers=E, json={}).status_code == 400)
for x in held_k: cl.post(f"/admin/api/spaces/held/{x['id']}", headers=E, json={'action': 'share', 'category': 'Work'})
t('…given a category, each goes on to the Organisation space', all(spaces.space_of(x['item_type'], x['item_id']) == O for x in held_k))
r = cl.post(f'/admin/api/spaces/{W}/retire', headers=E, json={'reason': 'Emptied by the move to the Organisation space.'})
with store.db() as c:
    row = c.execute('SELECT archived_at, closed FROM spaces WHERE id=?', (W,)).fetchone()
t('the emptied work space is retired: archived, not deleted', r.status_code == 200 and row and row['archived_at'] and row['closed'])
t('…its personal-area items went to the owner\'s personal space, never wider', spaces.space_of('record', fam) == spaces.personal_space('owner'))
t('…and it no longer lists for anyone but an Owner, nor takes new items', W not in spaces.my_spaces(OV) and W not in spaces.open_spaces()
  and not any(x['id'] == W for x in cl.get('/admin/api/spaces', headers=M).json().get('spaces', [])))
page = cl.get('/admin/spaces', headers=E).text
t('the Spaces page offers Rename and Retire on a space\'s card, and the move per destination', all(x in page for x in ("'Rename or describe'", "'Retire it'", 'p.teams', 'p.staying')))
for k in ('ALICE_TRUST_EASYAUTH', 'ALICE_USE_APP_ROLES', 'ALICE_OWNER_OBJECT_ID'): os.environ.pop(k, None)
