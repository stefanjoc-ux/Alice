"""Demo HR policy (summaries in knowledge, full document stays outside Alice) and the default knowledge review period."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, io, json, zipfile
from datetime import date, timedelta
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import knowledge as K, assistants as A
import openai
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
day = lambda n: (date.today() + timedelta(days=n)).isoformat()

seen = []
class R:
    def create(self, **kw):
        seen.append(kw)
        return NS(output_text='You can carry over up to 5 days, to be taken by 30 June [S1].', usage=NS(model_dump=lambda: {'input_tokens': 500, 'output_tokens': 30}))
class O:
    def __init__(s_, **k): s_.responses = R()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
openai.OpenAI = O

# ---------------- default review period ----------------
t('the default review period is 30 days', cl.get('/admin/api/knowledge-review-days', headers=H).json()['days'] == 30)
n1 = K.create('note', 'Office opening hours', 'The office is open from 8am to 6pm on weekdays.', 'Facilities', 'you')['id']
t('a new active item is due for review in 30 days', K.meta([n1])[n1]['review_by'] == day(30))
d1 = K.create('note', 'Draft travel guidance', 'Book rail travel at least seven days ahead where possible.', 'Model', 'model', status='draft')['id']
t('a draft has no review date until approved', K.meta([d1])[d1]['review_by'] is None)
cl.put('/admin/api/knowledge-review-days', headers=H, json={'days': 60})
cl.post('/admin/api/knowledge/review', headers=H, json={'ids': [d1], 'decision': 'approved'})
t('the period can be changed, and approval sets the review date', K.meta([d1])[d1]['review_by'] == day(60))
t('existing items keep their review date', K.meta([n1])[n1]['review_by'] == day(30))
up = cl.post('/files', json={'name': 'notes.txt', 'data': base64.b64encode(b'Parking permits are renewed every January.').decode()}).json()['id']
t('uploads get the default review date too', K.meta([up])[up]['review_by'] == day(60))
cl.put('/admin/api/knowledge-review-days', headers=H, json={'days': 0})
n2 = K.create('note', 'Kitchen rota', 'Teams take turns to tidy the kitchen each Friday afternoon.', 'Facilities', 'you')['id']
t('0 means no default review date', K.meta([n2])[n2]['review_by'] is None)
t('out-of-range periods are refused', cl.put('/admin/api/knowledge-review-days', headers=H, json={'days': 731}).status_code == 422)
cl.put('/admin/api/knowledge-review-days', headers=H, json={'days': 30})

# ---------------- demo HR policy ----------------
r = cl.post('/admin/api/assistants/demo-hr', headers=H)
x = r.json()
t('the demo HR policy loads as summaries awaiting approval', r.status_code == 200 and x['added'] == 12 and x['category'] == 'HR')
drafts = K.listing(status='draft', category='HR', limit=100)['items']
t('each summary is a draft in HR, owned by the policy owner', len(drafts) == 12 and all(d['owner'] == 'Head of People' for d in drafts))
t('each summary points to its section of the full document', all('Employee Policy Handbook v1.0, section' in d['source'] and 'not stored in Alice' in d['source'] for d in drafts))
with s.db() as c:
    names = [r[0] for r in c.execute('SELECT name FROM files')]
    texts = [c.execute('SELECT text FROM files WHERE id=?', (d['id'],)).fetchone()[0] for d in drafts]
t('the full handbook is not stored in Alice: summaries only', not any(n.lower().endswith('.docx') for n in names)
  and all('Summary only' in x for x in texts) and not any('Agency workers, contractors and volunteers' in x for x in texts))
t('loading again adds nothing', cl.post('/admin/api/assistants/demo-hr', headers=H).json()['added'] == 0)

seen.clear()
d = cl.post('/assistant/hr-policy/ask', json={'question': 'How many days of annual leave can I carry over?'}).json()
t('drafts are not used until approved', d['status'] == 'answered' and not d['sources'] and not [k for k in seen if 'SOURCES' in (k.get('instructions') or '')])
cl.post('/admin/api/knowledge/review', headers=H, json={'ids': [i['id'] for i in drafts], 'decision': 'approved'})
approved = K.listing(status='active', category='HR', limit=100)['items']
t('approved summaries get the 30-day review date', len(approved) == 12 and all(i['review_by'] == day(30) for i in approved))
seen.clear()
d = cl.post('/assistant/hr-policy/ask', json={'question': 'How many days of annual leave can I carry over?'}).json()
calls = [k for k in seen if 'SOURCES' in (k.get('instructions') or '')]
t('once approved, the assistant answers from the summary', d['status'] == 'answered' and d['sources'] and d['sources'][0]['title'] == 'HR policy summary: Annual leave')
t('the answer points to the full document section', 'Employee Policy Handbook v1.0, section 2' in d['sources'][0]['source'])
t('the model is told sources are summaries and where the full document is', calls and 'full document: Employee Policy Handbook v1.0, section 2' in calls[0]['instructions'])
t('the Assistants and Knowledge pages offer the demo and the review period', 'demo-hr' in cl.get('/admin/assistants').text and 'id="k-review-days"' in cl.get('/admin/knowledge').text)
