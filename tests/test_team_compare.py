"""Digital teams: compare a job with a reference cost plan, review the differences, learn from them and benchmark the team (10 Oct 2026).

A FICTIONAL signed-off job is compared with a FICTIONAL reference cost plan (an Excel workbook and a PDF) with known differences: each
is parsed and matched in code (by code, then description and unit), only what code cannot match goes to the lead's model, and every
difference is classed with exact arithmetic. The reference is kept with the job and never given to the team, not even on a benchmark
re-run. Review marks are saved; lessons become knowledge in the team's space; confirmed reference rates join the rate library tagged to
the client; Temple's instruction changes wait until accepted, and later jobs record the version that ran; a benchmark re-run respects
the spending cap, records versions and is compared again; client separation applies to the reference and what comes from it.
Stand-in models only."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, io, json, re
from decimal import Decimal
from types import SimpleNamespace
import app, substrate_store as s, assistants, org_research, usage_meter, rules_engine, knowledge, clients, spaces
import teams, team_qs, team_compare
import _drawings as DR
from fastapi.testclient import TestClient
from openpyxl import Workbook
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False

USAGE = SimpleNamespace(usage={'input_tokens': 10000, 'output_tokens': 1000})
CALLS = []
MARKER = 'External paving'                 # only in the reference: the team never sees it
ITEMS = [('Q1', 'Walls', 'Hall walls, blockwork', 100, 'm2', 50), ('Q2', 'Floor', 'Hall floor screed', 96, 'm2', 30),
         ('Q3', 'Roof', 'Roof covering', 120, 'm2', 80), ('Q4', 'Doors', 'Internal doors', 6, 'nr', 400)]
UNIT = {i[0]: i[4] for i in ITEMS}
RATE = {i[0]: i[5] for i in ITEMS}
STATE = {'match': None, 'lessons': None, 'temple': None}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    content = messages[0]['content']
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    CALLS.append({'workload': workload, 'payload': content, 'system': system, 'provider': provider})
    if '"reference_lines"' in content:
        return json.dumps(STATE['match'] or {'matches': [{'reference': 'R3', 'team': 'Q3', 'why': 'Both are the roof covering.'},
                                                         {'reference': 'R4', 'team': 'Q4', 'why': 'Wrong: different units.'},
                                                         {'reference': 'R99', 'team': 'Q1', 'why': 'No such line.'}]})
    if '"reviewed_differences"' in content:
        return json.dumps(STATE['lessons'] or {'lessons': [{'lesson': 'Check blockwork rates against recent tenders before accepting a published rate.',
                                                            'differences': ['R1', 'R99'], 'member': 'Cost Surveyor'}]})
    if workload == 'Digital team: Temple':
        return json.dumps(STATE['temple'] or {'instructions': 'Price blockwork from at least two recent published sources and say which you used.',
                                              'why': 'The blockwork rate was too high against the reference.', 'cites': ['R1']})
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in content:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload and 'SUGGESTED MARKET ADJUSTMENT' in content:
        return json.dumps({'accept': False, 'reason': 'No.', 'summary': 'Rejected.'})
    if 'Lead QS' in workload:
        return json.dumps({'plan': 'Measure from the schedule.', 'elements': [{'name': e, 'documents': []} for e in ('Walls', 'Floor', 'Roof', 'Doors')],
                           'documents': [{'name': 'FICTIONAL schedule.txt', 'use': 'all'}], 'location': '', 'summary': 'Planned.', 'note': 'Go.', 'questions': []})
    if 'Measurement' in workload:
        part = content.split('THIS PART: take off ONLY these elements:')[1].split('from the DOCUMENTS')[0]
        its = [{'ref': r, 'element': e, 'description': d, 'quantity': q, 'unit': u, 'source': {'document': 'FICTIONAL schedule.txt', 'line': '1'}}
               for r, e, d, q, u, _ in ITEMS if e in part]
        return json.dumps({'accept': True, 'items': its, 'summary': '', 'note': 'Price these.'})
    if 'Market Trends' in workload: return json.dumps({'matches': [], 'commentary': 'Nothing to compare.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


def fake_ask(prompt, query, provider, workload='', **kw):
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    CALLS.append({'workload': workload, 'payload': query, 'system': prompt})
    if 'MEASURED ITEMS' not in query: return json.dumps({'findings': [], 'commentary': 'No market evidence.'}), {}
    refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    return json.dumps({'rates': [{'ref': r, 'source': 'published', 'rate': RATE[r], 'unit': UNIT[r], 'source_url': 'https://fictional-prices.example/q',
                                  'source_date': '2026-06'} for r in refs], 'searches': ['rates']}), {'https://fictional-prices.example/q': 'Prices'}


assistants._call = fake_call
org_research._ask = fake_ask
b64 = lambda raw: base64.b64encode(raw).decode()


def reference_xlsx(name_in_it=''):
    """A FICTIONAL reference cost plan: walls (code Q1, a lower rate), floor (a smaller quantity), roof (worded differently, and its
    stated amount is not quantity x rate), exclusions, preliminaries."""
    wb = Workbook(); ws = wb.active; ws.title = 'Cost plan'
    ws.append(['FICTIONAL reference cost plan' + (f' for {name_in_it}' if name_in_it else '')])
    ws.append(['Ref', 'Description', 'Qty', 'Unit', 'Rate', 'Amount'])
    ws.append([None, 'Walls']); ws.append(['Q1', 'Hall walls, blockwork', 100, 'm2', 45, 4500])
    ws.append([None, 'Floor']); ws.append(['2.1', 'Hall floor screed', 90, 'm2', 30, '=C6*E6'])
    ws.append([None, 'Roof']); ws.append(['3.1', 'Roof covering, profiled sheet', 120, 'm2', 80, 9700])
    ws.append([None, 'Exclusions']); ws.append(['', 'Loose furniture', None, None, 'Excluded', None])
    ws.append(['', 'Preliminaries', None, None, None, 2000])
    out = io.BytesIO(); wb.save(out)
    return out.getvalue()


def reference_pdf():
    return DR.pdf([DR.text(50, 760, 'External works', 11) + '\n' + DR.text(50, 740, f'4.1 {MARKER} 50 m2 60.00 3,000.00')
                   + '\n' + DR.text(50, 700, 'Provisional sums', 11) + '\n' + DR.text(50, 680, 'Provisional sum: drainage connection 5,000.00')])


# ---------------- a FICTIONAL signed-off job ----------------
clients.create_client('Client Aardvark'); clients.create_client('Client Badger')
team = teams.from_template('quantity-surveying', name='Compare test team')
TID = team['id']
teams.set_autonomy(TID, 'signoff')
teams.create_filing_category(TID)


def start(title, client='Client Aardvark'):
    r = cl.post(f'/admin/api/teams/{TID}/jobs', headers=H, json={'job_type': 'cost-estimate', 'title': title, 'client': client,
                'brief': 'A fictional single-storey community hall, to be estimated from the schedule.',
                'uploads': [{'name': 'FICTIONAL schedule.txt', 'kind': 'schedule', 'text': 'Walls 100 m2; floor 96 m2; roof 120 m2; 6 internal doors.'}]})
    assert r.status_code == 200, r.text
    return r.json()


def sign_off(jid):
    so = next(x for x in teams._steps(jid) if x['status'] == 'pending' and x['kind'] == 'signoff')
    r = cl.post(f'/admin/api/teams/steps/{so["id"]}', json={'action': 'approve'}, headers=H)
    assert r.status_code == 200, r.text


j = start('FICTIONAL hall to compare')
JID = j['id']
t('the job is priced and waits for sign-off', j['status'] == 'waiting' and j['pending'][0]['kind'] == 'signoff')
pg = cl.get(f'/admin/api/teams/jobs/{JID}/page').json()
t('before sign-off it cannot be compared yet, and the page says why', pg['compare']['can'] is False and 'signed off or stopped' in pg['compare']['why_not'])
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons', headers=H, json={'uploads': [{'name': 'ref.xlsx', 'data': b64(reference_xlsx())}]})
t('…and a comparison is refused', r.status_code == 400)
sign_off(JID)
t('signed off, it can be compared', cl.get(f'/admin/api/teams/jobs/{JID}/page').json()['compare']['can'] is True)

# ---------------- parsing in code ----------------
lines, how, problem = team_compare._sheet_lines(reference_xlsx(), 'ref.xlsx')
k = {l['description']: l for l in lines}
t('the workbook is read in code into lines with element, quantity, unit, rate and total', len(lines) == 5 and not problem and 'code' in how
  and k['Hall walls, blockwork']['element'] == 'Walls' and k['Hall walls, blockwork']['code'] == 'Q1' and k['Hall walls, blockwork']['rate'] == 45.0)
t('a formula amount is worked out in code (90 x 30 = 2,700)', k['Hall floor screed']['amount'] == 2700.0 and k['Hall floor screed']['arithmetic'] is None)
t('a stated amount that is not quantity x rate is flagged (9,700 against 9,600)', k['Roof covering, profiled sheet']['arithmetic'] == {'stated': 9700.0, 'worked': 9600.0})
t('an exclusion and preliminaries are recognised', k['Loose furniture']['kind'] == 'excluded' and k['Preliminaries']['kind'] == 'addon'
  and k['Preliminaries']['addon'] == 'prelims')
pl, why = team_compare._pdf_lines(reference_pdf(), 'ref.pdf')
t('a PDF is read from its text layer: a measured line and a provisional sum', len(pl) == 2 and pl[0]['description'] == MARKER and pl[0]['quantity'] == 50.0
  and pl[0]['amount'] == 3000.0 and pl[0]['element'] == 'External works' and pl[1]['kind'] == 'ps' and pl[1]['amount'] == 5000.0)

rl = [team_compare._line('', 'Drainage', 'Drainage connection', Decimal('1'), 'item', Decimal('3500'), Decimal('3500'), '', False, False, 'x'),
      team_compare._line('', 'Fit-out', 'Kitchen fit-out', Decimal('1'), 'item', Decimal('2500'), Decimal('2500'), '', False, False, 'x')]
for n_, l_ in enumerate(rl, 1): l_['id'] = f'R{n_}'
tl = [{'ref': 'Q9', 'code': '', 'element': 'Drainage', 'description': 'Drainage connection', 'quantity': 1, 'unit': 'item', 'rate': 4000.0, 'rate_applied': 4000.0,
       'amount': 4000.0, 'kind': 'ps'},
      {'ref': 'Q8', 'code': '', 'element': 'Fit-out', 'description': 'Kitchen fit-out', 'quantity': 1, 'unit': 'item', 'rate': None, 'rate_applied': None,
       'amount': 0.0, 'kind': 'excluded'}]
pr, *_ = team_compare.match_lines(rl, tl)
bd = {d_['id']: d_ for d_ in team_compare.build(rl, tl, {'works': 0, 'provisional_total': 4000, 'construction': 4000, 'total': 4000}, pr)['differences']}
t('a provisional sum against a measured line, and an exclusion against a priced line, are classed as such', bd['R1']['class'] == 'ps_vs_measured'
  and bd['R1']['difference'] == 500.0 and bd['R2']['class'] == 'exclusion' and bd['R2']['difference'] == -2500.0)

# ---------------- client separation and the Purview label on the reference ----------------
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons', headers=H, json={'uploads': [{'name': 'ref.xlsx', 'data': b64(reference_xlsx('Client Badger'))}]})
t('a reference naming another client is refused by the job\'s client rule, and logged', r.status_code == 400 and 'Client Badger' in r.json()['detail'])
with s.db() as c:
    blk = c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked' AND target LIKE 'Digital team: reference cost plan%'").fetchone()[0]
    kept = c.execute('SELECT count(*) FROM team_reference_files').fetchone()[0]
t('…nothing of it was kept', blk >= 1 and kept == 0)

# ---------------- the comparison ----------------
CALLS.clear()
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons', headers=H, json={'uploads': [{'name': 'FICTIONAL reference.xlsx', 'data': b64(reference_xlsx())},
                                                                                     {'name': 'FICTIONAL external works.pdf', 'data': b64(reference_pdf())}]})
t('several reference files compare at once', r.status_code == 200 or print(r.text[:400]))
V = r.json()
CID = V['id']
D_ = {d['id']: d for d in V['differences']}
mcalls = [c for c in CALLS if '"reference_lines"' in c['payload']]
t('only the lines code could not match went to the lead\'s model, without rates', len(mcalls) == 1 and 'Roof covering, profiled sheet' in mcalls[0]['payload']
  and 'Hall walls, blockwork' not in mcalls[0]['payload'] and '"rate"' not in mcalls[0]['payload'])
pairs = {k_: v for k_, v in team_compare._row(CID)['result']['pairs'].items()}
t('matched by code, by description and unit, and the model\'s match checked in code', pairs['R1'][:2] == ['Q1', 'code'] and pairs['R2'][:2] == ['Q2', 'description']
  and pairs['R3'][:2] == ['Q3', 'model'] and 'R4' not in pairs and 'R99' not in pairs)
t('each difference classed correctly', D_['R1']['class'] == 'rate' and D_['R2']['class'] == 'quantity' and D_['R3']['class'] == 'arithmetic'
  and D_[[x for x in D_ if D_[x]['description'] == MARKER][0]]['class'] == 'missing_from_team' and D_['Q4']['class'] == 'extra_in_team'
  and any(d['class'] == 'missing_from_team' and 'drainage' in d['description'] for d in V['differences'])
  and not any('Loose furniture' in d['description'] for d in V['differences']))
t('arithmetic exact: rate difference (50 - 45) x 100 = 500.00', D_['R1']['difference'] == 500.0 and D_['R1']['effects']['rate'] == 500.0
  and D_['R1']['effects']['quantity'] == 0.0 and D_['R1']['difference_pct'] == 11.1)
t('…quantity difference (96 - 90) x 30 = 180.00, 6.7%', D_['R2']['difference'] == 180.0 and D_['R2']['effects']['quantity'] == 180.0 and D_['R2']['difference_pct'] == 6.7)
t('…the reference\'s own arithmetic: 9,600 against its stated 9,700', D_['R3']['team_amount'] == 9600.0 and D_['R3']['reference_amount'] == 9700.0
  and D_['R3']['difference'] == -100.0)
cp = team_qs.compute([{'ref': r_, 'element': e, 'quantity': q, 'rate': rt, 'rate_source': 'web'} for r_, e, d, q, u, rt in ITEMS],
                     1.0, team['settings'])
ref_total = Decimal('4500') + Decimal('2700') + Decimal('9700') + Decimal('3000') + Decimal('5000') + Decimal('2000')
T_ = V['totals']
t('totals in code: the reference shows preliminaries, so totals include them', T_['has_addons'] and T_['team_total'] == cp['total']
  and T_['reference_total'] == float(ref_total) and T_['variance'] == float(Decimal(str(cp['total'])) - ref_total)
  and T_['variance_pct'] == float(((Decimal(str(cp['total'])) - ref_total) / ref_total * 100).quantize(Decimal('0.1'))))
els = {e['element']: e for e in V['elements']}
t('per element: amount and %', els['Walls']['variance'] == 500.0 and els['Walls']['variance_pct'] == 11.1 and els['Doors']['reference'] == 0.0
  and els['Doors']['variance_pct'] is None and els['External works']['team'] == 0.0 and els['External works']['reference'] == 3000.0)
t('the drill-down has both sides, who produced the team\'s line, its rate source and cited source', D_['R1']['team_line']['priced_by'] == 'Cost Surveyor'
  and D_['R1']['team_line']['measured_by'] == 'Measurement Surveyor' and D_['R1']['team_line']['source_label'] == 'Published'
  and D_['R1']['team_line']['cited']['url'] == 'https://fictional-prices.example/q' and D_['R1']['reference_line']['where'].startswith('FICTIONAL reference.xlsx, sheet Cost plan, row'))
t('the comparison records the job version, team version, instruction set and models that ran', V['job_version'] == 1 and V['team_version'] == teams._row(JID)['team_version']
  and V['instruction_set'] >= 1 and any(m['role'] == 'Cost Surveyor' for m in V['models']) and V['models_ran'])
with s.db() as c:
    rf = [dict(x) for x in c.execute('SELECT name, role, client, space, alice_label FROM team_reference_files WHERE job_id=?', (JID,))]
    docs = [x[0] for x in c.execute('SELECT name FROM team_job_docs WHERE job_id=?', (JID,))]
t('the reference is kept with the job as role "reference", tagged to the job\'s client and in the job\'s space', len(rf) == 2 and all(x['role'] == 'reference'
  and x['client'] == 'Client Aardvark' and x['space'] == spaces.space_of('team_job', JID) for x in rf))
t('…and is not a job document, so the team never reads it', not any('reference' in d.lower() or 'external works' in d.lower() for d in docs))
t('the job page lists the comparison', cl.get(f'/admin/api/teams/jobs/{JID}/page').json()['compare']['comparisons'][0]['id'] == CID)

# ---------------- your review: the reference is not assumed correct ----------------
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/marks/R1', headers=H, json={'mark': 'reference', 'note': 'Blockwork rate was high for the region.'})
cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/marks/R2', headers=H, json={'mark': 'team', 'note': 'The reference missed the store.'})
cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/marks/R3', headers=H, json={'mark': 'unclear'})
V = cl.get(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}').json()
D_ = {d['id']: d for d in V['differences']}
t('review marks are saved, with notes and who', r.status_code == 200 and D_['R1']['mark']['mark'] == 'reference' and D_['R1']['mark']['note'].startswith('Blockwork')
  and D_['R2']['mark']['label'] == 'Team right' and D_['R3']['mark']['mark'] == 'unclear' and V['reviewed'] == 3)
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/marks/R1', headers=H, json={'mark': 'reference right'})
t('only the four marks are accepted', r.status_code == 422)

# ---------------- lessons: knowledge in the team's space, linked to the job and the lines ----------------
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/lessons', headers=H)
t('the Lead QS drafts lessons from your marks', r.status_code == 200 or print(r.text[:400]))
V = r.json()
lz = V['lessons'][0]
item = knowledge.meta([lz['knowledge_id']]).get(lz['knowledge_id'])
with s.db() as c: txt = c.execute('SELECT text FROM files WHERE id=?', (lz['knowledge_id'],)).fetchone()[0]
t('a lesson is created as knowledge, citing its lines and linked to the job and comparison', item and 'Check blockwork rates' in txt and 'R1 (Q1 ↔ Q1' in txt
  and 'R99' not in txt and f'#compare={CID}' in txt and teams.ref(JID) in txt and lz['lessons'][0]['differences'] == ['R1'])
t('…in the team\'s filing category, tagged to the job\'s client', item.get('category') == 'Quantity surveying' and clients.client_of('file', lz['knowledge_id']) == 'Client Aardvark')
team_space = spaces.space_of('team', TID)
with s.db() as c:
    queued = c.execute("SELECT count(*) FROM space_moves WHERE item_id=? AND to_space=?", (lz['knowledge_id'], team_space)).fetchone()[0]
t('…placed in the team\'s space through the sharing check', spaces.space_of('file', lz['knowledge_id']) == team_space or queued >= 1 or lz['placed'] in ('unchanged', 'moved'))

# ---------------- confirmed reference rates into the rate library, tagged to the client ----------------
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/rates', headers=H, json={})
lib = team_qs.library(TID)
row = next((x for x in lib if x['source'] == f'reference cost plan {teams.ref(JID)}'), None)
t('only the rate you confirmed (reference right) is added, with its source and the client tag', r.status_code == 200 and row and row['rate'] == 45.0
  and row['client'] == 'Client Aardvark' and row['description'] == 'Hall walls, blockwork' and len([x for x in lib if x['source'].startswith('reference cost plan')]) == 1)
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/rates', headers=H, json={})
t('…never twice', r.status_code == 400)
other = {'id': 'x', 'client': 'Client Badger', 'job_type': 'cost-estimate', 'team_id': TID, 'team_version': 1}
t('client separation: a job for another client does not get those rates', not any(x['source'].startswith('reference cost plan') for x in team_qs.library(TID, other))
  and any(x['source'].startswith('reference cost plan') for x in team_qs.library(TID, {**other, 'client': 'Client Aardvark'})))

# ---------------- Temple's instruction changes: shown, never applied until accepted ----------------
before = teams.get(TID)
pricer = next(m for m in before['members'] if m['role'] == 'Cost Surveyor')
r = cl.post(f'/admin/api/teams/jobs/{JID}/comparisons/{CID}/instructions', headers=H)
t('Temple proposes a change for the member whose line you marked reference right, citing it', r.status_code == 200 or print(r.text[:400]))
sg = r.json()['suggestions']
t('…one suggestion for the Cost Surveyor, citing R1', len(sg) == 1 and sg[0]['role'] == 'Cost Surveyor' and sg[0]['cites'] == ['R1'] and sg[0]['status'] == 'pending')
now = teams.get(TID)
t('…not applied: the team is unchanged', now['version'] == before['version'] and next(m for m in now['members'] if m['id'] == pricer['id'])['instructions'] == pricer['instructions'])
edited = 'Price blockwork from at least two recent published sources, name both, and prefer the lower unless the specification says otherwise.'
r = cl.post(f'/admin/api/teams/suggestions/{sg[0]["id"]}', headers=H, json={'action': 'approve', 'text': edited})
now = teams.get(TID)
t('accepted with your edits: a new team version with your text', r.status_code == 200 and now['version'] == before['version'] + 1
  and next(m for m in now['members'] if m['id'] == pricer['id'])['instructions'] == edited and 'edited by you' in teams.versions(TID)[0]['what'])
iv = team_compare.instruction_versions(TID)
t('member instructions are versioned: the instruction set moves on', iv[now['version']]['set'] == iv[before['version']]['set'] + 1
  and iv[now['version']]['members'][pricer['id']] == iv[before['version']]['members'][pricer['id']] + 1)
j2 = start('FICTIONAL later job')
t('a later job records the version that ran', j2['team_version'] == now['version'])

# ---------------- benchmarks ----------------
r = cl.put(f'/admin/api/teams/jobs/{JID}/benchmark', headers=H, json={'on': True})
t('a compared job is marked a benchmark', r.status_code == 200 and r.json()['benchmark']['on'] and r.json()['benchmark']['comparison'] == CID)
r = cl.put(f'/admin/api/teams/jobs/{j2["id"]}/benchmark', headers=H, json={'on': True})
t('…a job never compared cannot be one', r.status_code == 400)
est = cl.post(f'/admin/api/teams/{TID}/benchmarks/estimate', headers=H, json={'jobs': [JID]}).json()
t('the estimated cost is shown first, worked out from what its stages cost', est['jobs'][0]['estimate'] and est['jobs'][0]['estimate']['usd'] > 0
  and est['total']['usd'] == est['jobs'][0]['estimate']['usd'] and est['basis'].startswith('Estimate'))
v_before = teams._row(JID).get('version')
real_spend = rules_engine.check_spend
rules_engine.check_spend = lambda kind: (_ for _ in ()).throw(rules_engine.RuleViolation('Chat paused by Spending caps: FICTIONAL cap reached.'))
r = cl.post(f'/admin/api/teams/{TID}/benchmarks/run', headers=H, json={'jobs': [JID]})
t('the spending cap stops a benchmark re-run before it starts', r.status_code == 400 and 'Spending caps' in r.json()['detail'] and teams._row(JID).get('version') == v_before)
rules_engine.check_spend = real_spend
CALLS.clear()
r = cl.post(f'/admin/api/teams/{TID}/benchmarks/run', headers=H, json={'jobs': [JID]})
t('a benchmark re-run starts as a new version with the current instructions', r.status_code == 200 or print(r.text[:400]))
J = teams._row(JID)
t('…it ran to sign-off on its own (hand-offs automatic for this run)', J['version'] == v_before + 1 and J['status'] == 'waiting' and J['team_version'] == now['version'])
team_calls = [c for c in CALLS if '"reference_lines"' not in c['payload'] and '"reviewed_differences"' not in c['payload']]
t('the reference was never given to the team: no member\'s call holds a line of it', team_calls and not any(MARKER in c['payload'] or 'profiled sheet' in c['payload']
                                                                                                          or 'drainage connection' in c['payload'] for c in team_calls))
t('…and no model was asked to match on the benchmark comparison', not any('"reference_lines"' in c['payload'] for c in CALLS))
pricer_call = next(c for c in team_calls if 'MEASURED ITEMS' in c['payload'])
t('…the re-run used the accepted instructions', edited in pricer_call['system'])
vs = {x['version']: x for x in teams.job_versions(JID)['versions']}
t('the job version records the team version and models that ran', vs[J['version']]['kind'] == 'benchmark' and vs[J['version']]['team_version'] == now['version']
  and any(m['role'] == 'Cost Surveyor' for m in vs[J['version']]['models']) and vs[1]['team_version'] == before['version'])
cmps = team_compare.comparisons(JID)
bm = next(x for x in cmps if x['kind'] == 'benchmark')
t('when it finished it was compared with the same reference, recording its versions', bm['reference_of'] == CID and bm['job_version'] == J['version']
  and bm['team_version'] == now['version'] and bm['instruction_set'] == iv[now['version']]['set'] and bm['variance'] is not None)

# ---------------- the team page: accuracy and history ----------------
acc = cl.get(f'/admin/api/teams/{TID}/accuracy').json()
t('the accuracy panel: benchmark jobs, average and spread of total variance', acc['stats']['jobs'] == 1 and acc['stats']['mean_pct'] == bm['variance_pct']
  and acc['stats']['spread_pct'] == 0.0 and acc['benchmarks'][0]['job'] == JID)
t('…its trend by instruction version (the first comparison and the benchmark re-run)', len(acc['trend']) == 2 and acc['trend'][-1]['instruction_set'] == iv[now['version']]['set']
  and acc['trend'][0]['runs'] == 1)
t('…and by the models that ran', acc['by_models'] and sum(g['runs'] for g in acc['by_models']) == 2 and 'Cost Surveyor: claude-sonnet-5-5' in acc['by_models'][0]['models'])
t('…and the comparison history', len(acc['history']) == 2 and acc['history'][0]['kind'] == 'benchmark' and acc['history'][1]['id'] == CID
  and acc['history'][0]['href'].endswith('#compare=' + acc['history'][0]['id']))

# ---------------- spaces and permissions ----------------
import permissions
for route in ('GET /admin/api/teams/jobs/{jid}/comparisons', 'POST /admin/api/teams/jobs/{jid}/comparisons', 'GET /admin/api/teams/jobs/{jid}/comparisons/{cid}',
              'POST /admin/api/teams/jobs/{jid}/comparisons/{cid}/marks/{did}', 'POST /admin/api/teams/jobs/{jid}/comparisons/{cid}/lessons',
              'POST /admin/api/teams/jobs/{jid}/comparisons/{cid}/rates', 'POST /admin/api/teams/jobs/{jid}/comparisons/{cid}/instructions',
              'PUT /admin/api/teams/jobs/{jid}/benchmark', 'GET /admin/api/teams/{tid}/accuracy', 'POST /admin/api/teams/{tid}/benchmarks/estimate',
              'POST /admin/api/teams/{tid}/benchmarks/run'):
    assert route in permissions.ROUTES, route
t('every comparison and benchmark route declares its section (comparisons follow the job\'s permissions and spaces)', True)
r = cl.get(f'/admin/api/teams/jobs/{JID}/comparisons/{bm["id"][:-1]}0')
t('an unknown comparison on the job is not found', r.status_code == 404)
other_job = start('FICTIONAL other job')
r = cl.get(f'/admin/api/teams/jobs/{other_job["id"]}/comparisons/{CID}')
t('…nor is another job\'s comparison through this job', r.status_code == 404)
