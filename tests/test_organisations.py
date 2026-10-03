"""Organisation profiles: summarised facts with source pointers, approval, review dates, data minimisation,
lineage removal, the brief models receive (labels, providers, external apps), and the MCP tools."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import asyncio, json
from datetime import date, timedelta
import substrate_store as s, temple, clients as C, rules_engine as R, knowledge as K, organisations as O, actions
temple.save_settings(False, 'openai')
import app, mcp_server as M
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
C.create_client('Scottish Borders Council', ['SBC'])

# 1. organisations: clients included automatically; your own added here
O.create('Tuduma', 'company', "Stefan's former business tenant")
names = {o['name']: o for o in O.listing()['organisations']}
t('client listed as an organisation automatically', names['Scottish Borders Council']['is_client'])
t('own organisation listed, not a client', names['Tuduma']['kind'] == 'company' and not names['Tuduma']['is_client'])
t('client alias resolves', O.canonical('SBC') == 'Scottish Borders Council')
try: O.canonical('Nowhere Ltd'); t('unknown organisation refused', False)
except ValueError: t('unknown organisation refused', True)

# 2. facts: summaries with source pointers and review dates
add = lambda org, sec, text, **kw: cl.post('/admin/api/organisations/facts', json={'org': org, 'section': sec, 'statement': text,
                                           'source_system': kw.pop('system', 'Council Plan 2024-28 (public website)'), **kw}, headers=H)
r = add('SBC', 'security', 'Works at OFFICIAL; aligns to the NCSC Cyber Assessment Framework and holds Cyber Essentials Plus.',
        source_ref='https://example.org/council-plan').json()
f = O.facts('SBC')[0]
t('your fact is approved at once, on the client', r['status'] == 'approved' and f['org'] == 'Scottish Borders Council')
t('default review date about 12 months ahead', date.fromisoformat(f['review_by']) - date.today() > timedelta(days=360))
t('as-of defaults to today and source pointer kept', f['as_of'] == date.today().isoformat() and f['source_ref'].startswith('https://'))
for label, body, expect in [
        ('long text refused (summaries, not documents)', {'statement': 'x' * 401}, ''),
        ('missing source refused', {'source_system': ''}, ''),
        ('review date beyond 24 months refused', {'review_by': (date.today() + timedelta(days=800)).isoformat()}, '24 months'),
        ('past review date refused', {'review_by': '2020-01-01'}, 'future'),
        ('unknown section refused', {'section': 'gossip'}, 'Section')]:
    b = {'org': 'SBC', 'section': 'purpose', 'statement': 'Council priority is a fair and thriving economy.', 'source_system': 'Council Plan', **body}
    x = cl.post('/admin/api/organisations/facts', json=b, headers=H)
    t(f'{label} ({x.status_code})', x.status_code in (400, 422) and expect.lower() in x.text.lower())
t('duplicate recognised', add('SBC', 'security', 'Works at OFFICIAL; aligns to the NCSC Cyber Assessment Framework and holds Cyber Essentials Plus.').json()['duplicate'])

# 3. data minimisation and the other security rules
for label, text in [('email address', 'Service requests go to it.helpdesk@example.gov.uk for triage.'),
                    ('phone number', 'The service desk is on 01896 662787 during office hours.'),
                    ('special category about a person', 'Cllr Smith is off with a mental health condition until spring.'),
                    ('NI number', 'Payroll lead reference AB 12 34 56 C for the pilot.'),
                    ('secret', 'Tenant key sk-proj-' + 'a' * 48 + ' used for the integration.'),
                    ('protective marking', 'OFFICIAL-SENSITIVE briefing on the restructure.')]:
    x = add('SBC', 'structure', text)
    t(f'blocked: {label}', x.status_code == 400 and 'Blocked' in x.text)
t('organisational wording about services is fine', add('SBC', 'purpose', 'Priorities include mental health services, disability access and child poverty.').status_code == 200)
t('a named role holder is fine', add('SBC', 'structure', 'The Chief Digital Officer leads IT strategy; the SIRO sits with the Director of Resources.').status_code == 200)
with s.db() as c: n = c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked' AND rule='data_minimisation'").fetchone()[0]
t('minimisation blocks logged', n == 3)
R.update_rule('data_minimisation', new_params={'review_months': 6})
x = add('Tuduma', 'identity', 'Small Microsoft cloud consultancy tenant, now used for personal projects.', system='Stefan').json()
t('review period follows the rule setting', date.fromisoformat(x['review_by']) - date.today() < timedelta(days=190))

# 4. models propose; you approve (rules re-checked)
M.CLIENT = 'Claude Desktop'
p = M.propose_org_fact(organisation='SBC', section='commercial', statement='Buys IT services mainly through Scottish Government national frameworks.',
                       source_system='Procurement strategy (public website)', source_ref='https://example.org/procurement')
t('model fact is a proposal', p['status'] == 'proposed' and 'approves it' in p['message'])
t('proposal recorded with provenance', O.facts('SBC', 'proposed')[0]['proposed_by'] == 'model via Claude Desktop')
a = {x['key']: x for x in actions.summary()['sections']}
t('Actions lists it', any(i['type'] == 'orgfact' and i['id'] == p['id'] for i in a['waiting']['items']))
t('not in the brief until approved', 'Scottish Government national frameworks' not in O.brief('SBC')['text'])
cl.post('/admin/api/organisations/facts/review', json={'ids': [p['id']], 'decision': 'approved'}, headers=H)
t('approved via API, now in the brief', 'Scottish Government national frameworks' in O.brief('SBC')['text'])
try: M.propose_org_fact(organisation='SBC', section='structure', statement='Contact the CIO on 07700 900123 for anything urgent.', source_system='Email'); t('model cannot propose personal data', False)
except ValueError as e: t('model cannot propose personal data', 'Data minimisation' in str(e))

# 5. the brief: compact, sourced, labels and providers respected
add('SBC', 'technology', 'Microsoft 365 E5 tenant; identity in Entra ID with a hybrid AD estate.', system='Dataverse', source_ref='account/SBC', label='internal')
add('SBC', 'relationship', 'Internal note: incumbent is renewing in spring 2027.', system='Stefan', label='local')
b = O.brief('SBC', 'claude')
t('brief groups by section with sources', 'SECURITY AND COMPLIANCE' in b['text'] and '[Council Plan 2024-28 (public website): https://example.org/council-plan; as of' in b['text'])
t('Local only never in a brief', 'incumbent is renewing' not in b['text'])
t('Internal facts withheld from Grok (Provider allow-list labels)', 'Entra ID' in b['text'] and 'Entra ID' not in O.brief('SBC', 'grok')['text'])
t('client-confidential facts never to external apps', (O.update_fact(O.facts('SBC', section='technology')[0]['id'], label='client'), 'Entra ID' not in O.brief('SBC', 'copilot', external=True)['text'])[1]
  and 'Entra ID' in O.brief('SBC', 'claude')['text'])
t('same facts give the same brief (caches well)', O.brief('SBC', 'claude')['version'] == O.brief('SBC', 'claude')['version'])
for i in range(80): O.propose_fact('Tuduma', 'vocabulary', f'Term number {i}: a programme name used in internal planning documents.', 'Stefan', by='you')
tb = O.brief('Tuduma', 'claude')
t('brief kept within its budget, with a note', len(tb['text']) <= O.BRIEF_CHARS + 120 and 'more facts not shown' in tb['text'])
R.update_rule('client_separation', new_params={'strict': False, 'external': 'general'})
t('client separation "General only" keeps client organisations from external apps', O.brief('SBC', 'copilot', external=True)['text'] == '' and O.brief('Tuduma', 'copilot', external=True)['text'])
R.update_rule('client_separation', new_params={'strict': False, 'external': 'all'})

# 6. MCP tool as Claude Desktop sees it
g = M.get_organisation(name='SBC', section='security')
t('get_organisation returns the profile for one section', 'NCSC Cyber Assessment Framework' in g['profile'] and 'TECHNOLOGY' not in g['profile'])
t('get_organisation on an organisation without facts', M.get_organisation(name='Tuduma', section='values')['profile'] == '')
M.CLIENT = ''

# 7. web chat: a client-tagged chat gets the brief in its instructions
import inspect
src = inspect.getsource(app)
t('chat pipeline adds the client brief', 'organisations.brief(chat_owner, provider)' in src)

# 8. lineage: remove everything derived from a source
m = cl.get('/admin/api/organisations/source', params={'source_system': 'council plan 2024-28 (public website)', 'source_ref': 'HTTPS://example.org/council-plan'}, headers=H).json()['facts']
t('facts traced to their source (case-insensitive)', len(m) == 1)
t('without a reference, every fact from that system matches', len(O.by_source('Council Plan 2024-28 (public website)')) == 3)
x = cl.post('/admin/api/organisations/remove-source', json={'source_system': 'Council Plan 2024-28 (public website)', 'source_ref': 'https://example.org/council-plan', 'reason': 'erasure request'}, headers=H).json()
t('removed, kept in history as retired', x['removed'] == 1 and O.facts('SBC', 'retired')[0]['retired_reason'].startswith('Source removed'))
t('retired fact gone from the brief', 'NCSC Cyber Assessment Framework' not in O.brief('SBC', 'claude')['text'])

# 9. review dates: overdue facts flagged to models
fid = O.facts('SBC', section='commercial')[0]['id']
with s.db() as c: c.execute("UPDATE org_facts SET review_by='2020-01-01' WHERE id=?", (fid,))
t('overdue fact marked in the brief', 'review overdue' in O.brief('SBC', 'claude')['text'])
t('overdue counted on the page', {o['name']: o for o in O.listing()['organisations']}['Scottish Borders Council']['facts']['due'] == 1)
t('retire needs a reason', cl.post(f'/admin/api/organisations/facts/{fid}/retire', json={'reason': ''}, headers=H).status_code == 422)
t('retire works', cl.post(f'/admin/api/organisations/facts/{fid}/retire', json={'reason': 'Framework changed'}, headers=H).json()['status'] == 'retired')
with s.db() as c: acts = {r[0] for r in c.execute('SELECT DISTINCT action FROM activity')}
t('activity log names organisation events', {'org_fact_added', 'org_fact_proposed', 'org_fact_approved', 'org_fact_retired', 'org_source_removed'} <= acts)
