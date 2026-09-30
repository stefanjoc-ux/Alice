"""Auto routing and Temple skip a provider that has just failed, then return to it."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,json,uuid,time
from types import SimpleNamespace as NS
import httpx, openai, anthropic
calls=[]
class B(NS):
    def model_dump(self,exclude_none=True): return dict(vars(self))
class AM:
    async def create(self,**kw):
        calls.append(kw['model'])
        if 'routing' in (kw.get('system') or ''): return NS(content=[B(type='text',text='{"tier":"light","reason":"casual"}')],usage=None)
        return NS(content=[B(type='text',text='Answer from '+kw['model'])],usage=None)
class FA:
    def __init__(s,**k): s.messages=AM()
    async def __aenter__(s): return s
    async def __aexit__(s,*a): pass
anthropic.AsyncAnthropic=FA
import app, router, temple
temple.save_settings(False,'openai')
class R:
    async def create(self,**kw):
        calls.append(kw['model']); raise openai.APITimeoutError(request=httpx.Request('POST','https://api.openai.com'))
class O:
    def __init__(s,**k): s.responses=R()
    async def __aenter__(s): return s
    async def __aexit__(s,*a): pass
class M:
    def __init__(s,*a,**k): pass
    async def __aenter__(s): return s
    async def __aexit__(s,*a): pass
    async def list_tools(s): return [NS(name=n,description='',inputSchema={'type':'object'}) for n in app.ALLOWED_TOOLS]
app.AsyncOpenAI=O;app.Client=M
from fastapi.testclient import TestClient
cl=TestClient(app.app)
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
def ask(text):
    calls.clear();cid=cl.post('/chats').json()['id']
    cl.post('/chat',json={'chat_id':cid,'request_id':uuid.uuid4().hex,'text':text,'provider':'auto'})
    return cl.get('/chats/'+cid).json()['turns'][0]
a=ask('hi there, quick status please')
t('1st message: Luna times out, Sonnet answers', a['model']=='claude-sonnet-5-5' and 'gpt-6-luna' in calls)
print('   label:',a['route'])
b=ask('thanks, and another quick one')
t('next message skips Luna and goes straight to Haiku', b['model']=='claude-haiku-4-5-20251001' and 'gpt-6-luna' not in calls)
print('   label:',b['route'])
t('Temple uses Haiku while Luna is failing', temple.reviewer()=='claude' and temple.settings()['provider']=='openai')
router._failures['openai']=time.time()-601
t('after 10 minutes Luna is tried again', temple.reviewer()=='openai')
c=ask('ok one more')
t('Auto routes light messages back to Luna', 'gpt-6-luna' in calls)
