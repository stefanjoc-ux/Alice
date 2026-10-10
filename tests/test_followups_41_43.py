"""Tidy-ups found while testing #41-#43 (10 Oct 2026): a person's linked accounts' personal spaces are theirs (the Spaces page and the
sweep see them), what was left there after linking is repaired with a preview and duplicates are archived; Actions offers the move into
the Organisation space until it has run; "Move all" sits with the list; the Users and permissions intro and both linked rows; -Step users
assigns the roles on the connector app too. Every object ID, name and item is fictional. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os
import substrate_store as store
import app
import users, spaces, temple, admin_ui, actions
from fastapi.testclient import TestClient

EVERYDAY, ADMINACC = '0000f955-0000-4000-8000-0000000000e1', '0000e610-0000-4000-8000-0000000000e2'
temple.save_settings(False, 'claude')
spaces.BACKGROUND = False
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}


def who(oid, email, roles=()):
    claims = [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


E = who(EVERYDAY, 'owner@example.org', ['Alice.Owner'])
A = who(ADMINACC, 'admin@tenant.example.org', ['Alice.Admin'])
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': EVERYDAY})
for h in (E, A): cl.get('/', headers=h)
users._forget(); spaces.forget()
spaces.ensure_migrated()
P = spaces.personal_space(spaces.OWNER)
ADMIN_P = spaces.personal_space(ADMINACC)
spaces.ensure_personal(ADMINACC)

# The live state: the accounts were linked, but decisions made afterwards under the admin account sat in its own personal space
# (D-0041 to D-0046), and two of them were then recorded again in the owner's work space (D-0047 onwards).
r = cl.post(f'/admin/api/users/{ADMINACC}/link', headers=E, json={'to': EVERYDAY, 'note': 'Both are the owner: everyday and tenant admin accounts'})
t('the accounts are linked', r.status_code == 200)


def dec(title, text, space):
    rid = store.propose_decision(title, text, 'said so')['id']
    store.review(rid, 'approved')
    with store.db() as c:
        c.execute('INSERT INTO item_spaces(item_type,item_id,space_id,placed_at,placed_by) VALUES (?,?,?,?,?) '
                  'ON CONFLICT(item_type,item_id) DO UPDATE SET space_id=excluded.space_id', ('record', rid, space, store.now(), 'test'))
    return rid


left1 = dec('Spaces are open by default', 'Team spaces are readable by everyone in the organisation unless a manager closes them.', ADMIN_P)
left2 = dec('Release notes per release', 'Alice writes one knowledge item per release, listing its pull requests.', ADMIN_P)
again1 = dec('Spaces are open by default', 'Re-recorded (D-0047): open by default, so every team space is readable across Alice; a manager may close one with a reason.', spaces.WORK)
spaces.forget(); users._forget()

# ---------------- the linked account's personal space is the person's ----------------
lst = cl.get('/admin/api/spaces', headers=E).json()
ids = {s['id'] for s in lst['spaces']}
t('the Spaces page lists the linked account\'s personal space for the owner', ADMIN_P in ids and P in ids)
with store.as_viewer(users.viewer_for(EVERYDAY)):
    t('…and the owner sees what is in it', store.can_see('record', left1) and store.can_see('record', left2))
    sw = spaces.sweep_list()
t('the sweep counts the items in it', sw['in_personal'] >= 2)

# ---------------- repaired with a preview; duplicates archived ----------------
pv = cl.get('/admin/api/spaces/linked', headers=E).json()
by = {i['id']: i for i in pv['items']}
t('the preview lists what was left there, before anything changes', set(by) == {left1, left2} and spaces.space_of('record', left1) == ADMIN_P)
t('…a decision recorded again is offered for archiving, naming the later copy', by[left1]['suggested'] == 'archive'
  and by[left1]['duplicate_of']['id'] == again1)
t('…the others are offered for moving into the person\'s own personal space', by[left2]['suggested'] == 'move' and pv['to'] == P)
t('a reason is required', cl.post('/admin/api/spaces/linked', headers=E, json={'actions': {left2: 'move'}, 'note': ''}).status_code == 400)
r = cl.post('/admin/api/spaces/linked', headers=E, json={'actions': {left1: 'archive', left2: 'move'}, 'note': 'Repairing the split from before the link'})
x = r.json()
with store.db() as c: arch = c.execute('SELECT state FROM memory_archive WHERE record_id=?', (left1,)).fetchone()
t('the duplicate is archived (retired, history kept), the other moved into the owner\'s personal space', r.status_code == 200
  and x['archived'] == 1 and x['moved'] == 1 and arch and arch[0] == 'retired' and spaces.space_of('record', left2) == P)
with store.db() as c:
    t('…logged with the reason', c.execute("SELECT count(*) FROM activity WHERE action='linked_accounts_repaired' AND note LIKE '%split%'").fetchone()[0] == 1)
t('nothing is left to repair', not cl.get('/admin/api/spaces/linked', headers=E).json()['items'])
t('the admin account sees only its own linked accounts\' spaces, never another person\'s', all(
  s['kind'] != 'personal' or s['id'] in (P, ADMIN_P) for s in cl.get('/admin/api/spaces', headers=A).json()['spaces']))

# ---------------- the move into the Organisation space is offered on Actions until it has run ----------------
import knowledge
knowledge.create('note', 'Expenses policy', 'Expenses are claimed monthly through the finance portal with receipts attached.', 'Finance handbook',
                 'Owner', status='active')            # general knowledge in the work space: it belongs in the Organisation space
offer = spaces.org_migration_offer()
sec = {s['key']: s for s in cl.get('/admin/api/actions', headers=E).json()['sections']}
t('Actions offers the move into the Organisation space while it has not run, linking to its preview on Spaces',
  offer and offer['counts']['knowledge'] >= 1 and 'org_move' in sec and sec['org_move']['items'][0]['href'] == '/admin/spaces#organisation')
t('…not to someone who is not an Owner', 'org_move' not in {s['key'] for s in cl.get('/admin/api/actions', headers=A).json().get('sections', [])})
def _mig(state):
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES ('org_migration',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps({'state': state}),))
    spaces.forget()
_mig('running')
t('…not while it is running', spaces.org_migration_offer() is None)
_mig('done')
t('…and still after an earlier move while something is left in the work space (D-0053: all of it is organisational)', spaces.org_migration_offer() is not None)

# ---------------- the pages ----------------
script = admin_ui.SCRIPT
t('"Move all" goes in the card\'s header, top right, as Approve all does', 'sweepBlock(s.sweep,hr)' in script and 'head.prepend(all)' in script)
t('the Users and permissions intro describes spaces now', 'Until shared Spaces arrive' not in admin_ui.PAGES['users'][1]
  and 'open to the organisation' in admin_ui.PAGES['users'][1] and 'Entra' in admin_ui.PAGES['users'][1])
t('both rows of a linked pair say "Linked to …"', "D.users.filter(x=>x.linked_to===u.oid)" in script)
t('the Spaces page has the repair card and the Organisation card at the top', admin_ui.SECTIONS['spaces'].startswith('<section id="sp-linked" hidden></section><section id="sp-org" hidden></section>'))
setup = open(os.path.join(_util.ROOT, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
t('-Step users assigns the roles on the connector sign-in app as well as the web sign-in app',
  "Assign-People $State.webAuthClientId $sp 'Alice web sign-in'" in setup and "Assign-People $State.connectorClientId $csp 'Alice connector sign-in'" in setup)
