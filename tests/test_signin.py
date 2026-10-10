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
t('sign out of Alice: her sign-in cookies are expired, then the signed-out page', r.status_code == 303 and r.headers['location'] == '/signed-out?out=1'
  and any(c.startswith('AppServiceAuthSession=') and ('Max-Age=0' in c or 'expires=' in c.lower()) for c in sc)
  and any(c.startswith('AppServiceAuthSession1=') for c in sc) and all('Path=/' in c and 'Secure' in c and 'HttpOnly' in c for c in sc))
t('it does not send you to Microsoft sign-out', 'login.microsoftonline' not in r.headers['location'] and '/.auth/logout' not in r.headers['location'])
p = cl.get('/signed-out?out=1')
t('signed-out page: plain, no data, offers sign in again and the full sign-out', p.status_code == 200 and 'Signed out of Alice' in p.text
  and 'href="/signed-out?go=1"' in p.text and '/.auth/logout?post_logout_redirect_uri=/signed-out' in p.text and 'no-store' in p.headers.get('cache-control', '')
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
# Each check sets exactly the deployment settings it is about (_util.deployment_settings), so it passes the same way on a PC, in a
# pull request's image and in main's (whose build carries ALICE_REPO_URL).
with _util.deployment_settings():
    vi = version_info({'ALICE_VERSION': '5c49135', 'ALICE_BUILT': '2026-10-04T15:40:00Z', 'CONTAINER_APP_REVISION': 'alice-web--r5c49135',
                       'ALICE_REPO_URL': 'https://github.com/example-org/Alice'})
    t('version: the release code, when it was built, the running revision and a link to the change (the repository is a setting, D-0052)',
      vi['version'] == '5c49135' and vi['revision'] == 'alice-web--r5c49135' and vi['link'] == 'https://github.com/example-org/Alice/commit/5c49135')
    t('version: no repository configured, no link', version_info({'ALICE_VERSION': '5c49135'})['link'] == '')
with _util.deployment_settings(repo_url='https://github.com/example-org/Alice'):
    t('version: the repository from the deployment settings (as the image is built) links the commit',
      version_info({'ALICE_VERSION': '5c49135'})['link'] == 'https://github.com/example-org/Alice/commit/5c49135')
with _util.deployment_settings(file={'repo_url': 'https://github.com/example-org/Alice'}):
    t('version: …or from deployment.json in the data folder', version_info({'ALICE_VERSION': '5c49135'})['link'].endswith('/commit/5c49135'))
with _util.deployment_settings(repo_url='http://insecure.example.org/Alice'):
    t('version: never a link to a repository address that is not https', version_info({'ALICE_VERSION': '5c49135'})['link'] == '')
t('version: on the PC it says local, with no link', version_info({}) == {'version': 'local', 'built': '', 'revision': '', 'link': ''})
t('version: anything odd is not shown', version_info({'ALICE_VERSION': '<script>'})['version'] == 'local')
h = cl.get('/admin/memories').text
t('the menu shows the version at the bottom', 'class="nav-version"' in h and h.index('class="nav-version"') > h.index('aria-label="Console"')
  and '>' + version_info()['version'] + '</b>' in h)


# ---------------- "Sign in to Alice": the front page on /signed-out (the bookmark) ----------------
import re as _re2, shutil, subprocess, tempfile
os.environ.pop('ALICE_TRUST_EASYAUTH', None)
p = cl.get('/signed-out')
page = p.text
t('the front page is "Sign in to Alice" with one primary button, Sign in with Microsoft', p.status_code == 200 and '<title>Sign in to Alice</title>' in page
  and '<h1>Sign in to Alice</h1>' in page and page.count('class="go"') == 1 and '>Sign in with Microsoft</a>' in page
  and 'href="/signed-out?go=1"' in page)
t('…Microsoft asks who you are, every time', 'Microsoft will ask who you are (password, Windows Hello or passkey), every time.' in page)
t('no username, email or password fields: Alice never asks for credentials on her own pages',
  not _re2.search(r'<(input|form|textarea|select)\b', page, _re2.I) and 'type="password"' not in page)
t('the note: padlock, the address, Microsoft\'s own sign-in page, and who may get in',
  'Check the address bar shows a padlock' in page and 'login.microsoftonline.com' in page
  and 'Secured by Microsoft Entra ID. Only approved accounts can open Alice.' in page)
t('Alice\'s look: the shared theme, the Alice mark in the top bar and a padlock badge', '--teal:' in page and 'class="si-bar"' in page
  and '<img src="/static/favicon.png" alt="">ALICE' in page and 'id="si-secure"' in page and '<svg' in page)
t('no host is typed into the page: the badge and the note read it from the page\'s own address', 'location.hostname' in page
  and 'testserver' not in page and 'azurecontainerapps' not in page and 'example.org' not in page)
owner = app.store.owner_name()
t('wording for any user: no owner\'s name, no data', owner.lower() not in page.lower() and 'stefan' not in page.lower() and '@' not in page.replace('@media', ''))
t('holds no data and makes no call except the /me check', page.count('fetch(') == 1 and "fetch('/me'" in page and 'no-store' in p.headers.get('cache-control', ''))
t('on the bare page no signed-out message shows, and the Microsoft sign-out waits for a session', 'id="so-t"' not in page
  and 'id="so-ms" hidden' in page and 'id="so-warn" class="warn" hidden' in page)
t('phone and tablet: a 16 px gutter under 520 px and nothing wider than the screen', '@media(max-width:520px)' in page and 'margin:16px 16px 24px' in page
  and 'name="viewport"' in page)
t('Trouble signing in? still links the reset', 'Trouble signing in?' in page and 'href="/signed-out?reset=1"' in page)

# the existing messages appear above the button when they apply
for q, head in (('out=1', 'Signed out of Alice'), ('everywhere=1', 'Signed out of Alice everywhere')):
    pg = cl.get('/signed-out?' + q).text
    t(f'?{q}: "{head}" shows above the button, with the sign-out of Microsoft offered', f'<b id="so-t">{head}</b>' in pg
      and pg.index('id="so-t"') < pg.index('id="si-go"') and 'id="so-ms">' in pg and 'Sign out of Microsoft in this browser too' in pg)
t('"this browser still has a session" is kept, above the button, shown when /me says so', 'This browser still has an Alice session.' in page
  and page.index('id="so-warn"') < page.index('id="si-go"') and "getElementById('so-warn').hidden=false" in page)

# ?go=1: the sign-in cookies are expired and you go to Alice (Microsoft then asks who you are)
cl.cookies.clear()
for name, val in (('AppServiceAuthSession', 'secret-a'), ('AppServiceAuthSession3', 'secret-b'), ('Nonce', 'secret-n'),
                  ('NonceAbc', 'secret-n2'), ('alice_pref', 'keep')):
    cl.cookies.set(name, val)
r = cl.get('/signed-out?go=1', follow_redirects=False)
sc = r.headers.get_list('set-cookie')
gone = {c.split('=', 1)[0] for c in sc if 'Max-Age=0' in c}
t('?go=1 expires every AppServiceAuth and Nonce cookie for path / and goes to /', r.status_code == 303 and r.headers['location'] == '/'
  and {'AppServiceAuthSession', 'AppServiceAuthSession1', 'AppServiceAuthSession2', 'AppServiceAuthSession3', 'Nonce', 'NonceAbc'} <= gone
  and 'alice_pref' not in gone and all('Path=/' in c and 'Secure' in c for c in sc) and 'no-store' in r.headers.get('cache-control', ''))
cl.cookies.clear()
os.environ['ALICE_TRUST_EASYAUTH'] = '1'
t('the page and ?go=1 open for a session that was signed out everywhere (outside sign-in)', cl.get('/signed-out', headers=old_phone).status_code == 200
  and cl.get('/signed-out?go=1', headers=old_phone, follow_redirects=False).status_code == 303)
os.environ.pop('ALICE_TRUST_EASYAUTH', None)
t('it stays outside sign-in and nothing about sign-in settings changed', _re.search(r"excludedPaths: \['/healthz', '/signed-out', '/hooks/tradingview'\]", bicep) is not None
  and app.permissions.ROUTES['GET /signed-out'] == 'open')

# in a browser: the host shown is the page's own, the button clears any service worker before going on, and only /me is fetched
node = shutil.which('node')
if node:
    script = _re2.findall(r'<script>(.*?)</script>', page, _re2.S)[-1]
    harness = r"""
const calls=[],els={};let nav=null,unreg=0;
class El{constructor(id){this.id=id;this.textContent='';this.hidden=true;this.classList={add:c=>this.cls=c};this.svg={remove:()=>{this.svgGone=true}};this.handlers={};this.href='/signed-out?go=1'}
 querySelector(){return this.svg}addEventListener(k,f){this.handlers[k]=f}}
for(const id of ['si-secure','si-secure-t','si-go','so-warn','so-ms'])els[id]=new El(id);
const hosts=[new El('h1')];
global.document={getElementById:id=>els[id],querySelectorAll:()=>hosts};
global.location={hostname:process.argv[2],protocol:process.argv[3],set href(v){nav=v},get href(){return nav}};
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{serviceWorker:{getRegistrations:async()=>[{unregister:async()=>{unreg++;return true}}]}}});
global.fetch=(u,o)=>{calls.push(u);return Promise.resolve({ok:true,json:async()=>({signed_in:process.argv[4]==='1'})})};
eval(require('fs').readFileSync(process.argv[5],'utf8'));
setTimeout(async()=>{await els['si-go'].handlers.click({preventDefault(){},currentTarget:els['si-go']});
 setTimeout(()=>console.log(JSON.stringify({badge:els['si-secure-t'].textContent,note:hosts[0].textContent,cls:els['si-secure'].cls||'',lock:!els['si-secure'].svgGone,
  calls,nav,unreg,warn:!els['so-warn'].hidden,ms:!els['so-ms'].hidden})),20)},20);
"""
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'page.js'), 'w').write(script); open(os.path.join(d, 'h.js'), 'w').write(harness)
    run = lambda host, proto, signed: json.loads(subprocess.run([node, os.path.join(d, 'h.js'), host, proto, signed, os.path.join(d, 'page.js')],
                                                                capture_output=True, text=True, timeout=60).stdout or '{}')
    a = run('alice-web.fictional-tenant.uksouth.example', 'https:', '0')
    t('in a browser: the badge says Secure connection with the page\'s own host and keeps its padlock',
      a.get('badge') == 'Secure connection · alice-web.fictional-tenant.uksouth.example' and a.get('lock') is True)
    t('…the note names the same host', a.get('note') == 'alice-web.fictional-tenant.uksouth.example')
    t('…Sign in with Microsoft clears any service worker, then goes to ?go=1', a.get('unreg') == 1 and a.get('nav') == '/signed-out?go=1')
    t('…its only request is /me', a.get('calls') == ['/me'])
    t('…no session: no warning and no Microsoft sign-out offered', a.get('warn') is False and a.get('ms') is False)
    b = run('alice-web.fictional-tenant.uksouth.example', 'https:', '1')
    t('a session still in this browser: the warning and the Microsoft sign-out show', b.get('warn') is True and b.get('ms') is True)
    c = run('phish.example.net', 'http:', '0')
    t('an address without https never claims a secure connection', c.get('badge') == 'Not a secure connection · phish.example.net'
      and c.get('lock') is False and c.get('cls') == 'bad')
    l = run('127.0.0.1', 'http:', '0')
    t('on the PC it says this computer only', l.get('badge') == 'This computer only · 127.0.0.1' and l.get('cls') == 'plain')
else:
    print('  (node not installed: the in-browser checks of the sign-in page were skipped)')
