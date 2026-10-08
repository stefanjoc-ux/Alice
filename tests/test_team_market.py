"""Digital teams, market trends and a team that learns (Stefan, 8 Oct 2026): the Market Trends QS searches the web (a per-member tool,
switched on or off under Edit team) for current cost trends at the job's location, every finding cited with its date, and may suggest one
market adjustment that is applied, in code, only when the Lead QS accepts it. A team setting "File finished work in" (on/off plus a
category, never created silently) files a short summary of each signed-off job in that category through the normal knowledge checks,
tagged to the job's client and linked to the job; members with that category ticked then see past cost plans, and a client's summary
never reaches another client's job. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import io, json, re, zipfile
import app, substrate_store as s, assistants, org_research, rules_engine, knowledge, clients
import teams, team_qs
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
teams.BACKGROUND = False

# ---------------- the template's defaults; a member never set keeps how it worked ----------------
tpl = {m['id']: m for m in team_qs._template()['members']}
t('the QS template: Market Trends QS on Sonnet 5.5, with web search; the Cost Surveyor with web search', tpl['market-trends-qs']['provider'] == 'claude_sonnet'
  and tpl['market-trends-qs']['tools'] == {'web_search': True} and tpl['cost-surveyor']['tools'] == {'web_search': True})
t('…and "File finished work in" on, suggesting "Quantity surveying"', team_qs._template()['filing'] == {'on': True, 'category': 'Quantity surveying'})
t('a member with no switch set keeps how its stage worked before (Cost Surveyor searches, Market Trends does not)',
  teams.tool_on({}, 'web_search', 'qs_price') and not teams.tool_on({}, 'web_search', 'qs_trends'))

team = teams.from_template('quantity-surveying', name='Market test team')
TID = team['id']
teams.set_autonomy(TID, 'signoff')
tp = cl.get(f'/admin/api/teams/{TID}/page').json()
t('the team page shows the switches and the filing setting, and that the category does not exist yet', tp['tool_switches']['market-trends-qs'] == {'web_search': True}
  and 'Web search' in tp['member_tools']['market-trends-qs'] and tp['filing'] == {'on': True, 'category': 'Quantity surveying', 'exists': False})
t('…and the category is never created silently', 'Quantity surveying' not in [c['name'] for c in s.list_categories()['categories']])

# ---------------- stand-ins ----------------
DOC = 'FICTIONAL hall spec.md'
PLAN = {'plan': 'Measure from the specification.', 'elements': [{'name': 'Walls', 'documents': [DOC]}], 'documents': [{'name': DOC, 'use': 'all'}],
        'location': 'Perth, Scotland', 'summary': 'Planned.', 'note': 'Go.', 'questions': []}
ITEMS = [{'element': 'Walls', 'description': 'Blockwork wall', 'quantity': 100, 'unit': 'm2', 'source': {'document': DOC, 'page': '1'}}]
CALLS, ASKS = [], []
ADJ = {'reply': {'accept': True, 'reason': 'The index evidence is recent and regional.'}}
PAGES = {'https://fictional-prices.example/walls': 'Walls', 'https://fictional-index.example/tpi': 'Fictional tender price index Q3 2026',
         'https://fictional-index.example/scotland': 'Fictional regional costs'}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    payload = messages[0]['content']
    CALLS.append({'workload': workload, 'system': system, 'payload': payload, 'provider': provider})
    if 'Lead QS' in workload and 'SUGGESTED MARKET ADJUSTMENT' in payload: return json.dumps(ADJ['reply'])
    if 'Lead QS' in workload and 'COST PLAN FIGURES' in payload:
        return json.dumps({'accept': True, 'summary': 'A hall.', 'assumptions': [], 'exclusions': ['VAT'], 'risks': [], 'note': 'On.'})
    if 'Lead QS' in workload: return json.dumps(PLAN)
    if 'Measurement' in workload: return json.dumps({'accept': True, 'items': ITEMS, 'summary': '', 'note': 'Price these.'})
    if 'Cost Surveyor' in workload:              # no web search: it cannot cite a page, so it offers a rate with an invented one
        return json.dumps({'rates': [{'ref': 'Q1', 'rate': 75, 'source_url': 'https://invented.example/rate', 'source_date': '2026-01'}]})
    if 'Market Trends' in workload:
        refs = re.findall(r'^(Q\d+) \|', payload.split('RATES USED NOW')[1], re.M)
        return json.dumps({'matches': [{'ref': r, 'history': ['H1']} for r in refs], 'commentary': 'Close to the earlier hall.', 'summary': ''})
    raise AssertionError('unexpected call ' + workload)


MARKET = {'reply': None}


def market_reply(adj_pct=4.0, adj_src='https://fictional-index.example/tpi'):
    return {'findings': [{'finding': 'Tender prices rose 4% in the year to Q3 2026.', 'kind': 'inflation', 'source_url': 'https://fictional-index.example/tpi', 'source_date': '2026-09'},
                         {'finding': 'Scottish costs run slightly above the UK average.', 'kind': 'regional', 'source_url': 'https://made-up.example/x', 'source_date': '2026-08'},
                         {'finding': 'Blocks are scarce.', 'kind': 'materials', 'source_url': 'https://fictional-index.example/scotland', 'source_date': ''}],
            'adjustment': {'pct': adj_pct, 'reasoning': 'Rates are a year old against a 4% rise.', 'source_urls': [adj_src]},
            'commentary': 'Prices are still rising.', 'searches': ['tender price index Scotland 2026']}


def fake_ask(prompt, query, provider, workload='', **kw):
    ASKS.append({'workload': workload, 'query': query, 'kw': {k: v for k, v in kw.items() if k != 'meta'}})
    if 'MEASURED ITEMS IN THIS PART' in query:
        refs = re.findall(r'^(Q\d+) \|', query.split('MEASURED ITEMS IN THIS PART')[1].split('RATE LIBRARY')[0], re.M)
        return json.dumps({'rates': [{'ref': r, 'rate': 80, 'unit': 'm2', 'source_url': 'https://fictional-prices.example/walls', 'source_date': '2026-06'} for r in refs]}), dict(PAGES)
    return json.dumps(MARKET['reply'] or market_reply()), dict(PAGES)


assistants._call = fake_call
org_research._ask = fake_ask


def start(title, client=''):
    body = {'job_type': 'cost-estimate', 'title': title, 'brief': 'A fictional single-storey hall for a community trust, to be estimated.', 'location': 'Perth, Scotland',
            'client': client, 'uploads': [{'name': DOC, 'kind': 'spec', 'text': 'FICTIONAL specification. Page 1: walls.'}]}
    r = cl.post(f'/admin/api/teams/{TID}/jobs', json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def sign_off(j):
    r = cl.post(f'/admin/api/teams/steps/{j["pending"][0]["id"]}', json={'action': 'approve'}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- market trends: cited, dated; the adjustment only when the Lead QS accepts it ----------------
j = start('FICTIONAL market job 1')
mk = j['outputs']['trends']['market']
market_asks = [a for a in ASKS if 'MEASURED ITEMS' not in a['query']]
t('the Market Trends QS searched the web for the job\'s location, with its own model', market_asks and 'LOCATION: Perth, Scotland' in market_asks[-1]['query']
  and market_asks[-1]['kw']['model'] == 'claude-sonnet-5-5')
t('every finding kept cites a page the search returned, with its date; the others are dropped', [f['source_url'] for f in mk['findings']] == ['https://fictional-index.example/tpi']
  and mk['findings'][0]['source_date'] == '2026-09' and mk['dropped'] == 2)
t('the suggested adjustment carries its reasoning and cited sources', mk['adjustment'] == {'pct': 4.0, 'reasoning': 'Rates are a year old against a 4% rise.',
                                                                                           'sources': ['https://fictional-index.example/tpi']})
adj = j['outputs']['adjust']
lead_calls = [c for c in CALLS if 'SUGGESTED MARKET ADJUSTMENT' in c['payload']]
t('the Lead QS decides it (accepted, with its reason)', adj['decision'] == 'accepted' and adj['pct'] == 4.0 and adj['by'] == 'Lead QS' and len(lead_calls) == 1
  and 'do not calculate anything' in lead_calls[0]['payload'])
cp = team_qs.final_plan(j['outputs'])
base = j['outputs']['assemble']['cost_plan']
t('accepted: the adjustment is applied in code on the construction cost, and the totals follow', cp['market_adjustment'] == 320.0 and cp['construction'] == base['construction'] == 8000.0
  and cp['total'] > base['total'] and cp == team_qs.compute(j['outputs']['price']['items'], 1.0, base['percentages'], 4.0))
pg = cl.get(f'/admin/api/teams/jobs/{j["id"]}/page').json()
t('the job page shows the adjustment in the totals', pg['view']['plan']['totals']['market_adjustment'] == 320.0)
w = zipfile.ZipFile(io.BytesIO(cl.get('/documents/' + next(d['id'] for d in j['outputs']['documents'] if d['name'].endswith('.docx')) + '/download').content)).read('word/document.xml').decode()
t('the Word cost plan shows the market evidence with dates and the Lead QS\'s decision', 'Market adjustment (+4%, accepted by the Lead QS)' in w
  and 'fictional-index.example/tpi' in w and 'dated 2026-09' in w and 'Lead QS accepted it' in w)

ADJ['reply'] = {'accept': False, 'reason': 'The rates are already current.'}
j2 = start('FICTIONAL market job 2')
cp2 = team_qs.final_plan(j2['outputs'])
t('rejected by the Lead QS: nothing is applied', j2['outputs']['adjust']['decision'] == 'rejected' and cp2['market_adjustment'] == 0.0
  and cp2 == j2['outputs']['assemble']['cost_plan'])
MARKET['reply'] = market_reply(adj_pct=60)
j3 = start('FICTIONAL market job 3')
t('an adjustment out of range is reported, never passed to the Lead QS', j3['outputs']['trends']['market']['adjustment'] is None
  and 'outside' in j3['outputs']['trends']['market']['adjustment_refused']['reason'] and j3['outputs']['adjust']['decision'] == 'none')
MARKET['reply'] = market_reply(adj_src='https://made-up.example/x')
j4 = start('FICTIONAL market job 4')
t('an adjustment resting on no returned page is not passed on', j4['outputs']['trends']['market']['adjustment'] is None
  and 'no source' in j4['outputs']['trends']['market']['adjustment_refused']['reason'])
MARKET['reply'] = None
ADJ['reply'] = {'accept': True, 'reason': 'Agreed.'}

# ---------------- web search switched off per member ----------------
r = cl.put(f'/admin/api/teams/{TID}/members/market-trends-qs', json={'tools': {'web_search': False}}, headers=H)
t('switching web search off is a team change (versioned)', r.status_code == 200 and 'tools' in teams.versions(TID)[0]['what']
  and cl.get(f'/admin/api/teams/{TID}/page').json()['tool_switches']['market-trends-qs'] == {'web_search': False})
ASKS.clear()
j5 = start('FICTIONAL market job 5')
t('…then the Market Trends QS makes no web search, and no adjustment is suggested', not any('MEASURED ITEMS' not in a['query'] for a in ASKS)
  and j5['outputs']['trends']['market'] is None and j5['outputs']['adjust']['decision'] == 'none')
cl.put(f'/admin/api/teams/{TID}/members/market-trends-qs', json={'tools': {'web_search': True}}, headers=H)
cl.put(f'/admin/api/teams/{TID}/members/cost-surveyor', json={'tools': {'web_search': False}}, headers=H)
ASKS.clear(); CALLS.clear()
j6 = start('FICTIONAL market job 6')
t('the Cost Surveyor with web search off prices without searching: no page, so the item is unpriced, never invented',
  not any('MEASURED ITEMS' in a['query'] for a in ASKS) and any('Cost Surveyor' in c['workload'] and 'WEB SEARCH IS SWITCHED OFF' in c['system'] for c in CALLS)
  and j6['outputs']['price']['items'][0]['rate_source'] == 'unpriced')
cl.put(f'/admin/api/teams/{TID}/members/cost-surveyor', json={'tools': {'web_search': True}}, headers=H)

# ---------------- filing finished work ----------------
done = sign_off(j)
t('the category does not exist: sign-off saves the full cost plan, not filed, and says why', done['status'] == 'done' and done['outputs']['filed']['category'] == ''
  and 'does not exist yet' in done['outputs']['filed']['not_filed'])
t('the page offers to create it; the button creates it', cl.post(f'/admin/api/teams/{TID}/filing/category', headers=H).json()['exists']
  and 'Quantity surveying' in [c['name'] for c in s.list_categories()['categories']])
r = cl.put(f'/admin/api/teams/{TID}/filing', json={'on': True, 'category': ''}, headers=H)
t('filing on needs a category', r.status_code == 400)
clients.create_client('Fictional Client A')
clients.create_client('Fictional Client B')
ja = start('FICTIONAL market job for client A', client='Fictional Client A')
da = sign_off(ja)
kid = da['knowledge_id']
with s.db() as c:
    meta = dict(c.execute('SELECT * FROM knowledge_meta WHERE file_id=?', (kid,)).fetchone())
    text = c.execute('SELECT text FROM files WHERE id=?', (kid,)).fetchone()[0]
t('on sign-off the team proposes a short summary, filed in the home category (a draft through the usual approval path)',
  da['outputs']['filed'] == {'category': 'Quantity surveying', 'knowledge_id': kid} and meta['category'] == 'Quantity surveying' and meta['status'] == 'draft'
  and meta['title'].startswith('Cost plan summary: FICTIONAL market job for client A'))
t('…with scope, location, date, total, rates and their sources, estimates and unpriced items, and a link to the job',
  'Scope: A fictional single-storey hall' in text and 'Location: Perth, Scotland' in text and 'Signed off:' in text and 'Total excluding VAT: £' in text
  and 'RATE | Q1 | Blockwork wall | m2 | 80.0 | web | https://fictional-prices.example/walls | 2026-06' in text and 'Left unpriced: none' in text
  and f'/admin/teams/{TID}/jobs/{ja["id"]}' in text and 'market adjustment +4% accepted' in text)
item = next(i for i in knowledge.listing(status='draft', limit=1000)['items'] if i['id'] == kid)
t('…tagged to the job\'s client', item.get('client') == 'Fictional Client A')
real_check = rules_engine.check_knowledge
rules_engine.check_knowledge = lambda title, text: (_ for _ in ()).throw(rules_engine.RuleViolation('Blocked by a knowledge check.'))
jx = start('FICTIONAL market job refused by a check')
dx = sign_off(jx)
rules_engine.check_knowledge = real_check
t('it goes through the normal knowledge checks: a refusal files nothing, the job is still signed off', dx['status'] == 'done' and not dx['knowledge_id'])

jg = start('FICTIONAL market job, General')
sign_off(jg)
# make the filed summaries active, as an approval would
for x in knowledge.listing(status='draft', limit=1000)['items']:
    if x['title'].startswith('Cost plan summary'): knowledge.update(x['id'], status='active')
ASKS.clear()
jb = start('FICTIONAL market job for client B', client='Fictional Client B')
price_q = [a['query'] for a in ASKS if 'MEASURED ITEMS' in a['query']][-1]
t('a member with the category ticked sees past cost plans as knowledge (the Cost Surveyor, for comparison only)', 'PAST COST PLANS IN ALICE' in price_q
  and 'never a rate source' in price_q and 'Cost plan summary: FICTIONAL market job, General' in price_q)
t('…but never another client\'s: client A\'s summary stays out of client B\'s job', 'client A' not in price_q)
hist_b = team_qs.history(teams._row(jb['id']), teams._member(teams.get(TID), 'market-trends-qs'))
t('Market Trends compares with the filed summaries (General), never client A\'s', any('FICTIONAL market job, General' in h['source'] for h in hist_b)
  and not any('client A' in h['source'] for h in hist_b))
t('…and with that history it compares the rates too (the second check)', jb['outputs']['trends']['history'] > 0 and jb['outputs']['trends']['comparisons'])

# ---------------- the page ----------------
html = cl.get(f'/admin/teams/{TID}').text
t('the team page has the filing panel and the per-member tools', 'File finished work in' in html and "field('Tools',tools)" in html)
import shutil, subprocess, tempfile
from pathlib import Path
node = shutil.which('node')
if node:
    for url in (f'/admin/teams/{TID}', f'/admin/teams/{TID}/jobs/{j["id"]}'):
        js = '\n;\n'.join(re.findall(r'<script>(.*?)</script>', cl.get(url).text, re.S))
        f = Path(tempfile.mkdtemp()) / 'page.js'; f.write_text(js, encoding='utf-8')
        res = subprocess.run([node, '--check', str(f)], capture_output=True, text=True, timeout=60)
        t(f'the page script parses (node --check): {url.rsplit("/", 1)[-1][:8]}', res.returncode == 0 or print(res.stderr[:800]))
