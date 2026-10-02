"""Data touched, organised by source (web with URLs, document library with file paths, Alice's own data with links and
status), and the data sources outside Alice on the system map."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import substrate_store as s
s.init()
import agents as A, knowledge as K, organisations as O, doc_library as L
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

mem = s.propose('Rail booking rule', 'Book rail travel seven days ahead.', 'Stefan said')['id']; s.review(mem, 'approved')
gone = s.propose('Temporary parking note', 'Visitor parking is in bay four this week.', 'Stefan said')['id']
kn = K.create('note', 'Travel guidance', 'Book rail travel at least seven days ahead.', 'Travel team', 'you', label='internal')['id']
O.create('Acme Council')
URL = 'https://www.example.gov.uk/news/2026/09/a-very-long-path/' + 'x' * 120 + '?page=2'


@A.tracked('temple-org-research', trigger='test')
def fake_run():
    A.note('read', 'web', URL, 'Council news · cited')
    A.note('read', 'web', 'https://example.org/b', 'returned by the search, not cited')
    A.note('read', 'document', 'HR\\Employee-Policy-Handbook-v1.0.docx', 'section 3')
    A.note('read', 'knowledge', kn, 'part 1')
    A.note('read', 'memory', mem, 'compared')
    A.note('read', 'memory', mem, 'compared again')
    A.note('wrote', 'memory', mem, 'suggested replacement')
    A.note('read', 'memory', gone, 'compared')
    A.note('read', 'organisation', 'Acme Council', '')
    return {'status': 'complete', 'checked': 1}


fake_run()
with s.db() as c: c.execute('DELETE FROM records WHERE id=?', (gone,))
d = cl.get('/admin/api/agents/temple-org-research/touched', headers=H).json()
g = {x['key']: x for x in d['groups']}
t('items are grouped by source, web first', [x['key'] for x in d['groups']][:2] == ['web', 'library'] and {'knowledge', 'memories', 'organisations'} <= set(g))
w = next(i for i in g['web']['items'] if i['target_id'] == URL)
t('a web page shows its full URL as a link', w['location'] == URL and w['href'] == URL and w['target_name'] == 'www.example.gov.uk' and w['external'])
t('what happened is kept (cited or not)', 'Council news · cited' in w['details'])
doc = g['library']['items'][0]
t('a library document shows its file path inside the library', doc['target_name'] == 'Employee-Policy-Handbook-v1.0.docx'
  and doc['location'].startswith(str(L.ROOT)) and doc['location'].endswith('Employee-Policy-Handbook-v1.0.docx') and 'section 3' in doc['details'])
k = g['knowledge']['items'][0]
t('knowledge shows its name, label, status and a link to it', k['target_name'] == 'Travel guidance' and k['label'] == 'internal'
  and k['status'] == 'active' and k['href'].startswith('/admin/knowledge?') and 'Travel%20guidance' in k['href'] and k['location'] == 'Travel team')
m = next(i for i in g['memories']['items'] if i['target_id'] == mem)
t('one row per item, reads and writes counted together', m['read'] == 2 and m['wrote'] == 1 and m['kind'] == 'read and wrote' and len(m['details']) == 3)
t('memories link to the Memories page', m['href'].startswith('/admin/memories?status=all&q=Rail'))
t('an item no longer in Alice is shown as such', any(i['target_id'] == gone and i['status'] == 'deleted' for i in g['memories']['items']))
o = g['organisations']['items'][0]
t('organisations link to their profile', o['target_name'] == 'Acme Council' and o['href'] == '/admin/organisations?org=Acme%20Council')
t('group counts', g['memories']['read'] == 2 and g['memories']['wrote'] == 1 and g['web']['read'] == 2)
t('the period can be chosen', cl.get('/admin/api/agents/temple-org-research/touched?days=7', headers=H).json()['days'] == 7
  and cl.get('/admin/api/agents/temple-org-research/touched?days=400', headers=H).status_code == 422)

dm = cl.get('/admin/api/agents/temple-org-research/touched?demo=1', headers=H).json()
blob = json.dumps(dm)
t('demo mode hides URLs, paths and names', 'example.gov.uk' not in blob and 'Handbook' not in blob and 'Rail booking' not in blob and 'Acme' not in blob)

# the system map knows the sources outside Alice
L_ = cl.get('/admin/api/agents', headers=H).json()['agents']
hr = next(a for a in L_ if a['id'] == 'alice-assistants')
t('the assistants agent reads the document library', any(x['key'] == 'documents' for x in hr['anatomy_live']['data']))
page = cl.get('/admin/agents').text
t('the map draws the outside sources and the tab groups by source', 'Outside Alice' in page and "['documents','Document library'" in page and 'dt-group' in page)
t('documents is an allowed data source when editing an agent',
  cl.put('/admin/api/agents/temple-meeting', headers=H, json={'anatomy': {'data': ['input', 'documents']}}).status_code == 200)
t('Memories and Knowledge accept a search link', "params.get('q')" in cl.get('/admin/memories').text and "KQ.get('q')" in cl.get('/admin/knowledge').text)
