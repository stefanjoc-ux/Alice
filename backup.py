"""Backups (Stefan, 8 Oct 2026): the nightly off-site copy and the Backup page.

Three kinds of backup keep Alice safe in Azure (all set up by azure-setup.ps1 -Step backup, infra/backup.bicep):
  files     Azure Backup snapshots of the file share (Recovery Services vault, daily, kept 30 days): restore one file or folder.
  database  PostgreSQL's own backups (kept 35 days): restore the database to any point in time.
  offsite   this module, run as the Container Apps job alice-backup (ALICE_ROLE=backup) at 02:00 UK time: a pg_dump of the
            live database and a copy of the whole file share, compressed, written to a SEPARATE storage account in UK West
            whose container keeps every copy unchangeable for 35 days (time-based immutability) with soft delete behind it.

The job only READS live data: the database through pg_dump, the share through a read-only mount (/mnt/alice-ro). It writes
backup data to the off-site account and nowhere else (never the live share's account), with the managed identity (no keys).
Each run is recorded (backup_runs) and logged with its size, duration and result; a failure shows on Home and is emailed
to Stefan (notify.py). The Backup page (Admin, owner only) reads the vault and the database server's backup state from
Azure with the same identity (Reader on those two resources only).
"""
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import azure_io
import substrate_store as store
from azure_io import arm_get as _arm

COUNTED = [('memories', 'records'), ('knowledge items', 'knowledge_meta'), ('proposals', 'proposals'), ('files', 'files')]
STALE_HOURS = 26                 # no good off-site copy for this long = a warning on Home
_cache = {'at': 0.0, 'value': None}
_lock = threading.Lock()


def _ensure():
    with store.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS backup_runs (id TEXT PRIMARY KEY, kind TEXT NOT NULL, trigger TEXT NOT NULL DEFAULT '', "
                  "status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, duration_s REAL, size_bytes REAL NOT NULL DEFAULT 0, "
                  "detail TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '')")


try: _ensure()
except Exception as _e:        # the database unreachable: the job still reports the failure by email (run() records what it can)
    print(f'Could not prepare the backup_runs table: {type(_e).__name__}', file=sys.stderr)


# ---------------- UK time (Container Apps schedules are UTC; the job runs at 01:00 and 02:00 UTC and keeps the one at 02:00 UK) ----------------
def _last_sunday(year, month):
    d = date(year, month, 31)
    while d.weekday() != 6: d -= timedelta(days=1)
    return d


def uk_offset(utc):
    """Hours the UK is ahead of UTC at this moment: 1 in British Summer Time (last Sunday of March 01:00 UTC to last Sunday
    of October 01:00 UTC), else 0. Worked out here so it never depends on the image's time zone files."""
    y = utc.year
    start = datetime.combine(_last_sunday(y, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(y, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return 1 if start <= utc < end else 0


def uk_time(utc):
    return utc + timedelta(hours=uk_offset(utc))


def due(now):
    """Should a scheduled start at `now` (UTC) take the backup? The job is started at 01:00 and 02:00 UTC; only the one
    at 02:00 UK time goes ahead. A start at any other time (started by hand) always goes ahead."""
    if now.hour in (1, 2) and now.minute < 30:
        return uk_time(now).hour == 2
    return True


def next_at(now, hour=2, minute=0):
    """The next hour:minute UK time after `now` (UTC), as UTC."""
    local_day = uk_time(now).date()
    for d in range(0, 3):
        day = local_day + timedelta(days=d)
        local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
        for off in (1, 0):
            u = local - timedelta(hours=off)
            if uk_time(u).replace(tzinfo=timezone.utc) == local and u > now: return u
    return now + timedelta(days=1)


# ---------------- settings (from infra/backup.bicep through the environment) ----------------
def config():
    e = os.environ.get
    def num(name, default):
        try: return int(e(name, '') or default)
        except ValueError: return default
    return {
        'account': (e('ALICE_BACKUP_ACCOUNT', '') or '').strip().lower(),
        'container': (e('ALICE_BACKUP_CONTAINER', '') or 'alice-offsite').strip(),
        'region': e('ALICE_BACKUP_REGION', '') or 'UK West',
        'keep_days': num('ALICE_BACKUP_KEEP_DAYS', 35),
        'soft_delete_days': num('ALICE_BACKUP_SOFT_DELETE_DAYS', 35),
        'immutability_locked': e('ALICE_BACKUP_IMMUTABILITY_LOCKED', '') == '1',
        'source': e('ALICE_BACKUP_SOURCE', '') or '/mnt/alice-ro',
        'notify': (e('ALICE_BACKUP_NOTIFY', '') or '').strip(),
        'live_account': (e('ALICE_FILES_ACCOUNT', '') or '').strip().lower(),
        'vault_id': e('ALICE_BACKUP_VAULT_ID', '') or '',
        'files_days': num('ALICE_BACKUP_FILES_DAYS', 30),
        'files_time': e('ALICE_BACKUP_FILES_TIME', '') or '01:00',
        'pg_id': e('ALICE_PG_SERVER_ID', '') or '',
        'pg_days': num('ALICE_PG_BACKUP_DAYS', 35),
        'pg_geo': e('ALICE_PG_GEO_BACKUP', '') == '1',
        'lock': e('ALICE_BACKUP_LOCK', '') or '',
    }


def configured():
    return bool(config()['account'])


def owner_ok(headers):
    """Owner only. On the PC Alice listens on this computer only, so whoever is here is the owner. In Azure the sign-in's
    object ID must be the owner's (ALICE_OWNER_OBJECT_ID, from Bicep); if that is not set, nobody sees backups."""
    if os.environ.get('ALICE_TRUST_EASYAUTH') != '1': return True
    owner = (os.environ.get('ALICE_OWNER_OBJECT_ID') or '').strip().lower()
    oid = (headers.get('x-ms-client-principal-id') or '').strip().lower()
    return bool(owner) and oid == owner


# ---------------- the database: pg_dump, streamed ----------------
def pg_args(url):
    """pg_dump's arguments and environment for ALICE_DATABASE_URL (a libpq keyword string or a postgresql:// address).
    The password goes in PGPASSWORD, never on the command line."""
    conninfo, password = azure_io.pg_conninfo(url)
    env = dict(os.environ); env['PGPASSWORD'] = password; env.pop('ALICE_DATABASE_URL', None)
    return ['pg_dump', '--format=custom', '--compress=6', '--no-owner', '--no-privileges', '--dbname', conninfo], env, password


def database_url():
    return os.environ.get('ALICE_DATABASE_URL', '')


def dump_chunks(url):
    """pg_dump's output, chunk by chunk (custom format, already compressed). Raises with pg_dump's own message on failure."""
    args, env, password = pg_args(url)
    with tempfile.TemporaryFile() as err:
        try: p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=err, env=env)
        except FileNotFoundError: raise RuntimeError('pg_dump is not installed in this image') from None
        while True:
            chunk = p.stdout.read(1024 * 1024)
            if not chunk: break
            yield chunk
        code = p.wait()
        if code:
            err.seek(0)
            msg = err.read().decode('utf-8', 'replace')
            if password: msg = msg.replace(password, '***')
            raise RuntimeError('pg_dump failed: ' + ' '.join(msg.split())[-300:])


# ---------------- the file share: a tar.gz streamed from the read-only mount ----------------
class _Exact(io.RawIOBase):
    """Reads exactly `size` bytes from a file (padding with zeros if it shrank while being copied), so the archive stays whole."""

    def __init__(self, f, size):
        super().__init__(); self.f, self.left, self.short = f, size, False

    def readable(self): return True

    def read(self, n=-1):
        if self.left <= 0: return b''
        n = self.left if n is None or n < 0 else min(n, self.left)
        b = self.f.read(n)
        if not b: b = b'\0' * n; self.short = True
        self.left -= len(b)
        return b


def copy_files(source, writer):
    """Every file and folder under `source` into `writer` as a tar.gz. Returns counts (files, bytes, changed, skipped)."""
    if not os.path.isdir(source): raise RuntimeError(f'the file share is not mounted at {source}')
    out = {'files': 0, 'bytes': 0, 'changed': [], 'skipped': []}
    try: tar = tarfile.open(fileobj=writer, mode='w|gz', compresslevel=6)
    except TypeError: tar = tarfile.open(fileobj=writer, mode='w|gz')      # older Python: default compression
    with tar:
        for root, dirs, files in os.walk(source):
            dirs.sort(); files.sort()
            rel_root = os.path.relpath(root, source)
            for d in dirs:
                p = os.path.join(root, d)
                try: tar.add(p, arcname=os.path.normpath(os.path.join('alice', rel_root, d)), recursive=False)
                except OSError: out['skipped'].append(os.path.join(rel_root, d))
            for name in files:
                p = os.path.join(root, name); arc = os.path.normpath(os.path.join('alice', rel_root, name))
                try:
                    with open(p, 'rb') as f:
                        st = os.fstat(f.fileno())
                        info = tar.gettarinfo(arcname=arc, fileobj=f)
                        info.uname = info.gname = ''
                        rd = _Exact(f, st.st_size)
                        tar.addfile(info, rd)
                        if rd.short: out['changed'].append(arc[6:])
                    out['files'] += 1; out['bytes'] += st.st_size
                except OSError:
                    out['skipped'].append(os.path.join(rel_root, name))
    out['changed'] = out['changed'][:50]; out['skipped'] = out['skipped'][:50]
    return out


def counts():
    """How many memories, knowledge items, proposals and files the database holds (kept in each copy's manifest, so a
    restore can be checked against it)."""
    out = {}
    with store.db() as c:
        for label, table in COUNTED:
            try: out[label] = c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            except Exception: out[label] = None
    return out


# ---------------- one run ----------------
def _size(n):
    n = float(n or 0)
    for unit in ('bytes', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB': return (f'{n:.0f} {unit}' if unit == 'bytes' else f'{n:.1f} {unit}')
        n /= 1024


def _duration(s):
    s = int(round(s or 0))
    return f'{s // 60} min {s % 60} s' if s >= 60 else f'{s} s'


def _record(run_id, **fields):
    try:
        cols = ', '.join(f'{k}=?' for k in fields)
        with store.db() as c: c.execute(f'UPDATE backup_runs SET {cols} WHERE id=?', (*fields.values(), run_id))
    except Exception as e:
        print(f'Could not record the backup run: {type(e).__name__}', file=sys.stderr)


def _audit(action, target, detail):
    try:
        with store.db() as c: store.audit(c, action, target, 'backup', detail[:500])
    except Exception as e:
        print(f'Could not write the activity log: {type(e).__name__}', file=sys.stderr)


def _scrub(text):
    text = re.sub(r'(?i)(password|pwd|sig|token|key)=[^\s&;]+', r'\1=***', text or '')
    return re.sub(r'(?i)bearer\s+[A-Za-z0-9._\-]+', 'Bearer ***', text)[:400]


def _email_failure(cfg, when, error, kind='off-site backup'):
    """Tell Stefan by email (notify.py) and log whether it went."""
    import notify
    link = (os.environ.get('ALICE_PUBLIC_URL', '').rstrip('/') or '') + '/admin/backup'
    detail = error
    try:
        import rules_engine
        rules_engine.check_outbound(error, 'backup email', packs=False)
    except Exception:
        detail = 'The error text is not included (it failed Alice\'s security checks): open the Backup page to read it.'
    text = (f'Alice\'s nightly {kind} failed at {when}.\n\nWhat went wrong: {detail}\n\n'
            f'The live database and files are not affected; the earlier copies are still there. See the Backup page: {link}\n\n'
            'This email was sent by Alice. Do not reply.')
    ok, why = notify.send(cfg['notify'], f'Alice: the nightly {kind} failed', text)
    _audit('backup_failure_emailed' if ok else 'backup_failure_not_emailed', 'offsite',
           f'Emailed {cfg["notify"]}' if ok else f'Not emailed ({why}); the failure shows on Home and the Backup page')
    return ok


def run(trigger='schedule', now=None, force=False):
    """Take the off-site copy. Returns 0 when it is complete, 1 when it failed (the job then shows Failed in Azure)."""
    now = now or datetime.now(timezone.utc)
    if trigger == 'schedule' and not force and not due(now):
        print(f'Not 02:00 UK time ({uk_time(now):%H:%M} UK): the other scheduled start takes tonight\'s backup.')
        return 0
    cfg = config()
    run_id = uuid.uuid4().hex
    try:
        with store.db() as c:
            c.execute('INSERT INTO backup_runs(id,kind,trigger,status,started_at) VALUES (?,?,?,?,?)', (run_id, 'offsite', trigger, 'running', now.isoformat()))
    except Exception as e:
        print(f'Could not record the start: {type(e).__name__}', file=sys.stderr)
    t0 = time.monotonic()
    stamp = now.strftime('%Y%m%dT%H%MZ'); prefix = now.strftime('%Y/%m/%d/') + stamp
    detail = {'account': cfg['account'], 'container': cfg['container'], 'region': cfg['region'], 'keep_days': cfg['keep_days']}
    try:
        if not cfg['account']: raise RuntimeError('the off-site storage account is not set (ALICE_BACKUP_ACCOUNT): run azure-setup.ps1 -Step backup')
        blob = azure_io.Blobs(cfg['account'], cfg['container'], refuse=[cfg['live_account']])
        url = database_url()
        if not url: raise RuntimeError('ALICE_DATABASE_URL is not set: the off-site copy runs in Azure only')
        w = blob.writer(prefix + '-database.dump')
        for chunk in dump_chunks(url): w.write(chunk)
        w.close()
        detail['database'] = {'blob': w.name, 'bytes': w.size, 'sha256': w.sha256}
        w = blob.writer(prefix + '-files.tar.gz', 'application/gzip')
        f = copy_files(cfg['source'], w)
        w.close()
        detail['files'] = {'blob': w.name, 'bytes': w.size, 'sha256': w.sha256, 'count': f['files'], 'original_bytes': f['bytes'],
                           'changed_while_copying': f['changed'], 'skipped': f['skipped']}
        detail['counts'] = counts()
        took = time.monotonic() - t0
        manifest = {'alice_backup': 1, 'taken_at': now.isoformat(), 'took_s': round(took, 1), 'version': os.environ.get('ALICE_VERSION', 'local'),
                    'database': detail['database'], 'files': detail['files'], 'counts': detail['counts']}
        blob.put(prefix + '-manifest.json', json.dumps(manifest, indent=1).encode('utf-8'), 'application/json')
        detail['manifest'] = prefix + '-manifest.json'
        total = detail['database']['bytes'] + detail['files']['bytes']
        _record(run_id, status='ok', finished_at=store.now(), duration_s=round(took, 1), size_bytes=total, detail=json.dumps(detail))
        note = (f'Off-site copy to {cfg["account"]}/{cfg["container"]} ({cfg["region"]}): database {_size(detail["database"]["bytes"])}, '
                f'files {_size(detail["files"]["bytes"])} ({f["files"]:,} files), {_duration(took)}'
                + (f'; {len(f["skipped"])} could not be read' if f['skipped'] else ''))
        _audit('backup_completed', 'offsite', note)
        print(note)
        return 0
    except Exception as e:
        took = time.monotonic() - t0
        err = _scrub(str(e) or type(e).__name__)
        _record(run_id, status='failed', finished_at=store.now(), duration_s=round(took, 1), error=err, detail=json.dumps(detail))
        _audit('backup_failed', 'offsite', f'Off-site copy failed after {_duration(took)}: {err}')
        print('Off-site backup FAILED: ' + err, file=sys.stderr)
        try: _email_failure(cfg, f'{uk_time(now):%d %b %Y %H:%M} UK time', err)
        except Exception as x: print(f'Could not send the failure email: {type(x).__name__}', file=sys.stderr)
        return 1


# ---------------- what the Backup page and Home show ----------------
def _row(r):
    if not r: return None
    d = dict(r)
    try: d['detail'] = json.loads(d.get('detail') or '{}')
    except ValueError: d['detail'] = {}
    return d


def runs(kind='offsite', limit=10):
    with store.db() as c:
        return [_row(r) for r in c.execute('SELECT * FROM backup_runs WHERE kind=? ORDER BY started_at DESC LIMIT ?', (kind, limit))]


def last_ok(kind='offsite'):
    with store.db() as c:
        return _row(c.execute("SELECT * FROM backup_runs WHERE kind=? AND status='ok' ORDER BY started_at DESC LIMIT 1", (kind,)).fetchone())


def home_status(now=None):
    """For Home: None when all is well (or backups are not set up), else what is wrong and a link."""
    try:
        now = now or datetime.now(timezone.utc)
        recent = [r for r in runs('offsite', 5) if r['status'] != 'running']
        if not recent and not configured(): return None
        if recent and recent[0]['status'] == 'failed':
            when = recent[0]['started_at']
            return {'level': 'bad', 'when': when, 'link': '/admin/backup',
                    'text': 'The nightly off-site backup failed: ' + (recent[0]['error'] or 'see the Backup page') + '. Earlier copies are still kept.'}
        ok = last_ok()
        if configured() and (not ok or datetime.fromisoformat(ok['started_at']) < now - timedelta(hours=STALE_HOURS)):
            return {'level': 'warn', 'when': ok['started_at'] if ok else '', 'link': '/admin/backup',
                    'text': f'No off-site backup in the last {STALE_HOURS} hours' + ('' if ok else ' (none yet)') + '. Check the alice-backup job in Azure.'}
    except Exception:
        return None
    return None


def _files_state(cfg):
    out = {'where': '', 'keep_days': cfg['files_days'], 'schedule': f'Every day at {cfg["files_time"]} UK time', 'last': None, 'error': ''}
    if not cfg['vault_id']: out['error'] = 'Not set up yet: run azure-setup.ps1 -Step backup.'; return out
    out['where'] = 'Recovery Services vault ' + cfg['vault_id'].rstrip('/').split('/')[-1] + ' (snapshots stay in the share\'s own storage account, UK South)'
    try:
        h, m = (int(x) for x in cfg['files_time'].split(':'))
        out['next_run'] = next_at(datetime.now(timezone.utc), h, m).isoformat()
    except ValueError:
        pass
    try:
        items = _arm(cfg['vault_id'] + "/backupProtectedItems?$filter=backupManagementType eq 'AzureStorage'", '2023-04-01').get('value', [])
        if not items: out['error'] = 'The vault protects no file share yet.'; return out
        it = items[0]; p = it.get('properties', {})
        out['share'] = p.get('friendlyName', ''); out['state'] = p.get('protectionState', ''); out['health'] = p.get('healthStatus', '')
        out['last'] = {'time': p.get('lastBackupTime', ''), 'status': p.get('lastBackupStatus', '')}
        try:
            pts = _arm(it['id'] + '/recoveryPoints', '2023-04-01').get('value', [])
            pts.sort(key=lambda x: x.get('properties', {}).get('recoveryPointTime', ''), reverse=True)
            out['points'] = len(pts)
            if pts:
                pp = pts[0].get('properties', {})
                out['last']['time'] = pp.get('recoveryPointTime') or out['last']['time']
                if pp.get('recoveryPointSizeInGB') is not None: out['last']['size_gb'] = pp.get('recoveryPointSizeInGB')
                out['oldest'] = pts[-1].get('properties', {}).get('recoveryPointTime', '')
        except Exception as e:
            out['error'] = 'Could not list the restore points: ' + _scrub(str(e))
    except Exception as e:
        out['error'] = 'Could not read the vault: ' + _scrub(str(e))
    return out


def _database_state(cfg):
    out = {'keep_days': cfg['pg_days'], 'geo': cfg['pg_geo'], 'where': '', 'error': '',
           'schedule': 'Continuous: a full backup daily plus the transaction log every few minutes'}
    if not cfg['pg_id']: out['error'] = 'Not set up yet: run azure-setup.ps1 -Step backup.'; return out
    out['where'] = 'PostgreSQL server ' + cfg['pg_id'].rstrip('/').split('/')[-1] + (' (UK South, a copy in UK West)' if cfg['pg_geo'] else ' (UK South)')
    try:
        s = _arm(cfg['pg_id'], '2022-12-01').get('properties', {}).get('backup', {})
        out['keep_days'] = s.get('backupRetentionDays', cfg['pg_days']); out['geo'] = s.get('geoRedundantBackup') == 'Enabled'
        out['earliest_restore'] = s.get('earliestRestoreDate', '')
        try:
            b = _arm(cfg['pg_id'] + '/backups', '2022-12-01').get('value', [])
            b.sort(key=lambda x: x.get('properties', {}).get('completedTime', ''), reverse=True)
            if b: out['last'] = {'time': b[0].get('properties', {}).get('completedTime', ''), 'status': 'Completed',
                                 'type': b[0].get('properties', {}).get('backupType', '')}
            out['points'] = len(b)
        except Exception as e:
            out['error'] = 'Could not list the database backups: ' + _scrub(str(e))
    except Exception as e:
        out['error'] = 'Could not read the database server: ' + _scrub(str(e))
    return out


# ---------------- the restore drill (drill.py) and the targets ----------------
RPO_FILES_HOURS = 24          # recovery point for files: at most a day's changes lost (daily snapshot and nightly copy)
RTO_HOURS = 4                 # recovery time: Alice back within 4 hours
RUNBOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'restore.md')


def drill_config():
    e = os.environ.get
    return {'job': (e('ALICE_DRILL_JOB_ID', '') or '').strip(), 'reports': (e('ALICE_DRILL_REPORTS', '') or 'drill-reports').strip(),
            'rg': e('ALICE_DRILL_RG', '') or ''}


def _drill_summary(r):
    mins = round((r.get('recovery_s') or 0) / 60)
    return (f"Restore drill {'passed' if r.get('result') == 'passed' else 'failed'}"
            + (f': Alice back in {mins} min' if r.get('recovery_s') is not None else '')
            + (f"; {r['error']}" if r.get('error') else '')
            + ('; throwaway resources removed' if not (r.get('cleanup') or {}).get('left') else '; some throwaway resources were NOT removed'))[:500]


def _ingest(r):
    """Record a finished drill once (backup_runs, kind drill) and log it."""
    if not r.get('id') or r.get('result') not in ('passed', 'failed'): return
    with store.db() as c:
        if c.execute('SELECT 1 FROM backup_runs WHERE id=?', ('drill-' + r['id'],)).fetchone(): return
        c.execute('INSERT INTO backup_runs(id,kind,trigger,status,started_at,finished_at,duration_s,size_bytes,detail,error) VALUES (?,?,?,?,?,?,?,?,?,?)',
                  ('drill-' + r['id'], 'drill', r.get('trigger', ''), 'ok' if r['result'] == 'passed' else 'failed', r.get('started_at', store.now()),
                   r.get('finished_at'), r.get('total_s'), 0, json.dumps(r)[:200000], (r.get('error') or '')[:500]))
        store.audit(c, 'restore_drill_passed' if r['result'] == 'passed' else 'restore_drill_failed', 'drill', 'backup', _drill_summary(r))


def drills(limit=6):
    """The latest drill reports from the off-site account (newest first), each recorded once in Alice."""
    cfg, dc = config(), drill_config()
    if not cfg['account']: return []
    box = azure_io.Blobs(cfg['account'], dc['reports'])
    names = sorted((n for n in box.list() if n.endswith('/report.json')), reverse=True)[:limit]
    out = []
    for n in names:
        try: r = json.loads(box.get(n).decode('utf-8'))
        except Exception: continue
        out.append(r)
        try: _ingest(r)
        except Exception as e: print(f'Could not record drill {r.get("id")}: {type(e).__name__}', file=sys.stderr)
    return out


def drill_running():
    """A drill in progress (from the job's executions), or None."""
    job = drill_config()['job']
    if not job: return None
    for x in _arm(job + '/executions', '2024-03-01').get('value', []):
        p = x.get('properties') or {}
        if p.get('status') in ('Running', 'Processing'): return {'since': p.get('startTime', ''), 'execution': x.get('name', '')}
    return None


def start_drill():
    """Start the alice-drill job (the same job the Restore drill workflow starts). Refused while one is running."""
    job = drill_config()['job']
    if not job: raise ValueError('The restore drill is not set up yet: run azure-setup.ps1 -Step backup.')
    if drill_running(): raise ValueError('A restore drill is already running. It takes about 30 to 60 minutes.')
    _, _, d = azure_io.arm('POST', job + '/start', '2024-03-01', {})
    with store.db() as c:
        store.audit(c, 'restore_drill_started', 'drill', 'backup', 'Restore drill started from the Backup page (throwaway resources only; live data is not touched)')
    with _lock: _cache.update(at=0.0, value=None)
    return {'started': True, 'execution': d.get('name', '')}


def targets(o, now=None):
    """Recovery point and recovery time targets against what the backups and the last drill show."""
    now = now or datetime.now(timezone.utc)
    def age_h(iso):
        try: return (now - datetime.fromisoformat(str(iso).replace('Z', '+00:00'))).total_seconds() / 3600
        except Exception: return None
    newest = [x for x in (age_h((o['files'].get('last') or {}).get('time')), age_h((o['offsite'].get('last_ok') or {}).get('started_at'))) if x is not None]
    files_age = min(newest) if newest else None
    last_drill = next((d for d in o['drill']['recent'] if d.get('result') in ('passed', 'failed')), None)
    rec = last_drill.get('recovery_s') if last_drill else None
    return {
        'rpo_database': {'target': 'Minutes (point-in-time restore to any moment in the last ' + str(o['database'].get('keep_days') or 35) + ' days)',
                         'met': bool(o['database'].get('earliest_restore')), 'actual': 'Continuous' if o['database'].get('earliest_restore') else 'Not known yet'},
        'rpo_files': {'target': f'{RPO_FILES_HOURS} hours (daily snapshot and the nightly off-site copy)', 'hours': round(files_age, 1) if files_age is not None else None,
                      'met': files_age is not None and files_age <= RPO_FILES_HOURS + 2},
        'rto': {'target': f'Alice back within {RTO_HOURS} hours', 'hours': round(rec / 3600, 2) if rec is not None else None,
                'met': rec is not None and rec <= RTO_HOURS * 3600, 'drill_at': last_drill.get('started_at') if last_drill else ''},
    }


def runbook():
    try:
        with open(RUNBOOK, encoding='utf-8') as f: return f.read()
    except OSError:
        return ''


def overview(fresh=False):
    """The Backup page: each kind's last backup (time, size, status), how long it is kept, where, and the next run."""
    now = time.time()
    with _lock:
        if not fresh and _cache['value'] and now - _cache['at'] < 60: return _cache['value']
    cfg = config()
    rs = runs('offsite', 10); ok = last_ok()
    offsite = {
        'configured': bool(cfg['account']),
        'where': (f'Storage account {cfg["account"]}, container {cfg["container"]}, {cfg["region"]} (a separate account in another UK region)'
                  if cfg['account'] else ''),
        'keep_days': cfg['keep_days'], 'soft_delete_days': cfg['soft_delete_days'], 'immutability_locked': cfg['immutability_locked'],
        'protection': (f'Each copy cannot be changed or deleted for {cfg["keep_days"]} days (immutability'
                       + (', locked' if cfg['immutability_locked'] else '') + f'), then it is removed; deleted copies stay recoverable for '
                       f'{cfg["soft_delete_days"]} more days. Encrypted at rest (two layers, Microsoft-managed keys). Reached only with Alice\'s managed identity.'),
        'schedule': 'Every night at 02:00 UK time', 'next_run': next_at(datetime.now(timezone.utc)).isoformat() if cfg['account'] else '',
        'last': rs[0] if rs else None, 'last_ok': ok, 'recent': rs,
    }
    dc = drill_config()
    drill = {'configured': bool(dc['job']), 'rg': dc['rg'], 'recent': [], 'running': None, 'error': ''}
    if cfg['account']:
        try: drill['recent'] = drills()
        except Exception as e: drill['error'] = 'Could not read the drill reports: ' + _scrub(str(e))
    if dc['job']:
        try: drill['running'] = drill_running()
        except Exception as e: drill['error'] = (drill['error'] + ' ' if drill['error'] else '') + 'Could not see whether a drill is running: ' + _scrub(str(e))
    value = {'configured': configured(), 'offsite': offsite, 'files': _files_state(cfg), 'database': _database_state(cfg),
             'lock': {'on': bool(cfg['lock']), 'name': cfg['lock']}, 'home': home_status(), 'drill': drill}
    value['targets'] = targets(value)
    with _lock: _cache.update(at=now, value=value)
    return value


if __name__ == '__main__':
    # deploy/start.sh, role backup:  python backup.py run   (ALICE_BACKUP_FORCE=1 takes it whatever the time)
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        sys.exit(run(force=os.environ.get('ALICE_BACKUP_FORCE') == '1'))
    print('Usage: python backup.py run'); sys.exit(2)
