"""Proposal templates folder: choose where a writer's templates live, list only the Word documents there, and add a template
from the proposal page into that folder (never anywhere else, never over another file). Fictional files only."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, shutil, tempfile
from pathlib import Path
import substrate_store as s
s.init()
import doc_library as L, assistants as AS, proposals as P, proposal_starter as PS
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

FIX = Path(__file__).parent / 'fixtures' / 'proposal_template.docx'
root = Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents'
L.ROOT = root.resolve()
L.add_source('SharePoint', 'sharepoint', 'SharePoint: Bids site')
(root / 'SharePoint' / 'Proposal Templates').mkdir()
(root / 'SharePoint' / 'Proposals').mkdir()
shutil.copy(FIX, root / 'SharePoint' / 'Proposal Templates' / 'Standard SoW.docx')
shutil.copy(FIX, root / 'SharePoint' / 'Proposals' / 'Old proposal for a fictional council.docx')
L.add_source('Policies', 'folder')
shutil.copy(FIX, root / 'Policies' / 'Handbook.docx')

aid = 'proposal-writer'
base = f'/assistant/{aid}'
h = {'origin': 'http://testserver'}

r = cl.get(base + '/templates').json()
t('with no folder set, every Word document in the sources is offered', r['folder'] == '' and len(r['templates']) == 3)
t('the folders to choose from include folders inside a source', 'SharePoint/Proposal Templates' in r['folders'])

r = cl.post(base + '/templates/folder', json={'folder': 'SharePoint/Proposal Templates'}, headers=h)
t('a templates folder is set', r.status_code == 200 and r.json()['folder'] == 'SharePoint/Proposal Templates')
t('only the templates in that folder are offered', [x['name'] for x in r.json()['templates']] == ['Standard SoW.docx'])
t('the setting is kept on the writer', AS.get(aid)['settings']['template_folder'] == 'SharePoint/Proposal Templates')
su = cl.get(base + '/setup').json()
t('the proposal page gets the folder, the folders and the filtered list', su['template_folder'] == 'SharePoint/Proposal Templates'
  and len(su['templates']) == 1 and su['folders'])

# a template dropped into the folder appears without anything else happening (Refresh)
shutil.copy(FIX, root / 'SharePoint' / 'Proposal Templates' / 'RFP response 2026.docx')
r = cl.get(base + '/templates').json()
t('a new file in the folder shows up on refresh', sorted(x['name'] for x in r['templates']) == ['RFP response 2026.docx', 'Standard SoW.docx'])

for bad in ['../outside', 'Nowhere', '/etc', 'SharePoint/../../x']:
    rr = cl.post(base + '/templates/folder', json={'folder': bad}, headers=h)
    t(f'refused folder: {bad}', rr.status_code == 400)

# add a template from the page
data = base64.b64encode(FIX.read_bytes()).decode()
r = cl.post(base + '/templates', json={'name': 'Bid template v3.docx', 'data': data}, headers=h)
t('a template is added into the folder', r.status_code == 200 and r.json()['added'] == 'SharePoint/Proposal Templates/Bid template v3.docx'
  and (root / 'SharePoint' / 'Proposal Templates' / 'Bid template v3.docx').is_file())
r = cl.post(base + '/templates', json={'name': 'Bid template v3.docx', 'data': data}, headers=h)
t('never overwrites: a second copy gets its own name', r.status_code == 200 and r.json()['added'].endswith('Bid template v3 (2).docx'))
rr = cl.post(base + '/templates', json={'name': 'notes.txt', 'data': base64.b64encode(b'hello').decode()}, headers=h)
t('only Word documents', rr.status_code == 400 and '.docx' in rr.json()['detail'])
rr = cl.post(base + '/templates', json={'name': 'broken.docx', 'data': base64.b64encode(b'not a word file').decode()}, headers=h)
t('a file that is not really a Word document is refused', rr.status_code == 400)
rr = cl.post(base + '/templates', json={'name': '../../escape.docx', 'data': data}, headers=h)
t('a file name cannot leave the folder', rr.status_code == 200 and rr.json()['added'].startswith('SharePoint/Proposal Templates/')
  and not (root.parent / 'escape.docx').exists())
rr = cl.post(base + '/templates', json={'name': 'x.docx', 'data': data}, headers={'origin': 'https://elsewhere.example'})
t('cross-site uploads are refused', rr.status_code == 403)

# the outline works for a template picked from the folder
o = cl.get(base + '/outline', params={'template': 'SharePoint/Proposal Templates/Bid template v3.docx'})
t('an added template gives its sections', o.status_code == 200 and len(o.json()['sections']) >= 9)

# saving the writer on the Assistants page keeps the folder
a = AS.get(aid)
r = cl.put('/admin/api/assistants/' + aid, headers=H, json={'name': a['name'], 'provider': a['provider'], 'kind': 'proposal',
                                                            'settings': dict(a['settings'])})
t('saving the writer elsewhere keeps the templates folder', r.status_code == 200 and r.json()['settings']['template_folder'] == 'SharePoint/Proposal Templates')

# Parker offers only the folder's templates
tpls, paths, refs, _ = PS._offer('', aid)
t('Parker offers only the templates in the folder', tpls and all(x['path'].replace('\\', '/').startswith('SharePoint/Proposal Templates/') for x in tpls))

# a folder that has gone is said plainly
shutil.rmtree(root / 'SharePoint' / 'Proposal Templates')
r = cl.get(base + '/templates').json()
t('a folder that has gone is reported, not silently widened', r['folder_missing'] and r['templates'] == [])
rr = cl.post(base + '/templates', json={'name': 'x.docx', 'data': data}, headers=h)
t('nothing is added to a folder that has gone', rr.status_code == 400)
r = cl.post(base + '/templates/folder', json={'folder': ''}, headers=h).json()
t('back to every document source', r['folder'] == '' and len(r['templates']) == 2)

page = cl.get('/assistant/' + aid).text
t('the proposal page has the folder picker and Add a template', 'id="tplfold"' in page and 'id="tpl-file"' in page and 'Add a template' in page)
