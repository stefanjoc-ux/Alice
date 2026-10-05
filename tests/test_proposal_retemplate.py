"""Changing a written proposal's template: the content is kept. Matching section names carry over word for word (no model call);
otherwise the writer moves the content into the new template's sections, anything it could not place is listed, Argus checks it
and the Word document is rebuilt on the new template. Also: Argus's report is asked to be short and self-explanatory. Fictional
content only; no real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, shutil, tempfile, time, zipfile, io
from pathlib import Path
import substrate_store as s
s.init()
import app, doc_library as L, assistants as AS, proposals as P, proposal_docx as PD
from fastapi.testclient import TestClient
cl = TestClient(app.app)
h = {'origin': 'http://testserver'}

FIX = Path(__file__).parent / 'fixtures' / 'proposal_template.docx'
root = Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents'
L.ROOT = root.resolve()
L.add_source('Templates', 'sharepoint')
shutil.copy(FIX, root / 'Templates' / 'Standard.docx')
NEW = ['Overview', 'Our approach', 'Team']
(root / 'Templates' / 'Short.docx').write_bytes(PD.plain_docx('Short', [{'title': x, 'body': 'Guidance for ' + x, 'keep': False} for x in NEW]))
std = [x['title'] for x in PD.Template(FIX.read_bytes()).outline()]
std_write = [x['title'] for x in PD.Template(FIX.read_bytes()).outline() if not x['keep']]

calls = []
def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='Assistant', meta=None):
    msg = messages[0]['content']; calls.append((system[:40], msg))
    if system.startswith('You are Argus'):
        return json.dumps({'verdict': 'client_ready', 'score': 90, 'summary': 'Ready. Nothing major.', 'requirements':
                           [{'requirement': 'A six-week discovery phase', 'status': 'met', 'where': 'Proposed approach', 'note': ''}], 'issues': [], 'strengths': []})
    want = [ln[2:].split(' [KEEP]')[0] for ln in msg.split('SECTIONS\n')[1].split('\n\n')[0].split('\n') if ln.startswith('- ')]
    if system.startswith('You move an existing proposal'):
        old = json.loads(msg.split('EXISTING CONTENT (JSON)\n')[1].split('\n\n')[0])
        joined = ' '.join(x['body'] for x in old)
        return json.dumps({'sections': [{'title': w, 'body': f'Moved into {w}: ' + joined[:200]} for w in want], 'resource_plan': [],
                           'gaps': [], 'left_over': ['A paragraph about parking']})
    return json.dumps({'sections': [{'title': w, 'body': f'Original text for {w}, about the fictional borough discovery.'} for w in want],
                       'resource_plan': [], 'gaps': []})
AS._call = fake_call

aid = 'proposal-writer'
def wait(pid, n=200):
    for _ in range(n):
        p = P.get(pid)
        if p['status'] != 'running': return p
        time.sleep(0.05)
    return P.get(pid)
brief = 'Fictional Borough Council wants a six-week discovery of its data platform, with a roadmap and a fixed price.'
pid = cl.post(f'/assistant/{aid}/proposals', json={'title': 'Fictional discovery', 'organisation': 'Fictional Borough Council', 'brief': brief,
                                                   'template': 'Templates/Standard.docx', 'sections': [{'title': x} for x in std],
                                                   'rate_card': []}, headers=h).json()['id']
p = wait(pid)
t('a proposal is written on the first template', p['status'] == 'done' and p['inputs']['template'] == 'Templates/Standard.docx')
before = {x['title']: x['body'] for x in p['draft']['sections']}

# the same template: refused
r = cl.post(f'/assistant/{aid}/proposals/{pid}/template', json={'template': 'Templates/Standard.docx'}, headers=h)
t('moving to the template it already uses is refused', r.status_code == 400)
r = cl.post(f'/assistant/{aid}/proposals/{pid}/template', json={'template': '../../etc/passwd'}, headers=h)
t('a template outside the document sources is refused', r.status_code == 400)
t('cross-site requests are refused', cl.post(f'/assistant/{aid}/proposals/{pid}/template', json={'template': 'Templates/Short.docx'},
                                             headers={'origin': 'https://elsewhere.example'}).status_code == 403)

# a template with different sections: the writer moves the content
calls.clear()
r = cl.post(f'/assistant/{aid}/proposals/{pid}/template', json={'template': 'Templates/Short.docx'}, headers=h)
p = wait(pid)
mv = [c for c in calls if c[0].startswith('You move an existing proposal')]
t('changed: the content is moved by the writer into the new sections', r.status_code == 200 and p['status'] == 'done' and len(mv) == 1
  and [x['title'] for x in p['draft']['sections']] == NEW)
t('the writer got the existing content, the brief and the new sections, not a blank page', 'Original text for Executive summary' in mv[0][1]
  and 'six-week discovery' in mv[0][1] and '- Our approach' in mv[0][1])
t('the moved sections carry the existing content', all('Original text for' in x['body'] for x in p['draft']['sections']))
t('what could not be placed is listed, so nothing disappears silently', any('parking' in g for g in p['draft']['gaps']))
t('the proposal now uses the new template and its sections', p['inputs']['template'] == 'Templates/Short.docx'
  and [x['title'] for x in p['inputs']['sections']] == NEW)
t('Argus checked it, labelled as the template change', p['qa'][-1]['source'] == 'new template' and any(c[0].startswith('You are Argus') for c in calls))
with s.db() as c:     # the document is rebuilt on the new template
    row = c.execute('SELECT original FROM generated_documents WHERE id=?', (p['document_id'],)).fetchone()
xml = zipfile.ZipFile(io.BytesIO(bytes(row[0]))).read('word/document.xml').decode('utf-8') if row else ''
t('the Word document is rebuilt with the new sections', 'Our approach' in xml and 'Moved into Our approach' in xml and 'Delivery plan and timeline' not in xml)
with s.db() as c: act = c.execute("SELECT detail FROM activity WHERE action='proposal_retemplated' AND target=?", (pid,)).fetchone()
t('logged', act and 'Short.docx' in act[0])

# back to a template whose section names match: carried over word for word, no model call for the content
calls.clear()
p_before = {x['title']: x['body'] for x in P.get(pid)['draft']['sections']}
(root / 'Templates' / 'Short v2.docx').write_bytes(PD.plain_docx('Short v2', [{'title': x, 'body': 'New guidance', 'keep': False} for x in ['overview', 'Our Approach']]))
cl.post(f'/assistant/{aid}/proposals/{pid}/template', json={'template': 'Templates/Short v2.docx'}, headers=h)
p = wait(pid)
t('matching section names: carried over word for word, without asking the writer', not any(c[0].startswith('You move') for c in calls)
  and p['draft']['sections'][0]['body'] == p_before['Overview'] and p['draft']['sections'][1]['body'] == p_before['Our approach'])
t('a section with no place in the new template is listed', any('"Team"' in g for g in p['draft']['gaps']))

# Alice's own layout: the same sections, no template
cl.post(f'/assistant/{aid}/proposals/{pid}/template', json={'template': ''}, headers=h)
p = wait(pid)
t('to Alice\'s own layout: same sections, content unchanged', p['inputs']['template'] == '' and p['status'] == 'done'
  and [x['title'] for x in p['draft']['sections']] == ['overview', 'Our Approach'])

# the change-template control and the simpler QA view are on the page
page = cl.get(f'/assistant/{aid}').text
t('the page has the template switcher on the result', 'Move the content to this template' in page)
t('the QA view: one list of what to fix, brief coverage as a count', 'What to fix' in page and 'brief requirements met' in page
  and 'Brief gap' in page and 'Minor polish' in page and 'Meets the brief?' not in page)
t('Argus is asked for short, self-explanatory points', 'will not have the brief open' in P.QA_PROMPT and 'at most 12' in P.QA_PROMPT
  and 'at most 10' in P.QA_PROMPT)
