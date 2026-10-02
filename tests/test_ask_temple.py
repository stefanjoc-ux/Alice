"""Ask Temple: read-only tools over real data, and the full question loop with real OpenAI response objects."""
import _util
from _util import t
import json
from types import SimpleNamespace as NS
from openai.types.responses import Response
import app, substrate_store as s, temple, temple_ask as T
temple.save_settings(False, 'openai')
rid = s._propose_original('Prefers short answers', 'Prefers short, direct answers', 'User said')['id']; s.review(rid, 'approved')
with s.db() as c:
    c.execute('INSERT INTO activity(created_at,action,target,rule,detail) VALUES (?,?,?,?,?)',
              (s.now(), 'rule_blocked', 'chat message', 'secret_detection', 'Blocked: Anthropic API key'))
r = T.run_tool('search_activity', {'type': 'blocks'})
t('tool: search blocks', r['total_matching'] == 1 and r['entries'][0]['what'] == 'Blocked: Secret detection')
t('tool: counts by type', T.run_tool('activity_counts', {'start': '2026-01-01', 'group_by': 'type'})['total'] >= 2)
t('tool: outstanding actions', 'total' in T.run_tool('outstanding_actions', {}))
t('tool: usage and costs', 'spending_caps' in T.run_tool('usage_and_costs', {'period': '7d'}))
import assistants as AS, agents as AG, proposals as PR
with s.db() as c:
    c.execute('INSERT INTO activity(created_at,action,target,rule,detail) VALUES (?,?,?,?,?)', (s.now(), 'assistant_answered', 'hr-policy', 'assistant', 'summaries: Leave'))
    c.execute('INSERT INTO activity(created_at,action,target,rule,detail) VALUES (?,?,?,?,?)', (s.now(), 'assistant_blocked', 'hr-policy', 'assistant', 'health'))
ao = T.run_tool('agents_overview', {})
t('tool: agents overview lists every agent with its group and status', any(x['id'] == 'parker' and x['group'] == 'Proposals' for x in ao['agents'])
  and all('status' in x for x in ao['agents']) and not any(x['id'] == 'temple-proposal-starter' for x in ao['agents']))
t('tool: agent runs by id or name', T.run_tool('agent_runs', {'agent': 'parker'})['agent'].startswith('Parker') and 'error' in T.run_tool('agent_runs', {'agent': 'nobody at all'}))
asv = T.run_tool('assistants_overview', {'days': 30})
alex = next(x for x in asv['assistants'] if x['id'] == 'hr-policy'); park = next(x for x in asv['assistants'] if x['id'] == 'proposal-writer')
t('tool: the team of assistants, with how they are used', alex['name'] == 'Alex' and alex['questions'] == {'answered': 1, 'blocked': 1}
  and park['type'] == 'proposal writer' and 'proposals_by_status' in park)
w = PR.save_form('proposal-writer', {'title': 'Fabric baseline', 'organisation': 'NSC', 'brief': 'Six weeks.'})
po = T.run_tool('proposals_overview', {'status': 'in_progress'})
t('tool: proposals in progress', po['shown'] == 1 and po['proposals'][0]['title'] == 'Fabric baseline' and po['proposals'][0]['status'] == 'in progress (form)')
t('Temple is told about agents, assistants and proposals', 'team of assistants' in T.PROMPT and 'agents' in T.PROMPT)

def resp(output):
    return Response.model_validate({'id': 'r', 'object': 'response', 'created_at': 0, 'model': 'gpt-6-luna', 'output': output,
        'parallel_tool_calls': True, 'tool_choice': 'auto', 'tools': [], 'status': 'completed',
        'usage': {'input_tokens': 5, 'output_tokens': 5, 'total_tokens': 10, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                  'output_tokens_details': {'reasoning_tokens': 0}}})
state = {'n': 0, 'sent': None}
class R:
    def create(self, **kw):
        state['n'] += 1
        if state['n'] == 1:
            return resp([{'type': 'function_call', 'id': 'fc', 'call_id': 'c1', 'name': 'search_activity', 'arguments': json.dumps({'type': 'blocks'}), 'status': 'completed'}])
        state['sent'] = kw['input']
        return resp([{'type': 'message', 'id': 'm', 'role': 'assistant', 'status': 'completed',
                      'content': [{'type': 'output_text', 'text': 'One secret was blocked.', 'annotations': []}]}])
class O:
    def __init__(s, **k): s.responses = R()
    def __enter__(s): return s
    def __exit__(s, *a): pass
import openai; openai.OpenAI = O
a = T.ask('What was blocked?')
t('answers after looking things up', a['answer'] == 'One secret was blocked.' and a['looked_at'] == ['search activity (type=blocks)'])
t('tool results sent back to the model', [m.get('type', m.get('role')) for m in state['sent']] == ['user', 'function_call', 'function_call_output'])
try: T.ask('my key is sk-ant-api03-' + 'Z' * 40); t('secret in a question refused', False)
except ValueError: t('secret in a question refused', True)
