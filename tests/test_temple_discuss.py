"""Discuss a waiting decision with Temple on Actions: Temple sees the decision, its review and what that review compared;
its replies, a new recommendation and a suggested note come back; the discussion is kept with the decision; nothing is
approved or changed by Temple. No real model call."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, uuid
import app, substrate_store as s, temple, temple_discuss as D, actions
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'claude')

old = s._propose_original('Fictional Desk tooling', 'Decision: track paper trades in a spreadsheet', 'User said')['id']; s.review(old, 'approved')
rid = s.propose_decision('Paper trading platform', 'Build a paper trading desk in Alice', 'User agreed', rationale='One place for signals')['id']
with s.db() as c:
    c.execute('INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,finished_at,report,context) VALUES (?,?,?,?,?,?,?,?,?)',
              (uuid.uuid4().hex, rid, 'complete', 'claude', 'm', s.now(), s.now(),
               f'Recommendation: clarify\nReasons: overlaps with {old}.\nConflict: no',
               json.dumps({'compared_memories': [{'id': old, 'title': 'Fictional Desk tooling', 'content': 'Decision: track paper trades in a spreadsheet'},
                                                 {'id': 'x' * 32, 'title': 'Unrelated', 'content': 'Something else'}]})))

SENT = {}
class Msg:
    def create(self, **kw):
        SENT.update(kw)
        return type('R', (), {'content': [type('B', (), {'type': 'text', 'text': 'It overlaps with “Fictional Desk tooling”: that kept trades in a spreadsheet.\n'
                                                                       'Recommendation now: approve\nSuggested note: Replaces the spreadsheet approach.'})()],
                              'usage': type('U', (), {'input_tokens': 5, 'output_tokens': 5, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0})()})()
class A:
    def __init__(s, **k): s.messages = Msg()
    def __enter__(s): return s
    def __exit__(s, *a): pass
import anthropic; anthropic.Anthropic = A

t('needs the page token', cl.post(f'/admin/api/records/{rid}/discussion', json={'message': 'Hi'}).status_code == 403)
r = cl.post(f'/admin/api/records/{rid}/discussion', json={'message': 'What does it clash with?'}, headers=H)
j = r.json()
t('Temple answers, with a new recommendation and a suggested note split out', r.status_code == 200 and j['recommendation'] == 'approve'
  and j['note'] == 'Replaces the spreadsheet approach.' and 'Recommendation now' not in j['reply'] and 'Suggested note' not in j['reply'])
payload = SENT['messages'][0]['content']
t('Temple sees the decision, its review and only the items its review cited', 'Paper trading platform' in payload and 'overlaps with' in payload
  and 'Fictional Desk tooling' in payload and 'Unrelated' not in payload)
t('the discussion is kept with the decision', [m['role'] for m in cl.get(f'/admin/api/records/{rid}/discussion').json()['messages']] == ['you', 'temple'])
cl.post(f'/admin/api/records/{rid}/discussion', json={'message': 'And if I narrow it?'}, headers=H)
t('earlier turns go back to Temple', [m['role'] for m in SENT['messages']][2:] == ['user', 'assistant', 'user'])
with s.db() as c:
    st = c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]
    act = [r[0] for r in c.execute("SELECT detail FROM activity WHERE action='temple_decision_chat'")]
t('Temple changes nothing: the decision still waits for you', st == 'proposed')
t('the log records that a discussion happened, never what was said', act and not any('clash' in a for a in act))
dec = next(x for x in actions.summary()['sections'] if x['key'] == 'decisions')['items']
t('Actions shows how much has been discussed', next(x for x in dec if x['id'] == rid)['discussion'] == 4)
r = cl.post(f'/admin/api/records/{rid}/discussion', json={'message': 'my key is sk-ant-api03-' + 'Z' * 40}, headers=H)
t('a secret in a message is refused and not kept', r.status_code == 400 and len(D.history(rid)) == 4)
s.review(rid, 'approved')
t('only a decision still waiting can be discussed', cl.post(f'/admin/api/records/{rid}/discussion', json={'message': 'Hi'}, headers=H).status_code == 400)
page = cl.get('/admin/actions').text
t('the Actions page offers Discuss with Temple', 'Discuss with Temple' in page and "/discussion'" in page)
mem = cl.get('/admin/memories').text
t('categories and tags are compact cards that slide open', 'class="mem-setup"' in mem and 'id="cat-panel" class="mem-setup-card"' in mem
  and 'id="tag-panel" class="mem-setup-card"' in mem and 'id="cat-summary"' in mem and 'id="tag-summary"' in mem)
