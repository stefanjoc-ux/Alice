"""Temple's in-chat analysis: tolerant parsing, per-suggestion quote checks, specific failure messages."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,uuid
import substrate_store as s, temple, temple_chat as TC
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
cid=s.create_chat()['id'];tid=uuid.uuid4().hex
with s.db() as c: c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)",(tid,cid,'I  prefer   short answers in the morning. We will keep the carport roof clear.','Noted.','openai','complete',s.now()))
state={'reply':'','exc':None}
class R: usage=None
class O:
    def __init__(s_,**k): s_.responses=s_
    def create(s_,**k):
        if state['exc']: raise state['exc']
        r=R();r.output_text=state['reply'];return r
    def __enter__(s_): return s_
    def __exit__(s_,*a): pass
import openai;openai.OpenAI=O
def run(reply=None,exc=None):
    state['reply']=reply or '';state['exc']=exc
    with s.db() as c: c.execute('DELETE FROM temple_chat_jobs');c.execute('DELETE FROM temple_suggestions')
    TC.reserve(cid,tid,True);TC.analyse(cid,tid);p=TC.panel(cid);return p['jobs'][0],p['suggestions']
sug=lambda q,k='memory',title='t',rel=None:{'kind':k,'title':title,'content':'c '+title,'quote':q,'quote_turn':tid,'reason':'r','related_ids':rel or []}
fenced='```json\n'+json.dumps({'suggestions':[sug('i prefer short answers in the morning',title='a'),sug('I never said this',title='b'),sug('keep the carport roof clear','decision','c',['unknown-memory-id']),sug('short answers',title='d'),sug('in the morning',title='e'),{'kind':'weird'}]})+'\n```'
job,items=run(fenced)
print('   coverage:',job['coverage'])
t('fenced JSON accepted', job['status']=='complete')
t('quote with different spacing/case accepted', any(i['title']=='a' for i in items))
t('bad quote dropped alone, not the batch', not any(i['title']=='b' for i in items) and len(items)==4)
t('unknown memory reference ignored rather than failing', any(i['title']=='c' for i in items))
t('malformed item dropped, and the list kept to 4', len(items)==4 and 'dropped' in job['coverage'])
job,_=run('Sorry, I cannot help with that.');t('non-JSON reply explained: '+job['error'][:40], job['status']=='failed' and 'valid JSON' in job['error'])
class AuthenticationError(Exception): pass
class RateLimitError(Exception): pass
class APITimeoutError(Exception): pass
job,_=run(exc=AuthenticationError('401'));t('auth failure explained: '+job['error'][:45], 'key was rejected' in job['error'])
job,_=run(exc=RateLimitError('429'));t('credit/rate limit explained', 'credit' in job['error'])
job,_=run(exc=APITimeoutError('t'));t('timeout explained', 'too long' in job['error'])
job,_=run(json.dumps({'suggestions':[]}));t('nothing to suggest is a success, not an error', job['status']=='complete')
