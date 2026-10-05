"""Client demo (the demo Alice): never runs on live Alice, refuses a database it did not fill, builds a fictional team's history
around public facts, marks every page and connector answer as demo, and keeps Stefan's own apps out. No real model or web call;
the organisation and everyone here are made up."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import app, substrate_store as s, demo_instance as D, organisations as O, org_research, mcp_server, apps, knowledge
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

# live Alice: nothing here exists
t('live Alice has no demo page', cl.get('/admin/demo').status_code == 404 and 'Client demo' not in cl.get('/admin/memories').text)
try: D.generate('Fictional Borough Council'); t('live Alice refuses to generate', False)
except ValueError: t('live Alice refuses to generate', True)
try: D.reset(); t('live Alice refuses to reset', False)
except ValueError: t('live Alice refuses to reset', True)

D.ON = True
# the research stand-in: public facts with sources (as Temple's research would store them)
def fake_research(name, website=''):
    O.create(name, 'council', 'A fictional council used for testing.')
    for i, st in enumerate(['The council runs adult social care for 115,000 residents.', 'Its plan prioritises digital services.',
                            'It is investing in a new care management system.', 'Budget pressures require savings of £10m.']):
        O.propose_fact(name, 'purpose' if i < 2 else 'technology', st, 'Public web: example.org', f'https://example.org/p{i}', by='Temple research')
    return {'org': name, 'sources': [{'url': 'https://example.org/p0', 'title': 'Council plan', 'cited': True}]}
org_research.research = fake_research

team = [{'name': n, 'role': r, 'team': 'Digital', 'focus': 'x'} for n, r in [
    ('Ailsa Brodie', 'Head of Digital'), ('Morven Tait', 'Data Protection Officer'), ('Euan Laidlaw', 'Service Manager'),
    ('Kirsty Anderson', 'Finance Business Partner'), ('Rory Elliot', 'Project Manager'), ('Shona Hay', 'Analyst'),
    ('Fraser Scott', 'Social Work Team Lead'), ('Isla Grieve', 'Business Analyst'), ('Callum Turnbull', 'Infrastructure Lead'),
    ('Catriona Young', 'Policy Officer'), ('Lewis Hogg', 'Procurement Lead'), ('Fictional Council', 'Bad name')]]
PLAN = {'summary': 'A fictional council.', 'team': team, 'rule_pack': 'care', 'sensitive_example': 'OFFICIAL-SENSITIVE: draft restructure note',
        'workstreams': [{'name': 'Care system replacement', 'lead': 'Euan Laidlaw', 'summary': 's', 'themes': ['care']},
                        {'name': 'Digital front door', 'lead': 'Ailsa Brodie', 'summary': 's', 'themes': ['web']}],
        'categories': [{'name': 'Social care', 'description': 'care'}, {'name': 'Finance', 'description': 'money'}],
        'tags': [{'name': 'procurement', 'description': 'p'}, {'name': 'data protection', 'description': 'd'}]}
def content(ws, first):
    M = ['prefers weekly stand-ups with frontline service staff', 'keeps all supplier contact through the procurement lead',
         'records every data protection impact assessment before a pilot starts', 'reports progress to the board on the first Tuesday of the month']
    c = {'memories': [{'title': f'{ws}: memory {i}', 'content': f'In {ws} the team {M[i]}.', 'author': 'Shona Hay',
                       'days_ago': 20 + i * 10, 'category': 'Social care', 'tags': ['procurement']} for i in range(4)],
         'decisions': [{'title': f'{ws}: decision {i}', 'decision': ['Buy a cloud-hosted product rather than build in house', 'Run a twelve week pilot in two localities'][i] + f' ({ws})', 'rationale': 'Cheaper and faster', 'options': ['A', 'B'],
                        'revisit': 'Next April', 'author': 'Euan Laidlaw', 'days_ago': 100 + i, 'category': 'Finance'} for i in range(2)],
         'knowledge': [{'kind': 'meeting', 'title': f'{ws}: board meeting', 'summary': 'The board reviewed progress on the programme and agreed next steps.',
                        'author': 'Rory Elliot', 'days_ago': 45, 'category': 'Social care', 'attendees': ['Rory Elliot', 'Nobody Real'],
                        'decisions': ['Proceed'], 'actions': [{'action': 'Draft plan', 'owner': 'Isla Grieve', 'due': '2026-11-01'}]},
                       {'kind': 'note', 'title': f'{ws}: how we work', 'summary': 'Working agreement for the programme team, covering reviews and sign-off.',
                        'author': 'Isla Grieve', 'days_ago': 200, 'category': 'Finance'}],
         'conversations': [{'title': f'{ws}: Copilot chat on options', 'app': 'Microsoft Copilot', 'summary': 'Compared the options for the programme in detail. '
                            'Agreed to brief the board. Noted the risks and dependencies.', 'key_points': ['k'], 'author': 'Kirsty Anderson', 'days_ago': 15}],
         'pending': [{'title': f'{ws}: new idea', 'content': 'Try a pilot with two teams before the wider roll-out next year.', 'author': 'Lewis Hogg'}]}
    if first:
        c['clash'] = {'title': f'{ws}: reverse decision 0', 'decision': 'Drop option 0 and use option C', 'rationale': 'Supplier changed', 'options': ['0', 'C'],
                      'author': 'Ailsa Brodie', 'contradicts': f'{ws}: decision 0'}
        c['replaces'] = {'old_title': f'{ws}: how we work', 'title': f'{ws}: how we work (v2)', 'summary': 'Updated working agreement after the review.',
                         'author': 'Isla Grieve', 'days_ago': 8}
    return c
calls = []
def fake_ask(system, payload, max_tokens=12000):
    calls.append(system[:30])
    if 'design a realistic' in system: return json.loads(json.dumps(PLAN))
    ws = payload.split('This workstream: ')[1].split(',')[0]
    return content(ws, '"clash"' in system)
D._ask_json = fake_ask

g = cl.post('/admin/api/demo/generate', headers=H, json={'org': 'Fictional Borough Council', 'website': 'example.org'}).json()
import time
for _ in range(50):
    sc = cl.get('/admin/api/demo').json()['scenarios'][0]
    if sc['status'] != 'working': break
    time.sleep(0.1)
t('a scenario is generated: research first, then the team, then each workstream', sc['status'] == 'ready' and len(calls) == 3)
print('SCENARIO', sc['status'], sc.get('error'), sc.get('progress'))
names = [m['name'] for m in sc['plan']['team']]
t('every name is fictional: one that looks like the organisation is replaced', 'Fictional Council' not in names and len(set(names)) == len(names))
t('the page shows counts, a sample and the public sources', sc['counts']['memories'] == 8 and sc['facts']['count'] == 4 and sc['facts']['sources'])

# a database the demo did not fill is never loaded over
with s.db() as c: c.execute("DELETE FROM settings WHERE key='demo_instance'")
rid = s._propose_original('Real memory', 'Something real that must not be wiped by a demo', 'User said')['id']
try: D.load_now(sc['id']); t('a database with data the demo did not create is refused', False)
except ValueError as e: t('a database with data the demo did not create is refused', 'did not create' in str(e))
with s.db() as c: c.execute('DELETE FROM records WHERE id=?', (rid,))

r = D.load_now(sc['id'])
t('loading builds the history', r['memories'] == 8 and r['decisions'] == 4 and r['knowledge'] == 4 and r['conversations'] == 2 and r['pending'] == 3)
with s.db() as c:
    approved = c.execute("SELECT count(*) FROM records WHERE status='approved'").fetchone()[0]
    proposed = c.execute("SELECT count(*) FROM records WHERE status='proposed'").fetchone()[0]
    oldest = c.execute("SELECT min(created_at) FROM records").fetchone()[0]
    actors = {r[0] for r in c.execute("SELECT DISTINCT actor FROM activity WHERE actor<>''")}
    blocked = c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked'").fetchone()[0]
    facts = c.execute("SELECT count(*) FROM org_facts WHERE status='approved'").fetchone()[0]
    owners = {r[0] for r in c.execute("SELECT owner FROM record_meta WHERE owner<>''")}
t('history is approved; what is still waiting goes through the gates for real', approved == 12 and proposed == 3)
t('it is spread over months, by the team', oldest < (s.now()[:4] + '-08') and {'Shona Hay', 'Euan Laidlaw'} <= actors and {'Shona Hay', 'Euan Laidlaw'} <= owners)
t('a blocked OFFICIAL-SENSITIVE paste is in the log, as it would really happen', blocked >= 1)
t('the public facts are on the organisation\'s profile', facts == 4)
k = knowledge.listing(status='all', limit=50)['items']
t('an older note has been replaced by a newer one', any(i['status'] in ('replaced', 'superseded', 'archived') for i in k))
t('meeting attendees are only the fictional team', all('Nobody Real' not in (i.get('title', '') + json.dumps(i)) for i in k))
t('the sector rule pack is applied', 'care' in __import__('rule_packs').applied())

# every page and connector answer says demo; Stefan's own apps are not there
page = cl.get('/admin/memories').text
t('every page carries the demo banner naming the organisation', 'demo-banner' in page and 'Fictional Borough Council' in page and 'Client demo' in page)
t('the chat page too', 'demo-banner' in cl.get('/').text)
t('your own apps are not on the demo', cl.get('/admin/health').status_code == 404 and cl.get('/admin/api/health').status_code == 404
  and [a['id'] for a in apps.listing()] == [] and 'Health Insights' not in page)
import importlib
mcp_server.mcp._tool_manager if hasattr(mcp_server.mcp, '_tool_manager') else None
wrapped = mcp_server._marked(lambda: {'records': []})()
t('connector answers carry the demo notice', wrapped.get('demo_notice', '').startswith('DEMO'))
t('the connector is told it is the demo', 'THIS IS THE DEMO ALICE' in mcp_server.build_instructions(True))

# load again: fresh, nothing doubled; reset keeps scenarios and rules
D.load_now(sc['id'])
with s.db() as c: n = c.execute("SELECT count(*) FROM records").fetchone()[0]
t('loading again starts fresh', n == 15)
cl.post('/admin/api/demo/reset', headers=H)
with s.db() as c:
    n = c.execute("SELECT count(*) FROM records").fetchone()[0]; rules = c.execute('SELECT count(*) FROM rules').fetchone()[0]
t('clearing empties the demo but keeps scenarios and rules', n == 0 and rules > 5 and len(cl.get('/admin/api/demo').json()['scenarios']) == 1)
D.ON = False
