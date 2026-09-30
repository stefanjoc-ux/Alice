"""Saved conversations from Claude apps and Temple whole-chat review, with quote checks and client inheritance."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,time,uuid
import substrate_store as s, temple, clients as C, conversations as V
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
C.create_client('Fife Council',['Fife'])
import app, mcp_server as M
from fastapi.testclient import TestClient
cl=TestClient(app.app);H={'x-admin-token':app.ADMIN_TOKEN}
# 1. Claude Desktop saves a conversation
M.CLIENT='Claude Desktop'
r=M.save_conversation(title='Planning the Fife tenant pilot',summary='We planned the Fife tenant consolidation pilot: twenty mailboxes first, then batches of two hundred, with a rollback plan agreed.',
    key_points=['Pilot first','Batches of 200'],decisions=['Start with 20 mailboxes'],
    remember=['I prefer pilots of twenty mailboxes before any bulk migration'],user_quotes=['always pilot on a small group first','I want a rollback plan for every batch'])
print('   tool reply:',r['message'][:150])
cid=r['id']
chat=cl.get('/chats/'+cid).json()
t('stored as a chat from Claude Desktop with the summary', chat['source']=='Claude Desktop' and 'twenty mailboxes' in json.loads(chat['summary'])['summary'])
t('client detected from content', C.chat_client(cid)=='Fife Council')
props=s.organised_records('proposed')['records']
t('"remember" item became a memory proposal tagged to the client', any('pilots of twenty' in p['content'] for p in props) and C.client_of('memory',[p for p in props if 'pilots of twenty' in p['content']][0]['id'])=='Fife Council')
t('not in the chat sidebar', cid not in [c['id'] for c in s.active_chats()])
a=cl.get('/admin/api/archive?flag=external').json();t('on the Archive page under From Claude apps', [c['id'] for c in a['chats']]==[cid] and a['external']==1)
t('counts as captured (a memory was proposed)', a['chats'][0]['captured'])
t('duplicate save detected', M.save_conversation(title='Planning the Fife tenant pilot',summary='We planned the Fife tenant consolidation pilot: twenty mailboxes first, then batches of two hundred, with a rollback plan agreed.')['message']=='This conversation was already saved.')
try: M.save_conversation(title='Keys',summary='We set up the deployment and the key is sk-proj-'+'z'*48+' which goes in the pipeline.');t('secret in a conversation refused',False)
except ValueError as e: t('secret in a conversation refused: '+str(e)[:55],True)
# 2. Temple whole-chat review of the saved conversation (model mocked)
def fake(payload):
    return json.dumps({'suggestions':[
        {'kind':'memory','title':'Rollback plans','content':'Wants a rollback plan for every migration batch','quote':'I want a rollback plan for every batch','reason':'Stated preference'},
        {'kind':'knowledge','title':'Pilot method','content':'Pilot on a small group before bulk moves','quote':'always pilot on a small group first','reason':'Reusable method'},
        {'kind':'memory','title':'Invented','content':'Likes Sonnet','quote':'I love Sonnet best','reason':'assistant said so'}]}),'openai'
V._ask=fake
res=V.review_chat(cid,manual=True);print('   review:',res)
t('two grounded suggestions saved, invented quote dropped', res['suggestions']==2 and res['dropped']==1)
sug=cl.get('/admin/api/temple/suggestions?status=pending',headers=H).json()
t('suggestions appear in Temple → Chat suggestions', sug['counts']['pending']==2)
# accept the memory suggestion: inherits the chat client
sid=[x for x in sug['items'] if x['kind']=='memory'][0]['id']
acc=cl.post('/admin/api/temple-suggestions/'+sid,json={'action':'accept','content':'Wants a rollback plan for every migration batch'},headers=H).json()
t('accepted suggestion becomes a proposal tagged Fife', C.client_of('memory',acc['target'])=='Fife Council')
kid=[x for x in sug['items'] if x['kind']=='knowledge'][0]['id']
acc=cl.post('/admin/api/temple-suggestions/'+kid,json={'action':'accept','content':'Pilot on a small group before bulk moves'},headers=H).json()
import knowledge as K;m=K.meta([acc['target']])[acc['target']]
t('accepted knowledge is a client-confidential note', m['kind']=='note' and m['label']=='client' and C.client_of('file',acc['target'])=='Fife Council')
# 3. whole-chat review of an Alice chat: quotes checked against your messages
ac=s.create_chat()['id']
with s.db() as c:
    for u,rp in [('I only work from the Blairgowrie office on Fridays','Noted.'),('Can you draft the agenda?','Here it is.')]:
        c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)",(uuid.uuid4().hex,ac,u,rp,'openai','complete',s.now()))
V._ask=lambda p: (json.dumps({'suggestions':[{'kind':'memory','title':'Office days','content':'Works from the Blairgowrie office on Fridays','quote':'only work from the Blairgowrie office on Fridays','reason':'fact'},{'kind':'memory','title':'From assistant','content':'x','quote':'Here it is.','reason':'assistant text'}]}),'openai')
res=V.review_chat(ac,manual=True);t('Alice chat review keeps your quote, drops the assistant\'s', res['suggestions']==1 and res['dropped']==1)
# 4. never send marked material to Temple
mc=s.create_chat()['id']
with s.db() as c: c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)",(uuid.uuid4().hex,mc,'OFFICIAL-SENSITIVE\nbid numbers','ok','openai','complete',s.now()))
called=[];V._ask=lambda p: called.append(1)
res=V.review_chat(mc,manual=True);t('marked chat blocked, Temple never called', res['status']=='blocked' and not called)
# 5. bulk review of flagged archived chats
with s.db() as c: c.execute("UPDATE chats SET updated_at='2026-01-01T00:00:00+00:00' WHERE id IN (?,?)",(ac,mc))
x=cl.post('/admin/api/archive/temple-review-flagged',headers=H).json();print('   bulk started:',x)
