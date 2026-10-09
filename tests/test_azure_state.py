"""The setup state of azure-setup.ps1, kept in Azure (deploy/azure_state.py). Azure is a stand-in: every az command goes to
FakeAzure below, which keeps resources, deployments, the apps' settings and the state blob in memory and records each call,
so nothing leaves this machine. Covers: the state read from and written to Azure, the rebuild from what is deployed
(missing, or older than the newest deployment), the refusal when the local file differs, -UseLocalState, two runs at once,
and -Step check making no changes at all."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import copy
import io
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'deploy'))
import azure_state as S

RG, FILES, OFFSITE = 'alice-rg', 'aliceabc123files', 'aliceabc123offsite'
ME, ALSO = '11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222'
WEB_APP, API_APP, CONN_APP, GH_APP = 'aaaaaaaa-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000004'
KEY = 'c3RvcmFnZS1rZXktbm90LXJlYWw='
CALLERS = f'cccc=Microsoft Copilot:copilot;{S.TOKEN_STORE}=Microsoft Copilot:copilot'
PG_FQDN = 'alice-pg-abc123.postgres.database.azure.com'


def res(rtype, name): return {'type': rtype, 'name': name}


def env(d): return [{'name': k, 'value': v} for k, v in d.items()] + [{'name': 'ALICE_DATABASE_URL', 'secretRef': 'database-url'}]


def deployment(name, ts, params=None, outputs=None):
    return {'name': name, 'properties': {'timestamp': ts, 'provisioningState': 'Succeeded',
            'parameters': {k: {'type': 'String', 'value': v} for k, v in (params or {}).items()},
            'outputs': {k: {'type': 'String', 'value': v} for k, v in (outputs or {}).items()}}}


OUTPUTS = {'acrName': 'aliceabc123acr', 'acrLoginServer': 'aliceabc123acr.azurecr.io', 'keyVaultName': 'alice-kv-abc123',
           'storageAccount': FILES, 'shareName': 'alice', 'environmentDomain': 'blue-sea.uksouth.azurecontainerapps.io',
           'webUrl': 'https://alice-web.blue-sea.uksouth.azurecontainerapps.io', 'mcpUrl': 'https://alice-mcp.blue-sea.uksouth.azurecontainerapps.io',
           'postgresServer': 'alice-pg-abc123', 'offsiteAccount': OFFSITE, 'backupVault': 'alice-backup-vault'}


class FakeAzure:
    """Alice as deployed after -Step backup: apps, sign-in, connector, Copilot, mail, backups, lock, drill."""

    def __init__(self, backup=True):
        self.calls, self.blobs, self.n = [], {}, 0
        self.groups = {RG, RG + '-drill'} if backup else {RG}
        self.resources = [res('Microsoft.Storage/storageAccounts', FILES), res('Microsoft.KeyVault/vaults', 'alice-kv-abc123'),
                          res('Microsoft.ContainerRegistry/registries', 'aliceabc123acr'), res('Microsoft.DBforPostgreSQL/flexibleServers', 'alice-pg-abc123'),
                          res('Microsoft.App/managedEnvironments', 'alice-env'), res('Microsoft.ManagedIdentity/userAssignedIdentities', 'alice-identity'),
                          res('Microsoft.App/containerApps', 'alice-web'), res('Microsoft.App/containerApps', 'alice-mcp'),
                          res('Microsoft.App/jobs', 'alice-migrate-check'), res('Microsoft.App/jobs', 'alice-migrate-apply')]
        if backup:
            self.resources += [res('Microsoft.RecoveryServices/vaults', 'alice-backup-vault'), res('Microsoft.Storage/storageAccounts', OFFSITE),
                               res('Microsoft.App/jobs', 'alice-backup'), res('Microsoft.App/jobs', 'alice-drill')]
        params = {'backup': backup, 'backupNotify': 'stefan@example.org' if backup else '', 'databaseHost': '', 'useAppRoles': False,
                  'pgBackupRetentionDays': 35, 'filesBackupDays': 30, 'offsiteKeepDays': 35, 'offsiteSoftDeleteDays': 35, 'pgGeoRedundantBackup': False,
                  'webAuthClientId': WEB_APP, 'extAppId': API_APP, 'extCallers': CALLERS, 'extAudiences': 'api://copilot-sso', 'mailFrom': 'alice@example.org',
                  'allowedUserObjectIds': [ALSO], 'customDomain': 'alice.example.org', 'connectorClientId': CONN_APP, 'ownerObjectId': ME}
        outs = dict(OUTPUTS) if backup else {k: v for k, v in OUTPUTS.items() if k not in ('offsiteAccount', 'backupVault')}
        self.deployments = [deployment('alice-infra', '2026-09-20T10:00:00.1234567+00:00', {'backup': False}, outs),
                            deployment('alice-apps', '2026-10-07T21:14:03.5551234+00:00', params, outs)]
        if backup: self.deployments.append(deployment('alice-backup', '2026-10-07T21:12:00+00:00', {}, {}))
        wenv = {'ALICE_ROLE': 'web', 'ALICE_MAIL_FROM': 'alice@example.org', 'ALICE_PUBLIC_URL': 'https://alice.example.org',
                'ALICE_OWNER_OBJECT_ID': ME, 'ALICE_USE_APP_ROLES': '0'}
        if backup:
            wenv.update({'ALICE_BACKUP_ACCOUNT': OFFSITE, 'ALICE_BACKUP_KEEP_DAYS': '35', 'ALICE_BACKUP_SOFT_DELETE_DAYS': '35',
                         'ALICE_BACKUP_IMMUTABILITY_LOCKED': '0', 'ALICE_BACKUP_NOTIFY': 'stefan@example.org', 'ALICE_BACKUP_FILES_DAYS': '30',
                         'ALICE_PG_BACKUP_DAYS': '35', 'ALICE_PG_GEO_BACKUP': '0', 'ALICE_BACKUP_LOCK': 'alice-do-not-delete'})
        self.apps = {
            'alice-web': {'name': 'alice-web', 'properties': {'runningStatus': 'Running', 'configuration': {'ingress': {
                'fqdn': 'alice-web.blue-sea.uksouth.azurecontainerapps.io', 'customDomains': [{'name': 'alice.example.org'}]}},
                'template': {'containers': [{'image': 'aliceabc123acr.azurecr.io/alice:9f3e2d1', 'env': env(wenv)}]}}},
            'alice-mcp': {'name': 'alice-mcp', 'properties': {'runningStatus': 'Running', 'configuration': {'ingress': {'fqdn': 'alice-mcp.blue-sea.uksouth.azurecontainerapps.io'}},
                'template': {'containers': [{'image': 'aliceabc123acr.azurecr.io/alice:9f3e2d1', 'env': env({
                    'ALICE_EXT_APP_ID': API_APP, 'ALICE_EXT_CALLERS': CALLERS, 'ALICE_EXT_AUDIENCES': 'api://copilot-sso', 'ALICE_EXT_CONNECTOR_CLIENT_ID': CONN_APP})}]}}}}
        self.auth = {'properties': {'platform': {'enabled': True}, 'identityProviders': {'azureActiveDirectory': {'enabled': True,
                     'registration': {'clientId': WEB_APP}, 'validation': {'defaultAuthorizationPolicy': {'allowedPrincipals': {'identities': [ME, ALSO]}}}}}}}
        self.locks = [{'name': 'alice-do-not-delete', 'level': 'CanNotDelete'}] if backup else []
        self.secrets = ['pg-admin-password', 'database-url', 'openai-api-key', 'anthropic-api-key', 'web-auth-secret', 'connector-secret', 'connector-key']
        self.ad_apps = {WEB_APP: {'appId': WEB_APP, 'displayName': 'Alice web sign-in', 'appRoles': [{'value': v} for v in S.ROLE_VALUES]},
                        GH_APP: {'appId': GH_APP, 'displayName': 'Alice GitHub deploy'}}
        self.sp = {WEB_APP: {'id': 'sp-web-0001', 'appRoleAssignmentRequired': True}}
        self.assigned = [(ME, S.OWNER_ROLE_ID)]       # (person, app role) on the web sign-in's enterprise application
        self.immutability = {'immutabilityPeriodSinceCreationInDays': 35, 'state': 'Unlocked'}
        self.policy_days = 30
        self.pg_readable = True

    def blob_put(self, name, text):
        self.n += 1
        self.blobs[(FILES, name)] = {'text': text, 'etag': f'"0x8D{self.n:04d}"', 'lastModified': f'2026-10-08T12:00:{self.n:02d}+00:00'}

    def __call__(self, args, env=None):
        self.calls.append((list(args), dict(env or {})))
        a = [x for x in args if x not in ('-o', 'json')]
        opt = lambda k: a[a.index(k) + 1] if k in a else None
        ok = lambda obj: (0, json.dumps(obj), '')
        nf = (3, '', 'ERROR: (ResourceNotFound) not found')
        cmd = ' '.join(x for x in a if not x.startswith('-'))
        if a[:2] == ['group', 'show']: return ok({'name': opt('-n')}) if opt('-n') in self.groups else nf
        if a[:2] == ['resource', 'list']: return ok(self.resources) if opt('-g') in self.groups else nf
        if a[:3] == ['deployment', 'group', 'list']: return ok(self.deployments) if opt('-g') in self.groups else nf
        if a[:2] == ['containerapp', 'show']: return ok(self.apps[opt('-n')]) if opt('-n') in self.apps else nf
        if a[:3] == ['containerapp', 'auth', 'show']: return ok(self.auth) if 'alice-web' in self.apps else nf
        if a[:2] == ['lock', 'list']: return ok(self.locks)
        if a[:4] == ['storage', 'account', 'keys', 'list']: return ok([{'keyName': 'key1', 'value': KEY}])
        if a[:2] == ['storage', 'blob'] or a[:2] == ['storage', 'container'] and a[2] == 'create':
            assert (env or {}).get('AZURE_STORAGE_KEY') == KEY, 'the storage key goes to az in its environment'
        if a[:3] == ['storage', 'container', 'create']: return ok({'created': True})
        if a[:3] == ['storage', 'blob', 'show']:
            b = self.blobs.get((opt('--account-name'), opt('-n')))
            return ok({'properties': {'etag': b['etag'], 'lastModified': b['lastModified']}}) if b else (3, '', 'ERROR: The specified blob does not exist. ErrorCode:BlobNotFound')
        if a[:3] == ['storage', 'blob', 'download']:
            b = self.blobs.get((opt('--account-name'), opt('-n')))
            if not b: return (3, '', 'BlobNotFound')
            open(opt('--file'), 'w', encoding='utf-8').write(b['text']); return ok({})
        if a[:3] == ['storage', 'blob', 'upload']:
            key = (opt('--account-name'), opt('-n')); b = self.blobs.get(key)
            if '--if-match' in a and (not b or b['etag'] != opt('--if-match')): return (1, '', 'ERROR: The condition specified using HTTP conditional header(s) is not met. ErrorCode:ConditionNotMet')
            if '--if-none-match' in a and b: return (1, '', 'ERROR: ErrorCode:BlobAlreadyExists')
            self.blob_put(key[1], open(opt('--file'), encoding='utf-8').read()); return ok({})
        if a[:4] == ['storage', 'container', 'immutability-policy', 'show']: return ok(self.immutability) if OFFSITE in [r['name'] for r in self.resources] else nf
        if a[:4] == ['storage', 'account', 'blob-service-properties', 'show']: return ok({'deleteRetentionPolicy': {'days': 35}})
        if a[:3] == ['keyvault', 'secret', 'list']: return ok([{'name': n} for n in self.secrets])
        if a[:3] == ['ad', 'app', 'list']: return ok([x for x in self.ad_apps.values() if x['displayName'] == opt('--display-name')])
        if a[:3] == ['ad', 'app', 'show']: return ok(self.ad_apps[opt('--id')]) if opt('--id') in self.ad_apps else nf
        if a[:4] == ['ad', 'app', 'credential', 'list']: return ok([{'endDateTime': '2027-09-01T00:00:00Z'}])
        if a[:4] == ['ad', 'app', 'federated-credential', 'list']: return ok([{'subject': 'repo:x:ref:refs/heads/main'}, {'subject': 'repo:x:environment:production'}])
        if a[:3] == ['ad', 'sp', 'show']: return ok(self.sp.get(opt('--id'), {}))
        if a[:1] == ['rest'] and opt('--method') == 'GET' and opt('--url') == 'https://graph.microsoft.com/v1.0/servicePrincipals/sp-web-0001/appRoleAssignedTo':
            return ok({'value': [{'principalId': o, 'appRoleId': r} for o, r in self.assigned]})
        if a[:3] == ['backup', 'policy', 'show']: return ok({'properties': {'retentionPolicy': {'dailySchedule': {'retentionDuration': {'count': self.policy_days}}}}})
        if a[:3] == ['backup', 'item', 'list']: return ok([{'properties': {'friendlyName': 'alice', 'lastBackupTime': '2026-10-08T00:10:00Z', 'lastBackupStatus': 'Completed'}}])
        if a[:3] == ['postgres', 'flexible-server', 'show']:
            if not self.pg_readable or opt('-n') not in [r['name'] for r in self.resources]: return nf
            return ok({'fullyQualifiedDomainName': PG_FQDN, 'backup': {'backupRetentionDays': 35, 'geoRedundantBackup': 'Disabled'}})
        if a[:4] == ['containerapp', 'job', 'execution', 'list']: return ok([{'properties': {'status': 'Succeeded', 'startTime': '2026-10-08T01:00:05Z'}}])
        raise AssertionError('unexpected az call: ' + cmd)

    def writes(self):
        """Every recorded command that is not a read (the same test as the read-only guard)."""
        guard, out = S.read_only(lambda args, env=None: (0, '', '')), []
        for c, _ in self.calls:
            try: guard(c)
            except S.AzureError: out.append(c)
        return out

    def state(self):
        b = self.blobs.get((FILES, S.BLOB))
        return json.loads(b['text']) if b else None


def run(fn, *a, **kw):
    lines = []
    code = fn(*a, out=lambda s='': lines.append(str(s)), **kw)
    return code, '\n'.join(lines)


tmp = tempfile.mkdtemp(prefix='alice-state-')
path = lambda n: os.path.join(tmp, n)
def write(p, d): open(p, 'w', encoding='utf-8-sig').write(json.dumps(d))      # PowerShell 5.1 writes a BOM
def read(p): return json.load(open(p, encoding='utf-8-sig'))

# A complete state, as the script holds it after -Step backup
FULL = {**{k: v for k, v in OUTPUTS.items()}, 'keyVault': 'alice-kv-abc123', 'webAuthClientId': WEB_APP, 'extAppId': API_APP, 'extCallers': CALLERS,
        'extAudiences': ['api://copilot-sso'], 'mailFrom': 'alice@example.org', 'alsoAllow': [ALSO], 'customDomain': 'alice.example.org',
        'connectorClientId': CONN_APP, 'backup': True, 'backupNotify': 'stefan@example.org', 'noLock': False, 'githubClientId': GH_APP,
        'copilotAuthId': 'T_auth-config-123', 'image': 'aliceabc123acr.azurecr.io/alice:old', 'databaseHost': PG_FQDN, 'ownerObjectId': ME}

# ---------------- the state is written to Azure ----------------
az = FakeAzure()
p = path('save.json'); write(p, {**FULL, 'pendingPassword': 'NotInAzure123'})
code, text = run(S.save, az, RG, p, who=ME, step='backup')
st = az.state()
t('save: the state is written to the blob alice-setup/azure-state.json in Alice\'s own storage account', code == 0 and st and st['webAuthClientId'] == WEB_APP and st['backup'] is True)
t('save: who, from where, which step and the deployment it has seen are recorded', st['savedBy'] == ME and st['lastStep'] == 'backup' and st['savedAt'] and st['deployedAt'].startswith('2026-10-07T21:14:03'))
t('save: the pending database password never leaves this machine; the local cache keeps it', 'pendingPassword' not in st and 'NotInAzure' not in json.dumps(list(az.blobs.values())) and read(p)['pendingPassword'] == 'NotInAzure123')
t('save: the local file records where and which version (the ETag) it came from', read(p)['_azure']['account'] == FILES and read(p)['_azure']['etag'] == az.blobs[(FILES, S.BLOB)]['etag'])
t('save: each saved version is also kept under history/', any(n.startswith('history/') and n.endswith('-backup.json') for _, n in az.blobs))
t('save: the storage key is never on a command line', not any(KEY in ' '.join(c) for c, _ in az.calls))
t('save: the first write may only create the blob (If-None-Match: *)', any(c[:3] == ['storage', 'blob', 'upload'] and '--if-none-match' in c for c, _ in az.calls))
n = len(az.calls); before = dict(az.blobs)
code, _ = run(S.save, az, RG, p, who=ME, step='apps')
t('save: nothing new = nothing uploaded', code == 0 and az.blobs == before and not any(c[:3] == ['storage', 'blob', 'upload'] for c, _ in az.calls[n:]))
s2 = read(p); s2['mailFrom'] = 'alice2@example.org'; write(p, s2)
code, _ = run(S.save, az, RG, p, who=ME, step='mail')
t('save: a change is uploaded over the version it read (If-Match with its ETag)', code == 0 and az.state()['mailFrom'] == 'alice2@example.org'
  and any(c[:3] == ['storage', 'blob', 'upload'] and '--if-match' in c for c, _ in az.calls[n:]))

# ---------------- two runs at once: the second save is refused, nothing overwritten ----------------
a_path, b_path = path('a.json'), path('b.json')
for q in (a_path, b_path):
    if os.path.exists(q): os.remove(q)
code_a, _ = run(S.load, az, RG, a_path, who=ME); code_b, _ = run(S.load, az, RG, b_path, who=ME)
sa = read(a_path); sa['customDomain'] = 'a.example.org'; write(a_path, sa)
sb = read(b_path); sb['customDomain'] = 'b.example.org'; write(b_path, sb)
run(S.save, az, RG, a_path, who=ME, step='apps')
code, text = run(S.save, az, RG, b_path, who=ME, step='apps')
t('two runs at once: the second save is refused and the first one\'s change stays', code == 4 and az.state()['customDomain'] == 'a.example.org' and 'another run' in text)

# ---------------- the state is read from Azure ----------------
az = FakeAzure(); az.blob_put(S.BLOB, json.dumps({**FULL, 'deployedAt': '2026-10-07T21:14:03.5551234+00:00', 'savedAt': '2026-10-07T21:20:00Z', 'savedFrom': 'Cloud Shell'}))
p = path('fresh.json')
code, text = run(S.load, az, RG, p, who=ME)
t('load: no local file (a new Cloud Shell) = the Azure copy is used and cached locally', code == 0 and read(p)['backup'] is True and read(p)['webAuthClientId'] == WEB_APP
  and read(p)['copilotAuthId'] == 'T_auth-config-123' and 'Cloud Shell' in text)
t('load: up to date with the deployments = no rebuild and nothing written', 'Rebuilt' not in text and not az.writes())
code, text = run(S.load, az, RG, p, who=ME)
t('load: a local file equal to the Azure copy is fine', code == 0 and 'Stopped' not in text)
s3 = read(p); s3['alsoAllow'] = ALSO; s3['pgBackupRetentionDays'] = 35; s3['mailFrom'] = 'alice@example.org '; s3['useAppRoles'] = False; write(p, s3)
code, text = run(S.load, az, RG, p, who=ME)
t('load: the same settings written differently are equal (one item or a list, the default 35 days, unset or false)', code == 0 and 'Stopped' not in text)

# ---------------- refusal when the local file differs ----------------
old = {k: v for k, v in FULL.items() if k not in ('backup', 'backupNotify', 'noLock', 'offsiteAccount', 'backupVault', 'connectorClientId')}
p = path('pc.json'); write(p, old); raw = open(p, 'rb').read()
n = len(az.calls)
code, text = run(S.load, az, RG, p, who=ME)
t('mismatch: a local file older than the Azure copy stops the step (exit 3)', code == 3 and 'differs from the setup state in Azure' in text)
t('mismatch: it names each difference', all(k in text for k in ('backup', 'backupNotify', 'connectorClientId', 'backupVault')))
t('mismatch: it says how to use the Azure copy or the local file deliberately', 'rename or delete' in text and '-UseLocalState' in text)
t('mismatch: neither the local file nor the Azure copy is touched', open(p, 'rb').read() == raw and not [c for c, _ in az.calls[n:] if c[:3] == ['storage', 'blob', 'upload']])
code, text = run(S.load, az, RG, p, use_local=True, who=ME)
t('-UseLocalState: the local file is used deliberately, and said so', code == 0 and 'deliberately' in text and 'backup' not in read(p) and read(p)['_azure']['etag'])
run(S.save, az, RG, p, who=ME, step='apps')
t('-UseLocalState: the local file then replaces the Azure copy when the step saves', not az.state().get('backup') and not az.state().get('connectorClientId'))

# ---------------- rebuild: the Azure copy is missing (Cloud Shell forgot, the PC copy predates -Step backup) ----------------
az = FakeAzure()
p = path('pc-old.json'); write(p, {**old, 'copilotAuthId': 'T_auth-config-123'})
code, text = run(S.load, az, RG, p, who=ME)
st = az.state()
t('rebuild: a missing Azure copy is rebuilt from what is deployed before anything else, and saved', st is not None and 'Rebuilt the setup state' in text and 'there was no copy in Azure' in text)
t('rebuild: backups found (vault, job, lock) and their settings from alice-web', st['backup'] is True and st['noLock'] is False and st['backupNotify'] == 'stefan@example.org'
  and st['offsiteAccount'] == OFFSITE and st['backupVault'] == 'alice-backup-vault' and st['filesBackupDays'] == 30 and st['offsiteImmutabilityLocked'] is False)
t('rebuild: sign-in, the API app, callers, Copilot audiences, connector, mail and custom domain from the apps themselves',
  st['webAuthClientId'] == WEB_APP and st['extAppId'] == API_APP and st['extCallers'] == CALLERS and st['extAudiences'] == ['api://copilot-sso']
  and st['connectorClientId'] == CONN_APP and st['mailFrom'] == 'alice@example.org' and st['customDomain'] == 'alice.example.org')
t('rebuild: the other allowed people from the sign-in (the owner left out); app roles off', st['alsoAllow'] == [ALSO] and st['useAppRoles'] is False)
t('rebuild: names from the deployment outputs; database host and image too', st['keyVault'] == 'alice-kv-abc123' and st['storageAccount'] == FILES
  and st['webUrl'] == OUTPUTS['webUrl'] and st['image'].endswith(':9f3e2d1') and st['githubClientId'] == GH_APP)
t('rebuild: databaseHost left empty by the deployment = the address of postgresServer, never "not set"',
  st['databaseHost'] == PG_FQDN and 'database server alice-pg-abc123: its address' in text)
t('rebuild: what nothing deployed shows is kept from the local file, and said so', st['copilotAuthId'] == 'T_auth-config-123' and 'kept from' in text and 'copilotAuthId' in text)
t('rebuild: it shows each value and where it came from', re.search(r'backup\s+yes\s+\(found: alice-backup-vault', text) and 'alice-web: ALICE_BACKUP_NOTIFY' in text)
t('rebuild: then the old PC copy is refused (it lacks the backup step)', code == 3 and 'differs' in text)
os.remove(p)
code, text = run(S.load, az, RG, p, who=ME)
t('rebuild: with the old file moved away, the rebuilt copy is used (no second rebuild)', code == 0 and read(p)['backup'] is True and 'Rebuilt' not in text)

# ---------------- rebuild: the Azure copy is older than the newest deployment ----------------
az = FakeAzure()
stale = {k: v for k, v in FULL.items() if k not in ('backup', 'backupNotify', 'noLock', 'offsiteAccount', 'backupVault')}
stale.update(useAppRoles=True, deployedAt='2026-10-01T09:00:00Z', savedAt='2026-10-01T09:01:00Z')
az.blob_put(S.BLOB, json.dumps(stale))
p = path('stale.json')
code, text = run(S.load, az, RG, p, who=ME)
st = az.state()
t('older: a copy older than the newest deployment is rebuilt, and says why', code == 0 and 'is older than the deployment of 2026-10-07' in text)
t('older: what was deployed since is added (the backup step done elsewhere)', st['backup'] is True and st['backupNotify'] == 'stefan@example.org' and 'backup' in text)
t('older: only what changed is shown', 'webAuthClientId' not in text.split('Saved to')[0])
t('older: a switch the copy has on is never turned off by inference (app roles remembered, not yet put live)', st['useAppRoles'] is True and 'kept from the Azure copy' in text)
t('older: the rebuilt copy is saved over the version it read, and records the deployment it has seen', st['deployedAt'].startswith('2026-10-07T21:14') and st['lastStep'] == 'rebuild')

# merge rules on their own
m, kept = S.merge({'backup': True, 'noLock': False, 'alsoAllow': ['x'], 'mailFrom': 'a@x', 'customDomain': 'old.example.org'},
                  {'backup': False, 'noLock': True, 'alsoAllow': ['y'], 'mailFrom': '', 'customDomain': 'new.example.org'})
t('merge: backups, the lock and mail are kept when not found deployed; lists joined; a new value wins',
  m['backup'] is True and m['noLock'] is False and m['alsoAllow'] == ['x', 'y'] and m['mailFrom'] == 'a@x' and m['customDomain'] == 'new.example.org'
  and set(kept) == {'backup', 'noLock', 'mailFrom'})

# ---------------- the database host: derived, never empty when a server exists ----------------
az = FakeAzure()
next(d for d in az.deployments if d['name'] == 'alice-apps')['properties']['parameters']['databaseHost'] = {'type': 'String', 'value': 'alice-pg-restored.postgres.database.azure.com'}
live_state, src = S.rebuild(S.Live(az, RG))
t('rebuild: a databaseHost the deployment named (after a restore into a new server) is kept as it is',
  live_state['databaseHost'] == 'alice-pg-restored.postgres.database.azure.com')
az = FakeAzure(); az.pg_readable = False
live_state, _ = S.rebuild(S.Live(az, RG))
t('rebuild: a server whose address cannot be read leaves databaseHost out (the stored value is kept, not blanked)', 'databaseHost' not in live_state)
m, kept = S.merge({'databaseHost': ''}, {'databaseHost': PG_FQDN})
t('rebuild: an Azure copy that says "not set" takes the derived address', m['databaseHost'] == PG_FQDN)

az = FakeAzure()
p = path('dbhost.json'); write(p, {k: v for k, v in FULL.items() if k != 'databaseHost'})
code, text = run(S.database_host, az, RG, p)
t('database-host: not set = set to the address of postgresServer, and said so', code == 0 and read(p)['databaseHost'] == PG_FQDN and PG_FQDN in text and 'alice-pg-abc123' in text)
t('database-host: only reads Azure (the script saves the state afterwards)', not az.writes())
n = len(az.calls)
code, _ = run(S.database_host, az, RG, p)
t('database-host: already set = nothing read, nothing changed', code == 0 and len(az.calls) == n and read(p)['databaseHost'] == PG_FQDN)
write(p, {**FULL, 'databaseHost': 'alice-pg-restored.postgres.database.azure.com'})
code, _ = run(S.database_host, az, RG, p)
t('database-host: a host set after a restore is never replaced', code == 0 and read(p)['databaseHost'] == 'alice-pg-restored.postgres.database.azure.com')
az = FakeAzure(); az.pg_readable = False
write(p, {k: v for k, v in FULL.items() if k != 'databaseHost'}); raw = open(p, 'rb').read()
code, text = run(S.database_host, az, RG, p)
t('database-host: a server whose address cannot be read = refused (5), file untouched, says how to give it', code == 5 and open(p, 'rb').read() == raw
  and 'Stopped before deploying' in text and '-DatabaseHost' in text)
az = FakeAzure(); az.resources = [r for r in az.resources if r['type'] != 'Microsoft.DBforPostgreSQL/flexibleServers']
write(p, {'postgresServer': 'alice-pg-gone'})
code, text = run(S.database_host, az, RG, p)
t('database-host: no server in the resource group yet (the first -Step infra) = deploy, the template creates it', code == 0 and 'databaseHost' not in read(p) and 'creates one' in text)
az = FakeAzure(); real = az.__call__
az_fail = lambda args, env=None: (1, '', 'ERROR: AuthorizationFailed') if args[:2] == ['resource', 'list'] else real(args, env)
write(p, {})
code, text = run(S.database_host, az_fail, RG, p)
t('database-host: the resources cannot be listed = refused, never treated as "no server"', code == 5 and 'could not be read' in text and 'databaseHost' not in read(p))
az = FakeAzure()
write(p, {})
code, _ = run(S.database_host, az, RG, p)
t('database-host: no postgresServer in the state = the one server in the resource group', code == 0 and read(p)['databaseHost'] == PG_FQDN)

az = FakeAzure(); az.blob_put(S.BLOB, json.dumps({**{k: v for k, v in FULL.items() if k != 'databaseHost'}, 'deployedAt': '2026-10-07T21:14:03.5551234+00:00'}))
code, text = run(S.check, az, RG, path('nodb.json'), who=ME)
t('check: a state with no databaseHost while a server exists is flagged', 'Database Alice uses (databaseHost): missing' in text and not az.writes())

# ---------------- a local file for a resource group with no Alice ----------------
az = FakeAzure(); az.groups = set()
p = path('wrong-rg.json'); write(p, FULL)
code, text = run(S.load, az, 'alice-recovered-rg', p, who=ME)
t('a local file describing an Alice, run against an empty resource group, is refused', code == 3 and 'has none' in text and '-ResourceGroup' in text)
p = path('new-rg.json')
code, text = run(S.load, az, 'alice-recovered-rg', p, who=ME)
t('a brand-new resource group with no local file: fine, nothing written', code == 0 and not az.writes() and not os.path.exists(p))
code, _ = run(S.save, az, 'alice-recovered-rg', p if os.path.exists(p) else path('nothing.json'), who=ME)
t('saving before -Step infra has made a storage account: only the local file', code == 0 and not az.writes())

# ---------------- -Step check: read-only, says what each step set up, flags what is missing ----------------
az = FakeAzure(); az.blob_put(S.BLOB, json.dumps({**FULL, 'deployedAt': '2026-10-07T21:14:03.5551234+00:00', 'savedAt': '2026-10-07T21:20:00Z', 'lastStep': 'backup'}))
p = path('check.json'); write(p, FULL); raw = open(p, 'rb').read(); blobs = copy.deepcopy(az.blobs)
code, text = run(S.check, az, RG, p, who=ME)
t('check: lists each step', code == 0 and all(f'\n{s}\n' in text for s in ('state', 'infra', 'signin', 'apps', 'github', 'connector', 'copilot', 'mail', 'backup', 'users')))
t('check: the backup vault, lock, off-site account, retention and the nightly job, with their last run',
  all(x in text for x in ('Recovery Services vault', 'alice-backup-vault', 'File share snapshots kept', '30 days', 'alice-do-not-delete (CanNotDelete)',
                         OFFSITE, 'Off-site copies unchangeable for', 'Database backups kept', 'Nightly off-site copy job', 'Succeeded at 2026-10-08', 'Restore drill job')))
t('check: everything set up = nothing missing', 'Nothing missing.' in text)
t('check: made no changes at all (every az command a read; no blob, no file written)', not az.writes() and az.blobs == blobs and open(p, 'rb').read() == raw)
t('check: never even asks for a container or upload', not any(c[:2] in (['storage', 'blob'], ['storage', 'container']) and c[2] in ('upload', 'create') for c, _ in az.calls))

az.locks = []; az.policy_days = 7
az.resources = [r for r in az.resources if r['name'] != 'alice-backup']
code, text = run(S.check, az, RG, p, who=ME)
t('check: a lifted lock, a missing job and a changed retention are flagged', 'Needs attention (3)' in text and 'Resource group lock: missing' in text
  and 'Nightly off-site copy job: missing' in text and 'File share snapshots kept: differs' in text and not az.writes())

# ---------------- the owner of Alice (ownerObjectId): a setting you choose, kept, and checked; Entra decides who is an owner ----------------
NEW_OWNER = '33333333-3333-3333-3333-333333333333'
live_state, src = S.rebuild(S.Live(FakeAzure(), RG))
t('rebuild: the owner from alice-web (ALICE_OWNER_OBJECT_ID)', live_state.get('ownerObjectId') == ME and 'ALICE_OWNER_OBJECT_ID' in src['ownerObjectId'])
merged, kept = S.merge({**FULL, 'ownerObjectId': NEW_OWNER, 'adminObjectIds': [ME]}, live_state)
t('merge: an owner you chose (-OwnerObjectId) is kept, not put back to what is deployed, until -Step apps puts it live',
  merged['ownerObjectId'] == NEW_OWNER and 'ownerObjectId' in kept and merged['adminObjectIds'] == [ME])
merged, _ = S.merge({k: v for k, v in FULL.items() if k != 'ownerObjectId'}, live_state)
t('merge: an owner never set is filled from what is deployed (so -Step apps never changes it by surprise)', merged['ownerObjectId'] == ME)
az = FakeAzure(); az.blob_put(S.BLOB, json.dumps({**FULL, 'ownerObjectId': NEW_OWNER, 'adminObjectIds': [ME], 'deployedAt': '2026-10-07T21:14:03.5551234+00:00'}))
p = path('owner.json'); write(p, {**FULL, 'ownerObjectId': NEW_OWNER, 'adminObjectIds': [ME]})
code, text = run(S.check, az, RG, p, who=ME)
t('check: an owner fallback not yet live on alice-web is flagged with what to run', re.search(r'DIFFERS\s+Owner of Alice \(ownerObjectId\)\s+the state says ' + NEW_OWNER + ', alice-web has ' + ME, text) and 'run -Step apps' in text)
t('check: the owner without Alice.Owner, and an admin still holding Alice.Owner, are flagged (run -Step users)',
  re.search(r'MISSING\s+Alice.Owner: the owner\s+' + NEW_OWNER + ': run -Step users', text)
  and re.search(r'DIFFERS\s+Alice.Admin: admin\s+' + ME + ': also holds Alice.Owner', text) and not az.writes())
az.assigned = [(NEW_OWNER, S.OWNER_ROLE_ID), (ME, S.ADMIN_ROLE_ID), ('44444444-4444-4444-4444-444444444444', S.OWNER_ROLE_ID)]
az.apps['alice-web']['properties']['template']['containers'][0]['env'] = env({'ALICE_OWNER_OBJECT_ID': NEW_OWNER, 'ALICE_USE_APP_ROLES': '0'})
code, text = run(S.check, az, RG, p, who=ME)
t('check: once -Step users and -Step apps have run, the owner and the admin are ok, and any other owner Entra has is listed',
  re.search(r'ok\s+Owner of Alice \(ownerObjectId\)\s+' + NEW_OWNER, text) and re.search(r'ok\s+Alice.Owner: the owner', text)
  and re.search(r'ok\s+Alice.Admin: admin\s+' + ME, text) and re.search(r'info\s+Other owners \(Alice.Owner in Entra\)\s+4444', text))
setup = open(os.path.join(ROOT, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
t('setup: -OwnerObjectId is a remembered setting; every deployment names it, never simply whoever runs the script',
  '[string]$OwnerObjectId' in setup and "Set-Prop $State 'ownerObjectId'" in setup and 'ownerObjectId = $Me' not in setup
  and setup.count('ownerObjectId = (Owner)') == 2 and "elseif (-not (Owner))" in setup)
t('setup: -Step users gives the owner Alice.Owner first, the admins (you, a previous owner, -AdminObjectIds) Alice.Admin, and takes Alice.Owner from admins only',
  "Assign (Owner) $roles[0] 'the owner of Alice'" in setup and "Assign $o $roles[1] 'admin'" in setup and 'Add-Admin $Me' in setup
  and '--method DELETE' in setup and setup.index("Assign (Owner) $roles[0]") < setup.index('--method DELETE')
  and "if ($old) { Add-Admin $old }" in setup and 'second, break-glass' not in setup and "Sign-In-Others $values['allowedUserObjectIds']" in setup)

# ---------------- -Step users: the app roles JSON sent to Graph (az ad app update --app-roles) ----------------
OTHER_ROLE = {'allowedMemberTypes': ['User'], 'description': 'Someone else\'s role', 'displayName': 'Other', 'id': 'aaaaaaaa-1111-1111-1111-111111111111',
              'isEnabled': True, 'origin': 'Application', 'value': 'Other.Role'}
OLD_OWNER = {'allowedMemberTypes': ['User'], 'description': 'old text', 'displayName': 'Alice Owner', 'id': 'bbbbbbbb-2222-2222-2222-222222222222',
             'isEnabled': True, 'origin': 'Application', 'value': 'Alice.Owner'}


def roles_via_cli(existing_text):
    src, dst = path('roles-now.json'), path('roles-send.json')
    open(src, 'w', encoding='utf-8-sig').write(existing_text)          # PowerShell 5.1 may write a BOM
    code = S.main(['app-roles', '--existing', src, '--out', dst])
    return code, open(dst, encoding='utf-8').read() if code == 0 else ''


def well_typed(roles):
    """Graph's shape: a JSON array of objects; allowedMemberTypes a list of strings; isEnabled a boolean; every other field one string."""
    if not isinstance(roles, list) or not roles: return False
    for r in roles:
        if not isinstance(r, dict) or set(r) - set(S.ROLE_FIELDS): return False
        for k, v in r.items():
            if k == 'allowedMemberTypes':
                if not (isinstance(v, list) and v and all(isinstance(x, str) for x in v)): return False
            elif k == 'isEnabled':
                if not isinstance(v, bool): return False
            elif not isinstance(v, str): return False
    return True


cases = {
    'no roles yet': '[]',
    'empty output': '',
    'other roles kept, an existing Alice.Owner': json.dumps([OTHER_ROLE, OLD_OWNER], indent=2),
    'Windows PowerShell 5.1 wrapping (an array inside the array)': json.dumps([[OTHER_ROLE, OLD_OWNER]]),
    'a single role, not in an array': json.dumps(OTHER_ROLE),
    'a field that came back as a list': json.dumps([{**OTHER_ROLE, 'displayName': ['Other'], 'isEnabled': [True]}]),
}
results = {}
for name, text in cases.items():
    code, sent = roles_via_cli(text)
    results[name] = json.loads(sent) if code == 0 else None
    t(f'app roles JSON ({name}): an array of roles, every field a single value except allowedMemberTypes (a list of strings)',
      code == 0 and sent.lstrip().startswith('[') and well_typed(results[name]))
    t(f'app roles JSON ({name}): Alice.Owner, Alice.Admin and Alice.Member once each, enabled, for users',
      results[name] is not None and [r['value'] for r in results[name] if r['value'].startswith('Alice.')] == list(S.ROLE_VALUES)
      and all(r['isEnabled'] is True and r['allowedMemberTypes'] == ['User'] for r in results[name] if r['value'].startswith('Alice.')))
kept = results['other roles kept, an existing Alice.Owner']
t('app roles JSON: the app\'s other roles are kept, read-only fields (origin) left out',
  kept[0] == {k: v for k, v in OTHER_ROLE.items() if k != 'origin'} and not any('origin' in r for r in kept))
ids = {r['value']: r['id'] for r in kept}
t('app roles JSON: an Alice role that already exists keeps its own ID; the others get the fixed IDs',
  ids['Alice.Owner'] == OLD_OWNER['id'] and ids['Alice.Admin'] == S.ADMIN_ROLE_ID and {r['value']: r['id'] for r in results['no roles yet']}['Alice.Owner'] == S.OWNER_ROLE_ID)
t('app roles JSON: the 5.1 wrapping gives exactly what the plain array gives', results['Windows PowerShell 5.1 wrapping (an array inside the array)'] == kept)
t('app roles JSON: a list where one value belongs is sent as that value', results['a field that came back as a list'][0]['displayName'] == 'Other'
  and results['a field that came back as a list'][0]['isEnabled'] is True)
code, _ = roles_via_cli('not json')
t('app roles: unreadable current roles stop the step before anything is sent', code == 2)
t('check: reads the role IDs the app really has', S.role_ids({'appRoles': [OLD_OWNER]})['Alice.Owner'] == OLD_OWNER['id']
  and S.role_ids({'appRoles': [[OLD_OWNER]]})['Alice.Owner'] == OLD_OWNER['id'] and S.role_ids({})['Alice.Admin'] == S.ADMIN_ROLE_ID)
setup = open(os.path.join(ROOT, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
add_roles = setup.split('function Add-Roles', 1)[1].split('\n  }\n', 1)[0]
t('setup: the app roles are built by azure_state.py app-roles (not ConvertTo-Json), and the JSON is printed when az refuses it',
  'app-roles --existing' in add_roles and 'ConvertTo-Json' not in add_roles and 'catch' in add_roles and 'ReadAllText($send)' in add_roles)
t('setup: the role IDs used for assignments are read back from the app, never assumed',
  "appRoles[?value=='$($r.value)'].id | [0]" in setup and '388aff1f' not in setup.split("if (Want 'users')", 1)[1].split("if (Want 'connector')", 1)[0])
t('setup: no JSON array is read with @(... | ConvertFrom-Json) (Windows PowerShell 5.1 does not unroll it)',
  not re.search(r'@\(\s*AzCli[^\n]*\|\s*ConvertFrom-Json\s*\)', setup) and 'Json-Array (AzCli ad app show' in setup)

az = FakeAzure()          # no Azure copy yet, a deployment newer than everything
code, text = run(S.check, az, RG, path('none.json'), who=ME)
t('check: a missing Azure copy is flagged, and check does not create it', 'Setup state in Azure' in text and 'the next step rebuilds it' in text and az.state() is None and not az.writes())
code, text = run(S.check, FakeAzure(backup=False), RG, path('none.json'), who=ME)
t('check: before -Step backup, backups show as not set up (not as missing)', re.search(r'off\s+Backups\s+not set up', text) and 'Recovery Services vault' not in text)

ro = S.read_only(lambda args, env=None: (0, '[]', ''))
refused = []
for cmd in (['storage', 'blob', 'upload', '-n', 'x'], ['deployment', 'group', 'create', '-g', RG], ['lock', 'delete', '--name', 'show'],
            ['rest', '--method', 'POST', '--url', 'https://graph.microsoft.com/'], ['storage', 'container', 'create', '-n', 'list']):
    try: ro(cmd); refused.append(False)
    except S.AzureError: refused.append(True)
t('read-only guard: any command that is not a read is refused, whatever its arguments say', all(refused)
  and ro(['resource', 'list', '-g', RG])[0] == 0 and ro(['rest', '--method', 'GET', '--url', 'x'])[0] == 0)

# ---------------- the setup script uses it ----------------
setup = open(os.path.join(ROOT, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
t('setup: -Step check and -UseLocalState exist', re.search(r"ValidateSet\([^)]*'check'[^)]*\)\]\[string\]\$Step", setup) and '[switch]$UseLocalState' in setup)
t('setup: the Azure copy is settled before the state is loaded (load, then the cache)', setup.index('Sync-State\n$State = Load-State') > 0
  and "'load', '--resource-group'" in setup and "'--use-local'" in setup)
t('setup: every Save-State also saves to Azure, and the run stops if it cannot', re.search(r'function Save-State\(\$s\) \{.*?StateHelper save .*?LASTEXITCODE -ne 0', setup, re.S))
chk = setup.index("if ($Step -eq 'check')")
t('setup: -Step check runs before anything can save and returns straight after', chk < setup.index('Sync-State\n$State') and chk < setup.index("ContainsKey('DatabaseHost')")
  and 'StateHelper check' in setup[chk:chk + 400] and 'return' in setup[chk:chk + 500])
t('setup: the state is written back at the end of every step', re.search(r"Save-State \$State[^\n]*\nSay 'Done'", setup))
dep = setup[setup.index('function Deploy($stage, $extra) {'):]
dep = dep[:dep.index('\n}\n')]
t('setup: every deployment of main.bicep first makes sure databaseHost is set, and stops if it cannot',
  dep[len('function Deploy($stage, $extra) {'):].lstrip().startswith('Ensure-DatabaseHost')
  and re.search(r'function Ensure-DatabaseHost \{.*?StateHelper database-host .*?LASTEXITCODE -ne 0\) \{ throw', setup, re.S)
  and setup.count('deployment group create') == 2 and "-f $Template" in dep)
t('setup: the helper is stdlib only (it runs in Cloud Shell)', not re.search(r'^(import|from) (requests|azure|psycopg)', open(os.path.join(ROOT, 'deploy', 'azure_state.py')).read(), re.M))
