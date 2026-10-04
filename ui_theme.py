"""Shared look for every Alice page (chat and Command centre): colours, type, buttons, inputs and the top bar.
Page-specific layout stays with each page. Change colours here once and both follow."""

SHARED_CSS = r'''
:root{color-scheme:light;--ink:#14324a;--muted:#5d7385;--faint:#8aa0b0;--line:#d5e0e8;--line2:#b9cbd8;--bg:#f4f7fa;--panel:#fff;
 --teal:#075e79;--teal-d:#054a60;--teal2:#e3f1f6;--violet:#634394;--violet2:#f1ebf7;--bar:#0b1626;--warn:#e2a33b;--ok:#1e5b31;--bad:#7a1f1f}
*{box-sizing:border-box}[hidden]{display:none!important}
html,body{height:100%}body{margin:0;font:15px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--teal)}button,select,textarea,input{font:inherit;color:inherit}
button{cursor:pointer;border:1px solid var(--line);background:#fff;border-radius:8px;padding:6px 12px}
button:hover:not(:disabled){border-color:#9db7c6;background:#f7fbfd}button:disabled{opacity:.55;cursor:default}
button.primary{background:var(--teal);border-color:var(--teal);color:#fff;font-weight:600}
button.primary:hover:not(:disabled){background:var(--teal-d);border-color:var(--teal-d)}

:where(input:not([type=checkbox]):not([type=radio]):not([type=file]),select,textarea){border:1px solid var(--line2);border-radius:8px;padding:7px 10px;background:#fff}
input:focus-visible,select:focus-visible,textarea:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.muted{color:var(--muted)}.small{font-size:13px}
/* top bar, the same on every page */
.topbar{position:relative;display:flex;align-items:center;gap:10px;height:52px;padding:0 14px 0 12px;background:var(--bar);color:#dfeaf2;border-bottom:1px solid #1d3347;min-width:0}
.brand{display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:.1em;font-size:13px;color:#e8f6ff;text-decoration:none;flex:none;width:224px}
.brand img{width:28px;height:28px;border-radius:50%;box-shadow:0 0 12px #4de6ff55}
.ghost{background:none;border:1px solid transparent;color:#9fb8ca;padding:3px 7px;font-size:14px;line-height:1}.ghost:hover:not(:disabled){background:#17304a;border-color:#2a4459;color:#fff}
.bar-link{position:relative;font-size:13px;color:#e6f6ff;text-decoration:none;padding:5px 12px;border-radius:8px;background:#163a52;border:1px solid #2f6a85;flex:none}.bar-link:hover{background:#1d4a66}
.badge-count{position:absolute;top:-7px;right:-8px;background:var(--warn);color:#1b1203;border-radius:999px;font-size:11px;font-weight:700;padding:0 6px;line-height:17px}
.sp{flex:1;min-width:8px}
'''


# ---------------- signed-in badge (top bar, under ALICE) ----------------
# Filled from /me: in Azure the person Entra signed in (Container Apps sign-in headers); on the PC "This computer only".
SIGNIN_CSS = r'''
.brand{position:relative}.brand-home{color:inherit;text-decoration:none;display:flex;align-items:center}.brand-text{display:flex;flex-direction:column;align-items:flex-start;line-height:1.15;min-width:0;flex:1}
.signin{display:inline-flex;align-items:center;gap:4px;margin-top:2px;padding:0;border:0;background:none;color:#8fd9b5;font:500 11px/1.2 "Segoe UI",system-ui,sans-serif;letter-spacing:0;cursor:pointer;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.signin,.signin:hover:not(:disabled),.signin:focus{background:none;border:0;padding:0;border-radius:3px}.signin svg,.signin-pop svg{flex:none;width:11px;height:11px}.signin-pop .ok svg{width:14px;height:14px}.signin.local{color:#a9bfd0;cursor:default}.signin:hover span,.signin:focus-visible span{text-decoration:underline}
.signin-pop{position:absolute;top:46px;left:0;z-index:60;width:280px;padding:14px 16px;border-radius:10px;background:#fff;color:var(--ink);box-shadow:0 8px 28px rgba(10,30,50,.25);font-size:13px;letter-spacing:0;font-weight:400;text-align:left}
.signin-pop[hidden]{display:none}.signin-pop b{display:block;font-size:14px;margin-bottom:2px}.signin-pop .muted{color:var(--muted)}
.signin-pop .ok{display:flex;gap:6px;align-items:center;margin:10px 0;color:#1e7b4f;font-weight:600}.signin-pop a.out{display:block;margin-top:8px;font-weight:600}.signin-pop a.out.btn{margin:14px 0 8px;padding:9px 12px;border-radius:8px;background:var(--teal);color:#fff;text-align:center;text-decoration:none}.signin-pop a.out.btn:hover{background:var(--teal-d)}.signin-pop a.out.all{margin-top:4px;font-weight:400;font-size:12px;color:var(--muted)}
@media(max-width:900px){.brand .brand-text{display:flex}.brand .brand-text>a{display:none}.brand .signin span{display:none}.signin svg{width:14px;height:14px}.signin-pop{top:50px}}
'''
LOCK_SVG = '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M4 7V5a4 4 0 1 1 8 0v2h.5A1.5 1.5 0 0 1 14 8.5v6A1.5 1.5 0 0 1 12.5 16h-9A1.5 1.5 0 0 1 2 14.5v-6A1.5 1.5 0 0 1 3.5 7H4Zm2 0h4V5a2 2 0 1 0-4 0v2Z"/></svg>'
def brand_html(href='/', title='Alice'):
    """The top-bar brand: logo and ALICE link home; the signed-in badge sits under ALICE (a button, so not inside the link)."""
    from html import escape
    return ('<div class="brand"><a class="brand-home" href="' + escape(href) + '" title="' + escape(title) + '"><img src="/static/favicon.png" alt=""></a>'
            '<span class="brand-text"><a class="brand-home" href="' + escape(href) + '" title="' + escape(title) + '">ALICE</a>'
            '<button type="button" class="signin" id="signin" hidden aria-haspopup="dialog" aria-expanded="false"></button></span></div>')
SIGNIN_JS = r'''
(()=>{const b=document.getElementById('signin');if(!b)return;const brand=b.closest('.brand');
 fetch('/me',{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(me=>{if(!me)return;
  const lock='__LOCK__';
  if(!me.signed_in){b.classList.add('local');b.innerHTML=lock;const s=document.createElement('span');s.textContent='This computer only';b.append(s);b.title='Alice is running on this computer and is reachable only from it.';b.hidden=false;return}
  b.innerHTML=lock;const s=document.createElement('span');s.textContent=me.name||me.email;b.append(s);b.title='Signed in securely as '+me.email;b.hidden=false;
  const pop=document.createElement('div');pop.className='signin-pop';pop.hidden=true;pop.setAttribute('role','dialog');pop.setAttribute('aria-label','Signed in');
  const n=document.createElement('b');n.textContent=me.name||me.email;const e=document.createElement('div');e.className='muted';e.textContent=me.email;
  const ok=document.createElement('div');ok.className='ok';ok.innerHTML=lock;const t=document.createElement('span');t.textContent='Signed in securely with Microsoft Entra ID';ok.append(t);
  const note=document.createElement('div');note.className='muted';note.textContent='Only the accounts you allowed can open Alice. Every action you take is recorded under this name.';
  const out=document.createElement('a');out.className='out btn';out.href='/signout';out.setAttribute('role','button');out.textContent='Sign out of Alice';
  const all=document.createElement('a');all.className='out all';all.href='/.auth/logout?post_logout_redirect_uri=/signed-out';all.textContent='Sign out of Microsoft too';all.title='Also signs this browser out of Outlook, Teams and the Azure portal';
  const every=document.createElement('a');every.className='out all';every.href='#';every.textContent='Sign out of Alice on all devices';every.title='Your phone, tablet and other computers will have to sign in to Alice again';
  every.addEventListener('click',ev=>{ev.preventDefault();if(!confirm('Sign out of Alice on every device, including this one? Each will have to sign in again. Your Microsoft sign-in elsewhere is not affected.'))return;
   const tok='__SIGNIN_TOKEN__';
   fetch('/admin/api/signout-everywhere',{method:'POST',credentials:'same-origin',headers:{'x-admin-token':tok}}).then(r=>r.json().then(j=>({ok:r.ok,j}))).then(({ok,j})=>{if(ok)location.href=j.next;else alert(j.detail||'Could not sign out everywhere.')}).catch(()=>alert('Could not sign out everywhere.'))});
  const dev=document.createElement('a');dev.className='out all';dev.href='/admin/signins';dev.textContent='Where you are signed in';
  pop.append(n,e,ok,note,out,dev,every,all);brand.append(pop);
  const toggle=(show)=>{pop.hidden=!show;b.setAttribute('aria-expanded',String(show))};
  b.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();toggle(pop.hidden)});
  pop.addEventListener('click',ev=>ev.stopPropagation());
  document.addEventListener('click',()=>toggle(false));document.addEventListener('keydown',ev=>{if(ev.key==='Escape')toggle(false)});
 }).catch(()=>{})})();
'''.replace('__LOCK__', LOCK_SVG.replace("'", "\\'"))


# ---------------- background requests and an ended session ----------------
# Behind Container Apps sign-in, a request without a session is sent to Microsoft to sign in. For the page's own
# background requests (menu badges, the signed-in badge, data loads) that must not happen: each one would start its own
# sign-in and overwrite the one you are doing, so Microsoft asks again and again. X-Requested-With: XMLHttpRequest tells
# sign-in to answer 401 instead. On a 401 the page offers "Sign in again" (a full page load, one sign-in) once.
FETCH_JS = r"""
(()=>{if(window.__aliceFetch)return;window.__aliceFetch=1;const f=window.fetch.bind(window);let shown=false;
 const ended=()=>{if(shown)return;shown=true;const b=document.createElement('div');b.className='session-ended';b.setAttribute('role','alert');
  const t=document.createElement('span');t.textContent='Your Alice session has ended.';const a=document.createElement('button');a.type='button';a.textContent='Sign in again';
  a.onclick=()=>location.reload();b.append(t,a);(document.body||document.documentElement).append(b)};
 window.fetch=(u,o)=>{o=Object.assign({},o||{});let same=true;
  try{same=new URL(typeof u==='string'?u:u.url,location.href).origin===location.origin}catch{}
  if(same){const h=new Headers(o.headers||(typeof u!=='string'&&u.headers)||undefined);h.set('X-Requested-With','XMLHttpRequest');o.headers=h;if(!o.credentials)o.credentials='same-origin'}
  return f(u,o).then(r=>{if(same&&r.status===401&&!String(typeof u==='string'?u:u.url).includes('/me'))ended();return r})}})();
"""
FETCH_CSS = (".session-ended{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:999;display:flex;gap:14px;align-items:center;"
             "padding:12px 16px;border-radius:12px;background:#0b1626;color:#e8f6ff;box-shadow:0 10px 30px rgba(0,0,0,.35);font-size:14px}"
             ".session-ended button{background:#075e79;border:0;color:#fff;font-weight:600;padding:7px 14px;border-radius:8px}")


# ---------------- which release is running ----------------
def version_info(env=None):
    """The release this image is (ALICE_VERSION, set when the pipeline builds it), when it was built, and in Azure the
    running revision. 'local' on the PC. Nothing secret: a commit code and a time."""
    import os, re
    env = os.environ if env is None else env
    v = (env.get('ALICE_VERSION') or 'local').strip()[:40]
    if not re.fullmatch(r'[0-9A-Za-z._-]{1,40}', v): v = 'local'
    built = (env.get('ALICE_BUILT') or '').strip()[:25]
    rev = (env.get('CONTAINER_APP_REVISION') or '').strip()[:80]
    repo = (env.get('ALICE_REPO_URL') or 'https://github.com/stefanjoc-ux/Alice').rstrip('/')
    link = repo + '/commit/' + v if re.fullmatch(r'[0-9a-f]{7,40}', v) else ''
    return {'version': v, 'built': built, 'revision': rev, 'link': link}
