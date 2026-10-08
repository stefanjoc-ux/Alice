"""Health Insights: identifiers stripped before anything is kept, results read from a (fictional) Thriva-style PDF, uncertain
values wait for confirmation, trends compare like with like, only allowed models (Claude, GPT) get the context, and the
safety wording comes from code. No real model call; every person and value here is made up."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json
import app, substrate_store as s, health as H, documents, mcp_server, external_auth
from fastapi.testclient import TestClient
cl = TestClient(app.app); HD = {'x-admin-token': app.ADMIN_TOKEN}

def pdf(body): return base64.b64encode(documents.to_pdf('Thriva blood test report', body)).decode()

cl.put('/admin/api/health/settings', json={'redact_names': ['Alex Example']}, headers=HD)
r1 = cl.post('/admin/api/health/upload', headers=HD, json={'name': 'thriva-march.pdf', 'data': pdf(
    'Name: Alex Example Date of birth: 01/02/1980\nNHS number: 943 476 5919\nAddress: 1 Test Street, Testtown TT1 1TT\n'
    'Sample collected: 12/03/2026 Sex: Male Ferritin 120 ug/L 30 - 400\nVitamin D (25-OH) 42 nmol/L 50 - 175 Low\nHbA1c 36 mmol/mol < 42\n'
    'Total cholesterol 5.9 mmol/L < 5\nHDL cholesterol 1.4 mmol/L > 1\nEmail: alex@example.com Phone: 07700 900123\nDear Alex Example, your results.')})
d1 = r1.json()
t('a Thriva-style PDF is read', r1.status_code == 200 and {m['canonical'] for m in d1['markers']} >= {'Ferritin', 'Vitamin D', 'HbA1c', 'Total cholesterol', 'HDL cholesterol'} and d1['sample_date'] == '2026-03-12')
with s.db() as c: kept = c.execute('SELECT text_redacted FROM hi_documents WHERE id=?', (d1['id'],)).fetchone()[0]
t('identifiers are stripped before anything is kept', not any(x in kept for x in ('Alex', '1980', '943 476', 'TT1', 'alex@', '07700', 'Test Street')))
t('what was removed is recorded (counts only)', d1['removed'].get('NHS or CHI number') == 1 and d1['removed'].get('date of birth') == 1)
vd = next(m for m in d1['markers'] if m['canonical'] == 'Vitamin D')
t('the lab\'s own range and flag are kept', vd['ref_low'] == 50 and vd['ref_high'] == 175 and vd['state'] == 'low' and vd['status'] == 'confirmed')
t('the same report twice is refused', cl.post('/admin/api/health/upload', headers=HD, json={'name': 'again.pdf', 'data': pdf(
    'Name: Alex Example Date of birth: 01/02/1980\nNHS number: 943 476 5919\nAddress: 1 Test Street, Testtown TT1 1TT\n'
    'Sample collected: 12/03/2026 Sex: Male Ferritin 120 ug/L 30 - 400\nVitamin D (25-OH) 42 nmol/L 50 - 175 Low\nHbA1c 36 mmol/mol < 42\n'
    'Total cholesterol 5.9 mmol/L < 5\nHDL cholesterol 1.4 mmol/L > 1\nEmail: alex@example.com Phone: 07700 900123\nDear Alex Example, your results.')}).status_code == 400)

# a later CSV, vitamin D in ng/mL: converted for the trend; a value with no unit waits for you
csv_text = 'Marker,Result,Units,Reference range,Date\nVitamin D,24,ng/mL,20 - 70,2026-09-01\nFerritin,90,ug/L,30 - 400,2026-09-01\nMystery,5,,,2026-09-01\n'
d2 = cl.post('/admin/api/health/upload', headers=HD, json={'name': 'sept.csv', 'data': base64.b64encode(csv_text.encode()).decode()}).json()
myst = next(m for m in d2['markers'] if m['canonical'] == 'Mystery')
t('an uncertain value waits for you', myst['status'] == 'check' and 'No unit' in myst['issues'] and d2['status'] == 'check')
tr = {x['canonical']: x for x in H.trends()}
t('trends convert units only where it is safe', abs(tr['Vitamin D']['latest']['value'] - 24) < 0.01 and tr['Vitamin D']['history'][0]['value'] is not None
  and abs(tr['Vitamin D']['history'][0]['value'] - 42 / 2.496) < 0.05)
t('unconfirmed values are not in trends', 'Mystery' not in tr)
t('a 25% drop is notable', tr['Ferritin']['pct'] == -25.0 and tr['Ferritin']['notable'])
cl.post('/admin/api/health/markers/' + myst['id'], headers=HD, json={'action': 'reject'})

# who may read it
ctx = H.context('claude', 'test')
t('Claude may read confirmed results, with the safety rules from code', len(ctx['results']) >= 5 and 'not a diagnosis' in ctx['rules'] and 'medication' in ctx['rules'])
try: H.context('grok', 'test'); t('Grok never gets health data', False)
except ValueError: t('Grok never gets health data', True)
cl.put('/admin/api/health/settings', json={'providers': ['claude']}, headers=HD)
try: H.context('openai', 'test'); t('a model you switch off is refused', False)
except ValueError: t('a model you switch off is refused', True)
t('only Claude or GPT can ever be allowed', cl.put('/admin/api/health/settings', json={'providers': ['grok']}, headers=HD).status_code == 400)
cl.put('/admin/api/health/settings', json={'providers': ['claude', 'openai']}, headers=HD)

# the connector: Claude yes, Copilot no; never in memory search
mcp_server.CLIENT = 'Claude Desktop'
r = mcp_server.get_health_context()
t('Claude through the connector reads the context', any(x['marker'] == 'Ferritin' for x in r['results']))
mcp_server.CLIENT = ''
mcp_server.EXTERNAL = object()
mcp_server._viewer = lambda: None        # the owner's own signed-in connector (users.connector_viewer)
import types
mcp_server._who = lambda: external_auth.Caller('Microsoft Copilot', 'copilot')
try: mcp_server.get_health_context(); t('Copilot is refused', False)
except ValueError: t('Copilot is refused', True)
mcp_server._who = lambda: external_auth.Caller('Claude', 'claude')
n = mcp_server.propose_health_note('decision', 'Stop the statin and try diet first', 'Said in chat')
t('a model\'s note waits for approval, and a medication change is never a plan', n['status'] == 'proposed' and 'clinician' in n['message'])
e = next(x for x in H.entries() if x['id'] == n['id'])
t('it is kept as a follow-up to raise with the clinician', e['kind'] == 'follow_up' and e['caution'])
res = s.search_records('Ferritin') if hasattr(s, 'search_records') else None
with s.db() as c: in_memory = c.execute("SELECT count(*) FROM records WHERE content LIKE '%Ferritin%'").fetchone()[0]
t('health data never lands in memories', in_memory == 0)

# chat tool only for allowed providers
t('Alice\'s chat offers health_context only to allowed providers', H.allowed('claude') and not H.allowed('grok'))

# your notes, the card, the page, Apps and Actions, deletion
r = cl.post('/admin/api/health/entries', headers=HD, json={'kind': 'experiment', 'title': 'Vitamin D 2000 IU daily over winter', 'review_date': '2027-01-15'}).json()
t('you add something to track', r['status'] == 'active' and not r['caution'])
cl.post('/admin/api/health/entries/' + n['id'], headers=HD, json={'action': 'reject'})
card = cl.get('/admin/api/cards/health/Vitamin D').json()
t('a marker opens as a standard card with its history chart', card['title'] == 'Vitamin D' and len(card['sections'][1]['chart']['points']) == 2
  and any('Safety' == r[0] for r in card['sections'][3]['rows']))
ov = cl.get('/admin/api/health').json()
t('the page shows results, reports, tracking and the safety text', ov['latest_date'] == '2026-09-01' and len(ov['documents']) == 2 and 'not a diagnosis' in ov['safety'])
import apps
t('Health Insights is listed under Apps', any(a['id'] == 'health' for a in apps.listing()))
with s.db() as c:
    acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE action LIKE 'health_%'")}
    details = ' '.join(r[0] for r in c.execute("SELECT detail FROM activity WHERE action LIKE 'health_%'"))
t('views, uploads, edits and context reads are logged', {'health_uploaded', 'health_viewed', 'health_edited', 'health_context_read', 'health_context_refused'} <= acts)
t('the log never holds values or identifiers', not any(x in details for x in ('120', '42 nmol', 'Alex', '943')))
cl.delete('/admin/api/health/documents/' + d2['id'], headers=HD)
t('deleting a report removes its results', 'Ferritin' in {x['canonical'] for x in H.trends()} and H.trends()[0] and
  next(x for x in H.trends() if x['canonical'] == 'Ferritin')['latest']['date'] == '2026-03-12')
t('the page renders', 'id="hi-markers"' in cl.get('/admin/health').text)

# a report Alice's reader cannot follow: a model reads it (only an allowed one), and anything not in the report is not trusted
SENT = {}
class Msg:
    def create(self, **kw):
        SENT['text'] = kw['messages'][0]['content']
        out = {'sample_date': '2026-06-02', 'lab': 'Thriva', 'markers': [
            {'name': 'Zinc', 'value': '13.1', 'unit': 'umol/L', 'low': 11, 'high': 24, 'range_text': '11-24', 'flag': ''},
            {'name': 'Copper', 'value': '15', 'unit': 'umol/L', 'low': 99, 'high': 199, 'range_text': '', 'flag': ''}]}
        return type('R', (), {'content': [type('B', (), {'type': 'text', 'text': json.dumps(out)})()],
                              'usage': type('U', (), {'input_tokens': 5, 'output_tokens': 5, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0})()})()
class A:
    def __init__(s, **k): s.messages = Msg()
    def __enter__(s): return s
    def __exit__(s, *a): pass
import anthropic; anthropic.Anthropic = A
odd = pdf('Patient: Alex Example\nResults table\nZinc ........ 13.1 umol/L (11-24)\nCopper ........ 15 umol/L\nTaken 02/06/2026')
t('without your say, no model reads it', cl.post('/admin/api/health/upload', headers=HD, json={'name': 'odd.pdf', 'data': odd}).status_code == 400)
t('never a model you have not allowed', cl.post('/admin/api/health/upload', headers=HD, json={'name': 'odd.pdf', 'data': odd, 'use_model': True, 'provider': 'grok'}).status_code == 400)
d3 = cl.post('/admin/api/health/upload', headers=HD, json={'name': 'odd.pdf', 'data': odd, 'use_model': True, 'provider': 'claude'}).json()
zinc = next(m for m in d3['markers'] if m['canonical'] == 'Zinc'); cop = next(m for m in d3['markers'] if m['canonical'] == 'Copper')
t('the model only ever sees the report with identifiers removed', 'Alex' not in SENT['text'])
t('values found in the report are kept with their range', zinc['ref_low'] == 11 and zinc['confidence'] >= 0.8)
t('a range the report does not give is dropped and the value waits for you', cop['ref_low'] is None and cop['status'] == 'check')
