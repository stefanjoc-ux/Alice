"""Knowledge library: model drafts, rules on knowledge, security labels, formats (.vtt/.docx), meeting extracts, duplicates, categorising."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,base64,io,zipfile
import substrate_store as s, rules_engine as R, temple, clients as C, knowledge as K
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
import app, mcp_server as M
from fastapi.testclient import TestClient
cl=TestClient(app.app);H={'x-admin-token':app.ADMIN_TOKEN}
s.create_category('Work','Insight');C.create_client('Fife Council',['Fife'])
# 1. a model proposes knowledge (what I needed): draft, invisible until approved
M.CLIENT='Claude Desktop'
r=M.propose_knowledge(title='AI Substrate status 30 Sep',content='Status summary of the build: routing, rules, clients and knowledge. '*3,source='Summary of this conversation',category='work')
t('propose_knowledge creates a draft', r['status']=='draft')
fid=r['id']
t('draft invisible to list_files', fid not in [f['id'] for f in M.list_files()['files']])
try: M.read_file(fid);t('draft unreadable',False)
except ValueError: t('draft unreadable',True)
t('draft hidden from chat library', fid not in [f['id'] for f in app.list_saved_files()])
t('category matched case-insensitively', K.meta([fid])[fid]['category']=='Work')
t('provenance recorded', K.meta([fid])[fid]['added_by']=='model via Claude Desktop' and '[via Claude Desktop]' in K.meta([fid])[fid]['source'])
print('   review:',K.review([fid],'approved'))
t('approved item visible and readable', fid in [f['id'] for f in M.list_files()['files']] and M.read_file(fid)['lines'])
t('search finds it', any(m['file_id']==fid for m in M.search_files('routing rules')['matches']))
# 2. rules on knowledge
for label,content in [('secret','Deploy with key sk-proj-'+'k'*48+' in the pipeline config.'),('marking','OFFICIAL-SENSITIVE\nDraft for the council, do not share.'),('pii','Pay invoices to sort code 12-34-56 account 12345678 please.')]:
    try: M.propose_knowledge(title='x '+label,content=content,source='test');t(f'{label} blocked',False)
    except ValueError as e: t(f'{label} blocked: '+str(e)[:50],True)
# 3. labels
def note(title,label,client=''):
    return K.create('note',title,f'{title} body text that is long enough to save.','Written by you','you',label=label,client=client)['id']
loc=note('Local only note','local');itn=note('Internal note','internal');cli=note('Fife note','general',client='Fife Council')
t('client tag auto-labels client-confidential', K.meta([cli])[cli]['label']=='client')
ids=[f['id'] for f in M.list_files()['files']]
t('Claude Desktop: local and client items hidden, internal allowed', loc not in ids and cli not in ids and itn in ids)
M.CLIENT=''
ids=[f['id'] for f in M.list_files()['files']]
t('web chat MCP: local hidden, client visible (separation handled per chat)', loc not in ids and cli in ids)
out=json.dumps([{'type':'text','text':json.dumps(M.list_files())}])
seen=lambda o:[f['id'] for f in json.loads(json.loads(o)[0]['text'])['files']]
t('Grok cannot see Internal knowledge', itn not in seen(app.knowledge_filter('list_files',out,'grok')) and itn in seen(app.knowledge_filter('list_files',out,'claude')))
# 4. formats
vtt=b"WEBVTT\n\n0f1e/1-0\n00:00:01.000 --> 00:00:04.000\n<v Stefan O'Connor>Let's agree the pilot group.</v>\n\n00:00:04.500 --> 00:00:06.000\n<v Stefan O'Connor>Twenty mailboxes.</v>\n\n00:00:07.000 --> 00:00:09.000\n<v Jo Smith>Agreed, I'll send the list Friday.</v>\n"
print('   vtt ->',repr(K.vtt_to_text(vtt)))
t('vtt merges speaker turns', K.vtt_to_text(vtt).splitlines()==["Stefan O'Connor: Let's agree the pilot group. Twenty mailboxes.","Jo Smith: Agreed, I'll send the list Friday."])
buf=io.BytesIO();z=zipfile.ZipFile(buf,'w');z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Meeting notes</w:t></w:r></w:p><w:p><w:r><w:t>Decision: go </w:t></w:r><w:r><w:t>ahead</w:t></w:r></w:p></w:body></w:document>');z.close()
t('docx text extracted', K.docx_to_text(buf.getvalue())=='Meeting notes\nDecision: go ahead')
r=cl.post('/files',json={'name':'standup.vtt','data':base64.b64encode(vtt).decode()});t(f'.vtt upload accepted ({r.status_code})', r.status_code==200 and K.meta([r.json()['id']])[r.json()['id']]['kind']=='file')
r=cl.post('/files',json={'name':'notes.docx','data':base64.b64encode(buf.getvalue()).decode()});t('.docx upload accepted', r.status_code==200)
# 5. meeting extract (Temple mocked) + save
class FakeResp:
    output_text=json.dumps({'title':'Fife migration pilot','date':'2026-09-30','attendees':['Stefan','Jo'],'summary':'Agreed a pilot.','decisions':['Pilot with 20 mailboxes'],'actions':[{'action':'Send mailbox list','owner':'Jo','due':'Friday'}],'client':'Fife Council'})
    usage=None
class FakeOpenAI:
    def __init__(s_,**k):s_.responses=s_
    def create(s_,**k): return FakeResp()
    def __enter__(s_):return s_
    def __exit__(s_,*a):pass
import openai;openai.OpenAI=FakeOpenAI
x=cl.post('/admin/api/knowledge/meeting/extract',json={'transcript':K.vtt_to_text(vtt)+'\nFife pilot discussion'},headers=H).json()
t('meeting extracted with client matched', x['title']=='Fife migration pilot' and x['client']=='Fife Council' and x['actions'][0]['owner']=='Jo')
r=cl.post('/admin/api/knowledge/meeting',json={'title':x['title'],'content':x['summary'],'source':'Teams meeting 30 Sep','date':x['date'],'attendees':x['attendees'],'decisions':x['decisions'],'actions':x['actions'],'transcript':'Jo Smith: I will send the list','client':'Fife Council','label':'client'},headers=H).json()
text=cl.get('/admin/api/files/'+r['id'],headers=H).json()['text']
t('meeting saved active, searchable with decisions, actions and transcript', 'DECISIONS' in text and 'owner: Jo' in text and 'TRANSCRIPT' in text and K.meta([r['id']])[r['id']]['status']=='active')
bad=cl.post('/admin/api/knowledge/meeting/extract',json={'transcript':'SECRET\nOperation details and more text to pass the minimum length check here.'},headers=H)
t('marked transcript never sent to Temple', bad.status_code==400 and 'marking' in bad.json()['detail'])
# 6. listing, duplicates, archive
d=cl.get('/admin/api/knowledge?status=active',headers=H).json();print('   counts:',d['counts']['kind'],d['counts']['label'])
dup=K.create('note','Internal note','Internal note body text that is long enough to save.','Written by you','you',label='internal');t('duplicate content detected', dup['duplicate'])
cl.put('/admin/api/knowledge',json={'ids':[itn],'status':'archived'},headers=H);t('archived item hidden from models', itn not in [f['id'] for f in M.list_files()['files']])
# 7. categorising knowledge (Temple mocked)
import temple_categorise as TC
TC._ask=lambda p: json.dumps({'assignments':[{'id':m['id'],'category':'Work','confidence':0.9,'reason':'work'} for m in json.loads(p)['memories']]})
print('   categorise:',K.categorise(manual=True))
