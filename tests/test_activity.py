"""Activity log: labels, types, names, date filters, search and CSV."""
import _util
from _util import t
import app, substrate_store as s, activity_log as A
rid = s._propose_original('Fife bid approach', 'Lead with consolidation', 'User said')['id']
s.review(rid, 'approved')
with s.db() as c:
    for when, action, target, rule, detail in [
            (s.now(), 'rule_blocked', 'chat message', 'secret_detection', 'Blocked: Anthropic API key'),
            (s.now(), 'rule_blocked', 'grok', 'provider_allow', '1 memories withheld'),
            (s.now(), 'client_created', 'Fife Council', 'human_control', 'Fife'),
            ('2026-06-01T10:00:00+00:00', 'record_approved', 'x', 'human_review', 'old decision'),
            ('2026-08-15T10:00:00+00:00', 'knowledge_added', 'y', 'human_review', 'august note'),
            (s.now(), 'some_new_code', 't', 'r', 'unmapped')]:
        c.execute('INSERT INTO activity(created_at,action,target,rule,detail) VALUES (?,?,?,?,?)', (when, action, target, rule, detail))
d = A.query(preset='all')
t('types counted', d['counts'].get('blocks') == 2 and d['counts'].get('clients') == 1)
t('blocks headline the rule', [r['label'] for r in A.query(kind='blocks', preset='all')['rows']][-1] == 'Blocked: Secret detection')
t('IDs resolved to names', any(r['target_name'] == 'Memory: Fife bid approach' for r in d['rows']))
t('last 7 days excludes older entries', A.query(preset='7d')['total_all'] == d['total_all'] - 2)
t('custom range', A.query(preset='custom', start='2026-08-01', end='2026-08-31')['total'] == 1)
t('search by label', A.query(preset='all', q='client added')['total'] == 1)
t('search by rule name', A.query(preset='all', q='secret detection')['total'] == 1)
t('unknown codes still readable', [r['label'] for r in A.query(kind='other', preset='all')['rows']] == ['Some new code'])
csv = A.to_csv(kind='blocks', preset='all').splitlines()
t('CSV export', csv[0].startswith('Time (UTC),Type,What happened') and len(csv) == 3)
