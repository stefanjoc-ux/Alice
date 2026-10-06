"""Actions page: everything waiting is counted, and quick decisions work inline."""
import _util
from _util import t
import uuid
import app, substrate_store as s, temple, clients as C, knowledge as K, rules_engine as R, actions
temple.save_settings(False, 'openai')
s.create_category('Work', 'Insight'); s.create_category('Home', 'House and land'); C.create_client('Fife Council', ['Fife'])
p1 = s.propose('Prefers morning meetings', 'Prefers meetings before 11am on weekdays', 'User said in chat')['id']
p2 = s.propose_decision('Carport roof finish', 'Use clear polycarbonate sheets', 'User agreed', rationale='Light', revisit_date='2027-01-01')['id']
with s.db() as c:
    c.execute("INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,report,context) VALUES (?,?,?,?,?,?,?,?)",
              (uuid.uuid4().hex, p1, 'complete', 'openai', 'gpt-6-luna', s.now(), 'Recommendation: approve\nReasons: Clear.', '{}'))
    c.execute("INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,report,error,context) VALUES (?,?,?,?,?,?,?,?,?)",
              (uuid.uuid4().hex, p2, 'failed', 'openai', 'gpt-6-luna', s.now(), '', 'Provider request failed.', '{}'))
draft = K.create('note', 'Status summary', 'A summary of the substrate build and open items.', 'Summary of a conversation', 'model via Claude Desktop', status='draft')['id']
cid = s.create_chat()['id']; sid = uuid.uuid4().hex
with s.db() as c:
    c.execute("INSERT INTO temple_suggestions(id,chat_id,turn_id,kind,title,content,quote,quote_turn,reason,related,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (sid, cid, 't', 'memory', 'Walks Lexi at 7', 'Walks the dog at 7am daily', 'I walk Lexi at 7', 't', 'fact', '[]', s.now()))
a = s._propose_original('Beehive count', 'Has four colonies this year', 'User said')['id']; s.review(a, 'approved')
s.record_temple_results([(a, 'Home', 0.6, 'hobby')], 'auto')
d = s._propose_original('Boiler service', 'Boiler serviced every September', 'User said')['id']; s.review(d, 'approved'); R.set_review_by(d, '2025-01-01')
sm = actions.summary(); by = {x['key']: x['count'] for x in sm['sections']}
wt = next(x for x in sm['sections'] if x['key'] == 'waiting')
t('proposals and decisions counted (automatic approval off: all waiting)', by['waiting'] + by['decisions'] == 3 and wt['title'] == 'Awaiting approval')
t('knowledge drafts counted', any(i['type'] == 'draft' and i['id'] == draft for i in wt['items']))
t('Temple suggestions counted', by['suggestions'] == 1)
t('category suggestion counted', by['tags'] >= 1)
t('past review date counted', by['due'] == 1)
t('failed Temple review counted', by['failed'] == 1)
from fastapi.testclient import TestClient
c = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
before = actions.count()
c.post(f'/admin/api/records/{p1}/review', json={'decision': 'approved'}, headers=H)
c.post('/admin/api/knowledge/review', json={'ids': [draft], 'decision': 'approved'}, headers=H)
c.post('/admin/api/memories/suggestions', json={'ids': [a], 'action': 'dismiss'}, headers=H)
t('inline decisions reduce the total by 3', actions.count() == before - 3)
t('chat page count endpoint', c.get('/actions-count').json()['total'] == actions.count())
t('Actions has its own address', 'Everything waiting for your decision' in c.get('/admin/actions').text)

# Approve all on one section (Stefan, 6 Oct 2026): every item in it, each through its usual checks
H = {'x-admin-token': app.ADMIN_TOKEN}
from fastapi.testclient import TestClient
cl = TestClient(app.app)
w1 = s.propose('Likes early starts', 'Starts work at 7am most days', 'User said')['id']
w2 = s.propose('Prefers tea', 'Drinks tea, not coffee, at meetings', 'User said')['id']
w3 = K.create('note', 'Fictional rollout plan', 'A fictional plan to roll out the pilot in two phases.', 'Claude', 'model via Claude', status='draft')['id']
sec = next(x for x in actions.summary()['sections'] if x['key'] == 'waiting')
t('a section that can be approved all at once says so', sec['approve_all'] is True)
t('Approve all needs the page token', cl.post('/admin/api/actions/approve-all', json={'section': 'waiting'}).status_code == 403)
r = cl.post('/admin/api/actions/approve-all', json={'section': 'waiting'}, headers=H).json()
with s.db() as c: st = {x[0]: x[1] for x in c.execute('SELECT id, status FROM records WHERE id IN (?,?)', (w1, w2))}
t('Approve all approves every item in the section, memories and knowledge alike', r['done'] >= 3 and st == {w1: 'approved', w2: 'approved'}
  and K.meta([w3])[w3]['status'] == 'active')
t('nothing is left waiting there', next(x for x in actions.summary()['sections'] if x['key'] == 'waiting')['count'] == 0)
t('a section that is not for approval is refused', cl.post('/admin/api/actions/approve-all', json={'section': 'apps'}, headers=H).status_code == 400
  and cl.post('/admin/api/actions/approve-all', json={'section': 'opportunities'}, headers=H).status_code == 400)
with s.db() as c: logged = c.execute("SELECT detail FROM activity WHERE action='actions_approve_all'").fetchone()
t('it is logged as one action with the count', logged and 'approved' in logged[0])
t('the page has the button', 'Approve all ' in cl.get('/admin/actions').text)
