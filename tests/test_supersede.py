"""Replacements: retiring knowledge that a newer item replaces, the proposer's "supersedes", Temple's suggestions
(wording first, then a mocked model that must quote the newer item), what models see, and memory replacements."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import substrate_store as s, temple, clients as C, knowledge as K, temple_supersede as TS, actions
temple.save_settings(False, 'openai')
K.schedule_background = lambda *a, **k: None      # run Temple's checks explicitly, not in background threads
import app, mcp_server as M
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
s.create_category('Work', 'Insight'); C.create_client('Fife Council', ['Fife'])


def note(title, body, **kw):
    return K.create('note', title, body, 'Written by you', 'you', **kw)['id']


# ---- fake Temple provider: records what was sent, answers with a configurable verdict
SENT = []
ANSWER = {'verdict': 'replaces', 'reason': 'Later status of the same build.', 'quote': ''}
class FakeResp:
    usage = None
    def __init__(s_, text): s_.output_text = text
class FakeOpenAI:
    def __init__(s_, **k): s_.responses = s_
    def create(s_, **k):
        SENT.append(k.get('input', ''))
        return FakeResp(json.dumps(ANSWER))
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
import openai; openai.OpenAI = FakeOpenAI

# 1. the proposer names what it supersedes; you choose to retire it when approving
old = note('Project handover', 'Handover of the AI Substrate build as at 29 September: routing, rules and clients. ' * 3, category='Work')
M.CLIENT = 'Claude Desktop'
r = M.propose_knowledge(title='AI Substrate: status summary (30 Sep, evening)', source='Uploaded file',
                        content='AI SUBSTRATE STATUS. Supersedes the "Project handover" note of 29 September 2026. Routing, rules and clients. ' * 2,
                        category='Work', supersedes=['Project handover'])
new = r['id']
t('draft proposal reports the named replacement', 'replacing 1 existing item' in r['message'])
p = K.replacements('pending', new_id=new)
t('proposer suggestion recorded, pointing at the right item', len(p) == 1 and p[0]['old_id'] == old and p[0]['source'] == 'proposer')
t('nothing retired by proposing', K.meta([old])[old]['status'] == 'active')
a = {x['key']: x for x in actions.summary()['sections']}
t('Actions: draft shows what it replaces', a['drafts']['items'][0]['replaces'][0]['id'] == old)
t('Actions: no retire suggestion while the newer item is only a draft', a['replacements']['count'] == 0)
x = cl.post('/admin/api/knowledge/review', json={'ids': [new], 'decision': 'approved', 'retire_replaced': True}, headers=H).json()
t('approve and retire: one item retired', x['changed'] == 1 and x['retired'] == 1)
m = K.meta([old])[old]
t('old item archived with a link to the new one', m['status'] == 'archived' and m['superseded_by'] == new and m['supersede_reason'])
lst = K.listing(status='replaced')
t('Replaced view lists it, with the newer title', [i['id'] for i in lst['items']] == [old] and lst['items'][0]['replaced_by']['id'] == new)
t('new item lists what it replaces', K.listing(status='active', query='status summary')['items'][0]['replaces'][0]['id'] == old)
t('history links both versions, oldest first', [i['id'] for i in cl.get(f'/admin/api/knowledge/{new}/history').json()['items']] == [old, new])

# 2. what models see
t('list_files hides the retired item', old not in [f['id'] for f in M.list_files()['files']])
try: M.read_file(old); t('read_file on retired item points to the new one', False)
except ValueError as e: t('read_file on retired item points to the new one', 'replaced by "AI Substrate: status summary' in str(e) and new in str(e))
sr = M.search_files('routing rules')
t('search skips retired versions and says so', all(x['file_id'] != old for x in sr['matches']) and 'retired_files' in sr)
M.CLIENT = ''
t('web chat read_file filter gives the pointer too', 'Retired' in K.model_block(old, 'claude'))
loc = note('Local roadmap v2', 'Local only roadmap, second version, long enough to save.', label='local')
old2 = note('Local roadmap', 'Local roadmap first version, long enough to save here.')
K.supersede(old2, loc, 'newer version')
t('pointer never names an item the model may not read', 'not available to you' in K.model_block(old2, 'claude') and loc not in K.model_block(old2, 'claude'))

# 3. restore undoes the replacement
cl.put('/admin/api/knowledge', json={'ids': [old], 'status': 'active'}, headers=H)
m = K.meta([old])[old]
t('restore makes it active and clears the link', m['status'] == 'active' and not m['superseded_by'])
t('restored item readable again', M.read_file(old)['lines'])

# 4. Temple, wording only (free): the new item names the old one
SENT.clear()
h1 = note('Fife migration plan', 'Plan for the Fife tenant migration: pilot, waves, cut-over and rollback steps.', client='Fife Council')
h2 = note('Fife migration plan (October)', 'This replaces the "Fife migration plan" note. Pilot done; waves two and three next.', client='Fife Council')
res = TS.check([h2], manual=True)
p = K.replacements('pending', new_id=h2)
t('explicit wording found without a model call', res['suggested'] == 1 and p[0]['old_id'] == h1 and not SENT)
t('suggestion quotes the newer item', 'replaces the "Fife migration plan"' in p[0]['quote'])
t('Temple changed nothing', K.meta([h1])[h1]['status'] == 'active')
a = {x['key']: x for x in cl.get('/admin/api/actions', headers=H).json()['sections']}
t('Actions lists the retire suggestion', a['replacements']['count'] >= 1 and any(i['id'] == p[0]['id'] for i in a['replacements']['items']))
t('accept via API retires it', cl.post('/admin/api/knowledge/replacements', json={'ids': [p[0]['id']], 'action': 'accept'}, headers=H).json()['done'] == 1
  and K.meta([h1])[h1]['superseded_by'] == h2)

# 5. Temple, model judge: must quote the newer item; conservative verdicts ignored
w1 = note('Weekly billing process', 'Weekly billing: reconstruct the timesheet from calendar, email and Teams, then submit on Friday afternoon.', category='Work')
w2 = note('Weekly billing process, revised', 'Weekly billing: the agent reconstructs the timesheet from calendar, email and Teams; I check it and submit on Friday.', category='Work')
SENT.clear(); ANSWER.update(verdict='replaces', quote='the agent reconstructs the timesheet')
res = TS.check([w2], manual=True)
t('model consulted for a similar pair', len(SENT) == 1 and res['model_calls'] == 1)
t('verified quote -> suggestion', any(x['old_id'] == w1 for x in K.replacements('pending', new_id=w2)))
w3 = note('Weekly billing process, third go', 'Weekly billing: timesheet reconstructed from calendar, email and Teams, checked, then submitted.', category='Work')
SENT.clear(); ANSWER.update(verdict='replaces', quote='words that are not in the new item at all')
TS.check([w3], manual=True)
t('unverifiable quote -> no suggestion', not K.replacements('pending', new_id=w3) and SENT)
w4 = note('Weekly billing process, fourth', 'Weekly billing: timesheet from calendar, email and Teams, checked by me, submitted Friday.', category='Work')
SENT.clear(); ANSWER.update(verdict='complements', quote='checked by me')
TS.check([w4], manual=True)
t('complements -> no suggestion', not K.replacements('pending', new_id=w4))
d = K.replacements('pending', new_id=w2)[0]
cl.post('/admin/api/knowledge/replacements', json={'ids': [d['id']], 'action': 'dismiss'}, headers=H)
with s.db() as c: c.execute('UPDATE knowledge_meta SET supersede_checked_at=NULL WHERE file_id=?', (w2,))
TS.check([w2], manual=True)
t('keep both: the pair is not suggested again', not K.replacements('pending', new_id=w2) and K.meta([w1])[w1]['status'] == 'active')

# 6. security and separation: what never reaches Temple's model
SENT.clear()
l1 = note('Salary review notes', 'Salary review notes for the team: bands, timing, approvals and the budget line.', label='local')
l2 = note('Salary review notes, update', 'Salary review notes for the team: bands, timing, approvals, budget line and dates.', label='local')
TS.check([l2], manual=True)
t('Local only items are never sent to a model', not SENT)
f1 = note('Tenant migration runbook', 'Tenant migration runbook: identities, mailboxes, Teams and SharePoint cut-over steps.', client='Fife Council')
f2 = note('Tenant migration runbook v2', 'Tenant migration runbook: identities, mailboxes, Teams and SharePoint cut-over steps, revised.')
TS.check([f2], manual=True)
t("a General item is not compared with a client's item", not any(x['old_id'] == f1 for x in K.replacements('all', new_id=f2)))

# 7. backlog sweep checks items not yet checked
with s.db() as c: c.execute('UPDATE knowledge_meta SET supersede_checked_at=NULL')
res = cl.post('/admin/api/knowledge/find-replaced', headers=H).json()
t('sweep runs and reports', res['status'] == 'complete' and res['checked'] >= 5 and 'remaining' in res)
t('automatic checks respect Temple being switched off (no model calls)', (SENT.clear(), TS.check([w4])['model_calls'])[1] == 0)

# 8. deleting the newer item unlinks the older one
K.forget(loc)
t('deleted replacement no longer referenced', not K.meta([old2])[old2]['superseded_by'])

# 9. memories: Temple suggests "Replaces: <ID>", you approve as a replacement
mo = s.propose('Temple provider', 'Temple uses Luna for reviews.', 'Stefan said so')['id']; s.review(mo, 'approved')
mn = s.propose('Temple provider', 'Temple uses Haiku for reviews when Luna is failing.', 'Stefan said so')['id']
FakeResp_text = f'Recommendation: approve\nReasons: newer version of the same fact.\nReplaces: {mo}'
class MemResp:
    usage = None; output_text = FakeResp_text
class MemOpenAI(FakeOpenAI):
    def create(s_, **k): return MemResp()
openai.OpenAI = MemOpenAI
temple.review_record(mn)
item = [i for i in temple.queue('pending')['items'] if i['id'] == mn][0]
t('Temple queue carries the suggested replacement', item['replaces'] and item['replaces']['id'] == mo)
a = {x['key']: x for x in actions.summary()['sections']}
t('Actions proposal shows it', any(i['id'] == mn and i['replaces'] for i in a['proposals']['items']))
t('nothing replaced until you approve', s.records('approved')['total'] >= 1 and not any(r['id'] == mo and r['status'] == 'superseded' for r in s.records('all')['records']))
cl.post(f'/admin/api/records/{mn}/replace', json={'old_id': mo, 'reason': 'Approved on Actions'}, headers=H)
st = {r['id']: r['status'] for r in s.records('all')['records']}
t('approve as replacement supersedes the old memory', st[mo] == 'superseded' and st[mn] == 'approved')

# 10. a passing mention of one word in quotes is not a replacement
g1 = note('Temple settings and reviewer choices', 'Temple settings: automatic reviews, provider choice and categorising mode.')
g2 = note('Voice setup', 'This replaces nothing about "Temple" but mentions it. Voice uses ElevenLabs Scribe for speech.')
SENT.clear(); TS.check([g2], manual=False)
t('one quoted word does not count as naming an item', not any(x['old_id'] == g1 for x in K.replacements('all', new_id=g2)))
