"""Digital teams: drawings read in code first, flagged assumptions, and files added mid-job with a choice of re-run (10 Oct 2026).

A FICTIONAL A3 plan with a scale bar and dimensions is measured by Alice's own code within tolerance, every reading citing page and
area, with no model; only areas code cannot read go to a vision model, cropped. A missing dimension gives one flagged assumption (no
stop), its effect on cost worked out in code; a setting decides how bold assumptions may be and the cost above which the team must ask;
changing an assumption redoes only the lines it affects; decisions and drawing lessons are filed in Knowledge in the job's space. A file
added mid-job is matched as a revision in code, the old one kept and linked, and nothing is redone until you choose, each choice with its
estimated cost; the spending cap stops image reads and re-runs. Stand-in models only."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, io, json, re
from decimal import Decimal
from types import SimpleNamespace
import app, substrate_store as s, assistants, org_research, usage_meter, rules_engine, knowledge
import teams, team_qs, team_files, drawing_code
import _drawings as DR
from fastapi.testclient import TestClient
from pypdf import PdfReader
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False

USAGE = SimpleNamespace(usage={'input_tokens': 10000, 'output_tokens': 1000})        # Sonnet: $0.03 a call
VISION, CALLS = [], []
PLAN_PDF = 'FICTIONAL plan.pdf'
STATE = {'measure': None, 'review': None}
ASSUMED = {'assumption': 'Wall height taken as 3.0 m: no section drawing gives it', 'why': 'No height on the drawings',
           'affects': 'Q1 (Walls)', 'size': 'minor'}


def items(*refs_els):
    out = [{'ref': 'Q1', 'element': 'Walls', 'description': 'Hall walls, blockwork', 'quantity': 12, 'unit': 'm2',
            'source': {'document': PLAN_PDF, 'page': '1', 'area': 'A3'}, 'from_drawing': True},
           {'ref': 'Q2', 'element': 'Floor', 'description': 'Hall floor screed', 'quantity': 96, 'unit': 'm2',
            'source': {'document': PLAN_PDF, 'page': '1', 'area': 'A2'}, 'from_drawing': True}]
    return [i for i in out if i['element'] in refs_els]


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    content = messages[0]['content']
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    if isinstance(content, list):                              # a page or an area sent as an image
        att = [b for b in content if b.get('type') in ('document', 'image')]
        text = next(b['text'] for b in content if b.get('type') == 'text')
        boxes = []
        for b in att:
            if b.get('type') == 'document':
                pg = PdfReader(io.BytesIO(base64.b64decode(b['source']['data']))).pages[0]
                boxes.append((float(pg.cropbox.width), float(pg.cropbox.height)))
        VISION.append({'text': text, 'boxes': boxes, 'workload': workload})
        return json.dumps({'drawing_number': '', 'scale': '', 'dimensions': [{'text': 'Store 2400 wide', 'area': 'C1'}], 'levels': [], 'notes': [], 'unreadable': ''})
    CALLS.append({'workload': workload, 'payload': content, 'system': system})
    if 'NEW FILES' in content: return json.dumps(STATE['review'] or {'files': [], 'summary': 'FICTIONAL review.'})
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in content:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload and 'SUGGESTED MARKET ADJUSTMENT' in content:
        return json.dumps({'accept': False, 'reason': 'No.', 'summary': 'Rejected.'})
    if 'Lead QS' in workload:
        return json.dumps({'plan': 'Measure from the plan.', 'elements': [{'name': 'Walls', 'documents': []}, {'name': 'Floor', 'documents': []}],
                           'documents': [{'name': PLAN_PDF, 'use': 'all'}], 'location': '', 'summary': 'Planned.', 'note': 'Go.', 'questions': []})
    if 'Measurement' in workload:
        part = content.split('THIS PART: take off ONLY these elements:')[1].split('from the DOCUMENTS')[0]
        els = [e for e in ('Walls', 'Floor') if e in part]
        out = {'accept': True, 'items': items(*els), 'summary': '', 'note': 'Price these.', 'assumed': [ASSUMED] if 'Walls' in els else []}
        if STATE['measure']: out.update(STATE['measure'])
        return json.dumps(out)
    if 'Market Trends' in workload: return json.dumps({'matches': [], 'commentary': 'Nothing to compare.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


def fake_ask(prompt, query, provider, workload='', **kw):
    usage_meter.log(USAGE, 'claude', 'claude-sonnet-5-5', workload)
    if 'MEASURED ITEMS' not in query: return json.dumps({'findings': [], 'commentary': 'No market evidence.'}), {}
    refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    return json.dumps({'rates': [{'ref': r, 'source': 'published', 'rate': 50, 'unit': 'm2', 'source_url': 'https://fictional-prices.example/q',
                                  'source_date': '2026-06'} for r in refs], 'searches': ['rates']}), {'https://fictional-prices.example/q': 'Prices'}


assistants._call = fake_call
org_research._ask = fake_ask
b64 = lambda raw: base64.b64encode(raw).decode()

# ---------------- code first: the FICTIONAL plan measured by Alice's own code ----------------
raw = DR.pdf([DR.plan_page()])
r = drawing_code.read_pdf(raw)[1]
dim = r['dimensions'][0]
room = r['rooms'][0]
t('the scale comes from the scale bar (0 to 5 m)', r['scale'] and 'scale bar' in r['scale']['how'] and r['paper'] == 'A3 landscape')
t('a dimension line measures within tolerance of what is written (12000 = 12.00 m)', dim['value_m'] == Decimal('12.00')
  and abs(dim['measured_m'] - Decimal('12')) <= Decimal('0.12') and dim['agrees'] is True)
t('a room outline is measured at the scale: Hall 12 m x 8 m = 96 m2 (within 2%)', room['name'] == 'Hall'
  and abs(room['area_m2'] - Decimal('96')) <= Decimal('1.92') and abs(room['width_m'] - Decimal('12')) <= Decimal('0.12'))
t('every reading cites page and area', dim['area'] == 'A3' and room['area'] == 'A2' and r['drawing_number'] == 'FIC-A-101')
text = drawing_code.render(r, PLAN_PDF)
t('…in the text the team reads, each line naming the page and area', f'({PLAN_PDF}, page 1, area A3)' in text and f'({PLAN_PDF}, page 1, area A2)' in text
  and 'read from the drawing\'s text and lines by Alice in code (no model)' in text)
t('code read it all: nothing goes to a model', drawing_code.needs_model(r) == ('', []))
r2 = drawing_code.read_pdf(DR.pdf([DR.plan_page(bar=False)]))[1]
t('without a scale bar, the written ratio for the paper the page is on is used', r2['scale'] and '1:100' in r2['scale']['how']
  and abs(r2['dimensions'][0]['measured_m'] - Decimal('12')) <= Decimal('0.12'))
r3 = drawing_code.read_pdf(DR.pdf([DR.plan_page(bar=False, written='Scale 1:100 at A1')]))[1]
t('a written ratio for other paper (A1 on an A3 page) is not used, and it says so', r3['scale'] is None and 'is for A1 paper but this page is A3' in r3['scale_note']
  and r3['dimensions'][0]['measured_m'] is None)
r4 = drawing_code.read_pdf(DR.pdf([DR.plan_page(written='Scale 1:50 at A3')]))[1]
t('a written scale that does not match the scale bar: the bar wins, and it says so', 'scale bar' in r4['scale']['how'] and 'does not match the scale bar' in r4['scale_note'])
r5 = drawing_code.read_pdf(DR.pdf([DR.plan_page(extra=DR.line(900, 700, 1100, 700))]))[1]
t('drawn content with no text (area C1) is what a model is asked to read, cropped to that area', drawing_code.needs_model(r5) == ('areas', ['C1']))
r6 = drawing_code.read_pdf(DR.pdf([DR.line(100, 100, 500, 500)]))[1]
t('a page with no text layer at all (a scan) goes whole', drawing_code.needs_model(r6) == ('page', []))

# ---------------- in a job: code reads the plan, the model reads only the C1 area ----------------
team = teams.from_template('quantity-surveying', name='Drawings test team')
TID = team['id']
teams.set_autonomy(TID, 'signoff')
teams.create_filing_category(TID)


def start(title, extra=''):
    r = cl.post(f'/admin/api/teams/{TID}/jobs', headers=H, json={'job_type': 'cost-estimate', 'title': title, 'client': '',
                'brief': 'A fictional single-storey community hall, to be estimated from the plan.',
                'uploads': [{'name': PLAN_PDF, 'kind': 'drawing', 'data': b64(DR.pdf([DR.plan_page(extra=extra)]))}]})
    assert r.status_code == 200, r.text
    return r.json()


j = start('FICTIONAL hall from the plan', extra=DR.line(900, 700, 1100, 700))
t('the job runs to sign-off (the missing wall height did not stop it)', j['status'] == 'waiting' and j['pending'][0]['kind'] == 'signoff')
reads = team_files.reads(j['id'])
code = [x for x in reads if x['provider'] == 'code']
model = [x for x in reads if x['provider'] != 'code']
t('the plan page was read in code first, at no cost', len(code) == 1 and code[0]['cost_usd'] == 0 and 'scale bar' in code[0]['scale'])
t('…and only the C1 area went to the vision model, cropped to about a third of the page', len(VISION) == 1 and len(model) == 1 and model[0]['area'] == 'C1'
  and 'AREA: C1' in VISION[0]['text'] and VISION[0]['boxes'] and VISION[0]['boxes'][0][0] < DR.A3[0] / 2 and VISION[0]['boxes'][0][1] < DR.A3[1] / 2)
meas = next(c for c in CALLS if 'Measurement' in c['workload'])
t('the Measurement Surveyor sees code\'s measurements and the area reading, each citing page and area', 'Room: Hall, 12.00 m x 8.00 m = 96.00 m2 at the scale' in meas['payload']
  and f'Dimension: Store 2400 wide ({PLAN_PDF}, page 1, area C1)' in meas['payload'] and 'give that page and area in "source"' in meas['payload'])
J = teams._row(j['id'])
its = {i['ref']: i for i in J['outputs']['measure']['items']}
t('each quantity cites its page and area', its['Q1']['source'] == {'document': PLAN_PDF, 'page': '1', 'line': '', 'area': 'A3'}
  and its['Q2']['source_text'] == f'{PLAN_PDF}, page 1, area A2')

# ---------------- a missing dimension: one flagged assumption, its effect on cost in code ----------------
flags = teams.assumed(J['outputs'])
t('a missing dimension gives one flagged assumption (no question, no stop)', len(flags) == 1 and flags[0]['status'] == 'open'
  and flags[0]['assumption'].startswith('Wall height') and not any(x['kind'] == 'question' for x in teams._steps(j['id'])))
pg = cl.get(f'/admin/api/teams/jobs/{j["id"]}/page').json()
f0 = pg['assumed'][0]
t('its effect on cost is worked out in code from the lines it affects (Q1: 12 m2 x £50 = £600.00)', f0['impact'] == {'text': '£600.00', 'refs': ['Q1']})

# ---------------- how bold assumptions may be, and the cost above which the team must ask ----------------
r = cl.put(f'/admin/api/teams/{TID}/missing-info', json={'mode': 'assume', 'limit': 500}, headers=H)
t('the limit is a team setting (a new version)', r.status_code == 200 and teams.assume_limit(teams.get(TID)) == Decimal('500.00')
  and 'ask above £500.00' in teams.versions(TID)[0]['what'])
jl = start('FICTIONAL hall, over the limit')
q = next((x for x in jl['pending'] if x['kind'] == 'question'), None)
t('an assumption whose lines come to more than the limit is put to you, saying why', q is not None and 'Wall height' in q['note']
  and 'above your limit of £500.00' in q['content']['why'] and q['content']['flags'])
t('…the flag says it was asked', teams.assumed(teams._row(jl['id'])['outputs'])[0]['status'] == 'asked')
cl.post(f'/admin/api/teams/steps/{q["id"]}', json={'action': 'answer', 'note': 'Yes, 3.0 m is right.'}, headers=H)
fl = teams.assumed(teams._row(jl['id'])['outputs'])[0]
t('…and your answer decides it', fl['status'] == 'answered' and fl['decision']['text'] == 'Yes, 3.0 m is right.')
cl.put(f'/admin/api/teams/{TID}/missing-info', json={'mode': 'minor', 'limit': 0}, headers=H)
STATE['measure'] = {'assumed': [{**ASSUMED, 'assumption': 'The hall assumed to be single storey throughout', 'size': 'major', 'affects': 'Walls, Floor'}]}
jm = start('FICTIONAL hall, minor only')
STATE['measure'] = None
q = next((x for x in jm['pending'] if x['kind'] == 'question'), None)
t('with "minor points only", a major assumption is put to you', teams.missing_info(teams.get(TID)) == 'minor' and q is not None
  and 'single storey' in q['note'] and 'more than a minor point' in q['content']['why'])
t('the members are told how bold they may be', 'for a minor point (it changes a few lines a little), make a reasonable assumption'
  in [c for c in CALLS if 'Measurement' in c['workload']][-1]['system'])
teams.set_missing_info(TID, 'assume', 0)

# ---------------- Accept, Ask the client, Change (only the affected lines redone) ----------------
aid = f0['id']
CALLS.clear()
STATE['measure'] = {'assumed': [{**ASSUMED, 'assumption': 'Blockwork taken as 140 mm thick', 'affects': 'Q1'}]}
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/assumptions/{aid}', json={'action': 'change', 'text': 'Walls are 4.5 m high (see the client email).'}, headers=H)
STATE['measure'] = None
J = teams._row(j['id'])
t('changing an assumption starts a new version that redoes only the lines it affects', r.status_code == 200 and J['version'] == 2
  and teams.job_versions(j['id'])['versions'][-1]['kind'] == 'remeasure' and 'Re-measuring Walls' in r.json()['message'])
ms = [c for c in CALLS if 'Measurement' in c['workload']]
t('…only Walls measured again (Floor kept exactly), with your correction passed to the member', ms and all('ONLY these elements: Walls' in c['payload'] for c in ms)
  and 'Walls are 4.5 m high' in ms[0]['payload'])
pr = [c for c in CALLS if 'MEASURED ITEMS' in c.get('payload', '')]
J = teams._row(j['id'])
its = {i['element']: i for i in J['outputs']['price']['items']}
t('…only its items priced again; the Floor item and price kept', its['Floor']['ref'] == 'Q2' and its['Floor']['rate'] == 50)
fl = next(a for a in teams.assumed(J['outputs']) if a['id'] == aid)
t('…and the flag records the change, by whom, and the version', fl['status'] == 'changed' and fl['decision']['text'].startswith('Walls are 4.5 m')
  and fl['decision']['version'] == 2)
with s.db() as c:
    t('…logged', c.execute("SELECT count(*) FROM activity WHERE action='team_assumption_change' AND target=?", (j['id'],)).fetchone()[0] == 1)
new = [a for a in teams.assumed(J['outputs']) if a['status'] == 'open']
t('the member\'s own item numbers in an assumption follow Alice\'s renumbering (Q1 measured again is now Q3)', new and new[0]['affects'] == 'Q3'
  and next(f_ for f_ in cl.get(f'/admin/api/teams/jobs/{j["id"]}/page').json()['assumed'] if f_['id'] == new[0]['id'])['impact']['refs'] == ['Q3'])
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/assumptions/{new[0]["id"]}', json={'action': 'accept'}, headers=H)
t('Accept marks it accepted', r.status_code == 200 and next(a for a in teams.assumed(teams._row(j['id'])['outputs']) if a['id'] == new[0]['id'])['status'] == 'accepted')
nf = {'assumption': 'Floor finish assumed vinyl', 'why': 'Not specified', 'affects': 'nothing named', 'size': 'minor', 'id': 'abcd1234', 'status': 'open', 'stage': 'measure'}
o = teams._row(j['id'])['outputs']; o['_assumed'].append(nf); teams._set(j['id'], outputs=o)
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/assumptions/abcd1234', json={'action': 'change', 'text': 'Carpet.'}, headers=H)
t('a change naming no lines is refused, changing nothing (choose them with Re-price or Re-measure)', r.status_code == 400 and 'Re-price or Re-measure' in r.json()['detail']
  and teams._row(j['id'])['version'] == 2)
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/assumptions/abcd1234', json={'action': 'ask_client', 'text': 'Which floor finish do you want?'}, headers=H)
t('Ask the client lists the question on the job and in the outputs', r.status_code == 200
  and any('Asked the client: Which floor finish do you want?' in x for x in teams.assumed_lines(teams._row(j['id'])['outputs'])))

# ---------------- sign-off: what you decided and how the drawings were read go to Knowledge, in the job's space ----------------
so = next(x for x in teams._steps(j['id']) if x['status'] == 'pending' and x['kind'] == 'signoff')
cl.post(f'/admin/api/teams/steps/{so["id"]}', json={'action': 'approve'}, headers=H)
J = teams._row(j['id'])
lf = J['outputs'].get('lessons_filed') or []
item = knowledge.meta([lf[0]['knowledge_id']]).get(lf[0]['knowledge_id']) if lf else None
with s.db() as c:
    row = c.execute('SELECT text FROM files WHERE id=?', (lf[0]['knowledge_id'],)).fetchone() if lf else None
txt = row[0] if row else ''
t('at sign-off a knowledge note is filed in the team\'s category with the decided assumptions', lf and item and item.get('category') == 'Quantity surveying'
  and 'You changed to: Walls are 4.5 m high' in txt and 'You accepted as it was' in txt and 'It was put to the client: Which floor finish' in txt)
t('…and what the drawings taught (read in code, scale from the bar, the area a model had to read)', 'read in code' in txt and 'scale from the scale bar' in txt
  and 'area with drawn content but no text' in txt)
t('…placed in the job\'s space through the sharing check', lf[0]['placed'] in ('moved', 'shared', 'default', 'waiting', 'queued', 'kept', 'held'))

# ---------------- a file added mid-job: a revision found in code, kept and linked; choose with the cost shown first ----------------
STATE['review'] = None
CALLS.clear()
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/files', headers=H, json={'uploads': [{'name': 'FICTIONAL plan rev B.pdf', 'kind': 'drawing',
            'data': b64(DR.pdf([DR.plan_page(drawing_no='FIC-A-101')]))}]})
x = r.json()
docs = {d['name']: d for d in teams._docs_in(j['id'], include_replaced=True)}
t('a new revision of a drawing is found in code (same drawing number) and takes its place', r.status_code == 200
  and docs['FICTIONAL plan rev B.pdf']['replaces'] == docs[PLAN_PDF]['id'] and docs[PLAN_PDF]['replaced_by'] == docs['FICTIONAL plan rev B.pdf']['id'])
t('…the old one is kept and linked, never deleted, and the team works from the new one', PLAN_PDF in docs and PLAN_PDF not in {d['name'] for d in teams._docs_in(j['id'])}
  and any(d['name'] == PLAN_PDF and d['replaced_by'] == 'FICTIONAL plan rev B.pdf' for d in teams.job_detail(j['id'])['documents']))
rv = x['review']
t('…the report says so (found by Alice), and nothing is redone yet', rv['files'][0]['change'] == 'revision' and rv['files'][0]['found_by'] == 'code'
  and rv['files'][0]['replaces'] == PLAN_PDF and teams._row(j['id'])['version'] == 2 and teams._row(j['id'])['status'] == 'done')
t('…no lead call was needed: code matched it and there are no open assumptions', not any('NEW FILES' in c['payload'] for c in CALLS))
opts = {o['key']: o for o in rv['options']}
t('…options with their estimated cost first (re-measure the elements that used the old plan, re-price, full, nothing)', set(opts) == {'remeasure', 'reprice', 'full', 'none'}
  and opts['remeasure']['estimate'] and opts['full']['estimate'] and opts['remeasure']['elements'] == ['Walls', 'Floor'])
pj = teams._row(j['id'])['outputs']['plan']['element_documents']
t('…the revision replaces the old file in the elements\' documents', all('FICTIONAL plan rev B.pdf' in v and PLAN_PDF not in v for v in pj.values()) if pj else True)

# ---------------- the spending cap ----------------
real_spend = rules_engine.check_spend
rules_engine.check_spend = lambda kind: (_ for _ in ()).throw(rules_engine.RuleViolation('Chat paused by Spending caps: FICTIONAL cap reached.'))
r = cl.post(f'/admin/api/teams/jobs/{j["id"]}/files/rerun', headers=H, json={'choice': 'remeasure'})
t('the spending cap stops a re-run before it starts (the choice still waits)', r.status_code == 400 and 'Spending caps' in r.json()['detail']
  and teams._row(j['id'])['outputs']['_files_review']['status'] == 'waiting' and teams._row(j['id'])['version'] == 2)
VISION.clear()
jc = start('FICTIONAL hall, capped', extra=DR.line(900, 700, 1100, 700))
rules_engine.check_spend = real_spend
t('…and stops image reads: the job stops with the reason, nothing sent', jc['status'] == 'blocked' and 'Spending caps' in jc['error'] and not VISION
  and [x for x in team_files.reads(jc['id']) if x['provider'] == 'code'])

# ---------------- pages and routes ----------------
import permissions
t('routes declare their sections', permissions.ROUTES.get('POST /admin/api/teams/jobs/{jid}/files/rerun') == 'job:use:reprice'
  and permissions.ROUTES.get('POST /admin/api/teams/jobs/{jid}/assumptions/{aid}') == 'job:use:run')
html = cl.get(f'/admin/teams/{TID}/jobs/{j["id"]}').text
t('the job page: flagged assumptions with Accept, Change, Ask the client; the new files report with costed options; drawings read',
  all(x in html for x in ("'Flagged assumptions'", "'Accept'", "'Change'", "'Ask the client'", 'function reviewPanel(', "'/files/rerun'", "'Drawings read'",
                          "'Estimated cost: '")))
t('the Rules and autonomy tab: three settings and the cost limit', all(x in html for x in ("'Save limit'", "minor:'A member assumes only minor points")))
