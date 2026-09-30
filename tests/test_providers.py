"""Provider errors are explained in plain words, and Check connections reports each provider."""
import _util
from _util import t
import httpx, openai, anthropic
from types import SimpleNamespace as NS
import app

req = httpx.Request('POST', 'https://api.openai.com/v1/responses')
def status_err(cls, code, msg):
    return cls(message=msg, response=httpx.Response(code, request=req, json={'error': {'message': msg}}), body={'error': {'message': msg}})
cases = [('connection', openai.APIConnectionError(request=req), 'Could not reach'),
         ('timeout', openai.APITimeoutError(request=req), 'took too long'),
         ('no model access', status_err(openai.NotFoundError, 404, 'The model `gpt-6-luna` does not exist'), 'Model unavailable'),
         ('no credit', status_err(openai.RateLimitError, 429, 'You exceeded your current quota'), 'credit exhausted'),
         ('bad key', status_err(openai.AuthenticationError, 401, 'Incorrect API key provided'), 'key rejected'),
         ('outage', status_err(openai.InternalServerError, 503, 'The server is overloaded.'), 'HTTP 503')]
for label, e, expect in cases:
    msg = app.provider_error(e)
    t(f'{label}: explained', expect in msg)
t("provider's own message included", 'does not exist' in app.provider_error(cases[2][1]))

class O:
    def __init__(s, **k): s.responses = s
    async def __aenter__(s): return s
    async def __aexit__(s, *a): pass
    async def create(s, **k): raise status_err(openai.NotFoundError, 404, 'The model `gpt-6-luna` does not exist or you do not have access to it.')
class B(NS): pass
class A:
    def __init__(s, **k): s.messages = s
    async def __aenter__(s): return s
    async def __aexit__(s, *a): pass
    async def create(s, **k): return NS(content=[B(type='text', text='Connected')], usage=None)
app.AsyncOpenAI = O; anthropic.AsyncAnthropic = A
from fastapi.testclient import TestClient
res = TestClient(app.app).post('/admin/api/providers/check', headers={'x-admin-token': app.ADMIN_TOKEN}).json()['results']
by = {r['provider']: r for r in res}
t('check connections: OpenAI problem reported', not by['OpenAI']['ok'] and 'Model unavailable' in by['OpenAI']['message'])
t('check connections: Anthropic connected', by['Anthropic']['ok'])
