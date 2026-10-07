"""Applying a suggestion or editing a written proposal actually saves, and Argus checks what was saved (seen on P-6A32CB, 7 Oct 2026:
brief and roles applied in the browser only, Argus scored the old brief, a new version copied it). Apply stores the changes (rules
checked, roles repriced, a version recorded, marked as not checked by Argus yet); Undo puts the stored values back; Check again saves
the brief, notes, title and rate card from the page; Re-apply recovers changes that were marked applied but never stored.
No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, time
import substrate_store as s
s.init()
import app, assistants as AS, proposals as P, proposal_share as PS
from fastapi.testclient import TestClient
cl = TestClient(app.app)
h = {'origin': 'http://testserver'}
SEEN = []

def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='Assistant', meta=None):
    msg = messages[0]['content']
    if system.startswith('You are Argus'):
        SEEN.append(msg)
        return json.dumps({'verdict': 'needs_revision', 'score': 70, 'summary': 'Close.', 'requirements': [], 'issues': [], 'strengths': []})
    want = [ln[2:].split(' [KEEP]')[0] for ln in msg.split('SECTIONS\n')[1].split('\n\n')[0].split('\n') if ln.startswith('- ')]
    return json.dumps({'sections': [{'title': w, 'body': f'Draft text for {w} for the fictional borough.'} for w in want],
                       'resource_plan': [{'role': 'Consultant', 'quantity': 10}, {'role': 'Architect', 'quantity': 4}], 'gaps': []})
AS._call = fake_call

aid = 'proposal-writer'
card = [{'role': 'Consultant', 'unit': 'day', 'cost': 450, 'sell': 900, 'use': True}, {'role': 'Architect', 'unit': 'day', 'cost': 600, 'sell': 1200, 'use': True}]
OLD = 'Fictional Borough Council wants a six-week discovery of its data platform with a roadmap and a fixed price.'
NEW = 'Fictional Borough Council wants an eight-week discovery of its data platform, a roadmap, a costed options paper and a fixed price.'

def wait(pid):
    for _ in range(300):
        if P.get(pid)['status'] != 'running': return P.get(pid)
        time.sleep(0.05)
    return P.get(pid)

pid = cl.post(f'/assistant/{aid}/proposals', json={'title': 'Fictional data discovery', 'organisation': 'Fictional Borough Council', 'brief': OLD,
              'sections': [{'title': 'Summary'}, {'title': 'Approach'}], 'rate_card': card, 'template': ''}, headers=h).json()['id']
wait(pid)
ref = PS.ref(pid)
get = lambda: cl.get(f'/assistant/{aid}/proposals/{pid}').json()
decide = lambda sid, action: cl.post(f'/assistant/{aid}/proposals/{pid}/suggestions/{sid}', json={'action': action}, headers=h)
again = lambda sid, action: cl.post(f'/assistant/{aid}/proposals/{pid}/suggestions/{sid}/saved', json={'action': action}, headers=h)
sections = lambda p: [{'title': x['title'], 'body': x['body']} for x in p['draft']['sections']]

# 1. Apply saves
sg = PS.suggest(ref, 'Eight weeks and more consultant time.', {'brief': NEW, 'notes': 'Lead with the options paper.',
                'roles': [{'role': 'Consultant', 'days': 20}]}, 'Claude')
r = decide(sg['suggestion'], 'applied')
t('Apply on a written proposal answers with what was saved', r.status_code == 200 and r.json()['saved'] == ['brief', 'notes', 'roles'])
p = get()                                                    # a reload: what the page sees after F5
t('Apply survives a reload: the brief and notes are stored', p['brief'] == NEW and p['notes'] == 'Lead with the options paper.')
cons = next(x for x in p['inputs']['rate_card'] if x['role'] == 'Consultant')
line = next(x for x in p['pricing']['lines'] if x['role'] == 'Consultant')
t('a roles change is stored and repriced as Reprice does', cons['days'] == 20 and line['quantity'] == 20
  and p['pricing']['sell'] == 20 * 900 + 4 * 1200 and next(x for x in p['draft']['resource_plan'] if x['role'] == 'Consultant')['quantity'] == 20)
t('the draft is marked as changed since Argus last checked', set(p['context']['unchecked']['what']) == {'brief', 'notes', 'roles'})
last = p['context']['history'][-1]
t('the version says exactly what was saved, by whom and that Argus has not checked it',
  last['via'] == 'Claude' and last['what'].startswith('Saved changes suggested by Claude: brief, notes and roles (repriced). Not checked by Argus yet (saved ')
  and last['kind'] == 'applied')
sgx = next(x for x in p['context']['model_suggestions'] if x['id'] == sg['suggestion'])
t('the suggestion is applied and saved, with the stored values it replaced', sgx['state'] == 'applied' and sgx['saved_at'] and sgx['before']['brief'] == OLD)
t('nothing to re-apply when it was saved', p['lost_suggestions'] == [])
t('get_proposal shows the saved brief to every model', PS.detail(ref)['brief'] == NEW)

# 2. Argus checks what was saved
SEEN.clear()
r = cl.post(f'/assistant/{aid}/proposals/{pid}/recheck', json={'sections': sections(p), 'form': {'title': p['title'], 'organisation': p['organisation'],
            'brief': NEW, 'notes': p['notes']}}, headers=h)
p = wait(pid)
t('Argus receives the saved brief and the new price', r.status_code == 200 and SEEN and NEW in SEEN[-1] and OLD not in SEEN[-1]
  and '£22,800' in SEEN[-1].replace('22800', '22,800'))
t('after Check again it is no longer marked as changed', 'unchecked' not in P.get(pid)['context'])

# Check again with changes typed on the page: saved first, Argus checks the saved values
TYPED = NEW + ' The council also wants a short training session for its analysts.'
SEEN.clear()
rc = [dict(c, use=True) for c in P.get(pid)['inputs']['rate_card']]
for c in rc:
    if c['role'] == 'Architect': c['days'] = 6
r = cl.post(f'/assistant/{aid}/proposals/{pid}/recheck', json={'sections': sections(P.get(pid)), 'form': {'title': 'Fictional data discovery and training',
            'organisation': 'Fictional Borough Council', 'brief': TYPED, 'notes': 'Lead with the options paper.', 'rate_card': rc}}, headers=h)
p = wait(pid)
t('Check again saves the typed brief, title and rate card', r.status_code == 200 and p['brief'] == TYPED and p['title'] == 'Fictional data discovery and training'
  and next(x for x in p['pricing']['lines'] if x['role'] == 'Architect')['quantity'] == 6)
t('Argus checked the typed brief', SEEN and 'short training session' in SEEN[-1])
hist = [x['what'] for x in p['context']['history']]
t('the history says what Check again saved', any(w.startswith('Saved your changes to title, brief and rate card from the Parker page') for w in hist))

# a secret in the brief is refused, nothing stored
r = cl.post(f'/assistant/{aid}/proposals/{pid}/recheck', json={'sections': sections(p), 'form': {'brief': TYPED + ' key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'}}, headers=h)
t('a secret in the brief is refused on Check again, and not stored', r.status_code == 400 and 'sk-proj' not in P.get(pid)['brief'] and P.get(pid)['status'] == 'done')
with s.db() as c:                                            # a suggestion that somehow carries a secret (suggest() itself refuses one)
    ctx = json.loads(c.execute('SELECT context FROM proposals WHERE id=?', (pid,)).fetchone()['context'])
    ctx['model_suggestions'].append({'id': 'secret00001', 'from': 'Claude', 'at': s.now(), 'note': '', 'state': 'pending', 'changed': ['brief'],
                                     'updates': {'brief': TYPED + ' key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD'}})
    c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), pid))
r = decide('secret00001', 'applied')
p = get()
t('a secret in an applied brief is refused: nothing stored, the suggestion still waits', r.status_code == 400 and 'sk-proj' not in p['brief']
  and next(x for x in p['context']['model_suggestions'] if x['id'] == 'secret00001')['state'] == 'pending')
decide('secret00001', 'dismissed')

# Undo restores the stored values
sg2 = PS.suggest(ref, 'Shorter notes.', {'notes': 'Keep it short.', 'roles': [{'role': 'Architect', 'days': 2}]}, 'ChatGPT')
decide(sg2['suggestion'], 'applied')
t('applied: notes and roles stored', P.get(pid)['notes'] == 'Keep it short.' and next(x for x in P.get(pid)['pricing']['lines'] if x['role'] == 'Architect')['quantity'] == 2)
r = again(sg2['suggestion'], 'undo')
p = get()
t('Undo puts the stored notes, rate card and price back', r.status_code == 200 and p['notes'] == 'Lead with the options paper.'
  and next(x for x in p['pricing']['lines'] if x['role'] == 'Architect')['quantity'] == 6 and 'unchecked' not in p['context'])
t('Undo is recorded as a version', p['context']['history'][-1]['what'].startswith('Undid the changes suggested by ChatGPT')
  and next(x for x in p['context']['model_suggestions'] if x['id'] == sg2['suggestion'])['state'] == 'undone')

# 3. Save as a new version: the page loads the stored proposal into the form, so the new version carries the saved brief
p = get()
form = {'title': p['title'], 'organisation': p['organisation'], 'brief': p['brief'], 'notes': p['notes'] + ' Plus a typed note.',
        'sections': p['inputs']['sections'], 'rate_card': p['inputs']['rate_card'], 'started_from': pid}
nv = cl.post(f'/assistant/{aid}/work', json={'form': form}, headers=h).json()
t('Save as a new version carries the new brief and the unsaved form change', P.get(nv['id'])['brief'] == TYPED
  and P.get(nv['id'])['notes'].endswith('Plus a typed note.'))
cl.post(f'/assistant/{aid}/proposals/{nv["id"]}/restore', headers=h)          # keep the original as the current version for what follows
P.discard_form(aid, nv['id'])

# 4. Re-apply: suggestions marked applied before Apply saved (only the form changed)
def lost_one(sid, updates, by, at):
    with s.db() as c:
        ctx = json.loads(c.execute('SELECT context FROM proposals WHERE id=?', (pid,)).fetchone()['context'])
        ctx['model_suggestions'].append({'id': sid, 'from': by, 'at': at, 'note': 'Old apply.', 'state': 'applied', 'decided_at': at,
                                         'changed': ['brief', 'roles'], 'updates': updates})
        c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), pid))
B1 = TYPED + ' Version one of the lost change.'
B2 = TYPED + ' Version two of the lost change, the latest.'
time.sleep(0.01); lost_one('lost0000001', {'brief': B1, 'roles': [{'role': 'Consultant', 'days': 25}]}, 'Claude', s.now())
time.sleep(0.01); lost_one('lost0000002', {'brief': B2}, 'Claude', s.now())
p = get()
L = {x['id']: x for x in p['lost_suggestions']}
t('applied but never stored: both are offered for Re-apply, with what is missing', set(L) == {'lost0000001', 'lost0000002'}
  and L['lost0000001']['missing'] == ['brief', 'roles'] and L['lost0000002']['missing'] == ['brief'])
page = cl.get(f'/assistant/{aid}').text
t('the page has the Re-apply button and the unsaved note', "'Re-apply'" in page and 'Not saved yet: ' in page and 'Changed since Argus last checked: ' in page)
r = again('lost0000001', 'reapply')
p = get()
t('Re-apply restores the lost brief and roles, repriced', r.status_code == 200 and p['brief'] == B1
  and next(x for x in p['pricing']['lines'] if x['role'] == 'Consultant')['quantity'] == 25)
t('the history says it was re-applied and when it was first applied', p['context']['history'][-1]['what'].startswith('Re-applied and saved changes suggested by Claude (applied ')
  and 'but never saved): brief and roles' in p['context']['history'][-1]['what'])
t('re-applying the older one leaves the newer lost change on offer', [x['id'] for x in p['lost_suggestions']] == ['lost0000002'])
r = again('lost0000002', 'reapply')
p = get()
t('then the newer one: its brief is stored and nothing is left to re-apply', p['brief'] == B2 and p['lost_suggestions'] == [])
t('re-applying again is refused: nothing to do', again('lost0000002', 'reapply').status_code == 400)
time.sleep(0.01); lost_one('lost0000003', {'brief': OLD}, 'Claude', s.now())
again('lost0000003', 'leave')
t('Leave as it is: no more Re-apply for it', get()['lost_suggestions'] == [] and get()['brief'] == B2)

# a proposal in progress still applies in the form (it saves itself)
form_id = cl.post(f'/assistant/{aid}/work', json={'form': {'title': 'Half-finished bid', 'brief': 'Early notes for a fictional trust.', 'rate_card': card}}, headers=h).json()['id']
sf = PS.suggest(PS.ref(form_id), 'n', {'notes': 'More detail.'}, 'Claude')
r = cl.post(f'/assistant/{aid}/proposals/{form_id}/suggestions/{sf["suggestion"]}', json={'action': 'applied'}, headers=h)
t('a form: Apply is recorded and left to the form to save', r.status_code == 200 and r.json() == {'state': 'applied'}
  and P.get(form_id)['context']['history'][-1]['what'] == 'Applied changes suggested by Claude in the form: notes (saved with the form)')
