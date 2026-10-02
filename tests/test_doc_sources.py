"""Document sources: the Documents folder, one folder per source standing in for SharePoint, Fabric or Power Platform."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, tempfile
from pathlib import Path
import substrate_store as s
s.init()
import knowledge as K, documents as D, doc_library as L, agents as A
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

root = Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents'
L.ROOT = root.resolve()
t('the default folder is Documents next to Alice', L.BASE.name and str(L.Path(L.BASE / 'Documents')).endswith('Documents'))
d = cl.get('/admin/api/document-sources', headers=H).json()
t('no folder yet: no sources, and the page says so', d['sources'] == [] and d['exists'] is False and set(d['kinds']) == {'folder', 'sharepoint', 'fabric', 'power_platform'})

r = cl.post('/admin/api/document-sources', headers=H, json={'name': 'HR Policies', 'type': 'sharepoint', 'simulates': 'SharePoint: HR site, Policies library'})
t('a source can be added: a folder with its settings', r.status_code == 200 and (root / 'HR Policies' / '_source.json').is_file()
  and r.json()['type_name'] == 'SharePoint library' and r.json()['simulated'] and r.json()['connector'] == 'Microsoft Graph')
for bad in ['../escape', 'a/b', '', 'x' * 61, '.hidden', 'HR Policies']:
    t(f'refused source name: {bad[:12]!r}', cl.post('/admin/api/document-sources', headers=H, json={'name': bad, 'type': 'folder'}).status_code in (400, 422))
t('unknown types refused', cl.post('/admin/api/document-sources', headers=H, json={'name': 'X', 'type': 'dropbox'}).status_code == 422)
cl.post('/admin/api/document-sources', headers=H, json={'name': 'Finance Lakehouse', 'type': 'fabric'})
t('nothing escaped the Documents folder', not (root.parent / 'escape').exists())
with s.db() as c:
    t('adding a source is logged', c.execute("SELECT 1 FROM activity WHERE action='document_source_added' AND target='HR Policies'").fetchone() is not None)

hb = D.get(D.create('docx', 'Handbook', '# Handbook\n\n## 1 Scope\nApplies to all staff.\n\n## 2 Leave\nTwenty five days.')['id'])['data']
(root / 'HR Policies' / 'Employee-Handbook.docx').write_bytes(hb)
(root / 'HR Policies' / 'Archive').mkdir(); (root / 'HR Policies' / 'Archive' / 'Old-Handbook.md').write_text('# Old\nOld text.')
(root / 'HR Policies' / '~$lock.docx').write_bytes(b'x'); (root / 'HR Policies' / 'notes.exe').write_bytes(b'x')
(root / 'Finance Lakehouse' / 'budget.csv').write_text('line,amount\nLicences,1200\n')
(root / 'loose.txt').write_text('A loose document.')
src = {x['id']: x for x in cl.get('/admin/api/document-sources', headers=H).json()['sources']}
t('every folder is a source; loose files show as Documents', set(src) == {'', 'HR Policies', 'Finance Lakehouse'} and src['HR Policies']['files'] == 2
  and src['Finance Lakehouse']['type_name'] == 'Microsoft Fabric (OneLake)' and src['']['files'] == 1)

K.create('note', 'Summary: Leave', 'Summary only. Twenty five days of leave.', 'Handbook, section 2 (full document: HR Policies\\Employee-Handbook.docx; not stored in Alice)', 'you')
K.create('note', 'Summary: Scope', 'Summary only. The handbook applies to all staff.', 'Handbook, section 1 (full document: Policy library\\Employee-Handbook.docx; not stored in Alice)', 'you', status='draft')
f = {x['name']: x for x in cl.get('/admin/api/document-sources/files?source=HR%20Policies', headers=H).json()['files']}
t('documents are listed, including subfolders, never lock files or other types', set(f) == {'Employee-Handbook.docx', 'Old-Handbook.md'})
t('each document shows how many summaries in Alice point to it', f['Employee-Handbook.docx']['summaries'] == 2 and f['Employee-Handbook.docx']['summaries_active'] == 1)
t('files of an unknown source: 404', cl.get('/admin/api/document-sources/files?source=..', headers=H).status_code == 404)

p = L.resolve('Policy library\\Employee-Handbook.docx')
t('older pointers to another folder still find the document by name', p and p.name == 'Employee-Handbook.docx')
(root / 'Finance Lakehouse' / 'Old-Handbook.md').write_text('# Duplicate')
t('…but not when two documents share the name', L.resolve('Elsewhere/Old-Handbook.md') is None)
t('a document says which source it is in', L.describe(p) == 'SharePoint library "HR Policies" (simulated by a folder)')
t('the reader reports the source with each extract', L.extracts([('HR Policies/Employee-Handbook.docx', '2', 'Leave')], 'leave', 'openai')[0][0]['where'].startswith('SharePoint library'))

@A.tracked('alice-assistants', trigger='test')
def fake():
    A.note('read', 'document', 'HR Policies\\Employee-Handbook.docx', 'section 2')
    return {'status': 'complete', 'checked': 1}
fake()
f = {x['name']: x for x in cl.get('/admin/api/document-sources/files?source=HR%20Policies', headers=H).json()['files']}
t('each document shows how often agents read it', f['Employee-Handbook.docx']['reads'] == 1)
dt = [i for g in cl.get('/admin/api/agents/alice-assistants/touched', headers=H).json()['groups'] if g['key'] == 'library' for i in g['items']]
t('Data touched names the source of each document', dt and dt[0]['where'].startswith('SharePoint library "HR Policies"') and dt[0]['location'].endswith('Employee-Handbook.docx'))

page = cl.get('/admin/documents').text
t('the Documents page is in the menu and explains the flow', 'href="/admin/documents"' in cl.get('/admin/knowledge').text and 'Document sources' in page and 'ds-list' in page)
t('the demo HR summaries point to the HR Policies source', json.loads((L.BASE / 'demo_content' / 'hr_policy_summaries.json').read_text(encoding='utf-8'))['location'].startswith('Documents\\HR Policies\\'))
