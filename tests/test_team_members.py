"""Digital teams: the Members tab (9 Oct 2026; periods Last 7 days, This month, Last month, Last 12 months, All time and the
model tier, 10 Oct 2026).

Each member's figures for every period agree with the Overview's Running cost card, the Agents page and Usage; the editor's save is
one new team version; the hand-off order is saved as a new version (stages follow it only in job types made of your own steps);
warnings are worked out from the member's tools, its stages and the rate-source rule; a member cannot be removed while a job is
running on the current version; Add a member starts from a template. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import app, substrate_store as s, assistants, org_research, rules_engine, usage_meter, permissions
import teams, team_qs, team_costs
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False
D = lambda x: Decimal(str(x))

team = teams.from_template('quantity-surveying', name='Members test team')
TID = team['id']
teams.set_autonomy(TID, 'signoff')
DOC = 'FICTIONAL hall spec.md'
PLAN = {'plan': 'Measure from the specification.', 'elements': [{'name': 'Walls', 'documents': [DOC]}],
        'documents': [{'name': DOC, 'use': 'all'}], 'location': '', 'summary': 'Planned.', 'note': 'Go.', 'questions': []}
ITEMS = [{'element': 'Walls', 'description': 'Wall item 1', 'quantity': 10, 'unit': 'm2', 'source': {'document': DOC, 'page': '1'}}]
USAGE = SimpleNamespace(usage={'input_tokens': 10000, 'output_tokens': 1000})        # Sonnet: $0.03 a call


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    payload = messages[0]['content']
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    if 'Lead QS' in workload and 'message_from_the_user' in payload:
        return json.dumps({'reply': 'Noted.', 'route_to': '', 'note_for_member': '', 'not_allowed': []})
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in payload:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload and 'SUGGESTED MARKET ADJUSTMENT' in payload:
        return json.dumps({'accept': False, 'reason': 'Not convinced.', 'summary': 'Rejected.'})
    if 'Lead QS' in workload: return json.dumps(PLAN)
    if 'Measurement' in workload: return json.dumps({'accept': True, 'items': ITEMS, 'summary': '', 'note': 'Price these.'})
    if 'Market Trends' in workload: return json.dumps({'matches': [], 'commentary': 'Nothing to compare.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


def fake_ask(prompt, query, provider, workload='', **kw):
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    if 'MEASURED ITEMS' not in query: return json.dumps({'findings': [], 'commentary': 'No market evidence.'}), {}
    refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    return json.dumps({'rates': [{'ref': r, 'source': 'published', 'rate': 50, 'unit': 'm2', 'source_url': 'https://fictional-prices.example/q1',
                                  'source_date': '2026-06'} for r in refs], 'searches': ['wall rates']}), {'https://fictional-prices.example/q1': 'Wall prices'}


assistants._call = fake_call
org_research._ask = fake_ask


def start(title='FICTIONAL members job'):
    r = cl.post(f'/admin/api/teams/{TID}/jobs', headers=H, json={'job_type': 'cost-estimate', 'title': title, 'client': '',
                'brief': 'A fictional single-storey hall for a community trust, to be estimated.',
                'uploads': [{'name': DOC, 'kind': 'spec', 'text': 'FICTIONAL specification. Page 1: walls.'}]})
    assert r.status_code == 200, r.text
    return r.json()


def page(): return cl.get(f'/admin/api/teams/{TID}/page').json()


# ---------------- figures: the same as the Running cost card, the Agents page and Usage ----------------
j1 = start()
j2 = start('FICTIONAL members job two')
t('both jobs run to sign-off', j1['status'] == 'waiting' and j2['status'] == 'waiting')
cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'How is it going?', 'job': j1['id']}, headers=H)
NOW = datetime.now(timezone.utc) + timedelta(seconds=5)
base = team_costs.team(TID, now=NOW)
M = team_costs.members(TID, now=NOW)
keys = [p['key'] for p in M['periods']]
t('five periods: last 7 days, this month, last month, last 12 months, all time', keys == ['7d', 'month', 'last_month', '12m', 'all']
  and [p['label'] for p in M['periods']] == ['Last 7 days', 'This month', 'Last month', 'Last 12 months', 'All time']
  and M['periods'][4]['since'].startswith('tracked since '))
card = {m['id']: m for m in base['members']}
t('each member\'s cost for the last 7 days and 12 months is exactly the Overview card\'s figure',
  all(M['members'][mid]['costs'][k] == card[mid]['costs'][k] for mid in M['members'] for k in ('7d', '12m')))
t('…and the team total too', all(M['total'][k] == base['total'][k] for k in ('7d', '12m')))
with s.db() as c:
    recs = [dict(r) for r in c.execute('SELECT member_id, at, usd FROM team_costs WHERE team_id=?', (TID,))]
for k, _, st, en in team_costs.member_periods(NOW):
    want = {}
    for r in recs:
        if (st is None or r['at'] >= st.isoformat()) and (en is None or r['at'] < en.isoformat()): want[r['member_id']] = want.get(r['member_id'], D(0)) + D(r['usd'])
    t(f'{k}: each member\'s cost is the sum of its cost records in the period', all(D(M['members'][mid]['costs'][k]['usd']) == want.get(mid, D(0)) for mid in M['members']))
t('the team cost per job is the jobs\' cost over the number of jobs', M['jobs']['all'] == 2 and M['per_job']['all']['usd'] > 0)
t('the average per job over 12 months matches the card\'s "AI per job"',
  all(M['members'][mid]['per_job']['12m'] == card[mid]['per_job'] for mid in M['members']))
with s.db() as c:
    runs = c.execute("SELECT coalesce(sum(cost_usd),0) FROM agent_runs WHERE agent_id IN ('team-member','team-talk')").fetchone()[0]
    usage = c.execute("SELECT coalesce(sum(estimate_usd),0) FROM model_usage WHERE workload LIKE 'Digital team:%' OR workload LIKE '%Talk%'").fetchone()[0]
all_sum = sum((D(m['costs']['all']['usd']) for m in M['members'].values()), D(0)) + D(M['former']['all']['usd'])
t('since tracking began, the members add up to the team total', abs(all_sum - D(M['total']['all']['usd'])) < D('1e-9'))
t('…which is what the Agents page shows for the team\'s runs', abs(D(M['total']['all']['usd']) - D(runs)) < D('1e-9') and runs > 0)
lead = M['members']['lead-qs']
t('shares are of the team total for the period', abs(sum(m['share_pct']['all'] or 0 for m in M['members'].values()) - 100) < 0.5
  and lead['share_pct']['all'] == float((D(lead['costs']['all']['usd']) / D(M['total']['all']['usd']) * 100).quantize(Decimal('0.1'))))
t('jobs and the average per job are counted per period (two jobs; the lead also talked)', lead['jobs']['7d'] == 2
  and lead['per_job']['7d'] == team_costs.money(D(lead['costs']['7d']['usd']) / 2, M['fx']))
t('the trend is 12 weeks, and holds this week\'s cost', len(lead['trend']) == 12 and abs(sum(D(x['usd']) for x in lead['trend']) - D(lead['costs']['all']['usd'])) < D('1e-9'))
cs = M['members']['cost-surveyor']
t('the last jobs, newest first, with what each cost (the lead talked about the first job last)', [x['job_id'] for x in cs['last_jobs']] == [j2['id'], j1['id']]
  and [x['job_id'] for x in lead['last_jobs']] == [j1['id'], j2['id']] and all(x['ref'] and x['cost']['text'] for x in cs['last_jobs']))
P = page()
t('the team page carries the member figures, the flow, warnings and the previous version', P['member_costs']['members'].keys() == M['members'].keys()
  and P['member_view']['lead-qs']['to'] == ['measurement-surveyor', 'market-trends-qs'] and P['member_view']['cost-surveyor']['from'] == ['measurement-surveyor']
  and 'member_templates' in P and P['previous']['version'] == P['team']['version'] - 1)
team_costs.set_fx(0.8)
P = page()
t('in pounds at the rate you set, with the rate and date for hover', P['member_costs']['members']['lead-qs']['costs']['all']['text'].startswith('£')
  and P['member_costs']['members']['lead-qs']['costs']['all']['note'].startswith('at $1 = £0.8, set '))
team_costs.set_fx(None)
t('…or in dollars, saying so, when no rate is set', page()['member_costs']['members']['lead-qs']['costs']['all']['text'].startswith('$'))
with s.db() as c: c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),))
ps = {p['key']: p['since'] for p in team_costs.members(TID)['periods']}
t('a period that starts before tracking says "since <date>"; All time says when tracking began', ps['7d'].startswith('since ') and ps['12m'].startswith('since ')
  and ps['all'].startswith('tracked since '))
t('the editor and the card show each model\'s tier', page()['model_tiers'] == {'openai': 'Standard', 'claude': 'Light', 'claude_sonnet': 'Standard',
                                                                              'claude_opus': 'Premium', 'openai_astra': 'Premium'})

# ---------------- the Members tab's periods at their boundaries (calendar months, UTC) ----------------
pt = teams.create('Member periods team', 'Periods only.', members=[{'id': 'm1', 'role': 'Analyst'}, {'id': 'm2', 'role': 'Reviewer'}])
PT_ = pt['id']
NOW2 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
SEC = timedelta(seconds=1)
W = {k: (st, en) for k, _, st, en in team_costs.member_periods(NOW2)}
t('this month starts on the 1st; last month is the whole of September; 7 days and 12 months roll back',
  W['month'] == (datetime(2026, 10, 1, tzinfo=timezone.utc), None) and W['last_month'] == (datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc))
  and W['7d'][0] == NOW2 - timedelta(days=7) and W['12m'][0] == datetime(2025, 10, 10, 12, tzinfo=timezone.utc) and W['all'] == (None, None))
t('in January, last month is the previous December', [x[2:] for x in team_costs.member_periods(datetime(2027, 1, 5, tzinfo=timezone.utc)) if x[0] == 'last_month'][0]
  == (datetime(2026, 12, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)))
with s.db() as c:
    c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((NOW2 - timedelta(days=800)).isoformat(),))
    for at, mid, usd, jid in [(W['month'][0], 'm1', 1.00, 'ja'), (W['month'][0] - SEC, 'm1', 2.00, 'jb'), (W['last_month'][0], 'm2', 4.00, 'jb'),
                              (W['last_month'][0] - SEC, 'm2', 8.00, 'jc'), (W['7d'][0], 'm1', 16.00, 'ja'), (W['12m'][0] - SEC, 'm2', 32.00, 'jd'),
                              (NOW2 + SEC, 'm1', 1000.0, 'ja')]:
        c.execute('INSERT INTO team_costs(at,team_id,member_id,role,job_id,job_version,usd) VALUES (?,?,?,?,?,?,?)',
                  (at.isoformat(), PT_, mid, {'m1': 'Analyst', 'm2': 'Reviewer'}[mid], jid, 1, usd))
M2 = team_costs.members(PT_, now=NOW2)
u2 = lambda k: M2['total'][k]['usd']
t('a cost exactly at a period\'s start counts, one a second earlier does not, and last month stops at the 1st of this month',
  u2('month') == 1 + 16 and u2('last_month') == 2 + 4 and u2('7d') == 16 and u2('12m') == 1 + 2 + 4 + 8 + 16 and u2('all') == 1 + 2 + 4 + 8 + 16 + 32)
t('…nothing after "now" counts, and members add up to the team in every period', all(
  sum(D(m['costs'][k]['usd']) for m in M2['members'].values()) == D(M2['total'][k]['usd']) for k in ('7d', 'month', 'last_month', '12m', 'all')))
t('jobs worked and the cost per job per period, member and team', M2['members']['m1']['jobs']['month'] == 1 and M2['members']['m2']['jobs']['last_month'] == 1
  and M2['jobs']['last_month'] == 1 and M2['per_job']['last_month']['usd'] == 6.0 and M2['jobs']['all'] == 4 and M2['per_job']['all']['usd'] == 63 / 4)
with s.db() as c: c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((NOW2 - timedelta(days=5)).isoformat(),))
lm = {p['key']: p['since'] for p in team_costs.members(PT_, now=NOW2)['periods']}
t('a month wholly before tracking began says nothing was tracked', lm['last_month'].startswith('before tracking began') and lm['month'].startswith('since '))

# ---------------- the editor: one save, one new version ----------------
v0 = teams.get(TID)['version']
r = cl.put(f'/admin/api/teams/{TID}/members/measurement-surveyor', headers=H, json={
    'role': 'Measurement Surveyor', 'purpose': 'Measures.', 'instructions': 'Take off quantities, each with its source.', 'provider': 'claude_sonnet',
    'categories': [], 'packs': [], 'tools': {'web_search': False}})
v1 = teams.get(TID)['version']
t('saving the editor makes exactly one new team version, saying what changed', r.status_code == 200 and v1 == v0 + 1
  and 'purpose' in teams.versions(TID)[0]['what'] and 'instructions' in teams.versions(TID)[0]['what'])
P = page()
t('…and the editor compares with the version before', P['previous']['version'] == v0 and P['previous']['members']['measurement-surveyor']['instructions'] != 'Take off quantities, each with its source.')
t('saving nothing changed makes no version', cl.put(f'/admin/api/teams/{TID}/members/measurement-surveyor', headers=H, json={'purpose': 'Measures.'}).status_code == 200
  and teams.get(TID)['version'] == v1)
t('secrets in instructions are refused, and nothing is saved', cl.put(f'/admin/api/teams/{TID}/members/measurement-surveyor', headers=H,
  json={'instructions': 'Use the key sk-ant-api03-' + 'A' * 40}).status_code == 400 and teams.get(TID)['version'] == v1)

# ---------------- hand-off order ----------------
qs_stages = [s_['key'] for s_ in teams.get(TID)['job_types'][0]['stages']]
order = ['lead-qs', 'cost-surveyor', 'measurement-surveyor', 'market-trends-qs']
r = cl.put(f'/admin/api/teams/{TID}/member-order', headers=H, json={'order': order})
T = teams.get(TID)
t('the order is saved as a new team version', r.status_code == 200 and [m['id'] for m in T['members']] == order and T['version'] == v1 + 1
  and teams.versions(TID)[0]['what'].startswith('Hand-off order: Lead QS → Cost Surveyor'))
t('…but a job type with built-in steps keeps its stage order', [s_['key'] for s_ in T['job_types'][0]['stages']] == qs_stages)
t('the same order again makes no version', cl.put(f'/admin/api/teams/{TID}/member-order', headers=H, json={'order': order}).status_code == 200 and teams.get(TID)['version'] == T['version'])
t('an order that misses or repeats a member is refused', cl.put(f'/admin/api/teams/{TID}/member-order', headers=H, json={'order': order[:3]}).status_code == 400
  and cl.put(f'/admin/api/teams/{TID}/member-order', headers=H, json={'order': order[:3] + ['lead-qs']}).status_code == 400)
gen = teams.create('Generic order team', members=[{'id': 'a', 'role': 'Drafter'}, {'id': 'b', 'role': 'Checker'}, {'id': 'c', 'role': 'Editor'}],
                   job_types=[{'id': 'jt', 'name': 'Draft', 'stages': [{'key': 's1', 'title': 'Draft', 'member': 'a'}, {'key': 's2', 'title': 'Check', 'member': 'b'},
                                                                       {'key': 's3', 'title': 'Edit', 'member': 'c'}]}])
g = teams.reorder_members(gen['id'], ['b', 'a', 'c'])
t('in a job type of your own steps, the stages follow the new order (and the lead with them)', [s_['member'] for s_ in g['job_types'][0]['stages']] == ['b', 'a', 'c']
  and teams.lead_id(g) == 'b' and 'stages of Draft follow it' in teams.versions(gen['id'])[0]['what'])
t('the page says which job types follow the order', cl.get(f'/admin/api/teams/{gen["id"]}/page').json()['reorderable'] == ['Draft'] and page()['reorderable'] == [])
t('reordering needs Manage on the team', permissions.ROUTES.get('PUT /admin/api/teams/{tid}/member-order') == 'team:manage')

# ---------------- warnings ----------------
def warns(mid, kind=None):
    w = page()['member_view'][mid]['warnings']
    return [x for x in w if kind is None or x['kind'] == kind]


t('no knowledge: the categories ticked do not exist yet, so it is warned', any('do not exist yet' in x['text'] or 'does not exist yet' in x['text'] for x in warns('cost-surveyor', 'knowledge'))
  and warns('lead-qs', 'knowledge')[0]['text'].startswith('No knowledge ticked'))
s.create_category('Quantity surveying', 'Fictional test category.')
t('…and the warning goes once the category exists', not warns('cost-surveyor', 'knowledge'))
t('a pricing role with web search on: no pricing warning', not warns('cost-surveyor', 'pricing'))
teams.update_member(TID, 'cost-surveyor', {'tools': {'web_search': False}})
w = warns('cost-surveyor', 'pricing')
t('pricing with neither web search nor a rate library is warned, saying why', len(w) == 1 and 'web search is switched off' in w[0]['text']
  and 'no rate library yet' in w[0]['text'])
cl.post(f'/admin/api/teams/{TID}/rates/demo', json={}, headers=H)
t('…and not once the rate library has rates', not warns('cost-surveyor', 'pricing'))
rules_engine.update_rule('rate_sources', new_params={'order': list(rules_engine.RATE_SOURCES), 'allowed': ['published', 'built_up']})
w = warns('cost-surveyor', 'pricing')
t('…but again when the rule does not allow the rate library (read from the rule)', len(w) == 1 and 'does not allow the rate library' in w[0]['text'] and w[0]['href'].startswith('/admin/rules'))
w = warns('cost-surveyor', 'instructions')
t('instructions asking for what the rules or tools do not allow are warned', any('the rate library' in x['text'] and 'does not allow' in x['text'] for x in w)
  and any('searching the web' in x['text'] and 'switched off' in x['text'] for x in w))
rules_engine.update_rule('rate_sources', enabled=False)
t('the rule switched off allows every source, so those warnings go', not warns('cost-surveyor', 'pricing')
  and not any('does not allow' in x['text'] for x in warns('cost-surveyor', 'instructions')))
rules_engine.update_rule('rate_sources', enabled=True, new_params={'order': list(rules_engine.RATE_SOURCES), 'allowed': list(rules_engine.RATE_SOURCES_DEFAULT_ALLOWED)})
teams.update_member(TID, 'cost-surveyor', {'tools': {'web_search': True}, 'instructions': 'Do not search the web for anything. Estimate the rates yourself.'})
w = warns('cost-surveyor', 'instructions')
t('"do not search the web" is not a request; estimating rates the rule does not allow is', not any('searching the web' in x['text'] for x in w)
  and any('estimating rates' in x['text'] for x in w))
rules_engine.update_rule('rate_sources', new_params={'order': list(rules_engine.RATE_SOURCES), 'allowed': ['published', 'library', 'estimate']})
t('…and is fine once the rule allows estimates', not warns('cost-surveyor', 'instructions'))
t('a non-pricing role is not warned about rate sources', not any(x['kind'] == 'instructions' for x in warns('lead-qs')))
teams.update_member(TID, 'cost-surveyor', {'provider': 'claude'})
teams.update_member(TID, 'measurement-surveyor', {'provider': 'claude'})
teams.update_member(TID, 'lead-qs', {'provider': 'claude'})
w1, w2 = warns('cost-surveyor', 'model'), warns('measurement-surveyor', 'model')
t('web search and long structured lists on Haiku are warned', len(w1) == 1 and 'searches the web and returns long structured lists' in w1[0]['text']
  and 'Haiku' in w1[0]['text'] and len(w2) == 1 and 'returns long structured lists' in w2[0]['text'] and 'searches' not in w2[0]['text'])
t('…but not a member doing neither (the lead planning on Haiku)', not warns('lead-qs', 'model'))
teams.update_member(TID, 'cost-surveyor', {'provider': 'claude_sonnet'})
t('…and the warning goes on Sonnet', not warns('cost-surveyor', 'model'))
lr = page()['member_view']['cost-surveyor']['last_run']
t('each member\'s last run: when, on which job, and how it ended', lr and lr['job_id'] == j2['id'] and lr['status'] == 'done' and lr['label'] == 'Done')

# ---------------- add and remove ----------------
r = cl.post(f'/admin/api/teams/{TID}/members', headers=H, json={'template': 'researcher', 'role': 'Planning Researcher'})
new = next(m for m in r.json()['members'] if m['role'] == 'Planning Researcher')
t('Add a member from a template: its starting purpose, instructions and tools, with your changes', r.status_code == 200
  and new['tools'] == {'web_search': True} and new['instructions'].startswith('Search the web') and new['provider'] == 'claude_sonnet')
t('a blank member needs a role name', cl.post(f'/admin/api/teams/{TID}/members', headers=H, json={'template': 'blank', 'role': ''}).status_code == 400)
t('the templates offered: Estimator, Checker, Researcher and blank', [v['label'] for v in page()['member_templates'].values()] == ['Estimator', 'Checker', 'Researcher', 'Blank'])
cur = teams.get(TID)['version']
with s.db() as c:
    c.execute("INSERT INTO team_jobs(id,team_id,job_type,team_version,title,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
              ('f' * 32, TID, 'cost-estimate', cur, 'FICTIONAL running job', 'running', s.now(), s.now()))
r = cl.delete(f'/admin/api/teams/{TID}/members/{new["id"]}', headers=H)
t('removing a member is refused while a job is running on the current version', r.status_code == 400 and 'running on this version' in r.json()['detail']
  and any(m['id'] == new['id'] for m in teams.get(TID)['members']))
with s.db() as c: c.execute("UPDATE team_jobs SET team_version=? WHERE id=?", (cur - 1, 'f' * 32))
r = cl.delete(f'/admin/api/teams/{TID}/members/{new["id"]}', headers=H)
t('a job running on an earlier version does not stop it (that job keeps its version)', r.status_code == 200
  and not any(m['id'] == new['id'] for m in teams.get(TID)['members']) and any(m['role'] == 'Planning Researcher' for m in teams.get(TID, cur)['members']))
t('a member who works on a stage still cannot be removed', cl.delete(f'/admin/api/teams/{TID}/members/cost-surveyor', headers=H).status_code == 400)

# ---------------- the page ----------------
html = cl.get(f'/admin/teams/{TID}').text
t('the Members tab: period switcher, card grid in hand-off order, editor in the side panel, drag and keyboard reorder, Add a member',
  all(x in html for x in ("store.get('member-period','month')", "class:'tm-mgrid'", 'function openMember(', "wide:true", 'draggable', 'function moveKey(',
                          "'/member-order'", 'function addCard(', 'function wordDiff(')))
t('the side panel goes full screen on a phone', 'ic-drawer.ic-wide{top:0;width:100vw' in html)
