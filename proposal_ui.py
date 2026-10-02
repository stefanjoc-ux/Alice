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
.pe-rates .bad{color:#b3261e;font-weight:600}.pe-add{margin-top:8px}.pe-addbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.pe-paste{display:grid;gap:6px;margin-top:10px;padding:10px 12px;border:1px dashed var(--line2,#b9cbd8);border-radius:10px;background:#fbfcfd}.pe-paste textarea{width:100%;font-family:ui-monospace,Consolas,monospace;font-size:13px}
.pe-sec textarea.pe-inc{grid-column:1/-1;background:#fbfaf6;border-color:#e2d6b0}.pe-incbtn{margin-left:auto!important}
.pe-note{font-size:12.5px;color:var(--muted);margin:6px 0 10px}
@media(max-width:700px){.pe-rates thead{display:none}.pe-rates tr{display:grid;grid-template-columns:1fr 1fr;gap:4px;border-top:1px solid var(--line);padding:6px 0}.pe-rates td:first-child{grid-column:1/-1}}
'''

PE_JS = r'''
const PE=(()=>{
 const mk=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e};
 const btn=(label,fn,title)=>{const b=mk('button',label,'secondary pe-mini');b.type='button';if(title){b.title=title;b.setAttribute('aria-label',title)}b.onclick=fn;return b};
 function sections(box,items,opts={}){let list=(items||[]).map(s=>({title:s.title||'',guidance:s.guidance||'',include:s.include||'',keep:!!s.keep,source:s.source||''}));
  function draw(){box.replaceChildren();const wrap=mk('div','','pe-list');
   list.forEach((s,i)=>{const row=mk('div','','pe-sec');const t=document.createElement('input');t.type='text';t.maxLength=120;t.value=s.title;t.placeholder='Section title';t.setAttribute('aria-label','Section '+(i+1)+' title');t.oninput=()=>{s.title=t.value};
    const tools=mk('div','','pe-tools');tools.append(btn('↑',()=>{if(i){[list[i-1],list[i]]=[list[i],list[i-1]];draw()}},'Move up'),btn('↓',()=>{if(i<list.length-1){[list[i+1],list[i]]=[list[i],list[i+1]];draw()}},'Move down'),btn('Remove',()=>{list.splice(i,1);draw()},'Remove section '+(s.title||(i+1))));
    const g=document.createElement('textarea');g.maxLength=1500;g.rows=2;g.value=s.guidance;g.placeholder=s.keep?'Standard text is copied from the template as it is.':'What this section should cover: content suggestions, points to make, length, a table to include…';g.setAttribute('aria-label','Guidance for '+(s.title||'section '+(i+1)));g.oninput=()=>{s.guidance=g.value};g.disabled=s.keep&&s.source==='template';
    const meta=mk('div','','pe-meta');if(s.source)meta.append(mk('span',s.source==='template'?'From the template':s.source==='format and flow'?'Format and flow':'Added','pe-tag'+(s.source==='template'?' template':'')));
    const kl=mk('label');const kc=document.createElement('input');kc.type='checkbox';kc.checked=s.keep;kc.onchange=()=>{s.keep=kc.checked;draw()};kl.append(kc,document.createTextNode(' Standard text (keep as written)'));if(s.source==='template'||opts.allowKeep)meta.append(kl);
    if(s.keep)meta.append(mk('span','Kept word for word','pe-tag keep'));
    row.append(t,tools,g);
    if(opts.include&&!s.keep){const inc=document.createElement('textarea');inc.maxLength=4000;inc.rows=3;inc.value=s.include;inc.placeholder='Paste points or wording to include in this section: the writer works them in, keeping every point.';inc.setAttribute('aria-label','Text to include in '+(s.title||'section '+(i+1)));inc.className='pe-inc';inc.oninput=()=>{s.include=inc.value};
     if(s.include||s.showInc)row.append(inc);else{const b=btn('+ Text to include',()=>{s.showInc=true;draw();box.querySelectorAll('.pe-sec')[i]?.querySelector('.pe-inc')?.focus()},'Add text to include in '+(s.title||'this section'));b.classList.add('pe-incbtn');meta.append(b)}}
    row.append(meta);wrap.append(row)});
   if(!list.length)wrap.append(mk('p',opts.empty||'No sections yet.','pe-note'));
   const add=btn('Add section',()=>{list.push({title:'',guidance:'',keep:false,source:'added'});draw();const ins=box.querySelectorAll('.pe-sec input[type=text]');ins[ins.length-1]?.focus()});add.classList.add('pe-add');
   box.append(wrap,add)}
  draw();return {value:()=>list.filter(s=>s.title.trim()).map(s=>({title:s.title.trim(),guidance:s.guidance.trim(),include:(s.include||'').trim(),keep:s.keep})),set:x=>{list=(x||[]).map(s=>({...s}));draw()},add:x=>{list=list.concat((x||[]).map(s=>({...s})));draw()}}}
 const gbp=v=>'£'+Number(v||0).toLocaleString('en-GB',{maximumFractionDigits:2});
 function parseRates(text){const lines=String(text||'').split(/\r?\n/).map(l=>l.replace(/\s+$/,'')).filter(l=>l.trim()&&!/^\s*\|?\s*:?-{2,}/.test(l));const notes=[];
  const split=l=>(/\t/.test(l)?l.split('\t'):/\|/.test(l)?l.replace(/^\s*\||\|\s*$/g,'').split('|'):/;/.test(l)&&!/,\d{3}/.test(l)?l.split(';'):/ {2,}/.test(l)?l.split(/ {2,}/):l.split(',')).map(c=>c.trim());
  const num=c=>{const m=String(c).replace(/[£$€\s]/g,'').replace(/,(?=\d{3}\b)/g,'').match(/^-?\d+(\.\d+)?/);return m?m[0]:null};
  const unitOf=c=>/hour|hr\b|hourly|\/h\b/i.test(c)?'hour':/day|daily|\/d\b/i.test(c)?'day':null;
  let rows=lines.map(split).filter(r=>r.some(c=>c));if(!rows.length)return {rows:[],notes};
  let map=null;const hi=rows.findIndex(r=>r.filter(c=>c).length>=2&&r.every(c=>num(c)===null)&&r.some(c=>/role|grade|resource|position|title|name|cost|sell|rate|price|charge|unit/i.test(c)));
  const pre=hi>0?rows.slice(0,hi).flat().map(unitOf).find(Boolean):null;const h=hi>=0?rows[hi]:[];
  if(hi>=0){map={hdrUnit:pre};rows=rows.slice(hi);
   h.forEach((c,i)=>{const x=c.toLowerCase();if(map.role==null&&/role|grade|resource|position|title|name|job/.test(x))map.role=i;else if(map.cost==null&&/cost|internal|buy|pay/.test(x))map.cost=i;else if(map.sell==null&&/sell|charge|price|client|rate/.test(x))map.sell=i;else if(map.unit==null&&/unit|per|basis/.test(x))map.unit=i;
    if(!map.hdrUnit)map.hdrUnit=unitOf(c)});rows=rows.slice(1)}
  const out=[];for(const r of rows){let role,cost,sell,unit;
   if(map){role=r[map.role??0]||'';cost=map.cost!=null?num(r[map.cost]):null;sell=map.sell!=null?num(r[map.sell]):null;unit=(map.unit!=null&&unitOf(r[map.unit]||''))||map.hdrUnit||null;
    if(sell===null&&cost!==null&&map.sell==null){sell=cost;cost=null}}
   else{role=r.find(c=>c&&num(c)===null&&!unitOf(c))||'';const ns=r.map(num).filter(x=>x!==null);if(ns.length>=2){cost=ns[0];sell=ns[1]}else{cost=null;sell=ns[0]??null}unit=r.map(unitOf).find(Boolean)||null}
   role=role.replace(/\s+/g,' ').trim().slice(0,80);if(!role||sell===null)continue;
   out.push({role,unit:unit||'day',cost:cost??'',sell})}
  if(out.some(x=>x.cost===''))notes.push('Some rows have no cost rate: add it so Alice can work out the margin.');
  if(rows.length>out.length)notes.push((rows.length-out.length)+' row'+(rows.length-out.length===1?'':'s')+' skipped (no role or no rate).');
  return {rows:out.slice(0,40),notes}}
 function rates(box,items,units){let pasteOpen=false;let list=(items||[]).map(r=>({role:r.role||'',unit:r.unit||'day',cost:r.cost??'',sell:r.sell??''}));
  function draw(){box.replaceChildren();const t=mk('table','','pe-rates');const h=document.createElement('thead');const hr=document.createElement('tr');
   for(const x of ['Role','Unit','Cost rate','Sell rate','Margin',''])hr.append(mk('th',x));h.append(hr);t.append(h);const tb=document.createElement('tbody');
   list.forEach((r,i)=>{const tr=document.createElement('tr');const role=document.createElement('input');role.maxLength=80;role.value=r.role;role.placeholder='e.g. Solution architect';role.setAttribute('aria-label','Role '+(i+1));role.oninput=()=>{r.role=role.value};
    const u=document.createElement('select');u.setAttribute('aria-label','Unit for '+(r.role||'role '+(i+1)));for(const k of units||['day','hour']){const o=mk('option','per '+k);o.value=k;u.append(o)}u.value=r.unit;u.onchange=()=>{r.unit=u.value};
    const m=mk('td','','num');const upd=()=>{const c=parseFloat(String(r.cost).replace(/[£,]/g,'')),s=parseFloat(String(r.sell).replace(/[£,]/g,''));m.textContent=s>0&&!isNaN(c)?((s-c)/s*100).toFixed(1)+'%':'—';m.classList.toggle('bad',s>0&&c>s)};
    const num=(k,label)=>{const x=document.createElement('input');x.inputMode='decimal';x.value=r[k];x.placeholder='£';x.setAttribute('aria-label',label+' for '+(r.role||'role '+(i+1)));x.oninput=()=>{r[k]=x.value;upd()};return x};
    const c1=document.createElement('td');c1.append(role);const c2=document.createElement('td');c2.append(u);const c3=document.createElement('td');c3.append(num('cost','Cost rate'));const c4=document.createElement('td');c4.append(num('sell','Sell rate'));
    const c6=document.createElement('td');c6.append(btn('Remove',()=>{list.splice(i,1);draw()},'Remove '+(r.role||'role')));upd();tr.append(c1,c2,c3,c4,m,c6);tb.append(tr)});
   t.append(tb);box.append(t);if(!list.length)box.append(mk('p','No roles yet: the proposal will have no pricing table.','pe-note'));
   const add=btn('Add role',()=>{list.push({role:'',unit:'day',cost:'',sell:''});draw();const ins=box.querySelectorAll('.pe-rates tbody input');ins[ins.length-4]?.focus()});add.classList.add('pe-add');
   const pb=btn('Paste a table',()=>{pasteOpen=!pasteOpen;draw();box.querySelector('.pe-paste textarea')?.focus()},'Paste a rate card copied from Excel, Word or an email');pb.classList.add('pe-add');
   const bar=mk('div','','pe-addbar');bar.append(add,pb);box.append(bar);
   if(pasteOpen){const pp=mk('div','','pe-paste');const ta=document.createElement('textarea');ta.rows=5;ta.placeholder='Copy the rows from Excel, Word or an email and paste them here, for example:\nRole\tCost\tSell\nSolution architect\t650\t1200\nConsultant\t450\t850';ta.setAttribute('aria-label','Pasted rate card');
    const msg=mk('p','','pe-note');const use=btn('Replace the rate card',()=>apply(true)),more=btn('Add to the rate card',()=>apply(false)),cancel=btn('Cancel',()=>{pasteOpen=false;draw()});
    const show=()=>{const r=parseRates(ta.value);msg.textContent=ta.value.trim()?(r.rows.length?r.rows.length+' role'+(r.rows.length===1?'':'s')+' found: '+r.rows.slice(0,4).map(x=>x.role+' ('+(x.cost!==''?'cost '+x.cost+', ':'')+'sell '+x.sell+' per '+x.unit+')').join('; ')+(r.rows.length>4?'\u2026':'')+'.':'No roles found yet.')+(r.notes.length?' '+r.notes.join(' '):''):'Columns are read by their headings (role, unit, cost, sell); without headings, the first text is the role, the first number the cost and the second the sell rate.'};
    const apply=replace=>{const r=parseRates(ta.value);if(!r.rows.length){show();return}list=replace?r.rows:list.filter(x=>x.role.trim()).concat(r.rows);pasteOpen=false;draw()};
    ta.oninput=show;const act=mk('div','','pe-addbar');act.append(use,more,cancel);pp.append(ta,msg,act);box.append(pp);show()}}
  draw();return {value:()=>list.filter(r=>r.role.trim()).map(r=>({role:r.role.trim(),unit:r.unit,cost:String(r.cost).trim()||'0',sell:String(r.sell).trim()||'0'})),set:x=>{list=(x||[]).map(r=>({...r}));draw()}}}
 return {sections,rates,parseRates,gbp,mk}})();
'''
