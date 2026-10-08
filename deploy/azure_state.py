"""The setup state of deploy/azure-setup.ps1, kept in Azure so a run from any machine starts from what is really set up.

The state is what each step set up and every later step must keep (the sign-in app registrations, the Alice API app and
its callers, Copilot's audiences, the custom domain, mail, backups and their retention, the lock, app roles, the database
host after a restore). It used to live only in deploy/azure-state.json on whichever machine ran the step, so a run from a
machine with an old copy (or none: Cloud Shell forgets) could quietly undo an earlier step. Now (Stefan, 8 Oct 2026):

- The copy that counts is a blob in Alice's own storage account (the file share's account; container alice-setup, blob
  azure-state.json). `load` reads it at the start of every step, `save` writes it back each time the script saves (and
  once more at the end). Each saved version is also kept under history/. The local file is a cache of it.
- Missing, or older than the newest deployment in the resource group: it is rebuilt from what is deployed (deployment
  outputs and parameters, the apps' own settings, the web sign-in, the backup resources, the lock) and saved at once, and
  the run shows what was rebuilt and where each value came from.
- A local file that differs from the Azure copy stops the run, unless -UseLocalState (--use-local) says to use it.
- Writes carry the blob's ETag, so two runs at once (the PC and Cloud Shell) never overwrite each other.
- `check` is read-only: what each step has set up, and anything missing. Every az command it runs is a read
  (show, list, download); anything else is refused in code.
- `database-host` runs before every deployment of main.bicep: the state must name the database server Alice uses
  (databaseHost). Not set = the address of the resource group's own server (postgresServer), read from Azure; if that
  cannot be read, the deployment is refused. Only a resource group with no database server yet (the first -Step infra)
  deploys without one, because the template is about to create it.

Stdlib only (it runs from the PC's .venv and from Cloud Shell's python3). Talks to Azure only through the az CLI (AZ,
which the tests replace). Never reads .env; the storage key goes to az in its environment, never on a command line.
Exit codes: 0 fine, 2 Azure could not be read or written, 3 refused (local and Azure differ), 4 someone else saved first,
5 refused: no database host and none could be found.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

CONTAINER = 'alice-setup'
BLOB = 'azure-state.json'
MAIN_DEPLOYMENTS = ('alice-infra', 'alice-migrate', 'alice-apps')    # main.bicep, one name per stage
LOCAL_ONLY = ('pendingPassword',)        # the database password before Key Vault exists: never leaves this machine
BOOKKEEPING = ('_azure', 'savedAt', 'savedBy', 'savedFrom', 'lastStep', 'deployedAt')
NOT_COMPARED = BOOKKEEPING + LOCAL_ONLY + ('image',)   # image: steps always deploy the LIVE image (Image-Ref)
NOT_LIVE = ('copilotAuthId', 'copilotDemoAuthId', 'imageFresh')   # nothing deployed shows these
LISTS = ('alsoAllow', 'extAudiences')
PROTECTIONS_OFF = ('noLock',)          # true = a protection off: never inferred from what is deployed
DEFAULTS = {'pgBackupRetentionDays': 35, 'filesBackupDays': 30, 'offsiteKeepDays': 35, 'offsiteSoftDeleteDays': 35}
TOKEN_STORE = 'ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b'   # Microsoft's Enterprise token store (Copilot)
ROLE_VALUES = ('Alice.Owner', 'Alice.Admin', 'Alice.Member')
READ_VERBS = ('show', 'list', 'download')


class AzureError(Exception): pass
class Conflict(Exception): pass


def run_az(args, env=None):
    """The real az CLI. Returns (exit code, stdout, stderr)."""
    exe = shutil.which('az') or 'az'          # az.cmd on Windows
    try:
        p = subprocess.run([exe, *args, '--only-show-errors'], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env={**os.environ, **(env or {})})
        return p.returncode, p.stdout or '', p.stderr or ''
    except OSError as e:
        return 127, '', f'az could not be started: {e}'


AZ = run_az


def read_only(az):
    """An az that refuses anything but a read: -Step check must never change anything."""
    def guarded(args, env=None):
        verbs = []
        for a in args:                       # the command words, up to the first option
            if a.startswith('-'): break
            verbs.append(a)
        if verbs[:1] == ['rest']:
            ok = '--method' in args and args[args.index('--method') + 1].upper() == 'GET'
        else:
            ok = bool(verbs) and verbs[-1] in READ_VERBS
        if not ok: raise AzureError('refused in read-only mode: az ' + ' '.join(verbs))
        return az(args, env)
    return guarded


# ---------------- small helpers ----------------
def _now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _ts(s):
    """An Azure timestamp as a datetime (any fraction length, Z or +00:00); None if there is none."""
    if not s: return None
    s = str(s).strip().replace('Z', '+00:00')
    if '.' in s:
        head, rest = s.split('.', 1)
        frac = ''.join(ch for ch in rest if ch.isdigit())
        tz = rest[len(frac):]
        s = head + '.' + (frac + '000000')[:6] + tz
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _int(v):
    try: return int(v)
    except (TypeError, ValueError): return None


def _norm(k, v):
    """Values that mean the same thing compare equal: unset = '' = false = [] = the template's default."""
    if k in LISTS:
        items = [v] if isinstance(v, str) else list(v or [])
        items = sorted({str(x).strip().lower() for x in items if x is not None and str(x).strip()})
        return items or None
    if v is None or v is False or v == '' or v == [] or v == {}: return None
    if k in DEFAULTS and _int(v) == DEFAULTS[k]: return None
    if isinstance(v, str): return v.strip() or None
    return v


def _show(v):
    if v is None or v == '' or v == []: return 'not set'
    if isinstance(v, list): return ', '.join(str(x) for x in v)
    if isinstance(v, bool): return 'yes' if v else 'no'
    return str(v)


def differences(a, b):
    """[(key, value in a, value in b)] for every setting that differs (bookkeeping and the image left out)."""
    out = []
    for k in sorted(set(a or {}) | set(b or {})):
        if k in NOT_COMPARED: continue
        x, y = _norm(k, (a or {}).get(k)), _norm(k, (b or {}).get(k))
        if x != y: out.append((k, x, y))
    return out


def _canonical(content):
    keep = {k: v for k, v in content.items() if k not in ('_azure', 'savedAt', 'savedBy', 'savedFrom', 'lastStep') + LOCAL_ONLY}
    return json.dumps(keep, sort_keys=True, separators=(',', ':'))


def _sha(content): return hashlib.sha256(_canonical(content).encode()).hexdigest()


def read_local(path):
    if not path or not os.path.exists(path): return None
    with open(path, encoding='utf-8-sig') as f:
        text = f.read().strip()
    return json.loads(text) if text else {}


def write_local(path, state):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(state, indent=2, sort_keys=True))      # ASCII only: PowerShell 5.1 reads it without a BOM


def _where():
    if os.environ.get('ACC_CLOUD') or os.environ.get('AZUREPS_HOST_ENVIRONMENT', '').startswith('cloud-shell'): return 'Cloud Shell'
    return platform.node() or 'this computer'


# ---------------- reading Azure (management plane) ----------------
class Live:
    """What is deployed in the resource group, each answer read once."""

    def __init__(self, az, rg):
        self.az, self.rg, self._memo = az, rg, {}

    def j(self, *args):
        key = args
        if key not in self._memo:
            code, out, err = self.az(list(args) + ['-o', 'json'])
            try: self._memo[key] = json.loads(out) if code == 0 and out.strip() else None
            except ValueError: self._memo[key] = None
        return self._memo[key]

    def group(self, name=None): return self.j('group', 'show', '-n', name or self.rg)
    def resources(self): return self.j('resource', 'list', '-g', self.rg) or []
    def deployments(self): return self.j('deployment', 'group', 'list', '-g', self.rg) or []
    def app(self, name): return self.j('containerapp', 'show', '-n', name, '-g', self.rg)
    def auth(self): return self.j('containerapp', 'auth', 'show', '-n', 'alice-web', '-g', self.rg)
    def locks(self): return self.j('lock', 'list', '-g', self.rg) or []

    def named(self, rtype, name=None, suffix=None):
        for r in self.resources():
            if (r.get('type') or '').lower() != rtype.lower(): continue
            n = r.get('name') or ''
            if (name and n == name) or (suffix and n.endswith(suffix)): return n
        return None

    def storage_accounts(self):
        return [r.get('name') for r in self.resources() if (r.get('type') or '').lower() == 'microsoft.storage/storageaccounts']


PG_TYPE = 'Microsoft.DBforPostgreSQL/flexibleServers'


def server_fqdn(live, server):
    """The database server's address as Azure reports it, or None when it cannot be read."""
    if not server: return None
    srv = live.j('postgres', 'flexible-server', 'show', '-g', live.rg, '-n', server) or {}
    return (srv.get('fullyQualifiedDomainName') or (srv.get('properties') or {}).get('fullyQualifiedDomainName') or '').strip() or None


def env_of(app):
    try: items = app['properties']['template']['containers'][0].get('env') or []
    except (KeyError, IndexError, TypeError): return {}
    return {e.get('name'): e.get('value', '') for e in items if e.get('name') and 'secretRef' not in e}


def _image(app):
    try: return app['properties']['template']['containers'][0].get('image') or None
    except (KeyError, IndexError, TypeError): return None


def merge(azure, live_state):
    """The Azure copy brought up to date with what is deployed. What is deployed adds and updates; it never switches off
    or blanks what the Azure copy has (the script itself only ever adds: a value missing from what is deployed means a
    deployment that did not finish, or a run with an old copy, and the next step should put it back). Lists are joined.
    Returns (merged, [keys kept from the Azure copy])."""
    merged = {k: v for k, v in (azure or {}).items() if k not in BOOKKEEPING}
    kept = []
    for k, v in live_state.items():
        old = merged.get(k)
        if azure is None or k not in merged: merged[k] = v; continue
        if k in LISTS:
            have = [old] if isinstance(old, str) else list(old or [])
            merged[k] = have + [x for x in (v or []) if str(x).lower() not in {str(h).lower() for h in have}]
        elif k in PROTECTIONS_OFF and v and not old and azure.get('backup'):
            kept.append(k)                                  # the lock stays wanted
        elif _norm(k, v) is None and _norm(k, old) is not None:
            kept.append(k)
        else:
            merged[k] = v
    return merged, kept


def newest_deployment(live):
    stamps = [(_ts((d.get('properties') or {}).get('timestamp')), (d.get('properties') or {}).get('timestamp')) for d in live.deployments()]
    stamps = [s for s in stamps if s[0]]
    return max(stamps)[1] if stamps else ''


def older(saved, newest):
    """True when the newest deployment is later than the one the saved state had seen."""
    n = _ts(newest)
    if not n: return False
    s = _ts(saved)
    return s is None or n > s


def find_account(live, state=None):
    """Alice's own storage account (the file share's), or None when there is no Alice in the resource group yet."""
    names = live.storage_accounts()
    mine = [n for n in names if n.endswith('files')]
    want = (state or {}).get('storageAccount')
    if want and want in names: return want
    for d in live.deployments():
        out = ((d.get('properties') or {}).get('outputs') or {}).get('storageAccount') or {}
        if out.get('value') in names: return out['value']
    return mine[0] if len(mine) == 1 else None


def rebuild(live):
    """The state as it is deployed now: {key: value} and {key: where it was read}. A key is left out when its source
    could not be read (so a stored value is kept rather than guessed)."""
    s, src = {}, {}

    def put(k, v, where):
        if v is None: return
        s[k] = v; src[k] = where

    def ok(d): return ((d.get('properties') or {}).get('provisioningState') or '') == 'Succeeded'
    def stamp(d): return _ts((d.get('properties') or {}).get('timestamp')) or datetime.min.replace(tzinfo=timezone.utc)
    deps = sorted([d for d in live.deployments() if d.get('name') in MAIN_DEPLOYMENTS and ok(d)], key=stamp)
    for d in deps:     # oldest first: the newest deployment's outputs win
        for k, o in ((d.get('properties') or {}).get('outputs') or {}).items():
            if (o or {}).get('value'): put(k, o['value'], f"deployment {d['name']}, output {k}")

    def param(d, k):
        p = ((d or {}).get('properties') or {}).get('parameters') or {}
        return (p.get(k) or {}).get('value') if k in p else None
    newest = deps[-1] if deps else None
    apps = ([d for d in deps if d['name'] == 'alice-apps'] or [None])[-1]

    resources = live.resources()
    for key, rtype, kw in (('acrName', 'Microsoft.ContainerRegistry/registries', {}), ('keyVaultName', 'Microsoft.KeyVault/vaults', {}),
                           ('storageAccount', 'Microsoft.Storage/storageAccounts', {'suffix': 'files'}),
                           ('postgresServer', 'Microsoft.DBforPostgreSQL/flexibleServers', {})):
        if key not in s:
            n = live.named(rtype, **kw) if kw else next((r['name'] for r in resources if (r.get('type') or '').lower() == rtype.lower()), None)
            if n: put(key, n, f'resource {n}')
    if 'acrName' in s and 'acrLoginServer' not in s: put('acrLoginServer', s['acrName'] + '.azurecr.io', f"registry {s['acrName']}")
    if 'keyVaultName' in s: put('keyVault', s['keyVaultName'], src['keyVaultName'])
    if 'storageAccount' in s and 'shareName' not in s: put('shareName', 'alice', "the template's share name")

    web, mcp = live.app('alice-web'), live.app('alice-mcp')
    wenv, menv = env_of(web), env_of(mcp)
    if web:
        put('image', _image(web), 'alice-web: its running image')
        put('mailFrom', wenv.get('ALICE_MAIL_FROM', ''), 'alice-web: ALICE_MAIL_FROM')
        put('useAppRoles', wenv.get('ALICE_USE_APP_ROLES') == '1', 'alice-web: ALICE_USE_APP_ROLES')
        doms = ((web.get('properties') or {}).get('configuration') or {}).get('ingress') or {}
        doms = [c.get('name') for c in (doms.get('customDomains') or []) if c.get('name')]
        put('customDomain', doms[0].lower() if doms else '', 'alice-web: custom domain')
    elif apps:
        put('customDomain', param(apps, 'customDomain'), 'deployment alice-apps, parameter customDomain')
        put('mailFrom', param(apps, 'mailFrom'), 'deployment alice-apps, parameter mailFrom')
    if mcp:
        put('extAppId', menv.get('ALICE_EXT_APP_ID', ''), 'alice-mcp: ALICE_EXT_APP_ID')
        put('extCallers', menv.get('ALICE_EXT_CALLERS', ''), 'alice-mcp: ALICE_EXT_CALLERS')
        put('extAudiences', [a.strip() for a in menv.get('ALICE_EXT_AUDIENCES', '').split(',') if a.strip()], 'alice-mcp: ALICE_EXT_AUDIENCES')
        put('connectorClientId', menv.get('ALICE_EXT_CONNECTOR_CLIENT_ID', ''), 'alice-mcp: ALICE_EXT_CONNECTOR_CLIENT_ID')
    elif apps:
        for k in ('extAppId', 'extCallers', 'connectorClientId'): put(k, param(apps, k), f'deployment alice-apps, parameter {k}')
        aud = param(apps, 'extAudiences')
        if aud is not None: put('extAudiences', [a.strip() for a in aud.split(',') if a.strip()], 'deployment alice-apps, parameter extAudiences')

    auth = live.auth() if web else None
    aad = (((auth or {}).get('properties') or auth or {}).get('identityProviders') or {}).get('azureActiveDirectory') or {}
    put('webAuthClientId', ((aad.get('registration') or {}).get('clientId')) or (param(apps, 'webAuthClientId') if apps else None) or None,
        'alice-web sign-in: client ID' if (aad.get('registration') or {}).get('clientId') else 'deployment alice-apps, parameter webAuthClientId')
    who = ((((aad.get('validation') or {}).get('defaultAuthorizationPolicy') or {}).get('allowedPrincipals') or {}).get('identities'))
    owner = wenv.get('ALICE_OWNER_OBJECT_ID') or (param(apps, 'ownerObjectId') if apps else '') or ''
    if who:
        put('alsoAllow', [i for i in who if i and i.lower() != owner.lower()], 'alice-web sign-in: allowed people other than the owner')
    elif apps and param(apps, 'allowedUserObjectIds') is not None:
        put('alsoAllow', list(param(apps, 'allowedUserObjectIds') or []), 'deployment alice-apps, parameter allowedUserObjectIds')

    # The database Alice uses: the host the newest deployment named (after a restore into a new server), else the address
    # of this resource group's own server, which is what the template used when databaseHost was empty. Never left empty
    # when there is a server; left out (the stored value kept) when the address cannot be read.
    host = (param(newest, 'databaseHost') or '').strip() if newest else ''
    if host: put('databaseHost', host, f"deployment {newest['name']}, parameter databaseHost")
    elif s.get('postgresServer'):
        put('databaseHost', server_fqdn(live, s['postgresServer']),
            f"database server {s['postgresServer']}: its address (the deployment left databaseHost empty, which meant this server)")

    # Backups: the resources themselves, then the settings they were deployed with (alice-web's ALICE_BACKUP_* settings)
    vault = live.named('Microsoft.RecoveryServices/vaults', name='alice-backup-vault')
    job = live.named('Microsoft.App/jobs', name='alice-backup')
    offsite = live.named('Microsoft.Storage/storageAccounts', suffix='offsite')
    if resources or web:
        on = bool(vault or job or wenv.get('ALICE_BACKUP_ACCOUNT'))
        put('backup', on, 'found: ' + ', '.join(x for x in (vault, job, offsite) if x) if on else 'no backup vault, job or settings found')
        if on:
            if vault: put('backupVault', vault, f'resource {vault}')
            if offsite: put('offsiteAccount', offsite, f'resource {offsite}')
            lock = next((l for l in live.locks() if l.get('name') == 'alice-do-not-delete'), None)
            if 'ALICE_BACKUP_LOCK' in wenv: put('noLock', wenv['ALICE_BACKUP_LOCK'] == '', 'alice-web: ALICE_BACKUP_LOCK')
            else: put('noLock', lock is None, 'resource group lock alice-do-not-delete ' + ('found' if lock else 'not found'))
            for k, e, p in (('backupNotify', 'ALICE_BACKUP_NOTIFY', 'backupNotify'),):
                put(k, wenv[e] if e in wenv else param(newest, p), f'alice-web: {e}' if e in wenv else f'deployment parameter {p}')
            for k, e, p in (('filesBackupDays', 'ALICE_BACKUP_FILES_DAYS', 'filesBackupDays'), ('offsiteKeepDays', 'ALICE_BACKUP_KEEP_DAYS', 'offsiteKeepDays'),
                            ('offsiteSoftDeleteDays', 'ALICE_BACKUP_SOFT_DELETE_DAYS', 'offsiteSoftDeleteDays'),
                            ('pgBackupRetentionDays', 'ALICE_PG_BACKUP_DAYS', 'pgBackupRetentionDays')):
                v = _int(wenv.get(e)) if e in wenv else _int(param(newest, p))
                put(k, v, f'alice-web: {e}' if e in wenv else f'deployment parameter {p}')
            geo = (wenv.get('ALICE_PG_GEO_BACKUP') == '1') if 'ALICE_PG_GEO_BACKUP' in wenv else param(newest, 'pgGeoRedundantBackup')
            put('pgGeoBackup', bool(geo) if geo is not None else None,
                'alice-web: ALICE_PG_GEO_BACKUP' if 'ALICE_PG_GEO_BACKUP' in wenv else 'deployment parameter pgGeoRedundantBackup')
            locked = None
            if offsite:
                pol = live.j('storage', 'container', 'immutability-policy', 'show', '--account-name', offsite, '-c', 'alice-offsite', '-g', live.rg)
                if pol: locked = (pol.get('state') or (pol.get('properties') or {}).get('state') or '').lower() == 'locked'
            if locked is None and 'ALICE_BACKUP_IMMUTABILITY_LOCKED' in wenv: locked = wenv['ALICE_BACKUP_IMMUTABILITY_LOCKED'] == '1'
            put('offsiteImmutabilityLocked', locked, f'off-site container immutability policy on {offsite}')

    if live.named('Microsoft.App/containerApps', name='alice-demo-web'):
        demo = next((d for d in live.deployments() if d.get('name') == 'alice-demo' and ok(d)), None)
        outs = ((demo or {}).get('properties') or {}).get('outputs') or {}
        for k in ('demoWebUrl', 'demoMcpUrl'):
            if (outs.get(k) or {}).get('value'): put(k, outs[k]['value'], f'deployment alice-demo, output {k}')
    elif resources:
        put('demoWebUrl', '', 'no alice-demo-web app'); put('demoMcpUrl', '', 'no alice-demo-web app')

    gh = live.j('ad', 'app', 'list', '--display-name', 'Alice GitHub deploy')
    if gh and len(gh) == 1 and gh[0].get('appId'): put('githubClientId', gh[0]['appId'], 'app registration "Alice GitHub deploy"')
    return s, src


# ---------------- the state blob (data plane, with the account key in az's environment) ----------------
class Store:
    def __init__(self, az, rg, account):
        self.az, self.rg, self.account, self._key = az, rg, account, None

    def _env(self):
        if self._key is None:
            code, out, err = self.az(['storage', 'account', 'keys', 'list', '-g', self.rg, '-n', self.account, '-o', 'json'])
            try: self._key = json.loads(out)[0]['value'] if code == 0 else ''
            except (ValueError, IndexError, KeyError, TypeError): self._key = ''
            if not self._key: raise AzureError(f'could not read the key of storage account {self.account}: {err.strip()[:300]}')
        return {'AZURE_STORAGE_KEY': self._key}

    def _args(self, name=BLOB):
        return ['--account-name', self.account, '--auth-mode', 'key', '-c', CONTAINER, '-n', name]

    def where(self): return f'{self.account}/{CONTAINER}/{BLOB}'

    def props(self):
        code, out, err = self.az(['storage', 'blob', 'show', *self._args(), '-o', 'json'], self._env())
        if code != 0:
            if any(m in err for m in ('BlobNotFound', 'ContainerNotFound', 'does not exist', 'ResourceNotFound', 'not found')): return None
            raise AzureError(f'could not read {self.where()}: {err.strip()[:300]}')
        p = (json.loads(out) or {}).get('properties') or {}
        return {'etag': p.get('etag'), 'lastModified': p.get('lastModified')}

    def read(self):
        props = self.props()
        if not props: return None, None
        box = tempfile.mkdtemp(prefix='alice-state-')
        tmp = os.path.join(box, BLOB)
        try:
            code, out, err = self.az(['storage', 'blob', 'download', *self._args(), '--file', tmp, '-o', 'json'], self._env())
            if code != 0: raise AzureError(f'could not read {self.where()}: {err.strip()[:300]}')
            with open(tmp, encoding='utf-8-sig') as f: return json.loads(f.read() or '{}'), props
        finally:
            shutil.rmtree(box, ignore_errors=True)

    def write(self, content, etag=None, step=''):
        env = self._env()
        if not etag:
            self.az(['storage', 'container', 'create', '--account-name', self.account, '--auth-mode', 'key', '-n', CONTAINER, '-o', 'json'], env)
        box = tempfile.mkdtemp(prefix='alice-state-')
        tmp = os.path.join(box, BLOB)
        try:
            with open(tmp, 'w', encoding='utf-8') as f: f.write(json.dumps(content, indent=2, sort_keys=True))
            cond = ['--if-match', etag] if etag else ['--if-none-match', '*']
            code, out, err = self.az(['storage', 'blob', 'upload', *self._args(), '--file', tmp, '--overwrite', *cond, '-o', 'json'], env)
            if code != 0:
                if any(m in err for m in ('ConditionNotMet', '412', 'BlobAlreadyExists', 'already exists')): raise Conflict(err.strip()[:300])
                raise AzureError(f'could not write {self.where()}: {err.strip()[:300]}')
            stamp = content.get('savedAt', _now()).replace(':', '').replace('-', '')
            self.az(['storage', 'blob', 'upload', *self._args(f"history/{stamp}-{step or 'save'}.json"), '--file', tmp, '-o', 'json'], env)  # best effort
        finally:
            shutil.rmtree(box, ignore_errors=True)
        return self.props()


def _cache(path, state, local, account, props, sha):
    """The local file = the chosen state, plus this machine's own pending password, plus where it came from in Azure."""
    out = {k: v for k, v in state.items() if k != '_azure'}
    for k in LOCAL_ONLY:
        if local and k in local: out[k] = local[k]
    out['_azure'] = {'account': account, 'etag': (props or {}).get('etag'), 'lastModified': (props or {}).get('lastModified'), 'sha256': sha}
    write_local(path, out)


def _upload(store, content, etag, who, step, newest):
    content = {k: v for k, v in content.items() if k not in ('_azure',) + LOCAL_ONLY}
    content['deployedAt'] = newest or content.get('deployedAt', '')
    content.update(savedAt=_now(), savedBy=who or '', savedFrom=_where(), lastStep=step or '')
    props = store.write(content, etag, step)
    return content, props


# ---------------- the commands ----------------
def load(az, rg, path, use_local=False, who='', out=print):
    local = read_local(path)
    local_name = path or 'azure-state.json'
    live = Live(az, rg)
    acct = find_account(live, local)
    if not acct:
        content = {k: v for k, v in (local or {}).items() if k not in NOT_COMPARED and _norm(k, v) is not None}
        if content and not use_local:
            out(f'Stopped: {local_name} describes an Alice (storage account {local.get("storageAccount") or "?"}), but resource group {rg} has none.')
            out('Check -ResourceGroup. To build a new Alice there with these settings deliberately, add -UseLocalState.')
            return 3
        out(f'No Alice in resource group {rg} yet: nothing in Azure to read. The state is kept in Azure from the first deployment on.')
        return 0
    store = Store(az, rg, acct)
    try:
        azure, props = store.read()
    except AzureError as e:
        out(f'Stopped: {e}'); return 2
    newest = newest_deployment(live)
    if azure is None or older(azure.get('deployedAt'), newest):
        why = 'there was no copy in Azure' if azure is None else f"the copy in Azure (saved {azure.get('savedAt') or '?'}) is older than the deployment of {newest}"
        live_state, src = rebuild(live)
        merged, kept_azure = merge(azure, live_state)
        kept = []
        for k in NOT_LIVE:
            if k not in merged and local and _norm(k, local.get(k)) is not None:
                merged[k] = local[k]; kept.append(k)
        out(f'Rebuilt the setup state from what is deployed in {rg} ({why}):')
        shown = 0
        for k in sorted(live_state):
            if k in kept_azure: continue
            before = _norm(k, (azure or {}).get(k)); after = _norm(k, merged[k])
            if azure is not None and before == after: continue
            change = _show(merged[k]) if azure is None else f"{_show((azure or {}).get(k))} -> {_show(merged[k])}"
            out(f'  {k:<26} {change}   ({src[k]})'); shown += 1
        if azure is not None and not shown: out('  nothing had changed')
        if kept_azure: out(f"  kept from the Azure copy, though not found deployed (-Step check shows what is missing): {', '.join(kept_azure)}")
        if kept: out(f"  kept from {local_name} (nothing deployed shows them): {', '.join(kept)}")
        try:
            content, props = _upload(store, merged, (props or {}).get('etag'), who, 'rebuild', newest)
        except Conflict:
            out('Stopped: another run saved the setup state in Azure while this one was rebuilding it. Run the step again.'); return 4
        except AzureError as e:
            out(f'Stopped: {e}'); return 2
        out(f'Saved to {store.where()}.')
        azure = content
    diffs = differences(local, azure) if local is not None else []
    if diffs and not use_local:
        out(f'Stopped: {local_name} differs from the setup state in Azure ({store.where()}, saved {azure.get("savedAt") or "?"}'
            + (f' from {azure["savedFrom"]}' if azure.get('savedFrom') else '') + '):')
        for k, a, b in diffs: out(f'  {k:<26} here: {_show(a):<40} Azure: {_show(b)}')
        out('Nothing was run. The Azure copy is the one to trust (it is rebuilt from what is deployed when it falls behind).')
        out(f'  To use it: rename or delete {local_name} and run the step again; the file then becomes a cache of the Azure copy.')
        out('  To use the local file instead, deliberately: add -UseLocalState (it then replaces the Azure copy when the step saves).')
        return 3
    if diffs:
        out(f'Using {local_name} deliberately (-UseLocalState). It replaces the Azure copy when this step saves. It differs in: '
            + ', '.join(k for k, _, _ in diffs))
        chosen = {k: v for k, v in local.items() if k != '_azure'}
    else:
        chosen = azure
    _cache(path, chosen, local, acct, props, _sha(azure))
    out(f'Setup state read from {store.where()}' + (f" (saved {azure.get('savedAt')}" + (f" from {azure['savedFrom']}" if azure.get('savedFrom') else '') + ')' if azure.get('savedAt') else '') + '.')
    return 0


def save(az, rg, path, who='', step='', out=print):
    state = read_local(path) or {}
    meta = state.get('_azure') or {}
    live = Live(az, rg)
    acct = meta.get('account') or find_account(live, state)
    if not acct: return 0                    # no Alice in Azure yet (before -Step infra): the local file is all there is
    newest = newest_deployment(live)
    content = {k: v for k, v in state.items() if k not in ('_azure',) + LOCAL_ONLY}
    content['deployedAt'] = newest or content.get('deployedAt', '')
    if meta.get('account') == acct and meta.get('sha256') == _sha(content): return 0     # nothing new to save
    store = Store(az, rg, acct)
    try:
        content, props = _upload(store, content, meta.get('etag'), who, step, newest)
    except Conflict:
        out(f'Stopped: the setup state in Azure ({store.where()}) was saved by another run since this one read it, so it was not overwritten.')
        out('Run the step again: it starts from the newer state.')
        return 4
    except AzureError as e:
        out(f'Could not save the setup state to Azure: {e}'); return 2
    _cache(path, content, state, acct, props, _sha(content))
    return 0


def database_host(az, rg, path, out=print):
    """Before any deployment of main.bicep. The local state (the cache the script then saves to Azure) gets databaseHost
    when it has none: the address of the resource group's database server. Refused (5) when there is a server but its
    address cannot be read, so main.bicep is never deployed with an empty databaseHost for an existing database."""
    state = read_local(path) or {}
    if (state.get('databaseHost') or '').strip(): return 0
    live = Live(az, rg)
    listed = live.j('resource', 'list', '-g', rg) if live.group() else []
    if listed is None:
        out(f'Stopped before deploying: the resources in {rg} could not be read, so the database server Alice uses is not known.')
        out('Check you are signed in to the right subscription (az account show), then run the step again. Nothing was changed.')
        return 5
    servers = [r.get('name') for r in listed if (r.get('type') or '').lower() == PG_TYPE.lower()]
    server = state.get('postgresServer') if state.get('postgresServer') in servers else (servers[0] if len(servers) == 1 else None)
    if not servers:
        out(f'No database server in {rg} yet: this deployment creates one and Alice uses it (databaseHost is set from it next time).')
        return 0
    fqdn = server_fqdn(live, server)
    if not fqdn:
        which = server or ', '.join(servers)
        out(f'Stopped before deploying: databaseHost is not set and the address of the database server ({which}) could not be read.')
        out("Give it once with -DatabaseHost <server>.postgres.database.azure.com (the server Alice uses now). Nothing was changed.")
        return 5
    state['databaseHost'] = fqdn
    write_local(path, state)
    out(f'databaseHost was not set: now {fqdn}, the address of database server {server} (the one Alice uses; nothing about it changes).')
    return 0


def check(az, rg, path, who='', out=print):
    """Read-only: what each step has set up, and anything missing. Changes nothing, writes no file."""
    az = read_only(az)
    live = Live(az, rg)
    rows = []

    def row(step, item, status, detail=''): rows.append((step, item, status, detail))
    if not live.group():
        out(f'Resource group {rg} was not found (or you cannot read it). Nothing is set up there.'); return 0
    local = read_local(path)
    res = live.resources()
    has = lambda rtype, **kw: live.named(rtype, **kw)
    web, mcp = live.app('alice-web'), live.app('alice-mcp')
    wenv, menv = env_of(web), env_of(mcp)

    # ---- the state itself
    acct = find_account(live, local)
    azure = None
    if acct:
        try:
            azure, props = Store(az, rg, acct).read()
        except AzureError as e:
            row('state', 'Setup state in Azure', 'MISSING', str(e))
    newest = newest_deployment(live)
    live_state, src = rebuild(live) if acct else ({}, {})
    if acct and azure is None:
        row('state', 'Setup state in Azure', 'MISSING', f'no {CONTAINER}/{BLOB} in {acct}: the next step rebuilds it from what is deployed')
    elif azure is not None:
        row('state', 'Setup state in Azure', 'ok', f"{acct}/{CONTAINER}/{BLOB}, saved {azure.get('savedAt') or '?'}"
            + (f" from {azure['savedFrom']}" if azure.get('savedFrom') else '') + (f", step {azure['lastStep']}" if azure.get('lastStep') else ''))
        if older(azure.get('deployedAt'), newest):
            row('state', 'Up to date with the deployments', 'DIFFERS', f'a deployment at {newest} is newer: the next step rebuilds it')
        stale = [(k, a, b) for k, a, b in differences({k: azure.get(k) for k in live_state}, live_state)]
        for k, a, b in stale: row('state', f'  {k}', 'DIFFERS', f'Azure copy: {_show(a)}; deployed: {_show(b)} ({src[k]})')
    else:
        row('state', 'Setup state in Azure', 'off', 'no Alice here yet')
    if local is None: row('state', 'Local cache', 'info', 'none on this machine (the Azure copy is used)')
    elif azure is not None:
        d = differences(local, azure)
        row('state', 'Local cache', 'DIFFERS' if d else 'ok', ('differs in ' + ', '.join(k for k, _, _ in d) + ': a step would stop (or use -UseLocalState)') if d else 'matches the Azure copy')
    state = azure or local or {}

    # ---- infra
    for item, rtype, kw in (('Storage account (file share)', 'Microsoft.Storage/storageAccounts', {'suffix': 'files'}),
                            ('Key Vault', 'Microsoft.KeyVault/vaults', {}), ('Container registry', 'Microsoft.ContainerRegistry/registries', {}),
                            ('PostgreSQL server', 'Microsoft.DBforPostgreSQL/flexibleServers', {}),
                            ('Container Apps environment', 'Microsoft.App/managedEnvironments', {}),
                            ('Managed identity alice-identity', 'Microsoft.ManagedIdentity/userAssignedIdentities', {'name': 'alice-identity'})):
        n = has(rtype, **kw) if kw else next((r['name'] for r in res if (r.get('type') or '').lower() == rtype.lower()), None)
        row('infra', item, 'ok' if n else 'MISSING', n or 'not found: run -Step infra')
    pg_here = next((r['name'] for r in res if (r.get('type') or '').lower() == PG_TYPE.lower()), None)
    dbh = (state.get('databaseHost') or '').strip()
    if pg_here:
        row('infra', 'Database Alice uses (databaseHost)', 'ok' if dbh else 'MISSING',
            dbh or f'not set: the next step sets it from {pg_here}, or stops if it cannot read its address')
    kv = next((r['name'] for r in res if (r.get('type') or '').lower() == 'microsoft.keyvault/vaults'), None)
    listed = live.j('keyvault', 'secret', 'list', '--vault-name', kv) if kv else None
    secrets = {s.get('name') for s in (listed or [])}
    if kv and listed is None:
        row('infra', 'Key Vault secrets', 'info', f'could not list the secrets in {kv} (you need Key Vault Secrets Officer there); not checked')
        kv = None
    if kv:
        for n in ('pg-admin-password', 'database-url'):
            row('infra', f'Key Vault secret {n}', 'ok' if n in secrets else 'MISSING', '' if n in secrets else 'not in Key Vault')
        got = [n for n in ('openai-api-key', 'anthropic-api-key', 'xai-api-key', 'elevenlabs-api-key', 'alice-twelvedata-key') if n in secrets]
        row('secrets', 'API keys in Key Vault', 'ok' if got else 'off', ', '.join(got) if got else 'none stored: run -Step secrets')
    # ---- image, migrate
    img = _image(web)
    row('image', 'Live image (alice-web)', 'ok' if img else 'off', img or 'no apps yet')
    for j in ('alice-migrate-check', 'alice-migrate-apply'):
        n = has('Microsoft.App/jobs', name=j)
        row('migrate', f'Job {j}', 'ok' if n else 'off', '' if n else 'not created (only needed at cut-over)')
    row('files', 'Documents and images on the share', 'info', 'copied once at cut-over; not checked here')
    # ---- signin, apps
    auth = live.auth() if web else None
    aad = (((auth or {}).get('properties') or auth or {}).get('identityProviders') or {}).get('azureActiveDirectory') or {}
    cid = (aad.get('registration') or {}).get('clientId') or state.get('webAuthClientId')
    app = live.j('ad', 'app', 'show', '--id', cid) if cid else None
    row('signin', 'App registration "Alice web sign-in"', 'ok' if app else 'MISSING', cid or 'not created: run -Step signin')
    if kv: row('signin', 'Key Vault secret web-auth-secret', 'ok' if 'web-auth-secret' in secrets else 'MISSING', '')
    if app:
        creds = live.j('ad', 'app', 'credential', 'list', '--id', cid) or []
        ends = sorted(_ts(c.get('endDateTime')) for c in creds if _ts(c.get('endDateTime')))
        if ends:
            left = (ends[-1] - datetime.now(timezone.utc)).days
            row('signin', 'Sign-in secret', 'ok' if left > 30 else 'DIFFERS', f"expires {ends[-1]:%Y-%m-%d}" + ('' if left > 30 else ': renew with -Step signin'))
    for name in ('alice-web', 'alice-mcp'):
        a = web if name == 'alice-web' else mcp
        if a:
            p = a.get('properties') or {}
            fq = ((p.get('configuration') or {}).get('ingress') or {}).get('fqdn') or ''
            row('apps', name, 'ok', f"{p.get('runningStatus') or p.get('provisioningState') or ''} https://{fq}".strip())
        else:
            row('apps', name, 'MISSING' if state.get('webUrl') else 'off', 'not found: run -Step apps')
    if web:
        row('apps', 'Entra sign-in in front of alice-web', 'ok' if aad.get('enabled', True) and cid else 'MISSING', '')
        dom = live_state.get('customDomain')
        row('apps', 'Custom domain', 'ok' if dom else 'off', dom or 'none')
    # ---- github
    gh = live_state.get('githubClientId') or state.get('githubClientId')
    if gh:
        fed = live.j('ad', 'app', 'federated-credential', 'list', '--id', gh) or []
        row('github', 'App registration "Alice GitHub deploy"', 'ok', f'{gh}, {len(fed)} GitHub sign-in record(s)')
    else:
        row('github', 'App registration "Alice GitHub deploy"', 'off', 'not found: -Step github -GitHubRepo owner/name')
    # ---- connector, demo, copilot, mail
    con = menv.get('ALICE_EXT_CONNECTOR_CLIENT_ID') or ''
    if con or state.get('connectorClientId'):
        row('connector', 'Claude connector on alice-mcp', 'ok' if con else 'MISSING', con or 'in the state but not on alice-mcp: run -Step connector')
        if kv:
            for n in ('connector-secret', 'connector-key'): row('connector', f'Key Vault secret {n}', 'ok' if n in secrets else 'MISSING', '')
    else:
        row('connector', 'Claude connector', 'off', 'not set up')
    demo = [n for n in ('alice-demo-web', 'alice-demo-mcp') if has('Microsoft.App/containerApps', name=n)]
    row('demo', 'Demo Alice', 'ok' if len(demo) == 2 else ('MISSING' if demo or state.get('demoWebUrl') else 'off'), ', '.join(demo) or 'not set up')
    aud = menv.get('ALICE_EXT_AUDIENCES') or ''
    if aud or state.get('extAudiences'):
        row('copilot', 'Copilot audiences on alice-mcp', 'ok' if aud else 'MISSING', aud or 'in the state but not on alice-mcp')
        row('copilot', 'Copilot token store allowed', 'ok' if TOKEN_STORE in (menv.get('ALICE_EXT_CALLERS') or '') else 'MISSING', '')
    else:
        row('copilot', 'Microsoft 365 Copilot', 'off', 'not set up')
    mf = wenv.get('ALICE_MAIL_FROM') or ''
    row('mail', 'Alice sends email', 'ok' if mf else ('MISSING' if state.get('mailFrom') else 'off'), mf or 'not set up (-Step mail)')

    # ---- backup
    vault = has('Microsoft.RecoveryServices/vaults', name='alice-backup-vault')
    job = has('Microsoft.App/jobs', name='alice-backup')
    offsite = has('Microsoft.Storage/storageAccounts', suffix='offsite')
    wanted = bool(state.get('backup') or vault or job or offsite or wenv.get('ALICE_BACKUP_ACCOUNT'))
    if not wanted:
        row('backup', 'Backups', 'off', 'not set up: -Step backup')
    else:
        exp = lambda k: _int(state.get(k)) or DEFAULTS[k]
        row('backup', 'Recovery Services vault', 'ok' if vault else 'MISSING', vault or 'alice-backup-vault not found')
        if vault:
            pol = live.j('backup', 'policy', 'show', '-g', rg, '--vault-name', vault, '-n', 'alice-files-daily')
            days = _int(((((pol or {}).get('properties') or {}).get('retentionPolicy') or {}).get('dailySchedule') or {}).get('retentionDuration', {}).get('count'))
            if pol is None: row('backup', 'File share snapshots policy', 'MISSING', 'alice-files-daily not found')
            else: row('backup', 'File share snapshots kept', 'ok' if days == exp('filesBackupDays') else 'DIFFERS', f"{days} days" + ('' if days == exp('filesBackupDays') else f" (the state says {exp('filesBackupDays')})"))
            items = live.j('backup', 'item', 'list', '-g', rg, '--vault-name', vault, '--backup-management-type', 'AzureStorage', '--workload-type', 'AzureFileShare') or []
            share = next((i for i in items if ((i.get('properties') or {}).get('friendlyName') or i.get('name') or '').lower().endswith(state.get('shareName') or 'alice')), None)
            ip = (share or {}).get('properties') or {}
            row('backup', 'File share protected', 'ok' if share else 'MISSING', (f"last backup {ip.get('lastBackupTime') or '?'} ({ip.get('lastBackupStatus') or '?'})" if share else 'the share is not protected by the vault'))
        lock = next((l for l in live.locks() if l.get('name') == 'alice-do-not-delete'), None)
        if state.get('noLock'): row('backup', 'Resource group lock', 'off', 'switched off deliberately (-NoLock)' + (' but a lock is still there' if lock else ''))
        else: row('backup', 'Resource group lock', 'ok' if lock else 'MISSING', (f"alice-do-not-delete ({lock.get('level')})" if lock else 'alice-do-not-delete not found: -Step backup puts it back, or -NoLock if lifted deliberately'))
        pg = state.get('postgresServer') or next((r['name'] for r in res if (r.get('type') or '').lower() == 'microsoft.dbforpostgresql/flexibleservers'), None)
        server = live.j('postgres', 'flexible-server', 'show', '-g', rg, '-n', pg) if pg else None
        if server:
            b = server.get('backup') or (server.get('properties') or {}).get('backup') or {}
            days = _int(b.get('backupRetentionDays'))
            row('backup', 'Database backups kept', 'ok' if days == exp('pgBackupRetentionDays') else 'DIFFERS',
                f"{days} days, geo-redundant {b.get('geoRedundantBackup') or '?'}" + ('' if days == exp('pgBackupRetentionDays') else f" (the state says {exp('pgBackupRetentionDays')})"))
        row('backup', 'Off-site storage account', 'ok' if offsite else 'MISSING', offsite or 'the <prefix><suffix>offsite account was not found')
        if offsite:
            pol = live.j('storage', 'container', 'immutability-policy', 'show', '--account-name', offsite, '-c', 'alice-offsite', '-g', rg) or {}
            pp = pol.get('properties') or pol
            days = _int(pp.get('immutabilityPeriodSinceCreationInDays'))
            row('backup', 'Off-site copies unchangeable for', 'ok' if days == exp('offsiteKeepDays') else ('MISSING' if days is None else 'DIFFERS'),
                (f"{days} days ({(pp.get('state') or '?').lower()})" if days is not None else 'no immutability policy on alice-offsite') + ('' if days in (None, exp('offsiteKeepDays')) else f" (the state says {exp('offsiteKeepDays')})"))
            bs = live.j('storage', 'account', 'blob-service-properties', 'show', '-n', offsite, '-g', rg) or {}
            sd = _int(((bs.get('deleteRetentionPolicy') or {}).get('days')))
            row('backup', 'Off-site soft delete', 'ok' if sd == exp('offsiteSoftDeleteDays') else 'DIFFERS', f'{sd} days' + ('' if sd == exp('offsiteSoftDeleteDays') else f" (the state says {exp('offsiteSoftDeleteDays')})"))
        row('backup', 'Nightly off-site copy job', 'ok' if job else 'MISSING', job or 'alice-backup not found')
        if job:
            runs = live.j('containerapp', 'job', 'execution', 'list', '-n', job, '-g', rg) or []
            last = max(runs, key=lambda r: _ts((r.get('properties') or {}).get('startTime')) or datetime.min.replace(tzinfo=timezone.utc)) if runs else None
            lp = (last or {}).get('properties') or {}
            st = lp.get('status') or ''
            row('backup', 'Last off-site copy', 'ok' if st == 'Succeeded' else ('info' if not last or st == 'Running' else 'DIFFERS'),
                f"{st} at {lp.get('startTime')}" if last else 'no run yet')
        row('backup', 'Backup settings on alice-web', 'ok' if wenv.get('ALICE_BACKUP_ACCOUNT') else 'MISSING', '' if wenv.get('ALICE_BACKUP_ACCOUNT') else 'the Backup page has no settings: run any step that deploys the apps')
        drill_rg = live.group(f'{rg}-drill')
        row('backup', 'Restore drill resource group', 'ok' if drill_rg else 'MISSING', f'{rg}-drill' if drill_rg else f'{rg}-drill not found')
        dj = has('Microsoft.App/jobs', name='alice-drill')
        row('backup', 'Restore drill job', 'ok' if dj else 'MISSING', dj or 'alice-drill not found')

    # ---- users
    roles = {r.get('value') for r in ((app or {}).get('appRoles') or [])}
    have = [v for v in ROLE_VALUES if v in roles]
    sp = live.j('ad', 'sp', 'show', '--id', cid) if cid else None
    on = wenv.get('ALICE_USE_APP_ROLES') == '1'
    if have or state.get('useAppRoles') or on:
        row('users', 'App roles on "Alice web sign-in"', 'ok' if len(have) == 3 else 'MISSING', ', '.join(have) or 'none: run -Step users')
        req = bool((sp or {}).get('appRoleAssignmentRequired'))
        row('users', 'Assignment required', 'ok' if req else 'MISSING', '' if req else 'off: run -Step users')
        if bool(state.get('useAppRoles')) != on:
            row('users', 'App roles decide who gets in', 'DIFFERS', f"the state says {'on' if state.get('useAppRoles') else 'off'}, alice-web has {'on' if on else 'off'}: run -Step apps")
        else:
            row('users', 'App roles decide who gets in', 'ok' if on else 'off', 'on' if on else 'not yet (-Step users -UseAppRoles on, then -Step apps)')
    else:
        row('users', 'People and roles', 'off', 'not set up: -Step users')
    row('recover', 'Recovery', 'info', 'only for a NEW resource group (docs/restore.md part C)' if wanted else 'not used')

    # ---- print
    out(f'What is set up in {rg} (read-only: nothing was changed)')
    step = None
    for s, item, status, detail in rows:
        if s != step: out(f'\n{s}'); step = s
        out(f'  {status:<8} {item:<38} {detail}'.rstrip())
    bad = [r for r in rows if r[2] in ('MISSING', 'DIFFERS')]
    out('')
    if bad:
        out(f'Needs attention ({len(bad)}):')
        for s, item, status, detail in bad: out(f'  {s:<10} {item.strip()}: {status.lower()}' + (f' - {detail}' if detail else ''))
    else:
        out('Nothing missing.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='The setup state of azure-setup.ps1, kept in Azure.')
    ap.add_argument('command', choices=('load', 'save', 'check', 'database-host'))
    ap.add_argument('--resource-group', required=True)
    ap.add_argument('--file', required=True)
    ap.add_argument('--use-local', action='store_true')
    ap.add_argument('--who', default='')
    ap.add_argument('--step', default='')
    a = ap.parse_args(argv)
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    out = lambda s='': print(s, flush=True)
    try:
        if a.command == 'load': return load(AZ, a.resource_group, a.file, a.use_local, a.who, out)
        if a.command == 'save': return save(AZ, a.resource_group, a.file, a.who, a.step, out)
        if a.command == 'database-host': return database_host(AZ, a.resource_group, a.file, out)
        return check(AZ, a.resource_group, a.file, a.who, out)
    except AzureError as e:
        out(f'Stopped: {e}'); return 2


if __name__ == '__main__':
    sys.exit(main())
