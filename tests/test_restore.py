"""Restore (restore.py, role restore): loads an off-site copy into NEW, EMPTY resources only. Azure is a stand-in; with a test
PostgreSQL server (and pg_dump, pg_restore and psql), a real dump is loaded into a fresh database too."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import urllib.parse

import azure_io
import restore as R


def tgz(entries):
    """A tar.gz like the nightly copy's: {path: bytes or None for a folder}, plus optional raw TarInfo tweaks."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name, data in entries.items():
            info = tarfile.TarInfo(name)
            if data is None: info.type = tarfile.DIRTYPE; tar.addfile(info)
            elif isinstance(data, tuple):
                info.type, info.linkname = data; tar.addfile(info)
            else: info.size = len(data); tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


sha = lambda b: hashlib.sha256(b).hexdigest()

# ---------------- the dump's PostgreSQL 17 line is the only thing filtered ----------------
t('only the header\'s SET transaction_timeout is left out', R.SKIP_SET.match(b'SET transaction_timeout = 0;\n') and not R.SKIP_SET.match(b'SET statement_timeout = 0;\n'))

# ---------------- files: into an empty folder only, safely ----------------
arch = tgz({'alice': None, 'alice/Documents': None, 'alice/Documents/leave.txt': b'Annual leave (fictional).', 'alice/data/images/a.png': b'\x89PNG' + b'x' * 100})
d = tempfile.mkdtemp(prefix='alice-test-restore-')
n = R.unpack_files(io.BytesIO(arch), sha(arch), d)
t('the share archive unpacks into the folder (alice/ prefix removed)', n == 2 and open(os.path.join(d, 'Documents', 'leave.txt')).read() == 'Annual leave (fictional).' and R.file_count(d) == 2)
try: R.guard_folder(d); refused = False
except RuntimeError as e: refused = 'already holds files' in str(e)
t('a folder that already holds files is refused (never overwrites)', refused)
e2 = tempfile.mkdtemp(prefix='alice-test-restore-')
try: R.unpack_files(io.BytesIO(arch), sha(b'something else'), e2); bad = False
except RuntimeError as e: bad = 'damaged' in str(e)
t('an archive that does not match its manifest is reported as damaged', bad)
for evil in ({'alice/../../escape.txt': b'x'}, {'alice/link': (tarfile.SYMTYPE, '/etc/passwd')}):
    e3 = tempfile.mkdtemp(prefix='alice-test-restore-')
    a = tgz(evil)
    try: R.unpack_files(io.BytesIO(a), sha(a), e3); unsafe = False
    except RuntimeError as e: unsafe = 'unsafe' in str(e)
    t('an unsafe entry (' + list(evil)[0] + ') stops the unpacking', unsafe and not os.path.exists(os.path.join(os.path.dirname(e3), 'escape.txt')))

# ---------------- the database: a target that holds tables is refused ----------------
R.tables_in = lambda url: ['public.records']
try: R.guard_database('host=x dbname=alice'); refused = False
except RuntimeError as e: refused = 'new, empty database' in str(e)
t('a database that already holds tables is refused (a live Alice can never be overwritten)', refused)

# ---------------- a whole restore with stand-ins ----------------
DUMP = b'PGDMP' + os.urandom(2000)
FILES = tgz({'alice': None, 'alice/Documents/a.txt': b'a', 'alice/Documents/b.txt': b'b', 'alice/data/c.bin': b'c'})
MAN = {'alice_backup': 1, 'taken_at': '2026-10-08T01:00:30+00:00', 'version': '73f2f1f',
       'database': {'blob': '2026/10/08/20261008T0100Z-database.dump', 'bytes': len(DUMP), 'sha256': sha(DUMP)},
       'files': {'blob': '2026/10/08/20261008T0100Z-files.tar.gz', 'bytes': len(FILES), 'sha256': sha(FILES), 'count': 3},
       'counts': {'memories': 12, 'knowledge items': 4, 'proposals': 2, 'files': 1}}
BLOBS = {('aliceoff', 'alice-offsite', '2026/10/07/20261007T0100Z-manifest.json'): b'{}',
         ('aliceoff', 'alice-offsite', '2026/10/08/20261008T0100Z-manifest.json'): json.dumps(MAN).encode(),
         ('aliceoff', 'alice-offsite', MAN['database']['blob']): DUMP, ('aliceoff', 'alice-offsite', MAN['files']['blob']): FILES}
CALLS = []

def fake_http(method, url, data=None, headers=None, timeout=60):
    CALLS.append((method, url))
    if url.startswith('http://identity/'): return 200, {}, b'{"access_token": "tok", "expires_on": "9999999999"}'
    u = urllib.parse.urlsplit(url); acct = u.hostname.split('.')[0]; parts = u.path.split('/', 2); cont = parts[1]
    q = urllib.parse.parse_qs(u.query)
    if method == 'GET' and q.get('comp') == ['list']:
        pre = q.get('prefix', [''])[0]
        names = sorted(n for (a, c, n) in BLOBS if a == acct and c == cont and n.startswith(pre))
        return 200, {}, ('<EnumerationResults>' + ''.join(f'<Blob><Name>{n}</Name></Blob>' for n in names) + '<NextMarker /></EnumerationResults>').encode()
    name = urllib.parse.unquote(parts[2])
    if method == 'GET':
        b = BLOBS.get((acct, cont, name))
        return (200, {}, b) if b is not None else (404, {}, b'<Error><Message>The specified blob does not exist.</Message></Error>')
    if method == 'PUT' and q.get('comp') == ['block']:
        BLOBS.setdefault((acct, cont, '_blocks_' + name), b''); BLOBS[(acct, cont, '_blocks_' + name)] += data; return 201, {}, b''
    if method == 'PUT' and q.get('comp') == ['blocklist']:
        BLOBS[(acct, cont, name)] = BLOBS.pop((acct, cont, '_blocks_' + name), b''); return 201, {}, b''
    raise AssertionError(url)

azure_io.HTTP = fake_http
azure_io.STREAM = lambda url, headers=None, timeout=300: (CALLS.append(('STREAM', url)) or io.BytesIO(fake_http('GET', url)[2]))
LOADED = []
R.tables_in = lambda url: []
R.load_database = lambda path, url: LOADED.append((open(path, 'rb').read(), url))
COUNTS = {'memories': 12, 'knowledge items': 4, 'proposals': 2, 'files': 1}
R.database_counts = lambda url: dict(COUNTS)
target = tempfile.mkdtemp(prefix='alice-test-restore-')
os.environ.update({'IDENTITY_ENDPOINT': 'http://identity/token', 'IDENTITY_HEADER': 'h', 'ALICE_RESTORE_ACCOUNT': 'aliceoff',
                   'ALICE_RESTORE_TARGET_URL': 'host=drill-pg dbname=alice user=drilladmin password=pw', 'ALICE_RESTORE_FILES_DIR': target,
                   'ALICE_DRILL_ID': '20261008T031700Z-abc123', 'ALICE_FILES_ACCOUNT': 'alicelivefiles'})
code = R.run()
rep = json.loads(BLOBS[('aliceoff', 'drill-reports', '20261008T031700Z-abc123/restore.json')])
t('the newest copy is restored: the dump loaded as it was, the files unpacked', code == 0 and LOADED and LOADED[0][0] == DUMP and R.file_count(target) == 3
  and rep['backup']['manifest'].startswith('2026/10/08/'))
t('the counts are compared with the ones recorded from the live database when the copy was taken', rep['ok'] and all(r['ok'] for r in rep['counts'])
  and {r['what'] for r in rep['counts']} >= {'memories', 'knowledge items', 'proposals', 'files', 'files on the share'})
writes = [u for m, u in CALLS if m == 'PUT']
t('the only thing written is the drill\'s report, in drill-reports', writes and all('/drill-reports/' in u for u in writes))
t('the copy itself is only read', all(m in ('GET', 'STREAM') for m, u in CALLS if '/alice-offsite' in u))
n = len(CALLS)
t('a restarted container does not restore twice (this drill is already complete)', R.run() == 0 and len(CALLS) == n)

# mismatch, damage, live account
def fresh(drill):
    os.environ['ALICE_DRILL_ID'] = drill; os.environ['ALICE_RESTORE_FILES_DIR'] = tempfile.mkdtemp(prefix='alice-test-restore-')
fresh('20261008T040000Z-mismatch'); COUNTS['memories'] = 11
code = R.run(); rep = json.loads(BLOBS[('aliceoff', 'drill-reports', '20261008T040000Z-mismatch/restore.json')])
t('a count that differs fails the restore and says which', code == 1 and not rep['ok'] and 'memories 11 of 12' in rep['error'])
COUNTS['memories'] = 12
fresh('20261008T050000Z-damaged'); LOADED.clear()
BLOBS[('aliceoff', 'alice-offsite', MAN['database']['blob'])] = DUMP[:-1] + b'!'
code = R.run(); rep = json.loads(BLOBS[('aliceoff', 'drill-reports', '20261008T050000Z-damaged/restore.json')])
t('a damaged copy is not loaded at all', code == 1 and 'damaged' in rep['error'] and not LOADED)
BLOBS[('aliceoff', 'alice-offsite', MAN['database']['blob'])] = DUMP
fresh('20261008T060000Z-live'); os.environ['ALICE_RESTORE_ACCOUNT'] = 'alicelivefiles'
t('the live share\'s account is never used as a source', R.run() == 1)
os.environ['ALICE_RESTORE_ACCOUNT'] = 'aliceoff'

# ---------------- a real dump into a fresh database (needs a test PostgreSQL and the PostgreSQL client tools) ----------------
base = os.environ.get('ALICE_TEST_DATABASE_URL', '')
if base and all(shutil.which(x) for x in ('pg_dump', 'pg_restore', 'psql')):
    import importlib, uuid
    import psycopg
    from psycopg.conninfo import make_conninfo
    importlib.reload(R)
    import backup
    src_db, dst_db = 'alice_rs_src_' + uuid.uuid4().hex[:8], 'alice_rs_dst_' + uuid.uuid4().hex[:8]
    with psycopg.connect(base, autocommit=True) as c:
        c.execute(f'CREATE DATABASE {src_db}'); c.execute(f'CREATE DATABASE {dst_db}')
    src, dst = make_conninfo(base, dbname=src_db), make_conninfo(base, dbname=dst_db)
    try:
        with psycopg.connect(src, autocommit=True) as c:
            c.execute('CREATE EXTENSION IF NOT EXISTS citext')
            c.execute('CREATE TABLE records (id TEXT PRIMARY KEY, title CITEXT)'); c.execute("INSERT INTO records VALUES ('a','One'),('b','Two'),('c','Three')")
            c.execute('CREATE TABLE knowledge_meta (file_id TEXT PRIMARY KEY)'); c.execute("INSERT INTO knowledge_meta VALUES ('k1')")
            c.execute('CREATE TABLE proposals (id TEXT PRIMARY KEY)'); c.execute('CREATE TABLE files (id TEXT PRIMARY KEY)')
        path = os.path.join(tempfile.mkdtemp(prefix='alice-test-restore-'), 'db.dump')
        with open(path, 'wb') as f:
            for chunk in backup.dump_chunks(src): f.write(chunk)
        R.guard_database(dst)
        R.load_database(path, dst)
        got = R.database_counts(dst)
        t('a real pg_dump loads into a fresh database with pg_restore and psql (one transaction)', got == {'memories': 3, 'knowledge items': 1, 'proposals': 0, 'files': 0})
        try: R.guard_database(dst); again = False
        except RuntimeError: again = True
        t('…and that database is then refused as a target', again)
    finally:
        with psycopg.connect(base, autocommit=True) as c:
            for db in (src_db, dst_db): c.execute(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)')
