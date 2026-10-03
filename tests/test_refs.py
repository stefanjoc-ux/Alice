"""Reference numbers: M- memories, D- decisions, K- knowledge; backfill in created order; never reused; lookups."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import json, uuid
import substrate_store as s, temple, knowledge as K
temple.save_settings(False, 'openai')
def t(label, cond): print(('PASS ' if cond else 'FAIL ') + label)
import temple_categorise as TC, clients as _C
TC.schedule = lambda ids: None; _C.schedule_tagging = lambda *a, **k: None; K.schedule_background = lambda *a, **k: None

import refs, app, mcp_server as M
# items that exist before references are switched on (as on your machine today): made, then their numbers wiped
old = [s.propose(t_, c_, 'Stefan said so')['id'] for t_, c_ in [('Dog name', 'The dog is called Lexi'), ('Bee hives', 'Keeps four bee colonies at home'), ('Carport size', 'The larch carport is six by six metres')]]
oldk = K.create('note', 'Old note', 'An older knowledge note with enough text in it.', 'Written by you', 'you')['id']
with s.db() as c:     # make the created order unambiguous
    for n, rid in enumerate(old): c.execute('UPDATE records SET created_at=? WHERE id=?', (f'2026-01-0{n + 1}T00:00:00+00:00', rid))

with s.db() as c:
    c.execute('DELETE FROM item_refs'); c.execute('UPDATE ref_counters SET next=1')   # throwaway test database only
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
refs.ensure()
got = refs.of('record', old)
t('existing memories numbered in the order they were created', [got[i] for i in old] == ['M-0001', 'M-0002', 'M-0003'])
t('existing knowledge numbered', refs.of('file', [oldk])[oldk] == 'K-0001')

# new items are numbered as they are created
r = s.propose('Prefers Teams', 'Stefan prefers Teams over email for quick questions', 'Stefan said so')
t('a new memory gets the next M number straight away', r.get('ref') == 'M-0004')
d = s.propose_decision(title='Carport roof', decision='Use clear polycarbonate sheets with a 5 degree fall', source='Stefan said so',
                       rationale='Light', options=['EPDM', 'Polycarbonate'])
t('a decision gets a D number, not an M number', d.get('ref') == 'D-0001')
k = K.create('note', 'New note', 'A new knowledge note with enough text to save.', 'Written by you', 'you', status='draft')
t('a knowledge draft gets a K number', k.get('ref') == 'K-0002')
s.review(r['id'], 'rejected')
r2 = s.propose('Another fact', 'Another fact that is long enough to keep', 'Stefan said so')
t('numbers are never reused (a rejected memory keeps M-0004)', r2['ref'] == 'M-0005' and refs.of('record', [r['id']])[r['id']] == 'M-0004')
t('references are unique', len(set(refs.of('record', old + [r['id'], r2['id'], d['id']]).values())) == 6)

# items inserted directly (Temple capture, imports) are numbered on the next listing
rid = uuid.uuid4().hex
with s.db() as c:
    c.execute("INSERT INTO records(id,title,content,source,status,created_at) VALUES (?,?,?,?,?,?)",
              (rid, 'Captured', 'Captured directly by another path', 'Temple', 'proposed', '2026-01-01T00:00:00+00:00'))
cl.get('/admin/api/memories?status=all')
t('directly inserted item numbered on the next listing', refs.of('record', [rid]).get(rid) == 'M-0006')
t('ensure is idempotent', refs.ensure() == 0)

# parsing and lookup
t('parse is forgiving', refs.parse('m42') == 'M-0042' and refs.parse(' D-7 ') == 'D-0007' and refs.parse('K-0001') == 'K-0001')
t('parse ignores ordinary words', refs.parse('Mark') == '' and refs.parse('M-') == '' and refs.parse('2024') == '')
t('find', refs.find('d1') == ('record', d['id']) and refs.find('K-1') == ('file', oldk) and refs.find('M-9999') == (None, None))

# Memories page: refs shown and searchable
x = cl.get('/admin/api/memories?status=all').json()
t('Memories rows carry their reference', {row['ref'] for row in x['records']} >= {'M-0001', 'D-0001', 'M-0004'})
x = cl.get('/admin/api/memories?status=all&query=D-0001').json()
t('search by reference finds that one item', [row['id'] for row in x['records']] == [d['id']])
x = cl.get('/admin/api/memories?status=all&query=K-0001').json()
t('a knowledge reference finds no memory', x['records'] == [])
x = cl.get('/admin/api/knowledge?status=all&query=k2').json()
t('Knowledge search by reference', [i['id'] for i in x['items']] == [k['id']] and x['items'][0]['ref'] == 'K-0002')
t('Knowledge rows carry their reference', all(i.get('ref') for i in cl.get('/admin/api/knowledge?status=all').json()['items']))

# connector
s.review(old[0], 'approved'); s.review(d['id'], 'approved')
res = M.search_records('M-0001')
t('search_records by reference', [x['id'] for x in res['records']] == [old[0]] and res['records'][0]['ref'] == 'M-0001')
t('search_records results carry refs', all(x.get('ref') for x in M.search_records('')['records']))
t('search_records: an unapproved item is not returned by reference', M.search_records('M-0005')['records'] == [])
t('list_files carries refs', all(f.get('ref') for f in M.list_files()['files']))
t('read_file accepts a K reference', M.read_file('K-0001')['file_id'] == oldk)
t('search_files results carry refs', M.search_files('older knowledge')['matches'][0]['ref'] == 'K-0001')
