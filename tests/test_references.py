"""Reference documents for proposals: pick from the sources, upload with suggestions, summary drafts, rules on the way in."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, shutil, tempfile, time
from pathlib import Path
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import knowledge as K, doc_library as L, organisations as O, clients as C, agents as A, documents as D, references as RF, proposals as P
import anthropic
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

root = Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents'
L.ROOT = root.resolve()
L.add_source('SharePoint', 'sharepoint', 'SharePoint Online')
O.create('Northshire Council', 'council', client=True, aliases=['NSC'])
O.create('Southvale Council', 'council', client=True)
GUIDE = ('# Microsoft Success Guide for Fabric adoption\n\n## 1 Envision\nAgree business outcomes, executive sponsorship and a success plan '
         'before any build. Measure adoption with usage telemetry.\n\n## 2 Onboard\nStand up the Fabric capacity, workspaces and governance '
         'with Purview sensitivity labels and data loss prevention in place first.\n\n## 3 Drive value\nRun champions, office hours and '
         'quarterly business reviews against the success plan. ' + 'Adoption improves when people see value early. ' * 10)
guide = D.get(D.create('docx', 'Fabric success guide', GUIDE)['id'])['data']
b64 = lambda raw: base64.b64encode(raw).decode()

calls = []
class Msgs:
    def create(self, **kw):
        calls.append(kw)
        u = NS(model_dump=lambda: {'input_tokens': 1000, 'output_tokens': 300})
        sysm = kw['system']
        if sysm.startswith('Summarise this reference document'):
            txt = json.dumps({'summary': 'Microsoft guidance on Fabric adoption in three stages: envision, onboard and drive value, with governance first.',
                              'key_points': ['Success plan before build', 'Purview labels and DLP first', 'Champions and reviews'], 'use_for': 'Fabric adoption proposals.'})
        elif sysm.startswith('You are the proposal writer'):
            want = [ln[2:].split(' [KEEP]')[0] for ln in kw['messages'][0]['content'].split('SECTIONS\n')[1].split('\n\nRATE CARD')[0].split('\n') if ln.startswith('- ')]
            txt = json.dumps({'sections': [{'title': x, 'body': f'{x}: a structured adoption approach for the council with governance first and clear outcomes.'} for x in want],
                              'resource_plan': [], 'gaps': []})
        else:
            txt = json.dumps({'verdict': 'client_ready', 'score': 90, 'summary': 'Fine.', 'requirements': [{'requirement': 'Adoption', 'status': 'met', 'where': 'Approach'}], 'issues': []})
        return NS(content=[NS(type='text', text=txt)], usage=u)
class Anth:
    def __init__(s_, **k): s_.messages = Msgs()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
anthropic.Anthropic = Anth

# ---------------- inspect: suggestions, nothing saved ----------------
r = cl.post('/assistant/proposal-writer/references/inspect', json={'name': 'Fabric-Success-Guide.docx', 'data': b64(guide)})
x = r.json()
t('an upload is read and nothing is saved yet', r.status_code == 200 and x['token'] and not any(root.rglob('*.docx')))
t('a document that names no client is suggested as General', x['tag'] == 'general' and 'shared' in x['reason'])
t('it suggests a References folder in SharePoint and a title', x['folder'] == 'SharePoint' and x['new_folder'] == 'References' and x['title'] == 'Fabric success guide')
nsc = D.get(D.create('docx', 'NSC notes', '# Northshire Council discovery notes\n\n' + 'Northshire Council wants a Fabric baseline. ' * 20)['id'])['data']
y = cl.post('/assistant/proposal-writer/references/inspect', json={'name': 'nsc.docx', 'data': b64(nsc)}).json()
t('a document that names a client is suggested for that client only', y['tag'] == 'client' and y['client'] == 'Northshire Council')
both = D.get(D.create('docx', 'Both', '# Comparison\n\n' + 'Northshire Council and Southvale Council both run Fabric pilots. ' * 10)['id'])['data']
z = cl.post('/assistant/proposal-writer/references/inspect', json={'name': 'both.docx', 'data': b64(both), 'organisation': 'Southvale Council'}).json()
t('several clients named: warned, kept to one (the proposal\'s client)', z['tag'] == 'client' and z['client'] == 'Southvale Council' and 'several clients' in z['reason'])
bad = lambda name, raw: cl.post('/assistant/proposal-writer/references/inspect', json={'name': name, 'data': b64(raw)})
t('secrets are refused before anything is saved', bad('k.txt', ('Our key is sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD. ' + 'x ' * 200).encode()).status_code == 400)
t('protectively marked documents are refused', bad('m.txt', ('OFFICIAL-SENSITIVE\n' + 'Operational detail. ' * 30).encode()).status_code == 400)
t('files with almost no text are refused', bad('s.txt', b'hello').status_code == 400)
t('other file types are refused', bad('x.exe', b'MZ' + b'0' * 500).status_code == 400)
t('cross-origin uploads are refused', cl.post('/assistant/proposal-writer/references/inspect', headers={'origin': 'http://evil.example'},
                                              json={'name': 'a.txt', 'data': b64(b'x' * 300)}).status_code == 403)
t('the HR assistant has no reference uploads', cl.get('/assistant/hr-policy/references').status_code == 404)

# ---------------- save and summarise ----------------
def pw_setting(**kw):
    with s.db() as c:
        st = json.loads(c.execute("SELECT settings FROM assistants WHERE id='proposal-writer'").fetchone()[0] or '{}')
        st.update(kw)
        c.execute("UPDATE assistants SET settings=? WHERE id='proposal-writer'", (json.dumps(st),))
pw_setting(auto_approve_references=False)        # these checks follow the draft path; auto-approval is checked further down
save = lambda **k: cl.post('/assistant/proposal-writer/references', json={'token': x['token'], 'folder': 'SharePoint', **k})
t('a folder outside the document sources is refused', save(folder='../..').status_code == 400 and save(new_folder='../escape').status_code == 400)
r = save(new_folder='References', title='Microsoft Fabric success guide', tag='general')
g = r.json()
saved = root / 'SharePoint' / 'References' / 'Fabric-Success-Guide.docx'
t('saved into the chosen folder in the document source', r.status_code == 200 and saved.is_file() and saved.read_bytes() == guide and g['path'].replace('\\', '/') == 'SharePoint/References/Fabric-Success-Guide.docx')
km = K.meta([g['knowledge_id']])[g['knowledge_id']]
with s.db() as c: txt = c.execute('SELECT text FROM files WHERE id=?', (g['knowledge_id'],)).fetchone()[0]
t('the summary is a knowledge DRAFT pointing to the document', km['status'] == 'draft' and 'full document: SharePoint' in km['source'] and 'Summary only' in txt and 'Champions and reviews' in txt)
t('General: not tagged to any client', not C.client_of('file', g['knowledge_id']))
with s.db() as c: t('the document itself is not stored in Alice', not c.execute("SELECT 1 FROM files WHERE name LIKE 'Fabric-Success-Guide%'").fetchone())
t('the token is used once', save().status_code == 400)
t('the summariser ran as a tracked agent', A.runs(RF.SUMMARISER)['runs'] and any(i['target_type'] == 'knowledge' for i in A.touched_items(RF.SUMMARISER)))
yy = cl.post('/assistant/proposal-writer/references', json={'token': y['token'], 'folder': 'SharePoint', 'tag': 'client', 'client': 'Northshire Council'}).json()
t('a client reference is tagged to that client', C.client_of('file', yy['knowledge_id']) == 'Northshire Council')
t('an unknown client is refused', cl.post('/assistant/proposal-writer/references', json={'token': z['token'], 'folder': 'SharePoint', 'tag': 'client', 'client': 'Nobody'}).status_code == 400)
docs = {d['name']: d for d in cl.get('/assistant/proposal-writer/references').json()['documents']}
t('the list shows each document, its summary status and client', docs['Fabric-Success-Guide.docx']['summary'] == 'draft' and docs['nsc.docx']['clients'] == ['Northshire Council'])
t('folders to save to are listed', any(f['path'] == 'SharePoint/References' for f in cl.get('/assistant/proposal-writer/references').json()['folders']))

# ---------------- the writer uses them, under the rules ----------------
def wait(pid):
    for _ in range(200):
        p = cl.get(f'/assistant/proposal-writer/proposals/{pid}').json()
        if p['status'] != 'running': return p
        time.sleep(0.1)
    return p
brief = 'Southvale Council wants an adoption programme for Microsoft Fabric with governance first, champions and success measures over six months.'
calls.clear()
p = wait(cl.post('/assistant/proposal-writer/proposals', json={'title': 'Fabric adoption', 'organisation': 'Southvale Council', 'brief': brief,
       'sections': [{'title': 'Approach'}], 'rate_card': [], 'references': [g['path'], yy['path']]}).json()['id'])
w = [c for c in calls if c['system'].startswith('You are the proposal writer')][0]['messages'][0]['content']
t('the writer gets the reference passages relevant to the brief', p['status'] == 'done' and 'REFERENCE DOCUMENTS' in w and 'champions' in w.lower() and 'Fabric-Success-Guide.docx' in w)
t('another client\'s reference is left out, and you are told', 'Northshire' not in w and any('another client' in x for x in p['context']['used']['references_skipped']))
K.review([g['knowledge_id']], 'approved')
calls.clear()
p = wait(cl.post('/assistant/proposal-writer/proposals', json={'title': 'Fabric adoption 2', 'organisation': 'Southvale Council', 'brief': brief,
       'sections': [{'title': 'Approach'}], 'rate_card': [], 'references': [g['path']]}).json()['id'])
w = [c for c in calls if c['system'].startswith('You are the proposal writer')][0]['messages'][0]['content']
t('once approved, the summary is given too', 'Approved summary:' in w and 'envision, onboard and drive value' in w)
t('the references used are listed on the result', p['context']['used']['references'] == ['Fabric-Success-Guide.docx'])
t('the page offers reference documents', 'Reference documents' in cl.get('/assistant/proposal-writer').text and 'ref-file' in cl.get('/assistant/proposal-writer').text)

# ---------------- auto-approval (the owner's setting, on by default) ----------------
pw_setting(auto_approve_references=True)
mg = D.get(D.create('docx', 'Copilot guide', '# Microsoft Copilot adoption guide\n\n' + 'Copilot adoption works best with champions, scenarios and measured value. ' * 15)['id'])['data']
q = cl.post('/assistant/proposal-writer/references/inspect', json={'name': 'Copilot-Guide.docx', 'data': b64(mg)}).json()
ra = cl.post('/assistant/proposal-writer/references', json={'token': q['token'], 'folder': 'SharePoint/References', 'tag': 'general'}).json()
t('with auto-approval on, the summary is active straight away', ra['summary'] == 'approved' and K.meta([ra['knowledge_id']])[ra['knowledge_id']]['status'] == 'active')
with s.db() as c:
    rows = [dict(r) for r in c.execute("SELECT action,target,detail,actor FROM activity WHERE target=? ORDER BY id", (ra['knowledge_id'],))]
t('the auto-approval is logged for Temple', any(r['action'] == 'reference_auto_approved' and 'approved automatically' in r['detail'] for r in rows))
import activity_log as AL
t('the activity log names it', 'reference_auto_approved' in AL.LABELS)
aa = cl.get('/admin/api/temple/auto-approved').json()
t('the Temple page lists auto-approved summaries', any(i['target'] == ra['knowledge_id'] for i in aa['items']) and aa['days'] == 30)
docs = {d['name']: d for d in cl.get('/assistant/proposal-writer/references').json()['documents']}
t('the list shows it as approved', docs['Copilot-Guide.docx']['summary'] == 'approved')
pw_setting(auto_approve_references=False)
mg2 = D.get(D.create('docx', 'Purview guide', '# Microsoft Purview deployment guide\n\n' + 'Purview labelling starts with a small set of labels and clear owners. ' * 15)['id'])['data']
q2 = cl.post('/assistant/proposal-writer/references/inspect', json={'name': 'Purview-Guide.docx', 'data': b64(mg2)}).json()
rb = cl.post('/assistant/proposal-writer/references', json={'token': q2['token'], 'folder': 'SharePoint/References', 'tag': 'general'}).json()
t('with auto-approval off, it waits as a draft', rb['summary'] == 'draft' and K.meta([rb['knowledge_id']])[rb['knowledge_id']]['status'] == 'draft'
  and not any(i['target'] == rb['knowledge_id'] for i in cl.get('/admin/api/temple/auto-approved').json()['items']))
page = cl.get('/assistant/proposal-writer').text
t('the page shows only the chosen documents until you browse', 'ref-browse' in page and 'No reference documents chosen' in page)
t('the Temple page has the auto-approved panel', 't-auto' in cl.get('/admin/temple').text)
t('the Assistants page has the auto-approve switch', 'auto_approve_references' in cl.get('/admin/assistants').text)
