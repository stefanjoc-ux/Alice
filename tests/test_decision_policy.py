"""Temple manages decisions (Stefan's decision, 5 Oct 2026): once checked, a decision is recorded with who made it, clashes
included (noted, not held). Only the decision policy holds one: categories that always need approval, or Temple's impact
rating at or above a level. A held decision is emailed to its category's owner (or the default approver) through Microsoft
Graph; without email set up it simply waits on Actions, and the log says why. Decisions waiting from before are run through
the same checks. Nothing here contacts Microsoft or a model."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, os, time, uuid
import substrate_store as s, temple, knowledge as K, clients as C
import temple_categorise as TC
TC.schedule = lambda ids: None; C.schedule_tagging = lambda *a, **k: None; K.schedule_background = lambda *a, **k: None
import app, autoapprove as A, notify as N, actions
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

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
temple.save_settings(True, 'openai')
def status(rid):
    with s.db() as c: return c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]
def state(rid):
    r = A._state('memory', rid); return (r or {}).get('state'), (r or {}).get('reason', '')
def settle(rid, n=80):
    for _ in range(n):
        st = A._state('memory', rid)
        if st and st['state'] in ('approved', 'held') and st['reason'] != A.OLD_HOLD: return
        time.sleep(0.05)
def log(action, rid):
    with s.db() as c: return c.execute('SELECT detail FROM activity WHERE action=? AND target=? ORDER BY id DESC', (action, rid)).fetchone()
def dec(title, decision, category='', report='Recommendation: approve\nImpact: low\nConflict: no'):
    if report is not None: REPORTS[title] = report
    d = s.propose_decision(title=title, decision=decision, source='Stefan said so', rationale='Because it is simpler', category=category)
    settle(d['id']); return d['id']

# while automatic approval is off, decisions wait as before
t('automatic approval off: decisions are not managed', not A.managing_decisions())
d0 = dec('Laptop bag', 'Use the grey rucksack for client visits')
t('with automatic approval off a decision waits for you', status(d0) == 'proposed' and state(d0)[0] == 'held')
cl.put('/admin/api/auto-approve', json={'on': True}, headers=H)
t('switched on: Temple manages decisions by default', A.managing_decisions() and A.policy() == {'auto': True, 'categories': {}, 'impact': 'off', 'approver': ''})

# recorded, with who made it
d1 = dec('Carport roof', 'Use clear polycarbonate sheets with a five degree fall')
st, why = state(d1)
t('a checked decision is recorded automatically', status(d1) == 'approved' and st == 'approved')
t('with who made it and Temple\'s impact rating', 'for ' + s.owner_name() in why and 'low impact' in why)
meta = s.record_kinds([d1])[d1]['decision']
t('who made it is kept with the decision', meta['made_by'] == s.owner_name() and meta['via'] == '')
with s.db() as c: act = c.execute("SELECT actor,note FROM activity WHERE action='record_approved' AND target=?", (d1,)).fetchone()
t('logged as recorded by Alice, with why', act['actor'] == 'Alice' and 'Recorded automatically' in act['note'])

# a clash is recorded too, and noted: Alice records, she does not mediate
d2 = dec('Carport roof again', 'Use EPDM rubber on the carport roof instead of polycarbonate',
         report='Recommendation: clarify\nReasons: overturns the polycarbonate decision.\nImpact: medium\nConflict: yes')
st, why = state(d2)
t('a contradicting decision is still recorded', status(d2) == 'approved' and st == 'approved')
t('and the clash is noted with it', 'Contradicts an earlier decision' in why and 'overturns the polycarbonate' in why)

# Temple could not check it: still recorded, saying so
d3 = dec('Fence posts', 'Use pressure-treated posts for the paddock fence', report=None)
st, why = state(d3)
t('Temple could not check it: recorded, and it says so', st == 'approved' and 'not checked by Temple' in why)

# through the outside connector: recorded, with the connector named
with A.from_outside('Microsoft Copilot'):
    REPORTS['Meeting cadence'] = 'Recommendation: approve\nImpact: low\nConflict: no'
    dx = s.propose_decision(title='Meeting cadence', decision='Hold the RGU check-in fortnightly on Tuesdays', source='Copilot chat')
settle(dx['id'])
t('a decision from Copilot is recorded with who made it and the connector', status(dx['id']) == 'approved' and '(via Microsoft Copilot)' in state(dx['id'])[1])

# the policy: categories and impact
s.create_category('Finance', 'Money'); s.create_category('Home', 'House')
for bad, body in [('unknown category', {'categories': {'Nope': ''}}), ('bad owner email', {'categories': {'Finance': 'not-an-email'}}),
                  ('bad impact', {'impact': 'huge'}), ('bad approver', {'approver': 'x@'})]:
    r = cl.put('/admin/api/decision-policy', json={'auto': True, **body}, headers=H)
    t('refused: ' + bad, r.status_code == 400)
t('the policy needs the admin token', cl.put('/admin/api/decision-policy', json={'auto': True}).status_code in (401, 403))
r = cl.put('/admin/api/decision-policy', json={'auto': True, 'categories': {'Finance': 'finance.owner@example.org'}, 'impact': 'high',
                                               'approver': 'approver@example.org'}, headers=H)
p = r.json()
t('policy saved: Finance needs approval, high impact needs approval', r.status_code == 200 and p['categories'] == {'Finance': 'finance.owner@example.org'}
  and p['impact'] == 'high' and 'Finance' in p['category_names'] and p['email_ready'] is False)

d4 = dec('Supplier payment terms', 'Pay suppliers on 30 day terms from now on', category='Finance')
st, why = state(d4)
t('a decision in a category that needs approval is held', status(d4) == 'proposed' and st == 'held' and 'Decisions in Finance need approval' in why)
t('email not set up: it waits on Actions, and the log says why', 'email is not set up' in (log('decision_owner_not_emailed', d4) or [''])[0])
d5 = dec('Move house', 'Sell the Northampton house next spring', category='Home', report='Recommendation: approve\nImpact: high\nConflict: no')
t('high impact is held', state(d5)[0] == 'held' and 'rated it high impact' in state(d5)[1])
d6 = dec('Mower', 'Service the ride-on mower every March', category='Home', report='Recommendation: approve\nImpact: medium\nConflict: no')
t('medium impact goes through when only high needs approval', state(d6)[0] == 'approved')
d7 = dec('Hedge', 'Cut the beech hedge in late August', category='Home', report='Recommendation: approve\nConflict: no')
t('no impact rating when impact matters: held, saying so', state(d7)[0] == 'held' and 'could not rate its impact' in state(d7)[1])

# email, through a stand-in Microsoft Graph
sent = []
def fake_http(url, data=None, headers=None, timeout=15):
    if 'IDENTITY' in url or 'identity' in url: return 200, {'access_token': 'tok', 'expires_on': str(time.time() + 3600)}
    sent.append({'url': url, 'body': json.loads(data), 'auth': headers.get('Authorization')}); return 202, {}
N.HTTP = fake_http
os.environ.update(ALICE_MAIL_FROM='alice@example.org', IDENTITY_ENDPOINT='http://identity.local/token', IDENTITY_HEADER='h',
                  ALICE_PUBLIC_URL='https://alice.example.org')
t('email set up', N.configured() and cl.get('/admin/api/decision-policy').json()['mail_from'] == 'alice@example.org')
d8 = dec('Bank account', 'Move the business account to the new bank', category='Finance')
m = sent[-1] if sent else {}
msg = (m.get('body') or {}).get('message', {})
t('held decision emailed to the category owner, from Alice\'s mailbox, with the managed identity',
  m.get('url', '').endswith('/users/alice%40example.org/sendMail') and msg['toRecipients'][0]['emailAddress']['address'] == 'finance.owner@example.org'
  and m['auth'] == 'Bearer tok')
t('the email says what, who, why and where to approve', 'Move the business account' in msg['body']['content'] and 'Made by: ' + s.owner_name() in msg['body']['content']
  and 'Decisions in Finance need approval' in msg['body']['content'] and 'https://alice.example.org/admin/actions' in msg['body']['content'])
t('the send is logged', 'finance.owner@example.org' in (log('decision_owner_emailed', d8) or [''])[0])
d9 = dec('Holiday', 'Book the Turkey charter for June', category='Home', report='Recommendation: approve\nImpact: high\nConflict: no')
t('no category owner: the default approver gets it', sent[-1]['body']['message']['toRecipients'][0]['emailAddress']['address'] == 'approver@example.org')
# a decision whose text fails the security checks never reaches the email
import rules_engine as R
orig = R.check_outbound
R.check_outbound = lambda text, *a, **k: (_ for _ in ()).throw(R.RuleViolation('marked')) if 'Move the business account' in text else orig(text, *a, **k)
N.decision_held(d8, 'test', 'finance.owner@example.org')
R.check_outbound = orig
t('text that fails the checks is left out of the email', 'not included in this email' in sent[-1]['body']['message']['body']['content']
  and 'Move the business account' not in sent[-1]['body']['message']['body']['content'])
import demo_instance
demo_instance.ON = True
ok, why = N.send('someone@example.org', 'x', 'y')
demo_instance.ON = False
t('the demo Alice never sends email', not ok and 'demo' in why)

# Actions: held decisions are there, recorded ones are not
sm = cl.get('/admin/api/actions').json()
ids = {i['id'] for i in {x['key']: x for x in sm['sections']}['decisions']['items']}
t('Actions lists the held decisions, not the recorded ones', {d4, d5, d7, d8, d9} <= ids and not ({d1, d2, d6} & ids))
t('Actions explains that Temple records decisions', 'Temple records decisions' in {x['key']: x for x in sm['sections']}['decisions']['note'])
page = cl.get('/admin/actions').text
t('the Decisions settings are on the Actions page', 'id="act-dec"' in page and 'decision-policy' in page)

# undo a recorded decision
r = cl.post('/admin/api/auto-approve/undo', json={'item_type': 'memory', 'id': d6}, headers=H)
with s.db() as c:
    undone = c.execute("SELECT undone_at FROM auto_approvals WHERE item_type='memory' AND item_id=?", (d6,)).fetchone()[0]
    arch = c.execute('SELECT state FROM memory_archive WHERE record_id=?', (d6,)).fetchone()
t('a recorded decision can be undone (taken back out, history kept)', r.status_code == 200 and undone and arch and arch[0] != 'approved')

# decisions waiting from before Temple managed them: the backlog runs them through
A.set_policy(auto=False)
dold = dec('Old decision', 'Keep the motorhome at the farm over winter', report='Recommendation: approve\nImpact: low\nConflict: no')
t('switched off: waits', state(dold)[0] == 'held' and status(dold) == 'proposed')
A.set_policy(auto=True, categories={'Finance': 'finance.owner@example.org'}, impact='high', approver='approver@example.org')
with s.db() as c:   # as it was before this release: held with the old reason
    c.execute("UPDATE auto_approvals SET reason=? WHERE item_type='memory' AND item_id=?", (A.OLD_HOLD, dold))
r = cl.post('/admin/api/auto-approve/backlog', json={}, headers=H).json()
settle(dold)
t('backlog: decisions waiting from before are recorded once checked', r.get('decisions', 0) >= 1 and status(dold) == 'approved' and state(dold)[0] == 'approved')
t('backlog: decisions held by the policy stay held', state(d4)[0] == 'held' and status(d4) == 'proposed')

# switched off again: new decisions wait
A.set_policy(auto=False)
d11 = dec('After switch off', 'Buy a second log splitter for the yard')
t('Temple not managing decisions: new ones wait for you', status(d11) == 'proposed' and 'Temple does not manage decisions' in state(d11)[1])
