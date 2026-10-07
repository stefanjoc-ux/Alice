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
  "loginParameters: askEverySignIn ? ['prompt=login', 'domain_hint=organizations'] : ['domain_hint=organizations']" in bicep and 'param askEverySignIn bool = true' in bicep and "timeToExpiration: '08:00:00'" in bicep)
t('only the health check, the signed-out page and the TradingView webhook are outside sign-in',
  _re.search(r"excludedPaths: \['/healthz', '/signed-out', '/hooks/tradingview'\]", bicep) is not None)

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

# background requests never start their own Microsoft sign-in (they would overwrite the one you are doing)
for path in ('/', '/admin', '/admin/memories', '/admin/signins'):
    h = cl.get(path).text
    t(f'{path}: background requests say so (sign-in answers 401, not a new sign-in)', "h.set('X-Requested-With','XMLHttpRequest')" in h
      and h.index('window.__aliceFetch') < (h.index("api(") if "api(" in h else len(h)) and 'Your Alice session has ended.' in h)
sw = cl.get('/sw.js').text
t('the service worker is retired: it removes itself and reloads the pages it controlled',
  'self.registration.unregister()' in sw and 'skipWaiting' in sw and '.navigate(' in sw and "addEventListener('fetch'" not in sw
  and 'Tailscale' not in sw and 'offline' not in sw.lower())
t('the chat page no longer installs a service worker', 'serviceWorker.register' not in cl.get('/').text)

# sign-in reset on this device (the signed-out page is outside sign-in, so it works while sign-in loops)
p = cl.get('/signed-out')
t('signed-out page offers the sign-in reset', 'Trouble signing in?' in p.text and 'href="/signed-out?reset=1"' in p.text)
cl.cookies.clear()
for name, val in (('AppServiceAuthSession', 'secret-session-AAA'), ('AppServiceAuthSession2', 'secret-chunk-BBB'),
                  ('Nonce', 'secret-nonce-CCC'), ('alice_pref', 'keep-me-DDD')):
    cl.cookies.set(name, val)
r = cl.get('/signed-out?reset=1')
sc = r.headers.get_list('set-cookie')
expired = {c.split('=', 1)[0] for c in sc if 'Max-Age=0' in c or 'expires=' in c.lower()}
t('reset: every AppServiceAuth cookie and the Nonce cookie are expired for path /',
  r.status_code == 200 and {'AppServiceAuthSession', 'AppServiceAuthSession1', 'AppServiceAuthSession2', 'AppServiceAuthSession3', 'Nonce'} <= expired
  and all('Path=/' in c for c in sc))
t('reset: other cookies are left alone', 'alice_pref' not in expired)
t('reset: lists the names it found and their count, never a value',
  'AppServiceAuthSession2' in r.text and '>Nonce<' in r.text and 'data-count="3"' in r.text and 'cleared 3 sign-in cookies' in r.text
  and 'secret-' not in r.text and 'keep-me' not in r.text and 'alice_pref' not in r.text)
t('reset: removes any service worker and offers sign in', 'getRegistrations()' in r.text and '.unregister()' in r.text
  and '>Sign in to Alice</a>' in r.text and 'no-store' in r.headers.get('cache-control', ''))
cl.cookies.clear()
r = cl.get('/signed-out?reset=1')
t('reset with nothing to clear says so', 'Found 0 sign-in cookies' in r.text and 'data-count="0"' in r.text)
os.environ['ALICE_TRUST_EASYAUTH'] = '1'
t('reset still opens for a session signed out everywhere', cl.get('/signed-out?reset=1', headers=old_phone).status_code == 200)
os.environ.pop('ALICE_TRUST_EASYAUTH', None)

# which release is running, at the bottom of the Console menu
from ui_theme import version_info
vi = version_info({'ALICE_VERSION': '5c49135', 'ALICE_BUILT': '2026-10-04T15:40:00Z', 'CONTAINER_APP_REVISION': 'alice-web--r5c49135'})
t('version: the release code, when it was built, the running revision and a link to the change',
  vi['version'] == '5c49135' and vi['revision'] == 'alice-web--r5c49135' and vi['link'] == 'https://github.com/stefanjoc-ux/Alice/commit/5c49135')
t('version: on the PC it says local, with no link', version_info({}) == {'version': 'local', 'built': '', 'revision': '', 'link': ''})
t('version: anything odd is not shown', version_info({'ALICE_VERSION': '<script>'})['version'] == 'local')
h = cl.get('/admin/memories').text
t('the menu shows the version at the bottom', 'class="nav-version"' in h and h.index('class="nav-version"') > h.index('aria-label="Console"')
  and '>' + version_info()['version'] + '</b>' in h)
