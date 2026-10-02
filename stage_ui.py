"""The assistant stage: opening an assistant (Alex, Parker...) from Alice slides the Command centre away and brings the
assistant in, full screen, with Back to Alice and Open in a new window. The assistant runs in an iframe of its own page
(`?embed=1` hides that page's top bar); nothing about the assistant changes."""

STAGE_CSS = r'''
.as-stage{position:fixed;inset:0;z-index:1000;display:grid;grid-template-rows:48px minmax(0,1fr);background:#0b1626;visibility:hidden;
 transform:translateX(104%) scale(.98);transition:transform .55s cubic-bezier(.2,.8,.2,1),visibility 0s linear .55s;box-shadow:-30px 0 60px -20px rgba(0,0,0,.6)}
.as-stage-bar{display:flex;align-items:center;gap:10px;padding:0 12px;color:#dfeaf2;background:linear-gradient(90deg,#0b1626,#0d2a3f 60%,#1f2c55)}
.as-stage-bar b{font-size:15px;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.as-stage-bar .sp{flex:1}
.as-stage-bar button{border:1px solid rgba(255,255,255,.25)!important;background:rgba(255,255,255,.06)!important;color:#fff!important;border-radius:999px!important;padding:6px 14px!important;font-size:13px;font-weight:600}
.as-stage-bar button:hover{background:rgba(255,255,255,.16)!important}
.as-stage-mark{flex:none;width:28px;height:28px;border-radius:8px;display:grid;place-items:center;font-weight:700;color:#fff;background:linear-gradient(135deg,#7a5bb5,#0a7f9f)}
.as-stage iframe{width:100%;height:100%;border:0;background:#f4f7fa;opacity:0;transition:opacity .35s ease .25s}
.as-stage.loaded iframe{opacity:1}
.as-stage-load{position:absolute;inset:48px 0 0;display:grid;place-items:center;color:#9fb8ca;font-size:14px;pointer-events:none;transition:opacity .3s}
.as-stage.loaded .as-stage-load{opacity:0}
body>*:not(.as-stage){transition:transform .55s cubic-bezier(.2,.8,.2,1),opacity .45s ease,filter .45s ease;transform-origin:20% 50%}
body.as-on{overflow:hidden;background:#0b1626}
body.as-on>*:not(.as-stage){transform:translateX(-8%) scale(.9);opacity:0;filter:blur(8px);pointer-events:none}
body.as-on .as-stage{visibility:visible;transform:none;transition:transform .55s cubic-bezier(.2,.8,.2,1),visibility 0s}
@media (prefers-reduced-motion:reduce){.as-stage,body>*:not(.as-stage),.as-stage iframe{transition:none!important}}
'''

STAGE_HTML = ('<div class="as-stage" id="as-stage" role="dialog" aria-modal="true" aria-label="Assistant" aria-hidden="true">'
              '<div class="as-stage-bar"><button type="button" id="as-stage-back" title="Back to Alice (Esc)">← Back to Alice</button>'
              '<span class="as-stage-mark" id="as-stage-mark" aria-hidden="true">A</span><b id="as-stage-name">Assistant</b><span class="sp"></span>'
              '<button type="button" id="as-stage-pop" title="Open this assistant in its own window">Open in a new window ↗</button></div>'
              '<iframe id="as-stage-frame" title="Assistant"></iframe><div class="as-stage-load">Opening…</div></div>')

STAGE_JS = r'''
(()=>{const st=document.getElementById('as-stage');if(!st)return;const fr=document.getElementById('as-stage-frame');let open=false,back=null;
 const clean=u=>{try{const x=new URL(u,location.origin);x.searchParams.delete('embed');return x.pathname+x.search+x.hash}catch{return u}};
 function show(href,name){const u=new URL(href,location.origin);u.searchParams.set('embed','1');st.classList.remove('loaded');
  document.getElementById('as-stage-name').textContent=name||'Assistant';document.getElementById('as-stage-mark').textContent=(name||'A').trim().charAt(0).toUpperCase();
  fr.src=u.pathname+u.search;back=document.activeElement;st.setAttribute('aria-hidden','false');requestAnimationFrame(()=>document.body.classList.add('as-on'));
  if(!open){history.pushState({asStage:true},'',location.href);open=true}setTimeout(()=>document.getElementById('as-stage-back').focus(),560)}
 function hide(fromPop){if(!open)return;open=false;document.body.classList.remove('as-on');st.setAttribute('aria-hidden','true');
  setTimeout(()=>{if(!open){fr.src='about:blank';st.classList.remove('loaded')}},600);if(back&&back.focus)back.focus();if(!fromPop&&history.state&&history.state.asStage)history.back()}
 fr.addEventListener('load',()=>{if(fr.src&&!fr.src.endsWith('about:blank')){st.classList.add('loaded');try{const t=fr.contentDocument.title;if(t)document.getElementById('as-stage-name').textContent=t}catch{}}});
 document.getElementById('as-stage-back').onclick=()=>hide(false);
 document.getElementById('as-stage-pop').onclick=()=>{let u=fr.src;try{u=fr.contentWindow.location.href}catch{}window.open(clean(u),'_blank','noopener');hide(false)};
 window.addEventListener('popstate',()=>{if(open)hide(true)});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&open)hide(false)});
 document.addEventListener('click',e=>{if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  const a=e.target.closest('a[href]');if(!a)return;const u=new URL(a.getAttribute('href'),location.origin);
  if(u.origin!==location.origin||!/^\/assistant\/[^/]+$/.test(u.pathname))return;e.preventDefault();
  show(u.pathname+u.search,a.dataset.name||(a.querySelector('b')||a).textContent.split('\n')[0].replace(/[↗→]/g,'').trim())},true);
 window.openAssistant=show;})();
'''

EMBED_HEAD = ('<script>if(new URLSearchParams(location.search).get("embed"))document.documentElement.classList.add("embed")</script>'
              '<style>html.embed .topbar{display:none!important}html.embed body{grid-template-rows:minmax(0,1fr)!important}</style>')
