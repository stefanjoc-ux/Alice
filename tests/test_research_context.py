"""What Temple starts from (research_context.py): one function builds the context for organisation research and opportunity
scans; the page's preview and "Show the exact instructions" show what it builds, so what is shown is exactly what is sent.
Proves: the refactor changes nothing (old assembly kept here, frozen, compared with the new); the preview equals what the run
sends, guidance included; client separation and Local only facts are left out of both alike; the preview saves nothing and is
refused for demo data; each run keeps its instructions; Add and research now saves the guidance before the research starts;
the Show brief toggle. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
import substrate_store as s
s.init()
import app, organisations as O, org_research as OR, opportunities as OP, clients as C, temple, search_runs as SR, research_context as RC
import rules_engine as RE
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'claude')
C.create_client('Example Council', ['EC'])
C.create_client('Rival Borough', ['RB'])
O.update('Example Council', website='https://www.examplecouncil.gov.uk')
O.propose_fact('Example Council', 'technology', 'Uses Microsoft 365 across the council since 2021.', 'Council website', 'https://www.examplecouncil.gov.uk/ict')
O.propose_fact('Example Council', 'commercial', 'Shares a procurement framework with Rival Borough for cloud services.', 'Council website', 'https://www.examplecouncil.gov.uk/buy')
O.propose_fact('Example Council', 'structure', 'Runs a local transformation board chaired by the chief executive.', 'Board papers', 'internal', label='local')
SR.set_guidance('Example Council', 'Focus on the digital programmes in the Council Plan 2024-29.')
with s.db() as c:
    for i, (title, status) in enumerate([('Identity tender', 'suggested'), ('Old idea', 'tracking'), ('Lost bid', 'lost')]):
        c.execute('INSERT INTO opportunities(id,org,title,summary,why_now,timing,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                  (f'{i:032x}', 'Example Council', title, 'x', 'news' if i else '', 'Nov' if i else '', status, s.now(), f'2026-10-0{i + 1}'))

# ---------------- the old assembly, frozen as it was before research_context (8 Oct 2026) ----------------
def old_research(name, website=''):
    existing = None
    if name:
        try: existing = O.canonical(name)
        except ValueError: existing = None
    if existing and not website:
        with s.db() as c:
            row = c.execute('SELECT website FROM organisations WHERE name=?', (existing,)).fetchone()
        website = (row['website'] if row and 'website' in row.keys() else '') or ''
    query = ('Research this organisation: ' + (existing or name or '') + (f' (website: {website})' if website else '')).strip()
    prompt = OR.PROMPT.format(today=date.today().isoformat(), kinds=', '.join(O.KINDS), sections=', '.join(OR.PUBLIC_SECTIONS), max_facts=OR.MAX_FACTS)
    gtext, gver = SR.prompt_block(existing) if existing else ('', 0)
    prompt += gtext + ('\n\nAlso return "searches": ["the searches you ran"] in the JSON.')
    return prompt, query, gver


def old_scan(org, p):
    with s.db() as c:
        w = c.execute('SELECT website FROM organisations WHERE name=?', (org,)).fetchone()
        tracked = [dict(r) for r in c.execute("SELECT id,title,status,why_now,timing FROM opportunities WHERE org=? AND status<>'dismissed' ORDER BY updated_at DESC LIMIT 30", (org,))]
    site = (w['website'] if w and 'website' in w.keys() else '') or ''
    open_ = [t_ for t_ in tracked if t_['status'] in OP.OPEN][:15]
    b = O.brief(org, provider=p)
    query = (f'Organisation: {org}' + (f' (website: {site})' if site else '') + '\n\n' + (b['text'] or 'No approved profile facts yet.') +
             ('\n\nALREADY KNOWN OPPORTUNITIES (do not repeat): ' + '; '.join(t_['title'] for t_ in tracked) if tracked else '') +
             ('\n\nOPEN OPPORTUNITIES TO CHECK:\n' + '\n'.join(f"- id {t_['id'][:8]}: {t_['title']} (why it mattered: {t_['why_now'] or '-'}; timing: {t_['timing'] or '-'})"
                                                         for t_ in open_) if open_ else ''))
    gtext, gver = SR.prompt_block(org)
    prompt = OP.PROMPT.format(today=date.today().isoformat(), days=OP.NEWS_DAYS, max_opps=OP.MAX_OPPS, offerings='; '.join(OP.offerings())) + gtext + \
        ('\n\nAlso return, in the same JSON object, "searches": ["the searches you ran"] and "considered": [{"title": "", "reason": '
         '"outside_profile|low_relevance|closed|duplicate", "note": "one sentence"}] for items you looked at but did not suggest.')
    return prompt, query, gver


# The old scan sent facts naming another client; the one deliberate change is that they are now left out under Client separation.
# With Client separation off, old and new must be identical, character for character.
RE.update_rule('client_separation', enabled=False)
same = True
for name, web in [('Example Council', ''), ('EC', ''), ('Example Council', 'https://other.example.org'), ('Brand New Org', 'https://brandnew.example.org'), ('', 'https://only.example.org')]:
    ctx = RC.build('research', name=name, website=web)
    op, oq, ogv = old_research(name, web)
    same = same and ctx.prompt == op and ctx.message(ctx.provider) == oq and ctx.guidance_version == ogv
t('research: the new context is the old prompt and message, character for character (names, aliases, websites, new organisations)', same)
same = True
for p in ('claude', 'openai'):
    ctx = RC.build('scan', org='Example Council')
    op, oq, ogv = old_scan('Example Council', p)
    same = same and ctx.prompt == op and ctx.message(p) == oq and ctx.guidance_version == ogv
t('scan: the new context is the old prompt and message for each provider (brief, known and open opportunities, guidance)', same and 'Rival Borough' in oq)
RE.update_rule('client_separation', enabled=True)

# ---------------- the preview is what the run sends ----------------
N1 = 'https://www.examplecouncil.gov.uk/news'
CALLS = []


def fake(prompt, query, provider, workload='x'):
    CALLS.append((prompt, query, provider, workload))
    if 'opportunit' in workload.lower(): return json.dumps({'news': [], 'opportunities': [], 'checks': []}), {N1: 'News'}
    return json.dumps({'name': 'Example Council', 'facts': [{'section': 'purpose', 'statement': 'Its plan runs to 2029 with a digital first theme.', 'source_url': N1}]}), {N1: 'News'}


OR._ask = fake
pv = cl.post('/admin/api/organisations/context', json={'org': 'Example Council'}, headers=H).json()
rr = cl.post('/admin/api/organisations/research', json={'name': 'Example Council'}, headers=H).json()
RESEARCH_CALL = CALLS[-1]
t('research: the preview shows exactly the instructions and message the run sent', CALLS[-1][0] == pv['research']['system'] and CALLS[-1][1] == pv['research']['message'])
t('…guidance included, in both', 'digital programmes in the Council Plan' in CALLS[-1][0] and 'USER GUIDANCE' in pv['research']['system'])
pv = cl.post('/admin/api/organisations/context', json={'org': 'Example Council'}, headers=H).json()
rs = cl.post('/admin/api/opportunities/scan', json={'org': 'Example Council'}, headers=H).json()
t('scan: the preview shows exactly what the scan sent', CALLS[-1][0] == pv['scan']['system'] and CALLS[-1][1] == pv['scan']['message'])
t('…guidance included, in both', 'digital programmes in the Council Plan' in CALLS[-1][0])
t('a fact naming another client is left out of both, under Client separation', 'Rival Borough' not in CALLS[-1][1] and 'Rival Borough' not in pv['scan']['message']
  and 'Microsoft 365' in CALLS[-1][1] and pv['known']['other_client'] == 1)
t('a Local only fact is left out of both', 'transformation board' not in CALLS[-1][1] and 'transformation board' not in pv['scan']['message'] and pv['known']['local'] == 1)
with s.db() as c:
    logged = c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked' AND rule='client_separation' AND target LIKE 'opportunity scan brief%'").fetchone()[0]
t('the run logs what Client separation left out, as that rule\'s block', logged >= 1)
RE.update_rule('client_separation', enabled=False)
pv2 = cl.post('/admin/api/organisations/context', json={'org': 'Example Council'}, headers=H).json()
OP.scan('Example Council')
t('switched off on the Rules page, both include it again, alike', 'Rival Borough' in pv2['scan']['message'] and CALLS[-1][1] == pv2['scan']['message'])
RE.update_rule('client_separation', enabled=True)
t('the cards: who, what it knows, sections, rules read from the Rules page, the model', pv['who']['client'] and pv['who']['aliases'] == ['EC']
  and pv['who']['website'] == 'https://www.examplecouncil.gov.uk' and pv['known']['approved'] == 3
  and [x['key'] for x in pv['sections']['research']] == OR.PUBLIC_SECTIONS and pv['sections']['not_researched'] == ['Relationship']
  and {r['id']: r['on'] for r in pv['rules']['rules']}['client_separation'] and pv['rules']['model']['id'] == OR.MODELS['claude'][1])
RE.update_rule('pii', enabled=False)
t('a rule switched off shows as off (never hard-coded)', not {r['id']: r['on'] for r in cl.post('/admin/api/organisations/context', json={'org': 'Example Council'}, headers=H).json()['rules']['rules']}['pii'])
RE.update_rule('pii', enabled=True)

# ---------------- each run keeps its instructions ----------------
ins = SR.get(rr['run_id'])['instructions']
t('a research run keeps the exact instructions and message it ran with', ins and ins['system'] == RESEARCH_CALL[0] and ins['message'] == RESEARCH_CALL[1])
ins = SR.get(rs['run_id'])['instructions']
t('so does a scan', ins and ins['message'].startswith('Organisation: Example Council') and 'USER GUIDANCE' in ins['system'])
t('…returned with the run on the page', cl.get('/admin/api/organisations/searches?org=Example Council').json()['runs'][0]['instructions']['system'].startswith('You are Temple'))
OR._ask = lambda *a, **k: (_ for _ in ()).throw(ValueError('boom'))
try: OP.scan('Example Council')
except ValueError: pass
OR._ask = fake
t('a failed run keeps them too', SR.runs('Example Council')[0]['status'] == 'failed' and SR.runs('Example Council')[0]['instructions']['message'].startswith('Organisation:'))

# ---------------- the preview saves nothing ----------------
TABLES = ['activity', 'search_runs', 'org_guidance', 'organisations', 'org_facts', 'org_research', 'opportunities', 'org_watch', 'clients', 'settings', 'agent_runs']


def counts():
    with s.db() as c:
        out = {}
        for tb in TABLES:
            try: out[tb] = c.execute(f'SELECT count(*) FROM {tb}').fetchone()[0]
            except Exception: out[tb] = None
        return out


before = counts()
for body in [{'org': 'Example Council'}, {'org': 'Example Council', 'guidance': 'Compare them with Rival Borough.'},
             {'org': 'Example Council', 'guidance': 'Use sk-ant-api03-' + 'A' * 90},
             {'name': 'Brand New Org', 'website': 'brandnew.example.org', 'aliases': ['BNO'], 'kind': 'charity', 'client': True, 'guidance': 'Look at their annual report.'},
             {'name': 'Leak sk-ant-api03-' + 'B' * 30, 'website': ''}, {'name': 'Bad Site', 'website': 'http://localhost'}]:
    r = cl.post('/admin/api/organisations/context', json=body, headers=H)
t('the preview route saves nothing: no rows, no activity, no blocks logged, no agent runs', counts() == before and r.status_code == 200)
d = cl.post('/admin/api/organisations/context', json={'org': 'Example Council', 'guidance': 'Compare them with Rival Borough.'}, headers=H).json()
t('unsaved guidance naming another client: refused in the preview as it would be on saving', 'Rival Borough' in d['guidance']['error'] and 'Rival Borough' not in d['scan']['system'])
d = cl.post('/admin/api/organisations/context', json={'org': 'Example Council', 'guidance': 'Look at the 2027 budget.'}, headers=H).json()
t('unsaved guidance is shown in the instructions, marked as not saved yet', d['guidance']['draft'] and 'version unsaved' in d['research']['system'] and 'Look at the 2027 budget.' in d['scan']['system'])
d = cl.post('/admin/api/organisations/context', json={'name': 'Brand New Org', 'website': 'brandnew.example.org', 'aliases': ['BNO'], 'kind': 'charity', 'client': True}, headers=H).json()
t('a new organisation: who it is from the form, the message the research will send, no scan yet', not d['who']['exists'] and d['who']['aliases'] == ['BNO']
  and d['research']['message'] == 'Research this organisation: Brand New Org (website: https://brandnew.example.org)' and d['scan'] is None)
d = cl.post('/admin/api/organisations/context', json={'name': 'Leak sk-ant-api03-' + 'B' * 30}, headers=H).json()
t('what the checks would stop is shown as not sent, with the rule\'s own words', 'Secret detection' in d['research']['blocked'])
t('a website that is not public is explained', any('public website' in p for p in cl.post('/admin/api/organisations/context', json={'name': 'Bad Site', 'website': 'http://localhost'}, headers=H).json()['problems']))
t('an existing name says it already exists', any('already exists' in p for p in cl.post('/admin/api/organisations/context', json={'name': 'EC'}, headers=H).json()['problems']))
t('the preview is refused for demo data, like research', cl.post('/admin/api/organisations/context', json={'org': 'Example Council'}, headers={**H, 'x-alice-dataset': 'demo'}).status_code == 400)
t('…and needs the admin token', cl.post('/admin/api/organisations/context', json={'org': 'Example Council'}).status_code in (401, 403))

# ---------------- Add an organisation ----------------
n = len(CALLS)
x = cl.post('/admin/api/organisations/add', headers=H, json={'name': 'Northshire Trust', 'website': 'northshire.example.org', 'aliases': ['NST'], 'kind': 'charity',
                                                              'client': True, 'watch': True, 'guidance': 'Focus on their housing programme.', 'research': True}).json()
t('Add and research now: added with its details, then researched', x['name'] == 'Northshire Trust' and x['research']['status'] == 'complete' and len(CALLS) == n + 1)
t('…the guidance was saved before the research started, so the research used it', SR.current('Northshire Trust') == ('Focus on their housing programme.', 1)
  and 'Focus on their housing programme.' in CALLS[-1][0] and SR.get(x['research']['run_id'])['guidance_version'] == 1)
t('…website, other names, Client and Watch saved', [o for o in O.listing()['organisations'] if o['name'] == 'Northshire Trust'][0]['website'] == 'https://northshire.example.org'
  and 'NST' in C.list_clients()[[c_['name'] for c_ in C.list_clients()].index('Northshire Trust')]['aliases']
  and [w for w in OP.watch_list() if w['org'] == 'Northshire Trust'][0]['frequency'] == 'weekly')
n = len(CALLS)
y = cl.post('/admin/api/organisations/add', headers=H, json={'name': 'Quiet Body', 'kind': 'public body', 'client': True, 'watch': False})
t('Add only: added, nothing researched; a client left unwatched is not scanned', y.status_code == 200 and len(CALLS) == n
  and [w for w in OP.watch_list() if w['org'] == 'Quiet Body'][0]['frequency'] == 'off')
bad = cl.post('/admin/api/organisations/add', headers=H, json={'name': 'Careless Org', 'guidance': 'Compare with Rival Borough.', 'research': True})
t('guidance naming another client: refused before anything is saved', bad.status_code == 400 and not any(o['name'] == 'Careless Org' for o in O.listing()['organisations']))
t('a bad website is refused before anything is saved', cl.post('/admin/api/organisations/add', headers=H, json={'name': 'Local Thing', 'website': 'http://localhost'}).status_code == 400
  and not any(o['name'] == 'Local Thing' for o in O.listing()['organisations']))
t('Add and research now is refused with demo data', cl.post('/admin/api/organisations/add', headers={**H, 'x-alice-dataset': 'demo'}, json={'name': 'Demo Thing', 'research': True}).status_code == 400)
OR._ask = lambda *a, **k: (_ for _ in ()).throw(ValueError('boom'))
z = cl.post('/admin/api/organisations/add', headers=H, json={'name': 'Fails Later', 'guidance': 'Their estates strategy.', 'research': True}).json()
OR._ask = fake
t('a research failure after adding says so; the organisation and its guidance are kept', 'research_error' in z and SR.current('Fails Later')[1] == 1)

# ---------------- the page ----------------
page = cl.get('/admin/organisations').text
t('the page: three steps, the four cards, the exact instructions, the add form with its preview', all(x_ in page for x_ in (
    'What Temple starts from', 'Your guidance', '>Runs <', 'Show the exact instructions Temple will be given', "'Who to research'", "'What it already knows'",
    "'What it looks for'", "'Rules it follows'", 'id="o-n-ctx"', 'Add and research now', 'Add only', 'Ask Temple to suggest guidance', 'used by the next run')))
t('the old add-by-research form is gone', 'id="o-r-go"' not in page and 'id="o-new-save"' not in page)
node = shutil.which('node')
js = '\n;\n'.join(re.findall(r'<script>(.*?)</script>', page, re.S))
if node:
    f = Path(tempfile.mkdtemp()) / 'page.js'; f.write_text(js, encoding='utf-8')
    res = subprocess.run([node, '--check', str(f)], capture_output=True, text=True, timeout=60)
    t('the page script parses (node --check)', res.returncode == 0 or print(res.stderr[:800]))
    i = js.index('function briefToggle('); j = js.index('\n', js.index('return {set,toggle', i))
    f2 = Path(tempfile.mkdtemp()) / 'brief.js'
    f2.write_text(js[i:j] + r"""
const btn={textContent:'Show brief',attrs:{},setAttribute(k,v){this.attrs[k]=v}},out={textContent:'',hidden:false};const saved=[];let calls=0;
const B=briefToggle(btn,out,async()=>{calls++;return 'BRIEF TEXT'},v=>saved.push(v),false);
(async()=>{const r=[];await B.toggle();r.push(btn.textContent==='Hide brief'&&out.textContent==='BRIEF TEXT'&&!out.hidden&&btn.attrs['aria-expanded']==='true'&&saved.at(-1)===true);
 await B.toggle();r.push(btn.textContent==='Show brief'&&out.textContent===''&&out.hidden&&btn.attrs['aria-expanded']==='false'&&saved.at(-1)===false&&calls===1);
 const B2=briefToggle(btn,out,async()=>'AGAIN',v=>saved.push(v),true);await B2.set(B2.on);r.push(B2.on&&btn.textContent==='Hide brief'&&out.textContent==='AGAIN');
 console.log(JSON.stringify(r))})();
""", encoding='utf-8')
    res = subprocess.run([node, str(f2)], capture_output=True, text=True, timeout=60)
    r = json.loads(res.stdout or '[false,false,false]')
    t('Show brief shows it and becomes Hide brief, and remembers', r[0])
    t('Hide brief hides it and becomes Show brief, and remembers', r[1])
    t('a remembered choice opens it again on the next visit', r[2])
t('the choice is remembered per browser, guarded with try/catch', "try{localStorage.setItem('alice-org-brief'" in js and "try{return localStorage.getItem('alice-org-brief')==='1'}catch{return false}" in js)
