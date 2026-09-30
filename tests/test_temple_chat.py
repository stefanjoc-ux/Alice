"""Temple's in-chat suggestions, including decisions, accepted from the chat panel."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,uuid
import substrate_store as s, temple, temple_chat as TC
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
cid=s.create_chat()['id'];tid=uuid.uuid4().hex
with s.db() as c: c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)",(tid,cid,'Right, we will keep the gulet business on hold until spring, the numbers do not work yet','Understood.','openai','complete',s.now()))
out={'suggestions':[{'kind':'decision','title':'Gulet business on hold','content':'Keep the gulet charter business on hold until spring','quote':'we will keep the gulet business on hold until spring','quote_turn':tid,'reason':'Explicit decision','rationale':'The numbers do not work yet','options':[],'revisit':'Spring'}]}
class R:
    output_text=json.dumps(out);usage=None
class O:
    def __init__(s_,**k): s_.responses=s_
    def create(s_,**k): return R()
    def __enter__(s_): return s_
    def __exit__(s_,*a): pass
import openai;openai.OpenAI=O
t('reserve',TC.reserve(cid,tid,True));TC.analyse(cid,tid)
p=TC.panel(cid);d=[x for x in p['suggestions'] if x['kind']=='decision']
t('in-chat Temple suggests a decision in the editable format', len(d)==1 and d[0]['content']=='Decision: Keep the gulet charter business on hold until spring\nWhy: The numbers do not work yet\nRevisit when: Spring')
import app
from fastapi.testclient import TestClient
cl=TestClient(app.app);H={'x-admin-token':app.ADMIN_TOKEN}
r=cl.post('/admin/api/temple-suggestions/'+d[0]['id'],json={'action':'accept','content':d[0]['content']},headers=H).json()
k=s.record_kinds([r['target']])[r['target']]
t('accepting from the chat panel creates a decision memory', k['kind']=='decision' and k['decision']['revisit']=='Spring')
# other kinds still behave exactly as before
out['suggestions']=[{'kind':'memory','title':'Numbers first','content':'Checks the numbers before committing to a business','quote':'the numbers do not work yet','quote_turn':tid,'reason':'Preference'}]
R.output_text=json.dumps(out);tid2=tid
with s.db() as c: c.execute("DELETE FROM temple_chat_jobs")
TC.reserve(cid,tid,True);TC.analyse(cid,tid)
m=[x for x in TC.panel(cid)['suggestions'] if x['kind']=='memory'][0]
r=cl.post('/admin/api/temple-suggestions/'+m['id'],json={'action':'accept','content':m['content']},headers=H).json()
t('memory suggestions unchanged', s.record_kinds([r['target']]).get(r['target'],{}).get('kind','fact')=='fact' and any(x['id']==r['target'] for x in s.organised_records('proposed')['records']))
R.output_text=json.dumps({'suggestions':[{'kind':'decision','title':'x','content':'Invented decision','quote':'I never said this','quote_turn':tid,'reason':'r'}]})
with s.db() as c: c.execute("DELETE FROM temple_chat_jobs")
TC.reserve(cid,tid,True);TC.analyse(cid,tid)
j=TC.panel(cid)['jobs'][0];t('unverifiable quote: that suggestion is dropped, the run still completes', j['status']=='complete' and 'not found in your words' in j['coverage'])
