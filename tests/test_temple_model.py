"""Temple's model for screening and categories (temple_model.py; Stefan, 9 Oct 2026): Cloud or Local. Local is used for the
sharing check, categories, tags and keeping them tidy, and nothing else; the rules check what is sent either way; when the local
model does not answer the work waits (never sent to the cloud) unless the fallback switch is on; held work is shown and can be
tried again; every screening records which model did it; the evaluation scores both models on fixed fictional examples. The
local model and the cloud models are stand-ins: nothing real is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, os, re, time
import substrate_store as store
import app
import agents, assistants, memory_tags, spaces, temple, temple_categorise, temple_model, temple_tags, temple_taxonomy
from fastapi.testclient import TestClient

cl = TestClient(app.app)
temple.save_settings(False, 'claude')

# ---------------- stand-ins ----------------
LOCAL = {'up': True, 'calls': [], 'share': None}
CLOUD = []


def share_reply(text):
    body = text.split('\n\n', 1)[-1]
    low = body.lower()
    if not any(w in low for w in ('sick', 'depression', 'divorce', 'home address', 'mobile', 'personal:')):
        return json.dumps({'finding': False, 'findings': [], 'clear_because': 'Ordinary work content.'})
    typ = 'special_category' if ('sick' in low or 'depression' in low) else 'private' if 'personal:' in low else 'personal_data'
    return json.dumps({'finding': True, 'findings': [{'type': typ, 'quote': body[:120], 'about': 'a colleague',
                                                      'reason': 'It names a colleague\'s private circumstances.'}]})


def cat_reply(payload):
    d = json.loads(payload)
    names = [c['name'] for c in d['categories']]
    def pick(m):
        txt = (m.get('title', '') + ' ' + m.get('content', '')).lower()
        for n, words in (('Bids', ('proposal', 'bid', 'win theme')), ('Finance', ('invoice',)), ('Delivery', ('project', 'scope', 'client every')),
                         ('Personal', ('children', 'school'))):
            if n in names and any(w in txt for w in words): return n
        return None
    return json.dumps({'assignments': [{'id': m['id'], 'category': pick(m), 'confidence': 0.9, 'reason': 'fits'} for m in d['memories']]})


def fake_http(method, url, body, timeout):
    LOCAL['calls'].append((method, url, body))
    if not LOCAL['up']: raise temple_model.Unavailable('connection refused')
    if method == 'GET': return {'models': [{'name': 'qwen3:4b'}]}
    system, user = body['messages'][0]['content'], body['messages'][1]['content']
    if system == spaces.SCREEN_PROMPT: text = LOCAL['share'] or share_reply(user)
    elif system == temple_categorise.PROMPT: text = cat_reply(user)
    elif system == temple_tags.PROMPT: text = json.dumps({'tags': []})
    else: text = json.dumps({'changes': []})
    return {'message': {'role': 'assistant', 'content': text}, 'done_reason': 'stop'}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    CLOUD.append((workload, messages[0]['content']))
    if system == spaces.SCREEN_PROMPT:
        return json.dumps({'finding': False, 'findings': []})   # a weak cloud: always clear
    if system == temple_categorise.PROMPT: return cat_reply(messages[0]['content'])
    raise RuntimeError('no model in tests')


temple_model.HTTP = fake_http
assistants._call = fake_call
temple_categorise._cloud = lambda p: (CLOUD.append(('Temple categorise', p)) or cat_reply(p))
temple_tags._cloud = lambda p: (CLOUD.append(('Temple memory tags', p)) or json.dumps({'tags': []}))
temple_taxonomy._cloud = lambda p: (CLOUD.append(('Temple taxonomy review', p)) or (json.dumps({'changes': []}), False))


def local_calls(kind):
    want = {'share': spaces.SCREEN_PROMPT, 'cat': temple_categorise.PROMPT, 'tags': temple_tags.PROMPT}[kind]
    return [b for m, u, b in LOCAL['calls'] if m == 'POST' and b['messages'][0]['content'] == want]


def screenings():
    with store.db() as c: return [dict(r) for r in c.execute('SELECT * FROM temple_screenings ORDER BY at')]


# ---------------- the owner's data ----------------
store.create_category('Work'); store.create_category('Bids'); store.create_category('Delivery')
memory_tags.set_category_area('Work', 'work')


def mem(title, content, cat='Work'):
    r = store.propose(title, content, 'the owner said so')
    store.review(r['id'], 'approved')
    if cat: store.set_category([r['id']], cat)
    return r['id']


S = spaces.create('Bids team', 'Shared bid work')['id']

# ---------------- only the four screening jobs use it ----------------
t('the screening jobs are exactly: sharing check, categories, tags, keeping them tidy',
  set(temple_model.TASKS) == {'share_gate', 'categorise', 'tags', 'taxonomy'})
callers = {f for f in os.listdir(_util.ROOT) if f.endswith('.py') and 'temple_model.answer(' in open(os.path.join(_util.ROOT, f), encoding='utf-8').read()}
t('…and only those modules route through it (writing, judgement, Argus and teams stay on the cloud)',
  callers == {'spaces.py', 'temple_categorise.py', 'temple_tags.py', 'temple_taxonomy.py'})
t('the evaluation is a registered agent in the stewardship group', agents.get('temple-model-eval')['id'] == 'temple-model-eval'
  and 'temple-model-eval' in dict((g, ids) for g, _, _, ids in agents.GROUPS)['stewardship'])

# ---------------- Cloud by default; Local only once one is set up ----------------
st = cl.get('/admin/api/temple-model').json()
t('Cloud by default, fallback off, no local model set up', st['choice'] == 'cloud' and st['fallback'] is False and st['configured'] is False)
r = cl.put('/admin/api/temple-model', json={'choice': 'local'}, headers={'x-admin-token': app.ADMIN_TOKEN})
t('Local cannot be chosen before a local model is set up (it would hold everything)', r.status_code == 400 and '-Step localmodel' in r.json()['detail'])

m1 = mem('Bid openings', 'Every bid opens with a one-line summary of the benefit to the client.')
r = spaces.move('record', m1, S)
t('with Cloud, the sharing check uses the cloud model and never the local one', r['status'] == 'moved' and not local_calls('share')
  and any(w == 'Temple sharing check' for w, _ in CLOUD) and 'cloud model' in r['screened_by'])
t('…and the screening is recorded with its model', screenings()[-1]['place'] == 'cloud' and screenings()[-1]['model'] == 'claude-haiku-4-5-20251001'
  and json.loads(screenings()[-1]['items']) == [['record', m1]])

os.environ.update({'ALICE_LOCAL_MODEL_URL': 'http://alice-local-model', 'ALICE_LOCAL_MODEL': 'qwen3:4b'})
st = cl.get('/admin/api/temple-model').json()
t('once set up, the Agents page shows the local model answering', st['configured'] and st['reachable'] is True and st['local_model'] == 'qwen3:4b')
r = cl.put('/admin/api/temple-model', json={'choice': 'local'}, headers={'x-admin-token': app.ADMIN_TOKEN})
t('Stefan chooses Local (logged)', r.status_code == 200 and r.json()['choice'] == 'local')
with store.db() as c:
    t('…the change is in the activity log', c.execute("SELECT count(*) FROM activity WHERE action='temple_model_set'").fetchone()[0] >= 1)

# ---------------- Local: the sharing check ----------------
CLOUD.clear()
m2 = mem('Change requests', 'Any change to agreed scope on a live project needs a written change request.')
r = spaces.move('record', m2, S)
call = local_calls('share')[-1] if local_calls('share') else {}
t('with Local, the sharing check goes to the local model only', r['status'] == 'moved' and call and not CLOUD)
t('…as JSON, the chosen model, temperature 0, no thinking', call.get('model') == 'qwen3:4b' and call.get('format') == 'json'
  and call['options']['temperature'] == 0 and call.get('think') is False and 'Change requests' in call['messages'][1]['content'])
t('…and the model that did it is recorded (on the move, in the log, in screenings)', r['screened_by'] == 'local model qwen3:4b'
  and screenings()[-1]['place'] == 'local' and screenings()[-1]['model'] == 'qwen3:4b')
with store.db() as c:
    det = c.execute("SELECT detail FROM activity WHERE action='space_shared' ORDER BY id DESC").fetchone()[0]
t('…the activity log says which model checked it', 'local model qwen3:4b' in det)
m3 = mem('Cover', 'Priya Shah is off sick with depression until March, so route her approvals to Sam.')
r = spaces.move('record', m3, S)
with store.db() as c:
    mv = dict(c.execute('SELECT * FROM space_moves WHERE id=?', (r['move'],)).fetchone())
t('the local model\'s hit holds the item for its author, with its reasons and the model recorded', r['status'] == 'held'
  and 'private circumstances' in ' '.join(r['reasons']) and mv['screened_by'] == 'local model qwen3:4b')

# the rules run on what is sent whichever model answers: protectively marked text never reaches the local model either
n = len(local_calls('share'))
m4 = mem('Marked', 'The council\'s restructure plans for next year.')
with store.db() as c:      # marked text cannot become a memory at all; this stands for one marked after it was saved
    c.execute('UPDATE records SET content=? WHERE id=?', ('OFFICIAL-SENSITIVE: the council\'s restructure plans for next year.', m4))
r = spaces.move('record', m4, S)
t('a protectively marked item is stopped by the rules before any model, local included', r['status'] == 'held' and len(local_calls('share')) == n)

# ---------------- Local: categories and tags ----------------
temple_categorise.run(None, manual=True)
d = store.list_categories()
t('categories go to the local model', local_calls('cat') and not any(w == 'Temple categorise' for w, _ in CLOUD))
t('…and the categorising is recorded with each memory it covered', any(s['task'] == 'categorise' and s['place'] == 'local' for s in screenings()))
memory_tags.create_tag('pricing', 'Rates and prices', 'work')
temple_tags.run(None, manual=True)
t('tags go to the local model', local_calls('tags') and not any(w == 'Temple memory tags' for w, _ in CLOUD))
temple_taxonomy.review(manual=True)
t('keeping categories and tags tidy goes to the local model', any(s['task'] == 'taxonomy' and s['place'] == 'local' for s in screenings())
  and not any(w == 'Temple taxonomy review' for w, _ in CLOUD))

# ---------------- the local model does not answer: the work waits, never the cloud ----------------
LOCAL['up'] = False; CLOUD.clear()
m5 = mem('Win themes', 'Pick three win themes before writing a bid and repeat them in the summary.', 'Bids')
r = spaces.move('record', m5, S)
t('fallback off: a sharing check waits, and nothing goes to the cloud', r['status'] == 'held' and not CLOUD
  and 'did not answer' in ' '.join(r['reasons']) and spaces.space_of('record', m5) != S)
with store.db() as c:
    mv = dict(c.execute('SELECT * FROM space_moves WHERE id=?', (r['move'],)).fetchone())
t('…marked as held for the local model', mv['screened_by'] == 'held:local')
u = store.propose('Invoice terms', 'Invoices go out on the last working day of the month with 30-day terms.', 'said')
store.review(u['id'], 'approved')
held_cat = False
for _ in range(100):          # a new memory starts background categorising; wait until that run lets go of the lock
    try:
        if (temple_categorise.run([u['id']], manual=True) or {}).get('status') != 'busy': break
    except temple_model.LocalModelHeld:
        held_cat = True; break
    time.sleep(0.1)
t('categorising waits too (nothing to the cloud)', held_cat and not CLOUD)
with store.db() as c:
    run = c.execute("SELECT status, error FROM agent_runs WHERE agent_id='temple-categorise' ORDER BY started_at DESC").fetchone()
t('…the agent run is recorded as waiting (blocked), not as the agent failing', run['status'] == 'blocked' and 'did not answer' in run['error'])
st = cl.get('/admin/api/temple-model').json()
t('the Agents page shows what is waiting and why', st['held']['count'] >= 2 and {x['task'] for x in st['held']['by_task']} >= {'share_gate', 'categorise'}
  and 'connection refused' in st['held']['last_reason'] and st['reachable'] is False)
with store.db() as c:
    t('…and the activity log has it', c.execute("SELECT count(*) FROM activity WHERE action='temple_model_held'").fetchone()[0] >= 2)
r = cl.post('/admin/api/temple-model/retry', headers={'x-admin-token': app.ADMIN_TOKEN}).json()
t('Try again while it is still down: still waiting', 'still waiting' in r['results'].get('share_gate', '') and cl.get('/admin/api/temple-model').json()['held']['count'] >= 2)

LOCAL['up'] = True
r = cl.post('/admin/api/temple-model/retry', headers={'x-admin-token': app.ADMIN_TOKEN}).json()
t('Try again once it answers: the held share is checked and shared, categories done', r['results'].get('share_gate') == 'done'
  and r['results'].get('categorise') == 'done' and spaces.space_of('record', m5) == S)
with store.db() as c:
    mv = dict(c.execute('SELECT * FROM space_moves WHERE id=?', (mv['id'],)).fetchone())
t('…the move records the model that finally checked it', mv['status'] == 'shared' and mv['screened_by'] == 'local model qwen3:4b')
t('…and nothing is left waiting', cl.get('/admin/api/temple-model').json()['held']['count'] == 0)

# ---------------- fallback on: the cloud steps in, and that is recorded ----------------
cl.put('/admin/api/temple-model', json={'fallback': True}, headers={'x-admin-token': app.ADMIN_TOKEN})
LOCAL['up'] = False; CLOUD.clear()
m6 = mem('Weekly call', 'Project managers hold a 30-minute progress call with each client every Tuesday.', 'Delivery')
r = spaces.move('record', m6, S)
last = screenings()[-1]
t('fallback on: the cloud model checks it when the local one does not answer', r['status'] == 'moved' and any(w == 'Temple sharing check' for w, _ in CLOUD))
t('…recorded as a fallback, with the reason', last['place'] == 'cloud' and last['fallback'] == 1 and 'connection refused' in last['reason']
  and 'did not answer' in r['screened_by'])
cl.put('/admin/api/temple-model', json={'fallback': False}, headers={'x-admin-token': app.ADMIN_TOKEN})
LOCAL['up'] = True

# ---------------- the evaluation: fixed, fictional examples on both models ----------------
CLOUD.clear()
res = temple_model.evaluate()
ev = cl.get('/admin/api/temple-model').json()['evaluation']
by = {r_['place']: r_ for r_ in ev['results']}
t('the evaluation scores both models on the same examples', set(by) == {'cloud', 'local'} and by['local']['total'] == by['cloud']['total']
  == len(temple_model.SHARE_EXAMPLES) + len(temple_model.CATEGORY_EXAMPLES))
t('…the local stand-in gets every example right; the always-clear cloud stand-in misses the private ones',
  by['local']['right'] == by['local']['total'] and next(x for x in by['cloud']['tasks'] if x['task'] == 'share_gate')['right'] == 4)
t('…each example is listed with what was expected and what came back', all(set(e) >= {'item', 'expected', 'got', 'right'}
  for r_ in ev['results'] for x in r_['tasks'] for e in x['rows']))
t('…the examples are fictional and never the owner\'s data', not any('one-line summary of the benefit' in u_ for _, u_ in CLOUD))
with store.db() as c:
    t('…it ran as the temple-model-eval agent and was logged', c.execute("SELECT count(*) FROM agent_runs WHERE agent_id='temple-model-eval'").fetchone()[0] == 1
      and c.execute("SELECT count(*) FROM activity WHERE action='temple_model_eval'").fetchone()[0] == 1)
LOCAL['up'] = False
temple_model.evaluate()
ev = cl.get('/admin/api/temple-model').json()['evaluation']
t('if the local model does not answer, the evaluation says so plainly', 'did not answer' in next(x for x in ev['results'] if x['place'] == 'local')['error'])
LOCAL['up'] = True

# ---------------- the Agents page and the setup ----------------
page = cl.get('/admin/agents').text
t('the Agents page carries the card', 'id="tm-card"' in page and "Temple's model for screening and categories" in page)
bicep = open(os.path.join(_util.ROOT, 'infra', 'local-model.bicep'), encoding='utf-8').read()
main = open(os.path.join(_util.ROOT, 'infra', 'main.bicep'), encoding='utf-8').read()
t('the local model has internal ingress only and its own share', "external: false" in bicep and 'alice-models' in bicep and "'/mnt/alice'" not in bicep)
t('…and is off unless switched on', re.search(r'param localModel bool = false', main) and "if (withApps && (localModel || localModelParked))" in main)
ps = open(os.path.join(_util.ROOT, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
t('azure-setup has the localmodel step, run on its own', "'localmodel'" in ps and "if (Want 'localmodel')" in ps
  and "'users', 'localmodel'))" in ps)
