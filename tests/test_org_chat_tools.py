"""Chat access to organisations and opportunities: list_organisations, search_opportunities, client separation."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, uuid
from datetime import datetime, timezone
import substrate_store as s
s.init()
import organisations as O, opportunities as OP, clients as C, rules_engine as R
import app, mcp_server as M

C.create_client('Glenmorrow Council', ['GC'])
C.create_client('Caledon Police', ['CP'])
O.create('Northfield University', 'university', 'A research university')
O.update('Glenmorrow Council', kind='council', description='Rural Highland council', website='https://glenmorrow.example.gov.uk', account_manager='Morven Hay')
O.update('Caledon Police', kind='police', account_manager='Callum Reid')
O.propose_fact('Glenmorrow Council', 'technology', 'Runs Microsoft 365 E3 across all staff since 2022.', 'Council website', 'https://glenmorrow.example.gov.uk/ict')
now = datetime.now(timezone.utc).isoformat(timespec='seconds')


def opp(org, title, status, offering, conf, notes=''):
    with s.db() as c:
        c.execute('INSERT INTO opportunities(id,org,title,summary,why_now,offering,size,confidence,next_step,timing,evidence,status,notes,created_at,updated_at,trigger) '
                  'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (uuid.uuid4().hex, org, title, title + ' summary.', 'Committee approved it.', offering, 'medium', conf, 'Book a workshop.', 'Q1',
                   json.dumps(['https://news.example.org/' + uuid.uuid4().hex[:6]]), status, notes, now, now, 'you'))


opp('Glenmorrow Council', 'Tenant consolidation', 'pursuing', 'Tenant migration and consolidation', 0.8, 'Spoke to the digital lead.')
opp('Glenmorrow Council', 'Copilot pilot', 'suggested', 'Copilot and AI adoption', 0.6)
opp('Caledon Police', 'Entra ID modernisation', 'suggested', 'Identity and access (Entra ID)', 0.7)
opp('Caledon Police', 'Old print contract', 'lost', 'Devices and licensing', 0.3)
opp('Northfield University', 'Fabric data platform', 'tracking', 'Data and analytics (Fabric, Power Platform)', 0.5)

# ---- list_organisations ----
L = M.list_organisations()
names = [o['name'] for o in L['organisations']]
t('lists every organisation', set(names) >= {'Glenmorrow Council', 'Caledon Police', 'Northfield University'})
g = next(o for o in L['organisations'] if o['name'] == 'Glenmorrow Council')
t('shows type, client flag, facts and open opportunities', g['kind'] == 'council' and g['client'] and g['approved_facts'] == 1 and g['open_opportunities'] == 2)
t('account managers are never returned to the model', 'Morven' not in json.dumps(L))
t('filter by kind', [o['name'] for o in M.list_organisations(kind='police')['organisations']] == ['Caledon Police'])
t('filter clients only', 'Northfield University' not in [o['name'] for o in M.list_organisations(clients_only=True)['organisations']])
t('filter by word', [o['name'] for o in M.list_organisations(query='highland')['organisations']] == ['Glenmorrow Council'])
t('only those with open opportunities', len(M.list_organisations(with_open_opportunities=True)['organisations']) == 3)

# ---- search_opportunities ----
r = M.search_opportunities()
t('open opportunities by default (lost left out)', r['matched'] == 4 and all(o['status'] in ('suggested', 'tracking', 'pursuing') for o in r['opportunities']))
t('counts include closed ones', r['counts'].get('lost') == 1)
t('evidence links included', all(o['evidence'] and o['evidence'][0].startswith('https://') for o in r['opportunities']))
t('sorted with suggestions first, then by confidence', [o['title'] for o in r['opportunities']][:2] == ['Entra ID modernisation', 'Copilot pilot'])
t('by organisation (partial name)', {o['title'] for o in M.search_opportunities(organisation='glenmorrow')['opportunities']} == {'Tenant consolidation', 'Copilot pilot'})
t('by offering', [o['title'] for o in M.search_opportunities(offering='entra')['opportunities']] == ['Entra ID modernisation'])
t('by words', [o['title'] for o in M.search_opportunities(query='fabric')['opportunities']] == ['Fabric data platform'])
t('all statuses', M.search_opportunities(status='all')['matched'] == 5)
t('one status', [o['title'] for o in M.search_opportunities(status='lost')['opportunities']] == ['Old print contract'])
t('by account manager, names not returned', [o['organisation'] for o in M.search_opportunities(account_manager='callum')['opportunities']] == ['Caledon Police']
  and 'Callum' not in json.dumps(M.search_opportunities(account_manager='callum')))
try: M.search_opportunities(status='maybe'); t('bad status refused', False)
except ValueError: t('bad status refused', True)
t('your notes reach Alice web chat', any(o.get('notes') == 'Spoke to the digital lead.' for o in M.search_opportunities(organisation='Glenmorrow Council')['opportunities']))
opp('Northfield University', 'Marked bid', 'tracking', 'Devices and licensing', 0.4, 'Login password: Hunter2-Secret-Key-99812!')
with s.db() as c: c.execute("UPDATE opportunities SET summary='OFFICIAL-SENSITIVE: draft bid figures.' WHERE title='Marked bid'")
r = M.search_opportunities(organisation='Northfield University')
t('protectively marked opportunities are withheld', 'Marked bid' not in [o['title'] for o in r['opportunities']] and 'withheld_by_rules' in r)
with s.db() as c: c.execute("UPDATE opportunities SET summary='Bid for devices.', notes='api_key=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD' WHERE title='Marked bid'")
r = M.search_opportunities(query='marked')
t('notes with a secret are withheld', r['opportunities'] and 'notes' not in r['opportunities'][0] and 'notes_withheld' in r['opportunities'][0])
with s.db() as c: c.execute("DELETE FROM opportunities WHERE title='Marked bid'")
t('no matches explains how to scan', 'scan' in M.search_opportunities(query='zzzz')['message'].lower())

# ---- external apps ----
M.CLIENT = 'Claude Desktop'
ext = M.search_opportunities(organisation='Glenmorrow Council')
t('external apps do not get your notes', ext['matched'] == 2 and not any('notes' in o for o in ext['opportunities']))
R.update_rule('client_separation', new_params={'strict': False, 'external': 'general'})
ext = M.list_organisations()
t("external 'general' mode hides client organisations", [o['name'] for o in ext['organisations']] == ['Northfield University'] and 'withheld' in ext)
ext = M.search_opportunities()
t("external 'general' mode hides client opportunities", [o['organisation'] for o in ext['opportunities']] == ['Northfield University'] and 'withheld' in ext)
M.CLIENT = ''

# ---- Alice web chat: tools offered and client separation ----
t('chat can use the organisation and opportunity tools', {'get_organisation', 'list_organisations', 'search_opportunities'} <= app.ALLOWED_TOOLS)


def wrap(d): return json.dumps([{'type': 'text', 'text': json.dumps(d)}])
def unwrap(o): return json.loads(json.loads(o)[0]['text'])


out = unwrap(C.filter_tool_output('search_opportunities', {}, wrap(M.search_opportunities()), 'Glenmorrow Council'))
t('a client chat sees only its client and non-client organisations',
  {o['organisation'] for o in out['opportunities']} == {'Glenmorrow Council', 'Northfield University'} and 'withheld_by_client_separation' in out and out['matched'] == 3)
out = unwrap(C.filter_tool_output('list_organisations', {}, wrap(M.list_organisations()), 'Caledon Police'))
t('client chat: other clients left out of the list', 'Glenmorrow Council' not in [o['name'] for o in out['organisations']])
out = unwrap(C.filter_tool_output('get_organisation', {}, wrap(M.get_organisation(name='Glenmorrow Council')), 'Caledon Police'))
t("client chat: another client's profile withheld", 'error' in out and 'profile' not in out)
out = unwrap(C.filter_tool_output('search_opportunities', {}, wrap(M.search_opportunities()), ''))
t('a general chat sees everything (non-strict)', out['matched'] == 4)
