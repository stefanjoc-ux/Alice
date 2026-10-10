"""Digital teams: what they cost, re-pricing and job versions (Stefan, 8 Oct 2026).

Every model call made for a team job is recorded against the team, the member, the job and the job version, from the same figure as
Usage and the agent run; periods, the run rate (an Estimate), pounds only at the rate Stefan set, his own comparison figures only when
entered; Re-price and Re-measure as new versions that touch only the chosen items or elements; Copy as a new job under client
separation; Ask Temple's figures; the demo Alice's own figures; the connector wording. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import app, substrate_store as s, assistants, org_research, rules_engine, usage_meter, agents, clients
import teams, team_qs, team_costs, temple_ask
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False

team = teams.from_template('quantity-surveying', name='Costs test team')
TID = team['id']
teams.set_autonomy(TID, 'signoff')
DOC = 'FICTIONAL hall spec.md'
PLAN = {'plan': 'Measure from the specification.', 'elements': [{'name': 'Walls', 'documents': [DOC]}, {'name': 'Roof', 'documents': [DOC]}],
        'documents': [{'name': DOC, 'use': 'all'}], 'location': '', 'summary': 'Planned.', 'note': 'Go.', 'questions': []}
WALLS = [{'element': 'Walls', 'description': f'Wall item {n}', 'quantity': 10 * n, 'unit': 'm2', 'source': {'document': DOC, 'page': '1'}} for n in range(1, 5)]
ROOF = [{'element': 'Roof', 'description': 'Roof covering', 'quantity': 120, 'unit': 'm2', 'source': {'document': DOC, 'page': '2'}}]
CALLS, SEARCHES = [], []
STATE = {'measure': []}
USAGE = SimpleNamespace(usage={'input_tokens': 10000, 'output_tokens': 1000})        # Sonnet: $0.02 in + $0.01 out = $0.03 a call


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    payload = messages[0]['content']
    CALLS.append({'workload': workload, 'payload': payload, 'system': system})
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)              # the real ledger path: Usage, the agent run, the team
    if 'Lead QS' in workload and 'message_from_stefan' in payload:
        return json.dumps({'reply': 'Noted.', 'route_to': '', 'note_for_member': '', 'not_allowed': []})
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in payload:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload and 'SUGGESTED MARKET ADJUSTMENT' in payload:
        return json.dumps({'accept': False, 'reason': 'Not convinced.', 'summary': 'Rejected.'})
    if 'Lead QS' in workload: return json.dumps(PLAN)
    if 'Measurement' in workload:
        if STATE['measure']: return json.dumps(STATE['measure'].pop(0))
        mine = [x for x in WALLS + ROOF if x['element'] in payload.split('THIS PART: take off ONLY these elements:')[1].split('from the DOCUMENTS')[0]]
        return json.dumps({'accept': True, 'items': mine, 'summary': '', 'note': 'Price these.'})
    if 'Market Trends' in workload: return json.dumps({'matches': [], 'commentary': 'Nothing to compare.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


PAGES = {'https://fictional-prices.example/q1': 'Wall item 1 prices', 'https://fictional-prices.example/roof': 'Roof prices',
         'https://fictional-prices.example/similar': 'A similar hall'}
RATES = {'Wall item 1': 50, 'Roof covering': 40}


def fake_ask(prompt, query, provider, workload='', **kw):
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    if 'MEASURED ITEMS' not in query:                        # Market Trends' own search
        SEARCHES.append({'refs': [], 'kind': 'market', 'query': query})
        return json.dumps({'findings': [], 'commentary': 'No market evidence.'}), {}
    rows = re.findall(r'^(Q\d+) \| [^|]+ \| ([^|]+?) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    SEARCHES.append({'refs': [r for r, _ in rows], 'kind': 'price', 'query': query})
    out = []
    for ref, desc in rows:
        if desc in RATES:
            out.append({'ref': ref, 'source': 'published', 'rate': RATES[desc], 'unit': 'm2',
                        'source_url': 'https://fictional-prices.example/q1' if desc.startswith('Wall') else 'https://fictional-prices.example/roof', 'source_date': '2026-06'})
        elif 'ESTIMATE ALLOWED' in query.split(ref + ' |')[1].split('\n')[0]:
            out.append({'ref': ref, 'source': 'estimate', 'estimate': {'rate': 85, 'reasoning': 'Similar walls cost about £85 per m2.', 'assumptions': ['3 m high'],
                                                                       'comparables': [{'rate': 82, 'unit': 'm2', 'source_url': 'https://fictional-prices.example/similar', 'source_date': '2026-03'}]}})
    return json.dumps({'rates': out, 'searches': ['wall rates']}), dict(PAGES)


assistants._call = fake_call
org_research._ask = fake_ask


def start(title='FICTIONAL costs job', client=''):
    body = {'job_type': 'cost-estimate', 'title': title, 'brief': 'A fictional single-storey hall for a community trust, to be estimated.', 'client': client,
            'uploads': [{'name': DOC, 'kind': 'spec', 'text': 'FICTIONAL specification. Page 1: walls. Page 2: roof.'}]}
    r = cl.post(f'/admin/api/teams/{TID}/jobs', json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def items_of(j): return {i['ref']: i for i in teams._row(j['id'])['outputs']['price']['items']}


def rows(where='', args=()):
    with s.db() as c: return [dict(r) for r in c.execute('SELECT * FROM team_costs' + where, args)]


D = lambda x: Decimal(str(x))

# ---------------- attribution ----------------
j = start()
t('the job runs to sign-off', j['status'] == 'waiting' and j['pending'][0]['kind'] == 'signoff')
R = rows(' WHERE job_id=?', (j['id'],))
members = {r['member_id'] for r in R}
t('every call for the job is recorded against the team, the member (role), the job and version 1',
  R and all(r['team_id'] == TID and r['job_id'] == j['id'] and r['job_version'] == 1 and r['role'] and r['agent_id'] == 'team-member' for r in R)
  and members == {'lead-qs', 'measurement-surveyor', 'cost-surveyor', 'market-trends-qs'})
t('…each from the same figure as the Usage ledger ($0.03 a call here)', all(abs(r['usd'] - 0.03) < 1e-9 for r in R) and len(R) == len(CALLS) + len(SEARCHES))
with s.db() as c:
    runs = {r['id']: r['cost_usd'] for r in c.execute("SELECT id, cost_usd FROM agent_runs WHERE agent_id='team-member'")}
    usage = c.execute("SELECT coalesce(sum(estimate_usd),0) FROM model_usage WHERE workload LIKE 'Digital team:%'").fetchone()[0]
by_run = {}
for r in R: by_run[r['run_id']] = by_run.get(r['run_id'], D(0)) + D(r['usd'])
t('each agent run\'s cost on the Agents page is exactly the sum of its recorded calls', by_run and all(abs(D(runs[k]) - v) < D('1e-9') for k, v in by_run.items()))
C = team_costs.team(TID)
CALLS_AT_C = len(CALLS) + len(SEARCHES)            # each later call or search adds $0.03 to the team's figures
tot30 = D(C['total']['30d']['usd'])
t('the team total is the sum of its members', tot30 == sum((D(m['costs']['30d']['usd']) for m in C['members']), D(0)))
t('…and matches the Agents page and Usage', abs(tot30 - sum((D(v) for v in runs.values()), D(0))) < D('1e-9') and abs(tot30 - D(usage)) < D('1e-9'))
J = team_costs.job(j['id'])
t('the job\'s total equals its AI cost, with each member\'s share', abs(D(J['total']['usd']) - D(teams._row(j['id'])['ai_cost'])) < D('1e-9')
  and abs(sum(m['share_pct'] for m in J['members']) - 100) < 0.5 and J['versions'][1]['usd'] == J['total']['usd'])

# Talk to the team: the lead's call, against the job
cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'How is it going?', 'job': j['id']}, headers=H)
tk = rows(" WHERE kind='talk'")
t('Talk to the team is recorded against the lead, the job and its version', len(tk) == 1 and tk[0]['member_id'] == 'lead-qs' and tk[0]['job_id'] == j['id']
  and tk[0]['agent_id'] == 'team-talk' and tk[0]['job_version'] == 1)

# ---------------- periods at the boundaries, before tracking, run rate ----------------
other = teams.create('Period test team', 'Periods only.', members=[{'id': 'm1', 'role': 'Analyst'}, {'id': 'm2', 'role': 'Reviewer'}])
OT = other['id']
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
SEC = timedelta(seconds=1)
P = {k: st for k, _, st in team_costs.periods(NOW)}
t('periods: 7 and 30 days back, the calendar quarter, 12 months back', P['7d'] == NOW - timedelta(days=7) and P['30d'] == NOW - timedelta(days=30)
  and P['quarter'] == datetime(2026, 10, 1, tzinfo=timezone.utc) and P['12m'] == datetime(2025, 10, 8, 12, tzinfo=timezone.utc))
with s.db() as c:
    c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((NOW - timedelta(days=400)).isoformat(),))
    for at, mid, usd in [(P['7d'], 'm1', 1.00), (P['7d'] - SEC, 'm1', 2.00), (P['30d'], 'm2', 4.00), (P['30d'] - SEC, 'm2', 8.00),
                         (P['quarter'], 'm1', 16.00), (P['quarter'] - SEC, 'm1', 32.00), (P['12m'], 'm2', 64.00), (P['12m'] - SEC, 'm2', 128.00),
                         (NOW + SEC, 'm1', 1000.0)]:
        c.execute('INSERT INTO team_costs(at,team_id,member_id,role,job_id,job_version,usd) VALUES (?,?,?,?,?,?,?)',
                  (at.isoformat(), OT, mid, {'m1': 'Analyst', 'm2': 'Reviewer'}[mid], 'job-x', 1, usd))
C2 = team_costs.team(OT, now=NOW)
u = lambda k: C2['total'][k]['usd']
# 7d from 1 Oct 12:00, the quarter from 1 Oct 00:00, 30d from 8 Sep 12:00, 12m from 8 Oct 2025 12:00
t('a cost exactly at a period\'s start counts; a second earlier does not', u('7d') == 1.0 and u('30d') == 1 + 2 + 4 + 16 + 32 and u('quarter') == 1 + 2 + 16
  and u('12m') == 1 + 2 + 4 + 8 + 16 + 32 + 64)
t('…and nothing after "now" is counted', 1000.0 not in [m['costs']['7d']['usd'] for m in C2['members']])
byrole = {m['role']: m for m in C2['members']}
t('members add up to the team in every period', all(sum(D(m['costs'][k]['usd']) for m in C2['members']) == D(C2['total'][k]['usd']) for k in ('7d', '30d', 'quarter', '12m'))
  and byrole['Reviewer']['costs']['12m']['usd'] == 4 + 8 + 64)
t('the annual run rate is from the last 30 days and labelled Estimate', C2['run_rate']['label'] == 'Estimate'
  and abs(C2['run_rate']['value']['usd'] - 55 * 365 / 30) < 1e-9 and C2['run_rate']['basis'] == 'from the last 30 days')
t('no period says "since" when tracking began before all of them', not any(p['since'] for p in C2['periods']))
with s.db() as c:
    c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((NOW - timedelta(days=10)).isoformat(),))
    c.execute("INSERT INTO team_jobs(id,team_id,job_type,team_version,title,status,created_at,updated_at) VALUES ('oldjob1',?,?,1,'Old job','done',?,?)",
              (OT, 'x', (NOW - timedelta(days=20)).isoformat(), (NOW - timedelta(days=20)).isoformat()))
    c.execute("INSERT INTO team_steps(id,job_id,seq,kind,member,status,cost_usd,created_at) VALUES ('oldstep1','oldjob1',1,'turn','m1','done',1.25,?)",
              ((NOW - timedelta(days=20)).isoformat(),))
C3 = team_costs.team(OT, now=NOW)
since = {p['key']: p['since'] for p in C3['periods']}
t('a period that began before tracking says "since <date>"', since['7d'] == since['quarter'] == '' and since['30d'] == since['12m'] == 'since 28 Sep 2026')
t('costs from before tracking began are one figure, never split or guessed', C3['before_tracking']['usd'] == 1.25 and 'Before tracking began' in C3['before_text']
  and all(m['costs']['12m']['usd'] == byrole[m['role']]['costs']['12m']['usd'] for m in C3['members']))
t('with 10 days tracked, the run rate is worked from those days, still an Estimate', abs(C3['run_rate']['value']['usd'] - 55 * 365 / 10) < 1e-6
  and '10 days tracked' in C3['run_rate']['basis'])
with s.db() as c: c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((NOW - timedelta(days=3)).isoformat(),))
C4 = team_costs.team(OT, now=NOW)
t('with under a week tracked, no run rate is invented', C4['run_rate']['value'] is None and '7 days' in C4['run_rate']['basis'])
with s.db() as c: c.execute("UPDATE settings SET value=? WHERE key='team_costs_since'", ((NOW - timedelta(days=400)).isoformat(),))

# ---------------- pounds only at the rate Stefan set ----------------
t('no rate set: figures in US dollars, and it says so', C['fx']['rate'] is None and C['total']['30d']['text'].startswith('$')
  and C['fx']['note'] == 'in US dollars: no exchange rate set' and C['total']['30d']['gbp'] is None)
r = cl.put('/admin/api/teams/costs/rate', json={'rate': 0.8}, headers=H)
f = r.json()
t('a rate you set shows pounds, with the rate and the date beside the figures', r.status_code == 200 and f['rate'] == 0.8
  and re.fullmatch(r'at \$1 = £0\.8, set \d{1,2} [A-Z][a-z]{2} \d{4}', f['note']))
C5 = team_costs.team(OT, now=NOW)
t('…every figure converted in code to the penny', C5['total']['12m']['gbp'] == 101.6 and C5['total']['12m']['text'] == '£101.60'
  and all(m['costs']['7d']['note'] == f['note'] for m in C5['members']))
t('a rate that makes no sense is refused', cl.put('/admin/api/teams/costs/rate', json={'rate': 80}, headers=H).status_code == 400)
with s.db() as c: logged = c.execute("SELECT count(*) FROM activity WHERE action='team_costs_rate_set'").fetchone()[0]
t('setting the rate is logged', logged == 1)
cl.put('/admin/api/teams/costs/rate', json={'rate': None}, headers=H)
t('clearing it goes back to dollars', team_costs.fx()['rate'] is None and team_costs.money(1.5)['text'] == '$1.50')
t('a cost under a penny says so rather than £0.00', team_costs.money(0.001)['text'] == '<$0.01')

# ---------------- your figures: only when entered ----------------
t('no comparison unless you enter one', not C['staff_on'] and all(m['your_figures'] is None for m in C['members']))
r = cl.put(f'/admin/api/teams/{TID}/staff/cost-surveyor', json={'on': True, 'day_rate': 450, 'days': 2}, headers=H)
C6 = r.json()
cs = next(m for m in C6['members'] if m['id'] == 'cost-surveyor')
t('your day rate and days for a member show beside its AI cost as Your figures', r.status_code == 200 and cs['your_figures']['label'] == 'Your figures'
  and cs['your_figures']['per_job_gbp'] == 900.0 and '£450.00 a day × 2 days = £900.00 a job' == cs['your_figures']['text']
  and all(m['your_figures'] is None for m in C6['members'] if m['id'] != 'cost-surveyor'))
t('…and say the AI side is in dollars until a rate is set', 'US dollars' in cs['your_figures']['note'])
t('a bad day rate is refused', cl.put(f'/admin/api/teams/{TID}/staff/cost-surveyor', json={'on': True, 'day_rate': -5, 'days': 2}, headers=H).status_code == 400)
jp = cl.get(f'/admin/api/teams/jobs/{j["id"]}/page').json()
t('the job page shows Your figures beside that member\'s share only', [m['role'] for m in jp['costs']['members'] if m['your_figures']] == ['Cost Surveyor'])
# Your figures never reach a model: figures nobody would hit by chance, switched on, then a real model call made while they are
# on (Talk to the team sends the lead the team's context), and every call and search checked for the exact values.
cl.put(f'/admin/api/teams/{TID}/staff/cost-surveyor', json={'on': True, 'day_rate': 437.13, 'days': 3}, headers=H)
FIGURES = ('437.13', '1311.39', '1,311.39')
n_calls = len(CALLS)
r = cl.post(f'/admin/api/teams/{TID}/talk', json={'message': 'What does the Cost Surveyor cost us?', 'job': j['id']}, headers=H)
sent = ' '.join(str(c_['payload']) + ' ' + str(c_['system']) for c_ in CALLS) + ' ' + ' '.join(str(x['query']) for x in SEARCHES)
t('your figures are never sent to a model (a call made while they are on carries none of them)',
  team_costs.staff(TID).get('cost-surveyor', {}).get('day_rate') == 437.13 and r.status_code == 200 and len(CALLS) > n_calls
  and not any(f_ in sent for f_ in FIGURES))
cl.put(f'/admin/api/teams/{TID}/staff/cost-surveyor', json={'on': False}, headers=H)
t('switched off again: no comparison', all(m['your_figures'] is None for m in team_costs.team(TID)['members']))

# ---------------- the pages carry the figures ----------------
b = cl.get('/admin/api/teams/board').json()
mine = next(x for x in b['teams'] if x['id'] == TID)
since_c = 0.03 * (len(CALLS) + len(SEARCHES) - CALLS_AT_C)          # Talk to the team twice since C
t('All teams: each team\'s cost for the last 30 days and a total', since_c > 0 and abs(mine['cost']['usd'] - C['total']['30d']['usd'] - since_c) < 1e-9
  and D(b['costs']['total']['usd']) == sum((D(x['cost']['usd']) for x in b['teams']), D(0)) and b['costs']['label'] == 'Last 30 days')
pg = cl.get(f'/admin/api/teams/{TID}/page').json()
t('the team page carries the running cost: members × periods, total, run rate', [p_['key'] for p_ in pg['costs']['periods']] == ['7d', '30d', 'quarter', '12m']
  and pg['costs']['run_rate']['label'] == 'Estimate' and j['id'] in pg['costs']['jobs'])
html = cl.get(f'/admin/teams/{TID}').text
t('the pages draw them (Running cost, Your figures, cost column, sort by cost, Re-price, Re-measure, Copy, versions)',
  all(x in html for x in ("'Running cost'", "'Add your figures'", "'AI cost, 30 days'", 'value="cost"', "'Re-price'", "'Re-measure'", "'Copy as a new job'", "'Versions'")))

# ---------------- Re-price: a new version touching only the chosen items ----------------
v1 = items_of(j)
t('before: Q1 published; Q2–Q4 unpriced (nothing allowed priced them)', v1['Q1']['rate_source'] == 'web' and all(v1[k]['rate_source'] == 'unpriced' for k in ('Q2', 'Q3', 'Q4')))
v1_ids = {r['id'] for r in rows(' WHERE job_id=?', (j['id'],))}
n_measure = sum(1 for c_ in CALLS if 'Measurement' in c_['workload'])
n_trends = sum(1 for x in SEARCHES if x['kind'] == 'market')
SEARCHES.clear()
RATES['Wall item 2'] = 61.5
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/reprice', json={'refs': ['Q2', 'Q3'], 'note': 'Look again for Q2.'}, headers=H)
j2 = r.json()
v2 = items_of(j2)
t('re-pricing runs only the Cost Surveyor, on the chosen items', r.status_code == 200 and [x['refs'] for x in SEARCHES if x['kind'] == 'price'] == [['Q2', 'Q3']]
  and sum(1 for c_ in CALLS if 'Measurement' in c_['workload']) == n_measure and 'Look again for Q2.' in SEARCHES[0]['query'])
t('…keeping the measured quantities and every other item\'s price', all(v2[k]['quantity'] == v1[k]['quantity'] for k in v1) and v2['Q1'] == v1['Q1'] and v2['Q4'] == v1['Q4']
  and v2['Q2']['rate'] == 61.5 and v2['Q2']['rate_source'] == 'web')
t('Market Trends is not run again unless asked; its work is kept', not any(x['kind'] == 'market' for x in SEARCHES)
  and any(s_['kind'] == 'note' and 'not run again' in s_['note'] for s_ in teams._steps(j['id'])))
t('the Lead QS reassembles and it comes back for sign-off as v2', j2['status'] == 'waiting' and j2['pending'][0]['kind'] == 'signoff' and j2['version'] == 2
  and teams._row(j['id'])['outputs']['assemble']['cost_plan']['construction'] == float(D(50) * 10 + D('61.5') * 20 + D(40) * 120))
V = cl.get(f'/admin/api/teams/jobs/{j["id"]}/versions').json()
vs = {x['version']: x for x in V['versions']}
new_rows = [r_ for r_ in rows(' WHERE job_id=?', (j['id'],)) if r_['id'] not in v1_ids]
t('each version records what changed, who asked and the note', vs[2]['kind'] == 'reprice' and 'Q2, Q3' in vs[2]['what'] and vs[2]['note'] == 'Look again for Q2.'
  and vs[2]['asked_by'] and vs[2]['current'] and not vs[1]['current'])
t('the re-run\'s calls are recorded as v2, and each version\'s cost is its own', new_rows and all(r_['job_version'] == 2 for r_ in new_rows)
  and abs(D(vs[2]['cost']['usd']) - sum((D(r_['usd']) for r_ in new_rows), D(0))) < D('1e-9')
  and {r_['member_id'] for r_ in new_rows} == {'cost-surveyor', 'lead-qs'})
ov = cl.get(f'/admin/api/teams/jobs/{j["id"]}/versions/1').json()
t('v1 stays readable: its cost plan as it was', ov['version']['version'] == 1 and {x['ref']: x['source'] for x in ov['plan']['rows']}['Q2'] == 'unpriced'
  and ov['documents'] and ov['plan']['totals']['construction'] == 50 * 10 + 40 * 120 and ov['version']['cost']['usd'] > 0)
t('an unknown version is a 404', cl.get(f'/admin/api/teams/jobs/{j["id"]}/versions/9').status_code == 404)
docs = teams._row(j['id'])['outputs']['documents']
t('v2\'s documents are named after the job and version', all(' v2' in d_['name'] or 'v2' in d_['name'] for d_ in docs))

# sign off v2, then re-price the signed-off job with estimates allowed, a different order and Market Trends again
r = cl.post(f'/admin/api/teams/steps/{j2["pending"][0]["id"]}', json={'action': 'approve'}, headers=H)
t('v2 signed off', r.status_code == 200 and r.json()['status'] == 'done')
SEARCHES.clear()
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/reprice', json={'refs': ['Q4'], 'estimates': True, 'order': ['library', 'published'], 'trends': True}, headers=H)
j3 = r.json()
v3 = items_of(j3)
pq = [x for x in SEARCHES if x['kind'] == 'price']
t('a signed-off job can be re-priced (v3)', r.status_code == 200 and j3['version'] == 3 and j3['status'] == 'waiting')
t('…team estimates allowed for the chosen items on this re-run only', 'ESTIMATE ALLOWED' in pq[0]['query'] and v3['Q4']['rate_source'] == 'estimate' and v3['Q3']['rate_source'] == 'unpriced')
t('…the rate sources in the order asked for this re-run (what is allowed stays the rule\'s)', '1. library: allowed' in pq[0]['query'] and '2. published: allowed' in pq[0]['query']
  and rules_engine.rate_sources()['order'][0] == 'published')
t('…and Market Trends again when asked', any(x['kind'] == 'market' for x in SEARCHES))
V = cl.get(f'/admin/api/teams/jobs/{j["id"]}/versions').json()
vs = {x['version']: x for x in V['versions']}
t('the signed-off version is marked; the others are not', vs[2]['signed_off'] and vs[2]['signed_off_by'] and not vs[1]['signed_off'] and not vs[3]['signed_off'])
t('a bad item is refused', cl.post(f'/admin/api/teams/jobs/{j["id"]}/reprice', json={'refs': ['Q99']}, headers=H).status_code == 400)
teams._ACTIVE.add(j['id'])
t('no re-price while the team is working on the job', cl.post(f'/admin/api/teams/jobs/{j["id"]}/reprice', json={}, headers=H).status_code == 400)
teams._ACTIVE.discard(j['id'])
with s.db() as c: logged = [dict(x) for x in c.execute("SELECT actor, detail FROM activity WHERE action='team_job_reprice'")]
t('each re-run is logged with who asked', len(logged) == 2 and all(x['actor'] for x in logged) and 'v3' in logged[-1]['detail'])

# ---------------- Re-measure: chosen elements only, then only their items priced ----------------
k = start('FICTIONAL re-measure job')
before = items_of(k)
SEARCHES.clear(); n0 = len(CALLS)
ROOF[0] = {**ROOF[0], 'quantity': 150, 'description': 'Roof covering'}
r = cl.post(f'/admin/api/teams/jobs/{k["id"]}/remeasure', json={'elements': ['Roof']}, headers=H)
k2 = r.json()
after = items_of(k2)
mcalls = [c_ for c_ in CALLS[n0:] if 'Measurement' in c_['workload']]
t('only the chosen element is measured again', r.status_code == 200 and len(mcalls) == 1 and 'ONLY these elements: Roof' in mcalls[0]['payload'])
t('the other elements keep their items, refs and prices', all(after[k_] == before[k_] for k_ in before if before[k_]['element'] == 'Walls'))
roof_new = [x for x in after.values() if x['element'] == 'Roof']
t('the element measured again gets new items, and only they are priced', len(roof_new) == 1 and roof_new[0]['quantity'] == 150 and roof_new[0]['ref'] == 'Q6'
  and [x['refs'] for x in SEARCHES if x['kind'] == 'price'] == [['Q6']] and 'Q5' not in after)
t('re-measuring is a new version too', k2['version'] == 2 and k2['status'] == 'waiting')
t('an element not in the plan is refused', cl.post(f'/admin/api/teams/jobs/{k["id"]}/remeasure', json={'elements': ['Basement']}, headers=H).status_code == 400)

# ---------------- Copy as a new job: client separation applies ----------------
clients.create_client('Client Aardvark'); clients.create_client('Client Badger')
a = start('FICTIONAL client job', client='Client Aardvark')
t('a job for a client', a['client'] == 'Client Aardvark')
n_plan = sum(1 for c_ in CALLS if 'Lead QS' in c_['workload'] and 'COST PLAN' not in c_['payload'] and 'SUGGESTED' not in c_['payload'] and 'message_from_stefan' not in c_['payload'])
r = cl.post(f'/admin/api/teams/jobs/{a["id"]}/copy', json={'client': 'Client Badger'}, headers=H)
t('copying a client\'s job for another client is refused by the rule, and logged', r.status_code == 400 and 'Client Aardvark' in r.json()['detail']
  and 'Client-facing documents' in r.json()['detail'])
with s.db() as c: blk = c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked' AND rule='client_documents' AND target LIKE 'Digital team: copy%'").fetchone()[0]
t('…as a block under that rule', blk == 1)
r = cl.post(f'/admin/api/teams/jobs/{a["id"]}/copy', json={'client': 'Client Aardvark', 'title': 'FICTIONAL client job, phase 2'}, headers=H)
cp = r.json()
n_plan2 = sum(1 for c_ in CALLS if 'Lead QS' in c_['workload'] and 'COST PLAN' not in c_['payload'] and 'SUGGESTED' not in c_['payload'] and 'message_from_stefan' not in c_['payload'])
t('for the same client it is copied: documents, plan and settings kept', r.status_code == 200 and cp['client'] == 'Client Aardvark'
  and [d_['name'] for d_ in cp['documents']] == [DOC] and cp['team_version'] == a['team_version'] and cp['job_type'] == a['job_type'] and cp['id'] != a['id']
  and cp['title'] == 'FICTIONAL client job, phase 2')
t('…the plan is not made again (it starts at measuring)', n_plan2 == n_plan and teams._row(cp['id'])['outputs']['plan'] == teams._row(a['id'])['outputs']['plan'])
g = start('FICTIONAL general job')
t('a job with no client may be copied for any client', cl.post(f'/admin/api/teams/jobs/{g["id"]}/copy', json={'client': 'Client Badger'}, headers=H).status_code == 200)
with s.db() as c: c.execute("UPDATE team_job_docs SET text=text || ' Prepared for Client Aardvark.' WHERE job_id=?", (g['id'],))
r = cl.post(f'/admin/api/teams/jobs/{g["id"]}/copy', json={'client': 'Client Badger'}, headers=H)
t('…unless its documents name another client', r.status_code == 400 and 'Client Aardvark' in r.json()['detail'])
rules_engine.update_rule('client_documents', enabled=False)
t('with the rule switched off on the Rules page, the copy is allowed', cl.post(f'/admin/api/teams/jobs/{a["id"]}/copy', json={'client': 'Client Badger'}, headers=H).status_code == 200)
rules_engine.update_rule('client_documents', enabled=True)

# ---------------- Ask Temple: the same figures and labels ----------------
x = temple_ask.run_tool('team_costs', {'team': 'Period test team'})
C7 = team_costs.team(OT)
t('Ask Temple gets the team\'s figures with the same labels', x['team'] == 'Period test team' and x['team_total']['Last 7 days'] == C7['total']['7d']['text']
  and x['annual_run_rate']['Estimate'] == C7['run_rate']['value']['text'] and x['currency_note'] == C7['fx']['note'])
x = temple_ask.run_tool('team_costs', {'job': teams.ref(j['id'])})
t('…and a job\'s total, shares and versions', x['total'] == team_costs.job(j['id'])['total']['text'] and set(x['versions']) == {'v1', 'v2', 'v3'})
x = temple_ask.run_tool('team_costs', {})
t('…and every team over the last 30 days', 'Last 30 days' in x['period'] and {y['team'] for y in x['teams']} >= {'Costs test team'})
t('Ask Temple offers the tool', any(tool['name'] == 'team_costs' for tool in temple_ask.TOOLS))

# ---------------- the demo Alice shows only its own figures ----------------
demo_dir = tempfile.mkdtemp(prefix='alice-test-demo-')
code = ('import os, sys, json; sys.path.insert(0, os.getcwd()); import teams, team_costs, agents\n'
        't = teams.create("Demo team", "Demo.", members=[{"id": "d1", "role": "Demo member"}])\n'
        'with team_costs.scope(t["id"], "d1", "Demo member", "", 0): agents.add_cost(0.42, "claude", "claude-sonnet-5-5")\n'
        'b = team_costs.board([x["id"] for x in teams.listing()])\n'
        'print(json.dumps({"total": b["total"]["usd"], "teams": sorted(x["name"] for x in teams.listing())}))\n')
env = {**os.environ, 'AISUBSTRATE_DATA_DIR': demo_dir, 'ALICE_DEMO_INSTANCE': '1'}
env.pop('ALICE_DATABASE_URL', None)
out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=120)
demo = json.loads(out.stdout.strip().splitlines()[-1]) if out.returncode == 0 else {'error': out.stderr[-800:]}
live_total = team_costs.board([x['id'] for x in teams.listing()])['total']['usd']
if 'error' in demo: print(demo['error'])
t('the demo Alice (its own database) shows only its own team costs', demo.get('total') == 0.42 and 'Costs test team' not in demo.get('teams', []))
t('…and none of its costs reach live Alice', 'Demo team' not in [x['name'] for x in teams.listing()] and abs(live_total - 0.42) > 1e-9
  and not rows(" WHERE role='Demo member'"))

# ---------------- the connector's wording ----------------
import mcp_server, copilot_package, asyncio
tools = {x.name: x for x in asyncio.run(mcp_server.mcp.list_tools())}
dd, rd = tools['propose_decision'].description, tools['propose_record'].description
t('propose_decision says how decisions are approved under the current setting (Approval and library management)',
  mcp_server.approval_text('decision') in dd and '{approval' not in dd and 'awaiting their approval' not in dd)
t('propose_record says how memories are approved under the current setting', mcp_server.approval_text('memory') in rd and '{approval' not in rd)
t('the tool names are unchanged', {'propose_record', 'propose_decision'} <= set(tools))
t('the Copilot package version is raised for the new wording', tuple(int(x) for x in copilot_package.VERSION.split('.')) >= (1, 3, 0))
