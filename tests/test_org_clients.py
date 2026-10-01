"""Clients merged into Organisations: the Client switch, other names, tagged counts, the old page redirects."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import substrate_store as s
s.init()
import organisations as O, clients as C
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
get = lambda: {o['name']: o for o in cl.get('/admin/api/organisations', headers=H).json()['organisations']}

r = cl.post('/admin/api/organisations', headers=H, json={'name': 'Fife Council', 'kind': 'council', 'client': True, 'aliases': ['Fife', 'FC']})
t('adding an organisation as a client creates the client', r.status_code == 200 and C.names() == ['Fife Council'])
o = get()['Fife Council']
t('the organisation shows client, other names and tagged counts', o['is_client'] and o['aliases'] == ['Fife', 'FC'] and o['tagged'] == {'memories': 0, 'files': 0, 'chats': 0})
t('client detection uses the other names', C.detect('Meeting with FC about Teams') == ['Fife Council'])

cl.post('/admin/api/organisations', headers=H, json={'name': 'Northfield University', 'kind': 'university'})
t('an ordinary organisation is not a client', not get()['Northfield University']['is_client'] and get()['Northfield University']['tagged'] is None)
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Northfield University', 'client': True, 'aliases': ['NU']})
t('ticking Client makes it a client', r.status_code == 200 and 'Northfield University' in C.names() and get()['Northfield University']['aliases'] == ['NU'])
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Fife Council', 'aliases': ['Fife', 'Kingdom of Fife']})
t('other names can be changed without touching the switch', r.status_code == 200 and get()['Fife Council']['aliases'] == ['Fife', 'Kingdom of Fife'])
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Fife Council', 'description': 'Local authority'})
t('saving details alone leaves the client as it is', r.status_code == 200 and get()['Fife Council']['is_client'] and get()['Fife Council']['aliases'] == ['Fife', 'Kingdom of Fife'])

rid = s.propose('Fife Teams rollout', 'Fife Council is moving to Teams Phone.', 'Stefan in a test')['id']
C.tag('memory', [rid], 'Fife Council', 'human')
t('tagged counts follow tags', get()['Fife Council']['tagged']['memories'] == 1)
r = cl.put('/admin/api/organisations', headers=H, json={'name': 'Fife Council', 'client': False})
t('unticking Client returns what became General', r.status_code == 200 and r.json()['no_longer_client']['items'] == 1 and 'Fife Council' not in C.names())
t('the organisation and its profile stay', 'Fife Council' in get() and not get()['Fife Council']['is_client'])
t('its material is General again', C.client_of('memory', rid) == '')

r = cl.post('/admin/api/organisations', headers=H, json={'name': 'Northfield University'})
t('no duplicate of an existing client or organisation', r.status_code == 400)
C.create_client('Legacy Client', ['LC'])
t('a client made elsewhere still appears as an organisation', get()['Legacy Client']['is_client'])

r = cl.get('/admin/clients', follow_redirects=False)
t('the old Clients page sends you to Organisations filtered to clients', r.status_code in (302, 307) and r.headers['location'] == '/admin/organisations?filter=clients')
page = cl.get('/admin/organisations').text
t('client switch, other names and tagging are on the Organisations page', all(x in page for x in ('id="o-client"', 'id="o-aliases"', 'id="o-tagging"', 'id="c-table"', 'id="c-run"')))
t('Clients is no longer in the menu', 'data-page="clients"' not in page)
D = {**H, 'x-alice-dataset': 'demo'}
demo = cl.get('/admin/api/organisations', headers=D).json()['organisations']
first = next(o['name'] for o in demo if not o['is_client'])
r = cl.put('/admin/api/organisations', headers=D, json={'name': first, 'client': True, 'aliases': ['Demo alias']})
t('making a demo organisation a client stays in the demo store', r.status_code == 200 and first not in C.names()
  and next(o for o in cl.get('/admin/api/organisations', headers=D).json()['organisations'] if o['name'] == first)['is_client'])
