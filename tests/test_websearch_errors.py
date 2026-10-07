"""Web search failures: the provider's own message is kept and shown (never a key or what was sent), a refused request
(HTTP 4xx) is tried once with the other provider, the result says which provider produced it, and the calls match the
providers' current documentation. Provider calls are mocked throughout."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t as _t

def t(name, ok, info=''):
    _t(name, bool(ok))
    if not ok and info != '': print('     got:', str(info)[:400])
import json, logging, os
from types import SimpleNamespace as NS
import httpx, openai, anthropic
import substrate_store as s
s.init()
import organisations as O, org_research as OR, opportunities as OP, agents as A, temple
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'openai')

FAKE_KEY = 'sk-proj-' + 'Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4z'
PAGE = 'https://www.fallbackcouncil.gov.uk/plan'
REPLY = {'name': 'Fallback Council', 'kind': 'council', 'website': 'https://www.fallbackcouncil.gov.uk', 'description': 'A council.',
         'facts': [{'section': 'purpose', 'statement': 'Its plan for 2025-30 prioritises net zero.', 'source_url': PAGE, 'source_title': 'Plan'}]}

def http_error(cls, status, body):
    return cls(f'Error code: {status}', response=httpx.Response(status, request=httpx.Request('POST', 'https://api.example/v1')), body=body)

def openai_400(msg): return http_error(openai.BadRequestError, 400, {'error': {'message': msg, 'type': 'invalid_request_error'}})
def claude_400(msg): return http_error(anthropic.BadRequestError, 400, {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': msg}})

logged = []
class Grab(logging.Handler):
    def emit(self, rec): logged.append(rec.getMessage())
_lg = logging.getLogger('alice.websearch'); _lg.addHandler(Grab()); _lg.setLevel(logging.WARNING); _lg.propagate = False   # _util quietens the root logger

def runs_error():
    r = [x for x in A.runs('temple-org-research')['runs'] if x['status'] == 'failed']
    return A.run_detail(r[0]['id'])['run'].get('error', '') if r else ''

def activity(kind):
    with s.db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM activity WHERE action=? ORDER BY id DESC', (kind,))]

# 1. the provider's message is kept and shown, scrubbed of keys and of what was sent
calls = []
def openai_refuses(prompt, query, provider, workload='x'):
    calls.append(provider)
    if provider == 'openai':
        raise openai_400(f"Web search is not supported with reasoning effort 'none'. Key {FAKE_KEY} was used for: {query}")
    raise claude_400('Web search is not enabled for this organisation.')
OR._ask = openai_refuses
r = cl.post('/admin/api/organisations/research', json={'name': 'Fallback Council'}, headers=H)
d = r.json().get('detail', '')
t('a refused search is a clear 400, not a server error', r.status_code == 400)
t('the page says which provider refused it and what it said',
  d.startswith('OpenAI rejected the web search request (HTTP 400): Web search is not supported with reasoning effort'), d)
t('the other provider was tried once, and its answer is shown too', calls == ['openai', 'claude'] and 'Tried Anthropic instead' in d and 'not enabled' in d, d)
t('no key in what is shown', FAKE_KEY not in d and 'sk-proj' not in d and '[removed]' in d)
t('what was sent is not echoed back', 'Research this organisation' not in d and '[request]' in d)
err = runs_error()
t('the agent run keeps the provider message', 'HTTP 400' in err and 'reasoning effort' in err and FAKE_KEY not in err, err)
row = activity('org_research_failed')
t('the activity log keeps the provider message', row and 'reasoning effort' in row[0]['detail'] and FAKE_KEY not in row[0]['detail'], row and row[0]['detail'])
t('web.log gets a line per failure, without the key', len([x for x in logged if 'failed with' in x]) == 2
  and all(FAKE_KEY not in x and 'Research this organisation' not in x for x in logged), logged)

# 2. fallback: OpenAI refuses, Anthropic answers; the result says so
calls.clear(); logged.clear()
def openai_refuses_claude_answers(prompt, query, provider, workload='x'):
    calls.append(provider)
    if provider == 'openai': raise openai_400('Unsupported parameter.')
    return json.dumps(REPLY), {PAGE: 'Plan'}
OR._ask = openai_refuses_claude_answers
r = cl.post('/admin/api/organisations/research', json={'name': 'Fallback Council'}, headers=H).json()
t('fallback to the other provider produces the result', calls == ['openai', 'claude'] and r.get('proposed') == 1, r)
t('the result says which provider produced it, and why', r['provider'] == 'claude' and r['provider_name'] == 'Anthropic'
  and 'searched with Anthropic because OpenAI rejected the web search request (HTTP 400): Unsupported parameter' in r['summary'], r['summary'])
runs_hist = cl.get('/admin/api/organisations/research?org=Fallback Council').json()['runs']
t('the recorded run names the provider that answered', runs_hist[0]['provider'] == 'claude' and runs_hist[0]['status'] == 'complete')
t('web.log notes the fallback', any('answered by Anthropic' in x for x in logged), logged)

# 3. no fallback: a server error (5xx) is not retried with the other provider
calls.clear()
def openai_500(prompt, query, provider, workload='x'):
    calls.append(provider); raise http_error(openai.InternalServerError, 500, {'error': {'message': 'The server had an error.'}})
OR._ask = openai_500
d = cl.post('/admin/api/organisations/research', json={'name': 'Fallback Council'}, headers=H).json()['detail']
t('a 5xx is reported plainly and not retried elsewhere', calls == ['openai'] and 'OpenAI had an error answering the web search request (HTTP 500)' in d, d)

# 4. no fallback when the other provider has no key
calls.clear(); saved = os.environ.pop('ANTHROPIC_API_KEY')
OR._ask = openai_refuses
d = cl.post('/admin/api/organisations/research', json={'name': 'Fallback Council'}, headers=H).json()['detail']
os.environ['ANTHROPIC_API_KEY'] = saved
t('without the other key, only the first provider is tried', calls == ['openai'] and 'Tried Anthropic' not in d, d)

# 5. the other provider never gets material its rules refuse
calls.clear()
import rules_engine
real_check = rules_engine.check_outbound
def refuse_claude(text, target='chat message', provider=None, packs=True):
    if provider == 'claude': raise rules_engine.RuleViolation('Not sent: provider not allowed.')
    return real_check(text, target, provider, packs)
rules_engine.check_outbound = refuse_claude
d = cl.post('/admin/api/organisations/research', json={'name': 'Fallback Council'}, headers=H).json()['detail']
rules_engine.check_outbound = real_check
t('a fallback the rules refuse is not attempted; the first failure is shown', calls == ['openai'] and d.startswith('OpenAI rejected'), d)

# 6. other failures: key rejected, timeout, unknown exception (its text is not shown)
f = OR._failure(http_error(openai.AuthenticationError, 401, {'error': {'message': f'Incorrect API key provided: {FAKE_KEY}.'}}), 'openai')
t('401: the key is named as the problem, never shown', f['text'].startswith('OpenAI did not accept the API key (HTTP 401)') and FAKE_KEY not in f['text'], f)
f = OR._failure(anthropic.APITimeoutError(request=httpx.Request('POST', 'https://x')), 'claude')
t('timeout described plainly', f['text'].startswith('Anthropic took too long to answer the web search'), f)
f = OR._failure(RuntimeError('internal ' + FAKE_KEY), 'claude')
t('an unexpected error shows its type only', f['text'] == 'The web search request to Anthropic did not complete (RuntimeError)', f)
f = OR._failure(openai_400('x' * 500), 'openai')
t('long provider messages are trimmed', len(f['detail']) <= 220)

# 7. opportunity scans use the same search, fallback and messages
OR._ask = openai_refuses
r = cl.post('/admin/api/opportunities/scan', json={'org': 'Fallback Council'}, headers=H)
t('a failed scan is a 400 with the provider message', r.status_code == 400 and r.json()['detail'].startswith('OpenAI rejected the web search request (HTTP 400)'), r.text)
row = activity('opportunity_scan_failed')
t('a failed scan is in the activity log, without the key', row and 'HTTP 400' in row[0]['detail'] and FAKE_KEY not in row[0]['detail'])
def scan_fallback(prompt, query, provider, workload='x'):
    if provider == 'openai': raise openai_400('Unsupported parameter.')
    return json.dumps({'news': [], 'opportunities': [], 'checks': []}), {}
OR._ask = scan_fallback
r = cl.post('/admin/api/opportunities/scan', json={'org': 'Fallback Council'}, headers=H).json()
t('a scan falls back too and says which provider answered', r.get('provider') == 'claude' and 'searched with Anthropic because OpenAI rejected' in r['summary'], r)

# 8. nothing secret anywhere it was recorded
with s.db() as c:
    dump = json.dumps([dict(x) for x in c.execute('SELECT * FROM activity')]) + json.dumps([dict(x) for x in c.execute('SELECT * FROM org_research')]) \
        + json.dumps([dict(x) for x in c.execute('SELECT * FROM agent_runs')]) + json.dumps([dict(x) for x in c.execute('SELECT * FROM org_watch')])
t('the key appears in no log, run or table', FAKE_KEY not in dump and FAKE_KEY not in ' '.join(logged))

# 9. the provider calls themselves match the current documentation
seen_kwargs = {}
class FakeOpenAI:
    def __init__(self, **k): self.responses = NS(create=self.create)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def create(self, **k):
        seen_kwargs['openai'] = k
        return NS(output=[NS(action=NS(sources=[NS(url=PAGE, title='Plan')]), content=None)], output_text='{}', usage=None)
real_openai = openai.OpenAI; openai.OpenAI = FakeOpenAI
import usage_meter; real_log = usage_meter.log; usage_meter.log = lambda *a, **k: None
try: text, seen = OR._ask_openai('p', 'q')
finally: openai.OpenAI = real_openai
k = seen_kwargs['openai']
t('OpenAI: web_search tool with sources included', k['tools'] == [{'type': 'web_search'}] and k['include'] == ['web_search_call.action.sources'] and seen == {PAGE: 'Plan'})
t('OpenAI: reasoning is on (web search does not run with effort none)', k.get('reasoning', {}).get('effort') not in (None, 'none', 'minimal'))

class Block(NS):
    def model_dump(self, **k): return {x: y for x, y in vars(self).items() if not x.startswith('_')}
pages = [NS(content=[Block(type='server_tool_use', id='s1', name='web_search', input={'query': 'x'}),
                     Block(type='web_search_tool_result', tool_use_id='s1', content=[NS(url=PAGE, title='Plan')])], stop_reason='pause_turn'),
         NS(content=[Block(type='text', text='{"name":"X"}', citations=None)], stop_reason='end_turn')]
sent = []
class FakeAnthropic:
    def __init__(self, **k): self.messages = NS(create=self.create)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def create(self, **k): sent.append(k); return pages[len(sent) - 1]
real_anth = anthropic.Anthropic; anthropic.Anthropic = FakeAnthropic
try: text, seen = OR._ask_claude('p', 'q')
finally: anthropic.Anthropic = real_anth; usage_meter.log = real_log
t('Anthropic: basic web search tool for Haiku 4.5', sent[0]['tools'][0]['type'] == 'web_search_20250305' and sent[0]['model'] == 'claude-haiku-4-5-20251001')
t('Anthropic: a paused turn is sent back to continue', len(sent) == 2 and sent[1]['messages'][1]['role'] == 'assistant'
  and sent[1]['messages'][1]['content'][0]['type'] == 'server_tool_use' and text == '{"name":"X"}' and seen == {PAGE: 'Plan'})
