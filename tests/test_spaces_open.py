"""Work items stop getting stuck in personal spaces (Stefan, 10 Oct 2026; decision D-0040, design CR-4 hotfix). Temple's review
comes before the sharing check; Temple's category counts (rule temple_category); a share waiting for a category retries once it has
one; the default capture space; the one-off sweep of personal spaces; the sharing check holds only an actual finding; one identity for
the connector's reads and writes; linked accounts are one author; the author, the space's managers and an Owner decide a held share.
Every object ID, name and item here is fictional (the D-0040 text is a reconstruction of the decision's wording). No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os, threading
os.environ['ALICE_OWNER_NAME'] = 'Stefan'
import substrate_store as store
import app
import users, spaces, knowledge, memory_tags, temple, temple_categorise, assistants, mcp_server, rules_engine
from fastapi.testclient import TestClient

EVERYDAY, ADMINACC, MIRA, NIA, OLA = ('0000f955-0000-4000-8000-000000000001', '0000e610-0000-4000-8000-000000000002',
                                      '0000b1b1-0000-4000-8000-000000000003', '0000c2c2-0000-4000-8000-000000000004',
                                      '0000d3d3-0000-4000-8000-000000000005')
temple.save_settings(False, 'claude')
spaces.BACKGROUND = False
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}

# ---------------- the fixtures ----------------
D0040_TITLE = 'Alice is open by default (CR-4)'
D0040 = ('Alice is an institutional store of knowledge shared across teams: open by default. Work knowledge goes to the team space and '
         'general knowledge to the Organisation space; only items about the user themselves stay in their personal space, and HR '
         'casework and other sensitive data about named people go to a restricted space. Spaces as built are private first, so work '
         'knowledge ends up stuck in personal spaces such as Stefan: personal. Health, trading and mileage stay owner-only.')
SICK = 'Cover for Nia Brown: she has been on sickness absence since 3 March, so route her approvals to Sam until she is back.'
DIABETES = 'Ravi in delivery told me he was diagnosed with type 2 diabetes, so keep his site visits short.'


def screen_reply(text):
    """Temple's structured answer, as a careful model would give it."""
    if 'sickness absence' in text:
        return {'finding': True, 'findings': [{'type': 'special_category', 'quote': 'she has been on sickness absence since 3 March',
                                               'about': 'Nia Brown', 'reason': 'A named employee\'s sickness absence.'}]}
    if 'diabetes' in text:
        import re
        return {'finding': True, 'findings': [{'type': 'special_category', 'quote': re.search(r'\w+ was diagnosed with type 2 diabetes', text).group(0),
                                               'about': 'Ravi', 'reason': 'A colleague\'s health condition.'}]}
    if 'open by default' in text:
        # What Temple said live about D-0040: "yes", but every reason was a clear (no passage about a real person quoted).
        return {'finding': True, 'findings': [
            {'type': 'personal_data', 'quote': '', 'about': '', 'reason': 'Names Alice and refers to the user\'s personal space, but gives no '
                                                                         'private circumstances or contact details.'},
            {'type': 'special_category', 'quote': 'HR casework', 'about': '', 'reason': 'It mentions HR and sensitive data in general, not '
                                                                                     'special-category data about an identifiable person.'}]}
    return {'finding': False, 'findings': [], 'clear_because': 'Ordinary work content.'}


SWEEP_CALLS = []


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    if workload == 'Temple sharing check': return json.dumps(screen_reply(messages[0]['content']))
    if workload == 'Temple personal-space sweep':
        items = json.loads(messages[0]['content'])['items']
        SWEEP_CALLS.append([i['title'] for i in items])
        verdict = lambda i: 'work' if any(w in i['title'] for w in ('Tender', 'Bid', 'Portal')) else 'self'
        return json.dumps({'items': [{'id': i['id'], 'verdict': verdict(i), 'reason': 'About the work.' if verdict(i) == 'work' else 'About you.'}
                                     for i in items]})
    raise RuntimeError('no model in tests')


assistants._call = fake_call
CATS = {'open by default': 'Data & Access', 'Tender': 'Work', 'Bid': 'Work', 'Portal': 'Work', 'sickness': 'Work', 'diabetes': 'Work',
        'Supplier list': 'Work'}


def fake_ask(payload):
    d = json.loads(payload)
    def pick(m):
        txt = m.get('title', '') + ' ' + m.get('content', '')
        return next((c for w, c in CATS.items() if w in txt), None)
    return json.dumps({'assignments': [{'id': m['id'], 'category': pick(m), 'confidence': 0.9, 'reason': 'fits'} for m in d['memories']]})


temple_categorise._ask = fake_ask


SPAWNED = []
_spawn = store.spawn
def _tracked_spawn(*a, **k):
    th = _spawn(*a, **k); SPAWNED.append(th); return th
store.spawn = _tracked_spawn


def settle():
    """Wait for the background work Alice starts (Temple's categorising, then the shares waiting on it)."""
    while SPAWNED:
        SPAWNED.pop(0).join(timeout=30)


def who(oid, email, roles=()):
    claims = [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


E = who(EVERYDAY, 'stefan@example.org', ['Alice.Owner'])
A = who(ADMINACC, 'admin@tenant.example.org', ['Alice.Admin'])
M = who(MIRA, 'mira@example.org', ['Alice.Member'])
N = who(NIA, 'nia@example.org', ['Alice.Member'])
O = who(OLA, 'ola@example.org', ['Alice.Member'])
# Azure as it is live: app roles on, the configured owner object ID still the tenant admin account (the setup's old ownerObjectId)
WEB = {'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': ADMINACC}
os.environ.update(WEB)

with store.db() as c:
    for tb in ('spaces', 'space_members', 'item_spaces'): c.execute(f'DELETE FROM {tb}')
    c.execute("DELETE FROM settings WHERE key LIKE 'spaces_%'")
spaces._MIGRATED.clear(); spaces.forget()
for h in (E, A, M, N, O): cl.get('/', headers=h)
users._forget()
store.create_category('Data & Access'); store.create_category('Work'); store.create_category('Family')
memory_tags.set_category_area('Work', 'work'); memory_tags.set_category_area('Data & Access', 'work'); memory_tags.set_category_area('Family', 'personal')
spaces.ensure_migrated()
P, W = spaces.migration_report()['personal'], spaces.migration_report()['work']
prof = users.save_profile('', 'Team', {'sections': {'chat': 'use', 'archive': 'use', 'memories': 'use', 'knowledge': 'use'}})
for oid in (MIRA, NIA, OLA): users.update(oid, profile=prof['id'])
users._forget(); spaces.forget()


def connector(oid, fn, *a, **k):
    """A call on the outside connector exactly as alice-mcp makes it: not behind web sign-in, the caller from the token's object ID."""
    os.environ.pop('ALICE_TRUST_EASYAUTH', None)
    old = mcp_server._viewer
    mcp_server._viewer = lambda: users.connector_viewer(oid)
    try: return fn(*a, **k)
    finally:
        mcp_server._viewer = old
        store.VIEWER.set(None)
        os.environ['ALICE_TRUST_EASYAUTH'] = '1'


def activity(action):
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM activity WHERE action=? ORDER BY id', (action,))]


# ---------------- the sharing check holds only an actual finding ----------------
t('D-0040\'s wording trips none of the code checks', rules_engine.check_share(D0040_TITLE + '\n' + D0040) == [])
hold, notes = spaces.findings_from(json.dumps(screen_reply(D0040)), D0040_TITLE + '\n' + D0040)
t('Temple\'s live answer on D-0040 (yes, but no quoted passage about a real person) is not a finding', hold == [] and len(notes) == 2)
hold, _ = spaces.findings_from(json.dumps(screen_reply(SICK)), SICK)
t('a named employee\'s sickness absence, quoted, is a finding', len(hold) == 1 and hold[0]['type'] == 'special_category')
hold, notes = spaces.findings_from(json.dumps({'finding': True, 'findings': [{'type': 'special_category', 'quote': 'Nia has cancer', 'about': 'Nia'}]}), SICK)
t('a quote that is not in the item is never a finding', hold == [] and notes)


def human_mem(title, content, cat, viewer=None):
    with store.as_viewer(viewer):
        rid = store.propose(title, content, 'said so')['id']
    store.review(rid, 'approved')
    store.set_category([rid], cat)
    return rid


fx = human_mem(D0040_TITLE, D0040, 'Data & Access')
ok, reasons, by = spaces.gate('record', fx)
t('the D-0040 fixture passes the sharing check', ok and reasons == [])
sick = human_mem('Approvals cover', SICK, 'Work')
ok, reasons, _ = spaces.gate('record', sick)
t('a named employee\'s sickness absence is still held', not ok and reasons)
dia = human_mem('Site visits', DIABETES, 'Work')
ok, reasons, _ = spaces.gate('record', dia)
t('a flagged health detail is still held, with the passage quoted', not ok and any('type 2 diabetes' in r for r in reasons))

# ---------------- one identity: the connector's reads and writes ----------------
admin_web = users.viewer_for(ADMINACC)
with store.as_viewer(admin_web): web_key = spaces.person_key(admin_web)
lst = connector(ADMINACC, mcp_server.list_spaces)
r = connector(ADMINACC, mcp_server.propose_record, 'Supplier list', 'Keep the approved supplier list in the procurement folder.', 'said so')
with store.as_viewer(users.viewer_for(ADMINACC)):
    write_key = spaces._author_key('record', r['id'])
t('the connector reads (list_spaces) and writes (author, default space) as the same person as the web',
  web_key == ADMINACC == write_key and lst['default'] == spaces.space_of('record', r['id'])
  and {s['id'] for s in lst['spaces']} == {spaces.personal_space(ADMINACC)})
t('…and the owner\'s connector account reads as the owner in either process',
  connector(EVERYDAY, mcp_server.list_spaces)['default'] == W and {P, W} <= {s['id'] for s in connector(EVERYDAY, mcp_server.list_spaces)['spaces']})

# The live state before the fix: D-0040 written by the admin account through the connector, sitting in Stefan: personal, with a held
# move into Stefan: work keyed to the admin account (reproduced directly: this is the data the repair must put right).
with store.as_viewer(users.viewer_for(ADMINACC)):
    live = store.propose('Decision D-0040', D0040, 'Claude [via Claude]')['id']
settle()
with store.db() as c:
    c.execute('UPDATE item_spaces SET space_id=? WHERE item_type=? AND item_id=?', (P, 'record', live))
    c.execute("INSERT INTO space_moves(id,item_type,item_id,title,from_space,to_space,requested_by,author_key,status,reasons,screened_by,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ('a' * 32, 'record', live, 'Decision D-0040', P, W, ADMINACC, ADMINACC, 'held', '["old reason"]', 'model', store.now()))
admin_only = connector(ADMINACC, mcp_server.propose_record, 'Portal hours', 'The tender portal closes at noon on Fridays.', 'said so')['id']
settle()

# ---------------- linking a person's accounts: preview first, Owner only ----------------
t('a Member cannot link accounts', cl.post(f'/admin/api/users/{ADMINACC}/link/preview', headers=M, json={'to': EVERYDAY}).status_code == 403)
t('…nor an Admin', cl.post(f'/admin/api/users/{ADMINACC}/link', headers=A, json={'to': EVERYDAY, 'note': 'mine'}).status_code == 403)
pv = cl.post(f'/admin/api/users/{ADMINACC}/link/preview', headers=E, json={'to': EVERYDAY})
pj = pv.json()
t('the preview names what changes, before anything changes', pv.status_code == 200 and pj['to']['name'] == 'Stefan' and pj['authored'] >= 3
  and pj['shares'] == 1 and pj['personal_items'] >= 2 and 'Portal hours' in json.dumps(pj['personal_titles'])
  and spaces.space_of('record', admin_only) == spaces.personal_space(ADMINACC))
t('nothing was linked by the preview', users.primary(ADMINACC) == ADMINACC)
t('linking needs a reason', cl.post(f'/admin/api/users/{ADMINACC}/link', headers=E, json={'to': EVERYDAY, 'note': ''}).status_code == 400)
lk = cl.post(f'/admin/api/users/{ADMINACC}/link', headers=E, json={'to': EVERYDAY, 'note': 'Both are Stefan: everyday and tenant admin accounts'})
t('the Owner links the accounts', lk.status_code == 200 and users.primary(ADMINACC) == EVERYDAY)
t('…the account\'s personal-space items move into Stefan: personal (the same person)', spaces.space_of('record', admin_only) == P)
with store.db() as c:
    row = dict(c.execute("SELECT * FROM space_moves WHERE id=?", ('a' * 32,)).fetchone())
t('…the held D-0040 move is re-keyed to Stefan', row['author_key'] == spaces.OWNER and row['requested_by'] == spaces.OWNER)
t('…logged with who and why', any('everyday and tenant admin' in (a_['note'] or '') for a_ in activity('user_linked'))
  and activity('account_link_repaired'))
t('never linked automatically: Mira and Nia are still their own people', users.primary(MIRA) == MIRA and spaces.key_for(NIA) == NIA)
lst = connector(ADMINACC, mcp_server.list_spaces)
t('the linked admin account\'s connector now reads Stefan\'s spaces', {P, W} <= {s['id'] for s in lst['spaces']})
t('…but stays an Admin: never the owner-only areas', not users.is_owner(ADMINACC)
  and cl.get('/admin/api/health', headers=A).status_code == 403)

# the live D-0040 move, decided from Stefan's everyday web account
r = cl.post(f"/admin/api/spaces/held/{'a' * 32}", headers=E, json={'action': 'share'})
t('a connector item from a linked account is decided from the web account (no "only the person" refusal)', r.status_code == 200
  and r.json()['as'] == 'author' and spaces.space_of('record', live) == W)

# ---------------- the D-0040 sequence: proposed for Stefan: work through the connector ----------------
with store.db() as c:          # the fixtures above carry the same words: out of the duplicate check's way
    c.execute("UPDATE records SET status='rejected' WHERE id IN (?,?)", (fx, live))
r = connector(ADMINACC, mcp_server.propose_decision, 'Open by default', D0040, 'Stefan in Claude', rationale='CR-4', space=W)
rid = r['id']
t('the space check waits for Temple\'s review instead of refusing it as unclassified',
  r['space']['status'] in ('waiting', 'moved') and 'unclassified' not in json.dumps(r['space']).lower())
settle()
temple_categorise.schedule([rid]).join()
settle()
with store.db() as c:
    cat = c.execute('SELECT category, assigned_by FROM record_meta WHERE record_id=?', (rid,)).fetchone()
t('Temple categorises it "Data & Access"', tuple(cat) == ('Data & Access', 'temple'))
t('…and the D-0040 sequence ends in the shared space', spaces.space_of('record', rid) == W)
with store.db() as c:
    mv = c.execute("SELECT status FROM space_moves WHERE item_id=? ORDER BY created_at DESC", (rid,)).fetchone()
t('…with nothing left pending', mv is None or mv[0] == 'shared')

# ---------------- held moves retry once the item is categorised ----------------
CATS_BEFORE = dict(CATS)
with store.as_viewer(users.viewer_for(EVERYDAY)):
    lone = store.propose('Meeting rooms', 'Book the large meeting room a week ahead for client workshops.', 'said so')['id']
store.review(lone, 'approved')
settle()
with store.as_viewer(users.viewer_for(EVERYDAY)):
    spaces.move('record', lone, W) if spaces.space_of('record', lone) != W else None
settle()
held = [h for h in spaces.held(users.viewer_for(EVERYDAY)) if h['item_id'] == lone]
t('Temple not sure of the category: held, with the reason, on Actions', held and held[0]['needs_category']
  and any(s['key'] == 'shares' and any(lone in json.dumps(i) or 'Meeting rooms' in i['title'] for i in s['items'])
          for s in cl.get('/admin/api/actions', headers=E).json()['sections']))
store.set_category([lone], 'Work')
t('…a person gives it a category and it moves on its own', spaces.space_of('record', lone) == W)

# ---------------- the default capture space ----------------
r = connector(EVERYDAY, mcp_server.propose_record, 'Bid reviews', 'Bid reviews happen on the second Monday of each month.', 'said so')
settle()
t('a connector proposal with no space goes to the default capture space (Stefan: work), after Temple\'s review',
  spaces.space_of('record', r['id']) == W and 'Stefan: work' in r['space']['message'])
cl.post('/admin/api/spaces', headers=E, json={'name': 'Bid team'})
B = next(s['id'] for s in cl.get('/admin/api/spaces', headers=E).json()['spaces'] if s['name'] == 'Bid team')
cl.put(f'/admin/api/spaces/{B}/members', headers=E, json={'member': MIRA, 'role': 'contribute'})
cl.put(f'/admin/api/spaces/{B}/members', headers=E, json={'member': NIA, 'role': 'manage'})
cl.put(f'/admin/api/spaces/{B}/members', headers=E, json={'member': OLA, 'role': 'contribute'})
t('a Member cannot change where new items go', cl.put('/admin/api/spaces/capture', headers=M, json={'default': 'personal'}).status_code == 403)
r = cl.put('/admin/api/spaces/capture', headers=A, json={'person': MIRA, 'space': B})
t('an Admin sets Mira\'s team space', r.status_code == 200 and next(p for p in r.json()['people'] if p['key'] == MIRA)['goes_to'] == B)
r = connector(MIRA, mcp_server.propose_record, 'Bid style', 'Bids lead with the outcome for the client, then the method.', 'Mira said so')
settle()
t('…her connector proposals with no space go there', spaces.space_of('record', r['id']) == B)
with store.as_viewer(users.viewer_for(MIRA)): spaces.set_default(spaces.personal_space(MIRA))
r = connector(MIRA, mcp_server.propose_record, 'Bid notes', 'Mira keeps her own bid notes in a notebook.', 'Mira said so')
settle()
t('…her own "New items go to" still wins', spaces.space_of('record', r['id']) == spaces.personal_space(MIRA))
with store.as_viewer(users.viewer_for(MIRA)): spaces.set_default('')
t('the setting is logged', activity('capture_space_set'))

# ---------------- the one-off sweep: work items in personal spaces ----------------
with store.as_viewer(users.viewer_for(EVERYDAY)): spaces.set_default(P)      # to put items in his personal space for the sweep
sw_items = {}
for title, content, cat in (('Tender portal rules', 'Upload tenders as one PDF on the council portal.', 'Work'),
                            ('Bid calendar', 'The bid board meets on the first Tuesday of the month.', 'Work'),
                            ('Prefers bullet points', 'Stefan prefers bullet points in summaries.', ''),
                            ('School run', 'Stefan does the school run on Tuesdays.', 'Family')):
    sw_items[title] = human_mem(title, content, cat or 'Work', users.viewer_for(EVERYDAY))
    if not cat:
        with store.db() as c: c.execute("UPDATE record_meta SET category='',assigned_by='' WHERE record_id=?", (sw_items[title],))
with store.as_viewer(users.viewer_for(EVERYDAY)): spaces.set_default('')
settle()
t('the items start in Stefan: personal', all(spaces.space_of('record', i) == P for i in sw_items.values()))
sec = next((s for s in cl.get('/admin/api/actions', headers=E).json()['sections'] if s['key'] == 'sweep'), None)
t('Actions offers "Work items in personal spaces" before Temple has looked', sec and sec['info'] and sec['sweep']['in_personal'] >= 4)
r = cl.post('/admin/api/spaces/sweep/scan', headers=E)
sw = r.json()
titles = {i['title'] for i in sw['items']}
t('Temple lists the work items, with a preview and counts', r.status_code == 200 and {'Tender portal rules', 'Bid calendar'} <= titles
  and 'Prefers bullet points' not in titles and 'School run' not in titles and sw['counts']['self'] >= 2
  and all(i['preview'] for i in sw['items']) and sw['target'] == W)
t('items in a personal-area category are never sent to Temple', not any('School run' in x for x in sum(SWEEP_CALLS, [])))
t('nothing moved by looking', all(spaces.space_of('record', i) == P for i in sw_items.values()))
tid = next(i['id'] for i in sw['items'] if i['title'] == 'Tender portal rules')
r = cl.post('/admin/api/spaces/sweep/move', headers=E, json={'ids': [tid]})
t('Move one: only the confirmed item moves', r.status_code == 200 and spaces.space_of('record', sw_items['Tender portal rules']) == W
  and spaces.space_of('record', sw_items['Bid calendar']) == P)
t('Move needs a choice', cl.post('/admin/api/spaces/sweep/move', headers=E, json={}).status_code == 400)
r = cl.post('/admin/api/spaces/sweep/move', headers=E, json={'all': True})
t('Move all moves the rest of what Temple listed, and nothing else', spaces.space_of('record', sw_items['Bid calendar']) == W
  and spaces.space_of('record', sw_items['Prefers bullet points']) == P and spaces.space_of('record', sw_items['School run']) == P)
t('the sweep is logged', activity('space_sweep_scanned') and activity('space_sweep_moved'))

# ---------------- who decides a held share ----------------
with store.as_viewer(users.viewer_for(MIRA)):
    mh = store.propose('Approvals cover', SICK, 'Mira said so')['id']
store.review(mh, 'approved'); store.set_category([mh], 'Work')
with store.as_viewer(users.viewer_for(MIRA)): spaces.move('record', mh, B)
mid = next(h['id'] for h in spaces.held(users.viewer_for(MIRA)) if h['item_id'] == mh)
t('a Member who is neither the author nor a manager cannot decide', cl.post(f'/admin/api/spaces/held/{mid}', headers=O, json={'action': 'share', 'note': 'x'}).status_code == 403)
t('a manager must say why', cl.post(f'/admin/api/spaces/held/{mid}', headers=N, json={'action': 'keep'}).status_code == 400)
r = cl.post(f'/admin/api/spaces/held/{mid}', headers=N, json={'action': 'keep', 'note': 'Sickness details stay out of the bid team'})
t('the space\'s manager decides', r.status_code == 200 and r.json()['as'] == 'manager' and spaces.space_of('record', mh) != B)
with store.as_viewer(users.viewer_for(MIRA)): spaces.move('record', mh, B)
mid = next(h['id'] for h in spaces.held(users.viewer_for(MIRA)) if h['item_id'] == mh)
r = cl.post('/admin/api/spaces', headers=E, json={'name': 'Delivery'})
D = r.json()['id']
cl.put(f'/admin/api/spaces/{D}/members', headers=E, json={'member': MIRA, 'role': 'contribute'})
cl.put(f'/admin/api/spaces/{D}/members', headers=E, json={'member': NIA, 'role': 'manage'})
cl.delete(f'/admin/api/spaces/{D}/members/owner', headers=E)            # Stefan is no longer a member: an Owner of Alice all the same
with store.as_viewer(users.viewer_for(MIRA)):
    md = store.propose('Delivery cover', DIABETES, 'Mira said so')['id']
store.review(md, 'approved'); store.set_category([md], 'Work')
with store.as_viewer(users.viewer_for(MIRA)): spaces.move('record', md, D)
did = next(h['id'] for h in spaces.held(users.viewer_for(MIRA)) if h['item_id'] == md)
t('the Owner sees held shares for any shared space on the Spaces page', did in {h['id'] for h in cl.get('/admin/api/spaces', headers=E).json()['waiting']})
r = cl.post(f'/admin/api/spaces/held/{did}', headers=E, json={'action': 'share', 'note': 'Ravi asked for this to be known by the delivery team'})
t('the Owner decides, even for a space he is not a member of', r.status_code == 200 and r.json()['as'] == 'owner' and spaces.space_of('record', md) == D)
# a share into Stefan: work, held, by someone else's item: the Owner manages that space
with store.as_viewer(users.viewer_for(EVERYDAY)):
    oh = store.propose('Finance cover', 'Priya in finance said she was diagnosed with type 2 diabetes in May; plan the audit around her clinic days.', 'said so')['id']
store.review(oh, 'approved'); store.set_category([oh], 'Work')
with store.db() as c: c.execute('UPDATE item_authors SET author_oid=? WHERE item_type=? AND item_id=?', (MIRA, 'record', oh))
with store.as_viewer(users.viewer_for(EVERYDAY)): spaces.move('record', oh, W)
oid_ = next(h['id'] for h in spaces.held(users.viewer_for(EVERYDAY)) if h['item_id'] == oh)
r = cl.post(f'/admin/api/spaces/held/{oid_}', headers=E, json={'action': 'share', 'note': 'Kept for the team'})
t('"no longer contribute" is never shown to the Owner for a space he manages', r.status_code == 200 and 'contribute' not in r.text)
decided = [a_ for a_ in activity('space_shared') + activity('space_share_kept') if 'Why:' in (a_['detail'] or '')]
t('every decision is logged with who, in what capacity and why', len(decided) >= 3 and all(a_['actor'] and a_['note'] for a_ in decided)
  and any('a manager of the space' in a_['detail'] for a_ in decided) and any('an Owner of Alice' in a_['detail'] for a_ in decided))
t('the new rule is on the Rules page, on by default', rules_engine.on('temple_category')
  and any(r_['id'] == 'temple_category' for r_ in rules_engine.all_rules()))

# ---------------- the rule switched off: only a person's category counts ----------------
with store.db() as c: c.execute("UPDATE rules SET enabled=0 WHERE id='temple_category'")
rules_engine._rules_changed() if hasattr(rules_engine, '_rules_changed') else None
with store.as_viewer(users.viewer_for(EVERYDAY)):
    tc = store.propose('Tender clarifications', 'Send tender clarification questions through the portal only.', 'said so')['id']
store.review(tc, 'approved')
settle()
with store.as_viewer(users.viewer_for(EVERYDAY)): res = spaces.move('record', tc, W) if spaces.space_of('record', tc) != W else {'status': 'moved'}
t('with the rule off, Temple\'s category is not enough', res['status'] == 'held' and spaces.space_of('record', tc) != W
  and 'person' in ' '.join(res['reasons']))
with store.db() as c: c.execute("UPDATE rules SET enabled=1 WHERE id='temple_category'")
rules_engine._rules_changed() if hasattr(rules_engine, '_rules_changed') else None
for k in ('ALICE_TRUST_EASYAUTH', 'ALICE_USE_APP_ROLES', 'ALICE_OWNER_OBJECT_ID'): os.environ.pop(k, None)
