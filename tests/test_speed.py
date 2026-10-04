"""Speed: request timing (server time, database time, queries, connections), page loads from the browser, the Speed page,
and compression (pages compressed, streamed answers left alone). Only routes and timings are kept, never content."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import gzip
import temple
temple.save_settings(False, 'openai')
import app, speed, substrate_store as s
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

r = cl.get('/admin/api/memories?status=all')
t('every request says where its time went (Server-Timing)', 'app;dur=' in r.headers.get('server-timing', '') and 'queries' in r.headers['server-timing'])
q = int(r.headers['server-timing'].split('"')[1].split()[0])
t('database queries are counted for the request', q > 0)
cl.get('/admin/api/memories?status=all&query=secret-search-words')
cl.get('/healthz'); cl.get('/static/favicon.png')
speed.flush()
with s.db() as c:
    rows = {r['route']: dict(r) for r in c.execute('SELECT * FROM speed_routes')}
    cols = [r[1] for r in c.execute('PRAGMA table_info(speed_routes)')] + [r[1] for r in c.execute('PRAGMA table_info(speed_slow)')]
t('requests are recorded by route, counted together', rows.get('/admin/api/memories', {}).get('count') == 2 and rows['/admin/api/memories']['queries'] >= 2)
t('the health check and static files are not recorded', '/healthz' not in rows and not any(k.startswith('/static') for k in rows))
t('what you searched for is never kept (no query strings, no content columns)', not any('secret-search-words' in k for k in rows)
  and not {'body', 'query', 'content', 'params'} & set(cols))
cl.get('/admin/memories')
speed.flush()
with s.db() as c: t('Command centre pages are recorded under their own address', c.execute("SELECT 1 FROM speed_routes WHERE route='/admin/memories'").fetchone() is not None)

# slow requests keep their breakdown
m = speed.Meter(); m.queries, m.db_s, m.conns = 120, 1.4, 3
speed.record('GET', '/admin/api/assistants', 200, 2.2, m)
speed.flush()
rep = speed.report(7)
row = next(x for x in rep['server'] if x['route'] == '/admin/api/assistants')
t('report: average, slowest, database share, queries, connections', row['avg_ms'] == 2200 and row['max_ms'] == 2200 and row['db_share'] == 64
  and row['avg_queries'] == 120 and row['avg_conns'] == 3 and row['slow'] == 1)
t('slow requests listed with their breakdown', rep['slow'][0]['route'] == '/admin/api/assistants' and rep['slow'][0]['ms'] == 2200 and rep['slow'][0]['queries'] == 120)

# page loads reported by the browser
t('page load from the browser accepted', cl.post('/admin/api/speed/page', headers=H, json={'page': '/admin/assistants', 'ms': 3150, 'kb': 94}).status_code == 200)
t('page load needs the admin token', cl.post('/admin/api/speed/page', json={'page': '/admin', 'ms': 1}).status_code == 403)
t('only page addresses accepted', cl.post('/admin/api/speed/page', headers=H, json={'page': 'https://evil.example.com/x', 'ms': 1}).status_code == 400
  and cl.post('/admin/api/speed/page', headers=H, json={'page': '/admin?q=private words', 'ms': 1}).status_code == 400)
rep = cl.get('/admin/api/speed?days=7').json()
t('Speed page data: browser page loads and a summary', rep['pages'][0]['route'] == 'page /admin/assistants' and rep['pages'][0]['avg_ms'] == 3150
  and rep['summary']['page_loads'] == 1 and rep['summary']['requests'] > 0)
page = cl.get('/admin/speed').text
t('Speed page is served and in the menu', 'id="sp-server"' in page and 'data-page="speed"' in page)
t('every Command centre page reports its load time', "/admin/api/speed/page" in cl.get('/admin/apps').text)

# compression
r = cl.get('/admin/actions', headers={'Accept-Encoding': 'gzip'})
t('pages are compressed', r.headers.get('content-encoding') == 'gzip')
t('streamed answers are not compressed (they must arrive word by word)',
  any(getattr(mw, 'kwargs', {}).get('exclude_content_types') and 'application/x-ndjson' in mw.kwargs['exclude_content_types'] for mw in app.app.user_middleware))
from starlette.applications import Starlette
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import StreamingResponse
from starlette.routing import Route
async def nd(req):
    async def gen():
        for i in range(3): yield (str(i) * 800 + '\n').encode()
    return StreamingResponse(gen(), media_type='application/x-ndjson')
kw = next(mw.kwargs for mw in app.app.user_middleware if mw.cls is GZipMiddleware)
mini = GZipMiddleware(Starlette(routes=[Route('/s', nd)]), **kw)
t('an NDJSON stream passes through uncompressed with the same settings', TestClient(mini).get('/s', headers={'Accept-Encoding': 'gzip'}).headers.get('content-encoding') is None)
