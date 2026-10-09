"""Spaces and the owner of Alice (Stefan, 9 Oct 2026). Spaces use the ONE shared owner check (users.is_owner, through
permissions.is_owner_person): the account Entra makes an owner (Alice.Owner) is 'owner' in every membership; the configured owner
object ID (ALICE_OWNER_OBJECT_ID) counts only while app roles are off. So the migration puts Stefan's items in the personal space
and "Stefan: work" of his everyday account (Alice.Owner), never of his tenant admin account (Alice.Admin, the old configured ID),
and a real Member's older items go to that Member's own personal space. All object IDs here are fictional. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os
os.environ['ALICE_OWNER_NAME'] = 'Stefan'
import substrate_store as store
import app                    # creates the tables (and, at start-up, places existing items: none yet)
import users, spaces, knowledge, memory_tags, temple
from fastapi.testclient import TestClient

EVERYDAY, ADMINACC, MIRA = ('0000f955-0000-4000-8000-000000000001', '0000e610-0000-4000-8000-000000000002',
                            '0000b1b1-0000-4000-8000-000000000003')
temple.save_settings(False, 'claude')
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}


def who(oid, email, roles=()):
    claims = [{'typ': 'name', 'val': email.split('@')[0]}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


E = who(EVERYDAY, 'stefan@example.org', ['Alice.Owner'])                  # Stefan's everyday account: Alice.Owner
B = who(ADMINACC, 'admin@tenant.example.org', ['Alice.Admin'])            # his tenant admin account: Alice.Admin, the old configured ID
M = who(MIRA, 'mira@example.org', ['Alice.Member'])

# Azure as it is now: app roles on, and the configured owner object ID still names the admin account (the setup's old ownerObjectId)
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': ADMINACC})

# This throwaway database stands for the live one before spaces: people signed in under Task 1, items written by each.
with store.db() as c:
    for tb in ('spaces', 'space_members', 'item_spaces'): c.execute(f'DELETE FROM {tb}')
    c.execute("DELETE FROM settings WHERE key LIKE 'spaces_%'")
spaces._MIGRATED.clear(); spaces.forget()
for h in (E, B, M): users.identify({k.lower(): v for k, v in h.items()})
users._forget()
store.create_category('Work'); store.create_category('Family')
memory_tags.set_category_area('Work', 'work'); memory_tags.set_category_area('Family', 'personal')


def mem(oid, title, content, cat=''):
    with store.as_viewer(users.viewer_for(oid) if oid else None):
        r = store.propose(title, content, 'said so')
    store.review(r['id'], 'approved')
    if cat: store.set_category([r['id']], cat)
    return r['id']


m_family = mem(EVERYDAY, 'School run', 'Stefan does the school run on Tuesdays and Thursdays.', 'Family')
m_work = mem(EVERYDAY, 'Bid style', 'Bids lead with the outcome for the client, then the method and the team.', 'Work')
m_admin = mem(ADMINACC, 'Tenant set-up', 'The Alice tenant uses Entra app roles for Owner, Admin and Member.', 'Work')
m_old = mem('', 'Preferred editor', 'Stefan drafts proposals in Word, not Google Docs.')
m_mira = mem(MIRA, 'Mira likes tea', 'Mira prefers green tea in the morning meetings.')
with store.as_viewer(users.viewer_for(EVERYDAY)):
    k_family = knowledge.create('note', 'Holiday plans', 'The family holiday is booked for the second week of August.', 'typed', 'you', category='Family')['id']
with store.db() as c:
    c.execute('DELETE FROM item_spaces')            # Task 1 recorded authors only; no item had a space yet
    before = {t_: c.execute(f'SELECT count(*) FROM {t_}').fetchone()[0] for t_ in ('records', 'files')}

# ---------------- the one owner check decides who 'owner' is ----------------
ev, adm, mi = users.viewer_for(EVERYDAY), users.viewer_for(ADMINACC), users.viewer_for(MIRA)
t('the everyday account (Alice.Owner) is the owner in spaces', spaces.person_key(ev) == spaces.OWNER and users.is_owner(EVERYDAY))
t('the admin account (Alice.Admin, still the configured ID) is not: it has its own key', spaces.person_key(adm) == ADMINACC
  and not users.is_owner(ADMINACC))
t('owner_oids() names the everyday account and never the admin account', users.owner_oids() == [EVERYDAY])
t('background work on the owner\'s items reads as the everyday account', users.owner_viewer().owner and spaces.person_key(users.owner_viewer()) == spaces.OWNER)

# ---------------- the migration ----------------
spaces.ensure_migrated()
rep = spaces.migration_report()
P, W = rep['personal'], rep['work']
with store.db() as c:
    names = {r[0]: r[1] for r in c.execute('SELECT id, name FROM spaces')}
    members = sorted(tuple(r) for r in c.execute('SELECT space_id, member_key, role FROM space_members WHERE space_id IN (?,?)', (P, W)))
    after = {t_: c.execute(f'SELECT count(*) FROM {t_}').fetchone()[0] for t_ in ('records', 'files')}
t('the migration makes "Stefan: personal" and "Stefan: work"', names.get(P) == 'Stefan: personal' and names.get(W) == 'Stefan: work')
t('…with the owner (by the owner check) as their only member, never the admin account',
  members == sorted([(P, spaces.OWNER, 'manage'), (W, spaces.OWNER, 'manage')]))
t('Stefan\'s personal-area items go to his personal space', spaces.space_of('record', m_family) == P and spaces.space_of('file', k_family) == P)
t('…everything else of his to "Stefan: work", including what the admin account wrote and older items with no author',
  all(spaces.space_of('record', x) == W for x in (m_work, m_admin, m_old)))
t('a real Member\'s older memory goes to their own personal space, not Stefan\'s', spaces.space_of('record', m_mira) == spaces.personal_space(MIRA))
placed = sum(v for k, v in rep['counts'].items() if k.split(':')[0] in ('record', 'file'))
t('nothing lost: every item kept and placed once', before == after and placed == after['records'] + after['files'])
if placed != after['records'] + after['files']: print('   ', rep['counts'], after)

# ---------------- what each account sees afterwards ----------------
def ids(h):
    r = cl.get('/admin/api/memories?status=all', headers=h)
    return {x['id'] for x in r.json()['records']} if r.status_code == 200 else set()


t('the everyday account sees all of Stefan\'s items and none of Mira\'s', {m_family, m_work, m_admin, m_old} <= ids(E) and m_mira not in ids(E))
with store.as_viewer(adm):
    seen = [x for x in (m_family, m_work, m_admin, m_old) if store.can_see('record', x)]
    kf = store.can_see('file', k_family)
t('the admin account sees none of them: it is not a member of Stefan\'s spaces', seen == [] and not kf)
with store.as_viewer(mi):
    t('Mira still sees her own memory and nothing of Stefan\'s', store.can_see('record', m_mira)
      and not any(store.can_see('record', x) for x in (m_family, m_work, m_admin, m_old)))
sp = cl.get('/admin/api/spaces', headers=E).json()
t('the Spaces page shows the everyday account as the owner, with both spaces', sp['me'] == spaces.OWNER
  and {P, W} <= {s['id'] for s in sp['spaces']})
t('…and the admin account\'s own page shows neither', not {P, W} & {s['id'] for s in cl.get('/admin/api/spaces', headers=B).json()['spaces'] if s.get('my_role')})

# ---------------- memberships use the same check ----------------
with store.as_viewer(ev):
    S = spaces.create('Bids', 'Shared bid work')['id']
    spaces.set_member(S, ADMINACC, 'view')
    spaces.set_member(S, EVERYDAY, 'manage')
with store.db() as c:
    keys = sorted(r[0] for r in c.execute('SELECT member_key FROM space_members WHERE space_id=?', (S,)))
t('adding the admin account adds it as itself, never as the owner', keys == sorted([spaces.OWNER, ADMINACC]))
t('the people list offers the owner once, by name, and the admin account as itself',
  [p['key'] for p in sp['people']].count(spaces.OWNER) == 1 and ADMINACC in [p['key'] for p in sp['people']])
t('chats: the owner\'s author keys are the owner accounts, never the admin account', ADMINACC not in spaces.author_keys(ev)
  and EVERYDAY in spaces.author_keys(ev))

# ---------------- while app roles are off, the configured ID is the owner (the bootstrap fallback) ----------------
os.environ['ALICE_USE_APP_ROLES'] = '0'
users._forget(); spaces.forget()
t('with app roles off, the configured ID is the owner in spaces too (the same check)', spaces.person_key(users.viewer_for(ADMINACC)) == spaces.OWNER)
os.environ['ALICE_USE_APP_ROLES'] = '1'
users._forget(); spaces.forget()
t('…and once app roles are on again, it is not', spaces.person_key(users.viewer_for(ADMINACC)) == ADMINACC)
