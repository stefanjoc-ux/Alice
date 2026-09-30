"""Claude export import: verbatim turns, security skips, re-import, date filter, Temple review, retention guard."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import os,sys,json,io,zipfile,copy
import substrate_store as s, temple, clients as C, conversations as V, rules_engine as R
temple.save_settings(False,'openai')
def t(label,cond): print(('PASS ' if cond else 'FAIL ')+label)
C.create_client('Fife Council',['Fife'])
def msg(sender,text=None,content=None,att=None):
    m={'uuid':'m','sender':sender,'created_at':'2026-08-01T10:00:00Z','text':text or ''}
    if content: m['content']=content
    if att: m['attachments']=[{'file_name':att}]
    return m
convs=[
 {'uuid':'c1','name':'Fife tender approach','created_at':'2026-08-01T09:00:00Z','updated_at':'2026-08-02T09:00:00Z','chat_messages':[msg('human','How should we pitch the Fife tender?'),msg('assistant','Lead with consolidation.'),msg('human','Agreed, we will lead with consolidation',att='brief.pdf')]},
 {'uuid':'c2','name':'Hive inspection','created_at':'2026-07-01T09:00:00Z','updated_at':'2026-07-01T09:30:00Z','chat_messages':[msg('human',content=[{'type':'text','text':'When should I check for varroa?'}]),msg('assistant',content=[{'type':'text','text':'Monitor monthly; treat in August.'}])]},
 {'uuid':'c3','name':'Classified draft','created_at':'2026-08-03T09:00:00Z','updated_at':'2026-08-03T09:00:00Z','chat_messages':[msg('human','OFFICIAL-SENSITIVE\nNotes for the police bid'),msg('assistant','ok')]},
 {'uuid':'c4','name':'Deploy help','created_at':'2026-08-04T09:00:00Z','updated_at':'2026-08-04T09:00:00Z','chat_messages':[msg('human','my key is sk-ant-api03-'+'Q'*40),msg('assistant','Rotate it.')]},
 {'uuid':'c5','name':'','created_at':'2026-08-05T09:00:00Z','updated_at':'2026-08-05T09:00:00Z','chat_messages':[]},
]
def export(cs):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z: z.writestr('data-2026-09-30/conversations.json',json.dumps(cs)); z.writestr('data-2026-09-30/users.json','[]')
    return b.getvalue()
r=V.import_claude_export(export(convs));print('   first import:',{k:v for k,v in r.items() if k!='skipped'},'| skipped:',[(x['title'],x['reason']) for x in r['skipped']])
t('2 imported, marked + secret skipped, empty ignored', r['imported']==2 and len(r['skipped'])==2 and r['empty']==1)
a=s.archived_chats(source='external')['chats'];by={c['title']:c for c in a}
t('imported chats keep their original dates', by['Hive inspection']['updated_at'].startswith('2026-07-01'))
fife=s.get_chat(by['Fife tender approach']['id'])
t('verbatim turns, attachments noted', [x['user_text'] for x in fife['turns']]==['How should we pitch the Fife tender?','Agreed, we will lead with consolidation\n[Attached: brief.pdf]'] and fife['turns'][0]['reply']=='Lead with consolidation.')
t('block-style messages read', s.get_chat(by['Hive inspection']['id'])['turns'][0]['reply']=='Monitor monthly; treat in August.')
t('client detected on import', C.chat_client(by['Fife tender approach']['id'])=='Fife Council')
t('not in the chat sidebar', not s.active_chats())
t('secret never stored', 'sk-ant' not in json.dumps([s.get_chat(c['id']) for c in a]))
# re-import: unchanged + one conversation grown
grown=copy.deepcopy(convs);grown[1]['chat_messages']+= [msg('human','And oxalic acid in winter?'),msg('assistant','Yes, when broodless.')];grown[1]['updated_at']='2026-09-20T09:00:00Z'
r=V.import_claude_export(export(grown));print('   re-import:',{k:v for k,v in r.items() if k!='skipped'})
t('re-import: nothing duplicated, grown conversation updated', r['imported']==0 and r['updated']==1 and r['unchanged']==1 and len(s.archived_chats(source='external')['chats'])==2)
t('grown conversation has all turns', len(s.get_chat(by['Hive inspection']['id'])['turns'])==2)
r=V.import_claude_export(json.dumps(grown).encode(),since='2026-09-01');print('   since result:',{k:v for k,v in r.items() if k!='skipped'});t('raw conversations.json + since filter', r['older']==4 and r['unchanged']==1)
try: V.import_claude_export(b'hello');t('non-export rejected',False)
except ValueError as e: t('non-export rejected: '+str(e)[:50],True)
# Temple review of a verbatim import: no "reproduced" caveat; quotes checked against real messages
V._ask=lambda p:(json.dumps({'suggestions':[{'kind':'decision','title':'Tender pitch','content':'Lead the Fife tender with consolidation','quote':'we will lead with consolidation','reason':'agreed'}]}),'openai')
res=V.review_chat(by['Fife tender approach']['id'],manual=True)
with s.db() as c: sg=c.execute('SELECT reason FROM temple_suggestions').fetchone()[0]
t('review of a verbatim import works without the reproduced caveat', res['suggestions']==1 and 'reproduced' not in sg)
# retention: old imports kept until Temple has reviewed them
R.update_rule('retention',enabled=True,new_params={'months':1})
print('   retention:',R.run_retention())
left={c['title'] for c in s.archived_chats(source='external')['chats']}
t('unreviewed import kept, reviewed-with-capture kept', left=={'Fife tender approach','Hive inspection'})
