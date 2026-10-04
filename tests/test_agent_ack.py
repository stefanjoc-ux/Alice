"""Clearing an agent's failed run once you have seen, fixed or accepted it: the flag goes (Agents page, Home, Actions),
the run keeps its 'failed' outcome, your note is kept and logged, and it can be proposed as a decision for approval."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import substrate_store as s, temple, knowledge as K, agents as A, actions, home
temple.save_settings(False, 'openai')
K.schedule_background = lambda *a, **k: None
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

MODE = {'fail': True}
class Usage:
    def model_dump(self): return {'input_tokens': 100, 'output_tokens': 20}
class Resp:
    output_text = 'Recommendation: approve\nReasons: fine.'
    usage = Usage()
class FakeOpenAI:
    def __init__(s_, **k): s_.responses = s_
    def create(s_, **k):
        if MODE['fail']: raise RuntimeError('provider down')
        return Resp()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
import openai; openai.OpenAI = FakeOpenAI

def fail_once(txt):
    temple.review_record(s.propose('Fact ' + txt[:12], txt, 'Stefan said')['id'])

def agent(): return next(a for a in A.listing()['agents'] if a['id'] == 'temple-review')

fail_once('Kayak trip round Mull next June.')
a = agent()
t('a failed last run needs attention', a['failure_open'] and a['status'] == 'active')
t('Home lists it', any(x['id'] == 'temple-review' and x['why'] == 'last run failed' for x in home.summary()['agents']['attention']))
t('Actions lists it, pointing at the agent', any(i['id'] == 'temple-review' and 'last run failed' in i['title'] for i in
                                                 {x['key']: x for x in actions.summary()['sections']}['agents']['items']))
page = cl.get('/admin/agents', headers=H).text
t('the agent page offers Seen, Fixed and Accepted with a note', all(x in page for x in ("'seen','Seen'", "'fixed','Fixed'", "'accepted','Accepted'", 'ag-ack-note', '/acknowledge')))

# refused
t('acknowledging needs the admin token', cl.post('/admin/api/agents/temple-review/acknowledge', json={'kind': 'seen'}).status_code == 403)
t('an unknown kind is refused', cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'ignore'}).status_code == 422)
r = cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'fixed', 'note': 'rotated api_key=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'})
t('a note containing a key is refused', r.status_code == 400 and 'key' in r.text and agent()['failure_open'])
r = cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'fixed', 'decision': True})
t('a decision needs the note written', r.status_code == 400 and agent()['failure_open'])

# cleared
r = cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'seen', 'note': 'Provider outage, nothing to do on our side'})
a = agent()
t('seen: the flag clears', r.status_code == 200 and r.json()['acknowledged'] == 1 and not a['failure_open'])
run = A.runs('temple-review')['runs'][0]
t('the run keeps its failed outcome, with your note', run['status'] == 'failed' and run['ack_kind'] == 'seen' and 'Provider outage' in run['ack_note'])
t('gone from Home and Actions', not any(x['id'] == 'temple-review' for x in home.summary()['agents']['attention'])
  and not any(i['id'] == 'temple-review' for i in {x['key']: x for x in actions.summary()['sections']}['agents']['items']))
with s.db() as c:
    log = c.execute("SELECT detail FROM activity WHERE action='agent_failure_seen'").fetchone()
t('clearing is logged with the note', log and 'Provider outage' in log[0])
t('nothing left to clear is refused', cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'seen'}).status_code == 400)

# a new failure flags it again; fixed + decision
fail_once('Four colonies over winter this year.')
t('a new failure flags it again', agent()['failure_open'])
r = cl.post('/admin/api/agents/temple-review/acknowledge', headers=H,
            json={'kind': 'fixed', 'note': 'Replaced the OpenAI key in Key Vault and restarted both apps', 'decision': True})
did = r.json().get('decision')
with s.db() as c: d = c.execute('SELECT status, source FROM records WHERE id=?', (did,)).fetchone()
t('fixed, with the note proposed as a decision waiting for approval', r.status_code == 200 and d and d['status'] == 'proposed' and 'temple-review' not in d['source']
  and 'run ' in d['source'] and not agent()['failure_open'])

# failures before a fix you recorded don't count towards the automatic pause
fail_once('Larch cladding for the shed.'); fail_once('Motorhome trip to Skye in May.')
t('two failures after a fix: still running (the fixed one breaks the streak)', agent()['status'] == 'active')
fail_once('Clear roof sheets on the carport.')
t('three after the fix: pauses itself as before', agent()['status'] == 'paused')

# one run at a time from the runs list
MODE['fail'] = False
cl.post('/admin/api/agents/temple-review/status', json={'status': 'active'}, headers=H)
MODE['fail'] = True; fail_once('Bees fed fondant in January.'); fail_once('Gym four days a week.')
open_runs = [x for x in A.runs('temple-review')['runs'] if x['status'] == 'failed' and not x['ack_at']]
r = cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'accepted', 'run_id': open_runs[-1]['id']})
t('a single run can be cleared on its own', r.json()['acknowledged'] == 1 and agent()['failure_open'])
cl.post('/admin/api/agents/temple-review/acknowledge', headers=H, json={'kind': 'accepted'})
t('without a run id, all its open failures are cleared', not agent()['failure_open'])
