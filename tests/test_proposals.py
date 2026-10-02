"""Proposal writer: template sections, context under the rules, writer and QA agents, one automatic revision,
pricing from the rate card (cost never sent or printed), the Word document built from the template."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, io, json, shutil, tempfile, time, zipfile
from pathlib import Path
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import knowledge as K, doc_library as L, organisations as O, clients as C, agents as A, assistants as AS
import proposals as P, proposal_docx as PD
import anthropic
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

FIX = Path(__file__).parent / 'fixtures' / 'proposal_template.docx'
root = Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents'
L.ROOT = root.resolve()
L.add_source('Proposal Templates', 'sharepoint', 'SharePoint: Bids site, Templates library')
shutil.copy(FIX, root / 'Proposal Templates' / 'Proposal-template.docx')

# ---------------- the template ----------------
raw = FIX.read_bytes()
o = PD.outline(raw)
titles = [x['title'] for x in o['sections']]
t('template headings become the sections, in order', titles[:3] == ['Executive summary', 'Understanding of your requirements', 'Proposed approach'] and len(titles) == 9)
t('text under a heading is guidance; [keep] marks standard text', o['sections'][0]['guidance'].startswith('[Two or three') and
  next(x for x in o['sections'] if x['title'] == 'About us')['keep'])
t('placeholders are found in the body, header and footer', {'title', 'client', 'date', 'reference', 'author'} <= set(o['placeholders']))

# ---------------- settings on the assistant ----------------
a = AS.get('proposal-writer')
t('a Proposal writer assistant is ready to set up', a['kind'] == 'proposal' and a['provider'] == 'claude_sonnet')
card = [{'role': 'Solution architect', 'unit': 'day', 'cost': 650, 'sell': '1,200'}, {'role': 'Consultant', 'unit': 'day', 'cost': 450, 'sell': 850}]
body = {'name': 'Proposal writer', 'provider': 'claude_sonnet', 'kind': 'proposal', 'guidance': 'Plain UK English.',
        'settings': {'template': 'Proposal Templates/Proposal-template.docx', 'rate_card': card, 'min_margin': 50,
                     'sections': [{'title': 'Executive summary', 'guidance': 'Mention value for money.'}, {'title': 'Risks', 'guidance': 'Top five risks with mitigations.'}]}}
r = cl.put('/admin/api/assistants/proposal-writer', headers=H, json=body)
t('format and flow, rate card and template are saved', r.status_code == 200 and r.json()['settings']['rate_card'][0]['sell'] == 1200
  and r.json()['settings']['template'].endswith('Proposal-template.docx'))
for bad, why in [({'rate_card': [{'role': 'X', 'cost': 'abc', 'sell': 1}]}, 'number'), ({'template': '../../etc/passwd'}, 'template'),
                 ({'sections': [{'title': 'A'}, {'title': 'a'}]}, 'twice'), ({'rate_card': [{'role': 'X', 'cost': -1, 'sell': 1}]}, 'between')]:
    rr = cl.put('/admin/api/assistants/proposal-writer', headers=H, json=dict(body, settings=dict(body['settings'], **bad)))
    t(f'refused: {why}', rr.status_code == 400 and why in rr.json()['detail'])
t('the type cannot change once created', cl.put('/admin/api/assistants/hr-policy', headers=H, json={'name': 'HR policy assistant', 'kind': 'proposal'}).json()['kind'] == 'qa')
t('templates are listed from the document sources', any(x['name'] == 'Proposal-template.docx' and x['source'] == 'Proposal Templates'
                                                      for x in cl.get('/admin/api/proposal-templates', headers=H).json()['templates']))
st = cl.get('/assistant/proposal-writer/setup').json()
secs = [x['title'] for x in st['sections']]
t('the page starts from the template sections plus your format and flow', secs[0] == 'Executive summary' and secs[-1] == 'Risks'
  and 'Mention value for money.' in st['sections'][0]['guidance'] and st['sections'][-1]['source'] == 'format and flow')

# ---------------- context material ----------------
O.create('Northshire Council', 'council', client=True, aliases=['NSC'])
O.create('Southvale Council', 'council', client=True)
f1 = O.propose_fact('Northshire Council', 'purpose', 'Northshire is moving its data platform to Microsoft Fabric in 2027.', 'Public web', 'https://example.gov.uk/fabric')
O.review_facts([f1['id']], 'approved')
m_ok = s.propose('Fabric baseline approach', 'Our Fabric data security baseline starts with Purview labelling and DLP before migration.', 'Stefan said')['id']; s.review(m_ok, 'approved')
m_nsc = s.propose('Northshire stakeholders', 'Northshire Council data security lead wants a six week discovery for Fabric.', 'Stefan said')['id']; s.review(m_nsc, 'approved')
m_svc = s.propose('Southvale Fabric pricing', 'Southvale Council Fabric discovery was priced at forty days of consultancy.', 'Stefan said')['id']; s.review(m_svc, 'approved')
C.tag('memory', [m_nsc], 'Northshire Council'); C.tag('memory', [m_svc], 'Southvale Council')

# ---------------- mock models ----------------
calls = []
def writer_json(sections, revised=False, client='Northshire Council'):
    return json.dumps({'sections': [{'title': x, 'body': ('Revised. ' if revised else '') + f'{client} needs a secure Fabric baseline. {x} text with enough words to count as a real section of a proposal for the client.'}
                                    for x in sections],
                       'resource_plan': [{'role': 'Solution architect', 'quantity': 10, 'purpose': 'Design'}, {'role': 'Consultant', 'quantity': 15.2, 'purpose': 'Delivery'},
                                         {'role': 'Astronaut', 'quantity': 3}],
                       'gaps': ['Start date not given']})
QA1 = {'verdict': 'needs_revision', 'score': 62, 'summary': 'Close.', 'requirements': [{'requirement': 'Six week discovery', 'status': 'partly', 'where': 'Proposed approach'}],
       'issues': [{'severity': 'high', 'section': 'Proposed approach', 'issue': 'Discovery length not stated', 'fix': 'Say six weeks'}], 'strengths': ['Clear']}
QA2 = {'verdict': 'client_ready', 'score': 88, 'summary': 'Ready.', 'requirements': [{'requirement': 'Six week discovery', 'status': 'met', 'where': 'Proposed approach'}],
       'issues': [{'severity': 'low', 'section': 'Next steps', 'issue': 'Add owners', 'fix': 'Name roles'}], 'strengths': ['Specific']}
MODE = {'qa': [QA1, QA2]}
class Msgs:
    def create(self, **kw):
        calls.append(kw)
        usage = NS(model_dump=lambda: {'input_tokens': 1000, 'output_tokens': 400})
        if kw['system'].startswith('You are the proposal writer'):
            want = [ln[2:].split(' [KEEP]')[0] for ln in kw['messages'][0]['content'].split('SECTIONS\n')[1].split('\n\nRATE CARD')[0].split('\n') if ln.startswith('- ')]
            client = kw['messages'][0]['content'].split('CLIENT: ')[1].split('\n')[0]
            text = writer_json(want, 'PREVIOUS DRAFT' in kw['messages'][0]['content'], client)
        elif kw['system'].startswith('You are the Proposal QA'):
            text = json.dumps(MODE['qa'].pop(0) if MODE['qa'] else QA2)
        else:
            text = '{}'
        return NS(content=[NS(type='text', text=text)], usage=usage)
class Anth:
    def __init__(s_, **k): s_.messages = Msgs()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
anthropic.Anthropic = Anth

def wait(pid, secs=20):
    end = time.time() + secs
    while time.time() < end:
        p = cl.get(f'/assistant/proposal-writer/proposals/{pid}').json()
        if p['status'] != 'running': return p
        time.sleep(0.1)
    return p

brief = ('Northshire Council wants a partner to set a data security baseline before moving to Microsoft Fabric. They want a six week '
         'discovery, a Purview labelling baseline and a roadmap. Responses by the end of October.')
r = cl.post('/assistant/proposal-writer/proposals', json={'title': 'Fabric security baseline', 'organisation': 'NSC', 'brief': brief,
                                                          'sections': st['sections'], 'rate_card': card})
t('a proposal starts in the background', r.status_code == 200 and r.json()['id'])
p = wait(r.json()['id'])
t('it finishes with a Word document', p['status'] == 'done' and p['document_id'] and not print(p.get('error') or ''))
t('the organisation is recognised by its other name and marked as a client', p['organisation'] == 'Northshire Council' and p['client'] == 'Northshire Council')
w = [c for c in calls if c['system'].startswith('You are the proposal writer')]
q = [c for c in calls if c['system'].startswith('You are the Proposal QA')]
t('writer, QA, one automatic revision, QA again', len(w) == 2 and len(q) == 2 and 'PREVIOUS DRAFT' in w[1]['messages'][0]['content']
  and 'Discovery length not stated' in w[1]['messages'][0]['content'])
t('the QA reports are kept: needs revision, then client ready', [x['verdict'] for x in p['qa']] == ['needs_revision', 'client_ready'] and p['qa'][1]['score'] == 88)
t('the draft is the revision', p['draft']['sections'][0]['body'].startswith('Revised.'))
ctx = w[0]['messages'][0]['content']
t('the writer gets the client profile and relevant memories', 'moving its data platform to Microsoft Fabric' in ctx and 'Fabric baseline approach' in ctx)
t('this client\'s tagged memories are included', 'Northshire stakeholders' in ctx)
t('another client\'s memories never are', 'Southvale' not in ctx and not any('Southvale' in c['messages'][0]['content'] for c in calls))
t('cost rates never reach a model', not any('650' in c['messages'][0]['content'] for c in w)
  and not any('1200' in c['messages'][0]['content'] or '1,200' in c['messages'][0]['content'] for c in w))
t('roles not on the rate card are dropped; quantities rounded to half days', [x['role'] for x in p['draft']['resource_plan']] == ['Solution architect', 'Consultant']
  and p['draft']['resource_plan'][1]['quantity'] == 15.0 and p['draft']['dropped_roles'] == ['Astronaut'])
pr = p['pricing']
t('Alice prices the plan from the sell rates', pr['sell'] == 10 * 1200 + 15 * 850 and pr['rows'][-1] == ['Total', '', '', '£24,750'])
t('cost and margin are worked out for you', pr['cost'] == 10 * 650 + 15 * 450 and round(pr['margin'], 1) == round((24750 - 13250) / 24750 * 100, 1))
t('margin below your minimum is flagged', any('below your minimum of 50%' in x for x in pr['warnings']))
t('QA sees sell prices only', '£24,750' in q[0]['messages'][0]['content'] and '£13,250' not in q[0]['messages'][0]['content'] and '650' not in q[0]['messages'][0]['content'])
t('what Alice used is listed for you', p['context']['used']['organisation'] == 'Northshire Council' and 'Fabric baseline approach' in p['context']['used']['memories'])

import documents as D
doc = D.get(p['document_id'])['data']
text = K.docx_to_text(doc)
t('the document is the template, filled in', 'HEADER: Northshire Council | Fabric security baseline' in text and 'Prepared for Northshire Council' in text)
t('every section is there in order, the extra one at the end', text.index('# Executive summary') < text.index('# Proposed approach') < text.index('# Risks'))
t('standard [keep] text is kept word for word', 'We are an independent technology partner' in text and '[keep]' not in text)
t('the pricing table sits in the Commercials section, cost never appears', 'Row 4: Total |  |  | £24,750' in text and '£650' not in text and '13,250' not in text and 'All prices exclude VAT.' in text)
t('no guidance or placeholders are left', '[Two or three' not in text and '{{' not in text)
with zipfile.ZipFile(io.BytesIO(doc)) as z:
    t('the template look is untouched (styles, header, footer)', z.read('word/styles.xml') == zipfile.ZipFile(io.BytesIO(raw)).read('word/styles.xml')
      and any(n.startswith('word/header') for n in z.namelist()))
with s.db() as c:
    t('the document is not knowledge', not c.execute("SELECT 1 FROM files WHERE name LIKE 'Fabric-security%'").fetchone())
    t('the proposal is logged', c.execute("SELECT 1 FROM activity WHERE action='proposal_written' AND detail LIKE '%client_ready%'").fetchone() is not None)
runs = {x: A.runs(x)['runs'] for x in (P.WRITER, P.QA)}
t('both agents ran as tracked runs (2 writer, 2 QA)', len(runs[P.WRITER]) == 2 and len(runs[P.QA]) == 2)
touched = A.touched_items(P.WRITER)
t('the writer\'s Data touched shows the template, memories and the client profile, sent to Sonnet',
  any(i['target_type'] == 'document' for i in touched) and any(i['target_id'] == m_ok for i in touched)
  and all('Claude Sonnet 5.5 (Anthropic)' in i['sent_to'] for i in touched if i['read']))

# ---------------- QA passes first time: no revision ----------------
calls.clear(); MODE['qa'] = [QA2]
p2 = wait(cl.post('/assistant/proposal-writer/proposals', json={'title': 'Second proposal', 'organisation': 'Someone New Ltd', 'brief': brief,
                                                                  'use_memory': False, 'sections': [{'title': 'Summary'}, {'title': 'Pricing'}], 'rate_card': card}).json()['id'])
t('client ready first time: no revision', p2['status'] == 'done' and len(p2['qa']) == 1 and sum(1 for c in calls if c['system'].startswith('You are the proposal writer')) == 1)
t('an organisation not on the Organisations page is used as typed, not as a client', p2['organisation'] == 'Someone New Ltd' and p2['client'] == '')
t('with memory off, no memories are sent', 'APPROVED MEMORIES' not in calls[0]['messages'][0]['content'])

# ---------------- Alice's own checks ----------------
chk = P.alice_checks([{'title': 'A', 'body': 'We worked with Southvale Council on this. Price £5,000. [Insert case study]', 'keep': False},
                      {'title': 'B', 'body': '', 'keep': False}], 'Northshire Council')
kinds = ' '.join(c['issue'] for c in chk)
t('Alice flags other clients named, prices in text, placeholders and empty sections',
  'another client: Southvale Council' in kinds and 'Prices in the text' in kinds and 'Placeholder' in kinds and 'is empty' in kinds)

# ---------------- refusals ----------------
def start(**k):
    return cl.post('/assistant/proposal-writer/proposals', json={'title': 'Test', 'organisation': '', 'brief': brief, **k})
t('a brief that is too short is refused', start(brief='Fix it please').status_code == 400)
t('a secret in the brief is refused before anything is sent', start(brief=brief + ' key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD').status_code == 400)
t('protectively marked briefs are refused', start(brief='OFFICIAL-SENSITIVE\n' + brief).status_code == 400)
t('cross-origin requests are refused', cl.post('/assistant/proposal-writer/proposals', headers={'origin': 'http://evil.example'},
                                               json={'title': 'T', 'brief': brief}).status_code == 403)
A.set_status(P.QA, 'paused', 'test')
t('a paused agent stops new proposals', start().status_code == 503)
A.set_status(P.QA, 'active')
t('proposal writers do not answer questions', cl.post('/assistant/proposal-writer/ask', json={'question': 'hello there'}).status_code == 400)

# failure is reported, not hidden
class Broken:
    def __init__(s_, **k): s_.messages = s_
    def create(s_, **k): return NS(content=[NS(type='text', text='not json at all')], usage=NS(model_dump=lambda: {'input_tokens': 1, 'output_tokens': 1}))
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
anthropic.Anthropic = Broken
pf = wait(start().json()['id'])
t('an unusable model answer fails the proposal with a clear message', pf['status'] == 'failed' and 'usable answer' in pf['error'])
anthropic.Anthropic = Anth

lst = cl.get('/assistant/proposal-writer/proposals').json()['proposals']
t('recent proposals are listed with their QA verdict', lst and any(x['verdict'] == 'client_ready' for x in lst))
t('another assistant cannot read a proposal', cl.get(f'/assistant/hr-policy/proposals/{p["id"]}').status_code == 404)
page = cl.get('/assistant/proposal-writer').text
t('the proposal page has the brief, format and flow and rate card', 'id="brief"' in page and 'Format and flow' in page and 'Rate card' in page)
t('the Assistants page offers the proposal settings', 'Format and flow' in cl.get('/admin/assistants').text)

# no template: Alice's own layout
cl.put('/admin/api/assistants/proposal-writer', headers=H, json=dict(body, settings=dict(body['settings'], template='')))
MODE['qa'] = [QA2]
p3 = wait(start(sections=[{'title': 'Summary'}, {'title': 'Investment'}], rate_card=card).json()['id'])
t3 = K.docx_to_text(D.get(p3['document_id'])['data']) if p3['status'] == 'done' else ''
t('without a template, Alice\'s own layout with the same sections and pricing', '# Summary' in t3 and '£24,750' in t3 and not print(p3.get('error') or ''))

# numbered lists restart in each section (Word would otherwise carry on counting)
import re as _re
out = PD.fill(raw, [{'title': 'A', 'body': '1. one\n2. two'}, {'title': 'B', 'body': '1. again'}], {})
with zipfile.ZipFile(io.BytesIO(out)) as z:
    ids = _re.findall(r'<w:numId w:val="(\d+)"', z.read('word/document.xml').decode())
    t('each numbered list restarts at 1', len(set(ids)) == 2 and z.read('word/numbering.xml').decode().count('<w:startOverride w:val="1"/>') == 2)
t('placeholders split across runs are still filled', 'Prepared for Acme' in K.docx_to_text(PD.fill(raw, [], {'client': 'Acme'})))

# ---------------- choosing a better model ----------------
t('premium models are offered for proposals, with rough costs', {'claude_opus', 'openai_astra'} <= {m['key'] for m in cl.get('/assistant/proposal-writer/setup').json()['models'] if m['premium']}
  and all(m['writer_cost'] is not None for m in cl.get('/assistant/proposal-writer/setup').json()['models']))
t('a question-answering assistant cannot use a premium model', cl.put('/admin/api/assistants/hr-policy', headers=H, json={'name': 'HR policy assistant', 'provider': 'claude_opus'}).status_code == 400)
t('provider families for the rules', AS.family('openai_astra') == 'openai' and AS.family('claude_opus') == 'claude')
cl.put('/admin/api/assistants/proposal-writer', headers=H, json=dict(body, settings=dict(body['settings'], template='Proposal Templates/Proposal-template.docx')))
calls.clear(); MODE['qa'] = [QA2]
p4 = wait(start(writer_model='claude_opus', qa_model='claude_sonnet', sections=[{'title': 'Summary'}], rate_card=card).json()['id'])
wm = [c['model'] for c in calls if c['system'].startswith('You are the proposal writer')]
qm = [c['model'] for c in calls if c['system'].startswith('You are the Proposal QA')]
t('each proposal can use another writer and QA model', p4['status'] == 'done' and wm == ['claude-opus-5-5'] and qm == ['claude-sonnet-5-5']
  and p4['inputs']['writer'] == 'claude_opus')
t('unknown models are refused', start(writer_model='gpt-99').status_code == 400)
t('Opus is recorded as where the data went', any('Claude Opus 5.5 (Anthropic)' in i['sent_to'] for i in A.touched_items(P.WRITER)))
t('the Agents page names the model in use', 'Claude Sonnet 5.5 (Proposal writer)' in next(a for a in cl.get('/admin/api/agents', headers=H).json()['agents'] if a['id'] == P.WRITER)['anatomy_live']['model'])
import openai
seen_o = []
class ORsp:
    def create(self, **kw):
        seen_o.append(kw)
        return NS(output_text='{}', usage=NS(model_dump=lambda: {'input_tokens': 10, 'output_tokens': 5}))
class OAI:
    def __init__(s_, **k): s_.responses = ORsp()
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
openai.OpenAI = OAI
AS._call('openai_astra', 'sys', [{'role': 'user', 'content': 'x'}])
t('GPT-6 Astra is called with reasoning on (it has no "none" setting)', seen_o[-1]['model'] == 'gpt-6-astra' and seen_o[-1]['reasoning']['effort'] == 'medium')

# ---------------- structure, text to include, re-checks and QA of your own document ----------------
anthropic.Anthropic = Anth
calls.clear(); MODE['qa'] = [QA2]
r = start(structure='1. Why now\n- budget pressure\n2. Approach', sections=[{'title': 'Summary', 'include': '- Fixed price\n- Starts in January'}, {'title': 'Pricing'}], rate_card=card)
p5 = wait(r.json()['id'])
wmsg = [c for c in calls if c['system'].startswith('You are the proposal writer')][0]['messages'][0]['content']
t('a pasted structure reaches the writer as the author\'s outline', 'STRUCTURE AND POINTS FROM THE AUTHOR\n1. Why now\n- budget pressure' in wmsg)
t('text to include is given per section', 'Include: - Fixed price' in wmsg and 'Starts in January' in wmsg and p5['inputs']['sections'][0]['include'].startswith('- Fixed'))
t('a structure with a secret is refused', start(structure='key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD').status_code == 400)

calls.clear(); MODE['qa'] = [QA2]
edited = [{'title': x['title'], 'body': ('My edited summary with the January start date and a fixed price for the council. ' * 3) if x['title'] == 'Summary' else x['body']}
          for x in p5['draft']['sections']]
r = cl.post(f'/assistant/proposal-writer/proposals/{p5["id"]}/recheck', json={'sections': edited})
p6 = wait(p5['id'])
q6 = [c for c in calls if c['system'].startswith('You are the Proposal QA')]
t('your edits go back to QA and the document is rebuilt', r.status_code == 200 and p6['status'] == 'done' and len(p6['qa']) == len(p5['qa']) + 1
  and p6['qa'][-1]['source'] == 'your edits' and len(q6) == 1 and 'My edited summary' in q6[0]['messages'][0]['content']
  and p6['document_id'] != p5['document_id'] and 'My edited summary' in K.docx_to_text(D.get(p6['document_id'])['data']))
t('no writer run for a re-check', not [c for c in calls if c['system'].startswith('You are the proposal writer')])
t('every section must come back, titles unchanged', cl.post(f'/assistant/proposal-writer/proposals/{p5["id"]}/recheck', json={'sections': edited[:1]}).status_code == 400)
t('another assistant cannot re-check it', cl.post(f'/assistant/hr-policy/proposals/{p5["id"]}/recheck', json={'sections': edited}).status_code == 404)

mine = D.get(D.create('docx', 'My version', '# Summary\nOur own words for the council: fixed price, January start, governance first. ' * 2
                      + '\n\n# Approach\nThree phases over six weeks with workshops and a roadmap at the end of it all.')['id'])['data']
calls.clear(); MODE['qa'] = [QA1]
r = cl.post(f'/assistant/proposal-writer/proposals/{p5["id"]}/qa-upload', json={'name': 'Fabric-v2.docx', 'data': base64.b64encode(mine).decode()})
p7 = wait(p5['id'])
q7 = [c for c in calls if c['system'].startswith('You are the Proposal QA')]
t('a revised version uploaded from Word is checked against the brief', r.status_code == 200 and p7['qa'][-1]['source'] == 'uploaded: Fabric-v2.docx'
  and 'Our own words for the council' in q7[0]['messages'][0]['content'] and [x['title'] for x in p7['qa'][-1]['sections']] == ['Summary', 'Approach'])
t('the uploaded document is not kept, and the draft is unchanged', p7['draft'] == p6['draft'] and p7['document_id'] == p6['document_id'])
t('a secret in an uploaded version is refused', cl.post(f'/assistant/proposal-writer/proposals/{p5["id"]}/qa-upload',
  json={'name': 'k.txt', 'data': base64.b64encode(('# A\nkey sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD ' + 'x ' * 200).encode()).decode()}).status_code == 400)

calls.clear(); MODE['qa'] = [QA2]
r = cl.post('/assistant/proposal-writer/proposals/qa-only', json={'title': 'Existing bid', 'organisation': 'NSC', 'brief': brief, 'name': 'bid.docx',
                                                                    'data': base64.b64encode(mine).decode(), 'qa_model': 'claude_sonnet'})
p8 = wait(r.json()['id'])
t('QA only: a proposal you already have is checked without writing anything', r.status_code == 200 and p8['status'] == 'done' and len(p8['qa']) == 1
  and not p8['document_id'] and p8['inputs']['qa_only'] and p8['organisation'] == 'Northshire Council'
  and not [c for c in calls if c['system'].startswith('You are the proposal writer')] and [x['title'] for x in p8['draft']['sections']] == ['Summary', 'Approach'])
t('QA only needs a brief', cl.post('/assistant/proposal-writer/proposals/qa-only', json={'title': 'X bid', 'brief': 'too short', 'name': 'a.docx',
                                                                                           'data': base64.b64encode(mine).decode()}).status_code == 400)
t('a QA-only proposal cannot be "edited and re-checked"', cl.post(f'/assistant/proposal-writer/proposals/{p8["id"]}/recheck',
  json={'sections': [{'title': 'Summary', 'body': 'x'}, {'title': 'Approach', 'body': 'y'}]}).status_code == 400)
secs = P.document_sections('t.docx', PD.fill(raw, [{'title': 'Executive summary', 'body': 'A ' * 150}, {'title': 'Proposed approach', 'body': 'B ' * 150}], {'title': 'T', 'client': 'C'}))
t('a document is split at its main headings', [x['title'] for x in secs][-2:] == ['Executive summary', 'Proposed approach'])
page = cl.get('/assistant/proposal-writer').text
t('the page offers the structure box, QA-only mode and re-checks', all(x in page for x in ('id="structure"', 'Turn into sections', 'Check one I already have', 'Edit the draft and check again', 'Upload a revised version for QA')))

# pasting a rate card table (the parser runs in the browser; checked with Node when it is installed)
import shutil, subprocess, proposal_ui
node = shutil.which('node')
if node:
    js = Path(tempfile.mkdtemp()) / 'pe.js'
    js.write_text('const document={};' + proposal_ui.PE_JS + 'module.exports=PE;', encoding='utf-8')
    out = subprocess.run([node, str(Path(__file__).parent / 'js' / 'rate_paste_test.js'), str(js)], capture_output=True, text=True, timeout=60).stdout
    t('a pasted rate card table is read: headings, order, units, £ and commas, markdown, no headings', out.strip().endswith('7 passed 0 failed'))
t('the rate card offers Paste a table', 'Paste a table' in proposal_ui.PE_JS and 'parseRates' in proposal_ui.PE_JS)
