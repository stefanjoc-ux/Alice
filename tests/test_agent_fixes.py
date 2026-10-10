"""The three agents failing on 10 Oct 2026, and resuming one Alice paused.
1. Temple's category and tag housekeeping asked OpenAI for JSON mode with the word JSON only in its instructions: OpenAI refuses
   (HTTP 400) unless the INPUT mentions JSON. Every JSON-mode call now goes through openai_json, which adds it.
2. Talk to the team failed when the lead answered in words, or ran past its length limit.
3. Whole-chat reviews failed on a reply cut off at the length limit, or with a line break inside a JSON string.
A paused agent whose cause is fixed is resumed once at start-up and catches up (approved items with no category included).
No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, os, re, uuid
import substrate_store as s, agents as A, temple, openai_json
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'openai')
import temple_categorise as TC, knowledge as K
K.schedule_background = lambda *a, **k: None
def cat_ask(payload):      # Temple's categorising (memories and knowledge), stubbed for the whole suite
    ids = [m['id'] for m in json.loads(payload)['memories']]
    return json.dumps({'assignments': [{'id': i, 'category': 'Leisure', 'confidence': 0.95, 'reason': 'A hobby.'} for i in ids]})
TC._ask = cat_ask

# ---- a stand-in for OpenAI that applies OpenAI's own rule for JSON mode ----
class FakeBadRequest(Exception):
    status_code = 400
    def __init__(s_, msg): super().__init__(msg); s_.message = msg
FakeBadRequest.__module__ = 'openai._exceptions'
class Usage:
    def model_dump(self): return {'input_tokens': 100, 'output_tokens': 20}
SENT, REPLY = [], {'text': '{}'}
class Resp:
    status = 'completed'; incomplete_details = None; usage = Usage()
    def __init__(s_, text): s_.output_text = text
class FakeOpenAI:
    def __init__(s_, **k): s_.responses = s_
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
    def create(s_, **k):
        SENT.append(k)
        if ((k.get('text') or {}).get('format') or {}).get('type') == 'json_object' and not openai_json.mentions_json(k.get('input')):
            raise FakeBadRequest("Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'.")
        return Resp(REPLY['text'])
import openai; openai.OpenAI = FakeOpenAI

def json_calls(): return [k for k in SENT if openai_json.wants_json(k)]

# ---- the provider layer ----
t('input without the word gets the instruction', openai_json.with_json_word('{"memories": []}').endswith(openai_json.INSTRUCTION))
t('input that mentions JSON is left as it was', openai_json.with_json_word('Answer in json please') == 'Answer in json please')
msgs = [{'role': 'user', 'content': 'Hello'}]
t('a list of messages gets a last user message', openai_json.with_json_word(msgs)[-1] == {'role': 'user', 'content': openai_json.INSTRUCTION} and len(msgs) == 1)
t('content parts are read too', openai_json.mentions_json([{'role': 'user', 'content': [{'type': 'input_text', 'text': 'reply as JSON'}]}]))

# no call anywhere asks OpenAI for JSON mode except through openai_json
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bad = []
for root, dirs, files in os.walk(here):
    dirs[:] = [d for d in dirs if d not in ('.git', '.venv', 'tests', 'node_modules', '__pycache__', 'data')]
    for f in files:
        if f.endswith('.py') and f != 'openai_json.py':
            src = open(os.path.join(root, f), encoding='utf-8').read()
            if re.search(r"json_object|['\"]type['\"]\s*:\s*['\"]json_schema['\"]", src): bad.append(f)
t('every JSON-mode call to OpenAI goes through openai_json: ' + (', '.join(bad) or 'none elsewhere'), not bad)

# ---- 1. Temple's category and tag housekeeping (the paused agent): the failure reproduced, then fixed ----
import temple_taxonomy as TX
REPLY['text'] = json.dumps({'changes': []})
try:
    FakeOpenAI().create(model='gpt-6-luna', instructions=TX.PROMPT, input=json.dumps({'memories': [{'id': 'm1', 'title': 'Boat'}]}), text=openai_json.JSON_MODE)
    t('the stand-in refuses JSON mode with JSON only in the instructions (as OpenAI did)', False)
except FakeBadRequest:
    t('the stand-in refuses JSON mode with JSON only in the instructions (as OpenAI did)', 'JSON' in TX.PROMPT)
SENT.clear()
out, cut = TX._cloud(json.dumps({'categories': [], 'memories': [{'id': 'm1', 'title': 'Kayak', 'content': 'Mull trip'}]}))
t('the housekeeping call now succeeds, in JSON mode, with JSON in its input', out == REPLY['text'] and not cut
  and len(json_calls()) == 1 and openai_json.mentions_json(json_calls()[0]['input']))
TX.set_mode('auto')
s.create_category('Leisure', 'Hobbies and trips')
for txt in ('Kayaking round Mull next June.', 'Sea swimming at Portobello on Sundays.'):
    s.propose('Trip ' + txt[:14], txt, 'test')
SENT.clear()
res = TX.review(manual=True)
t('a whole housekeeping review runs to the end', res.get('status') == 'complete' and json_calls() and all(openai_json.mentions_json(k['input']) for k in json_calls()))

# ---- 2. Talk to the team ----
import assistants, teams, team_qs
teams.BACKGROUND = False
CALLS = []
real_call = assistants._call
def talk_fake(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None, **kw):
    CALLS.append(dict(kw, max_tokens=max_tokens, system=system))
    return TALK.pop(0)(meta)
assistants._call = talk_fake
TID = team_qs.TEAM_ID
TALK = [lambda m: 'Happy to help: we measure, price and check the cost plan.']
r = cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'What does the team do?'}, headers=H)
msgs = cl.get(f'/admin/api/teams/{TID}/talk').json()['messages']
t('a lead who answers in words, not JSON: the words are the reply (it failed before)', r.status_code == 200 and msgs[-1]['content'].startswith('Happy to help'))
t('Talk asks for JSON mode through the provider layer', CALLS and CALLS[-1].get('json_mode') is True)
def cut(m):
    m['truncated'] = True; return '{"reply": "Our plan is long and'
TALK = [cut, lambda m: json.dumps({'reply': 'In short: measured and priced.', 'route_to': '', 'note_for_member': ''})]
CALLS.clear()
r = cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'Tell me everything about the job.'}, headers=H)
t('an answer cut off at the length limit is asked for again, shorter (it failed before)', r.status_code == 200 and len(CALLS) == 2
  and 'too long' in CALLS[1]['system'] and cl.get(f'/admin/api/teams/{TID}/talk').json()['messages'][-1]['content'] == 'In short: measured and priced.')
t('room for the full reply', CALLS[0]['max_tokens'] >= 3000)
run = cl.get('/admin/api/agents/team-talk/runs').json()
t('both runs recorded as complete', isinstance(run, (list, dict)) and not any(x.get('status') == 'failed' for x in (run if isinstance(run, list) else run.get('runs', []))))
# the real OpenAI path: Talk's call reaches OpenAI in JSON mode with the word in its input
assistants._call = real_call
SENT.clear(); REPLY['text'] = json.dumps({'reply': 'Noted.', 'route_to': '', 'note_for_member': ''})
txt = assistants._call('openai',
                       'Return a reply object.', [{'role': 'user', 'content': '{"message_from_the_user": "Hello"}'}], json_mode=True)
t('assistants._call(json_mode=True) to OpenAI: JSON mode with JSON in the input', txt == REPLY['text'] and json_calls() and openai_json.mentions_json(json_calls()[-1]['input']))

# ---- 3. Whole-chat reviews ----
import conversations as V
ac = s.create_chat()['id']
with s.db() as c:
    c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)",
              (uuid.uuid4().hex, ac, 'I only work from the Blairgowrie office on Fridays', 'Noted.', 'openai', 'complete', s.now()))
good = {'suggestions': [{'kind': 'memory', 'title': 'Office days', 'content': 'Works from the office\non Fridays',
                         'quote': 'only work from the Blairgowrie office on Fridays', 'reason': 'fact'}]}
raw = json.dumps(good).replace('\\n', '\n')          # a real line break inside a string, as models sometimes write
p, badn = V.parse_suggestions(raw)
t('a line break inside a JSON string is read (it failed before)', len(p.suggestions) == 1)
p, badn = V.parse_suggestions(json.dumps(good) + '\nNotes: {see above}')
t('words with braces after the JSON are ignored', len(p.suggestions) == 1)
ASKS = []
def ask(payload, extra=''):
    ASKS.append(extra)
    return ('{"suggestions": [{"kind": "memory", "title": "Office d' if len(ASKS) == 1 else json.dumps(good)), 'openai'
V._ask = ask
res = V.review_chat(ac, manual=True)
t('a reply cut off at the length limit is asked for once more, shorter (it failed before)', res['status'] == 'complete' and len(ASKS) == 2
  and ASKS[1] == V.SHORTER and res['suggestions'] == 1)
ASKS.clear(); V._ask = lambda payload, extra='': (ASKS.append(1) or 'Nothing here.', 'openai')
res = V.review_chat(ac, manual=True)
t('a reply still unreadable twice fails with the reason', res['status'] == 'failed' and 'expected format' in res['message'] and len(ASKS) == 2)
import importlib; importlib.reload(V)
SENT.clear(); REPLY['text'] = json.dumps({'suggestions': []})
V._ask('CONVERSATION IN ALICE: Boats\n\nUSER: hello')
t('the review asks OpenAI for JSON mode, with JSON in its input', json_calls() and openai_json.mentions_json(json_calls()[-1]['input']))

# ---- resuming the paused agent, and catching up ----
def fail_run(aid, err):
    with s.db() as c:
        c.execute("INSERT INTO agent_runs(id,agent_id,trigger,started_at,finished_at,status,error) VALUES (?,?,?,?,?,?,?)",
                  (uuid.uuid4().hex, aid, 'test', s.now(), s.now(), 'failed', err))
ERR = "OpenAI rejected the request (HTTP 400): Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'."
for _ in range(3): fail_run('temple-taxonomy', ERR)
A.set_status('temple-taxonomy', 'paused', f'{A.FAIL_LIMIT} failed runs in a row; last error: ' + ERR[:120], by='Alice')
CAUGHT = []
real_catch_up = A.catch_up
A.catch_up = lambda aid, wait=False: CAUGHT.append(aid)
t('resumed at start-up after the fix', A.resume_fixed() == ['temple-taxonomy'] and A.get('temple-taxonomy')['status'] == 'active')
t('…and it catches up on what it missed', CAUGHT == ['temple-taxonomy'])
t('…its failure streak is cleared (Home no longer flags it)', not any(x['id'] == 'temple-taxonomy' for x in __import__('home').summary()['agents']['attention']))
A.set_status('temple-taxonomy', 'paused', f'{A.FAIL_LIMIT} failed runs in a row; last error: ' + ERR[:120], by='Alice')
t('each fix resumes once only', A.resume_fixed() == [] and A.get('temple-taxonomy')['status'] == 'paused')
with s.db() as c: c.execute("DELETE FROM settings WHERE key LIKE 'agent_fix:%'")
A.set_status('temple-taxonomy', 'paused', 'by you')
t('an agent a person paused is left paused', A.resume_fixed() == [] and A.get('temple-taxonomy')['status'] == 'paused')
CAUGHT.clear()
r = cl.post('/admin/api/agents/temple-taxonomy/status', json={'status': 'active'}, headers=H)
t('Resume on the Agents page resumes it and starts the catch-up', r.status_code == 200 and r.json()['status'] == 'active' and CAUGHT == ['temple-taxonomy'])
page = cl.get('/admin/agents').text
t('the Agents page offers Resume and shows the last error in full', "btn('Resume'" in page and 'error in full' in page)
A.catch_up = real_catch_up

# the catch-up: an approved memory with no category that Temple had already looked at is categorised
rid = s.propose('Sailing club', 'Member of the sailing club at Largs.', 'test')['id']
s.review(rid, 'approved')
with s.db() as c:
    c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (rid,))
    c.execute("UPDATE record_meta SET category='', temple_checked_at=? WHERE record_id=?", (s.now(), rid))
REPLY['text'] = json.dumps({'changes': []})
got = A.catch_up('temple-taxonomy', wait=True)
with s.db() as c: cat = c.execute('SELECT category FROM record_meta WHERE record_id=?', (rid,)).fetchone()[0]
t('catch-up: housekeeping review, memories, knowledge and held shares, each reported', set(got) == {'review', 'memories', 'knowledge', 'shares'}
  and got['review'].get('status') == 'complete')
t('catch-up: the approved memory with no category gets one', cat == 'Leisure')
with s.db() as c:
    t('catch-up is in the activity log', c.execute("SELECT 1 FROM activity WHERE action='agent_catch_up'").fetchone() is not None)

# ---- Home: long warnings carry the name, the state and the reason separately ----
A.set_status('temple-taxonomy', 'paused', f'{A.FAIL_LIMIT} failed runs in a row; last error: ' + ERR[:120], by='Alice')
x = next(x for x in __import__('home').summary()['agents']['attention'] if x['id'] == 'temple-taxonomy')
t('Home: name, state and reason apart', x['name'] and x['state'] == 'paused' and 'json' in x['detail'])
home_page = cl.get('/admin').text
t('Home draws the warning as a wrapping flag: name and state on one line, the reason cut to two lines',
  'hm-flag-top' in home_page and '-webkit-line-clamp:2' in home_page and 'hm-flag-why' in home_page)
A.set_status('temple-taxonomy', 'active')
