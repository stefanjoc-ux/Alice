"""Assistants answer from summaries first; only when those do not answer do they read the full document, on demand."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import io, json, tempfile, zipfile
from pathlib import Path
from types import SimpleNamespace as NS
import substrate_store as s
import agents as A_
s.init()
import knowledge as K, assistants as A, documents as D, doc_library as L
import openai
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

lib = Path(tempfile.mkdtemp(prefix='alice-library-')) / 'library'; lib.mkdir()
L.ROOT = lib.resolve()
HANDBOOK = '''# Employee Policy Handbook

## 1 Scope
This handbook applies to all employees. Agency workers, contractors and volunteers follow their own agreements, but the
dignity at work standards apply to everyone on site.

## 2 Annual leave
Full-time staff receive 25 days plus bank holidays. Up to 5 days may be carried over to 30 June.

### 2.1 Buying and selling leave
Staff may buy up to 5 extra days a year through salary sacrifice, applied for in the January window.

## 3 Sickness absence
Report sickness to your manager by 10am on the first day.
'''
data = D.get(D.create('docx', 'Employee Policy Handbook', HANDBOOK)['id'])['data']
(lib / 'Handbook.docx').write_bytes(data)

# the same handbook carrying a Purview label that is mapped to Block
G = '11111111-2222-3333-4444-555555555555'
buf = io.BytesIO()
with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, 'w') as zout:
    for n in zin.namelist(): zout.writestr(n, zin.read(n))
    zout.writestr('docProps/custom.xml', '<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
                  'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
                  f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="2" name="MSIP_Label_{G}_Enabled"><vt:lpwstr>true</vt:lpwstr></property>'
                  f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="3" name="MSIP_Label_{G}_Name"><vt:lpwstr>Restricted HR</vt:lpwstr></property></Properties>')
(lib / 'Labelled.docx').write_bytes(buf.getvalue())

# ---------------- the library reader ----------------
t('a pointer is read from the summary source', L.pointer({'source': 'Handbook v1, section 2 (full document: Policy library\\Handbook.docx; not stored in Alice)'})
  == ('Policy library\\Handbook.docx', '2'))
t('a pointer resolves inside the library, with or without the folder name', L.resolve('Handbook.docx') and L.resolve(f'{lib.name}\\Handbook.docx'))
outside = lib.parent / 'outside.txt'; outside.write_text('secret')
t('a pointer can never leave the library', L.resolve('../outside.txt') is None and L.resolve(str(outside)) is None and L.resolve('nope.docx') is None)
(lib / 'script.py').write_text('print(1)')
t('only document types are read', L.resolve('script.py') is None)
text = L._read(L.resolve('Handbook.docx'))[1]
sec2 = L.section(text, '2')
t('a numbered section is read to the next heading at its level', 'carried over' in sec2 and 'Buying and selling' in sec2 and 'Sickness' not in sec2)
t('a subsection reads on its own', 'salary sacrifice' in L.section(text, '2.1') and 'carried over' not in L.section(text, '2.1'))

# ---------------- the assistant ----------------
seen, replies = [], []
class R:
    def create(self, **kw):
        if 'You are HR test' not in (kw.get('instructions') or ''):     # background agents (Temple) are not the assistant
            return NS(output_text='{}', usage=NS(model_dump=lambda: {'input_tokens': 1, 'output_tokens': 1}))
        seen.append(kw)
        if replies == ['smart']:          # behaves like a model following the rules: summaries do not cover it, the document does
            out = 'Agency workers follow their own agreements [D1].' if 'DOCUMENT EXTRACTS' in kw['instructions'] else 'NOT_IN_SOURCES'
        else: out = replies.pop(0) if replies else 'Answer [S1].'
        return NS(output_text=out, usage=NS(model_dump=lambda: {'input_tokens': 500, 'output_tokens': 30}))
class O:
    def __init__(s_, **k): s_.responses = R()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
openai.OpenAI = O

s.create_category('HRX', 'test')
SRC = 'Employee Policy Handbook, section {} (full document: Policy library\\{}; not stored in Alice)'
leave = K.create('note', 'Summary: Annual leave', 'Summary only. 25 days plus bank holidays; up to 5 days carried over to 30 June.', SRC.format(2, 'Handbook.docx'), 'you', category='HRX')['id']
sick = K.create('note', 'Summary: Sickness absence', 'Summary only. Report sickness absence to your manager on the first day.', SRC.format(3, 'Handbook.docx'), 'you', category='HRX')['id']
a = cl.post('/admin/api/assistants', headers=H, json={'name': 'HR test', 'categories': ['HRX'], 'contact': 'HR'}).json()
t('document checks are on by default', a['allow_documents'] is True)
ask = lambda q: cl.post(f'/assistant/{a["id"]}/ask', json={'question': q}).json()

seen.clear(); replies[:] = ['You get 25 days plus bank holidays [S1].']
d = ask('How many days of annual leave do I get?')
t('summaries answer: one model call, no document read', len(seen) == 1 and 'SOURCES' in seen[0]['instructions'] and 'DOCUMENT EXTRACTS' not in seen[0]['instructions']
  and d['sources'] and d['sources'][0]['type'] == 'summary')
t('the model is told how to say the summaries do not answer', 'NOT_IN_SOURCES' in seen[0]['instructions'])

seen.clear(); replies[:] = ['NOT_IN_SOURCES', 'You can buy up to 5 extra days through salary sacrifice [D1].']
d = ask('Can I buy extra annual leave days?')
t('when the summaries do not answer, the full document is checked', len(seen) == 2 and 'DOCUMENT EXTRACTS' in seen[1]['instructions']
  and 'salary sacrifice' in seen[1]['instructions'] and d['reply'].startswith('You can buy'))
t('the pointed-to section is the one read', 'Up to 5 days may be carried over' in seen[1]['instructions'])
t('the answer cites the document and says it was read on demand', d['sources'][0]['type'] == 'document' and d['sources'][0]['name'] == 'Handbook.docx'
  and any('isn\u2019t in my policy summaries' in n and 'not stored' in n for n in d['notes']))
with s.db() as c:
    t('nothing from the document is stored in Alice', not c.execute("SELECT 1 FROM files WHERE text LIKE '%salary sacrifice%'").fetchone())
    t('the document read is logged as activity', c.execute("SELECT 1 FROM activity WHERE detail LIKE '%full document consulted%'").fetchone() is not None)

seen.clear(); replies[:] = ['smart']
d = ask('Does the handbook apply to agency workers?')
t('a question only the full document covers reaches it', len(seen) >= 1 and 'Agency workers, contractors' in seen[-1]['instructions'] and d['sources'][0]['type'] == 'document')

seen.clear(); replies[:] = ['NOT_IN_SOURCES', 'NOT_IN_SOURCES']
d = ask('What is the parking policy for annual leave days?')
t('not in the summaries or the document: the not-found reply', d['reply'].startswith('I could not find anything') and 'HR' in d['reply'] and not d['sources'])
t('the marker is never shown to staff', 'NOT_IN_SOURCES' not in d['reply'])

# labelled document: blocked by its Purview mapping
cl.put('/admin/api/purview-labels', headers=H, json={'label_id': G, 'action': 'block', 'name': 'Restricted HR'})
with s.db() as c: c.execute('UPDATE knowledge_meta SET source=? WHERE file_id=?', (SRC.format(3, 'Labelled.docx'), sick))
seen.clear(); replies[:] = ['NOT_IN_SOURCES', 'From the document [D1].']
d = ask('Who do I report sickness absence to and by what time?')
t('a document whose Purview label is blocked is never sent', seen and not any('Labelled.docx' in k['instructions'].split('DOCUMENT EXTRACTS (')[1] for k in seen if 'DOCUMENT EXTRACTS (' in k['instructions'])
  and not any(x.get('name') == 'Labelled.docx' for x in d['sources']))
import doc_library
ex, skipped = doc_library.extracts([('Labelled.docx', '3', 'x')], 'sickness', 'openai')
t('the reader says why it was skipped', not ex and any('Restricted HR' in x and 'blocked' in x for x in skipped))

# streamed: the person is told when the full document is being checked
cl.put(f'/admin/api/assistants/{a["id"]}', headers=H, json={'name': 'HR test', 'categories': ['HRX'], 'contact': 'HR', 'allow_documents': True})
with s.db() as c: c.execute('UPDATE knowledge_meta SET source=? WHERE file_id=?', (SRC.format(3, 'Handbook.docx'), sick))
seen.clear(); replies[:] = ['NOT_IN_SOURCES', 'You can buy up to 5 extra days [D1].']
r = cl.post(f'/assistant/{a["id"]}/ask', json={'question': 'Can I buy extra annual leave days?'}, headers={'Accept': 'application/x-ndjson'})
lines = [json.loads(x) for x in r.text.splitlines() if x.strip()]
t('streamed: first a notice that the full document is being checked, then the answer', r.headers['content-type'].startswith('application/x-ndjson')
  and lines[0].get('stage') == 'documents' and 'checking the full policy document' in lines[0]['message'] and lines[-1]['result']['reply'].startswith('You can buy'))
t('the document source is named in the answer', 'where' in lines[-1]['result']['sources'][0])
seen.clear(); replies[:] = ['You get 25 days [S1].']
lines = [json.loads(x) for x in cl.post(f'/assistant/{a["id"]}/ask', json={'question': 'How many days of annual leave do I get?'},
                                        headers={'Accept': 'application/x-ndjson'}).text.splitlines() if x.strip()]
t('streamed: no notice when the summaries answer', len(lines) == 1 and lines[0]['result']['sources'][0]['type'] == 'summary')
r = cl.post(f'/assistant/{a["id"]}/ask', json={'question': 'Here is my key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'}, headers={'Accept': 'application/x-ndjson'})
x = [json.loads(v) for v in r.text.splitlines() if v.strip()][-1]
t('streamed: blocked questions come back as an answer the page can show', x.get('result', {}).get('status') == 'blocked' or x.get('error', {}).get('status') == 400)

runs = [r for r in A_.runs('alice-assistants')['runs']]
t('every answer is a tracked agent run, with the document read and the model it went to',
  runs and any(i['target_type'] == 'document' and i['sent_to'] for i in A_.touched_items('alice-assistants')))
t('the staff page script parses the streamed lines', "buf.indexOf('\\n')" in cl.get(f'/assistant/{a["id"]}').text)

# switched off
cl.put(f'/admin/api/assistants/{a["id"]}', headers=H, json={'name': 'HR test', 'categories': ['HRX'], 'contact': 'HR', 'allow_documents': False})
seen.clear(); replies[:] = ['The summaries do not say; contact HR.']
d = ask('Can I buy extra annual leave days?')
t('with document checks off, only the summaries are used', len(seen) == 1 and 'NOT_IN_SOURCES' not in seen[0]['instructions'] and d['sources'][0]['type'] == 'summary')
t('the Assistants form offers the switch and the staff page shows document checks',
  'allow_documents' in cl.get('/admin/assistants').text and 'Full document checked' in cl.get(f'/assistant/{a["id"]}').text)
