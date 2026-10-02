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
.pe-rtop{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 8px}.pe-rtop input[type=search]{flex:1;min-width:160px}.pe-rtop .on{background:var(--teal)!important;color:#fff!important;border-color:var(--teal)!important}
.pe-target{display:flex!important;align-items:center;gap:6px;font-weight:600!important;font-size:14px}.pe-target input{width:64px!important;text-align:right}
.pe-file{cursor:pointer;border:1px solid var(--line2,#b9cbd8);border-radius:8px;background:#fff;display:inline-flex;align-items:center}
.pe-rates td:nth-child(2){width:28%}.pe-rates td:nth-child(3){width:112px}.pe-rates td:nth-child(4){width:80px}
.pe-rates tr.off td{opacity:.55}.pe-rates td:first-child{width:34px;text-align:center}.pe-rates input[type=checkbox]{width:auto}
.pe-mcell{white-space:nowrap}.pe-mwrap{display:inline-flex;align-items:center;gap:3px}.pe-mwrap input{width:64px!important;text-align:right}.pe-mwrap input.bad{color:#b3261e;border-color:#e0aaaa}.pe-mcell .pe-mini{margin-left:4px!important}
.pe-rtotal{display:flex;gap:6px 18px;flex-wrap:wrap;align-items:center;margin-top:10px;padding:10px 12px;border-radius:10px;background:#f4f8fb;border:1px solid var(--line);font-size:14px}
.pe-rsum{display:flex;gap:6px 14px;flex-wrap:wrap;align-items:baseline}.pe-rsum span{color:var(--muted);font-size:12.5px}.pe-rsum b{font-variant-numeric:tabular-nums;margin-right:6px}.pe-bad{color:#b3261e;font-weight:600}
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
 const gbp=v=>{const x=Number(v||0);return '£'+x.toLocaleString('en-GB',Number.isInteger(x)?{}:{minimumFractionDigits:2,maximumFractionDigits:2})};
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
 function rates(box,items,units,opts={}){let pasteOpen=false,showAll=true,filter='';let target=Number(opts.target??30);
  const n=v=>{const x=parseFloat(String(v??'').replace(/[£,\s]/g,''));return isNaN(x)?null:x};
  const sellFor=c=>target<100?Math.round(c/(1-target/100)*100)/100:c;
  const mk_=r=>{const c=n(r.cost),sv=n(r.sell);const o={role:r.role||'',unit:r.unit||'day',cost:r.cost??'',sell:r.sell??'',days:r.days??'',use:r.use!==false,override:!!r.override};
   if(c!==null&&(sv===null)){o.sell=sellFor(c);o.override=false}else if(c!==null&&sv!==null)o.override=!!r.override||Math.abs(sv-sellFor(c))>0.01;return o};
  let list=(items||[]).map(mk_);
  const marginOf=r=>{const c=n(r.cost),sv=n(r.sell);return c!==null&&sv?(sv-c)/sv*100:null};
  function draw(){box.replaceChildren();
   const top=mk('div','','pe-rtop');const tl=mk('label','','pe-target');const ti=document.createElement('input');ti.inputMode='decimal';ti.value=target;ti.setAttribute('aria-label','Target margin');ti.oninput=()=>{const v=n(ti.value);if(v===null||v<0||v>=95)return;target=v;for(const r of list)if(!r.override&&n(r.cost)!==null)r.sell=sellFor(n(r.cost));body();foot()};
   tl.append(document.createTextNode('Target margin '),ti,document.createTextNode(' %'));
   const all=btn('Apply to every role',()=>{for(const r of list){r.override=false;if(n(r.cost)!==null)r.sell=sellFor(n(r.cost))}draw()},'Set every sell rate from its cost at the target margin');
   top.append(tl,all);
   if(opts.parse){const fl=mk('label','Load a pricing spreadsheet','secondary pe-mini pe-file');const fi=document.createElement('input');fi.type='file';fi.accept='.xlsx,.xlsm,.csv';fi.hidden=true;fl.append(fi);
    fi.onchange=async()=>{const f=fi.files[0];fi.value='';if(!f)return;const note=box.querySelector('.pe-rnote');if(note)note.textContent='Reading '+f.name+'…';
     try{const r=await opts.parse(f);const have=new Set(list.map(x=>x.role.toLowerCase()));const add=r.rows.filter(x=>!have.has(x.role.toLowerCase())).map(x=>mk_({...x,use:false}));list=list.concat(add);showAll=true;draw();
      box.querySelector('.pe-rnote').textContent=add.length+' role'+(add.length===1?'':'s')+' added from '+f.name+(r.sheet?' (sheet '+r.sheet+')':'')+'. Tick the ones this proposal needs.'+(r.rows.length>add.length?' '+(r.rows.length-add.length)+' already listed.':'')}
     catch(e){box.querySelector('.pe-rnote').textContent=e.message}};top.append(fl)}
   const pb=btn('Paste a table',()=>{pasteOpen=!pasteOpen;draw();box.querySelector('.pe-paste textarea')?.focus()},'Paste a rate card copied from Excel, Word or an email');top.append(pb);
   box.append(top);
   if(list.length>8){const fb=mk('div','','pe-rtop');const used=list.filter(r=>r.use).length;const c1=btn('Ticked ('+used+')',()=>{showAll=false;draw()}),c2=btn('All roles ('+list.length+')',()=>{showAll=true;draw()});(showAll?c2:c1).classList.add('on');
    const fi=document.createElement('input');fi.type='search';fi.placeholder='Find a role';fi.value=filter;fi.setAttribute('aria-label','Find a role');fi.oninput=()=>{filter=fi.value.toLowerCase();body()};fb.append(c1,c2,fi);box.append(fb)}
   const t=mk('table','','pe-rates');const h=document.createElement('thead');const hr=document.createElement('tr');
   for(const x of ['Use','Role','Unit','Days','Cost rate','Sell rate','Margin',''])hr.append(mk('th',x));h.append(hr);t.append(h);const tb=document.createElement('tbody');t.append(tb);box.append(t);
   const tf=mk('div','','pe-rtotal');box.append(tf);
   function body(){tb.replaceChildren();const shown=list.filter(r=>(showAll||r.use)&&(!filter||r.role.toLowerCase().includes(filter)));
    for(const r of shown){const i=list.indexOf(r);const tr=document.createElement('tr');if(!r.use)tr.className='off';
     const u0=document.createElement('input');u0.type='checkbox';u0.checked=r.use;u0.setAttribute('aria-label','Use '+(r.role||'this role'));u0.onchange=()=>{r.use=u0.checked;tr.className=r.use?'':'off';foot()};
     const role=document.createElement('input');role.maxLength=80;role.value=r.role;role.placeholder='e.g. Solution architect';role.setAttribute('aria-label','Role '+(i+1));role.oninput=()=>{r.role=role.value};
     const u=document.createElement('select');u.setAttribute('aria-label','Unit for '+(r.role||'role'));for(const k of units||['day','hour']){const o=mk('option','per '+k);o.value=k;u.append(o)}u.value=r.unit;u.onchange=()=>{r.unit=u.value;foot()};
     const inp=(k,label,ph)=>{const x=document.createElement('input');x.inputMode='decimal';x.value=r[k];x.placeholder=ph||'';x.setAttribute('aria-label',label+' for '+(r.role||'role'));return x};
     const days=inp('days','Days','optional'),cost=inp('cost','Cost rate','£'),sell=inp('sell','Sell rate','£');const mg=document.createElement('input');mg.inputMode='decimal';mg.setAttribute('aria-label','Margin for '+(r.role||'role'));
     const showM=()=>{const m=marginOf(r);if(document.activeElement!==mg)mg.value=m===null?'':m.toFixed(1);mg.classList.toggle('bad',m!==null&&(m<0||(opts.minMargin!=null&&m<opts.minMargin)));mg.title=m!==null&&opts.minMargin!=null&&m<opts.minMargin?'Below your minimum margin of '+opts.minMargin+'%':'';reset.hidden=!r.override};
     days.oninput=()=>{r.days=days.value;foot()};
     cost.oninput=()=>{r.cost=cost.value;const c=n(cost.value);if(!r.override&&c!==null){r.sell=sellFor(c);sell.value=r.sell}showM();foot()};
     sell.oninput=()=>{r.sell=sell.value;r.override=true;showM();foot()};
     mg.oninput=()=>{const m=n(mg.value),c=n(r.cost);if(m===null||c===null||m>=100)return;r.sell=Math.round(c/(1-m/100)*100)/100;sell.value=r.sell;r.override=true;reset.hidden=false;foot()};
     mg.onblur=showM;
     const reset=btn('↺',()=>{r.override=false;const c=n(r.cost);if(c!==null){r.sell=sellFor(c);sell.value=r.sell}showM();foot()},'Back to the target margin');
     const mcell=mk('td','','pe-mcell');const mw=mk('span','','pe-mwrap');mw.append(mg,mk('span','%'));mcell.append(mw,reset);
     const rm=btn('Remove',()=>{list.splice(i,1);draw()},'Remove '+(r.role||'role'));
     const td=x=>{const c=document.createElement('td');c.append(x);return c};tr.append(td(u0),td(role),td(u),td(days),td(cost),td(sell),mcell,td(rm));tb.append(tr);showM()}
    if(!shown.length)tb.append(Object.assign(document.createElement('tr'),{innerHTML:'<td colspan="8" class="pe-note">'+(list.length?'No roles match.':'No roles yet: load a pricing spreadsheet, paste a table or add roles.')+'</td>'}))}
   function foot(){const u=list.filter(r=>r.use&&r.role.trim());const wd=u.filter(r=>n(r.days)>0&&n(r.cost)!==null&&n(r.sell)!==null);
    const c=wd.reduce((a,r)=>a+n(r.days)*n(r.cost),0),sv=wd.reduce((a,r)=>a+n(r.days)*n(r.sell),0);tf.replaceChildren();
    tf.append(mk('b','For reference'),mk('span',u.length+' role'+(u.length===1?'':'s')+' ticked'+(wd.length?', '+wd.length+' with days':'')));
    if(wd.length){const g=mk('div','','pe-rsum');for(const [l,v] of [['Cost',gbp(c)],['Sell price',gbp(sv)],['Margin',sv?((sv-c)/sv*100).toFixed(1)+'%':'—']])g.append(mk('span',l),mk('b',v));tf.append(g);
     const m=sv?(sv-c)/sv*100:0;if(opts.minMargin!=null&&sv&&m<opts.minMargin)tf.append(mk('span','⚠ Below your minimum margin of '+opts.minMargin+'%','pe-bad'))}
    else tf.append(mk('span','Add days to the ticked roles to see the cost, sell price and margin. Roles without days: the writer suggests the days.','pe-note'))}
   body();foot();
   const bar=mk('div','','pe-addbar');bar.append((()=>{const b=btn('Add role',()=>{list.push(mk_({role:'',unit:'day',cost:'',sell:'',use:true}));showAll=true;draw();const ins=box.querySelectorAll('.pe-rates tbody tr:last-child input');ins[1]?.focus()});b.classList.add('pe-add');return b})());
   box.append(bar,mk('p','','pe-note pe-rnote'));
   if(pasteOpen){const pp=mk('div','','pe-paste');const ta=document.createElement('textarea');ta.rows=5;ta.placeholder='Copy the rows from Excel, Word or an email and paste them here, for example:\nRole\tCost\tSell\nSolution architect\t650\t1200\nConsultant\t450\t850';ta.setAttribute('aria-label','Pasted rate card');
    const msg=mk('p','','pe-note');const use=btn('Replace the rate card',()=>apply(true)),more=btn('Add to the rate card',()=>apply(false)),cancel=btn('Cancel',()=>{pasteOpen=false;draw()});
    const show=()=>{const r=parseRates(ta.value);msg.textContent=ta.value.trim()?(r.rows.length?r.rows.length+' role'+(r.rows.length===1?'':'s')+' found: '+r.rows.slice(0,4).map(x=>x.role+' ('+(x.cost!==''?'cost '+x.cost+', ':'')+'sell '+x.sell+' per '+x.unit+')').join('; ')+(r.rows.length>4?'…':'')+'.':'No roles found yet.')+(r.notes.length?' '+r.notes.join(' '):''):'Columns are read by their headings (role, unit, cost, sell); without headings, the first text is the role, the first number the cost and the second the sell rate.'};
    const apply=replace=>{const r=parseRates(ta.value);if(!r.rows.length){show();return}const add=r.rows.map(x=>mk_({...x,override:true}));list=replace?add:list.filter(x=>x.role.trim()).concat(add);pasteOpen=false;draw()};
    ta.oninput=show;const act=mk('div','','pe-addbar');act.append(use,more,cancel);pp.append(ta,msg,act);box.append(pp);show()}}
  draw();return {value:()=>list.filter(r=>r.role.trim()).map(r=>({role:r.role.trim(),unit:r.unit,cost:String(r.cost).trim()||'0',sell:String(r.sell).trim()||'0',days:String(r.days??'').trim(),use:r.use,override:r.override})),
   target:()=>target,set:x=>{list=(x||[]).map(mk_);draw()},
   pick:roles=>{const m=new Map((roles||[]).map(r=>[String(r.role).toLowerCase(),r]));for(const r of list){const g=m.get(r.role.trim().toLowerCase());r.use=!!g;if(g&&g.days)r.days=g.days}showAll=false;draw()}}}
 return {sections,rates,parseRates,gbp,mk}})();
'''
