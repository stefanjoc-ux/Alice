"""The Proposal writer page: a brief in; a QA-checked Word proposal out. No menus and no access to the rest of Alice."""
import json
from html import escape


def render(a):
    from ui_theme import SHARED_CSS
    from proposal_ui import PE_CSS, PE_JS
    data = json.dumps({'id': a['id'], 'name': a['name'], 'greeting': a['greeting'], 'paused': a['status'] != 'active'})
    return ('''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + escape(a['name']) + '''</title><link rel="icon" href="/static/favicon.png" type="image/png">
<style>''' + SHARED_CSS + PE_CSS + '''
body{display:grid;grid-template-rows:52px minmax(0,1fr);overflow:hidden}
.topbar .brand{width:auto}.topbar .who{font-size:15px;font-weight:600;color:#fff;letter-spacing:0}
main{overflow:auto;padding:24px 16px 60px}
.wrap{max-width:980px;margin:0 auto;display:grid;gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.card h1{margin:0 0 6px;font-size:21px}.card h2{margin:0 0 10px;font-size:17px}.card>p.lead{margin:0;color:var(--muted)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid2 label,.stack label{display:grid;gap:4px;font-weight:600;font-size:14px}
.stack{display:grid;gap:12px}textarea#brief{min-height:190px}textarea{resize:vertical}
.hint{font-weight:400;color:var(--muted);font-size:12.5px}
details.fold{border-top:1px solid var(--line);padding-top:12px}details.fold>summary{cursor:pointer;font-weight:700;font-size:15px;list-style:none;display:flex;gap:8px;align-items:center}
details.fold>summary::before{content:'\\25B8';color:var(--muted)}details.fold[open]>summary::before{content:'\\25BE'}
.check{display:flex!important;gap:8px;align-items:center;font-weight:400!important}
.pe-meta label{display:flex!important;gap:6px;align-items:center;font-weight:400!important;font-size:12.5px}
.go{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.steps{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:6px}.steps li{display:flex;gap:10px;align-items:center;color:var(--muted)}
.steps li::before{content:'';width:10px;height:10px;border-radius:50%;border:2px solid #b9c6cf;flex:none}
.steps li.done{color:var(--ink)}.steps li.done::before{background:#55b987;border-color:#55b987}
.steps li.now{color:var(--ink);font-weight:600}.steps li.now::before{border-color:#e2a33b;background:#fdf3e1;animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.4}}
.verdict{display:flex;gap:14px;align-items:center;flex-wrap:wrap;border-radius:10px;padding:12px 14px;margin-bottom:12px}
.verdict.ok{background:#eef8f1;border:1px solid #9fcfaf}.verdict.warn{background:#fdf3e1;border:1px solid #e2bf85}.verdict.bad{background:#fbeaea;border:1px solid #e0aaaa}
.verdict strong{font-size:16px}.dl{margin-left:auto;background:var(--teal);color:#fff!important;padding:9px 16px;border-radius:8px;text-decoration:none;font-weight:600;white-space:nowrap}.dl:hover{filter:brightness(1.1)}.score{font-size:24px;font-weight:700}
table.t{width:100%;border-collapse:collapse;font-size:14px}table.t th{text-align:left;font-size:12.5px;color:var(--muted);padding:6px;border-bottom:1px solid var(--line)}
table.t td{padding:6px;border-bottom:1px solid var(--line);vertical-align:top}table.t td.num{text-align:right;white-space:nowrap}table.t tr.tot td{font-weight:700}
.st{font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid}.st.met{background:#eef8f1;color:#1e5b31;border-color:#9fcfaf}.st.partly{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.st.missing,.st.high{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}.st.medium{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.st.low{background:#f4f6f8;color:#4b5a66;border-color:#c1cbd3}
.internal{border:2px dashed #c7b8dd;background:#faf7fd}.internal h2::after{content:' \\00b7 internal: not in the document, never sent to the AI';font-size:12px;font-weight:400;color:#634394}
.warnline{color:#7a1f1f;font-weight:600;margin:6px 0 0}
.issues{display:grid;gap:8px;margin:0;padding:0;list-style:none}.issues li{display:grid;gap:2px;border-left:3px solid #c1cbd3;padding-left:10px}.issues li.high{border-color:#b3261e}.issues li.medium{border-color:#e2a33b}
.draft h3{margin:16px 0 4px;font-size:15px}.draft .body{white-space:pre-wrap;font-size:14px;line-height:1.55}
.recent{display:grid;gap:6px}.recent button{text-align:left;display:flex;justify-content:space-between;gap:12px;width:100%}
.err{background:#fbeaea;border:1px solid #e0aaaa;border-radius:10px;padding:10px 12px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
[hidden]{display:none!important}
.ref-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.ref-tools input{flex:1;min-width:200px}
.ref-upl{cursor:pointer;border:1px solid var(--line2,#b9cbd8);border-radius:8px;padding:8px 14px;font-weight:600;font-size:14px;background:#fff}.ref-upl:hover{border-color:var(--teal)}
.ref-list{display:grid;gap:6px;max-height:320px;overflow:auto;padding-right:4px}
.ref-item{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-weight:400!important}
.ref-item.off{opacity:.55}.ref-item b{font-weight:600;overflow-wrap:anywhere}.ref-item .hint{display:block}
.ref-badges{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.rb{font-size:11.5px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);background:#f4f6f8;color:#4b5a66;white-space:nowrap}
.rb.ok{background:#eef8f1;color:#1e5b31;border-color:#9fcfaf}.rb.wait{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.rb.cl{background:#ede7f6;color:#4b2f73;border-color:#c7b8dd}
.ref-panel{border:1px solid #c7b8dd;background:#faf7fd;border-radius:12px;padding:14px 16px;margin-bottom:10px;display:grid;gap:10px}
.ref-panel h3{margin:0;font-size:15px}.ref-panel .grid2 label,.ref-panel>label{display:grid;gap:4px;font-weight:600;font-size:14px}
.ref-tag{display:grid;gap:6px}.ref-tag label{display:flex!important;gap:8px;align-items:center;font-weight:400!important}
.ref-ok{background:#eef8f1;border:1px solid #9fcfaf;border-radius:10px;padding:10px 12px;font-size:14px}
@media(max-width:760px){.grid2,.cols{grid-template-columns:1fr}}
</style></head><body>
<header class="topbar"><span class="brand"><img src="/static/favicon.png" alt=""><span class="who">''' + escape(a['name']) + '''</span></span><div class="sp"></div><span class="small" style="color:#9fb8ca">Built on Alice</span></header>
<main><div class="wrap">
<section class="card"><h1>''' + escape(a['name']) + '''</h1><p class="lead" id="greeting"></p></section>
<section class="card" id="prog" hidden aria-live="polite"><h2 id="prog-title">Working on it</h2><ol class="steps" id="steps"></ol><div class="err" id="perr" hidden></div></section>
<div id="result"></div>
<form class="card stack" id="f">
<h2>New proposal</h2>
<div class="grid2"><label>Proposal title<input id="title" maxlength="150" required placeholder="e.g. Data security baseline for Microsoft Fabric"></label>
<label>Client or organisation<input id="org" maxlength="80" list="orgs" placeholder="Start typing a name"><datalist id="orgs"></datalist><span class="hint" id="org-hint">Its approved profile is used. Only this client's tagged material is used, never another client's.</span></label></div>
<label>Brief and context<textarea id="brief" maxlength="20000" required placeholder="Paste the brief or describe what the client wants: outcomes, scope, requirements, timescales, evaluation criteria, anything they said."></textarea>
<span class="hint">Everything in the brief is checked before it goes to the AI: secrets and protective markings are refused.</span></label>
<label>Notes for the writer <span class="hint">(optional: angle to take, things to stress or avoid)</span><textarea id="notes" maxlength="4000" rows="3"></textarea></label>
<div class="grid2"><label>Writer model<select id="wm"></select></label><label>QA model<select id="qm"></select></label></div>
<p class="hint" id="cost"></p>
<label class="check"><input type="checkbox" id="mem" checked> Use what Alice knows: approved memories, decisions and knowledge that are general or for this client</label>
<details class="fold" id="refs-fold"><summary>Reference documents <span class="hint" id="ref-count"></span></summary>
<p class="pe-note">Background the writer can draw on, such as Microsoft success guides or your own method papers. It reads each document's approved summary and the passages relevant to this brief, under the same rules as everything else. The documents stay in their source.</p>
<div class="ref-tools"><input type="search" id="ref-q" placeholder="Filter by name or source" aria-label="Filter reference documents"><label class="secondary ref-upl" tabindex="0">Upload a reference document<input type="file" id="ref-file" accept=".docx,.pdf,.txt,.md,.csv" hidden></label></div>
<div class="ref-panel" id="ref-panel" hidden></div>
<div class="ref-list" id="ref-list"></div></details>
<details class="fold" open><summary>Format and flow</summary>
<p class="pe-note">The sections in order. Template sections keep the template's formatting; add sections, rename them, reorder them, or add content suggestions for each. Standard text is copied from the template word for word.</p><div id="secs"></div><p class="pe-note" id="tpl"></p></details>
<details class="fold"><summary>Rate card</summary>
<p class="pe-note">The writer picks the days per role; Alice prices them from the sell rates and adds the pricing table. Cost rates stay in Alice: never sent to the AI, never in the document.</p><div id="rates"></div></details>
<div class="go"><button class="primary" id="go" type="submit">Write proposal</button><span class="hint" id="go-note">Writing, a QA check and one revision if needed: usually two to four minutes.</span></div>
<div class="err" id="ferr" role="alert" hidden></div>
</form>
<section class="card" id="recent-box" hidden><h2>Recent proposals</h2><div class="recent" id="recent"></div></section>
</div></main>
<script>
const A=''' + data.replace('</', '<\\/') + ''';
''' + PE_JS + r'''
const $=id=>document.getElementById(id),mk=PE.mk;let S=null,secEd=null,rateEd=null,timer=null;
const base='/assistant/'+encodeURIComponent(A.id);
async function api(path,method,body){const r=await fetch(base+path,{method:method||'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:(Array.isArray(d.detail)?d.detail.map(x=>x.msg).join('; '):'Something went wrong. Try again.'));return d}
const STEPS=[['Gathering','Gathering what Alice knows and writing the draft'],['checking the draft','Proposal QA checks the draft against the brief'],['Revising','Revising with the QA feedback (only if needed)'],['checking the revision','Proposal QA checks the revision'],['Building','Building the Word document']];
function drawSteps(stage,status,qa){const ol=$('steps');ol.replaceChildren();let idx=STEPS.findIndex(s=>stage&&stage.includes(s[0]));if(status==='done')idx=STEPS.length;
 const skipped=status==='done'&&qa&&qa.length===1;
 STEPS.forEach(([k,l],i)=>{if(skipped&&(i===2||i===3))return;const li=mk('li',i===2&&skipped?l:l,i<idx?'done':i===idx?'now':'');ol.append(li)})}
let R={documents:[],folders:[],clients:[],categories:[]};const picked=new Set();
async function loadRefs(){try{R=await api('/references')}catch{R={documents:[],folders:[],clients:[],categories:[]}}drawRefs()}
function drawRefs(){const q=($('ref-q').value||'').toLowerCase(),org=$('org').value.trim().toLowerCase(),box=$('ref-list');box.replaceChildren();
 const tpl=(S&&S.template||'').replace(/\\/g,'/');const docs=R.documents.filter(d=>d.path.replace(/\\/g,'/')!==tpl).filter(d=>!q||(d.name+' '+d.source+' '+d.path).toLowerCase().includes(q));
 if(!R.documents.length)box.append(mk('p','No documents in the document sources yet. Upload one, or add files to a source on the Documents page.','pe-note'));
 for(const d of docs){const other=d.clients.length&&!d.clients.some(c=>c.toLowerCase()===org);const row=mk('label','','ref-item'+(other?' off':''));
  const cb=document.createElement('input');cb.type='checkbox';cb.checked=picked.has(d.path);cb.disabled=other&&!picked.has(d.path);cb.onchange=()=>{cb.checked?picked.add(d.path):picked.delete(d.path);count()};
  const mid=mk('span');mid.append(mk('b',d.name),mk('span',d.source+' · '+d.path,'hint'));
  const bd=mk('span','','ref-badges');bd.append(mk('span',d.summary==='approved'?'Summary approved':d.summary==='draft'?'Summary awaiting approval':'No summary yet','rb'+(d.summary==='approved'?' ok':d.summary==='draft'?' wait':'')));
  for(const c of d.clients)bd.append(mk('span','For '+c+' only','rb cl'));if(!d.clients.length&&d.summary)bd.append(mk('span','General','rb'));
  if(other)row.title='Tagged to another client: it can only be used on that client\u2019s proposals.';row.append(cb,mid,bd);box.append(row)}
 count()}
function count(){$('ref-count').textContent=picked.size?'\u00b7 '+picked.size+' selected':''}
$('ref-q').oninput=drawRefs;
$('ref-file').onchange=async()=>{const f=$('ref-file').files[0];$('ref-file').value='';if(!f)return;const pan=$('ref-panel');pan.hidden=false;pan.replaceChildren(mk('p','Reading '+f.name+'\u2026','hint'));
 if(f.size>15*1024*1024){pan.replaceChildren(mk('p','That file is larger than 15 MB.','err'));return}
 const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=no;r.readAsDataURL(f)});
 let x;try{x=await api('/references/inspect','POST',{name:f.name,data,organisation:$('org').value})}catch(e){pan.replaceChildren(mk('p',e.message,'err'));return}
 refForm(x)};
function refForm(x){const pan=$('ref-panel');pan.replaceChildren();pan.append(mk('h3','Add '+x.name+' as a reference'));
 if(x.purview)pan.append(mk('p','Purview label: '+x.purview+'. Alice checks its mapping before anything is sent to the AI.','hint'));
 const ti=document.createElement('input');ti.maxLength=200;ti.value=x.title;const tl=mk('label','Title');tl.append(ti);
 const fs=document.createElement('select');for(const f of R.folders){const o=document.createElement('option');o.value=f.path;o.textContent=f.path.replace(/\//g,' \u203a ')+' ('+f.type_name+')';fs.append(o)}fs.value=x.folder;
 const nf=document.createElement('input');nf.maxLength=60;nf.value=x.new_folder||'';nf.placeholder='Optional';
 const g=mk('div','','grid2');const l1=mk('label','Save to');l1.append(fs,mk('span','Saved in the document source, not in Alice.','hint'));const l2=mk('label','New folder inside it');l2.append(nf);g.append(l1,l2);
 const tg=mk('div','','ref-tag');tg.append(mk('b','Who can use it'));const mkr=(v,txt)=>{const l=mk('label');const r=document.createElement('input');r.type='radio';r.name='reftag';r.value=v;r.checked=x.tag===v;l.append(r,document.createTextNode(txt));return [l,r]};
 const [lg,rg]=mkr('general','General: every client\u2019s proposals can use it');const [lc,rc]=mkr('client','One client only:');
 const cs=document.createElement('select');for(const c of R.clients){const o=document.createElement('option');o.value=c;o.textContent=c;cs.append(o)}if(x.client)cs.value=x.client;lc.append(cs);cs.onchange=()=>{rc.checked=true};
 tg.append(lg,lc,mk('span','Suggested: '+x.reason,'hint'));
 const cat=document.createElement('select');const o0=document.createElement('option');o0.value='';o0.textContent='No category';cat.append(o0);for(const c of R.categories){const o=document.createElement('option');o.value=c;o.textContent=c;cat.append(o)}cat.value=x.category||'';
 const cl=mk('label','Category in Knowledge');cl.append(cat);
 const go=document.createElement('button');go.type='button';go.className='primary';go.textContent='Save, summarise and use it';const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';cancel.textContent='Cancel';cancel.onclick=()=>{pan.hidden=true};
 const act=mk('div','','go');act.append(go,cancel,mk('span','The summary goes to Knowledge as a draft for approval. Takes about half a minute.','hint'));
 go.onclick=async()=>{go.disabled=true;go.textContent='Saving and summarising\u2026';
  try{const r=await api('/references','POST',{token:x.token,folder:fs.value,new_folder:nf.value,title:ti.value,tag:rc.checked?'client':'general',client:rc.checked?cs.value:'',category:cat.value});
   picked.add(r.path);await loadRefs();pan.replaceChildren(mk('div',r.note?r.note:'Saved to '+r.path.replace(/[\\\/]/g,' \u203a ')+' ('+r.where+')'+(r.client?', for '+r.client+' only':', for every client')+'. '+(r.duplicate?'Alice already had this summary.':'The summary is waiting for your approval in Knowledge; until then the writer uses the passages relevant to each brief.')+' It is selected for this proposal.','ref-ok'))}
  catch(e){go.disabled=false;go.textContent='Save, summarise and use it';pan.append(mk('p',e.message,'err'))}};
 pan.append(tl,g,tg,cl,act)}
async function load(){S=await api('/setup');loadRefs();$('greeting').textContent=A.paused?A.name+' is paused at the moment.':A.greeting;
 $('orgs').replaceChildren(...S.organisations.map(o=>{const x=document.createElement('option');x.value=o.name;if(o.client)x.label=o.name+' (client)';return x}));
 const opt=m=>{const o=document.createElement('option');o.value=m.key;o.textContent=m.name+(m.premium?' (premium)':'');return o};
 $('wm').replaceChildren(...S.models.map(opt));$('qm').replaceChildren(...S.models.map(opt));$('wm').value=S.writer;$('qm').value=S.qa;
 const cost=()=>{const w=S.models.find(m=>m.key===$('wm').value),q=S.models.find(m=>m.key===$('qm').value);if(!w||!q||w.writer_cost==null||q.qa_cost==null){$('cost').textContent='';return}
  const t=w.writer_cost+q.qa_cost;$('cost').textContent='Roughly $'+(t<1?t.toFixed(2):t.toFixed(2))+' for this proposal (draft, QA, one revision and a second QA check), depending on the brief and context. Defaults are set on the Assistants page.'};
 $('wm').onchange=cost;$('qm').onchange=cost;cost();
 secEd=PE.sections($('secs'),S.sections,{empty:'No sections yet: add some, or choose a template on the Assistants page.'});rateEd=PE.rates($('rates'),S.rate_card,S.units);
 $('tpl').textContent=S.template_error?S.template_error:S.template?'Template: '+S.template:'No template set: Alice uses its own Word layout. Set a template on the Assistants page.';
 if(A.paused)$('go').disabled=true;recent();const q=new URLSearchParams(location.search).get('p');if(q)follow(q)}
$('org').addEventListener('input',()=>drawRefs());
$('org').oninput=()=>{const o=S&&S.organisations.find(x=>x.name.toLowerCase()===$('org').value.trim().toLowerCase());$('org-hint').textContent=o?(o.client?o.name+' is a client: its tagged memories and knowledge are included; other clients’ never are.':'Its approved profile is used.'):($('org').value.trim()?'Not in the list: Alice checks other names it knows (e.g. SBC); if none match, the name is used as typed.':'Its approved profile is used. Only this client’s tagged material is used, never another client’s.')};
$('f').onsubmit=async e=>{e.preventDefault();$('ferr').hidden=true;$('go').disabled=true;
 try{const r=await api('/proposals','POST',{title:$('title').value,organisation:$('org').value,brief:$('brief').value,notes:$('notes').value,use_memory:$('mem').checked,references:[...picked],writer_model:$('wm').value,qa_model:$('qm').value,sections:secEd.value(),rate_card:rateEd.value()});
  history.replaceState(null,'','?p='+r.id);document.querySelectorAll('details.fold').forEach(d=>d.open=false);follow(r.id);document.querySelector('main').scrollTop=0}
 catch(err){$('ferr').textContent=err.message;$('ferr').hidden=false;$('go').disabled=A.paused}};
function follow(pid){clearInterval(timer);$('result').replaceChildren();$('prog').hidden=false;$('perr').hidden=true;$('prog-title').textContent='Working on it';drawSteps('Gathering','running');
 const tick=async()=>{let p;try{p=await api('/proposals/'+pid)}catch(err){clearInterval(timer);$('perr').textContent=err.message;$('perr').hidden=false;return}
  drawSteps(p.stage,p.status,p.qa);
  if(p.status==='running')return;clearInterval(timer);$('go').disabled=A.paused;
  if(p.status==='failed'){$('prog-title').textContent='This proposal could not be finished';$('perr').textContent=p.error;$('perr').hidden=false;recent();return}
  $('prog').hidden=true;show(p);recent()};
 tick();timer=setInterval(tick,1500)}
function table(head,rows,cls){const t=mk('table','','t');const h=document.createElement('tr');for(const x of head)h.append(mk('th',x));t.append(h);for(const r of rows){const tr=document.createElement('tr');if(r.cls)tr.className=r.cls;for(const c of r.cells){const td=document.createElement('td');if(c&&c.node)td.append(c.node);else td.textContent=c??'';if(c&&c.num)td.className='num';tr.append(td)}t.append(tr)}return t}
const n=(v,num)=>({node:mk('span',v),num});
function show(p){const box=$('result');box.replaceChildren();const qa=p.qa[p.qa.length-1]||{};
 const top=mk('section','','card');const v=mk('div','','verdict '+(qa.verdict==='client_ready'?'ok':(qa.issues||[]).some(i=>i.severity==='high')?'bad':'warn'));
 v.append(mk('span',qa.score!=null?qa.score+'/100':'','score'));const vt=mk('div');vt.append(mk('strong',qa.verdict==='client_ready'?'Client ready, according to Proposal QA':'Needs your attention before it goes to the client'),mk('div',qa.summary||'','hint'));v.append(vt);
 const dl=document.createElement('a');dl.href='/documents/'+p.document_id+'/download';dl.className='dl';dl.textContent='Download Word document';v.append(dl);top.append(mk('h2',p.title+(p.organisation?' · '+p.organisation:'')),v);
 if(p.qa.length>1)top.append(mk('p','First QA check: '+(p.qa[0].score??'?')+'/100, '+(p.qa[0].issues||[]).length+' issues. The writer revised it once using that feedback; the result above is the second check.','hint'));
 const mn=k=>(S&&S.models.find(m=>m.key===k)||{}).name||k;if(p.inputs&&p.inputs.writer)top.append(mk('p','Written by '+mn(p.inputs.writer)+'; checked by '+mn(p.inputs.qa)+'.','hint'));
 top.append(mk('p','Read it before it goes anywhere: QA is a second pair of eyes, not a sign-off.','hint'));box.append(top);
 const cols=mk('div','','cols');
 const rq=mk('section','','card');rq.append(mk('h2','Meets the brief?'));if((qa.requirements||[]).length)rq.append(table(['Requirement','','Where'],qa.requirements.map(r=>({cells:[r.requirement+(r.note?' — '+r.note:''),{node:mk('span',{met:'Met',partly:'Partly',missing:'Missing'}[r.status],'st '+r.status)},r.where||'']}))));else rq.append(mk('p','QA listed no requirements.','hint'));
 const is=mk('section','','card');is.append(mk('h2','Issues to look at'));const ul=mk('ul','','issues');for(const i of qa.issues||[]){const li=mk('li','',i.severity);const h=mk('div');h.append(mk('span',i.severity,'st '+i.severity),document.createTextNode(' '+(i.section?i.section+': ':'')+i.issue));li.append(h);if(i.fix)li.append(mk('span','Fix: '+i.fix,'hint'));ul.append(li)}
 if(!(qa.issues||[]).length)ul.append(mk('li','None.'));is.append(ul);if((qa.strengths||[]).length)is.append(mk('p','Strengths: '+qa.strengths.join('; '),'hint'));
 cols.append(rq,is);box.append(cols);
 const pr=p.pricing||{};if((pr.lines||[]).length){const c=mk('section','','card internal');c.append(mk('h2','Commercials'));
  c.append(table(['Role','Quantity','Sell rate','Sell','Cost','Margin'],pr.lines.map(l=>({cells:[l.role,n(l.quantity+' '+l.unit+(l.quantity===1?'':'s'),1),n(PE.gbp(l.sell_rate),1),n(PE.gbp(l.sell),1),n(PE.gbp(l.cost),1),n(l.margin==null?'—':l.margin.toFixed(1)+'%',1)]})).concat([{cls:'tot',cells:['Total','','',n(PE.gbp(pr.sell),1),n(PE.gbp(pr.cost),1),n(pr.margin==null?'—':pr.margin.toFixed(1)+'%',1)]}])));
  for(const w of pr.warnings||[])c.append(mk('p','⚠ '+w,'warnline'));box.append(c)}
 const d=p.draft||{};const more=mk('section','','card');
 if((d.gaps||[]).length){more.append(mk('h2','Gaps the writer could not fill'));const g=mk('ul');for(const x of d.gaps)g.append(mk('li',x));more.append(g)}
 if((d.dropped_roles||[]).length)more.append(mk('p','Roles the writer wanted that are not on the rate card (left out): '+d.dropped_roles.join(', '),'hint'));
 const u=(p.context||{}).used||{};more.append(mk('h2','What Alice used'));const ul2=mk('ul');
 ul2.append(mk('li',u.organisation?'Organisation profile: '+u.organisation:'No organisation profile.'));ul2.append(mk('li',(u.memories||[]).length?'Memories: '+u.memories.join('; '):'No memories.'));ul2.append(mk('li',(u.knowledge||[]).length?'Knowledge: '+u.knowledge.join('; '):'No knowledge.'));
 if((u.references||[]).length)ul2.append(mk('li','Reference documents: '+u.references.join('; ')));for(const x of u.references_skipped||[])ul2.append(mk('li','Reference left out: '+x));
 if((p.context||{}).skipped)ul2.append(mk('li',p.context.skipped+' item(s) left out by the rules.'));more.append(ul2);
 const dr=document.createElement('details');dr.className='fold draft';dr.append(mk('summary','Read the draft here'));for(const s of d.sections||[]){dr.append(mk('h3',s.title),mk('div',s.keep?'(standard text from the template)':s.body,'body'))}more.append(dr);box.append(more)}
async function recent(){try{const d=await api('/proposals');$('recent-box').hidden=!d.proposals.length;$('recent').replaceChildren(...d.proposals.map(x=>{const b=mk('button','','secondary');b.type='button';
 b.append(mk('span',x.title+(x.organisation?' · '+x.organisation:'')),mk('span',x.status==='running'?'writing…':x.status==='failed'?'failed':(x.verdict==='client_ready'?'client ready':'needs attention')+(x.score!=null?' · '+x.score+'/100':'')+' · '+new Date(x.created_at).toLocaleDateString('en-GB'),'hint'));
 b.onclick=()=>{history.replaceState(null,'','?p='+x.id);follow(x.id);window.scrollTo(0,0);document.querySelector('main').scrollTop=0};return b}))}catch{}}
load().catch(e=>{$('ferr').textContent=e.message;$('ferr').hidden=false});
</script></body></html>''')
