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

# signing out of Alice only (not the whole Microsoft session in the browser)
h = cl.get('/admin').text
t('badge offers "Sign out of Alice" first, Microsoft sign-out as the second option', "out.href='/signout'" in h and "post_logout_redirect_uri=/signed-out" in h
  and h.index("'/signout'") < h.index('/.auth/logout'))
cl.cookies.set('AppServiceAuthSession', 'session-value-not-real'); cl.cookies.set('AppServiceAuthSession1', 'part-two')
r = cl.get('/signout', follow_redirects=False)
sc = r.headers.get_list('set-cookie')
t('sign out of Alice: her sign-in cookies are expired, then the signed-out page', r.status_code == 303 and r.headers['location'] == '/signed-out'
  and any(c.startswith('AppServiceAuthSession=') and ('Max-Age=0' in c or 'expires=' in c.lower()) for c in sc)
  and any(c.startswith('AppServiceAuthSession1=') for c in sc) and all('Path=/' in c and 'Secure' in c and 'HttpOnly' in c for c in sc))
t('it does not send you to Microsoft sign-out', 'login.microsoftonline' not in r.headers['location'] and '/.auth/logout' not in r.headers['location'])
p = cl.get('/signed-out')
t('signed-out page: plain, no data, offers sign in again and the full sign-out', p.status_code == 200 and 'Signed out of Alice' in p.text
  and 'href="/"' in p.text and '/.auth/logout?post_logout_redirect_uri=/signed-out' in p.text and 'no-store' in p.headers.get('cache-control', '')
  and 'stefan' not in p.text.lower())
import re as _re
bicep = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'infra', 'main.bicep')).read()
t('every new Alice session asks who you are (not just the browser\'s Microsoft session), sessions last 8 hours',
  "loginParameters: askEverySignIn ? ['prompt=login'] : []" in bicep and 'param askEverySignIn bool = true' in bicep and "timeToExpiration: '08:00:00'" in bicep)
t('only the health check and the signed-out page are outside sign-in', _re.search(r"excludedPaths: \['/healthz', '/signed-out'\]", bicep) is not None)

# sign out everywhere: sessions that signed in before the moment you pressed it must sign in again, on every device
import base64, json as _json, time as _time
def principal(iat):
    c = {'claims': [{'typ': 'name', 'val': 'Stefan'}] + ([{'typ': 'iat', 'val': str(iat)}] if iat else [])}
    return {'x-ms-client-principal-name': 'stefan@example.org', 'x-ms-client-principal': base64.b64encode(_json.dumps(c).encode()).decode()}
A = {'x-admin-token': app.ADMIN_TOKEN}
import substrate_store as s
t('the badge offers sign out on all devices, with the token filled in', 'Sign out of Alice on all devices' in h and '__SIGNIN_TOKEN__' not in h
  and app.ADMIN_TOKEN in h[h.rindex('signout-everywhere') - 2000:h.rindex('signout-everywhere') + 400])
t('on the PC there is nothing to sign out elsewhere', cl.post('/admin/api/signout-everywhere', headers=A).status_code == 400)
import signins
t('device names are plain', signins.device_name('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 Edg/141.0') == 'Edge on Windows'
  and signins.device_name('Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36') == 'Chrome on Android tablet'
  and signins.device_name('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1') == 'Safari on iPhone')
t('on the PC the Sign-ins page says there is nothing to list', cl.get('/admin/api/signins').json()['behind_signin'] is False and cl.get('/admin/signins').status_code == 200
  and 'data-page="signins"' in cl.get('/admin/signins').text)
os.environ['ALICE_TRUST_EASYAUTH'] = '1'
now = int(_time.time())
old_phone, this_pc = principal(now - 3 * 86400), principal(now - 600)
t('before: both devices get in', cl.get('/admin/api/apps', headers={**old_phone}).status_code == 200 and cl.get('/admin/api/apps', headers=this_pc).status_code == 200)
PC_UA = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 Edg/141.0', 'x-forwarded-for': '203.0.113.7, 10.0.0.4'}
TAB_UA = {'user-agent': 'Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36', 'x-forwarded-for': '198.51.100.20'}
tablet = principal(now - 3600)
signins._touched.clear()
cl.get('/admin/api/apps', headers={**this_pc, **PC_UA}); cl.get('/admin/api/apps', headers={**tablet, **TAB_UA})
L = cl.get('/admin/api/signins', headers=this_pc).json()
by = {x['device']: x for x in L['sessions']}
t('Sign-ins lists each device with its address, and which one is this device', {'Edge on Windows', 'Chrome on Android tablet'} <= set(by)
  and by['Edge on Windows']['this_device'] and not by['Chrome on Android tablet']['this_device'] and by['Edge on Windows']['address'] == '203.0.113.7'
  and by['Chrome on Android tablet']['state'] == 'active' and L['can_tell_sessions_apart'])
t('signing out one device needs the admin token', cl.post(f"/admin/api/signins/{by['Chrome on Android tablet']['id']}/signout").status_code == 403)
r = cl.post(f"/admin/api/signins/{by['Chrome on Android tablet']['id']}/signout", headers=A)
t('sign out the tablet: it is turned away, this device carries on', r.status_code == 200 and cl.get('/admin/api/apps', headers={**tablet, **TAB_UA}).status_code == 401
  and cl.get('/admin', headers=tablet, follow_redirects=False).status_code == 303 and cl.get('/admin/api/apps', headers=this_pc).status_code == 200)
t('the tablet shows as signed out', next(x for x in cl.get('/admin/api/signins', headers=this_pc).json()['sessions'] if x['device'] == 'Chrome on Android tablet')['state'] == 'signed_out')
t('an unknown session id is refused', cl.post('/admin/api/signins/' + '0' * 20 + '/signout', headers=A).status_code == 404
  and cl.post('/admin/api/signins/not-an-id/signout', headers=A).status_code == 422)
with s.db() as c: t('signing out a device is logged with the device', 'Chrome on Android tablet' in (c.execute("SELECT detail FROM activity WHERE action='signed_out_device'").fetchone() or [''])[0])
t('needs the admin token', cl.post('/admin/api/signout-everywhere', headers=this_pc).status_code == 403)
t('refused if sign-in gives no sign-in time (nothing changed)', cl.post('/admin/api/signout-everywhere', headers={**A, **principal(0)}).status_code == 400
  and cl.get('/admin/api/apps', headers=old_phone).status_code == 200)
r = cl.post('/admin/api/signout-everywhere', headers={**A, **this_pc})
t('signing out everywhere ends with this device signed out too', r.status_code == 200 and r.json()['next'] == '/signout?everywhere=1')
t('an older session on another device is turned away from the data', cl.get('/admin/api/apps', headers=old_phone).status_code == 401)
r = cl.get('/admin', headers=old_phone, follow_redirects=False)
t('and its pages send it to sign out', r.status_code == 303 and r.headers['location'] == '/signout?everywhere=1')
t('this device too (signed in 10 minutes ago)', cl.get('/admin/api/apps', headers=this_pc).status_code == 401)
t('a fresh sign-in gets in (Entra back-dates the sign-in time by up to 5 minutes)', cl.get('/admin/api/apps', headers=principal(int(_time.time()) - 290)).status_code == 200)
t('sign out and the signed-out page still open for old sessions', cl.get('/signout?everywhere=1', headers=old_phone, follow_redirects=False).headers['location'] == '/signed-out?everywhere=1'
  and 'everywhere' in cl.get('/signed-out?everywhere=1', headers=old_phone).text and cl.get('/healthz', headers=old_phone).status_code == 200)
with s.db() as c: t('signing out everywhere is logged', c.execute("SELECT 1 FROM activity WHERE action='signed_out_everywhere'").fetchone() is not None)
os.environ.pop('ALICE_TRUST_EASYAUTH', None)
t('on the PC the check does nothing', cl.get('/admin/api/apps').status_code == 200)
