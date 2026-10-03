"""Signed-in badge: /me reports the Entra sign-in only when Alice trusts Container Apps sign-in; both top bars carry the badge."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import base64, json, os
def t(label, cond): print(('PASS ' if cond else 'FAIL ') + label)

import app
from fastapi.testclient import TestClient
cl = TestClient(app.app)
claims = base64.b64encode(json.dumps({'claims': [{'typ': 'name', 'val': "Stefan O'Connor"}]}).encode()).decode()
H = {'x-ms-client-principal-name': 'stefan@example.org', 'x-ms-client-principal': claims}

os.environ.pop('ALICE_TRUST_EASYAUTH', None)
t('on the PC (not behind sign-in): this computer only', cl.get('/me').json() == {'signed_in': False})
t('sign-in headers are ignored unless Alice is behind sign-in', cl.get('/me', headers=H).json() == {'signed_in': False})
os.environ['ALICE_TRUST_EASYAUTH'] = '1'
m = cl.get('/me', headers=H).json()
t('behind sign-in: the signed-in name and email', m == {'signed_in': True, 'email': 'stefan@example.org', 'name': "Stefan O'Connor", 'provider': 'Microsoft Entra ID'})
t('no name claim: email only', cl.get('/me', headers={'x-ms-client-principal-name': 'stefan@example.org'}).json()['name'] == '')
t('garbled claims never break it', cl.get('/me', headers={**H, 'x-ms-client-principal': '!!!'}).json()['email'] == 'stefan@example.org')
t('no sign-in header: not signed in', cl.get('/me').json() == {'signed_in': False})
os.environ.pop('ALICE_TRUST_EASYAUTH', None)

for path in ('/', '/admin', '/admin/apps', '/admin/mileage'):
    h = cl.get(path).text
    t(f'{path}: badge under ALICE, outside the home link', 'id="signin"' in h and '<a class="brand-home" href="/"' in h and "fetch('/me'" in h
      and h.count('<a class="brand"') == 0)
