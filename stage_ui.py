"""The assistant stage: opening an assistant (Alex, Parker...) from Alice. The tile or link you clicked grows into the
assistant, full screen, while the Console recedes behind it; a splash with the assistant's mark shows until its page
has loaded. Back to Alice (also Esc and the browser's back) shrinks it back into the tile; Open in a new window pops it out.
The assistant runs in an iframe of its own page (`?embed=1` hides that page's top bar); nothing about the assistant changes."""

NIB = ('<svg viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="stg-nib" x1="0" y1="0" x2="1" y2="1"><stop offset="0" '
       'stop-color="#7a5bb5"/><stop offset="1" stop-color="#0a7f9f"/></linearGradient></defs><rect width="48" height="48" rx="13" '
       'fill="url(#stg-nib)"/><path d="M17 8h14v5.5c0 1.6 2.2 4.2 2.2 9.2 0 2.4-.6 3.9-1.6 5.4L24 41l-7.6-12.9c-1-1.5-1.6-3-1.6-5.4 0-5 '
       '2.2-7.6 2.2-9.2z" fill="#fff"/><path d="M24 26v13" stroke="#3d72a6" stroke-width="1.9" stroke-linecap="round"/><circle cx="24" '
       'cy="23.5" r="2.9" fill="url(#stg-nib)"/></svg>')

STAGE_CSS = r'''
.as-stage{position:fixed;inset:0;z-index:1000;display:grid;grid-template-rows:48px minmax(0,1fr);background:#f4f7fa;visibility:hidden;will-change:clip-path,opacity}
.as-stage-bar{display:flex;align-items:center;gap:10px;padding:0 12px;color:#dfeaf2;background:linear-gradient(90deg,#0b1626,#0d2a3f 60%,#1f2c55)}
.as-stage-bar b{font-size:15px;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.as-stage-bar .sp{flex:1}
.as-stage-bar button{border:1px solid rgba(255,255,255,.25)!important;background:rgba(255,255,255,.06)!important;color:#fff!important;border-radius:999px!important;padding:6px 14px!important;font-size:13px;font-weight:600}
.as-stage-bar button:hover{background:rgba(255,255,255,.16)!important}
.as-mark{flex:none;width:28px;height:28px;border-radius:8px;display:grid;place-items:center;font-weight:700;color:#fff;background:linear-gradient(135deg,#1d8fb0,#075e79);overflow:hidden}
.as-mark svg{width:100%;height:100%;display:block}
.as-stage iframe{width:100%;height:100%;border:0;background:#f4f7fa;opacity:0;transition:opacity .4s ease}
.as-stage.loaded iframe{opacity:1}
.as-splash{position:absolute;inset:48px 0 0;display:grid;place-content:center;justify-items:center;gap:14px;background:radial-gradient(600px 300px at 50% 40%,#e9f2f7,#f4f7fa);transition:opacity .45s ease;pointer-events:none}
.as-splash .as-mark{width:76px;height:76px;border-radius:22px;font-size:34px;box-shadow:0 18px 40px -18px rgba(7,94,121,.7);animation:as-breathe 1.6s ease-in-out infinite}
.as-splash b{font-size:20px;color:#14324a}.as-splash span{font-size:13px;color:#5d7385}
.as-stage.loaded .as-splash{opacity:0}
@keyframes as-breathe{50%{transform:scale(1.06)}}
body.as-on{overflow:hidden}
'''

STAGE_HTML = ('<div class="as-stage" id="as-stage" role="dialog" aria-modal="true" aria-label="Assistant" aria-hidden="true">'
              '<div class="as-stage-bar"><button type="button" id="as-stage-back" title="Back to Alice (Esc)">← Back to Alice</button>'
              '<span class="as-mark" id="as-stage-mark" aria-hidden="true">A</span><b id="as-stage-name">Assistant</b><span class="sp"></span>'
              '<button type="button" id="as-stage-pop" title="Open this assistant in its own window">Open in a new window ↗</button></div>'
              '<iframe id="as-stage-frame" title="Assistant"></iframe>'
              '<div class="as-splash"><span class="as-mark" id="as-splash-mark" aria-hidden="true">A</span><b id="as-splash-name">Assistant</b><span>Opening…</span></div></div>')

STAGE_JS = r'''
(()=>{const st=document.getElementById('as-stage');if(!st)return;const fr=document.getElementById('as-stage-frame');
 const NIB=__NIB__;let open=false,from=null,back=null,loadedAt=0,shownAt=0,anims=[];
 const calm=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const EASE='cubic-bezier(.65,0,.25,1)',T=calm?480:820;      // Windows 'Show animations' off: shorter and without blur, still the same movement
 const behind=()=>[...document.body.children].filter(e=>e!==st&&e.tagName!=='SCRIPT');
 const clean=u=>{try{const x=new URL(u,location.origin);x.searchParams.delete('embed');return x.pathname+x.search+x.hash}catch{return u}};
 const rectOf=el=>{const W=innerWidth,H=innerHeight;let r=el&&el.isConnected?el.getBoundingClientRect():null;
  if(!r||!r.width||r.bottom<0||r.top>H)r={left:W*.35,top:H*.35,right:W*.65,bottom:H*.65};
  return 'inset('+Math.max(0,r.top)+'px '+Math.max(0,W-r.right)+'px '+Math.max(0,H-r.bottom)+'px '+Math.max(0,r.left)+'px round 16px)'};
 function mark(el,name,kind){el.replaceChildren();if(kind==='proposal'){el.innerHTML=NIB;el.style.background='none'}else{el.textContent=(name||'A').trim().charAt(0).toUpperCase();el.style.background=''}}
 function finish(){anims.forEach(a=>{try{a.cancel()}catch{}});anims=[]}
 function reveal(){if(!loadedAt)return;const wait=Math.max(0,shownAt+T-Date.now());setTimeout(()=>{if(open)st.classList.add('loaded')},wait)}
 function show(href,name,el,kind){if(open)return;finish();const u=new URL(href,location.origin);u.searchParams.set('embed','1');
  from=el||null;back=document.activeElement;open=true;loadedAt=0;shownAt=Date.now();st.classList.remove('loaded');
  for(const id of ['as-stage-name','as-splash-name'])document.getElementById(id).textContent=name||'Assistant';
  mark(document.getElementById('as-stage-mark'),name,kind);mark(document.getElementById('as-splash-mark'),name,kind);
  fr.src=u.pathname+u.search;st.style.visibility='visible';st.setAttribute('aria-hidden','false');document.body.classList.add('as-on');
  anims.push(st.animate([{clipPath:rectOf(from),opacity:.85},{clipPath:'inset(0px 0px 0px 0px round 0px)',opacity:1}],{duration:T,easing:EASE,fill:'both'}));
  for(const e of behind())anims.push(e.animate([{transform:'none',opacity:1,filter:'none'},{transform:'scale(.94)',opacity:.25,filter:calm?'none':'blur(3px)'}],{duration:T,easing:EASE,fill:'both'}));
  history.pushState({asStage:true},'',location.href);setTimeout(()=>document.getElementById('as-stage-back').focus(),T)}
 function hide(fromPop){if(!open)return;open=false;st.setAttribute('aria-hidden','true');
  const out=st.animate([{clipPath:'inset(0px 0px 0px 0px round 0px)',opacity:1},{clipPath:rectOf(from),opacity:.4}],{duration:T*.8,easing:EASE,fill:'both'});
  for(const e of behind())e.animate([{transform:'scale(.94)',opacity:.25,filter:calm?'none':'blur(3px)'},{transform:'none',opacity:1,filter:'none'}],{duration:T*.8,easing:EASE});
  anims.forEach(a=>{if(a!==out)try{a.cancel()}catch{}});anims=[out];
  out.onfinish=()=>{if(open)return;st.style.visibility='hidden';out.cancel();anims=[];document.body.classList.remove('as-on');fr.src='about:blank';st.classList.remove('loaded');if(back&&back.focus)back.focus()};
  if(!fromPop&&history.state&&history.state.asStage)history.back()}
 fr.addEventListener('load',()=>{if(!open||!fr.src||fr.src.endsWith('about:blank'))return;loadedAt=Date.now();try{const t=fr.contentDocument.title;if(t)document.getElementById('as-stage-name').textContent=t}catch{}reveal()});
 document.getElementById('as-stage-back').onclick=()=>hide(false);
 document.getElementById('as-stage-pop').onclick=()=>{let u=fr.src;try{u=fr.contentWindow.location.href}catch{}window.open(clean(u),'_blank','noopener');hide(false)};
 window.addEventListener('popstate',()=>{if(open)hide(true)});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&open)hide(false)});
 document.addEventListener('click',e=>{if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  const a=e.target.closest('a[href]');if(!a)return;const u=new URL(a.getAttribute('href'),location.origin);
  if(u.origin!==location.origin||!/^\/assistant\/[^/]+$/.test(u.pathname))return;e.preventDefault();
  const tile=a.closest('.as-c,li,.hm-btn,tr')||a;
  show(u.pathname+u.search,a.dataset.name||(a.querySelector('b')||a).textContent.split('\n')[0].replace(/[↗→]/g,'').trim(),tile,a.dataset.kind||'')},true);
 window.openAssistant=show;})();
'''.replace('__NIB__', __import__('json').dumps(NIB))

EMBED_HEAD = ('<script>if(new URLSearchParams(location.search).get("embed"))document.documentElement.classList.add("embed")</script>'
              '<style>html.embed .topbar{display:none!important}html.embed body{grid-template-rows:minmax(0,1fr)!important}</style>')
