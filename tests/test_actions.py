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
t('proposals and decisions counted', by['proposals'] == 2)
t('knowledge drafts counted', by['drafts'] == 1)
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
t('Command centre opens on Actions', 'Actions' in c.get('/admin').text)
