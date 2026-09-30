"""Client separation: aliases, tagging and precedence, per-chat filtering, strict mode, Claude Desktop scope, inheritance."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,base64
import substrate_store as s, rules_engine as R, temple, clients as C
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
# migration: old guidance row becomes enforced
with s.db() as c: c.execute("UPDATE rules SET kind='guidance',params='{}' WHERE id='client_separation'")
R._init();t('client separation migrated to enforced', R.rule('client_separation')['kind']=='enforced' and R.rule('client_separation')['params']=={'strict':False,'external':'all'})
C.create_client('Fife Council',['Fife','FC']);C.create_client('Scottish Borders Council',['Borders','SBC'])
t('detect alias',C.detect('Draft the Fife business case')==['Fife Council'])
t('detect short alias case-sensitive', C.detect('FC wants a call')==['Fife Council'] and C.detect('the fc of stuff')==[])
t('no match inside words', C.detect('Fifer and Bordersville')==[])
t('two clients detected', sorted(C.detect('Compare Fife with Borders'))==['Fife Council','Scottish Borders Council'])
# memories and files
def mem(t_,c_): r=s._propose_original(t_,c_,'User said');s.review(r['id'],'approved');return r['id']
f1=mem('Fife pricing','Fife discount is 12% on licences'); b1=mem('Borders pricing','Borders rate card at 9% margin'); g1=mem('Azure landing zone','Preferred hub-spoke pattern with Entra')
x1=mem('Tenant migration lesson','Always pilot mailbox moves on a small group first')
import app
with app.connect_db() as con:
    for fid,name,text in [('a'*32,'fife.txt','Fife Council tender notes'),('b'*32,'borders.txt','Borders proposal draft'),('c'*32,'azure.txt','Azure design notes')]:
        con.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",(fid,name,fid+'h',b'x',text,'s','2026-09-01',1))
# tagging pass: aliases first, then Temple for the rest (mocked)
C._ask=lambda p: json.dumps({'assignments':[{'type':i['type'],'id':i['id'],'client':'Fife Council' if 'pilot' in i['content'] else None,'confidence':0.6,'reason':'mentions a Fife pilot?'} for i in json.loads(p)['items']]})
r=C.run_tagging(manual=True);print('   tagging:',r)
own=C.clients_for('memory',[f1,b1,g1,x1]);t('alias-tagged Fife/Borders memories, Azure stays General', own.get(f1)=='Fife Council' and own.get(b1)=='Scottish Borders Council' and not own.get(g1))
t('unsure Temple match became a suggestion, not a tag', not own.get(x1) and C.items('memory','__suggested__')['total']==1)
t('files alias-tagged', C.clients_for('file',['a'*32,'b'*32,'c'*32])=={'a'*32:'Fife Council','b'*32:'Scottish Borders Council','c'*32:''})
# precedence
C.tag('memory',[g1],'Fife Council','human');C.tag('memory',[g1],'Scottish Borders Council','temple');t('human tag beats automatic', C.client_of('memory',g1)=='Fife Council')
C.tag('memory',[g1],'','human')
# enforcement filter
out=lambda payload: json.dumps([{'type':'text','text':json.dumps(payload)}])
recs=out({'records':[{'id':f1,'title':'Fife pricing'},{'id':b1,'title':'Borders pricing'},{'id':g1,'title':'Azure landing zone'}]})
seen=lambda o,key='records':[x.get('title') or x.get('name') or x.get('file_id') for x in json.loads(json.loads(o)[0]['text'])[key]]
t('Fife chat: Borders memory withheld', seen(C.filter_tool_output('search_records',{},recs,'Fife Council'))==['Fife pricing','Azure landing zone'])
t('untagged chat: everything visible', len(seen(C.filter_tool_output('search_records',{},recs,'')))==3)
files=out({'files':[{'id':'a'*32,'name':'fife.txt'},{'id':'b'*32,'name':'borders.txt'},{'id':'c'*32,'name':'azure.txt'}]})
t('Fife chat: Borders file hidden from list_files', seen(C.filter_tool_output('list_files',{},files,'Fife Council'),'files')==['fife.txt','azure.txt'])
matches=out({'matches':[{'file_id':'a'*32},{'file_id':'b'*32}]})
t('search_files matches filtered', seen(C.filter_tool_output('search_files',{},matches,'Fife Council'),'matches')==['a'*32])
rd=C.filter_tool_output('read_file',{},out({'file_id':'b'*32,'lines':[{'text':'secret borders'}]}),'Fife Council')
t('read_file of Borders file refused in Fife chat','Withheld by Client separation' in rd and 'secret borders' not in rd)
R.update_rule('client_separation',new_params={'strict':True,'external':'general'})
t('strict: untagged chat sees General only', seen(C.filter_tool_output('search_records',{},recs,''))==['Azure landing zone'])
# external (Claude Desktop) general mode
import mcp_server as M;M.CLIENT='Claude Desktop'
t('Claude Desktop sees General memories only', [x['title'] for x in M.search_records('')['records']]==['Tenant migration lesson','Azure landing zone'])
try: M.read_file('a'*32);t('Claude Desktop cannot read Fife file',False)
except ValueError: t('Claude Desktop cannot read Fife file',True)
M.CLIENT='';R.update_rule('client_separation',new_params={'strict':False,'external':'all'})
# chats
from fastapi.testclient import TestClient
cl=TestClient(app.app)
cid=cl.post('/chats').json()['id']
t('set client on empty chat', cl.put(f'/chats/{cid}/client',json={'client':'Fife Council'}).json()=={'client':'Fife Council'})
up=cl.post('/files',json={'name':'fife-notes.txt','data':base64.b64encode(b'Workshop notes: tenant plan').decode(),'chat_id':cid}).json()
t('upload in Fife chat inherits Fife', C.client_of('file',up['id'])=='Fife Council')
pr=s._propose_original('Workshop date','Workshop is on 14 October at Glenrothes','User said')['id']
C.tag_from_chat_output('propose_record',out({'id':pr,'status':'proposed'}),cid);t('memory proposed in Fife chat inherits Fife', C.client_of('memory',pr)=='Fife Council')
with s.db() as c: c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES ('tt',?,'hi','hello','openai','complete',?)",(cid,s.now()))
t('changing client on a chat with messages asks for a new chat', cl.put(f'/chats/{cid}/client',json={'client':'Scottish Borders Council'}).json().get('needs_new_chat') is True)
t('unknown client rejected', cl.put(f'/chats/{cid}/client',json={'client':'Nobody'}).status_code==400)
C.delete_client('Scottish Borders Council');t('deleting a client makes its items General', not C.client_of('memory',b1) and not C.client_of('file','b'*32))
