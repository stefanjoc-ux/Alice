"""The Activity page's picture: counts by area over time, the approval gate, blocks by rule, agents, models, heatmap."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import uuid
from datetime import datetime, timedelta, timezone
import substrate_store as s
s.init()
import activity_log as AL, agents as A
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

now = datetime.now(timezone.utc)
def add(action, days=0, hours=0, rule='human_review'):
    with s.db() as c:
        c.execute('INSERT INTO activity(created_at,action,target,rule,detail) VALUES (?,?,?,?,?)',
                  ((now - timedelta(days=days, hours=hours)).isoformat(), action, 'x', rule, ''))
with s.db() as c: base = c.execute('SELECT count(*) FROM activity').fetchone()[0]
for a in ['record_proposed'] * 5 + ['record_approved'] * 3 + ['record_rejected']: add(a, days=1)
for a in ['knowledge_proposed'] * 2 + ['knowledge_approved'] * 2: add(a, days=2)
add('rule_blocked', days=1, rule='secret_detection'); add('rule_blocked', days=1, rule='secret_detection'); add('rule_blocked', rule='protective_marking')
add('assistant_escalated'); add('tool_completed', days=3); add('org_fact_proposed', days=40)
with s.db() as c:
    for st in ('complete', 'complete', 'failed'):
        c.execute('INSERT INTO agent_runs(id,agent_id,trigger,started_at,status,cost_usd,calls) VALUES (?,?,?,?,?,?,?)',
                  (uuid.uuid4().hex, 'temple-review', 'x', now.isoformat(), st, 0.01, 1))
    c.execute('INSERT INTO model_usage(created_at,provider,model,workload,input_tokens,output_tokens,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?,?,?)',
              (now.isoformat(), 'openai', 'gpt-6-luna', 'Chat', 10, 5, 0.002, '{}'))

d = cl.get('/admin/api/activity-overview?preset=7d&tz=-60', headers=H).json()
t('daily buckets cover the period', d['unit'] == 'day' and 7 <= len(d['buckets']) <= 8)
t('everything in the period is counted, nothing older', d['totals']['events'] == base + 18 and not any(g['proposed'] for g in d['gate'] if g['name'] == 'Organisation facts'))
gate = {g['name']: g for g in d['gate']}
t('the approval gate counts proposals and your decisions', gate['Memories and decisions'] == {'name': 'Memories and decisions', 'proposed': 5, 'approved': 3, 'rejected': 1}
  and gate['Knowledge drafts']['approved'] == 2)
blocks = {b['name']: b['n'] for b in d['blocks']}
t('blocks are counted by rule name', blocks.get('Secret detection') == 2 and blocks.get('Protective marking guard') == 1 and blocks.get('Assistant question sent to a person') == 1)
t('blocks are kept out of the area stack', sum(b['blocks'] for b in d['buckets']) == 4 and d['totals']['blocked'] == 4)
t('areas add up', sum(sum(b[g['key']] for g in d['groups']) for b in d['buckets']) + 4 == d['totals']['events'])
ag = {a['id']: a for a in d['agents']}
t('agent runs and failures', ag['temple-review']['runs'] >= 3 and ag['temple-review']['failed'] >= 1 and d['totals']['failed_runs'] >= 1)
t('AI calls by model with a friendly name', any(m['name'] == 'GPT-6 Luna (OpenAI)' and m['calls'] >= 1 for m in d['models']))
t('the heatmap is 7 days by 24 hours and adds up', len(d['heat']) == 7 and all(len(r) == 24 for r in d['heat']) and sum(map(sum, d['heat'])) == d['totals']['events'])
h = cl.get('/admin/api/activity-overview?preset=today&tz=0', headers=H).json()
t('today is shown by hour', h['unit'] == 'hour' and len(h['buckets']) <= 25)
a = cl.get('/admin/api/activity-overview?preset=all', headers=H).json()
t('all time includes older activity', a['totals']['events'] > d['totals']['events'] and any(g['proposed'] for g in a['gate'] if g['name'] == 'Organisation facts'))
t('a time zone shifts the hours', cl.get('/admin/api/activity-overview?preset=7d&tz=-60', headers=H).json()['heat'] != cl.get('/admin/api/activity-overview?preset=7d&tz=300', headers=H).json()['heat'])
t('silly time zones are refused', cl.get('/admin/api/activity-overview?tz=99999', headers=H).status_code == 422)
c = cl.get('/admin/api/activity-overview?preset=custom&start=2020-01-01&end=2020-01-31', headers=H).json()
t('an empty period still draws', c['totals']['events'] == 0 and len(c['buckets']) == 31)
page = cl.get('/admin/activity').text
t('the Activity page has the picture and the log', 'id="av"' in page and 'activity-overview' in page and 'id="al-log"' in page)
