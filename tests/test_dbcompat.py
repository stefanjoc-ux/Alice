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

# 3. speed (6 Oct 2026): reads open no transaction; the first write does, and the block still commits or rolls back as one
t('plain reads are recognised; BEGIN, WITH and locking reads are not', D._plain_read('SELECT 1') and D._plain_read('  select x from y')
  and D._plain_read('PRAGMA table_info(chats)') and not D._plain_read('BEGIN IMMEDIATE') and not D._plain_read('WITH a AS (DELETE FROM x) SELECT 1')
  and not D._plain_read('SELECT * FROM x FOR UPDATE') and not D._plain_read('INSERT INTO x VALUES (1)'))
if os.environ.get('ALICE_DATABASE_URL'):
    import substrate_store as s
    with s.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS dc_lazy (k TEXT PRIMARY KEY, v INTEGER)')
    with s.db() as c:
        c.execute('SELECT count(*) FROM dc_lazy').fetchone()
        t('a block that only reads opens no transaction', c._tx is None)
    try:
        with s.db() as c:
            c.execute('SELECT 1').fetchone()
            c.execute("INSERT INTO dc_lazy VALUES ('a', 1)")
            t('the first write opens the transaction', c._tx is not None)
            c.execute("INSERT INTO dc_lazy VALUES ('b', 2)")
            raise RuntimeError('stop')
    except RuntimeError: pass
    with s.db() as c: n = c.execute('SELECT count(*) FROM dc_lazy').fetchone()[0]
    t('an error after the writes still rolls the whole block back', n == 0)
    with s.db() as c:
        c.execute("INSERT INTO dc_lazy VALUES ('c', 3)")
        try: c.execute("INSERT INTO dc_lazy VALUES ('c', 4)")
        except sqlite3.IntegrityError: pass
        c.execute("INSERT INTO dc_lazy VALUES ('d', 5)")
    with s.db() as c: rows = sorted(r[0] for r in c.execute('SELECT k FROM dc_lazy'))
    t('a caught error inside a transaction still leaves it usable (savepoints after the first write)', rows == ['c', 'd'])
    try:
        with s.db() as c:
            try: c.execute('SELECT * FROM no_such_table_here')
            except sqlite3.OperationalError: pass
            c.execute("INSERT INTO dc_lazy VALUES ('e', 6)")
    except Exception as e: t('a failed read before any write does not poison the block', False)
    else:
        with s.db() as c: t('a failed read before any write does not poison the block', c.execute("SELECT 1 FROM dc_lazy WHERE k='e'").fetchone() is not None)
    with s.db() as c:
        c.execute('BEGIN IMMEDIATE')
        t('BEGIN IMMEDIATE opens the transaction, so the write lock is held to the end of the block', c._tx is not None)
