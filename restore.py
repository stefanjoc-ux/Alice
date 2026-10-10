"""Restore Alice from a nightly off-site copy (8 Oct 2026), run as ALICE_ROLE=restore.

It only ever restores into NEW, EMPTY resources: it refuses a target database that already holds tables and a target
folder that already holds files, so it can never overwrite live data. It reads the copy (database dump, file share
archive, manifest) from the off-site account with the managed identity, checks each against the manifest's sha256,
loads the database with pg_restore and psql in one transaction, unpacks the files, then counts memories, knowledge
items, proposals and files and compares them with the counts the manifest recorded from the live database when the copy
was taken.

Used by:
  - the restore drill (drill.py): the init container of the temporary Alice, writing its report to the off-site
    account's drill-reports container (ALICE_DRILL_ID);
  - a full recovery into a new resource group (azure-setup.ps1 -Step recover; docs/restore.md, part C).
It imports nothing that touches a database, so the target stays empty until the dump is loaded."""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone

import azure_io

COUNTED = [('memories', 'records'), ('knowledge items', 'knowledge_meta'), ('proposals', 'proposals'), ('files', 'files')]
MARKER = '.alice-restored-'           # written into the files folder when a drill's restore is complete (a restart skips it)
HEADER_LINES = 200                    # only the dump's opening SET lines are filtered
SKIP_SET = re.compile(rb'^SET transaction_timeout\b')   # PostgreSQL 17's pg_restore writes it; a 16 server refuses it


def config():
    e = os.environ.get
    return {
        'account': (e('ALICE_RESTORE_ACCOUNT', '') or e('ALICE_BACKUP_ACCOUNT', '') or '').strip().lower(),
        'container': (e('ALICE_RESTORE_CONTAINER', '') or 'alice-offsite').strip(),
        'manifest': (e('ALICE_RESTORE_MANIFEST', '') or '').strip(),
        'target': e('ALICE_RESTORE_TARGET_URL', '') or '',
        'files_dir': e('ALICE_RESTORE_FILES_DIR', '') or '/mnt/alice',
        'drill_id': (e('ALICE_DRILL_ID', '') or '').strip(),
        'reports': (e('ALICE_DRILL_REPORTS', '') or 'drill-reports').strip(),
        'live_account': (e('ALICE_FILES_ACCOUNT', '') or '').strip().lower(),
    }


def latest_manifest(blobs, prefix=''):
    names = [n for n in blobs.list(prefix) if n.endswith('-manifest.json')]
    if not names: raise RuntimeError(f'no off-site copy found in {blobs.account}/{blobs.container}')
    return max(names)


# ---------------- the target must be new and empty ----------------
def _psql_args(url):
    conninfo, password = azure_io.pg_conninfo(url)
    env = dict(os.environ); env['PGPASSWORD'] = password
    for k in ('ALICE_DATABASE_URL', 'ALICE_RESTORE_TARGET_URL'): env.pop(k, None)
    return conninfo, password, env


def _query(url, sql):
    """Run one query with psql and return its rows (tab separated)."""
    conninfo, password, env = _psql_args(url)
    p = subprocess.run(['psql', '--no-psqlrc', '-X', '-A', '-t', '-F', '\t', '-v', 'ON_ERROR_STOP=1', '-c', sql, '--dbname', conninfo],
                       env=env, capture_output=True, timeout=120)
    if p.returncode:
        msg = p.stderr.decode('utf-8', 'replace')
        if password: msg = msg.replace(password, '***')
        raise RuntimeError('psql: ' + ' '.join(msg.split())[-300:])
    return [line.split('\t') for line in p.stdout.decode('utf-8').splitlines() if line.strip()]


def tables_in(url):
    """The tables a database holds outside PostgreSQL's own schemas."""
    return [r[0] for r in _query(url, "SELECT table_schema||'.'||table_name FROM information_schema.tables "
                                       "WHERE table_schema NOT IN ('pg_catalog','information_schema') AND table_type='BASE TABLE'")]


def guard_database(url):
    if not url: raise RuntimeError('no target database (ALICE_RESTORE_TARGET_URL)')
    found = tables_in(url)
    if found:
        raise RuntimeError(f'the target database already holds {len(found)} table(s): a restore only ever goes into a new, empty database')


def guard_folder(d):
    if not os.path.isdir(d): raise RuntimeError(f'the target folder {d} does not exist')
    found = [n for n in os.listdir(d) if n not in ('lost+found',) and not n.startswith(MARKER)]
    if found: raise RuntimeError(f'the target folder {d} already holds files: a restore only ever goes into a new, empty share')


# ---------------- the database ----------------
class _Hashing(io.RawIOBase):
    def __init__(self, f):
        super().__init__(); self.f = f; self.h = hashlib.sha256(); self.size = 0

    def readable(self): return True

    def readinto(self, b):
        data = self.f.read(len(b))
        n = len(data); b[:n] = data; self.h.update(data); self.size += n
        return n

    def drain(self):
        while self.read(1024 * 1024): pass


def download(blobs, name, sha, path):
    """A blob to a local file, checked against the manifest's sha256."""
    src = _Hashing(blobs.stream(name))
    with open(path, 'wb') as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk: break
            out.write(chunk)
    if sha and src.h.hexdigest() != sha: raise RuntimeError(f'{name} does not match its manifest (sha256): the copy is damaged')
    return src.size


def load_database(dump_path, url):
    """pg_restore the dump into the empty target in one transaction (psql --single-transaction, stop on the first error).
    Only PostgreSQL 17's SET transaction_timeout line in the dump's header is left out (a 16 server refuses it)."""
    conninfo, password, env = _psql_args(url)
    with tempfile.TemporaryFile() as e1, tempfile.TemporaryFile() as e2:
        try:
            p1 = subprocess.Popen(['pg_restore', '--no-owner', '--no-privileges', '-f', '-', dump_path], stdout=subprocess.PIPE, stderr=e1, env=env)
            p2 = subprocess.Popen(['psql', '--no-psqlrc', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '--single-transaction', '--dbname', conninfo],
                                  stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=e2, env=env)
        except FileNotFoundError:
            raise RuntimeError('pg_restore or psql is not installed here') from None
        n = 0
        try:
            for line in p1.stdout:
                n += 1
                if n <= HEADER_LINES and SKIP_SET.match(line): continue
                p2.stdin.write(line)
        except BrokenPipeError:
            pass
        finally:
            try: p2.stdin.close()
            except BrokenPipeError: pass
        c1, c2 = p1.wait(), p2.wait()
        if c1 or c2:
            e1.seek(0); e2.seek(0)
            msg = (e1.read() + b' ' + e2.read()).decode('utf-8', 'replace')
            if password: msg = msg.replace(password, '***')
            raise RuntimeError('loading the database failed (nothing was kept): ' + ' '.join(msg.split())[-400:])


def database_counts(url):
    out = {}
    for label, table in COUNTED:
        try: out[label] = int(_query(url, f'SELECT count(*) FROM {table}')[0][0])
        except Exception: out[label] = None
    return out


# ---------------- the files ----------------
def unpack_files(stream, sha, d):
    """The file share archive into an empty folder: members under alice/ only, no absolute paths or '..', no links out."""
    src = _Hashing(stream)
    root = os.path.realpath(d)
    count = 0
    with tarfile.open(fileobj=src, mode='r|gz') as tar:
        for m in tar:
            if m.name in ('alice', 'alice/') or not m.name.startswith('alice/'): continue
            rel = m.name[len('alice/'):]
            target = os.path.realpath(os.path.join(root, rel))
            if os.path.isabs(rel) or not (target == root or target.startswith(root + os.sep)) or m.issym() or m.islnk() or m.isdev():
                raise RuntimeError(f'the archive holds an unsafe entry ({m.name}); nothing more was unpacked')
            m.name = rel
            if m.isdir(): os.makedirs(target, exist_ok=True); continue
            if not m.isfile(): continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            f = tar.extractfile(m)
            with open(target, 'wb') as out:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk: break
                    out.write(chunk)
            count += 1
        src.drain()
    if sha and src.h.hexdigest() != sha: raise RuntimeError('the file share archive does not match its manifest (sha256): the copy is damaged')
    return count


def file_count(d):
    return sum(len([f for f in fs if not f.startswith(MARKER)]) for _, _, fs in os.walk(d))


def compare(expected, restored):
    rows = []
    for label, _ in COUNTED + [('files on the share', '')]:
        e, r = expected.get(label), restored.get(label)
        if e is None and r is None: continue
        rows.append({'what': label, 'expected': e, 'restored': r, 'ok': e == r})
    return rows


# ---------------- one restore ----------------
def run():
    cfg = config()
    started = time.monotonic()
    report = {'kind': 'restore', 'drill_id': cfg['drill_id'], 'started_at': datetime.now(timezone.utc).isoformat(), 'ok': False}
    marker = os.path.join(cfg['files_dir'], MARKER + cfg['drill_id']) if cfg['drill_id'] else ''
    if marker and os.path.exists(marker):
        print('This drill\'s restore is already complete (the container restarted): nothing to do.')
        return 0
    try:
        blobs = azure_io.Blobs(cfg['account'], cfg['container'], refuse=[cfg['live_account']])
        guard_database(cfg['target'])
        guard_folder(cfg['files_dir'])
        name = cfg['manifest'] or latest_manifest(blobs)
        manifest = json.loads(blobs.get(name).decode('utf-8'))
        report['backup'] = {'manifest': name, 'taken_at': manifest.get('taken_at', ''), 'version': manifest.get('version', '')}
        with tempfile.TemporaryDirectory() as tmp:
            dump = os.path.join(tmp, 'database.dump')
            report['database_bytes'] = download(blobs, manifest['database']['blob'], manifest['database'].get('sha256', ''), dump)
            load_database(dump, cfg['target'])
        report['files_restored'] = unpack_files(blobs.stream(manifest['files']['blob']), manifest['files'].get('sha256', ''), cfg['files_dir'])
        restored = database_counts(cfg['target']); restored['files on the share'] = file_count(cfg['files_dir'])
        expected = dict(manifest.get('counts') or {}); expected['files on the share'] = manifest['files'].get('count')
        report['counts'] = compare(expected, restored)
        report['ok'] = all(r['ok'] for r in report['counts'])
        if not report['ok']: report['error'] = 'the restored counts do not match the copy: ' + ', '.join(
            f"{r['what']} {r['restored']} of {r['expected']}" for r in report['counts'] if not r['ok'])
        if marker and report['ok']:
            with open(marker, 'w') as f: f.write(report['started_at'])
    except Exception as e:
        report['error'] = ' '.join((str(e) or type(e).__name__).split())[:500]
    report['took_s'] = round(time.monotonic() - started, 1)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(report))
    if cfg['drill_id']:
        try:
            azure_io.Blobs(cfg['account'], cfg['reports']).put(f"{cfg['drill_id']}/restore.json", json.dumps(report).encode('utf-8'), 'application/json')
        except Exception as e:
            print(f'Could not write the restore report: {e}', file=sys.stderr)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(run())
