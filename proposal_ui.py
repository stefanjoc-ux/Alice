"""Editors shared by the proposal page and the Assistants page: Format and flow (sections) and the Rate card.
Self-contained JavaScript (its own helpers) so it can sit on either page."""

PE_CSS = r'''
.pe-list{display:grid;gap:8px}.pe-sec{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 10px;align-items:start;background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.pe-sec input[type=text]{font-weight:600}.pe-sec textarea{grid-column:1/-1;min-height:44px;resize:vertical}
.pe-sec .pe-tools{display:flex;gap:4px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.pe-sec .pe-meta{grid-column:1/-1;display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12.5px;color:var(--muted)}
.pe-tag{font-size:11.5px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);background:#f4f6f8;color:#4b5a66}
.pe-tag.template{background:#e3f1f6;color:#064b63;border-color:#89b1bf}.pe-tag.keep{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}
.pe-mini{padding:3px 9px!important;font-size:12px!important;margin:0!important;min-height:0!important}
.pe-rates{width:100%;border-collapse:collapse;font-size:14px}.pe-rates th{text-align:left;font-size:12.5px;color:var(--muted);font-weight:600;padding:4px 6px}
.pe-rates td{padding:4px 6px;vertical-align:middle}.pe-rates input,.pe-rates select{width:100%;min-width:0}.pe-rates td.num{text-align:right;white-space:nowrap}
.pe-rates .bad{color:#b3261e;font-weight:600}.pe-add{margin-top:8px}
.pe-note{font-size:12.5px;color:var(--muted);margin:6px 0 10px}
@media(max-width:700px){.pe-rates thead{display:none}.pe-rates tr{display:grid;grid-template-columns:1fr 1fr;gap:4px;border-top:1px solid var(--line);padding:6px 0}.pe-rates td:first-child{grid-column:1/-1}}
'''

PE_JS = r'''
const PE=(()=>{
 const mk=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e};
 const btn=(label,fn,title)=>{const b=mk('button',label,'secondary pe-mini');b.type='button';if(title){b.title=title;b.setAttribute('aria-label',title)}b.onclick=fn;return b};
 function sections(box,items,opts={}){let list=(items||[]).map(s=>({title:s.title||'',guidance:s.guidance||'',keep:!!s.keep,source:s.source||''}));
  function draw(){box.replaceChildren();const wrap=mk('div','','pe-list');
   list.forEach((s,i)=>{const row=mk('div','','pe-sec');const t=document.createElement('input');t.type='text';t.maxLength=120;t.value=s.title;t.placeholder='Section title';t.setAttribute('aria-label','Section '+(i+1)+' title');t.oninput=()=>{s.title=t.value};
    const tools=mk('div','','pe-tools');tools.append(btn('↑',()=>{if(i){[list[i-1],list[i]]=[list[i],list[i-1]];draw()}},'Move up'),btn('↓',()=>{if(i<list.length-1){[list[i+1],list[i]]=[list[i],list[i+1]];draw()}},'Move down'),btn('Remove',()=>{list.splice(i,1);draw()},'Remove section '+(s.title||(i+1))));
    const g=document.createElement('textarea');g.maxLength=1500;g.rows=2;g.value=s.guidance;g.placeholder=s.keep?'Standard text is copied from the template as it is.':'What this section should cover: content suggestions, points to make, length, a table to include…';g.setAttribute('aria-label','Guidance for '+(s.title||'section '+(i+1)));g.oninput=()=>{s.guidance=g.value};g.disabled=s.keep&&s.source==='template';
    const meta=mk('div','','pe-meta');if(s.source)meta.append(mk('span',s.source==='template'?'From the template':s.source==='format and flow'?'Format and flow':'Added','pe-tag'+(s.source==='template'?' template':'')));
    const kl=mk('label');const kc=document.createElement('input');kc.type='checkbox';kc.checked=s.keep;kc.onchange=()=>{s.keep=kc.checked;draw()};kl.append(kc,document.createTextNode(' Standard text (keep as written)'));if(s.source==='template'||opts.allowKeep)meta.append(kl);
    if(s.keep)meta.append(mk('span','Kept word for word','pe-tag keep'));
    row.append(t,tools,g,meta);wrap.append(row)});
   if(!list.length)wrap.append(mk('p',opts.empty||'No sections yet.','pe-note'));
   const add=btn('Add section',()=>{list.push({title:'',guidance:'',keep:false,source:'added'});draw();const ins=box.querySelectorAll('.pe-sec input[type=text]');ins[ins.length-1]?.focus()});add.classList.add('pe-add');
   box.append(wrap,add)}
  draw();return {value:()=>list.filter(s=>s.title.trim()).map(s=>({title:s.title.trim(),guidance:s.guidance.trim(),keep:s.keep})),set:x=>{list=(x||[]).map(s=>({...s}));draw()}}}
 const gbp=v=>'£'+Number(v||0).toLocaleString('en-GB',{maximumFractionDigits:2});
 function rates(box,items,units){let list=(items||[]).map(r=>({role:r.role||'',unit:r.unit||'day',cost:r.cost??'',sell:r.sell??''}));
  function draw(){box.replaceChildren();const t=mk('table','','pe-rates');const h=document.createElement('thead');const hr=document.createElement('tr');
   for(const x of ['Role','Unit','Cost rate','Sell rate','Margin',''])hr.append(mk('th',x));h.append(hr);t.append(h);const tb=document.createElement('tbody');
   list.forEach((r,i)=>{const tr=document.createElement('tr');const role=document.createElement('input');role.maxLength=80;role.value=r.role;role.placeholder='e.g. Solution architect';role.setAttribute('aria-label','Role '+(i+1));role.oninput=()=>{r.role=role.value};
    const u=document.createElement('select');u.setAttribute('aria-label','Unit for '+(r.role||'role '+(i+1)));for(const k of units||['day','hour']){const o=mk('option','per '+k);o.value=k;u.append(o)}u.value=r.unit;u.onchange=()=>{r.unit=u.value};
    const m=mk('td','','num');const upd=()=>{const c=parseFloat(String(r.cost).replace(/[£,]/g,'')),s=parseFloat(String(r.sell).replace(/[£,]/g,''));m.textContent=s>0&&!isNaN(c)?((s-c)/s*100).toFixed(1)+'%':'—';m.classList.toggle('bad',s>0&&c>s)};
    const num=(k,label)=>{const x=document.createElement('input');x.inputMode='decimal';x.value=r[k];x.placeholder='£';x.setAttribute('aria-label',label+' for '+(r.role||'role '+(i+1)));x.oninput=()=>{r[k]=x.value;upd()};return x};
    const c1=document.createElement('td');c1.append(role);const c2=document.createElement('td');c2.append(u);const c3=document.createElement('td');c3.append(num('cost','Cost rate'));const c4=document.createElement('td');c4.append(num('sell','Sell rate'));
    const c6=document.createElement('td');c6.append(btn('Remove',()=>{list.splice(i,1);draw()},'Remove '+(r.role||'role')));upd();tr.append(c1,c2,c3,c4,m,c6);tb.append(tr)});
   t.append(tb);box.append(t);if(!list.length)box.append(mk('p','No roles yet: the proposal will have no pricing table.','pe-note'));
   const add=btn('Add role',()=>{list.push({role:'',unit:'day',cost:'',sell:''});draw();const ins=box.querySelectorAll('.pe-rates tbody input');ins[ins.length-4]?.focus()});add.classList.add('pe-add');box.append(add)}
  draw();return {value:()=>list.filter(r=>r.role.trim()).map(r=>({role:r.role.trim(),unit:r.unit,cost:String(r.cost).trim()||'0',sell:String(r.sell).trim()||'0'})),set:x=>{list=(x||[]).map(r=>({...r}));draw()}}}
 return {sections,rates,gbp,mk}})();
'''
