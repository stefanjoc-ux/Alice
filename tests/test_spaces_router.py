"""Temple's router and restricted spaces (design CR-4 phase 2; Stefan, 10 Oct 2026). Temple routes each captured item: about the work
to the team space, for the whole organisation to the Organisation space, about its author to their personal space, about a named
person or special category data to the team's restricted space, unsure to its author; the reason is kept on the item. Restricted
spaces are made with a stated purpose and are never open. Approval goes to each space's managers: Temple approves under the space's
rules, a clash waits for that space's managers, and the owner sees a summary.

The HR acceptance scenario: a company deploys Alice and an HR adviser joins the Entra group HR-Team. A policy chat in Copilot lands in
the HR space and Sales can read it; a named employee's absence goes only to HR casework; "I prefer bullet points" goes to her personal
space; nothing waits for the owner; a clash with an existing policy decision waits for HR's managers; special category data never lands
in an open space; removed from HR-Team, she loses HR and HR casework at her next sign-in, and her work items stay.
Every object ID, name and item is fictional. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os, uuid
os.environ['ALICE_OWNER_NAME'] = 'Stefan'
import substrate_store as store
import app
import users, spaces, knowledge, memory_tags, temple, temple_categorise, assistants, mcp_server, rules_engine, autoapprove, external_auth
from fastapi.testclient import TestClient

OWNER, ADMIN, HANA, MO, SOL = ('0000f955-0000-4000-8000-000000000001', '0000e610-0000-4000-8000-000000000002',
                               '0000a1a1-0000-4000-8000-000000000003', '0000b2b2-0000-4000-8000-000000000004',
                               '0000c3c3-0000-4000-8000-000000000005')
G_HR, G_SALES = 'a1a1a1a1-0000-4000-8000-00000000000a', 'b2b2b2b2-0000-4000-8000-00000000000b'
spaces.BACKGROUND = False
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}

# ---------------- stand-ins for Temple (no model is called) ----------------
ROUTED, SCREENED = [], []


def route_reply(text):
    if 'bullet points' in text: return {'route': 'self', 'reason': 'A preference of the person who saved it.'}
    if 'absence' in text and 'Dev Patel' in text: return {'route': 'sensitive', 'reason': 'About a named employee\'s absence.'}
    if 'Everyone at Northfield' in text: return {'route': 'general', 'reason': 'For the whole organisation.'}
    if 'something or other' in text: return {'route': 'unsure', 'reason': 'Too vague to place.'}
    return {'route': 'work', 'reason': 'An HR policy for the team.'}


def screen_reply(text):
    if 'Dev Patel' in text and 'sickness absence' in text:
        return {'finding': True, 'findings': [{'type': 'special_category', 'quote': 'Dev Patel has been on sickness absence', 'about': 'Dev Patel',
                                               'reason': 'A named employee\'s sickness absence.'}]}
    if 'Priya Shah' in text:
        return {'finding': True, 'findings': [{'type': 'special_category', 'quote': 'Priya Shah has epilepsy', 'about': 'Priya Shah',
                                               'reason': 'A named employee\'s health condition.'}]}
    return {'finding': False, 'findings': [], 'clear_because': 'An HR policy, no one named.'}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    text = messages[0]['content']
    if workload == 'Temple routing':
        ROUTED.append(text); return json.dumps(route_reply(text))
    if workload == 'Temple sharing check':
        SCREENED.append(text); return json.dumps(screen_reply(text))
    raise RuntimeError('no model in tests')


assistants._call = fake_call
temple_categorise._ask = lambda payload: json.dumps({'assignments': [{'id': m['id'], 'category': 'HR', 'confidence': 0.9, 'reason': 'fits'}
                                                                     for m in json.loads(payload)['memories']]})
REPORTS = {}


def fake_review(rid):
    with store.db() as c: title = c.execute('SELECT title FROM records WHERE id=?', (rid,)).fetchone()[0]
    with store.db() as c:
        c.execute("INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,finished_at,report,context) VALUES (?,?,?,?,?,?,?,?,?)",
                  (uuid.uuid4().hex, rid, 'complete', 'openai', 'gpt-6-luna', store.now(), store.now(),
                   REPORTS.get(title, 'Recommendation: approve\nImpact: low\nConflict: no'), '{}'))
    return {'status': 'complete'}


temple.review_record = fake_review
temple.save_settings(True, 'openai')

SPAWNED = []
_spawn = store.spawn
def _tracked_spawn(*a, **k):
    th = _spawn(*a, **k); SPAWNED.append(th); return th
store.spawn = _tracked_spawn


def settle():
    """Wait for the background work (Temple's review and categorising, then the router and the sharing check)."""
    while SPAWNED:
        SPAWNED.pop(0).join(timeout=30)


def who(oid, email, roles=(), grps=None):
    claims = [{'typ': 'name', 'val': email.split('@')[0].capitalize()}] + [{'typ': 'roles', 'val': r} for r in roles]
    claims += [{'typ': 'groups', 'val': g} for g in (grps or [])]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


def copilot(oid, fn, *a, **k):
    """A call through the outside connector from Microsoft 365 Copilot, as alice-mcp makes it: the caller from the token."""
    os.environ.pop('ALICE_TRUST_EASYAUTH', None)
    old_v, old_w, old_e = mcp_server._viewer, mcp_server._who, mcp_server.EXTERNAL
    mcp_server._viewer = lambda: users.connector_viewer(oid)
    mcp_server._who = lambda: external_auth.Caller('Microsoft Copilot', 'copilot')
    mcp_server.EXTERNAL = object()
    try: return fn(*a, **k)
    finally:
        mcp_server._viewer, mcp_server._who, mcp_server.EXTERNAL = old_v, old_w, old_e
        store.VIEWER.set(None)
        os.environ['ALICE_TRUST_EASYAUTH'] = '1'


def activity(action):
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM activity WHERE action=? ORDER BY id', (action,))]


V = lambda oid: users.viewer_for(oid)


def sees(oid, kind, iid):
    with store.as_viewer(V(oid)): return store.can_see(kind, iid)


def kstatus(fid):
    with store.db() as c: return c.execute('SELECT status FROM knowledge_meta WHERE file_id=?', (fid,)).fetchone()[0]


def status(rid):
    with store.db() as c: return c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]


# ---------------- the company deploys Alice ----------------
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
E = who(OWNER, 'stefan@example.org', ['Alice.Owner'])
A = who(ADMIN, 'admin@northfield.example.org', ['Alice.Admin'])
H0 = who(HANA, 'hana@northfield.example.org', ['Alice.Member'])
MO_H = who(MO, 'mo@northfield.example.org', ['Alice.Member'])
SO = who(SOL, 'sol@northfield.example.org', ['Alice.Member'], [G_SALES])
for h in (E, A, H0, MO_H, SO): cl.get('/', headers=h)
users._forget(); spaces.forget()
store.create_category('HR'); memory_tags.set_category_area('HR', 'work')
for rid in ('open_spaces', 'temple_router'):
    with store.db() as c: c.execute('UPDATE rules SET enabled=1 WHERE id=?', (rid,))
rules_engine._rules_changed(); spaces.forget()
t('the router rule is on the Rules page (Organisation set)', any(r['id'] == 'temple_router' and r['set_key'] == 'organisation' for r in rules_engine.all_rules()))
cl.put('/admin/api/auto-approve', json={'on': True}, headers=E)
t('automatic approval is on', autoapprove.on())

HR = cl.post('/admin/api/spaces', headers=A, json={'name': 'HR', 'description': 'HR policy and practice'}).json()['id']
SALES = cl.post('/admin/api/spaces', headers=A, json={'name': 'Sales', 'description': 'The sales team'}).json()['id']
cl.put(f'/admin/api/spaces/{HR}/members', headers=A, json={'member': MO, 'role': 'manage'})
users._forget(); spaces.forget()

# ---------------- restricted spaces: a stated purpose, made by an Admin or a space's manager ----------------
r = cl.post('/admin/api/spaces', headers=SO, json={'name': 'Sales casework', 'description': 'Named customers', 'kind': 'restricted'})
t('a Member who manages no space cannot make a restricted space', r.status_code == 403)
r = cl.post('/admin/api/spaces', headers=MO_H, json={'name': 'HR casework', 'kind': 'restricted'})
t('a restricted space needs its purpose', r.status_code == 400 and 'for' in r.json()['detail'])
r = cl.post('/admin/api/spaces', headers=MO_H, json={'name': 'HR team space', 'description': 'x'})
t('…and a Member who manages a space still cannot make a team space', r.status_code == 403)
r = cl.post('/admin/api/spaces', headers=MO_H, json={'name': 'HR casework', 'description': 'HR casework about named employees', 'kind': 'restricted'})
CASE = r.json().get('id')
t('the manager of a space makes a restricted space with its purpose', r.status_code == 200 and spaces.names()[CASE]['kind'] == 'restricted')
t('…and manages it', spaces.managers(CASE) == {MO})
t('a restricted space is never open, even with "Team spaces are open" on', CASE not in spaces.open_spaces())
t('new spaces hold clashes for their managers; spaces from before keep noting them',
  spaces.clash_policy(HR) == 'wait' and spaces.clash_policy(CASE) == 'wait' and spaces.clash_policy(spaces.WORK) == 'note')
r = cl.put(f'/admin/api/spaces/{HR}/rules', headers=SO, json={'restricted_space': CASE})
t('only a manager names a team\'s restricted space', r.status_code == 403)
r = cl.put(f'/admin/api/spaces/{HR}/rules', headers=MO_H, json={'restricted_space': SALES})
t('…and it must be a restricted space', r.status_code == 400)
r = cl.put(f'/admin/api/spaces/{HR}/rules', headers=MO_H, json={'restricted_space': CASE})
t('HR\'s manager names HR casework as HR\'s restricted space', r.status_code == 200 and spaces.restricted_for(HR) == CASE)
t('…logged', any('HR casework' in a['detail'] for a in activity('space_rules_set')))
lst = cl.get('/admin/api/spaces', headers=MO_H).json()
hr_card = next(s for s in lst['spaces'] if s['id'] == HR)
t('the Spaces page shows the kind, the restricted space and the clash rule', hr_card['restricted_space'] == CASE and hr_card['clash_policy'] == 'wait'
  and next(s for s in lst['spaces'] if s['id'] == CASE)['kind_label'] == 'Restricted' and lst['router_on'] and lst['can_create_restricted'])

# ---------------- the HR adviser joins Entra group HR-Team ----------------
r = cl.post('/admin/api/groups', headers=A, json={'group_id': G_HR, 'label': 'HR-Team', 'profile': users.TEAM_PROFILE,
                                                  'spaces': [{'space': HR, 'role': 'contribute'}, {'space': CASE, 'role': 'contribute'}]})
t('an Admin maps HR-Team to HR and HR casework', r.status_code == 200)
cl.post('/admin/api/groups', headers=A, json={'group_id': G_SALES, 'label': 'Sales', 'spaces': [{'space': SALES, 'role': 'contribute'}]})
H = who(HANA, 'hana@northfield.example.org', ['Alice.Member'], [G_HR])
cl.get('/', headers=H); cl.get('/', headers=SO)
users._forget(); spaces.forget()
with store.as_viewer(V(HANA)):
    t('she contributes to HR and HR casework from her first sign-in', spaces.may_contribute(V(HANA), HR) and spaces.may_contribute(V(HANA), CASE))
    t('her team space for new items is HR (never the restricted space)', spaces.default_for(V(HANA)) == HR)
# An existing, approved policy decision in HR (from before she joined)
with store.as_viewer(V(MO)):
    old = store.propose_decision('Absence reporting', 'Staff report absence to HR by email before 10am on the first day.', 'HR policy 2025',
                                 rationale='One place for absence records.')['id']
settle()
with store.db() as c: c.execute("UPDATE records SET status='approved' WHERE id=?", (old,))
spaces._place('record', old, HR)

# ---------------- a policy chat in Copilot lands in HR, and Sales can read it ----------------
n_screen = len(SCREENED)
pol = copilot(HANA, mcp_server.propose_knowledge, 'Flexible working policy',
              'From a Copilot chat about the flexible working policy: requests are answered within four weeks, and a refusal gives one of the '
              'eight statutory business reasons.', 'Copilot chat with Hana', category='HR')
settle()
pid = pol['id']
t('the policy note from Copilot lands in HR', spaces.space_of('file', pid) == HR)
t('…approved after the checks (notes from Copilot are on by default)', kstatus(pid) == 'active')
t('…through the sharing check', len(SCREENED) > n_screen)
rt = spaces.route_of('file', pid)
t('the route and its reason are kept on the item', rt and rt['route'] == 'work' and rt['reason'] and rt['space_name'] == 'HR')
t('Sales reads it (HR is open to the organisation)', sees(SOL, 'file', pid))
t('…and the owner and Admin too', sees(OWNER, 'file', pid) and sees(ADMIN, 'file', pid))

# ---------------- a named employee's absence goes only to HR casework ----------------
ab = copilot(HANA, mcp_server.propose_record, 'Dev Patel absence', 'Dev Patel in the warehouse has been on sickness absence since 2 October; '
             'his return-to-work meeting is booked for the 20th.', 'Hana in Copilot')
settle()
aid = ab['id']
t('a named employee\'s absence goes to HR casework', spaces.space_of('record', aid) == CASE)
t('…with the reason kept', spaces.route_of('record', aid)['route'] == 'sensitive')
t('…readable only by HR casework\'s members: not Sales, not the owner, not the Admin',
  sees(HANA, 'record', aid) and sees(MO, 'record', aid) and not sees(SOL, 'record', aid) and not sees(OWNER, 'record', aid) and not sees(ADMIN, 'record', aid))
t('…and it never sat in an open space', not any(m for m in activity('space_shared') if aid == m['target']))
t('the routing is logged', any(a['target'] == aid for a in activity('space_routed')))

# ---------------- "I prefer bullet points" goes to her personal space ----------------
bp = copilot(HANA, mcp_server.propose_record, 'Bullet points', 'I prefer bullet points in summaries.', 'Hana in Copilot')['id']
settle()
t('"I prefer bullet points" stays in her personal space', spaces.space_of('record', bp) == spaces.personal_space(HANA))
t('…with the reason (about her)', spaces.route_of('record', bp)['route'] == 'self')
t('…seen by nobody else', not sees(SOL, 'record', bp) and not sees(OWNER, 'record', bp) and not sees(MO, 'record', bp))

# ---------------- for the whole organisation, and unsure ----------------
gen = copilot(HANA, mcp_server.propose_knowledge, 'Office closure', 'Everyone at Northfield: the office is closed on 24 December and staff '
              'work from home that day.', 'Copilot chat with Hana', category='HR')['id']
settle()
t('something for the whole organisation goes to HR when she cannot add to the Organisation space', spaces.space_of('file', gen) == HR)
cl.put(f'/admin/api/spaces/{spaces.ORG}/members', headers=A, json={'member': HANA, 'role': 'contribute'})
spaces.forget()
gen2 = copilot(HANA, mcp_server.propose_knowledge, 'Office closure 2', 'Everyone at Northfield: the office is closed on 31 December too, '
               'with the same arrangements.', 'Copilot chat with Hana', category='HR')['id']
settle()
t('…and to the Organisation space when she can', spaces.space_of('file', gen2) == spaces.ORG)
vague = copilot(HANA, mcp_server.propose_record, 'Note', 'Remember something or other about the thing next week.', 'Hana in Copilot')['id']
settle()
held = [h for h in spaces.held(V(HANA)) if h['item_id'] == vague]
t('unsure: it waits for its author, with Temple\'s reason', spaces.space_of('record', vague) == spaces.personal_space(HANA)
  and held and held[0]['as'] == 'author' and any('not sure' in r for r in held[0]['reasons']))

# ---------------- special category data never lands in an open space ----------------
sc = copilot(HANA, mcp_server.propose_record, 'Shift pattern', 'Priya Shah has epilepsy, so the night shift rota keeps her on days.', 'Hana in Copilot')['id']
settle()
t('routed as work, but the sharing check finds special category data: it goes to HR casework', spaces.space_of('record', sc) == CASE)
t('…never into HR (open)', not sees(SOL, 'record', sc))
cl.put(f'/admin/api/spaces/{HR}/rules', headers=MO_H, json={'restricted_space': ''})
spaces.forget()
sc2 = copilot(HANA, mcp_server.propose_record, 'Rota', 'Priya Shah has epilepsy; check the rota with her line manager.', 'Hana in Copilot')['id']
settle()
t('with no restricted space named for the team, it is held for its author, never placed in the open space',
  spaces.space_of('record', sc2) == spaces.personal_space(HANA) and any(h['item_id'] == sc2 for h in spaces.held(V(HANA))))
ab2 = copilot(HANA, mcp_server.propose_record, 'Dev Patel absence 2', 'Dev Patel absence update: sickness absence continues to the 30th.', 'Hana in Copilot')['id']
settle()
t('…and so is an item Temple routes as about a named person', spaces.space_of('record', ab2) == spaces.personal_space(HANA))
cl.put(f'/admin/api/spaces/{HR}/rules', headers=MO_H, json={'restricted_space': CASE})
spaces.forget()

# ---------------- a clash with an existing policy decision waits for HR's managers ----------------
REPORTS['Absence reporting by phone'] = 'Recommendation: clarify\nReasons: overturns the absence reporting decision.\nImpact: medium\nConflict: yes'
cd = copilot(HANA, mcp_server.propose_decision, 'Absence reporting by phone', 'Staff phone their line manager before 9am on the first day of absence.',
             'Hana in Copilot', rationale='Faster cover.')['id']
settle()
t('the clashing decision is in HR and waits (not recorded)', spaces.space_of('record', cd) == HR and status(cd) == 'proposed')
st = autoapprove._state('memory', cd)
t('…held for HR\'s managers, saying so', st and st['state'] == 'held' and 'managers of HR' in st['reason'])
mine = {a['id'] for a in cl.get('/admin/api/spaces/approvals', headers=MO_H).json()['items']}
t('HR\'s manager sees it in their approvals', cd in mine)
t('…and HR casework\'s waiting memory (from Copilot) too', aid in mine)
t('the adviser (a contributor) does not', cd not in {a['id'] for a in cl.get('/admin/api/spaces/approvals', headers=H).json()['items']})
t('she approves "I prefer bullet points" herself: it waits in her personal space',
  bp in {a['id'] for a in cl.get('/admin/api/spaces/approvals', headers=H).json()['items']})
t('Sales cannot decide HR\'s item', cl.post(f'/admin/api/spaces/approvals/memory/{cd}', headers=SO, json={'decision': 'approved'}).status_code == 403)

# ---------------- nothing waits for the owner ----------------
acts = cl.get('/admin/api/actions', headers=E).json()
body = json.dumps(acts)
t('nothing waits for the owner: none of these items is on the owner\'s Actions', not any(i in body for i in (cd, aid, bp, vague, sc2, ab2)))
sm = next((s for s in acts['sections'] if s['key'] == 'space_managers'), None) if isinstance(acts, dict) and 'sections' in acts else \
     next((s for s in acts if isinstance(s, dict) and s.get('key') == 'space_managers'), None)
t('…the owner sees a summary by space (counts only)', sm and sm['count'] >= 2 and sm['info'] and 'HR' in json.dumps(sm['items']))
r = cl.post(f'/admin/api/spaces/approvals/memory/{cd}', headers=MO_H, json={'decision': 'approved', 'note': 'Phone first is the new rule from November.'})
t('HR\'s manager approves the decision', r.status_code == 200 and status(cd) == 'approved')
log = activity('space_approval_decided')
t('…logged with who and why', log and 'manager' in log[-1]['detail'] and 'November' in log[-1]['detail'])
r = cl.post(f'/admin/api/spaces/approvals/memory/{bp}', headers=H, json={'decision': 'approved'})
t('she approves her own preference', r.status_code == 200 and status(bp) == 'approved')

# ---------------- removed from HR-Team, she loses HR and HR casework at next sign-in; her work stays ----------------
cl.get('/', headers=who(HANA, 'hana@northfield.example.org', ['Alice.Member'], []))
users._forget(); spaces.forget()
with store.db() as c:
    left = {r[0] for r in c.execute('SELECT space_id FROM space_members WHERE member_key=?', (HANA,))}
t('removed from HR-Team, she leaves HR and HR casework at her next sign-in', HR not in left and CASE not in left)
with store.as_viewer(V(HANA)):
    t('…she can no longer add to HR', not spaces.may_contribute(V(HANA), HR))
t('…nor read HR casework', not sees(HANA, 'record', aid) and not sees(HANA, 'record', sc))
t('…her work items stay where they are, with her as author', spaces.space_of('file', pid) == HR and spaces.space_of('record', aid) == CASE
  and spaces.space_of('record', cd) == HR and store.author_of('record', aid) == HANA)
t('…HR casework\'s members still read them', sees(MO, 'record', aid))
t('…and her personal space is still hers', sees(HANA, 'record', bp) and spaces.space_of('record', bp) == spaces.personal_space(HANA))

# ---------------- the router off: the sharing check alone, as before ----------------
with store.db() as c: c.execute("UPDATE rules SET enabled=0 WHERE id='temple_router'")
rules_engine._rules_changed(); spaces.forget()
cl.get('/', headers=H); users._forget(); spaces.forget()
n = len(ROUTED)
off = copilot(HANA, mcp_server.propose_knowledge, 'Lone working policy', 'Lone working: check in with the duty manager every two hours on a '
              'late shift.', 'Copilot chat with Hana', category='HR')['id']
settle()
t('with the router rule off, nothing is routed and items go to the default space through the sharing check', len(ROUTED) == n
  and spaces.space_of('file', off) == HR and spaces.route_of('file', off) is None)
t('Temple\'s router is a registered agent', any(a[0] == 'temple-router' for a in __import__('agents').BUILTIN))
for k in ('ALICE_TRUST_EASYAUTH', 'ALICE_USE_APP_ROLES', 'ALICE_OWNER_OBJECT_ID'): os.environ.pop(k, None)
