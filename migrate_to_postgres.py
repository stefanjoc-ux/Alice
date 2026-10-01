"""Copy Alice's SQLite database into PostgreSQL, and prove the copy is exact.

    python migrate_to_postgres.py                 dry run: copies everything inside one transaction,
                                                  checks it, then rolls back (nothing is kept)
    python migrate_to_postgres.py --apply         the same, then commits
    python migrate_to_postgres.py --apply --replace   empties the TARGET's Alice tables first (target only)

Source: data\\substrate.db (or --source PATH), opened read-only; it is never changed.
Target: the connection string in ALICE_MIGRATE_TARGET_URL (never printed). Use the Azure database's admin
login for the migration, then give the app its own login.

Tables are created from SQLite's own definitions (which include every column added since), translated for
PostgreSQL, so column order matches exactly. Then every row is copied and each table is checked: same row
count and the same checksum over every value. chat_turns keeps SQLite's insertion order (its rowid).
Generated images in data\\images are not part of the database; they move separately.
"""
import argparse
import hashlib
import os
import re
import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg import sql as pgsql

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import dbcompat

try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass

SERIAL_COLUMNS = {}          # filled from the translated definitions: table -> serial column


def sqlite_objects(src):
    tables = [(r[0], r[1]) for r in src.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    indexes = [(r[0], r[1]) for r in src.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY rowid")]
    return tables, indexes


def pg_create(table_sql):
    s = re.sub(r'^\s*CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?', 'CREATE TABLE IF NOT EXISTS ', table_sql, flags=re.I)
    return dbcompat.translate(s)


def pg_index(index_sql):
    s = re.sub(r'^\s*CREATE\s+(UNIQUE\s+)?INDEX\s+(IF\s+NOT\s+EXISTS\s+)?', lambda m: f"CREATE {m.group(1) or ''}INDEX IF NOT EXISTS ",
               index_sql, flags=re.I)
    return dbcompat.translate(s)


def norm(v):
    if v is None: return '\x00null'
    if isinstance(v, (bytes, bytearray, memoryview)): return 'b:' + hashlib.sha256(bytes(v)).hexdigest()
    if isinstance(v, bool): return str(int(v))
    if isinstance(v, float): return repr(v)
    return str(v)


def checksum(rows):
    h = hashlib.sha256()
    for r in sorted('\x1f'.join(norm(v) for v in row) for row in rows): h.update(r.encode('utf-8', 'surrogatepass')); h.update(b'\x1e')
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default=str(Path(os.getenv('AISUBSTRATE_DATA_DIR', str(BASE / 'data'))) / 'substrate.db'))
    ap.add_argument('--apply', action='store_true', help='Commit the copy (default is a dry run that rolls back)')
    ap.add_argument('--replace', action='store_true', help='Empty the target Alice tables first (target only)')
    a = ap.parse_args()
    url = os.getenv('ALICE_MIGRATE_TARGET_URL', '').strip()
    if not url: print('Set ALICE_MIGRATE_TARGET_URL to the target PostgreSQL connection string.'); return 2
    src_path = Path(a.source)
    if not src_path.is_file(): print(f'No SQLite database at {src_path}.'); return 2

    src = sqlite3.connect(src_path.resolve().as_uri() + '?mode=ro', uri=True)
    src.execute('PRAGMA query_only=ON')
    tables, indexes = sqlite_objects(src)
    print(f"{'DRY RUN (nothing kept)' if not a.apply else 'APPLY'}: {len(tables)} tables from {src_path.name}\n")

    problems = []
    with psycopg.connect(url, autocommit=False) as dst:
        dst.adapters.register_dumper(bool, dbcompat._BoolAsInt)
        with dst.cursor() as cur:
            cur.execute('CREATE EXTENSION IF NOT EXISTS citext')
            existing = {r[0] for r in cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()")}
            names = [t for t, _ in tables]
            busy = [t for t in names if t in existing and cur.execute(pgsql.SQL('SELECT count(*) FROM {}').format(pgsql.Identifier(t))).fetchone()[0]]
            if busy and not a.replace:
                print('The target already has data in: ' + ', '.join(busy) + '\nUse --replace to empty those tables first, or point at an empty database.')
                return 1
            for t, ddl in tables:
                q = pg_create(ddl)
                cur.execute(q)
                if t in busy: cur.execute(pgsql.SQL('TRUNCATE {}').format(pgsql.Identifier(t)))
                m = re.search(r'(\w+)\s+BIGSERIAL', q, re.I)
                if m: SERIAL_COLUMNS[t] = m.group(1)
            for _, ddl in indexes:
                cur.execute(pg_index(ddl))

            for t, _ in tables:
                cols = [r[1] for r in src.execute(f'PRAGMA table_info("{t}")')]
                keep_rowid = t in dbcompat.ROWID_TABLES
                sel = ', '.join(f'"{c}"' for c in cols) + (', rowid' if keep_rowid else '')
                rows = src.execute(f'SELECT {sel} FROM "{t}"').fetchall()
                tcols = cols + (['rowid'] if keep_rowid else [])
                ins = pgsql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                    pgsql.Identifier(t), pgsql.SQL(', ').join(map(pgsql.Identifier, tcols)), pgsql.SQL(', ').join(pgsql.Placeholder() * len(tcols)))
                try:
                    if rows: cur.executemany(ins, rows)
                except psycopg.Error as e:
                    problems.append(f'{t}: could not copy ({str(e).splitlines()[0]})'); dst.rollback(); break
                serial = SERIAL_COLUMNS.get(t)
                if serial and rows:
                    cur.execute(pgsql.SQL("SELECT setval(pg_get_serial_sequence(%s, %s), (SELECT max({}) FROM {}))").format(
                        pgsql.Identifier(serial), pgsql.Identifier(t)), (t, serial))
                back = cur.execute(pgsql.SQL('SELECT {} FROM {}').format(pgsql.SQL(', ').join(map(pgsql.Identifier, tcols)), pgsql.Identifier(t))).fetchall()
                same_n, same_sum = len(back) == len(rows), checksum(back) == checksum(rows)
                print(f"{'OK  ' if same_n and same_sum else 'DIFF'} {t:<26} {len(rows):>7} rows" + ('' if same_sum else '  (values differ)'))
                if not (same_n and same_sum): problems.append(f'{t}: {len(rows)} rows in SQLite, {len(back)} in PostgreSQL' + ('' if same_sum else ', values differ'))

        if problems or not a.apply:
            dst.rollback()
        else:
            dst.commit()
    src.close()
    print()
    if problems:
        print('NOT COPIED. Problems:\n  ' + '\n  '.join(problems)); return 1
    print('All tables match.' + (' Committed.' if a.apply else ' Dry run: rolled back, nothing kept. Run with --apply to copy for real.'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
