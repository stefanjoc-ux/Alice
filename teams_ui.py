"""The Teams page (Workspace › Teams): digital teams, their jobs board, starting a job, refining members and stages, the rate
library and the version history. Registered in admin_ui (PAGES, SECTIONS, SCRIPT, NAV_GROUPS, NAV_ICONS)."""

TITLE = ('Teams', 'Digital teams: AI members who work a job stage by stage and hand work to each other. You approve each hand-off, '
                  'or only the final output, and refine any member as you go. Every change is versioned, and each job runs on the team version it started with.')

ICON = ('<path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M16.5 10a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"/>'
        '<path d="M2.5 19c.6-3.2 2.9-5 5.5-5s4.9 1.8 5.5 5"/><path d="M14 14.2c.8-.5 1.6-.7 2.5-.7 2.2 0 4.2 1.5 4.7 4.5"/>')

SECTION = r'''<style>
.tm-top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.tm-top select{min-width:220px}
.tm-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 4px}.tm-pane[hidden]{display:none}
.tm-job{border:1px solid #d3dee6;border-radius:12px;padding:14px 16px;margin:12px 0;background:#fff}.tm-job.tm-hl{border-color:#075e79;box-shadow:0 0 0 3px rgba(7,94,121,.15)}
.tm-jh{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.tm-jh strong{font-size:16px}.tm-jh .sp{flex:1}
.tm-stages{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.tm-st{font-size:12px;padding:4px 10px;border-radius:999px;border:1px solid #c1cbd3;background:#f4f6f8;color:#4b5a66}
.tm-st.done{background:#e6f4ea;border-color:#9fcfaf;color:#1e5b31}.tm-st.now{background:#075e79;border-color:#075e79;color:#fff}.tm-st b{font-weight:600}
.tm-wait{border-left:4px solid #b7791f;background:#fdf8ee;border-radius:8px;padding:10px 12px;margin:8px 0}.tm-wait .act-buttons{margin-top:8px}
.tm-wait textarea{width:100%;min-height:60px;margin-top:6px}.tm-err{border-left:4px solid #b42318;background:#fbeaea;border-radius:8px;padding:10px 12px;margin:8px 0}
.tm-out{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}.tm-out a{font-size:13px}
.tm-steps{margin-top:8px}.tm-steps summary{cursor:pointer;font-weight:600;font-size:13px}.tm-step{border-top:1px solid #e3e9ee;padding:8px 0;font-size:13px}
.tm-step .k{font-weight:600}.tm-step pre{white-space:pre-wrap;font-size:12px;background:#f6f8fa;border-radius:6px;padding:8px;max-height:280px;overflow:auto}
.tm-tbl{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}.tm-tbl th,.tm-tbl td{border:1px solid #dbe3ea;padding:4px 6px;text-align:left;vertical-align:top}.tm-tbl th{background:#eef3f7}.tm-tbl td.n{text-align:right;font-variant-numeric:tabular-nums}
.tm-form{display:grid;gap:10px;max-width:920px}.tm-form label{display:grid;gap:4px;font-weight:600;font-size:14px}.tm-form textarea{min-height:90px}
.tm-docs{display:grid;gap:6px}.tm-doc{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border:1px solid #d3dee6;border-radius:8px;padding:6px 10px;font-size:13px}.tm-doc span{flex:1}
.tm-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.tm-mem{border:1px solid #d3dee6;border-radius:12px;padding:14px 16px;margin:12px 0;background:#fff}.tm-mem h3{margin:0 0 8px}
.tm-mem .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.tm-mem label{display:grid;gap:4px;font-size:13px;font-weight:600}
.tm-mem textarea.ins{min-height:150px}.tm-checks{display:flex;flex-wrap:wrap;gap:4px 12px;font-weight:400}.tm-checks label{display:flex;gap:6px;align-items:center;font-weight:400}
.tm-sugg{border-left:4px solid #6b4fa0;background:#f7f4fb;border-radius:8px;padding:10px 12px;margin:10px 0}.tm-sugg pre{white-space:pre-wrap;font-size:12.5px;background:#fff;border:1px solid #e1d8ee;border-radius:6px;padding:8px}
.tm-stage{border:1px solid #d3dee6;border-radius:10px;padding:10px 12px;margin:8px 0;display:grid;gap:8px;background:#fff}.tm-stage .tm-row label{flex:1;min-width:180px}
.tm-flow{font-size:13px;color:#3d5566;margin:6px 0 10px}.tm-auto label{display:flex;gap:8px;align-items:flex-start;margin:6px 0;font-weight:400}
</style>
<section><div class="mem-head"><h2 id="tm-name">Teams</h2><div class="tm-top"><select id="tm-pick" aria-label="Team"></select><button type="button" class="secondary" id="tm-new">New team</button></div></div>
<p id="tm-desc" class="muted small"></p><div id="tm-tiles" class="mi-ov-tiles"></div>
<div class="tm-tabs" role="tablist" id="tm-tabs"></div></section>
<section class="tm-pane" id="tm-p-jobs"><div class="mem-head"><h2>Jobs</h2><span class="small muted" id="tm-jobs-note"></span></div><div id="tm-jobs"></div></section>
<section class="tm-pane" id="tm-p-start" hidden><div class="mem-head"><h2>Start a job</h2><button type="button" class="secondary" id="tm-demo">Load the demo project (fictional)</button></div>
<div class="tm-form"><label>Job type<select id="tm-jt"></select></label><label>Title<input id="tm-title" maxlength="150" placeholder="e.g. New community hall, early cost estimate"></label>
<label>Brief<textarea id="tm-brief" maxlength="20000" placeholder="What is wanted, in a few sentences: what the building is for, its size, construction, what to include and leave out."></textarea></label>
<div class="tm-row"><label style="flex:1">Location (optional)<input id="tm-loc" maxlength="120" placeholder="e.g. Perth, Scotland"></label><label style="flex:1">Client (optional)<input id="tm-client" maxlength="80" placeholder="An organisation marked Client keeps the job to its own material"></label></div>
<div><strong>Documents</strong><p class="small muted">Specification, schedules, drawings. Uploaded documents are checked for secrets and protective markings and kept with the job; documents picked from a document source stay there and are read at each turn.</p>
<div class="tm-row"><input type="file" id="tm-files" multiple accept=".pdf,.docx,.xlsx,.csv,.txt,.md"><select id="tm-lib" aria-label="Pick from the document sources"><option value="">Or pick from the document sources…</option></select><button type="button" class="secondary" id="tm-lib-add">Add</button></div>
<div class="tm-docs" id="tm-docs"></div></div>
<div class="tm-row"><button type="button" id="tm-go">Start the job</button><span class="small muted" id="tm-go-note"></span></div></div></section>
<section class="tm-pane" id="tm-p-members" hidden><div class="mem-head"><h2>How much the team does on its own</h2></div><div class="tm-auto" id="tm-auto"></div>
<div id="tm-settings"></div>
<div class="mem-head"><h2>Members</h2><button type="button" class="secondary" id="tm-add-mem">Add a member</button></div><div id="tm-sugg-all"></div><div id="tm-members"></div></section>
<section class="tm-pane" id="tm-p-types" hidden><div class="mem-head"><h2>Job types and hand-offs</h2></div><p class="small muted">Each stage says who works, what they hand on, and what the next member checks before accepting it. The receiver can send work back with reasons.</p><div id="tm-types"></div></section>
<section class="tm-pane" id="tm-p-rates" hidden><div class="mem-head"><h2>Rate library</h2><span class="small muted" id="tm-rates-n"></span></div>
<p class="small muted">Your own rates (CSV or Excel with Description, Unit and Rate; optional Code, Region, As of, Source). Used only where no published rate with a source and date is found; the source of every rate is shown in the cost plan.</p>
<div class="tm-row"><input type="file" id="tm-rates-file" accept=".csv,.xlsx"><input id="tm-rates-label" maxlength="120" placeholder="Name, e.g. 2025 tender returns"><button type="button" class="secondary" id="tm-rates-up">Upload</button><button type="button" class="secondary" id="tm-rates-demo">Load the fictional demo rate library</button></div>
<div id="tm-batches"></div><div class="table-wrap"><table class="tm-tbl" id="tm-rates"></table></div></section>
<section class="tm-pane" id="tm-p-versions" hidden><div class="mem-head"><h2>Versions</h2><button type="button" class="secondary" id="tm-undo">Undo the latest change</button></div>
<p class="small muted">Every change to a member, a stage, the autonomy or the settings is a new version. Each job runs on the version it started with.</p><div class="table-wrap"><table class="tm-tbl" id="tm-versions"></table></div></section>'''

SCRIPT = r"""
if(PAGE==='teams'){
 const q=new URLSearchParams(location.search);const T={id:q.get('team')||'',d:null,job:q.get('job')||'',docs:[],timer:null,open:new Set(q.get('job')?[q.get('job')]:[]),lib:null};
 const TABS=[['jobs','Jobs'],['start','Start a job'],['members','Members'],['types','Job types'],['rates','Rate library'],['versions','Versions']];
 let tab=(location.hash||'').slice(1);if(!TABS.some(t=>t[0]===tab))tab='jobs';
 const STATUS={running:['Working…','v-run'],waiting:['Waiting for you','v-warn'],blocked:['Stopped: needs you','v-bad'],done:['Signed off','v-ok'],stopped:['Stopped','v-none']};
 const gbp=v=>v==null?'':'£'+Number(v).toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
 const when=iso=>{const d=new Date(iso);return isNaN(d)?iso:d.toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})};
 const b=(label,fn,secondary)=>{const x=el('button',label,secondary?'secondary mini-act':'mini-act');x.type='button';x.onclick=()=>run(async()=>{x.disabled=true;try{await fn()}finally{x.disabled=false}});return x};
 const field=(label,node)=>{const l=el('label',label);l.append(node);return l};
 const input=(v,max,ph)=>{const i=document.createElement('input');i.value=v||'';if(max)i.maxLength=max;if(ph)i.placeholder=ph;return i};
 const area=(v,max,cls)=>{const t=document.createElement('textarea');t.value=v||'';if(max)t.maxLength=max;if(cls)t.className=cls;return t};
 const select=(opts,v)=>{const s=document.createElement('select');for(const [k,l] of opts){const o=el('option',l);o.value=k;s.append(o)}s.value=v;return s};
 function drawTabs(){const box=$('tm-tabs');box.replaceChildren(...TABS.map(([k,l])=>{const c=el('button',l,'chip'+(k===tab?' on':''));c.type='button';c.setAttribute('role','tab');c.setAttribute('aria-selected',k===tab);c.onclick=()=>{tab=k;try{window.history.replaceState(null,'','#'+k)}catch{}drawTabs();if(k==='rates'&&T.d)run(drawRates)};return c}));
  for(const [k] of TABS)$('tm-p-'+k).hidden=k!==tab}
 async function load(){const d=await api(T.id?'/admin/api/teams/'+encodeURIComponent(T.id):'/admin/api/teams');if(!d.team){$('tm-name').textContent='No teams yet';return}T.d=d;T.id=d.team.id;draw()}
 function draw(){const d=T.d,t=d.team;$('tm-name').textContent=t.name;$('tm-desc').textContent=t.description||'';
  const pk=$('tm-pick');pk.replaceChildren(...d.teams.map(x=>{const o=el('option',x.name);o.value=x.id;return o}));pk.value=t.id;
  const waiting=d.jobs.reduce((n,j)=>n+j.pending.length,0)+d.suggestions.length;
  const k=(v,l,sub)=>{const x=el('div','','mi-k');x.append(el('b',v),el('span',l));if(sub)x.append(el('span',sub,'sub'));return x};
  $('tm-tiles').replaceChildren(k(String(t.members.length),'Members',t.members.map(m=>m.role).join(', ')),k('v'+t.version,'Team version',(d.versions[0]||{}).what||''),
   k(String(d.jobs.filter(j=>!['done','stopped'].includes(j.status)).length),'Jobs in progress',d.jobs.filter(j=>j.status==='done').length+' signed off'),
   k(String(waiting),'Waiting for you',d.autonomy[t.autonomy]),k('$'+d.jobs.reduce((n,j)=>n+(j.ai_cost||0),0).toFixed(2),'AI cost of these jobs',''));
  drawTabs();drawJobs();drawStart();drawMembers();drawTypes();run(drawRates);drawVersions();
  clearTimeout(T.timer);if(d.jobs.some(j=>j.status==='running'))T.timer=setTimeout(()=>run(refreshJobs),2500)}
 async function refreshJobs(){const d=await api('/admin/api/teams/'+encodeURIComponent(T.id));T.d=d;draw()}
 // ---------- the jobs board ----------
 function table(head,rows){const t=el('table','','tm-tbl');const h=document.createElement('tr');for(const x of head)h.append(el('th',x));t.append(h);
  for(const r of rows){const tr=document.createElement('tr');for(const c of r){const td=document.createElement('td');if(c&&c.node)td.append(c.node);else td.textContent=c==null?'':String(c);if(typeof c==='number')td.className='n';tr.append(td)}t.append(tr)}return t}
 function linkTo(url,text){const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=text||url;return a}
 function outputView(stage,o){const box=el('div','');if(!o||typeof o!=='object'){box.append(el('pre',String(o||'')));return box}
  if(stage==='plan'){if(o.plan)box.append(el('p',o.plan));if((o.elements||[]).length)box.append(el('p','Elements: '+o.elements.join(', '),'small'));if(o.location)box.append(el('p','Location: '+o.location,'small'));return box}
  if(stage==='measure'){box.append(table(['Ref','Element','Description','Qty','Unit','Source'],(o.items||[]).map(i=>[i.ref,i.element,i.description+(i.approximate?' (approx.)':''),i.quantity,i.unit,i.source_text])));
   if((o.rejected||[]).length)box.append(el('p','Left out: '+o.rejected.map(r=>r.description+' ('+r.reason+')').join('; '),'small muted'));return box}
  if(stage==='price'){box.append(table(['Ref','Description','Qty','Unit','Rate','Where the rate came from'],(o.items||[]).map(i=>[i.ref,i.description,i.quantity,i.unit,i.rate==null?'unpriced':gbp(i.rate),
    {node:i.rate_source==='web'?(()=>{const s=el('span','Published: ');s.append(linkTo(i.source_url,i.source_title||i.source_url),document.createTextNode(' ('+i.source_date+')'));return s})():el('span',i.rate_source==='library'?'Your rate library: '+i.library_row.description+(i.library_row.as_of?' ('+i.library_row.as_of+')':''):'Unpriced: '+(i.rate_note||''))}])));
   if(o.location)box.append(el('p',o.location.note,'small'));if((o.refused_rates||[]).length)box.append(el('p','Rates not used: '+o.refused_rates.map(r=>r.ref+' ('+r.reason+')').join('; '),'small muted'));if(o.searched_with)box.append(el('p','Web search: '+o.searched_with,'small muted'));return box}
  if(stage==='assemble'){const cp=o.cost_plan||{};if(o.summary)box.append(el('p',o.summary));
   box.append(table(['','GBP'],(cp.elements||[]).map(e=>[e.element,gbp(e.subtotal)]).concat([['Construction',gbp(cp.construction)],['Preliminaries',gbp(cp.prelims)],['Contingency',gbp(cp.contingency)],['Fees',gbp(cp.fees)],['Total excluding VAT',gbp(cp.total)]])));
   for(const [h,list] of [['Assumptions',o.assumptions],['Exclusions',o.exclusions]])if((list||[]).length){box.append(el('strong',h,'small'));const ul=el('ul','');for(const x of list)ul.append(el('li',x,'small'));box.append(ul)}
   if((o.risks||[]).length){box.append(el('strong','Risks','small'));const ul=el('ul','');for(const r of o.risks)ul.append(el('li',r.risk+(r.mitigation?' Mitigation: '+r.mitigation:''),'small'));box.append(ul)}return box}
  if(stage==='trends'){box.append(el('p',o.report||''));if((o.comparisons||[]).length)box.append(table(['Ref','Description','Rate now','Past rate','Date','Source','Difference'],o.comparisons.flatMap(c=>c.past.map(p=>[c.ref,c.description,gbp(c.rate_now),gbp(p.rate),p.date,p.source,(p.difference_pct>0?'+':'')+p.difference_pct+'%']))));return box}
  box.append(el('pre',typeof o==='string'?o:JSON.stringify(o,null,1)));return box}
 function pendingBox(j,s){const w=el('div','','tm-wait');const who=s.role||'A member';
  if(s.kind==='question'){w.append(el('strong',who+' asks you'));for(const x of (s.content.questions||[]))w.append(el('p',x));const ta=area('',2000);ta.placeholder='Your answer';w.append(ta,(()=>{const r=el('div','','act-buttons');r.append(b('Send answer',async()=>{if(!ta.value.trim())throw Error('Type your answer.');await api('/admin/api/teams/steps/'+s.id,'POST',{action:'answer',note:ta.value});$('notice').textContent='Answer sent. '+who+' carries on.';await refreshJobs()}),b('Open',()=>openStep(s),true));return r})());return w}
  w.append(el('strong',s.kind==='signoff'?'Ready for your sign-off':who+' → '+(s.to_role||'next')+': approve the hand-off?'));if(s.note)w.append(el('p',s.note));
  if(s.kind==='signoff'){const o=j.outputs;if(o.summary)w.append(el('p',o.summary,'small'))}
  const r=el('div','','act-buttons');r.append(b(s.kind==='signoff'?'Approve and finish':'Approve',async()=>{const x=await api('/admin/api/teams/steps/'+s.id,'POST',{action:'approve'});$('notice').textContent=s.kind==='signoff'?'Signed off'+(x.knowledge_id?' and saved to Knowledge.':'.'):'Approved: '+(s.to_role||'the next member')+' starts now.';await refreshJobs()}),
   b('Send back',async()=>{const n=prompt('What needs to change? '+(s.kind==='signoff'?'The Lead QS reworks the cost plan with your note.':who+' redoes this stage with your note.'));if(!n||!n.trim())return;await api('/admin/api/teams/steps/'+s.id,'POST',{action:'send_back',note:n});$('notice').textContent='Sent back with your note.';await refreshJobs()},true),
   b('Open and discuss with Temple',()=>openStep(s),true));w.append(r);return w}
 function openStep(s){openCard('/admin/api/cards/review/h-'+s.id,{onClose:()=>run(refreshJobs)})}
 function drawJobs(){const box=$('tm-jobs');box.replaceChildren();const jobs=T.d.jobs;$('tm-jobs-note').textContent=jobs.length?jobs.length+' job'+(jobs.length===1?'':'s'):'';
  if(!jobs.length){const p=el('p','No jobs yet. ','muted');const a=el('button','Start a job','secondary mini-act');a.type='button';a.onclick=()=>{tab='start';drawTabs()};p.append(a);box.append(p);return}
  for(const j of jobs){const c=el('div','','tm-job'+(T.job===j.id?' tm-hl':''));c.id='job-'+j.id;const h=el('div','','tm-jh');h.append(el('span',j.ref,'ref'),el('strong',j.title));const [sl,sc]=STATUS[j.status]||[j.status,'v-none'];h.append(el('span',sl,'badge '+sc),el('span','','sp'),el('span',j.job_type_name+' · team v'+j.team_version+' · AI $'+(j.ai_cost||0).toFixed(2)+' · '+when(j.created_at),'small muted'));c.append(h);
   const sg=el('div','','tm-stages');j.stages.forEach((s,i)=>{const x=el('span','','tm-st'+(i<j.stage||j.status==='done'?' done':(i===j.stage&&!['done','stopped'].includes(j.status)?' now':'')));x.append(el('b',s.title),document.createTextNode(' · '+s.role));sg.append(x)});c.append(sg);
   if(j.holder&&!['done','stopped'].includes(j.status))c.append(el('p','With: '+j.holder+(j.status==='running'?' (working)':''),'small'));
   if(j.error){const e=el('div','','tm-err');e.append(el('strong','Stopped: '),document.createTextNode(j.error));const r=el('div','','act-buttons');r.append(b('Resume',async()=>{await api('/admin/api/teams/jobs/'+j.id+'/resume','POST',{});await refreshJobs()}));e.append(r);c.append(e)}
   else if(j.status==='running'&&!j.busy&&(Date.now()-new Date(j.updated_at))>10*60000){const e=el('div','This job stopped while Alice restarted.','tm-err');e.append(b('Resume',async()=>{await api('/admin/api/teams/jobs/'+j.id+'/resume','POST',{});await refreshJobs()}));c.append(e)}
   for(const s of j.pending)c.append(pendingBox(j,s));
   const last=[...j.steps].reverse().find(s=>s.kind==='handoff');if(last&&!j.pending.length)c.append(el('p','Last hand-off ('+last.role+' → '+last.to_role+'): '+(last.note||''),'small muted'));
   const outs=el('div','','tm-out');for(const d of (j.outputs.documents||[])){const a=document.createElement('a');a.href='/documents/'+d.id+'/download';a.textContent='⬇ '+d.kind+': '+d.name;outs.append(a)}if(j.knowledge_id){const a=document.createElement('a');a.href='/admin/knowledge';a.textContent='Saved to Knowledge ↗';outs.append(a)}if(outs.childNodes.length)c.append(outs);
   const det=document.createElement('details');det.className='tm-steps';det.open=T.open.has(j.id);det.ontoggle=()=>{det.open?T.open.add(j.id):T.open.delete(j.id)};det.append(el('summary','Work so far, hand-offs and notes ('+j.steps.length+' steps)'));
   for(const s of j.steps){const row=el('div','','tm-step');const lbl={turn:'Worked',handoff:'Hand-off',sendback:'Sent back',question:'Question',signoff:'Sign-off'}[s.kind]||s.kind;
    row.append(el('span',lbl+' · ','k'),el('span',(s.kind==='sendback'?s.role+' → '+s.to_role:s.kind==='handoff'?s.role+' → '+s.to_role:s.role)+' · '+s.stage+' · '+s.status.replace('_',' ')+' · '+when(s.created_at)+(s.cost_usd?' · $'+s.cost_usd.toFixed(3):'')));
    if(s.note)row.append(el('div',s.note,'small'));if(s.decision_note)row.append(el('div','Your note: '+s.decision_note,'small'));
    if(s.kind==='turn'&&s.status==='done'&&s.content.output){const od=document.createElement('details');od.append(el('summary','What '+s.role+' produced'),outputView(s.stage,s.content.output));
     if((s.content.searches||[]).length){for(const sr of s.content.searches){od.append(el('p','Searched with '+sr.provider+(sr.queries.length?': '+sr.queries.join('; '):''),'small'));const ul=el('ul','');for(const x of sr.sources){const li=el('li','','small');li.append(linkTo(x.url,x.title||x.url),document.createTextNode(x.cited?' · cited':' · seen, not cited'));ul.append(li)}od.append(ul)}}
     row.append(od)}
    det.append(row)}
   c.append(det);const r=el('div','','act-buttons');if(!['done','stopped'].includes(j.status))r.append(b('Stop this job',async()=>{if(!confirm('Stop '+j.ref+'? Its work so far is kept.'))return;await api('/admin/api/teams/jobs/'+j.id+'/stop','POST',{});await refreshJobs()},true));c.append(r);box.append(c)}
  if(T.job){const x=$('job-'+T.job);if(x){x.scrollIntoView({block:'start'});T.job=''}}}
 // ---------- start a job ----------
 function drawStart(){const t=T.d.team;const s=$('tm-jt');const cur=s.value;s.replaceChildren(...t.job_types.map(x=>{const o=el('option',x.name+(x.description?' · '+x.description:''));o.value=x.id;return o}));if(cur)s.value=cur;drawDocs();
  if(!T.lib)run(async()=>{T.lib=(await api('/admin/api/teams/library-files')).files;const l=$('tm-lib');for(const f of T.lib){const o=el('option',f.source+' › '+f.path);o.value=f.path;l.append(o)}})}
 function kindSel(v){return select(Object.entries(T.d.doc_kinds),v)}
 function drawDocs(){const box=$('tm-docs');box.replaceChildren(...T.docs.map((d,i)=>{const r=el('div','','tm-doc');r.append(el('span',(d.path?'📁 ':'📄 ')+d.name));const k=kindSel(d.kind);k.onchange=()=>{d.kind=k.value};k.setAttribute('aria-label','What this document is');const x=el('button','Remove','secondary mini-act');x.type='button';x.onclick=()=>{T.docs.splice(i,1);drawDocs()};r.append(k,x);return r}));
  $('tm-go-note').textContent=T.docs.length?T.docs.length+' document'+(T.docs.length===1?'':'s'):'Add the specification, schedules and drawings.'}
 const guess=n=>/draw|plan|elevation|section|\.dwg/i.test(n)?'drawing':/schedule|\.csv|\.xlsx/i.test(n)?'schedule':/spec/i.test(n)?'spec':'brief';
 $('tm-files').onchange=()=>run(async()=>{for(const f of $('tm-files').files){if(f.size>15*1024*1024)throw Error(f.name+' is larger than 15 MB.');const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(Error('Could not read '+f.name));r.readAsDataURL(f)});T.docs.push({name:f.name,kind:guess(f.name),data})}$('tm-files').value='';drawDocs()});
 $('tm-lib-add').onclick=()=>{const p=$('tm-lib').value;if(!p)return;if(!T.docs.some(d=>d.path===p))T.docs.push({name:p.split('/').pop(),kind:guess(p),path:p});$('tm-lib').value='';drawDocs()};
 $('tm-demo').onclick=()=>run(async()=>{const d=await api('/admin/api/teams/demo-project');$('tm-title').value=d.title;$('tm-brief').value=d.brief;$('tm-loc').value=d.location;$('tm-client').value='';T.docs=d.documents.map(x=>({name:x.name,kind:x.kind,text:x.text}));drawDocs();
  $('notice').textContent='Demo project loaded (fictional). Load the fictional demo rate library on the Rate library tab too, then Start the job.'});
 $('tm-go').onclick=()=>run(async()=>{const go=$('tm-go');go.disabled=true;try{const body={job_type:$('tm-jt').value,title:$('tm-title').value,brief:$('tm-brief').value,location:$('tm-loc').value,client:$('tm-client').value,
   uploads:T.docs.filter(d=>!d.path).map(d=>({name:d.name,kind:d.kind,...(d.text!=null?{text:d.text}:{data:d.data})})),library:T.docs.filter(d=>d.path).map(d=>({path:d.path,kind:d.kind}))};
  const j=await api('/admin/api/teams/'+encodeURIComponent(T.id)+'/jobs','POST',body);T.docs=[];for(const id of ['tm-title','tm-brief','tm-loc','tm-client'])$(id).value='';T.job=j.id;T.open.add(j.id);tab='jobs';try{window.history.replaceState(null,'','#jobs')}catch{}
  $('notice').textContent=j.ref+' started. '+(T.d.team.autonomy==='approve'?'Each hand-off will wait for you here and on Actions.':'It runs on its own; questions and the final output wait for you.');await refreshJobs()}finally{go.disabled=false}});
 // ---------- members, autonomy, settings, Temple's suggestions ----------
 function drawMembers(){const t=T.d.team,d=T.d;const au=$('tm-auto');au.replaceChildren();
  for(const [k,l] of Object.entries(d.autonomy)){const lab=el('label','');const r=document.createElement('input');r.type='radio';r.name='tm-autonomy';r.value=k;r.checked=t.autonomy===k;
   r.onchange=()=>run(async()=>{await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/autonomy','PUT',{autonomy:k});$('notice').textContent='Saved as a new team version: '+l+'.';await load()});
   const txt=el('span','');txt.append(el('strong',l),el('div',k==='approve'?'Every hand-off waits on Actions with Approve, Send back and Discuss with Temple.':'Hand-offs go ahead on their own; questions and the final output still wait for you.','small muted'));lab.append(r,txt);au.append(lab)}
  const st=$('tm-settings');st.replaceChildren();const keys=Object.keys(t.settings||{});
  if(keys.length){st.append(el('h3','Percentages applied by Alice'));const row=el('div','','tm-row');const ins={};for(const k of keys){const i=input(String(t.settings[k]),6);i.type='number';i.step='0.5';i.min='0';i.max='50';i.style.width='90px';ins[k]=i;row.append(field(k.replace('_pct','').replace(/^./,c=>c.toUpperCase())+' %',i))}
   row.append(b('Save',async()=>{const s={};for(const k of keys)s[k]=+ins[k].value;await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/settings','PUT',{settings:s});$('notice').textContent='Saved as a new team version.';await load()},true));st.append(row)}
  const box=$('tm-members');box.replaceChildren();
  for(const m of t.members)box.append(memberCard(m));
  const left=d.suggestions.filter(s=>!t.members.some(m=>m.id===s.member));$('tm-sugg-all').replaceChildren(...left.map(suggBox))}
 function checks(all,on){const w=el('div','','tm-checks');const boxes=[];for(const [k,l] of all){const lab=el('label','');const c=document.createElement('input');c.type='checkbox';c.value=k;c.checked=on.includes(k);boxes.push(c);lab.append(c,document.createTextNode(l));w.append(lab)}w.values=()=>boxes.filter(c=>c.checked).map(c=>c.value);return w}
 function suggBox(s){const w=el('div','','tm-sugg');w.append(el('strong','Temple suggests new instructions'+(s.role?' for '+s.role:'')),el('p',s.reason,'small'));
  const cur=document.createElement('details');cur.append(el('summary','Current instructions'),el('pre',s.current_text));w.append(cur,el('div','Suggested instructions','small'),el('pre',s.proposed));
  const r=el('div','','act-buttons');r.append(b('Approve: use these',async()=>{await api('/admin/api/teams/suggestions/'+s.id,'POST',{action:'approve'});$('notice').textContent='Applied as a new team version.';await load()}),b('Reject',async()=>{await api('/admin/api/teams/suggestions/'+s.id,'POST',{action:'reject'});await load()},true));w.append(r);return w}
 function memberCard(m){const t=T.d.team,d=T.d;const c=el('div','','tm-mem');c.append(el('h3',m.role));
  const role=input(m.role,80),purpose=area(m.purpose,600),ins=area(m.instructions,6000,'ins'),prov=select(Object.entries(d.models),m.provider);purpose.rows=2;
  const cats=checks(d.categories.map(x=>[x,x]),m.categories||[]),packs=checks(Object.entries(d.packs),m.packs||[]);
  const g=el('div','','grid');g.append(field('Role name',role),field('Model',prov));c.append(g,field('Purpose',purpose),field('Standing instructions',ins),field('Knowledge categories it may use (none = no knowledge)',cats),field('Its own rule packs',packs));
  const used=t.job_types.flatMap(jt=>jt.stages.filter(s=>s.member===m.id).map(s=>jt.name+' › '+s.title));if(used.length)c.append(el('p','Works on: '+used.join(', '),'small muted'));
  const r=el('div','','act-buttons');r.append(b('Save',async()=>{await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/members/'+encodeURIComponent(m.id),'PUT',{role:role.value,purpose:purpose.value,instructions:ins.value,provider:prov.value,categories:cats.values(),packs:packs.values()});$('notice').textContent='Saved as a new team version.';await load()}),
   b('Remove',async()=>{if(!confirm('Remove '+m.role+' from the team? (You can undo it on the Versions tab.)'))return;await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/members/'+encodeURIComponent(m.id),'DELETE');await load()},true));c.append(r);
  for(const s of d.suggestions.filter(s=>s.member===m.id))c.append(suggBox(s));
  c.append(talk(m));return c}
 function talk(m){const t=T.d.team;const wrap=document.createElement('details');wrap.className='dec-talk';const sm=el('summary','');sm.append(el('span','Ask Temple about '+m.role,'dec-talk-t'),el('span','How its jobs went, and better instructions (applied only if you approve)','small muted'));wrap.append(sm);
  const url='/admin/api/teams/'+encodeURIComponent(t.id)+'/members/'+encodeURIComponent(m.id)+'/discussion';
  const log=el('div','','dec-talk-log'),form=el('form','','dec-talk-form'),ta=document.createElement('textarea'),send=el('button','Send');ta.rows=2;ta.maxLength=4000;ta.placeholder='Ask Temple, e.g. what keeps being sent back?';ta.setAttribute('aria-label','Message to Temple');send.type='submit';
  const starters=el('div','','dec-talk-starters');for(const s of ['How could '+m.role+'’s instructions be better?','What keeps being sent back, and why?','What did Stefan have to correct?']){const x=el('button',s,'chip');x.type='button';x.onclick=()=>{ta.value=s;form.requestSubmit()};starters.append(x)}
  form.append(ta,send);wrap.append(log,starters,form);let loaded=false;
  const show=ms=>{log.replaceChildren(...ms.map(x=>{const bb=el('div','','dec-msg '+(x.role==='temple'?'from-t':'from-you'));bb.append(el('div',x.role==='temple'?'Temple':'You','who'),el('div',x.content,'txt'));if(x.note)bb.append(el('div','Suggestion waiting for your approval above: '+x.note,'small'));return bb}));starters.hidden=ms.length>0;log.scrollTop=log.scrollHeight};
  wrap.addEventListener('toggle',()=>{if(wrap.open&&!loaded){loaded=true;run(async()=>show((await api(url)).messages))}});
  form.onsubmit=e=>{e.preventDefault();const msg=ta.value.trim();if(!msg||send.disabled)return;send.disabled=true;ta.value='';const wait=el('div','Temple is thinking…','dec-msg from-t thinking');log.append(wait);
   run(async()=>{try{const r=await api(url,'POST',{message:msg});show(r.messages);if(r.suggestion){$('notice').textContent='Temple suggested new instructions: they wait for your approval.';await load()}}catch(err){wait.remove();ta.value=msg;throw err}finally{send.disabled=false}})};
  return wrap}
 $('tm-add-mem').onclick=()=>run(async()=>{const role=prompt('Role name for the new member, e.g. Services Engineer');if(!role||!role.trim())return;await api('/admin/api/teams/'+encodeURIComponent(T.id)+'/members','POST',{role,provider:'claude_sonnet',purpose:'',instructions:''});$('notice').textContent=role+' added. Give them a purpose and instructions, then a stage on Job types.';await load()});
 // ---------- job types: stages and hand-offs ----------
 function drawTypes(){const t=T.d.team;const box=$('tm-types');box.replaceChildren();const mopts=t.members.map(m=>[m.id,m.role]);
  for(const jt of t.job_types){const c=el('div','','tm-mem');c.append(el('h3',jt.name));const name=input(jt.name,80),desc=area(jt.description,600);desc.rows=2;c.append(field('Name',name),field('Description',desc));
   const flow=el('p','','tm-flow');c.append(flow);const list=el('div','');c.append(list);let rows=jt.stages.map(s=>({...s}));
   const redraw=()=>{flow.textContent='Flow: '+rows.map(s=>(t.members.find(m=>m.id===s.member)||{role:'?'}).role).join(' → ')+' → you (sign-off)';list.replaceChildren(...rows.map((s,i)=>{const w=el('div','','tm-stage');
    const ti=input(s.title,80),mem=select(mopts,s.member),task=area(s.task,2000),hands=area(s.hands,600),chk=area(s.checks,1000);task.rows=2;hands.rows=2;chk.rows=2;
    for(const [n,k] of [[ti,'title'],[mem,'member'],[task,'task'],[hands,'hands'],[chk,'checks']])n.oninput=n.onchange=()=>{s[k]=n.value;if(k==='member')flow.textContent='Flow: '+rows.map(x=>(t.members.find(m=>m.id===x.member)||{role:'?'}).role).join(' → ')+' → you (sign-off)'};
    const top=el('div','','tm-row');top.append(el('strong',(i+1)+'.'),field('Stage',ti),field('Who works',mem));
    const mv=el('div','','act-buttons');const up=el('button','↑','secondary mini-act'),dn=el('button','↓','secondary mini-act'),rm=el('button','Remove','secondary mini-act');for(const x of [up,dn,rm])x.type='button';up.disabled=!i;dn.disabled=i===rows.length-1;
    up.onclick=()=>{[rows[i-1],rows[i]]=[rows[i],rows[i-1]];redraw()};dn.onclick=()=>{[rows[i+1],rows[i]]=[rows[i],rows[i+1]];redraw()};rm.onclick=()=>{if(rows.length<2)return;rows.splice(i,1);redraw()};mv.append(up,dn,rm);top.append(mv);
    w.append(top,field('Task',task),field('What they hand on',hands),field(i?'What they check before accepting the work handed to them':'What they check (first stage: nothing is handed to them)',chk));
    if(s.handler&&s.handler!=='generic')w.append(el('span','Built-in step: '+s.handler.replace('qs_','')+' (its source and arithmetic checks run in code)','small muted'));return w}))};
   redraw();const r=el('div','','act-buttons');r.append(b('Add a stage',()=>{rows.push({key:'',title:'New stage',member:mopts[0]?mopts[0][0]:'',task:'',hands:'',checks:'',handler:'generic'});redraw()},true),
    b('Save stages',async()=>{await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/job-types/'+encodeURIComponent(jt.id),'PUT',{name:name.value,description:desc.value,stages:rows.map(s=>({key:s.key||'',title:s.title,member:s.member,task:s.task||'',hands:s.hands||'',checks:s.checks||''}))});$('notice').textContent='Saved as a new team version. Jobs already running keep the version they started on.';await load()}));
   c.append(r);box.append(c)}
  const add=el('div','','act-buttons');add.append(b('Add a job type',async()=>{const n=prompt('Name of the job type, e.g. Feasibility estimate');if(!n||!n.trim())return;await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/job-types','POST',{name:n});$('notice').textContent='Job type added with one stage. Add the stages and hand-offs, then Save stages.';await load()},true));box.append(add)}
 // ---------- rate library ----------
 async function drawRates(){const t=T.d.team,r=T.d.rates;$('tm-rates-n').textContent=r.count+' rate'+(r.count===1?'':'s');
  $('tm-batches').replaceChildren(...r.batches.map(x=>{const row=el('div','','tm-doc');row.append(el('span',x.batch_name+' · '+x.n+' rates · added '+when(x.added_at)),b('Remove',async()=>{if(!confirm('Remove the '+x.n+' rates in “'+x.batch_name+'”?'))return;await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/rates/'+x.batch,'DELETE');await load()},true));return row}));
  if(tab!=='rates'){$('tm-rates').replaceChildren();return}
  const rows=(await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/rates')).rates;$('tm-rates').replaceChildren(...(rows.length?[table(['Code','Description','Unit','Rate','Region','As of','Source'],rows.slice(0,300).map(x=>[x.code,x.description,x.unit,gbp(x.rate),x.region,x.as_of,x.source]))]:[]))}
 $('tm-rates-up').onclick=()=>run(async()=>{const f=$('tm-rates-file').files[0];if(!f)throw Error('Choose a CSV or Excel file first.');const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(Error('Could not read the file.'));r.readAsDataURL(f)});
  const x=await api('/admin/api/teams/'+encodeURIComponent(T.id)+'/rates','POST',{name:f.name,data,label:$('tm-rates-label').value});$('notice').textContent=x.added+' rates added'+(x.skipped?', '+x.skipped+' rows skipped (no description, unit or rate)':'')+'.';$('tm-rates-file').value='';await load()});
 $('tm-rates-demo').onclick=()=>run(async()=>{const x=await api('/admin/api/teams/'+encodeURIComponent(T.id)+'/rates/demo','POST',{});$('notice').textContent=x.added+' fictional demo rates added.';await load()});
 // ---------- versions ----------
 function drawVersions(){const t=T.d.team,box=$('tm-versions');box.replaceChildren();const h=document.createElement('tr');for(const x of ['Version','When','Who','What changed',''])h.append(el('th',x));box.append(h);
  for(const v of T.d.versions){const tr=document.createElement('tr');tr.append(el('td','v'+v.version+(v.version===t.version?' (current)':'')),el('td',when(v.changed_at)),el('td',v.changed_by),el('td',v.what));const td=document.createElement('td');
   if(v.version<t.version)td.append(b('Restore',async()=>{if(!confirm('Restore v'+v.version+'? It becomes a new version; nothing is lost.'))return;await api('/admin/api/teams/'+encodeURIComponent(t.id)+'/restore','POST',{version:v.version});$('notice').textContent='Restored v'+v.version+' as a new version.';await load()},true));tr.append(td);box.append(tr)}
  $('tm-undo').disabled=t.version<2}
 $('tm-undo').onclick=()=>run(async()=>{const v=T.d.versions[0];if(!confirm('Undo v'+v.version+': '+v.what+'?'))return;await api('/admin/api/teams/'+encodeURIComponent(T.id)+'/restore','POST',{undo:true});$('notice').textContent='Undone. That is a new version too, so you can undo the undo.';await load()});
 $('tm-pick').onchange=()=>{T.id=$('tm-pick').value;run(load)};
 $('tm-new').onclick=()=>run(async()=>{const n=prompt('Name of the new team');if(!n||!n.trim())return;const t=await api('/admin/api/teams','POST',{name:n,description:''});T.id=t.id;tab='members';await load();$('notice').textContent='Team created. Add members, then a job type.'});
 window.addEventListener('hashchange',()=>{const h=location.hash.slice(1);if(TABS.some(x=>x[0]===h)&&h!==tab){tab=h;drawTabs();if(h==='rates'&&T.d)run(drawRates)}});
 drawTabs();run(load);
}
"""
