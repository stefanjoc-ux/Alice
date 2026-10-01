"""PostgreSQL behind Alice's SQLite-style database calls.

Alice was written against sqlite3. When ALICE_DATABASE_URL is set, substrate_store.db() hands out a
PgConnection from this module instead: it accepts the same SQL Alice already writes (? placeholders,
INSERT OR IGNORE, BEGIN IMMEDIATE, PRAGMA table_info, instr, COLLATE NOCASE...), returns rows that behave
like sqlite3.Row (by index or column name, dict(row) works), and raises sqlite3's exception types, so code
that catches sqlite3.IntegrityError or sqlite3.OperationalError keeps working unchanged.

Transactions match sqlite3's context manager: `with conn:` commits on success and rolls back on error.
Each statement runs inside its own savepoint, so an error that the caller catches does not poison the rest
of the transaction (in PostgreSQL it otherwise would). BEGIN IMMEDIATE becomes a transaction-scoped
advisory lock, which serialises writers the way SQLite's reserved lock does.

Nothing here reads credentials itself: the connection string comes from the environment (Key Vault in Azure).
"""
import re
import sqlite3
import threading
from functools import lru_cache

try:                        # only needed when ALICE_DATABASE_URL is set; SQLite installs don't need it
    import psycopg
    from psycopg import errors as pgerr
    from psycopg.adapt import Dumper
    from psycopg_pool import ConnectionPool
except ImportError:         # translation (and its tests) still work without the driver
    psycopg = pgerr = ConnectionPool = None
    Dumper = object

ROWID_TABLES = {'chat_turns'}   # tables whose code orders by SQLite's rowid
WRITE_LOCK = 0x41_6C_69_63   # 'Alic': key for the advisory lock that stands in for BEGIN IMMEDIATE


# ---------------- SQL translation ----------------
_QUOTED = re.compile(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")")


def _outside_quotes(sql, fn):
    parts = _QUOTED.split(sql)
    return ''.join(p if i % 2 else fn(p) for i, p in enumerate(parts))


def _table_info(m):
    return ("SELECT column_name AS name, data_type AS type FROM information_schema.columns "
            f"WHERE table_schema=current_schema() AND table_name='{m.group(1).lower()}' ORDER BY ordinal_position")


def _plain(p, ddl=False):
    p = p.replace('%', '%%').replace('?', '%s')
    p = re.sub(r'\binstr\s*\(', 'strpos(', p, flags=re.I)
    if ddl: return p                                       # CREATE TABLE ... (LIKE other) copies a table
    p = re.sub(r'\bNOT\s+LIKE\b', 'NOT ILIKE', p, flags=re.I)
    p = re.sub(r'(?<!NOT )\bLIKE\b', 'ILIKE', p, flags=re.I)
    return p


@lru_cache(maxsize=4096)
def translate(sql):
    s = sql.strip().rstrip(';').strip()
    if re.fullmatch(r'BEGIN(\s+(IMMEDIATE|EXCLUSIVE|DEFERRED))?(\s+TRANSACTION)?', s, re.I):
        return f'SELECT pg_advisory_xact_lock({WRITE_LOCK})'
    m = re.fullmatch(r'PRAGMA\s+table_info\s*\(\s*["\']?(\w+)["\']?\s*\)', s, re.I)
    if m: return _table_info(m)
    if re.match(r'PRAGMA\b', s, re.I): return None          # SQLite tuning pragmas: nothing to do
    ddl = re.match(r'(CREATE|ALTER)\b', s, re.I)

    def fix(p):
        if ddl:
            p = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'BIGSERIAL PRIMARY KEY', p, flags=re.I)
            p = re.sub(r'\bTEXT\b([^,()]*?)\s+COLLATE\s+NOCASE\b', r'CITEXT\1', p, flags=re.I)
            p = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', p, flags=re.I)
            p = re.sub(r'\bBLOB\b', 'BYTEA', p, flags=re.I)
        p = re.sub(r'([\w.]+)\s+COLLATE\s+NOCASE\b', r'lower(\1)', p, flags=re.I)
        return _plain(p, bool(ddl))

    out = _outside_quotes(s, fix)
    t = re.match(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\(', out, re.I)
    if t and t.group(1).lower() in ROWID_TABLES:      # SQLite's hidden insertion order, made explicit
        out = out[:out.rstrip().rfind(')')] + ', rowid BIGSERIAL)'
    if re.match(r'INSERT\s+OR\s+IGNORE\s+INTO\b', out, re.I):
        out = re.sub(r'^INSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', out, flags=re.I) + ' ON CONFLICT DO NOTHING'
    elif re.match(r'INSERT\s+OR\s+REPLACE\b', out, re.I):
        raise sqlite3.OperationalError('INSERT OR REPLACE is not supported on PostgreSQL; use INSERT ... ON CONFLICT(...) DO UPDATE.')
    return out


def split_script(script):
    """Split an executescript() body into statements, ignoring semicolons inside quotes."""
    out, buf = [], []
    for i, part in enumerate(_QUOTED.split(script)):
        if i % 2: buf.append(part); continue
        pieces = part.split(';')
        for j, piece in enumerate(pieces):
            buf.append(piece)
            if j < len(pieces) - 1:
                stmt = ''.join(buf).strip()
                if stmt: out.append(stmt)
                buf = []
    stmt = ''.join(buf).strip()
    if stmt: out.append(stmt)
    return out


# ---------------- rows, cursors, errors ----------------
class Row(tuple):
    """Like sqlite3.Row: row[0], row['name'], row.keys(), dict(row)."""
    __slots__ = ()
    _keys = ()

    def __new__(cls, values, keys):
        r = super().__new__(cls, values)
        return r

    def __getitem__(self, k):
        if isinstance(k, str):
            try: return tuple.__getitem__(self, self._index[k])
            except KeyError:
                lk = k.lower()
                for i, name in enumerate(self._keys):
                    if name.lower() == lk: return tuple.__getitem__(self, i)
                raise IndexError('No item with that key') from None
        return tuple.__getitem__(self, k)

    def keys(self): return list(self._keys)


@lru_cache(maxsize=2048)
def _row_class(keys):
    return type('Row', (Row,), {'__slots__': (), '_keys': keys, '_index': {k: i for i, k in enumerate(keys)}})


def _map_error(e):
    msg = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    if isinstance(e, pgerr.IntegrityError): return sqlite3.IntegrityError(msg)
    if isinstance(e, (pgerr.UndefinedTable, pgerr.UndefinedColumn, pgerr.SyntaxError, pgerr.UndefinedFunction,
                      pgerr.ReadOnlySqlTransaction, psycopg.OperationalError, pgerr.LockNotAvailable,
                      pgerr.QueryCanceled, pgerr.DeadlockDetected, pgerr.SerializationFailure)):
        return sqlite3.OperationalError(msg)
    if isinstance(e, psycopg.DataError): return sqlite3.DataError(msg) if hasattr(sqlite3, 'DataError') else sqlite3.OperationalError(msg)
    return sqlite3.OperationalError(msg)


class Cursor:
    def __init__(self, rows=None, rowcount=-1, description=None):
        self._rows, self.rowcount, self.description, self._i = rows or [], rowcount, description, 0
        self.lastrowid = None

    def fetchone(self):
        if self._i >= len(self._rows): return None
        self._i += 1
        return self._rows[self._i - 1]

    def fetchall(self):
        rest, self._i = self._rows[self._i:], len(self._rows)
        return rest

    def fetchmany(self, n=1):
        rest = self._rows[self._i:self._i + n]; self._i += len(rest)
        return rest

    def __iter__(self):
        while True:
            r = self.fetchone()
            if r is None: return
            yield r


class _BoolAsInt(Dumper):
    """SQLite stores Python booleans as 0/1 in INTEGER columns; do the same here."""
    oid = psycopg.adapters.types['int8'].oid if psycopg else 0
    def dump(self, obj): return b'1' if obj else b'0'


# ---------------- connection ----------------
class PgConnection:
    """One pooled PostgreSQL connection that behaves like the sqlite3 connections Alice uses."""

    def __init__(self, pool, readonly=False):
        self._pool, self._readonly = pool, readonly
        self._conn = pool.getconn()
        self._tx = None
        self.row_factory = None          # accepted and ignored; rows always behave like sqlite3.Row
        if readonly: self._conn.execute('SET default_transaction_read_only = on')

    # sqlite3's context manager: commit on success, roll back on error (connection stays open)
    def __enter__(self):
        if self._tx is None:
            self._tx = self._conn.transaction()
            self._tx.__enter__()
        return self

    def __exit__(self, et, ev, tb):
        tx, self._tx = self._tx, None
        if tx is not None:
            try: tx.__exit__(et, ev, tb)
            except psycopg.Error as e: raise _map_error(e) from e
        return False

    def commit(self):
        if self._tx is not None:
            self.__exit__(None, None, None); self.__enter__()

    def rollback(self):
        if self._tx is not None:
            tx, self._tx = self._tx, None
            try: tx.__exit__(sqlite3.OperationalError, sqlite3.OperationalError('rollback'), None)
            except Exception: pass
            self.__enter__()

    def close(self):
        if self._conn is None: return
        if self._tx is not None:
            try: self._tx.__exit__(None, None, None)
            except Exception: pass
            self._tx = None
        try:
            if self._readonly: self._conn.execute('RESET default_transaction_read_only')
        except Exception: pass
        self._pool.putconn(self._conn); self._conn = None

    def __del__(self):
        try: self.close()
        except Exception: pass

    def _run(self, sql, params):
        q = translate(sql)
        if q is None: return Cursor()
        try:
            if self._tx is not None:
                with self._conn.transaction():      # savepoint: a caught error leaves the transaction usable
                    cur = self._conn.execute(q, params or None, prepare=False)
            else:
                cur = self._conn.execute(q, params or None, prepare=False)
        except psycopg.Error as e:
            raise _map_error(e) from e
        if cur.description is None: return Cursor(rowcount=cur.rowcount)
        cls = _row_class(tuple(d.name for d in cur.description))
        rows = [cls(r, None) for r in cur.fetchall()]
        return Cursor(rows, cur.rowcount, cur.description)

    def execute(self, sql, params=()):
        if isinstance(params, dict): raise sqlite3.ProgrammingError('Named parameters are not supported; use ?.')
        return self._run(sql, tuple(params))

    def executemany(self, sql, seq):
        n = 0
        for p in seq: n += max(0, self.execute(sql, p).rowcount)
        return Cursor(rowcount=n)

    def executescript(self, script):
        for stmt in split_script(script): self._run(stmt, ())
        return Cursor()


_pools, _lock = {}, threading.Lock()


def _configure(conn):
    conn.adapters.register_dumper(bool, _BoolAsInt)


def pool_for(url):
    if psycopg is None:
        raise RuntimeError('ALICE_DATABASE_URL is set but the PostgreSQL driver is missing: pip install "psycopg[binary]" psycopg-pool')
    with _lock:
        p = _pools.get(url)
        if p is None:
            p = ConnectionPool(url, min_size=1, max_size=10, kwargs={'autocommit': True}, configure=_configure, open=True,
                               name='alice')
            with p.connection() as c:
                try: c.execute('CREATE EXTENSION IF NOT EXISTS citext SCHEMA public')
                except psycopg.Error: pass   # already there, or not allowed: CITEXT columns then fail loudly
            _pools[url] = p
        return p


def connect(url, readonly=False):
    return PgConnection(pool_for(url), readonly)


def close_pools():
    with _lock:
        for p in _pools.values():
            try: p.close()
            except Exception: pass
        _pools.clear()
