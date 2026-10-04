"""Activity log entries have references (L-000123) and open as a standard information card: what happened, where
(happened in / logged by, as paths), when, who, why, related entries and technical details."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import app, substrate_store as s, rules_engine, activity_log as A
from fastapi.testclient import TestClient
cl = TestClient(app.app)
try: rules_engine.check_outbound('OFFICIAL-SENSITIVE briefing', 'hr-policy')
except ValueError: pass
with s.db() as c:
    s.audit(c, 'rule_blocked', 'Alex', 'rule_pack:hr_casework', 'HR team pack · Casework stays inside your tenant: test')
rows = cl.get('/admin/api/activity-log?preset=all').json()['rows']
t('every log row has a reference', all(r['ref'].startswith('L-') and len(r['ref']) == 8 for r in rows))
pack, block = rows[0], rows[1]
t('a rule pack block is headed by the safeguard\'s name', pack['label'] == 'Blocked: Casework stays inside your tenant')
t('a reference finds its entry', cl.get('/admin/api/activity-log?q=' + block['ref']).json()['total'] == 1)
c = cl.get('/admin/api/cards/log/' + block['ref']).json()
keys = [x['key'] for x in c['sections']]
t('the card has the standard sections in the standard order', keys == ['what', 'where', 'when', 'who', 'why', 'related', 'technical'])
where = {p['label']: [n['label'] for n in p['path']] for p in c['sections'][1]['paths']}
t('where it happened: Alice › Assistants › Alex', where['Happened in'] == ['Alice', 'Assistants', 'Alex'])
t('what logged it: Alice › Rules › Security › Protective marking guard', where['Logged by'] == ['Alice', 'Rules', 'Security', 'Protective marking guard'])
why = dict(next(x for x in c['sections'] if x['key'] == 'why')['rows'])
t('why: the rule, what it is for, and that it stopped', why['Triggered by'] == 'Enforced rule' and 'OFFICIAL-SENSITIVE' in why['What the rule is for'] and why['Outcome'].startswith('Stopped'))
t('a block is shown in the warning tone with links to the item and the rule', c['tone'] == 'bad' and [a['label'] for a in c['actions']] == ['Open Alex', 'Open the rule'])
pc = A.card(pack['ref'])
t('a pack block is logged by Rule packs › HR team pack › the safeguard', [n['label'] for n in pc['sections'][1]['paths'][1]['path']] == ['Alice', 'Rule packs', 'HR team pack', 'Casework stays inside your tenant'])
t('related: other entries about the same item', block['ref'] not in [i['ref'] for i in pc['sections'][5]['items']])
t('unknown reference: 404', cl.get('/admin/api/cards/log/L-999999').status_code == 404 and cl.get('/admin/api/cards/memory/M-0001').status_code == 404)
page = cl.get('/admin/activity').text
t('the page opens cards in a side panel and links to them', 'function openCard(' in page and 'ic-drawer' in page and "searchParams.set('log'" in page)
