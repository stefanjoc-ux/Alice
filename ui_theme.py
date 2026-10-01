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
