"""GPT-6 Astra in chat: chosen by hand only, correct model and reasoning, no images, priced correctly, not used by Auto."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import uuid
from types import SimpleNamespace as NS
import app, router, usage_meter, rule_packs
import substrate_store as s

seen = []
class B(NS):
    def model_dump(self, exclude_none=True): return dict(vars(self))
class R:
    async def create(self, **kw):
        seen.append(kw)
        return NS(output=[B(type='message', content=[])], output_text='Answer from ' + kw['model'],
                  usage=NS(model_dump=lambda: {'input_tokens': 1000, 'output_tokens': 500, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}))
class O:
    def __init__(s_, **k): s_.responses = R()
    async def __aenter__(s_): return s_
    async def __aexit__(s_, *a): pass
class M:
    def __init__(s_, *a, **k): pass
    async def __aenter__(s_): return s_
    async def __aexit__(s_, *a): pass
    async def list_tools(s_): return [NS(name=n, description='', inputSchema={'type': 'object'}) for n in app.ALLOWED_TOOLS]
app.AsyncOpenAI = O; app.Client = M
from fastapi.testclient import TestClient
cl = TestClient(app.app)

def ask(text, provider, images=False):
    seen.clear(); cid = cl.post('/chats').json()['id']
    r = cl.post('/chat', json={'chat_id': cid, 'request_id': uuid.uuid4().hex, 'text': text, 'provider': provider, 'images': images})
    return r, cl.get('/chats/' + cid).json()['turns'][0]

r, turn = ask('Explain zero trust in two sentences.', 'openai_astra')
t('Astra is selectable in chat and answers', r.status_code == 200 and turn['reply'] == 'Answer from gpt-6-astra')
t('Astra uses its own reasoning setting (it has no "none")', seen and seen[0]['model'] == 'gpt-6-astra' and seen[0]['reasoning'] == {'effort': 'medium'})
t('Astra gets room for reasoning tokens', seen[0]['max_output_tokens'] == 8000)
r, turn = ask('Explain zero trust in two sentences.', 'openai')
t('GPT-6 Luna is unchanged', seen[0]['model'] == 'gpt-6-luna' and seen[0]['reasoning'] == {'effort': 'none'} and seen[0]['max_output_tokens'] == 2400)
r, turn = ask('Draw a lighthouse', 'openai_astra', images=True)
t('image generation refused clearly for Astra', not seen and 'not set up for GPT-6 Astra' in (turn.get('error') or turn.get('reply') or r.text))
with s.db() as c:
    row = c.execute("SELECT estimate_usd FROM model_usage WHERE model='gpt-6-astra' ORDER BY id DESC LIMIT 1").fetchone()
t('usage priced at Astra rates ($10 in, $50 out per million)', row and abs(row[0] - (1000 * 10 + 500 * 50) / 1e6) < 1e-9)
import inspect
t('Auto never routes or retries to Astra', 'openai_astra' not in inspect.getsource(router.route) and
  all(router.fallback_for(x, im) != 'openai_astra' for x in ('openai', 'grok', 'claude') for im in (False, True)))
t('the chat page offers GPT-6 Astra', 'value="openai_astra"' in cl.get('/').text)
t('rule packs treat Astra as OpenAI', rule_packs._live_provider('openai_astra')['name'].startswith('OpenAI'))
t('labelled for routing notes', router.LABEL['openai_astra'] == 'GPT-6 Astra')
t('the image button explains why it is off for Astra', 'not set up for GPT-6 Astra' in cl.get('/').text)
