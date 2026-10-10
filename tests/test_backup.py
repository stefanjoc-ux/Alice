"""Backups: the nightly off-site copy (backup.py, the alice-backup job) and the Backup page. Azure is a stand-in: the
identity endpoint, the off-site storage account and Azure Resource Manager are fakes, and pg_dump is replaced, so nothing
leaves this machine and no real database or share is read."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import io
import json
import os
import re
import tarfile
import tempfile
import urllib.parse
from datetime import datetime, timedelta, timezone

import substrate_store as store
store.init()
import backup as B
import notify

UTC = timezone.utc
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda *p: open(os.path.join(ROOT, *p), encoding='utf-8').read()

# ---------------- UK time: 02:00 UK whatever the season ----------------
t('winter: the 01:00 UTC start is skipped (01:00 UK)', not B.due(datetime(2026, 1, 15, 1, 0, 20, tzinfo=UTC)))
t('winter: the 02:00 UTC start takes the backup (02:00 UK)', B.due(datetime(2026, 1, 15, 2, 0, 20, tzinfo=UTC)))
t('summer: the 01:00 UTC start takes the backup (02:00 BST)', B.due(datetime(2026, 7, 15, 1, 0, 20, tzinfo=UTC)))
t('summer: the 02:00 UTC start is skipped (03:00 BST)', not B.due(datetime(2026, 7, 15, 2, 0, 20, tzinfo=UTC)))
t('the day the clocks go forward (29 Mar 2026): exactly one of the two runs', B.due(datetime(2026, 3, 29, 1, 1, tzinfo=UTC)) and not B.due(datetime(2026, 3, 29, 2, 1, tzinfo=UTC)))
t('the day the clocks go back (25 Oct 2026): exactly one of the two runs', not B.due(datetime(2026, 10, 25, 1, 1, tzinfo=UTC)) and B.due(datetime(2026, 10, 25, 2, 1, tzinfo=UTC)))
t('a start by hand at another time always goes ahead', B.due(datetime(2026, 7, 15, 14, 7, tzinfo=UTC)))
t('the next run is 02:00 UK time (01:00 UTC in summer, 02:00 UTC in winter)',
  B.next_at(datetime(2026, 7, 15, 12, 0, tzinfo=UTC)) == datetime(2026, 7, 16, 1, 0, tzinfo=UTC)
  and B.next_at(datetime(2026, 1, 15, 12, 0, tzinfo=UTC)) == datetime(2026, 1, 16, 2, 0, tzinfo=UTC)
  and B.next_at(datetime(2026, 10, 24, 12, 0, tzinfo=UTC)) == datetime(2026, 10, 25, 2, 0, tzinfo=UTC))

# ---------------- pg_dump: the password never goes on the command line ----------------
args, env, pw = B.pg_args('host=alice-pg.private.postgres.database.azure.com port=5432 dbname=alice user=aliceadmin password=S3cretPw sslmode=require')
t('pg_dump: custom format, compressed, no owners', args[:5] == ['pg_dump', '--format=custom', '--compress=6', '--no-owner', '--no-privileges'])
t('pg_dump: the password is passed in PGPASSWORD, never in the arguments', env['PGPASSWORD'] == 'S3cretPw' and not any('S3cretPw' in a for a in args)
  and 'ALICE_DATABASE_URL' not in env and 'sslmode=require' in args[-1])
args, env, pw = B.pg_args('postgresql://alice:p%40ss@db.example/alice?sslmode=require')
t('pg_dump: a postgresql:// address works too', env['PGPASSWORD'] == 'p@ss' and 'dbname=alice' in args[-1] and 'p@ss' not in ' '.join(args))

# ---------------- the stand-in Azure ----------------
CALLS, BLOBS, ARMQ, MAIL = [], {}, {}, []
OFFSITE, LIVE = 'aliceabc123offsite', 'aliceabc123files'

def fake_http(method, url, data=None, headers=None, timeout=60):
    headers = headers or {}
    CALLS.append((method, url, dict(headers)))
    if url.startswith('http://identity/'):
        res = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)['resource'][0]
        return 200, {}, json.dumps({'access_token': 'tok-' + res, 'expires_on': '9999999999'}).encode()
    u = urllib.parse.urlsplit(url)
    if u.hostname.endswith('.blob.core.windows.net'):
        assert headers.get('Authorization') == 'Bearer tok-https://storage.azure.com/'
        name = urllib.parse.unquote(u.path.split('/', 2)[2]); q = urllib.parse.parse_qs(u.query)
        b = BLOBS.setdefault((u.hostname, name), {'blocks': {}})
        if q.get('comp') == ['block']:
            b['blocks'][q['blockid'][0]] = data; return 201, {}, b''
        if q.get('comp') == ['blocklist']:
            if 'data' in b and headers.get('If-None-Match') == '*': return 409, {}, b'<Error><Message>The blob already exists.</Message></Error>'
            ids = re.findall(r'<Latest>(.*?)</Latest>', data.decode())
            b['data'] = b''.join(b['blocks'][i] for i in ids); b['commit_headers'] = dict(headers); return 201, {}, b''
    if u.hostname == 'management.azure.com':
        for k, v in ARMQ.items():
            if k in u.path: return v
        return 404, {}, b'{"error":{"message":"not found"}}'
    raise AssertionError('unexpected call to ' + url)

import azure_io
azure_io.HTTP = fake_http
notify.HTTP = lambda url, data=None, headers=None, timeout=15: (MAIL.append((url, json.loads(data) if data else None)) or (202, {})) if 'graph.microsoft.com/v1.0' in url else (200, {'access_token': 'g', 'expires_on': '9999999999'})

src = tempfile.mkdtemp(prefix='alice-test-share-')
os.makedirs(os.path.join(src, 'Documents', 'Policy library')); os.makedirs(os.path.join(src, 'data', 'images'))
open(os.path.join(src, 'Documents', 'Policy library', 'leave.txt'), 'w').write('Annual leave: 25 days (fictional).')
open(os.path.join(src, 'data', 'images', 'a.png'), 'wb').write(os.urandom(5000))
os.environ.update({'IDENTITY_ENDPOINT': 'http://identity/msi/token', 'IDENTITY_HEADER': 'hdr', 'ALICE_IDENTITY_CLIENT_ID': 'cid',
                   'ALICE_BACKUP_ACCOUNT': OFFSITE, 'ALICE_FILES_ACCOUNT': LIVE, 'ALICE_BACKUP_SOURCE': src,
                   'ALICE_BACKUP_NOTIFY': 'stefan@example.org', 'ALICE_MAIL_FROM': 'alice@example.org'})
DUMP = b'PGDMP' + os.urandom(3000)
B.dump_chunks = lambda url: iter([DUMP[:1000], DUMP[1000:]])
azure_io.BLOCK = 1024                                     # small blocks, so the files go up in several
store.propose('Fictional memory', 'A fact for the backup test.', 'Test')

# The job reads the live database's address (in Azure); here only the stand-in pg_dump receives it.
B.database_url = lambda: 'host=fake.example dbname=alice'
run_job = B.run
now = datetime(2026, 1, 15, 2, 0, 30, tzinfo=UTC)
code = run_job(now=now)
t('the nightly copy completes (exit code 0)', code == 0)
writes = [(m, u) for m, u, h in CALLS if m == 'PUT']
hosts = {urllib.parse.urlsplit(u).hostname for m, u in writes}
t('every write goes to the off-site account only', writes and hosts == {OFFSITE + '.blob.core.windows.net'})
t('nothing is ever written to the live file share\'s account', not any(LIVE in u for m, u, h in CALLS))
t('backup data is reached with the managed identity (no keys)', all(h.get('Authorization', '').startswith('Bearer ') for m, u, h in CALLS if m == 'PUT'))
names = sorted(n for (h, n) in BLOBS)
t('three blobs per night, named by date: database, files, manifest', names == ['2026/01/15/20260115T0200Z-database.dump',
  '2026/01/15/20260115T0200Z-files.tar.gz', '2026/01/15/20260115T0200Z-manifest.json'])
blob = lambda suffix: next(v for (h, n), v in BLOBS.items() if n.endswith(suffix))
t('the database dump is copied exactly', blob('-database.dump')['data'] == DUMP)
t('a blob is never overwritten (If-None-Match: *)', all(v['commit_headers'].get('If-None-Match') == '*' for v in BLOBS.values()))
t('the files went up in several blocks', len(blob('-files.tar.gz')['blocks']) > 1)
with tarfile.open(fileobj=io.BytesIO(blob('-files.tar.gz')['data']), mode='r:gz') as tar:
    members = {m.name: m for m in tar.getmembers()}
    leave = tar.extractfile('alice/Documents/Policy library/leave.txt').read()
t('the whole share is in the compressed copy, files intact', 'alice/data/images/a.png' in members and leave == b'Annual leave: 25 days (fictional).')
man = json.loads(blob('-manifest.json')['data'])
t('the manifest lists sizes, checksums and the counts to check a restore against',
  man['database']['bytes'] == len(DUMP) and len(man['files']['sha256']) == 64 and man['counts']['memories'] >= 1 and 'proposals' in man['counts'] and man['files']['count'] == 2)
with store.db() as c:
    row = c.execute("SELECT * FROM backup_runs WHERE status='ok'").fetchone()
    act = c.execute("SELECT * FROM activity WHERE action='backup_completed'").fetchone()
t('the run is recorded with its size and duration', row and row['size_bytes'] > len(DUMP) and row['duration_s'] is not None)
t('the activity log says size, duration and result', act and 'database' in act['detail'] and 'files' in act['detail'] and re.search(r'\d+ s', act['detail']) and OFFSITE in act['detail'])
t('Home is quiet while backups are fine', B.home_status(now=now + timedelta(hours=2)) is None)
t('…but warns when no good copy for over a day', (B.home_status(now=now + timedelta(hours=30)) or {}).get('level') == 'warn')

# ---------------- not 02:00 UK: the other scheduled start does nothing ----------------
n = len(CALLS)
t('the scheduled start at 01:00 UTC in winter takes nothing', run_job(now=datetime(2026, 1, 16, 1, 0, 10, tzinfo=UTC)) == 0 and len(CALLS) == n)

# ---------------- refuses to write anywhere but the off-site account ----------------
os.environ['ALICE_BACKUP_ACCOUNT'] = LIVE
n = len(CALLS)
code = run_job(now=datetime(2026, 1, 16, 2, 0, 10, tzinfo=UTC))
t('the live share\'s account is refused as a backup target', code == 1 and not any(m == 'PUT' for m, u, h in CALLS[n:]))
os.environ['ALICE_BACKUP_ACCOUNT'] = OFFSITE

# ---------------- a failure is recorded, shown on Home and emailed ----------------
def broken(url):
    raise RuntimeError('pg_dump failed: connection to server failed: password=S3cretPw rejected')
    yield b''
B.dump_chunks = broken
MAIL.clear()
os.environ['IDENTITY_ENDPOINT'] = 'http://identity/msi/token'
fail_at = datetime(2026, 1, 17, 2, 0, 10, tzinfo=UTC)
code = run_job(now=fail_at)
with store.db() as c:
    last = c.execute("SELECT * FROM backup_runs ORDER BY started_at DESC LIMIT 1").fetchone()
    acts = [r['action'] for r in c.execute("SELECT action FROM activity WHERE action LIKE 'backup%' ORDER BY id")]
t('a failed copy exits 1, so the job shows Failed in Azure', code == 1)
t('the failure is recorded with what went wrong (secrets removed)', last['status'] == 'failed' and 'pg_dump failed' in last['error'] and 'S3cretPw' not in last['error'])
t('the failure is in the activity log', 'backup_failed' in acts)
sent = [m for m in MAIL if m[1]]
t('Stefan is emailed about it', sent and sent[-1][1]['message']['toRecipients'][0]['emailAddress']['address'] == 'stefan@example.org'
  and 'failed' in sent[-1][1]['message']['subject'] and 'S3cretPw' not in json.dumps(sent[-1][1]) and 'backup_failure_emailed' in acts)
hs = B.home_status(now=fail_at + timedelta(hours=1))
t('Home shows the failure', hs and hs['level'] == 'bad' and hs['link'] == '/admin/backup' and 'failed' in hs['text'])
os.environ.pop('ALICE_MAIL_FROM')
run_job(now=datetime(2026, 1, 18, 2, 0, 10, tzinfo=UTC))
with store.db() as c:
    nm = c.execute("SELECT detail FROM activity WHERE action='backup_failure_not_emailed' ORDER BY id DESC").fetchone()
t('without email set up, it says why no email went (and still shows on Home)', nm and 'not set up' in nm['detail'])

# ---------------- a file that shrinks while it is copied keeps the archive whole ----------------
r = B._Exact(io.BytesIO(b'abc'), 6)
t('a file that shrank mid-copy is padded and flagged', r.read(10) == b'abc' and r.read(10) == b'\0\0\0' and r.short and r.read() == b'')

# ---------------- the Backup page: owner only, state read from Azure ----------------
vault = '/subscriptions/s1/resourceGroups/alice-rg/providers/Microsoft.RecoveryServices/vaults/alice-backup-vault'
pgid = '/subscriptions/s1/resourceGroups/alice-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/alice-pg-abc'
item = vault + '/backupFabrics/Azure/protectionContainers/storagecontainer;Storage;alice-rg;' + LIVE + '/protectedItems/AzureFileShare;alice'
os.environ.update({'ALICE_BACKUP_VAULT_ID': vault, 'ALICE_PG_SERVER_ID': pgid, 'ALICE_BACKUP_LOCK': 'alice-do-not-delete'})
ARMQ.update({
    '/recoveryPoints': (200, {}, json.dumps({'value': [{'properties': {'recoveryPointTime': '2026-01-17T01:00:05Z', 'recoveryPointSizeInGB': 2}},
                                                       {'properties': {'recoveryPointTime': '2026-01-16T01:00:05Z'}}]}).encode()),
    '/backupProtectedItems': (200, {}, json.dumps({'value': [{'id': item, 'properties': {'friendlyName': 'alice', 'protectionState': 'Protected',
                                                                                          'lastBackupTime': '2026-01-17T01:00:05Z', 'lastBackupStatus': 'Completed'}}]}).encode()),
    '/backups': (200, {}, json.dumps({'value': [{'properties': {'completedTime': '2026-01-17T03:10:00Z', 'backupType': 'FULL'}}]}).encode()),
    'flexibleServers/alice-pg-abc': (200, {}, json.dumps({'properties': {'backup': {'backupRetentionDays': 35, 'geoRedundantBackup': 'Disabled',
                                                                                    'earliestRestoreDate': '2025-12-13T03:00:00Z'}}}).encode()),
})
o = B.overview(fresh=True)
t('page: the file share\'s last snapshot, its size and restore points', o['files']['last']['time'] == '2026-01-17T01:00:05Z' and o['files']['last']['size_gb'] == 2 and o['files']['points'] == 2)
t('page: the database restore window and retention', o['database']['earliest_restore'].startswith('2025-12-13') and o['database']['keep_days'] == 35 and o['database']['geo'] is False)
t('page: the off-site copy\'s last run, last good run, where it is kept and the next run',
  o['offsite']['last']['status'] == 'failed' and o['offsite']['last_ok'] and 'UK West' in o['offsite']['where'] and o['offsite']['next_run'] and o['offsite']['keep_days'] == 35)
t('page: the resource group lock', o['lock'] == {'on': True, 'name': 'alice-do-not-delete'})
t('page: the database is read through Resource Manager with the identity, read-only', all(m == 'GET' for m, u, h in CALLS if 'management.azure.com' in u)
  and any(h.get('Authorization') == 'Bearer tok-https://management.azure.com/' for m, u, h in CALLS if 'management.azure.com' in u))
ARMQ.clear(); ARMQ['/backupProtectedItems'] = (403, {}, b'{"error":{"code":"AuthorizationFailed","message":"no access to the vault"}}')
o = B.overview(fresh=True)
t('page: Azure refusing is shown plainly, not a crash', 'no access to the vault' in o['files']['error'] and o['database']['error'])

import app
from fastapi.testclient import TestClient
cl = TestClient(app.app)
t('on the PC the Backup page opens (this computer only)', cl.get('/admin/backup').status_code == 200 and cl.get('/admin/api/backup').status_code == 200)
t('the Backup page is in the Admin menu', 'data-page="backup"' in cl.get('/admin').text)
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_OWNER_OBJECT_ID': '11111111-2222-3333-4444-555555555555'})
other = {'x-ms-client-principal-id': '99999999-2222-3333-4444-555555555555', 'x-ms-client-principal-name': 'someone@example.org'}
owner = {'x-ms-client-principal-id': '11111111-2222-3333-4444-555555555555', 'x-ms-client-principal-name': 'stefan@example.org'}
t('in Azure: another signed-in person is refused the page and its data', cl.get('/admin/backup', headers=other).status_code == 403
  and cl.get('/admin/api/backup', headers=other).status_code == 403)
t('in Azure: the owner sees it', cl.get('/admin/backup', headers=owner).status_code == 200 and cl.get('/admin/api/backup', headers=owner).status_code == 200)
os.environ['ALICE_OWNER_OBJECT_ID'] = ''
t('in Azure with no owner set: nobody sees backups', cl.get('/admin/api/backup', headers=owner).status_code == 403)
os.environ.pop('ALICE_TRUST_EASYAUTH')
h = cl.get('/admin/api/home', headers={'x-admin-token': app.ADMIN_TOKEN}).json()
t('Home carries the backup failure', h.get('backup') and h['backup']['level'] == 'bad')
import activity_log
t('the activity log names backup events', all(a in activity_log.LABELS for a in ('backup_completed', 'backup_failed', 'backup_failure_emailed', 'backup_failure_not_emailed')))

# ---------------- the infrastructure says what it should ----------------
bk, main, setup = read('infra', 'backup.bicep'), read('infra', 'main.bicep'), read('deploy', 'azure-setup.ps1')
t('off-site: a separate storage account in UK West', "param offsiteLocation string = 'ukwest'" in main and 'location: offsiteLocation' in bk and "'${prefix}${suffix}offsite'" in main)
t('off-site: immutability for the keep period (35 days by default)', "immutabilityPeriodSinceCreationInDays: offsiteKeepDays" in bk and 'param offsiteKeepDays int = 35' in main)
t('off-site: soft delete for blobs and the container', 'deleteRetentionPolicy: { enabled: true, days: offsiteSoftDeleteDays }' in bk and 'containerDeleteRetentionPolicy' in bk)
t('off-site: Entra only (no account keys), encrypted at rest twice, no public blobs', 'allowSharedKeyAccess: false' in bk and 'requireInfrastructureEncryption: true' in bk and 'allowBlobPublicAccess: false' in bk)
t('off-site: the identity may write there; the job reads the share read-only', 'roles.blobContributor' in bk and "accessMode: 'ReadOnly'" in bk and "mountPath: '/mnt/alice-ro'" in bk)
t('the job: 01:00 and 02:00 UTC (02:00 UK kept in code), role backup', "cronExpression: '0 1,2 * * *'" in bk and "{ name: 'ALICE_ROLE', value: 'backup' }" in bk and 'backup)' in read('deploy', 'start.sh'))
t('file share: Recovery Services vault with a daily policy kept 30 days', 'Microsoft.RecoveryServices/vaults@' in bk and "scheduleRunFrequency: 'Daily'" in bk and 'param filesBackupDays int = 30' in main and 'AzureFileShareProtectedItem' in bk)
t('resource group lock: CanNotDelete, on by default, with how to lift it', "level: 'CanNotDelete'" in bk and 'param lockResourceGroup bool = true' in main and 'az lock delete --name alice-do-not-delete' in bk)
t('database: 35 days by default; geo-redundant a parameter, off', 'param pgBackupRetentionDays int = 35' in main and 'backupRetentionDays: pgBackupRetentionDays' in main and 'param pgGeoRedundantBackup bool = false' in main)
t('setup: -Step backup exists, and every later step keeps backups on', re.search(r"ValidateSet\([^)]*'backup'[^)]*\)\]\[string\]\$Step", setup) and "if ($State.backup) {" in setup and "Run-Job 'alice-backup'" in setup)
t('the image has pg_dump', 'postgresql-client' in read('Dockerfile'))
t('the pipeline moves the backup job to each new image', 'alice-backup' in read('.github', 'workflows', 'deploy.yml'))

# ---------------- a real pg_dump, when this run has a test PostgreSQL server and pg_dump (the pipeline's image does) ----------------
import shutil
if os.environ.get('ALICE_TEST_DATABASE_URL') and shutil.which('pg_dump'):
    import importlib
    importlib.reload(B)                      # the real dump_chunks and database_url
    out = b''.join(B.dump_chunks(os.environ['ALICE_TEST_DATABASE_URL']))
    t('a real pg_dump of the test database streams a custom-format archive', out.startswith(b'PGDMP') and len(out) > 100)
