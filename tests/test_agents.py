"""Agents: the register, runs and what they touched, costs, automatic pausing, your controls and versions,
and connected apps' permissions enforced on every tool call."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import substrate_store as s, temple, clients as C, knowledge as K, agents as A, actions, usage_meter
temple.save_settings(False, 'openai')
K.schedule_background = lambda *a, **k: None
import app, mcp_server as M
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
s.create_category('Work', 'Insight'); s.create_category('Home', 'Home')

# 1. the register: Alice's automations and the known apps are listed from the start
ids = {a['id']: a for a in cl.get('/admin/api/agents').json()['agents']}
t('Temple automations registered', {'temple-review', 'temple-chat', 'temple-categorise', 'temple-tagging', 'temple-replacements'} <= set(ids))
t('connected apps registered', ids['claude-desktop']['kind'] == 'app' and ids['microsoft-copilot']['kind'] == 'app')
t('agents reading outside content are flagged', ids['temple-chat-review']['external_content'] and not ids['temple-categorise']['external_content'])
t('every agent has a review date', all(a['review_by'] for a in ids.values()))

# 2. a run is recorded with what it read, its cost and outcome
class Usage:
    def model_dump(self): return {'input_tokens': 2000, 'output_tokens': 400}
class Resp:
    output_text = 'Recommendation: approve\nReasons: fine.'
    usage = Usage()
MODE = {'fail': False}
class FakeOpenAI:
    def __init__(s_, **k): s_.responses = s_
    def create(s_, **k):
        if MODE['fail']: raise RuntimeError('provider down')
        return Resp()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
import openai; openai.OpenAI = FakeOpenAI
old = s.propose('Carport roof', 'Clear twinwall polycarbonate for the carport.', 'Stefan said', 'Home')['id']; s.review(old, 'approved')
rid = s.propose('Carport roof colour', 'The carport roof sheets should be clear, not opal.', 'Stefan said', 'Home')['id']
r = temple.review_record(rid)
runs = A.runs('temple-review')['runs']
t('run recorded as complete', r['status'] == 'complete' and runs and runs[0]['status'] == 'complete')
t('model cost attributed to the run', runs[0]['calls'] == 1 and runs[0]['cost_usd'] > 0)
d = A.run_detail(runs[0]['id'])
t('run records what it read (the proposal and the memories compared)', d['touched']['read']['memory'] >= 2 and any(e['target_id'] == old for e in d['events']))
t('data touched lists the item by name', any(i['target_name'] == 'Memory: Carport roof' for i in A.touched_items('temple-review')))

# 3. three failures in a row pause the agent; Actions says so; it then refuses to run
MODE['fail'] = True
for i, txt in enumerate(['Kayak trip round Mull next June.', 'Four colonies over winter this year.', 'Larch cladding for the shed.']):
    p = s.propose(f'Fact {i}', txt, 'Stefan said')['id']
    temple.review_record(p)
a = A.get('temple-review')
t('paused itself after 3 failed runs, with the reason', a['status'] == 'paused' and '3 failed runs' in a['status_reason'] and 'last error' in a['status_reason'])
sec = {x['key']: x for x in actions.summary()['sections']}
t('Actions shows the paused agent', sec['agents']['count'] >= 1 and any('paused itself' in i['title'] for i in sec['agents']['items']))
try: temple.review_record(p); t('paused agent refuses to run', False)
except A.AgentBlocked as e: t('paused agent refuses to run', 'paused' in str(e))
MODE['fail'] = False
cl.post('/admin/api/agents/temple-review/status', json={'status': 'active'}, headers=H)
t('resuming clears the failure streak and it runs again', temple.review_record(p)['status'] == 'complete' and A.get('temple-review')['status'] == 'active')

# 4. a monthly budget pauses it once reached
cl.put('/admin/api/agents/temple-review', json={'budget_usd': 0.0001, 'note': 'test budget'}, headers=H)
try: temple.review_record(p); t('over budget: paused and refused', False)
except A.AgentBlocked as e: t('over budget: paused and refused', 'budget' in str(e) and A.get('temple-review')['status'] == 'paused')
cl.put('/admin/api/agents/temple-review', json={'clear_budget': True, 'note': 'remove test budget'}, headers=H)
cl.post('/admin/api/agents/temple-review/status', json={'status': 'active'}, headers=H)
v = cl.get('/admin/api/agents/temple-review/versions', headers=H).json()['versions']
t('settings changes are versioned with your note', v[0]['note'] == 'remove test budget' and v[1]['config']['budget_usd'] == 0.0001 and v[0]['config']['budget_usd'] is None)

# 5. spending-cap pauses are "blocked", not failures of the agent
import rules_engine as R
R.update_rule('spend_cap', new_params={'daily_usd': 0.1, 'monthly_usd': 1, 'warn_percent': 10})
with s.db() as c: c.execute("INSERT INTO model_usage(created_at,provider,model,workload,input_tokens,output_tokens,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?,?,?)",
                            (s.now(), 'openai', 'gpt-6-luna', 'Chat', 1, 1, 0.5, '{}'))
try: temple.review_record(p)
except ValueError: pass
t('spending cap: run recorded as blocked, agent stays active', A.runs('temple-review')['runs'][0]['status'] == 'blocked' and A.get('temple-review')['status'] == 'active')
with s.db() as c: c.execute("DELETE FROM model_usage WHERE workload='Chat'")

# 6. runs with nothing to do are not kept
before = A.runs('temple-tagging')['total']
C.run_tagging()            # no clients: nothing to do
t('idle runs are not recorded', A.runs('temple-tagging')['total'] == before)

# 7. connected apps: every tool call recorded and checked against the app's permissions
M.CLIENT = 'Claude Desktop'
M.search_records(query='')
M.propose_record(title='Desktop test', content='Proposed from Claude Desktop in a test.', source='Stefan said')
day = A.runs('claude-desktop')['runs'][0]
t('tool calls counted on the day', day['calls'] == 2)
dd = A.run_detail(day['id'])
t('reads and writes recorded', 'memory' in dd['touched'].get('read', {}) and 'memory' in dd['touched'].get('wrote', {}))
cl.put('/admin/api/agents/claude-desktop', json={'permissions': {'mode': 'read'}, 'note': 'read only'}, headers=H)
try: M.propose_record(title='Blocked', content='Should not be proposed by a read-only app.', source='x'); t('read-only app cannot propose', False)
except ValueError as e: t('read-only app cannot propose', 'read-only' in str(e))
cl.put('/admin/api/agents/claude-desktop', json={'permissions': {'mode': 'propose', 'categories': ['Work']}}, headers=H)
recs = M.search_records(query='')
t('category limit: only Work memories reach the app', all(r.get('category') == 'Work' for r in recs['records']) and 'withheld_by_agent_permissions' in recs)
cl.put('/admin/api/agents/claude-desktop', json={'permissions': {'categories': [], 'tools': ['search_records']}}, headers=H)
try: M.list_files(); t('tool limit: other tools refused', False)
except ValueError as e: t('tool limit: other tools refused', 'not allowed to use list_files' in str(e))
cl.put('/admin/api/agents/claude-desktop', json={'permissions': {'tools': [], 'max_calls_per_day': 1}}, headers=H)
try: M.search_records(query=''); t('daily call limit enforced', False)
except ValueError as e: t('daily call limit enforced', 'limit' in str(e))
cl.put('/admin/api/agents/claude-desktop', json={'permissions': {'max_calls_per_day': None}}, headers=H)
note = K.create('note', 'Internal roadmap', 'Internal roadmap note body long enough to save here.', 'you', 'you', label='internal')['id']
cl.put('/admin/api/agents/claude-desktop', json={'permissions': {'labels': ['general']}}, headers=H)
t('label limit: Internal knowledge hidden from the app', note not in [f['id'] for f in M.list_files()['files']])
try: M.read_file(note); t('label limit: read refused', False)
except ValueError as e: t('label limit: read refused', 'may not read internal' in str(e))
cl.post('/admin/api/agents/claude-desktop/status', json={'status': 'stopped', 'reason': 'test'}, headers=H)
try: M.search_records(query=''); t('stopped app refused on every call', False)
except ValueError as e: t('stopped app refused on every call', 'stopped' in str(e))
M.CLIENT = 'Claude Code'
M.search_records(query='')
t('a new app is registered on first connection', A.get('claude-code')['kind'] == 'app')
M.CLIENT = ''
t('Alice web chat is not an agent (no gating)', M._app('list_files') == (None, None))

# 8. the page and activity
page = cl.get('/admin/agents').text
t('Agents page renders', 'id="ag-table"' in page)
with s.db() as c: acts = {r[0] for r in c.execute('SELECT DISTINCT action FROM activity')}
t('pauses, stops and changes are in the activity log', {'agent_paused', 'agent_stopped', 'agent_updated', 'agent_registered'} <= acts)
