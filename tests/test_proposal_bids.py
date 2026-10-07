"""Bids and versions of Parker's proposals (Stefan, 7 Oct 2026): a bid is a chain of versions; its current version is the newest one
not superseded. Save as a new version and Make this replace... link them (never by title), Restore as a separate proposal undoes it;
both sides are in the version history. A superseded version is read-only. Its pending model suggestions move to the current version,
re-checked there, and what no longer fits is listed, never dropped. The Proposals list is one row per bid with the AI cost across
its versions; the connector tools list bids and refuse changes to an earlier version. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, time
import substrate_store as s
s.init()
import app, assistants as AS, proposals as P, proposal_share as PS, proposal_bids as B, mcp_server as M
from fastapi.testclient import TestClient
cl = TestClient(app.app)
h = {'origin': 'http://testserver'}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='Assistant', meta=None):
    msg = messages[0]['content']
    if system.startswith('You are Argus'):
        return json.dumps({'verdict': 'client_ready', 'score': 88, 'summary': 'Fine.', 'requirements': [], 'issues': [], 'strengths': []})
    want = [ln[2:].split(' [KEEP]')[0] for ln in msg.split('SECTIONS\n')[1].split('\n\n')[0].split('\n') if ln.startswith('- ')]
    return json.dumps({'sections': [{'title': w, 'body': f'Draft text for {w}.'} for w in want],
                       'resource_plan': [{'role': 'Consultant', 'quantity': 5}], 'gaps': []})
AS._call = fake_call

aid = 'proposal-writer'
card = [{'role': 'Consultant', 'unit': 'day', 'cost': 450, 'sell': 900, 'use': True}, {'role': 'Architect', 'unit': 'day', 'cost': 600, 'sell': 1200, 'use': True}]
BRIEF = 'Fictional Borders Council wants a discovery of its data platform with a roadmap, a fixed price and a six-week plan.'


def write(title, sections, org='Fictional Borders Council', started_from=''):
    pid = cl.post(f'/assistant/{aid}/proposals', json={'title': title, 'organisation': org, 'brief': BRIEF, 'template': '',
                  'sections': [{'title': x} for x in sections], 'rate_card': card, 'started_from': started_from}, headers=h).json()['id']
    for _ in range(300):
        if P.get(pid)['status'] != 'running': break
        time.sleep(0.05)
    return pid


def pending(pid): return [x for x in P.get(pid)['context'].get('model_suggestions') or [] if x.get('state') == 'pending']
def whats(pid): return [x['what'] for x in P.get(pid)['context'].get('history') or []]
def bids(): return cl.get(f'/assistant/{aid}/proposals').json()


# ---------------- Save as a new version: joins the bid and supersedes its current version ----------------
a = write('Borders data discovery', ['Summary', 'Approach'])
ra = B.ref(a)
PS.suggest(ra, 'Rewrite the approach.', {'draft': [{'title': 'Approach', 'body': 'Six weeks in three stages.'}],
                                          'roles': [{'role': 'Architect', 'days': 3}]}, 'Claude')
PS.suggest(ra, 'Lead with outcomes.', {'notes': 'Lead with outcomes.'}, 'ChatGPT')
P.add_cost(a, 1.25, 'writing')
b = cl.post(f'/assistant/{aid}/work', json={'form': {'title': 'Borders data discovery', 'organisation': 'Fictional Borders Council',
            'brief': BRIEF, 'sections': [{'title': 'Summary'}, {'title': 'Approach'}], 'rate_card': card, 'started_from': a}}, headers=h).json()
b = b['id']; rb = B.ref(b)
A, Bp = P.get(a), P.get(b)
t('Save as a new version: the new one joins the bid and supersedes the old one at once', A['superseded_by'] == b and Bp['superseded_by'] == ''
  and A['bid_id'] == a and Bp['bid_id'] == a)
t('both sides are in the version history, with who', 'Superseded by ' + rb in whats(a) and 'Started as a new version; replaces ' + ra in whats(b)
  and P.get(a)['context']['history'][-1]['by'])
info = B.info(a)
t('the bid knows its versions in order and which is current', [v['ref'] for v in info['versions']] == [ra, rb] and info['current'] == b
  and not info['is_current'] and info['superseded_by_ref'] == rb)

# ---------------- suggestions carry over, re-checked; what no longer fits is listed ----------------
pb = pending(b)
t('pending suggestions move to the current version', len(pb) == 2 and not pending(a)
  and {x['state'] for x in P.get(a)['context']['model_suggestions']} == {'carried'})
c1 = next(x for x in pb if x['from'] == 'Claude')
t('each carried suggestion says where it was written', c1['carried_from']['ref'] == ra and c1['carried_from']['version'] == 1)
t('what still fits stays: the role is on this version\'s rate card', c1['updates'].get('roles') == [{'role': 'Architect', 'use': True, 'days': 3.0, 'sell': None}])
t('what no longer fits is listed, not dropped: this version has no written draft yet', 'draft' not in c1['updates']
  and c1['no_longer'] == ['Draft section “Approach”: this version has no written draft yet'] and c1['changed'] == ['roles'])
c2 = next(x for x in pb if x['from'] == 'ChatGPT')
t('a suggestion that fits completely carries over with nothing listed', c2['updates'] == {'notes': 'Lead with outcomes.'} and not c2['no_longer'])
r = cl.post(f'/assistant/{aid}/proposals/{b}/suggestions/{c2["id"]}', json={'action': 'dismissed'}, headers=h)
t('Apply and Dismiss work on a carried suggestion as on any other', r.status_code == 200 and len(pending(b)) == 1)

# ---------------- a superseded version is read-only ----------------
for path, body in (('recheck', {'sections': [{'title': 'Summary', 'body': 'x'}, {'title': 'Approach', 'body': 'y'}]}),
                   ('revise', {'fixes': [{'issue': 'x', 'fix': 'y'}]}), ('reprice', {'rate_card': card}), ('template', {'template': ''})):
    r = cl.post(f'/assistant/{aid}/proposals/{a}/{path}', json=body, headers=h)
    t(f'no Argus checks or edits start on a superseded version ({path}): refused, naming the current one', r.status_code == 400 and rb in r.json()['detail'])
try: P.qa_upload(aid, a, 'x.txt', b'Summary\nSome text for the check.'); t('no upload checks on it either', False)
except ValueError as e: t('no upload checks on it either', rb in str(e))
import proposal_starter as PST
try: PST.chat(aid, 'Change the title', work_id=a); t('no new Parker edits on it', False)
except ValueError as e: t('no new Parker edits on it', 'read-only' in str(e))
t('it is not deleted: still there, with its draft', P.get(a)['status'] == 'done' and P.get(a)['draft']['sections'])

# ---------------- connector tools ----------------
L = M.list_proposals()['proposals']
mine = [x for x in L if x['proposal'] in (ra, rb)]
t('list_proposals lists the bid once, as its current version, with the earlier references', len(mine) == 1 and mine[0]['proposal'] == rb
  and [e['proposal'] for e in mine[0]['earlier_versions']] == [ra] and mine[0]['version_in_bid'] == 2)
t('searching for an earlier reference finds the bid', [x['proposal'] for x in M.list_proposals(query=ra)['proposals']] == [rb])
g = M.get_proposal(ra)
t('get_proposal on a superseded version says so and names the current one', g['superseded'] and g['superseded_by'] == rb and rb in g['superseded_note']
  and rb in g['how_to_change'] and g['bid']['current_version'] == rb)
t('get_proposal by title gives the current version', M.get_proposal('borders data discovery')['proposal'] == rb)
try: M.propose_proposal_changes(ra, 'Too late', {'notes': 'x'}); t('propose_proposal_changes on a superseded version is refused', False)
except ValueError as e: t('propose_proposal_changes on a superseded version is refused, naming the current one', rb in str(e) and 'earlier version' in str(e))

# ---------------- the Proposals list: one row per bid, costs roll up ----------------
P.add_cost(b, 0.32, 'parker')
d = bids()
bid = next(x for x in d['bids'] if x['current'] == b)
t('one row per bid: its current version, the earlier ones below it', bid['earlier'] == [a] and bid['versions'] == 2 and bid['organisation'] == 'Fictional Borders Council')
t('the AI cost rolls up across the versions; each keeps its own', abs(bid['ai_cost_total'] - (P.get(a)['context']['ai_cost']['total'] + 0.32)) < 1e-6
  and bid['ai_cost_current'] == 0.32)
rows = {x['id']: x for x in d['proposals']}
t('each row knows its place in the bid', rows[a]['bid_version'] == 1 and rows[b]['bid_version'] == 2 and rows[a]['superseded_by'] == b)
t('a bid in progress sits under In progress', bid['group'] == 'progress')
page = cl.get(f'/assistant/{aid}').text
t('the page groups by client, shows earlier versions and the cost in total',
  'No client' in page and 'earlier version' in page and 'in total' in page and 'this version' in page)
t('the page offers Make this replace and Restore as a separate proposal', 'Make this replace' in page and 'Restore as a separate proposal' in page
  and 'Carried over from' in page and 'No longer applies here' in page and 'Superseded by' in page)

# ---------------- Make this replace...: the user picks; the old ones become earlier versions ----------------
c = write('Borders discovery, first go', ['Summary', 'Approach'])
rc = B.ref(c)
PS.suggest(rc, 'Two sections.', {'draft': [{'title': 'Approach', 'body': 'New approach.'}, {'title': 'Summary', 'body': 'New summary.'}]}, 'Claude')
dd = write('Borders discovery, second go', ['Summary', 'Plan'])
rd = B.ref(dd)
t('proposals with similar titles are never linked by themselves', P.get(c)['superseded_by'] == '' and P.get(dd)['superseded_by'] == '')
r = cl.post(f'/assistant/{aid}/proposals/{dd}/replaces', json={'replaces': [c]}, headers=h)
t('Make this replace: the picked proposal becomes an earlier version', r.status_code == 200 and P.get(c)['superseded_by'] == dd
  and r.json()['replaces'] == [rc] and r.json()['carried'] == 1)
t('both sides recorded: Replaces and Superseded by', 'Replaces ' + rc in whats(dd) and 'Superseded by ' + rd in whats(c))
cs = pending(dd)[0]
t('a section that does not exist in the current version is listed as no longer applying',
  cs['updates'] == {'draft': [{'title': 'Summary', 'body': 'New summary.'}]} and cs['carried_from']['ref'] == rc
  and cs['no_longer'] == ['Draft section “Approach”: not a section of this version’s draft'])
r = cl.post(f'/assistant/{aid}/proposals/{dd}/replaces', json={'replaces': [c]}, headers=h)
t('a version already in the bid cannot be linked again', r.status_code == 400)
r = cl.post(f'/assistant/{aid}/proposals/{c}/replaces', json={'replaces': [b]}, headers=h)
t('a superseded version cannot be made to replace anything', r.status_code == 400 and rd in r.json()['detail'])
r = cl.post(f'/assistant/{aid}/proposals/{dd}/replaces', json={'replaces': [a]}, headers=h)
t('only the current version of another bid can be picked', r.status_code == 400 and rb in r.json()['detail'])
t('cross-site requests are refused', cl.post(f'/assistant/{aid}/proposals/{dd}/replaces', json={'replaces': [b]},
                                             headers={'origin': 'https://elsewhere.example'}).status_code == 403)

# ---------------- Restore as a separate proposal: undo ----------------
r = cl.post(f'/assistant/{aid}/proposals/{c}/restore', headers=h)
t('restored: a bid of its own again', r.status_code == 200 and P.get(c)['superseded_by'] == '' and P.get(c)['bid_id'] == '' and P.get(dd)['bid_id'] == '')
t('the history says so on both sides', any(w.startswith('Restored as a separate proposal') for w in whats(c)) and any(w.startswith('No longer replaces ' + rc) for w in whats(dd)))
back = pending(c)
t('its carried suggestion goes back with it, exactly as written', len(back) == 1 and not pending(dd) and 'carried_from' not in back[0]
  and back[0]['updates'] == {'draft': [{'title': 'Approach', 'body': 'New approach.'}, {'title': 'Summary', 'body': 'New summary.'}]})
r = cl.post(f'/assistant/{aid}/proposals/{c}/restore', headers=h)
t('restoring a current version is refused', r.status_code == 400)

# ---------------- writing from a written proposal is a new version too ----------------
e = write('Borders discovery, third go', ['Summary', 'Plan'], started_from=dd)
t('written from a written proposal: it supersedes that one', P.get(dd)['superseded_by'] == e and 'Replaces ' + rd in whats(e)
  and P.get(e)['status'] == 'done')

# ---------------- removing a new version in progress puts the old one back ----------------
with s.db() as cx: cx.execute('UPDATE proposals SET status=? WHERE id=?', ('form', b))
r = cl.post(f'/assistant/{aid}/work/{b}/discard', headers=h)
t('removing the version in progress makes the earlier one current again', r.status_code == 200 and P.get(a)['superseded_by'] == '')
back = pending(a)
t('with the suggestion still waiting, back as it was written', len(back) == 1 and back[0]['from'] == 'Claude' and 'carried_from' not in back[0]
  and back[0]['updates']['draft'] == [{'title': 'Approach', 'body': 'Six weeks in three stages.'}])
with s.db() as cx: acts = {r[0] for r in cx.execute("SELECT action FROM activity")}
t('linking and restoring are in the activity log', {'proposal_versions_linked', 'proposal_version_restored'} <= acts)
