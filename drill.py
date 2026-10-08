"""The restore drill (Stefan, 8 Oct 2026), run as the Container Apps job alice-drill (ALICE_ROLE=drill): proves last
night's off-site copy brings Alice back, and how long that takes.

  1. Finds the newest off-site copy (its manifest) and the image of the release that took it.
  2. Builds THROWAWAY resources in the drill resource group (never Alice's own): a private network, a PostgreSQL
     server and database, a storage account with a file share, a Container Apps environment, and a temporary Alice.
  3. The temporary Alice's init container (restore.py) loads the copy into that empty database and share, then Alice
     starts: no API keys (no model calls), no email, no schedules, and sign-in locked to Stefan (Entra; everything but
     /healthz answers 401 to anyone else).
  4. Checks it starts (/healthz) and compares the restored counts of memories, knowledge items, proposals and files with
     the counts recorded from the live database when the copy was taken.
  5. ALWAYS deletes every throwaway resource, success or failure (and anything left from an earlier drill first).
  6. Writes its report to the off-site account's drill-reports container (the Backup page reads it) and emails Stefan.

It never reads or writes Alice's live resources: its identity has Contributor on the drill resource group only, read
access to the off-site copies, write access to drill-reports only, and pull access to the image registry. Every
Resource Manager call is checked to be inside the drill resource group before it is made."""
import json
import os
import re
import secrets
import sys
import time
import uuid
from datetime import datetime, timezone

import azure_io
from azure_io import arm

API = {'Microsoft.Storage/storageAccounts': '2023-01-01', 'Microsoft.Network/virtualNetworks': '2023-09-01',
       'Microsoft.Network/privateDnsZones': '2020-06-01', 'Microsoft.Network/privateDnsZones/virtualNetworkLinks': '2020-06-01',
       'Microsoft.DBforPostgreSQL/flexibleServers': '2022-12-01', 'Microsoft.App/managedEnvironments': '2024-03-01',
       'Microsoft.App/containerApps': '2024-03-01'}
DELETE_ORDER = ['Microsoft.App/containerApps', 'Microsoft.App/managedEnvironments', 'Microsoft.DBforPostgreSQL/flexibleServers',
                'Microsoft.Network/privateDnsZones/virtualNetworkLinks', 'Microsoft.Network/privateDnsZones',
                'Microsoft.Network/virtualNetworks', 'Microsoft.Storage/storageAccounts']
TIMEOUTS = {'provision': 3600, 'start': 2700, 'delete': 1800}
CLEANUP_PASSES = 4
SLEEP = time.sleep           # replaced in tests
CLOCK = time.monotonic


class Refused(RuntimeError):
    pass


def config():
    e = os.environ.get
    def num(name, default):
        try: return float(e(name, '') or default)
        except ValueError: return default
    return {
        'subscription': (e('ALICE_DRILL_SUBSCRIPTION', '') or '').strip(),
        'rg': (e('ALICE_DRILL_RG', '') or '').strip(),
        'live_rg': (e('ALICE_DRILL_LIVE_RG', '') or '').strip(),
        'location': e('ALICE_DRILL_LOCATION', '') or 'uksouth',
        'account': (e('ALICE_BACKUP_ACCOUNT', '') or '').strip().lower(),
        'container': (e('ALICE_BACKUP_CONTAINER', '') or 'alice-offsite').strip(),
        'reports': (e('ALICE_DRILL_REPORTS', '') or 'drill-reports').strip(),
        'live_account': (e('ALICE_FILES_ACCOUNT', '') or '').strip().lower(),
        'identity_id': e('ALICE_DRILL_IDENTITY_ID', '') or '',
        'identity_client_id': e('ALICE_IDENTITY_CLIENT_ID', '') or '',
        'registry': (e('ALICE_ACR_SERVER', '') or '').strip(),
        'image': (e('ALICE_DRILL_IMAGE', '') or '').strip(),
        'auth_client_id': e('ALICE_DRILL_AUTH_CLIENT_ID', '') or '',
        'tenant': e('ALICE_TENANT_ID', '') or '',
        'owner_oid': e('ALICE_OWNER_OBJECT_ID', '') or '',
        'owner_name': e('ALICE_OWNER_NAME', '') or 'Owner',
        'notify': (e('ALICE_BACKUP_NOTIFY', '') or '').strip(),
        'rto_hours': num('ALICE_DRILL_RTO_HOURS', 4),
    }


class Drill:
    def __init__(self, cfg, trigger='manual'):
        if not re.fullmatch(r'[0-9a-fA-F-]{36}', cfg['subscription'] or ''): raise Refused('the subscription is not set (ALICE_DRILL_SUBSCRIPTION)')
        if not re.fullmatch(r'[-\w._()]{1,90}', cfg['rg'] or ''): raise Refused('the drill resource group is not set (ALICE_DRILL_RG)')
        if cfg['live_rg'] and cfg['rg'].lower() == cfg['live_rg'].lower():
            raise Refused('the drill resource group is Alice\'s own resource group: a drill only ever builds in a resource group of its own')
        self.cfg, self.trigger = cfg, trigger
        self.id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')[:-3] + 'Z-' + uuid.uuid4().hex[:6]   # sorts by time
        self.short = uuid.uuid4().hex[:8]
        self.rg_path = f'/subscriptions/{cfg["subscription"]}/resourceGroups/{cfg["rg"]}'
        self.report = {'kind': 'drill', 'id': self.id, 'trigger': trigger, 'started_at': datetime.now(timezone.utc).isoformat(),
                       'result': 'running', 'steps': [], 'rto_hours': cfg['rto_hours'], 'cleanup': {'removed': [], 'left': []}}
        self.t0 = CLOCK()

    # ---- safety: every Resource Manager call stays inside the drill resource group ----
    def _path(self, rel):
        path = self.rg_path + rel
        if not path.lower().startswith(self.rg_path.lower() + '/') or '..' in rel.split('/') or '//' in rel:
            raise Refused('refusing a call outside the drill resource group')
        return path

    def _rid(self, rtype, name):
        return self._path(f'/providers/{rtype}/{name}')

    def step(self, what):
        self.report['steps'].append({'at': round(CLOCK() - self.t0, 1), 'what': what})
        print(f'[{round(CLOCK() - self.t0):>5}s] {what}', flush=True)

    def put(self, rtype, name, body, api=None):
        path = self._rid(rtype, name)
        arm('PUT', path, api or API[rtype], body)
        return path

    def wait_ready(self, path, api, what, timeout=None):
        end = CLOCK() + (timeout or TIMEOUTS['provision'])
        while True:
            state = (arm('GET', path, api, ok=(200,))[2].get('properties') or {}).get('provisioningState', 'Succeeded')
            if state == 'Succeeded': return
            if state in ('Failed', 'Canceled'): raise RuntimeError(f'Azure could not create the {what} ({state})')
            if CLOCK() > end: raise RuntimeError(f'the {what} was not ready after {int((timeout or TIMEOUTS["provision"]) / 60)} minutes')
            SLEEP(15)

    # ---- the copy ----
    def find_copy(self):
        self.backups = azure_io.Blobs(self.cfg['account'], self.cfg['container'], refuse=[self.cfg['live_account']])
        names = [n for n in self.backups.list() if n.endswith('-manifest.json')]
        if not names: raise RuntimeError('there is no off-site copy to restore yet')
        self.manifest_name = max(names)
        self.manifest = json.loads(self.backups.get(self.manifest_name).decode('utf-8'))
        version = str(self.manifest.get('version') or '')
        self.image = (f'{self.cfg["registry"]}/alice:{version}' if self.cfg['registry'] and re.fullmatch(r'[0-9a-f]{7,40}', version)
                      else self.cfg['image'])
        if not self.image: raise RuntimeError('no image to run: the copy names no release and ALICE_DRILL_IMAGE is not set')
        self.report['backup'] = {'manifest': self.manifest_name, 'taken_at': self.manifest.get('taken_at', ''), 'version': version,
                                 'counts': self.manifest.get('counts') or {}, 'files': (self.manifest.get('files') or {}).get('count')}
        self.step(f'Using the copy taken {self.manifest.get("taken_at", "?")} (release {version or "unknown"})')

    # ---- throwaway resources ----
    def build(self):
        loc = self.cfg['location']
        names = self.names = {'storage': f'alicedrill{self.short}', 'vnet': 'alice-drill-vnet', 'dns': 'alice-drill.private.postgres.database.azure.com',
                              'pg': f'alice-drill-pg-{self.short}', 'env': 'alice-drill-env', 'app': 'alice-drill-web'}
        self.step('Creating the throwaway network, storage, database server and environment')
        vnet = self.put('Microsoft.Network/virtualNetworks', names['vnet'], {'location': loc, 'properties': {
            'addressSpace': {'addressPrefixes': ['10.60.0.0/16']},
            'subnets': [{'name': 'apps', 'properties': {'addressPrefix': '10.60.0.0/23', 'delegations': [{'name': 'aca', 'properties': {'serviceName': 'Microsoft.App/environments'}}]}},
                        {'name': 'database', 'properties': {'addressPrefix': '10.60.2.0/24', 'delegations': [{'name': 'pg', 'properties': {'serviceName': 'Microsoft.DBforPostgreSQL/flexibleServers'}}]}}]}})
        st = self.put('Microsoft.Storage/storageAccounts', names['storage'], {'location': loc, 'sku': {'name': 'Standard_LRS'}, 'kind': 'StorageV2',
                      'properties': {'minimumTlsVersion': 'TLS1_2', 'allowBlobPublicAccess': False, 'supportsHttpsTrafficOnly': True}})
        dns = self.put('Microsoft.Network/privateDnsZones', names['dns'], {'location': 'global'})
        self.wait_ready(vnet, API['Microsoft.Network/virtualNetworks'], 'network')
        self.wait_ready(dns, API['Microsoft.Network/privateDnsZones'], 'private DNS zone')
        link = self.put('Microsoft.Network/privateDnsZones', f'{names["dns"]}/virtualNetworkLinks/link',
                        {'location': 'global', 'properties': {'registrationEnabled': False, 'virtualNetwork': {'id': vnet}}},
                        api=API['Microsoft.Network/privateDnsZones/virtualNetworkLinks'])
        self.wait_ready(link, API['Microsoft.Network/privateDnsZones/virtualNetworkLinks'], 'DNS link')
        self.password = secrets.token_urlsafe(24).replace('-', 'a').replace('_', 'b')
        pg = self.put('Microsoft.DBforPostgreSQL/flexibleServers', names['pg'], {'location': loc, 'sku': {'name': 'Standard_B1ms', 'tier': 'Burstable'},
                      'properties': {'version': '16', 'administratorLogin': 'drilladmin', 'administratorLoginPassword': self.password,
                                     'storage': {'storageSizeGB': 32}, 'backup': {'backupRetentionDays': 7, 'geoRedundantBackup': 'Disabled'},
                                     'network': {'delegatedSubnetResourceId': vnet + '/subnets/database', 'privateDnsZoneArmResourceId': dns},
                                     'highAvailability': {'mode': 'Disabled'}}})
        env = self.put('Microsoft.App/managedEnvironments', names['env'], {'location': loc, 'properties': {
            'vnetConfiguration': {'infrastructureSubnetId': vnet + '/subnets/apps', 'internal': False},
            'workloadProfiles': [{'name': 'Consumption', 'workloadProfileType': 'Consumption'}]}})
        self.wait_ready(st, API['Microsoft.Storage/storageAccounts'], 'storage account')
        arm('PUT', st + '/fileServices/default/shares/alice', API['Microsoft.Storage/storageAccounts'], {'properties': {'shareQuota': 100}})
        self.wait_ready(pg, API['Microsoft.DBforPostgreSQL/flexibleServers'], 'database server')
        arm('PUT', pg + '/configurations/azure.extensions', API['Microsoft.DBforPostgreSQL/flexibleServers'], {'properties': {'value': 'CITEXT', 'source': 'user-override'}})
        arm('PUT', pg + '/databases/alice', API['Microsoft.DBforPostgreSQL/flexibleServers'], {'properties': {'charset': 'UTF8', 'collation': 'en_US.utf8'}})
        self.wait_ready(pg + '/databases/alice', API['Microsoft.DBforPostgreSQL/flexibleServers'], 'database')
        fqdn = arm('GET', pg, API['Microsoft.DBforPostgreSQL/flexibleServers'], ok=(200,))[2].get('properties', {}).get('fullyQualifiedDomainName', '')
        self.db_url = f'host={fqdn} port=5432 dbname=alice user=drilladmin password={self.password} sslmode=require'
        self.wait_ready(env, API['Microsoft.App/managedEnvironments'], 'Container Apps environment')
        key = arm('POST', st + '/listKeys', API['Microsoft.Storage/storageAccounts'], ok=(200,))[2]['keys'][0]['value']
        arm('PUT', env + '/storages/alice-files', API['Microsoft.App/managedEnvironments'], {'properties': {'azureFile': {
            'accountName': names['storage'], 'accountKey': key, 'shareName': 'alice', 'accessMode': 'ReadWrite'}}})
        self.step('Throwaway resources ready')
        self.start_alice(env)

    def start_alice(self, env):
        c, names = self.cfg, self.names
        self.step(f'Starting a temporary Alice ({self.image}) that restores the copy first')
        identity = {'type': 'UserAssigned', 'userAssignedIdentities': {c['identity_id']: {}}}
        restore_env = [{'name': 'ALICE_ROLE', 'value': 'restore'}, {'name': 'ALICE_RESTORE_ACCOUNT', 'value': c['account']},
                       {'name': 'ALICE_RESTORE_CONTAINER', 'value': c['container']}, {'name': 'ALICE_RESTORE_MANIFEST', 'value': self.manifest_name},
                       {'name': 'ALICE_RESTORE_TARGET_URL', 'secretRef': 'target-db'}, {'name': 'ALICE_RESTORE_FILES_DIR', 'value': '/mnt/alice'},
                       {'name': 'ALICE_DRILL_ID', 'value': self.id}, {'name': 'ALICE_DRILL_REPORTS', 'value': c['reports']},
                       {'name': 'ALICE_IDENTITY_CLIENT_ID', 'value': c['identity_client_id']}, {'name': 'AISUBSTRATE_DATA_DIR', 'value': '/tmp/alice-restore'},
                       {'name': 'ALICE_FILES_ACCOUNT', 'value': c['live_account']}]
        web_env = [{'name': 'ALICE_ROLE', 'value': 'web'}, {'name': 'ALICE_DATABASE_URL', 'secretRef': 'target-db'},
                   {'name': 'AISUBSTRATE_DATA_DIR', 'value': '/mnt/alice/data'}, {'name': 'ALICE_DOCUMENT_LIBRARY', 'value': '/mnt/alice/Documents'},
                   {'name': 'ALICE_TRUST_EASYAUTH', 'value': '1'}, {'name': 'ALICE_OWNER_OBJECT_ID', 'value': c['owner_oid']},
                   {'name': 'ALICE_OWNER_NAME', 'value': c['owner_name']}, {'name': 'ALICE_NO_SCHEDULER', 'value': '1'}]
        mounts = [{'volumeName': 'alice', 'mountPath': '/mnt/alice'}]
        app = self.put('Microsoft.App/containerApps', names['app'], {'location': c['location'], 'identity': identity, 'properties': {
            'environmentId': env, 'workloadProfileName': 'Consumption',
            'configuration': {'activeRevisionsMode': 'Single',
                              'ingress': {'external': True, 'targetPort': 8000, 'transport': 'auto', 'allowInsecure': False},
                              'registries': [{'server': c['registry'], 'identity': c['identity_id']}] if c['registry'] else [],
                              'secrets': [{'name': 'target-db', 'value': self.db_url}]},
            'template': {'initContainers': [{'name': 'restore', 'image': self.image, 'resources': {'cpu': 1.0, 'memory': '2Gi'}, 'env': restore_env, 'volumeMounts': mounts}],
                         'containers': [{'name': 'web', 'image': self.image, 'resources': {'cpu': 1.0, 'memory': '2Gi'}, 'env': web_env, 'volumeMounts': mounts}],
                         'scale': {'minReplicas': 1, 'maxReplicas': 1},
                         'volumes': [{'name': 'alice', 'storageType': 'AzureFile', 'storageName': 'alice-files',
                                      'mountOptions': 'uid=10001,gid=10001,dir_mode=0770,file_mode=0660'}]}}})
        # Sign-in locked to Stefan: Entra, his object ID only; anyone else gets 401. /healthz stays open for the check.
        arm('PUT', app + '/authConfigs/current', API['Microsoft.App/containerApps'], {'properties': {
            'platform': {'enabled': True},
            'globalValidation': {'unauthenticatedClientAction': 'Return401', 'excludedPaths': ['/healthz']},
            'identityProviders': {'azureActiveDirectory': {'enabled': True,
                'registration': {'clientId': c['auth_client_id'], 'openIdIssuer': f'https://login.microsoftonline.com/{c["tenant"]}/v2.0'},
                'validation': {'allowedAudiences': [c['auth_client_id'], f'api://{c["auth_client_id"]}'],
                               'defaultAuthorizationPolicy': {'allowedPrincipals': {'identities': [c['owner_oid']]}}}}}}})
        self.app_path = app
        self.wait_ready(app, API['Microsoft.App/containerApps'], 'temporary Alice')
        self.fqdn = ((arm('GET', app, API['Microsoft.App/containerApps'], ok=(200,))[2].get('properties') or {}).get('configuration') or {}).get('ingress', {}).get('fqdn', '')
        if not self.fqdn: raise RuntimeError('the temporary Alice has no address')

    # ---- does it start, and does it hold what the copy held? ----
    def restore_report(self):
        try: return json.loads(azure_io.Blobs(self.cfg['account'], self.cfg['reports']).get(f'{self.id}/restore.json').decode('utf-8'))
        except Exception: return None

    def check(self):
        self.step('Waiting for the restore and for Alice to answer')
        end = CLOCK() + TIMEOUTS['start']
        while True:
            rep = self.restore_report()
            if rep and not rep.get('ok'):
                self.report['counts'] = rep.get('counts') or []
                bad = ', '.join(f"{r['what']} {r['restored']} of {r['expected']}" for r in self.report['counts'] if not r.get('ok'))
                raise RuntimeError('the restore failed: ' + (rep.get('error') or 'see its report') + (f' ({bad})' if bad and bad not in (rep.get('error') or '') else ''))
            try:
                status = azure_io.HTTP('GET', f'https://{self.fqdn}/healthz', None, {}, 20)[0]
            except OSError:
                status = 0
            if status == 200 and rep:
                break
            if CLOCK() > end: raise RuntimeError(f'the temporary Alice did not answer within {TIMEOUTS["start"] // 60} minutes'
                                                 + ('' if rep else ' (the restore did not report)'))
            SLEEP(20)
        self.report['recovery_s'] = round(CLOCK() - self.t0, 1)
        self.report['restore'] = {k: rep.get(k) for k in ('took_s', 'database_bytes', 'files_restored')}
        self.report['counts'] = rep.get('counts') or []
        self.step(f'Alice answered after {round(self.report["recovery_s"] / 60, 1)} minutes')
        bad = [r for r in self.report['counts'] if not r.get('ok')]
        if bad or not self.report['counts']:
            raise RuntimeError('the restored counts do not match the live counts recorded with the copy: '
                               + (', '.join(f"{r['what']} {r['restored']} of {r['expected']}" for r in bad) or 'no counts came back'))

    # ---- always: remove every throwaway resource ----
    def resources(self):
        _, _, d = arm('GET', self._path('/resources'), '2021-04-01', ok=(200,))
        return [r for r in d.get('value', []) if r.get('id', '').lower().startswith(self.rg_path.lower() + '/')]

    def cleanup(self, label='Removing the throwaway resources'):
        self.step(label)
        removed, left = [], []
        for attempt in range(CLEANUP_PASSES):       # later passes catch what a dependency held back (a network stays "in use"
            items = self.resources()                # for a few minutes after its Container Apps environment is deleted)
            if not items: break
            if attempt: SLEEP(120)
            items.sort(key=lambda r: DELETE_ORDER.index(r['type']) if r.get('type') in DELETE_ORDER else len(DELETE_ORDER))
            for r in items:
                rid, rtype = r['id'], r.get('type', '')
                api = API.get(rtype) or API.get('/'.join(rtype.split('/')[:2])) or '2021-04-01'
                try:
                    arm('DELETE', self._path(rid[len(self.rg_path):]), api, ok=(200, 202, 204, 404))
                    end = CLOCK() + TIMEOUTS['delete']
                    while arm('GET', self._path(rid[len(self.rg_path):]), api, ok=(200, 404))[0] == 200:
                        if CLOCK() > end: raise RuntimeError('still there after 30 minutes')
                        SLEEP(15)
                    removed.append(r.get('name', rid))
                except Exception as e:
                    print(f'Could not remove {r.get("name")}: {e}', file=sys.stderr)
        try: left = [r.get('name', r['id']) for r in self.resources()]
        except Exception as e: left = [f'unknown ({e})']
        self.report['cleanup']['removed'] += [n for n in removed if n not in self.report['cleanup']['removed']]
        self.report['cleanup']['left'] = left
        return not left

    # ---- the whole drill ----
    def run(self):
        try:
            self.find_copy()
            if self.resources(): self.cleanup('Removing what an earlier drill left behind')
            self.build()
            self.check()
            self.report['result'] = 'passed'
        except Exception as e:
            self.report['result'] = 'failed'
            self.report['error'] = ' '.join((str(e) or type(e).__name__).split())[:500]
            self.step('Failed: ' + self.report['error'])
        finally:
            try: clean = self.cleanup()
            except Exception as e:
                clean = False; self.report['cleanup']['left'] = [f'unknown ({e})']
            if not clean:
                self.report['result'] = 'failed'
                self.report['error'] = (self.report.get('error', '') + ' ' if self.report.get('error') else '') + \
                    'Some throwaway resources could not be removed: ' + ', '.join(self.report['cleanup']['left']) + \
                    f' (delete them in the {self.cfg["rg"]} resource group).'
            self.report['total_s'] = round(CLOCK() - self.t0, 1)
            self.report['finished_at'] = datetime.now(timezone.utc).isoformat()
            self.report['within_rto'] = bool(self.report.get('recovery_s') is not None and self.report['recovery_s'] <= self.cfg['rto_hours'] * 3600)
            self.save()
            self.email()
        return 0 if self.report['result'] == 'passed' else 1

    def save(self):
        try:
            azure_io.Blobs(self.cfg['account'], self.cfg['reports']).put(f'{self.id}/report.json', json.dumps(self.report).encode('utf-8'), 'application/json')
        except Exception as e:
            print(f'Could not save the drill report: {e}', file=sys.stderr)
        print(json.dumps(self.report))

    def email(self):
        r = self.report
        mins = lambda s: f'{round(s / 60)} minutes' if s is not None else 'not reached'
        lines = [f'Restore drill {r["id"]}: {"PASSED" if r["result"] == "passed" else "FAILED"}.', '']
        if r.get('backup'): lines.append(f'Copy restored: taken {r["backup"]["taken_at"]} (release {r["backup"]["version"] or "unknown"}).')
        lines.append(f'Alice back in: {mins(r.get("recovery_s"))} (target: within {r["rto_hours"]:g} hours).')
        for c in r.get('counts') or []:
            lines.append(f'  {c["what"]}: {c["restored"]} restored, {c["expected"]} in the copy' + ('' if c['ok'] else '  <- does not match'))
        if r.get('error'): lines += ['', 'What went wrong: ' + r['error']]
        lines += ['', 'Throwaway resources removed: ' + ('all' if not r['cleanup']['left'] else 'NOT ALL: ' + ', '.join(r['cleanup']['left'])),
                  'Live data was not touched.', '', 'Details: ' + (os.environ.get('ALICE_PUBLIC_URL', '').rstrip('/') + '/admin/backup'),
                  '', 'This email was sent by Alice. Do not reply.']
        try:
            import notify
            ok, why = notify.send(self.cfg['notify'], f'Alice restore drill {"passed" if r["result"] == "passed" else "FAILED"}', '\n'.join(lines))
            if not ok: print(f'Not emailed: {why}', file=sys.stderr)
        except Exception as e:
            print(f'Could not email the result: {e}', file=sys.stderr)


def run(trigger=None):
    trigger = trigger or os.environ.get('ALICE_DRILL_TRIGGER', '') or 'manual'
    try: d = Drill(config(), trigger)
    except Refused as e:
        print('Restore drill refused: ' + str(e), file=sys.stderr)
        return 2
    return d.run()


if __name__ == '__main__':
    sys.exit(run())
