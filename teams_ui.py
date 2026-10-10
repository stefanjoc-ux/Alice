"""The Digital teams pages (Workspace › Teams; 7 Oct 2026): All teams (/admin/teams), a team (/admin/teams/{id}) and a
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
.tm-partprog{margin:-4px 0 12px;font-size:13.5px;font-weight:600;color:var(--teal)}.tm-reply{margin-top:6px}.tm-reply pre{white-space:pre-wrap;font-size:12.5px;max-height:260px;overflow:auto}
.tm-err{border-left:4px solid var(--tm-bad);background:#fbeaea;border-radius:8px;padding:10px 12px;margin:0 0 12px}
.tm-src{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 8px;border-radius:5px;border:1px solid;white-space:nowrap}
.tm-src.web{background:#e3f1f6;border-color:#9ccbdc;color:#054a60}.tm-src.library{background:#f1ebf7;border-color:#cbb8e2;color:#4b2f73}.tm-src.yours{background:#e6f4ea;border-color:#9fcfaf;color:#1e5b31}
.tm-src.built_up{background:#e8eef9;border-color:#a9bde3;color:#1f3a68}.tm-src.estimate{background:#fdf0e1;border-color:#e8b27a;color:#7a3a05;border-style:dashed}
.tm-market{border-top:1px solid var(--line,#dfe6eb);margin-top:12px;padding-top:8px}.tm-market h4{margin:0 0 6px}
.tm-conflict{border-left:4px solid #e8b27a;background:#fdf6ec;border-radius:8px;padding:10px 12px;margin:0 0 12px}.tm-conflict a{margin-right:12px}
.tm-src.provisional{background:#eef7ee;border-color:#8fc59a;color:#1d5a2a;border-style:dashed}.tm-src.excluded{background:#f1f4f6;border-color:#9aa8b4;color:#3d4b57;text-decoration:line-through}
.tm-ask{border:1px solid #f0c48a;background:var(--tm-wait-bg);border-radius:10px;padding:10px 12px;margin:10px 0}.tm-ask p{margin:0 0 8px}
.tm-dec td input.ex{width:100%;min-width:140px;margin-top:4px}.tm-ps{margin:14px 0 0}.tm-ps h4{margin:0 0 6px}
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
.tm-cost{font-variant-numeric:tabular-nums}.tm-cost td.n,.tm-cost th.n{text-align:right;white-space:nowrap}.tm-cost tfoot td{font-weight:700;border-top:2px solid #c9d5de}
.tm-fx{font-size:12px;color:var(--muted);margin:4px 0 0}.tm-fx button{margin-left:6px;padding:1px 8px;font-size:12px}.tm-est{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;border:1px solid #c9b8e3;background:#f6f2fb;color:#4b2f73;border-radius:999px;padding:0 7px;margin-left:6px}
.tm-yours{font-size:12px;color:#3d5566}.tm-yours b{color:#16384d}.tm-ver{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:6px}.tm-ver li{border:1px solid #dbe3ea;border-radius:8px;padding:7px 10px;font-size:13px;display:grid;gap:2px}
.tm-ver li.cur{border-color:#7fb3c8;background:#f3f9fb}.tm-ver .h{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tm-ver .h b{font-size:13.5px}.tm-ver .h .c{margin-left:auto;font-variant-numeric:tabular-nums}
.tm-so{font-size:11px;font-weight:700;border-radius:999px;padding:0 7px;background:#e7f4ea;border:1px solid #9ccfaa;color:#1d5a2c}.tm-rerun{border-left:4px solid #7fb3c8;background:#f3f9fb;border-radius:8px;padding:10px 12px;margin:0 0 12px;font-size:13.5px}
.tm-rp{border:1px solid #c9d5de;border-radius:12px;padding:14px 16px;margin:0 0 14px;background:#fff}.tm-rp h3{margin:0 0 4px}.tm-rp .items{display:grid;gap:2px;max-height:300px;overflow:auto;border:1px solid #eef3f6;border-radius:8px;padding:6px 8px;margin:8px 0}
.tm-rp .items label{display:flex;gap:8px;align-items:flex-start;font-size:13px;font-weight:400}.tm-rp .opts{display:grid;gap:6px;margin:8px 0}.tm-rp .opts label{display:flex;gap:8px;align-items:center;font-weight:400;font-size:13.5px}
.tm-order{list-style:none;margin:4px 0;padding:0;display:grid;gap:4px}.tm-order li{display:flex;gap:6px;align-items:center;font-size:13px}.tm-order li button{padding:0 8px}.tm-order li.off span{color:var(--muted);text-decoration:line-through}
.tm-rp textarea{width:100%;min-height:54px}.tm-sortl{display:flex;gap:6px;align-items:center;font-size:13px}
.ts-grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:20px;align-items:start}.ts-steps{display:grid;gap:16px;margin:0;padding:0;list-style:none}
.ts-step{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 18px}.ts-step h3{margin:0 0 10px;display:flex;gap:10px;align-items:center;font-size:16px}
.ts-num{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:var(--teal);color:#fff;font-size:13px;font-weight:700;flex:none}
.ts-step label{display:grid;gap:4px;font-size:13px;font-weight:600;margin:0 0 10px}.ts-step .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ts-step .hint{font-weight:400;color:var(--muted);font-size:12px}
.ts-types{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin:0 0 10px;border:0;padding:0}.ts-types legend{font-size:13px;font-weight:600;margin:0 0 6px;padding:0}
.ts-type{display:flex!important;gap:8px;align-items:flex-start;border:1px solid var(--line);border-radius:10px;padding:9px 11px;font-weight:400!important;cursor:pointer;margin:0!important}
.ts-type:has(input:checked){border-color:var(--teal);background:#eef7fa;box-shadow:0 0 0 1px var(--teal)}.ts-type b{display:block;font-size:13.5px}.ts-type span{font-size:12px;color:var(--muted)}
.ts-drop{border:2px dashed #9fb6c4;border-radius:12px;padding:22px;text-align:center;background:#f7fafc;cursor:pointer;color:#3d5566}.ts-drop:focus-visible,.ts-drop.over{border-color:var(--teal);background:#eef7fa;outline:none}
.ts-drop b{display:block;font-size:15px;color:var(--ink);margin:0 0 2px}.ts-files{display:grid;gap:8px;margin:10px 0 0}
.ts-file{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:8px 11px;font-size:13px}
.ts-file .nm{font-weight:600;overflow-wrap:anywhere}.ts-file .meta{font-size:12px;color:var(--muted)}.ts-file .meta .lbl{color:#4b2f73}.ts-file .prob{font-size:12px;color:var(--tm-bad)}
.ts-file.tpl{border-color:#7fb3c8;background:#f1f8fb;box-shadow:inset 4px 0 0 var(--teal)}.ts-file select{margin:0;min-width:150px}.ts-file button{margin:0}
.ts-tag{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:0 7px;margin-left:6px;border:1px solid #9ccbdc;background:#e3f1f6;color:#054a60}.ts-tag.warn{border-color:#f0c48a;background:var(--tm-wait-bg);color:#8a3f06}.ts-tag.ok{border-color:#9ccfaa;background:#e7f4ea;color:#1d5a2c}
.ts-opt{display:flex!important;gap:8px;align-items:flex-start;font-weight:400!important}.ts-src{margin:4px 0 10px;padding-left:20px;font-size:13px}.ts-src li.off{color:var(--muted)}
.ts-next{position:sticky;top:12px;background:var(--bar,#0b1626);color:#e8f0f6;border-radius:16px;padding:18px}.ts-next h3{color:#fff;margin:0 0 4px;font-size:16px}.ts-next p{color:#b9cad6;font-size:13px;margin:0 0 10px}
.ts-who{list-style:none;margin:0 0 12px;padding:0;display:grid;gap:10px}.ts-who li{display:grid;grid-template-columns:32px minmax(0,1fr);gap:10px;font-size:13px}.ts-who b{color:#fff}.ts-who .d{color:#b9cad6;font-size:12.5px}
.ts-who .tm-av{background:#1d3550;color:#fff;border-color:#3b5a78}.ts-typ{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:13px;margin:0 0 12px;padding:10px 0;border-top:1px solid #23405d;border-bottom:1px solid #23405d}.ts-typ dt{color:#b9cad6}.ts-typ dd{margin:0;color:#fff;font-weight:600}
.ts-ready{list-style:none;margin:0 0 14px;padding:0;display:grid;gap:6px;font-size:13px}.ts-ready li{display:grid;grid-template-columns:20px 1fr;gap:6px}.ts-ready .i{font-weight:700}.ts-ready .ok .i{color:#7ee2a0}.ts-ready .warn .i{color:#f5c26b}.ts-ready .no .i{color:#ff9b9b}
.ts-next button.go{width:100%;margin:0;background:#fff;color:var(--bar,#0b1626);font-weight:700}.ts-next button.go:disabled{opacity:.55}.ts-next a{color:#9fd3e6}
.tm-map{max-width:min(960px,96vw);width:100%;border:0;border-radius:14px;padding:18px 20px}.tm-map::backdrop{background:rgba(11,22,38,.55)}.tm-map h3{margin:0 0 6px}.tm-map .sheet{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:10px 0}
.tm-map .roles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.tm-map label{display:grid;gap:3px;font-size:12.5px;font-weight:600}.tm-map .prev{max-height:220px;overflow:auto;margin:8px 0}.tm-map .prev td,.tm-map .prev th{font-size:11.5px;padding:2px 6px;border:1px solid #e3e9ee;white-space:nowrap;max-width:180px;overflow:hidden;text-overflow:ellipsis}
.tm-map .tm-acts button:first-child{background:var(--teal);color:#fff;border-color:var(--teal)}.tm-tpl{display:grid;gap:6px;font-size:13px}.tm-diffs{margin:6px 0 0;padding-left:18px;font-size:12.5px}.tm-diffs li{margin:2px 0}
.tm-mhead{display:flex;gap:10px 16px;align-items:center;flex-wrap:wrap;margin:0 0 6px}.tm-mhead .tm-fx{flex-basis:100%;margin:0}.tm-mtot{margin:0;font-size:14px}.tm-mtot b{font-variant-numeric:tabular-nums}.tm-mhelp{margin:0 0 12px}
.tm-mgrid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:24px 32px}.tm-mc{position:relative;min-width:0}
.tm-mcd{position:relative;height:100%;box-sizing:border-box;background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px;display:flex;flex-direction:column;gap:9px;transition:box-shadow .15s,border-color .15s}
.tm-mc.lead .tm-mcd{border-width:2px}.tm-mcd:hover,.tm-mcd:focus-within{border-color:#7fa9c4;box-shadow:0 2px 10px rgba(16,43,64,.08)}
.tm-mcd .top{display:flex;gap:10px;align-items:flex-start}.tm-mcd .nm{flex:1;min-width:0}.tm-mcd h4{margin:0;font-size:15.5px;line-height:1.3}
#tm-app button.tm-mc-open{all:unset;cursor:pointer;font-weight:650;color:var(--ink)}#tm-app button.tm-mc-open::after{content:'';position:absolute;inset:0;border-radius:14px}
#tm-app button.tm-mc-open:focus-visible{outline:none}.tm-mcd:has(.tm-mc-open:focus-visible){outline:2px solid var(--teal);outline-offset:2px}
.tm-mcd .purpose{margin:2px 0 0;font-size:13px;color:#30495c;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.tm-mcd a,.tm-mcd time{position:relative;z-index:1}#tm-app button.tm-handle{all:unset;box-sizing:border-box;cursor:grab;position:relative;z-index:1;flex:none;width:30px;height:30px;display:grid;place-items:center;border-radius:8px;color:#4b5a66;font-size:17px}
#tm-app button.tm-handle:hover{background:#eef3f7}#tm-app button.tm-handle:focus-visible{outline:2px solid var(--teal);outline-offset:1px}#tm-app button.tm-handle[aria-pressed=true]{background:var(--teal);color:#fff}
.tm-mc.grab .tm-mcd{border-color:var(--teal);box-shadow:0 0 0 3px #bfe0ea}.tm-mc.dragging{opacity:.45}.tm-mc.over .tm-mcd{border-color:var(--teal);border-style:dashed}
.tm-lead{flex:none;font-weight:700;background:#e3f1f6;border-color:#9ccbdc;color:#054a60}.tm-mchips{gap:4px}.tm-mchips .tm-chip{font-size:11.5px;padding:1px 8px}
.tm-chip.t{background:#e3f1f6;border-color:#9ccbdc;color:#054a60}.tm-chip.k{background:#eef3f7;border-color:#d3dee6}.tm-chip.p{background:#f1ebf7;border-color:#cbb8e2;color:#4b2f73}
.tm-mcost{border-top:1px solid #eef3f6;padding-top:8px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:center}.tm-mcost .big{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
.tm-mcost .small{grid-column:1}.tm-spark{grid-column:2;grid-row:1/span 2;width:120px;height:28px}.tm-spark polyline{fill:none;stroke:var(--teal);stroke-width:1.6;stroke-linejoin:round}.tm-spark circle{fill:var(--teal)}
.tm-mrun{font-size:12.5px;color:#3d5566}.tm-mflow{margin:0;font-size:12.5px;color:#3d5566}.tm-msugg{margin:0;font-size:12.5px;color:#4b2f73;font-weight:600}
.tm-mwarn{margin:0;padding:7px 10px 7px 24px;background:#fff4e5;border:1px solid #f0c48a;border-radius:9px;font-size:12.5px;color:#6b3305}.tm-mwarn li{margin:2px 0}
.tm-mcd.tm-madd{border:2px dashed #9fb6c4;background:#f9fbfc;justify-content:center}.tm-madd h4{font-size:15px}.tm-madd p{margin:0}
.tm-mc.arr-r::after{content:'→';position:absolute;right:-26px;top:50%;transform:translateY(-50%);font-size:20px;font-weight:700;color:#5f8ea8}
.tm-mc.arr-d::after{content:'↓';position:absolute;left:50%;bottom:-23px;transform:translateX(-50%);font-size:18px;font-weight:700;color:#5f8ea8}
.tm-ed{display:grid;gap:8px}.tm-ed label{display:grid;gap:4px;font-weight:600;font-size:13px;margin:0}.tm-ed p{margin:0}.tm-ed textarea.tm-ins{min-height:300px;font-size:13.5px;line-height:1.5}
.tm-ed .tm-checks label{display:flex;gap:6px;align-items:center;font-weight:400}.tm-changed>summary{cursor:pointer;font-weight:600;font-size:13px}.tm-diffbox{display:grid;gap:6px;margin-top:6px}.tm-diff{white-space:pre-wrap;font-size:12.5px;line-height:1.55;background:#fbfcfd;border:1px solid #e3e9ee;border-radius:8px;padding:8px 10px;max-height:280px;overflow:auto;overflow-wrap:anywhere}
.tm-diff ins{background:#dff3e4;color:#1d5a2a;text-decoration:none}.tm-diff del{background:#fbe3e3;color:#7a1f1f}
.tm-diff ins::before,.tm-diff ins::after,.tm-diff del::before,.tm-diff del::after{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.tm-diff ins::before{content:' [added: '}.tm-diff del::before{content:' [removed: '}.tm-diff ins::after,.tm-diff del::after{content:'] '}
.tm-edfoot{display:flex;gap:8px;flex-wrap:wrap;align-items:center;width:100%}.tm-edfoot button{margin:0}.tm-edfoot .tm-rm{margin-left:auto}.tm-edmsg{flex-basis:100%;margin:0;color:#b42318}.tm-edmsg:empty{display:none}
@media(max-width:640px){.tm-mgrid{grid-template-columns:minmax(0,1fr)}.tm-period{display:flex;flex-wrap:wrap}.tm-period button.ghost{flex:1 1 auto}}
#tm-app .tm-answer{display:flex;gap:8px;align-items:flex-start}#tm-app .tm-answer textarea{flex:1}#tm-app .tm-answer button{margin:6px 0 0;flex:none}
.tm-asm{margin:0;padding-left:20px;display:grid;gap:8px;font-size:13.5px}.tm-assumed{border-left:4px solid #e8b27a}
@media(max-width:1000px){.ts-grid{grid-template-columns:minmax(0,1fr)}.ts-next{position:static}}
@media(max-width:640px){.ts-step .row{grid-template-columns:minmax(0,1fr)}.ts-file{grid-template-columns:minmax(0,1fr)}.ts-file select{min-width:0;width:100%}}
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
  <label class="tm-sortl">Sort by <select id="tb-sort" aria-label="Sort teams by"><option value="needs">Needs you first</option><option value="name">Name</option><option value="cost">Cost, last 30 days</option></select></label>
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
 const V={tid:P[3]?decodeURIComponent(P[3]):'',jid:P[4]==='jobs'&&P[5]?P[5]:'',start:P[4]==='start',d:null,timer:null,icons:{}};
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
 // ---------- costs: figures come from the server (team_costs.py) with the rate they are shown at ----------
 const money=(m,fx)=>m?h('span',{class:'tm-money',title:m.note||(fx&&fx.note)||''},m.text):h('span',{class:'muted'},'—');
 function fxLine(fx,label){const p=h('p',{class:'tm-fx'},(label||'Costs')+' '+fx.note+'.');const b=btn(fx.rate?'Change rate':'Set a rate',async()=>{const v=prompt('Pounds per US dollar, e.g. 0.79 (your own rate: Alice never looks one up). Leave empty to show US dollars.',fx.rate||'');if(v===null)return;
   await api('/admin/api/teams/costs/rate','PUT',{rate:v.trim()===''?null:Number(v)});$('notice').textContent=v.trim()===''?'Team costs are shown in US dollars.':'Team costs are shown in pounds at $1 = £'+Number(v)+'.';await reload()},'secondary');p.append(b);return p}
 // ---------- Needs you rows (all teams, and a team's own) ----------
 function needsBox(items,title){if(!items.length)return null;const box=h('section',{class:'tm-needs','aria-labelledby':'tm-needs-h'});
  box.append(h('h3',{id:'tm-needs-h'},title||'Needs you',h('span',{class:'n'},String(items.length))));
  for(const i of items){const who=h('div',{class:'t'});
   if(i.team_id)who.append(h('a',{href:'/admin/teams/'+enc(i.team_id)},i.team));else who.append(h('b',null,i.team));
   if(i.job_ref)who.append(' › ',h('a',{href:i.href},i.job_ref+' '+i.job_title));
   const go=i.resume?btn('Resume',async()=>{await api('/admin/api/teams/jobs/'+i.resume+'/resume','POST',{});$('notice').textContent=i.job_ref+' resumed.';await reload()}):h('a',{class:'button',href:i.href},i.action);
   box.append(h('div',{class:'tm-nrow'},mark(i.hex,i.icon,'sm'),h('div',null,who,h('div',{class:'s'},i.text)),i.at?tm(i.at):h('span'),go))}
  return box}
 async function reload(){if(V.jid)await loadJob();else if(V.start)await loadStart();else if(V.tid)await loadTeam();else await loadBoard()}
 // ---------- Screen 1: all teams ----------
 const B={status:store.get('status','all'),group:store.get('group','discipline'),view:store.get('view','cards'),sort:store.get('sort','needs'),q:''};
 async function loadBoard(){const d=await api('/admin/api/teams/board');V.d=d;setIconsFrom(d);drawBoard()}
 function drawBoard(){const d=V.d,s=d.summary;$('tv-board').hidden=false;
  $('tb-sum').textContent=[plural(s.teams,'team'),plural(s.members,'member'),plural(s.running,'job')+' running',(s.needs_you?s.needs_you+' need'+(s.needs_you===1?'s':'')+' you':'nothing needs you')].join(' · ');
  if(d.costs){const c=d.costs;$('tb-sum').append(h('br'),'AI cost, '+c.label.toLowerCase()+(c.since?' ('+c.since+')':'')+': ',h('b',null,c.total.text),' ',fxLine(c.fx,''))}
  $('tb-sort').value=B.sort;
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
  const cost=t=>t.cost?t.cost.usd:0;const SORTS={needs:(a,b)=>(b.needs_you-a.needs_you)||a.name.localeCompare(b.name),name:(a,b)=>a.name.localeCompare(b.name),cost:(a,b)=>(cost(b)-cost(a))||a.name.localeCompare(b.name)};
  for(const g of names){const ts=groups.get(g).sort(SORTS[B.sort]||SORTS.needs);const sec=h('section',{class:'tm-group','aria-label':g||'Teams'});
   if(g)sec.append(h('h3',null,g,h('span',{class:'c'},plural(ts.length,'team'))));
   sec.append(B.view==='list'?teamTable(ts):h('div',{class:'tm-grid'},ts.map(teamCard)));box.append(sec)}}
 function teamCard(t){const c=h('article',{class:'tm-card'+(t.status==='draft'?' draft':'')});
  c.append(h('div',{class:'top'},mark(t.hex,t.icon),h('div',{class:'nm'},h('h4',null,h('a',{href:t.href},t.name)),h('div',{class:'meta'},[plural(t.members.length,'member'),t.autonomy_label].filter(Boolean).join(' · '))),pill(t.status,t.status_label)));
  if(t.description)c.append(h('p',{class:'purpose',title:t.description},t.description));
  if(t.members.length)c.append(h('div',{class:'tm-avs'},t.members.map(m=>avatar(m.initials,m.role,m.lead,t.hex))));
  if(t.status==='draft')c.append(h('div',{class:'missing'},h('b',null,'Not ready to run: '),t.missing.join(' · ')));
  if(t.job){c.append(h('div',{class:'live'},progBar(t.job.progress),h('a',{href:t.job.href},t.job.ref+' '+t.job.title),whereLine(t.job.where)))}
  c.append(h('div',{class:'foot'},h('span',null,plural(t.running,'job')+' running · '+t.done+' done'),t.cost?h('span',{title:'AI cost over the last 30 days, '+t.cost.note},t.cost.text+' in 30 days'):null,t.last_activity?h('span',null,'Last activity ',tm(t.last_activity)):null));return c}
 function teamTable(ts){const wrap=h('div',{class:'table-wrap'});const tb=h('table',{class:'tm-list'});
  tb.append(h('thead',null,h('tr',null,['Team','Members','Autonomy','Status','Live job','AI cost, 30 days','Last activity'].map(x=>h('th',{scope:'col',class:x.startsWith('AI cost')?'num':null},x)))));const body=h('tbody');
  for(const t of ts)body.append(h('tr',null,h('td',null,h('div',{class:'tn'},mark(t.hex,t.icon,'sm'),h('a',{href:t.href},t.name))),h('td',null,String(t.members.length)),h('td',null,t.autonomy_label),
   h('td',null,pill(t.status,t.status_label)),h('td',null,t.job?h('a',{href:t.job.href},t.job.ref):'—'),h('td',{class:'num'},money(t.cost)),h('td',null,t.last_activity?tm(t.last_activity):'')));
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
 const T={editOpen:false,talkOpen:false,pt:null};
 async function loadTeam(poll){const d=await api('/admin/api/teams/'+enc(V.tid)+'/page');V.d=d;setIconsFrom(d);
  const typing=T.editOpen||['knowledge','rules'].includes(tab)||(tab==='members'&&(document.body.classList.contains('ic-open')||!!M.grab));if(!poll||!typing)drawTeam();     // a refresh never wipes a form you are filling in or a card you are moving
  clearTimeout(V.timer);if(d.jobs.some(j=>j.status==='running'))V.timer=setTimeout(()=>run(()=>loadTeam(true)),3000)}
 function teamHead(){const d=V.d,t=d.team,idn=d.identity;const head=h('div',{class:'tm-thead'});
  const chips=h('div',{class:'tm-chips'},h('a',{class:'tm-chip',href:'#rules',onclick:()=>setTab('rules')},d.autonomy[t.autonomy]),...d.chips.map(c=>h('a',{class:'tm-chip'+(c.off?' off':''),href:c.href},c.label)),idn.discipline?h('span',{class:'tm-chip'},idn.discipline):null,pill(d.status,d.status_label));
  const pin=btn(d.pinned?'Unpin':'Pin',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/pin','PUT',{on:!d.pinned});d.pinned=!d.pinned;await loadTeam()},'secondary');pin.setAttribute('aria-pressed',d.pinned);pin.title=d.pinned?'Remove from Pinned teams':'Keep this team in Pinned teams';
  const edit=h('button',{type:'button',class:'secondary','aria-expanded':T.editOpen},'Edit team');edit.onclick=()=>{T.editOpen=!T.editOpen;drawTeam()};
  const ask=h('button',{type:'button',class:'secondary','aria-expanded':T.talkOpen},'Ask the team');ask.onclick=()=>{T.talkOpen=!T.talkOpen;drawTeam()};
  const start=h('a',{class:'button',href:'/admin/teams/'+enc(t.id)+'/start'},'Start a job');
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
   const ol=h('ol',{class:'tm-ol'});for(const o of pr.order)ol.append(h('li',{class:o.allowed===false?'off':null},h('b',null,o.title+(o.allowed===false?' (not allowed by the rule)':'')),h('span',{class:'small'},o.detail)));s.append(ol);if(pr.note)s.append(h('p',{class:'small'},pr.note));
   const links=h('p',{class:'small'},'Related rules: ');pr.rules.forEach((r,i)=>{if(i)links.append(', ');links.append(h('a',{href:r.href},r.name+(r.on?'':' (switched off)')))});links.append(pr.rules.length?' · ':'',h('a',{href:'/admin/rules#rules'},'Open the Rules page'));s.append(links);left.append(s)}
  // right: jobs and rules
  const jp=h('section',{class:'tm-panel','aria-labelledby':'tm-jobs-h'},h('h3',{id:'tm-jobs-h'},'Jobs',d.jobs.length?h('a',{href:'#jobs',onclick:e=>{e.preventDefault();setTab('jobs')}},'See all'):null));
  const hot=d.jobs.find(j=>j.pending.length||j.status==='blocked');
  if(hot)jp.append(jobRow(hot,true));for(const j of d.jobs.filter(j=>j!==hot).slice(0,5))jp.append(jobRow(j,false));
  if(!d.jobs.length)jp.append(h('p',{class:'tm-empty'},'No jobs yet.'));side.append(jp,rulesPanel(false));p.append(costCard())}
 function costCard(){const d=V.d,C=d.costs,t=d.team;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-cost-h'},h('h3',{id:'tm-cost-h'},'Running cost'));
  s.append(h('p',{class:'small muted'},'What each member’s AI calls cost, from the same figures as Usage and the Agents page. Tracking began '+C.since_text+'.'));
  const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-tbl tm-cost'});const P=C.periods;
  tb.append(h('thead',null,h('tr',null,h('th',{scope:'col'},'Member'),...P.map(p=>h('th',{scope:'col',class:'n'},p.label,p.since?h('div',{class:'small muted'},p.since):null)),h('th',{scope:'col',class:'n'},'AI per job'))));
  const body=h('tbody');for(const m of C.members){const yf=m.your_figures;const setYf=m.current?btn(yf?'Change':'Add',async()=>{const r=prompt('Your day rate for a person doing the '+m.role+' role, in pounds (leave empty to remove your figures):',yf?yf.day_rate:'');if(r===null)return;
    if(r.trim()===''){await api('/admin/api/teams/'+enc(t.id)+'/staff/'+enc(m.id),'PUT',{on:false});$('notice').textContent='Your figures for '+m.role+' removed.';await loadTeam();return}
    const n=prompt('Days a person would take for one job:',yf?yf.days:'');if(n===null||n.trim()==='')return;await api('/admin/api/teams/'+enc(t.id)+'/staff/'+enc(m.id),'PUT',{on:true,day_rate:Number(r),days:Number(n)});$('notice').textContent='Your figures for '+m.role+' saved.';await loadTeam()},'secondary'):null;
   if(setYf){setYf.textContent=yf?'Change your figures':'Add your figures';setYf.style.cssText='padding:1px 8px;font-size:12px;margin-top:3px'}
   body.append(h('tr',null,h('th',{scope:'row'},m.role+(m.current?'':' (no longer in the team)'),h('div',{class:'tm-yours'},yf?[h('b',null,yf.label+': '),yf.text+'. ',yf.note?h('span',{class:'muted'},yf.note+' '):null]:null,setYf)),
    ...P.map(p=>h('td',{class:'n'},money(m.costs[p.key]))),h('td',{class:'n',title:m.jobs?'Average over '+plural(m.jobs,'job')+' in the last 12 months':''},m.per_job?money(m.per_job):'—')))}
  tb.append(body,h('tfoot',null,h('tr',null,h('td',null,'Team total'),...P.map(p=>h('td',{class:'n'},money(C.total[p.key]))),h('td'))));wrap.append(tb);s.append(wrap);
  const rr=C.run_rate;s.append(h('p',{class:'small'},h('b',null,'Annual run rate: '),rr.value?[money(rr.value),h('span',{class:'tm-est'},rr.label),' '+rr.basis+'.']:[h('span',{class:'tm-est'},rr.label),' '+rr.basis]));
  if(C.before_tracking)s.append(h('p',{class:'small muted'},C.before_text+': ',money(C.before_tracking),'. Not split by member or period.'));
  s.append(h('p',{class:'small muted'},'Your figures are your own day rates and days for the human role, off unless you add them; Alice never supplies a market rate.'));
  s.append(fxLine(C.fx));return s}
 function jobRow(j,hl){const r=h('div',{class:'tm-jrow'+(hl?' hl':'')});const st=j.pending.length||j.status==='blocked'?['needs_you',j.status==='blocked'?'Stopped':'Needs you']:j.status==='done'?['done','Signed off']:j.status==='stopped'?['stopped','Stopped']:['running','Running'];
  r.append(h('div',{class:'l'},h('a',{href:'/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id},j.ref+' '+j.title),pill(st[0],st[1])));
  if(!['done','stopped'].includes(j.status))r.append(progBar(j.progress),whereLine(j.where));else r.append(h('div',{class:'small muted'},j.job_type_name+' · '+when(j.updated_at)));
  if(hl)r.append(h('div',null,h('a',{class:'button',href:'/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id},j.status==='blocked'?'Open':'Review')));return r}
 function rulesPanel(full){const d=V.d,R=d.rules;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-rules-h'+(full?'f':'')},h('h3',{id:'tm-rules-h'+(full?'f':'')},'Rules this team follows',h('a',{href:'/admin/rules#rules'},'Rules page')));
  const ul=h('ul',{class:'tm-rules'});for(const r of R.rules){ul.append(h('li',null,h('span',{class:'tm-tick'+(r.on?'':' off'),'aria-hidden':'true'},r.on?'✓':'✕'),h('div',null,h('a',{href:r.href},r.name),h('span',{class:'tm-sr'},r.on?' (on)':' (switched off)'),r.on?null:h('b',{class:'small'},' Switched off'),h('div',{class:'u'},r.use),full&&r.description?h('div',{class:'small'},r.description):null)))}
  s.append(ul);if(R.applied_packs.length)s.append(h('p',{class:'small'},'Rule packs applied to every model call: ',...R.applied_packs.map((x,i)=>[i?', ':'',h('a',{href:x.href},x.name)])));
  for(const m of R.member_packs)if(m.packs.length)s.append(h('p',{class:'small'},m.member+'’s own rule packs: '+m.packs.join(', ')));return s}
 // ---- Jobs tab: start a job, all jobs ----
 function drawJobsTab(p){const d=V.d,t=d.team;const sp=h('section',{class:'tm-panel',id:'tm-start'});
  sp.append(h('div',{class:'tm-head',style:'margin:0'},h('div',null,h('h3',{style:'margin:0'},'Start a job'),h('p',{class:'small muted',style:'margin:2px 0 0'},'The job, its documents and pricing template, and how it should be priced, on one screen.')),h('a',{class:'button',href:'/admin/teams/'+enc(t.id)+'/start'},'Start a job')));p.append(sp);
  const list=h('section',{class:'tm-panel'},h('h3',null,'All jobs'));if(!d.jobs.length)list.append(h('p',{class:'tm-empty'},'No jobs yet.'));
  else{const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-list'});tb.append(h('thead',null,h('tr',null,['Job','Status','Where it is','Started','AI cost'].map(x=>h('th',{scope:'col'},x)))));const body=h('tbody');
   for(const j of d.jobs){const st=j.pending.length?['needs_you','Needs you']:j.status==='blocked'?['blocked','Stopped']:j.status==='done'?['done','Signed off']:j.status==='stopped'?['stopped','Stopped']:['running','Running'];
    body.append(h('tr',null,h('td',null,h('a',{href:'/admin/teams/'+enc(t.id)+'/jobs/'+j.id},j.ref+' '+j.title),h('div',{class:'small muted'},j.job_type_name+' · team v'+j.team_version)),h('td',null,pill(st[0],st[1])),
     h('td',{style:'min-width:200px'},['done','stopped'].includes(j.status)?j.where:[progBar(j.progress),whereLine(j.where)]),h('td',null,when(j.created_at)),h('td',{class:'num'},money(d.costs.jobs[j.id]||{text:(d.costs.fx.rate?'£':'$')+'0.00',note:d.costs.fx.note}))))}
   tb.append(body);wrap.append(tb);list.append(wrap,fxLine(d.costs.fx,'AI costs'))}p.append(list)}
 // ---- Members tab ----
 function checks(all,on){const w=h('div',{class:'tm-checks'});const boxes=[];for(const [k,l] of all){const c=h('input',{type:'checkbox',value:k});c.checked=on.includes(k);boxes.push(c);w.append(h('label',null,c,l))}w.values=()=>boxes.filter(c=>c.checked).map(c=>c.value);return w}
 const field=(label,node)=>h('label',null,label,node);
 function suggBox(s){const w=h('div',{class:'tm-sugg'},h('strong',null,'Temple suggests new instructions'+(s.role?' for '+s.role:'')),h('p',{class:'small'},s.reason));
  w.append(h('details',null,h('summary',null,'Current instructions'),h('pre',null,s.current_text)),h('div',{class:'small'},'Suggested instructions'),h('pre',null,s.proposed));
  w.append(h('div',{class:'tm-acts'},btn('Approve: use these',async()=>{await api('/admin/api/teams/suggestions/'+s.id,'POST',{action:'approve'});$('notice').textContent='Applied as a new team version.';await loadTeam()}),btn('Reject',async()=>{await api('/admin/api/teams/suggestions/'+s.id,'POST',{action:'reject'});await loadTeam()},'secondary')));return w}
 // ---- Members tab (9 Oct 2026): cards in hand-off order with their costs for a period you choose; each card opens its editor
 // in the side panel (the information card pattern). Drag a card, or use its handle with the keyboard, to change the hand-off order.
 const M={grab:'',order:null,orig:null,ro:null};
 const memberPeriod=()=>{const C=V.d.member_costs;const k=store.get('member-period','30d');return C&&C.periods.some(p=>p.key===k)?k:'30d'};
 const initials=role=>((role||'?').match(/[A-Za-z0-9]+/g)||['?']).slice(0,2).map(w=>w[0]).join('').toUpperCase();
 function shownOrder(){const d=V.d,ms=d.team.members.slice();ms.sort((a,b)=>(b.id===d.lead)-(a.id===d.lead));return ms.map(m=>m.id)}
 function spark(trend,label){const W=120,H=28,vs=trend.map(x=>x.usd),hi=Math.max(...vs,0);const NS='http://www.w3.org/2000/svg';const svg=document.createElementNS(NS,'svg');
  svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.setAttribute('class','tm-spark');svg.setAttribute('role','img');
  svg.setAttribute('aria-label',label+', week by week: '+trend.map(x=>x.text).join(', '));
  const pts=vs.map((v,i)=>(i*(W-4)/(vs.length-1)+2).toFixed(1)+','+(hi?(H-3-(H-6)*v/hi):H-3).toFixed(1)).join(' ');
  const pl=document.createElementNS(NS,'polyline');pl.setAttribute('points',pts);svg.append(pl);
  const last=document.createElementNS(NS,'circle');const lp=pts.split(' ').pop().split(',');last.setAttribute('cx',lp[0]);last.setAttribute('cy',lp[1]);last.setAttribute('r','2.2');svg.append(last);
  const tt=document.createElementNS(NS,'title');tt.textContent=label+': '+trend.map(x=>x.text).join(' · ');svg.append(tt);return svg}
 function roleOfId(id){return (V.d.team.members.find(m=>m.id===id)||{role:'a former member'}).role}
 function warnList(ws,m){if(!ws.length)return null;const ul=h('ul',{class:'tm-mwarn','aria-label':'Warnings'});
  for(const w of ws)ul.append(h('li',null,w.text,w.href?[' ',h('a',{href:w.href},'Open the rule')]:null));return ul}
 function memberCardM(m,i,n){const d=V.d,C=d.member_costs,mv=d.member_view[m.id]||{to:[],from:[],warnings:[],works_on:[],builtin_tools:[]},per=memberPeriod(),lead=m.id===d.lead;
  const li=h('li',{class:'tm-mc'+(lead?' lead':'')+(M.grab===m.id?' grab':''),'data-mid':m.id,draggable:'true'});
  const card=h('article',{class:'tm-mcd','aria-labelledby':'tm-mc-'+m.id});if(lead)card.style.borderColor=d.identity.hex;
  const open=h('button',{type:'button',class:'tm-mc-open',id:'tm-mc-'+m.id,'aria-haspopup':'dialog'},m.role);open.onclick=()=>openMember(m.id);
  const handle=h('button',{type:'button',class:'tm-handle','aria-label':'Move '+m.role+': position '+(i+1)+' of '+n+'. Press Space to pick up, arrow keys to move, Space again to drop, Escape to cancel.','aria-pressed':String(M.grab===m.id),title:'Drag to change the hand-off order, or press Space then the arrow keys'},'⠿');
  handle.onkeydown=e=>moveKey(e,m.id);handle.onclick=e=>e.stopPropagation();
  card.append(h('div',{class:'top'},avatar(mv.initials||initials(m.role),m.role,lead,d.identity.hex,'lg'),h('div',{class:'nm'},h('h4',null,open),m.purpose?h('p',{class:'purpose'},m.purpose):h('p',{class:'purpose muted'},'No purpose yet.')),lead?h('span',{class:'tm-chip tm-lead'},'Lead'):null,handle));
  const tools=(d.member_tools[m.id]||[]),cats=m.categories||[],packs=(m.packs||[]).map(k=>d.packs[k]||k);
  const chips=h('div',{class:'tm-chips tm-mchips'},h('span',{class:'tm-chip',title:'Model'},d.models[m.provider]||m.provider),...tools.map(x=>h('span',{class:'tm-chip t'},x)),
   ...(cats.length?cats.map(x=>h('span',{class:'tm-chip k',title:'Knowledge category'},x)):[]),...packs.map(x=>h('span',{class:'tm-chip p',title:'Its own rule pack'},x)));card.append(chips);
  if(C){const mc=C.members[m.id],P=C.periods.find(x=>x.key===per);const share=mc.share_pct[per];
   card.append(h('div',{class:'tm-mcost'},h('div',{class:'big'},money(mc.costs[per],C.fx),P.since?h('span',{class:'small muted'},' '+P.since):null),
    h('div',{class:'small'},share==null?'No team cost in this period':share+'% of the team',' · ',plural(mc.jobs[per],'job'),mc.per_job[per]?[' · ',money(mc.per_job[per],C.fx),' a job on average']:null),
    spark(mc.trend,m.role+'’s AI cost over the last 12 weeks')))}
  const st=d.member_states[m.id];const lr=mv.last_run;
  card.append(h('div',{class:'tm-mrun'},st&&st.state!=='idle'?h('span',{class:'tm-state '+st.state},st.label+(st.job?' · '+st.job:'')):null,st&&st.state!=='idle'&&lr?' · ':null,
   lr?[h('span',{class:lr.status==='failed'?'tm-state blocked':'muted'},'Last ran '),tm(lr.at),' on ',h('a',{href:'/admin/teams/'+enc(lr.team_id)+'/jobs/'+lr.job_id},lr.job_ref),' · ',h('b',{class:lr.status==='failed'?'tm-state blocked':''},lr.label)]:(st&&st.state!=='idle'?null:h('span',{class:'muted'},'Has not run a job yet'))));
  if(mv.to.length)card.append(h('p',{class:'tm-mflow'},'Hands work to ',h('b',null,mv.to.map(roleOfId).join(', '))));
  const wl=warnList(mv.warnings,m);if(wl)card.append(wl);
  if(d.suggestions.some(s=>s.member===m.id))card.append(h('p',{class:'tm-msugg'},'Temple suggests new instructions: open to review'));
  li.append(card);
  li.ondragstart=e=>{M.drag=m.id;li.classList.add('dragging');try{e.dataTransfer.setData('text/plain',m.id);e.dataTransfer.effectAllowed='move'}catch{}};
  li.ondragend=()=>{li.classList.remove('dragging');M.drag='';document.querySelectorAll('.tm-mc.over').forEach(x=>x.classList.remove('over'))};
  li.ondragover=e=>{if(!M.drag||M.drag===m.id)return;e.preventDefault();li.classList.add('over')};li.ondragleave=()=>li.classList.remove('over');
  li.ondrop=e=>{e.preventDefault();li.classList.remove('over');const from=M.drag;if(!from||from===m.id)return;const o=shownOrder().filter(x=>x!==from);o.splice(o.indexOf(m.id)+(shownOrder().indexOf(from)<shownOrder().indexOf(m.id)?1:0),0,from);run(()=>saveOrder(o))};
  return li}
 function addCard(){const d=V.d,li=h('li',{class:'tm-mc add'});const c=h('div',{class:'tm-mcd tm-madd'},h('h4',null,'Add a member'),h('p',{class:'small muted'},'Start from:'));
  const row=h('div',{class:'tm-acts'});for(const [k,x] of Object.entries(d.member_templates)){const b=h('button',{type:'button',class:'secondary'},x.label);b.onclick=()=>openMember('',k);row.append(b)}
  c.append(row,h('p',{class:'small muted'},'You can change everything before you save it. Then give it a stage on Rules and autonomy.'));li.append(c);return li}
 function placeArrows(grid){const items=[...grid.querySelectorAll('.tm-mc:not(.add)')];items.forEach((li,i)=>{li.classList.remove('arr-r','arr-d');const nx=items[i+1];if(!nx)return;
  const mv=V.d.member_view[li.dataset.mid];if(!mv||!mv.to.includes(nx.dataset.mid))return;if(Math.abs(nx.offsetTop-li.offsetTop)<4)li.classList.add('arr-r');else if(Math.abs(nx.offsetLeft-li.offsetLeft)<4)li.classList.add('arr-d')})}
 function drawGrid(grid){const d=V.d,t=d.team;const ids=M.order||shownOrder();const byId=Object.fromEntries(t.members.map(m=>[m.id,m]));
  grid.replaceChildren(...ids.map((id,i)=>memberCardM(byId[id],i,ids.length)),addCard());requestAnimationFrame(()=>placeArrows(grid));
  if(M.ro)M.ro.disconnect();if(window.ResizeObserver){M.ro=new ResizeObserver(()=>placeArrows(grid));M.ro.observe(grid)}}
 function drawMembersTab(p){const d=V.d,t=d.team,C=d.member_costs,per=memberPeriod();
  const head=h('div',{class:'tm-mhead'});
  if(C){const seg=h('div',{class:'tm-seg tm-period',role:'group','aria-label':'Costs for'});for(const pr of C.periods){const b=h('button',{type:'button',class:'ghost','aria-pressed':String(pr.key===per)},pr.label);b.onclick=()=>{store.set('member-period',pr.key);drawTeam()};seg.append(b)}
   const P=C.periods.find(x=>x.key===per);head.append(seg,h('p',{class:'tm-mtot'},'Team total, '+P.label.toLowerCase()+(P.since?' ('+P.since+')':'')+': ',h('b',null,money(C.total[per],C.fx)),
    C.former[per].usd?h('span',{class:'small muted'},' (includes ',money(C.former[per],C.fx),' by members no longer in the team)'):null));head.append(fxLine(C.fx))}
  else head.append(h('p',{class:'small muted'},'Costs are not shown: your permissions for this team do not include seeing costs.'));
  p.append(head);
  p.append(h('p',{class:'small muted tm-mhelp'},'In hand-off order, the lead first. Click a member to edit it; drag a card, or use its ⠿ handle with Space and the arrow keys, to change the order. '
   +(d.reorderable.length?'The stages of '+d.reorderable.join(', ')+' follow the order. ':'')+'Job types with built-in steps keep their stage order (Rules and autonomy). Every change is a new team version.'));
  for(const s of d.suggestions.filter(s=>!t.members.some(m=>m.id===s.member)))p.append(suggBox(s));
  const grid=h('ol',{class:'tm-mgrid','aria-label':'Members in hand-off order'});p.append(grid,h('p',{class:'tm-sr','aria-live':'assertive',id:'tm-move-live'}));drawGrid(grid)}
 async function saveOrder(order){const t=V.d.team;await api('/admin/api/teams/'+enc(t.id)+'/member-order','PUT',{order});M.order=null;M.grab='';$('notice').textContent='Hand-off order saved as a new team version.';await loadTeam()}
 function moveKey(e,mid){const live=$('tm-move-live'),grid=document.querySelector('.tm-mgrid');const say=x=>{if(live)live.textContent=x};
  if(e.key===' '||e.key==='Enter'){e.preventDefault();if(M.grab!==mid){M.grab=mid;M.order=shownOrder();M.orig=M.order.slice();drawGrid(grid);say(roleOfId(mid)+' picked up. Use the arrow keys to move it, Space to drop it, Escape to cancel.')}
   else{const o=M.order,changed=o.join()!==M.orig.join();M.grab='';if(!changed){M.order=null;drawGrid(grid);say('Order unchanged.')}else{say(roleOfId(mid)+' dropped at position '+(o.indexOf(mid)+1)+'. Saving.');run(()=>saveOrder(o))}}
   focusHandle(mid);return}
  if(e.key==='Escape'&&M.grab===mid){e.preventDefault();M.grab='';M.order=null;drawGrid(grid);focusHandle(mid);say('Move cancelled.');return}
  if(M.grab!==mid||!['ArrowUp','ArrowLeft','ArrowDown','ArrowRight'].includes(e.key))return;e.preventDefault();
  const o=M.order,i=o.indexOf(mid),j=i+(e.key==='ArrowUp'||e.key==='ArrowLeft'?-1:1);if(j<0||j>=o.length){say(j<0?'Already first.':'Already last.');return}
  [o[i],o[j]]=[o[j],o[i]];drawGrid(grid);focusHandle(mid);say(roleOfId(mid)+', position '+(j+1)+' of '+o.length+'.')}
 function focusHandle(mid){const x=document.querySelector('.tm-mc[data-mid="'+CSS.escape(mid)+'"] .tm-handle');if(x)x.focus()}
 // A word-by-word comparison of two texts (standing instructions), for "What changed". Comparison only: nothing is calculated here.
 function wordDiff(a,b){const A=(a||'').split(/(\s+)/).filter(x=>x!==''),B=(b||'').split(/(\s+)/).filter(x=>x!=='');const n=A.length,m=B.length;if(n*m>2500000)return null;
  const L=[];for(let i=0;i<=n;i++)L.push(new Uint16Array(m+1));for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)L[i][j]=A[i]===B[j]?L[i+1][j+1]+1:Math.max(L[i+1][j],L[i][j+1]);
  const out=[];let i=0,j=0;const push=(k,x)=>{const l=out[out.length-1];if(l&&l[0]===k)l[1]+=x;else out.push([k,x])};
  while(i<n&&j<m){if(A[i]===B[j]){push(' ',A[i]);i++;j++}else if(L[i+1][j]>=L[i][j+1])push('-',A[i++]);else push('+',B[j++])}while(i<n)push('-',A[i++]);while(j<m)push('+',B[j++]);return out}
 function diffView(box,prev,now,label){box.replaceChildren();if(prev==null){box.append(h('p',{class:'small muted'},label));return}
  if((prev||'').trim()===(now||'').trim()){box.append(h('p',{class:'small muted'},'No change: the same as '+label+'.'));return}
  const parts=wordDiff(prev,now);if(!parts){box.append(h('p',{class:'small muted'},'Too long to compare word by word.'));return}
  const words=k=>parts.filter(x=>x[0]===k).reduce((n,x)=>n+(x[1].match(/\S+/g)||[]).length,0);
  box.append(h('p',{class:'small'},'Compared with '+label+': '+plural(words('+'),'word')+' added, '+plural(words('-'),'word')+' removed.'),
   h('div',{class:'tm-diff'},...parts.map(([k,x])=>k===' '?x:h(k==='+'?'ins':'del',null,x))))}
 function openMember(mid,tpl){const d=V.d,t=d.team,isNew=!mid;const src=isNew?{...d.member_templates[tpl||'blank']}:t.members.find(m=>m.id===mid);if(!src)return;
  const m={role:src.role||'',purpose:src.purpose||'',instructions:src.instructions||'',provider:src.provider||'claude_sonnet',categories:src.categories||[],packs:src.packs||[],tools:src.tools||null};
  const mv=isNew?{to:[],from:[],warnings:[],works_on:[],builtin_tools:[]}:d.member_view[mid];
  const role=h('input',{type:'text',maxlength:'80',value:m.role,required:true,placeholder:'e.g. Services Engineer'}),prov=h('select');for(const [k,l] of Object.entries(d.models))prov.append(h('option',{value:k},l));prov.value=m.provider;
  const purpose=h('textarea',{maxlength:'600',rows:'3'});purpose.value=m.purpose;const ins=h('textarea',{maxlength:'6000',rows:'16',class:'tm-ins'});ins.value=m.instructions;
  const sw=isNew?Object.fromEntries(Object.keys(d.tool_names).map(k=>[k,!!(m.tools&&m.tools[k])])):(d.tool_switches[mid]||{});const tools=checks(Object.entries(d.tool_names),Object.keys(sw).filter(k=>sw[k]));
  const cats=checks(d.categories.map(x=>[x,x]),m.categories),packs=checks(Object.entries(d.packs),m.packs);
  const secs=[];const P=d.previous;
  const roleBox=h('div',{class:'tm-ed'},field('Role name',role),field('Model',prov));
  if(!isNew){if(mv.works_on.length)roleBox.append(h('p',{class:'small'},h('b',null,'Works on: '),mv.works_on.join(', ')));
   if(mv.from.length||mv.to.length)roleBox.append(h('p',{class:'small'},mv.from.length?['Gets work from ',h('b',null,mv.from.map(roleOfId).join(', ')),'. ']:null,mv.to.length?['Hands work to ',h('b',null,mv.to.map(roleOfId).join(', ')),'.']:null))}
  const wl=warnList(mv.warnings,m);if(wl)roleBox.prepend(wl);
  secs.push({key:'what',title:'Role and model',node:roleBox},{key:'why',title:'Purpose',node:h('div',{class:'tm-ed'},field('One line: what this member is for',purpose))});
  const diff=h('div',{class:'tm-diffbox','aria-live':'polite'});const prev=isNew?null:(P.members[mid]||null);
  const lab=isNew?'This member is new.':!P.version?'There is no earlier version of the team.':!prev?'This member was added in v'+t.version+'.':'v'+P.version+' (before v'+t.version+': '+P.what+')';
  const redraw=()=>diffView(diff,prev?prev.instructions||'':null,ins.value,lab);let tmr=null;ins.oninput=()=>{clearTimeout(tmr);tmr=setTimeout(redraw,250)};redraw();
  const insBox=h('div',{class:'tm-ed'},field('Standing instructions',ins),h('details',{class:'tm-changed',open:true},h('summary',null,'What changed'),diff));
  if(!isNew){for(const s of d.suggestions.filter(s=>s.member===mid))insBox.append(suggBox(s));insBox.append(coachTalk(t.members.find(x=>x.id===mid)))}
  secs.push({key:'what',title:'Standing instructions',node:insBox});
  secs.push({key:'technical',title:'Tools',node:h('div',{class:'tm-ed'},tools,mv.builtin_tools.length?h('p',{class:'small muted'},'Its stages also use: '+mv.builtin_tools.join(', ')+' (built in).'):null)});
  secs.push({key:'related',title:'Knowledge',node:h('div',{class:'tm-ed'},d.categories.length?cats:h('p',{class:'small muted'},'There are no categories yet: create them on the Memories page.'),h('p',{class:'small muted'},'Only active knowledge in the ticked categories, never Local only items, only what its model may receive, and only the clients’ material the Rules page allows.'))});
  secs.push({key:'where',title:'Rule packs',node:h('div',{class:'tm-ed'},packs,h('p',{class:'small muted'},'Its own packs apply to every call it makes, on top of the packs applied to Alice’s live rules.'))});
  const C=d.member_costs;if(!isNew&&C){const mc=C.members[mid];const tb=h('table',{class:'tm-tbl tm-cost'},h('thead',null,h('tr',null,h('th',{scope:'col'},'Period'),h('th',{scope:'col',class:'n'},'Cost'),h('th',{scope:'col',class:'n'},'Share'),h('th',{scope:'col',class:'n'},'Jobs'),h('th',{scope:'col',class:'n'},'Per job'))));
   const body=h('tbody');for(const pr of C.periods)body.append(h('tr',null,h('th',{scope:'row'},pr.label,pr.since?h('div',{class:'small muted'},pr.since):null),h('td',{class:'n'},money(mc.costs[pr.key],C.fx)),h('td',{class:'n'},mc.share_pct[pr.key]==null?'—':mc.share_pct[pr.key]+'%'),h('td',{class:'n'},String(mc.jobs[pr.key])),h('td',{class:'n'},money(mc.per_job[pr.key],C.fx))));tb.append(body);
   const jl=h('ul',{class:'tm-ver'});for(const j of mc.last_jobs)jl.append(h('li',null,h('div',{class:'h'},h('a',{href:'/admin/teams/'+enc(t.id)+'/jobs/'+j.job_id},j.ref+' '+j.title),h('span',{class:'c'},money(j.cost,C.fx))),h('div',{class:'small muted'},'Last worked on '+when(j.at))));
   secs.push({key:'when',title:'Cost',node:h('div',{class:'tm-ed'},h('div',{class:'table-wrap'},tb),h('h4',{style:'margin:12px 0 4px'},mc.last_jobs.length>1?'Its last '+plural(mc.last_jobs.length,'job'):'Its last job'),mc.last_jobs.length?jl:h('p',{class:'small muted'},'No jobs yet.'),fxLine(C.fx))})}
  const msg=h('p',{class:'small tm-edmsg',role:'status'});
  const body=()=>({role:role.value,purpose:purpose.value,instructions:ins.value,provider:prov.value,categories:cats.values?cats.values():[],packs:packs.values(),tools:Object.fromEntries(Object.keys(d.tool_names).map(k=>[k,tools.values().includes(k)]))});
  const save=h('button',{type:'button',class:'primary'},isNew?'Add to the team':'Save as a new version'),cancel=h('button',{type:'button',class:'secondary'},'Cancel');cancel.onclick=()=>closeCard();
  save.onclick=async()=>{if(!role.value.trim()){msg.textContent='Give the member a role name.';role.focus();return}save.disabled=true;msg.textContent='Saving…';
   try{if(isNew)await api('/admin/api/teams/'+enc(t.id)+'/members','POST',{...body(),template:tpl||'blank'});else await api('/admin/api/teams/'+enc(t.id)+'/members/'+enc(mid),'PUT',body());
    closeCard();$('notice').textContent=isNew?role.value.trim()+' added as a new team version. Give it a stage on Rules and autonomy.':'Saved as a new team version.';await loadTeam()}
   catch(e){msg.textContent=e.message}finally{save.disabled=false}};
  const foot=h('div',{class:'tm-edfoot'},save,cancel);
  if(!isNew){const rm=h('button',{type:'button',class:'secondary tm-rm'},'Remove from the team');rm.onclick=async()=>{if(!confirm('Remove '+src.role+' from the team? Jobs already run keep the version they ran on, and you can undo this on the Activity tab.'))return;
   rm.disabled=true;try{await api('/admin/api/teams/'+enc(t.id)+'/members/'+enc(mid),'DELETE');closeCard();$('notice').textContent=src.role+' removed (a new team version).';await loadTeam()}catch(e){msg.textContent=e.message}finally{rm.disabled=false}};foot.append(rm)}
  foot.append(msg);
  const first=JSON.stringify(body());const go=x=>()=>{if(JSON.stringify(body())!==first&&!confirm('Discard your changes to '+(src.role||'this member')+'?'))return;openMember(x)};
  const ids=shownOrder(),i=ids.indexOf(mid);
  openCard({kind_label:'Digital team · '+(isNew?'New member':'Member'),title:isNew?'New member: '+(d.member_templates[tpl||'blank'].label):src.role,subtitle:t.name+' · team v'+t.version+(mid===d.lead?' · Lead':''),
   badge:mv.warnings.length?plural(mv.warnings.length,'warning'):'',tone:mv.warnings.length?'warn':'',sections:secs},
   {wide:true,footer:()=>foot,position:isNew?'':(i+1)+' of '+ids.length,prev:isNew||i<1?null:go(ids[i-1]),next:isNew||i>=ids.length-1?null:go(ids[i+1])});
  setTimeout(()=>{(isNew?role:null)?.focus()},50)}
 function coachTalk(m){const t=V.d.team;const wrap=h('details',{class:'dec-talk'});wrap.append(h('summary',null,h('span',{class:'dec-talk-t'},'Ask Temple about '+m.role),h('span',{class:'small muted'},' How its jobs went, and better instructions (applied only if you approve)')));
  const url='/admin/api/teams/'+enc(t.id)+'/members/'+enc(m.id)+'/discussion';const log=h('div',{class:'dec-talk-log'}),form=h('form',{class:'dec-talk-form'}),ta=h('textarea',{rows:'2',maxlength:'4000',placeholder:'Ask Temple, e.g. what keeps being sent back?','aria-label':'Message to Temple'}),send=h('button',{type:'submit'},'Send');
  const starters=h('div',{class:'dec-talk-starters'});for(const s of ['How could '+m.role+'’s instructions be better?','What keeps being sent back, and why?','What did I have to correct?']){const x=h('button',{type:'button',class:'chip'},s);x.onclick=()=>{ta.value=s;form.requestSubmit()};starters.append(x)}
  form.append(ta,send);wrap.append(log,starters,form);let loaded=false;
  const show=ms=>{log.replaceChildren(...ms.map(x=>h('div',{class:'dec-msg '+(x.role==='temple'?'from-t':'from-you')},h('div',{class:'who'},x.role==='temple'?'Temple':'You'),h('div',{class:'txt'},x.content),x.note?h('div',{class:'small'},'Suggestion waiting for your approval above: '+x.note):null)));starters.hidden=ms.length>0;log.scrollTop=log.scrollHeight};
  wrap.addEventListener('toggle',()=>{if(wrap.open&&!loaded){loaded=true;run(async()=>show((await api(url)).messages))}});
  form.onsubmit=e=>{e.preventDefault();const msg=ta.value.trim();if(!msg||send.disabled)return;send.disabled=true;ta.value='';const wait=h('div',{class:'dec-msg from-t thinking'},'Temple is thinking…');log.append(wait);
   run(async()=>{try{const r=await api(url,'POST',{message:msg});show(r.messages);if(r.suggestion){$('notice').textContent='Temple suggested new instructions: they wait for your approval.';await loadTeam()}}catch(err){wait.remove();ta.value=msg;throw err}finally{send.disabled=false}})};return wrap}
 // ---- Knowledge tab: categories per member, the rate library ----
 function filingPanel(){const d=V.d,t=d.team,f=d.filing;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-file-h'},h('h3',{id:'tm-file-h'},'File finished work in'),h('p',{class:'small muted'},'When you sign off a job, the team proposes a short summary (scope, location, date, rates used with their sources, total, what was estimated or left unpriced) to Knowledge in this category, through the usual checks, tagged to the job\'s client and linked to the job. Temple may add tags but never moves it.'));
  const on=h('input',{type:'checkbox'});on.checked=!!f.on;const cat=h('select',{'aria-label':'Category to file finished work in'});const names=[...new Set(d.categories.concat(f.category&&!f.exists?[f.category]:[]))];
  for(const x of names)cat.append(h('option',{value:x},x+(x===f.category&&!f.exists?' (not created yet)':'')));cat.value=f.category||names[0]||'';
  s.append(h('div',{class:'tm-acts'},h('label',null,on,' File finished work'),cat,btn('Save',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/filing','PUT',{on:on.checked,category:cat.value});$('notice').textContent='Saved as a new team version.';await loadTeam()},'secondary')));
  if(f.category&&!f.exists)s.append(h('p',{class:'small',role:'note'},'“'+f.category+'” does not exist yet, so finished work cannot be filed there. ',btn('Create “'+f.category+'”',async()=>{await api('/admin/api/teams/'+enc(t.id)+'/filing/category','POST',{});$('notice').textContent='Category created.';await loadTeam()},'secondary')));
  return s}
 function drawKnowledgeTab(p){const d=V.d,t=d.team;p.append(filingPanel(),pricingPanel());const s=h('section',{class:'tm-panel'},h('h3',null,'Knowledge each member may use'),h('p',{class:'small muted'},'Members read only active knowledge in the categories ticked here, never Local only items, only what their model may receive, and only the clients’ material the Rules page allows. None ticked = no knowledge.'));
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
  const mi=h('section',{class:'tm-panel tm-auto'},h('h3',null,'When information is missing'));
  for(const [k,l] of Object.entries(d.missing_info_options)){const r=h('input',{type:'radio',name:'tm-missing',value:k});r.checked=d.missing_info===k;r.onchange=()=>run(async()=>{await api('/admin/api/teams/'+enc(t.id)+'/missing-info','PUT',{mode:k});$('notice').textContent='Saved as a new team version: '+l+'. Jobs already started keep the version they started on.';await loadTeam()});
   mi.append(h('label',null,r,h('span',null,h('strong',null,l),h('div',{class:'small muted'},k==='ask'?'A member that lacks something it needs asks you, and waits for your answer.':'A member states a reasonable assumption and carries on; every assumption is listed in the cost plan, the outputs and the filled templates. It asks only when an assumption would change the result materially, and says why.'))))}
  p.append(a,mi,rulesPanel(true));const jts=h('section',{class:'tm-panel'},h('h3',null,'Job types and hand-offs'),h('p',{class:'small muted'},'Each stage says who works, what they hand on, and what the next member checks before accepting it. The receiver can send work back with reasons.'));drawTypes(jts);p.append(jts)}
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
  for(const s of steps)ul.append(h('li',null,s.member==='you'?avatar('You','You',false,'','you'):avatar(((s.role||'?').match(/[A-Za-z0-9]+/g)||['?']).slice(0,2).map(w=>w[0]).join('').toUpperCase(),s.role||'A member'),h('div',null,h('span',{class:'w'},(s.member==='you'?'You':s.role)+' '+(KIND[s.kind]||s.kind)),' · ',h('a',{href:'/admin/teams/'+enc(t.id)+'/jobs/'+s.job.id},s.job.ref),h('div',null,s.note||''),tm(s.created_at))));
  recent.append(ul);p.append(v,recent)}
 // ---------- Talk to the team (a team or a job) ----------
 function talkPanel(tid,jid){const key=tid+'/'+(jid||'');V.talk=V.talk||{};if(V.talk[key])return V.talk[key];const box=h('div',{class:'tm-talk'});V.talk[key]=box;const log=h('div',{class:'log','aria-live':'polite'}),ta=h('textarea',{maxlength:'4000',placeholder:'Write to the team. The lead answers and passes it on to whoever should act.','aria-label':'Message to the team'}),send=h('button',{type:'submit'},'Send');
  const form=h('form',null,ta,send);box.append(log,form);
  const linked=m=>m.role==='you'?[m.content]:String(m.content).split(/(\/admin\/[^\s,]+)/).map((x,i)=>i%2?h('a',{href:x},x.includes('/rules')?'Open the rule':'Open the job'):x);
  const show=ms=>{log.replaceChildren(...(ms.length?ms.map(m=>h('div',{class:'tm-msg '+(m.role==='you'?'you':'lead')},h('span',{class:'w'},m.who+' · '+when(m.created_at)),...linked(m),m.routed_role?h('span',{class:'r'},'Passed on to '+m.routed_role+': '+m.note):null)):[h('p',{class:'tm-empty'},'No messages yet.')]));log.scrollTop=log.scrollHeight};
  run(async()=>show((await api('/admin/api/teams/'+enc(tid)+'/talk'+(jid?'?job='+jid:''))).messages));
  form.onsubmit=e=>{e.preventDefault();const msg=ta.value.trim();if(!msg||send.disabled)return;send.disabled=true;ta.value='';const wait=h('div',{class:'tm-msg lead'},'Writing…');log.append(wait);
   run(async()=>{try{const r=await api('/admin/api/teams/'+enc(tid)+'/talk','POST',{message:msg,job:jid||''});show(r.messages);if(r.routed_to&&jid)await loadJob()}catch(err){wait.remove();ta.value=msg;throw err}finally{send.disabled=false}})};return box}
 // ---------- Screen 3: a job ----------
 const J={src:'all',panel:'',sel:null,els:null,est:false,trends:false,order:null,note:'',client:null,title:''};
 async function loadJob(){const d=await api('/admin/api/teams/jobs/'+V.jid+'/page');V.d=d;setIconsFrom(d.nav);if(d.team_id!==V.tid){location.replace(d.url);return}
  const qa=new URLSearchParams(location.search).get('add');if(qa!==null&&!J.addOpened){J.addOpened=true;if(d.can.add_files){J.panel='files';J.add={docs:[],els:[],note:'',answers:/^[0-9a-f]{32}$/.test(qa)&&d.pending.some(x=>x.id===qa)?qa:''}}}
  drawJob();clearTimeout(V.timer);if(d.status==='running')V.timer=setTimeout(()=>run(loadJob),2500)}
 // ---- Add files to a job that has started (9 Oct 2026): the Start screen's roles; re-runs only what depends on them ----
 const ROLE_NAMES={drawing:'Drawing',spec:'Specification',schedule:'Schedule',template:'Cost/pricing template',brief:'Other'};
 function filesPanel(){const d=V.d;const s=h('section',{class:'tm-rp',id:'tm-rp','aria-labelledby':'tm-rp-h'});J.add=J.add||{docs:[],els:[],note:''};const A=J.add;
  const q=A.answers?d.pending.find(x=>x.id===A.answers):null;
  s.append(h('h3',{id:'tm-rp-h'},q?'Add a file to answer '+(q.role||'the member'):'Add files to this job'),
   h('p',{class:'small muted'},q?'The file answers the question: '+(q.content.questions||[]).join(' ')+' The member carries on with it.':
    'Same roles and checks as the Start screen. Only the work that depends on the new files is done again, as a new version'+(d.status==='running'?' (once the team stops for you)':'')+'; work not done yet simply uses them.'));
  const file=h('input',{type:'file',multiple:true,accept:'.pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md,.png,.jpg,.jpeg,.webp','aria-label':'Files to add'});
  file.onchange=()=>run(async()=>{for(const fl of file.files){if(fl.size>15*1024*1024)throw Error(fl.name+' is larger than 15 MB.');const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(Error('Could not read '+fl.name));r.readAsDataURL(fl)});
    const doc={name:fl.name,data,role:'brief'};try{const info=await api('/admin/api/teams/'+enc(d.team_id)+'/inspect','POST',{name:fl.name,data});doc.role=info.guess;doc.info=info}catch(e){doc.info={problem:e.message}}A.docs.push(doc)}file.value='';drawJob()});
  s.append(h('div',{class:'tm-acts'},h('label',{class:'small'},'Choose files ',file)));
  const ul=h('div',{class:'ts-files'});for(const doc of A.docs){const sel=h('select',{'aria-label':'Role of '+doc.name});for(const [k,l] of Object.entries(ROLE_NAMES)){if(q&&k==='template')continue;sel.append(h('option',{value:k},l))}sel.value=doc.role;sel.onchange=()=>{doc.role=sel.value};
   const rm=h('button',{type:'button',class:'secondary'},'Remove');rm.onclick=()=>{A.docs=A.docs.filter(x=>x!==doc);drawJob()};
   ul.append(h('div',{class:'ts-file'+(doc.role==='template'?' tpl':'')},h('div',null,h('div',{class:'nm'},doc.name),h('div',{class:'meta'},[(doc.info||{}).type,(doc.info||{}).pages?plural(doc.info.pages,'page'):'',(doc.info||{}).label?'Label: '+doc.info.label:''].filter(Boolean).join(' · ')),(doc.info||{}).problem?h('div',{class:'prob'},doc.info.problem):null),sel,rm))}
  if(A.docs.length)s.append(ul);
  if(!q&&d.elements.length){const box=h('div',{class:'items',role:'group','aria-label':'Elements these files concern'});for(const e of d.elements){const c=h('input',{type:'checkbox',value:e});c.checked=A.els.includes(e);c.onchange=()=>{A.els=c.checked?[...A.els,e]:A.els.filter(x=>x!==e)};box.append(h('label',null,c,e))}
   s.append(h('p',{class:'small',style:'margin:8px 0 0'},h('b',null,'Which elements do they concern? '),'Those measured already are measured again from the documents, and only their items priced again. None ticked = every element.'),box)}
  const note=h('textarea',{maxlength:'1000',placeholder:'A note for the team (optional), e.g. revision B replaces the first floor plan','aria-label':'A note for the team'});note.value=A.note;note.oninput=()=>{A.note=note.value};s.append(note);
  const cancel=h('button',{type:'button',class:'secondary'},'Cancel');cancel.onclick=()=>{J.panel='';J.add=null;drawJob()};
  s.append(h('div',{class:'tm-acts'},btn(q?'Add and answer':'Add to the job',async()=>{if(!A.docs.length)throw Error('Choose a file to add.');let msg=[];
   for(const doc of A.docs.filter(x=>x.role==='template')){const x=await api('/admin/api/teams/'+enc(d.team_id)+'/pricing-templates','POST',{name:doc.name,data:doc.data});await api('/admin/api/teams/jobs/'+d.id+'/template','PUT',{path:x.path});msg.push(doc.name+' is now this job\'s pricing template and has been filled again.')}
   const rest=A.docs.filter(x=>x.role!=='template');if(rest.length){const r=await api('/admin/api/teams/jobs/'+d.id+'/files','POST',{uploads:rest.map(x=>({name:x.name,data:x.data,kind:x.role})),elements:A.els,answers:A.answers||'',note:A.note});msg.push(r.message)}
   J.panel='';J.add=null;$('notice').textContent=msg.join(' ');await loadJob()}),cancel));return s}
 function openAdd(answers){J.panel='files';J.add={docs:[],els:[],note:'',answers:answers||''};drawJob();const x=$('tm-rp');if(x)x.scrollIntoView({block:'nearest'})}
 function assumedPanel(){const d=V.d;if(!d.assumed.length)return null;const s=h('section',{class:'tm-panel tm-assumed','aria-labelledby':'tm-asm-h'},h('h3',{id:'tm-asm-h'},'Assumed where information was missing'),
   h('p',{class:'small muted'},d.missing_info.mode==='assume'?'The team is set to Assume and flag: it carried on with these instead of asking you. Each is listed in the cost plan, the workbook and the filled template.':'Assumptions the team still made, listed in the outputs.'));
  const ul=h('ul',{class:'tm-asm'});for(const a of d.assumed)ul.append(h('li',null,a.assumption,a.why?h('div',{class:'small muted'},'Missing: '+a.why):null,a.affects?h('div',{class:'small muted'},'Affects: '+a.affects):null,h('div',{class:'small muted'},a.role+' · '+a.stage_title)));s.append(ul);return s}
 function drawingsPanel(){const d=V.d,x=d.drawings;if(!x||!x.pages.length)return null;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-dr-h'},h('h3',{id:'tm-dr-h'},'Pages read as images'),
   h('p',{class:'small muted'},plural(x.read,'page')+' read by a vision model'+(x.total?', '+x.total.text+' ('+x.total.note+')':'')+'. Each reading is under its page in the documents the team reads.'));
  const ul=h('ul',{class:'tm-ver'});for(const p of x.pages)ul.append(h('li',null,h('div',{class:'h'},h('b',null,p.doc+' p.'+p.page),p.drawing_no?h('span',{class:'small'},'Drawing '+p.drawing_no):null,h('span',{class:'c'},p.cost?money(p.cost):'')),
   h('div',{class:'small'+(p.status==='read'?'':' tm-state blocked')},p.status==='read'?(p.scale?'Scale '+p.scale:'No scale shown')+' · '+p.model+' · for '+p.role:'Not read: '+p.reason)));s.append(ul);return s}
 function briefCard(){const d=V.d;openCard({ref:d.ref,kind_label:'Digital team · Brief and files',title:d.title,subtitle:d.team.name+' · '+d.job_type_name,
  sections:[{key:'what',title:'Brief',text:d.brief},{key:'what',title:'Documents',rows:d.documents.length?d.documents.map(x=>[d.doc_kinds[x.kind]||x.kind,x.source==='library'?x.name+' (document source: '+x.path+')':x.name]):null,text:d.documents.length?'':'No documents.'},
   {key:'where',title:'Where',rows:[['Location',d.location||'Not given (national rates)'],['Client',d.client||'None (General material only for client-facing work)']]},{key:'when',title:'When',rows:[['Started',{time:d.created_at}],['Last change',{time:d.updated_at}]]},
   {key:'who',title:'Who',text:'Started by '+(d.created_by||'you')+'. Team version v'+d.team_version+'.'}],actions:[]},
   {footer:()=>d.can.add_files?(()=>{const b=h('button',{type:'button'},'Add files');b.onclick=()=>{closeCard();openAdd('')};return b})():null})}
 function drawJob(){keepScroll(drawJobNow)}
 function drawJobNow(){const d=V.d;$('tv-split').hidden=false;drawNav(d.nav,d.team_id);const main=$('tm-main');main.replaceChildren();
  main.append(h('nav',{class:'tm-crumbs','aria-label':'Breadcrumb'},h('a',{href:'/admin/teams'},'Digital teams'),'›',h('a',{href:d.team.href},d.team.name),'›',h('span',{'aria-current':'page'},d.ref+' '+d.title)));
  const acts=h('div',{class:'tm-acts'});const brief=h('button',{type:'button',class:'secondary'},'Brief and files');brief.onclick=briefCard;acts.append(brief);
  const pp=d.part_progress,failedPart=d.status==='blocked'&&pp&&pp.failed;
  if(d.status==='blocked'||(d.status==='running'&&!d.busy&&(Date.now()-new Date(d.updated_at))>10*60000))acts.append(btn(failedPart?'Try again':'Resume',async()=>{await api('/admin/api/teams/jobs/'+d.id+'/resume','POST',{});$('notice').textContent=failedPart?'Trying '+pp.failed.label+' again; the parts already done are kept.':'Resumed.';await loadJob()}));
  const toggle=(k,label)=>{const b=h('button',{type:'button',class:J.panel===k?'':'secondary','aria-expanded':String(J.panel===k)},label);b.onclick=()=>{J.panel=J.panel===k?'':k;drawJob();const x=$('tm-rp');if(x)x.scrollIntoView({block:'nearest'})};return b};
  if(d.can.reprice)acts.append(toggle('reprice','Re-price'));if(d.can.remeasure)acts.append(toggle('remeasure','Re-measure'));
  if(d.can.resume)acts.append(btn('Resume',async()=>{if(!confirm('Resume '+d.ref+' as v'+((d.version||1)+1)+'? It carries on where it stopped; nothing done so far is run again.'))return;await api('/admin/api/teams/jobs/'+d.id+'/resume','POST',{});$('notice').textContent='Resumed as v'+((d.version||1)+1)+': it carries on where it stopped.';await loadJob()}));
  if(d.can.add_files){const b=h('button',{type:'button',class:J.panel==='files'?'':'secondary','aria-expanded':String(J.panel==='files')},'Add files');b.onclick=()=>{if(J.panel==='files'){J.panel='';J.add=null;drawJob()}else openAdd('')};acts.append(b)}
  acts.append(toggle('copy','Copy as a new job'));
  if(!['done','stopped'].includes(d.status))acts.append(btn('Stop job',async()=>{if(!confirm('Stop '+d.ref+'? Its work so far is kept.'))return;await api('/admin/api/teams/jobs/'+d.id+'/stop','POST',{});await loadJob()},'secondary'));
  const desc=[plural(d.documents.length,'document')+' provided',d.location||null,'started '+when(d.created_at)+(d.created_by?' by '+d.created_by:'')].filter(Boolean).join(' · ');
  main.append(h('div',{class:'tm-thead'},mark(d.identity.hex,d.identity.icon,'lg'),h('div',{class:'nm'},h('p',{class:'tm-label'+(d.is_demo?'':' plain')},(d.is_demo?'Demo · fictional · ':'')+d.job_type_name+' · '+d.ref),h('h2',null,d.title),h('p',null,desc)),acts));
  const track=h('ol',{class:'tm-track','aria-label':'Stages'});const SW={done:'Done',current:'Working now',waiting:'Waiting for you',todo:'To come',blocked:'Stopped by a failure',stopped:'Stopped'};
  for(const s of d.progress)track.append(h('li',{class:s.state},h('b',null,s.title),h('span',{class:'who'},s.role),h('span',{class:'tm-state '+s.state},SW[s.state]+(s.count?' · '+s.count:''))));main.append(track);
  if(pp&&!['done','stopped'].includes(d.status))main.append(h('p',{class:'tm-partprog',role:'status'},pp.text+(failedPart?' · stopped at '+pp.failed.label:'')));
  if(d.error)main.append(h('div',{class:'tm-err',role:'alert'},h('strong',null,'Stopped: '),d.error,failedPart?h('div',{class:'small'},'Try again redoes only '+pp.failed.label+(pp.kept?'; the '+plural(pp.kept,'part')+' already done '+(pp.kept===1?'is':'are')+' kept.':'.')):null));
  const cols=h('div',{class:'tm-cols'});const left=h('div'),side=h('div',{class:'tm-side'});cols.append(left,side);main.append(cols);
  if(J.panel)left.append(J.panel==='files'?filesPanel():rerunPanel(J.panel));
  if(d.files_pending)left.append(h('div',{class:'tm-rerun',role:'status'},h('b',null,'New files waiting: '),d.files_pending.names.join(', ')+'. The work that depends on them is done again as soon as the team stops for you.'));
  if(d.rerun)left.append(h('div',{class:'tm-rerun',role:'status'},h('b',null,'v'+d.rerun.version+' in progress: '),(d.versions.versions.find(x=>x.current)||{}).what||'',d.rerun.by?' Asked by '+d.rerun.by+'.':''));
  if(d.copied_from)left.append(h('p',{class:'small muted'},'Copied from ',h('a',{href:'/admin/teams/'+enc(d.team_id)+'/jobs/'+d.copied_from.job},d.copied_from.ref+' v'+d.copied_from.version),': documents, plan and settings kept; the client was chosen again.'));
  for(const c of (d.view&&d.view.conflicts)||[])left.append(h('div',{class:'tm-conflict',role:'note'},h('strong',null,(d.view.lead||'The lead')+': '),c.text,h('div',{style:'margin-top:6px'},...(c.links||[]).map(l=>h('a',{href:l.href},l.label+' ↗')))));
  if(d.view&&d.view.decision)left.append(decisionPanel(d.view.decision));for(const s of d.pending)left.append(pendingBox(s));
  left.append(outputPanel());const ap=assumedPanel();if(ap)left.append(ap);
  const tl=h('section',{class:'tm-panel','aria-labelledby':'tm-tl-h'},h('h3',{id:'tm-tl-h'},'What the team did'));tl.append(timeline());side.append(tl);
  side.append(h('section',{class:'tm-panel','aria-labelledby':'tm-talk-h'},h('h3',{id:'tm-talk-h'},'Talk to the team'),h('p',{class:'small muted'},'Messages go to '+(d.lead.role||'the lead')+', who answers and passes them to whoever should act.'),talkPanel(d.team_id,d.id)));
  const tc=templateCard();if(tc)side.append(tc);const dp=drawingsPanel();if(dp)side.append(dp);side.append(thisJob())}
 function thisJob(){const d=V.d,C=d.costs,Vs=d.versions;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-this-h'},h('h3',{id:'tm-this-h'},'This job'));
  s.append(h('dl',{class:'tm-kv'},h('dt',null,'AI cost'),h('dd',null,h('b',null,money(C.total)),d.status==='done'?'':' so far'),h('dt',null,'Version'),h('dd',null,'v'+(d.version||1)),h('dt',null,'Autonomy'),h('dd',null,d.autonomy_label),h('dt',null,'Team version'),h('dd',null,'v'+d.team_version),h('dt',null,'Client'),h('dd',null,d.client||'None')));
  if(C.members.length){const ul=h('ul',{class:'tm-ver','aria-label':'Each member’s share'});for(const m of C.members)ul.append(h('li',null,h('div',{class:'h'},h('b',null,m.role),h('span',{class:'small muted'},m.share_pct+'%'),h('span',{class:'c'},money(m.cost))),m.your_figures?h('div',{class:'tm-yours'},h('b',null,m.your_figures.label+': '),m.your_figures.text,m.your_figures.note?' '+m.your_figures.note:''):null));s.append(h('h4',{style:'margin:10px 0 0'},'Each member’s share'),ul)}
  if(C.before_tracking)s.append(h('p',{class:'small muted'},C.before_text+': ',money(C.before_tracking),' (not split by member or version).'));
  const vl=h('ul',{class:'tm-ver','aria-label':'Versions'});for(const v of Vs.versions.slice().reverse()){
   const view=!v.current&&v.readable?h('button',{type:'button',class:'secondary',style:'padding:1px 9px;font-size:12px'},'Open v'+v.version):null;if(view)view.onclick=()=>run(()=>openVersion(v.version));
   const li=h('li',{class:v.current?'cur':null},h('div',{class:'h'},h('b',null,v.label),h('span',null,v.kind_label),v.signed_off?h('span',{class:'tm-so',title:'Signed off by '+v.signed_off_by+' '+when(v.signed_off_at)},'Signed off'):null,v.current?h('span',{class:'small muted'},'current'):null,h('span',{class:'c'},money(v.cost))),
    h('div',{class:'small'},v.what),v.note?h('div',{class:'small muted'},'Note: '+v.note):null,h('div',{class:'small muted'},(v.asked_by?'Asked by '+v.asked_by+' · ':'')+when(v.started_at)),view);vl.append(li)}
  s.append(h('h4',{style:'margin:10px 0 0'},'Versions'),vl,fxLine(C.fx));return s}
 async function openVersion(v){const d=V.d;const x=await api('/admin/api/teams/jobs/'+d.id+'/versions/'+v);const pl=x.plan;const secs=[{key:'what',title:x.version.kind_label+' · '+x.version.label,text:x.version.what+(x.version.note?'\n\nNote: '+x.version.note:'')+(x.summary?'\n\n'+x.summary:'')}];
  if(pl){secs.push({key:'what',title:pl.stage==='measure'?'Measured (not priced)':'The cost plan in '+x.version.label,rows:pl.rows.map(r=>[r.ref+' '+r.description,qty(r.quantity)+' '+r.unit+(r.rate==null?'':' × '+gbp(r.rate))+(r.amount==null?'':' = '+gbp(r.amount))+' · '+r.source_label])});
   if(pl.totals)secs.push({key:'what',title:'Totals in '+x.version.label,rows:[['Construction',gbp(pl.totals.construction)],['Preliminaries',gbp(pl.totals.prelims)],['Contingency',gbp(pl.totals.contingency)],['Fees',gbp(pl.totals.fees)],['Total excluding VAT',gbp(pl.totals.total)]]})}
  else if(x.text)secs.push({key:'what',title:x.text.stage,text:x.text.text});
  secs.push({key:'when',title:'When',rows:[['Started',{time:x.version.started_at}]].concat(x.version.signed_off?[['Signed off by '+x.version.signed_off_by,{time:x.version.signed_off_at}]]:[])});
  secs.push({key:'who',title:'Who',text:'Asked by '+(x.version.asked_by||'you')+'. Cost of this version: '+x.version.cost.text+' ('+x.version.cost.note+').'});
  openCard({ref:d.ref+' '+x.version.label,kind_label:'Digital team · Earlier version (read only)',title:d.title,subtitle:d.team.name,badge:x.version.signed_off?'Signed off':'Superseded',tone:'',sections:secs,actions:x.documents.map(doc=>({label:'Download '+doc.kind+': '+doc.name,href:'/documents/'+doc.id+'/download'}))})}
 function rerunPanel(kind){const d=V.d;const s=h('section',{class:'tm-rp',id:'tm-rp','aria-labelledby':'tm-rp-h'});const close=h('button',{type:'button',class:'secondary'},'Cancel');close.onclick=()=>{J.panel='';drawJob()};
  if(kind==='copy'){if(J.client===null)J.client=d.client||'';if(!J.title)J.title=d.title+' (copy)';const cl=h('input',{type:'text',maxlength:'80',value:J.client,placeholder:'An organisation marked Client, or leave empty for no client','aria-label':'Client for the new job'}),ti=h('input',{type:'text',maxlength:'150',value:J.title,'aria-label':'Title of the new job'});
   cl.oninput=()=>{J.client=cl.value};ti.oninput=()=>{J.title=ti.value};
   s.append(h('h3',{id:'tm-rp-h'},'Copy as a new job'),h('p',{class:'small muted'},'The new job keeps this job’s documents, '+((d.outputs.plan)?'the Lead’s plan (so it starts at measuring) ':'')+'and settings (job type, location, team v'+d.team_version+'). Choose the client again: client separation decides from the Rules page whether this job’s material may be used for it.'),
    h('div',{class:'tm-form'},h('label',null,'Title',ti),h('label',null,'Client',cl)));
   const go=btn('Copy and start',async()=>{const j=await api('/admin/api/teams/jobs/'+d.id+'/copy','POST',{client:cl.value,title:ti.value});J.panel='';J.client=null;J.title='';location.href='/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id});
   s.append(h('div',{class:'tm-acts',style:'margin-top:10px'},go,close));return s}
  const rs=d.rate_sources;if(!J.order)J.order=rs.order.slice();
  const rows=(d.view&&d.view.plan&&d.view.plan.rows)||[];
  if(kind==='reprice'&&!J.sel)J.sel=rows.filter(r=>r.source==='unpriced'||r.source==='estimate'||r.source==='provisional').map(r=>r.ref);
  if(kind==='remeasure'&&!J.els)J.els=[];
  s.append(h('h3',{id:'tm-rp-h'},kind==='reprice'?'Re-price':'Re-measure'),h('p',{class:'small muted'},kind==='reprice'?'Only the Cost Surveyor works again, on the items you tick; the measured quantities and every other price are kept. The Lead QS then reassembles the cost plan and it comes back for your sign-off as v'+((d.version||1)+1)+'.':'The Measurement Surveyor takes off the elements you tick again; the other elements are kept as measured. Only the items measured again are priced, then the cost plan is reassembled and comes back for your sign-off as v'+((d.version||1)+1)+'.'));
  const box=h('div',{class:'items',role:'group','aria-label':kind==='reprice'?'Items to re-price':'Elements to re-measure'});
  if(kind==='reprice'){for(const r of rows){const c=h('input',{type:'checkbox'});c.checked=J.sel.includes(r.ref);c.onchange=()=>{J.sel=c.checked?[...new Set([...J.sel,r.ref])]:J.sel.filter(x=>x!==r.ref);cnt.textContent=plural(J.sel.length,'item')+' chosen'};
    box.append(h('label',null,c,h('span',null,h('b',null,r.ref+' '),r.description+' ',h('span',{class:'tm-src '+r.source},r.source_label),r.rate!=null?' '+gbp(r.rate)+' per '+r.unit:'')))}}
  else{for(const e of d.elements){const c=h('input',{type:'checkbox'});c.checked=J.els.includes(e);c.onchange=()=>{J.els=c.checked?[...new Set([...J.els,e])]:J.els.filter(x=>x!==e);cnt.textContent=plural(J.els.length,'element')+' chosen'};box.append(h('label',null,c,e))}}
  const cnt=h('span',{class:'small muted'},kind==='reprice'?plural(J.sel.length,'item')+' chosen':plural(J.els.length,'element')+' chosen');
  const est=h('input',{type:'checkbox'});est.checked=J.est;est.onchange=()=>{J.est=est.checked};const tr=h('input',{type:'checkbox'});tr.checked=J.trends;tr.onchange=()=>{J.trends=tr.checked};
  const pst=h('input',{type:'checkbox'});pst.checked=!!J.ps;pst.onchange=()=>{J.ps=pst.checked};
  const ol=h('ol',{class:'tm-order','aria-label':'Order of the rate sources for this re-run'});const drawOrder=()=>{ol.replaceChildren(...J.order.map((k,i)=>{const up=h('button',{type:'button',class:'secondary','aria-label':'Move '+rs.names[k]+' up',disabled:i===0},'↑'),dn=h('button',{type:'button',class:'secondary','aria-label':'Move '+rs.names[k]+' down',disabled:i===J.order.length-1},'↓');
   up.onclick=()=>{J.order.splice(i-1,0,J.order.splice(i,1)[0]);drawOrder()};dn.onclick=()=>{J.order.splice(i+1,0,J.order.splice(i,1)[0]);drawOrder()};const ok=rs.allowed.includes(k);return h('li',{class:ok?null:'off'},up,dn,h('span',null,rs.names[k]),ok?null:h('span',{class:'small muted'},' not allowed by the rule'+(k==='estimate'?' (tick “Allow team estimates” for these items)':k==='provisional'?' (tick “Allow provisional sums” for these items)':'')))}))};drawOrder();
  const note=h('textarea',{maxlength:'1000',placeholder:'A note for the team (optional), e.g. look for a regional rate for Perth','aria-label':'Note for the team'});note.value=J.note;note.oninput=()=>{J.note=note.value};
  s.append(box,cnt,h('div',{class:'opts'},h('label',null,est,'Allow team estimates on '+(kind==='reprice'?'these items':'the items measured again')+', on this re-run only'),h('label',null,pst,'Allow provisional sums for '+(kind==='reprice'?'these items':'the items measured again')+', on this re-run only'),h('label',null,tr,'Run Market Trends again (otherwise its report and the market adjustment decision are kept)')),
   h('details',null,h('summary',{class:'small'},'Rate-source order for this re-run'),h('p',{class:'small muted'},'What may be used stays the rule’s: ',h('a',{href:rs.href},'Where digital teams’ rates come from'),'. Unpriced is always last.'),ol),note);
  const go=btn(kind==='reprice'?'Re-price':'Re-measure',async()=>{const same=J.order.join()===rs.order.join();const body={estimates:J.est,provisional:!!J.ps,trends:J.trends,note:J.note,order:same?[]:J.order};
   if(kind==='reprice'){if(!J.sel.length)throw Error('Tick at least one item to re-price.');body.refs=J.sel}else{if(!J.els.length)throw Error('Tick at least one element to re-measure.');body.elements=J.els}
   await api('/admin/api/teams/jobs/'+d.id+'/'+kind,'POST',body);Object.assign(J,{panel:'',sel:null,els:null,est:false,ps:false,trends:false,order:null,note:''});$('notice').textContent='v'+((d.version||1)+1)+' started: the team is working on it. v'+(d.version||1)+' stays readable under This job.';await loadJob()});
  s.append(h('div',{class:'tm-acts',style:'margin-top:10px'},go,close));return s}
 function decisionPanel(x){const d=V.d;const s=h('section',{class:'tm-dec','aria-labelledby':'tm-dec-h'},h('h3',{id:'tm-dec-h'},x.title),h('p',{class:'small'},x.why));
  const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-plan'});tb.append(h('thead',null,h('tr',null,h('th',{scope:'col'},'Item'),h('th',{scope:'col',class:'n'},'Qty'),h('th',{scope:'col'},'Unit'),h('th',{scope:'col'},'Your rate (£ per unit)'),h('th',{scope:'col'},'Leave unpriced'),h('th',{scope:'col'},'Exclude: not in scope'))));
  const body=h('tbody'),rows=[];for(const i of x.items){const rate=h('input',{type:'number',min:'0.01',step:'0.01',inputmode:'decimal','aria-label':'Rate for '+i.ref+' '+i.description+' in pounds per '+i.unit}),lv=h('input',{type:'checkbox','aria-label':'Leave '+i.ref+' unpriced'});
   const ex=h('input',{type:'checkbox','aria-label':'Exclude '+i.ref+' as not in scope'}),why=h('input',{type:'text',class:'ex',maxlength:'200',placeholder:'Why, e.g. existing manhole, not new work','aria-label':'Why '+i.ref+' is not in scope',hidden:true});
   const sync=()=>{rate.disabled=lv.checked||ex.checked;if(rate.disabled)rate.value='';lv.disabled=ex.checked;why.hidden=!ex.checked};lv.onchange=sync;ex.onchange=()=>{if(ex.checked)lv.checked=false;sync();if(ex.checked)why.focus()};rows.push({ref:i.ref,i,rate,lv,ex,why});
   body.append(h('tr',null,h('td',null,h('b',null,i.ref+' '),i.description,h('div',{class:'sub'},i.element+(i.unmeasured?' · not measurable from the documents':i.approximate?' · quantity from a drawing, approximate':''))),h('td',{class:'n'},qty(i.quantity)),h('td',null,i.unit),h('td',null,rate),h('td',null,lv),h('td',null,ex,why)))}
  tb.append(body);wrap.append(tb);s.append(wrap);const save=h('input',{type:'checkbox'});save.checked=true;const note=h('textarea',{maxlength:'2000',placeholder:'A note for the team (needed to send work back)','aria-label':'Note for the team'});
  const entries=()=>rows.map(r=>r.ex.checked?{ref:r.ref,exclude:r.why.value.trim()}:{ref:r.ref,rate:r.rate.value===''?null:+r.rate.value,unpriced:r.lv.checked}).filter(e=>e.exclude!==undefined||e.unpriced||e.rate!=null);
  const ask=h('div',{class:'tm-ask',role:'alert',hidden:true});
  const undecidedRows=()=>rows.filter(r=>!r.ex.checked&&!r.lv.checked&&r.rate.value==='');
  const submit=async go_on=>{for(const r of rows)if(r.ex.checked&&!r.why.value.trim()){r.why.focus();throw Error('Say briefly why '+r.ref+' is not in scope.')}
   const left=undecidedRows();if(left.length){askWhat(left,go_on);return}
   const e=entries();await api('/admin/api/teams/jobs/'+d.id+'/rates','POST',{entries:e,save_to_library:save.checked,go_on});
   $('notice').textContent='Recorded as yours'+(save.checked&&e.some(x=>x.rate!=null)?' and saved to the rate library':'')+(go_on?'. '+(d.lead.role||'The lead')+' carries on.':'.');await loadJob()};
  // nothing silent: an item with no rate and no tick is asked about, never left unpriced without your say
  function askWhat(left,go_on){const refs=left.map(r=>r.ref);ask.hidden=false;ask.replaceChildren(h('p',null,h('b',null,plural(left.length,'item')+' '+(left.length===1?'has':'have')+' no rate and no decision: '),refs.join(', ')+'. What should happen to '+(left.length===1?'it':'them')+'?'));
   const acts=h('div',{class:'tm-acts'});
   acts.append(btn('Leave '+(left.length===1?'it':'them')+' unpriced',async()=>{for(const r of left){r.lv.checked=true;r.lv.onchange()}ask.hidden=true;await submit(go_on)},'secondary'));
   if(x.can_estimate){acts.append(btn('Ask the team to estimate '+(left.length===1?'it':'them'),()=>askTeam('estimate',refs),'secondary'),btn('Ask for provisional sums',()=>askTeam('provisional',refs),'secondary'))}
   acts.append(btn('Exclude '+(left.length===1?'it':'them')+' (give a reason)',async()=>{for(const r of left){r.ex.checked=true;r.ex.onchange()}ask.hidden=true;left[0].why.focus()},'secondary'),btn('Go back',async()=>{ask.hidden=true;left[0].rate.focus()},'secondary'));
   ask.append(acts);ask.scrollIntoView({block:'nearest'})}
  async function askTeam(kind,picked){await api('/admin/api/teams/jobs/'+d.id+'/'+(kind==='estimate'?'estimate':'provisional'),'POST',{refs:picked,note:note.value});
   $('notice').textContent=x.pricer+(kind==='estimate'?' will estimate ':' will give provisional sums for ')+picked.join(', ')+'; '+x.lead+' then brings them back to you.';await loadJob()}
  const acts=h('div',{class:'opts'},h('label',null,save,'Save the rates I enter to my rate library'));s.append(acts,note);
  const b=h('div',{class:'tm-acts',style:'margin-top:10px'});
  const left=()=>{const p=undecidedRows().map(r=>r.ref);if(!p.length)throw Error('Every item has a rate or a decision: nothing left to ask the team about.');return p};
  if(x.can_estimate){const est=btn('Ask the team to estimate these',()=>askTeam('estimate',left()),'secondary');est.id='estimate';
   const psb=btn('Ask the team for provisional sums',()=>askTeam('provisional',left()),'secondary');psb.id='provisional';
   s.append(h('p',{class:'small'},x.estimate_rule_on?'Team estimates are allowed by the rule. ':h('span',null,'Team estimates are not allowed by the rule ',h('a',{href:x.rule_href},'Where digital teams\' rates come from'),'; “Ask the team to estimate these” allows them for the items without a rate here, on this job only. '),
    'Each estimate comes back badged Estimate, with its reasoning listed as an assumption. “Ask the team for provisional sums” asks for a lump sum for each, with the range found and every page cited, badged PS.'));b.append(est,psb)}
  else s.append(h('p',{class:'small',role:'note'},h('b',null,'Estimates and provisional sums: '),x.cannot_ask_why||'not available at this point.',' What the rules allow: ',h('a',{href:x.rule_href},'Where digital teams\' rates come from'),'.'));
  const psw=h('input',{type:'checkbox'});psw.checked=!!x.ps_on;psw.onchange=()=>run(async()=>{await api('/admin/api/teams/jobs/'+d.id+'/provisional','PUT',{on:psw.checked});$('notice').textContent='Provisional sums '+(psw.checked?'allowed':'switched off')+' on this job, from the next pricing.';await loadJob()});
  s.append(h('div',{class:'opts'},h('label',null,psw,'Provisional sums on this job'),h('span',{class:'small muted'},' ',x.ps_setting===null?(x.ps_rule_on?'(allowed by the rule)':'(not allowed by the rule; tick to allow them on this job)'):(x.ps_rule_on?'(the rule allows them; this job has its own setting)':'(the rule does not allow them; this job has its own setting)'),' ',h('a',{href:x.rule_href},'The rule'))));
  if(x.state==='handoff'){b.append(btn('Use these and continue',()=>submit(true)),btn('Ask '+x.pricer+' to search again',async()=>{const n=note.value.trim()||('Search again for: '+x.items.map(i=>i.ref+' '+i.description).join('; '));await api('/admin/api/teams/steps/'+x.step_id,'POST',{action:'send_back',note:n});$('notice').textContent=x.pricer+' will search again.';await loadJob()},'secondary'))}
  else{b.append(btn('Use these',()=>submit(false)));if(x.state==='signoff')b.append(btn('Send back to '+x.lead,async()=>{if(!note.value.trim())throw Error('Say what needs to change in the note, so '+x.lead+' can act on it.');await api('/admin/api/teams/steps/'+x.step_id,'POST',{action:'send_back',note:note.value});$('notice').textContent='Sent back to '+x.lead+' with your note.';await loadJob()},'secondary'))}
  s.append(b,ask);return s}
 function pendingBox(s){const d=V.d;const w=h('div',{class:'tm-wait'});const who=s.role||'A member';
  if(s.kind==='question'){w.append(h('strong',null,who+' asks you'));for(const x of (s.content.questions||[]))w.append(h('p',null,x));if(s.content.why)w.append(h('p',{class:'small'},h('b',null,'Why it matters: '),s.content.why));const ta=h('textarea',{maxlength:'2000',placeholder:'Your answer','aria-label':'Your answer to '+who});
   const add=s.content.asks_file&&d.can.add_files?h('button',{type:'button',class:'secondary'},'Add a file'):null;if(add)add.onclick=()=>openAdd(s.id);
   w.append(h('div',{class:'tm-answer'},ta,add),h('div',{class:'tm-acts'},btn('Send answer',async()=>{if(!ta.value.trim())throw Error('Type your answer.');await api('/admin/api/teams/steps/'+s.id,'POST',{action:'answer',note:ta.value});$('notice').textContent='Answer sent. '+who+' carries on.';await loadJob()}),btn('Discuss with Temple',()=>openStep(s),'secondary')));return w}
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
   const body=h('tbody');for(const r of pl.rows.filter(r=>J.src==='all'?!['provisional','excluded'].includes(r.source):r.source===J.src)){const badge=r.source==='web'&&r.source_url?h('a',{class:'tm-src web',href:r.source_url,target:'_blank',rel:'noopener noreferrer',title:(r.source_title||r.source_url)+(r.source_date?' ('+r.source_date+')':'')},'Web ↗'):h('span',{class:'tm-src '+r.source,title:r.note||r.source_title||''},r.source_label);
    const srcCell=h('td',null,badge,r.source==='library'&&r.source_title?h('div',{class:'sub'},r.source_title+(r.source_date?' · '+r.source_date:'')):null,r.source==='web'&&r.source_date?h('div',{class:'sub'},r.source_date):null,r.source==='yours'&&r.decided_by?h('div',{class:'sub'},'by '+r.decided_by):null,r.working?h('div',{class:'sub'},r.working.map(w=>w.description+' '+w.quantity_per_unit+' × '+gbp(w.rate)).join(' + ')):null,r.estimate?h('div',{class:'sub'},'Reasoning: '+r.estimate.reasoning.slice(0,200)):null,r.undecided?h('div',{class:'sub'},'Waiting for your decision'):r.source==='unpriced'&&r.decided_by?h('div',{class:'sub'},'Left unpriced by '+r.decided_by):null);
    body.append(h('tr',{class:r.undecided?'und':null},h('td',{style:'min-width:180px'},h('b',null,r.ref+' '),r.description,h('div',{class:'sub'},r.element+' · '+r.quantity_source+(r.approximate?' · approximate (from a drawing)':''))),h('td',{class:'n'},qty(r.quantity)),h('td',null,r.unit),h('td',{class:'n'},r.rate==null?'—':gbp(r.rate)),srcCell,h('td',{class:'n'},r.amount==null?'—':gbp(r.amount))))}
   tb.append(body);wrap.append(tb);s.append(wrap);if(pl.location_note)s.append(h('p',{class:'small muted'},pl.location_note));
   if((pl.provisional||[]).length){const byref={};for(const r of pl.rows)byref[r.ref]=r;const ps=h('div',{class:'tm-ps'},h('h4',null,'Provisional sums'),h('p',{class:'small muted',style:'margin:0 0 6px'},'Lump sums for work the documents do not let the team measure, from typical UK costs for this location and date. Included in the total.'));
    const pw=h('div',{class:'table-wrap'}),pt=h('table',{class:'tm-plan'});pt.append(h('thead',null,h('tr',null,h('th',{scope:'col'},'Work'),h('th',{scope:'col'},'Range found'),h('th',{scope:'col'},'Sources'),h('th',{scope:'col',class:'n'},'Sum'))));const pb=h('tbody');
    for(const p of pl.provisional){const r=byref[p.ref]||{},pv=r.provisional||{};pb.append(h('tr',null,h('td',{style:'min-width:180px'},h('b',null,p.ref+' '),p.description,' ',h('span',{class:'tm-src provisional'},'PS'),h('div',{class:'sub'},p.element+(r.measured?' · measured as '+qty(r.measured.quantity)+' '+r.measured.unit:'')),pv.reasoning?h('div',{class:'sub'},'Reasoning: '+pv.reasoning.slice(0,300)):null),
      h('td',null,gbp(p.low)+' to '+gbp(p.high)),h('td',null,...(pv.sources||[]).map(x=>h('div',{class:'sub'},h('a',{href:x.source_url,target:'_blank',rel:'noopener noreferrer'},(x.source_title||x.source_url)+' ↗'),' '+x.source_date+(x.cost?' · '+gbp(x.cost):'')))),h('td',{class:'n'},gbp(p.amount))))}
    pb.append(h('tr',null,h('td',{colspan:'3'},h('b',null,'Provisional sums subtotal')),h('td',{class:'n'},h('b',null,gbp(pl.provisional_total)))));pt.append(pb);pw.append(pt);ps.append(pw);if(pl.provisional_line)ps.append(h('p',{class:'small muted'},pl.provisional_line));s.append(ps)}
   if((pl.exclusions||[]).length){const ul=h('ul',{class:'small'});for(const x of pl.exclusions)ul.append(h('li',null,x));s.append(h('div',{class:'tm-ps'},h('h4',null,'Excluded: not in scope'),ul))}
   if(pl.stage==='price'){if(pl.totals){const P=pl.percentages||{};const tot=h('dl',{class:'tm-tot'});const row=(k,v,b)=>tot.append(h('dt',null,b?h('b',null,k):k),h('dd',{style:'margin:0;text-align:right'},b?h('b',null,gbp(v)):gbp(v)));
     if(pl.totals.provisional_total){row('Measured works',pl.totals.works);row('Provisional sums',pl.totals.provisional_total)}
     row('Construction',pl.totals.construction);if(pl.totals.market_adjustment)row('Market adjustment ('+(pl.totals.market_pct>0?'+':'')+pl.totals.market_pct+'%, accepted by the Lead QS)',pl.totals.market_adjustment);row('Preliminaries'+(P.prelims_pct!=null?' ('+P.prelims_pct+'%)':''),pl.totals.prelims);row('Contingency'+(P.contingency_pct!=null?' ('+P.contingency_pct+'%)':''),pl.totals.contingency);row('Fees'+(P.fees_pct!=null?' ('+P.fees_pct+'%)':''),pl.totals.fees);row('Total excluding VAT',pl.totals.total,true);
     s.append(tot,h('p',{class:'small muted',style:'text-align:right'},'Worked out by Alice from the rates and quantities above; unpriced items are excluded.'));if(pl.estimated_line)s.append(h('p',{class:'small',style:'text-align:right'},h('span',{class:'tm-src estimate'},'Estimate'),' ',pl.estimated_line))}
    else s.append(h('p',{class:'small',role:'note'},h('b',null,'No total yet: '),plural(pl.undecided,'item')+' still '+(pl.undecided===1?'needs':'need')+' a rate or to be marked unpriced.'))}}
  else if(v.text){s.append(h('h3',{id:'tm-out-h'},'The work so far: '+v.text.stage),h('pre',null,v.text.text))}
  else s.append(h('h3',{id:'tm-out-h'},'The work so far'),h('p',{class:'tm-empty'},d.status==='running'?'The team is working on the first stage…':'Nothing produced yet.'));
  const mk=(d.outputs.trends||{}).market;if(mk){const m=h('div',{class:'tm-market'},h('h4',null,'The market: '+mk.location));const ul=h('ul',null);for(const f of mk.findings)ul.append(h('li',null,f.finding+' ',h('a',{href:f.source_url,target:'_blank',rel:'noopener noreferrer'},(f.source_title||'source')+' ↗'),h('span',{class:'small muted'},' '+f.source_date)));m.append(mk.findings.length?ul:h('p',{class:'small muted'},'No market finding could be cited.'));
   const a=d.outputs.adjust||{};if(mk.adjustment)m.append(h('p',{class:'small'},h('b',null,'Suggested adjustment '+(mk.adjustment.pct>0?'+':'')+mk.adjustment.pct+'%: '),mk.adjustment.reasoning,' ',a.decision==='accepted'?h('b',null,'Accepted by '+a.by+': '+a.reason):a.decision==='rejected'?h('b',null,'Rejected by '+a.by+': '+a.reason):'Waiting for the Lead QS.'));s.append(m)}
  if(d.outputs.filed){const fl=d.outputs.filed;s.append(h('p',{class:'small'},fl.category?'Filed in Knowledge under “'+fl.category+'”.':'Saved to Knowledge (not filed: '+fl.not_filed+')'))}
  if(docs.length||d.knowledge_id){const o=h('div',{class:'tm-out'});for(const x of docs)o.append(h('a',{href:'/documents/'+x.id+'/download'},'⬇ '+x.kind+': '+x.name));if(d.knowledge_id)o.append(h('a',{href:'/admin/knowledge'},'Saved to Knowledge ↗'));s.append(o)}return s}
 function timeline(){const d=V.d;const ms={};for(const m of d.members)ms[m.id]=m;const ul=h('ol',{class:'tm-tl'});if(!d.timeline.length)return h('p',{class:'tm-empty'},'Nothing yet.');
  for(const x of d.timeline){const m=ms[x.member];const av=x.member==='you'?avatar('You','You',false,'','you'):avatar(m?m.initials:'A',x.who,m&&m.id===d.lead.id,d.identity.hex);
   const reply=x.raw_reply?h('details',{class:'tm-reply'},h('summary',null,'What it replied'+(x.part?' ('+x.part+')':'')),h('p',{class:'small muted'},'The first 500 characters of the reply, as received.'),h('pre',null,x.raw_reply)):null;
   const parts=x.parts&&x.parts.parts>1?h('div',{class:'small muted'},'Worked in '+plural(x.parts.parts,'part')+(x.parts.halved?', '+x.parts.halved+' halved after an answer was cut off':'')):null;
   const li=h('li',null,av,h('div',null,h('span',{class:'w'},x.who),x.stage?h('span',{class:'small muted'},' · '+x.stage):null,h('div',null,x.text),parts,reply,x.outcome?h('div',{class:'o'},x.outcome):null,tm(x.at)));
   if(x.output_text){const b=h('button',{type:'button',class:'secondary'},'See the output');b.onclick=()=>openCard({ref:d.ref,kind_label:'Digital team · Output',title:x.output_title,subtitle:d.title,sections:[{key:'what',title:x.stage,text:x.output_text},{key:'when',title:'When',rows:[['Produced',{time:x.at}]]}],actions:[]});li.lastChild.append(b)}
   ul.append(li)}return ul}
 // ---------- the pricing template mapping editor (shared by the start screen, the Knowledge tab and the job page) ----------
 async function openMapping(path,opts){opts=opts||{};const q='?path='+enc(path)+(opts.team?'&team='+enc(opts.team):'')+(opts.redetect?'&redetect=true':'');const m=await api('/admin/api/teams/pricing-templates/mapping'+q);
  const old=document.getElementById('tm-map');if(old)old.remove();const dlg=h('dialog',{class:'tm-map',id:'tm-map','aria-labelledby':'tm-map-h'});document.body.append(dlg);
  const R=m.roles||{};const ROLES=['ref','description','quantity','unit','rate','amount','source'];const req=['description','quantity','unit','rate'];
  const byName={};for(const s of (m.mapping&&m.mapping.sheets)||[])byName[s.sheet]=s;
  const status={confirmed:'Confirmed'+(m.confirmed_by?' by '+m.confirmed_by:''),detected:'Detected by '+((m.mapping||{}).detected_by==='model'?'a model (the team lead’s), as code could not tell':'Alice’s code')+': check it, then confirm',changed:'The file has changed since its mapping was confirmed: check it again',none:m.problem||'Not mapped yet'}[m.status]||m.status;
  dlg.append(h('h3',{id:'tm-map-h'},'Mapping: '+((m.template||{}).name||path)),h('p',{class:'small muted'},status+'. Alice reads each item row from these columns; elements are the sheets, or the section headings under the header.'));
  const mode=h('select',{'aria-label':'Where the elements are'},h('option',{value:'headings'},'Section headings on the sheet'),h('option',{value:'sheets'},'One sheet per element'),h('option',{value:'single'},'No elements (one list)'));mode.value=(m.mapping||{}).mode||'single';
  dlg.append(h('label',{style:'max-width:320px'},'Elements are',mode));const blocks=[];
  for(const pv of m.preview||[]){const cur=byName[pv.sheet];const use=h('input',{type:'checkbox'});use.checked=!!cur;const hr=h('input',{type:'number',min:'1',max:'60',value:cur?cur.header_row:1,style:'width:80px'});
   const headerText=()=>{const row=(pv.rows.find(r=>r[0]===+hr.value)||[]).slice(1);const o={};pv.columns.forEach((c,i)=>{o[c]=row[i]||''});return o};
   const sels={};const roles=h('div',{class:'roles'});const fillSel=()=>{const ht=headerText();for(const r of ROLES){const was=sels[r]?sels[r].value:(cur&&cur.columns[r])||'';const sel=h('select',{'aria-label':(R[r]||r)+' column on '+pv.sheet},h('option',{value:''},'—'));for(const c of pv.columns)sel.append(h('option',{value:c},c+(ht[c]?' · '+ht[c]:'')));sel.value=was;sels[r]=sel}
    roles.replaceChildren(...ROLES.map(r=>h('label',null,(R[r]||r)+(req.includes(r)?' *':''),sels[r])))};fillSel();hr.oninput=fillSel;
   const tb=h('table',{class:'prev'});tb.append(h('tr',null,h('th',null,'Row'),...pv.columns.map(c=>h('th',null,c))));for(const r of pv.rows)tb.append(h('tr',null,...r.map((v,i)=>h(i?'td':'th',{title:String(v)},String(v)))));
   const els=cur&&cur.elements&&cur.elements.length?h('p',{class:'small'},'Elements found: '+cur.elements.map(e=>e.name+' (row '+e.row+')').join(', ')):null;
   const b=h('div',{class:'sheet'},h('label',{class:'ts-opt'},use,h('b',null,pv.sheet+': this sheet holds priced items')),h('label',{style:'max-width:200px'},'Header row',hr),roles,els,h('div',{class:'prev'},tb));dlg.append(b);
   blocks.push({sheet:pv.sheet,use,hr,sels,cur})}
  const msg=h('p',{class:'small',role:'alert'});const close=()=>{dlg.close();dlg.remove()};
  const ok=btn('Confirm mapping',async()=>{msg.textContent='';const sheets=[];let edited=false;for(const b of blocks){if(!b.use.checked){if(b.cur)edited=true;continue}const cols={};for(const r of ROLES)if(b.sels[r].value)cols[r]=b.sels[r].value;
    const missing=req.filter(r=>!cols[r]);if(missing.length){msg.textContent=b.sheet+': choose the '+missing.map(r=>(R[r]||r).toLowerCase()).join(', ')+' column.';return}
    if(!b.cur||b.cur.header_row!==+b.hr.value||JSON.stringify(b.cur.columns)!==JSON.stringify(cols))edited=true;sheets.push({sheet:b.sheet,header_row:+b.hr.value,columns:cols,elements:b.cur&&b.cur.header_row===+b.hr.value?b.cur.elements:[]})}
   if(!sheets.length){msg.textContent='Tick at least one sheet that holds priced items.';return}if(m.mapping&&mode.value!==m.mapping.mode)edited=true;
   const x=await api('/admin/api/teams/pricing-templates/mapping','PUT',{path,mapping:{mode:mode.value,sheets,edited,detected_by:(m.mapping||{}).detected_by}});close();$('notice').textContent='Mapping confirmed for '+((m.template||{}).name||path)+'.';if(opts.onDone)await opts.onDone(x)});
  const again=btn('Detect again',async()=>{close();await openMapping(path,{...opts,redetect:true})},'secondary');
  if(m.can_ask_model)dlg.append(h('p',{class:'small'},btn('Ask the team lead’s model to read the layout',async()=>{await api('/admin/api/teams/pricing-templates/mapping/detect','POST',{path,team:opts.team});close();await openMapping(path,opts)},'secondary'),' It reads only the top rows of the template; you still confirm the mapping.'));const cancel=h('button',{type:'button',class:'secondary'},'Cancel');cancel.onclick=close;
  dlg.append(msg,h('div',{class:'tm-acts'},ok,again,cancel));dlg.addEventListener('cancel',e=>{e.preventDefault();close()});dlg.showModal()}
 const tplTag=t=>t?(t.shared?h('span',{class:'ts-tag'},'Shared'):h('span',{class:'ts-tag'},'For '+t.client)):null;
 const mapTag=t=>t?h('span',{class:'ts-tag '+(t.mapping==='confirmed'?'ok':'warn')},t.mapping==='confirmed'?'Mapping confirmed':t.mapping_label||'Mapping not confirmed'):null;
 // ---------- Start a job (mock-up approved, 8 Oct 2026) ----------
 const S={d:null,title:'',client:'',location:'',jt:'',brief:'',docs:[],estimates:false,ps:null,autonomy:'',tpl:null,own:false,check:null,lib:null,n:0,timer:null};
 const ROLE_KIND={drawing:'drawing',spec:'spec',schedule:'schedule',brief:'brief'};
 async function loadStart(){const d=await api('/admin/api/teams/'+enc(V.tid)+'/start');S.d=d;setIconsFrom(d);if(!S.jt&&d.job_types[0])S.jt=d.job_types[0].id;if(!S.autonomy)S.autonomy=d.autonomy;defaultTemplate();drawStart();scheduleCheck()}
 function orgDefault(){const d=S.d,c=S.client.trim().toLowerCase();if(!c)return null;const k=Object.keys(d.org_defaults).find(x=>x.toLowerCase()===c);return k?d.org_defaults[k]:null}
 function defaultTemplate(){if(S.own||(S.tpl&&!S.tpl.auto))return;const o=orgDefault();const t=o?{...o,auto:true,from:'client'}:S.d.templates.default?{...S.d.templates.default,auto:true,from:'team'}:null;S.tpl=t}
 function scheduleCheck(){clearTimeout(S.timer);S.timer=setTimeout(()=>run(runCheck),300)}
 async function runCheck(){const f={job_type:S.jt,title:S.title,brief:S.brief,location:S.location,client_name:S.client.trim(),template:S.tpl?{path:S.tpl.path}:null,
   documents:S.docs.map(x=>({name:x.name,role:x.role,scale:x.info?x.info.scale:null,problem:x.info?x.info.problem:''}))};S.check=await api('/admin/api/teams/'+enc(V.tid)+'/start-check','POST',{form:f});drawPanel()}
 function drawStart(){const d=S.d;$('tv-split').hidden=false;drawNav(d.nav,d.team.id);const main=$('tm-main');main.replaceChildren();
  main.append(h('nav',{class:'tm-crumbs','aria-label':'Breadcrumb'},h('a',{href:'/admin/teams'},'Digital teams'),'›',h('a',{href:d.team.href},d.team.name),'›',h('span',{'aria-current':'page'},'Start a job')));
  main.append(h('div',{class:'tm-thead'},mark(d.team.hex,d.team.icon,'lg'),h('div',{class:'nm'},h('h2',null,'Start a job for '+d.team.name),h('p',null,'Tell the team what is needed and give it the documents. It works stage by stage and comes back to you as you choose below, then for your sign-off.'))));
  const grid=h('div',{class:'ts-grid'});const steps=h('ol',{class:'ts-steps','aria-label':'Steps'});grid.append(steps,h('aside',{class:'ts-next',id:'ts-next','aria-labelledby':'ts-next-h'}));main.append(grid);
  // 1 the job
  const title=h('input',{type:'text',maxlength:'150',value:S.title,placeholder:'e.g. New community hall, early cost plan',required:true,'aria-required':'true'});title.oninput=()=>{S.title=title.value;scheduleCheck()};
  const dl=h('datalist',{id:'ts-orgs'},...d.organisations.map(o=>h('option',{value:o.name},o.client?'Client':'')));
  const client=h('input',{type:'text',maxlength:'80',list:'ts-orgs',value:S.client,placeholder:'An organisation, or leave empty for no client'});client.oninput=()=>{S.client=client.value;if(S.tpl&&S.tpl.auto)S.tpl=null;defaultTemplate();drawDocs();scheduleCheck()};
  const loc=h('input',{type:'text',maxlength:'120',value:S.location,placeholder:'e.g. Perth, Scotland'});loc.oninput=()=>{S.location=loc.value;scheduleCheck()};
  const types=h('fieldset',{class:'ts-types'},h('legend',null,'What’s needed'));for(const jt of d.job_types){const r=h('input',{type:'radio',name:'ts-jt',value:jt.id});r.checked=S.jt===jt.id;r.onchange=()=>{S.jt=jt.id;drawPanel();scheduleCheck()};types.append(h('label',{class:'ts-type'},r,h('span',null,h('b',null,jt.name),jt.description)))}
  const brief=h('textarea',{maxlength:'20000',rows:'4',placeholder:'What is wanted, in a few sentences.'});brief.value=S.brief;brief.oninput=()=>{S.brief=brief.value;scheduleCheck()};
  steps.append(h('li',{class:'ts-step'},h('h3',null,h('span',{class:'ts-num','aria-hidden':'true'},'1'),'The job'),h('label',null,'Name',title),
   h('div',{class:'row'},h('label',null,'Client',client,dl,h('span',{class:'hint'},'A client keeps the job to its own material and its default pricing template.')),h('label',null,'Location',loc,h('span',{class:'hint'},'Market Trends uses it for regional costs.'))),
   d.job_types.length?types:h('p',{class:'tm-empty'},'This team has no job types yet: add one on the team’s Rules and autonomy tab.'),h('label',null,'Brief',brief)));
  // 2 documents
  const file=h('input',{type:'file',multiple:true,accept:'.pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md,.png,.jpg,.jpeg,.webp',hidden:true,'aria-hidden':'true',tabindex:'-1'});file.onchange=()=>run(async()=>{await addFiles(file.files);file.value=''});
  const drop=h('div',{class:'ts-drop',role:'button',tabindex:'0','aria-label':'Add documents: drop files here or press Enter to choose them'},h('b',null,'Drop the documents here'),'or click to choose: specification, schedules, drawings, and a cost or pricing template');
  drop.onclick=()=>file.click();drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();file.click()}};
  drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')};drop.ondragleave=()=>drop.classList.remove('over');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');run(()=>addFiles(e.dataTransfer.files))};
  const libBox=h('div',{id:'ts-lib'});const pick=d.library?h('button',{type:'button',class:'secondary'},'Pick from a document library'):null;if(pick)pick.onclick=()=>run(drawLib);
  const demo=h('button',{type:'button',class:'secondary'},'Load the demo project (fictional)');demo.onclick=()=>run(async()=>{const x=await api('/admin/api/teams/demo-project');S.title=x.title;S.brief=x.brief;S.location=x.location;S.client='';title.value=x.title;brief.value=x.brief;loc.value=x.location;client.value='';
   for(const y of x.documents){S.docs.push({key:++S.n,name:y.name,text:y.text,role:y.kind==='brief'?'brief':y.kind,info:{type:'Text',lines:y.text.split('\n').filter(Boolean).length,scale:y.kind==='drawing'?/\b1\s*:\s*\d{1,4}\b|\bscale\b/i.test(y.text):null,label:'',problem:''}})}
   drawDocs();scheduleCheck();$('notice').textContent='Demo project loaded (fictional). Load the fictional demo rate library on the Knowledge tab too, then Start the job.'});
  steps.append(h('li',{class:'ts-step'},h('h3',null,h('span',{class:'ts-num','aria-hidden':'true'},'2'),'Documents'),drop,file,h('div',{class:'tm-acts',style:'margin-top:8px'},pick,demo),libBox,h('div',{class:'ts-files',id:'ts-files','aria-live':'polite'})));
  // 3 pricing
  const rs=d.rate_sources;const ol=h('ol',{class:'ts-src'});for(const k of rs.order)ol.append(h('li',{class:rs.allowed.includes(k)?null:'off'},rs.names[k]+(rs.allowed.includes(k)?'':' (not allowed by the rule)')));ol.append(h('li',null,'Otherwise unpriced, never invented'));
  const est=h('input',{type:'checkbox'});est.checked=S.estimates;est.onchange=()=>{S.estimates=est.checked};
  const psRule=rs.allowed.includes('provisional');const psx=h('input',{type:'checkbox'});psx.checked=S.ps===null?psRule:S.ps;psx.onchange=()=>{S.ps=psx.checked===psRule?null:psx.checked};
  const appr=h('fieldset',{class:'ts-types'},h('legend',null,'Approval'));for(const [k,l] of Object.entries(d.autonomy_options)){const r=h('input',{type:'radio',name:'ts-appr',value:k});r.checked=S.autonomy===k;r.onchange=()=>{S.autonomy=k;drawPanel()};
   appr.append(h('label',{class:'ts-type'},r,h('span',null,h('b',null,k==='approve'?'Every hand-off':'Only the final output'),l+(k===d.autonomy?' (the team’s setting)':''))))}
  steps.append(h('li',{class:'ts-step'},h('h3',null,h('span',{class:'ts-num','aria-hidden':'true'},'3'),'How it should be priced'),h('p',{class:'small',style:'margin:0'},'Rates come from, in this order (the rule ',h('a',{href:rs.href},'Where digital teams’ rates come from'),'):'),ol,
   h('label',{class:'ts-opt'},est,h('span',null,'Allow team estimates on this job',h('span',{class:'hint',style:'display:block'},rs.allowed.includes('estimate')?'The rule already allows them.':'Each estimate is badged Estimate and listed as an assumption with its reasoning.'))),
   h('label',{class:'ts-opt'},psx,h('span',null,'Allow provisional sums on this job',h('span',{class:'hint',style:'display:block'},(psRule?'The rule allows them; untick to keep them off this job. ':'The rule does not allow them; tick to allow them on this job only. ')+'For work the documents do not let the team measure: a lump sum from cited typical costs, badged PS, in its own section.'))),appr));
  drawDocs();drawPanel()}
 async function drawLib(){const box=$('ts-lib');if(!S.lib)S.lib=(await api('/admin/api/teams/library-files')).files;const tpls=S.d.templates.templates||[];
  const sel=h('select',{'aria-label':'Document from the document sources'},h('option',{value:''},'Choose a document…'));for(const x of S.lib)sel.append(h('option',{value:x.path},x.source+' › '+x.path));
  if(tpls.length){const g=h('optgroup',{label:'Pricing templates'});for(const x of tpls)g.append(h('option',{value:'tpl:'+x.path},x.path));sel.append(g)}
  const add=btn('Add',async()=>{const v=sel.value;if(!v)return;if(v.startsWith('tpl:')){await useTemplate(v.slice(4));box.replaceChildren();return}
   if(S.docs.some(x=>x.path===v))return;const doc={key:++S.n,name:v.split('/').pop(),path:v,role:'brief',busy:true};S.docs.push(doc);drawDocs();try{doc.info=await api('/admin/api/teams/'+enc(V.tid)+'/inspect','POST',{path:v});doc.role=doc.info.guess==='template'?'schedule':doc.info.guess}finally{doc.busy=false}box.replaceChildren();drawDocs();scheduleCheck()});
  box.replaceChildren(h('div',{class:'tm-acts',style:'margin-top:8px'},sel,add))}
 async function addFiles(list){for(const fl of list){if(fl.size>15*1024*1024)throw Error(fl.name+' is larger than 15 MB.');const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(Error('Could not read '+fl.name));r.readAsDataURL(fl)});
   const doc={key:++S.n,name:fl.name,data,role:'brief',busy:true};S.docs.push(doc);drawDocs();
   try{doc.info=await api('/admin/api/teams/'+enc(V.tid)+'/inspect','POST',{name:fl.name,data});doc.role=doc.info.guess}catch(e){doc.info={problem:e.message,type:'',label:''};doc.role='brief'}finally{doc.busy=false}
   if(doc.role==='template')await makeTemplate(doc);drawDocs();scheduleCheck()}}
 async function makeTemplate(doc){if(doc.path){S.docs=S.docs.filter(x=>x!==doc);await useTemplate(doc.path);return}
  try{const x=await api('/admin/api/teams/'+enc(V.tid)+'/pricing-templates','POST',{name:doc.name,data:doc.data});S.docs=S.docs.filter(y=>y!==doc);S.tpl={...x,auto:false,from:'chosen'};S.own=false;S.d.templates=await api('/admin/api/teams/'+enc(V.tid)+'/pricing-templates');
   $('notice').textContent=doc.name+' saved to '+(S.d.templates.settings.folder||'the templates folder')+' as a pricing template.'}
  catch(e){doc.role='schedule';$('notice').textContent=e.message}}
 async function useTemplate(path){const m=await api('/admin/api/teams/pricing-templates/mapping?path='+enc(path)+'&team='+enc(V.tid));S.tpl={...m.template,auto:false,from:'chosen'};S.own=false;drawDocs();scheduleCheck()}
 function drawDocs(){const box=$('ts-files');if(!box)return;box.replaceChildren();const R=S.d.roles;
  const roleSel=(v,label,fn)=>{const s=h('select',{'aria-label':'Role of '+label});for(const [k,l] of Object.entries(R))s.append(h('option',{value:k},l));s.value=v;s.onchange=()=>run(()=>fn(s.value));return s};
  if(S.tpl){const t=S.tpl;const from=t.from==='client'?'Default for '+S.client.trim():t.from==='team'?'The team’s default':'Chosen for this job';
   const chk=t.path?btn('Check mapping',()=>openMapping(t.path,{team:V.tid,onDone:async()=>{await useTemplate(t.path);if(t.auto)S.tpl.auto=true,S.tpl.from=t.from}}),'secondary'):null;
   const rm=h('button',{type:'button',class:'secondary','aria-label':'Use Alice’s own layout instead of '+t.name},'Remove');rm.onclick=()=>{S.tpl=null;S.own=true;drawDocs();scheduleCheck()};
   box.append(h('div',{class:'ts-file tpl'},h('div',null,h('div',{class:'nm'},'📊 '+t.name,tplTag(t),mapTag(t)),h('div',{class:'meta'},'Cost/pricing template · '+from+' · ',t.path),chk?h('div',{style:'margin-top:4px'},chk):null),
    roleSel('template',t.name,v=>{if(v==='template')return;S.tpl=null;S.own=true;if(t.path)S.docs.push({key:++S.n,name:t.name,path:t.path,role:v,info:{type:'Excel',label:''}});drawDocs();scheduleCheck()}),rm))}
  else box.append(h('p',{class:'small muted',style:'margin:2px 0'},S.own?'No pricing template: Alice’s own layout. ':'No pricing template yet: add one (role Cost/pricing template), or Alice’s own layout is used. ',S.own?(()=>{const b=h('button',{type:'button',class:'secondary',style:'padding:1px 8px;font-size:12px'},'Use the default again');b.onclick=()=>{S.own=false;defaultTemplate();drawDocs();scheduleCheck()};return b})():null));
  for(const x of S.docs){const i=x.info||{};const bits=[i.type,i.pages?plural(i.pages,'page'):i.sheets?plural(i.sheets,'sheet'):i.lines?plural(i.lines,'line'):null,x.path?'from a document source':null].filter(Boolean).join(' · ');
   const rm=h('button',{type:'button',class:'secondary','aria-label':'Remove '+x.name},'Remove');rm.onclick=()=>{S.docs=S.docs.filter(y=>y!==x);drawDocs();scheduleCheck()};
   box.append(h('div',{class:'ts-file'},h('div',null,h('div',{class:'nm'},(x.path?'📁 ':'📄 ')+x.name),h('div',{class:'meta'},x.busy?'Reading…':bits,i.label?h('span',{class:'lbl'},' · Label: '+i.label):null,x.role==='drawing'&&i.scale===false?' · no scale found':''),i.problem?h('div',{class:'prob',role:'alert'},i.problem):null),
    roleSel(x.role,x.name,async v=>{x.role=v;if(v==='template')await makeTemplate(x);drawDocs();scheduleCheck()}),rm))}}
 function drawPanel(){const box=$('ts-next');if(!box)return;const d=S.d;const jt=d.job_types.find(x=>x.id===S.jt);box.replaceChildren(h('h3',{id:'ts-next-h'},'What happens next'));
  if(!jt){box.append(h('p',null,'Choose what’s needed.'));return}
  box.append(h('p',null,(S.autonomy==='approve'?'You approve each hand-off; ':'The team works on its own; ')+'the final output always waits for your sign-off.'));
  const ul=h('ul',{class:'ts-who'});for(const m of jt.members){let does=m.does.join(' Then: ');if(!S.location.trim()&&/cost trends|regional factor/i.test(does))does+=' (no location given: national figures)';ul.append(h('li',null,avatar(m.initials,m.role,m.lead,'','lg'),h('div',null,h('b',null,m.role+(m.lead?' (lead)':'')),h('div',{class:'d'},does))))}box.append(ul);
  if(jt.typical&&(jt.typical.run_time||jt.typical.ai_cost)){const dlx=h('dl',{class:'ts-typ'});if(jt.typical.run_time)dlx.append(h('dt',null,'Typical time to your sign-off'),h('dd',null,jt.typical.run_time));if(jt.typical.ai_cost)dlx.append(h('dt',null,'Typical AI cost'),h('dd',{title:jt.typical.ai_cost.note},jt.typical.ai_cost.text));
   box.append(dlx,h('p',{style:'font-size:12px'},'From '+plural(jt.typical.jobs,'finished job')+' of this team.'))}
  const C=S.check;box.append(h('h3',{style:'font-size:14px;margin:6px 0'},'Ready to start'));
  if(C){const rl=h('ul',{class:'ts-ready'});for(const it of C.items){const cls=it.ok?'ok':it.level==='required'?'no':'warn';rl.append(h('li',{class:cls},h('span',{class:'i','aria-hidden':'true'},it.ok?'✓':it.level==='required'?'✕':'!'),h('span',null,h('span',{class:'tm-sr'},it.ok?'Done: ':it.level==='required'?'Needed: ':'Note: '),it.text)))}box.append(rl)}
  const go=h('button',{type:'button',class:'go',disabled:!(C&&C.ready)},'Start the job');go.onclick=()=>run(startJob);box.append(go)}
 async function startJob(){const d=S.d;const body={job_type:S.jt,title:S.title,brief:S.brief,location:S.location,client:S.client.trim(),
   uploads:S.docs.filter(x=>!x.path).map(x=>({name:x.name,kind:ROLE_KIND[x.role]||'brief',...(x.text!=null?{text:x.text}:{data:x.data})})),library:S.docs.filter(x=>x.path).map(x=>({path:x.path,kind:ROLE_KIND[x.role]||'brief'})),
   template:S.tpl?(S.tpl.auto?null:S.tpl.path):(S.own?'':null),autonomy:S.autonomy===d.autonomy?'':S.autonomy,estimates:S.estimates,provisional:S.ps};
  const j=await api('/admin/api/teams/'+enc(V.tid)+'/jobs','POST',body);location.href='/admin/teams/'+enc(V.tid)+'/jobs/'+j.id}
 // ---------- pricing templates on the Knowledge tab ----------
 function pricingPanel(){const d=V.d,t=d.team;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-pt-h'},h('h3',{id:'tm-pt-h'},'Pricing templates'),h('p',{class:'small muted'},'Spreadsheet templates the team fills with each job’s items and rates (one per job). They stay in the document sources, never in Alice. A template is shared unless you tag it to a client; then only that client’s jobs may use it.'));
  const P=T.pt;if(!P){s.append(h('p',{class:'small muted'},'Loading…'));run(async()=>{T.pt=await api('/admin/api/teams/'+enc(t.id)+'/pricing-templates');drawTeam()});return s}
  const fsel=(v,label)=>{const x=h('select',{'aria-label':label},h('option',{value:''},'Not set'));for(const f of P.folders)x.append(h('option',{value:f},f));x.value=v||'';return x};
  const folder=fsel(P.settings.folder,'Templates folder'),outs=fsel(P.settings.outputs,'Where filled copies are saved');const def=h('select',{'aria-label':'The team’s default template'},h('option',{value:''},'Alice’s own layout'));for(const x of P.templates.filter(x=>x.shared&&x.readable))def.append(h('option',{value:x.path},x.name));def.value=P.settings.default||'';
  const save=btn('Save',async()=>{T.pt=await api('/admin/api/teams/'+enc(t.id)+'/pricing-templates','PUT',{folder:folder.value,outputs:outs.value,default:def.value});$('notice').textContent='Saved as a new team version.';drawTeam()});
  s.append(h('div',{class:'tm-form'},h('div',{class:'row'},h('label',null,'Templates folder',folder),h('label',null,'Save filled copies to (optional)',outs)),h('label',null,'The team’s default template',def),h('div',{class:'tm-acts'},save)));
  if(P.folder_missing)s.append(h('p',{class:'small',role:'alert'},'The templates folder is no longer in the document sources: choose it again.'));
  const wrap=h('div',{class:'table-wrap'}),tb=h('table',{class:'tm-tbl'});tb.append(h('thead',null,h('tr',null,['Template','Who may use it','Mapping',''].map(x=>h('th',{scope:'col'},x)))));const body=h('tbody');
  for(const x of P.templates){const cs=h('select',{'aria-label':'Client for '+x.name},h('option',{value:''},'Shared (any job)'));for(const c of P.clients)cs.append(h('option',{value:c},'Only '+c));cs.value=x.client||'';
   cs.onchange=()=>run(async()=>{await api('/admin/api/teams/pricing-templates/client','PUT',{path:x.path,client:cs.value});T.pt=null;$('notice').textContent=x.name+(cs.value?' tagged to '+cs.value+'.':' is shared.');drawTeam()});
   const rm=P.can_manage?btn('Remove from this list',async()=>{if(!confirm('Remove '+x.name+' from this team’s list? The file in the document source and its mapping are kept, and you can add it back under Show hidden.'))return;T.pt=await api('/admin/api/teams/'+enc(t.id)+'/pricing-templates/hidden','PUT',{path:x.path,hidden:true});$('notice').textContent=T.pt.message;drawTeam()},'secondary'):null;
   body.append(h('tr',null,h('td',null,x.name,h('div',{class:'small muted'},x.path)),h('td',null,x.readable?cs:'—'),h('td',null,mapTag(x)),h('td',null,h('div',{class:'tm-acts'},x.readable?btn('Check mapping',()=>openMapping(x.path,{team:t.id,onDone:async()=>{T.pt=null;drawTeam()}}),'secondary'):null,rm))))}
  tb.append(body);wrap.append(tb);s.append(P.templates.length?wrap:h('p',{class:'tm-empty'},P.settings.folder?'No templates in '+P.settings.folder+' yet.':'Choose the templates folder first.'));
  for(const f of P.fallbacks||[])s.append(h('p',{class:'small',role:'note'},f));
  if((P.hidden||[]).length){const tg=h('button',{type:'button',class:'secondary','aria-expanded':String(!!T.showHidden)},(T.showHidden?'Hide the removed templates':'Show hidden')+' ('+P.hidden.length+')');tg.onclick=()=>{T.showHidden=!T.showHidden;drawTeam()};s.append(h('div',{class:'tm-acts',style:'margin-top:8px'},tg));
   if(T.showHidden){const ul=h('ul',{class:'tm-ver','aria-label':'Templates removed from this team’s list'});for(const x of P.hidden){const back=P.can_manage?btn('Add back',async()=>{T.pt=await api('/admin/api/teams/'+enc(t.id)+'/pricing-templates/hidden','PUT',{path:x.path,hidden:false});$('notice').textContent=T.pt.message;drawTeam()},'secondary'):null;
     ul.append(h('li',null,h('div',{class:'h'},h('b',null,x.name),back),h('div',{class:'small muted'},x.path+(x.exists?'':' · not in the document sources any more')),h('div',{class:'small muted'},'Removed'+(x.hidden_by?' by '+x.hidden_by:'')+' '+when(x.hidden_at))))}
    s.append(ul)}}
  const up=h('input',{type:'file',accept:'.xlsx,.xlsm,.csv','aria-label':'Add a pricing template'});up.onchange=()=>run(async()=>{const fl=up.files[0];if(!fl)return;const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(Error('Could not read '+fl.name));r.readAsDataURL(fl)});
   const x=await api('/admin/api/teams/'+enc(t.id)+'/pricing-templates','POST',{name:fl.name,data});up.value='';T.pt=null;$('notice').textContent=x.name+' added to '+P.settings.folder+'. Check its mapping before a job uses it.';drawTeam()});
  s.append(h('div',{class:'tm-acts',style:'margin-top:8px'},h('label',{class:'small'},'Add a template (saved into the templates folder, never overwriting) ',up),btn('Refresh',async()=>{T.pt=null;drawTeam()},'secondary')));return s}
 // ---------- the job's pricing template (job page) ----------
 function templateCard(){const d=V.d,tp=d.pricing_template;if(!tp)return null;const s=h('section',{class:'tm-panel','aria-labelledby':'tm-tp-h'},h('h3',{id:'tm-tp-h'},'Pricing template'));
  const from={client:'Default for '+(d.client||'the client'),team:'The team’s default',chosen:'Chosen for this job'}[tp.from]||'';
  const w=h('div',{class:'tm-tpl'});w.append(h('div',null,h('b',null,tp.own?'Alice’s own layout':tp.name),tp.own?null:tplTag(tp),tp.own?null:mapTag(tp)));
  const about=tp.own?'Alice’s Word cost plan and Excel workbook, without a template of yours.':from;if(about)w.append(h('div',{class:'small muted'},about));
  if(!tp.own&&tp.readable)w.append(h('div',null,btn('Check mapping',()=>openMapping(tp.path,{team:d.team_id,onDone:async()=>{await loadJob()}}),'secondary')));
  const sel=h('select',{'aria-label':'Pricing template for this job'},h('option',{value:''},'Alice’s own layout'));for(const x of tp.choices.filter(x=>x.readable))sel.append(h('option',{value:x.path},x.name+(x.shared?'':' (for '+x.client+')')));sel.value=tp.own?'':tp.path;
  const use=btn('Use this template',async()=>{await api('/admin/api/teams/jobs/'+d.id+'/template','PUT',{path:sel.value});$('notice').textContent=tp.measured?'Template changed; filled again from the same items.':'Template changed.';await loadJob()},'secondary');
  w.append(h('label',{class:'small'},'Change it ',sel),use);if(tp.measured)w.append(h('p',{class:'small muted',style:'margin:0'},'The items are already measured: a new template is filled from the same items, without re-running the team.'));
  const f=tp.fill;if(f&&f.message)w.append(h('p',{class:'small',role:'status'},f.message));
  const last=tp.fills[tp.fills.length-1];if(last){w.append(h('p',{class:'small',style:'margin:0'},'Filled for v'+last.version+' ',when(last.created_at),last.client?' · tagged to '+last.client:'',' · ',h('a',{href:'/documents/'+last.doc_id+'/download'},'Download ⬇'),last.library_path?' · saved to '+last.library_path:''));
   if(last.differences.length){const ul=h('ul',{class:'tm-diffs','aria-label':'Where the template’s formulas differ from Alice’s figures'});for(const x of last.differences)ul.append(h('li',null,h('b',null,x.where+': '),x.note));w.append(h('p',{class:'small',style:'margin:4px 0 0'},h('b',null,'The template’s own formulas against Alice’s figures:')),ul)}
   else w.append(h('p',{class:'small muted',style:'margin:0'},'The template’s formulas agree with Alice’s figures.'))}
  if(!tp.own&&(d.outputs.documents||d.status==='done'||(d.status==='stopped'&&tp.measured)))w.append(btn('Fill the template again',async()=>{await api('/admin/api/teams/jobs/'+d.id+'/template/fill','POST',{});$('notice').textContent='Filled again from the items as they stand.';await loadJob()},'secondary'));
  s.append(w);return s}
 // ---------- start: old links, then the right screen ----------
 const qp=new URLSearchParams(location.search);
 if(!V.tid&&qp.get('job'))run(async()=>{const j=await api('/admin/api/teams/jobs/'+enc(qp.get('job')));location.replace('/admin/teams/'+enc(j.team_id)+'/jobs/'+j.id)});
 else if(!V.tid&&qp.get('team'))location.replace('/admin/teams/'+enc(qp.get('team'))+(location.hash||''));
 else if(V.jid)run(loadJob);
 else if(V.start)run(loadStart);
 else if(V.tid){run(async()=>{await loadTeam();api('/admin/api/teams/'+enc(V.tid)+'/seen','POST',{}).catch(()=>{})});window.addEventListener('hashchange',()=>{const k=location.hash.slice(1);if(TABS.some(x=>x[0]===k)&&k!==tab){tab=k;if(V.d)drawTeam()}})}
 else{run(loadBoard);$('tb-q').oninput=()=>{B.q=$('tb-q').value;drawTeams()};$('tb-group').onchange=()=>{B.group=$('tb-group').value;store.set('group',B.group);drawTeams()};$('tb-sort').onchange=()=>{B.sort=$('tb-sort').value;store.set('sort',B.sort);drawTeams()};
  $('tb-cards').onclick=()=>{B.view='cards';store.set('view','cards');drawBoard()};$('tb-list').onclick=()=>{B.view='list';store.set('view','list');drawBoard()};
  $('tb-new').onclick=()=>newTeamPanel(false);$('tb-templates').onclick=()=>newTeamPanel(true)}
}
"""
