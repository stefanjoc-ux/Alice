"""PostgreSQL compatibility layer: SQL translation always; live behaviour when ALICE_TEST_DATABASE_URL is set."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import os, sqlite3, threading, time
import dbcompat as D

# 1. translation (no database needed)
tr = D.translate
t('placeholders and literal percent', tr("SELECT * FROM x WHERE a=? AND b LIKE '50%'") == "SELECT * FROM x WHERE a=%s AND b ILIKE '50%'")
t('question mark inside a string is left alone', tr("SELECT '?' , ?") == "SELECT '?' , %s")
t('percent outside strings is escaped', tr('SELECT a%2 FROM x') == 'SELECT a%%2 FROM x')
t('instr becomes strpos', 'strpos(lower(title),lower(%s))>0' in tr('SELECT 1 WHERE instr(lower(title),lower(?))>0'))
t('INSERT OR IGNORE becomes ON CONFLICT DO NOTHING', tr('INSERT OR IGNORE INTO s VALUES (?,?)') == 'INSERT INTO s VALUES (%s,%s) ON CONFLICT DO NOTHING')
t('BEGIN IMMEDIATE becomes the write lock', 'pg_advisory_xact_lock' in tr('BEGIN IMMEDIATE'))
t('PRAGMA table_info reads information_schema', "table_name='chats'" in tr('PRAGMA table_info(chats)'))
t('other PRAGMAs are dropped', tr('PRAGMA journal_mode=WAL') is None)
ddl = tr("CREATE TABLE IF NOT EXISTS c (name TEXT PRIMARY KEY COLLATE NOCASE, n REAL, b BLOB, id INTEGER PRIMARY KEY AUTOINCREMENT)")
t('DDL types translated', 'CITEXT PRIMARY KEY' in ddl and 'DOUBLE PRECISION' in ddl and 'BYTEA' in ddl and 'BIGSERIAL PRIMARY KEY' in ddl)
t('ORDER BY ... COLLATE NOCASE becomes lower()', tr('SELECT name FROM c ORDER BY name COLLATE NOCASE') == 'SELECT name FROM c ORDER BY lower(name)')
t('chat_turns keeps an insertion-order rowid', tr('CREATE TABLE IF NOT EXISTS chat_turns (id TEXT PRIMARY KEY)').endswith(', rowid BIGSERIAL)'))
try: tr('INSERT OR REPLACE INTO x VALUES (?)'); t('INSERT OR REPLACE refused with a clear message', False)
except sqlite3.OperationalError as e: t('INSERT OR REPLACE refused with a clear message', 'ON CONFLICT' in str(e))
t('scripts split on semicolons outside quotes', D.split_script("CREATE TABLE a(x TEXT DEFAULT ';'); CREATE TABLE b(y)") == ["CREATE TABLE a(x TEXT DEFAULT ';')", 'CREATE TABLE b(y)'])

# 2. live behaviour on PostgreSQL
if os.environ.get('ALICE_DATABASE_URL'):
    import substrate_store as s
    with s.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS dc_t (name TEXT PRIMARY KEY COLLATE NOCASE, n INTEGER NOT NULL DEFAULT 0, f REAL, b BLOB)')
        c.execute('INSERT INTO dc_t(name,n,f,b) VALUES (?,?,?,?)', ('Fife Council', True, 0.1234567891234, b'\x00\x01'))
    with s.db() as c:
        r = c.execute('SELECT * FROM dc_t WHERE name=?', ('fife council',)).fetchone()
    t('rows by name and index; dict(row) works', r['name'] == 'Fife Council' and r[0] == 'Fife Council' and dict(r)['n'] == 1)
    t('case-insensitive names like SQLite NOCASE', r is not None)
    t('booleans stored as 0/1, doubles keep precision, bytes round-trip', r['n'] == 1 and r['f'] == 0.1234567891234 and bytes(r['b']) == b'\x00\x01')
    with s.db() as c:
        try: c.execute('INSERT INTO dc_t(name) VALUES (?)', ('FIFE COUNCIL',)); ok = False
        except sqlite3.IntegrityError: ok = True
        c.execute('INSERT INTO dc_t(name) VALUES (?)', ('Angus Council',))   # transaction still usable after the caught error
    with s.db() as c: n = c.execute('SELECT count(*) FROM dc_t').fetchone()[0]
    t('duplicate raises sqlite3.IntegrityError; the transaction carries on', ok and n == 2)
    try:
        with s.db() as c:
            c.execute('INSERT INTO dc_t(name) VALUES (?)', ('Rolled back',)); raise RuntimeError('boom')
    except RuntimeError: pass
    with s.db() as c: gone = not c.execute('SELECT 1 FROM dc_t WHERE name=?', ('Rolled back',)).fetchone()
    t('an error inside `with` rolls everything back', gone)
    try:
        with s.db() as c: c.execute('SELECT nope FROM dc_t'); t('unknown column raises sqlite3.OperationalError', False)
    except sqlite3.OperationalError: t('unknown column raises sqlite3.OperationalError', True)
    ro = s.connect(readonly=True)
    try: ro.execute('INSERT INTO dc_t(name) VALUES (?)', ('x',)); t('read-only connection refuses writes', False)
    except sqlite3.OperationalError: t('read-only connection refuses writes', True)
    finally: ro.close()
    with s.db() as c: t('read-only setting does not leak to the next pooled connection', c.execute("SELECT current_setting('default_transaction_read_only')").fetchone()[0] == 'off')
    # BEGIN IMMEDIATE serialises writers like SQLite's lock
    order = []
    def writer(tag, hold):
        with s.db() as c:
            c.execute('BEGIN IMMEDIATE'); order.append(tag + '-in'); time.sleep(hold); order.append(tag + '-out')
    a = threading.Thread(target=writer, args=('a', 0.4)); a.start(); time.sleep(0.1)
    b = threading.Thread(target=writer, args=('b', 0)); b.start(); a.join(); b.join()
    t('BEGIN IMMEDIATE: second writer waits for the first', order == ['a-in', 'a-out', 'b-in', 'b-out'])
    with s.db() as c: cols = {r['name'] for r in c.execute('PRAGMA table_info(dc_t)')}
    t('PRAGMA table_info lists the columns', cols == {'name', 'n', 'f', 'b'})
else:
    print('   (PostgreSQL checks skipped: set ALICE_TEST_DATABASE_URL to a test server to run them)')
