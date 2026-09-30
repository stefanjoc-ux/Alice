"""Rule sets: memory governance, guidance, chat and upload blocks, MCP withholding, allow-lists, review-by, spending caps."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,uuid,base64
import substrate_store as s, rules_engine as R, temple
temple.save_settings(False,'openai')
from fastapi.testclient import TestClient
import app
c=TestClient(app.app); tok=app.ADMIN_TOKEN; H={'x-admin-token':tok}
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
# --- memory governance
for title,content,source,expect in [('Monthly spend totals','monthly spend totals','monthly spend totals','Quality'),
    ('Deploy key','Use sk-proj-'+'x'*48,'user said','Secret'),('Card','Card 4111 1111 1111 1111 for travel','user','Personal identifiers'),
    ('Spend reports in GBP','Show spend report amounts in GBP with monthly totals','User said on 28 Sep',None)]:
    try: s.propose(title,content,source); ok=expect is None
    except R.RuleViolation as e: ok=expect is not None and expect.lower() in str(e).lower()
    t(f'propose "{title}" -> {expect or "allowed"}',ok)
try: s.propose('Spend reports GBP','Show spend report amounts in GBP with monthly totals.','User said again');t('near-duplicate blocked',False)
except R.RuleViolation as e: t('near-duplicate blocked: '+str(e)[:60],True)
bad=s._propose_original('Monthly spend totals','monthly spend totals','monthly spend totals')['id']   # Temple-style direct insert bypasses propose
try: s.review(bad,'approved');t('approval blocks the bypassed broken record',False)
except R.RuleViolation: t('approval blocks the bypassed broken record',True)
print('   bulk:',s.bulk_review([bad],'approved'))
# --- guidance compilation
g=s.rules()['guidance'];t('effective guidance includes rule sets in order', g.index('[Organisation]')<g.index('[Personal]') and 'direct, honest pushback' in g)
# --- chat: secret blocked before storage
cid=c.post('/chats').json()['id']
r=c.post('/chat',json={'chat_id':cid,'request_id':'x1','text':'my key is sk-ant-api03-'+'Q'*40,'provider':'openai'})
t(f'chat with API key refused ({r.status_code})', r.status_code==400 and not c.get('/chats/'+cid).json()['turns'])
r=c.post('/chat',json={'chat_id':cid,'request_id':'x2','text':'OFFICIAL-SENSITIVE\nDraft for Police Scotland','provider':'openai'})
t('chat with protective marking refused', r.status_code==400 and 'marking' in r.json()['detail'])
# --- uploads
r=c.post('/files',json={'name':'bid.txt','data':base64.b64encode(b'OFFICIAL-SENSITIVE: COMMERCIAL\npricing').decode(),'chat_id':cid})
t(f'marked upload refused ({r.status_code})', r.status_code==400)
r=c.post('/files',json={'name':'notes.txt','data':base64.b64encode(b'Ordinary meeting notes about the carport.').decode(),'chat_id':cid});t('ordinary upload allowed',r.status_code==200)
# --- MCP: legacy marked file withheld from every tool
import mcp_server as M
with app.connect_db() as con: con.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",('f'*32,'old.txt','h'*64,b'x','SECRET\nold material','x','2026-01-01',1))
try: M.read_file('f'*32);t('read_file withholds marked legacy file',False)
except ValueError as e: t('read_file withholds marked legacy file',True)
t('search_files skips it', 'withheld_files' in M.search_files('material'))
t('list_files flags it', any(f.get('withheld') for f in M.list_files()['files']))
# --- provider allow-list + external scope
s.create_category('Work','Insight');s.create_category('Family','Relatives')
w=s._propose_original('Fife bid approach','Lead with the tenant consolidation story','User said')['id'];s.review(w,'approved');s.set_category([w],'Work')
f=s._propose_original('Dad visit','Dad visits in November','User said')['id'];s.review(f,'approved');s.set_category([f],'Family')
out=json.dumps([{'type':'text','text':json.dumps(M.search_records(''))}])
titles=lambda o:[x['title'] for x in json.loads(json.loads(o)[0]['text'])['records']]
t('Grok cannot see Work memories', 'Fife bid approach' not in titles(R.filter_tool_output(out,'grok')) and 'Dad visit' in titles(R.filter_tool_output(out,'grok')))
t('Claude still sees Work memories', 'Fife bid approach' in titles(R.filter_tool_output(out,'claude')))
R.update_rule('external_scope',new_params={'allowed_categories':['Work']});M.CLIENT='Claude Desktop'
t('external client limited to Work', [x['title'] for x in M.search_records('')['records']]==['Fife bid approach']);M.CLIENT=''
# --- review-by
R.set_review_by(w,'2020-01-01');t('expired memory annotated for models', M.search_records('Fife')['records'][0].get('possibly_out_of_date') is True)
t('expired count on Memories page', s.organised_records('approved')['expired']==1)
# --- spending cap
R.update_rule('spend_cap',new_params={'daily_usd':1,'monthly_usd':10,'warn_percent':80})
with s.db() as con: con.execute("INSERT INTO model_usage(created_at,provider,model,workload,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?)",(s.now(),'claude','claude-opus-5-5','chat',0.85,'{}'))
print('   spend:',R.spend_status())
try: temple.review_record(w);t('Temple paused at warning level',False)
except ValueError as e: t('Temple paused at warning level',True)
R.check_spend('chat');t('chat still allowed at warning level',True)
with s.db() as con: con.execute("INSERT INTO model_usage(created_at,provider,model,workload,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?)",(s.now(),'claude','claude-opus-5-5','chat',0.30,'{}'))
r=c.post('/chat',json={'chat_id':cid,'request_id':'x3','text':'hello','provider':'openai'});t('chat blocked at cap: '+r.json().get('detail','')[:55],r.status_code==400)
# --- locked + API
r=c.put('/admin/api/rules/approval_required',json={'enabled':False},headers=H);t('core rule cannot be switched off',r.status_code==400)
r=c.post('/admin/api/rules/custom',json={'set_key':'organisation','name':'Bid tone','text':'Write bids in plain English.'},headers=H);t('custom guidance rule created',r.status_code==200 and 'plain English' in s.rules()['guidance'])
print('   blocks logged:',len(R.recent_blocks()))
