"""Actions items open as information cards with the full detail and Ask Temple (Stefan, 6 Oct 2026): a held memory, a knowledge draft,
an organisation fact and one of Temple's category changes. Temple can be asked about each while it waits; it changes nothing.
Fictional content only; no real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, uuid
import app, substrate_store as s, temple, autoapprove, knowledge, organisations, action_cards as AC, temple_discuss as D, refs
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'claude')

SENT = {}
class Msg:
    def create(self, **kw):
        SENT.update(kw)
        return type('R', (), {'content': [type('B', (), {'type': 'text', 'text': 'It is consistent with what Alice holds.\nRecommendation now: approve'})()],
                              'usage': type('U', (), {'input_tokens': 5, 'output_tokens': 5, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0})()})()
class A:
    def __init__(s, **k): s.messages = Msg()
    def __enter__(s): return s
    def __exit__(s, *a): pass
import anthropic; anthropic.Anthropic = A

# a memory held back, with Temple's review comparing it with an approved one
old = s._propose_original('Fictional proposal style', 'Proposals lead with outcomes for the fictional borough.', 'User said')['id']; s.review(old, 'approved')
rid = s._propose_original('Preference for outcome-led proposals', 'Lead every proposal with the outcomes the client wants.', 'Microsoft Copilot [via outside connector]')['id']
with s.db() as c:
    c.execute('INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,finished_at,report,context) VALUES (?,?,?,?,?,?,?,?,?)',
              (uuid.uuid4().hex, rid, 'complete', 'claude', 'm', s.now(), s.now(), f'Recommendation: approve\nReasons: consistent with {old}.\nConflict: no',
               json.dumps({'compared_memories': [{'id': old, 'title': 'Fictional proposal style', 'content': 'Proposals lead with outcomes'}]})))
autoapprove.hold('memory', rid, 'Proposed by Microsoft Copilot through the outside connector.')
refs.ensure()

c1 = cl.get(f'/admin/api/cards/review/r-{rid}').json()
secs = {x['title']: x for x in c1['sections']}
t('a held memory opens as a card: the full text, why it waits and what Temple thinks', c1['kind_label'] == 'Memory waiting for you'
  and secs['What it says']['text'].startswith('Lead every proposal') and 'outside connector' in json.dumps(secs['Why it waits, and what Temple thinks'])
  and 'Approve' in json.dumps(secs['Why it waits, and what Temple thinks']))
t('Temple\'s review reads with titles, not IDs', old not in json.dumps(c1) and 'Fictional proposal style' in json.dumps(c1))
rel = secs['What Temple compared it with']['items']
t('what Temple compared it with is listed by reference, each opening its own card', rel and rel[0]['ref'].startswith('M-')
  and cl.get('/admin/api/cards/review/' + rel[0]['ref']).json()['title'] == 'Fictional proposal style')
t('a waiting item offers Ask Temple; an approved one does not', c1['discuss']['url'] == f'/admin/api/review-items/r-{rid}/discussion'
  and 'discuss' not in cl.get('/admin/api/cards/review/' + rel[0]['ref']).json())

r = cl.post(f'/admin/api/review-items/r-{rid}/discussion', json={'message': 'Does it clash with anything?'}, headers=H).json()
t('Ask Temple on a memory: an answer and a recommendation', r['recommendation'] == 'approve' and 'consistent' in r['reply'])
payload = SENT['messages'][0]['content']
t('Temple sees the memory, why it was held and what its review compared', 'outcome-led' in payload and 'outside connector' in payload and 'Fictional proposal style' in payload)
t('kept with the item', [m['role'] for m in cl.get(f'/admin/api/review-items/r-{rid}/discussion').json()['messages']] == ['you', 'temple'])
with s.db() as c: st = c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]
t('Temple changes nothing', st == 'proposed')

# a knowledge draft that would replace an older item
k_old = knowledge.create('note', 'Fictional rollout note v1', 'Rollout to one team first.', 'User', 'you')['id']
k = knowledge.create('note', 'Rolling out Alice to a client team', 'Roll out to the fictional HR team through Copilot, then widen.', 'Claude', 'Claude',
                     status='draft')['id']
knowledge.add_replacement(k, k_old, 'proposer', reason='newer plan')
autoapprove.hold('knowledge', k, 'Proposed by Claude through the outside connector.')
c2 = cl.get(f'/admin/api/cards/review/k-{k}').json()
j2 = json.dumps(c2)
t('a knowledge draft opens with its text, who added it, why it waits and what it would replace', c2['kind_label'] == 'Knowledge draft'
  and 'fictional HR team' in j2 and 'outside connector' in j2 and 'Fictional rollout note v1' in j2 and c2['discuss'])
r = cl.post(f'/admin/api/review-items/k-{k}/discussion', json={'message': 'Summarise it'}, headers=H)
t('Ask Temple on a knowledge draft', r.status_code == 200 and 'fictional HR team' in SENT['messages'][0]['content']
  and 'Rollout to one team first' in SENT['messages'][0]['content'])

# an organisation fact
organisations.create('Fictional Borough Council', 'council')
f = organisations.propose_fact('Fictional Borough Council', next(iter(organisations.SECTION_NAMES)), 'Runs a fictional data platform.', 'web',
                               'https://example.org/fictional', by='Temple')
fid = f['id'] if isinstance(f, dict) else f
c3 = cl.get(f'/admin/api/cards/review/o-{fid}').json()
t('an organisation fact opens with its source', 'Runs a fictional data platform.' in json.dumps(c3) and 'example.org' in json.dumps(c3))

# one of Temple's category changes waiting for you
tid = uuid.uuid4().hex[:12]
with s.db() as c:
    c.execute("INSERT INTO taxonomy_changes(id,created_at,kind,op,target,detail,reason,state,why_waiting,signature) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (tid, s.now(), 'category', 'rename', 'Client Proposals', json.dumps({'name': 'Client Proposals', 'new_name': 'Projects', 'confidence': 0.8}),
               'The name is too narrow for what it holds.', 'proposed', 'You created “Client Proposals”.', 'sig-' + tid))
c4 = cl.get(f'/admin/api/cards/review/t-{tid}').json()
j4 = json.dumps(c4)
t('a category change opens with what changes, why, why it waits and confidence', 'Rename' in c4['title'] and 'Projects' in j4
  and 'too narrow' in j4 and 'You created' in j4 and '80%' in j4 and c4['discuss'])
r = cl.post(f'/admin/api/review-items/t-{tid}/discussion', json={'message': 'Is there a better name?'}, headers=H)
t('Ask Temple on its own change', r.status_code == 200 and 'Projects' in SENT['messages'][0]['content'])

t('a bad key is refused', cl.get('/admin/api/review-items/x-123456/discussion').status_code == 422
  and cl.get('/admin/api/cards/review/r-000000').status_code == 404)
t('Ask Temple needs the page token', cl.post(f'/admin/api/review-items/t-{tid}/discussion', json={'message': 'Hi'}).status_code == 403)
with s.db() as c: acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE action LIKE 'temple_%chat'")}
t('logged without content', 'temple_item_chat' in acts)
page = cl.get('/admin/actions').text
t('Actions opens a card from each item, with Ask Temple', "cards/review/" in page and 'icDiscuss' in page and 'Full details' in page)
