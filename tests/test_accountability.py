"""Accountability and Purview labels: owners, who approved and why, audit lines for Log Analytics, Purview sensitivity labels."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, io, json, logging, os, zipfile
import substrate_store as s
s.init()
import knowledge as K, purview_labels as P, activity_log, mcp_server as M
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}


def last_activity(action):
    with s.db() as c:
        r = c.execute('SELECT * FROM activity WHERE action=? ORDER BY id DESC LIMIT 1', (action,)).fetchone()
    return dict(r) if r else {}


# ---------------- owners ----------------
a = s.propose('Teams Phone decision', 'We are moving the service desk to Teams Phone in 2027.', 'Stefan in a test')['id']
b = s.propose('Backup policy', 'Backups are kept for 35 days in the primary region.', 'Stefan in a test')['id']
r = cl.post('/admin/api/memories/owner', headers=H, json={'ids': [a], 'owner': 'Morven Hay'})
t('a memory can be given an owner', r.status_code == 200 and r.json()['updated'] == 1)
d = cl.get('/admin/api/memories?status=proposed', headers=H).json()
row = next(x for x in d['records'] if x['id'] == a)
t('the owner shows on the memory and in the owner list', row['owner'] == 'Morven Hay' and d['owners'] == ['Morven Hay'])
t('filter by owner', [x['id'] for x in cl.get('/admin/api/memories?status=proposed&owner=Morven%20Hay', headers=H).json()['records']] == [a])
t('filter for no owner', [x['id'] for x in cl.get('/admin/api/memories?status=proposed&owner=__none__', headers=H).json()['records']] == [b])
t('an owner must be a name', cl.post('/admin/api/memories/owner', headers=H, json={'ids': [a], 'owner': 'm.hay@example.com'}).status_code == 400)
t('setting an owner is logged', last_activity('owner_set').get('detail') == 'Morven Hay')

fid = K.create('note', 'Incident runbook', 'Steps for a major incident: call the duty manager, open a bridge, log the timeline.', 'Written by you', 'you')['id']
r = cl.put('/admin/api/knowledge', headers=H, json={'ids': [fid], 'owner': 'Callum Reid'})
t('knowledge can be given an owner', r.status_code == 200)
kd = cl.get('/admin/api/knowledge?status=all&owner=Callum%20Reid', headers=H).json()
t('knowledge owner filter and owner list', [x['id'] for x in kd['items']] == [fid] and set(kd['owners']) == {'Morven Hay', 'Callum Reid'})

# ---------------- who approved and why ----------------
os.environ['ALICE_OWNER_NAME'] = 'Stefan Test'
r = cl.post(f'/admin/api/records/{a}/review', headers=H, json={'decision': 'approved'})
act = last_activity('record_approved')
t('an approval records who approved it', r.status_code == 200 and act.get('actor') == 'Stefan Test' and act.get('note') == '')
r = cl.post('/admin/api/memories/review', headers=H, json={'ids': [b], 'decision': 'rejected', 'note': 'Superseded by the new retention standard'})
act = last_activity('record_rejected')
t('a rejection records the reason given', act.get('actor') == 'Stefan Test' and act.get('note') == 'Superseded by the new retention standard')
d = cl.get('/admin/api/memories?status=all', headers=H).json()
dec = {x['id']: x['decided'] for x in d['records']}
t('memories show who decided, when and why', dec[a]['actor'] == 'Stefan Test' and dec[b]['note'].startswith('Superseded') and dec[b]['action'] == 'record_rejected')
t('the note only applies to that decision', last_activity('owner_set').get('note') == '')

draft = K.create('note', 'Draft supplier summary', 'Summary of the three shortlisted suppliers and their contract terms.', 'Model', 'model', status='draft')['id']
cl.post('/admin/api/knowledge/review', headers=H, json={'ids': [draft], 'decision': 'approved', 'note': 'Checked against the tender pack'})
item = next(x for x in cl.get('/admin/api/knowledge?status=all', headers=H).json()['items'] if x['id'] == draft)
t('knowledge approvals record who and why', item['decided']['actor'] == 'Stefan Test' and item['decided']['note'] == 'Checked against the tender pack')

r = cl.post(f'/admin/api/memories/owner', headers={**H, 'x-ms-client-principal-name': 'spoof@example.com'}, json={'ids': [a], 'owner': 'Isla Grant'})
t('a sign-in header is ignored unless Alice runs behind Entra', last_activity('owner_set').get('actor') == 'Stefan Test')
os.environ['ALICE_TRUST_EASYAUTH'] = '1'
cl.post(f'/admin/api/memories/owner', headers={**H, 'x-ms-client-principal-name': 'isla.grant@contoso.example'}, json={'ids': [a], 'owner': 'Isla Grant'})
t('behind Entra the signed-in person is recorded', last_activity('owner_set').get('actor') == 'isla.grant@contoso.example')
os.environ.pop('ALICE_TRUST_EASYAUTH')
csv_text = cl.get('/admin/api/activity-log.csv?period=all', headers=H).text
t('the activity export includes who and the reason', 'By,Reason given' in csv_text and 'Superseded by the new retention standard' in csv_text)

lines = []
class Grab(logging.Handler):
    def emit(self, rec): lines.append(rec.getMessage())
logging.getLogger('alice.audit').addHandler(Grab()); logging.getLogger('alice.audit').setLevel(logging.INFO)
os.environ['ALICE_AUDIT_STDOUT'] = '1'
cl.post('/admin/api/memories/owner', headers=H, json={'ids': [a], 'owner': 'Ewan Mackay'})
os.environ.pop('ALICE_AUDIT_STDOUT')
cl.post('/admin/api/memories/owner', headers=H, json={'ids': [a], 'owner': 'Morven Hay'})
ev = [e for e in (json.loads(x) for x in lines) if e['action'] == 'owner_set']     # background Temple jobs may log too
t('with ALICE_AUDIT_STDOUT=1 each activity row is one JSON line (for Log Analytics)', len(ev) == 1 and ev[0]['detail'] == 'Ewan Mackay' and ev[0]['actor'] == 'Stefan Test' and ev[0]['type'] == 'alice.audit')

# owners never reach a model
with s.db() as c: c.execute("UPDATE records SET status='approved' WHERE id=?", (b,))
out = json.dumps(M.search_records(query=''))
files_out = json.dumps(M.list_files())
t('owner names are never returned to a model', 'Morven' not in out and 'Callum' not in files_out)


# ---------------- Purview sensitivity labels ----------------
G1, G2, G3, G4 = ('11111111-2222-3333-4444-555555555555', 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                  '99999999-8888-7777-6666-555555555555', '12345678-1234-1234-1234-123456789abc')


def docx(text, guid=None, name=None, labelinfo=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr('word/document.xml', '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
        if guid and not labelinfo:
            props = [('Enabled', 'true'), ('SetDate', '2026-09-01T10:00:00Z'), ('Method', 'Standard'), ('SiteId', '0f0f0f0f-0000-0000-0000-000000000000')]
            if name: props.append(('Name', name))
            body = ''.join(f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="{i + 2}" name="MSIP_Label_{guid}_{k}"><vt:lpwstr>{v}</vt:lpwstr></property>'
                           for i, (k, v) in enumerate(props))
            z.writestr('docProps/custom.xml', '<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
                       'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">' + body + '</Properties>')
        if guid and labelinfo:
            z.writestr('docMetadata/LabelInfo.xml', '<?xml version="1.0"?><clbl:labelList xmlns:clbl="http://schemas.microsoft.com/office/2020/mipLabelMetadata">'
                       f'<clbl:label id="{{{guid}}}" enabled="1" method="Standard" siteId="{{0f0f0f0f-0000-0000-0000-000000000000}}" removed="0"/></clbl:labelList>')
    return buf.getvalue()


def upload(name, raw, chat_id=''):
    return cl.post('/files', json={'name': name, 'data': base64.b64encode(raw).decode(), 'chat_id': chat_id})


t('reads a label from an Office file', P.read_label('x.docx', docx('hello', G1, 'Confidential')) == {'id': G1, 'name': 'Confidential'})
t('reads a label id from LabelInfo.xml', P.read_label('x.docx', docx('hello', G2, labelinfo=True)) == {'id': G2, 'name': ''})
t('no label, nothing read', P.read_label('x.docx', docx('hello')) is None)
r = upload('plain.docx', docx('A plain document about service desk hours.'))
t('an unlabelled file is unaffected', r.status_code == 200 and 'purview' not in r.json() and K.meta([r.json()['id']])[r.json()['id']]['label'] == 'general')

r = upload('confidential.docx', docx('Contract summary for the managed service renewal.', G1, 'Confidential'))
fid1 = r.json()['id']
m = K.meta([fid1])[fid1]
t('an unmapped label is treated as Internal and recorded', r.status_code == 200 and m['label'] == 'internal' and m['purview_label'] == 'Confidential' and 'not mapped' in r.json()['purview'])
labels = cl.get('/admin/api/purview-labels', headers=H).json()['labels']
t('the label appears for mapping with its file count', any(l['label_id'] == G1 and l['name'] == 'Confidential' and l['files'] == 1 and l['action'] == '' for l in labels))
t('a new label is logged', last_activity('purview_label_seen').get('target') == G1)

cl.put('/admin/api/purview-labels', headers=H, json={'label_id': G1, 'action': 'local'})
r = upload('confidential2.docx', docx('Second contract summary for the network renewal.', G1, 'Confidential'))
t('a mapped label applies its Alice label', K.meta([r.json()['id']])[r.json()['id']]['label'] == 'local')
cl.put('/admin/api/purview-labels', headers=H, json={'label_id': G1, 'action': 'general'})
cid = cl.post('/chats').json()['id']
import clients as C
C.create_client('Example Council', ['EC']); C.set_chat_client(cid, 'Example Council')
r = upload('client.docx', docx('Example Council network diagram notes for the core switches.', G1, 'Confidential'), cid)
t('a mapping never lowers what Alice already set (client chat stays Client-confidential)', K.meta([r.json()['id']])[r.json()['id']]['label'] == 'client')

cl.put('/admin/api/purview-labels', headers=H, json={'label_id': G2, 'action': 'block', 'name': 'Highly Confidential'})
r = upload('blocked.docx', docx('Board paper on the restructure.', G2, labelinfo=True))
t('a label mapped to Block is not saved', r.status_code == 400 and 'Highly Confidential' in r.text)
r = upload('marked.docx', docx('Operational notes for the next phase.', G3, 'OFFICIAL-SENSITIVE'))
t('an unmapped protective-marking label is blocked', r.status_code == 400 and 'OFFICIAL-SENSITIVE' in r.text)
t('blocks are logged as rule blocks', last_activity('rule_blocked').get('rule') == 'purview_labels')
t('mapping needs a real label id', cl.put('/admin/api/purview-labels', headers=H, json={'label_id': 'Confidential', 'action': 'internal'}).status_code == 400)

from pypdf import PdfWriter
w = PdfWriter(); w.add_blank_page(200, 200)
w.add_metadata({f'/MSIP_Label_{G4}_Enabled': 'true', f'/MSIP_Label_{G4}_Name': 'Internal Only'})
pb = io.BytesIO(); w.write(pb)
t('reads a label from a PDF', P.read_label('x.pdf', pb.getvalue()) == {'id': G4, 'name': 'Internal Only'})

page = cl.get('/admin/rules').text
t('the Rules page has the Purview label mapping', 'id="pv-list"' in page and 'id="pv-add"' in page)
t('Memories and Knowledge pages have owner filters', 'id="mem-owner"' in cl.get('/admin/memories').text and 'id="k-f-owner"' in cl.get('/admin/knowledge').text)
