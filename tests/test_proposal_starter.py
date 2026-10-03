"""Parker: completing the proposal form in conversation, under the same rules as the writer, advisory only."""
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
        settings=dict(a['settings'], chat_provider='claude', rate_card=[{'role': 'Solution architect', 'unit': 'day', 'cost': 653, 'sell': 1217},
                                                {'role': 'Project manager', 'unit': 'day', 'cost': 451, 'sell': 809}]))

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


REPLY.update({'reply': 'I have filled in the title, client and brief. Who is the named sponsor?',
              'updates': {'title': 'Fabric data security baseline', 'organisation': 'NSC',
                          'brief': 'Background\nNorthshire Council is moving finance data to Fabric in 2027.\n\nScope\nA six-week discovery and labelling baseline.',
                          'notes': 'Lead with our baseline approach [M1].', 'template': 'Proposal Templates/Insight-template.docx',
                          'structure': [{'heading': 'Approach', 'points': ['governance first', '']}, {'heading': '', 'points': ['x']}],
                          'references': ['SharePoint/References/Fabric-guide.docx', 'SharePoint/References/Invented.docx', 'SharePoint/References/Southvale-notes.docx'],
                          'roles': [{'role': 'solution architect', 'days': '10.2'}, {'role': 'Astronaut', 'days': 3}, {'role': 'Project manager', 'use': False},
                                    {'role': 'Project manager', 'days': 4}], 'bogus': 'x'},
              'questions': ['Who is the named sponsor?', '', 'What is the budget?']})
FORM = {'title': '', 'brief': '', 'roles': [{'role': 'Solution architect', 'unit': 'day', 'use': True, 'days': '', 'cost': '653', 'sell': '1217'},
                                           {'role': 'Project manager', 'unit': 'day', 'use': False, 'days': ''}]}
go = lambda **k: cl.post('/assistant/proposal-writer/parker', json={'message': 'Six-week Fabric data security baseline for NSC: discovery, labels and a roadmap.', 'form': FORM, **k})
r = go()
x = r.json()
u = x.get('updates', {})
t('Parker replies and fills in the form', r.status_code == 200 and x['reply'].startswith('I have filled') and u['title'] == 'Fabric data security baseline' and 'six-week discovery' in u['brief'])
t('the client is recognised by its other name', u['organisation'] == 'Northshire Council' and x['client'] is True)
t('only templates on offer are kept', u['template'].replace('\\', '/') == 'Proposal Templates/Insight-template.docx')
t('invented documents and another client\'s are dropped', [p.replace('\\', '/') for p in u['references']] == ['SharePoint/References/Fabric-guide.docx'])
t('only rate card roles, once each, days rounded to half days, ticks kept', u['roles'] == [{'role': 'Solution architect', 'use': True, 'days': 10.0, 'sell': None}, {'role': 'Project manager', 'use': False, 'days': None, 'sell': None}])
t('empty headings and points are dropped; unknown fields ignored', u['structure'] == [{'heading': 'Approach', 'points': ['governance first']}] and 'bogus' not in u)
t('questions and what changed are passed on', x['questions'] == ['Who is the named sponsor?', 'What is the budget?'] and x['changed'][:3] == ['title', 'client', 'brief'] and x['model'] == 'Claude Haiku 4.5')
msg = calls[-1]['messages'][0]['content']
t('Parker sees the client profile and relevant memories', 'moving its finance data to Microsoft Fabric' in msg and 'Fabric baseline approach' in msg)
t('another client\'s memories and documents are never sent', 'Southvale' not in msg)
t('Parker sees cost and sell rates and the margin (your decision)', 'costs \u00a3653.00, sells at \u00a31,217.00 per day, margin 46.3%' in msg)
t('the form is sent as it stands', 'Solution architect (ticked, costs' in msg and 'not ticked: Project manager' in msg)
calls.clear()
hist = [{'role': 'you', 'text': 'Fabric baseline for NSC'}, {'role': 'parker', 'text': 'Who is the named sponsor?'}]
REPLY.update({'reply': 'Added the sponsor to the brief.', 'updates': {'brief': 'Background\n...\n\nStakeholders and sponsor\nDirector of Finance (sponsor).'}, 'questions': []})
r2 = go(message='The sponsor is the Director of Finance.', history=hist, form=dict(FORM, title='Fabric data security baseline', organisation='Northshire Council'))
m2 = calls[-1]['messages'][0]['content']
t('you can keep chatting: the conversation goes with each turn', r2.status_code == 200 and 'PARKER: Who is the named sponsor?' in m2 and 'The sponsor is the Director of Finance.' in m2)
t('details you give land in the right field', 'Director of Finance (sponsor)' in r2.json()['updates']['brief'] and r2.json()['changed'] == ['brief'])
t('each turn is a tracked Parker run', len(A.runs(PS.PARKER)['runs']) >= 2 and any(i['target_type'] == 'memory' for i in A.touched_items(PS.PARKER)))
t('Parker is in the Proposals group; the old Temple starter is retired from the list', A.group_of(A.get(PS.PARKER)) == 'proposals'
  and not any(a['id'] == 'temple-proposal-starter' for a in A.listing()['agents']))
with s.db() as c: rows = [dict(x) for x in c.execute("SELECT detail,rule FROM activity WHERE action='parker_update' ORDER BY id")]
t('each turn is logged for Temple: what changed and what it asked, never the conversation', len(rows) == 2 and rows[0]['rule'] == 'advisory'
  and 'updated title, client, brief' in rows[0]['detail'] and 'asked about: Who is the named sponsor?' in rows[0]['detail']
  and not any('Director of Finance' in r['detail'] for r in rows) and 'parker_update' in AL.LABELS)
tp = cl.get('/admin/api/temple/parker').json()
t('the Temple page lists Parker\'s activity', len(tp['items']) == 2 and 't-parker' in cl.get('/admin/temple').text)
with s.db() as c: t('nothing is saved: no proposal was created', not c.execute('SELECT 1 FROM proposals').fetchone())

doc = D.get(D.create('docx', 'RFP', '# Invitation to tender\n\nSouthvale Council invites proposals for a Copilot readiness review. ' * 5)['id'])['data']
d = cl.post('/assistant/proposal-writer/parker/document', json={'name': 'rfp.docx', 'data': b64(doc)})
t('the client\'s brief can be added: read once, a token comes back', d.status_code == 200 and d.json()['name'] == 'rfp.docx' and len(d.json()['token']) == 32)
calls.clear(); REPLY['updates'] = {'organisation': 'Southvale', 'references': ['SharePoint/References/Southvale-notes.docx']}
r3 = cl.post('/assistant/proposal-writer/parker', json={'message': '', 'doc_token': d.json()['token'], 'form': {}})
t('Parker reads the document on later turns too', r3.status_code == 200 and 'Invitation to tender' in calls[-1]['messages'][0]['content'])
t('the client is found in the document, and its own documents are then on offer', r3.json()['updates'].get('organisation') == 'Southvale Council'
  and any('Southvale-notes' in p for p in r3.json()['updates']['references']))
t('the document is not kept', not any('rfp' in p.name.lower() for p in root.rglob('*')))
t('an expired document is refused', cl.post('/assistant/proposal-writer/parker', json={'message': 'hi there', 'doc_token': 'f' * 32}).status_code == 400)
t('an empty message is refused', cl.post('/assistant/proposal-writer/parker', json={'message': ''}).status_code == 400)
calls.clear()
t('secrets are refused before anything is sent', go(message='key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD please').status_code == 400 and not calls)
t('secrets in the conversation are refused too', go(message='ok', history=[{'role': 'you', 'text': 'sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'}]).status_code == 400 and not calls)
t('protectively marked documents are refused', cl.post('/assistant/proposal-writer/parker/document', json={'name': 'm.txt', 'data': b64(('OFFICIAL-SENSITIVE\n' + 'Operational detail. ' * 20).encode())}).status_code == 400)
t('cross-origin requests are refused', cl.post('/assistant/proposal-writer/parker', headers={'origin': 'http://evil.example'}, json={'message': 'a b c d e'}).status_code == 403)
t('only proposal writers have Parker', cl.post('/assistant/hr-policy/parker', json={'message': 'a b c d e'}).status_code == 404)
REPLY.update({'reply': 'ok', 'updates': {'brief': 'Use key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD.'}})
t('what comes back is checked too', go().status_code == 400)
REPLY['updates'] = {}
A.set_status(PS.PARKER, 'paused', 'test')
t('a paused Parker does not run', go().status_code in (409, 503))
A.set_status(PS.PARKER, 'active')
# ---------------- revising a proposal that has been written ----------------
DRAFT = [{'title': 'Approach', 'body': 'The work runs in five phases over 20 consultant days.'},
         {'title': 'About us', 'body': 'Standard company text.', 'keep': True}, {'title': 'Commercials', 'body': 'A fixed fee.'}]
calls.clear()
REPLY.update({'reply': 'I have added the on-site start to the approach.', 'questions': [],
              'updates': {'draft': [{'title': 'approach', 'body': 'The work runs in five phases over 20 consultant days. The first days are on site; the rest is remote.'},
                                    {'title': 'About us', 'body': 'Rewritten standard text.'}, {'title': 'Invented section', 'body': 'x'}],
                          'brief': 'Background\nOn-site start, then remote.'}})
rd = cl.post('/assistant/proposal-writer/parker', json={'message': 'Add to the approach: the first days are on site, the rest remote.',
                                                       'form': dict(FORM, title='Fabric baseline', brief='Background', draft=DRAFT)})
md = calls[-1]['messages'][0]['content']
t('Parker sees the proposal as written when you revise it', rd.status_code == 200 and 'DRAFT (the proposal as written' in md and '## Approach' in md
  and 'five phases over 20 consultant days' in md and '[standard text: do not change]' in md)
ud = rd.json()['updates']
t('Parker rewrites the sections you ask about; standard text and invented sections are left alone', ud['draft'] == [{'title': 'Approach',
  'body': 'The work runs in five phases over 20 consultant days. The first days are on site; the rest is remote.'}] and 'draft sections' in rd.json()['changed'])
with s.db() as c: last = c.execute("SELECT detail FROM activity WHERE action='parker_update' ORDER BY id DESC").fetchone()['detail']
t('the Temple log names the sections Parker changed', 'draft sections (Approach)' in last and 'on site' not in last)
calls.clear()
t('secrets in the draft are refused before anything is sent', cl.post('/assistant/proposal-writer/parker', json={'message': 'tidy it', 'form': {'draft': [
  {'title': 'Approach', 'body': 'key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'}]}}).status_code == 400 and not calls)
REPLY['updates'] = {'draft': [{'title': 'Approach', 'body': 'Use key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD.'}]}
t('rewritten sections are checked too', cl.post('/assistant/proposal-writer/parker', json={'message': 'tidy it', 'form': {'draft': DRAFT}}).status_code == 400)
REPLY['updates'] = {}
# ---------------- sell rates you state; replies that are not JSON; the conversation kept with the proposal ----------------
REPLY.update({'reply': 'Set the sell rate to 1050 a day on the ticked roles; the page shows the margin.', 'questions': [],
              'updates': {'roles': [{'role': 'Solution architect', 'use': True, 'sell': '1,050'}, {'role': 'Project manager', 'use': True, 'days': 3, 'sell': -5}]}})
rs = go(message='Change the sell rate to a 1050 day rate. The PM can stay, light touch.').json()
t('Parker sets the sell rate you give it (never sees costs)', rs['updates']['roles'] == [{'role': 'Solution architect', 'use': True, 'days': None, 'sell': 1050.0},
  {'role': 'Project manager', 'use': True, 'days': 3.0, 'sell': None}] and 'sell = cost / (1 - margin)' in PS.PROMPT)
class Plain:
    def __init__(s_, texts): s_.texts = texts
real_create = Msgs.create
seq = []
def create(self, **kw):
    calls.append(kw)
    txt = seq.pop(0)
    return NS(content=[NS(type='text', text=txt)], usage=NS(model_dump=lambda: {'input_tokens': 100, 'output_tokens': 50}))
Msgs.create = create
seq[:] = ['Happy to help: tell me the client first.']
rp = go(message='hello there Parker')
t('a reply in plain words is shown as it is, with no changes', rp.status_code == 200 and rp.json()['reply'] == 'Happy to help: tell me the client first.' and rp.json()['updates'] == {})
calls.clear(); seq[:] = ['{"reply": "Done", "updates": {"brief": "cut sho', json.dumps({'reply': 'Done, briefly.', 'updates': {'title': 'Short title'}, 'questions': []})]
rr = go(message='Rewrite the whole brief please')
t('a reply cut short is asked for again, once', rr.status_code == 200 and rr.json()['updates'] == {'title': 'Short title'} and len(calls) == 2
  and 'not valid JSON' in calls[1]['messages'][0]['content'])
seq[:] = ['{"broken', '{"also broken']
t('two broken replies: a clear error', go(message='Rewrite it again').status_code == 400)
Msgs.create = real_create
import proposals as PR
wf = PR.save_form('proposal-writer', {'title': 'Fabric baseline', 'brief': 'Six weeks.'})
REPLY.update({'reply': 'Noted the sponsor.', 'updates': {}, 'questions': []})
rw = cl.post('/assistant/proposal-writer/parker', json={'message': 'The sponsor is the Director of Finance.', 'form': {'title': 'Fabric baseline'}, 'work_id': wf['id']}).json()
ctx = PR.get(wf['id'])['context']
t('Parker\'s conversation is kept with the proposal, so it follows you to another device', rw['saved_to'] == wf['id']
  and ctx['parker_chat'][-2:] == [{'role': 'you', 'text': 'The sponsor is the Director of Finance.'}, {'role': 'parker', 'text': 'Noted the sponsor.'}])
t('the turn\'s AI cost is added to the proposal', ctx['ai_cost']['parker'] > 0 and ctx['ai_cost']['total'] == ctx['ai_cost']['parker'])
with s.db() as c: t('the activity log still never holds the conversation', not c.execute("SELECT 1 FROM activity WHERE detail LIKE '%Director of Finance%'").fetchone())
nf = PR.save_form('proposal-writer', {'title': 'New one', 'parker_chat': [{'role': 'you', 'text': 'hi'}, {'role': 'parker', 'text': 'hello'}], 'parker_cost': 0.02})
t('a new proposal brings the conversation so far, and its cost, when it is first saved', PR.get(nf['id'])['context']['parker_chat'][1]['text'] == 'hello'
  and PR.get(nf['id'])['context']['ai_cost']['parker'] == 0.02)
t('a secret in the conversation is not saved', cl.post('/assistant/proposal-writer/work', json={'form': {'title': 'x', 'parker_chat': [{'role': 'you', 'text': 'sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'}]}}).status_code == 400)
page = cl.get('/assistant/proposal-writer').text
t('a proposal can be loaded back into the form', 'Load into the form' in page and 'loadIntoForm' in page)
t('the page has Parker\'s chat, always in view, and collapsible sections', all(x in page for x in ('Start with Parker', 'id="pk-msg"', 'id="pk-file"', 'Working with Parker', 'id="col-all"', 'id="exp-all"'))
  and 'Start with Temple' not in page)

# ---------------- roles loaded on the page; what was priced ----------------
calls.clear(); REPLY.update({'reply': 'Updated the commercials wording to 20 days.', 'updates': {'roles': [{'role': 'AI and Financial Consultant', 'days': 20}]}, 'questions': []})
rp2 = cl.post('/assistant/proposal-writer/parker', json={'message': 'The rate card went from 10 to 20 days.', 'form': {'title': 'Finance discovery',
      'roles': [{'role': 'AI and Financial Consultant', 'unit': 'day', 'use': True, 'days': '20', 'sell': '1050', 'cost': '700'}],
      'priced': [{'role': 'AI and Financial Consultant', 'quantity': 10, 'sell_rate': 1050}], 'priced_total': 10500}}).json()
mp = calls[-1]['messages'][0]['content']
t('Parker sees roles from a price book loaded on the page, with days and sell rates', 'AI and Financial Consultant (ticked, 20 days, costs \u00a3700.00, sells at \u00a31,050.00 per day, margin 33.3%)' in mp)
t('Parker sees what the written proposal was priced at', 'AI and Financial Consultant: 10 at \u00a31,050.00; total \u00a310,500.00' in mp and 'Update the pricing' in PS.PROMPT)
t('Parker can update those roles', rp2['updates']['roles'][0]['role'] == 'AI and Financial Consultant')
