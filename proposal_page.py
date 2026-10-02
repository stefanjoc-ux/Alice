"""The Proposal writer page: a brief in; a QA-checked Word proposal out. No menus and no access to the rest of Alice."""
import json
from html import escape
from urllib.parse import quote


def parker_logo(size=40, uid='pk'):
    """Parker's mark: a pen nib on a violet-to-teal tile."""
    return (f'<svg class="parker" width="{size}" height="{size}" viewBox="0 0 48 48" role="img" aria-label="Parker">'
            f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7a5bb5"/>'
            f'<stop offset="1" stop-color="#0a7f9f"/></linearGradient></defs>'
            f'<rect width="48" height="48" rx="13" fill="url(#{uid})"/>'
            f'<path d="M17 8h14v5.5c0 1.6 2.2 4.2 2.2 9.2 0 2.4-.6 3.9-1.6 5.4L24 41l-7.6-12.9c-1-1.5-1.6-3-1.6-5.4 0-5 2.2-7.6 2.2-9.2z" fill="#fff"/>'
            f'<path d="M17 13.5h14" stroke="#4a6fae" stroke-opacity=".35" stroke-width="1.4"/>'
            f'<path d="M24 26v13" stroke="#3d72a6" stroke-width="1.9" stroke-linecap="round"/>'
            f'<circle cx="24" cy="23.5" r="2.9" fill="url(#{uid})"/>'
            f'<path d="M12.5 41.5h7" stroke="#fff" stroke-opacity=".55" stroke-width="2" stroke-linecap="round"/></svg>')


def render(a):
    from ui_theme import SHARED_CSS
    from proposal_ui import PE_CSS, PE_JS
    data = json.dumps({'id': a['id'], 'name': a['name'], 'greeting': a['greeting'], 'paused': a['status'] != 'active'})
    return ('''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + escape(a['name']) + '''</title><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,''' + quote(parker_logo(48, 'fv')) + '''">
<style>''' + SHARED_CSS + PE_CSS + '''
body{display:grid;grid-template-rows:52px minmax(0,1fr);overflow:hidden}
.topbar .brand{width:auto}.topbar .who{font-size:15px;font-weight:600;color:#fff;letter-spacing:0}
main{overflow:auto;padding:24px 16px 60px}
.wrap{max-width:980px;margin:0 auto;display:grid;gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.card h1{margin:0 0 6px;font-size:21px}.card h2{margin:0 0 10px;font-size:17px}.card>p.lead{margin:0;color:var(--muted)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid2 label,.stack label{display:grid;gap:4px;font-weight:600;font-size:14px}
.stack{display:grid;gap:12px}textarea#brief{min-height:190px}textarea{resize:vertical}
.hint{font-weight:400;color:var(--muted);font-size:12.5px}
details.fold{border-top:1px solid var(--line);padding-top:12px}details.fold>summary{cursor:pointer;font-weight:700;font-size:15px;list-style:none;display:flex;gap:8px;align-items:center}
details.fold>summary::before{content:'\\25B8';color:var(--muted)}details.fold[open]>summary::before{content:'\\25BE'}
.check{display:flex!important;gap:8px;align-items:center;font-weight:400!important}
.pe-meta label{display:flex!important;gap:6px;align-items:center;font-weight:400!important;font-size:12.5px}
.go{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.steps{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:6px}.steps li{display:flex;gap:10px;align-items:center;color:var(--muted)}
.steps li::before{content:'';width:10px;height:10px;border-radius:50%;border:2px solid #b9c6cf;flex:none}
.steps li.done{color:var(--ink)}.steps li.done::before{background:#55b987;border-color:#55b987}
.steps li.now{color:var(--ink);font-weight:600}.steps li.now::before{border-color:#e2a33b;background:#fdf3e1;animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.4}}
.verdict{display:flex;gap:14px;align-items:center;flex-wrap:wrap;border-radius:10px;padding:12px 14px;margin-bottom:12px}
.verdict.ok{background:#eef8f1;border:1px solid #9fcfaf}.verdict.warn{background:#fdf3e1;border:1px solid #e2bf85}.verdict.bad{background:#fbeaea;border:1px solid #e0aaaa}
.verdict strong{font-size:16px}.dl{margin-left:auto;background:var(--teal);color:#fff!important;padding:9px 16px;border-radius:8px;text-decoration:none;font-weight:600;white-space:nowrap}.dl:hover{filter:brightness(1.1)}.score{font-size:24px;font-weight:700}
table.t{width:100%;border-collapse:collapse;font-size:14px}table.t th{text-align:left;font-size:12.5px;color:var(--muted);padding:6px;border-bottom:1px solid var(--line)}
table.t td{padding:6px;border-bottom:1px solid var(--line);vertical-align:top}table.t td.num{text-align:right;white-space:nowrap}table.t tr.tot td{font-weight:700}
.st{font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid}.st.met{background:#eef8f1;color:#1e5b31;border-color:#9fcfaf}.st.partly{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.st.missing,.st.high{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}.st.medium{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.st.low{background:#f4f6f8;color:#4b5a66;border-color:#c1cbd3}
.internal{border:2px dashed #c7b8dd;background:#faf7fd}.internal h2::after{content:' \\00b7 internal: not in the document, never sent to the AI';font-size:12px;font-weight:400;color:#634394}
.warnline{color:#7a1f1f;font-weight:600;margin:6px 0 0}
.issues{display:grid;gap:8px;margin:0;padding:0;list-style:none}.issues li{display:grid;gap:2px;border-left:3px solid #c1cbd3;padding-left:10px}.issues li.high{border-color:#b3261e}.issues li.medium{border-color:#e2a33b}
.draft h3{margin:16px 0 4px;font-size:15px}.draft .body{white-space:pre-wrap;font-size:14px;line-height:1.55}
.recent{display:grid;gap:6px}.recent button{text-align:left;display:flex;justify-content:space-between;gap:12px;width:100%}
.err{background:#fbeaea;border:1px solid #e0aaaa;border-radius:10px;padding:10px 12px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
[hidden]{display:none!important}.qa-mode .w-only{display:none!important}
.mode{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.mode h2{margin:0}.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid var(--line2,#b9cbd8);background:#fff;border-radius:999px;padding:6px 14px;font-weight:600;font-size:13.5px;cursor:pointer;color:var(--ink)}.mode .chip.on{background:var(--teal)!important;border-color:var(--teal)!important;color:#fff!important}.mode .chip:not(.on){background:#fff!important;color:var(--ink)!important}
.rounds{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:13px;color:var(--muted);margin:4px 0}.rounds b{color:var(--ink)}
.act{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:6px}.act label.btnlike{cursor:pointer;border:1px solid var(--line2,#b9cbd8);border-radius:8px;padding:8px 14px;font-weight:600;font-size:14px;background:#fff}
.edit-sec{display:grid;gap:4px;margin:12px 0}.edit-sec textarea{min-height:140px;font-size:14px;line-height:1.5}
.ref-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.ref-tools input{flex:1;min-width:200px}
.ref-upl{cursor:pointer;border:1px solid var(--line2,#b9cbd8);border-radius:8px;padding:8px 14px;font-weight:600;font-size:14px;background:#fff}.ref-upl:hover{border-color:var(--teal)}
.ref-list{display:grid;gap:6px;max-height:320px;overflow:auto;padding-right:4px}
.ref-item{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-weight:400!important}
.ref-item.off{opacity:.55}.ref-item b{font-weight:600;overflow-wrap:anywhere}.ref-item .hint{display:block}
.ref-badges{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.rb{font-size:11.5px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);background:#f4f6f8;color:#4b5a66;white-space:nowrap}
.rb.ok{background:#eef8f1;color:#1e5b31;border-color:#9fcfaf}.rb.wait{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.rb.cl{background:#ede7f6;color:#4b2f73;border-color:#c7b8dd}
.ref-panel{border:1px solid #c7b8dd;background:#faf7fd;border-radius:12px;padding:14px 16px;margin-bottom:10px;display:grid;gap:10px}
.ref-panel h3{margin:0;font-size:15px}.ref-panel .grid2 label,.ref-panel>label{display:grid;gap:4px;font-weight:600;font-size:14px}
.ref-tag{display:grid;gap:6px}.ref-tag label{display:flex!important;gap:8px;align-items:center;font-weight:400!important}
.ref-ok{background:#eef8f1;border:1px solid #9fcfaf;border-radius:10px;padding:10px 12px;font-size:14px}
@media(max-width:760px){.grid2,.cols{grid-template-columns:minmax(0,1fr)}}



/* Parker chat (always in view) */
.pk{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;background:var(--panel);border:1px solid #d6c8ea;border-radius:16px;overflow:hidden;box-shadow:0 1px 2px rgba(16,42,67,.04),0 10px 26px -16px rgba(75,47,115,.45)}
.pk-head{display:flex;gap:10px;align-items:center;padding:12px 14px;background:linear-gradient(135deg,#f6f2fb,#eef6f9);border-bottom:1px solid #e4dbf0}
.pk-head b{display:block;font-size:15.5px}.pk-head span.s{font-size:12px;color:var(--muted)}.pk-head .parker{flex:none;border-radius:10px}
.pk-head #pk-wide{margin-left:auto}.pk-head .pk-new{font-size:12px;padding:4px 10px;border-radius:999px}
.pk-log{flex:1 1 auto;min-height:0;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#fcfbfe}
.pk-m{max-width:92%;padding:11px 14px;border-radius:14px;font-size:15px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
.pk-m.you{align-self:flex-end;background:linear-gradient(135deg,#0a6d8b,#075e79);color:#fff;border-bottom-right-radius:4px}
.pk-m.pk-p{align-self:flex-start;background:#fff;border:1px solid #e4dbf0;border-bottom-left-radius:4px}
.pk-m.err{background:#fbeaea;border-color:#e0aaaa}
.pk-ch{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.pk-ch span{background:#f1ebf7;border:1px solid #d6c8ea;color:#4b2f73;border-radius:999px;padding:2px 9px;font-size:12px;font-weight:600;cursor:pointer}
.pk-q{margin:8px 0 0;padding:8px 10px 8px 26px;background:#fdf7ea;border:1px solid #ecd6a8;border-radius:10px;font-size:13px;white-space:normal}
.pk-q li{cursor:pointer}.pk-q li:hover{text-decoration:underline}
.pk-undo{margin-top:6px;font-size:12px;border:0!important;background:none!important;color:#634394!important;padding:0!important;text-decoration:underline;cursor:pointer}
.pk-starts{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.pk-starts button{font-size:12.5px;padding:5px 11px;border-radius:999px;border:1px solid #d6c8ea;background:#fff;color:#4b2f73;font-weight:600}
.pk-typing{align-self:flex-start;display:inline-flex;gap:4px;background:#fff;border:1px solid #e4dbf0;border-radius:14px;padding:11px 13px}
.pk-typing i{width:7px;height:7px;border-radius:50%;background:#a48fc9;animation:bob 1.2s infinite}.pk-typing i:nth-child(2){animation-delay:.15s}.pk-typing i:nth-child(3){animation-delay:.3s}
@keyframes bob{0%,60%,100%{transform:none;opacity:.5}30%{transform:translateY(-4px);opacity:1}}
.pk-in{border-top:1px solid #e4dbf0;padding:10px 12px 8px;background:#fff}
.pk-box{display:flex;gap:8px;align-items:flex-end;border:1px solid #cdbfe3;border-radius:12px;padding:6px 6px 6px 10px;background:#fff}
.pk-box:focus-within{border-color:#634394;box-shadow:0 0 0 3px rgba(99,67,148,.12)}
.pk-box textarea{flex:1;border:0!important;outline:none;box-shadow:none!important;background:transparent!important;resize:none;min-height:76px;max-height:300px;padding:8px 0!important;font-size:15px;line-height:1.5;font-weight:400}
.pk-att{cursor:pointer;flex:none;width:34px;height:34px;border-radius:9px;display:grid;place-items:center;color:#4b2f73;border:1px dashed #b9a6d6;font-size:17px}.pk-att:hover{background:#faf7fd}
.pk-send{flex:none;border:0!important;color:#fff!important;font-weight:700;padding:9px 14px!important;border-radius:9px!important;background:linear-gradient(135deg,#634394,#075e79)!important}
.pk-send:disabled{opacity:.55}
.pk-doc{display:inline-flex;gap:6px;align-items:center;background:#ede7f6;color:#4b2f73;border-radius:999px;padding:3px 6px 3px 11px;font-size:12px;font-weight:600;margin:0 0 6px}.pk-doc button{border:0;background:none;color:#4b2f73;padding:0 4px;font-size:14px}
.pk-foot{margin:7px 2px 0;font-size:11.5px;color:var(--muted);line-height:1.4}.pk-foot b{color:#4b2f73}
.sumbar{flex:none;background:var(--panel);border:1px solid #dce6ee;border-radius:14px;padding:10px 14px}
.sumbar>summary{cursor:pointer;list-style:none;display:flex;gap:8px;align-items:center;font-size:13px}.sumbar>summary::-webkit-details-marker{display:none}
.sumbar>summary b{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.sumbar>summary span{margin-left:auto;font-weight:600;font-variant-numeric:tabular-nums}
.sumbar[open]>summary{margin-bottom:6px}
.sumbar .go2{width:100%;margin-top:10px;padding:10px 16px;font-size:15px;border-radius:10px}
/* collapsible sections */
.formbar{display:flex;gap:8px;align-items:center;justify-content:flex-end;font-size:13px;color:var(--muted);margin-bottom:-6px}
.formbar button{border:0;background:none;color:var(--teal);font-weight:600;padding:2px 4px;font-size:13px}
section.panel>.ph{cursor:pointer;user-select:none}
section.panel>.ph::after{content:'';margin-left:auto;flex:none;width:9px;height:9px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:rotate(-135deg);transition:transform .15s}
section.panel.shut>.ph::after{transform:rotate(45deg)}
section.panel.shut>:not(.ph){display:none!important}
.panel.pk-hit{animation:hit 1.6s ease-out}@keyframes hit{0%{box-shadow:0 0 0 4px rgba(99,67,148,.35)}100%{box-shadow:0 0 0 0 rgba(99,67,148,0)}}
.ph .pk-tag,summary .pk-tag{font-size:11.5px;font-weight:700;color:#4b2f73;background:#f1ebf7;border:1px solid #d6c8ea;border-radius:999px;padding:1px 8px;margin-left:8px;vertical-align:middle}
.tfill{border-color:#a98fd0!important;background:#fbf8ff!important;box-shadow:0 0 0 3px rgba(99,67,148,.10)!important}
/* ---------- look and feel ---------- */
main{padding:20px 0 40px;background:linear-gradient(180deg,#eef3f7 0,#f4f7fa 260px)}
.wrap{max-width:1500px;padding:0 20px;gap:20px}
.hero{position:relative;overflow:hidden;border-radius:16px;color:#e8f1f7;background:radial-gradient(900px 300px at 85% -40%,rgba(64,170,200,.35),transparent 60%),linear-gradient(120deg,#0b1626 0%,#0d2a3f 55%,#075e79 100%);padding:24px 26px 22px;margin:0}
.hero::after{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);background-size:28px 28px;mask-image:linear-gradient(90deg,transparent,#000 70%);pointer-events:none}
.hero-in{position:relative;z-index:1;display:flex;gap:24px;align-items:flex-end;justify-content:space-between;flex-wrap:wrap}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#8fd0e3;font-weight:700;margin:0 0 6px}
.hero h1{margin:0 0 8px;font-size:30px;line-height:1.15;color:#fff;font-weight:700;letter-spacing:-.01em}
.hero .lead{margin:0;max-width:620px;color:#c4d6e2;font-size:15.5px}
.flow{list-style:none;display:flex;gap:0;margin:0;padding:0;counter-reset:fl}
.flow li{counter-increment:fl;display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:#dbe8f0;white-space:nowrap}
.flow li::before{content:counter(fl);display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);font-size:12px}
.flow li+li::before{margin-left:0}.flow li:not(:last-child)::after{content:'';width:26px;height:1px;background:rgba(255,255,255,.35);margin:0 10px}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 470px;gap:20px;align-items:start}
@media(min-width:1600px){.layout{grid-template-columns:minmax(0,1fr) 540px}}
.layout.pk-wide{grid-template-columns:minmax(0,1fr) min(760px,55%)}
.colmain{display:grid;gap:16px;min-width:0}
.side{position:sticky;top:0;height:calc(100vh - 52px - 40px);display:flex;flex-direction:column;gap:12px;min-height:0}
.card{border-radius:14px;border-color:#dce6ee;box-shadow:0 1px 2px rgba(16,42,67,.04),0 6px 18px -10px rgba(16,42,67,.18)}
.card h2{font-size:17px;letter-spacing:-.005em}
#f{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}.wrap{counter-reset:panel}
.full{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;margin-top:16px}.colmain{grid-template-columns:minmax(0,1fr)}.panel{min-width:0}
.panel{background:var(--panel);border:1px solid #dce6ee;border-radius:14px;padding:20px 22px;box-shadow:0 1px 2px rgba(16,42,67,.04),0 6px 18px -10px rgba(16,42,67,.18);display:grid;gap:14px}
.panel:not([hidden]){counter-increment:panel}
.ph{display:flex;gap:12px;align-items:center;min-width:0}.ph>div{min-width:0}.mode{min-width:0}
.ph::before,details.panel>summary::before{content:counter(panel)!important;flex:none;display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:var(--teal2);color:var(--teal);font-weight:700;font-size:14px;border:1px solid #bcdbe6}
.ph h2,.ph .pt{margin:0;font-size:17px;font-weight:700}.ph .ps,.psub{display:block;font-size:12.5px;color:var(--muted);font-weight:400;margin-top:1px}
.ph .mode{flex:1}
details.panel{padding:0;gap:0}details.panel>summary{padding:18px 22px;border-radius:14px;font-size:17px!important;gap:12px!important}
details.panel>summary:hover{background:#f8fbfd}details.panel[open]>summary{border-bottom:1px solid var(--line);border-radius:14px 14px 0 0}
details.panel>summary::after{content:'';margin-left:auto;width:9px;height:9px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:rotate(45deg);transition:transform .15s}
details.panel[open]>summary::after{transform:rotate(-135deg)}
details.panel>.pbody{padding:16px 22px 20px;display:grid;grid-template-columns:minmax(0,1fr);gap:12px}details.panel{min-width:0}
details.panel>summary .hint{font-size:13px}
.panel select{width:100%;min-width:0;max-width:100%}.panel>label,.pbody>label,.qa-only>label{display:grid;grid-template-columns:minmax(0,1fr);gap:6px;font-weight:600;font-size:13.5px}.grid2{align-items:start}.grid2 label{gap:6px!important;font-size:13.5px}
.panel :where(input:not([type=checkbox]):not([type=radio]):not([type=file]),select,textarea),.side select{font-weight:400;border-radius:10px;border:1px solid #c9d7e2;background:#fbfdfe;padding:9px 12px;transition:border-color .12s,box-shadow .12s,background .12s}
.panel :where(input,select,textarea):focus{outline:none;border-color:var(--teal);background:#fff;box-shadow:0 0 0 3px rgba(7,94,121,.14)}
.panel ::placeholder{color:#94a7b5;font-weight:400}
textarea#brief{min-height:210px;line-height:1.55}
.toggle{display:flex!important;gap:12px;align-items:flex-start;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:#f8fbfd;font-weight:400!important}
.toggle input{margin-top:3px;accent-color:var(--teal);width:16px;height:16px}.toggle b{display:block;font-weight:600}
.costline{display:flex;gap:8px;align-items:baseline;margin:0}.costline::before{content:'$';display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:#eef8f1;color:var(--ok);font-weight:700;font-size:11.5px;flex:none;transform:translateY(4px)}
.costline:empty{display:none}
.mode .chips{background:#eef3f7;padding:4px;border-radius:999px;border:1px solid var(--line)}
.mode .chip{border:0!important;padding:7px 16px}.mode .chip:not(.on){background:transparent!important;color:var(--muted)!important}
.mode .chip.on{box-shadow:0 2px 6px -2px rgba(7,94,121,.5)}
.actionbar{position:static;display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:14px 20px;border-radius:14px;background:linear-gradient(135deg,#f3f9fb,#faf7fd);border:1px solid #dce6ee;box-shadow:0 0 0 0 rgba(16,42,67,.35)}
.actionbar .primary{padding:11px 22px;font-size:15px;border-radius:10px;box-shadow:0 6px 14px -8px rgba(7,94,121,.8)}
.actionbar .hint{flex:1;min-width:200px}
.ptitle{display:flex;gap:16px;align-items:center;margin-bottom:10px}.ptitle h1{margin:0}.ptitle .eyebrow{margin:0 0 4px}
.hero .parker{flex:none;filter:drop-shadow(0 8px 18px rgba(0,0,0,.35));border-radius:16px}
.topbar .parker{border-radius:8px}
.sum .go2{width:100%;margin-top:14px;padding:11px 16px;font-size:15px;border-radius:10px}
/* side summary */
.sum h2{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 10px}
.sum dl{margin:0;display:grid;gap:0}.sum dl>div{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px dashed var(--line);font-size:14px}
.sum dl>div:last-child{border-bottom:0}.sum dt{color:var(--muted)}.sum dd{margin:0;font-weight:600;text-align:right;overflow-wrap:anywhere;min-width:0}
.sum dd.none{color:#9aabb8;font-weight:400}
.sum .big{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.sum .big div{background:#f4f8fb;border:1px solid var(--line);border-radius:10px;padding:8px 10px}.sum .big span{display:block;font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.sum .big b{font-size:17px;font-variant-numeric:tabular-nums}
.sum .safe{margin:14px 0 0;font-size:12px;color:#4b2f73;background:var(--violet2);border-radius:10px;padding:9px 11px;line-height:1.45}
.recent{gap:8px}.recent button{border-radius:10px;padding:10px 12px;display:grid!important;gap:2px;border-left:4px solid #c1cbd3;font-weight:600;font-size:13.5px}
.recent button.ok{border-left-color:#55b987}.recent button.warn{border-left-color:#e2a33b}.recent button.bad{border-left-color:#b3261e}.recent button.run{border-left-color:#4aa3c0}
.recent button .hint{font-weight:400}
/* progress stepper */
#prog h2{margin-bottom:4px}
.steps{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:0;margin:16px 0 4px;counter-reset:st}
.steps li{counter-increment:st;display:grid!important;align-items:start!important;align-content:start;justify-items:center;text-align:center;gap:8px;font-size:12.5px;position:relative;padding:0 6px}
.steps li::before{content:counter(st)!important;width:34px!important;height:34px!important;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:13px;color:#8aa0b0;background:#fff;position:relative;z-index:1}
.steps li.done::before{content:'\\2713'!important;color:#fff}.steps li.now::before{color:#9a6512}
.steps li:not(:first-child)::after{content:'';position:absolute;top:17px;right:50%;width:100%;height:2px;background:#dbe4ea;z-index:0}
.steps li.done:not(:first-child)::after,.steps li.now:not(:first-child)::after{background:#55b987}
/* results */
.verdict{padding:16px 18px;border-radius:14px;gap:18px}
.score{--p:0;--c:#55b987;width:68px;height:68px;border-radius:50%;display:grid;place-items:center;font-size:19px!important;background:radial-gradient(closest-side,#fff 78%,transparent 80% 100%),conic-gradient(var(--c) calc(var(--p)*1%),#e3e9ee 0);flex:none}
.verdict>div{flex:1 1 260px;min-width:0}.verdict.warn .score{--c:#e2a33b}.verdict.bad .score{--c:#b3261e}
.dl{padding:11px 18px!important;border-radius:10px!important;box-shadow:0 6px 14px -8px rgba(7,94,121,.8)}
.dl::before{content:'\\2193\\00a0\\00a0'}
table.t th{text-transform:uppercase;letter-spacing:.05em;font-size:11.5px}table.t tr:nth-child(even) td{background:#fafcfd}
.internal{border:1px solid #d9cdea;background:linear-gradient(180deg,#fbf9fe,#fff)}
@media(max-width:1080px){.layout{grid-template-columns:minmax(0,1fr)}.side{position:static;height:auto}.pk{height:560px;flex:none}}
@media(max-width:760px){.wrap{padding:0 12px}.panel{padding:16px}details.panel>summary{padding:16px}details.panel>.pbody{padding:14px 16px 18px}.ph{align-items:flex-start}.actionbar{padding:12px;position:static}.mode .chips{border-radius:14px}.hero h1{font-size:24px}.flow{display:none}.steps{grid-auto-flow:row}.steps li{grid-template-columns:34px 1fr;justify-items:start;text-align:left}.steps li::after{display:none}}
</style></head><body>
<header class="topbar"><span class="brand">''' + parker_logo(26, 'tb') + '''<span class="who">''' + escape(a['name']) + '''</span></span><div class="sp"></div><span class="small" style="color:#9fb8ca">Built on Alice</span></header>
<main><div class="wrap"><div class="layout"><div class="colmain">
<section class="hero"><div class="hero-in"><div><div class="ptitle">''' + parker_logo(58, 'hr') + '''<div><p class="eyebrow">Proposal writer \u00b7 bid and proposal studio</p><h1>''' + escape(a['name']) + '''</h1></div></div><p class="lead" id="greeting"></p></div>
<ol class="flow" aria-label="How it works"><li>Brief</li><li>Draft</li><li>QA check</li><li>Word document</li></ol></div></section>
<section class="card" id="prog" hidden aria-live="polite"><h2 id="prog-title">Working on it</h2><ol class="steps" id="steps"></ol><div class="err" id="perr" hidden></div></section>
<div id="result"></div>
<form id="f">
<div class="formbar"><span>Proposal form</span><button type="button" id="exp-all">Expand all</button><button type="button" id="col-all">Collapse all</button></div>
<section class="panel"><div class="ph"><div class="mode"><div><h2 id="f-h">New proposal</h2><span class="ps">The brief, and who it is for</span></div><div class="chips" role="tablist" aria-label="What to do"><button type="button" class="chip on" id="m-write" role="tab" aria-selected="true">Write a proposal</button><button type="button" class="chip" id="m-qa" role="tab" aria-selected="false">Check one I already have</button></div></div></div>
<div class="grid2"><label>Proposal title<input id="title" maxlength="150" required placeholder="e.g. Data security baseline for Microsoft Fabric"></label>
<label>Client or organisation<input id="org" maxlength="80" list="orgs" placeholder="Start typing a name"><datalist id="orgs"></datalist><span class="hint" id="org-hint">Its approved profile is used. Only this client's tagged material is used, never another client's.</span></label></div>
<label>Brief and context<textarea id="brief" maxlength="20000" required placeholder="Paste the brief or describe what the client wants: outcomes, scope, requirements, timescales, evaluation criteria, anything they said."></textarea>
<span class="hint">Everything in the brief is checked before it goes to the AI: secrets and protective markings are refused.</span></label>
<div class="qa-only" hidden><label>Your proposal document<input type="file" id="qa-file" accept=".docx,.pdf,.txt,.md"><span class="hint">Word, PDF or text. Proposal QA checks it against the brief above. Your document is read for the check and not kept.</span></label></div>
<label class="w-only">Notes for the writer <span class="hint">(optional: angle to take, things to stress or avoid)</span><textarea id="notes" maxlength="4000" rows="3" placeholder="e.g. Lead with value for money; they were burned by a big-bang migration before."></textarea></label>
</section>
<section class="panel"><div class="ph"><div><span class="pt">Set-up</span><span class="ps">Template, models and what Alice may draw on</span></div></div>
<label class="w-only">Proposal template<select id="tplsel"></select><span class="hint" id="tpl-hint"></span></label>
<div class="grid2"><label class="w-only">Writer model<select id="wm"></select></label><label>QA model<select id="qm"></select></label></div>
<p class="hint costline" id="cost"></p>
<label class="toggle w-only"><input type="checkbox" id="mem" checked><span><b>Use what Alice knows</b><span class="hint">Approved memories, decisions and knowledge that are general or tagged to this client. Never another client’s.</span></span></label>
</section>
<details class="fold panel w-only" id="refs-fold"><summary><span>Reference documents <span class="hint" id="ref-count"></span><span class="psub">Background the writer can draw on</span></span></summary><div class="pbody">
<p class="pe-note">Background the writer can draw on, such as Microsoft success guides or your own method papers. It reads each document's approved summary and the passages relevant to this brief, under the same rules as everything else. The documents stay in their source.</p>
<div class="ref-tools"><button type="button" class="secondary" id="ref-browse">Choose documents</button><input type="search" id="ref-q" placeholder="Filter by name or source" aria-label="Filter reference documents" hidden><label class="secondary ref-upl" tabindex="0">Upload a reference document<input type="file" id="ref-file" accept=".docx,.pdf,.txt,.md,.csv" hidden></label></div>
<div class="ref-panel" id="ref-panel" hidden></div>
<div class="ref-list" id="ref-list"></div></div></details>
<details class="fold panel w-only" open><summary><span>Format and flow<span class="psub">Sections, order and what goes in each</span></span></summary><div class="pbody">
<label>Paste a structure <span class="hint">(optional: headings, points or a rough outline, e.g. from the client's question list)</span><textarea id="structure" maxlength="6000" rows="4" placeholder="1. Executive summary&#10;- why now, value for money&#10;2. Our approach&#10;- phased, governance first&#10;3. Social value"></textarea></label>
<div class="go"><button type="button" class="secondary" id="struct-go">Turn into sections</button><span class="hint">Headings become sections; bullet points under a heading become text to include. Or leave it here and the writer follows it as an outline.</span></div>
<p class="pe-note">The sections in order. Template sections keep the template's formatting; add sections, rename them, reorder them, or add content suggestions for each. Standard text is copied from the template word for word.</p><div id="secs"></div><p class="pe-note" id="tpl"></p></div></details>
<div class="err" id="ferr" role="alert" hidden></div>
</form>
</div>
<aside class="side">
<section class="pk" id="pk" aria-label="Work with Parker"><div class="pk-head">''' + parker_logo(34, 'ch') + '''<div><b id="pk-title">Start with Parker</b><span class="s">Your proposal assistant</span></div><button type="button" class="secondary pk-new" id="pk-wide" title="Make Parker’s panel wider" aria-pressed="false">Wider</button><button type="button" class="secondary pk-new" id="pk-new" title="Start a new conversation (the form stays as it is)" style="margin-left:6px">New chat</button></div>
<div class="pk-log" id="pk-log" aria-live="polite"></div>
<div class="pk-in"><div id="pk-docs"></div><div class="pk-box"><label class="pk-att" title="Add the client’s brief or RFP" tabindex="0">+<input type="file" id="pk-file" accept=".docx,.pdf,.txt,.md" hidden></label><textarea id="pk-msg" maxlength="4000" placeholder="Tell Parker about the proposal, or answer its question…" aria-label="Message to Parker" rows="3"></textarea><button type="button" class="pk-send" id="pk-send">Send</button></div>
<p class="pk-foot"><b>Working with Parker:</b> it fills in the form as you talk and asks for what’s missing. Its changes are outlined, and you can undo any of them. Nothing is saved until you write the proposal.</p></div></section>
<details class="sumbar sum" id="sum-box"><summary><b>This proposal</b><span id="sum-line"></span></summary><dl id="sum"></dl><div class="big" id="sum-big"></div><p class="safe">Cost rates and protectively marked material never reach the AI. Every piece of context is checked on the way out.</p></details><button type="button" class="primary go2" id="go2" style="flex:none">Write proposal</button>
</aside></div>
<div class="full" id="full">
<details class="fold panel w-only"><summary><span>Rate card<span class="psub">Roles, days, cost and sell rates, margin</span></span></summary><div class="pbody">
<p class="pe-note">Load your pricing tool or paste a rate card, set the target margin Alice applies to each cost, and tick the roles this proposal needs. Change any sell rate or margin to override it (\u21ba puts it back); Price book keeps the rate from your pricing tool and Change shows the difference, so you can see what applying the target margin does. Add days to fix a role's quantity; the writer suggests the rest. Cost rates stay in Alice: never sent to the AI, never in the document.</p><div id="rates"></div></div></details>
<div class="actionbar"><button class="primary" id="go" type="submit" form="f">Write proposal</button><span class="hint" id="go-note">Writing, a QA check and one revision if needed: usually two to four minutes.</span></div>
<section class="card" id="recent-box" hidden><h2>Recent proposals</h2><div class="recent" id="recent"></div></section>
</div></div></main>
<script>
const A=''' + data.replace('</', '<\\/') + ''';
''' + PE_JS + r'''
const $=id=>document.getElementById(id),mk=PE.mk;let S=null,secEd=null,rateEd=null,timer=null;
const base='/assistant/'+encodeURIComponent(A.id);
async function api(path,method,body){const r=await fetch(base+path,{method:method||'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:(Array.isArray(d.detail)?d.detail.map(x=>x.msg).join('; '):'Something went wrong. Try again.'));return d}
const STEPS=[['Gathering','Gathering what Alice knows and writing the draft'],['checking the draft','Proposal QA checks the draft against the brief'],['Revising','Revising with the QA feedback (only if needed)'],['checking the revision','Proposal QA checks the revision'],['Building','Building the Word document']];
function drawSteps(stage,status,qa){const ol=$('steps');ol.replaceChildren();let idx=STEPS.findIndex(s=>stage&&stage.includes(s[0]));if(status==='done')idx=STEPS.length;
 if(status==='running'&&idx<0&&stage){ol.append(mk('li',stage,'now'));return}
 const skipped=status==='done'&&qa&&qa.length===1;
 STEPS.forEach(([k,l],i)=>{if(skipped&&(i===2||i===3))return;const li=mk('li',i===2&&skipped?l:l,i<idx?'done':i===idx?'now':'');ol.append(li)})}
let R={documents:[],folders:[],clients:[],categories:[]};const picked=new Set();
async function loadRefs(){try{R=await api('/references')}catch{R={documents:[],folders:[],clients:[],categories:[]}}drawRefs()}
let browsing=false;
$('ref-browse').onclick=()=>{browsing=!browsing;$('ref-q').hidden=!browsing;if(browsing)$('ref-q').focus();else $('ref-q').value='';drawRefs()};
function drawRefs(){const q=($('ref-q').value||'').toLowerCase(),org=$('org').value.trim().toLowerCase(),box=$('ref-list');box.replaceChildren();
 const tpl=(S&&S.template||'').replace(/\\/g,'/');const avail=R.documents.filter(d=>d.path.replace(/\\/g,'/')!==tpl);
 $('ref-browse').textContent=browsing?'Done':(picked.size?'Change documents':'Choose documents')+' ('+avail.length+' available)';
 if(!browsing&&!picked.size){box.append(mk('p','No reference documents chosen. Choose from the document sources, or upload one.','pe-note'));count();return}
 const docs=avail.filter(d=>browsing||picked.has(d.path)).filter(d=>!q||(d.name+' '+d.source+' '+d.path).toLowerCase().includes(q));
 if(!R.documents.length)box.append(mk('p','No documents in the document sources yet. Upload one, or add files to a source on the Documents page.','pe-note'));
 for(const d of docs){const other=d.clients.length&&!d.clients.some(c=>c.toLowerCase()===org);const row=mk('label','','ref-item'+(other?' off':''));
  const cb=document.createElement('input');cb.type='checkbox';cb.checked=picked.has(d.path);cb.disabled=other&&!picked.has(d.path);cb.onchange=()=>{cb.checked?picked.add(d.path):picked.delete(d.path);count()};
  const mid=mk('span');mid.append(mk('b',d.name),mk('span',d.source+' · '+d.path,'hint'));
  const bd=mk('span','','ref-badges');bd.append(mk('span',d.summary==='approved'?'Summary approved':d.summary==='draft'?'Summary awaiting approval':'No summary yet','rb'+(d.summary==='approved'?' ok':d.summary==='draft'?' wait':'')));
  for(const c of d.clients)bd.append(mk('span','For '+c+' only','rb cl'));if(!d.clients.length&&d.summary)bd.append(mk('span','General','rb'));
  if(other)row.title='Tagged to another client: it can only be used on that client\u2019s proposals.';row.append(cb,mid,bd);box.append(row)}
 count()}
function count(){$('ref-count').textContent=picked.size?'\u00b7 '+picked.size+' selected':'';summary()}
$('ref-q').oninput=drawRefs;
$('ref-file').onchange=async()=>{const f=$('ref-file').files[0];$('ref-file').value='';if(!f)return;const pan=$('ref-panel');pan.hidden=false;pan.replaceChildren(mk('p','Reading '+f.name+'\u2026','hint'));
 if(f.size>15*1024*1024){pan.replaceChildren(mk('p','That file is larger than 15 MB.','err'));return}
 const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=no;r.readAsDataURL(f)});
 let x;try{x=await api('/references/inspect','POST',{name:f.name,data,organisation:$('org').value})}catch(e){pan.replaceChildren(mk('p',e.message,'err'));return}
 refForm(x)};
function refForm(x){const pan=$('ref-panel');pan.replaceChildren();pan.append(mk('h3','Add '+x.name+' as a reference'));
 if(x.purview)pan.append(mk('p','Purview label: '+x.purview+'. Alice checks its mapping before anything is sent to the AI.','hint'));
 const ti=document.createElement('input');ti.maxLength=200;ti.value=x.title;const tl=mk('label','Title');tl.append(ti);
 const fs=document.createElement('select');for(const f of R.folders){const o=document.createElement('option');o.value=f.path;o.textContent=f.path.replace(/\//g,' \u203a ')+' ('+f.type_name+')';fs.append(o)}fs.value=x.folder;
 const nf=document.createElement('input');nf.maxLength=60;nf.value=x.new_folder||'';nf.placeholder='Optional';
 const g=mk('div','','grid2');const l1=mk('label','Save to');l1.append(fs,mk('span','Saved in the document source, not in Alice.','hint'));const l2=mk('label','New folder inside it');l2.append(nf);g.append(l1,l2);
 const tg=mk('div','','ref-tag');tg.append(mk('b','Who can use it'));const mkr=(v,txt)=>{const l=mk('label');const r=document.createElement('input');r.type='radio';r.name='reftag';r.value=v;r.checked=x.tag===v;l.append(r,document.createTextNode(txt));return [l,r]};
 const [lg,rg]=mkr('general','General: every client\u2019s proposals can use it');const [lc,rc]=mkr('client','One client only:');
 const cs=document.createElement('select');for(const c of R.clients){const o=document.createElement('option');o.value=c;o.textContent=c;cs.append(o)}if(x.client)cs.value=x.client;lc.append(cs);cs.onchange=()=>{rc.checked=true};
 tg.append(lg,lc,mk('span','Suggested: '+x.reason,'hint'));
 const cat=document.createElement('select');const o0=document.createElement('option');o0.value='';o0.textContent='No category';cat.append(o0);for(const c of R.categories){const o=document.createElement('option');o.value=c;o.textContent=c;cat.append(o)}cat.value=x.category||'';
 const cl=mk('label','Category in Knowledge');cl.append(cat);
 const go=document.createElement('button');go.type='button';go.className='primary';go.textContent='Save, summarise and use it';const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';cancel.textContent='Cancel';cancel.onclick=()=>{pan.hidden=true};
 const act=mk('div','','go');act.append(go,cancel,mk('span','Alice summarises it into Knowledge, pointing to the document. Takes about half a minute.','hint'));
 go.onclick=async()=>{go.disabled=true;go.textContent='Saving and summarising\u2026';
  try{const r=await api('/references','POST',{token:x.token,folder:fs.value,new_folder:nf.value,title:ti.value,tag:rc.checked?'client':'general',client:rc.checked?cs.value:'',category:cat.value});
   picked.add(r.path);await loadRefs();pan.replaceChildren(mk('div',r.note?r.note:'Saved to '+r.path.replace(/[\\\/]/g,' \u203a ')+' ('+r.where+')'+(r.client?', for '+r.client+' only':', for every client')+'. '+(r.duplicate?'Alice already had this summary.':r.summary==='approved'?'The summary is in Knowledge (approved automatically, logged on the Temple page).':'The summary is waiting for your approval in Knowledge; until then the writer uses the passages relevant to each brief.')+' It is selected for this proposal.','ref-ok'))}
  catch(e){go.disabled=false;go.textContent='Save, summarise and use it';pan.append(mk('p',e.message,'err'))}};
 pan.append(tl,g,tg,cl,act)}
async function load(){S=await api('/setup');loadRefs();$('greeting').textContent=A.paused?A.name+' is paused at the moment.':A.greeting;
 $('orgs').replaceChildren(...S.organisations.map(o=>{const x=document.createElement('option');x.value=o.name;if(o.client)x.label=o.name+' (client)';return x}));
 const opt=m=>{const o=document.createElement('option');o.value=m.key;o.textContent=m.name+(m.premium?' (premium)':'');return o};
 $('wm').replaceChildren(...S.models.map(opt));$('qm').replaceChildren(...S.models.map(opt));$('wm').value=S.writer;$('qm').value=S.qa;
 const cost=()=>{const w=S.models.find(m=>m.key===$('wm').value),q=S.models.find(m=>m.key===$('qm').value);if(!w||!q||w.writer_cost==null||q.qa_cost==null){$('cost').textContent='';window.estimate=null;return}
  const t=mode==='qa'?q.qa_cost/2:w.writer_cost+q.qa_cost;window.estimate=t;$('cost').textContent='Roughly $'+t.toFixed(2)+(mode==='qa'?' for the QA check.':' for this proposal (draft, QA, one revision and a second QA check), depending on the brief and context. Defaults are set on the Assistants page.')};
 $('wm').onchange=cost;$('qm').onchange=cost;cost();window.cost=cost;
 secEd=PE.sections($('secs'),S.sections,{include:true,empty:'No sections yet: add some, or choose a template on the Assistants page.'});rateEd=PE.rates($('rates'),S.rate_card,S.units,{target:S.target_margin,minMargin:S.min_margin,parse:async f=>api('/rates/parse','POST',{name:f.name,data:await fileData(f)})});
 const ts=$('tplsel');const topt=(v,txt)=>{const o=document.createElement('option');o.value=v;o.textContent=txt;return o};
 ts.replaceChildren(...S.templates.map(x=>topt(x.path,x.name+' · '+x.source+(x.path===S.template?' (default)':''))),topt('','No template: Alice’s own Word layout'));
 if(S.template&&!S.templates.some(x=>x.path===S.template))ts.prepend(topt(S.template,S.template+' (not found)'));ts.value=S.template||'';
 let tplTitles=new Set(S.sections.filter(x=>x.source==='template').map(x=>x.title));window.tplOf=()=>tplTitles;
 const tplHint=(o,err)=>{$('tpl-hint').textContent=err||(ts.value?(o&&o.sections?o.sections.filter(x=>x.source==='template').length+' sections from the template; its cover, styles, header and footer are kept.':'Sections, styles, cover, header and footer come from the template.'):'No template: the proposal uses Alice’s own Word layout with the sections below.')+(S.templates.length?'':' Put a Word template in a folder on the Documents page to choose it here.')};
 tplHint(null,S.template_error);$('tpl').textContent='';
 ts.onchange=async()=>{try{const o=await api('/outline?template='+encodeURIComponent(ts.value));const now=secEd.value();const fresh=new Set(o.sections.map(x=>x.title.toLowerCase()));
   const mine=now.filter(x=>!tplTitles.has(x.title)&&!fresh.has(x.title.toLowerCase())).map(x=>({...x,source:'added'}));
   secEd.set(o.sections.concat(mine));tplTitles=new Set(o.sections.filter(x=>x.source==='template').map(x=>x.title));tplHint(o)}catch(e){tplHint(null,e.message)}};
 if(A.paused)$('go').disabled=true;summary();recent();const q=new URLSearchParams(location.search).get('p');if(q)follow(q)}
$('org').addEventListener('input',()=>drawRefs());
$('org').oninput=()=>{const o=S&&S.organisations.find(x=>x.name.toLowerCase()===$('org').value.trim().toLowerCase());$('org-hint').textContent=o?(o.client?o.name+' is a client: its tagged memories and knowledge are included; other clients’ never are.':'Its approved profile is used.'):($('org').value.trim()?'Not in the list: Alice checks other names it knows (e.g. SBC); if none match, the name is used as typed.':'Its approved profile is used. Only this client’s tagged material is used, never another client’s.')};
let mode='write';
function summary(){const dl=$('sum');if(!dl||!S)return;dl.replaceChildren();const row=(k,v)=>{const d=mk('div');d.append(mk('dt',k),mk('dd',v||'Not set',v?'':'none'));dl.append(d)};
 const org=$('org').value.trim();const o=S.organisations.find(x=>x.name.toLowerCase()===org.toLowerCase());row('Client',org?(org+(o&&o.client?' (client)':'')):'');
 if(mode==='qa'){row('Document',($('qa-file').files[0]||{}).name||'');row('QA model',($('qm').selectedOptions[0]||{}).textContent||'')}
 else{const ts=$('tplsel').selectedOptions[0];row('Template',ts?(ts.value?ts.textContent.split(' · ')[0].replace(/\.docx$/i,''):'Alice’s own layout'):'');
  row('Sections',secEd?String(secEd.value().length):'');row('References',picked.size?String(picked.size):'');
  row('Writer',($('wm').selectedOptions[0]||{}).textContent||'');row('Alice’s knowledge',$('mem').checked?'Used':'Not used')}
 const big=$('sum-big');big.replaceChildren();const tile=(k,v)=>{const d=mk('div');d.append(mk('span',k),mk('b',v));big.append(d)};
 if(mode!=='qa'&&rateEd){const rs=rateEd.value().filter(r=>r.use);const priced=rs.filter(r=>r.days&&r.sell!=='');const sell=priced.reduce((a,r)=>a+Number(String(r.sell).replace(/[£,]/g,''))*Number(r.days),0);
  const cst=priced.reduce((a,r)=>a+Number(String(r.cost).replace(/[£,]/g,''))*Number(r.days),0);tile('Roles',String(rs.length));tile('Sell price',priced.length?PE.gbp(Math.round(sell)):'—');
  if(priced.length&&sell)tile('Margin',((sell-cst)/sell*100).toFixed(1)+'%')}
 if(window.estimate!=null)tile('AI cost','$'+window.estimate.toFixed(2));
 const ln=[...big.children].filter(d=>d.firstChild.textContent!=='AI cost').map(d=>d.lastChild.textContent+(d.firstChild.textContent==='Roles'?' roles':'')).filter(x=>x&&x!=='—');$('sum-line').textContent=ln.join(' \u00b7 ')||(org||'')}
$('f').addEventListener('input',()=>summary());$('f').addEventListener('change',()=>summary());$('f').addEventListener('click',()=>setTimeout(summary,0));
function setMode(m){mode=m;$('pk').hidden=m==='qa';$('f').classList.toggle('qa-mode',m==='qa');$('full').classList.toggle('qa-mode',m==='qa');document.querySelector('.qa-only').hidden=m!=='qa';$('m-write').classList.toggle('on',m==='write');$('m-qa').classList.toggle('on',m==='qa');
 $('m-write').setAttribute('aria-selected',m==='write');setTimeout(summary,0);$('m-qa').setAttribute('aria-selected',m==='qa');$('f-h').textContent=m==='qa'?'Check a proposal':'New proposal';
 $('go').textContent=m==='qa'?'Check it against the brief':'Write proposal';$('go-note').textContent=m==='qa'?'Proposal QA reads your document and checks it against the brief: usually under a minute.':'Writing, a QA check and one revision if needed: usually two to four minutes.';if(S)cost()}
$('m-write').onclick=()=>setMode('write');$('go2').onclick=()=>{if(!$('go').disabled)$('f').requestSubmit($('go'))};new MutationObserver(()=>{$('go2').disabled=$('go').disabled;$('go2').textContent=$('go').textContent}).observe($('go'),{attributes:true,childList:true});$('m-qa').onclick=()=>setMode('qa');
function parseStructure(text){const out=[];let cur=null;const head=/^\s{0,1}(#{1,4}\s+|\d{1,2}(\.\d{1,2})*[.)]\s+|[A-Z][.)]\s+)?(.+)$/;
 for(const raw of text.split(/\r?\n/)){if(!raw.trim())continue;const bullet=/^\s*([-*•▪–]|\(?[a-z]\))\s+/.test(raw)||/^\s{2,}\S/.test(raw);
  if(bullet&&cur){cur.include+=(cur.include?'\n':'')+'- '+raw.replace(/^\s*([-*•▪–]|\(?[a-z]\))\s*/,'').trim();continue}
  const m=raw.match(head);const t=(m?m[3]:raw).replace(/[:\s]+$/,'').trim();if(!t)continue;
  if(t.length>120&&cur){cur.include+=(cur.include?'\n':'')+t;continue}
  cur={title:t.slice(0,120),guidance:'',include:'',keep:false,source:'added'};out.push(cur)}
 return out}
$('struct-go').onclick=()=>{const secs=parseStructure($('structure').value);if(!secs.length){$('ferr').textContent='Paste some headings first: one per line, with any points under them.';$('ferr').hidden=false;return}$('ferr').hidden=true;
 const cur=secEd.value();if(cur.length&&!confirm('Replace the current sections with these '+secs.length+'?\n\nCancel adds them after the current sections instead.'))secEd.add(secs);else secEd.set(secs);$('structure').value=''};
async function fileData(f){if(f.size>15*1024*1024)throw new Error('That file is larger than 15 MB.');return await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=no;r.readAsDataURL(f)})}
$('f').onsubmit=async e=>{e.preventDefault();$('ferr').hidden=true;$('go').disabled=true;
 if(mode==='qa'){try{const f=$('qa-file').files[0];if(!f)throw new Error('Choose your proposal document.');const r=await api('/proposals/qa-only','POST',{title:$('title').value,organisation:$('org').value,brief:$('brief').value,name:f.name,data:await fileData(f),qa_model:$('qm').value});
   history.replaceState(null,'','?p='+r.id);follow(r.id);document.querySelector('main').scrollTop=0}catch(err){$('ferr').textContent=err.message;$('ferr').hidden=false;$('go').disabled=A.paused}return}
 try{const r=await api('/proposals','POST',{structure:$('structure').value,title:$('title').value,organisation:$('org').value,brief:$('brief').value,notes:$('notes').value,use_memory:$('mem').checked,references:[...picked],template:$('tplsel').value,writer_model:$('wm').value,qa_model:$('qm').value,sections:secEd.value(),rate_card:rateEd.value()});
  history.replaceState(null,'','?p='+r.id);document.querySelectorAll('details.fold').forEach(d=>d.open=false);follow(r.id);document.querySelector('main').scrollTop=0}
 catch(err){$('ferr').textContent=err.message;$('ferr').hidden=false;$('go').disabled=A.paused}};
function follow(pid){clearInterval(timer);$('result').replaceChildren();$('prog').hidden=false;$('perr').hidden=true;$('prog-title').textContent='Working on it';drawSteps('Gathering','running');
 const tick=async()=>{let p;try{p=await api('/proposals/'+pid)}catch(err){clearInterval(timer);$('perr').textContent=err.message;$('perr').hidden=false;return}
  drawSteps(p.stage,p.status,p.qa);
  if(p.status==='running')return;clearInterval(timer);$('go').disabled=A.paused;
  if(p.status==='failed'){$('prog-title').textContent='This proposal could not be finished';$('perr').textContent=p.error;$('perr').hidden=false;recent();return}
  $('prog').hidden=true;show(p);recent()};
 tick();timer=setInterval(tick,1500)}
function table(head,rows,cls){const t=mk('table','','t');const h=document.createElement('tr');for(const x of head)h.append(mk('th',x));t.append(h);for(const r of rows){const tr=document.createElement('tr');if(r.cls)tr.className=r.cls;for(const c of r.cells){const td=document.createElement('td');if(c&&c.node)td.append(c.node);else td.textContent=c??'';if(c&&c.num)td.className='num';tr.append(td)}t.append(tr)}return t}
const n=(v,num)=>({node:mk('span',v),num});
function show(p){const box=$('result');box.replaceChildren();const qa=p.qa[p.qa.length-1]||{};
 const top=mk('section','','card');const v=mk('div','','verdict '+(qa.verdict==='client_ready'?'ok':(qa.issues||[]).some(i=>i.severity==='high')?'bad':'warn'));
 const sc=mk('span',qa.score!=null?String(qa.score):'—','score');sc.style.setProperty('--p',qa.score||0);sc.title=qa.score!=null?qa.score+' out of 100':'';v.append(sc);const vt=mk('div');vt.append(mk('strong',qa.verdict==='client_ready'?'Client ready, according to Proposal QA':'Needs your attention before it goes to the client'),mk('div',qa.summary||'','hint'));v.append(vt);
 if(p.document_id){const dl=document.createElement('a');dl.href='/documents/'+p.document_id+'/download';dl.className='dl';dl.textContent='Download Word document';v.append(dl)}top.append(mk('h2',p.title+(p.organisation?' · '+p.organisation:'')),v);
 if(p.qa.length>1){const rr=mk('div','','rounds');rr.append(mk('span','QA checks:'));p.qa.forEach((q,i)=>{if(i)rr.append(mk('span','→'));const b=mk('b',(q.score??'?')+'/100');b.title=(q.source||'check '+(i+1));rr.append(mk('span',(q.source||('check '+(i+1)))+' '),b)});top.append(rr)}
 if(p.error)top.append(mk('p','The last re-check did not finish: '+p.error,'err'));
 const act=mk('div','','act');
 if(!p.inputs.qa_only&&(p.draft.sections||[]).length){const eb=document.createElement('button');eb.type='button';eb.className='secondary';eb.textContent='Edit the draft and check again';eb.onclick=()=>editDraft(p);act.append(eb)}
 const ul_=mk('label','Upload a revised version for QA','btnlike');const fi=document.createElement('input');fi.type='file';fi.accept='.docx,.pdf,.txt,.md';fi.hidden=true;ul_.append(fi);
 fi.onchange=async()=>{const f=fi.files[0];fi.value='';if(!f)return;try{await api('/proposals/'+p.id+'/qa-upload','POST',{name:f.name,data:await fileData(f)});follow(p.id)}catch(e){alertBox(e.message)}};act.append(ul_);
 act.append(mk('span',p.inputs.qa_only?'Changed it? Upload the new version and QA checks it again.':'Edited it in Word? Upload it and QA checks your version against the brief (it is not kept).','hint'));top.append(act);
 const mn=k=>(S&&S.models.find(m=>m.key===k)||{}).name||k;if(p.inputs&&p.inputs.writer)top.append(mk('p','Written by '+mn(p.inputs.writer)+'; checked by '+mn(p.inputs.qa)+'.','hint'));
 top.append(mk('p','Read it before it goes anywhere: QA is a second pair of eyes, not a sign-off.','hint'));box.append(top);
 if(p.inputs.qa_only&&p.inputs.file)top.insertBefore(mk('p','Checked: '+p.inputs.file,'hint'),top.children[2]||null);
 const cols=mk('div','','cols');
 const rq=mk('section','','card');rq.append(mk('h2','Meets the brief?'));if((qa.requirements||[]).length)rq.append(table(['Requirement','','Where'],qa.requirements.map(r=>({cells:[r.requirement+(r.note?' — '+r.note:''),{node:mk('span',{met:'Met',partly:'Partly',missing:'Missing'}[r.status],'st '+r.status)},r.where||'']}))));else rq.append(mk('p','QA listed no requirements.','hint'));
 const is=mk('section','','card');is.append(mk('h2','Issues to look at'));const ul=mk('ul','','issues');for(const i of qa.issues||[]){const li=mk('li','',i.severity);const h=mk('div');h.append(mk('span',i.severity,'st '+i.severity),document.createTextNode(' '+(i.section?i.section+': ':'')+i.issue));li.append(h);if(i.fix)li.append(mk('span','Fix: '+i.fix,'hint'));ul.append(li)}
 if(!(qa.issues||[]).length)ul.append(mk('li','None.'));is.append(ul);if((qa.strengths||[]).length)is.append(mk('p','Strengths: '+qa.strengths.join('; '),'hint'));
 cols.append(rq,is);box.append(cols);
 const pr=p.pricing||{};if((pr.lines||[]).length){const c=mk('section','','card internal');c.append(mk('h2','Commercials'));
  c.append(table(['Role','Quantity','Sell rate','Sell','Cost','Margin'],pr.lines.map(l=>({cells:[l.role,n(l.quantity+' '+l.unit+(l.quantity===1?'':'s'),1),n(PE.gbp(l.sell_rate),1),n(PE.gbp(l.sell),1),n(PE.gbp(l.cost),1),n(l.margin==null?'—':l.margin.toFixed(1)+'%',1)]})).concat([{cls:'tot',cells:['Total','','',n(PE.gbp(pr.sell),1),n(PE.gbp(pr.cost),1),n(pr.margin==null?'—':pr.margin.toFixed(1)+'%',1)]}])));
  for(const w of pr.warnings||[])c.append(mk('p','⚠ '+w,'warnline'));box.append(c)}
 const d=p.draft||{};const more=mk('section','','card');
 if((d.gaps||[]).length){more.append(mk('h2','Gaps the writer could not fill'));const g=mk('ul');for(const x of d.gaps)g.append(mk('li',x));more.append(g)}
 if((d.dropped_roles||[]).length)more.append(mk('p','Roles the writer wanted that are not on the rate card (left out): '+d.dropped_roles.join(', '),'hint'));
 const u=(p.context||{}).used||{};if(!p.inputs.qa_only){more.append(mk('h2','What Alice used'));const ul2=mk('ul');
 ul2.append(mk('li',u.organisation?'Organisation profile: '+u.organisation:'No organisation profile.'));ul2.append(mk('li',(u.memories||[]).length?'Memories: '+u.memories.join('; '):'No memories.'));ul2.append(mk('li',(u.knowledge||[]).length?'Knowledge: '+u.knowledge.join('; '):'No knowledge.'));
 if((u.references||[]).length)ul2.append(mk('li','Reference documents: '+u.references.join('; ')));for(const x of u.references_skipped||[])ul2.append(mk('li','Reference left out: '+x));
 if((p.context||{}).skipped)ul2.append(mk('li',p.context.skipped+' item(s) left out by the rules.'));more.append(ul2)}
 const dr=document.createElement('details');dr.className='fold draft';dr.append(mk('summary','Read the draft here'));for(const s of d.sections||[]){dr.append(mk('h3',s.title),mk('div',s.keep?'(standard text from the template)':s.body,'body'))}more.append(dr);box.append(more)}

// ---------- Parker: work on the form in conversation ----------
const PK={history:[],doc:null,busy:false};
function snap(){const tt=window.tplOf?window.tplOf():new Set();return {f:['title','org','brief','notes','structure'].map(id=>[id,$(id).value]),tpl:$('tplsel').value,secs:secEd.value().map(x=>({...x,source:tt.has(x.title)?'template':'added'})),refs:[...picked],rates:rateEd.value(),mem:$('mem').checked}}
async function restore(u){for(const[id,v]of u.f){$(id).value=v;$(id).classList.remove('tfill');$(id).dispatchEvent(new Event('input',{bubbles:true}))}
 if($('tplsel').value!==u.tpl){$('tplsel').value=u.tpl;await $('tplsel').onchange()}secEd.set(u.secs);picked.clear();u.refs.forEach(x=>picked.add(x));drawRefs();rateEd.set(u.rates);$('mem').checked=u.mem;clearTags();summary()}
['title','org','brief','notes','structure'].forEach(id=>$(id).addEventListener('keydown',()=>$(id).classList.remove('tfill')));
function clearTags(){document.querySelectorAll('.pk-tag').forEach(x=>x.remove())}
function reveal(node){const p=node.closest('.panel');if(!p)return;if(p.tagName==='DETAILS')p.open=true;else p.classList.remove('shut');
 const head=p.tagName==='DETAILS'?p.querySelector('summary>span'):p.querySelector('.ph h2,.ph .pt');if(head&&!head.querySelector('.pk-tag'))head.append(mk('span','Updated by Parker','pk-tag'));
 p.classList.remove('pk-hit');void p.offsetWidth;p.classList.add('pk-hit')}
function fill(id,v){if(!v)return false;const e=$(id);e.value=v;e.classList.add('tfill');e.dispatchEvent(new Event('input',{bubbles:true}));reveal(e);return true}
const WHERE={title:'title',client:'org',brief:'brief',notes:'notes',template:'tplsel',structure:'structure',references:'ref-list',roles:'rates'};
async function applyParker(u){clearTags();
 fill('title',u.title);fill('org',u.organisation);fill('brief',u.brief);fill('notes',u.notes);
 if(u.template&&u.template!==$('tplsel').value){$('tplsel').value=u.template;await $('tplsel').onchange();reveal($('tplsel'))}
 if(u.structure)fill('structure',u.structure.map(x=>x.heading+(x.points.length?'\n'+x.points.map(p=>'- '+p).join('\n'):'')).join('\n'));
 if(u.references){picked.clear();u.references.forEach(x=>picked.add(x));drawRefs();reveal($('ref-list'))}
 if(u.roles){rateEd.merge(u.roles);reveal($('rates'))}
 summary()}
function form(){return {title:$('title').value,organisation:$('org').value,brief:$('brief').value,notes:$('notes').value,template:$('tplsel').value,structure:$('structure').value,
 references:[...picked],sections:secEd?secEd.value().map(x=>x.title):[],roles:rateEd?rateEd.value().map(r=>({role:r.role,unit:r.unit,use:r.use,days:r.days})):[]}}
function pkScroll(){const l=$('pk-log');l.scrollTop=l.scrollHeight}
function pkSay(cls,text){const m=mk('div',text,'pk-m '+cls);$('pk-log').append(m);pkScroll();return m}
function pkIntro(){$('pk-log').replaceChildren();const m=pkSay('pk-p',A.paused?A.name+' is paused at the moment.':'Hi, I’m Parker. Tell me about the proposal in a sentence or two, or add the client’s brief or RFP with +. I’ll fill in the form with you and ask for anything that’s missing.');
 if(A.paused)return;const st=mk('div','','pk-starts');for(const [t,fn] of [['Add the client’s brief',()=>$('pk-file').click()],['What’s still missing?',()=>pkSend('What is still missing from the form?')],['Tighten the brief',()=>pkSend('Tighten the brief: clear headings, nothing invented.')]]){const b=mk('button',t);b.type='button';b.onclick=fn;st.append(b)}m.append(st)}
function pkDocs(){const b=$('pk-docs');b.replaceChildren();if(!PK.doc)return;const c=mk('span','📄 '+PK.doc.name,'pk-doc');const x=mk('button','×');x.type='button';x.setAttribute('aria-label','Stop using '+PK.doc.name);x.onclick=()=>{PK.doc=null;pkDocs()};c.append(x);b.append(c)}
function pkGrow(){const t=$('pk-msg');t.style.height='auto';t.style.height=Math.max(76,Math.min(t.scrollHeight,300))+'px'}
function pkWide(on){document.querySelector('.layout').classList.toggle('pk-wide',on);$('pk-wide').textContent=on?'Narrower':'Wider';$('pk-wide').setAttribute('aria-pressed',on);try{localStorage.setItem('alice.parker.wide',on?'1':'')}catch{}}
$('pk-wide').onclick=()=>pkWide(!document.querySelector('.layout').classList.contains('pk-wide'));try{if(localStorage.getItem('alice.parker.wide'))pkWide(true)}catch{}
async function pkSend(text){if(PK.busy||A.paused)return;text=(text||'').trim();if(!text&&!PK.doc)return;PK.busy=true;$('pk-send').disabled=true;$('pk-title').textContent='Parker';
 if(text)pkSay('you',text);const ty=mk('div','','pk-typing');ty.append(mk('i'),mk('i'),mk('i'));$('pk-log').append(ty);pkScroll();
 try{const before=snap();const r=await api('/parker','POST',{message:text,history:PK.history,form:form(),organisation:$('org').value,doc_token:PK.doc?PK.doc.token:''});ty.remove();
  await applyParker(r.updates);const m=pkSay('pk-p',r.reply);
  if(r.changed.length){const ch=mk('div','','pk-ch');for(const c of r.changed){const t=mk('span',c);t.title='Show '+c;t.onclick=()=>{const e=$(WHERE[c]);if(e){reveal(e);e.scrollIntoView({behavior:'smooth',block:'center'})}};ch.append(t)}m.append(ch);
   const un=mk('button','Undo these changes','pk-undo');un.type='button';un.onclick=async()=>{await restore(before);un.replaceWith(mk('span','Undone.','hint'))};m.append(un)}
  if(r.questions.length>1){const ul=mk('ul','','pk-q');for(const q of r.questions.slice(1)){const li=mk('li',q);li.title='Answer this';li.onclick=()=>{$('pk-msg').value=q.replace(/\?$/,'')+': ';$('pk-msg').focus();pkGrow()};ul.append(li)}m.append(ul)}
  pkScroll();
  PK.history.push({role:'you',text:text||'(added '+(PK.doc?PK.doc.name:'a document')+')'},{role:'parker',text:r.reply});PK.history=PK.history.slice(-12)}
 catch(e){ty.remove();pkSay('pk-p err',e.message)}
 finally{PK.busy=false;$('pk-send').disabled=A.paused;$('pk-msg').focus()}}
$('pk-send').onclick=()=>{const t=$('pk-msg').value;$('pk-msg').value='';pkGrow();pkSend(t)};
$('pk-msg').addEventListener('input',pkGrow);
$('pk-msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('pk-send').click()}});
$('pk-new').onclick=()=>{PK.history=[];PK.doc=null;pkDocs();clearTags();pkIntro()};
document.querySelector('.pk-att').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('pk-file').click()}};
$('pk-file').onchange=async()=>{const f=$('pk-file').files[0];$('pk-file').value='';if(!f)return;
 try{const d=await api('/parker/document','POST',{name:f.name,data:await fileData(f)});PK.doc=d;pkDocs();pkSend($('pk-msg').value.trim()||'')}catch(e){pkSay('pk-p err',e.message)}};
if(A.paused){$('pk-send').disabled=true;$('pk-msg').disabled=true}
pkIntro();
// ---------- collapsible sections ----------
document.querySelectorAll('section.panel>.ph').forEach(h=>h.addEventListener('click',e=>{if(e.target.closest('button,input,select,a,label,textarea'))return;h.parentElement.classList.toggle('shut')}));
$('exp-all').onclick=()=>{document.querySelectorAll('main section.panel').forEach(p=>p.classList.remove('shut'));document.querySelectorAll('main details.panel').forEach(d=>d.open=true)};
$('col-all').onclick=()=>{document.querySelectorAll('main section.panel').forEach(p=>p.classList.add('shut'));document.querySelectorAll('main details.panel').forEach(d=>d.open=false)};
function alertBox(msg){const e=mk('div',msg,'err');$('result').prepend(e);setTimeout(()=>e.remove(),8000)}
function editDraft(p){const box=$('result');const c=mk('section','','card');c.append(mk('h2','Edit the draft'),mk('p','Change any section, then send it back: Proposal QA checks your version against the brief and the Word document is rebuilt from the template. The headings stay as they are.','hint'));
 const eds=[];for(const s of p.draft.sections||[]){const w=mk('div','','edit-sec');w.append(mk('b',s.title));if(s.keep){w.append(mk('span','(standard text from the template: not edited here)','hint'))}else{const t=document.createElement('textarea');t.value=s.body;t.maxLength=20000;t.setAttribute('aria-label','Text of '+s.title);w.append(t);eds.push([s,t])}c.append(w)}
 const go=document.createElement('button');go.type='button';go.className='primary';go.textContent='Save changes and check again';const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';cancel.textContent='Cancel';cancel.onclick=()=>show(p);
 go.onclick=async()=>{go.disabled=true;try{await api('/proposals/'+p.id+'/recheck','POST',{sections:(p.draft.sections||[]).map(s=>{const e=eds.find(x=>x[0]===s);return {title:s.title,body:e?e[1].value:''}})});follow(p.id)}catch(e){go.disabled=false;alertBox(e.message)}};
 const a=mk('div','','act');a.append(go,cancel);c.append(a);box.replaceChildren(c);document.querySelector('main').scrollTop=0}
async function recent(){try{const d=await api('/proposals');$('recent-box').hidden=!d.proposals.length;$('recent').replaceChildren(...d.proposals.map(x=>{const b=mk('button','','secondary '+(x.status==='running'?'run':x.status==='failed'?'bad':x.verdict==='client_ready'?'ok':'warn'));b.type='button';
 b.append(mk('span',x.title+(x.organisation?' · '+x.organisation:'')),mk('span',x.status==='running'?'writing…':x.status==='failed'?'failed':(x.verdict==='client_ready'?'client ready':'needs attention')+(x.score!=null?' · '+x.score+'/100':'')+' · '+new Date(x.created_at).toLocaleDateString('en-GB'),'hint'));
 b.onclick=()=>{history.replaceState(null,'','?p='+x.id);follow(x.id);window.scrollTo(0,0);document.querySelector('main').scrollTop=0};return b}))}catch{}}
load().catch(e=>{$('ferr').textContent=e.message;$('ferr').hidden=false});
</script></body></html>''')
