"""The page staff use to talk to an assistant: no menus, no access to the rest of Alice, nothing kept in the browser
beyond the open page. Answers show their sources; blocked or escalated questions say who to contact instead."""
import json
from html import escape


def _topics(a):
    """Titles of the approved knowledge the assistant answers from (what staff can ask about)."""
    try:
        import assistants
        return sorted({i['title'] for i in assistants.scope(a) if i.get('title')}, key=str.lower)
    except Exception:
        return []


def render(a):
    from ui_theme import SHARED_CSS
    topics = _topics(a)
    data = json.dumps({'id': a['id'], 'name': a['name'], 'greeting': a['greeting'], 'paused': a['status'] != 'active', 'topics': topics[:8]})
    initial = escape((a['name'] or 'A').strip()[:1].upper())
    contact = escape(a.get('contact') or '')
    about = escape(a.get('description') or '')
    cover = ''.join(f'<li>{escape(t)}</li>' for t in topics[:12]) + (f'<li class="more">and {len(topics) - 12} more</li>' if len(topics) > 12 else '')
    return ('''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + escape(a['name']) + '''</title>''' + __import__('stage_ui').EMBED_HEAD + '''<link rel="icon" href="/static/favicon.png" type="image/png">
<style>''' + SHARED_CSS + '''
body{display:grid;grid-template-rows:52px minmax(0,1fr);overflow:hidden;background:linear-gradient(180deg,#eef3f7 0,#f4f7fa 300px)}
.topbar .brand{width:auto}.topbar .who{font-size:15px;font-weight:600;color:#fff;letter-spacing:0}
[hidden]{display:none!important}
.shell{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;max-width:1180px;width:100%;margin:0 auto;padding:0 20px;min-height:0}
.chat{display:grid;grid-template-rows:minmax(0,1fr) auto;min-height:0;min-width:0}
main{overflow:auto;padding:22px 2px 18px;min-height:0}
.wrap{display:flex;flex-direction:column;gap:16px}
/* welcome */
.welcome{position:relative;overflow:hidden;border-radius:16px;color:#e8f1f7;padding:26px 26px 22px;
 background:radial-gradient(700px 240px at 90% -30%,rgba(64,170,200,.35),transparent 60%),linear-gradient(120deg,#0b1626 0%,#0d2a3f 55%,#075e79 100%);
 box-shadow:0 10px 30px -18px rgba(11,22,38,.8)}
.welcome::after{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);background-size:28px 28px;mask-image:linear-gradient(90deg,transparent,#000 75%);pointer-events:none}
.welcome>*{position:relative;z-index:1}
.w-top{display:flex;gap:14px;align-items:center}
.badge{flex:none;width:46px;height:46px;border-radius:13px;display:grid;place-items:center;font-weight:700;font-size:20px;color:#fff;background:linear-gradient(135deg,#1d8fb0,#075e79);border:1px solid rgba(255,255,255,.25);box-shadow:0 6px 16px -8px rgba(0,0,0,.6)}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:#8fd0e3;font-weight:700;margin:0 0 2px}
.welcome h1{margin:0;font-size:26px;line-height:1.15;color:#fff;letter-spacing:-.01em}
.welcome .lead{margin:14px 0 0;color:#c4d6e2;font-size:15.5px;max-width:640px}
.topics{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.topics button{border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.08);color:#fff;border-radius:999px;padding:7px 14px;font-size:13.5px;font-weight:600}
.topics button:hover:not(:disabled){background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.5)}
.t-label{margin:16px 0 0;font-size:12px;color:#9fc0d2;font-weight:600}
/* conversation */
.turn{display:flex;gap:10px;align-items:flex-end;max-width:100%}
.turn.me{justify-content:flex-end}
.av{flex:none;width:32px;height:32px;border-radius:10px;display:grid;place-items:center;font-weight:700;font-size:14px;color:#fff;background:linear-gradient(135deg,#1d8fb0,#075e79);margin-bottom:2px}
.msg{max-width:min(640px,86%);padding:13px 16px;border-radius:16px;white-space:pre-wrap;line-height:1.6;font-size:15px;min-width:0;overflow-wrap:anywhere}
.msg.me{background:linear-gradient(135deg,#0a6d8b,#075e79);color:#fff;border-bottom-right-radius:5px;box-shadow:0 6px 14px -10px rgba(7,94,121,.9)}
.msg.bot{background:var(--panel);border:1px solid #dce6ee;border-bottom-left-radius:5px;box-shadow:0 1px 2px rgba(16,42,67,.04),0 8px 20px -14px rgba(16,42,67,.25)}
.msg.bot.stop{background:#fdf7ea;border-color:#ecd6a8}
.msg.bot.stop::before{content:'Not something I can answer here';display:block;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#8a5a0f;margin-bottom:6px}
.src{margin-top:12px;padding-top:10px;border-top:1px solid var(--line);font-size:13px;color:var(--muted);white-space:normal;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.src .h{font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-right:2px}
.src .c{display:inline-flex;gap:6px;align-items:center;background:#f2f7fa;border:1px solid #d3e3ec;color:var(--ink);border-radius:8px;padding:3px 9px;font-size:12.5px}
.src .c b{color:var(--teal);font-weight:700}
.src .c.doc{background:#eef8f1;border-color:#b9dcc5}.src .c.doc b{color:#1e5b31}
.src .t{flex-basis:100%;font-size:12.5px}
.note{margin-top:8px;font-size:12.5px;color:var(--muted);white-space:normal}
.busy{display:flex;gap:10px;align-items:center;color:var(--muted);font-size:14px}
.dots{display:inline-flex;gap:4px;background:var(--panel);border:1px solid #dce6ee;border-radius:14px;padding:12px 14px}
.dots i{width:7px;height:7px;border-radius:50%;background:#8aa9bb;animation:bob 1.2s infinite}.dots i:nth-child(2){animation-delay:.15s}.dots i:nth-child(3){animation-delay:.3s}
@keyframes bob{0%,60%,100%{transform:none;opacity:.5}30%{transform:translateY(-4px);opacity:1}}
.busy.deep .lbl{color:#6b4406;background:#fdf6e3;border:1px solid #ecd9a6;border-radius:10px;padding:7px 12px}
/* composer */
form#ask{padding:6px 0 16px}
.box{display:flex;gap:10px;align-items:flex-end;background:var(--panel);border:1px solid #cddbe5;border-radius:16px;padding:8px 8px 8px 16px;box-shadow:0 10px 30px -18px rgba(16,42,67,.5);transition:border-color .12s,box-shadow .12s}
.box:focus-within{border-color:var(--teal);box-shadow:0 0 0 3px rgba(7,94,121,.12),0 10px 30px -18px rgba(16,42,67,.5)}
.box textarea{flex:1;resize:none;min-height:42px;max-height:180px;border:0!important;outline:none;box-shadow:none!important;background:transparent;padding:10px 0;font-size:15px;line-height:1.5}
#send{border-radius:12px;padding:10px 18px;font-size:15px;box-shadow:0 6px 14px -8px rgba(7,94,121,.8)}
.foot{margin:8px 4px 0;font-size:12px;color:var(--muted);display:flex;gap:8px;align-items:flex-start}
/* about panel */
.about{overflow:auto;padding:22px 0 18px;display:grid;gap:14px;align-content:start;min-height:0}
.acard{background:var(--panel);border:1px solid #dce6ee;border-radius:14px;padding:16px 18px;box-shadow:0 1px 2px rgba(16,42,67,.04),0 6px 18px -12px rgba(16,42,67,.2)}
.acard h2{margin:0 0 10px;font-size:12.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.acard p{margin:0;font-size:14px}
.acard ul{margin:0;padding:0;list-style:none;display:grid;gap:6px}
.cover li{font-size:13.5px;padding-left:16px;position:relative}.cover li::before{content:'';position:absolute;left:0;top:8px;width:7px;height:7px;border-radius:2px;background:#9ccbdb}
.cover li.more{color:var(--muted)}.cover li.more::before{display:none}
.how{counter-reset:h}.how li{counter-increment:h;display:grid;grid-template-columns:24px 1fr;gap:10px;font-size:13.5px;align-items:start}
.how li::before{content:counter(h);width:22px;height:22px;border-radius:7px;display:grid;place-items:center;background:var(--teal2);color:var(--teal);font-weight:700;font-size:12px}
.privacy{background:var(--violet2);border-color:#d9cdea}.privacy p{color:#4b2f73;font-size:13px}
.contact b{display:block;font-size:15px;margin-top:2px}
@media(max-width:980px){.shell{grid-template-columns:minmax(0,1fr)}.about{display:none}}
@media(max-width:600px){.shell{padding:0 12px}.welcome{padding:20px 18px}.welcome h1{font-size:22px}.msg{max-width:92%}.av{display:none}}
</style></head><body>
<header class="topbar"><span class="brand"><img src="/static/favicon.png" alt=""><span class="who">''' + escape(a['name']) + '''</span></span><div class="sp"></div><span class="small" style="color:#9fb8ca">Built on Alice</span></header>
<div class="shell"><div class="chat">
<main id="log" aria-live="polite"><div class="wrap" id="wrap">
<section class="welcome"><div class="w-top"><span class="badge" aria-hidden="true">''' + initial + '''</span><div><p class="eyebrow">Staff assistant</p><h1>''' + escape(a['name']) + '''</h1></div></div>
<p class="lead" id="greeting"></p><p class="t-label" id="t-label" hidden>Ask about</p><div class="topics" id="topics"></div></section>
</div></main>
<form id="ask"><div class="box"><label for="q" class="small" hidden>Your question</label>
<textarea id="q" maxlength="2000" rows="1" placeholder="Ask a question about the policies" aria-label="Your question"></textarea>
<button id="send" class="primary" type="submit">Ask</button></div>
<p class="foot">Answers come from the published policies and may not cover your situation. Don't include personal details such as health, casework or ID numbers: they are blocked or removed before anything reaches the AI. Nothing you type is kept.</p></form>
</div>
<aside class="about" aria-label="About this assistant">
''' + (f'<section class="acard"><h2>About</h2><p>{about}</p></section>' if about else '') + '''
''' + (f'<section class="acard"><h2>What it covers</h2><ul class="cover">{cover}</ul></section>' if cover else '') + '''
<section class="acard"><h2>How answers work</h2><ul class="how"><li>It reads the approved policy summaries first.</li><li>If they don’t answer, it checks the full policy document and tells you which section.</li><li>Every answer shows its sources, so you can read the policy yourself.</li></ul></section>
<section class="acard privacy"><h2>Your privacy</h2><p>Nothing you type is kept. Personal details such as health, casework or ID numbers are blocked or removed before anything reaches the AI.</p></section>
''' + (f'<section class="acard contact"><h2>About your own situation</h2><p>Contact<b>{contact}</b></p></section>' if contact else '') + '''
</aside></div>
<script>
const A=''' + data.replace('</', '<\\/') + ''';
const $=id=>document.getElementById(id);const turns=[];
$('greeting').textContent=A.paused?A.name+' is paused at the moment.':A.greeting;if(A.paused){$('q').disabled=$('send').disabled=true}
if(A.topics.length&&!A.paused){$('t-label').hidden=false;for(const t of A.topics){const b=document.createElement('button');b.type='button';b.textContent=t;b.onclick=()=>{$('q').value='What does the '+t.replace(/^the /i,'')+' say?';$('ask').requestSubmit()};$('topics').append(b)}}
function el(tag,cls,text){const d=document.createElement(tag);if(cls)d.className=cls;if(text!=null)d.textContent=text;return d}
function scroll(){$('log').scrollTop=$('log').scrollHeight}
function add(cls,text){const row=el('div','turn '+(cls.startsWith('me')?'me':'bot'));const d=el('div','msg '+cls,text);
 if(!cls.startsWith('me'))row.append(el('span','av',"''' + initial + '''"));row.append(d);$('wrap').append(row);scroll();return d}
function grow(){const q=$('q');q.style.height='auto';q.style.height=Math.min(q.scrollHeight,180)+'px'}
$('q').addEventListener('input',grow);
$('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('ask').requestSubmit()}});
$('ask').onsubmit=async e=>{e.preventDefault();const q=$('q').value.trim();if(!q||$('send').disabled)return;
 add('me',q);$('q').value='';grow();$('send').disabled=true;document.querySelectorAll('#topics button').forEach(b=>b.disabled=true);
 const busy=el('div','busy turn bot');const dots=el('span','dots');dots.append(el('i'),el('i'),el('i'));const lbl=el('span','lbl','Checking the policy summaries…');busy.append(dots,lbl);$('wrap').append(busy);scroll();
 try{const r=await fetch('/assistant/'+encodeURIComponent(A.id)+'/ask',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},body:JSON.stringify({question:q,history:turns})});
  let d={},err=null;
  if(r.ok&&r.body&&(r.headers.get('content-type')||'').includes('ndjson')){const rd=r.body.getReader(),dec=new TextDecoder();let buf='';
   for(;;){const {value,done}=await rd.read();if(value)buf+=dec.decode(value,{stream:true});let i;
    while((i=buf.indexOf('\\n'))>=0){const line=buf.slice(0,i).trim();buf=buf.slice(i+1);if(!line)continue;const x=JSON.parse(line);
     if(x.stage){lbl.textContent=x.message;busy.classList.add('deep');scroll()}else if(x.error)err=x.error;else d=x.result}
    if(done)break}}
  else{try{d=await r.json()}catch{d={}}if(!r.ok)err={detail:d&&d.detail}}
  busy.remove();
  if(err){add('bot stop',err.detail||'Something went wrong. Try again in a moment.');return}
  const m=add('bot'+(d.status==='answered'?'':' stop'),d.reply);
  const summ=(d.sources||[]).filter(x=>x.type!=='document');
  if(summ.length){const s=el('div','src');s.append(el('span','h','Sources'));for(const x of summ){const c=el('span','c');c.append(el('b',null,x.ref),document.createTextNode(x.title+(x.part>1?' (part '+x.part+')':'')));s.append(c)}m.append(s)}
  const checked=(d.sources||[]).filter(x=>x.type==='document');
  if(checked.length){const by={};for(const x of checked){const k=x.name+'|'+(x.where||'');(by[k]=by[k]||{ref:x.ref,name:x.name,where:x.where,secs:[]});if(x.section&&!by[k].secs.includes(x.section))by[k].secs.push(x.section)}
   const f=el('div','src');f.append(el('span','h','Full document checked'));
   for(const v of Object.values(by)){const c=el('span','c doc');c.title=v.where||'';c.append(el('b',null,v.ref||'D'),document.createTextNode(v.name+(v.secs.length?(v.secs.length>1?', sections ':', section ')+v.secs.join(', '):'')+(v.where?' — '+v.where:'')));f.append(c)}m.append(f)}
  const docs=[...new Set(summ.map(x=>x.source).filter(Boolean))];if(docs.length){m.append(el('div','src',null));m.lastChild.append(el('span','t','Full policy: '+docs.map(x=>x.split(' (full document')[0]).join(' · ')+'. Alice keeps summaries only; the full document stays in its document source.'))}
  if(d.notes&&d.notes.length)m.append(el('div','note',d.notes.join(' ')));
  scroll();
  if(d.status==='answered'){turns.push({role:'user',text:q},{role:'assistant',text:d.reply});while(turns.length>6)turns.shift()}}
 catch{busy.remove();add('bot stop','Could not reach the assistant. Check your connection and try again.')}
 finally{$('send').disabled=A.paused;document.querySelectorAll('#topics button').forEach(b=>b.disabled=A.paused);$('q').focus()}};
</script></body></html>''')
