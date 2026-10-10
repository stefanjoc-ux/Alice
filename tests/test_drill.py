"""The restore drill (drill.py) and its place on the Backup page. Azure is a stand-in that keeps the resources the drill
creates, so the tests can see that it builds only in its own resource group, never touches live resources (only reads
the backup), compares the counts, and always removes everything it built, even when a step fails."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import os
import re
import urllib.parse

import substrate_store as store
store.init()
import azure_io
import drill as D
import notify

SUB = '11111111-2222-3333-4444-555555555555'
DRILL_RG, LIVE_RG = 'alice-rg-drill', 'alice-rg'
LIVE_DB = 'host=alice-pg-LIVE.private.postgres.database.azure.com dbname=alice user=aliceadmin password=LIVE-SECRET'
os.environ['ALICE_DATABASE_URL_FOR_LIVE'] = LIVE_DB      # present in the process: it must never reach any call
ENV = {'ALICE_DRILL_SUBSCRIPTION': SUB, 'ALICE_DRILL_RG': DRILL_RG, 'ALICE_DRILL_LIVE_RG': LIVE_RG, 'ALICE_BACKUP_ACCOUNT': 'aliceabcoffsite',
       'ALICE_BACKUP_CONTAINER': 'alice-offsite', 'ALICE_DRILL_REPORTS': 'drill-reports', 'ALICE_FILES_ACCOUNT': 'aliceabcfiles',
       'ALICE_DRILL_IDENTITY_ID': f'/subscriptions/{SUB}/resourceGroups/{LIVE_RG}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/alice-drill-identity',
       'ALICE_IDENTITY_CLIENT_ID': 'drill-client', 'ALICE_ACR_SERVER': 'aliceabcacr.azurecr.io', 'ALICE_DRILL_AUTH_CLIENT_ID': 'web-signin-app',
       'ALICE_TENANT_ID': 'tenant-1', 'ALICE_OWNER_OBJECT_ID': 'owner-oid-1', 'ALICE_BACKUP_NOTIFY': 'stefan@example.org', 'ALICE_MAIL_FROM': 'alice@example.org',
       'IDENTITY_ENDPOINT': 'http://identity/token', 'IDENTITY_HEADER': 'h'}
os.environ.update(ENV)

MANIFEST = {'taken_at': '2026-10-08T01:00:30+00:00', 'version': '73f2f1f', 'database': {'blob': 'x-database.dump'}, 'files': {'blob': 'x-files.tar.gz', 'count': 40},
            'counts': {'memories': 12, 'knowledge items': 4, 'proposals': 2, 'files': 1}}
STATE, CALLS, BLOBS, MAIL = {}, [], {}, []
SCENARIO = {}

def rtype(path):
    segs = path.split('/providers/', 1)[1].split('/')
    return '/'.join([segs[0], segs[1]] + segs[3::2])

TOP = set(D.DELETE_ORDER)

def arm_fake(method, url, data, headers):
    u = urllib.parse.urlsplit(url); path = urllib.parse.unquote(u.path); key = path.lower()
    if method == 'GET' and key.endswith('/resources'):
        items = [{'id': r['id'], 'type': r['type'], 'name': r['id'].rsplit('/', 1)[1]} for k, r in STATE.items() if r['type'] in TOP and k.startswith(key[:-len('/resources')] + '/')]
        return 200, {}, json.dumps({'value': items}).encode()
    if method == 'PUT':
        typ = rtype(path)
        STATE[key] = {'id': path, 'type': typ, 'body': json.loads(data or b'{}'), 'polls': 0}
        if typ == 'Microsoft.App/containerApps' and not path.lower().endswith('/authconfigs/current'):
            env = {e['name']: e.get('value') for e in STATE[key]['body']['properties']['template']['initContainers'][0]['env']}
            drill_id = env['ALICE_DRILL_ID']
            counts = [{'what': w, 'expected': n, 'restored': (n - 1 if SCENARIO.get('mismatch') == w else n), 'ok': SCENARIO.get('mismatch') != w}
                      for w, n in list(MANIFEST['counts'].items()) + [('files on the share', 40)]]
            if not SCENARIO.get('no_report'):
                rep = {'ok': not SCENARIO.get('restore_fails') and not SCENARIO.get('mismatch'), 'counts': counts, 'took_s': 300, 'database_bytes': 5000, 'files_restored': 40}
                if SCENARIO.get('restore_fails'): rep['error'] = 'loading the database failed (nothing was kept): ERROR: something'
                if SCENARIO.get('mismatch'): rep['error'] = 'the restored counts do not match the copy'
                BLOBS[('aliceabcoffsite', 'drill-reports', f'{drill_id}/restore.json')] = json.dumps(rep).encode()
        return 201, {}, b'{}'
    if method == 'POST' and key.endswith('/listkeys'):
        return 200, {}, b'{"keys": [{"value": "drill-account-key"}]}'
    if method == 'DELETE':
        r = STATE.get(key)
        if r and r['type'] in SCENARIO.get('stuck', ()): return 409, {}, b'{"error":{"message":"in use"}}'
        if r:
            r['deleting'] = True
            for k in list(STATE):
                if k.startswith(key + '/'): del STATE[k]
        return 202, {}, b''
    if method == 'GET':
        r = STATE.get(key)
        if not r: return 404, {}, b'{"error":{"message":"not found"}}'
        if r.get('deleting'):
            del STATE[key]; return 200, {}, b'{}'
        r['polls'] += 1
        state = 'Failed' if r['type'] in SCENARIO.get('fail', ()) else ('Creating' if r['polls'] == 1 and r['type'] in TOP else 'Succeeded')
        props = {'provisioningState': state}
        if r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers': props['fullyQualifiedDomainName'] = 'alice-drill-pg.alice-drill.private.postgres.database.azure.com'
        if r['type'] == 'Microsoft.App/containerApps': props['configuration'] = {'ingress': {'fqdn': 'alice-drill-web.happy.uksouth.azurecontainerapps.io'}}
        return 200, {}, json.dumps({'properties': props}).encode()
    raise AssertionError(method + ' ' + url)

def fake_http(method, url, data=None, headers=None, timeout=60):
    CALLS.append((method, url, data))
    if url.startswith('http://identity/'): return 200, {}, b'{"access_token": "tok", "expires_on": "9999999999"}'
    u = urllib.parse.urlsplit(url)
    if u.hostname == 'management.azure.com': return arm_fake(method, url, data, headers)
    if u.hostname.endswith('.azurecontainerapps.io'):
        return (200, {}, b'{"ok": true}') if not SCENARIO.get('never_starts') else (503, {}, b'')
    if u.hostname.endswith('.blob.core.windows.net'):
        acct = u.hostname.split('.')[0]; cont = u.path.split('/')[1]; q = urllib.parse.parse_qs(u.query)
        if method == 'GET' and q.get('comp') == ['list']:
            names = sorted(n for (a, c, n) in BLOBS if a == acct and c == cont)
            return 200, {}, ''.join(f'<Name>{n}</Name>' for n in names).encode()
        name = urllib.parse.unquote(u.path.split('/', 2)[2])
        if method == 'GET':
            b = BLOBS.get((acct, cont, name))
            return (200, {}, b) if b is not None else (404, {}, b'')
        if q.get('comp') == ['block']:
            BLOBS[(acct, cont, '_b_' + name)] = BLOBS.get((acct, cont, '_b_' + name), b'') + data; return 201, {}, b''
        if q.get('comp') == ['blocklist']:
            BLOBS[(acct, cont, name)] = BLOBS.pop((acct, cont, '_b_' + name), b''); return 201, {}, b''
    raise AssertionError(url)

azure_io.HTTP = fake_http
notify.HTTP = lambda url, data=None, headers=None, timeout=15: (MAIL.append(json.loads(data)) or (202, {})) if data else (200, {'access_token': 'g', 'expires_on': '9999999999'})
BLOBS[('aliceabcoffsite', 'alice-offsite', '2026/10/07/20261007T0100Z-manifest.json')] = b'{"version": "old"}'
BLOBS[('aliceabcoffsite', 'alice-offsite', '2026/10/08/20261008T0100Z-manifest.json')] = json.dumps(MANIFEST).encode()
TICK = [0.0]
D.SLEEP = lambda s: TICK.__setitem__(0, TICK[0] + s)
D.CLOCK = lambda: TICK[0]

def drill(**scenario):
    SCENARIO.clear(); SCENARIO.update(scenario); CALLS.clear(); MAIL.clear()
    before = set(BLOBS)
    code = D.run('manual')
    new = [k for k in BLOBS if k not in before and k[1] == 'drill-reports' and k[2].endswith('/report.json')]
    return code, json.loads(BLOBS[new[0]]) if new else None

def arm_paths(): return [urllib.parse.unquote(urllib.parse.urlsplit(u).path) for m, u, d in CALLS if urllib.parse.urlsplit(u).hostname == 'management.azure.com']

# ---------------- a drill that passes ----------------
code, rep = drill()
drill_prefix = f'/subscriptions/{SUB}/resourceGroups/{DRILL_RG}/'.lower()
t('a good copy passes the drill (exit 0)', code == 0 and rep['result'] == 'passed')
t('every Resource Manager call stays inside the drill\'s own resource group', arm_paths() and all(p.lower().startswith(drill_prefix) for p in arm_paths()))
t('nothing in Alice\'s live resource group is read or written', not any(f'/resourcegroups/{LIVE_RG}/' in p.lower() for p in arm_paths()))
blob_calls = [(m, u) for m, u, d in CALLS if '.blob.core.windows.net' in u]
t('the backup is only read; the only write is the drill\'s report', all(m == 'GET' for m, u in blob_calls if '/alice-offsite' in u)
  and all('/drill-reports/' in u for m, u in blob_calls if m == 'PUT') and any(m == 'PUT' for m, u in blob_calls))
t('the live file share\'s account and the live database are never contacted', not any('aliceabcfiles' in u for m, u, d in CALLS)
  and not any(d and b'LIVE-SECRET' in d for m, u, d in CALLS) and not any('alice-pg-LIVE' in u for m, u, d in CALLS))
t('the newest copy is used, with the image of the release that took it', rep['backup']['manifest'].startswith('2026/10/08/') and rep['backup']['version'] == '73f2f1f')
t('every throwaway resource is removed afterwards', not STATE and not rep['cleanup']['left'] and len(rep['cleanup']['removed']) >= 6)
t('the restored counts are compared with the live counts recorded with the copy', len(rep['counts']) == 5 and all(c['ok'] for c in rep['counts']))
t('the time to get Alice back is measured against the 4-hour target', rep['recovery_s'] is not None and rep['within_rto'] and rep['rto_hours'] == 4 and rep['total_s'] >= rep['recovery_s'])
t('Stefan is emailed the result', MAIL and 'passed' in MAIL[-1]['message']['subject'] and 'Live data was not touched' in MAIL[-1]['message']['body']['content'])

# What the temporary Alice is given (captured from the PUT of the container app)
app_put = next(json.loads(d) for m, u, d in CALLS if m == 'PUT' and u.split('?')[0].endswith('/containerApps/alice-drill-web'))
auth_put = next(json.loads(d) for m, u, d in CALLS if m == 'PUT' and '/authConfigs/current' in u)
web_env = {e['name']: e.get('value', '<secret>') for e in app_put['properties']['template']['containers'][0]['env']}
t('the temporary Alice runs the copy\'s release', app_put['properties']['template']['containers'][0]['image'] == 'aliceabcacr.azurecr.io/alice:73f2f1f')
t('…restores first (init container), into the throwaway database only', app_put['properties']['template']['initContainers'][0]['env'][0] == {'name': 'ALICE_ROLE', 'value': 'restore'}
  and 'drill-pg' in app_put['properties']['configuration']['secrets'][0]['value'] and 'LIVE' not in json.dumps(app_put))
t('…with no AI keys, no email and no schedules', not any(k in web_env for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ALICE_MAIL_FROM')) and web_env['ALICE_NO_SCHEDULER'] == '1')
v = auth_put['properties']
t('…and sign-in locked to Stefan (Entra, his object ID only; 401 for anyone else)', v['globalValidation']['unauthenticatedClientAction'] == 'Return401'
  and v['identityProviders']['azureActiveDirectory']['validation']['defaultAuthorizationPolicy']['allowedPrincipals']['identities'] == ['owner-oid-1'])
first_put = next(i for i, (m, u, d) in enumerate(CALLS) if m == 'PUT' and 'management' in u)
t('the database server and environment are private to their own network', any('delegatedSubnetResourceId' in (d or b'').decode() for m, u, d in CALLS[first_put:] if m == 'PUT'))

# ---------------- failures: always cleaned up ----------------
code, rep = drill(fail=('Microsoft.DBforPostgreSQL/flexibleServers',))
t('a database server Azure cannot create fails the drill…', code == 1 and rep['result'] == 'failed' and 'database server' in rep['error'])
t('…and everything already built is still removed', not STATE and not rep['cleanup']['left'] and any('alicedrill' in n for n in rep['cleanup']['removed']))
code, rep = drill(restore_fails=True)
t('a restore that fails is reported with its reason, and cleaned up', code == 1 and 'loading the database failed' in rep['error'] and not STATE)
code, rep = drill(mismatch='proposals')
t('counts that differ fail the drill, naming what differs', code == 1 and 'proposals' in rep['error'] and not STATE)
code, rep = drill(never_starts=True, no_report=True)
t('an Alice that never answers fails after the time limit, and is cleaned up', code == 1 and 'did not answer' in rep['error'] and not STATE and rep.get('recovery_s') is None)
code, rep = drill(stuck=('Microsoft.Storage/storageAccounts',))
t('a resource that cannot be removed fails the drill and is named, so it can be deleted by hand', code == 1 and any('alicedrill' in n for n in rep['cleanup']['left'])
  and 'could not be removed' in rep['error'] and DRILL_RG in rep['error'])
STATE.clear()

# ---------------- leftovers from an earlier drill are removed first ----------------
left = f'/subscriptions/{SUB}/resourceGroups/{DRILL_RG}/providers/Microsoft.Storage/storageAccounts/alicedrillold00001'
STATE[left.lower()] = {'id': left, 'type': 'Microsoft.Storage/storageAccounts', 'body': {}, 'polls': 5}
code, rep = drill()
deletes = [i for i, (m, u, d) in enumerate(CALLS) if m == 'DELETE' and 'alicedrillold00001' in u]
first_put = next(i for i, (m, u, d) in enumerate(CALLS) if m == 'PUT' and 'management' in u)
t('what an earlier drill left behind is removed before building', code == 0 and deletes and deletes[0] < first_put and not STATE)

# ---------------- never in Alice's own resource group ----------------
os.environ['ALICE_DRILL_RG'] = LIVE_RG
CALLS.clear()
t('the drill refuses to run in Alice\'s own resource group (nothing is called)', D.run('manual') == 2 and not CALLS)
os.environ['ALICE_DRILL_RG'] = DRILL_RG
try: D.Drill(D.config())._path('/../../alice-rg/providers/x'); escaped = True
except D.Refused: escaped = False
t('a path that would leave the drill resource group is refused', not escaped)

# ---------------- the Backup page: reports, the button, targets ----------------
import backup as B
JOB = f'/subscriptions/{SUB}/resourceGroups/{LIVE_RG}/providers/Microsoft.App/jobs/alice-drill'
os.environ.update({'ALICE_DRILL_JOB_ID': JOB, 'ALICE_BACKUP_ACCOUNT': 'aliceabcoffsite'})
EXECS = {'value': []}
web_calls = []
def web_http(method, url, data=None, headers=None, timeout=60):
    if 'management.azure.com' in url and '/jobs/alice-drill' in url:
        web_calls.append((method, url))
        if url.split('?')[0].endswith('/executions'): return 200, {}, json.dumps(EXECS).encode()
        if method == 'POST' and url.split('?')[0].endswith('/start'): return 202, {}, b'{"name": "alice-drill-abc12"}'
    if 'management.azure.com' in url: return 403, {}, b'{"error":{"message":"no access"}}'
    return fake_http(method, url, data, headers, timeout)
azure_io.HTTP = web_http
o = B.overview(fresh=True)
t('the Backup page lists the drills, newest first', o['drill']['configured'] and len(o['drill']['recent']) >= 3 and o['drill']['recent'][0]['started_at'] >= o['drill']['recent'][-1]['started_at'])
with store.db() as c:
    n_runs = c.execute("SELECT count(*) FROM backup_runs WHERE kind='drill'").fetchone()[0]
    n_log = c.execute("SELECT count(*) FROM activity WHERE action IN ('restore_drill_passed','restore_drill_failed')").fetchone()[0]
B.overview(fresh=True)
with store.db() as c:
    again = c.execute("SELECT count(*) FROM activity WHERE action IN ('restore_drill_passed','restore_drill_failed')").fetchone()[0]
t('each drill is recorded and logged once', n_runs >= 3 and n_log == n_runs and again == n_log)
tg = o['targets']
t('targets: recovery time from the last drill against 4 hours; files 24 hours; database minutes',
  tg['rto']['hours'] is not None and tg['rto']['met'] and '4 hours' in tg['rto']['target'] and '24 hours' in tg['rpo_files']['target'] and 'Minutes' in tg['rpo_database']['target'])
r = B.start_drill()
t('the button starts the same job as the workflow (alice-drill)', r['started'] and any(m == 'POST' and '/jobs/alice-drill/start' in u for m, u in web_calls))
EXECS['value'] = [{'name': 'alice-drill-abc12', 'properties': {'status': 'Running', 'startTime': '2026-10-08T10:00:00Z'}}]
try: B.start_drill(); twice = True
except ValueError as e: twice = 'already running' not in str(e)
t('a second drill is refused while one is running', not twice)
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app)
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_OWNER_OBJECT_ID': 'owner-oid-1'})
other = {'x-ms-client-principal-id': 'someone-else', 'x-admin-token': app.ADMIN_TOKEN}
t('only the owner can start a drill or read the runbook', cl.post('/admin/api/backup/drill', headers=other).status_code == 403
  and cl.get('/admin/api/backup/runbook', headers=other).status_code == 403)
owner = {'x-ms-client-principal-id': 'owner-oid-1', 'x-admin-token': app.ADMIN_TOKEN}
r = cl.post('/admin/api/backup/drill', headers=owner)
t('…and the owner is told plainly when one is already running', r.status_code == 400 and 'already running' in r.json()['detail'])
rb = cl.get('/admin/api/backup/runbook', headers=owner).json()['text']
t('the runbook on the page is docs/restore.md', rb.startswith('# Restoring Alice'))
os.environ.pop('ALICE_TRUST_EASYAUTH')

# ---------------- the runbook, the workflow and the infrastructure ----------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda *p: open(os.path.join(ROOT, *p), encoding='utf-8').read()
for part, words in (('## A. One file or folder', 'restore-azurefiles'), ('## B. The database to a point in time', 'flexible-server restore'),
                    ('## C. Everything, from the nightly off-site copy', '-Step recover'), ('## D. Rolling back a release', 'promote.sh rollback')):
    t(f'runbook: {part[3:]} with its Cloud Shell commands', part in rb and words in rb)
t('runbook: placeholders only, never a secret (passwords are read from Key Vault into a variable)', '<subscription id>' in rb
  and not re.search(r'password=(?!\$)[^\s"]+', rb) and 'sk-' not in rb)
wf = read('.github', 'workflows', 'restore-drill.yml')
t('workflow: a manual button and a monthly run, starting the same job and failing when the drill fails', 'workflow_dispatch' in wf and "cron: '17 3 1 * *'" in wf
  and 'az containerapp job start -n alice-drill' in wf and '[ "$ST" = "Succeeded" ] || {' in wf)
bk, main, access, setup = read('infra', 'backup.bicep'), read('infra', 'main.bicep'), read('infra', 'drill-access.bicep'), read('deploy', 'azure-setup.ps1')
t('infra: the drill identity is Contributor on the drill resource group only', "scope: resourceGroup(drillResourceGroup)" in bk and 'contributor' in access
  and "param drillResourceGroup string = '${resourceGroup().name}-drill'" in main)
t('infra: it reads the copies, writes only drill-reports, pulls the image and may give its own identity to the temporary Alice',
  'drillReadsCopies' in bk and 'scope: drillReports' in bk and 'drillPullsImage' in bk and 'scope: drillIdentity' in bk)
t('infra: the drill job has no database address and no keys', 'ALICE_DATABASE_URL' not in bk.split("resource drillJob")[1].split('resource drillStarter')[0])
t('infra: Alice may start that one job and nothing else', "'Microsoft.App/jobs/start/action'" in bk and 'scope: drillJob' in bk)
t('setup: -Step backup creates the drill resource group; -Step recover only in a new resource group', 'group create -n "$ResourceGroup-drill"' in setup
  and '-Step recover only runs in a new resource group' in setup)
t('the pipeline moves the drill job to each new image', 'alice-drill' in read('.github', 'workflows', 'deploy.yml'))
