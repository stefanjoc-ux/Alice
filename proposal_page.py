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
    from ui_theme import SHARED_CSS, FETCH_JS, FETCH_CSS
    from proposal_ui import PE_CSS, PE_JS
    data = json.dumps({'id': a['id'], 'name': a['name'], 'greeting': a['greeting'], 'paused': a['status'] != 'active'})
    return ('''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + escape(a['name']) + '''</title>''' + __import__('stage_ui').EMBED_HEAD + '''<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,''' + quote(parker_logo(48, 'fv')) + '''">
<style>''' + FETCH_CSS + SHARED_CSS + PE_CSS + '''
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
.internal{border:2px dashed #c7b8dd;background:#faf7fd}.internal h2::after{content:' \\00b7 internal: costs and margins never go in the document; Parker sees them, the writer and Argus do not';font-size:12px;font-weight:400;color:#634394}
.warnline{color:#7a1f1f;font-weight:600;margin:6px 0 0}
.issues{display:grid;gap:8px;margin:0;padding:0;list-style:none}.issues li{display:grid;gap:2px;border-left:3px solid #c1cbd3;padding-left:10px}.issues li.high{border-color:#b3261e}.issues li.medium{border-color:#e2a33b}
.draft h3{margin:16px 0 4px;font-size:15px}.draft .body{white-space:pre-wrap;font-size:14px;line-height:1.55}
.recent{display:grid;gap:6px}.recent button{text-align:left;display:flex;justify-content:space-between;gap:12px;width:100%}
.err{background:#fbeaea;border:1px solid #e0aaaa;border-radius:10px;padding:10px 12px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
[hidden]{display:none!important}.qa-mode .w-only{display:none!important}
.mode{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.mode h2{margin:0}.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid var(--line2,#b9cbd8);background:#fff;border-radius:999px;padding:6px 14px;font-weight:600;font-size:13.5px;cursor:pointer;color:var(--ink)}.mode .chip.on{background:var(--teal)!important;border-color:var(--teal)!important;color:#fff!important}.mode .chip:not(.on){background:#fff!important;color:var(--ink)!important}
.qa-simple h2{margin-bottom:2px}.qa-cov{margin:0 0 10px;color:var(--muted);font-size:14px}.qa-cov strong{color:var(--ink)}
.qa-line{font-size:14.5px;line-height:1.45}.qa-where{font-size:12px;color:var(--muted)}.qa-fix{font-size:13.5px;color:#234;background:#f4f8fa;border-radius:8px;padding:6px 10px;margin-top:3px}
.issues li.brief{border-color:#7a5bb0}.st.brief{background:#f1ecfa;color:#4a2f7a;border-color:#c7b8dd}.issues li.none{border:0;padding:0;color:var(--muted)}
.qa-minor,.qa-ok{margin-top:10px}.qa-met{margin:6px 0 0;padding-left:4px;list-style:none;display:grid;gap:4px;font-size:13.5px;color:#2d4a3a}
.retpl{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}.retpl label{display:flex;gap:8px;align-items:center;margin:0}.retpl select{width:auto;min-width:240px;max-width:100%}
.pk-model{border-left:3px solid #7a5bb0}.pk-model strong{display:block;margin-bottom:4px}.pk-mnote{white-space:pre-wrap}.pk-mbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}
.rounds{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:13px;color:var(--muted);margin:4px 0}.rounds b{color:var(--ink)}
.act{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:6px}.act label.btnlike{cursor:pointer;border:1px solid var(--line2,#b9cbd8);border-radius:8px;padding:8px 14px;font-weight:600;font-size:14px;background:#fff}
.edit-sec{display:grid;gap:4px;margin:12px 0}.edit-sec textarea{min-height:140px;font-size:14px;line-height:1.5}
.ref-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.ref-tools input{flex:1;min-width:200px}
.ref-upl{cursor:pointer;border:1px solid var(--line2,#b9cbd8);border-radius:8px;padding:8px 14px;font-weight:600;font-size:14px;background:#fff}.ref-upl:hover{border-color:var(--teal)}
.tpl-tools{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-top:-4px}.tpl-fold{display:grid;gap:4px;font-weight:600;font-size:13px;flex:1;min-width:220px}.tpl-tools .ref-upl,.tpl-tools button{white-space:nowrap}
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
.workbar{position:relative;display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:var(--panel);border:1px solid #dce6ee;border-radius:14px;padding:10px 12px 10px 16px;box-shadow:0 1px 2px rgba(16,42,67,.04)}
.wb-cur{display:flex;gap:10px;align-items:baseline;min-width:0;flex:1 1 300px}.wb-k{font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700;flex:none}
.wb-ref{font-size:12px;font-weight:700;color:#4b5a66;background:#eef3f7;border-radius:6px;padding:1px 7px;font-variant-numeric:tabular-nums;white-space:nowrap;flex:none}.wb-ref[hidden]{display:none}
.wb-cur b{font-size:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.wb-state{font-size:12.5px;color:var(--muted);white-space:nowrap}.wb-state.bad{color:#b3261e;font-weight:600;white-space:normal}.wb-state.ok::before{content:'\2713  ';color:#2f9e6e}
.wb-acts{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.wb-n{display:inline-block;min-width:18px;padding:0 6px;border-radius:999px;background:#eef3f7;font-size:12px;margin-left:2px}
.wb-pop{position:absolute;z-index:30;right:10px;top:calc(100% + 6px);width:min(560px,94vw);max-height:min(70vh,560px);overflow:auto;background:var(--panel);border:1px solid #cddbe5;border-radius:14px;box-shadow:0 18px 40px -16px rgba(16,42,67,.45);padding:12px;display:grid;gap:10px}
.wb-pop input{width:100%}.wb-g{font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700;margin:6px 2px 2px}
.wb-it{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:8px 10px;cursor:pointer;background:#fff}
.wb-it:hover{border-color:var(--teal)}.wb-it.on{border-color:var(--teal);box-shadow:0 0 0 2px rgba(7,94,121,.12)}
.wb-it b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.wb-it .hint{display:block}
.wb-pill{font-size:11.5px;font-weight:700;border-radius:999px;padding:2px 9px;white-space:nowrap;background:#eef3f7;color:#4b5a66}
.wb-sug{font-size:11.5px;font-weight:700;border-radius:999px;padding:2px 9px;white-space:nowrap;background:#fdf3e1;color:#6b4406}.wb-n.sug{background:#f07f1b;color:#fff}
.pk-open{margin-top:8px}
.wb-ver{font:600 12px inherit;border:1px solid var(--line);background:#fff;color:#33424e;border-radius:999px;padding:2px 10px;cursor:pointer;white-space:nowrap}.wb-ver:hover{border-color:#9fb3c2}
.wb-h{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;padding:8px 4px;border-top:1px solid var(--line);font-size:13px}.wb-h:first-of-type{border-top:0}.wb-h b{font-variant-numeric:tabular-nums}.wb-h .hint{grid-column:2}
.wb-via{font-size:11.5px;font-weight:700;border-radius:999px;padding:1px 8px;background:#eef3f7;color:#33424e;margin-left:6px}.wb-via.model{background:#e9e4f7;color:#3e2a73}
.wb-pill.form{background:#f1ebf7;color:#4b2f73}.wb-pill.run{background:#e3f1f6;color:#064b63}.wb-pill.ok{background:#eef8f1;color:#1e5b31}.wb-pill.warn{background:#fdf3e1;color:#6b4406}.wb-pill.bad{background:#fbeaea;color:#7a1f1f}
.wb-x{border:0!important;background:none!important;color:var(--muted)!important;font-size:16px;padding:0 4px!important}.wb-x:hover{color:#b3261e!important}
.fixch{display:flex;gap:6px;margin-top:4px}.fixch button{font-size:12px;padding:3px 10px;border-radius:999px}.fixch .fx-y.on{background:#eef8f1!important;border-color:#55b987!important;color:#1e5b31!important;font-weight:700}
.fixch .fx-n.on{background:#fbeaea!important;border-color:#e0aaaa!important;color:#7a1f1f!important;font-weight:700}.issues li.rej>div:first-child,.issues li.rej>.hint{opacity:.5;text-decoration:line-through}
.fixwhy{width:100%;margin-top:6px;font-size:13px;border-radius:10px;border:1px solid #cddbe5;padding:7px 10px;background:#fbfdfe;resize:vertical}.issues li.rej .fixwhy{opacity:1;text-decoration:none}
.pdiff{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px}.pdiff .hint{flex:1;min-width:240px}.pdiff ul{margin:0 0 4px;padding-left:20px;width:100%;font-size:14px}
.pdiff.on{background:#fdf7ea;border:1px solid #ecd6a8;border-radius:12px;padding:10px 14px}.pd-h{margin:0;font-weight:700;width:100%;color:#6b4406}
.fixbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}.wb-cost{font-size:11.5px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
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
/* bids and versions */
.wb-org{font-size:12.5px;font-weight:700;color:#33424e;margin:4px 2px 0;padding-left:2px;border-left:3px solid #cddbe5;padding-left:8px}
.wb-old{margin:-4px 0 2px 18px}.wb-old>summary{cursor:pointer;font-size:12.5px;color:var(--teal);font-weight:600;padding:2px 0;list-style-position:inside}
.wb-old .wb-it{background:#f8fafb;border-style:dashed;margin-top:6px}.wb-pill.old{background:#eceff2;color:#55636e}
.wb-rp label{display:flex;gap:8px;align-items:flex-start;border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:#fff;cursor:pointer;font-size:14px}
.wb-rp label input{margin-top:3px;width:auto!important;flex:none}.wb-rp label>span{flex:1;min-width:0}.wb-rp .hint{display:block}
.supd{border-left:4px solid #8a99a6;background:#f6f8fa}.supd h2{margin-bottom:4px}
.pk-carried{border-left:3px dashed #b07d2b;background:#fffaf0}.pk-from{display:inline-block;font-size:11.5px;font-weight:700;color:#6b4406;background:#fdf3e1;border:1px solid #ecd6a8;border-radius:999px;padding:1px 8px;margin-bottom:6px}
.pk-gone{margin:8px 0 0;padding:8px 10px;border-radius:8px;background:#fbeeee;border:1px solid #ecc8c8;font-size:13px}.pk-gone b{display:block;color:#7a1f1f;margin-bottom:2px}.pk-gone ul{margin:0;padding-left:18px}
</style></head><body>
<header class="topbar"><span class="brand">''' + parker_logo(26, 'tb') + '''<span class="who">''' + escape(a['name']) + '''</span></span><div class="sp"></div><span class="small" style="color:#9fb8ca">Built on Alice</span></header>
<main><div class="wrap"><div class="layout"><div class="colmain">
<div class="workbar" id="workbar"><div class="wb-cur"><span class="wb-k">Working on</span><b id="wb-title">New proposal</b><span id="wb-ref" class="wb-ref" hidden></span><span id="wb-state" class="wb-state"></span><button type="button" id="wb-ver" class="wb-ver" hidden aria-expanded="false" aria-controls="wb-hist" title="Versions: when it changed, who by and from where"></button></div>
<div class="wb-acts"><button type="button" class="secondary" id="wb-keep" hidden title="Keep the changes you have made to this written proposal as a new proposal in progress">Save as a new version</button><button type="button" class="secondary" id="wb-repl" hidden aria-expanded="false" aria-controls="wb-rp" title="Pick older proposals that this one replaces: they become its earlier versions">Make this replace…</button><button type="button" class="secondary" id="wb-list" aria-expanded="false" aria-controls="wb-pop">Proposals <span id="wb-n" class="wb-n"></span> ▾</button><button type="button" class="primary" id="wb-new">+ New proposal</button></div>
<div class="wb-pop" id="wb-hist" hidden role="region" aria-label="Versions"></div><div class="wb-pop wb-rp" id="wb-rp" hidden role="region" aria-label="Make this replace other proposals"></div><div class="wb-pop" id="wb-pop" hidden><input type="search" id="wb-q" placeholder="Find a proposal by title, client or reference (P-…)" aria-label="Find a proposal"><div id="wb-items"></div></div></div>
<section class="hero"><div class="hero-in"><div><div class="ptitle">''' + parker_logo(58, 'hr') + '''<div><p class="eyebrow">Proposal writer \u00b7 bid and proposal studio</p><h1>''' + escape(a['name']) + '''</h1></div></div><p class="lead" id="greeting"></p></div>
<ol class="flow" aria-label="How it works"><li>Brief</li><li>Draft</li><li>Argus checks</li><li>Word document</li></ol></div></section>
<section class="card" id="prog" hidden aria-live="polite"><h2 id="prog-title">Working on it</h2><ol class="steps" id="steps"></ol><div class="err" id="perr" hidden></div></section>
<div id="result"></div>
<form id="f">
<div class="formbar"><span>Proposal form</span><button type="button" id="exp-all">Expand all</button><button type="button" id="col-all">Collapse all</button></div>
<section class="panel"><div class="ph"><div class="mode"><div><h2 id="f-h">New proposal</h2><span class="ps">The brief, and who it is for</span></div><div class="chips" role="tablist" aria-label="What to do"><button type="button" class="chip on" id="m-write" role="tab" aria-selected="true">Write a proposal</button><button type="button" class="chip" id="m-qa" role="tab" aria-selected="false">Check one I already have</button></div></div></div>
<div class="grid2"><label>Proposal title<input id="title" maxlength="150" required placeholder="e.g. Data security baseline for Microsoft Fabric"></label>
<label>Client or organisation<input id="org" maxlength="80" list="orgs" placeholder="Start typing a name"><datalist id="orgs"></datalist><span class="hint" id="org-hint">Its approved profile is used. Only this client's tagged material is used, never another client's.</span></label></div>
<label>Brief and context<textarea id="brief" maxlength="20000" required placeholder="Paste the brief or describe what the client wants: outcomes, scope, requirements, timescales, evaluation criteria, anything they said."></textarea>
<span class="hint">Everything in the brief is checked before it goes to the AI: secrets and protective markings are refused.</span></label>
<div class="qa-only" hidden><label>Your proposal document<input type="file" id="qa-file" accept=".docx,.pdf,.txt,.md"><span class="hint">Word, PDF or text. Argus checks it against the brief above. Your document is read for the check and not kept.</span></label></div>
<label class="w-only">Notes for the writer <span class="hint">(optional: angle to take, things to stress or avoid)</span><textarea id="notes" maxlength="4000" rows="3" placeholder="e.g. Lead with value for money; they were burned by a big-bang migration before."></textarea></label>
</section>
<section class="panel"><div class="ph"><div><span class="pt">Set-up</span><span class="ps">Template, models and what Alice may draw on</span></div></div>
<label class="w-only">Proposal template<select id="tplsel"></select><span class="hint" id="tpl-hint"></span></label>
<div class="tpl-tools w-only"><label class="tpl-fold">Templates folder<select id="tplfold" aria-label="Templates folder"></select></label><label class="ref-upl" tabindex="0" role="button" id="tpl-upl">Add a template<input type="file" id="tpl-file" accept=".docx" hidden></label><button type="button" class="secondary" id="tpl-refresh" title="Look in the folder again">Refresh</button></div>
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
<p class="pk-foot"><b>Working with Parker:</b> it fills in the form as you talk and asks for what’s missing. Its changes are outlined, and you can undo any of them. The proposal and this conversation save themselves, so you can carry on from another device.</p></div></section>
<details class="sumbar sum" id="sum-box"><summary><b>This proposal</b><span id="sum-line"></span></summary><dl id="sum"></dl><div class="big" id="sum-big"></div><p class="safe">Cost rates and protectively marked material never reach the AI. Every piece of context is checked on the way out.</p></details><button type="button" class="primary go2" id="go2" style="flex:none">Write proposal</button>
</aside></div>
<div class="full" id="full">
<details class="fold panel w-only"><summary><span>Rate card<span class="psub">Roles, days, cost and sell rates, margin</span></span></summary><div class="pbody">
<p class="pe-note">Load your pricing tool or paste a rate card, set the target margin Alice applies to each cost, and tick the roles this proposal needs. Change any sell rate or margin to override it (\u21ba puts it back); Price book keeps the rate from your pricing tool and Change shows the difference, so you can see what applying the target margin does. Add days to fix a role's quantity; the writer suggests the rest. Cost rates never go in the document or to the writer and Argus; Parker can see them, to help you with the commercials.</p><div id="rates"></div></div></details>
<div class="actionbar"><button class="primary" id="go" type="submit" form="f">Write proposal</button><span class="hint" id="go-note">Writing, a QA check and one revision if needed: usually two to four minutes.</span></div>
</div></div></main>
<script>''' + FETCH_JS + '''
const A=''' + data.replace('</', '<\\/') + ''';
''' + PE_JS + r'''
const $=id=>document.getElementById(id),mk=PE.mk;let S=null,secEd=null,rateEd=null,timer=null;
const base='/assistant/'+encodeURIComponent(A.id);
async function api(path,method,body){const r=await fetch(base+path,{method:method||'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:(Array.isArray(d.detail)?d.detail.map(x=>x.msg).join('; '):'Something went wrong. Try again.'));return d}
const STEPS=[['Gathering','Gathering what Alice knows and writing the draft'],['checking the draft','Argus checks the draft against the brief'],['Revising','Revising with the QA feedback (only if needed)'],['checking the revision','Argus checks the revision'],['Building','Building the Word document']];
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
 const fillT=(list,want)=>{S.templates=list;const cur=want!=null?want:ts.value;
  ts.replaceChildren(...list.map(x=>topt(x.path,x.name+(S.template_folder?(x.folder!==S.template_folder?' · '+x.folder.split('/').slice(1).join('/'):''):' · '+x.source)+(x.path===S.template?' (default)':''))),topt('','No template: Alice’s own Word layout'));
  if(S.template&&!list.some(x=>x.path===S.template))ts.prepend(topt(S.template,S.template.split('/').pop()+(S.template_error?' (not found)':' (default, outside this folder)')));
  ts.value=[...ts.options].some(o=>o.value===cur)?cur:(S.template||'')};
 fillT(S.templates,S.template||'');
 const tf=$('tplfold');tf.replaceChildren(topt('','Every document source'),...(S.folders||[]).map(f=>topt(f,f.replace(/\//g,' › '))));
 if(S.template_folder&&!(S.folders||[]).includes(S.template_folder))tf.append(topt(S.template_folder,S.template_folder+' (not found)'));tf.value=S.template_folder||'';
 const tplNote=t=>{$('tpl-hint').textContent=t};
 const applyT=(r,want)=>{S.template_folder=r.folder;S.folders=r.folders;fillT(r.templates,want);
  tplNote(r.folder_missing?'The templates folder "'+r.folder+'" is no longer in the document sources. Choose another.':(r.templates.length?r.templates.length+' template'+(r.templates.length===1?'':'s')+' in '+(r.folder?'“'+r.folder.replace(/\//g,' › ')+'”':'the document sources')+'.':'No Word templates in '+(r.folder?'this folder':'the document sources')+' yet: use Add a template.'))};
 tf.onchange=async()=>{try{applyT(await api('/templates/folder','POST',{folder:tf.value}))}catch(e){tplNote(e.message);tf.value=S.template_folder||''}};
 $('tpl-refresh').onclick=async()=>{try{applyT(await api('/templates'))}catch(e){tplNote(e.message)}};
 $('tpl-upl').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('tpl-file').click()}};
 $('tpl-file').onchange=async()=>{const f=$('tpl-file').files[0];$('tpl-file').value='';if(!f)return;
  if(!S.template_folder){tplNote('Choose the templates folder first, then add the template to it.');return}
  tplNote('Adding '+f.name+'…');try{const r=await api('/templates','POST',{name:f.name,data:await fileData(f)});applyT(r,r.added);await ts.onchange();tplNote(f.name+' added to “'+r.folder.replace(/\//g,' › ')+'” and chosen for this proposal.')}catch(e){tplNote(e.message)}};
 let tplTitles=new Set(S.sections.filter(x=>x.source==='template').map(x=>x.title));window.tplOf=()=>tplTitles;
 const tplHint=(o,err)=>{$('tpl-hint').textContent=err||(ts.value?(o&&o.sections?o.sections.filter(x=>x.source==='template').length+' sections from the template; its cover, styles, header and footer are kept.':'Sections, styles, cover, header and footer come from the template.'):'No template: the proposal uses Alice’s own Word layout with the sections below.')+(S.templates.length?'':' Choose the templates folder below and add a template to it.')};
 tplHint(null,S.template_error);$('tpl').textContent='';
 ts.onchange=async()=>{try{const o=await api('/outline?template='+encodeURIComponent(ts.value));const now=secEd.value();const fresh=new Set(o.sections.map(x=>x.title.toLowerCase()));
   const mine=now.filter(x=>!tplTitles.has(x.title)&&!fresh.has(x.title.toLowerCase())).map(x=>({...x,source:'added'}));
   secEd.set(o.sections.concat(mine));tplTitles=new Set(o.sections.filter(x=>x.source==='template').map(x=>x.title));tplHint(o)}catch(e){tplHint(null,e.message)}};
 if(A.paused)$('go').disabled=true;summary();await recent();const q=new URLSearchParams(location.search).get('p');if(q)await openItem(q);else{setState('Saves itself as you work');updateBar();pkWaiting()}}
$('org').addEventListener('input',()=>drawRefs());
$('org').oninput=()=>{const o=S&&S.organisations.find(x=>x.name.toLowerCase()===$('org').value.trim().toLowerCase());$('org-hint').textContent=o?(o.client?o.name+' is a client: its tagged memories and knowledge are included; other clients’ never are.':'Its approved profile is used.'):($('org').value.trim()?'Not in the list: Alice checks other names it knows (e.g. SBC); if none match, the name is used as typed.':'Its approved profile is used. Only this client’s tagged material is used, never another client’s.')};
let mode='write',CUR=null,EDS=null;
function formEmpty(){return !$('title').value.trim()&&!$('brief').value.trim()}
async function loadIntoForm(p,quiet,noSay){LOADING++;try{await fillIn(p,quiet,noSay)}finally{LOADING--}}
async function fillIn(p,quiet,noSay){const i=p.inputs||{};const before=snap();
 $('title').value=p.title||'';$('org').value=p.organisation||'';$('brief').value=p.brief||'';$('notes').value=p.notes||'';$('structure').value=i.structure||'';
 ['title','org','brief','notes','structure'].forEach(id=>$(id).dispatchEvent(new Event('input',{bubbles:true})));
 if(i.template!=null&&i.template!==$('tplsel').value&&[...$('tplsel').options].some(o=>o.value===i.template)){$('tplsel').value=i.template;await $('tplsel').onchange()}
 if((i.sections||[]).length){const tt=window.tplOf?window.tplOf():new Set();secEd.set(i.sections.map(x=>({...x,source:tt.has(x.title)?'template':'added'})))}
 picked.clear();(i.references||[]).forEach(x=>picked.add(x));drawRefs();
 if(i.form)rateEd.set(i.rate_card||[]);else if((i.rate_card||[]).length)rateEd.pick(i.rate_card);
 for(const [id,k] of [['wm','writer'],['qm','qa']])if(i[k]&&[...$(id).options].some(o=>o.value===i[k]))$(id).value=i[k];
 if(i.use_memory!=null)$('mem').checked=!!i.use_memory;if(window.cost)window.cost();summary();updateBar();drawPriceDiff();if(noSay)return;
 pkSay('pk-p','I\u2019ve loaded \u201c'+(p.title||'this proposal')+'\u201d into the form'+((p.draft&&(p.draft.sections||[]).length)?', and I can see the draft as written. Tell me what to change, for example \u201cadd to the approach that the first days are on site\u201d, and I\u2019ll update the draft and the brief.':'.')+(quiet?'':' Undo puts the form back.'));
 if(!quiet){const m=$('pk-log').lastChild;const un=mk('button','Undo','pk-undo');un.type='button';un.onclick=async()=>{await restore(before);un.replaceWith(mk('span','Undone.','hint'))};m.append(un)}}
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
 $('go').textContent=m==='qa'?'Check it against the brief':'Write proposal';$('go-note').textContent=m==='qa'?'Argus reads your document and checks it against the brief: usually under a minute.':'Writing, a QA check and one revision if needed: usually two to four minutes.';if(S)cost()}
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
 try{const r=await api('/proposals','POST',{structure:$('structure').value,title:$('title').value,organisation:$('org').value,brief:$('brief').value,notes:$('notes').value,use_memory:$('mem').checked,references:[...picked],template:$('tplsel').value,writer_model:$('wm').value,qa_model:$('qm').value,sections:secEd.value(),rate_card:rateEd.value(),work_id:WORK||'',started_from:(!WORK&&OPEN)?OPEN:''});
  clearTimeout(saveT);saveT=null;stashChat();if(WORK&&WORK!==r.id)moveChat(WORK,r.id);else if(!WORK)moveChat(OPEN,r.id,!!OPEN);WORK=null;OPEN=r.id;DIRTY=false;setState('');recent();
  history.replaceState(null,'','?p='+r.id);document.querySelectorAll('details.fold').forEach(d=>d.open=false);follow(r.id);document.querySelector('main').scrollTop=0}
 catch(err){$('ferr').textContent=err.message;$('ferr').hidden=false;$('go').disabled=A.paused}};
function follow(pid){clearInterval(timer);$('result').replaceChildren();$('prog').hidden=false;$('perr').hidden=true;$('prog-title').textContent='Working on it';drawSteps('Gathering','running');
 const tick=async()=>{let p;try{p=await api('/proposals/'+pid)}catch(err){clearInterval(timer);$('perr').textContent=err.message;$('perr').hidden=false;return}
  drawSteps(p.stage,p.status,p.qa);
  if(p.status==='running')return;clearInterval(timer);if(p.id===OPEN){HIST=(p.context||{}).history||[];drawVer()}$('go').disabled=A.paused;if(p.status==='form'){$('prog').hidden=true;return}
  if(p.status==='failed'){$('prog-title').textContent='This proposal could not be finished';$('perr').textContent=p.error;$('perr').hidden=false;recent();return}
  $('prog').hidden=true;show(p);if(p.superseded_by)retired(p);recent()};
 tick();timer=setInterval(tick,1500)}
function table(head,rows,cls){const t=mk('table','','t');const h=document.createElement('tr');for(const x of head)h.append(mk('th',x));t.append(h);for(const r of rows){const tr=document.createElement('tr');if(r.cls)tr.className=r.cls;for(const c of r.cells){const td=document.createElement('td');if(c&&c.node)td.append(c.node);else td.textContent=c??'';if(c&&c.num)td.className='num';tr.append(td)}t.append(tr)}return t}
const n=(v,num)=>({node:mk('span',v),num});
function show(p){CUR=p;EDS=null;if(formEmpty()&&!p.inputs.qa_only&&S)setTimeout(()=>loadIntoForm(p,true,!!p.superseded_by),0);const box=$('result');box.replaceChildren();const qa=p.qa[p.qa.length-1]||{};
 const top=mk('section','','card');const v=mk('div','','verdict '+(qa.verdict==='client_ready'?'ok':(qa.issues||[]).some(i=>i.severity==='high')?'bad':'warn'));
 const sc=mk('span',qa.score!=null?String(qa.score):'—','score');sc.style.setProperty('--p',qa.score||0);sc.title=qa.score!=null?qa.score+' out of 100':'';v.append(sc);const vt=mk('div');vt.append(mk('strong',qa.verdict==='client_ready'?'Client ready, according to Argus':'Needs your attention before it goes to the client'),mk('div',qa.summary||'','hint'));v.append(vt);
 if(p.document_id){const dl=document.createElement('a');dl.href='/documents/'+p.document_id+'/download';dl.className='dl';dl.textContent='Download Word document';v.append(dl)}top.append(mk('h2',p.title+(p.organisation?' · '+p.organisation:'')),v);
 if(p.qa.length>1){const rr=mk('div','','rounds');rr.append(mk('span','Argus checks:'));p.qa.forEach((q,i)=>{if(i)rr.append(mk('span','→'));const b=mk('b',(q.score??'?')+'/100');b.title=(q.source||'check '+(i+1));rr.append(mk('span',(q.source||('check '+(i+1)))+' '),b)});top.append(rr)}
 if(p.error)top.append(mk('p','The last re-check did not finish: '+p.error,'err'));
 const act=mk('div','','act');
 if(!p.inputs.qa_only){const lf=document.createElement('button');lf.type='button';lf.className='secondary';lf.textContent='Load into the form';lf.title='Put this proposal\u2019s brief, notes, template, sections, references and roles back into the form, to change it with Parker or write a new version';lf.onclick=()=>loadIntoForm(p,false);act.append(lf)}
 if(!p.inputs.qa_only&&(p.draft.sections||[]).length){const eb=document.createElement('button');eb.type='button';eb.className='secondary';eb.textContent='Edit the draft and check again';eb.onclick=()=>editDraft(p);act.append(eb)}
 const ul_=mk('label','Upload a revised version for QA','btnlike');const fi=document.createElement('input');fi.type='file';fi.accept='.docx,.pdf,.txt,.md';fi.hidden=true;ul_.append(fi);
 fi.onchange=async()=>{const f=fi.files[0];fi.value='';if(!f)return;try{await api('/proposals/'+p.id+'/qa-upload','POST',{name:f.name,data:await fileData(f)});follow(p.id)}catch(e){alertBox(e.message)}};act.append(ul_);
 act.append(mk('span',p.inputs.qa_only?'Changed it? Upload the new version and Argus checks it again.':'Edited it in Word? Upload it and Argus checks your version against the brief (it is not kept).','hint'));top.append(act);
 if(!p.inputs.qa_only&&(p.draft.sections||[]).length&&S){const tr=mk('div','','retpl');const ts2=document.createElement('select');ts2.setAttribute('aria-label','Template');
  const cur=p.inputs.template||'';const opt=(v,t)=>{const o=document.createElement('option');o.value=v;o.textContent=t;return o};
  ts2.append(...(S.templates||[]).map(x=>opt(x.path,x.name)),opt('','Alice’s own Word layout'));if(cur&&![...ts2.options].some(o=>o.value===cur))ts2.prepend(opt(cur,cur.split('/').pop()));ts2.value=cur;
  const mv=mk('button','Move the content to this template','secondary');mv.type='button';mv.disabled=true;ts2.onchange=()=>{mv.disabled=ts2.value===cur||p.status==='running'};
  mv.onclick=async()=>{mv.disabled=true;try{await api('/proposals/'+p.id+'/template','POST',{template:ts2.value});follow(p.id);document.querySelector('main').scrollTop=0}catch(e){mv.disabled=false;alertBox(e.message)}};
  const lb=mk('label','','');lb.append(mk('strong','Template '),ts2);tr.append(lb,mv,mk('span','The content you have is kept: sections with the same name carry over as they are, the rest is moved into the new template’s sections, Argus checks it and the Word document is rebuilt on the new template.','hint'));top.append(tr)}
 const mn=k=>(S&&S.models.find(m=>m.key===k)||{}).name||k;if(p.inputs&&p.inputs.writer)top.append(mk('p','Written by '+mn(p.inputs.writer)+'; checked by Argus ('+mn(p.inputs.qa)+').','hint'));
 const ac=(p.context||{}).ai_cost;if(ac&&ac.total)top.append(mk('p','Alice AI cost for this proposal so far: $'+ac.total.toFixed(2)+(ac.parker?' (writing and Argus $'+(ac.writing||0).toFixed(2)+', Parker $'+ac.parker.toFixed(2)+')':''),'hint'));
 top.append(mk('p','Read it before it goes anywhere: Argus is a second pair of eyes, not a sign-off.','hint'));box.append(top);
 if(p.inputs.qa_only&&p.inputs.file)top.insertBefore(mk('p','Checked: '+p.inputs.file,'hint'),top.children[2]||null);
 const reqs=qa.requirements||[],metR=reqs.filter(r=>r.status==='met');const items=[];
 for(const r of reqs)if(r.status!=='met')items.push({severity:r.status==='missing'?'high':'medium',section:r.where||'',brief:true,
   issue:'The brief asks for '+r.requirement.replace(/^[A-Z](?=[a-z ])/,c=>c.toLowerCase()).replace(/[.\s]+$/,'')+(r.status==='missing'?': not covered.':': only partly covered.'),
   fix:r.note||('Cover it'+(r.where?' in '+r.where:'')+'.')});
 for(const i of qa.issues||[])items.push({...i,brief:false});
 const ORD={high:0,medium:1,low:2},LAB={high:'Must fix',medium:'Should fix',low:'Polish'};items.sort((a,b)=>ORD[a.severity]-ORD[b.severity]);
 const can=!p.inputs.qa_only&&(p.draft.sections||[]).length;const is=mk('section','','card qa-simple');const main=items.filter(i=>i.severity!=='low'),minor=items.filter(i=>i.severity==='low');
 const hd=mk('h2',main.length?'What to fix ('+main.length+')':'Nothing important to fix');is.append(hd);
 const cov=mk('p','','qa-cov');cov.append(mk('strong',reqs.length?metR.length+' of '+reqs.length+' brief requirements met':'Argus listed no brief requirements'));
 if(reqs.length&&metR.length===reqs.length)cov.append(document.createTextNode(' ✓'));is.append(cov);
 const pickF=new Map(),NOTES=new Map();const fbar=mk('div','','fixbar');const fgo=mk('button','','primary');fgo.type='button';const fnote=mk('span','','hint');
 const syncF=()=>{const n=[...pickF.values()].filter(v=>v==='yes').length,r=[...pickF.values()].filter(v=>v==='no').length;fgo.disabled=(!n&&!r)||p.status==='running';fgo.textContent=n?'Revise with '+n+' accepted fix'+(n>1?'es':''):r?'Check again with your decisions':'Accept or reject fixes';fnote.textContent=n?n+' accepted, '+r+' rejected. The writer makes only the accepted changes, Argus checks them and won’t raise the rejected ones again, and the Word document is rebuilt.':r?r+' rejected. Nothing is rewritten: Argus checks again with your reasons and won’t raise these again.':'Accept the changes you want and reject the rest (a note on why helps), then revise.'};
 const row=(i,k)=>{const li=mk('li','',i.severity+(i.brief?' brief':''));const h=mk('div','','qa-line');h.append(mk('span',i.brief?'Brief gap':LAB[i.severity],'st '+(i.brief?'brief':i.severity)));
   h.append(document.createTextNode(' '+i.issue));li.append(h);if(i.section)li.append(mk('span','In: '+i.section,'qa-where'));if(i.fix)li.append(mk('div','Change: '+i.fix,'qa-fix'));
   if(i.fix&&can){const ch=mk('div','','fixch');const y=mk('button','Accept','fx-y'),nn=mk('button','Reject','fx-n');y.type=nn.type='button';
    const why=document.createElement('textarea');why.className='fixwhy';why.rows=2;why.maxLength=600;why.hidden=true;why.setAttribute('aria-label','Why, for '+(i.issue||'this fix'));
    const set=v=>{if(pickF.get(k)===v)pickF.delete(k);else pickF.set(k,v);const d=pickF.get(k);y.classList.toggle('on',d==='yes');nn.classList.toggle('on',d==='no');li.classList.toggle('rej',d==='no');
     why.hidden=!d;why.placeholder=d==='yes'?'Optional: how you want it done (e.g. name the roles, not people)':'Optional: why not (e.g. the client asked for no expenses detail; Argus and the writer will take this forward)';if(d)why.focus();syncF()};
    y.onclick=()=>set('yes');nn.onclick=()=>set('no');ch.append(y,nn);li.append(ch,why);NOTES.set(k,why)}return li};
 const ul=mk('ul','','issues');main.forEach(i=>ul.append(row(i,items.indexOf(i))));if(!main.length)ul.append(mk('li',items.length?'Only minor polish below.':'Argus found nothing to change.','none'));is.append(ul);
 if(minor.length){const md=document.createElement('details');md.className='fold qa-minor';md.append(mk('summary','Minor polish ('+minor.length+')'));const ml=mk('ul','','issues');minor.forEach(i=>ml.append(row(i,items.indexOf(i))));md.append(ml);is.append(md)}
 if(qa.rejected_not_raised)is.append(mk('p',qa.rejected_not_raised+' point'+(qa.rejected_not_raised>1?'s':'')+' you rejected earlier came up again and '+(qa.rejected_not_raised>1?'were':'was')+' left out.','hint'));
 if(items.some(i=>i.fix)&&can){fgo.onclick=async()=>{const withNote=k=>{const {brief,...x}=items[k];return {...x,note:(NOTES.get(k)||{}).value||''}};const fixes=[...pickF.entries()].filter(([,v])=>v==='yes').map(([k])=>withNote(k)),rejected=[...pickF.entries()].filter(([,v])=>v==='no').map(([k])=>withNote(k));fgo.disabled=true;
   try{await api('/proposals/'+p.id+'/revise','POST',{fixes,rejected});follow(p.id);document.querySelector('main').scrollTop=0}catch(e){fgo.disabled=false;alertBox(e.message)}};fbar.append(fgo,fnote);is.append(fbar);syncF()}
 if(metR.length||(qa.strengths||[]).length){const ok=document.createElement('details');ok.className='fold qa-ok';ok.append(mk('summary','What already meets the brief'));const ol=mk('ul','','qa-met');
  for(const r of metR)ol.append(mk('li','✓ '+r.requirement+(r.where?' (in '+r.where+')':'')));for(const x of qa.strengths||[])ol.append(mk('li','+ '+x));ok.append(ol);is.append(ok)}
 box.append(is);
 const pr=p.pricing||{};if((pr.lines||[]).length||(!p.inputs.qa_only&&(p.draft.sections||[]).length)){const c=mk('section','','card internal');c.append(mk('h2','Commercials'));
  const pd=mk('div','','pdiff');pd.id='pdiff';c.append(pd);PRICED=pr;drawPriceDiff(pd);if(!(pr.lines||[]).length){box.append(c);c.append(mk('p','Not priced yet: tick roles with days on the rate card, then Update the pricing.','hint'))}else{
  c.append(table(['Role','Quantity','Sell rate','Sell','Cost','Margin'],pr.lines.map(l=>({cells:[l.role,n(l.quantity+' '+l.unit+(l.quantity===1?'':'s'),1),n(PE.gbp(l.sell_rate),1),n(PE.gbp(l.sell),1),n(PE.gbp(l.cost),1),n(l.margin==null?'—':l.margin.toFixed(1)+'%',1)]})).concat([{cls:'tot',cells:['Total','','',n(PE.gbp(pr.sell),1),n(PE.gbp(pr.cost),1),n(pr.margin==null?'—':pr.margin.toFixed(1)+'%',1)]}])));
  for(const w of pr.warnings||[])c.append(mk('p','⚠ '+w,'warnline'));box.append(c)}}
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
function snap(){const tt=window.tplOf?window.tplOf():new Set();return {f:['title','org','brief','notes','structure'].map(id=>[id,$(id).value]),tpl:$('tplsel').value,secs:secEd.value().map(x=>({...x,source:tt.has(x.title)?'template':'added'})),refs:[...picked],rates:rateEd.value(),mem:$('mem').checked,drafts:EDS?EDS.map(([x,t])=>[x.title,t.value]):null}}
async function restore(u){for(const[id,v]of u.f){$(id).value=v;$(id).classList.remove('tfill');$(id).dispatchEvent(new Event('input',{bubbles:true}))}
 if($('tplsel').value!==u.tpl){$('tplsel').value=u.tpl;await $('tplsel').onchange()}secEd.set(u.secs);picked.clear();u.refs.forEach(x=>picked.add(x));drawRefs();rateEd.set(u.rates);$('mem').checked=u.mem;clearTags();
 if(EDS&&CUR){for(const [x,t] of EDS){const old=u.drafts?(u.drafts.find(d=>d[0]===x.title)||[])[1]:x.body;if(old!=null)t.value=old;t.classList.remove('tfill')}}summary()}
['title','org','brief','notes','structure'].forEach(id=>$(id).addEventListener('keydown',()=>$(id).classList.remove('tfill')));
function clearTags(){document.querySelectorAll('.pk-tag').forEach(x=>x.remove())}
function reveal(node){const p=node.closest('.panel');if(!p)return;if(p.tagName==='DETAILS')p.open=true;else p.classList.remove('shut');
 const head=p.tagName==='DETAILS'?p.querySelector('summary>span'):p.querySelector('.ph h2,.ph .pt');if(head&&!head.querySelector('.pk-tag'))head.append(mk('span','Updated by Parker','pk-tag'));
 p.classList.remove('pk-hit');void p.offsetWidth;p.classList.add('pk-hit')}
function fill(id,v){if(!v)return false;const e=$(id);e.value=v;e.classList.add('tfill');e.dispatchEvent(new Event('input',{bubbles:true}));reveal(e);return true}
const WHERE={'draft sections':'draft-ed',title:'title',client:'org',brief:'brief',notes:'notes',template:'tplsel',structure:'structure',references:'ref-list',roles:'rates'};
async function applyParker(u){clearTags();
 fill('title',u.title);fill('org',u.organisation);fill('brief',u.brief);fill('notes',u.notes);
 if(u.template&&u.template!==$('tplsel').value){$('tplsel').value=u.template;await $('tplsel').onchange();reveal($('tplsel'))}
 if(u.structure)fill('structure',u.structure.map(x=>x.heading+(x.points.length?'\n'+x.points.map(p=>'- '+p).join('\n'):'')).join('\n'));
 if(u.references){picked.clear();u.references.forEach(x=>picked.add(x));drawRefs();reveal($('ref-list'))}
 if(u.roles){rateEd.merge(u.roles);reveal($('rates'))}
 if(u.draft&&CUR){if(!EDS)editDraft(CUR);let first=null;for(const d of u.draft){const e=EDS.find(x=>x[0].title===d.title);if(!e)continue;e[1].value=d.body;e[1].classList.add('tfill');first=first||e[1]}if(first)first.scrollIntoView({behavior:'smooth',block:'center'})}
 summary()}
function draftNow(){if(EDS&&CUR)return (CUR.draft.sections||[]).map(s=>{const e=EDS.find(x=>x[0]===s);return {title:s.title,body:e?e[1].value:s.body,keep:!!s.keep}});
 if(CUR&&!CUR.inputs.qa_only&&CUR.draft)return (CUR.draft.sections||[]).map(s=>({title:s.title,body:s.body,keep:!!s.keep}));return []}
function form(){return {title:$('title').value,organisation:$('org').value,brief:$('brief').value,notes:$('notes').value,template:$('tplsel').value,structure:$('structure').value,
 references:[...picked],sections:secEd?secEd.value().map(x=>x.title):[],draft:draftNow(),roles:rateEd?rateEd.value().map(r=>({role:r.role,unit:r.unit,use:r.use,days:r.days,sell:r.sell,cost:r.cost})):[],
 priced:CUR&&CUR.pricing?(CUR.pricing.lines||[]).map(l=>({role:l.role,quantity:l.quantity,sell_rate:l.sell_rate,cost_rate:l.cost_rate})):[],priced_total:CUR&&CUR.pricing?CUR.pricing.sell:null,priced_cost:CUR&&CUR.pricing?CUR.pricing.cost:null}}
function pkScroll(){const l=$('pk-log');l.scrollTop=l.scrollHeight}
function pkSay(cls,text){const m=mk('div',text,'pk-m '+cls);$('pk-log').append(m);pkScroll();return m}
function pkIntro(){$('pk-log').replaceChildren();const m=pkSay('pk-p',A.paused?A.name+' is paused at the moment.':'Hello, I’m Parker. Tell me about the proposal in a sentence or two, or add the client’s brief or RFP with +. I’ll fill in the form with you and ask for anything that’s missing.');
 if(A.paused)return;const st=mk('div','','pk-starts');for(const [t,fn] of [['Add the client’s brief',()=>$('pk-file').click()],['What’s still missing?',()=>pkSend('What is still missing from the form?')],['Tighten the brief',()=>pkSend('Tighten the brief: clear headings, nothing invented.')]]){const b=mk('button',t);b.type='button';b.onclick=fn;st.append(b)}m.append(st)}
function pkDocs(){const b=$('pk-docs');b.replaceChildren();if(!PK.doc)return;const c=mk('span','📄 '+PK.doc.name,'pk-doc');const x=mk('button','×');x.type='button';x.setAttribute('aria-label','Stop using '+PK.doc.name);x.onclick=()=>{PK.doc=null;pkDocs()};c.append(x);b.append(c)}
function pkGrow(){const t=$('pk-msg');t.style.height='auto';t.style.height=Math.max(76,Math.min(t.scrollHeight,300))+'px'}
function pkWide(on){document.querySelector('.layout').classList.toggle('pk-wide',on);$('pk-wide').textContent=on?'Narrower':'Wider';$('pk-wide').setAttribute('aria-pressed',on);try{localStorage.setItem('alice.parker.wide',on?'1':'')}catch{}}
$('pk-wide').onclick=()=>pkWide(!document.querySelector('.layout').classList.contains('pk-wide'));try{if(localStorage.getItem('alice.parker.wide'))pkWide(true)}catch{}
async function pkSend(text){if(PK.busy||A.paused)return;text=(text||'').trim();if(!text&&!PK.doc)return;PK.busy=true;$('pk-send').disabled=true;$('pk-title').textContent='Parker';
 if(text)pkSay('you',text);const ty=mk('div','','pk-typing');ty.append(mk('i'),mk('i'),mk('i'));$('pk-log').append(ty);pkScroll();
 try{const before=snap();const r=await api('/parker','POST',{message:text,history:PK.history,form:form(),organisation:$('org').value,doc_token:PK.doc?PK.doc.token:'',work_id:WORK||OPEN||''});ty.remove();
  await applyParker(r.updates);if(r.changed.length)changed();const m=pkSay('pk-p',r.reply);
  if(r.changed.length){const ch=mk('div','','pk-ch');for(const c of r.changed){const t=mk('span',c);t.title='Show '+c;t.onclick=()=>{const e=$(WHERE[c]);if(e){reveal(e);e.scrollIntoView({behavior:'smooth',block:'center'})}};ch.append(t)}m.append(ch);
   const un=mk('button','Undo these changes','pk-undo');un.type='button';un.onclick=async()=>{await restore(before);un.replaceWith(mk('span','Undone.','hint'))};m.append(un)}
  if(r.questions.length>1){const ul=mk('ul','','pk-q');for(const q of r.questions.slice(1)){const li=mk('li',q);li.title='Answer this';li.onclick=()=>{$('pk-msg').value=q.replace(/\?$/,'')+': ';$('pk-msg').focus();pkGrow()};ul.append(li)}m.append(ul)}
  pkScroll();
  const you=text||'(added '+(PK.doc?PK.doc.name:'a document')+')';PK.history.push({role:'you',text:you},{role:'parker',text:r.reply});PK.history=PK.history.slice(-12);
  if(!r.saved_to){if(WORK)api('/parker/keep','POST',{work_id:WORK,you,reply:r.reply,cost_usd:r.cost_usd||0}).catch(()=>{});else PK.cost=(PK.cost||0)+(r.cost_usd||0)}}
 catch(e){ty.remove();pkSay('pk-p err',e.message)}
 finally{PK.busy=false;$('pk-send').disabled=A.paused;$('pk-msg').focus()}}
function pkSuggestions(p){const list=((p.context||{}).model_suggestions||[]).filter(x=>x.state==='pending');
 for(const sg of list){const cf=sg.carried_from,m=pkSay('pk-p pk-model'+(cf?' pk-carried':''),'');
  if(cf){const f=mk('span','Carried over from '+cf.ref+(cf.version?' (version '+cf.version+')':''),'pk-from');f.title='Written against '+cf.ref+', an earlier version of this bid; checked again against this version';m.append(f)}
  m.append(mk('strong',sg.from+' suggested changes'),mk('div',sg.note||'','pk-mnote'));
  if(cf)m.append(mk('div','Written against '+cf.ref+', not this version. Alice checked it again against this one: what still fits is below.','hint'));
  const ch=mk('div','','pk-ch');for(const c of sg.changed||[])ch.append(mk('span',c));m.append(ch);
  if((sg.no_longer||[]).length){const g=mk('div','','pk-gone');g.append(mk('b','No longer applies here'));const ul=mk('ul');for(const x of sg.no_longer)ul.append(mk('li',x));g.append(ul);m.append(g)}
  const bar=mk('div','','pk-mbar');const ap=mk('button','Apply','primary');const di=mk('button','Dismiss','secondary');ap.type=di.type='button';
  if(!(sg.changed||[]).length){ap.disabled=true;ap.title='Nothing in it applies to this version: dismiss it'}
  ap.onclick=async()=>{ap.disabled=di.disabled=true;try{if(sg.updates.draft){for(let k=0;k<40&&!(CUR&&CUR.id===p.id);k++)await new Promise(r=>setTimeout(r,250));if(!(CUR&&CUR.id===p.id))throw new Error('The draft is still loading: try Apply again in a moment.')}
    const before=snap();VIA=sg.from;await applyParker(sg.updates);await api('/proposals/'+p.id+'/suggestions/'+sg.id,'POST',{action:'applied'});await reloadVer(p.id);changed();recent();
    const un=mk('button','Undo these changes','pk-undo');un.type='button';un.onclick=async()=>{await restore(before);un.replaceWith(mk('span','Undone.','hint'))};
    bar.replaceChildren(mk('span','Applied. Check it, then save or send it to Argus as usual.','hint'),un)}catch(e){ap.disabled=di.disabled=false;alertBox(e.message)}};
  di.onclick=async()=>{ap.disabled=di.disabled=true;try{await api('/proposals/'+p.id+'/suggestions/'+sg.id,'POST',{action:'dismissed'});recent();bar.replaceChildren(mk('span','Dismissed.','hint'))}catch(e){ap.disabled=di.disabled=false;alertBox(e.message)}};
  bar.append(ap,di);m.append(bar)}
 if(list.length)pkScroll()}
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
let PRICED=null;
function priceDiff(){if(!PRICED||!rateEd)return [];const num=v=>{const x=parseFloat(String(v??'').replace(/[£,\s]/g,''));return isNaN(x)?null:x};
 const now=rateEd.value().filter(r=>r.use&&r.role.trim()),was=new Map((PRICED.lines||[]).map(l=>[l.role.toLowerCase(),l])),out=[];
 for(const r of now){const l=was.get(r.role.trim().toLowerCase()),d=num(r.days),sv=num(r.sell);
  if(!l){if(d)out.push(r.role+': added, '+d+' '+r.unit+(d===1?'':'s'));continue}
  if(d&&Math.abs(d-l.quantity)>0.001)out.push(r.role+': '+l.quantity+' \u2192 '+d+' '+r.unit+'s');
  if(sv!==null&&Math.abs(sv-l.sell_rate)>0.004)out.push(r.role+': '+PE.gbp(l.sell_rate)+' \u2192 '+PE.gbp(sv)+' a '+r.unit)}
 const nowSet=new Set(now.map(r=>r.role.trim().toLowerCase()));for(const l of PRICED.lines||[])if(!nowSet.has(l.role.toLowerCase()))out.push(l.role+': unticked, comes out');return out}
function drawPriceDiff(el){const box=el||$('pdiff');if(!box||!CUR)return;box.replaceChildren();const diff=priceDiff();const b=mk('button',diff.length?'Update the pricing':'Update the pricing from the rate card','');b.type='button';b.className=diff.length?'primary':'secondary';
 if(diff.length){const h=mk('p','The rate card has changed since this proposal was priced:','pd-h');const ul=mk('ul');diff.slice(0,8).forEach(x=>ul.append(mk('li',x)));box.append(h,ul)}
 b.onclick=async()=>{b.disabled=true;try{const r=await api('/proposals/'+CUR.id+'/reprice','POST',{rate_card:rateEd.value()});follow(CUR.id);document.querySelector('main').scrollTop=0}catch(e){b.disabled=false;alertBox(e.message)}};
 box.append(b,mk('span','Alice reprices it from the ticked roles (your days win), Argus checks the draft against the new price, and the Word document is rebuilt. Ask Parker to bring the wording in line, e.g. \u201c20 consultant days\u201d.','hint'));box.classList.toggle('on',!!diff.length)}
$('full').addEventListener('input',()=>setTimeout(drawPriceDiff,0));$('full').addEventListener('change',()=>setTimeout(drawPriceDiff,0));$('full').addEventListener('click',()=>setTimeout(drawPriceDiff,0));
function alertBox(msg){const e=mk('div',msg,'err');$('result').prepend(e);setTimeout(()=>e.remove(),8000)}
function editDraft(p){const box=$('result');const c=mk('section','','card');c.append(mk('h2','Edit the draft'),mk('p','Change any section, then send it back: Argus checks your version against the brief and the Word document is rebuilt from the template. The headings stay as they are.','hint'));
 const eds=[];for(const s of p.draft.sections||[]){const w=mk('div','','edit-sec');w.append(mk('b',s.title));if(s.keep){w.append(mk('span','(standard text from the template: not edited here)','hint'))}else{const t=document.createElement('textarea');t.value=s.body;t.maxLength=20000;t.setAttribute('aria-label','Text of '+s.title);w.append(t);eds.push([s,t])}c.append(w)}
 const go=document.createElement('button');go.type='button';go.className='primary';go.textContent='Save changes and check again';const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';cancel.textContent='Cancel';cancel.onclick=()=>show(p);
 go.onclick=async()=>{go.disabled=true;try{await api('/proposals/'+p.id+'/recheck','POST',{sections:(p.draft.sections||[]).map(s=>{const e=eds.find(x=>x[0]===s);return {title:s.title,body:e?e[1].value:''}})});follow(p.id)}catch(e){go.disabled=false;alertBox(e.message)}};
 const a=mk('div','','act');a.append(go,cancel);c.append(a);box.replaceChildren(c);EDS=eds;c.id='draft-ed';document.querySelector('main').scrollTop=0}
// ---------- proposals on the go: list, switching, autosave ----------
let WORK=null,OPEN=null,LOADING=0,saveT=null,ITEMS=[],DIRTY=false;
let HIST=[],VIA='';
const when=t=>new Date(t).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
const isModel=v=>!!v&&!/^(Parker page|Parker and Argus)$/.test(v);
function drawVer(){const b=$('wb-ver'),box=$('wb-hist');const last=HIST[HIST.length-1];b.hidden=!(OPEN&&last);if(!last){box.hidden=true;return}
 b.textContent='v'+last.v+' · '+when(last.at)+(last.via?' · '+last.via:'');
 box.replaceChildren(mk('div','Versions of this proposal','wb-g'));
 for(const x of [...HIST].reverse()){const r=mk('div','','wb-h');const top=mk('div');top.append(mk('span',x.what||'Edited'),mk('span',x.via||'Parker page','wb-via'+(isModel(x.via)?' model':'')));
  r.append(mk('b','v'+x.v),top,mk('span',when(x.at)+(x.by?' · '+x.by:'')+(x.edits>1?' · '+x.edits+' saves':''),'hint'));box.append(r)}}
function addVer(v){if(!v)return;const last=HIST[HIST.length-1];if(last&&last.v===v.v)HIST[HIST.length-1]=v;else HIST.push(v);drawVer()}
async function reloadVer(id){try{const p=await api('/proposals/'+id);if(id===OPEN){HIST=(p.context||{}).history||[];drawVer()}}catch{}}
$('wb-ver').onclick=e=>{e.stopPropagation();const h=$('wb-hist');h.hidden=!h.hidden;$('wb-ver').setAttribute('aria-expanded',String(!h.hidden));$('wb-pop').hidden=true};
document.addEventListener('click',e=>{if(!e.target.closest('#wb-hist,#wb-ver'))$('wb-hist').hidden=true});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('wb-hist').hidden=true});
const STATE=x=>x.superseded_by?['Superseded by P-'+String(x.superseded_by).slice(0,6).toUpperCase(),'old']:x.status==='form'?['In progress','form']:x.status==='running'?['Being written','run']:x.status==='failed'?['Failed','bad']:[(x.verdict==='client_ready'?'Client ready':'Needs attention')+(x.score!=null?' · '+x.score:''),x.verdict==='client_ready'?'ok':'warn'];
async function recent(){try{const d=await api('/proposals');ITEMS=d.proposals;BIDS=d.bids||[];const sg=ITEMS.filter(x=>x.suggestions).length;const n=$('wb-n');n.textContent=BIDS.length||'';n.classList.toggle('sug',!!sg);
 n.title=sg?sg+(sg===1?' proposal has':' proposals have')+' suggested changes waiting':'';drawItems();updateBar()}catch{}}
function pkWaiting(){const w=ITEMS.filter(x=>x.suggestions&&x.id!==OPEN);if(!w.length)return;
 const m=pkSay('pk-p pk-model','');m.append(mk('strong','Suggested changes are waiting'));
 for(const x of w){const d=mk('div','','pk-open');d.append(mk('div',(x.title||'Untitled proposal')+': '+x.suggestions+(x.suggestions===1?' suggestion':' suggestions')+' from '+(x.suggested_by||[]).join(', '),'pk-mnote'));
  const b=mk('button','Open it to apply or dismiss','secondary');b.type='button';b.onclick=()=>openItem(x.id);d.append(b);m.append(d)}}
const money=v=>'$'+Number(v||0).toFixed(2);
function itemRow(x,b){const it=mk('div','','wb-it'+(x.id===OPEN?' on':''));it.tabIndex=0;it.setAttribute('role','button');const t=mk('div');
 const sug=x.activity_kind==='suggestion',multi=(x.bid_versions||1)>1;const ln=mk('span',(x.ref?x.ref+' · ':'')+(multi?'version '+x.bid_version+' of '+x.bid_versions:'v'+(x.version||1))+' · '+(sug?'Suggestion from '+x.activity_from+' ':(x.status==='form'?'Edited ':'Updated '))+when(x.activity_at||x.edited_at||x.updated_at||x.created_at),'hint');if(x.edited_via&&!sug)ln.append(mk('span',x.edited_via,'wb-via'+(isModel(x.edited_via)?' model':'')));
 ln.title=(multi?'v'+(x.version||1)+' of its own history · ':'')+(x.edited_what||'')+(x.edited_by?' · '+x.edited_by:'');t.append(mk('b',(x.title||'Untitled proposal')+(x.organisation?' · '+x.organisation:'')),ln);
 const [lab,cls]=STATE(x);const pc=mk('span','','');pc.style.cssText='display:flex;gap:8px;align-items:center';
 const cost=b&&b.versions>1&&b.ai_cost_total?'AI '+money(b.ai_cost_total)+' in total ('+money(x.ai_cost)+' this version)':x.ai_cost?'AI '+money(x.ai_cost):'';if(b&&b.versions>1&&cost){const cl=mk('span',cost,'wb-cost');cl.style.display='block';t.append(cl)}else pc.append(mk('span',cost,'wb-cost'));
 if(x.suggestions){const sp=mk('span',x.suggestions+(x.suggestions===1?' suggestion':' suggestions'),'wb-sug');sp.title='Suggested by '+(x.suggested_by||[]).join(', ')+': open it to apply or dismiss';pc.append(sp)}pc.append(mk('span',lab,'wb-pill '+cls));
 pc.title=cost?(b&&b.versions>1?'What Alice’s AI calls have cost across all '+b.versions+' versions of this bid (writing, Argus and Parker), and for this version alone':'What Alice’s AI calls for this proposal have cost so far (writing, Argus and Parker)'):'';it.append(t,pc);
 if(x.status==='form'&&!x.superseded_by){const xb=mk('button','×','wb-x');xb.type='button';xb.title='Remove this proposal in progress';xb.setAttribute('aria-label','Remove '+(x.title||'this proposal'));
  xb.onclick=async e=>{e.stopPropagation();if(!confirm('Remove “'+(x.title||'Untitled proposal')+'” from your proposals in progress?'+(multi?'\n\nThe version it replaced becomes the current version again.':'')))return;try{await api('/work/'+x.id+'/discard','POST',{});if(x.id===OPEN)await openNew();await recent()}catch(err){alertBox(err.message)}};it.append(xb)}else it.append(mk('span'));
 it.onclick=()=>{$('wb-pop').hidden=true;$('wb-list').setAttribute('aria-expanded','false');openItem(x.id)};it.onkeydown=e=>{if(e.key==='Enter')it.click()};return it}
function drawItems(){const q=($('wb-q').value||'').toLowerCase(),box=$('wb-items');box.replaceChildren();
 const by=new Map(ITEMS.map(x=>[x.id,x])),hay=x=>((x.title||'')+' '+(x.organisation||'')+' '+(x.ref||'')).toLowerCase();
 const list=BIDS.map(b=>({b,cur:by.get(b.current),old:(b.earlier||[]).map(i=>by.get(i)).filter(Boolean)})).filter(o=>o.cur&&(!q||hay(o.cur).includes(q)||o.old.some(x=>hay(x).includes(q))))
  .sort((a,b)=>String(b.cur.activity_at||'').localeCompare(String(a.cur.activity_at||'')));
 if(!list.length){box.append(mk('p',ITEMS.length?'No proposals match.':'No proposals yet. Start one with + New proposal; it saves itself as you work.','hint'));return}
 for(const [g,f] of [['In progress',x=>x.group==='progress'],['Being written',x=>x.group==='running'],['Written',x=>x.group==='written']]){const its=list.filter(o=>f(o.cur));if(!its.length)continue;box.append(mk('div',g+' ('+its.length+')','wb-g'));
  const orgs=[...new Set(its.map(o=>o.cur.organisation||''))].sort((a,b)=>!a?1:!b?-1:a.localeCompare(b));      // by client; No client last
  for(const org of orgs){box.append(mk('div',org||'No client','wb-org'));
   for(const o of its.filter(o=>(o.cur.organisation||'')===org)){box.append(itemRow(o.cur,o.b));
    if(o.old.length){const d=document.createElement('details');d.className='wb-old';d.open=o.old.some(x=>x.id===OPEN)||(!!q&&o.old.some(x=>hay(x).includes(q)));
     d.append(mk('summary',o.old.length+(o.old.length===1?' earlier version':' earlier versions')));for(const x of o.old)d.append(itemRow(x,null));box.append(d)}}}}}
// ---------- bids and versions: a superseded version is read-only; Make this replace…; Restore as a separate proposal ----------
let RO=false,BIDS=[];
function setRO(on){RO=!!on;$('f').inert=RO;$('full').inert=RO;$('pk-msg').disabled=RO||!!A.paused;$('pk-send').disabled=RO||!!A.paused;$('go').disabled=RO||!!A.paused;
 const m=$('pk-msg');if(!m.dataset.ph)m.dataset.ph=m.placeholder;m.placeholder=RO?'This version is superseded and read-only: open the current version to work with Parker.':m.dataset.ph}
function retired(p){const b=p.bid||{};setRO(true);const box=$('result');box.querySelector('.supd')?.remove();
 box.querySelectorAll('.act,.retpl,.fixbar,.fixch,.pdiff').forEach(e=>e.remove());
 const c=mk('section','','card supd');c.append(mk('h2','Superseded by '+(b.superseded_by_ref||'P-'+String(p.superseded_by).slice(0,6).toUpperCase())));
 c.append(mk('p','This is version '+(b.version||1)+' of '+((b.versions||[]).length||1)+' of this bid, kept as it was: read-only, so no new Parker edits or Argus checks start on it. Suggestions that were waiting on it moved to the current version.','hint'));
 const a=mk('div','','act');if(b.current&&b.current!==p.id){const o=mk('button','Open the current version ('+b.current_ref+')','primary');o.type='button';o.onclick=()=>openItem(b.current);a.append(o)}
 const r=mk('button','Restore as a separate proposal','secondary');r.type='button';r.title='Undo the link: this version (with any versions before it) becomes a proposal of its own again';
 r.onclick=async()=>{if(!confirm('Restore '+(p.ref||'P-'+p.id.slice(0,6).toUpperCase())+' as a separate proposal?\n\nIt stops being an earlier version of this bid and can be changed again. Suggestions carried over from it that are still waiting go back with it.'))return;
  r.disabled=true;try{await api('/proposals/'+p.id+'/restore','POST',{});await recent();openItem(p.id)}catch(e){r.disabled=false;alertBox(e.message)}};
 a.append(r);c.append(a);box.prepend(c);updateBar()}
function drawReplace(){const box=$('wb-rp');box.replaceChildren();const me=ITEMS.find(i=>i.id===OPEN);if(!me)return;
 const mine=new Set([me.id,...ITEMS.filter(i=>i.bid_current===me.bid_current).map(i=>i.id)]);
 const cand=BIDS.filter(b=>!mine.has(b.current)).map(b=>[b,ITEMS.find(i=>i.id===b.current)]).filter(([,x])=>x&&x.status!=='running');
 const org=(me.organisation||'').toLowerCase(),same=cand.filter(([,x])=>org&&(x.organisation||'').toLowerCase()===org),other=cand.filter(c=>!same.includes(c));
 box.append(mk('div','Make '+me.ref+' replace…','wb-g'),mk('p','Tick the proposals this one replaces. They become its earlier versions: kept as they are, read-only, with their waiting suggestions moved here. Restore as a separate proposal undoes it.','hint'));
 if(!cand.length){box.append(mk('p','There are no other proposals to pick.','hint'));return}
 const picked=new Set();const go=mk('button','Make '+me.ref+' replace the ticked proposals','primary');go.type='button';go.disabled=true;
 const row=([b,x])=>{const l=document.createElement('label');const cb=document.createElement('input');cb.type='checkbox';cb.onchange=()=>{cb.checked?picked.add(x.id):picked.delete(x.id);go.disabled=!picked.size};
  const t=mk('span');t.append(mk('b',(x.title||'Untitled proposal')+(x.organisation?' · '+x.organisation:'')),mk('span',x.ref+(b.versions>1?' · current of '+b.versions+' versions':'')+' · '+STATE(x)[0]+' · '+when(x.activity_at||x.updated_at),'hint'));l.append(cb,t);return l};
 if(same.length){box.append(mk('div','Same client','wb-org'));same.forEach(c=>box.append(row(c)))}
 if(other.length){box.append(mk('div',same.length?'Other proposals':'Proposals','wb-org'));other.forEach(c=>box.append(row(c)))}
 go.onclick=async()=>{const ids=[...picked];if(!confirm('Make '+me.ref+' replace '+ids.length+(ids.length===1?' proposal':' proposals')+'?'))return;go.disabled=true;
  try{const r=await api('/proposals/'+me.id+'/replaces','POST',{replaces:ids});box.hidden=true;await recent();await openItem(me.id);if(r.carried)pkSay('pk-p',r.carried+(r.carried===1?' suggestion was':' suggestions were')+' carried over from the versions it replaces: check each one below.')}
  catch(e){go.disabled=false;alertBox(e.message)}};
 const a=mk('div','','act');a.append(go);box.append(a)}
$('wb-repl').onclick=e=>{e.stopPropagation();const b=$('wb-rp');b.hidden=!b.hidden;$('wb-repl').setAttribute('aria-expanded',String(!b.hidden));$('wb-pop').hidden=$('wb-hist').hidden=true;if(!b.hidden)drawReplace()};
document.addEventListener('click',e=>{if(!e.target.closest('#wb-rp,#wb-repl'))$('wb-rp').hidden=true});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('wb-rp').hidden=true});
function updateBar(){$('wb-title').textContent=$('title').value.trim()||(OPEN?'Untitled proposal':'New proposal');const rf=$('wb-ref');rf.hidden=!OPEN;rf.textContent=OPEN?'P-'+String(OPEN).slice(0,6).toUpperCase():'';const x=ITEMS.find(i=>i.id===OPEN);
 $('wb-keep').hidden=!(OPEN&&!WORK&&DIRTY)||RO;$('wb-repl').hidden=!(OPEN&&x&&!x.superseded_by&&x.status!=='running')||RO;if(!saveT&&!$('wb-state').classList.contains('bad')){const st=$('wb-state');
  if(WORK)st.textContent=st.textContent||'Saved';else if(x&&x.status!=='form'){st.className='wb-state';st.textContent=STATE(x)[0]+(DIRTY?' · changes not saved: write a new version or Save as a new version':'')}else if(!OPEN){st.className='wb-state';st.textContent=DIRTY?'':'Saves itself as you work'}}}
function setState(t,cls){const st=$('wb-state');st.textContent=t;st.className='wb-state'+(cls?' '+cls:'')}
let FROM='';
function formData(){return {via:VIA,started_from:FROM,parker_chat:WORK?[]:PK.history,parker_cost:WORK?0:(PK.cost||0),title:$('title').value,organisation:$('org').value,brief:$('brief').value,notes:$('notes').value,structure:$('structure').value,template:$('tplsel').value,
 sections:secEd.value(),rate_card:rateEd.value(),references:[...picked],writer:$('wm').value,qa:$('qm').value,use_memory:$('mem').checked}}
function changed(){if(LOADING||RO||mode!=='write'||!S)return;DIRTY=true;
 if(!WORK&&OPEN){updateBar();return}                                           // a written proposal: kept as it is unless you save a new version
 clearTimeout(saveT);setState('Saving…');saveT=setTimeout(saveNow,1200)}
async function saveNow(force){clearTimeout(saveT);saveT=null;const f=formData();
 if(!WORK&&!force&&!f.title.trim()&&!f.brief.trim()&&!f.notes.trim()){setState('');return}
 try{const sent=(f.parker_chat||[]).length;const r=await api('/work','POST',{id:WORK||'',form:f});if(r.created){let extra=Math.max(0,(PK.cost||0)-(f.parker_cost||0));PK.cost=0;
  for(let k=sent;k+1<PK.history.length;k+=2){api('/parker/keep','POST',{work_id:r.id,you:PK.history[k].text,reply:PK.history[k+1].text,cost_usd:extra}).catch(()=>{});extra=0}moveChat(OPEN||'new',r.id);WORK=r.id;OPEN=r.id;HIST=[];CUR=null;history.replaceState(null,'','?p='+r.id);recent()}
  DIRTY=false;VIA='';FROM='';addVer(r.version);setState('Saved '+new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}),'ok');const x=ITEMS.find(i=>i.id===WORK);if(x){x.title=f.title;x.organisation=f.organisation;x.updated_at=new Date().toISOString()}updateBar()}
 catch(e){setState('Not saved: '+e.message,'bad')}}
$('f').addEventListener('input',changed);$('f').addEventListener('change',changed);
$('full').addEventListener('input',changed);$('full').addEventListener('change',changed);$('full').addEventListener('click',e=>{if(e.target.closest('button'))setTimeout(changed,0)});
$('secs').addEventListener('click',e=>{if(e.target.closest('button'))setTimeout(changed,0)});$('ref-list').addEventListener('change',changed);
$('title').addEventListener('input',updateBar);
$('wb-keep').onclick=()=>{stashChat();const from=OPEN;FROM=from||'';OPEN=null;CUR=null;DIRTY=true;saveNow(true).then(()=>{if(OPEN&&from)moveChat(from,OPEN,true)})};
$('wb-list').onclick=()=>{const p=$('wb-pop');p.hidden=!p.hidden;$('wb-list').setAttribute('aria-expanded',String(!p.hidden));if(!p.hidden){drawItems();$('wb-q').focus()}};
$('wb-q').oninput=drawItems;document.addEventListener('click',e=>{if(!e.target.closest('#workbar'))$('wb-pop').hidden=true});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('wb-pop').hidden=true});
$('wb-new').onclick=()=>openNew();
const chatKey=id=>'alice.parker.chat.'+(id||'new');
function stashChat(){}
function moveChat(){}
function restoreChat(id,p){PK.history=[];PK.cost=0;PK.doc=null;pkDocs();pkIntro();const h=((p&&p.context)||{}).parker_chat||[];
 if(h.length){PK.history=h;$('pk-title').textContent='Parker';for(const m of h)pkSay(m.role==='you'?'you':'pk-p',m.text)}}
async function resetForm(){LOADING++;try{clearInterval(timer);$('result').replaceChildren();$('prog').hidden=true;$('ferr').hidden=true;CUR=null;EDS=null;
 for(const id of ['title','org','brief','notes','structure']){$(id).value='';$(id).classList.remove('tfill')}
 if($('tplsel').value!==(S.template||'')){$('tplsel').value=S.template||'';await $('tplsel').onchange()}
 secEd.set(S.sections);rateEd.set(S.rate_card);picked.clear();drawRefs();$('wm').value=S.writer;$('qm').value=S.qa;$('mem').checked=true;clearTags();
 ['org','title'].forEach(id=>$(id).dispatchEvent(new Event('input',{bubbles:true})));if(window.cost)window.cost();summary()}finally{LOADING--}}
async function flush(){if(saveT){await saveNow()}}
async function openNew(){await flush();stashChat();setRO(false);await resetForm();WORK=null;OPEN=null;DIRTY=false;VIA='';FROM='';HIST=[];drawVer();setState('Saves itself as you work');history.replaceState(null,'',location.pathname);restoreChat(null);updateBar();drawItems();pkWaiting();document.querySelector('main').scrollTop=0}
async function openItem(id){await flush();stashChat();let p;try{p=await api('/proposals/'+id)}catch(e){alertBox(e.message);return}
 setRO(false);await resetForm();OPEN=id;DIRTY=false;VIA='';FROM='';HIST=(p.context||{}).history||[];drawVer();history.replaceState(null,'','?p='+id);restoreChat(id,p);setTimeout(()=>pkSuggestions(p),0);
 if(p.status==='form'){WORK=id;await loadIntoForm(p,true,true);setState('Saved '+new Date(p.updated_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}),'ok');
  if(p.superseded_by)retired(p);else if(!PK.history.length)pkSay('pk-p','Back to “'+(p.title||'this proposal')+'”. Everything you had is here. What would you like to change?')}
 else{WORK=null;setState('');follow(id)}
 updateBar();drawItems();document.querySelector('main').scrollTop=0}
load().catch(e=>{$('ferr').textContent=e.message;$('ferr').hidden=false});
</script></body></html>''')
