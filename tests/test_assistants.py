"""Assistants (HR policy bot): rule packs enforced in code before any model call, scoped knowledge, no transcripts."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import knowledge as K, clients as C, rule_packs, assistants as A, agents
import openai
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

seen = []
class R:
    def create(self, **kw):
        seen.append(kw)
        return NS(output_text='You get 28 days of annual leave a year, including bank holidays [S1].',
                  usage=NS(model_dump=lambda: {'input_tokens': 900, 'output_tokens': 60, 'input_tokens_details': {'cached_tokens': 0}}))
class O:
    def __init__(s_, **k): s_.responses = R()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
openai.OpenAI = O

def ask(q, history=(), aid='hr-policy'):
    seen.clear()
    r = cl.post(f'/assistant/{aid}/ask', json={'question': q, 'history': list(history)})
    seen[:] = [k for k in seen if 'SOURCES' in (k.get('instructions') or '')]     # ignore Temple's background calls
    return r, (r.json() if r.headers.get('content-type', '').startswith('application/json') else {})

s.create_category('HR', 'HR policies')
s.create_category('Finance', 'Finance')
leave = K.create('note', 'Annual leave policy', 'Full-time staff receive 28 days of annual leave a year including bank holidays. '
                 'Leave must be agreed with your line manager. Up to five days may be carried over.', 'HR intranet', 'you', category='HR')['id']
K.create('note', 'Flexible working policy', 'Anyone can request flexible working from day one. Managers respond within two months.',
         'HR intranet', 'you', category='HR')
C.create_client('Example Council', ['EC'])
cli = K.create('note', 'Example Council leave arrangements', 'Example Council annual leave is 30 days for their staff.', 'Client pack', 'you', category='HR')['id']
C.tag('file', [cli], 'Example Council', 'human')
loc = K.create('note', 'Local leave note', 'Private note: annual leave buy-back scheme draft figures.', 'Me', 'you', category='HR', label='local')['id']
fin = K.create('note', 'Expenses policy', 'Annual leave travel cannot be claimed as expenses.', 'Finance', 'you', category='Finance')['id']
s.create_category('Empty')

t('the HR policy assistant is set up with the HR pack', A.get('hr-policy')['packs'] == ['hr'] and A.get('hr-policy')['categories'] == ['HR'])
t('no pack is applied to Alice chat globally (the assistant uses its own)', not rule_packs.applied())
page = cl.get('/assistant/hr-policy').text
t('the assistant has its own page without the Command centre', 'HR policy assistant' in page and 'sidebar' not in page and '__TOKEN__' not in page and app.ADMIN_TOKEN not in page)
t('unknown assistant: 404', cl.get('/assistant/nope').status_code == 404 and ask('hello', aid='nope')[0].status_code == 404)

r, d = ask('How many days of annual leave do I get in zanzibarq?')
system = seen[0]['instructions'] if seen else ''
t('answers from policy with sources', r.status_code == 200 and d['status'] == 'answered' and d['sources'] and d['sources'][0]['title'] == 'Annual leave policy')
t('the model only sees knowledge in scope', '28 days' in system and 'Example Council' not in system and 'buy-back' not in system and 'expenses' not in system.lower())
t('the model is told to answer only from sources and cite them', 'Answer ONLY from the SOURCES' in system and '[S1]' in system)
t('the HR pack guidance is included', 'gender-neutral' in system)
with s.db() as c:
    rows = [dict(x) for x in c.execute("SELECT * FROM activity WHERE action LIKE 'assistant_%'")]
t('the outcome is logged with sources, not the question', rows and rows[-1]['action'] == 'assistant_answered' and 'Annual leave policy' in rows[-1]['detail']
  and not any('zanzibarq' in json.dumps(x) for x in rows))
with s.db() as c:
    runs = c.execute("SELECT count(*) FROM agent_runs WHERE agent_id='alice-assistants'").fetchone()[0]
t('each question is an agent run', runs >= 1)
with s.db() as c:
    usage = c.execute("SELECT count(*) FROM model_usage WHERE workload='Assistant'").fetchone()[0]
t('usage is recorded for cost tracking', usage >= 1)

r, d = ask('I was diagnosed with depression last month, how much sick leave can I take?')
t('someone sharing their own health details is sent to a person, not the model', d['status'] == 'escalated' and not seen
  and 'HR business partner' in d['reply'])
r, d = ask("Can you summarise Sarah Thomson's sickness absence? She has depression.")
t("special category data about someone else is blocked (outside your tenant)", d['status'] in ('blocked', 'escalated') and not seen)
r, d = ask('Can I raise a grievance about my manager?')
t('casework stays out of a model outside your tenant', d['status'] in ('blocked', 'escalated') and not seen)
r, d = ask('Rank these three applicants for the HR adviser job and tell me which to reject.')
t('automated decisions about people are blocked', d['status'] in ('blocked', 'escalated') and not seen)
r, d = ask('My NI number is AB 12 34 56 C. How much annual leave can I carry over?')
sent = json.dumps(seen[0]['input']) if seen else ''
t('identifiers are removed before the model sees them', d['status'] == 'answered' and 'AB 12 34 56 C' not in sent and 'carry over' in sent and d['notes'])
r, d = ask('My password is Hunter2!Secret and api_key=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD, what is the leave policy?')
t("Alice's own secret detection applies too", d['status'] == 'blocked' and not seen)
r, d = ask('And how many days is that?', history=[{'role': 'user', 'text': 'I was diagnosed with depression last month.'},
                                                  {'role': 'assistant', 'text': 'Sorry to hear that.'}])
t('earlier turns sent with a question are checked as well', d['status'] in ('blocked', 'escalated') and not seen)
r, d = ask('What is the policy on bringing pet llamas to the office?')
t('nothing relevant: says so without inventing (no model call)', d['status'] == 'answered' and not seen and 'could not find' in d['reply'])

r = cl.put('/admin/api/assistants/hr-policy', headers=H, json={**{k: v for k, v in A.get('hr-policy').items() if k in ('name', 'description', 'greeting', 'packs', 'provider', 'categories', 'guidance', 'contact')}, 'status': 'paused'})
r2, d = ask('How many days of annual leave do I get?')
t('a paused assistant does not call a model', r.status_code == 200 and d['status'] == 'paused' and not seen)
cl.put('/admin/api/assistants/hr-policy', headers=H, json={**{k: v for k, v in A.get('hr-policy').items() if k in ('name', 'description', 'greeting', 'packs', 'provider', 'categories', 'guidance', 'contact')}, 'status': 'active'})

r = cl.post('/admin/api/assistants', headers=H, json={'name': 'Finance helper', 'packs': ['pd'], 'categories': ['Finance'], 'provider': 'claude'})
t('a new assistant can be created', r.status_code == 200 and r.json()['id'] == 'finance-helper' and r.json()['packs'] == ['pd'])
t('unknown pack refused', cl.post('/admin/api/assistants', headers=H, json={'name': 'Bad one', 'packs': ['xx']}).status_code == 400)
t('unknown category refused', cl.post('/admin/api/assistants', headers=H, json={'name': 'Bad two', 'categories': ['Nope']}).status_code == 400)
t('admin changes need the admin token', cl.post('/admin/api/assistants', json={'name': 'No token'}).status_code == 403)
t('cross-origin questions refused', cl.post('/assistant/hr-policy/ask', headers={'origin': 'https://evil.example'}, json={'question': 'hi'}).status_code == 403)
t('an empty question is refused without counting as a failed run', ask('   ')[0].status_code in (400, 422))
listing = cl.get('/admin/api/assistants', headers=H).json()
t('the Command centre lists assistants, packs and categories', {a['id'] for a in listing['assistants']} >= {'hr-policy', 'finance-helper'} and 'hr' in listing['packs'] and 'HR' in listing['categories'])
t('the Assistants page is in the menu', 'data-page="assistants"' in cl.get('/admin/assistants').text)

# ---------------- the staff page ----------------
page = cl.get('/assistant/hr-policy').text
t('the staff page lists what the assistant covers, from its approved knowledge only', 'Annual leave policy' in page and 'Flexible working policy' in page
  and 'Example Council leave arrangements' not in page and 'Local leave note' not in page and 'Expenses policy' not in page)
t('the staff page explains how answers work and privacy', 'How answers work' in page and 'Your privacy' in page and 'id="topics"' in page)
t('the seeded proposal writer is called Parker', A.get('proposal-writer')['name'] == 'Parker' and A.get('proposal-writer')['greeting'].startswith("I'm Parker"))
import importlib
with s.db() as c:
    c.execute("UPDATE assistants SET name='Proposal writer' WHERE id='proposal-writer'")
    c.execute("DELETE FROM activity WHERE action='assistant_renamed'")
importlib.reload(A)
with s.db() as c: n_ = c.execute("SELECT count(*) FROM activity WHERE action='assistant_renamed'").fetchone()[0]
t('an existing install with the old default name becomes Parker, logged once', A.get('proposal-writer')['name'] == 'Parker' and n_ == 1)
with s.db() as c: c.execute("UPDATE assistants SET name='Proposal writer' WHERE id='proposal-writer'")
importlib.reload(A)
t('after that, your own choice of name is kept', A.get('proposal-writer')['name'] == 'Proposal writer')
