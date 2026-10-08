"""Digital teams, judgement when Stefan allows it (Stefan, 8 Oct 2026): five rate sources in the order and with the permissions the rule
"Where digital teams' rates come from" sets on the Rules page (published, library, built up, estimate; unpriced last). Estimates are
refused unless the rule or the per-job "Ask the team to estimate these" allows them; built-up rates are worked out in code from cited
parts; badges and the assumptions list name estimates with their reasoning, and the totals say how much is estimated. No question is
sent back to Stefan unchanged, a send-back loop is stopped, and a note asking for something the rules do not allow is explained with
where to allow it. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, re
import app, substrate_store as s, assistants, org_research, rules_engine
import teams, team_qs
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False

# ---------------- the rule ----------------
rs = rules_engine.rate_sources()
t('the rate-source rule is on the Rules page: published, library, built up allowed; estimate only when asked',
  rs == {'on': True, 'order': ['published', 'library', 'built_up', 'estimate'], 'allowed': ['published', 'library', 'built_up']}
  and rules_engine.rule('rate_sources')['kind'] == 'enforced')
r = cl.put('/admin/api/rules/rate_sources', json={'params': {'order': ['library', 'nonsense', 'published'], 'allowed': ['library', 'estimate', 'bogus']}}, headers=H)
t('its order and permissions are edited there, cleaned in code', r.status_code == 200
  and rules_engine.rate_sources()['order'] == ['library', 'published', 'built_up', 'estimate'] and rules_engine.rate_sources()['allowed'] == ['library', 'estimate'])
DEFAULT = {'order': ['published', 'library', 'built_up', 'estimate'], 'allowed': ['published', 'library', 'built_up']}
rules_engine.update_rule('rate_sources', new_params=DEFAULT)
page = cl.get('/admin/rules').text
t('the Rules page has the editor for it (order and allowed)', "r.id==='rate_sources'" in page and 'Unpriced: always last' in page)

# ---------------- the team and stand-in models ----------------
team = teams.from_template('quantity-surveying', name='Estimates test team')
TID = team['id']
teams.set_autonomy(TID, 'signoff')
DOC = 'FICTIONAL hall spec.md'
PLAN = {'plan': 'Measure from the specification.', 'elements': [{'name': 'Walls', 'documents': [DOC]}], 'documents': [{'name': DOC, 'use': 'all'}],
        'location': '', 'summary': 'Planned.', 'note': 'Go.', 'questions': []}
ITEMS = [{'element': 'Walls', 'description': f'Wall item {n}', 'quantity': 10, 'unit': 'm2', 'source': {'document': DOC, 'page': '1'}} for n in range(1, 5)]
CALLS, SEARCHES = [], []
STATE = {'plan': [], 'measure': [], 'talk': []}
P = {'f': None}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    payload = messages[0]['content']
    CALLS.append({'workload': workload, 'system': system, 'payload': payload})
    if 'Lead QS' in workload and 'message_from_stefan' in payload:
        return json.dumps(STATE['talk'].pop(0))
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in payload:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload: return json.dumps(STATE['plan'].pop(0) if STATE['plan'] else PLAN)
    if 'Measurement' in workload:
        return json.dumps(STATE['measure'].pop(0) if STATE['measure'] else {'accept': True, 'items': ITEMS, 'summary': '', 'note': 'Price these.'})
    if 'Market Trends' in workload: return json.dumps({'matches': [], 'commentary': 'Nothing to compare.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


PAGES = {'https://fictional-prices.example/q1': 'Wall item 1 prices', 'https://fictional-prices.example/blocks': 'Blocks',
         'https://fictional-prices.example/labour': 'Labour rates', 'https://fictional-prices.example/similar': 'A similar hall'}


def fake_ask(prompt, query, provider, workload='', **kw):
    refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    SEARCHES.append({'refs': refs, 'query': query, 'prompt': prompt})
    return json.dumps(P['f'](refs, query)), dict(PAGES)


def rates_standard(refs, query):
    """Q1 published; Q2 built up; Q3 nothing; Q4 an estimate offered."""
    out = []
    for r in refs:
        if r == 'Q1': out.append({'ref': r, 'source': 'published', 'rate': 50, 'unit': 'm2', 'source_url': 'https://fictional-prices.example/q1', 'source_date': '2026-06'})
        if r == 'Q2': out.append({'ref': r, 'source': 'built_up', 'rate': 999, 'built_up': {'components': [
            {'description': 'Concrete blocks', 'quantity_per_unit': 10, 'unit': 'nr', 'rate': 1.25, 'source_url': 'https://fictional-prices.example/blocks', 'source_date': '2026-05'},
            {'description': 'Bricklayer', 'quantity_per_unit': 0.333, 'unit': 'hr', 'rate': 31.5, 'source_url': 'https://fictional-prices.example/labour', 'source_date': '2026-04'}]}})
        if r == 'Q4': out.append({'ref': r, 'source': 'estimate', 'estimate': {'rate': 85, 'reasoning': 'Similar block walls cost about £80–£90 per m2 at this height.',
                                                                              'assumptions': ['Wall height 3 m (not given on the drawings)'],
                                                                              'comparables': [{'rate': 82, 'unit': 'm2', 'source_url': 'https://fictional-prices.example/similar', 'source_date': '2026-03'},
                                                                                              {'rate': 70, 'unit': 'm2', 'source_url': 'https://made-up.example/x', 'source_date': '2026-01'}]}})
    return {'rates': out, 'searches': ['wall rates']}


assistants._call = fake_call
org_research._ask = fake_ask

# Market Trends QS searches the market too (task 3): its queries get a plain answer with no findings here
_price_ask = org_research._ask
org_research._ask = lambda prompt, query, provider, workload='', **kw: ((json.dumps({'findings': [], 'commentary': 'No market evidence.'}), {})
                                                                         if 'MEASURED ITEMS' not in query else _price_ask(prompt, query, provider, workload, **kw))
P['f'] = rates_standard


def start(title='FICTIONAL estimates job'):
    body = {'job_type': 'cost-estimate', 'title': title, 'brief': 'A fictional single-storey hall for a community trust, to be estimated.',
            'uploads': [{'name': DOC, 'kind': 'spec', 'text': 'FICTIONAL specification. Page 1: walls.'}]}
    r = cl.post(f'/admin/api/teams/{TID}/jobs', json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def items_of(j): return {i['ref']: i for i in j['outputs']['price']['items']}


# ---------------- estimates refused unless allowed; built-up rates in code ----------------
j = start()
it = items_of(j)
t('the prompt names each source in the rule\'s order and whether it is allowed', '4. estimate: not allowed' in SEARCHES[-1]['query']
  and '1. published: allowed' in SEARCHES[-1]['query'])
t('a published rate with its returned page and date is used (badge Published)', it['Q1']['rate_source'] == 'web' and it['Q1']['rate'] == 50.0)
t('a built-up rate is worked out in code from its cited parts, not the model\'s figure', it['Q2']['rate_source'] == 'built_up'
  and it['Q2']['rate'] == 22.99 and [w['amount'] for w in it['Q2']['working']] == [12.5, 10.49] and all(w['source_url'] in PAGES for w in it['Q2']['working']))
t('an estimate is refused while the rule does not allow it: the item stays unpriced', it['Q4']['rate_source'] == 'unpriced' and it['Q4']['rate'] is None
  and any(x['ref'] == 'Q4' and x['source'] == 'estimate' and 'not allowed' in x['reason'] for x in j['outputs']['price']['refused_rates']))
t('nothing priced it: unpriced, never invented', it['Q3']['rate_source'] == 'unpriced')

# a built-up rate with an uncited part is refused
P['f'] = lambda refs, q: {'rates': [{'ref': 'Q2', 'source': 'built_up', 'built_up': {'components': [
    {'description': 'Blocks', 'quantity_per_unit': 10, 'rate': 1.25, 'source_url': 'https://made-up.example/blocks', 'source_date': '2026-05'}]}}]}
jb = start('FICTIONAL estimates job: uncited part')
t('a built-up rate with a part the search did not return is refused, with the reason', items_of(jb)['Q2']['rate_source'] == 'unpriced'
  and any(x['ref'] == 'Q2' and x['source'] == 'built_up' and 'no page the search returned' in x['reason'] for x in jb['outputs']['price']['refused_rates']))
P['f'] = rates_standard

# ---------------- the decision panel: Ask the team to estimate these ----------------
pg = cl.get(f'/admin/api/teams/jobs/{j["id"]}/page').json()
dec = pg['view']['decision']
t('the decision panel offers Ask the team to estimate these, saying the rule does not allow estimates', dec['can_estimate'] and not dec['estimate_rule_on']
  and dec['rule_href'] == '/admin/rules?rule=rate_sources#rules' and {i['ref'] for i in dec['items']} == {'Q3', 'Q4'})
t('the badges: Published, Built up, Unpriced', {r_['ref']: r_['source_label'] for r_ in pg['view']['plan']['rows']} == {'Q1': 'Published', 'Q2': 'Built up', 'Q3': 'Unpriced', 'Q4': 'Unpriced'})
t('an item that is not waiting cannot be estimated', cl.post(f'/admin/api/teams/jobs/{j["id"]}/estimate', json={'refs': ['Q1']}, headers=H).status_code == 400)
SEARCHES.clear()
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/estimate', json={'refs': ['Q4'], 'note': 'Assume a 3 m wall height.'}, headers=H)
j2 = r.json()
it2 = items_of(j2)
t('only the chosen item goes back to the Cost Surveyor, marked ESTIMATE ALLOWED, with Stefan\'s note', r.status_code == 200 and [x['refs'] for x in SEARCHES] == [['Q4']]
  and 'Q4 | Walls | Wall item 4 | 10.0 | m2 | ESTIMATE ALLOWED' in SEARCHES[0]['query'] and 'Assume a 3 m wall height.' in SEARCHES[0]['query'])
t('the estimate is used for that item on this job only, with its reasoning and assumptions', it2['Q4']['rate_source'] == 'estimate' and it2['Q4']['rate'] == 85.0
  and it2['Q4']['estimate']['assumptions'] == ['Wall height 3 m (not given on the drawings)'])
t('…a comparable rate counts only with a page the search returned', [c_['source_url'] for c_ in it2['Q4']['estimate']['comparables']] == ['https://fictional-prices.example/similar']
  and it2['Q4']['estimate']['comparables_dropped'] == 1)
t('the other items are kept exactly as priced', all(it2[k] == it[k] for k in ('Q1', 'Q2', 'Q3')))
t('the Lead QS assembles again and it comes back for sign-off', j2['status'] == 'waiting' and j2['pending'][0]['kind'] == 'signoff')
t('the request is in the job\'s history, with who asked', any(x['kind'] == 'estimates' and x['content']['refs'] == ['Q4'] for x in j2['steps']))
asm = j2['outputs']['assemble']
t('the estimate is listed under assumptions with its reasoning', any(a.startswith('Q4 Wall item 4: team estimate of £85.00 per m2') and 'Reasoning: Similar block walls' in a
                                                                     and 'Assumed: Wall height 3 m' in a for a in asm['assumptions']))
cp = asm['cost_plan']
t('the totals say how much is estimated (in code)', cp['estimated'] == 850.0 and cp['estimated_pct'] == round(850 / cp['construction'] * 100, 1)
  and any(a.startswith('£850.00 of the') and 'comes from team estimates' in a for a in asm['assumptions']))
pg = cl.get(f'/admin/api/teams/jobs/{j["id"]}/page').json()
t('the badge says Estimate, with the reasoning on the row', {r_['ref']: r_['source_label'] for r_ in pg['view']['plan']['rows']}['Q4'] == 'Estimate'
  and next(r_ for r_ in pg['view']['plan']['rows'] if r_['ref'] == 'Q4')['estimate']['reasoning'])
import zipfile, io
docs = j2['outputs']['documents']
w = zipfile.ZipFile(io.BytesIO(cl.get('/documents/' + next(d['id'] for d in docs if d['name'].endswith('.docx')) + '/download').content)).read('word/document.xml').decode()
t('the Word cost plan marks it ESTIMATE, shows built-up working and the estimated share', 'ESTIMATE by the team' in w and 'built up by Alice from cited published rates' in w
  and 'comes from team estimates' in w)
t('compute: the estimated share to one decimal place', team_qs.compute([{'ref': 'A', 'element': 'E', 'quantity': 1, 'rate': 300, 'rate_source': 'estimate'},
                                                                         {'ref': 'B', 'element': 'E', 'quantity': 1, 'rate': 600, 'rate_source': 'web'}])['estimated_pct'] == 33.3)

# ---------------- the rule decides: estimates allowed, order changed, rule off ----------------
rules_engine.update_rule('rate_sources', new_params={'order': DEFAULT['order'], 'allowed': ['published', 'library', 'built_up', 'estimate']})
j3 = start('FICTIONAL estimates job: estimates allowed')
t('with estimates allowed by the rule, the estimate is used at once', items_of(j3)['Q4']['rate_source'] == 'estimate')
rules_engine.update_rule('rate_sources', new_params={'order': ['built_up', 'published', 'library', 'estimate'], 'allowed': ['published', 'built_up']})
P['f'] = lambda refs, q: {'rates': [dict(x, built_up={'components': [{'description': 'Blocks', 'quantity_per_unit': 2, 'rate': 10, 'source_url': 'https://fictional-prices.example/blocks',
                                                                         'source_date': '2026-05'}]}) if x['ref'] == 'Q1' else x for x in rates_standard(refs, q)['rates']]}
j4 = start('FICTIONAL estimates job: order changed')
t('the order is the rule\'s: built up before published when you put it first', items_of(j4)['Q1']['rate_source'] == 'built_up' and items_of(j4)['Q1']['rate'] == 20.0)
P['f'] = rates_standard
rules_engine.update_rule('rate_sources', enabled=False)
j5 = start('FICTIONAL estimates job: rule off')
t('switched off on the Rules page, every source may be used', items_of(j5)['Q4']['rate_source'] == 'estimate')
rules_engine.update_rule('rate_sources', enabled=True, new_params=DEFAULT)

# ---------------- a note that asks for what the rules do not allow ----------------
P['f'] = lambda refs, q: dict(rates_standard(refs, q), not_allowed=['Stefan asked for estimates for every unpriced item'])
j6 = start('FICTIONAL estimates job: conflict')
pend = j6['pending'][0]
teams.set_autonomy(TID, 'approve')
r = cl.post(f'/admin/api/teams/steps/{pend["id"]}', json={'action': 'send_back', 'note': 'Just estimate anything you cannot find.'}, headers=H)
teams.set_autonomy(TID, 'signoff')
pg = cl.get(f'/admin/api/teams/jobs/{j6["id"]}/page').json()
cf = pg['view']['conflicts']
t('the team says plainly that the rule does not allow it, and links to the rule and the per-job button', cf
  and 'does not allow team estimates' in cf[0]['text'] and [l['label'] for l in cf[0]['links']] == ['Open the rule', 'Ask the team to estimate these']
  and cf[0]['links'][0]['href'] == '/admin/rules?rule=rate_sources#rules' and cf[0]['links'][1]['href'].endswith(f'/jobs/{j6["id"]}#estimate'))
t('…and the estimate offered after the note is still refused', next(r_ for r_ in pg['view']['plan']['rows'] if r_['ref'] == 'Q4')['source'] == 'unpriced')
P['f'] = rates_standard
STATE['talk'] = [{'reply': 'Estimates are not allowed for this team at the moment.', 'route_to': '', 'note_for_member': '',
                  'not_allowed': [{'what': 'Estimating every unpriced item', 'rule': 'rate_sources'}, {'what': 'x', 'rule': 'made_up_rule'}]}]
r = cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'Can you just estimate the rest?', 'job': j6['id']}, headers=H)
last = r.json()['messages'][-1]['content']
t('Talk to the team: the lead was told what the rules allow now', 'rate_sources' in CALLS[-1]['payload'] and 'not allowed: Team estimate' in CALLS[-1]['payload'])
t('…says it is not allowed, with the rule\'s link and the job\'s button; a rule it was not told about is ignored', r.status_code == 200
  and 'Not allowed at the moment: Estimating every unpriced item' in last and '/admin/rules?rule=rate_sources#rules' in last and '#estimate' in last and 'made_up_rule' not in last)

# ---------------- no unchanged re-ask ----------------
teams.set_autonomy(TID, 'approve')
Q = 'Is the hall to include a stage?'
STATE['plan'] = [dict(PLAN, questions=[Q]), PLAN, dict(PLAN, questions=[Q]), dict(PLAN, questions=[Q], what_changed='The new note mentions a performance space.')]
j7 = start('FICTIONAL estimates job: questions')
qq = j7['pending'][0]
cl.post(f'/admin/api/teams/steps/{qq["id"]}', json={'action': 'answer', 'note': 'No stage.'}, headers=H)
h1 = teams.job_detail(j7['id'])['pending'][0]
cl.post(f'/admin/api/teams/steps/{h1["id"]}', json={'action': 'send_back', 'note': 'Add external works.'}, headers=H)
j7 = teams.job_detail(j7['id'])
t('the same question again, without what changed, is not sent to Stefan: the earlier answer stands', j7['pending'][0]['kind'] == 'handoff'
  and sum(1 for x in j7['steps'] if x['kind'] == 'question') == 1 and any(x['kind'] == 'note' and 'your earlier answer stands' in x['note'] and 'No stage.' in x['note'] for x in j7['steps']))
cl.post(f'/admin/api/teams/steps/{j7["pending"][0]["id"]}', json={'action': 'send_back', 'note': 'Add a performance space.'}, headers=H)
j7 = teams.job_detail(j7['id'])
t('asked again with what changed, the re-ask says so', j7['pending'][0]['kind'] == 'question'
  and 'What changed since last time: The new note mentions a performance space.' in j7['pending'][0]['content']['questions'][0])
t('members are told never to re-ask unchanged', 'Never ask Stefan a question he has already answered' in CALLS[-1]['system'])

# a receiver that would send the same unchanged work back for the same reasons is stopped
teams.set_autonomy(TID, 'signoff')
STATE['measure'] = [{'accept': False, 'reasons': ['The plan names no external works.'], 'items': []}] * 3
j8 = start('FICTIONAL estimates job: loop')
sb = [x for x in j8['steps'] if x['kind'] == 'sendback']
t('a send-back with the same reasons on unchanged work is not sent round again: Stefan is asked, saying nothing changed',
  len(sb) == 2 and sb[1]['content']['same_as_before'] and j8['pending'][0]['kind'] == 'question'
  and 'has not changed since the last time' in j8['pending'][0]['content']['questions'][0])
last_sb = {'content': {'reasons': ['A', 'B'], 'work': 'w1'}}
t('what changed between send-backs is said plainly', teams._what_changed(last_sb, ['A', 'C'], 'w2') == 'Since the last send-back: 1 new reason, 1 earlier reason now met, the work was redone since the last send-back.')

# ---------------- the page script ----------------
html = cl.get(f'/admin/teams/{TID}/jobs/{j["id"]}').text
t('the job page has the button, the Estimate and Built up badges and the conflict box', "'Ask the team to estimate these'" in html and '.tm-src.estimate' in html
  and '.tm-src.built_up' in html and 'tm-conflict' in html)
import shutil, subprocess, tempfile
from pathlib import Path
node = shutil.which('node')
if node:
    for url in (f'/admin/teams/{TID}/jobs/{j["id"]}', '/admin/rules'):
        js = '\n;\n'.join(re.findall(r'<script>(.*?)</script>', cl.get(url).text, re.S))
        f = Path(tempfile.mkdtemp()) / 'page.js'; f.write_text(js, encoding='utf-8')
        res = subprocess.run([node, '--check', str(f)], capture_output=True, text=True, timeout=60)
        t(f'the page script parses (node --check): {url.split("/")[2]}', res.returncode == 0 or print(res.stderr[:800]))
