// The Parker page's draft as one document, and editing it in place (run by test_proposals.py with Node; no browser needed).
const E=require(process.argv[2]);let ok=0,bad=0;const t=(n,c)=>{if(c){ok++}else{bad++;console.log('FAIL',n)}};
const all=(el,f,out=[])=>{for(const c of el.children||[]){if(f(c))out.push(c);all(c,f,out)}return out};
const cls=k=>el=>el.classList&&el.classList.contains(k);
const p={id:'p1',title:'Fabric security baseline',organisation:'Northshire Council',inputs:{template:'Proposal Templates/Proposal-template.docx'},
 draft:{sections:[{title:'Executive summary',body:'First line\nof one paragraph.\n\n- point a\n- point b\n\n**Bold** start.'},{title:'About us',body:'',keep:true},
  {title:'Commercials',body:'A fixed price.'}]},pricing:{lines:[{role:'Consultant',quantity:10,unit:'day',sell_rate:900,sell:9000}],sell:9000}};
const D=E.drawDoc(p);E.set({DOC:D});
const heads=all(D.doc,el=>el.tagName==='H1'||el.tagName==='H2').map(h=>h.textContent);
t('one document: the title, then each section heading in reading order',JSON.stringify(heads)===JSON.stringify(['Fabric security baseline','Executive summary','About us','Commercials']));
const secs=all(D.doc,cls('doc-sec'));const body0=all(secs[0],cls('doc-body'))[0];
t('section text is shown under its heading, as the Word document reads it',all(body0,el=>el.tagName==='P')[0].textContent==='First line of one paragraph.'
 &&all(body0,el=>el.tagName==='LI').length===2&&all(body0,el=>el.tagName==='STRONG')[0].textContent==='Bold');
t('standard text is read-only and marked as from the template',secs[1].classList.contains('keep')&&!all(secs[1],cls('doc-ed')).length&&secs[1].textContent.includes('From the template'));
t('the pricing table sits in the Commercials section, sell prices only',all(secs[2],el=>el.tagName==='TABLE').length===1&&secs[2].textContent.includes('£9,000')&&secs[2].textContent.includes('Total'));
t('not editable until you choose to edit',!D.doc.classList.contains('editing')&&D.bar.hidden&&(body0.onclick(),all(secs[0],cls('doc-ed'))[0].hidden));
E.editDraft(p);const EDS=E.get('EDS');
t('Edit the draft switches the same view to editing, one editor per section that is not standard text',D.doc.classList.contains('editing')&&!D.bar.hidden&&EDS.length===2&&EDS.map(x=>x[0].title).join()==='Executive summary,Commercials');
body0.onclick();const ta=all(secs[0],cls('doc-ed'))[0];
t('clicking into a section\'s text edits it there',!ta.hidden&&body0.hidden&&ta.value===p.draft.sections[0].body&&E.focused()===ta);
ta.value='Our new summary.';ta.oninput();
t('a changed section is marked',secs[0].classList.contains('changed')&&D.bar.textContent.includes('1 section changed'));
ta.onblur();t('leaving it shows the new text in place',ta.hidden&&!body0.hidden&&body0.textContent==='Our new summary.');
EDS[1][1].value='Suggested commercials text.';EDS[1][1].classList.add('tfill');
t('a suggested change lands in place, highlighted',secs[2].classList.contains('tfill')&&all(secs[2],cls('doc-body'))[0].textContent==='Suggested commercials text.');
const go=all(D.bar,el=>el.tagName==='BUTTON').find(b=>b.textContent.startsWith('Save changes'));go.onclick();
setTimeout(()=>{const c=E.calls();
 t('Save sends every section, each edit to its own section',c.api.length===1&&c.api[0][0]==='/proposals/p1/recheck'&&JSON.stringify(c.api[0][2].sections)===JSON.stringify(
  [{title:'Executive summary',body:'Our new summary.'},{title:'About us',body:''},{title:'Commercials',body:'Suggested commercials text.'}])&&c.follow[0]==='p1');
 const D2=E.drawDoc(p);E.set({DOC:D2,EDS:null,RO:true});E.editDraft(p);
 t('a superseded (read-only) version cannot be edited',!D2.doc.classList.contains('editing')&&E.get('EDS')===null);
 console.log(ok,'passed',bad,'failed')},10);
