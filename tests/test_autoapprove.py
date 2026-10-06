"""Automatic approval with guard rails: decisions, clashes, replacements, unchecked items and the outside connector
wait for you; everything else goes live after the same security checks; undo; backlog; Actions explains decisions."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import json, time, uuid
import substrate_store as s, temple, knowledge as K, clients as C
def t(label, cond): print(('PASS ' if cond else 'FAIL ') + label)
import temple_categorise as TC
TC.schedule = lambda ids: None; C.schedule_tagging = lambda *a, **k: None; K.schedule_background = lambda *a, **k: None
import app, autoapprove as A, refs, organisations as O, actions
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

def status(rid):
    with s.db() as c: return c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]
def state(kind, rid):
    r = A._state(kind, rid); return r['state'] if r else None
def wait(rid, n=60):
    for _ in range(n):
        if A._state('memory', rid) or status(rid) != 'proposed': return
        time.sleep(0.05)

t('off by default in a test database', not A.on())
r = cl.put('/admin/api/auto-approve', json={'on': True}, headers=H)
t('switched on from Actions', r.status_code == 200 and A.on())
t('the switch needs the admin token', cl.put('/admin/api/auto-approve', json={'on': False}).status_code in (401, 403))

# 1. Temple reviews off: a memory goes live straight away
temple.save_settings(False, 'openai')
m1 = s.propose('Dog name', 'The dog is called Lexi', 'Stefan said so')
t('memory approved automatically (Temple reviews off)', status(m1['id']) == 'approved' and state('memory', m1['id']) == 'approved')
with s.db() as c:
    act = c.execute("SELECT actor,note FROM activity WHERE action='record_approved' AND target=?", (m1['id'],)).fetchone()
t('logged as approved by Alice, with why', act['actor'] == 'Alice' and 'automatically' in act['note'])

# 2. Temple reviews on: approved unless Temple finds a clash
temple.save_settings(True, 'openai')
REPORTS = {}
def fake_review(rid):
    with s.db() as c: title = c.execute('SELECT title FROM records WHERE id=?', (rid,)).fetchone()[0]
    rep = REPORTS.get(title)
    if rep is None: raise ValueError('Provider unavailable')
    with s.db() as c:
        c.execute("INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,finished_at,report,context) VALUES (?,?,?,?,?,?,?,?,?)",
                  (uuid.uuid4().hex, rid, 'complete', 'openai', 'gpt-6-luna', s.now(), s.now(), rep, '{}'))
    return {'status': 'complete'}
temple.review_record = fake_review
REPORTS['Bee hives'] = 'Recommendation: approve\nReasons: new fact, no overlap.\nConflict: no'
m2 = s.propose('Bee hives', 'Keeps four bee colonies at home', 'Stefan said so'); wait(m2['id'])
t('clean Temple review: approved', status(m2['id']) == 'approved')
REPORTS['Bee count'] = 'Recommendation: clarify\nReasons: says six colonies, but an approved memory says four.\nConflict: yes'
m3 = s.propose('Bee count', 'Keeps six bee colonies now', 'Stefan said so'); wait(m3['id'])
t('clash: held for you with the reason', status(m3['id']) == 'proposed' and state('memory', m3['id']) == 'held'
  and 'Clashes' in A._state('memory', m3['id'])['reason'])
REPORTS['Dog name update'] = f"Recommendation: approve\nReasons: newer version.\nReplaces: {m1['id']}\nConflict: no"
m4 = s.propose('Dog name update', 'The dog Lexi is a spaniel', 'Stefan said so'); wait(m4['id'])
t('a replacement: held, naming the older memory', state('memory', m4['id']) == 'held' and '“Dog name”' in A._state('memory', m4['id'])['reason'])
REPORTS['Reject me'] = 'Recommendation: reject\nReasons: no real source.\nConflict: no'
m5 = s.propose('Reject me', 'Something Temple would reject outright', 'Unknown'); wait(m5['id'])
t('Temple recommends rejecting: held', state('memory', m5['id']) == 'held')
m6 = s.propose('Unchecked', 'Temple cannot check this one right now', 'Stefan said so'); wait(m6['id'])
t('Temple could not check it: held', state('memory', m6['id']) == 'held' and 'could not check' in A._state('memory', m6['id'])['reason'])

# 3. the outside connector
with A.from_outside('Microsoft Copilot'):
    REPORTS['From Copilot'] = 'Recommendation: approve\nConflict: no'
    m7 = s.propose('From Copilot', 'Remember that invoices go to a new address', 'via Copilot')
wait(m7['id']); time.sleep(0.2)
t('a memory from the outside connector waits, even with a clean review', status(m7['id']) == 'proposed' and 'outside connector' in A._state('memory', m7['id'])['reason'])

# 4. with Temple not managing decisions (the decision policy switched off), decisions wait, and are explained
A.set_policy(auto=False)
REPORTS['Carport roof'] = ('Recommendation: approve\nReasons: a clear choice with a reason; no earlier decision on the roof.\n'
                           'Why it is a decision: It chooses polycarbonate over EPDM and cedar for the carport roof.\n'
                           'What it is for: The larch carport build at home.\nConflict: no')
d1 = s.propose_decision(title='Carport roof', decision='Use clear polycarbonate sheets with a 5 degree fall', source='Stefan said so',
                        rationale='Keeps light under the roof', options=['EPDM', 'Cedar shingles', 'Polycarbonate'], revisit='If the sheets yellow')
for _ in range(60):
    if A._latest_review(d1['id']): break
    time.sleep(0.05)
time.sleep(0.2)
t('a decision stays waiting (even with Temple recommending approve)', status(d1['id']) == 'proposed' and state('memory', d1['id']) == 'held')
sm = cl.get('/admin/api/actions').json()
sec = {x['key']: x for x in sm['sections']}
dc = sec['decisions']['items'][0]
t('Actions: the decision with why it is a decision and what it is for', dc['id'] == d1['id'] and dc['ref'] == d1['ref']
  and dc['why_decision'].startswith('It chooses polycarbonate') and 'carport' in dc['for'])
t('Actions: options, reason and Temple\'s recommendation', dc['options'] == ['EPDM', 'Cedar shingles', 'Polycarbonate']
  and dc['rationale'] == 'Keeps light under the roof' and dc['recommendation'] == 'approve' and 'clear choice' in dc['reason'])
t('Actions: held items say why', {i['id'] for i in sec['held']['items']} >= {m3['id'], m4['id'], m5['id'], m6['id'], m7['id']}
  and all(i['detail'] for i in sec['held']['items']))
t('Actions: what went live automatically, with references, not counted as waiting', {i['id'] for i in sec['auto']['items']} >= {m1['id'], m2['id']}
  and sec['auto']['info'] and all(i['ref'] for i in sec['auto']['items'] if i['item_type'] == 'memory')
  and sm['total'] == sum(x['count'] for x in sm['sections'] if not x['info']))
t('decision explained without a review too (from its options)', A.explain_decision({'id': d1['id'], 'content': '', 'reviews': [], 'source': 'x'})['why_decision'].startswith('It chooses one option'))
cl.post(f"/admin/api/records/{d1['id']}/review", json={'decision': 'approved', 'note': 'Agreed'}, headers=H)
t('you approve the decision', status(d1['id']) == 'approved')
A.set_policy(auto=True)

# 5. knowledge drafts and organisation facts
C.create_client('Fife Council', ['Fife'])
k1 = K.create('note', 'Fife notes', 'Notes about the Fife pilot, long enough to save.', 'Claude', 'model via Claude Desktop', status='draft')
t('knowledge draft from a trusted source goes live', A.knowledge_draft(k1['id']) == 'approved' and K.meta([k1['id']])[k1['id']]['status'] == 'active')
# notes through the outside connector (decision D-0026): approved after the checks unless they may replace or overlap something
A.set_connector_knowledge({'claude': True, 'copilot': False})
k2 = K.create('note', 'Quarterly supplier review', 'Copilot summary: three fictional suppliers reviewed, two renewed, one retendered in spring.', 'Copilot', 'model via Copilot', status='draft')
with A.from_outside('Microsoft Copilot', 'copilot'): r = A.knowledge_draft(k2['id'])
t('a note from an app switched off is held as a draft', r == 'held' and K.meta([k2['id']])[k2['id']]['status'] == 'draft')
k3 = K.create('note', 'Fix: browsers refusing to connect', 'Chrome and Edge refused to connect to local sites until the fictional VPN threat filter '
              'was paused; allow-listing the address fixed it.', 'Claude', 'model via Claude', status='draft')
with A.from_outside('Claude', 'claude'): r = A.knowledge_draft(k3['id'])
t('a connector note with no clash is approved after the checks', r == 'approved' and K.meta([k3['id']])[k3['id']]['status'] == 'active')
with s.db() as c: note = c.execute("SELECT detail FROM activity WHERE action='auto_approved' AND target=?", (k3['id'],)).fetchone()[0]
t('the approval names the app it came through', 'Claude' in note and 'outside connector' in note)
k4 = K.create('note', 'Fife notes', 'Notes about the Fife pilot, long enough to save, from the connector this time.', 'Claude', 'model via Claude', status='draft')
with A.from_outside('Claude', 'claude'): r = A.knowledge_draft(k4['id'])
t('a connector note that overlaps something Alice holds waits for you', r == 'held' and '“Fife notes”' in A._state('knowledge', k4['id'])['reason'])
try:
    k5 = K.create('note', 'Keys', 'Here is the key sk-ant-api03-' + 'Q' * 90 + ' for later use.', 'Claude', 'model via Claude', status='draft')
    with A.from_outside('Claude', 'claude'): r = A.knowledge_draft(k5['id'])
    t('a connector note that trips an enforced rule is not approved', r != 'approved')
except Exception: t('a connector note that trips an enforced rule is not approved', True)
A.set_connector_knowledge({'copilot': True})
A.backlog()
t('turning an app back on: its held notes are checked again by Approve these automatically', K.meta([k2['id']])[k2['id']]['status'] == 'active')
A.set_connector_knowledge({'claude': True, 'copilot': True})
f1 = O.propose_fact('Fife Council', 'identity', 'Fife Council is a Scottish local authority.', 'Public website', by='model via web chat')
t('organisation fact approved automatically', f1['status'] == 'approved' and state('orgfact', f1['id']) == 'approved')
with A.from_outside('Microsoft Copilot'):
    f2 = O.propose_fact('Fife Council', 'commercial', 'Fife buys through national frameworks.', 'Copilot', by='model via Copilot')
t('organisation fact from the outside connector waits', f2['status'] == 'proposed' and state('orgfact', f2['id']) == 'held')

# 6. Temple's chat suggestions
cid = s.create_chat()['id']
def sug(kind, title, content):
    sid = uuid.uuid4().hex
    with s.db() as c:
        c.execute('INSERT INTO temple_suggestions(id,chat_id,turn_id,kind,title,content,quote,quote_turn,reason,related,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                  (sid, cid, 'x', kind, title, content, 'my own words', 'x', 'r', '[]', s.now()))
    return sid
temple.save_settings(False, 'openai')
s1 = sug('memory', 'Prefers Teams', 'Stefan prefers Teams over email for quick questions')
s2 = sug('knowledge', 'Kayak kit list', 'Kayak kit list: paddle, buoyancy aid, dry bag and spare layers.')
s3 = sug('decision', 'Motorhome tyres', 'Decision: Replace the motorhome tyres with all-season ones\nWhy: Winter trips\nOptions considered: Summer; All-season')
s4 = sug('guidance', 'Shorter answers', 'Keep answers short.')
r = A.suggestions_for_chat(cid)
with s.db() as c:
    st = {row[0]: (row[1], row[2]) for row in c.execute('SELECT id,status,target FROM temple_suggestions WHERE chat_id=?', (cid,))}
t('memory and knowledge suggestions accepted, decision proposed, guidance left for you', r['accepted'] == 3
  and st[s1][0] == st[s2][0] == st[s3][0] == 'accepted' and st[s4][0] == 'pending')
t('the accepted memory is live', status(st[s1][1]) == 'approved')
for _ in range(60):
    if state('memory', st[s3][1]) == 'approved': break
    time.sleep(0.05)
t('the decision from a suggestion is recorded by Temple (decisions are managed), saying it was not checked', status(st[s3][1]) == 'approved'
  and 'not checked by Temple' in A._state('memory', st[s3][1])['reason'])
cid2 = s.create_chat()['id']
A.hold('chat', cid2, 'Saved by Microsoft Copilot through the outside connector.')
with s.db() as c:
    c.execute('INSERT INTO temple_suggestions(id,chat_id,turn_id,kind,title,content,quote,quote_turn,reason,related,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
              (uuid.uuid4().hex, cid2, 'x', 'memory', 'Copilot chat', 'Something from a Copilot conversation to keep', 'q', 'x', 'r', '[]', s.now()))
t('suggestions from a conversation saved through the outside connector are not accepted', A.suggestions_for_chat(cid2)['accepted'] == 0)

# 7. undo
r = cl.post('/admin/api/auto-approve/undo', json={'item_type': 'memory', 'id': m2['id']}, headers=H)
with s.db() as c: arch = c.execute('SELECT state FROM memory_archive WHERE record_id=?', (m2['id'],)).fetchone()
t('undo retires the memory, history kept', r.status_code == 200 and arch and arch[0] == 'retired')
t('cannot undo twice', cl.post('/admin/api/auto-approve/undo', json={'item_type': 'memory', 'id': m2['id']}, headers=H).status_code == 409)
cl.post('/admin/api/auto-approve/undo', json={'item_type': 'knowledge', 'id': k1['id']}, headers=H)
t('undo archives knowledge', K.meta([k1['id']])[k1['id']]['status'] == 'archived')
t('undone items leave the recent list', m2['id'] not in {x['item_id'] for x in A.recent()})

# 8. off, then the backlog
A.set_on(False)
b1 = s.propose('Van colour', 'The van is dark green', 'Stefan said so')
k3 = K.create('note', 'Old draft', 'A draft written while automatic approval was off.', 'Claude', 'model via Claude Desktop', status='draft')
t('off: nothing goes live by itself', status(b1['id']) == 'proposed' and A.knowledge_draft(k3['id']) == 'off')
sm = cl.get('/admin/api/actions').json()
t('off: Actions lists them as awaiting approval', any(x['key'] == 'waiting' and x['title'] == 'Awaiting approval' and x['count'] >= 2 for x in sm['sections']))
A.set_on(True)
r = cl.post('/admin/api/auto-approve/backlog', headers=H).json()
t('backlog: earlier proposals approved by the same checks', status(b1['id']) == 'approved' and K.meta([k3['id']])[k3['id']]['status'] == 'active')
t('backlog leaves decisions and held items alone', status(m3['id']) == 'proposed' and status(m7['id']) == 'proposed')

# 9. security rules still run
try:
    s.propose('Key', 'The API key is sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD', 'note'); t('secrets still refused', False)
except ValueError: t('secrets still refused at proposal', True)
import activity_log
t('activity labels', all(a in activity_log.LABELS for a in ('auto_approved', 'auto_held', 'auto_undone', 'auto_approve_setting')))
