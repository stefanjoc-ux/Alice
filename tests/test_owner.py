"""The owner of Alice: Entra decides (Stefan, 9 Oct 2026), through ONE shared check (users.is_owner, used by
permissions.is_owner_person and backup.owner_ok). Anyone assigned the Alice.Owner app role is an owner (full access, including
Health, Trading, Mileage and Backups); the configured owner object ID (ALICE_OWNER_OBJECT_ID, the setup state's ownerObjectId)
counts only as the bootstrap fallback while app roles are off; never an account name or email. Covers: Stefan's everyday
account (Alice.Owner) recognised as Owner on every owner-only page and API, in both sign-in modes; his admin account (Alice.Admin)
and everyone else refused on every one; the fallback ignored once app roles are on; the owner rules on Users and permissions;
the Backup page in the Admin menu for owners only; and the vault query URL-encoded. All object IDs here are fictional. No real
model or Azure is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, http.client, json, os, re, urllib.parse
import app, substrate_store as store, users, permissions
from fastapi.testclient import TestClient

cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}
EVERYDAY, ADMINACC, ADMIN2, ALT, SECOND = ('0000f955-0000-4000-8000-000000000001', '0000e610-0000-4000-8000-000000000002',
                                           '0000adad-0000-4000-8000-000000000003', '0000a17a-0000-4000-8000-000000000004',
                                           '00005ec0-0000-4000-8000-000000000005')


def who(oid, email, roles=()):
    claims = [{'typ': 'name', 'val': email.split('@')[0]}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


E = who(EVERYDAY, 'stefan@example.org', ['Alice.Owner'])                  # Stefan's everyday account: Alice.Owner
E_NOROLE = who(EVERYDAY, 'stefan@example.org')                            # the same account before -Step users
B = who(ADMINACC, 'admin@tenant.example.org', ['Alice.Admin'])            # his tenant admin account: Alice.Admin, not an owner
A = who(ADMIN2, 'ada@example.org', ['Alice.Admin'])
S2 = who(SECOND, 'sam@example.org', ['Alice.Owner'])                      # anyone Entra makes an owner is one
SAME_EMAIL = who(ALT, 'stefan@example.org', ['Alice.Admin'])              # the owner's email on another account: not the owner
OWNER_PAGES = ['/admin/backup', '/admin/health', '/admin/trading', '/admin/mileage']
OWNER_APIS = [r.split(' ', 1) for r, spec in permissions.ROUTES.items() if spec == 'owner']


def fill(path):
    return re.sub(r'\{[a-z_]+\}', '0123456789abcdef0123456789abcdef', path)


def refused_everywhere(h):
    bad = []
    for page in OWNER_PAGES:
        if cl.get(page, headers=h).status_code != 403: bad.append(page)
    for method, path in OWNER_APIS:
        r = cl.request(method, fill(path), headers=h, json={})
        if r.status_code != 403: bad.append(f'{method} {path} -> {r.status_code}')
    return bad


def owner_everywhere(h):
    acc = cl.get('/admin/api/my-access', headers=h).json()
    return (acc['role'] == 'owner' and acc['owner_person'] is True
            and all(cl.get(p, headers=h).status_code == 200 for p in OWNER_PAGES + ['/admin/users'])
            and all(cl.get(u, headers=h).status_code == 200 for u in ('/admin/api/backup', '/admin/api/backup/runbook', '/admin/api/health',
                                                                      '/admin/api/mileage', '/admin/api/users'))
            and cl.post('/admin/api/backup/drill', headers=h).status_code == 400)      # allowed; refused only because no drill is set up here


t('the owner-only API list covers backups, the drill, health, trading and mileage',
  {'GET /admin/api/backup', 'POST /admin/api/backup/drill', 'GET /admin/api/health', 'GET /admin/api/trading', 'GET /admin/api/mileage'}
  <= {f'{m} {p}' for m, p in OWNER_APIS})

# ---------------- before the switch (app roles off): ownerObjectId is the bootstrap fallback ----------------
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '0', 'ALICE_OWNER_OBJECT_ID': EVERYDAY})
users._forget()
t('app roles off: the configured owner (fallback) is the owner on every owner-only page and API, before any role', owner_everywhere(E_NOROLE))
t('app roles off: …and with Alice.Owner assigned', owner_everywhere(E))
for h, name in ((B, 'the admin account (Alice.Admin)'), (who(ADMINACC, 'admin@tenant.example.org'), 'the admin account before -Step users'),
                (SAME_EMAIL, "an account with the owner's email but another object ID")):
    bad = refused_everywhere(h)
    t(f'app roles off: {name} gets into Alice but is refused every owner-only page and API', not bad
      and cl.get('/admin/api/memories', headers=h).status_code == 200)
    if bad: print('   not refused:', bad[:10])

# ---------------- after the switch (app roles on): Entra decides ----------------
os.environ['ALICE_USE_APP_ROLES'] = '1'
users._forget()
t('app roles on: Alice.Owner makes the everyday account the owner on every owner-only page and API', owner_everywhere(E))
t('app roles on: anyone else Entra gives Alice.Owner is an owner too', owner_everywhere(S2))
for h, name in ((B, 'the admin account (Alice.Admin)'), (A, 'another Admin'), (SAME_EMAIL, "an account with the owner's email")):
    bad = refused_everywhere(h)
    t(f'app roles on: {name} is refused every owner-only page and API', not bad)
    if bad: print('   not refused:', bad[:10])
os.environ['ALICE_OWNER_OBJECT_ID'] = ADMINACC
users._forget()
t('app roles on: the configured ID is only a fallback: without Alice.Owner it is not the owner', not refused_everywhere(B)
  and cl.get('/admin/api/my-access', headers=B).json()['role'] == 'admin')
os.environ['ALICE_OWNER_OBJECT_ID'] = EVERYDAY
users._forget()

# ---------------- the Backup page in the Admin menu: owners only ----------------
home_e, home_b = (cl.get('/admin', headers=h).text for h in (E, B))
item = re.search(r'<a href="/admin/backup" data-page="backup"[^>]*><svg[^>]*>.*?</svg><span class="nav-label">Backups</span></a>', home_e)
t('the Admin menu lists Backups, with its icon, for the owner', bool(item) and re.search(r'data-fold="Admin".*data-page="backup"', home_e, re.S))
t('…but never for an Admin (nor Health, Trading or Mileage)', 'data-page="backup"' not in home_b and 'data-page="health"' not in home_b and 'data-page="users"' in home_b)

# ---------------- the owner rules on Users and permissions ----------------
t('nobody can demote, suspend or re-profile an Alice.Owner holder (their role is changed in Entra)',
  all(cl.put(f'/admin/api/users/{oid}', headers=h, json=body).status_code == 403
      for oid in (EVERYDAY, SECOND) for h in (E, S2, B) for body in ({'role': 'member'}, {'status': 'suspended'}, {'profile': 'member'})))
lst = {u['oid']: u for u in cl.get('/admin/api/users', headers=E).json()['users']}
t('Users and permissions marks the owners, and why', lst[EVERYDAY]['is_owner'] and 'Alice.Owner' in lst[EVERYDAY]['owner_by']
  and lst[SECOND]['is_owner'] and not lst[ADMINACC]['is_owner'] and lst[ADMINACC]['effective_role'] == 'admin')
t('background work and the connector know the owner from their last sign-in (no sign-in to read)',
  users.viewer_for(EVERYDAY).owner and permissions.is_owner_person(users.viewer_for(EVERYDAY)) and users.connector_viewer(EVERYDAY).owner
  and not users.viewer_for(ADMINACC).owner)
cl.get('/', headers=who(SECOND, 'sam@example.org', ['Alice.Admin']))      # Entra changes the role
users._forget()
t('Alice.Owner taken away in Entra: no longer an owner, at once and in the background',
  not refused_everywhere(who(SECOND, 'sam@example.org', ['Alice.Admin'])) and not users.viewer_for(SECOND).owner)
t('the owner check never reads a name or email', 'email' not in users.is_owner.__code__.co_varnames
  and 'principal-name' not in open(os.path.join(_util.ROOT, 'backup.py'), encoding='utf-8').read().split('def owner_ok', 1)[1].split('\ndef ', 1)[0])
os.environ.pop('ALICE_TRUST_EASYAUTH', None); os.environ.pop('ALICE_USE_APP_ROLES', None); os.environ.pop('ALICE_OWNER_OBJECT_ID', None)
users._forget()
t('on the PC (no sign-in) whoever is here is still the owner', cl.get('/admin/api/backup').status_code == 200 and 'data-page="backup"' in cl.get('/admin').text)

# ---------------- Azure REST addresses: query parameters URL-encoded ----------------
import azure_io
import backup
FILTER = "backupManagementType eq 'AzureStorage'"
VAULT = '/subscriptions/0000/resourceGroups/alice-rg/providers/Microsoft.RecoveryServices/vaults/alice-backup-vault'
bad_char = getattr(http.client, '_contains_disallowed_url_pchar_re', re.compile('[\x00-\x20\x7f]'))
u = azure_io.arm_url(VAULT + '/backupProtectedItems', '2023-04-01', {'$filter': FILTER})
q = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
t('a filter with spaces and quotes is encoded (no space, quote or control character left in the address)',
  not bad_char.search(u) and ' ' not in u and "'" not in u and q['$filter'] == [FILTER] and q['api-version'] == ['2023-04-01'])
u2 = azure_io.arm_url(VAULT + "/backupProtectedItems?$filter=" + FILTER + "&$top=5", '2023-04-01')
q2 = urllib.parse.parse_qs(urllib.parse.urlsplit(u2).query)
t('…also when it is written straight into the path', not bad_char.search(u2) and q2['$filter'] == [FILTER] and q2['$top'] == ['5'])
t('…and an already-encoded one is not encoded twice', azure_io.arm_url(VAULT + '/x?$filter=a%20eq%20%27b%27', '1') == azure_io.arm_url(VAULT + '/x', '1', {'$filter': "a eq 'b'"}))
SEEN = []


def fake_http(method, url, data=None, headers=None, timeout=60):
    SEEN.append(url)
    if url.startswith('http://identity/'): return 200, {}, b'{"access_token":"tok","expires_on":"9999999999"}'
    if bad_char.search(url): raise http.client.InvalidURL(f"URL can't contain control characters. {url!r}")
    if '/backupProtectedItems' in url:
        return 200, {}, json.dumps({'value': [{'id': VAULT + '/item1', 'properties': {'friendlyName': 'alice', 'lastBackupStatus': 'Completed'}}]}).encode()
    return 200, {}, b'{"value": []}'


os.environ.update({'IDENTITY_ENDPOINT': 'http://identity/token', 'IDENTITY_HEADER': 'h'})
azure_io.HTTP = fake_http
out = backup._files_state({**backup.config(), 'vault_id': VAULT, 'files_time': '01:00', 'files_days': 30})
sent = [s for s in SEEN if '/backupProtectedItems' in s]
t('the Backup page reads the vault (no "URL can\'t contain control characters")', not out['error'] and out.get('share') == 'alice'
  and sent and urllib.parse.parse_qs(urllib.parse.urlsplit(sent[0]).query)['$filter'] == [FILTER])
for k in ('IDENTITY_ENDPOINT', 'IDENTITY_HEADER'): os.environ.pop(k, None)
