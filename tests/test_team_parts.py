"""Digital teams working in parts (Stefan, 8 Oct 2026): members whose output is a list (Measurement Surveyor, Cost Surveyor,
Market Trends QS) work element by element, each part seeing the brief and the whole element list but only its own sources; the
parts are merged in code with nothing lost or duplicated and every source kept. A part cut off at the model's length limit is
halved and tried again; at the smallest part the job stops naming the element, and Try again redoes only that part. Replies are
read tolerantly (citation markup, JSON inside text), one format retry, then a plain reason with the start of the reply kept on
the job. Each member's output limit is its model's real limit. The Cost Surveyor defaults to Sonnet. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, re, shutil, subprocess, tempfile
from pathlib import Path
import app, substrate_store as s, assistants, org_research, rules_engine
import teams, team_qs
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False

# ---------------- tolerant reading ----------------
d = teams.parse_json('Here is the take-off you asked for:\n```json\n{"items": [{"ref": "Q1"}], "summary": "done"}\n```\nLet me know.')
t('JSON inside surrounding text and code fences is read', d['items'][0]['ref'] == 'Q1')
d = teams.parse_json('<cite index="1-2">{"rates": [{"ref": "Q1", "rate": 12, "note": "from <cite index=\\"3\\">a price book</cite>"}]}</cite>')
t('web-search citation markup is removed before reading (as organisations.strip_citations)', d['rates'][0]['rate'] == 12 and 'cite' not in d['rates'][0]['note'])
d = teams.parse_json('I priced them {roughly}. {"rates": []} and that is all {really}.')
t('the JSON object is found even when other braces surround it', d == {'rates': []})
try: teams.parse_json('I could not find any published rates for these items.', 'Cost Surveyor', 'the list of priced items'); ok = False
except teams.Unreadable as e: ok = 'it was text, not the list of priced items' in str(e) and e.raw.startswith('I could not')
t('an answer with no JSON is Unreadable, with a plain reason and the raw reply', ok)

# ---------------- each model's real output limit ----------------
t('output limits are the models\' own (Sonnet and Opus 128K, Haiku 64K)', assistants.MAX_OUTPUT['claude_sonnet'] == 128000
  and assistants.MAX_OUTPUT['claude_opus'] == 128000 and assistants.MAX_OUTPUT['claude'] == 64000 and set(assistants.MAX_OUTPUT) == set(assistants.PROVIDERS))


class FakeStream:
    def __init__(self, box, kw): self.box, self.kw = box, kw
    def __enter__(self): self.box.append(('stream', self.kw['max_tokens'])); return self
    def __exit__(self, *a): return False
    def get_final_message(self):
        class B: type, text = 'text', '{"ok": true}'
        class R: content, stop_reason, usage = [B()], 'end_turn', None
        return R()


class FakeAnthropic:
    calls = []
    def __init__(self, **kw): self.messages = self
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def stream(self, **kw): return FakeStream(FakeAnthropic.calls, kw)
    def create(self, **kw):
        FakeAnthropic.calls.append(('create', kw['max_tokens'])); return FakeStream(FakeAnthropic.calls, kw).get_final_message()


import anthropic, usage_meter
real_anthropic, real_log = anthropic.Anthropic, usage_meter.log
anthropic.Anthropic, usage_meter.log = FakeAnthropic, lambda *a, **k: None
meta = {}
assistants._call('claude_sonnet', 'sys', [{'role': 'user', 'content': 'x'}], max_tokens=128000, meta=meta)
assistants._call('claude', 'sys', [{'role': 'user', 'content': 'x'}], max_tokens=1500)
t('a long Claude answer is streamed (no HTTP timeout); a short one is not', FakeAnthropic.calls == [('stream', 128000), ('create', 1500)] and meta['truncated'] is False)
anthropic.Anthropic, usage_meter.log = real_anthropic, real_log

# ---------------- the team and the stand-in models ----------------
team = teams.from_template('quantity-surveying', name='Parts test team')
TID = team['id']
cs = teams._member(team, 'cost-surveyor')
t('the QS template defaults the Cost Surveyor to Claude Sonnet 5.5', cs['provider'] == 'claude_sonnet'
  and next(m for m in team_qs._template()['members'] if m['id'] == 'cost-surveyor')['provider'] == 'claude_sonnet')
teams.update_member(team_qs.TEAM_ID, 'cost-surveyor', {'provider': 'claude'})
team_qs.seed()
t('an existing team keeps its own choice of model', teams._member(teams.get(team_qs.TEAM_ID), 'cost-surveyor')['provider'] == 'claude')
teams.set_autonomy(TID, 'signoff')

ELEMENTS = ['Substructure', 'Frame', 'Roof', 'Walls', 'Finishes']
DOCS = {e: f'FICTIONAL {e.lower()} spec.md' for e in ELEMENTS}
PLAN = {'plan': 'Measure each element from its own specification.', 'elements': [{'name': e, 'documents': [DOCS[e]]} for e in ELEMENTS],
        'documents': [{'name': n, 'use': 'quantities'} for n in DOCS.values()], 'location': '', 'summary': 'Planned.', 'note': 'Go.', 'questions': []}
CALLS, PROGRESS = [], []
MODE = {'measure': 'normal', 'trends': 'normal'}
JOB = {}


def measured(part_elements, payload):
    items = []
    for e in part_elements:
        items.append({'element': e, 'description': f'{e} main item', 'quantity': 10, 'unit': 'm2', 'source': {'document': DOCS[e], 'page': '1'}})
        items.append({'element': e, 'description': f'{e} second item', 'quantity': 4, 'unit': 'nr', 'source': {'document': DOCS[e], 'page': '2'}})
    if 'Roof' in part_elements: items.append(dict(items[0]))         # the same item twice: kept once
    return items


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    payload = messages[0]['content']
    CALLS.append({'workload': workload, 'system': system, 'payload': payload, 'max_tokens': max_tokens, 'provider': provider})
    meta = meta if isinstance(meta, dict) else {}
    meta['truncated'] = False
    if JOB.get('id'):
        PROGRESS.append(teams.job_detail(JOB['id'])['part_progress'])
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in payload:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload: return json.dumps(PLAN)
    if 'Measurement' in workload:
        mine = re.search(r'THIS PART: take off ONLY these elements: (.*?), from the DOCUMENTS', payload).group(1).split(', ')
        mode = MODE['measure']
        if mode == 'halve' and len(mine) > 1:                             # too long for one answer: cut off
            meta['truncated'] = True; return '{"accept": true, "items": [{"element": "'
        if mode == 'stop_roof' and 'Roof' in mine:
            meta['truncated'] = True; return '{"items": ['
        if mode == 'text' and 'Roof' in mine:
            return 'I measured the roof but the tiles schedule is unclear. ' + 'sk-ant-api03-' + 'Z' * 90 if 'ONLY the JSON' not in system else 'Still prose, sorry.'
        if mode == 'retry' and 'Roof' in mine and 'ONLY the JSON' not in system:
            return 'Here is my take-off for the roof: the main item is 10 m2.'
        return 'Sure. <cite index="0-1">' + json.dumps({'accept': True, 'items': measured(mine, payload), 'summary': '', 'note': 'Priced next.'}) + '</cite>'
    if 'Market Trends' in workload:
        refs = re.findall(r'^(Q\d+) \|', payload.split('RATES USED NOW')[1], re.M)
        return json.dumps({'matches': [{'ref': r, 'history': ['H1']} for r in refs], 'commentary': 'Similar to last time.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


SEARCHES = []


def fake_ask(prompt, query, provider, workload='', **kw):
    refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    if JOB.get('id'): PROGRESS.append(teams.job_detail(JOB['id'])['part_progress'])
    SEARCHES.append({'refs': refs, 'kw': {k: v for k, v in kw.items() if k != 'meta'}, 'factor': 'leave location_factor empty' not in query})
    rates = [{'ref': r, 'rate': 10 + int(r[1:]), 'unit': '', 'source_url': f'https://fictional-prices.example/{r}', 'source_date': '2026-05'} for r in refs]
    rates.append({'ref': 'Q999', 'rate': 1, 'source_url': 'https://fictional-prices.example/Q1', 'source_date': '2026-05'})   # not in this part
    return json.dumps({'rates': rates, 'searches': [f'rates for {",".join(refs)}']}), {f'https://fictional-prices.example/{r}': f'Price page {r}' for r in refs}


assistants._call = fake_call
org_research._ask = fake_ask


def start(title='FICTIONAL parts job'):
    body = {'job_type': 'cost-estimate', 'title': title, 'brief': 'A fictional single-storey hall for a community trust, to be estimated.',
            'uploads': [{'name': n, 'kind': 'spec', 'text': f'FICTIONAL specification for {e}. Page 1 and page 2.'} for e, n in DOCS.items()]}
    r = cl.post(f'/admin/api/teams/{TID}/jobs', json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- split and merge ----------------
j = start()
meas = [c for c in CALLS if 'Measurement' in c['workload']]
t('the take-off is worked in parts of three elements (5 elements = 2 parts)', len(meas) == 2)
t('each part sees the brief and the whole element list', all('A fictional single-storey hall' in c['payload'] and 'WHOLE PLAN: elements Substructure, Frame, Roof, Walls, Finishes' in c['payload'] for c in meas))
doc_in = lambda e, c: f'=== {DOCS[e]} (' in c['payload']
t('…but only its own sources (documents)', all(doc_in(e, meas[0]) for e in ELEMENTS[:3]) and not any(doc_in(e, meas[0]) for e in ELEMENTS[3:])
  and all(doc_in(e, meas[1]) for e in ELEMENTS[3:]) and not any(doc_in(e, meas[1]) for e in ELEMENTS[:3]))
items = j['outputs']['measure']['items']
t('merged in code: every element\'s items, the duplicate once, numbered in order', len(items) == 10 and [i['ref'] for i in items] == [f'Q{n}' for n in range(1, 11)]
  and [i['element'] for i in items][::2] == ELEMENTS)
t('…each item keeps its source reference', all(i['source']['document'] == DOCS[i['element']] and i['source_text'] for i in items))
t('every member call uses its model\'s real output limit', all(c['max_tokens'] == assistants.MAX_OUTPUT[c['provider']] for c in CALLS if 'Talk' not in c['workload']))
t('the Cost Surveyor searches with its own model (Sonnet) and its output limit', SEARCHES and all(x['kw'] == {'model': 'claude-sonnet-5-5', 'max_tokens': 128000} for x in SEARCHES))
price = j['outputs']['price']['items']
t('pricing: all ten items in one part (under twenty items), the regional factor looked for once', len(SEARCHES) == 1 and SEARCHES[0]['factor'])
t('every item priced with its own cited page; a rate for an item outside the part is ignored', all(i['rate_source'] == 'web' and i['source_url'].endswith('/' + i['ref']) for i in price))
turns = {x['stage']: x for x in j['steps'] if x['kind'] == 'turn' and x['status'] == 'done'}
t('parts per stage are recorded on the run', turns['measure']['content']['parts'] == {'parts': 2, 'halved': 0, 'elements': 5})
with s.db() as c:
    ev = [r[0] for r in c.execute("SELECT detail FROM agent_events WHERE run_id=? AND kind='note'", (turns['measure']['run_id'],))]
t('…and as a note on the agent run', any('Take off quantities: 2 parts' in e for e in ev))
t('the job no longer carries part state once the stage is done', '_parts' not in teams._row(j['id'])['outputs'] or 'measure' not in teams._row(j['id'])['outputs']['_parts'])

# many items: pricing in several parts, by element, nothing lost
SEARCHES.clear()
many = [{'ref': f'Q{n}', 'element': ELEMENTS[(n - 1) // 9], 'description': f'item {n}', 'quantity': 1, 'unit': 'm2', 'source': {'document': 'x', 'page': '1'}, 'source_text': 'x'}
        for n in range(1, 46)]
pieces = team_qs._item_pieces(many)
t('items are grouped by element, at most twenty to a piece', all(len(p['refs']) <= team_qs.PRICE_ITEMS for p in pieces) and len(pieces) == 5)
packs = teams._pack(pieces, team_qs.PRICE_ITEMS, lambda p: len(p['refs']))
t('…and packed into parts of up to twenty items', [sum(len(p['refs']) for p in x) for x in packs] == [18, 18, 9]
  and [r for x in packs for p in x for r in p['refs']] == [i['ref'] for i in many])

# ---------------- halving on truncation ----------------
CALLS.clear(); MODE['measure'] = 'halve'
j2 = start('FICTIONAL parts job: halving')
meas = [c for c in CALLS if 'Measurement' in c['workload']]
items = j2['outputs']['measure']['items']
t('a part cut off is halved and tried again until each answer fits', j2['status'] == 'waiting' and len(items) == 10 and len({i['ref'] for i in items}) == 10)
t('…the halves cover every element once (nothing lost or duplicated)', sorted({i['element'] for i in items}) == sorted(ELEMENTS)
  and sorted((i['element'], i['description']) for i in items) == sorted((e, f'{e} {k} item') for e in ELEMENTS for k in ('main', 'second')))
mt = next(x for x in j2['steps'] if x['kind'] == 'turn' and x['stage'] == 'measure' and x['status'] == 'done')
t('…and the halving is recorded', mt['content']['parts']['halved'] >= 2 and mt['content']['parts']['parts'] == 5)

# ---------------- a named stop after repeated truncation; Try again redoes only that part ----------------
CALLS.clear(); MODE['measure'] = 'stop_roof'
JOB.clear()
j3 = start('FICTIONAL parts job: roof too long')
t('the job stops only at the smallest part, naming the element', j3['status'] == 'blocked' and '“Roof”' in j3['error'] and 'cut off' in j3['error'])
pp = j3['part_progress']
t('the page knows which part failed and how many are kept', pp and pp['failed']['label'] == 'Roof' and pp['kept'] >= 2 and pp['text'].startswith('Measuring: element'))
page = cl.get(f'/admin/api/teams/jobs/{j3["id"]}/page').json()
t('the stage tracker shows progress within the stage', next(x for x in page['progress'] if x['key'] == 'measure')['count'].endswith('elements done'))
done_before = [c['payload'] for c in CALLS if 'Measurement' in c['workload'] and 'Roof' not in c['payload'].split('THIS PART')[1]]
CALLS.clear(); MODE['measure'] = 'normal'
r = cl.post(f'/admin/api/teams/jobs/{j3["id"]}/resume', headers=H).json()
again = [c for c in CALLS if 'Measurement' in c['workload']]
mine = lambda c: c['payload'].split('THIS PART: take off ONLY these elements: ')[1].split(', from the DOCUMENTS')[0]
t('Try again starts with the failed part and never redoes the parts already done', mine(again[0]) == 'Roof'
  and not any(x in mine(c) for c in again for x in ('Substructure', 'Frame')) and done_before
  and r['status'] == 'waiting' and len(r['outputs']['measure']['items']) == 10)

# ---------------- progress within a stage while it works ----------------
CALLS.clear(); PROGRESS.clear(); MODE['measure'] = 'normal'
teams.update_member(TID, 'market-trends-qs', {})
JOB['id'] = None
real_in_parts = teams.in_parts


def watching(job, stage, *a, **k):
    JOB['id'] = job['id']
    try: return real_in_parts(job, stage, *a, **k)
    finally: JOB['id'] = None


teams.in_parts = watching
j4 = start('FICTIONAL parts job: progress')
teams.in_parts = real_in_parts
texts = [p['text'] for p in PROGRESS if p]
t('the page shows progress within a stage ("Measuring: element 1 of 5", then "…4 of 5")', 'Measuring: element 1 of 5 (Substructure, Frame, Roof)' in texts
  and 'Measuring: element 4 of 5 (Walls, Finishes)' in texts and any(x.startswith('Pricing: element 1 of 5') for x in texts))

# ---------------- one format retry, then a plain reason with the raw reply ----------------
CALLS.clear(); MODE['measure'] = 'retry'
j5 = start('FICTIONAL parts job: format retry')
roof = [c for c in CALLS if 'Measurement' in c['workload'] and 'ONLY these elements: Substructure, Frame, Roof' in c['payload']]
t('an unreadable answer is asked for once more, "reply with only the JSON in this shape"', len(roof) == 2 and 'Reply with ONLY the JSON, in exactly this shape' in roof[1]['system']
  and '"items"' in roof[1]['system'].split('exactly this shape')[1] and j5['status'] == 'waiting')

CALLS.clear(); MODE['measure'] = 'text'
j6 = start('FICTIONAL parts job: prose')
t('still unreadable: the job stops with a plain reason', j6['status'] == 'blocked' and 'it was text, not the list of measured items' in j6['error'])
page = cl.get(f'/admin/api/teams/jobs/{j6["id"]}/page').json()
fail = next(x for x in page['timeline'] if x['kind'] == 'turn' and x['status'] == 'failed')
t('the start of the reply is kept on the job for "What it replied", with the part', fail['raw_reply'] == 'Still prose, sorry.' and 'Roof' in fail['part'])
t('…at most 500 characters, through check_outbound', len(teams.reply_excerpt('x' * 2000, 'QS')) == 500
  and 'Not kept' in teams.reply_excerpt('key sk-ant-api03-' + 'Z' * 90, 'QS'))

# ---------------- a cut-off price part halves its items ----------------
real_ask = org_research._ask
CUT = []


def cut_ask(prompt, query, provider, workload='', **kw):
    refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
    CUT.append(refs)
    if len(refs) > 3: kw['meta']['truncated'] = True; return '{"rates": [', {}
    return real_ask(prompt, query, provider, workload, **kw)


org_research._ask = cut_ask
MODE['measure'] = 'normal'
j7 = start('FICTIONAL parts job: price halving')
org_research._ask = real_ask
pr = j7['outputs']['price']['items']
t('a price part cut off is halved by items and every item is still priced from its own page', len(pr) == 10 and all(i['rate_source'] == 'web' for i in pr)
  and CUT[0] == [f'Q{n}' for n in range(1, 11)] and sorted(r for x in CUT if len(x) <= 3 for r in x) == sorted(f'Q{n}' for n in range(1, 11)))

# ---------------- the page script ----------------
html = cl.get(f'/admin/teams/{TID}/jobs/{j6["id"]}').text
t('the job page offers Try again, the part progress and a folded "What it replied"', "'Try again'" in html and 'tm-partprog' in html and "'What it replied'" in html)
node = shutil.which('node')
if node:
    js = '\n;\n'.join(re.findall(r'<script>(.*?)</script>', html, re.S))
    f = Path(tempfile.mkdtemp()) / 'page.js'; f.write_text(js, encoding='utf-8')
    res = subprocess.run([node, '--check', str(f)], capture_output=True, text=True, timeout=60)
    t('the page script parses (node --check)', res.returncode == 0 or print(res.stderr[:800]))
