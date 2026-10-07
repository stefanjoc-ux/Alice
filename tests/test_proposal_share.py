"""Parker's proposals for every model (Stefan's decision, 5 Oct 2026): list_proposals, get_proposal (brief, draft, rate card with
cost, sell and margin, pricing, Argus's latest points) and propose_proposal_changes, which only ever saves a suggestion: the user
applies or dismisses it on the Parker page. Changes are checked like Parker's own (only roles, templates and sections that
exist); secrets and markings are refused; client separation still applies to outside connections. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, os, time
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import app, assistants as AS, proposals as P, proposal_share as PS, mcp_server as M, agents
from fastapi.testclient import TestClient
cl = TestClient(app.app)
h = {'origin': 'http://testserver'}

def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='Assistant', meta=None):
    msg = messages[0]['content']
    if system.startswith('You are Argus'):
        return json.dumps({'verdict': 'needs_revision', 'score': 70, 'summary': 'Close. Say six weeks.', 'requirements':
                           [{'requirement': 'A six-week discovery phase', 'status': 'partly', 'where': 'Approach', 'note': 'Never says six weeks.'},
                            {'requirement': 'A roadmap', 'status': 'met', 'where': 'Approach', 'note': ''}],
                           'issues': [{'severity': 'high', 'section': 'Summary', 'issue': 'Names the wrong council.', 'fix': 'Use Fictional Borough Council.'}], 'strengths': []})
    want = [ln[2:].split(' [KEEP]')[0] for ln in msg.split('SECTIONS\n')[1].split('\n\n')[0].split('\n') if ln.startswith('- ')]
    return json.dumps({'sections': [{'title': w, 'body': f'Draft text for {w} for the fictional borough.'} for w in want],
                       'resource_plan': [{'role': 'Consultant', 'quantity': 10}, {'role': 'Architect', 'quantity': 4}], 'gaps': []})
AS._call = fake_call

aid = 'proposal-writer'
card = [{'role': 'Consultant', 'unit': 'day', 'cost': 450, 'sell': 900, 'use': True}, {'role': 'Architect', 'unit': 'day', 'cost': 600, 'sell': 1200, 'use': True}]
pid = cl.post(f'/assistant/{aid}/proposals', json={'title': 'Fictional data discovery', 'organisation': 'Fictional Borough Council',
              'brief': 'Fictional Borough Council wants a six-week discovery of its data platform with a roadmap and a fixed price.',
              'sections': [{'title': 'Summary'}, {'title': 'Approach'}], 'rate_card': card, 'template': ''}, headers=h).json()['id']
for _ in range(200):
    if P.get(pid)['status'] != 'running': break
    time.sleep(0.05)
ref = PS.ref(pid)
form = cl.post(f'/assistant/{aid}/work', json={'form': {'title': 'Half-finished bid', 'organisation': 'Another Fictional Trust',
               'brief': 'Early notes for a fictional trust.', 'sections': [{'title': 'Overview'}], 'rate_card': card}}, headers=h).json()['id']

# list
r = M.list_proposals()
refs = [x['proposal'] for x in r['proposals']]
t('every model can list Parker\'s proposals, written and in progress', ref in refs and PS.ref(form) in refs)
row = next(x for x in r['proposals'] if x['proposal'] == ref)
t('each has its reference, status, QA and sell total', row['status'] == 'written' and row['qa'] == 'needs revision 70/100'
  and row['sell_total'] == 10 * 900 + 4 * 1200 and row['writer'])
t('in progress shows as a form', next(x for x in r['proposals'] if x['proposal'] == PS.ref(form))['status'].startswith('in progress'))
t('search by words', [x['proposal'] for x in M.list_proposals(query='trust')['proposals']] == [PS.ref(form)])

# read one in full
d = M.get_proposal(ref)
t('get by reference: the brief and the draft text', d['proposal'] == ref and 'six-week' in d['brief']
  and [x['title'] for x in d['draft']] == ['Summary', 'Approach'] and 'Draft text for Approach' in d['draft'][1]['body'])
t('the rate card with cost, sell and margin', {x['role']: (x['cost_rate'], x['sell_rate'], x['margin_pct']) for x in d['rate_card']}
  == {'Consultant': (450, 900, 50.0), 'Architect': (600, 1200, 50.0)})
t('the pricing with cost and margin', d['pricing']['sell_total'] == 13800 and d['pricing']['cost_total'] == 10 * 450 + 4 * 600
  and d['pricing']['lines'][0]['cost_rate'] in (450, 600))
t('Argus\'s latest points as one plain list', d['qa']['brief_requirements_met'] == '1 of 2' and d['qa']['what_to_fix'][0]['kind'] == 'brief gap'
  and any(x['kind'] == 'must fix' for x in d['qa']['what_to_fix']))
t('get by title words too', M.get_proposal('fictional data discovery')['proposal'] == ref)
try: M.get_proposal('P-000000'); t('an unknown reference is refused', False)
except ValueError as e: t('an unknown reference is refused, pointing to list_proposals', 'list_proposals' in str(e))

# propose changes: saved for the user, never applied
before = P.get(pid)
r = M.propose_proposal_changes(ref, 'Says six weeks and trims the architect days.', {
    'draft': [{'title': 'Approach', 'body': 'A six-week discovery in three stages.'}, {'title': 'Not a section', 'body': 'x'}],
    'roles': [{'role': 'Architect', 'days': 3}, {'role': 'Astronaut', 'days': 9}], 'template': 'Nowhere/none.docx', 'notes': 'Lead with outcomes.'})
after = P.get(pid)
t('a suggestion is saved for the user, nothing in the proposal changes', r['changes'] == ['notes', 'roles', 'draft sections']
  and 'template' in r['left_out'] and after['draft'] == before['draft'] and after['inputs'] == before['inputs'] and after['notes'] == before['notes'])
sg = after['context']['model_suggestions'][-1]
t('only roles and sections that exist are kept', sg['updates']['roles'] == [{'role': 'Architect', 'use': True, 'days': 3.0, 'sell': None}]
  and sg['updates']['draft'] == [{'title': 'Approach', 'body': 'A six-week discovery in three stages.'}] and sg['state'] == 'pending')
t('who suggested it is kept', sg['from'] == "Alice's chat")
t('get_proposal shows what is waiting', M.get_proposal(ref)['model_suggestions_pending'][0]['id'] == sg['id'])
t('the reply says it is not applied yet and how to find it', 'not applied yet' in r['message'] and ref in r['message']
  and r['open'] == f'/assistant/{aid}?p={pid}')
os.environ['ALICE_PUBLIC_URL'] = 'https://alice.example.org/'
t('with a public address, the reply carries the full link', PS.page_link(P.get(pid)) == f'https://alice.example.org/assistant/{aid}?p={pid}'
  and M.get_proposal(ref)['page'].startswith('https://alice.example.org/'))
os.environ.pop('ALICE_PUBLIC_URL')
row = next(x for x in cl.get(f'/assistant/{aid}/proposals', headers=h).json()['proposals'] if x['id'] == pid)
t('the Parker page\'s Proposals list carries the count waiting and who from', row['suggestions'] == 1 and row['suggested_by'] == ["Alice's chat"])
t('list shows the count waiting', next(x for x in M.list_proposals()['proposals'] if x['proposal'] == ref)['pending_model_suggestions'] == 1)
try: M.propose_proposal_changes(ref, 'x', {'astronauts': 1}); t('nothing usable: refused, saying what can change', False)
except ValueError as e: t('nothing usable: refused, saying what can change', 'roles' in str(e) and 'draft' in str(e))
try: M.propose_proposal_changes(ref, 'Adds the key', {'notes': 'api key sk-ant-api03-' + 'A' * 90}); t('a secret is refused', False)
except ValueError as e: t('a secret is refused', True)
try: M.propose_proposal_changes(ref, 'Marked', {'brief': 'OFFICIAL-SENSITIVE: the restructure'}); t('a protective marking is refused', False)
except ValueError as e: t('a protective marking is refused', True)

# the user applies or dismisses it on the Parker page
r = cl.post(f'/assistant/{aid}/proposals/{pid}/suggestions/{sg["id"]}', json={'action': 'applied'}, headers=h)
t('applied on the Parker page: marked and logged', r.status_code == 200 and P.get(pid)['context']['model_suggestions'][-1]['state'] == 'applied')
t('cross-site requests are refused', cl.post(f'/assistant/{aid}/proposals/{pid}/suggestions/{sg["id"]}', json={'action': 'dismissed'},
                                             headers={'origin': 'https://elsewhere.example'}).status_code == 403)
r2 = M.propose_proposal_changes(ref, 'Another idea', {'notes': 'Mention the roadmap first.'})
r = cl.post(f'/assistant/{aid}/proposals/{pid}/suggestions/{r2["suggestion"]}', json={'action': 'dismissed'}, headers=h)
t('dismissed', r.status_code == 200 and P.get(pid)['context']['model_suggestions'][-1]['state'] == 'dismissed')
with s.db() as c: acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE target=?", (pid,))}
t('suggested, applied and dismissed are in the log', {'proposal_change_suggested', 'proposal_change_applied', 'proposal_change_dismissed'} <= acts)
page = cl.get(f'/assistant/{aid}').text
t('the Parker page shows model suggestions with Apply and Dismiss', 'pkSuggestions' in page and 'suggested changes' in page)
t('the Proposals list badges proposals with suggestions, and a new page points to them', 'wb-sug' in page and 'pkWaiting()' in page
  and 'Open it to apply or dismiss' in page)
t('Apply waits for the draft to load before applying draft changes', 'The proposal is still loading' in page)
row = next(x for x in cl.get(f'/assistant/{aid}/proposals', headers=h).json()['proposals'] if x['id'] == pid)
t('nothing waiting once applied or dismissed', row['suggestions'] == 0)

# versions: when, who and from where
hist = P.get(pid)['context']['history']
t('a written proposal has versions: written by Parker, then the applied suggestion with where it came from',
  hist[0]['v'] == 1 and hist[0]['via'] == 'Parker and Argus' and hist[0]['what'].startswith('Written by Parker')
  and any(x['kind'] == 'applied' and x['via'] == "Alice's chat" and 'notes' in x['what'] for x in hist))
t('versions count up', [x['v'] for x in hist] == list(range(1, len(hist) + 1)))
w = cl.post(f'/assistant/{aid}/work', json={'form': {'title': 'Fictional versioned form', 'brief': 'A brief.'}}, headers=h).json()
t('a new form starts at version 1 on the Parker page', w['version']['v'] == 1 and w['version']['via'] == 'Parker page' and w['version']['what'] == 'Started')
w2 = cl.post(f'/assistant/{aid}/work', json={'id': w['id'], 'form': {'title': 'Fictional versioned form', 'brief': 'A longer brief.'}}, headers=h).json()
t('autosaves from the same place within half an hour stay one version', w2['version']['v'] == 1 and w2['version']['edits'] == 2)
w3 = cl.post(f'/assistant/{aid}/work', json={'id': w['id'], 'form': {'title': 'Fictional versioned form', 'brief': 'Brief from Claude.', 'via': 'Claude'}}, headers=h).json()
t('an edit carrying a suggestion from Claude is a new version, via Claude', w3['version']['v'] == 2 and w3['version']['via'] == 'Claude')
with s.db() as c:
    ctx = json.loads(c.execute('SELECT context FROM proposals WHERE id=?', (w['id'],)).fetchone()['context'])
    ctx['history'][-1]['at'] = '2026-01-01T09:00:00+00:00'
    c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), w['id']))
w4 = cl.post(f'/assistant/{aid}/work', json={'id': w['id'], 'form': {'title': 'Fictional versioned form', 'brief': 'Later.', 'via': 'Claude'}}, headers=h).json()
t('the same place after a long gap is a new version', w4['version']['v'] == 3)
row = next(x for x in cl.get(f'/assistant/{aid}/proposals', headers=h).json()['proposals'] if x['id'] == w['id'])
t('the Proposals list shows version, when and where', row['version'] == 3 and row['edited_via'] == 'Claude' and row['edited_at'])
k = cl.post(f'/assistant/{aid}/work', json={'form': {'title': 'Copy', 'brief': 'b', 'started_from': pid}}, headers=h).json()
t('saving a written proposal as a new version says which it replaces', k['version']['what'] == 'Started as a new version; replaces ' + ref)
cl.post(f'/assistant/{aid}/work/{k["id"]}/discard', headers=h)          # removed again: the written one is current once more
t('removing that new version makes the written one current again', P.get(pid)['superseded_by'] == '')
g = M.get_proposal(ref); hist = P.get(pid)['context']['history']
t('models see the version and recent history', g['version']['number'] == hist[-1]['v'] and g['history'][-1]['v'] == hist[-1]['v']
  and next(x for x in M.list_proposals()['proposals'] if x['proposal'] == ref)['version'].startswith('v'))
page = cl.get(f'/assistant/{aid}').text
t('the workbar shows the version, with a versions list', 'id="wb-ver"' in page and 'id="wb-hist"' in page and 'Versions of this proposal' in page)

# outside connections: same tools, same access; client separation still applies, and the caller is named
M._who = lambda: NS(label='Microsoft Copilot', provider='copilot')
M._app = lambda tool: (None, None)
M._client_hidden = lambda org, who: org == 'Another Fictional Trust'
r = M.list_proposals()
t('an outside model sees the same, minus clients it may not see', ref in [x['proposal'] for x in r['proposals']] and PS.ref(form) not in
  [x['proposal'] for x in r['proposals']] and r['withheld'] == 1)
t('and the costs', M.get_proposal(ref)['rate_card'][0]['cost_rate'] in (450, 600))
try: M.get_proposal(PS.ref(form)); t('a hidden client\'s proposal cannot be read', False)
except ValueError: t('a hidden client\'s proposal cannot be read', True)
r = M.propose_proposal_changes(ref, 'From Copilot', {'notes': 'Shorter summary.'})
t('a suggestion from an outside model names it', P.get(pid)['context']['model_suggestions'][-1]['from'] == 'Microsoft Copilot')

t('Alice\'s own chat has the tools', {'list_proposals', 'get_proposal', 'propose_proposal_changes'} <= app.ALLOWED_TOOLS)
t('registered for the Agents page, the change tool as a write', 'get_proposal' in agents.TOOLS and 'propose_proposal_changes' in agents.WRITE_TOOLS)

# the Proposals list: a reference on every row, the latest activity (edit or suggestion), suggestions waiting = In progress
def rows(): return {x['id']: x for x in cl.get(f'/assistant/{aid}/proposals').json()['proposals']}
for x in P.get(pid)['context'].get('model_suggestions') or []:
    if x.get('state') == 'pending': PS.decide(aid, pid, x['id'], 'dismissed')
L = rows()
t('every row carries its reference, as proposal_share.ref', L[pid]['ref'] == ref and L[form]['ref'] == PS.ref(form) and ref == 'P-' + pid[:6].upper())
t('a written proposal with nothing waiting is Written, its date the last edit',
  L[pid]['group'] == 'written' and L[pid]['activity_kind'] == 'edit' and L[pid]['activity_at'] == L[pid]['edited_at'])
t('a proposal in progress is In progress', L[form]['group'] == 'progress' and L[form]['activity_kind'] == 'edit')
before = L[pid]
s1 = PS.suggest(ref, 'Tighter summary.', {'notes': 'Keep the summary to one paragraph.'}, 'Claude')
time.sleep(0.01)
s2 = PS.suggest(ref, 'Say six weeks.', {'notes': 'Say six weeks in the approach.'}, 'ChatGPT')
L = rows(); x = L[pid]
t('a written proposal with suggestions waiting moves to In progress', x['group'] == 'progress' and x['status'] == 'done')
t('it keeps its status and score for the pill, and the suggestion count',
  x['verdict'] == before['verdict'] and x['score'] == before['score'] and x['suggestions'] == 2)
t('its date is the newest suggestion, with who suggested it',
  x['activity_kind'] == 'suggestion' and x['activity_from'] == 'ChatGPT' and x['activity_at'] > x['edited_at']
  and x['activity_at'] == max(s['at'] for s in P.get(pid)['context']['model_suggestions'] if s['state'] == 'pending'))
t('the newest activity sorts first', sorted(L.values(), key=lambda r: r['activity_at'], reverse=True)[0]['id'] == pid)
PS.decide(aid, pid, s1['suggestion'], 'applied')
x = rows()[pid]
pend = [s for s in P.get(pid)['context']['model_suggestions'] if s['state'] == 'pending']
t('with one still waiting it stays In progress; applying counts as an edit, so the date is the later of the two',
  x['group'] == 'progress' and x['suggestions'] == 1 and x['activity_at'] == max(x['edited_at'], pend[0]['at']))
PS.decide(aid, pid, s2['suggestion'], 'dismissed')
x = rows()[pid]
t('applied or dismissed, it goes back to Written, dated by its last edit',
  x['group'] == 'written' and x['activity_kind'] == 'edit' and x['activity_at'] == x['edited_at'] and not x['suggestions'])
t('the applied suggestion is saved on the written proposal, the dismissed one is not', P.get(pid)['notes'] == 'Keep the summary to one paragraph.')
t('a suggestion on a proposal in progress keeps it In progress',
  (PS.suggest(PS.ref(form), 'n', {'notes': 'More detail.'}, 'Claude') and rows()[form]['group'] == 'progress'))
page = cl.get(f'/assistant/{aid}').text
t('the page searches by reference and shows it in the workbar', 'x.ref||' in page and 'id="wb-ref"' in page and 'Suggestion from ' in page)
