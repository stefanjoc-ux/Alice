"""Provider errors everywhere: the provider's own reason (HTTP status and message, trimmed) is kept in the agent run, the
activity log and web.log and shown on screen, instead of the exception's name; no key and no request content is ever
kept. Also: conversations sent to Anthropic never start with an assistant turn or hold an empty message. Provider
calls are mocked throughout."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, logging
from types import SimpleNamespace as NS
import httpx, openai, anthropic
import substrate_store as s
s.init()
import provider_errors as PE, agents as A, temple, temple_chat, assistants as AS
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

KEY = 'sk-ant-api03-' + 'Qw1Er2Ty3Ui4Op5As6Df7Gh8'
def err(cls, status, msg, lib=anthropic):
    req = httpx.Request('POST', 'https://api.example/v1/messages')
    body = {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': msg}}
    return cls(f'Error code: {status}', response=httpx.Response(status, request=req), body=body)
CREDIT = err(anthropic.BadRequestError, 400, f'Your credit balance is too low to access the Anthropic API. Key {KEY}')

logged = []
class Grab(logging.Handler):
    def emit(self, rec): logged.append(rec.getMessage())
for name in ('alice.provider',):
    lg = logging.getLogger(name); lg.addHandler(Grab()); lg.setLevel(logging.WARNING); lg.propagate = False   # _util quietens the root logger

# 1. the formatter
d = PE.describe(CREDIT)
t('names the provider from the library that raised it', d['provider'] == 'claude' and d['name'] == 'Anthropic')
t('status and the provider\'s own message', d['text'].startswith('Anthropic rejected the request (HTTP 400): Your credit balance is too low'), )
t('a key in the message is removed', KEY not in d['text'] and '[removed]' in d['text'])
sent = 'Summarise the confidential board paper about the restructure'
d = PE.describe(err(anthropic.BadRequestError, 400, f'Could not process: {sent}'), sent=(sent,))
t('an echo of what was sent is removed', sent not in d['text'] and '[request]' in d['text'])
t('long messages are trimmed', len(PE.describe(err(anthropic.BadRequestError, 400, 'x' * 900))['detail']) <= PE.MAX_DETAIL)
d = PE.describe(err(openai.NotFoundError, 404, 'The model gpt-6-luna does not exist', openai))
t('OpenAI errors are named as OpenAI', d['text'].startswith('OpenAI says the model or feature is not available to this account (HTTP 404)'))
d = PE.describe(anthropic.APIConnectionError(request=httpx.Request('POST', 'https://x')))
t('connection failures are described plainly', d['text'].startswith('Could not reach Anthropic'))
t('only the libraries\' own errors count as provider errors', PE.is_provider_error(CREDIT) and not PE.is_provider_error(RuntimeError('x')))
d = PE.describe(err(anthropic.BadRequestError, 400, ''))
t('no message: the status alone, never "Error code: 400" twice', d['text'] == 'Anthropic rejected the request (HTTP 400)')

# 2. agent runs keep the provider message (any tracked agent)
@A.tracked('temple-review')
def failing(): raise CREDIT
try: failing()
except anthropic.BadRequestError: pass
run = [x for x in A.runs('temple-review')['runs'] if x['status'] == 'failed'][0]
e = A.run_detail(run['id'])['run']['error']
t('a failed agent run keeps the provider message, not the exception name', 'credit balance is too low' in e and 'HTTP 400' in e and KEY not in e)
t('web.log gets one line, without the key', any('credit balance' in x for x in logged) and not any(KEY in x for x in logged))

# 3. Temple's record review
class Refuses:
    def __init__(self, **k): self.messages = NS(create=self.create)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def create(self, **k): raise CREDIT
real = anthropic.Anthropic; anthropic.Anthropic = Refuses
# proposed with automatic review off: with it on, propose() starts a background review of the same record, and the direct
# review below would race it and correctly answer "A review is already running" (seen on PostgreSQL, where queries are slower)
temple.save_settings(False, 'claude')
rid = s.propose('Prefers short meetings', 'Stefan prefers meetings of 25 minutes.', 'Stefan said')['id']
temple.save_settings(True, 'claude')
try: out = temple.review_record(rid)
except Exception as x: out = {'error': repr(x)}
t('a failed Temple review records the provider message', out.get('status') == 'failed' and out['error'].startswith('Anthropic rejected the request (HTTP 400): Your credit balance')
  and KEY not in out['error'])
with s.db() as c: act = c.execute("SELECT detail FROM activity WHERE action='temple_failed' ORDER BY id DESC").fetchone()
t('and the activity log says why', act and 'credit balance is too low' in act['detail'] and KEY not in act['detail'])

# 4. Temple's chat suggestions
x = temple_chat._explain(CREDIT)
t('chat suggestions failure: the provider message', x.startswith('Anthropic rejected the request (HTTP 400): Your credit balance') and KEY not in x)

# 5. an assistant answering staff: the page gets the provider's reason
code, detail = app._assistant_error(CREDIT)
t('assistants and proposals: 502 with the provider message', code == 502 and detail.startswith('Anthropic rejected the request (HTTP 400): Your credit balance') and KEY not in detail)
y = app.provider_error(CREDIT)
t('chat errors: the status is shown with the message, no key', 'HTTP 400' in y and 'credit balance' in y and KEY not in y)
anthropic.Anthropic = real

# 6. conversations sent to Anthropic: never an assistant turn first, never an empty message
m = AS.claude_messages([{'role': 'assistant', 'content': 'Hello, how can I help?'}, {'role': 'user', 'content': '  '},
                        {'role': 'user', 'content': 'What is the leave policy?'}, {'role': 'assistant', 'content': ''},
                        {'role': 'user', 'content': 'And for part-time staff?'}])
t('leading assistant turns and empty messages are dropped', [x['role'] for x in m] == ['user', 'user'] and m[0]['content'] == 'What is the leave policy?')
sent_kw = []
class Records:
    def __init__(self, **k): self.messages = NS(create=self.create)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def create(self, **k):
        sent_kw.append(k); return NS(content=[NS(type='text', text='ok')], usage=NS(model_dump=lambda: {}), stop_reason='end_turn')
anthropic.Anthropic = Records
import usage_meter; real_log = usage_meter.log; usage_meter.log = lambda *a, **k: None
try: AS._call('claude_sonnet', 'sys', [{'role': 'assistant', 'content': 'Hi'}, {'role': 'user', 'content': 'Q'}])
finally: anthropic.Anthropic = real; usage_meter.log = real_log
k = sent_kw[0]
t('assistant calls send a user turn first', k['messages'] == [{'role': 'user', 'content': 'Q'}])
t('no sampling or thinking settings that Sonnet 5.5 / Opus 5.5 refuse', not ({'temperature', 'top_p', 'top_k', 'thinking'} & set(k)) and k['model'] == 'claude-sonnet-5-5')
