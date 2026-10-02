"""The page staff use to talk to an assistant: no menus, no access to the rest of Alice, nothing kept in the browser
beyond the open page. Answers show their sources; blocked or escalated questions say who to contact instead."""
import json
from html import escape


def render(a):
    from ui_theme import SHARED_CSS
    data = json.dumps({'id': a['id'], 'name': a['name'], 'greeting': a['greeting'], 'paused': a['status'] != 'active'})
    return ('''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + escape(a['name']) + '''</title><link rel="icon" href="/static/favicon.png" type="image/png">
<style>''' + SHARED_CSS + '''
body{display:grid;grid-template-rows:52px minmax(0,1fr) auto;overflow:hidden}
.topbar .brand{width:auto}.topbar .who{font-size:15px;font-weight:600;color:#fff;letter-spacing:0}
main{overflow:auto;padding:24px 16px}
.wrap{max-width:780px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
.intro{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.intro h1{margin:0 0 6px;font-size:20px}.intro p{margin:0;color:var(--muted)}
.msg{max-width:88%;padding:12px 14px;border-radius:12px;white-space:pre-wrap;line-height:1.55}
.me{align-self:flex-end;background:var(--teal);color:#fff;border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:var(--panel);border:1px solid var(--line);border-bottom-left-radius:4px}
.bot.stop{background:#fdf3e1;border-color:#e9c98d}
.bot .src{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);font-size:13px;color:var(--muted);white-space:normal}
.bot .src b{color:var(--ink)}
.bot .note{margin-top:8px;font-size:12.5px;color:var(--muted);white-space:normal}
form{border-top:1px solid var(--line);background:var(--panel);padding:12px 16px}
.row{max-width:780px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
textarea{flex:1;resize:none;min-height:46px;max-height:180px}
.foot{max-width:780px;margin:6px auto 0;font-size:12px;color:var(--muted)}
.busy{color:var(--muted);font-style:italic;align-self:flex-start}
</style></head><body>
<header class="topbar"><span class="brand"><img src="/static/favicon.png" alt=""><span class="who">''' + escape(a['name']) + '''</span></span><div class="sp"></div><span class="small" style="color:#9fb8ca">Built on Alice</span></header>
<main id="log" aria-live="polite"><div class="wrap" id="wrap">
<section class="intro"><h1>''' + escape(a['name']) + '''</h1><p id="greeting"></p></section>
</div></main>
<form id="ask"><div class="row"><label for="q" class="small" hidden>Your question</label>
<textarea id="q" maxlength="2000" rows="1" placeholder="Ask a question about the policies" aria-label="Your question"></textarea>
<button id="send" class="primary" type="submit">Ask</button></div>
<p class="foot">Answers come from the published policies and may not cover your situation. Don't include personal details such as health, casework or ID numbers: they are blocked or removed before anything reaches the AI. Nothing you type is kept.</p></form>
<script>
const A=''' + data.replace('</', '<\\/') + ''';
const $=id=>document.getElementById(id);const turns=[];
$('greeting').textContent=A.paused?A.name+' is paused at the moment.':A.greeting;if(A.paused){$('q').disabled=$('send').disabled=true}
function add(cls,text){const d=document.createElement('div');d.className='msg '+cls;d.textContent=text;$('wrap').append(d);$('log').scrollTop=$('log').scrollHeight;return d}
$('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('ask').requestSubmit()}});
$('ask').onsubmit=async e=>{e.preventDefault();const q=$('q').value.trim();if(!q||$('send').disabled)return;
 add('me',q);$('q').value='';$('send').disabled=true;const busy=document.createElement('div');busy.className='busy';busy.textContent='Checking the policies…';$('wrap').append(busy);
 try{const r=await fetch('/assistant/'+encodeURIComponent(A.id)+'/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,history:turns})});
  let d;try{d=await r.json()}catch{d={}}busy.remove();
  if(!r.ok){add('bot stop',(d&&d.detail)||'Something went wrong. Try again in a moment.');return}
  const m=add('bot'+(d.status==='answered'?'':' stop'),d.reply);
  if(d.sources&&d.sources.length){const s=document.createElement('div');s.className='src';const b=document.createElement('b');b.textContent='Sources: ';s.append(b,document.createTextNode(d.sources.map(x=>'['+x.ref+'] '+x.title+(x.part>1?' (part '+x.part+')':'')).join(' · ')));m.append(s)}
  const checked=(d.sources||[]).filter(x=>x.type==='document');
  if(checked.length){const f=document.createElement('div');f.className='src';f.textContent='Checked the full document: '+[...new Set(checked.map(x=>x.name+(x.section?', section '+x.section:'')))].join(' · ')+'. Read for this answer only; not stored in Alice.';m.append(f)}
  const docs=[...new Set((d.sources||[]).filter(x=>x.type!=='document').map(x=>x.source).filter(Boolean))];if(docs.length){const f=document.createElement('div');f.className='src';f.textContent='Full policy: '+docs.map(x=>x.split(' (full document')[0]).join(' · ')+'. Alice keeps summaries only; the full document stays in the policy library.';m.append(f)}
  if(d.notes&&d.notes.length){const n=document.createElement('div');n.className='note';n.textContent=d.notes.join(' ');m.append(n)}
  if(d.status==='answered'){turns.push({role:'user',text:q},{role:'assistant',text:d.reply});while(turns.length>6)turns.shift()}}
 catch{busy.remove();add('bot stop','Could not reach the assistant. Check your connection and try again.')}
 finally{$('send').disabled=A.paused;$('q').focus()}};
</script></body></html>''')
