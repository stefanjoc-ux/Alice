"""Decisions: proposal, structure, filters, Temple suggestions with edits, meeting decisions, duplicates."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,uuid
import substrate_store as s, temple, clients as C, conversations as V, knowledge as K
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
s.create_category('Work','Insight');C.create_client('Fife Council',['Fife'])
import app, mcp_server as M
from fastapi.testclient import TestClient
cl=TestClient(app.app);H={'x-admin-token':app.ADMIN_TOKEN}
# 1. a model proposes a decision
M.CLIENT='Claude Desktop'
r=M.propose_decision(title='Roof finish for the carport',decision='Use clear corrugated polycarbonate sheets with a 5 degree fall',source='Stefan: "go with clear sheets and a 5 degree fall"',
    rationale='Keeps the car visible from the house and sheds rain',options_considered=['EPDM membrane','Cedar shingles','Clear polycarbonate'],revisit_when='If the sheets yellow or crack',revisit_date='2028-09-30',category='work')
t('decision proposed', r['status']=='proposed')
did=r['id'];row=s.organised_records('proposed',kind='decision')['records']
t('listed under Decisions with structure', len(row)==1 and row[0]['decision']['options']==['EPDM membrane','Cedar shingles','Clear polycarbonate'] and row[0]['review_by']=='2028-09-30')
t('category applied', row[0]['category']=='Work')
s.review(did,'approved')
sr=[x for x in M.search_records('carport')['records'] if x['id']==did][0]
t('models see it as a decision with detail', sr.get('type')=='decision' and sr['decision_detail']['revisit']=='If the sheets yellow or crack')
try: M.propose_decision(title='Carport roof finish',decision='Use clear corrugated polycarbonate sheets with a 5 degree fall',source='again');t('duplicate decision blocked',False)
except ValueError as e: t('duplicate decision blocked',True)
try: M.propose_decision(title='x',decision='Yes',source='s');t('empty decision rejected',False)
except Exception: t('empty decision rejected',True)
facts=s.organised_records('approved',kind='fact')['total'];decs=s.organised_records('approved',kind='decision')['total']
t('Facts / Decisions filters split correctly', decs==1 and facts==0)
# 2. Temple whole-chat review finds a decision
cid=s.create_chat()['id'];C.set_chat_client(cid,'Fife Council')
with s.db() as c:
    for u,a in [('For Fife we will pilot with 20 mailboxes, not a big bang, because rollback is easier','Makes sense.'),('Revisit after the first batch','Noted.')]:
        c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)",(uuid.uuid4().hex,cid,u,a,'openai','complete',s.now()))
V._ask=lambda p:(json.dumps({'suggestions':[{'kind':'decision','title':'Fife migration approach','content':'Pilot with 20 mailboxes rather than a big-bang migration',
    'quote':'we will pilot with 20 mailboxes, not a big bang','reason':'Explicit decision','rationale':'Rollback is easier','options':['Big bang','Pilot of 20 mailboxes'],'revisit':'After the first batch'}]}),'openai')
print('   review:',V.review_chat(cid,manual=True))
sug=[x for x in cl.get('/admin/api/temple/suggestions',headers=H).json()['items'] if x['kind']=='decision'][0]
t('suggestion stored in editable decision format', sug['content'].startswith('Decision: Pilot with 20') and 'Options considered: Big bang; Pilot of 20 mailboxes' in sug['content'])
edited=sug['content'].replace('After the first batch','After the first batch of 200')
acc=cl.post('/admin/api/temple-suggestions/'+sug['id'],json={'action':'accept','content':edited},headers=H).json()
k=s.record_kinds([acc['target']])[acc['target']]
t('accepting creates a decision memory with your edit', k['kind']=='decision' and k['decision']['revisit']=='After the first batch of 200')
t('and it inherits the chat client', C.client_of('memory',acc['target'])=='Fife Council')
t('accepted twice is refused', cl.post('/admin/api/temple-suggestions/'+sug['id'],json={'action':'accept','content':edited},headers=H).status_code==400)
# 3. meeting extract decisions -> records
m=K.create('meeting','Fife steering group','Agreed next steps for the pilot.','Teams meeting','you',label='client',client='Fife Council',category='Work',
           meeting={'date':'2026-09-30','decisions':['Use the Glenrothes office for the pilot group','Weekly checkpoint on Fridays'],'actions':[]})
x=cl.post(f"/admin/api/knowledge/{m['id']}/decisions",headers=H).json();print('   meeting:',x)
props=s.organised_records('proposed',kind='decision')['records']
t('meeting decisions proposed with date, category and client', x['proposed']==2 and all(p['decision']['decided_on']=='2026-09-30' and p['category']=='Work' and C.client_of('memory',p['id'])=='Fife Council' for p in props if 'Glenrothes' in p['content'] or 'Fridays' in p['content']))
t('running it again does not duplicate', cl.post(f"/admin/api/knowledge/{m['id']}/decisions",headers=H).json()['proposed']==0)
