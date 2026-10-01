"""Organisations: demo data kept apart from live data, account managers, and the new page layout."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import substrate_store as s
s.init()
import organisations as O, demo_data, clients as C
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}; D = {**H, 'x-alice-dataset': 'demo'}

C.create_client('Example Council', ['EC'])
O.propose_fact('Example Council', 'technology', 'Uses Microsoft 365 across the council since 2021.', 'Council website', 'https://www.examplecouncil.gov.uk/ict')

live = cl.get('/admin/api/organisations', headers=H).json()
t('live shows only real organisations', [o['name'] for o in live['organisations']] == ['Example Council'] and live['demo'] is False)
demo = cl.get('/admin/api/organisations', headers=D).json()
names = [o['name'] for o in demo['organisations']]
t('demo shows the fictional set, not the real one', demo['demo'] is True and len(names) >= 12 and 'Example Council' not in names)
t('demo organisations have account managers', len(demo['managers']) >= 3 and all(o['account_manager'] for o in demo['organisations'] if o['is_client']))
t('demo websites are reserved example domains', all(not o['website'] or '.example.' in o['website'] for o in demo['organisations']))
first = names[0]
t('a demo organisation is not found in live', cl.get('/admin/api/organisations/facts?org=' + first + '&status=all', headers=H).status_code in (400, 404))
t('demo has facts to review', any(o['facts']['proposed'] for o in demo['organisations']))
opp = cl.get('/admin/api/opportunities', headers=D).json()
t('demo has opportunities with account managers', opp['opportunities'] and all('account_manager' in o for o in opp['opportunities']))
t('live has no demo opportunities', not cl.get('/admin/api/opportunities', headers=H).json()['opportunities'])

r = cl.post('/admin/api/organisations/research', headers=D, json={'name': 'Anywhere Council'})
t('research is refused for demo data', r.status_code == 400 and 'demo' in r.text.lower())
r = cl.post('/admin/api/opportunities/scan', headers=D, json={'org': first})
t('opportunity scans are refused for demo data', r.status_code == 400 and 'demo' in r.text.lower())

r = cl.put('/admin/api/organisations', headers=D, json={'name': first, 'account_manager': 'Test Person'})
t('editing demo data works', r.status_code == 200 and next(o for o in cl.get('/admin/api/organisations', headers=D).json()['organisations'] if o['name'] == first)['account_manager'] == 'Test Person')
r = cl.post('/admin/api/organisations', headers=D, json={'name': 'Demo Only Trust', 'kind': 'charity'})
t('adding to demo data stays in demo', r.status_code == 200 and 'Demo Only Trust' not in [o['name'] for o in cl.get('/admin/api/organisations', headers=H).json()['organisations']])
with s.db() as c:
    t('the live database has no demo rows', c.execute("SELECT count(*) FROM organisations WHERE name='Demo Only Trust'").fetchone()[0] == 0)

r = cl.post('/admin/api/demo-data/reset', headers=H)
after = cl.get('/admin/api/organisations', headers=D).json()['organisations']
t('reset restores the fictional set', r.status_code == 200 and 'Demo Only Trust' not in [o['name'] for o in after]
  and next(o for o in after if o['name'] == first)['account_manager'] != 'Test Person')
t('ensure is a no-op when the demo store is current', demo_data.ensure() is False)
with s.dataset('demo'):
    with s.db() as c: c.execute("UPDATE settings SET value='stale' WHERE key='demo_schema'")
t('a changed live schema rebuilds the demo store', demo_data.ensure() is True and demo_data.ensure() is False)
t('the header only switches the two demo pages', 'Example Council' in cl.get('/admin/api/clients', headers=D).text)
with s.db() as c: live_rules = c.execute('SELECT count(*) FROM rules').fetchone()[0]
with s.dataset('demo'):
    with s.db() as c: demo_rules = c.execute('SELECT count(*) FROM rules').fetchone()[0]
t('demo store keeps the same rules as live', live_rules > 0 and demo_rules == live_rules)

# account managers
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Example Council', 'account_manager': "Morven O'Hay-Reid"})
t('an account manager can be set', r.status_code == 200 and cl.get('/admin/api/organisations', headers=H).json()['organisations'][0]['account_manager'] == "Morven O'Hay-Reid")
t('managers are listed for the filter', cl.get('/admin/api/organisations', headers=H).json()['managers'] == ["Morven O'Hay-Reid"])
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Example Council', 'account_manager': 'someone@example.com'})
t('an account manager must be a name, not an address', r.status_code == 400)
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Example Council', 'account_manager': ''})
t('an account manager can be cleared', r.status_code == 200 and cl.get('/admin/api/organisations', headers=H).json()['organisations'][0]['account_manager'] in ('', None))
with s.db() as c:
    cols = [r['name'] for r in c.execute('PRAGMA table_info(organisations)')]
t('a column is reserved for the Entra ID object ID', 'account_manager_oid' in cols)

page = cl.get('/admin/organisations').text
t('the page has the grouped list, filters and collapsible sections', all(x in page for x in ('id="o-list"', 'id="o-filter"', 'id="o-f-mgr"', 'data-sec="facts"', 'id="o-mgr"', 'id="o-demo"')))
t('the page sends the demo header only when demo data is on', "X-Alice-Dataset':'demo'" in page and "window.ALICE_DATASET==='demo'" in page)
t('global demo mode includes Organisations', "DEMO_PAGES=['agents','rule-packs','organisations']" in page)
