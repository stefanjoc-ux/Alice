"""Digital teams pages (Stefan, 7 Oct 2026): All teams (grouping fields, filters, search, drafts), Needs you from every source,
pins per person, the team page (tabs, the no-knowledge warning, rules and price order read from the code that applies them),
the job page (your rates recorded as yours, saved to the rate library only when ticked, sources and no total while items are
undecided), Talk to the team (checked, routed to a member), templates and team marks. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, re
import app, substrate_store as s, agents, assistants, org_research, rules_engine, temple, temple_discuss
import teams, team_qs
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False
temple.save_settings(False, 'claude')
TID, JT = team_qs.TEAM_ID, 'cost-estimate'

PLAN = {'plan': 'Measure by element.', 'elements': ['Substructure', 'Windows'], 'documents': [], 'location': '', 'summary': 'Planned.', 'note': 'Measure.', 'questions': []}
ITEMS = [{'element': 'Substructure', 'description': 'Concrete strip foundation 600 x 900 mm including excavation', 'quantity': 74, 'unit': 'm',
          'source': {'document': 'FICTIONAL specification.md', 'page': '1'}},
         {'element': 'Windows', 'description': 'Bespoke oak rooflight to main hall', 'quantity': 2, 'unit': 'nr', 'source': {'document': 'FICTIONAL specification.md', 'page': '2'}},
         {'element': 'Finishes', 'description': 'Acoustic ceiling panels to main hall', 'quantity': 170, 'unit': 'm2', 'source': {'document': 'FICTIONAL finishes schedule.csv', 'line': 'Line 5'}}]
STATE = {'plan': [], 'talk': []}
SEEN = []


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    payload = messages[0]['content']
    SEEN.append((workload, system, payload))
    if 'lead of' in system:
        return json.dumps(STATE['talk'].pop(0) if STATE['talk'] else {'reply': 'Understood.', 'route_to': '', 'note_for_member': ''})
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in payload:
        return json.dumps({'accept': True, 'summary': 'A small hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'Over to you.'})
    if 'Lead QS' in workload: return json.dumps(STATE['plan'].pop(0) if STATE['plan'] else PLAN)
    if 'Measurement' in workload: return json.dumps({'accept': True, 'items': ITEMS, 'summary': '3 items measured', 'note': 'Price these.'})
    if 'Market Trends' in workload: return json.dumps({'matches': [], 'commentary': 'Nothing comparable.', 'summary': 'Compared.'})
    raise AssertionError('unexpected call ' + workload)


assistants._call = fake_call
RET = {'https://fictional-prices.example/foundations': 'Fictional price book'}
PRICE_QUERIES = []
org_research._ask = lambda prompt, query, provider, workload='', **kw: PRICE_QUERIES.append(query) or (json.dumps({'rates': [
    {'ref': 'Q1', 'rate': 160, 'unit': 'm', 'source_url': 'https://fictional-prices.example/foundations', 'source_title': 'Foundations', 'source_date': '2026-05'}],
    'summary': '', 'note': 'Priced what I could.'}), dict(RET))
demo = team_qs.demo_project()


def start(tid=TID, **kw):
    body = {'job_type': JT, 'title': demo['title'], 'brief': demo['brief'], 'location': demo['location'], 'uploads': demo['documents']}
    body.update(kw)
    r = cl.post(f'/admin/api/teams/{tid}/jobs', json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def page(jid): return cl.get(f'/admin/api/teams/jobs/{jid}/page').json()
def step(sid, action, note=''): return cl.post(f'/admin/api/teams/steps/{sid}', json={'action': action, 'note': note}, headers=H)
def board(): return cl.get('/admin/api/teams/board').json()


# ---------------- the screens render ----------------
for path in ('/admin/teams', f'/admin/teams/{TID}', f'/admin/teams/{TID}/jobs/' + 'a' * 32):
    t(f'{path} renders', cl.get(path).status_code == 200)
html = cl.get(f'/admin/teams/{TID}').text
t('the team page has the six tabs, remembered in the address', all(x in html for x in ("['overview','Overview']", "['jobs','Jobs']", "['members','Members']", "['knowledge','Knowledge']",
                                                                                     "['rules','Rules and autonomy']", "['activity','Activity']")) and "replaceState(null,'','#'+k)" in html)
t('the board remembers its choices per browser, guarded', "localStorage.getItem('alice-teams-'+k)" in html and 'catch{return d}' in html)
t('a bad team id in the address is refused', cl.get('/admin/teams/bad id!').status_code in (404, 422))

# ---------------- marks, disciplines, drafts, templates ----------------
b = board()
qs = next(x for x in b['teams'] if x['id'] == TID)
t('the seeded team has its colour, icon and discipline', qs['colour'] == 'teal' and qs['icon'] == 'calculator' and qs['discipline'] == 'Quantity surveying')
t('colours are a fixed set, white text on each passes 4.5:1', set(b['colours']) == set(teams.COLOURS) and all(len(v['hex']) == 7 for v in b['colours'].values()))
def _lum(hx):
    r, g, bl = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bl)
t('…checked', all(1.05 / (_lum(v[0]) + 0.05) >= 4.5 for v in teams.COLOURS.values()))
r = cl.post('/admin/api/teams', json={'name': 'Bid team', 'description': 'Writes tender responses.', 'colour': 'navy', 'icon': 'pen', 'discipline': 'Bids and proposals'}, headers=H)
BID = r.json()['id']
t('a new team takes a colour, an icon and a discipline', r.status_code == 200 and r.json()['colour'] == 'navy' and r.json()['discipline'] == 'Bids and proposals')
t('an unknown colour or icon is refused', cl.post('/admin/api/teams', json={'name': 'X', 'colour': 'neon'}, headers=H).status_code == 400
  and cl.put(f'/admin/api/teams/{BID}/identity', json={'icon': 'rocket'}, headers=H).status_code == 400)
v0 = teams.get(BID)['current_version']
r = cl.put(f'/admin/api/teams/{BID}/identity', json={'colour': 'plum', 'discipline': 'Bids'}, headers=H)
t('editing the mark or discipline is a new version that says what changed', r.status_code == 200 and teams.get(BID)['current_version'] == v0 + 1
  and 'colour' in teams.versions(BID)[0]['what'] and 'discipline' in teams.versions(BID)[0]['what'])
bt = next(x for x in board()['teams'] if x['id'] == BID)
t('a team with no members or job types is a draft that says what is missing', bt['status'] == 'draft' and 'Add members' in bt['missing'] and 'Add a job type' in bt['missing'])
t('a fixed address under /admin/api/teams is never a team id', teams.create('Board')['id'] != 'board')
r = cl.post('/admin/api/teams', json={'name': 'Cost planning (Edinburgh)', 'template': 'quantity-surveying', 'colour': 'brick', 'icon': 'building'}, headers=H)
T2 = r.json()['id']
t('a team from a template copies its members and job types, with your name and mark', r.status_code == 200 and [m['role'] for m in r.json()['members']][0] == 'Lead QS'
  and r.json()['job_types'][0]['stages'][2]['handler'] == 'qs_price' and r.json()['colour'] == 'brick' and r.json()['name'] == 'Cost planning (Edinburgh)')
t('templates are listed on the board; no example teams are created on their own', [x['key'] for x in board()['templates']] == ['quantity-surveying']
  and len(board()['teams']) == 4)

# ---------------- a job waiting on unpriced items ----------------
team_qs.load_demo_rates(TID)
j = start()
JID = j['id']
for _ in range(2): step(page(JID)['pending'][0]['id'], 'approve')
p = page(JID)
dec = p['view']['decision']
pl = p['view']['plan']
t('the job waits on the hand-off out of pricing, and the Lead QS asks for a decision on the unpriced items',
  dec and dec['state'] == 'handoff' and dec['lead'] == 'Lead QS' and dec['pricer'] == 'Cost Surveyor' and {i['ref'] for i in dec['items']} == {'Q2', 'Q3'}
  and dec['title'] == 'Lead QS needs a decision on 2 items')
t('the cost plan so far shows each source (web linked to its page, library, unpriced)', {r_['ref']: r_['source'] for r_ in pl['rows']} == {'Q1': 'web', 'Q2': 'unpriced', 'Q3': 'unpriced'}
  and pl['rows'][0]['source_url'] == 'https://fictional-prices.example/foundations' and pl['counts'] == {'web': 1, 'library': 0, 'built_up': 0, 'estimate': 0, 'yours': 0, 'unpriced': 2})
t('no total while items are undecided; amounts still worked out in code', pl['totals'] is None and pl['undecided'] == 2 and pl['rows'][0]['amount'] == 11840.0
  and pl['rows'][1]['amount'] is None)
t('the stage tracker: three done (with counts), the next waiting for you, then to come and your sign-off', [x['state'] for x in p['progress']] == ['done', 'done', 'done', 'waiting', 'todo', 'todo']
  and p['progress'][1]['count'] == '3 items' and p['progress'][-1]['title'] == 'Your sign-off')
t('the job is labelled as the demo job', p['is_demo'] and p['where'].startswith('Waiting for you'))

# ---------------- Needs you, from each source ----------------
nb = board()
mine = [i for i in nb['needs'] if i['job_id'] == JID]
t('Needs you: the decision on unpriced items, from the lead, goes straight to the job', len(mine) == 1 and mine[0]['kind'] == 'decision'
  and 'Lead QS needs a decision on 2 unpriced items' in mine[0]['text'] and mine[0]['href'] == f'/admin/teams/{TID}/jobs/{JID}' and mine[0]['action'] == 'Review')
STATE['plan'] = [dict(PLAN, questions=['Is the hall to include a stage?'])]
jq = start(T2, title='FICTIONAL demo: hall with a question')
it = next(i for i in board()['needs'] if i['job_id'] == jq['id'])
t('…a question, with the question in plain words', it['kind'] == 'question' and 'Is the hall to include a stage?' in it['text'] and it['action'] == 'Answer' and it['team'] == 'Cost planning (Edinburgh)')
step(jq['pending'][0]['id'], 'answer', 'No stage.')
it = next(i for i in board()['needs'] if i['job_id'] == jq['id'])
t('…a hand-off', it['kind'] == 'handoff' and 'approve the hand-off to Measurement Surveyor' in it['text'])
teams.set_autonomy(T2, 'signoff')
js = start(T2, title='FICTIONAL demo: runs on its own')
t('…an output waiting for sign-off (with undecided unpriced items, the decision comes first)', any(i['job_id'] == js['id'] and i['kind'] == 'decision' for i in board()['needs']))
with s.db() as c:
    c.execute('INSERT INTO team_suggestions(id,team_id,member,proposed,reason,status,created_at) VALUES (?,?,?,?,?,?,?)', ('f' * 32, BID, 'x', 'New text', 'Better.', 'pending', s.now()))
t('…Temple\'s suggestion', any(i['kind'] == 'suggestion' and i['team_id'] == BID and i['href'].endswith('#members') for i in board()['needs']))
real = assistants._call
class FakeProviderError(Exception):
    status_code = 400
    message = 'Your credit balance is too low.'
FakeProviderError.__module__ = 'anthropic._exceptions'
def failing(*a, **k): raise FakeProviderError('Your credit balance is too low.')
assistants._call = failing
jf = start(T2, title='FICTIONAL demo: provider refuses')
assistants._call = real
it = next(i for i in board()['needs'] if i['job_id'] == jf['id'])
t('…a job stopped by a failure, with the provider\'s own message and Resume', it['kind'] == 'stopped' and 'credit balance is too low' in it['text'] and it['resume'] == jf['id']
  and it['action'] == 'Resume')
t2b = next(x for x in board()['teams'] if x['id'] == T2)
t('…and that team shows as Paused, in words, counted under Needs you', t2b['status'] == 'paused' and t2b['status_label'] == 'Paused' and t2b['needs_you'])
agents.set_status('team-member', 'paused', '3 failed runs in a row; last error: Anthropic rejected the request (HTTP 400): Your credit balance is too low.', by='Alice')
nb = board()
t('…members paused on the Agents page after failed runs: one item first, with the reason', nb['needs'][0]['kind'] == 'paused' and 'credit balance' in nb['needs'][0]['text']
  and nb['needs'][0]['href'] == '/admin/agents?agent=team-member' and all(x['status'] in ('paused', 'draft') for x in nb['teams']))
agents.set_status('team-member', 'active')
cl.post(f'/admin/api/teams/jobs/{jf["id"]}/stop', headers=H)
t('the summary line counts teams, members, jobs running and what needs you', set(nb['summary']) == {'teams', 'members', 'running', 'needs_you'} and nb['summary']['needs_you'] == len(nb['needs']))

# ---------------- grouping and filters (the fields the board groups and filters on) ----------------
b = board()
by = {x['id']: x for x in b['teams']}
t('every team carries what the board groups by (discipline, status) and filters on', all({'discipline', 'status', 'status_label', 'needs_you', 'search'} <= set(x) for x in b['teams'])
  and by[TID]['status'] == 'needs_you' and by[BID]['status'] == 'draft' and by[BID]['discipline'] == 'Bids')
t('search covers member roles and job names', 'cost surveyor' in by[TID]['search'] and 'larchbank' in by[TID]['search'])
t('a card shows the lead and the live job with one segment per stage plus sign-off', [m['lead'] for m in by[TID]['members']] == [True, False, False, False]
  and by[TID]['job']['id'] == JID and len(by[TID]['job']['progress']) == 6 and by[TID]['job']['where'].startswith('Waiting for you'))
t('disciplines are suggested from the teams and a starter list', 'Bids' in b['disciplines'] and 'Quantity surveying' in b['disciplines'])

# ---------------- pins and recent teams, per person ----------------
with s.acting('Stefan'):
    cl.put(f'/admin/api/teams/{T2}/pin', json={'on': True}, headers=H)
    teams.seen(TID); teams.seen(BID)
    pa = teams.prefs()
with s.acting('Someone Else'):
    pb = teams.prefs()
    teams.set_pin(BID, True)
with s.acting('Stefan'):
    nav = teams._nav()
t('pins and recent teams are kept per person', pa['pins'] == [T2] and pa['recent'] == [BID, TID] and pb == {'pins': [], 'recent': []})
t('the team menu lists pinned teams with their mark and a needs-you flag, and recent ones not pinned', [x['id'] for x in nav['pins']] == [T2] and nav['pins'][0]['needs_you'] is not None
  and [x['id'] for x in nav['recent']] == [BID, TID] and nav['pins'][0]['hex'] == teams.COLOURS['brick'][0])
with s.acting('Stefan'):
    cl.put(f'/admin/api/teams/{T2}/pin', json={'on': False}, headers=H)
    t('unpinning removes it for you only', teams.prefs()['pins'] == [])
with s.acting('Someone Else'): t('…and the other person keeps theirs', teams.prefs()['pins'] == [BID])

# ---------------- the team page ----------------
tp = cl.get(f'/admin/api/teams/{TID}/page').json()
t('members with no knowledge ticked are listed for the warning', set(tp['readiness']['no_knowledge']) == {m['id'] for m in tp['team']['members']} and tp['readiness']['hint'])
s.create_category('Cost data')
cl.put(f'/admin/api/teams/{TID}/members/lead-qs', json={'categories': ['Cost data']}, headers=H)
tp = cl.get(f'/admin/api/teams/{TID}/page').json()
t('ticking knowledge clears that member\'s warning (the Knowledge tab saves through the member API)', 'lead-qs' not in tp['readiness']['no_knowledge'] and len(tp['readiness']['no_knowledge']) == 3)
t('the lead is whoever works the first stage', tp['lead'] == 'lead-qs')
t('each member\'s state in the live job', tp['member_states']['measurement-surveyor']['label'] == 'Done · 3 items measured' and tp['member_states']['lead-qs']['state'] == 'waiting'
  and tp['member_states']['market-trends-qs']['label'] == 'To come')
t('tools come from the stages a member works on (web search for the Cost Surveyor)', tp['member_tools']['cost-surveyor'] == ['Rate library', 'Web search'] and tp['member_tools']['lead-qs'] == [])
t('where prices come from: the order the pricing code applies, read from the rate-source rule', [(o['key'], o['allowed']) for o in tp['pricing'][0]['order']]
  == [(x['key'], x['allowed']) for x in team_qs.price_rules()] == [('published', True), ('library', True), ('built_up', True), ('estimate', False), ('unpriced', True)]
  and tp['pricing'][0]['role'] == 'Cost Surveyor' and 'not by the models' in tp['pricing'][0]['note'] and tp['pricing'][0]['rules'][0]['href'].startswith('/admin/rules?rule='))
ids = [x['id'] for x in tp['rules']['rules']]
t('rules this team follows: the member turns\' guardrails, named as on the Rules page, with links', ids == [x for x in agents.ANATOMY['team-member']['guardrails'] if x != 'client_separation']
  and all(x['name'] == rules_engine.rule(x['id'])['name'] and x['on'] and x['href'] == f'/admin/rules?rule={x["id"]}#rules' for x in tp['rules']['rules']))
rules_engine.update_rule('spend_cap', enabled=False)
rules_engine.update_rule('client_separation', enabled=False)
tp = cl.get(f'/admin/api/teams/{TID}/page').json()
t('switching a rule off on the Rules page shows here as switched off', next(x for x in tp['rules']['rules'] if x['id'] == 'spend_cap')['on'] is False)
t('the client separation chip reads the rule', any(c['label'] == 'Client separation off' and c['off'] for c in tp['chips']))
rules_engine.update_rule('spend_cap', enabled=True); rules_engine.update_rule('client_separation', enabled=True)
teams.update_job_type(TID, JT, client_facing=False)
tp = cl.get(f'/admin/api/teams/{TID}/page').json()
t('a team whose jobs are not client-facing follows Client separation instead', 'client_separation' in [x['id'] for x in tp['rules']['rules']] and 'client_documents' not in [x['id'] for x in tp['rules']['rules']])
teams.update_job_type(TID, JT, client_facing=True)
t('Actions and cards link to the new addresses', all(w['href'].startswith('/admin/teams/') for w in teams.waiting())
  and cl.get('/admin/api/cards/review/h-' + page(JID)['pending'][0]['id']).json()['actions'][0]['href'] == f'/admin/teams/{TID}/jobs/{JID}')

# ---------------- your decision on unpriced items ----------------
lib_before = len(team_qs.library(TID))
t('a rate must be above zero', cl.post(f'/admin/api/teams/jobs/{JID}/rates', json={'entries': [{'ref': 'Q2', 'rate': -5}]}, headers=H).status_code == 400)
t('only unpriced items waiting for a decision', cl.post(f'/admin/api/teams/jobs/{JID}/rates', json={'entries': [{'ref': 'Q1', 'rate': 5}]}, headers=H).status_code == 400)
t('nothing entered is refused', cl.post(f'/admin/api/teams/jobs/{JID}/rates', json={'entries': [{'ref': 'Q2'}]}, headers=H).status_code == 400)
with s.acting('Stefan'):
    r = cl.post(f'/admin/api/teams/jobs/{JID}/rates', json={'entries': [{'ref': 'Q2', 'rate': 1250.5}], 'save_to_library': False}, headers=H)
p = page(JID)
q2 = next(x for x in p['view']['plan']['rows'] if x['ref'] == 'Q2')
t('your rate is recorded as yours, source "Your rate"', r.status_code == 200 and q2['source'] == 'yours' and q2['source_label'] == 'Your rate' and q2['rate'] == 1250.5
  and q2['decided_by'] == 'Stefan' and q2['amount'] == 2501.0)
rs = [x for x in p['steps'] if x['kind'] == 'rates']
t('…in the job\'s history, with who decided', len(rs) == 1 and rs[0]['decided_by'] == 'Stefan' and 'Your rate' in rs[0]['note'] and rs[0]['member'] == 'stefan'
  and any(x['kind'] == 'rates' and x['who'] == 'Stefan' for x in p['timeline']))
t('not ticked: nothing saved to the rate library', len(team_qs.library(TID)) == lib_before)
t('still no total: one item undecided', p['view']['plan']['totals'] is None and p['view']['plan']['undecided'] == 1 and p['view']['decision']['count'] == 1)
r = cl.post(f'/admin/api/teams/jobs/{JID}/rates', json={'entries': [{'ref': 'Q3', 'rate': 42}], 'save_to_library': True, 'go_on': True}, headers=H)
p = page(JID)
lib = team_qs.library(TID)
t('ticked: the rate goes into the rate library through its own import', len(lib) == lib_before + 1 and any(x['description'] == 'Acoustic ceiling panels to main hall' and x['rate'] == 42
  and x['batch_name'] == f'Your rates from {teams.ref(JID)}' for x in lib))
t('"Use these and continue" approves the hand-off: the Lead QS assembles with your rates', r.status_code == 200 and p['outputs']['assemble']
  and not p['view']['decision'] and [x['state'] for x in p['progress']][3] == 'done')
pl = p['view']['plan']
exp = team_qs.compute(p['outputs']['price']['items'], 1.0, team_qs.SETTINGS)
t('every item decided: the total appears, worked out in code', pl['totals'] and pl['undecided'] == 0 and pl['totals']['total'] == exp['total']
  and pl['totals']['construction'] == 11840.0 + 2501.0 + 7140.0)
r = cl.post(f'/admin/api/teams/jobs/{JID}/rates', json={'entries': [{'ref': 'Q3', 'rate': 1}]}, headers=H)
t('a decided item cannot be decided again', r.status_code == 400)

# at sign-off (team runs on its own): leave one unpriced, enter the other; documents follow; a refusal changes nothing
pj = page(js['id'])
t('at sign-off the decision panel offers Send back to the lead', pj['view']['decision']['state'] == 'signoff' and pj['pending'][0]['kind'] == 'signoff')
old_docs = {d['id'] for d in pj['outputs']['documents']}
with s.db() as c: c.execute("UPDATE team_jobs SET outputs=replace(outputs, 'Bespoke oak rooflight', 'Bespoke oak rooflight sk-ant-api03-" + 'D' * 90 + "') WHERE id=?", (js['id'],))
before = page(js['id'])['outputs']['price']
r = cl.post(f'/admin/api/teams/jobs/{js["id"]}/rates', json={'entries': [{'ref': 'Q2', 'rate': 10}], 'save_to_library': True}, headers=H)
t('saving to the rate library runs its checks; a refusal changes nothing', r.status_code == 400 and page(js['id'])['outputs']['price'] == before)
with s.db() as c: c.execute("UPDATE team_jobs SET outputs=replace(outputs, ' sk-ant-api03-" + 'D' * 90 + "', '') WHERE id=?", (js['id'],))
r = cl.post(f'/admin/api/teams/jobs/{js["id"]}/rates', json={'entries': [{'ref': 'Q2', 'rate': 900}, {'ref': 'Q3', 'unpriced': True}], 'save_to_library': False}, headers=H)
pj = page(js['id'])
t('left unpriced by you: excluded from the total, which now shows', r.status_code == 200 and pj['view']['plan']['totals'] and pj['view']['plan']['undecided'] == 0
  and any('left unpriced by' in a for a in pj['outputs']['assemble']['assumptions']) and not any(a.startswith('Q2 ') and 'unpriced' in a for a in pj['outputs']['assemble']['assumptions']))
t('…the cost plan recalculated and the Word and Excel documents rebuilt', pj['outputs']['assemble']['cost_plan']['total'] == pj['view']['plan']['totals']['total']
  and pj['outputs']['documents'] and not ({d['id'] for d in pj['outputs']['documents']} & old_docs) and pj['pending'][0]['kind'] == 'signoff')
t('the sign-off itself still waits for you', pj['status'] == 'waiting')

# ---------------- Talk to the team ----------------
STATE['talk'] = [{'reply': 'Noted: the Cost Surveyor will prefer 2025 rates.', 'route_to': 'cost-surveyor', 'note_for_member': 'Prefer rates published in 2025 or later.'}]
jt_ = start(title='FICTIONAL demo: talking')
r = cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'Please use recent rates only.', 'job': jt_['id']}, headers=H)
ms = r.json()['messages']
t('a message goes to the lead, who answers and routes it', r.status_code == 200 and [m['role'] for m in ms] == ['you', 'lead'] and ms[1]['who'] == 'Lead QS'
  and ms[1]['routed_role'] == 'Cost Surveyor' and 'Please use recent rates only.' in SEEN[-1][2])
t('…as a tracked agent run', any(x['id'] == 'team-talk' for x in agents.listing()['agents']) and cl.get('/admin/api/agents/team-talk/runs').json())
step(page(jt_['id'])['pending'][0]['id'], 'approve'); step(page(jt_['id'])['pending'][0]['id'], 'approve')
t('the routed note reaches that member the next time it works on the job', 'Prefer rates published in 2025 or later.' in PRICE_QUERIES[-1])
t('…and is in the timeline', any(x['kind'] == 'routed' for x in page(jt_['id'])['timeline']))
t('a message holding a secret never reaches the model', cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'key sk-ant-api03-' + 'E' * 90, 'job': jt_['id']}, headers=H).status_code == 400
  and 'sk-ant' not in SEEN[-1][2])
real_spend = rules_engine.check_spend
rules_engine.check_spend = lambda kind: (_ for _ in ()).throw(rules_engine.RuleViolation('Spending cap reached: chat is paused.'))
t('the spending cap applies', cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'How is it going?'}, headers=H).status_code == 400)
rules_engine.check_spend = real_spend
r = cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'What does the team do?'}, headers=H)
t('Ask the team without a job: kept with the team, nothing routed', r.status_code == 200 and len(cl.get(f'/admin/api/teams/{TID}/talk').json()['messages']) == 2
  and not r.json()['routed_to'])
t('another team\'s job is refused', cl.post(f'/admin/api/teams/{T2}/talk', json={'message': 'Hello', 'job': jt_['id']}, headers=H).status_code == 400)
