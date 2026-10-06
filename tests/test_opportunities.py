"""Client opportunities: scans (on request and on schedule), evidence checks, the tracker, schedule and offerings."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
from datetime import datetime, timedelta, timezone
import substrate_store as s
s.init()
import organisations as O, org_research as OR, opportunities as OP, agents as A, temple, clients as C
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'claude')
C.create_client('Example Council', ['EC'])
O.propose_fact('Example Council', 'technology', 'Uses Microsoft 365 across the council since 2021.', 'Council website', 'https://www.examplecouncil.gov.uk/ict')
O.propose_fact('Example Council', 'relationship', 'Internal note: open discussion about a managed service.', 'Account plan', label='local')

N1, N2, N3 = ('https://www.examplecouncil.gov.uk/news/digital-strategy', 'https://www.publiccontractsscotland.gov.uk/notice/123',
              'https://www.bbc.co.uk/news/scotland-cyber')
REPLY = {'news': [
    {'title': 'Council approves new digital strategy', 'url': N1, 'published': '2026-09-20', 'summary': 'A five-year strategy with cloud first.'},
    {'title': 'Tender: identity and access platform', 'url': N2, 'published': '2026-09-25', 'summary': 'Closes 30 November.'},
    {'title': 'Invented article', 'url': 'https://made-up.example/x', 'published': '2026-09-01'}],
    'opportunities': [
    {'title': 'Identity platform tender', 'summary': 'The council is procuring an identity and access platform. Contact procurement@examplecouncil.gov.uk.',
     'why_now': 'Tender published on Public Contracts Scotland, closing 30 November.', 'offering': 'identity and access (entra id)', 'size': 'medium',
     'confidence': 0.8, 'next_step': 'Download the tender pack and book a bid/no-bid.', 'timing': 'before 30 Nov', 'evidence': [N2]},
    {'title': 'Cloud-first strategy support', 'summary': 'The new strategy commits to cloud first.', 'why_now': 'Strategy approved in September.',
     'offering': 'Azure cloud and infrastructure', 'size': 'large', 'confidence': 1.7, 'next_step': 'Offer a strategy workshop.', 'evidence': [N1, N3]},
    {'title': 'Unevidenced idea', 'summary': 'They might want devices.', 'evidence': ['https://made-up.example/y']}]}
SEEN = {N1: 'Digital strategy', N2: 'Notice 123', N3: 'Cyber news'}
calls = []
def fake(prompt, query, provider, workload='x'):
    calls.append((prompt, query, provider, workload)); return json.dumps(REPLY), dict(SEEN)
OR._ask = fake

# 1. run now
r = cl.post('/admin/api/opportunities/scan', json={'org': 'Example Council'}, headers=H).json()
t('scan on request: two evidenced opportunities, invented one dropped', r['opportunities'] == 2 and any('No evidence' in d['reason'] for d in r['dropped']))
t('news from pages the search returned is stored; invented article is not', r['news'] == 2)
q = calls[-1][1]
t('the scan reads the approved profile', 'Microsoft 365 across the council' in q)
t('local-only facts never reach the model', 'managed service' not in q)
t('usage is labelled as an opportunity scan', calls[-1][3] == 'Temple opportunity scan')
tr = cl.get('/admin/api/opportunities').json()
ops = {o['title']: o for o in tr['opportunities']}
t('opportunities arrive as suggestions', tr['counts']['suggested'] == 2 and all(o['status'] == 'suggested' for o in ops.values()))
t('contact details stripped from the text', 'procurement@' not in ops['Identity platform tender']['summary'] and '[email removed]' in ops['Identity platform tender']['summary'])
t('offering matched to your list; confidence kept between 0 and 1', ops['Identity platform tender']['offering'] == 'Identity and access (Entra ID)' and ops['Cloud-first strategy support']['confidence'] == 1.0)
t('evidence links kept, only those the search returned', ops['Cloud-first strategy support']['evidence'] == [N1, N3])
t('latest news listed', {n['url'] for n in tr['news']} == {N1, N2})

# 2. running again: no duplicates
r2 = OP.scan('Example Council')
t('a second scan does not repeat known opportunities or news', r2['opportunities'] == 0 and r2['news'] == 0)
t('the model is told what is already known', 'Identity platform tender' in calls[-1][1])

# 3. tracking
oid = ops['Identity platform tender']['id']
cl.put('/admin/api/opportunities/' + oid, json={'status': 'pursuing', 'notes': 'Bid/no-bid on Friday.'}, headers=H)
o = [x for x in cl.get('/admin/api/opportunities?status=pursuing').json()['opportunities'] if x['id'] == oid][0]
t('status and notes saved', o['status'] == 'pursuing' and o['notes'] == 'Bid/no-bid on Friday.')
t('unknown status refused', cl.put('/admin/api/opportunities/' + oid, json={'status': 'maybe'}, headers=H).status_code == 400)
t('changes need the admin token', cl.put('/admin/api/opportunities/' + oid, json={'status': 'won'}).status_code in (401, 403))
t('filter by organisation', all(x['org'] == 'Example Council' for x in cl.get('/admin/api/opportunities?org=Example Council').json()['opportunities']))

# 4. schedule
w = {x['org']: x for x in OP.watch_list()}
t('clients are watched weekly by default', w['Example Council']['frequency'] == 'weekly' and w['Example Council']['is_client'])
cl.post('/admin/api/opportunities/schedule', json={'org': 'Example Council', 'frequency': 'monthly'}, headers=H)
t('frequency saved', {x['org']: x for x in OP.watch_list()}['Example Council']['frequency'] == 'monthly')
with s.db() as c: c.execute("UPDATE org_watch SET next_run=? WHERE org='Example Council'", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),))
t('a past next run is due', 'Example Council' in OP.due())
done = OP.run_due()
nw = {x['org']: x for x in OP.watch_list()}['Example Council']
t('the scheduler scans what is due and books the next slot about a month on', done and nw['next_run'] > (datetime.now(timezone.utc) + timedelta(days=29)).isoformat())
t('scheduled runs are marked as such', calls and len(done) == 1)
O.create('Fresh Trust', 'charity')
cl.post('/admin/api/opportunities/schedule', json={'org': 'Fresh Trust', 'frequency': 'weekly'}, headers=H)
t('a newly watched organisation waits for its first weekly slot', 'Fresh Trust' not in OP.due())
cl.post('/admin/api/opportunities/schedule', json={'org': 'Example Council', 'frequency': 'off'}, headers=H)
with s.db() as c: c.execute("UPDATE org_watch SET next_run=? WHERE org='Example Council'", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),))
t('switched off: never due', 'Example Council' not in OP.due())

# 5. safety and the agent
A.set_status('temple-opportunities', 'paused', 'test')
res = OP.run_due()
cl.post('/admin/api/opportunities/schedule', json={'org': 'Fresh Trust', 'frequency': 'weekly'}, headers=H)
with s.db() as c: c.execute("UPDATE org_watch SET next_run=? WHERE org='Fresh Trust'", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),))
n_before = len(calls); OP.run_due()
t('a paused agent does not scan on schedule (and does not crash the scheduler)', len(calls) == n_before and
  {x['org']: x for x in OP.watch_list()}['Fresh Trust']['last_status'] == 'skipped')
A.set_status('temple-opportunities', 'active')
runs = A.runs('temple-opportunities')['runs']
t('scans appear on the Agents page with what they wrote', runs and A.run_detail([x for x in runs if x['status'] == 'complete'][-1]['id'])['touched'].get('wrote', {}).get('opportunity') == 2)
t('scans record the web pages they read', A.run_detail([x for x in runs if x['status'] == 'complete'][-1]['id'])['touched'].get('read', {}).get('web', 0) >= 1)
t('unknown organisation refused', cl.post('/admin/api/opportunities/scan', json={'org': 'Nobody'}, headers=H).status_code == 400)
O.create('OFFICIAL-SENSITIVE Unit', 'other')
n_before = len(calls)
t('a marked request never reaches the model', cl.post('/admin/api/opportunities/scan', json={'org': 'OFFICIAL-SENSITIVE Unit'}, headers=H).status_code == 400 and len(calls) == n_before)

# 6. offerings and the page
x = cl.put('/admin/api/opportunities-offerings', json={'offerings': ['Copilot and AI adoption', '', 'Tenant migration']}, headers=H).json()
t('offerings saved (blanks ignored)', x['offerings'] == ['Copilot and AI adoption', 'Tenant migration'] and OP.offerings() == x['offerings'])
t('at least one offering needed', cl.put('/admin/api/opportunities-offerings', json={'offerings': ['  ']}, headers=H).status_code == 400)
page = cl.get('/admin/organisations').text
t('page has the slide-out tracker and the scan controls', 'id="opp-drawer"' in page and 'id="o-opp-scan"' in page)
import actions
sec = {x['key']: x for x in actions.summary()['sections']}
t('suggested opportunities appear in Actions', 'opportunities' in sec and sec['opportunities']['count'] == cl.get('/admin/api/opportunities').json()['counts']['suggested'])

# ---- keeping opportunities fresh ----
open_ = [o for o in OP.tracker()['opportunities'] if o['status'] in ('suggested', 'tracking', 'pursuing') and o['org'] == 'Example Council']
ids = {o['title']: o['id'] for o in open_}
idp, cloud = ids.get('Identity platform tender'), ids.get('Cloud-first strategy support')
if idp and cloud:
    OP.update(cloud, status='tracking'); OP.update(idp, status='suggested')
    N4 = 'https://www.publiccontractsscotland.gov.uk/notice/123/award'
    REPLY_CHECK = {'news': [{'title': 'Contract awarded: identity platform', 'url': N4, 'published': '2026-10-01', 'summary': 'Awarded.'}], 'opportunities': [],
                   'checks': [{'id': idp[:8], 'state': 'closed', 'note': 'The tender was awarded to another supplier on 1 October.', 'evidence': [N4]},
                              {'id': cloud[:8], 'state': 'changed', 'note': 'The strategy now starts in April, not January.', 'evidence': ['https://not-returned.example/z']},
                              {'id': 'deadbeef', 'state': 'closed', 'note': 'invented id', 'evidence': [N4]}]}
    def fake2(prompt, query, provider, workload='x'):
        calls.append((prompt, query, provider, workload)); return json.dumps(REPLY_CHECK), {**SEEN, N4: 'Award notice'}
    OR._ask = fake2
    r = OP.scan('Example Council')
    q = calls[-1][1]
    t('open opportunities are sent to be re-checked, by short id', 'OPEN OPPORTUNITIES TO CHECK' in q and idp[:8] in q and cloud[:8] in q)
    tr = {o['id']: o for o in OP.tracker()['opportunities']}
    t('a closed suggestion, with evidence from the search, is dismissed with the reason', tr[idp]['status'] == 'dismissed'
      and tr[idp]['notes'].startswith('Closed: The tender was awarded') and tr[idp]['freshness'] == 'closed' and tr[idp]['freshness_evidence'] == [N4])
    t('a change without evidence from the search is not believed (stays live, checked)', tr[cloud]['freshness'] == 'live'
      and tr[cloud]['status'] == 'tracking' and tr[cloud]['last_checked'])
    t('scan summary counts the checks', r['checked'] == 2 and r['closed'] == 1 and 'open checked' in r['summary'])
    REPLY_CHECK['checks'] = [{'id': cloud[:8], 'state': 'closed', 'note': 'Programme cancelled at committee.', 'evidence': [N4]}]
    OP.scan('Example Council')
    tr = {o['id']: o for o in OP.tracker()['opportunities']}
    t('a closed opportunity you are tracking is only flagged: your call', tr[cloud]['status'] == 'tracking' and tr[cloud]['freshness'] == 'closed')
else:
    t('fresh-check setup found the open opportunities', False)

# stale suggestions
import uuid as _u
old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
sid, lid = _u.uuid4().hex, _u.uuid4().hex
with s.db() as c:
    for i_, title_, fr, lc in [(sid, 'Old idea nobody touched', '', None), (lid, 'Old idea still live', 'live', s.now())]:
        c.execute("INSERT INTO opportunities(id,org,title,summary,status,created_at,updated_at,last_checked,freshness) VALUES (?,?,?,?,?,?,?,?,?)",
                  (i_, 'Example Council', title_, 'x', 'suggested', old, old, lc, fr))
t('expiry setting defaults to 30 days', OP.expire_days() == 30)
n = OP.expire_stale()
tr = {o['id']: o for o in OP.tracker()['opportunities']}
t('a suggestion nobody acted on goes stale and is dismissed', tr[sid]['status'] == 'dismissed' and 'Went stale' in tr[sid]['notes'])
t('one a scan recently confirmed as live does not', tr[lid]['status'] == 'suggested')
r = cl.put('/admin/api/opportunities-expiry', json={'days': 0}, headers=H)
t('expiry can be switched off', r.status_code == 200 and OP.expire_days() == 0 and OP.expire_stale() == 0)
t('expiry route needs the admin token', cl.put('/admin/api/opportunities-expiry', json={'days': 30}).status_code in (401, 403))

# the watch tick box
C.create_client('Watch Council', ['WC'])
OP.set_watch('Watch Council', False)
t('unticked: not watched', [w for w in OP.watch_list() if w['org'] == 'Watch Council'][0]['frequency'] == 'off')
OP.set_watch('Watch Council', True)
w = [w for w in OP.watch_list() if w['org'] == 'Watch Council'][0]
t('ticked: watched weekly with a first slot', w['frequency'] == 'weekly' and w['next_run'])
import activity_log
t('activity labels for freshness', all(a in activity_log.LABELS for a in ('opportunity_closed', 'opportunity_changed', 'opportunity_expired')))

# one scheduler only, even with two revisions running
t('this process takes the schedule lease', OP._lease())
with s.db() as c:
    c.execute("UPDATE scheduler_lease SET holder='another-revision', expires_at=? WHERE name='opportunities'", ((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),))
t('while another process holds it, this one does not run the schedule', not OP._lease() and OP.run_due() == [])
with s.db() as c:
    c.execute("UPDATE scheduler_lease SET expires_at=? WHERE name='opportunities'", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),))
t('a lapsed lease is taken over', OP._lease())
r = cl.get('/healthz')
t('health probe answers without data', r.status_code == 200 and r.json()['ok'] is True and set(r.json()) == {'ok', 'database'})
t('hovering over Watched shows when Alice last checked and when she checks next', 'watchInfo' in cl.get('/admin/organisations').text
  and 'Next run:' in cl.get('/admin/organisations').text)
