"""The Digital teams pages (Workspace › Teams; Stefan, 7 Oct 2026): All teams (/admin/teams), a team (/admin/teams/{id}) and a
job (/admin/teams/{id}/jobs/{job}). One Console page ('teams'); the script reads which screen from the address. Registered in
admin_ui (PAGES, SECTIONS, SCRIPT, NAV_GROUPS, NAV_ICONS). Every safeguard shown here is read from rules_engine through the API."""

TITLE = ('Teams', 'Digital teams: AI members who work a job stage by stage and hand work to each other. You approve each hand-off, or only '
                  'the final output. Every change to a team is versioned, and each job runs on the team version it started with.')

ICON = ('<path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M16.5 10a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"/>'
        '<path d="M2.5 19c.6-3.2 2.9-5 5.5-5s4.9 1.8 5.5 5"/><path d="M14 14.2c.8-.5 1.6-.7 2.5-.7 2.2 0 4.2 1.5 4.7 4.5"/>')

SECTION = r'''<style>
#tm-app{--tm-wait:#b45309;--tm-wait-fill:#d97706;--tm-wait-bg:#fff4e5;--tm-done:#4f8a9e;--tm-todo:#dbe4ea;--tm-bad:#b42318}
#tm-app .tm-b{margin:0}
.tm-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.tm-head{display:flex;gap:16px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;margin:0 0 14px}
.tm-head h2{font-size:22px;margin:0}.tm-head .tm-sum{margin:2px 0 0;color:var(--muted);font-size:14px}
.tm-acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.tm-acts button,.tm-acts a.button{margin:0}
.tm-mark{flex:none;display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:11px;color:#fff}
.tm-mark svg{width:58%;height:58%;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.tm-mark.sm{width:26px;height:26px;border-radius:8px}.tm-mark.lg{width:52px;height:52px;border-radius:14px}
.tm-pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;border:1px solid;white-space:nowrap}
.tm-pill::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor}
.tm-pill.s-needs_you,.tm-pill.s-waiting{background:var(--tm-wait-bg);color:#8a3f06;border-color:#f0c48a}.tm-pill.s-running,.tm-pill.s-current{background:#e3f1f6;color:#054a60;border-color:#9ccbdc}
.tm-pill.s-idle,.tm-pill.s-todo{background:#f1f4f6;color:#4b5a66;border-color:#c9d5de}.tm-pill.s-paused,.tm-pill.s-blocked{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}
.tm-pill.s-draft{background:#fff;color:#4b5a66;border:1px dashed #8aa0b0}.tm-pill.s-done{background:#e6f4ea;color:#1e5b31;border-color:#9fcfaf}.tm-pill.s-stopped{background:#eef1f4;color:#4b5a66;border-color:#c1cbd3}
.tm-needs{border:1px solid #f0c48a;background:#fffaf2;border-radius:14px;padding:14px 16px;margin:0 0 16px}
.tm-needs h3{margin:0 0 8px;font-size:15px;display:flex;gap:8px;align-items:center}.tm-needs h3 .n{background:var(--tm-wait-fill);color:#1b1203;border-radius:999px;font-size:12px;padding:0 8px}
.tm-nrow{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #f3dfc0}.tm-nrow:first-of-type{border-top:0}
.tm-nrow .t{font-size:13px;color:var(--muted)}.tm-nrow .t a{font-weight:600;color:var(--ink)}.tm-nrow .s{font-size:14px;overflow-wrap:anywhere}.tm-nrow time{font-size:12px;color:var(--muted);white-space:nowrap}
.tm-nrow button{margin:0}
.tm-ctl{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 14px}.tm-ctl input[type=search]{flex:1 1 220px;min-width:180px;width:auto;margin:0}
.tm-ctl .rl-chips{flex:2 1 auto}.tm-ctl label{margin:0;display:flex;gap:6px;align-items:center;font-size:13px;color:var(--muted)}.tm-ctl select{padding:6px 8px}
.tm-seg{display:inline-flex;border:1px solid var(--line2);border-radius:9px;overflow:hidden}.tm-seg button.ghost{margin:0;border:0;border-radius:0;padding:6px 12px;background:#fff;color:var(--ink);font-size:13px}
.tm-seg button.ghost[aria-pressed=true]{background:var(--teal);color:#fff;font-weight:600}
#tm-app section.tm-group{margin:0 0 20px;background:none;border:0;padding:0;border-radius:0}.tm-group>h3{font-size:14px;margin:0 0 10px;color:#3d5566;display:flex;gap:8px;align-items:baseline}.tm-group>h3 .c{font-weight:400;color:var(--muted);font-size:13px}
.tm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.tm-card{position:relative;background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px;display:flex;flex-direction:column;gap:10px;transition:box-shadow .15s,border-color .15s}
.tm-card:hover,.tm-card:focus-within{border-color:#7fa9c4;box-shadow:0 2px 10px rgba(16,43,64,.08)}.tm-card.draft{border:1.5px dashed #8aa0b0;background:#fbfcfd}
.tm-card .top{display:flex;gap:12px;align-items:flex-start}.tm-card .nm{flex:1;min-width:0}.tm-card h4{margin:0;font-size:16px;line-height:1.3}
.tm-card h4 a{color:var(--ink);text-decoration:none}.tm-card h4 a::after{content:'';position:absolute;inset:0;border-radius:14px}.tm-card h4 a:focus-visible{outline:none}.tm-card:has(h4 a:focus-visible){outline:2px solid var(--teal);outline-offset:2px}
.tm-card .meta{font-size:12.5px;color:var(--muted)}.tm-card .purpose{margin:0;font-size:13.5px;color:#30495c;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.tm-card .live{position:relative;z-index:1;border-top:1px solid #e6edf2;padding-top:10px;font-size:13px}.tm-card .live a{font-weight:600}
.tm-card .missing{font-size:13px;color:#4b5a66}.tm-card .missing b{color:#8a3f06}
.tm-card .foot{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--muted);border-top:1px solid #eef3f6;padding-top:8px;margin-top:auto}
.tm-avs{display:flex;flex-wrap:wrap;gap:6px}.tm-card .tm-avs{position:relative;z-index:1;align-self:flex-start}.tm-av{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:50%;background:#eef3f7;color:#1d3a50;font-size:11.5px;font-weight:700;border:1px solid #c9d5de}
.tm-av.lead{border-color:#fff}.tm-av.lg{width:38px;height:38px;font-size:13px}
.tm-prog{display:flex;gap:3px;margin:6px 0 4px}.tm-prog span{flex:1;height:7px;border-radius:4px;background:var(--tm-todo)}
.tm-prog .done{background:var(--tm-done)}.tm-prog .current{background:var(--teal)}.tm-prog .waiting{background:var(--tm-wait-fill)}.tm-prog .blocked{background:var(--tm-bad)}.tm-prog .stopped{background:#8a99a6}
.tm-where{font-size:12.5px;color:#3d5566}.tm-where.w{color:#8a3f06;font-weight:600}
.tm-list td,.tm-list th{font-size:13.5px;vertical-align:middle}.tm-list .tn{display:flex;gap:10px;align-items:center;min-width:200px}.tm-list a{font-weight:600}
.tm-panel{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:0 0 16px}.tm-panel>h3:first-child{margin-top:0}
.tm-form{display:grid;gap:12px;max-width:860px}.tm-form label{margin:0;display:grid;gap:4px;font-weight:600;font-size:14px}.tm-form .row{display:flex;gap:12px;flex-wrap:wrap}.tm-form .row>label{flex:1 1 220px}
.tm-form h3{margin:0}.tm-form fieldset{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0}.tm-form legend{font-weight:600;font-size:14px;padding:0 4px}
.tm-swatches{display:flex;flex-wrap:wrap;gap:8px}.tm-swatches label{display:inline-flex;align-items:center;gap:6px;font-weight:400;font-size:13px;margin:0;cursor:pointer;padding:4px 8px 4px 4px;border:1px solid var(--line);border-radius:999px}
.tm-swatches input{position:absolute;opacity:0;width:1px;height:1px}.tm-swatches label:has(input:checked){border-color:var(--teal);box-shadow:0 0 0 2px var(--teal);font-weight:600}
.tm-swatches label:has(input:focus-visible){outline:2px solid var(--teal);outline-offset:2px}.tm-swatches .sw{width:22px;height:22px;border-radius:50%}
.tm-tmpl{display:grid;gap:8px}.tm-tmpl label{display:flex;gap:10px;align-items:flex-start;font-weight:400;border:1px solid var(--line);border-radius:10px;padding:10px;cursor:pointer}
.tm-tmpl label:has(input:checked){border-color:var(--teal);background:#f3f9fb}.tm-tmpl b{display:block}
.tm-split{display:grid;grid-template-columns:210px minmax(0,1fr);gap:20px;align-items:start}
.tm-nav{position:sticky;top:0;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;font-size:14px}
.tm-nav a.back{display:block;font-weight:600;text-decoration:none;margin:0 0 10px}.tm-nav h4{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:12px 0 6px}
.tm-nav ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:minmax(0,1fr);gap:2px}.tm-nav li{min-width:0}.tm-nav li a{display:flex;align-items:center;gap:8px;padding:6px 6px;border-radius:8px;text-decoration:none;color:var(--ink);line-height:1.3}
.tm-nav li a:hover{background:#f1f6f9}.tm-nav li a[aria-current=page]{background:#e3f1f6;font-weight:600}.tm-nav li a span.n{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tm-dot{width:9px;height:9px;border-radius:50%;background:var(--tm-wait-fill);flex:none}.tm-nav .empty{font-size:12.5px;color:var(--muted);margin:0}
.tm-thead{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:0 0 12px}.tm-thead .nm{flex:1;min-width:220px}.tm-thead h2{margin:0;font-size:22px}
.tm-thead p{margin:2px 0 6px;color:var(--muted);font-size:14px}.tm-chips{display:flex;flex-wrap:wrap;gap:6px}.tm-chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;padding:3px 10px;border-radius:999px;border:1px solid #c9d5de;background:#f6f9fb;color:#1d3a50;text-decoration:none}
.tm-chip.off{background:#fbeaea;border-color:#e0aaaa;color:#7a1f1f}.tm-chip.warn{background:var(--tm-wait-bg);border-color:#f0c48a;color:#8a3f06;font-weight:600}
.tm-tabs{display:flex;gap:2px;border-bottom:1px solid var(--line);margin:0 0 16px;overflow-x:auto;scrollbar-width:thin}
.tm-tabs button.ghost{margin:0 0 -1px;border:0;border-bottom:3px solid transparent;border-radius:0;background:none;padding:9px 14px;font-size:14px;color:#3d5566;white-space:nowrap}
.tm-tabs button.ghost[aria-selected=true]{border-bottom-color:var(--teal);color:var(--ink);font-weight:650}.tm-tabs .n{font-size:12px;color:var(--muted);margin-left:4px}
.tm-cols{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:16px;align-items:start}
.tm-how .lead-wrap{display:flex;justify-content:center}.tm-mcard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:grid;gap:6px;font-size:13px}
.tm-mcard .r{display:flex;gap:10px;align-items:center}.tm-mcard b{font-size:14.5px}.tm-mcard .p{color:#30495c}.tm-mcard .k{color:var(--muted)}
.tm-mcard.lead{max-width:520px;width:100%;border-width:2px}.tm-conn{width:2px;height:22px;margin:0 auto;background:#b9cbd8}
.tm-mrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;position:relative;padding-top:12px;border-top:2px solid #b9cbd8}
.tm-state{font-size:12.5px;font-weight:600}.tm-state.waiting{color:#8a3f06}.tm-state.current{color:var(--teal)}.tm-state.done{color:#1e5b31}.tm-state.blocked{color:#7a1f1f}.tm-state.idle,.tm-state.todo{color:var(--muted)}
.tm-cats{display:flex;flex-wrap:wrap;gap:4px}.tm-cats span{font-size:11.5px;background:#eef3f7;border-radius:5px;padding:1px 7px}
.tm-ol{margin:6px 0 10px;padding-left:22px}.tm-ol li{margin:6px 0}.tm-ol b{display:block}
.tm-side .tm-panel h3{margin:0 0 10px;font-size:15px;display:flex;justify-content:space-between;align-items:baseline;gap:8px}.tm-side .tm-panel h3 a{font-size:13px;font-weight:400}
.tm-jrow{display:grid;gap:2px;padding:10px 0;border-top:1px solid #eef3f6;font-size:13px}.tm-jrow:first-of-type{border-top:0}.tm-jrow .l{display:flex;gap:8px;align-items:center;justify-content:space-between}
.tm-jrow.hl{background:var(--tm-wait-bg);border:1px solid #f0c48a;border-radius:10px;padding:10px 12px;margin:0 0 6px}
.tm-rules{list-style:none;margin:0;padding:0;display:grid;gap:8px;font-size:13px}.tm-rules li{display:grid;grid-template-columns:20px minmax(0,1fr);gap:8px}
.tm-tick{width:18px;height:18px;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:#e6f4ea;color:#1e5b31;border:1px solid #9fcfaf}
.tm-tick.off{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}.tm-rules .u{color:var(--muted);font-size:12px}
.tm-crumbs{font-size:13px;margin:0 0 8px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;color:var(--muted)}.tm-crumbs a{text-decoration:none}
.tm-label{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#8a3f06;margin:0}.tm-label.plain{color:var(--muted)}
.tm-track{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin:0 0 16px;list-style:none;padding:0}
.tm-track li{border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:#fff;font-size:12.5px;display:grid;gap:2px}
.tm-track li b{font-size:13px;line-height:1.3}.tm-track li .who{color:var(--muted)}.tm-track li.done{background:#f3f8fa;border-color:#b7d3de}.tm-track li.current{border:2px solid var(--teal)}
.tm-track li.waiting{border:2px solid var(--tm-wait-fill);background:var(--tm-wait-bg)}.tm-track li.todo{border-style:dashed;color:#4b5a66}.tm-track li.blocked{border:2px solid var(--tm-bad);background:#fbeaea}
.tm-dec{border:2px solid var(--tm-wait-fill);background:var(--tm-wait-bg);border-radius:14px;padding:14px 16px;margin:0 0 16px}.tm-dec h3{margin:0 0 4px;font-size:16px}
.tm-dec table input[type=number]{width:110px;margin:0;padding:5px 8px}.tm-dec .opts{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0 0}.tm-dec .opts label{margin:0;display:flex;gap:6px;align-items:center;font-size:13.5px}
.tm-dec textarea{width:100%;min-height:54px;margin:8px 0 0}
.tm-wait{border-left:4px solid var(--tm-wait-fill);background:#fffaf2;border-radius:8px;padding:10px 12px;margin:0 0 12px}.tm-wait textarea{width:100%;min-height:60px;margin-top:6px}
.tm-err{border-left:4px solid var(--tm-bad);background:#fbeaea;border-radius:8px;padding:10px 12px;margin:0 0 12px}
.tm-src{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 8px;border-radius:5px;border:1px solid;white-space:nowrap}
.tm-src.web{background:#e3f1f6;border-color:#9ccbdc;color:#054a60}.tm-src.library{background:#f1ebf7;border-color:#cbb8e2;color:#4b2f73}.tm-src.yours{background:#e6f4ea;border-color:#9fcfaf;color:#1e5b31}
.tm-src.unpriced{background:var(--tm-wait-bg);border-color:#f0c48a;color:#8a3f06}.tm-src.to_price{background:#f1f4f6;border-color:#c9d5de;color:#4b5a66}
.tm-plan tr.und td{background:#fff7eb}.tm-plan td.n,.tm-plan th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.tm-plan .sub{font-size:12px;color:var(--muted)}.tm-plan th,.tm-plan td{padding:8px 8px}
.tm-tot{display:grid;grid-template-columns:auto auto;gap:4px 18px;justify-content:end;font-size:14px;margin:10px 0 0;font-variant-numeric:tabular-nums}.tm-tot b{font-size:15px}
.tm-tl{list-style:none;margin:0;padding:0;display:grid;gap:0;max-height:620px;overflow:auto}.tm-tl li{display:grid;grid-template-columns:32px minmax(0,1fr);gap:10px;padding:9px 0;border-top:1px solid #eef3f6;font-size:13px}
.tm-tl li:first-child{border-top:0}.tm-tl .w{font-weight:650}.tm-tl time{color:var(--muted);font-size:12px}.tm-tl .o{font-size:12px;color:#3d5566}.tm-tl button.secondary{margin:4px 0 0;padding:2px 9px;font-size:12px}
.tm-av.you{background:#fff4e5;border-color:#f0c48a;color:#8a3f06}
.tm-talk .log{display:grid;gap:8px;max-height:320px;overflow:auto;margin:0 0 8px}.tm-msg{border-radius:10px;padding:8px 10px;font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}
.tm-msg.you{background:#e3f1f6;margin-left:24px}.tm-msg.lead{background:#f4f6f8;margin-right:24px}.tm-msg .w{display:block;font-size:11.5px;font-weight:700;color:#3d5566}.tm-msg .r{display:block;font-size:12px;color:#4b2f73;margin-top:4px}
.tm-talk textarea{width:100%;min-height:58px;margin:0 0 6px}.tm-kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;font-size:13px;margin:0}.tm-kv dt{color:var(--muted)}.tm-kv dd{margin:0}
.tm-mem{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 12px;background:#fff}.tm-mem h3{margin:0 0 8px;display:flex;gap:10px;align-items:center}
.tm-mem .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.tm-mem label{display:grid;gap:4px;font-size:13px;font-weight:600;margin:6px 0}
.tm-mem textarea.ins{min-height:150px}.tm-checks{display:flex;flex-wrap:wrap;gap:4px 14px;font-weight:400}.tm-checks label{display:flex;gap:6px;align-items:center;font-weight:400;margin:2px 0}
.tm-sugg{border-left:4px solid #6b4fa0;background:#f7f4fb;border-radius:8px;padding:10px 12px;margin:10px 0}.tm-sugg pre{white-space:pre-wrap;font-size:12.5px;background:#fff;border:1px solid #e1d8ee;border-radius:6px;padding:8px}
.tm-stage{border:1px solid #d3dee6;border-radius:10px;padding:10px 12px;margin:8px 0;display:grid;gap:8px;background:#fff}.tm-stage .row{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end}.tm-stage .row label{flex:1;min-width:180px;margin:0}
.tm-stage label{display:grid;gap:4px;font-size:13px;font-weight:600;margin:0}.tm-flow{font-size:13px;color:#3d5566;margin:6px 0 10px}.tm-auto label{display:flex;gap:8px;align-items:flex-start;margin:6px 0;font-weight:400}
.tm-tbl{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}.tm-tbl th,.tm-tbl td{border-bottom:1px solid #dbe3ea;padding:5px 8px;text-align:left;vertical-align:top}
.tm-docs{display:grid;gap:6px}.tm-doc{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border:1px solid #d3dee6;border-radius:8px;padding:6px 10px;font-size:13px}.tm-doc span{flex:1}
.tm-out{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0 0;font-size:13.5px}.tm-empty{color:var(--muted);font-size:14px;margin:6px 0}
@media(max-width:1100px){.tm-cols{grid-template-columns:minmax(0,1fr)}}
@media(max-width:900px){.tm-split{grid-template-columns:minmax(0,1fr)}.tm-nav{position:static}.tm-nav ul{display:flex;flex-wrap:wrap;gap:6px}.tm-nav li a{border:1px solid var(--line);border-radius:999px;padding:4px 10px}.tm-nav h4{margin:8px 0 4px}}
@media(max-width:640px){.tm-nrow{grid-template-columns:auto minmax(0,1fr);align-items:start}.tm-nrow time{grid-column:2}.tm-nrow button{grid-column:2;justify-self:start}.tm-grid{grid-template-columns:minmax(0,1fr)}.tm-head h2,.tm-thead h2{font-size:19px}}
</style>
<div id="tm-app">
<div id="tv-board" hidden>
 <div class="tm-head"><div><h2>Digital teams</h2><p class="tm-sum" id="tb-sum"></p></div>
  <div class="tm-acts"><button type="button" class="secondary" id="tb-templates">Team templates</button><button type="button" id="tb-new">+ New team</button></div></div>
 <div id="tb-newpanel" class="tm-panel" hidden></div>
 <div id="tb-needs"></div>
 <div class="tm-ctl" role="group" aria-label="Find and arrange teams">
  <input type="search" id="tb-q" placeholder="Find a team, member role or job" aria-label="Find a team, member role or job" maxlength="80">
  <div class="rl-chips" id="tb-chips" role="group" aria-label="Show"></div>
  <label>Group by <select id="tb-group" aria-label="Group teams by"></select></label>
  <div class="tm-seg" role="group" aria-label="View"><button type="button" class="ghost" id="tb-cards" aria-pressed="true">Cards</button><button type="button" class="ghost" id="tb-list" aria-pressed="false">List</button></div>
 </div>
 <div id="tb-groups" aria-live="polite"></div>
</div>
<div id="tv-split" class="tm-split" hidden>
 <aside class="tm-nav" id="tm-nav" aria-label="Teams"></aside>
 <div id="tm-main" class="tm-mainview"></div>
</div>
</div>'''

SCRIPT = r"""
if(PAGE==='teams'){
 const P=location.pathname.replace(/\/+$/,'').split('/');            // ['', 'admin', 'teams', id?, 'jobs'?, job?]
 const V={tid:P[3]?decodeURIComponent(P[3]):'',jid:P[4]==='jobs'&&P[5]?P[5]:'',d:null,timer:null,icons:{}};
 // ---------- small helpers ----------
 const h=(tag,a,...kids)=>{const e=document.createElement(tag);if(a)for(const [k,v] of Object.entries(a)){if(v==null||v===false)continue;if(k==='class')e.className=v;else if(k==='text')e.textContent=v;else if(k.startsWith('on'))e[k]=v;else if(k==='style')e.style.cssText=v;else e.setAttribute(k,v===true?'':v)}
  for(const c of kids.flat()){if(c==null||c===false)continue;e.append(c.nodeType?c:document.createTextNode(String(c)))}return e};
 const enc=encodeURIComponent;
 const gbp=v=>v==null?'':'£'+Number(v).toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
 const qty=v=>v==null?'':Number(v).toLocaleString('en-GB',{maximumFractionDigits:3});
 const when=iso=>{const d=new Date(iso);return isNaN(d)?'':d.toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})};
 const ago=iso=>{const d=new Date(iso);if(!iso||isNaN(d))return '';const s=(Date.now()-d)/1000;if(s<60)return 'just now';if(s<3600)return Math.floor(s/60)+' min ago';if(s<86400)return Math.floor(s/3600)+' h ago';if(s<86400*7)return Math.floor(s/86400)+' d ago';return d.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})};
 const tm=iso=>h('time',{datetime:iso,title:when(iso)},ago(iso));
 const plural=(n,w,ws)=>n+' '+(n===1?w:(ws||w+'s'));
 const btn=(label,fn,cls)=>{const x=h('button',{type:'button',class:cls||''},label);x.onclick=()=>run(async()=>{x.disabled=true;try{await fn()}finally{x.disabled=false}});return x};
 const store={get(k,d){try{const v=JSON.parse(localStorage.getItem('alice-teams-'+k));return v==null?d:v}catch{return d}},set(k,v){try{localStorage.setItem('alice-teams-'+k,JSON.stringify(v))}catch{}}};
 function mark(hex,icon,size,label){const m=h('span',{class:'tm-mark'+(size?' '+size:''),style:'background:'+hex,role:label?'img':null,'aria-label':label||null,'aria-hidden':label?null:'true'});
  m.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+(V.icons[icon]||V.icons.people||'')+'</svg>';return m}
 const pill=(status,label)=>h('span',{class:'tm-pill s-'+status},label);
 function avatar(initials,role,lead,hex,cls){const a=h('span',{class:'tm-av'+(lead?' lead':'')+(cls?' '+cls:''),title:role+(lead?' (lead)':''),role:'img','aria-label':role+(lead?', the lead':'')},initials);if(lead&&hex)a.style.boxShadow='0 0 0 2px #fff,0 0 0 4px '+hex;return a}
 const STATE_WORD={done:'done',current:'working now',waiting:'waiting for you',todo:'to come',blocked:'stopped by a failure',stopped:'stopped'};
 function progBar(prog){const n=prog.length;const cur=prog.findIndex(p=>p.state!=='done');const at=cur<0?n:cur+1;const p=prog[cur]||prog[n-1];
  const bar=h('div',{class:'tm-prog',role:'img','aria-label':'Stage '+Math.min(at,n)+' of '+n+': '+p.title+', '+STATE_WORD[p.state]});
  for(const s of prog)bar.append(h('span',{class:s.state,title:s.title+(s.role&&s.role!=='You'?' · '+s.role:'')+': '+STATE_WORD[s.state]}));return bar}
 const scroller=()=>document.querySelector('.content')||document.scrollingElement;
 const keepScroll=fn=>{const sc=scroller(),y=sc?sc.scrollTop:0,wy=window.scrollY;fn();if(sc)sc.scrollTop=y;window.scrollTo(0,wy)};
 const whereLine=w=>h('div',{class:'tm-where'+(/^Waiting for|^Stopped/.test(w)?' w':'')},w);
 function setIconsFrom(d){if(d&&d.icons)for(const [k,v] of Object.entries(d.icons))V.icons[k]=typeof v==='string'?v:v.svg}
 // ---------- Needs you rows (all teams, and a team's own) ----------
 function needsBox(items,title){if(!items.length)return null;const box=h('section',{class:'tm-needs','aria-labelledby':'tm-needs-h'});
  box.append(h('h3',{id:'tm-needs-h'},title||'Needs you',h('span',{class:'n'},String(items.length))));
  for(const i of items){const who=h('div',{class:'t'});
   if(i.team_id)who.append(h('a',{href:'/admin/teams/'+enc(i.team_id)},i.team));else who.append(h('b',null,i.team));
   if(i.job_ref)who.append(' › ',h('a',{href:i.href},i.job_ref+' '+i.job_title));
   const go=i.resume?btn('Resume',async()=>{await api('/admin/api/teams/jobs/'+i.resume+'/resume','POST',{});$('notice').textContent=i.job_ref+' resumed.';await reload()}):h('a',{class:'button',href:i.href},i.action);
   box.append(h('div',{class:'tm-nrow'},mark(i.hex,i.icon,'sm'),h('div',null,who,h('div',{class:'s'},i.text)),i.at?tm(i.at):h('span'),go))}
  return box}
 async function reload(){if(V.jid)await loadJob();else if(V.tid)await loadTeam();else await loadBoard()}
 // ---------- Screen 1: all teams ----------
 const B={status:store.get('status','all'),group:store.get('group','discipline'),view:store.get('view','cards'),q:''};
 async function loadBoard(){const d=await api('/admin/api/teams/board');V.d=d;setIconsFrom(d);drawBoard()}
 function drawBoard(){const d=V.d,s=d.summary;$('tv-board').hidden=false;
  $('tb-sum').textContent=[plural(s.teams,'team'),plural(s.members,'member'),plural(s.running,'job')+' running',(s.needs_you?s.needs_you+' need'+(s.needs_you===1?'s':'')+' you':'nothing needs you')].join(' · ');
  $('tb-needs').replaceChildren(...[needsBox(d.needs)].filter(Boolean));
  const counts={all:d.teams.length,needs:d.teams.filter(t=>t.needs_you).length,running:d.teams.filter(t=>t.status==='running').length,idle:d.teams.filter(t=>t.status==='idle').length,draft:d.teams.filter(t=>t.status==='draft').length};
  filterChips($('tb-chips'),[['all','All',counts.all],['needs','Needs you',counts.needs],['running','Running',counts.running],['idle','Idle',counts.idle],['draft','Drafts',counts.draft]],B.status,k=>{B.status=k;store.set('status',k);drawBoard()});
  const gs=$('tb-group');const opts=[['discipline','Discipline'],['status','Status'],['none','None']];if(!opts.some(o=>o[0]===B.group))B.group='discipline';
  gs.replaceChildren(...opts.map(([k,l])=>{const o=h('option',{value:k},l);return o}));gs.value=B.group;
  $('tb-cards').setAttribute('aria-pressed',B.view==='cards');$('tb-list').setAttribute('aria-pressed',B.view==='list');drawTeams()}
 function drawTeams(){const d=V.d;const q=B.q.trim().toLowerCase();
  const pass=t=>(B.status==='all'||(B.status==='needs'?t.needs_you:t.status===B.status))&&(!q||q.split(/\s+/).every(w=>t.search.includes(w)));
  const list=d.teams.filter(pass);const box=$('tb-groups');box.replaceChildren();
  if(!d.teams.length){box.append(h('div',{class:'tm-panel'},h('p',{class:'tm-empty'},'No teams yet. Start one with + New team, or from a template.')));return}
  if(!list.length){box.append(h('p',{class:'tm-empty'},'No team matches. Clear the search or choose All.'));return}
  const SORD=['needs_you','paused','running','idle','draft'];
  const key=t=>B.group==='discipline'?(t.discipline||'No discipline yet'):B.group==='status'?t.status_label:'';
  const groups=new Map();for(const t of list){const k=key(t);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(t)}
  let names=[...groups.keys()];if(B.group==='status')names.sort((a,b)=>SORD.indexOf(groups.get(a)[0].status)-SORD.indexOf(groups.get(b)[0].status));else names.sort((a,b)=>(a==='No discipline yet')-(b==='No discipline yet')||a.localeCompare(b));
  for(const g of names){const ts=groups.get(g).sort((a,b)=>(b.needs_you-a.needs_you)||a.name.localeCompare(b.name));const sec=h('section',{class:'tm-group','aria-label':g||'Teams'});
   if(g)sec.append(h('h3',null,g,h('span',{class:'c'},plural(ts.length,'team'))));
   sec.append(B.view==='list'?teamTable(ts):h('div',{class:'tm-grid'},ts.map(teamCard)));box.append(sec)}}
 function teamCard(t){const c=h('article',{class:'tm-card'+(t.status==='draft'?' draft':'')});
  c.append(h('div',{class:'top'},mark(t.hex,t.icon),h('div',{class:'nm'},h('h4',null,h('a',{href:t.href},t.name)),h('div',{class:'meta'},[plural(t.members.length,'member'),t.autonomy_label].filter(Boolean).join(' · '))),pill(t.status,t.status_label)));
  if(t.description)c.append(h('p',{class:'purpose',title:t.description},t.description));
  if(t.members.length)c.append(h('div',{class:'tm-avs'},t.members.map(m=>avatar(m.initials,m.role,m.lead,t.hex))));
  if(t.status==='draft')c.append(h('div',{class:'missing'},h('b',null,'Not ready to run: '),t.missing.join(' · ')));
  if(t.job){c.append(h('div',{class:'live'},progBar(t.job.progress),h('a',{href:t.job.href},t.job.ref+' '+t.job.title),whereLine(t.job.where)))}
  c.append(h('div',{class:'foot'},h('span',null,plural(t.running,'job')+' running · '+t.done+' done'),t.last_activity?h('span',null,'Last activity ',tm(t.last_activity)):null));return c}
 function teamTable(ts){const wrap=h('div',{class:'table-wrap'});const tb=h('table',{class:'tm-list'});
  tb.append(h('thead',null,h('tr',null,['Team','Members','Autonomy','Status','Live job','Last activity'].map(x=>h('th',{scope:'col'},x)))));const body=h('tbody');
  for(const t of ts)body.append(h('tr',null,h('td',null,h('div',{class:'tn'},mark(t.hex,t.icon,'sm'),h('a',{href:t.href},t.name))),h('td',null,String(t.members.length)),h('td',null,t.autonomy_label),
   h('td',null,pill(t.status,t.status_label)),h('td',null,t.job?h('a',{href:t.job.href},t.job.ref):'—'),h('td',null,t.last_activity?tm(t.last_activity):'')));
  tb.append(body);wrap.append(tb);return wrap}
 // ---------- new team (blank or from a template), and editing a team's name, mark and discipline ----------
 function swatches(name,legend,opts,cur){const fs=h('fieldset',null,h('legend',null,legend));const row=h('div',{class:'tm-swatches'});
  for(const [k,o] of Object.entries(opts)){const inp=h('input',{type:'radio',name,value:k});inp.checked=k===cur;const lab=h('label',{title:o.name});
   if(o.hex)lab.append(inp,h('span',{class:'sw',style:'background:'+o.hex}),o.name);else{lab.append(inp,mark('#4b5a66',k,'sm'),o.name)}row.append(lab)}fs.append(row);fs.value=()=>{const x=fs.querySelector('input:checked');return x?x.value:''};return fs}
 function disciplineInput(v,list){const id='tm-disc-'+Math.random().toString(36).slice(2,8);const inp=h('input',{type:'text',maxlength:'60',list:id,placeholder:'e.g. Quantity surveying',value:v||''});const dl=h('datalist',{id});for(const x of list||[])dl.append(h('option',{value:x}));const w=h('span');w.append(inp,dl);w.input=inp;return w}
 function newTeamPanel(fromTemplates){const d=V.d,box=$('tb-newpanel');box.hidden=false;box.replaceChildren();const f=h('form',{class:'tm-form'});
  const tmpl=h('fieldset',null,h('legend',null,'Start from'));const tl=h('div',{class:'tm-tmpl'});const pick=(k)=>{const t=d.templates.find(x=>x.key===k);if(t){name.value=name.value||t.name;disc.input.value=t.discipline;const c=colours.querySelector('input[value="'+t.colour+'"]');if(c)c.checked=true;const i=icons.querySelector('input[value="'+t.icon+'"]');if(i)i.checked=true}};
  const opt=(k,title,desc)=>{const r=h('input',{type:'radio',name:'tm-from',value:k});r.checked=k===(fromTemplates&&d.templates[0]?d.templates[0].key:'');r.onchange=()=>pick(k);return h('label',null,r,h('span',null,h('b',null,title),h('span',{class:'small muted'},desc)))};
  tl.append(opt('','A blank team','Name it, then add members and a job type.'));for(const t of d.templates)tl.append(opt(t.key,'Template: '+t.name,t.description+' Members: '+t.members.join(', ')+'.'));tmpl.append(tl);
  const name=h('input',{type:'text',maxlength:'80',required:true,placeholder:'e.g. Bid team'}),disc=disciplineInput('',d.disciplines),desc=h('textarea',{maxlength:'600',rows:'2',placeholder:'What the team is for, in a sentence'});
  const colours=swatches('tm-colour','Colour',d.colours,Object.keys(d.colours)[0]),icons=swatches('tm-icon','Icon',d.icons,'people');
  const go=h('button',{type:'submit'},'Create the team'),cancel=h('button',{type:'button',class:'secondary'},'Cancel');cancel.onclick=()=>{box.hidden=true};
  f.append(h('h3',null,fromTemplates?'Team templates':'New team'),tmpl,h('div',{class:'row'},h('label',null,'Name',name),h('label',null,'Discipline',disc)),h('label',null,'Purpose (optional)',desc),colours,icons,h('div',{class:'tm-acts'},go,cancel));
  f.onsubmit=e=>{e.preventDefault();run(async()=>{go.disabled=true;try{const from=(f.querySelector('input[name=tm-from]:checked')||{}).value||'';
   const t=await api('/admin/api/teams','POST',{name:name.value,description:desc.value,discipline:disc.input.value,colour:colours.value(),icon:icons.value(),template:from});
   location.href='/admin/teams/'+enc(t.id)+(from?'#overview':'#members')}finally{go.disabled=false}})};
  box.append(f);if(fromTemplates&&d.templates[0])pick(d.templates[0].key);box.scrollIntoView({block:'nearest'});name.focus()}
 // ---------- the left team menu (team and job pages) ----------
 function drawNav(nav,current){const box=$('tm-nav');box.replaceChildren(h('a',{class:'back',href:'/admin/teams'},'‹ All teams'));
  const list=(title,rows,empty)=>{box.append(h('h4',null,title));if(!rows.length){box.append(h('p',{class:'empty'},empty));return}const ul=h('ul');
   for(const r of rows){const a=h('a',{href:r.href,'aria-current':r.id===current?'page':null,title:r.name+' · '+r.status_label},mark(r.hex,r.icon,'sm'),h('span',{class:'n'},r.name));if(r.needs_you)a.append(h('span',{class:'tm-dot',title:'Needs you'}),h('span',{class:'tm-sr'},'(needs you)'));ul.append(h('li',null,a))}box.append(ul)};
  list('Pinned',nav.pins,'Pin a team from its page to keep it here.');list('Recent',nav.recent,'Teams you open appear here.')}
 // ---------- Screen 2: a team ----------
 const TABS=[['overview','Overview'],['jobs','Jobs'],['members','Members'],['knowledge','Knowledge'],['rules','Rules and autonomy'],['activity','Activity']];
 let tab=(location.hash||'').slice(1);if(!TABS.some(t=>t[0]===tab))tab='overview';
 const T={docs:[],lib:null,startOpen:false,editOpen:false,talkOpen:false};
 async function loadTeam(poll){const d=await api('/admin/api/teams/'+enc(V.tid)+'/page');V.d=d;setIconsFrom(d);
  const typing=T.editOpen||(tab==='jobs'&&T.startOpen)||['members','knowledge','rules'].includes(tab);if(!poll||!typing)drawTeam();     // a refresh never wipes a form you are filling in
  clearTimeout(V.timer);if(d.jobs.some(j=>j.status==='running'))V.timer=setTimeout(()=>run(()=>loadTeam(true)),3000)}
 function teamHead(){const d=V.d,t=d.team,idn=d.identity;const head=h('div',{class:'tm-thead'});
  const chips=h('div',{class:'tm-chips'},h('a',{class:'tm-chip',href:'#rules',onclick:()=>setTab('rules')},d.autonomy[t.autonomy]),...d.chips.map(c=>h('a',{class:'tm-chip'+(c.off?' off':''),href:c.href},c.label)),idn.discipline?h('span',{class:'tm-chip'},idn.discipline):null,pill(d.status,d.status_label));
  const pin=btn(d.pinned?'Unpin':'Pin',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/pin','PUT',{on:!d.pinned});d.pinned=!d.pinned;await loadTeam()},'secondary');pin.setAttribute('aria-pressed',d.pinned);pin.title=d.pinned?'Remove from Pinned teams':'Keep this team in Pinned teams';
  const edit=h('button',{type:'button',class:'secondary','aria-expanded':T.editOpen},'Edit team');edit.onclick=()=>{T.editOpen=!T.editOpen;drawTeam()};
  const ask=h('button',{type:'button',class:'secondary','aria-expanded':T.talkOpen},'Ask the team');ask.onclick=()=>{T.talkOpen=!T.talkOpen;drawTeam()};
  const start=h('button',{type:'button'},'Start a job');start.onclick=()=>{T.startOpen=true;setTab('jobs');setTimeout(()=>{const x=$('tm-start');if(x){x.scrollIntoView({block:'start'});const f=x.querySelector('select,input');if(f)f.focus()}},0)};
  head.append(mark(idn.hex,idn.icon,'lg'),h('div',{class:'nm'},h('h2',null,t.name),t.description?h('p',null,t.description):null,chips),h('div',{class:'tm-acts'},pin,edit,ask,start));return head}
 function editPanel(){const d=V.d,t=d.team,idn=d.identity;const f=h('form',{class:'tm-form tm-panel'});const name=h('input',{type:'text',maxlength:'80',value:t.name,required:true}),disc=disciplineInput(idn.discipline,d.disciplines),desc=h('textarea',{maxlength:'600',rows:'2'});desc.value=t.description||'';
  const colours=swatches('tm-ecolour','Colour',d.colours,idn.colour),icons=swatches('tm-eicon','Icon',d.icons,idn.icon);const save=h('button',{type:'submit'},'Save'),cancel=h('button',{type:'button',class:'secondary'},'Cancel');cancel.onclick=()=>{T.editOpen=false;drawTeam()};
  f.append(h('h3',null,'Edit team'),h('div',{class:'row'},h('label',null,'Name',name),h('label',null,'Discipline',disc)),h('label',null,'Purpose',desc),colours,icons,h('p',{class:'small muted'},'Saved as a new team version.'),h('div',{class:'tm-acts'},save,cancel));
  f.onsubmit=e=>{e.preventDefault();run(async()=>{save.disabled=true;try{await api('/admin/api/teams/'+enc(t.id)+'/identity','PUT',{name:name.value,description:desc.value,discipline:disc.input.value,colour:colours.value(),icon:icons.value()});T.editOpen=false;$('notice').textContent='Saved as a new team version.';await loadTeam()}finally{save.disabled=false}})};return f}
 function setTab(k){tab=k;try{window.history.replaceState(null,'','#'+k)}catch{}drawTeam();const tb=document.querySelector('.tm-tabs [aria-selected=true]');if(tb)tb.focus({preventScroll:true})}
 function drawTeam(){keepScroll(drawTeamNow)}
 function drawTeamNow(){const d=V.d,t=d.team;$('tv-split').hidden=false;drawNav(d.nav,t.id);const main=$('tm-main');main.replaceChildren();
  main.append(teamHead());if(T.editOpen)main.append(editPanel());if(T.talkOpen)main.append(h('section',{class:'tm-panel'},h('h3',null,'Ask the team'),h('p',{class:'small muted'},'Your message goes to '+leadRole()+', the lead, who answers for the team. It cannot approve or change anything.'),talkPanel(t.id,'')));
  const nb=needsBox(d.needs,'Needs you in this team');if(nb)main.append(nb);
  const counts={jobs:d.jobs.length,members:t.members.length};const tabs=h('div',{class:'tm-tabs',role:'tablist','aria-label':'Team'});
  for(const [k,l] of TABS){const b=h('button',{type:'button',class:'ghost',role:'tab',id:'tm-tab-'+k,'aria-selected':String(k===tab),'aria-controls':'tm-panel-'+k,tabindex:k===tab?'0':'-1'},l,counts[k]!=null?h('span',{class:'n'},String(counts[k])):null);b.onclick=()=>setTab(k);
   b.onkeydown=e=>{const i=TABS.findIndex(x=>x[0]===k);if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();setTab(TABS[(i+(e.key==='ArrowRight'?1:TABS.length-1))%TABS.length][0])}};tabs.append(b)}
  main.append(tabs);const panel=h('div',{role:'tabpanel',id:'tm-panel-'+tab,'aria-labelledby':'tm-tab-'+tab});main.append(panel);
  ({overview:drawOverview,jobs:drawJobsTab,members:drawMembersTab,knowledge:drawKnowledgeTab,rules:drawRulesTab,activity:drawActivityTab}[tab])(panel)}
 const leadRole=()=>{const d=V.d;return (d.team.members.find(m=>m.id===d.lead)||{role:'the lead'}).role};
 function memberCard(m,lead){const d=V.d,st=d.member_states[m.id]||{state:'idle',label:'Idle'};const c=h('div',{class:'tm-mcard'+(lead?' lead':'')});if(lead)c.style.borderColor=d.identity.hex;
  const init=(m.role.match(/[A-Za-z0-9]+/g)||['?']).slice(0,2).map(w=>w[0]).join('').toUpperCase();
  c.append(h('div',{class:'r'},avatar(init,m.role,lead,d.identity.hex,'lg'),h('div',null,h('b',null,m.role),lead?h('div',{class:'k'},'Lead'):null)));
  if(m.purpose)c.append(h('div',{class:'p'},m.purpose));
  const tools=d.member_tools[m.id]||[];c.append(h('div',{class:'k'},(d.models[m.provider]||m.provider)+(tools.length?' · '+tools.join(', '):'')));
  if((m.categories||[]).length)c.append(h('div',{class:'tm-cats','aria-label':'Knowledge categories'},m.categories.map(x=>h('span',null,x))));
  else c.append(h('div',null,h('a',{class:'tm-chip warn',href:'#knowledge',onclick:e=>{e.preventDefault();setTab('knowledge')}},'No knowledge ticked: add')));
  c.append(h('div',{class:'tm-state '+st.state},st.label));return c}
 function drawOverview(p){const d=V.d,t=d.team;const cols=h('div',{class:'tm-cols'});const left=h('div'),side=h('div',{class:'tm-side'});cols.append(left,side);p.append(cols);
  const how=h('section',{class:'tm-panel tm-how','aria-labelledby':'tm-how-h'},h('h3',{id:'tm-how-h'},'How the team works'));
  if(!t.members.length)how.append(h('p',{class:'tm-empty'},'No members yet. Add them on the Members tab.'));
  else{const lead=t.members.find(m=>m.id===d.lead)||t.members[0];how.append(h('div',{class:'lead-wrap'},memberCard(lead,true)));const rest=t.members.filter(m=>m!==lead);
   if(rest.length){how.append(h('div',{class:'tm-conn','aria-hidden':'true'}),h('div',{class:'tm-mrow'},rest.map(m=>memberCard(m,false))))}}
  if(d.readiness.missing.length)how.append(h('p',{class:'small'},h('b',null,'Not ready to run: '),d.readiness.missing.join(' · ')));
  left.append(how);
  for(const pr of d.pricing){const s=h('section',{class:'tm-panel','aria-labelledby':'tm-price-h'},h('h3',{id:'tm-price-h'},'Where prices come from'),h('p',{class:'small muted'},pr.role+' prices each item in this order ('+pr.stage+'):'));
   const ol=h('ol',{class:'tm-ol'});for(const o of pr.order)ol.append(h('li',null,h('b',null,o.title),h('span',{class:'small'},o.detail)));s.append(ol);if(pr.note)s.append(h('p',{class:'small'},pr.note));
   const links=h('p',{class:'small'},'Related rules: ');pr.rules.forEach((r,i)=>{if(i)links.append(', ');links.append(h('a',{href:r.href},r.name+(r.on?'':' (switched off)')))});links.append(pr.rules.length?' · ':'',h('a',{href:'/admin/rules#rules'},'Open the Rules page'));s.append(links);left.append(s)}
  // right: jobs and rules
  const jp=h('section',{class:'tm-panel','aria-labelledby':'tm-jobs-h'},h('h3',{id:'tm-jobs-h'},'Jobs',d.jobs.length?h('a',{href:'#jobs',onclick:e=>{e.preventDefault();setTab('jobs')}},'See all'):null));
  const hot=d.jobs.find(j=>j.pending.length||j.status==='blocked');
  if(hot)jp.append(jobRow(hot,true));for(const j of d.jobs.filter(j=>j!==hot).slice(0,5))jp.append(jobRow(j,false));
  if(!d.jobs.length)jp.append(h('p',{class:'tm-empty'},'No jobs yet.'));side.append(jp,rulesPanel(false))}
 function jobRow(j,hl){const r=h('div',{class:'tm-jrow'+(hl?' hl':'')});const st=j.pending.length||j.status==='blocked'?['needs_you',j.status==='blocked'?'Stopped':'Needs you']:j.status==='done'?['done','Signed off']:j.status==='stopped'?['stopped','Stopped']:['running','Running'];
  r.append(h('div',{class:'l'},h('a',{href:'/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id},j.ref+' '+j.title),pill(st[0],st[1])));
  if(!['done','stopped'].includes(j.status))r.append(progBar(j.progress),whereLine(j.where));else r.append(h('div',{class:'small muted'},j.job_type_name+' · '+when(j.updated_at)));
  if(hl)r.append(h('div',null,h('a',{class:'button',href:'/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id},j.status==='blocked'?'Open':'Review')));return r}
 function rulesPanel(full){const d=V.d,R=d.rules;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-rules-h'+(full?'f':'')},h('h3',{id:'tm-rules-h'+(full?'f':'')},'Rules this team follows',h('a',{href:'/admin/rules#rules'},'Rules page')));
  const ul=h('ul',{class:'tm-rules'});for(const r of R.rules){ul.append(h('li',null,h('span',{class:'tm-tick'+(r.on?'':' off'),'aria-hidden':'true'},r.on?'✓':'✕'),h('div',null,h('a',{href:r.href},r.name),h('span',{class:'tm-sr'},r.on?' (on)':' (switched off)'),r.on?null:h('b',{class:'small'},' Switched off'),h('div',{class:'u'},r.use),full&&r.description?h('div',{class:'small'},r.description):null)))}
  s.append(ul);if(R.applied_packs.length)s.append(h('p',{class:'small'},'Rule packs applied to every model call: ',...R.applied_packs.map((x,i)=>[i?', ':'',h('a',{href:x.href},x.name)])));
  for(const m of R.member_packs)if(m.packs.length)s.append(h('p',{class:'small'},m.member+'’s own rule packs: '+m.packs.join(', ')));return s}
 // ---- Jobs tab: start a job, all jobs ----
 function drawJobsTab(p){const d=V.d,t=d.team;const sp=h('section',{class:'tm-panel',id:'tm-start'});const toggle=h('button',{type:'button',class:T.startOpen?'secondary':'','aria-expanded':T.startOpen},T.startOpen?'Close':'Start a job');toggle.onclick=()=>{T.startOpen=!T.startOpen;drawTeam()};
  sp.append(h('div',{class:'tm-head',style:'margin:0'},h('h3',{style:'margin:0'},'Start a job'),toggle));if(T.startOpen)sp.append(startForm());p.append(sp);
  const list=h('section',{class:'tm-panel'},h('h3',null,'All jobs'));if(!d.jobs.length)list.append(h('p',{class:'tm-empty'},'No jobs yet.'));
  else{const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-list'});tb.append(h('thead',null,h('tr',null,['Job','Status','Where it is','Started','AI cost'].map(x=>h('th',{scope:'col'},x)))));const body=h('tbody');
   for(const j of d.jobs){const st=j.pending.length?['needs_you','Needs you']:j.status==='blocked'?['blocked','Stopped']:j.status==='done'?['done','Signed off']:j.status==='stopped'?['stopped','Stopped']:['running','Running'];
    body.append(h('tr',null,h('td',null,h('a',{href:'/admin/teams/'+enc(t.id)+'/jobs/'+j.id},j.ref+' '+j.title),h('div',{class:'small muted'},j.job_type_name+' · team v'+j.team_version)),h('td',null,pill(st[0],st[1])),
     h('td',{style:'min-width:200px'},['done','stopped'].includes(j.status)?j.where:[progBar(j.progress),whereLine(j.where)]),h('td',null,when(j.created_at)),h('td',{class:'num'},'$'+(j.ai_cost||0).toFixed(2))))}
   tb.append(body);wrap.append(tb);list.append(wrap)}p.append(list)}
 function startForm(){const d=V.d,t=d.team;const f=h('div',{class:'tm-form'});if(!t.job_types.length){f.append(h('p',{class:'tm-empty'},'Add a job type on the Rules and autonomy tab first.'));return f}
  const jt=h('select');for(const x of t.job_types)jt.append(h('option',{value:x.id},x.name+(x.description?' · '+x.description:'')));
  const title=h('input',{type:'text',maxlength:'150',placeholder:'e.g. New community hall, early cost estimate'}),brief=h('textarea',{maxlength:'20000',rows:'4',placeholder:'What is wanted, in a few sentences.'});
  const loc=h('input',{type:'text',maxlength:'120',placeholder:'e.g. Perth, Scotland'}),client=h('input',{type:'text',maxlength:'80',placeholder:'An organisation marked Client keeps the job to its own material'});
  const files=h('input',{type:'file',multiple:true,accept:'.pdf,.docx,.xlsx,.csv,.txt,.md','aria-label':'Upload documents'}),lib=h('select',{'aria-label':'Pick from the document sources'},h('option',{value:''},'Or pick from the document sources…')),add=h('button',{type:'button',class:'secondary'},'Add');
  const docs=h('div',{class:'tm-docs'}),note=h('span',{class:'small muted'});
  const guess=n=>/draw|plan|elevation|section|\.dwg/i.test(n)?'drawing':/schedule|\.csv|\.xlsx/i.test(n)?'schedule':/spec/i.test(n)?'spec':'brief';
  const drawDocs=()=>{docs.replaceChildren(...T.docs.map((x,i)=>{const k=h('select',{'aria-label':'What '+x.name+' is'});for(const [kk,l] of Object.entries(d.doc_kinds))k.append(h('option',{value:kk},l));k.value=x.kind;k.onchange=()=>{x.kind=k.value};
   const rm=h('button',{type:'button',class:'secondary'},'Remove');rm.onclick=()=>{T.docs.splice(i,1);drawDocs()};return h('div',{class:'tm-doc'},h('span',null,(x.path?'📁 ':'📄 ')+x.name),k,rm)}));note.textContent=T.docs.length?plural(T.docs.length,'document'):'Add the specification, schedules and drawings.'};
  files.onchange=()=>run(async()=>{for(const fl of files.files){if(fl.size>15*1024*1024)throw Error(fl.name+' is larger than 15 MB.');const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(Error('Could not read '+fl.name));r.readAsDataURL(fl)});T.docs.push({name:fl.name,kind:guess(fl.name),data})}files.value='';drawDocs()});
  add.onclick=()=>{const v=lib.value;if(!v)return;if(!T.docs.some(x=>x.path===v))T.docs.push({name:v.split('/').pop(),kind:guess(v),path:v});lib.value='';drawDocs()};
  run(async()=>{if(!T.lib)T.lib=(await api('/admin/api/teams/library-files')).files;for(const x of T.lib)lib.append(h('option',{value:x.path},x.source+' › '+x.path))});
  const demo=h('button',{type:'button',class:'secondary'},'Load the demo project (fictional)');demo.onclick=()=>run(async()=>{const x=await api('/admin/api/teams/demo-project');title.value=x.title;brief.value=x.brief;loc.value=x.location;client.value='';T.docs=x.documents.map(y=>({name:y.name,kind:y.kind,text:y.text}));drawDocs();$('notice').textContent='Demo project loaded (fictional). Load the fictional demo rate library on the Knowledge tab too, then Start the job.'});
  const go=h('button',{type:'button'},'Start the job');go.onclick=()=>run(async()=>{go.disabled=true;try{const body={job_type:jt.value,title:title.value,brief:brief.value,location:loc.value,client:client.value,
   uploads:T.docs.filter(x=>!x.path).map(x=>({name:x.name,kind:x.kind,...(x.text!=null?{text:x.text}:{data:x.data})})),library:T.docs.filter(x=>x.path).map(x=>({path:x.path,kind:x.kind}))};
   const j=await api('/admin/api/teams/'+enc(t.id)+'/jobs','POST',body);T.docs=[];location.href='/admin/teams/'+enc(t.id)+'/jobs/'+j.id}finally{go.disabled=false}});
  f.append(h('label',null,'Job type',jt),h('label',null,'Title',title),h('label',null,'Brief',brief),h('div',{class:'row'},h('label',null,'Location (optional)',loc),h('label',null,'Client (optional)',client)),
   h('div',null,h('b',null,'Documents'),h('p',{class:'small muted'},'Uploaded documents are checked for secrets and protective markings and kept with the job; documents picked from a document source stay there and are read at each turn.'),h('div',{class:'tm-acts'},files,lib,add),docs),
   h('div',{class:'tm-acts'},go,demo,note));drawDocs();return f}
 // ---- Members tab ----
 function checks(all,on){const w=h('div',{class:'tm-checks'});const boxes=[];for(const [k,l] of all){const c=h('input',{type:'checkbox',value:k});c.checked=on.includes(k);boxes.push(c);w.append(h('label',null,c,l))}w.values=()=>boxes.filter(c=>c.checked).map(c=>c.value);return w}
 const field=(label,node)=>h('label',null,label,node);
 function suggBox(s){const w=h('div',{class:'tm-sugg'},h('strong',null,'Temple suggests new instructions'+(s.role?' for '+s.role:'')),h('p',{class:'small'},s.reason));
  w.append(h('details',null,h('summary',null,'Current instructions'),h('pre',null,s.current_text)),h('div',{class:'small'},'Suggested instructions'),h('pre',null,s.proposed));
  w.append(h('div',{class:'tm-acts'},btn('Approve: use these',async()=>{await api('/admin/api/teams/suggestions/'+s.id,'POST',{action:'approve'});$('notice').textContent='Applied as a new team version.';await loadTeam()}),btn('Reject',async()=>{await api('/admin/api/teams/suggestions/'+s.id,'POST',{action:'reject'});await loadTeam()},'secondary')));return w}
 function drawMembersTab(p){const d=V.d,t=d.team;const top=h('div',{class:'tm-head'},h('p',{class:'small muted',style:'margin:0'},'Each member’s role, model and standing instructions. Knowledge categories are on the Knowledge tab.'),btn('Add a member',async()=>{const role=prompt('Role name for the new member, e.g. Services Engineer');if(!role||!role.trim())return;await api('/admin/api/teams/'+enc(t.id)+'/members','POST',{role,provider:'claude_sonnet',purpose:'',instructions:''});$('notice').textContent=role+' added. Give them a purpose and instructions, then a stage on Rules and autonomy.';await loadTeam()},'secondary'));p.append(top);
  for(const s of d.suggestions.filter(s=>!t.members.some(m=>m.id===s.member)))p.append(suggBox(s));
  for(const m of t.members){const c=h('div',{class:'tm-mem'});c.append(h('h3',null,avatar((m.role.match(/[A-Za-z0-9]+/g)||['?']).slice(0,2).map(w=>w[0]).join('').toUpperCase(),m.role,m.id===d.lead,d.identity.hex),m.role,m.id===d.lead?h('span',{class:'tm-chip'},'Lead'):null));
   const role=h('input',{type:'text',maxlength:'80',value:m.role}),purpose=h('textarea',{maxlength:'600',rows:'2'}),ins=h('textarea',{maxlength:'6000',class:'ins'}),prov=h('select');purpose.value=m.purpose||'';ins.value=m.instructions||'';
   for(const [k,l] of Object.entries(d.models))prov.append(h('option',{value:k},l));prov.value=m.provider;const packs=checks(Object.entries(d.packs),m.packs||[]);
   c.append(h('div',{class:'grid'},field('Role name',role),field('Model',prov)),field('Purpose',purpose),field('Standing instructions',ins),field('Its own rule packs',packs));
   const used=t.job_types.flatMap(jt=>jt.stages.filter(s=>s.member===m.id).map(s=>jt.name+' › '+s.title));if(used.length)c.append(h('p',{class:'small muted'},'Works on: '+used.join(', ')));
   c.append(h('div',{class:'tm-acts'},btn('Save',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/members/'+enc(m.id),'PUT',{role:role.value,purpose:purpose.value,instructions:ins.value,provider:prov.value,packs:packs.values()});$('notice').textContent='Saved as a new team version.';await loadTeam()}),
    btn('Remove',async()=>{if(!confirm('Remove '+m.role+' from the team? (You can undo it on the Activity tab.)'))return;await api('/admin/api/teams/'+enc(t.id)+'/members/'+enc(m.id),'DELETE');await loadTeam()},'secondary')));
   for(const s of d.suggestions.filter(s=>s.member===m.id))c.append(suggBox(s));c.append(coachTalk(m));p.append(c)}}
 function coachTalk(m){const t=V.d.team;const wrap=h('details',{class:'dec-talk'});wrap.append(h('summary',null,h('span',{class:'dec-talk-t'},'Ask Temple about '+m.role),h('span',{class:'small muted'},' How its jobs went, and better instructions (applied only if you approve)')));
  const url='/admin/api/teams/'+enc(t.id)+'/members/'+enc(m.id)+'/discussion';const log=h('div',{class:'dec-talk-log'}),form=h('form',{class:'dec-talk-form'}),ta=h('textarea',{rows:'2',maxlength:'4000',placeholder:'Ask Temple, e.g. what keeps being sent back?','aria-label':'Message to Temple'}),send=h('button',{type:'submit'},'Send');
  const starters=h('div',{class:'dec-talk-starters'});for(const s of ['How could '+m.role+'’s instructions be better?','What keeps being sent back, and why?','What did I have to correct?']){const x=h('button',{type:'button',class:'chip'},s);x.onclick=()=>{ta.value=s;form.requestSubmit()};starters.append(x)}
  form.append(ta,send);wrap.append(log,starters,form);let loaded=false;
  const show=ms=>{log.replaceChildren(...ms.map(x=>h('div',{class:'dec-msg '+(x.role==='temple'?'from-t':'from-you')},h('div',{class:'who'},x.role==='temple'?'Temple':'You'),h('div',{class:'txt'},x.content),x.note?h('div',{class:'small'},'Suggestion waiting for your approval above: '+x.note):null)));starters.hidden=ms.length>0;log.scrollTop=log.scrollHeight};
  wrap.addEventListener('toggle',()=>{if(wrap.open&&!loaded){loaded=true;run(async()=>show((await api(url)).messages))}});
  form.onsubmit=e=>{e.preventDefault();const msg=ta.value.trim();if(!msg||send.disabled)return;send.disabled=true;ta.value='';const wait=h('div',{class:'dec-msg from-t thinking'},'Temple is thinking…');log.append(wait);
   run(async()=>{try{const r=await api(url,'POST',{message:msg});show(r.messages);if(r.suggestion){$('notice').textContent='Temple suggested new instructions: they wait for your approval.';await loadTeam()}}catch(err){wait.remove();ta.value=msg;throw err}finally{send.disabled=false}})};return wrap}
 // ---- Knowledge tab: categories per member, the rate library ----
 function drawKnowledgeTab(p){const d=V.d,t=d.team;const s=h('section',{class:'tm-panel'},h('h3',null,'Knowledge each member may use'),h('p',{class:'small muted'},'Members read only active knowledge in the categories ticked here, never Local only items, only what their model may receive, and only the clients’ material the Rules page allows. None ticked = no knowledge.'));
  if(!d.categories.length)s.append(h('p',{class:'tm-empty'},'There are no categories yet: create them on the Memories page.'));
  for(const m of t.members){const c=checks(d.categories.map(x=>[x,x]),m.categories||[]);const row=h('div',{class:'tm-mem'},h('h3',null,m.role,(m.categories||[]).length?null:h('span',{class:'tm-chip warn'},'No knowledge ticked')),c,h('div',{class:'tm-acts'},btn('Save',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/members/'+enc(m.id),'PUT',{categories:c.values()});$('notice').textContent='Saved as a new team version.';await loadTeam()},'secondary')));s.append(row)}
  p.append(s);if(d.pricing.length)p.append(ratesPanel())}
 function ratesPanel(){const d=V.d,t=d.team,r=d.rates;const s=h('section',{class:'tm-panel'},h('h3',null,'Rate library ',h('span',{class:'small muted'},plural(r.count,'rate'))),h('p',{class:'small muted'},'Your own rates (CSV or Excel with Description, Unit and Rate; optional Code, Region, As of, Source). Used only where no published rate with a source and date is found; rates you enter on a job can be saved here too.'));
  const file=h('input',{type:'file',accept:'.csv,.xlsx','aria-label':'Rate library file'}),label=h('input',{type:'text',maxlength:'120',placeholder:'Name, e.g. 2025 tender returns','aria-label':'Name for these rates',style:'width:auto;flex:1;margin:0'});
  s.append(h('div',{class:'tm-acts'},file,label,btn('Upload',async()=>{const f=file.files[0];if(!f)throw Error('Choose a CSV or Excel file first.');const data=await new Promise((ok,no)=>{const x=new FileReader();x.onload=()=>ok(String(x.result).split(',')[1]);x.onerror=()=>no(Error('Could not read the file.'));x.readAsDataURL(f)});
   const x=await api('/admin/api/teams/'+enc(t.id)+'/rates','POST',{name:f.name,data,label:label.value});$('notice').textContent=x.added+' rates added'+(x.skipped?', '+x.skipped+' rows skipped (no description, unit or rate)':'')+'.';await loadTeam()},'secondary'),
   btn('Load the fictional demo rate library',async()=>{const x=await api('/admin/api/teams/'+enc(t.id)+'/rates/demo','POST',{});$('notice').textContent=x.added+' fictional demo rates added.';await loadTeam()},'secondary')));
  for(const x of r.batches)s.append(h('div',{class:'tm-doc'},h('span',null,x.batch_name+' · '+plural(x.n,'rate')+' · added '+when(x.added_at)),btn('Remove',async()=>{if(!confirm('Remove the '+x.n+' rates in “'+x.batch_name+'”?'))return;await api('/admin/api/teams/'+enc(t.id)+'/rates/'+x.batch,'DELETE');await loadTeam()},'secondary')));
  const tbl=h('div',{class:'table-wrap'});s.append(tbl);if(r.count)run(async()=>{const rows=(await api('/admin/api/teams/'+enc(t.id)+'/rates')).rates;const tb=h('table',{class:'tm-tbl'},h('thead',null,h('tr',null,['Code','Description','Unit','Rate','Region','As of','Source'].map(x=>h('th',{scope:'col'},x)))));const body=h('tbody');
   for(const x of rows.slice(0,300))body.append(h('tr',null,[x.code,x.description,x.unit,gbp(x.rate),x.region,x.as_of,x.source].map(v=>h('td',null,v||''))));tb.append(body);tbl.append(tb)});return s}
 // ---- Rules and autonomy tab ----
 function drawRulesTab(p){const d=V.d,t=d.team;const a=h('section',{class:'tm-panel tm-auto'},h('h3',null,'How much the team does on its own'));
  for(const [k,l] of Object.entries(d.autonomy)){const r=h('input',{type:'radio',name:'tm-autonomy',value:k});r.checked=t.autonomy===k;r.onchange=()=>run(async()=>{await api('/admin/api/teams/'+enc(t.id)+'/autonomy','PUT',{autonomy:k});$('notice').textContent='Saved as a new team version: '+l+'.';await loadTeam()});
   a.append(h('label',null,r,h('span',null,h('strong',null,l),h('div',{class:'small muted'},k==='approve'?'Every hand-off waits for you (here and on Actions) with Approve, Send back and Discuss with Temple.':'Hand-offs go ahead on their own; questions and the final output still wait for you.'))))}
  const keys=Object.keys(t.settings||{});if(keys.length){const row=h('div',{class:'tm-acts'});const ins={};for(const k of keys){const i=h('input',{type:'number',step:'0.5',min:'0',max:'50',value:String(t.settings[k]),style:'width:90px'});ins[k]=i;row.append(h('label',{style:'display:grid;gap:4px;margin:0'},k.replace('_pct','').replace(/^./,c=>c.toUpperCase())+' %',i))}
   row.append(btn('Save percentages',async()=>{const s={};for(const k of keys)s[k]=+ins[k].value;await api('/admin/api/teams/'+enc(t.id)+'/settings','PUT',{settings:s});$('notice').textContent='Saved as a new team version.';await loadTeam()},'secondary'));a.append(h('h4',null,'Percentages applied by Alice'),row)}
  p.append(a,rulesPanel(true));const jts=h('section',{class:'tm-panel'},h('h3',null,'Job types and hand-offs'),h('p',{class:'small muted'},'Each stage says who works, what they hand on, and what the next member checks before accepting it. The receiver can send work back with reasons.'));drawTypes(jts);p.append(jts)}
 function drawTypes(box){const t=V.d.team;const mopts=t.members.map(m=>[m.id,m.role]);const sel=(opts,v)=>{const s=h('select');for(const [k,l] of opts)s.append(h('option',{value:k},l));s.value=v;return s};
  for(const jt of t.job_types){const c=h('div',{class:'tm-mem'},h('h3',null,jt.name));const name=h('input',{type:'text',maxlength:'80',value:jt.name}),desc=h('textarea',{maxlength:'600',rows:'2'});desc.value=jt.description||'';c.append(field('Name',name),field('Description',desc));
   const cf=h('input',{type:'checkbox'});cf.checked=jt.client_facing!==undefined?!!jt.client_facing:jt.finish==='cost_estimate';c.append(h('label',{class:'r-check',style:'display:flex;gap:8px;font-weight:400'},cf,'Client-facing output: uses only General material and the job’s own client (rule “Client-facing documents use only that client’s material” on the Rules page). Unticked, the Client separation rule applies.'));
   const flow=h('p',{class:'tm-flow'});const list=h('div');c.append(flow,list);let rows=jt.stages.map(s=>({...s}));const roleOf=id=>(t.members.find(m=>m.id===id)||{role:'?'}).role;
   const redraw=()=>{flow.textContent='Flow: '+rows.map(s=>roleOf(s.member)).join(' → ')+' → you (sign-off)';list.replaceChildren(...rows.map((s,i)=>{const w=h('div',{class:'tm-stage'});
    const ti=h('input',{type:'text',maxlength:'80',value:s.title}),mem=sel(mopts,s.member),task=h('textarea',{maxlength:'2000',rows:'2'}),hands=h('textarea',{maxlength:'600',rows:'2'}),chk=h('textarea',{maxlength:'1000',rows:'2'});task.value=s.task||'';hands.value=s.hands||'';chk.value=s.checks||'';
    for(const [n,k] of [[ti,'title'],[mem,'member'],[task,'task'],[hands,'hands'],[chk,'checks']])n.oninput=n.onchange=()=>{s[k]=n.value;if(k==='member')flow.textContent='Flow: '+rows.map(x=>roleOf(x.member)).join(' → ')+' → you (sign-off)'};
    const up=h('button',{type:'button',class:'secondary','aria-label':'Move stage up'},'↑'),dn=h('button',{type:'button',class:'secondary','aria-label':'Move stage down'},'↓'),rm=h('button',{type:'button',class:'secondary'},'Remove');up.disabled=!i;dn.disabled=i===rows.length-1;
    up.onclick=()=>{[rows[i-1],rows[i]]=[rows[i],rows[i-1]];redraw()};dn.onclick=()=>{[rows[i+1],rows[i]]=[rows[i],rows[i+1]];redraw()};rm.onclick=()=>{if(rows.length<2)return;rows.splice(i,1);redraw()};
    w.append(h('div',{class:'row'},h('strong',null,(i+1)+'.'),field('Stage',ti),field('Who works',mem),h('div',{class:'tm-acts'},up,dn,rm)),field('Task',task),field('What they hand on',hands),field(i?'What they check before accepting the work handed to them':'What they check (first stage: nothing is handed to them)',chk));
    if(s.handler&&s.handler!=='generic')w.append(h('span',{class:'small muted'},'Built-in step: '+s.handler.replace('qs_','')+' (its source and arithmetic checks run in code)'));return w}))};
   redraw();c.append(h('div',{class:'tm-acts'},btn('Add a stage',()=>{rows.push({key:'',title:'New stage',member:mopts[0]?mopts[0][0]:'',task:'',hands:'',checks:'',handler:'generic'});redraw()},'secondary'),
    btn('Save stages',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/job-types/'+enc(jt.id),'PUT',{name:name.value,description:desc.value,client_facing:cf.checked,stages:rows.map(s=>({key:s.key||'',title:s.title,member:s.member,task:s.task||'',hands:s.hands||'',checks:s.checks||''}))});$('notice').textContent='Saved as a new team version. Jobs already running keep the version they started on.';await loadTeam()})));box.append(c)}
  box.append(h('div',{class:'tm-acts'},btn('Add a job type',async()=>{const n=prompt('Name of the job type, e.g. Feasibility estimate');if(!n||!n.trim())return;await api('/admin/api/teams/'+enc(t.id)+'/job-types','POST',{name:n});$('notice').textContent='Job type added with one stage. Add the stages and hand-offs, then Save stages.';await loadTeam()},'secondary')))}
 // ---- Activity tab: versions, and what the team did lately ----
 function drawActivityTab(p){const d=V.d,t=d.team;const v=h('section',{class:'tm-panel'},h('div',{class:'tm-head',style:'margin:0 0 6px'},h('h3',{style:'margin:0'},'Versions'),btn('Undo the latest change',async()=>{const x=d.versions[0];if(!confirm('Undo v'+x.version+': '+x.what+'?'))return;await api('/admin/api/teams/'+enc(t.id)+'/restore','POST',{undo:true});$('notice').textContent='Undone. That is a new version too, so you can undo the undo.';await loadTeam()},'secondary')),
   h('p',{class:'small muted'},'Every change to a member, a stage, the autonomy, the settings or the team’s name and mark is a new version. Each job runs on the version it started with.'));
  const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-tbl'});tb.append(h('thead',null,h('tr',null,['Version','When','Who','What changed',''].map(x=>h('th',{scope:'col'},x)))));const body=h('tbody');
  for(const x of d.versions)body.append(h('tr',null,h('td',null,'v'+x.version+(x.version===t.version?' (current)':'')),h('td',null,when(x.changed_at)),h('td',null,x.changed_by),h('td',null,x.what),h('td',null,x.version<t.version?btn('Restore',async()=>{if(!confirm('Restore v'+x.version+'? It becomes a new version; nothing is lost.'))return;await api('/admin/api/teams/'+enc(t.id)+'/restore','POST',{version:x.version});$('notice').textContent='Restored v'+x.version+' as a new version.';await loadTeam()},'secondary'):'')));
  tb.append(body);wrap.append(tb);v.append(wrap);
  const recent=h('section',{class:'tm-panel'},h('h3',null,'Lately in jobs'));const steps=d.jobs.flatMap(j=>j.steps.map(s=>({...s,job:j}))).sort((a,b)=>b.created_at.localeCompare(a.created_at)).slice(0,30);
  if(!steps.length)recent.append(h('p',{class:'tm-empty'},'Nothing yet.'));const ul=h('ul',{class:'tm-tl'});const KIND={turn:'worked on',handoff:'handed on',sendback:'sent work back',question:'asked you',signoff:'sign-off',rates:'rates decided'};
  for(const s of steps)ul.append(h('li',null,s.member==='stefan'?avatar('You','You',false,'','you'):avatar(((s.role||'?').match(/[A-Za-z0-9]+/g)||['?']).slice(0,2).map(w=>w[0]).join('').toUpperCase(),s.role||'A member'),h('div',null,h('span',{class:'w'},(s.member==='stefan'?'You':s.role)+' '+(KIND[s.kind]||s.kind)),' · ',h('a',{href:'/admin/teams/'+enc(t.id)+'/jobs/'+s.job.id},s.job.ref),h('div',null,s.note||''),tm(s.created_at))));
  recent.append(ul);p.append(v,recent)}
 // ---------- Talk to the team (a team or a job) ----------
 function talkPanel(tid,jid){const key=tid+'/'+(jid||'');V.talk=V.talk||{};if(V.talk[key])return V.talk[key];const box=h('div',{class:'tm-talk'});V.talk[key]=box;const log=h('div',{class:'log','aria-live':'polite'}),ta=h('textarea',{maxlength:'4000',placeholder:'Write to the team. The lead answers and passes it on to whoever should act.','aria-label':'Message to the team'}),send=h('button',{type:'submit'},'Send');
  const form=h('form',null,ta,send);box.append(log,form);
  const show=ms=>{log.replaceChildren(...(ms.length?ms.map(m=>h('div',{class:'tm-msg '+(m.role==='you'?'you':'lead')},h('span',{class:'w'},m.who+' · '+when(m.created_at)),m.content,m.routed_role?h('span',{class:'r'},'Passed on to '+m.routed_role+': '+m.note):null)):[h('p',{class:'tm-empty'},'No messages yet.')]));log.scrollTop=log.scrollHeight};
  run(async()=>show((await api('/admin/api/teams/'+enc(tid)+'/talk'+(jid?'?job='+jid:''))).messages));
  form.onsubmit=e=>{e.preventDefault();const msg=ta.value.trim();if(!msg||send.disabled)return;send.disabled=true;ta.value='';const wait=h('div',{class:'tm-msg lead'},'Writing…');log.append(wait);
   run(async()=>{try{const r=await api('/admin/api/teams/'+enc(tid)+'/talk','POST',{message:msg,job:jid||''});show(r.messages);if(r.routed_to&&jid)await loadJob()}catch(err){wait.remove();ta.value=msg;throw err}finally{send.disabled=false}})};return box}
 // ---------- Screen 3: a job ----------
 const J={src:'all'};
 async function loadJob(){const d=await api('/admin/api/teams/jobs/'+V.jid+'/page');V.d=d;setIconsFrom(d.nav);if(d.team_id!==V.tid){location.replace(d.url);return}drawJob();clearTimeout(V.timer);if(d.status==='running')V.timer=setTimeout(()=>run(loadJob),2500)}
 function briefCard(){const d=V.d;openCard({ref:d.ref,kind_label:'Digital team · Brief and files',title:d.title,subtitle:d.team.name+' · '+d.job_type_name,
  sections:[{key:'what',title:'Brief',text:d.brief},{key:'what',title:'Documents',rows:d.documents.length?d.documents.map(x=>[d.doc_kinds[x.kind]||x.kind,x.source==='library'?x.name+' (document source: '+x.path+')':x.name]):null,text:d.documents.length?'':'No documents.'},
   {key:'where',title:'Where',rows:[['Location',d.location||'Not given (national rates)'],['Client',d.client||'None (General material only for client-facing work)']]},{key:'when',title:'When',rows:[['Started',{time:d.created_at}],['Last change',{time:d.updated_at}]]},
   {key:'who',title:'Who',text:'Started by '+(d.created_by||'you')+'. Team version v'+d.team_version+'.'}],actions:[]})}
 function drawJob(){keepScroll(drawJobNow)}
 function drawJobNow(){const d=V.d;$('tv-split').hidden=false;drawNav(d.nav,d.team_id);const main=$('tm-main');main.replaceChildren();
  main.append(h('nav',{class:'tm-crumbs','aria-label':'Breadcrumb'},h('a',{href:'/admin/teams'},'Digital teams'),'›',h('a',{href:d.team.href},d.team.name),'›',h('span',{'aria-current':'page'},d.ref+' '+d.title)));
  const acts=h('div',{class:'tm-acts'});const brief=h('button',{type:'button',class:'secondary'},'Brief and files');brief.onclick=briefCard;acts.append(brief);
  if(d.status==='blocked'||(d.status==='running'&&!d.busy&&(Date.now()-new Date(d.updated_at))>10*60000))acts.append(btn('Resume',async()=>{await api('/admin/api/teams/jobs/'+d.id+'/resume','POST',{});await loadJob()}));
  if(!['done','stopped'].includes(d.status))acts.append(btn('Stop job',async()=>{if(!confirm('Stop '+d.ref+'? Its work so far is kept.'))return;await api('/admin/api/teams/jobs/'+d.id+'/stop','POST',{});await loadJob()},'secondary'));
  const desc=[plural(d.documents.length,'document')+' provided',d.location||null,'started '+when(d.created_at)+(d.created_by?' by '+d.created_by:'')].filter(Boolean).join(' · ');
  main.append(h('div',{class:'tm-thead'},mark(d.identity.hex,d.identity.icon,'lg'),h('div',{class:'nm'},h('p',{class:'tm-label'+(d.is_demo?'':' plain')},(d.is_demo?'Demo · fictional · ':'')+d.job_type_name+' · '+d.ref),h('h2',null,d.title),h('p',null,desc)),acts));
  const track=h('ol',{class:'tm-track','aria-label':'Stages'});const SW={done:'Done',current:'Working now',waiting:'Waiting for you',todo:'To come',blocked:'Stopped by a failure',stopped:'Stopped'};
  for(const s of d.progress)track.append(h('li',{class:s.state},h('b',null,s.title),h('span',{class:'who'},s.role),h('span',{class:'tm-state '+s.state},SW[s.state]+(s.count?' · '+s.count:''))));main.append(track);
  if(d.error)main.append(h('div',{class:'tm-err',role:'alert'},h('strong',null,'Stopped: '),d.error));
  const cols=h('div',{class:'tm-cols'});const left=h('div'),side=h('div',{class:'tm-side'});cols.append(left,side);main.append(cols);
  if(d.view&&d.view.decision)left.append(decisionPanel(d.view.decision));for(const s of d.pending)left.append(pendingBox(s));
  left.append(outputPanel());
  const tl=h('section',{class:'tm-panel','aria-labelledby':'tm-tl-h'},h('h3',{id:'tm-tl-h'},'What the team did'));tl.append(timeline());side.append(tl);
  side.append(h('section',{class:'tm-panel','aria-labelledby':'tm-talk-h'},h('h3',{id:'tm-talk-h'},'Talk to the team'),h('p',{class:'small muted'},'Messages go to '+(d.lead.role||'the lead')+', who answers and passes them to whoever should act.'),talkPanel(d.team_id,d.id)));
  side.append(h('section',{class:'tm-panel'},h('h3',null,'This job'),h('dl',{class:'tm-kv'},h('dt',null,'AI cost'),h('dd',null,'$'+(d.ai_cost||0).toFixed(2)+' so far'),h('dt',null,'Autonomy'),h('dd',null,d.autonomy_label),h('dt',null,'Team version'),h('dd',null,'v'+d.team_version),h('dt',null,'Client'),h('dd',null,d.client||'None'))))}
 function decisionPanel(x){const d=V.d;const s=h('section',{class:'tm-dec','aria-labelledby':'tm-dec-h'},h('h3',{id:'tm-dec-h'},x.title),h('p',{class:'small'},x.why));
  const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-plan'});tb.append(h('thead',null,h('tr',null,h('th',{scope:'col'},'Item'),h('th',{scope:'col',class:'n'},'Qty'),h('th',{scope:'col'},'Unit'),h('th',{scope:'col'},'Your rate (£ per unit)'),h('th',{scope:'col'},'Leave unpriced'))));
  const body=h('tbody'),rows=[];for(const i of x.items){const rate=h('input',{type:'number',min:'0.01',step:'0.01',inputmode:'decimal','aria-label':'Rate for '+i.ref+' '+i.description+' in pounds per '+i.unit}),lv=h('input',{type:'checkbox','aria-label':'Leave '+i.ref+' unpriced'});
   lv.onchange=()=>{rate.disabled=lv.checked;if(lv.checked)rate.value=''};rows.push({ref:i.ref,rate,lv});
   body.append(h('tr',null,h('td',null,h('b',null,i.ref+' '),i.description,h('div',{class:'sub'},i.element+(i.approximate?' · quantity from a drawing, approximate':''))),h('td',{class:'n'},qty(i.quantity)),h('td',null,i.unit),h('td',null,rate),h('td',null,lv)))}
  tb.append(body);wrap.append(tb);s.append(wrap);const save=h('input',{type:'checkbox'});save.checked=true;const note=h('textarea',{maxlength:'2000',placeholder:'A note for the team (needed to send work back)','aria-label':'Note for the team'});
  const entries=()=>rows.map(r=>({ref:r.ref,rate:r.rate.value===''?null:+r.rate.value,unpriced:r.lv.checked})).filter(e=>e.unpriced||e.rate!=null);
  const submit=async go_on=>{const e=entries();if(!e.length)throw Error('Enter a rate, or tick Leave unpriced, for at least one item.');await api('/admin/api/teams/jobs/'+d.id+'/rates','POST',{entries:e,save_to_library:save.checked,go_on});
   $('notice').textContent='Recorded as yours'+(save.checked&&e.some(x=>!x.unpriced)?' and saved to the rate library':'')+(go_on?'. '+(d.lead.role||'The lead')+' carries on.':'.');await loadJob()};
  const acts=h('div',{class:'opts'},h('label',null,save,'Save the rates I enter to my rate library'));s.append(acts,note);
  const b=h('div',{class:'tm-acts',style:'margin-top:10px'});
  if(x.state==='handoff'){b.append(btn('Use these and continue',()=>submit(true)),btn('Ask '+x.pricer+' to search again',async()=>{const n=note.value.trim()||('Search again for: '+x.items.map(i=>i.ref+' '+i.description).join('; '));await api('/admin/api/teams/steps/'+x.step_id,'POST',{action:'send_back',note:n});$('notice').textContent=x.pricer+' will search again.';await loadJob()},'secondary'))}
  else{b.append(btn('Use these',()=>submit(false)));if(x.state==='signoff')b.append(btn('Send back to '+x.lead,async()=>{if(!note.value.trim())throw Error('Say what needs to change in the note, so '+x.lead+' can act on it.');await api('/admin/api/teams/steps/'+x.step_id,'POST',{action:'send_back',note:note.value});$('notice').textContent='Sent back to '+x.lead+' with your note.';await loadJob()},'secondary'))}
  s.append(b);return s}
 function pendingBox(s){const d=V.d;const w=h('div',{class:'tm-wait'});const who=s.role||'A member';
  if(s.kind==='question'){w.append(h('strong',null,who+' asks you'));for(const x of (s.content.questions||[]))w.append(h('p',null,x));const ta=h('textarea',{maxlength:'2000',placeholder:'Your answer','aria-label':'Your answer to '+who});w.append(ta,h('div',{class:'tm-acts'},btn('Send answer',async()=>{if(!ta.value.trim())throw Error('Type your answer.');await api('/admin/api/teams/steps/'+s.id,'POST',{action:'answer',note:ta.value});$('notice').textContent='Answer sent. '+who+' carries on.';await loadJob()}),btn('Discuss with Temple',()=>openStep(s),'secondary')));return w}
  w.append(h('strong',null,s.kind==='signoff'?'Ready for your sign-off':who+' → '+(s.to_role||'next')+': approve the hand-off?'));if(s.note)w.append(h('p',null,s.note));if(s.kind==='signoff'&&d.outputs.summary)w.append(h('p',{class:'small'},d.outputs.summary));
  const note=h('textarea',{maxlength:'2000',placeholder:'Your note (needed to send it back)','aria-label':'Your note'});w.append(note);
  w.append(h('div',{class:'tm-acts'},btn(s.kind==='signoff'?'Approve and finish':'Approve',async()=>{const x=await api('/admin/api/teams/steps/'+s.id,'POST',{action:'approve',note:note.value});$('notice').textContent=s.kind==='signoff'?'Signed off'+(x.knowledge_id?' and saved to Knowledge.':'.'):'Approved: '+(s.to_role||'the next member')+' starts now.';await loadJob()}),
   btn('Send back',async()=>{if(!note.value.trim())throw Error('Say what needs to change in the note, so the team can act on it.');await api('/admin/api/teams/steps/'+s.id,'POST',{action:'send_back',note:note.value});$('notice').textContent='Sent back with your note.';await loadJob()},'secondary'),btn('Discuss with Temple',()=>openStep(s),'secondary')));return w}
 function openStep(s){openCard('/admin/api/cards/review/h-'+s.id,{onClose:()=>run(loadJob)})}
 function outputPanel(){const d=V.d,v=d.view||{};const s=h('section',{class:'tm-panel','aria-labelledby':'tm-out-h'});const docs=(v.documents||d.outputs.documents||[]);
  if(v.plan){const pl=v.plan;s.append(h('h3',{id:'tm-out-h'},pl.stage==='measure'?'Measured so far (not priced yet)':'The cost plan so far'));
   const order=Object.keys(pl.labels).filter(k=>pl.counts[k]);if(!order.includes(J.src)&&J.src!=='all')J.src='all';const chips=h('div',{class:'rl-chips',role:'group','aria-label':'Show items by where the rate came from',style:'margin:0 0 10px'});
   filterChips(chips,[['all','All',pl.rows.length],...order.map(k=>[k,pl.labels[k],pl.counts[k]])],J.src,k=>{J.src=k;drawJob()});s.append(chips);
   const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-plan'});tb.append(h('thead',null,h('tr',null,h('th',{scope:'col'},'Item'),h('th',{scope:'col',class:'n'},'Qty'),h('th',{scope:'col'},'Unit'),h('th',{scope:'col',class:'n'},'Rate'),h('th',{scope:'col'},'Source'),h('th',{scope:'col',class:'n'},'Amount'))));
   const body=h('tbody');for(const r of pl.rows.filter(r=>J.src==='all'||r.source===J.src)){const badge=r.source==='web'&&r.source_url?h('a',{class:'tm-src web',href:r.source_url,target:'_blank',rel:'noopener noreferrer',title:(r.source_title||r.source_url)+(r.source_date?' ('+r.source_date+')':'')},'Web ↗'):h('span',{class:'tm-src '+r.source,title:r.note||r.source_title||''},r.source_label);
    const srcCell=h('td',null,badge,r.source==='library'&&r.source_title?h('div',{class:'sub'},r.source_title+(r.source_date?' · '+r.source_date:'')):null,r.source==='web'&&r.source_date?h('div',{class:'sub'},r.source_date):null,r.source==='yours'&&r.decided_by?h('div',{class:'sub'},'by '+r.decided_by):null,r.undecided?h('div',{class:'sub'},'Waiting for your decision'):r.source==='unpriced'&&r.decided_by?h('div',{class:'sub'},'Left unpriced by '+r.decided_by):null);
    body.append(h('tr',{class:r.undecided?'und':null},h('td',{style:'min-width:180px'},h('b',null,r.ref+' '),r.description,h('div',{class:'sub'},r.element+' · '+r.quantity_source+(r.approximate?' · approximate (from a drawing)':''))),h('td',{class:'n'},qty(r.quantity)),h('td',null,r.unit),h('td',{class:'n'},r.rate==null?'—':gbp(r.rate)),srcCell,h('td',{class:'n'},r.amount==null?'—':gbp(r.amount))))}
   tb.append(body);wrap.append(tb);s.append(wrap);if(pl.location_note)s.append(h('p',{class:'small muted'},pl.location_note));
   if(pl.stage==='price'){if(pl.totals){const P=pl.percentages||{};const tot=h('dl',{class:'tm-tot'});const row=(k,v,b)=>tot.append(h('dt',null,b?h('b',null,k):k),h('dd',{style:'margin:0;text-align:right'},b?h('b',null,gbp(v)):gbp(v)));
     row('Construction',pl.totals.construction);row('Preliminaries'+(P.prelims_pct!=null?' ('+P.prelims_pct+'%)':''),pl.totals.prelims);row('Contingency'+(P.contingency_pct!=null?' ('+P.contingency_pct+'%)':''),pl.totals.contingency);row('Fees'+(P.fees_pct!=null?' ('+P.fees_pct+'%)':''),pl.totals.fees);row('Total excluding VAT',pl.totals.total,true);
     s.append(tot,h('p',{class:'small muted',style:'text-align:right'},'Worked out by Alice from the rates and quantities above; unpriced items are excluded.'))}
    else s.append(h('p',{class:'small',role:'note'},h('b',null,'No total yet: '),plural(pl.undecided,'item')+' still '+(pl.undecided===1?'needs':'need')+' a rate or to be marked unpriced.'))}}
  else if(v.text){s.append(h('h3',{id:'tm-out-h'},'The work so far: '+v.text.stage),h('pre',null,v.text.text))}
  else s.append(h('h3',{id:'tm-out-h'},'The work so far'),h('p',{class:'tm-empty'},d.status==='running'?'The team is working on the first stage…':'Nothing produced yet.'));
  if(docs.length||d.knowledge_id){const o=h('div',{class:'tm-out'});for(const x of docs)o.append(h('a',{href:'/documents/'+x.id+'/download'},'⬇ '+x.kind+': '+x.name));if(d.knowledge_id)o.append(h('a',{href:'/admin/knowledge'},'Saved to Knowledge ↗'));s.append(o)}return s}
 function timeline(){const d=V.d;const ms={};for(const m of d.members)ms[m.id]=m;const ul=h('ol',{class:'tm-tl'});if(!d.timeline.length)return h('p',{class:'tm-empty'},'Nothing yet.');
  for(const x of d.timeline){const m=ms[x.member];const av=x.member==='stefan'?avatar('You','You',false,'','you'):avatar(m?m.initials:'A',x.who,m&&m.id===d.lead.id,d.identity.hex);
   const li=h('li',null,av,h('div',null,h('span',{class:'w'},x.who),x.stage?h('span',{class:'small muted'},' · '+x.stage):null,h('div',null,x.text),x.outcome?h('div',{class:'o'},x.outcome):null,tm(x.at)));
   if(x.output_text){const b=h('button',{type:'button',class:'secondary'},'See the output');b.onclick=()=>openCard({ref:d.ref,kind_label:'Digital team · Output',title:x.output_title,subtitle:d.title,sections:[{key:'what',title:x.stage,text:x.output_text},{key:'when',title:'When',rows:[['Produced',{time:x.at}]]}],actions:[]});li.lastChild.append(b)}
   ul.append(li)}return ul}
 // ---------- start: old links, then the right screen ----------
 const qp=new URLSearchParams(location.search);
 if(!V.tid&&qp.get('job'))run(async()=>{const j=await api('/admin/api/teams/jobs/'+enc(qp.get('job')));location.replace('/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id)});
 else if(!V.tid&&qp.get('team'))location.replace('/admin/teams/'+enc(qp.get('team'))+(location.hash||''));
 else if(V.jid)run(loadJob);
 else if(V.tid){run(async()=>{await loadTeam();api('/admin/api/teams/'+enc(V.tid)+'/seen','POST',{}).catch(()=>{})});window.addEventListener('hashchange',()=>{const k=location.hash.slice(1);if(TABS.some(x=>x[0]===k)&&k!==tab){tab=k;if(V.d)drawTeam()}})}
 else{run(loadBoard);$('tb-q').oninput=()=>{B.q=$('tb-q').value;drawTeams()};$('tb-group').onchange=()=>{B.group=$('tb-group').value;store.set('group',B.group);drawTeams()};
  $('tb-cards').onclick=()=>{B.view='cards';store.set('view','cards');drawBoard()};$('tb-list').onclick=()=>{B.view='list';store.set('view','list');drawBoard()};
  $('tb-new').onclick=()=>newTeamPanel(false);$('tb-templates').onclick=()=>newTeamPanel(true)}
}
"""
