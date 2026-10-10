"""Handing over a departing person's work (handover.py; Stefan, 9 Oct 2026). Only an Owner; only once the person is suspended
or has lost their Alice role; titles only until an item is opened (and the opening is logged); items move only when ticked and
only through the sharing check; what it holds is explained on Actions for an Owner to decide; nothing is deleted and every
step is logged with who and why. All people and content are fictional; no real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os
import substrate_store as store
import app
import knowledge, assistants, temple, spaces, users, handover

temple.save_settings(False, 'claude')
SCREEN = {'reply': {'finding': False, 'findings': []}, 'calls': []}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    if workload == 'Temple sharing check':
        SCREEN['calls'].append(messages[0]['content'])
        return json.dumps(SCREEN['reply'])
    raise RuntimeError('no model in tests')


assistants._call = fake_call

from fastapi.testclient import TestClient
cl = TestClient(app.app)
OWNER, MIRA, ADA, NIA = ('0000aaaa-0000-0000-0000-000000000001', '0000bbbb-0000-0000-0000-000000000002',
                         '0000dddd-0000-0000-0000-000000000004', '0000cccc-0000-0000-0000-000000000003')
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}


def who(oid, email, roles):
    c = {'claims': [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]}
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps(c).encode()).decode(), **TOKEN}


O, M, A, N = (who(OWNER, 'stefan@example.org', ['Alice.Owner']), who(MIRA, 'mira@example.org', ['Alice.Member']),
              who(ADA, 'ada@example.org', ['Alice.Admin']), who(NIA, 'nia@example.org', ['Alice.Member']))
for h in (O, M, A, N): cl.get('/', headers=h)
users.update(ADA, role='admin'); users._forget(); spaces.forget()

store.create_category('Work'); store.create_category('Family')
import memory_tags
memory_tags.set_category_area('Work', 'work'); memory_tags.set_category_area('Family', 'personal')

# ---------------- Mira's personal space (fictional) ----------------
with store.as_viewer(users.viewer_for(MIRA)):
    def mem(title, content, cat=''):
        r = store.propose(title, content, 'Mira said so')
        store.review(r['id'], 'approved')
        if cat: store.set_category([r['id']], cat)
        return r['id']
    m_clean = mem('Bid checklist', 'Every bid gets a second reader two days before the deadline.', 'Work')
    m_other = mem('Bid colours', 'Cover pages use the navy template for public-sector bids.', 'Work')
    m_health = mem('Cover while away', 'Mira is off for surgery in November, so the team covers her bids.', 'Work')
    m_uncat = mem('Bid lessons', 'Short executive summaries scored better in the last three bids.')
    m_family = mem('School pick-up', 'Mira leaves at three on Fridays for the school pick-up.', 'Family')
    k_note = knowledge.create('note', 'Framework renewal notes', 'The fictional framework renews every four years.', 'typed', 'you', category='Work')['id']
P = spaces.personal_space(MIRA)
t('her items are in her personal space', all(spaces.space_of('record', x) == P for x in (m_clean, m_health, m_uncat, m_family))
  and spaces.space_of('file', k_note) == P)
own = store.propose('Owner note', 'The owner keeps the bid diary.', 'the owner')['id']

r = cl.post('/admin/api/spaces', headers=O, json={'name': 'Bid team'})
B = r.json()['id']
r = cl.post('/admin/api/spaces', headers=A, json={'name': 'Admin space'})
X = r.json()['id']                                  # a shared space the Owner does not manage
with store.db() as c:
    before = {tb: c.execute(f'SELECT count(*) FROM {tb}').fetchone()[0] for tb in ('records', 'files', 'users', 'activity')}

# ---------------- only for a departing person, only an Owner ----------------
r = cl.get(f'/admin/api/users/{MIRA}/handover', headers=O)
t('while she is active, her work cannot be handed over', r.status_code == 403 and 'still active' in r.json()['detail'])
t('…and the Users page offers no Hand over for her', MIRA not in cl.get('/admin/api/users', headers=O).json().get('handover', {}))
cl.put(f'/admin/api/users/{MIRA}', headers=O, json={'status': 'suspended'})
users._forget()
t('suspended: the Users page offers Hand over with her item count', cl.get('/admin/api/users', headers=O).json()['handover'].get(MIRA) == 6)
t('an Admin sees no Hand over', 'handover' not in cl.get('/admin/api/users', headers=A).json())
for h, label in ((A, 'an Admin'), (N, 'a Member')):
    t(f'{label} is refused the list', cl.get(f'/admin/api/users/{MIRA}/handover', headers=h).status_code == 403)
    t(f'{label} is refused an item', cl.get(f'/admin/api/users/{MIRA}/handover/item', params={'type': 'record', 'id': m_clean}, headers=h).status_code == 403)
    t(f'{label} cannot hand anything over', cl.post(f'/admin/api/users/{MIRA}/handover', headers=h,
      json={'items': [{'type': 'record', 'id': m_clean}], 'space': B, 'note': 'Testing a refusal'}).status_code == 403)
with store.as_viewer(users.viewer_for(ADA)):
    try: handover.listing(MIRA); ok = False
    except PermissionError: ok = True
t('…and the function itself refuses a non-Owner (not only the route)', ok)
r = cl.get(f'/admin/api/users/{OWNER}/handover', headers=O)
t('an owner\'s own work is never "handed over"', r.status_code == 403)

# ---------------- titles only ----------------
L = cl.get(f'/admin/api/users/{MIRA}/handover', headers=O).json()
body = json.dumps(L)
t('the list groups her items by type, titles only', [g['label'] for g in L['groups']] == ['Memories', 'Knowledge'] and L['total'] == 6
  and {i['title'] for g in L['groups'] for i in g['items']} >= {'Bid checklist', 'Cover while away', 'Framework renewal notes'})
t('…no content in the list', 'second reader' not in body and 'surgery' not in body and 'four years' not in body
  and not any('text' in i or 'content' in i for g in L['groups'] for i in g['items']))
t('…marks what has no category confirmed by a person, and what is private', next(i for i in L['groups'][0]['items'] if i['id'] == m_uncat)['classified'] is False
  and next(i for i in L['groups'][0]['items'] if i['id'] == m_family)['private'] is True)
t('…offers only shared spaces the Owner manages (never one they are not a manager of, never a personal space)',
  B in [s['id'] for s in L['spaces']] and X not in [s['id'] for s in L['spaces']] and P not in [s['id'] for s in L['spaces']])
r = cl.get(f'/admin/api/users/{MIRA}/handover/item', params={'type': 'record', 'id': m_health}, headers=O)
t('opening one item shows its content', r.status_code == 200 and 'surgery' in r.json()['text'])
with store.db() as c:
    op = c.execute("SELECT actor, detail FROM activity WHERE action='handover_item_opened' ORDER BY id DESC").fetchone()
t('…and the opening is logged with who', op and op['actor'] == 'stefan@example.org' and 'Cover while away' in op['detail'])
t('an item not in her personal space cannot be opened this way', cl.get(f'/admin/api/users/{MIRA}/handover/item', params={'type': 'record', 'id': own},
  headers=O).status_code == 404)

# ---------------- moves only when ticked and checked ----------------
go = lambda items, note='Mira left on 9 October; her bid notes go to the Bid team', space=B, cats=None: cl.post(
    f'/admin/api/users/{MIRA}/handover', headers=O, json={'items': items, 'space': space, 'note': note, 'categories': cats or {}})
t('a reason is required', go([{'type': 'record', 'id': m_clean}], note='').status_code == 400 and spaces.space_of('record', m_clean) == P)
t('a space the Owner does not manage is refused, and nothing moves', go([{'type': 'record', 'id': m_clean}], space=X).status_code == 403
  and spaces.space_of('record', m_clean) == P)
t('nothing ticked: nothing to do', go([]).status_code == 400)
n_calls = len(SCREEN['calls'])
r = go([{'type': 'record', 'id': m_clean}, {'type': 'file', 'id': k_note}]).json()
t('the ticked items pass the sharing check and move', len(r['moved']) == 2 and spaces.space_of('record', m_clean) == B and spaces.space_of('file', k_note) == B
  and len(SCREEN['calls']) == n_calls + 2 and 'Bid checklist' in SCREEN['calls'][n_calls])
t('…and only those: the rest stay in her personal space', all(spaces.space_of('record', x) == P for x in (m_other, m_health, m_uncat, m_family)))
with store.db() as c:
    mv = c.execute("SELECT actor, note, detail FROM activity WHERE action='handover_moved' ORDER BY id DESC").fetchone()
    run_ = c.execute("SELECT actor, note, detail FROM activity WHERE action='handover_run' ORDER BY id DESC").fetchone()
t('each move is logged with who and why', mv['actor'] == 'stefan@example.org' and 'Mira left on 9 October' in mv['note'] and 'Bid team' in mv['detail'])
t('…and the hand-over as a whole, with its counts', run_ and 'Mira left' in run_['note'] and '2 handed over' in run_['detail'])

r = go([{'type': 'record', 'id': m_uncat}]).json()
t('an unclassified memory is refused, with the reason', len(r['refused']) == 1 and 'category' in ' '.join(r['refused'][0]['reasons'])
  and spaces.space_of('record', m_uncat) == P)
r = go([{'type': 'record', 'id': m_uncat}], cats={m_uncat: 'Work'}).json()
with store.db() as c:
    by = c.execute('SELECT assigned_by, category FROM record_meta WHERE record_id=?', (m_uncat,)).fetchone()
t('given a category by the Owner here, it is classified and handed over', len(r['moved']) == 1 and spaces.space_of('record', m_uncat) == B
  and by['assigned_by'] == 'human' and by['category'] == 'Work')
r = go([{'type': 'record', 'id': own}]).json()
t('an item that is not in her personal space is not moved', len(r['refused']) == 1 and spaces.space_of('record', own) != B)

# ---------------- held items explained on Actions ----------------
SCREEN['reply'] = {'finding': True, 'findings': [{'type': 'special_category', 'quote': 'Mira is off for surgery in November', 'about': 'Mira',
                                                  'reason': 'It mentions a colleague\'s surgery.'}]}
r = go([{'type': 'record', 'id': m_health}]).json()
SCREEN['reply'] = {'finding': False, 'findings': []}
t('a health detail is held, not moved', len(r['held']) == 1 and spaces.space_of('record', m_health) == P
  and 'surgery' in ' '.join(r['held'][0]['reasons']))
r = go([{'type': 'record', 'id': m_family}]).json()
t('an item in a personal-area category is held as private', len(r['held']) == 1 and any('private' in x for x in r['held'][0]['reasons']))
sec = next((x for x in cl.get('/admin/api/actions', headers=O).json()['sections'] if x['key'] == 'handover'), None)
t('held items are explained on Actions for the Owner, with the reasons and the Owner\'s own reason', sec and sec['count'] == 2
  and any('surgery' in i['detail'] and 'Mira left' in i['detail'] for i in sec['items'])
  and all(i['href'] == f'/admin/users#handover={MIRA}' for i in sec['items']) and 'sharing check' in sec['note'])
t('…not on the Spaces page\'s author list, and not in the author\'s Shares section', not any(w['item_id'] in (m_health, m_family)
  for w in cl.get('/admin/api/spaces', headers=O).json()['waiting']))
t('…and listed in the Hand over panel', {h['item_id'] for h in cl.get(f'/admin/api/users/{MIRA}/handover', headers=O).json()['held']} == {m_health, m_family})
hid = next(i['id'] for i in sec['items'] if 'surgery' in i['detail'])
fid = next(i['id'] for i in sec['items'] if i['id'] != hid)
t('the Spaces author route cannot decide a hand-over item', cl.post(f'/admin/api/spaces/held/{hid}', headers=O, json={'action': 'share'}).status_code == 403)
t('an Admin cannot decide it', cl.post(f'/admin/api/handover/held/{hid}', headers=A, json={'action': 'keep'}).status_code == 403)
t('sharing anyway needs a reason', cl.post(f'/admin/api/handover/held/{hid}', headers=O, json={'action': 'share'}).status_code == 400
  and spaces.space_of('record', m_health) == P)
cl.post(f'/admin/api/handover/held/{hid}', headers=O, json={'action': 'keep'})
t('keep: it stays in her personal space', spaces.space_of('record', m_health) == P)
r = cl.post(f'/admin/api/handover/held/{fid}', headers=O, json={'action': 'share', 'note': 'The team needs to know her Friday hours'})
with store.db() as c:
    sh = c.execute("SELECT actor, note FROM activity WHERE action='handover_shared' ORDER BY id DESC").fetchone()
t('share anyway, with a reason: it moves, logged with who and why', r.status_code == 200 and spaces.space_of('record', m_family) == B
  and sh['actor'] == 'stefan@example.org' and 'Friday hours' in sh['note'])
t('decided items leave Actions', not next((x for x in cl.get('/admin/api/actions', headers=O).json()['sections'] if x['key'] == 'handover' and x['count']), None))

# ---------------- nothing deleted; her account and history stay ----------------
with store.db() as c:
    after = {tb: c.execute(f'SELECT count(*) FROM {tb}').fetchone()[0] for tb in ('records', 'files', 'users', 'activity')}
    authors = {r[0] for r in c.execute("SELECT author_oid FROM item_authors WHERE item_id IN (?,?)", (m_clean, m_uncat))}
t('nothing is deleted: every memory, knowledge item and person is still there', all(after[k] == before[k] for k in ('records', 'files', 'users'))
  and after['activity'] > before['activity'])
t('her account stays (suspended), with its history', users.person(MIRA)['status'] == 'suspended'
  and cl.get('/admin/api/activity-log', params={'q': 'mira'}, headers=O).status_code == 200)
t('handed-over items keep their author', authors == {MIRA})
t('the shared space\'s members now see what was handed over', m_clean in {x['id'] for x in cl.get('/admin/api/memories?status=all', headers=O).json()['records']})

# ---------------- restored access: back to private ----------------
cl.put(f'/admin/api/users/{MIRA}', headers=O, json={'status': 'active'})
users._forget()
t('restored: her personal space is private again', cl.get(f'/admin/api/users/{MIRA}/handover', headers=O).status_code == 403)

# ---------------- the page ----------------
page = cl.get('/admin/users', headers=O).text
t('the Users page has the Hand over panel', 'id="us-ho"' in page and 'Hand over the ticked items' in page and 'handover/item' in page)
