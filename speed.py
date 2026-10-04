"""Speed: where Alice's time goes, so slow screens can be fixed with evidence rather than guesses.

For every request (except static files and the health check) the middleware in app.py records the total server time,
the time spent in the database and how many queries and connections it took (counted in dbcompat and store.connect via
the context variable below). The Command centre pages also report how long they took to load in your browser
(network + drawing), which is what you actually feel on the tablet. Nothing about the content of a request is kept:
only the route (e.g. /admin/api/memories), method, status and timings.

Kept in memory and written to the database once a minute by a background thread (never inside a request):
  speed_routes  one row per day and route: count, total and slowest time, database time, queries, slow ones (> 1 s)
  speed_slow    the last 500 slow requests (> 1 s), each with its breakdown
Shown on the Speed page (Records and settings); 30 days kept.
"""
import contextvars
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta

import substrate_store as store

SLOW_MS = 1000
KEEP_DAYS = 30
SKIP = ('/static/', '/healthz', '/favicon', '/manifest.webmanifest', '/icon-')


class Meter:
    __slots__ = ('queries', 'db_s', 'conns', 'conn_s')

    def __init__(self):
        self.queries, self.db_s, self.conns, self.conn_s = 0, 0.0, 0, 0.0


CURRENT = contextvars.ContextVar('alice_speed', default=None)


def db_call(seconds):
    m = CURRENT.get()
    if m is not None: m.queries += 1; m.db_s += seconds


def conn_open(seconds):
    m = CURRENT.get()
    if m is not None: m.conns += 1; m.conn_s += seconds


def skip(path):
    return any(path.startswith(p) for p in SKIP)


def route_name(scope, path):
    """The route template (so /admin/api/records/<id> is one row), but the real address for Command centre pages."""
    r = scope.get('route')
    name = getattr(r, 'path', '') or path
    if name in ('/admin/{page}', '/assistant/{aid}', '/assistant/{assistant_id}'): name = path
    return name[:120]


_lock = threading.Lock()
_agg = {}                         # (day, method, route) -> [count, total_ms, max_ms, db_ms, queries, conns, slow]
_slow = deque(maxlen=500)


def record(method, route, status, total_s, m, kind='server', extra=''):
    ms = round(total_s * 1000, 1)
    db_ms = round(m.db_s * 1000, 1) if m else 0.0
    q, conns = (m.queries, m.conns) if m else (0, 0)
    day = datetime.now(timezone.utc).date().isoformat()
    key = (day, method if kind == 'server' else 'PAGE', route)
    with _lock:
        a = _agg.setdefault(key, [0, 0.0, 0.0, 0.0, 0, 0, 0])
        a[0] += 1; a[1] += ms; a[2] = max(a[2], ms); a[3] += db_ms; a[4] += q; a[5] += conns
        if ms >= SLOW_MS:
            a[6] += 1
            _slow.append((store.now(), key[1], route, int(status or 0), ms, db_ms, q, conns, extra[:200]))
    _start_flusher()


def page_load(route, total_ms, transfer_kb=0.0):
    """A page load as measured in the browser (navigation timing): sent by the page itself after it has drawn."""
    total_ms = max(0.0, min(float(total_ms), 600000.0))
    record('PAGE', route[:120], 200, total_ms / 1000, None, kind='page', extra=f'{float(transfer_kb):.0f} KB transferred')


def _schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS speed_routes (day TEXT NOT NULL, method TEXT NOT NULL, route TEXT NOT NULL, '
              'count INTEGER NOT NULL DEFAULT 0, total_ms REAL NOT NULL DEFAULT 0, max_ms REAL NOT NULL DEFAULT 0, '
              'db_ms REAL NOT NULL DEFAULT 0, queries INTEGER NOT NULL DEFAULT 0, conns INTEGER NOT NULL DEFAULT 0, '
              'slow INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, method, route))')
    c.execute('CREATE TABLE IF NOT EXISTS speed_slow (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, method TEXT NOT NULL, '
              'route TEXT NOT NULL, status INTEGER NOT NULL DEFAULT 0, ms REAL NOT NULL, db_ms REAL NOT NULL DEFAULT 0, '
              'queries INTEGER NOT NULL DEFAULT 0, conns INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT \'\')')


with store.db() as _c: _schema(_c)


def _hook():
    import dbcompat
    dbcompat.ON_QUERY = db_call
    dbcompat.ON_CONNECT = conn_open
    store.ON_SQLITE_QUERY = lambda _sql: db_call(0.0)


_hook()


def flush():
    """Write what has been measured since the last flush. Runs outside any request, so it is never measured itself."""
    with _lock:
        agg, slow = dict(_agg), list(_slow)
        _agg.clear(); _slow.clear()
    if not agg and not slow: return 0
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=KEEP_DAYS)).isoformat()
    with store.db() as c:
        for (day, method, route), a in agg.items():
            c.execute('INSERT INTO speed_routes (day,method,route,count,total_ms,max_ms,db_ms,queries,conns,slow) VALUES (?,?,?,?,?,?,?,?,?,?) '
                      'ON CONFLICT(day,method,route) DO UPDATE SET count=speed_routes.count+excluded.count, '
                      'total_ms=speed_routes.total_ms+excluded.total_ms, '
                      'max_ms=CASE WHEN excluded.max_ms > speed_routes.max_ms THEN excluded.max_ms ELSE speed_routes.max_ms END, '
                      'db_ms=speed_routes.db_ms+excluded.db_ms, queries=speed_routes.queries+excluded.queries, '
                      'conns=speed_routes.conns+excluded.conns, slow=speed_routes.slow+excluded.slow',
                      (day, method, route, *a))
        for s in slow:
            c.execute('INSERT INTO speed_slow (at,method,route,status,ms,db_ms,queries,conns,note) VALUES (?,?,?,?,?,?,?,?,?)', s)
        c.execute('DELETE FROM speed_routes WHERE day < ?', (cutoff,))
        c.execute('DELETE FROM speed_slow WHERE id NOT IN (SELECT id FROM speed_slow ORDER BY id DESC LIMIT 500)')
    return len(agg)


_flusher = None


def _start_flusher():
    global _flusher
    if _flusher is not None: return
    with _lock:
        if _flusher is not None: return
        def loop():
            while True:
                time.sleep(60)
                try: flush()
                except Exception: pass
        _flusher = threading.Thread(target=loop, daemon=True, name='speed-flush')
        _flusher.start()


def report(days=7):
    """The Speed page: slowest routes first (by total time spent), page loads in the browser, recent slow requests."""
    try: flush()
    except Exception: pass
    since = (datetime.now(timezone.utc).date() - timedelta(days=max(1, min(int(days), KEEP_DAYS)) - 1)).isoformat()
    with store.db() as c:
        rows = [dict(r) for r in c.execute(
            'SELECT method, route, SUM(count) AS count, SUM(total_ms) AS total_ms, MAX(max_ms) AS max_ms, SUM(db_ms) AS db_ms, '
            'SUM(queries) AS queries, SUM(conns) AS conns, SUM(slow) AS slow FROM speed_routes WHERE day >= ? '
            'GROUP BY method, route ORDER BY SUM(total_ms) DESC', (since,))]
        slow = [dict(r) for r in c.execute('SELECT at, method, route, status, ms, db_ms, queries, conns, note FROM speed_slow '
                                           'ORDER BY id DESC LIMIT 100')]
    out = []
    for r in rows:
        n = max(1, r['count'])
        out.append({'method': r['method'], 'route': r['route'], 'count': r['count'], 'avg_ms': round(r['total_ms'] / n),
                    'max_ms': round(r['max_ms']), 'db_share': round(100 * r['db_ms'] / r['total_ms']) if r['total_ms'] else 0,
                    'avg_db_ms': round(r['db_ms'] / n), 'avg_queries': round(r['queries'] / n, 1),
                    'avg_conns': round(r['conns'] / n, 1), 'slow': r['slow'], 'total_s': round(r['total_ms'] / 1000, 1)})
    server = [r for r in out if r['method'] != 'PAGE']
    pages = sorted([r for r in out if r['method'] == 'PAGE'], key=lambda r: -r['avg_ms'])
    tot = sum(r['total_s'] for r in server)
    db = sum(r['avg_db_ms'] * r['count'] for r in server) / 1000
    return {'days': days, 'server': server[:60], 'pages': pages[:40], 'slow': slow,
            'summary': {'requests': sum(r['count'] for r in server), 'server_s': round(tot, 1), 'db_s': round(db, 1),
                        'db_share': round(100 * db / tot) if tot else 0, 'slow': sum(r['slow'] for r in server),
                        'page_loads': sum(r['count'] for r in pages),
                        'avg_page_ms': round(sum(r['avg_ms'] * r['count'] for r in pages) / max(1, sum(r['count'] for r in pages)))}}
