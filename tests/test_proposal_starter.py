"""Start with Temple: a starter for the Proposal writer form, under the same rules as the writer, advisory only."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, shutil, tempfile
from pathlib import Path
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import knowledge as K, doc_library as L, organisations as O, clients as C, agents as A, documents as D, assistants as AS, temple
import proposal_starter as PS, activity_log as AL
import anthropic
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app)
b64 = lambda raw: base64.b64encode(raw).decode()

root = Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents'
L.ROOT = root.resolve()
L.add_source('SharePoint', 'sharepoint', 'SharePoint Online')
L.add_source('Proposal Templates', 'sharepoint', 'Bids site')
shutil.copy(Path(__file__).parent / 'fixtures' / 'proposal_template.docx', root / 'Proposal Templates' / 'Insight-template.docx')
(root / 'SharePoint' / 'References').mkdir(parents=True)
(root / 'SharePoint' / 'References' / 'Fabric-guide.docx').write_bytes(D.get(D.create('docx', 'Fabric guide', '# Fabric guide\n\n' + 'Governance first. ' * 40)['id'])['data'])
(root / 'SharePoint' / 'References' / 'Southvale-notes.docx').write_bytes(D.get(D.create('docx', 'SV', '# Southvale notes\n\n' + 'Southvale pilot. ' * 40)['id'])['data'])
O.create('Northshire Council', 'council', client=True, aliases=['NSC'])
O.create('Southvale Council', 'council', client=True)
f = O.propose_fact('Northshire Council', 'purpose', 'Northshire Council is moving its finance data to Microsoft Fabric in 2027.', 'Public web', 'https://example.gov.uk')
O.review_facts([f['id']], 'approved')
m = s.propose('Fabric baseline approach', 'Our Fabric baseline starts with Purview labelling and DLP before migration.', 'Stefan said')['id']; s.review(m, 'approved')
sv = s.propose('Southvale stakeholders', 'Southvale Council wants weekly steering meetings with the CFO.', 'Stefan said')['id']; s.review(sv, 'approved')
C.tag('memory', [sv], 'Southvale Council')
k = K.create('note', 'Southvale pilot summary', 'Southvale Council pilot. full document: SharePoint/References/Southvale-notes.docx', 'SharePoint/References/Southvale-notes.docx (full document: SharePoint/References/Southvale-notes.docx; not stored in Alice)',
             'Owner', status='draft', client='Southvale Council', client_by='human')
K.review([k['id']], 'approved')
a = AS.get('proposal-writer')
AS.save('proposal-writer', name=a['name'], description=a['description'], greeting=a['greeting'], provider=a['provider'], guidance=a['guidance'], kind='proposal',
        settings=dict(a['settings'], rate_card=[{'role': 'Solution architect', 'unit': 'day', 'cost': 653, 'sell': 1217},
                                                {'role': 'Project manager', 'unit': 'day', 'cost': 451, 'sell': 809}]))
temple.save_settings(False, 'claude')

calls, REPLY = [], {}
class Msgs:
    def create(self, **kw):
        calls.append(kw)
        return NS(content=[NS(type='text', text=json.dumps(REPLY))], usage=NS(model_dump=lambda: {'input_tokens': 2000, 'output_tokens': 600}))
class Anth:
    def __init__(self, **k): self.messages = Msgs()
    def __enter__(self): return self
    def __exit__(self, *a): pass
anthropic.Anthropic = Anth

REPLY.update({'title': 'Fabric data security baseline', 'organisation': 'NSC',
              'brief': 'Background\nNorthshire Council is moving finance data to Fabric in 2027.\n\nScope\nA six-week discovery and labelling baseline.',
              'notes': 'Lead with our baseline approach [M1].', 'template': 'Proposal Templates/Insight-template.docx',
              'structure': [{'heading': 'Approach', 'points': ['governance first', '']}, {'heading': '', 'points': ['x']}],
              'references': ['SharePoint/References/Fabric-guide.docx', 'SharePoint/References/Invented.docx', 'SharePoint/References/Southvale-notes.docx'],
              'roles': [{'role': 'solution architect', 'days': '10.2'}, {'role': 'Astronaut', 'days': 3}, {'role': 'Project manager', 'days': None},
                        {'role': 'Project manager', 'days': 4}],
              'questions': ['Start date?', ''], 'why': 'From your request and the council profile.'})
go = lambda **k: cl.post('/assistant/proposal-writer/starter', json={'ask': 'Six-week Fabric data security baseline for NSC: discovery, labels and a roadmap.', **k})
r = go()
x = r.json()
t('Temple suggests a starter', r.status_code == 200 and x['title'] == 'Fabric data security baseline' and 'six-week discovery' in x['brief'])
t('the client is recognised by its other name', x['organisation'] == 'Northshire Council' and x['client'] is True)
t('only templates on offer are kept', x['template'].replace('\\', '/') == 'Proposal Templates/Insight-template.docx')
t('invented documents and another client\'s are dropped', [p.replace('\\', '/') for p in x['references']] == ['SharePoint/References/Fabric-guide.docx'])
t('only rate card roles, once each, days rounded to half days', x['roles'] == [{'role': 'Solution architect', 'days': 10.0}, {'role': 'Project manager', 'days': None}])
t('empty headings and points are dropped', x['structure'] == [{'heading': 'Approach', 'points': ['governance first']}])
t('questions and the reason are passed on', x['questions'] == ['Start date?'] and x['why'] and x['model'] == 'Claude Haiku 4.5')
msg = calls[-1]['messages'][0]['content']
t('Temple sees the client profile and relevant memories', 'moving its finance data to Microsoft Fabric' in msg and 'Fabric baseline approach' in msg)
t('another client\'s memories and documents are never sent', 'Southvale' not in msg)
t('rates are never sent: role names only', 'Solution architect (per day)' in msg and '653' not in msg and '1217' not in msg and '1,217' not in msg)
t('templates and reference documents are offered by name', 'Proposal Templates/Insight-template.docx' in msg and 'SharePoint/References/Fabric-guide.docx' in msg)
t('the run is a tracked Temple agent', A.runs(PS.STARTER)['runs'] and any(i['target_type'] == 'memory' for i in A.touched_items(PS.STARTER)))
t('the agent is in the Proposals group', A.group_of(A.get(PS.STARTER)) == 'proposals')
with s.db() as c: row = c.execute("SELECT detail,rule FROM activity WHERE action='proposal_starter' ORDER BY id DESC").fetchone()
t('logged as advisory, nothing saved', row and row['rule'] == 'advisory' and 'Fabric data security baseline' in row['detail'] and 'proposal_starter' in AL.LABELS)
with s.db() as c: t('no proposal was created', not c.execute('SELECT 1 FROM proposals').fetchone())

doc = D.get(D.create('docx', 'RFP', '# Invitation to tender\n\nSouthvale Council invites proposals for a Copilot readiness review. ' * 5)['id'])['data']
calls.clear(); REPLY['organisation'] = ''
r = go(ask='', name='rfp.docx', data=b64(doc))
t('a client brief document can be the whole request', r.status_code == 200 and 'Invitation to tender' in calls[-1]['messages'][0]['content'])
t('the client is found in the document', r.json()['organisation'] == 'Southvale Council')
t('documents tagged to that client are then on offer', any('Southvale-notes' in p for p in r.json()['references']))
REPLY['organisation'] = 'NSC'
t('the uploaded document is not kept', not any('rfp' in p.name.lower() for p in root.rglob('*')))
t('a request that is too short is refused', go(ask='help').status_code == 400)
calls.clear()
t('secrets are refused before anything is sent', go(ask='Fabric baseline for NSC, key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD please').status_code == 400 and not calls)
t('protectively marked briefs are refused', go(ask='', name='m.txt', data=b64(('OFFICIAL-SENSITIVE\n' + 'Operational detail. ' * 20).encode())).status_code == 400 and not calls)
t('cross-origin requests are refused', cl.post('/assistant/proposal-writer/starter', headers={'origin': 'http://evil.example'}, json={'ask': 'a b c d e'}).status_code == 403)
t('only proposal writers have a starter', cl.post('/assistant/hr-policy/starter', json={'ask': 'a b c d e'}).status_code == 404)
REPLY['brief'] = 'Use key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD.'
t('what comes back is checked too', go().status_code == 400)
REPLY['brief'] = 'A brief.'
A.set_status(PS.STARTER, 'paused', 'test')
t('a paused starter does not run', go().status_code in (409, 503))
A.set_status(PS.STARTER, 'active')
page = cl.get('/assistant/proposal-writer').text
t('the page has Start with Temple', 'Start with Temple' in page and 'id="tp-ask"' in page and 'id="tp-file"' in page and 'Undo' in page)
