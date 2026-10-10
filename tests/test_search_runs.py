"""Temple explains and steers organisation research and opportunity scans: each run's record (searches, sources, found, rejected
with reasons) is kept for 90 days; Ask Temple sees only that run and that organisation and changes nothing; research guidance per
organisation is versioned, used on the next run, and needs Stefan's approval when Temple suggests it; secrets, markings and other
clients' names are refused. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
from datetime import datetime, timedelta, timezone
import substrate_store as s
s.init()
import app, organisations as O, org_research as OR, opportunities as OP, clients as C, temple, temple_discuss, search_runs as SR, actions, agents
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'claude')
C.create_client('Example Council', ['EC'])
C.create_client('Rival Borough', ['RB'])
O.propose_fact('Example Council', 'technology', 'Uses Microsoft 365 across the council since 2021.', 'Council website', 'https://www.examplecouncil.gov.uk/ict')
O.create('Other Trust', 'other', 'A fictional trust.')

N1, N2, N3 = ('https://www.examplecouncil.gov.uk/news/digital-strategy', 'https://www.publiccontractsscotland.gov.uk/notice/123',
              'https://www.examplecouncil.gov.uk/about')
SCAN = {'news': [{'title': 'Council approves new digital strategy', 'url': N1, 'published': '2026-09-20', 'summary': 'Cloud first.'}],
        'opportunities': [
            {'title': 'Identity platform tender', 'summary': 'Procuring identity and access.', 'why_now': 'Tender published.', 'offering': 'Identity and access (Entra ID)',
             'size': 'medium', 'confidence': 0.8, 'next_step': 'Download the pack.', 'timing': 'before 30 Nov', 'evidence': [N2]},
            {'title': 'Unevidenced idea', 'summary': 'They might want devices.', 'confidence': 0.6, 'evidence': ['https://made-up.example/y']},
            {'title': 'Weak hunch', 'summary': 'Possibly something.', 'confidence': 0.1, 'offering': 'Devices and licensing', 'evidence': [N1]}],
        'considered': [{'title': 'School laptops', 'reason': 'outside_profile', 'note': 'Schools buy their own devices.'}],
        'searches': ['Example Council digital strategy 2026', 'Example Council tender identity']}
RESEARCH = {'name': 'Example Council', 'kind': 'council', 'website': 'https://www.examplecouncil.gov.uk',
            'facts': [{'section': 'purpose', 'statement': 'Its council plan runs to 2029 with a digital first theme.', 'source_url': N3, 'source_title': 'About'},
                      {'section': 'identity', 'statement': 'A made up fact.', 'source_url': 'https://made-up.example/z'},
                      {'section': 'gossip', 'statement': 'Not a public section.', 'source_url': N3}],
            'searches': ['Example Council about']}
CALLS = []


def fake(prompt, query, provider, workload='x'):
    CALLS.append((prompt, query, provider, workload))
    OR._ran('provider-reported search ' + str(len(CALLS)))
    data = SCAN if 'opportunit' in workload.lower() else RESEARCH
    return json.dumps(data), {N1: 'Digital strategy', N2: 'Notice 123', N3: 'About the council'}


OR._ask = fake

# ---------------- the record of an opportunity scan ----------------
r = cl.post('/admin/api/opportunities/scan', json={'org': 'Example Council'}, headers=H).json()
t('the scan returns its run id', r.get('run_id'))
run = SR.get(r['run_id'])
rec = run['record']
t('the record keeps what Alice sent and the searches the provider ran', rec['queries'][0]['sent'].startswith('Organisation: Example Council')
  and rec['queries'][0]['searches'] == ['provider-reported search 1'])
t('…and the sources returned, cited or not', {x['url'] for x in rec['sources']} == {N1, N2, N3} and any(x['cited'] for x in rec['sources']))
t('found: the evidenced opportunity', [x['title'] for x in rec['found']] == ['Identity platform tender'])
codes = {x['title']: x['code'] for x in rec['rejected']}
t('rejected with reasons: no citation, below relevance, and Temple\'s own judgement (outside the profile)', codes.get('Unevidenced idea') == 'no_citation'
  and codes.get('Weak hunch') == 'low_relevance' and codes.get('School laptops') == 'outside_profile'
  and any('Temple\'s judgement' in x['reason'] for x in rec['rejected']))
r2 = OP.scan('Example Council')
codes2 = {x['title']: x['code'] for x in SR.get(r2['run_id'])['record']['rejected']}
t('a repeat is recorded as a duplicate', codes2.get('Identity platform tender') == 'duplicate')
d = cl.get('/admin/api/organisations/searches?org=Example Council').json()
t('the page lists both runs with counts and reasons', len(d['runs']) == 2 and d['runs'][0]['counts']['sources'] == 3
  and any(x['code'] == 'duplicate' for x in d['runs'][0]['rejected_by_reason']))

# a scan that finds nothing is recorded too
SCAN_SAVED = dict(SCAN)
SCAN.update({'opportunities': [], 'considered': [], 'news': []})
r3 = OP.scan('Example Council')
t('a scan with no opportunities found is recorded', SR.get(r3['run_id'])['record']['found'] == [] and SR.get(r3['run_id'])['summary'].startswith('0 new'))
SCAN.update(SCAN_SAVED)

# the rules check on suggestions is the Rules page's own: on = left out and logged as a block, off = not applied here either
import rules_engine as RE
SECRET_IDEA = {'title': 'Key rotation help', 'summary': 'Their key sk-ant-api03-' + 'K' * 90 + ' was published.', 'why_now': 'Leak.',
               'offering': 'Cyber security and compliance', 'confidence': 0.9, 'evidence': [N1]}
MARKED_IDEA = {'title': 'Records review', 'summary': 'OFFICIAL-SENSITIVE papers mention a records review.', 'why_now': 'Papers.',
               'offering': 'Data and analytics (Fabric, Power Platform)', 'confidence': 0.9, 'evidence': [N1]}
SCAN['opportunities'] = SCAN_SAVED['opportunities'] + [SECRET_IDEA, MARKED_IDEA]
ra = SR.get(OP.scan('Example Council')['run_id'])['record']
rcodes = {x['title']: x for x in ra['rejected']}
t('with both rules on, a suggestion holding a secret or a marking is left out as a rules failure', rcodes.get('Key rotation help', {}).get('code') == 'rules'
  and rcodes.get('Records review', {}).get('code') == 'rules' and 'Secret detection' in rcodes['Key rotation help']['reason'])
with s.db() as c:
    blocks = [r_[0] for r_ in c.execute("SELECT target FROM activity WHERE action='rule_blocked' AND target LIKE 'opportunity suggestion%'")]
t('…and each is logged as a block, like every other rule block', len(blocks) >= 2)
RE.update_rule('secret_detection', enabled=False, reason='Test: rules off'); RE.update_rule('protective_marking', enabled=False, reason='Test: rules off')
rb = SR.get(OP.scan('Example Council')['run_id'])['record']
t('switched off on the Rules page, neither filter applies here either', {'Key rotation help', 'Records review'} <= {x['title'] for x in rb['found']})
RE.update_rule('protective_marking', enabled=True, new_params={'markings': ['SECRET']}, reason='Test: one marking')
with s.db() as c: c.execute("DELETE FROM opportunities WHERE title IN ('Key rotation help','Records review')")
rc_ = SR.get(OP.scan('Example Council')['run_id'])['record']
t('the marking check follows the rule\'s own list of markings', 'Records review' in {x['title'] for x in rc_['found']})
RE.update_rule('secret_detection', enabled=True, reason='Test: back on'); RE.update_rule('protective_marking', new_params={'markings': ['OFFICIAL-SENSITIVE', 'SECRET', 'TOP SECRET']}, reason='Test: back to the default')
with s.db() as c: c.execute("DELETE FROM opportunities WHERE title IN ('Key rotation help','Records review')")
SCAN.update(SCAN_SAVED)

# ---------------- the record of organisation research ----------------
rr = cl.post('/admin/api/organisations/research', json={'name': 'Example Council'}, headers=H).json()
rec = SR.get(rr['run_id'])['record']
rc = {x['title']: x['code'] for x in rec['rejected']}
t('research: found and rejected with reasons (no citation, outside the profile)', len(rec['found']) == 1
  and rc.get('A made up fact.') == 'no_citation' and rc.get('Not a public section.') == 'outside_profile')
rr2 = OR.research('Example Council')
t('research: a fact already on the profile is a duplicate', any(x['code'] == 'duplicate' for x in SR.get(rr2['run_id'])['record']['rejected']))

# a failed run is recorded
def failing(prompt, query, provider, workload='x'):
    raise ValueError('boom')
OR._ask = failing
try: OP.scan('Example Council'); ok = False
except ValueError: ok = True
OR._ask = fake
t('a failed scan is recorded with its error', ok and SR.runs('Example Council')[0]['status'] == 'failed')

# kept 90 days
with s.db() as c: c.execute('UPDATE search_runs SET created_at=? WHERE id=?', ((datetime.now(timezone.utc) - timedelta(days=91)).isoformat(), r['run_id']))
OP.scan('Example Council')
t('records older than 90 days are dropped', r['run_id'] not in [x['id'] for x in SR.runs('Example Council', 50)])

# ---------------- research guidance ----------------
t('guidance is limited to 1,000 characters', cl.put('/admin/api/organisations/guidance', json={'org': 'Example Council', 'text': 'x' * 1001}, headers=H).status_code == 400)
t('guidance holding a secret is refused', cl.put('/admin/api/organisations/guidance', json={'org': 'Example Council', 'text': 'Use sk-ant-api03-' + 'A' * 90}, headers=H).status_code == 400)
t('guidance holding a protective marking is refused', cl.put('/admin/api/organisations/guidance', json={'org': 'Example Council', 'text': 'OFFICIAL-SENSITIVE notes'}, headers=H).status_code == 400)
x = cl.put('/admin/api/organisations/guidance', json={'org': 'Example Council', 'text': 'Compare them with Rival Borough.'}, headers=H)
t('guidance naming another client is refused (client separation)', x.status_code == 400 and 'Rival Borough' in x.json()['detail'])
t('…for a non-client organisation too', cl.put('/admin/api/organisations/guidance', json={'org': 'Other Trust', 'text': 'Compare them with Rival Borough.'}, headers=H).status_code == 400)
RE.update_rule('client_separation', enabled=False)
t('with Client separation switched off on the Rules page, that check is off here too',
  cl.put('/admin/api/organisations/guidance', json={'org': 'Other Trust', 'text': 'Compare them with Rival Borough.'}, headers=H).status_code == 200)
RE.update_rule('client_separation', enabled=True)
t('…its own name and aliases are fine', cl.put('/admin/api/organisations/guidance', json={'org': 'Example Council', 'text': 'Focus on EC digital programmes.'}, headers=H).status_code == 200)
g = cl.put('/admin/api/organisations/guidance', json={'org': 'Example Council', 'text': 'Focus on the Council Plan digital programmes and Public Contracts Scotland notices.'}, headers=H).json()
t('Stefan\'s edit is saved as a new version with who and when', g['version'] == 2 and g['history'][0]['created_by'] and g['history'][0]['via'] == 'you')
r4 = OP.scan('Example Council')
t('the next scan uses the guidance, fenced below the rules, and records its version', 'Public Contracts Scotland notices' in CALLS[-1][0]
  and 'USER GUIDANCE' in CALLS[-1][0] and CALLS[-1][0].index('Rules:') < CALLS[-1][0].index('USER GUIDANCE') and SR.get(r4['run_id'])['guidance_version'] == 2)
rr3 = OR.research('Example Council')
t('…and so does the next research run', 'Public Contracts Scotland notices' in CALLS[-1][0] and SR.get(rr3['run_id'])['guidance_version'] == 2)
from datetime import date
core = OP.PROMPT.format(today=date.today().isoformat(), days=OP.NEWS_DAYS, max_opps=OP.MAX_OPPS, offerings='; '.join(OP.offerings()))
t('the core prompt, with its citation requirement, is unchanged: guidance is only added after it', CALLS[-2][0].startswith(core)
  and 'No opportunity without evidence' in core)

# ---------------- Ask Temple about a run ----------------
SENT = []
def coach(provider, system, messages):
    SENT.append((system, messages))
    return ('Nothing about cloud migration came back: the searches focused on the strategy and the tender, and the one idea about devices had no citation.\n'
            'Suggested guidance:\nFocus on the Council Plan digital programmes, cloud migration and Public Contracts Scotland notices.\nWhy: The last scan missed cloud work.'), 'claude-haiku-4-5-20251001'
temple_discuss._complete = coach
OP.scan('Other Trust')                                            # another organisation's run, which Temple must not see
rid = r4['run_id']
before = SR.current('Example Council')
a = cl.post(f'/admin/api/search-runs/{rid}/discussion', json={'message': 'Why was nothing found about their cloud migration?'}, headers=H)
payload = SENT[-1][1][0]['content']
t('Ask Temple answers about the run', a.status_code == 200 and 'cloud migration' in a.json()['reply'] and 'Suggested guidance' not in a.json()['reply'])
t('Temple sees that run\'s record and the organisation\'s profile and guidance', 'Identity platform tender' in payload and 'Microsoft 365 across the council' in payload
  and 'Public Contracts Scotland notices' in payload and json.loads(payload.split('\n', 1)[1])['run']['guidance_version_used'] == 2)
other_ids = [x['id'] for x in SR.runs('Other Trust')]
t('…and nothing from other runs or other organisations', 'Other Trust' not in payload and not any(i in payload for i in other_ids)
  and payload.count('"sent"') == 1)
t('talking changes nothing: the guidance is the same until Stefan approves', SR.current('Example Council') == before)
gid = a.json()['guidance_suggestion']
ov = cl.get('/admin/api/organisations/searches?org=Example Council').json()['guidance']
t('Temple\'s suggestion waits for approval, and shows on Actions', gid and ov['proposals'][0]['id'] == gid
  and next(x for x in actions.summary()['sections'] if x['key'] == 'guidance')['count'] == 1)
ap = cl.post(f'/admin/api/organisations/guidance/{gid}', json={'action': 'approve'}, headers=H).json()
t('approved: saved as a new version, marked as Temple\'s, with who approved it', ap['version'] == 3 and ap['history'][0]['via'] == 'temple' and ap['history'][0]['created_by']
  and 'cloud migration' in ap['text'])
t('a decided suggestion cannot be decided again', cl.post(f'/admin/api/organisations/guidance/{gid}', json={'action': 'reject'}, headers=H).status_code == 400)
r5 = OP.scan('Example Council')
t('run again uses the approved guidance', 'cloud migration and Public Contracts' in CALLS[-1][0] and SR.get(r5['run_id'])['guidance_version'] == 3)
t('the discussion is kept with the run', len(cl.get(f'/admin/api/search-runs/{rid}/discussion').json()['messages']) == 2)
def coach_other(provider, system, messages):
    return 'Try comparing.\nSuggested guidance:\nCompare with Rival Borough procurement.\nWhy: test', 'claude-haiku-4-5-20251001'
temple_discuss._complete = coach_other
a2 = cl.post(f'/admin/api/search-runs/{rid}/discussion', json={'message': 'Anything else?'}, headers=H).json()
t('Temple cannot suggest guidance naming another client: it is not kept', not a2['guidance_suggestion'] and 'not kept' in a2['messages'][-1]['content'])
rej_before = SR.current('Example Council')
def coach_again(provider, system, messages):
    return 'Maybe.\nSuggested guidance:\nOnly look at housing.\nWhy: test', 'claude-haiku-4-5-20251001'
temple_discuss._complete = coach_again
g2 = cl.post(f'/admin/api/search-runs/{rid}/discussion', json={'message': 'And?'}, headers=H).json()['guidance_suggestion']
cl.post(f'/admin/api/organisations/guidance/{g2}', json={'action': 'reject'}, headers=H)
t('a rejected suggestion changes nothing', SR.current('Example Council') == rej_before)
t('a message holding a secret is not sent to Temple', cl.post(f'/admin/api/search-runs/{rid}/discussion', json={'message': 'key sk-ant-api03-' + 'B' * 90}, headers=H).status_code == 400)
t('Ask Temple about runs is its own agent, in Clients and opportunities', agents._AGENT_GROUP.get('temple-search-discuss') == 'clients')
with s.db() as c:
    acts = {r_[0] for r_ in c.execute("SELECT action FROM activity WHERE action LIKE 'research_guidance%' OR action='temple_search_chat'")}
t('guidance changes and discussions are logged', {'research_guidance_saved', 'research_guidance_proposed', 'research_guidance_approved', 'research_guidance_rejected', 'temple_search_chat'} <= acts)
t('the Organisations page renders', cl.get('/admin/organisations').status_code == 200)
