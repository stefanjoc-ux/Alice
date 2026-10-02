"""Admin page rendering, separate from chat and API handlers."""
import json
from html import escape

PAGES = {
 'home': ('Home','What needs you, what happened today and what you were working on.'),
 'actions': ('Actions','Everything waiting for your decision, in one place. Quick decisions here; open the full page when you need to edit.'),
 'usage': ('Usage & costs','Estimated API spend and savings. Includes Chat, Temple, routing and images.'),
 'temple': ('Temple','Your advisory memory steward. Human decisions remain in control.'),
 'knowledge': ('Knowledge','Files, notes and meeting extracts. Tag them like memories; security labels decide which models may read each item.'),
 'memories': ('Memories','Review proposed records and browse approved knowledge.'),
 'agents': ('Agents','Everything that acts on Alice without you typing it: Temple\'s automations and connected apps. What each does, what it touched, what it cost, and its limits. Pause or stop any of them here.'),
 'organisations': ('Organisations','Clients and other organisations: short approved facts with a pointer to the source, opportunities, and for clients the names Alice recognises and the memories and files tagged to them. Detail stays in the source system.'),
 'archive': ('Archived chats','Inactive Alice chats (30 days) and conversations saved from Claude apps. Ask Temple to review any of them for memories and knowledge.'),
 'documents': ('Documents','Document sources: full documents that stay outside Alice. Knowledge keeps approved summaries that point to them; assistants read a section on demand only when the summaries do not answer. For now each source is a folder in the Documents folder that stands in for SharePoint, Fabric or Power Platform; in Azure each becomes a real connector.'),
 'assistants': ('Assistants','Focused assistants built on Alice, such as Alex (HR policies) and Parker (proposals). Each has its own rule packs, model and knowledge, and staff use it on its own page without seeing the rest of Alice.'),
 'rule-packs': ('Rule packs','Ready-made safeguards for teams adopting AI. Switch each one on or off, test a message against the pack (a sandbox: no AI is called), and apply a pack to Alice\'s live rules when you want it enforced.'),
 'rules': ('Rules','Rule sets in precedence order. Enforced rules are checked in code; guidance rules are instructions to the model.'),
 'activity': ('Activity','Everything Alice and Temple did, and every decision you made: filter by type, date or words, and export for an audit trail.'),
}

SECTIONS = {
'home': r'''<section class="hm-hero"><div><h2 id="hm-hello">Hello</h2><p id="hm-sub" class="muted"></p></div>
<div class="hm-go"><a class="hm-btn primary" href="/?new=1"><span>&#9998;</span>New chat</a><a class="hm-btn" id="hm-prop" href="/admin/assistants"><span>&#10064;</span>Write a proposal</a><a class="hm-btn" href="/admin/temple?tab=ask"><span>?</span>Ask Temple</a><a class="hm-btn" href="/admin/knowledge"><span>+</span>Add knowledge</a></div></section>
<div id="hm" class="hm"></div>''',
'documents': r'''<section><div class="mem-head"><h2>Document sources</h2><button id="ds-new" type="button" class="secondary">Add a source</button></div>
<p class="muted small" id="ds-root"></p>
<div class="ds-how"><div><strong>1. Documents stay in their source</strong><span>SharePoint, Fabric, Power Platform or a folder. Alice never copies them in.</span></div><div><strong>2. Knowledge holds summaries</strong><span>Approved summaries point to the document and section they came from.</span></div><div><strong>3. Full detail on demand</strong><span>When the summaries don't answer, an assistant reads that section for one answer, under the rules.</span></div></div>
<form id="ds-form" class="as-card" hidden><h3>New document source</h3><div class="k-meta-row"><label>Name<input id="ds-name" maxlength="60" placeholder="e.g. Finance Policies"></label><label>Stands in for<select id="ds-type"></select></label></div>
<label>What it simulates<input id="ds-sim" maxlength="200" placeholder="e.g. SharePoint: Finance site, Policies library"></label><label>Description<input id="ds-desc" maxlength="300"></label>
<div class="arc-actions"><button>Create source</button><button type="button" id="ds-cancel" class="secondary">Cancel</button></div><p class="muted small">This creates a folder in the Documents folder. Put the documents in that folder; Alice lists them here.</p></form>
<div id="ds-list"></div></section>''',
'assistants': r'''<section><div class="mem-head"><h2>Assistants</h2><button id="as-new" type="button" class="primary">New assistant</button></div>
<p class="muted small">Every question goes through Alice first: secrets and protective markings are blocked, the assistant's rule packs block, escalate or remove identifiers, and only knowledge in its categories is used (never client-tagged or Local only material). No transcript is kept; the Activity log records whether each question was answered, blocked or escalated, and which sources were used.</p>
<div class="as-tiles" id="as-tiles"></div>
<div class="as-bar"><input type="search" id="as-q" placeholder="Find an assistant" aria-label="Find an assistant"><div class="as-chips" id="as-kinds" role="group" aria-label="Type"></div><div class="as-chips" id="as-status" role="group" aria-label="Status"></div><div class="as-chips as-view" id="as-view" role="group" aria-label="View"></div></div>
<div id="as-editor"></div>
<div id="as-list"></div></section>''',
'rule-packs': r'''<div id="rp-packs" class="t-tabs" role="tablist" aria-label="Rule packs"></div>
<section id="rp-head"></section>
<div class="rp-grid"><div id="rp-rules"></div>
<aside class="rp-try"><section><div class="mem-head"><h2>Try it</h2><span class="muted small">No AI is called</span></div>
<div id="rp-samples" class="mem-cats"></div>
<label class="small" for="rp-text">Message</label><textarea id="rp-text" rows="4" maxlength="5000" placeholder="Type a request, or pick an example above"></textarea>
<label class="small" for="rp-provider">Sent to</label><select id="rp-provider"></select>
<div class="row" style="margin-top:10px"><button id="rp-run" type="button" class="primary">Run through the rules</button></div>
<div id="rp-result" aria-live="polite"></div></section></aside></div>''',
'actions': r'''<section><div class="mem-head"><h2 id="act-total">Actions</h2><button id="act-refresh" type="button" class="secondary">Refresh</button></div><p class="muted small">Approving here is the same decision as on the full page: security rules are re-checked, and nothing becomes a memory or knowledge without you.</p></section><div id="act-sections"></div>''' ,
'usage': r'''<section><div class="usage-bar"><h2>Spend</h2><label>Period <select id="usage-period"><option value="7d">Last 7 days</option><option value="30d" selected>Last 30 days</option><option value="month">This month</option><option value="all">All time</option></select></label><button id="usage-refresh" type="button">Refresh</button></div><div id="usage-stats" class="stats usage-stats"></div><p id="usage-caveat" class="muted"></p></section>
<section><div class="mem-head"><h2>Provider connections</h2><button id="prov-check" type="button" class="secondary">Check connections</button></div><p class="muted small">Sends one tiny request to each provider you have a key for (a fraction of a penny each) and reports key, credit and model-access problems in plain words.</p><div id="prov-results"></div></section>
<section><h2>Cost by model and workload</h2><div class="table-wrap"><table id="usage-groups"></table></div></section>
<section><h2>Optimisations and estimated savings</h2><p class="muted">Savings compare what you paid with what the same calls would have cost without each optimisation. Only measurable items have a figure.</p><div class="table-wrap"><table id="usage-savings"></table></div></section>
<section><h2>Daily cost</h2><div class="table-wrap"><table id="usage-days"></table></div></section>
<section><h2>Latest 50 API responses</h2><div class="table-wrap"><table id="usage-recent"></table></div></section>
<section><details><summary>Grok connection check and estimate notes</summary><p>Add XAI_API_KEY to your local .env and restart both servers. The check makes one small billable API request; it does not send your saved files or memories.</p><button id="grok-check" type="button">Check Grok connection</button><p id="grok-check-result" role="status"></p><p>Counts include every returned model response, including tool rounds, Temple and the routing classifier. Failed requests without usage data are not included. This is not a spending cap or a provider invoice; provider billing is authoritative. Luna estimates are conservative: when write details are missing, all uncached input is priced at the cache-write rate. Grok images are priced at $0.04 each (xAI Imagine 2.0, 1K low quality) unless IMAGE_PRICE_GROK is set in .env; OpenAI images stay unpriced until IMAGE_PRICE_OPENAI is set. Standard global rates checked 29 September 2026, in USD; taxes, regional premiums and Azure costs are excluded.</p></details></section>''',
'temple': r'''<section class="t-head"><div class="mem-head"><h2>Temple review</h2><span id="t-summary" class="muted small"></span></div>
<details id="t-settings-panel"><summary>Temple settings</summary><form id="temple-settings"><label>Reviewer <select id="temple-provider"><option value="openai">OpenAI · GPT-6 Luna</option><option value="claude">Claude · Haiku 4.5</option></select></label><label><input type="checkbox" id="temple-enabled"> Automatically review new memory proposals</label><p class="muted small">Temple checks proposals for duplicates, conflicts and unclear sources. It is advisory: it cannot approve or change memories. Each review sends the proposal and a selection of approved memories to the reviewer and costs API usage. Source descriptions are not independently verified.</p><button>Save Temple settings</button></form></details>
<details id="t-parker" class="t-auto t-parker" hidden><summary></summary><ul id="t-parker-list"></ul><p class="muted small">Parker works through proposal forms with people on the Parker page. Each turn is logged here: what it changed and what it asked for, never the conversation. Nothing Parker does is saved until someone writes the proposal.</p></details>
<details id="t-auto" class="t-auto" hidden><summary></summary><ul id="t-auto-list"></ul><p class="muted small">Reference summaries are approved automatically because the Proposal writer is set to do so (Assistants page). Each one is in Knowledge, where you can retire it.</p></details>
<div class="t-tabs" role="tablist"><button id="tab-reviews" type="button" role="tab" class="chip on">Memory reviews</button><button id="tab-suggestions" type="button" role="tab" class="chip">Chat suggestions</button><button id="tab-ask" type="button" role="tab" class="chip">Ask Temple</button></div></section>
<section id="pane-reviews"><div id="t-views" class="mem-tabs"></div><div class="mem-tools"><input id="t-query" type="search" maxlength="200" placeholder="Search proposals" aria-label="Search proposals"></div><div id="t-verdicts" class="mem-cats"></div>
<div id="t-bulk" class="mem-bulk" hidden><strong id="t-selected"></strong><button id="t-approve" type="button">Approve</button><button id="t-reject" type="button" class="secondary">Reject</button><button id="t-review" type="button" class="secondary">Review with Temple</button><button id="t-clear" type="button" class="secondary">Clear</button></div>
<div class="table-wrap"><table id="t-table" class="mem-table"></table></div><p id="t-count" class="muted small"></p><button id="t-more" type="button" class="secondary" hidden>Load more</button></section>
<section id="pane-suggestions" hidden><div id="s-status" class="mem-tabs"></div><div class="mem-tools"><input id="s-query" type="search" maxlength="200" placeholder="Search suggestions" aria-label="Search suggestions"></div><div id="s-kinds" class="mem-cats"></div>
<div id="s-bulk" class="mem-bulk" hidden><strong id="s-selected"></strong><button id="s-accept" type="button" class="primary" title="Accept the selected suggestions as written. Memories and decisions become proposals for you to approve.">Accept</button><button id="s-later" type="button" class="secondary">Later</button><button id="s-dismiss" type="button" class="secondary">Dismiss</button><button id="s-clear" type="button" class="secondary">Clear</button></div>
<div class="table-wrap"><table id="s-table" class="mem-table"></table></div><p id="s-count" class="muted small"></p><button id="s-more" type="button" class="secondary" hidden>Load more</button>
<p class="muted small">Accepting a memory creates a proposal for approval. A knowledge note becomes a searchable file. Guidance is appended to your response guidance. Rule requests are logged, not enforced.</p></section>
<section id="pane-ask" hidden><div class="mem-head"><h2>Ask Temple</h2><span class="muted small">Read-only · answers from the activity log, actions and usage</span></div>
<div id="ask-starters" class="mem-cats"></div><div id="ask-log" class="ask-log" aria-live="polite"></div>
<form id="ask-form" class="ask-form"><textarea id="ask-q" rows="2" maxlength="4000" placeholder="e.g. What did the rules block this week?" aria-label="Question for Temple"></textarea><div class="arc-actions"><button id="ask-go">Ask</button><button id="ask-clear" type="button" class="secondary">Clear conversation</button></div></form>
<p class="muted small">Temple looks things up with read-only tools and shows what it checked. It can't approve or change anything; it tells you where to do that. The conversation is kept on this page only.</p></section>''',
'agents': r'''<div id="ag-list"><div id="ag-view" class="mem-tabs ag-view"></div>
<section id="ag-map-wrap" hidden><div class="mem-head"><h2>System map</h2><span id="ag-map-note" class="muted small"></span></div><div id="ag-map"></div></section>
<div id="ag-cards-wrap"><div class="ag-tools"><input id="ag-search" type="search" placeholder="Find an agent by name or what it does" aria-label="Find an agent"><span id="ag-summary" class="muted small"></span></div>
<p class="muted small">Agents only propose; nothing they do is approved without you, and the rules apply on top of their limits. An agent pauses itself after 3 failed runs in a row or at its monthly budget. Agents are grouped by the job they share; ones needing attention are listed first.</p>
<div id="ag-groups"></div><div id="ag-table-wrap" class="table-wrap" hidden></div></div></div>
<div id="ag-detail" hidden></div>''',
'organisations': r'''<button id="opp-open" type="button" class="opp-tab" aria-controls="opp-drawer" aria-expanded="false">Opportunities<span id="opp-badge" class="badge-count" hidden></span></button>
<aside id="opp-drawer" class="opp-drawer" aria-label="Opportunity tracker" aria-hidden="true"><div class="opp-head"><h2>Opportunity tracker</h2><button id="opp-close" type="button" class="secondary">Close</button></div>
<p class="muted small">Temple scans each watched organisation's approved profile and recent news, and suggests opportunities with the news behind them. Track the ones worth pursuing; nothing is shared or sent anywhere.</p>
<div class="opp-filters"><div id="opp-status" class="mem-cats"></div><label class="small">Organisation <select id="opp-org"></select></label></div>
<div id="opp-list"></div>
<details id="opp-news-box"><summary>Latest news <span id="opp-news-n" class="muted small"></span></summary><ol id="opp-news"></ol></details>
<details id="opp-sched-box"><summary>Schedule</summary><p class="muted small">Scheduled scans run in the background (first slot: next Monday morning) and pause at the spending cap or if you pause the agent. Run now any time.</p><div id="opp-sched"></div></details>
<details id="opp-off-box"><summary>Your offerings</summary><p class="muted small">Temple maps each opportunity to one of these. One per line.</p><textarea id="opp-offerings" rows="7"></textarea><button id="opp-off-save" type="button" class="secondary">Save offerings</button></details>
</aside><div id="opp-scrim" class="opp-scrim" hidden></div>
<div id="o-demo-bar" class="o-demo-bar" hidden><strong>Demo data.</strong> These are fictional organisations kept in a separate store; your real organisations are hidden and untouched. Research and opportunity scans are off. <button id="o-demo-reset" type="button" class="secondary mini-act">Reset demo data</button></div>
<div class="o-shell">
<aside class="o-side" aria-label="Organisations list">
 <div class="o-side-head"><input id="o-search" type="search" placeholder="Find an organisation" aria-label="Find an organisation"><button id="o-add-toggle" type="button" title="Add an organisation">+ Add</button></div>
 <div id="o-filter" class="o-chips"></div>
 <div class="o-side-sel"><select id="o-f-kind" aria-label="Type"></select><select id="o-f-mgr" aria-label="Account manager"></select></div>
 <div class="o-side-foot"><span id="o-summary" class="muted small"></span><label class="o-demo-toggle" title="Show fictional organisations instead of your real ones"><input id="o-demo" type="checkbox"> Demo data</label></div>
 <div id="o-list"></div>
</aside>
<div class="o-main">
 <section id="o-add" hidden><div class="mem-head"><h2>Add an organisation</h2><button id="o-add-close" type="button" class="secondary mini-act">Close</button></div>
  <div class="o-research-new"><h3>Research it online</h3><p class="muted small">Type a name, a website, or both. Temple searches the public web and proposes facts for each section, every one citing the page it came from. Nothing is approved until you approve it.</p>
  <div class="k-meta-row"><label>Name<input id="o-r-name" maxlength="60" placeholder="e.g. Perth and Kinross Council"></label><label>Website<input id="o-r-web" maxlength="300" placeholder="e.g. https://www.pkc.gov.uk"></label></div>
  <button id="o-r-go" type="button">Research online</button> <span id="o-r-status" class="muted small" role="status"></span></div>
  <details><summary>Or add it without research</summary><div class="k-meta-row"><label>Name<input id="o-new-name" maxlength="60"></label><label>Type<select id="o-new-kind"></select></label><label>Description<input id="o-new-desc" maxlength="500"></label></div><label class="r-check"><input id="o-new-client" type="checkbox"> Client (keep its material apart from other clients)</label><button id="o-new-save" type="button">Add organisation</button></details></section>
 <section id="o-empty" class="o-empty"><h2>Organisations</h2><p class="muted">Summaries, not documents: each fact is a sentence or two with its source and a review-by date. Facts you add are approved; facts from models wait for your approval. Organisational information and roles only, not people.</p><p class="muted">Choose an organisation on the left, or add one.</p></section>
 <div id="o-detail" hidden>
  <section class="o-head"><div class="o-head-top"><div><h2 id="o-title"></h2><div id="o-meta" class="o-meta"></div></div>
   <div class="o-head-act"><button id="o-research" type="button">Research online</button><button id="o-opp-scan" type="button" class="secondary">Scan for opportunities</button><button id="o-opp-view" type="button" class="secondary">Open tracker</button></div></div>
   <p id="o-research-status" class="muted small" role="status"></p><p id="o-opp-status" class="muted small" role="status"></p></section>
  <details class="o-sec" data-sec="details"><summary><span>Details</span><span id="o-sum-details" class="o-sum"></span></summary><div class="o-sec-body">
   <div class="k-meta-row"><label>Type<select id="o-kind"></select></label><label>Account manager<input id="o-mgr" list="o-mgr-list" maxlength="80" placeholder="e.g. Morven Hay"><datalist id="o-mgr-list"></datalist></label></div>
   <div class="k-meta-row"><label>Description<input id="o-desc" maxlength="500"></label><label>Website<input id="o-web" maxlength="300" placeholder="https://"></label></div>
   <label class="r-check"><input id="o-client" type="checkbox"> Client: keep its memories, files and chats apart from other clients'</label>
   <div id="o-aliases-wrap" class="k-meta-row"><label>Other names Alice should recognise (comma separated)<input id="o-aliases" maxlength="400" placeholder="e.g. SBC, Scottish Borders"></label></div>
   <p id="o-client-help" class="muted small">Alice spots a client in chats and files by its name and its other names, so use names of the organisation, not of people.</p>
   <p class="muted small">The account manager is for your own tracking: it is never sent to a model. It is typed here for now and can be looked up from Entra ID once Alice runs in Azure.</p>
   <button id="o-save" type="button" class="secondary">Save details</button></div></details>
  <details class="o-sec" data-sec="facts" open><summary><span>Profile facts</span><span id="o-sum-facts" class="o-sum"></span></summary><div class="o-sec-body"><div id="o-status" class="mem-tabs"></div><div id="o-facts"></div></div></details>
  <details class="o-sec" data-sec="opps"><summary><span>Opportunities</span><span id="o-sum-opps" class="o-sum"></span></summary><div class="o-sec-body">
   <div class="arc-actions"><label class="small">Scan for opportunities <select id="o-opp-freq"><option value="weekly">weekly</option><option value="fortnightly">fortnightly</option><option value="monthly">monthly</option><option value="off">off</option></select></label></div><div id="o-opp-mini"></div></div></details>
  <details class="o-sec" data-sec="tagged" id="o-tagged-sec"><summary><span>Tagged material</span><span id="o-sum-tagged" class="o-sum"></span></summary><div class="o-sec-body"><p id="o-tagged-text" class="small"></p><button id="o-tagged-show" type="button" class="secondary">Show and change tags</button></div></details>
  <details class="o-sec" data-sec="research"><summary><span>Research history</span><span id="o-sum-research" class="o-sum"></span></summary><div class="o-sec-body"><div id="o-research-box"></div></div></details>
  <details class="o-sec" data-sec="add"><summary><span>Add a fact</span></summary><div class="o-sec-body">
   <div class="k-meta-row"><label>Section<select id="f-section"></select></label><label>Security label<select id="f-label"></select></label></div><p id="f-hint" class="muted small"></p>
   <label>Fact: a summary in a sentence or two<textarea id="f-statement" rows="3" maxlength="400"></textarea></label><span id="f-count" class="muted small"></span>
   <div class="k-meta-row"><label>Source system<input id="f-system" maxlength="80" placeholder="e.g. Council Plan (public website), SharePoint, Dataverse"></label><label>Source reference<input id="f-ref" maxlength="500" placeholder="URL, record ID or document name"></label></div>
   <div class="k-meta-row"><label>As of<input id="f-asof" type="date"></label><label>Review by (blank = default)<input id="f-review" type="date"></label></div><button id="f-save" type="button">Add fact</button></div></details>
  <details class="o-sec" data-sec="brief"><summary><span>Brief models receive</span></summary><div class="o-sec-body"><div class="arc-actions"><label>For <select id="b-provider"></select></label><label class="r-check"><input id="b-external" type="checkbox"> As an external app (Claude Desktop, Copilot)</label><button id="b-show" type="button" class="secondary">Show brief</button></div><pre id="b-text" class="k-text"></pre></div></details>
 </div>
 <details class="o-sec o-erase" data-sec="erase"><summary><span>Remove facts from a source</span><span class="o-sum">Erasure requests and withdrawn sources</span></summary><div class="o-sec-body"><p class="muted small">Across all organisations: retires every approved fact and rejects every proposal whose source matches. History is kept as retired.</p>
 <div class="k-meta-row"><label>Source system<input id="r-system" maxlength="80"></label><label>Source reference (optional)<input id="r-ref" maxlength="500"></label><label>Reason<input id="r-reason" maxlength="500" placeholder="e.g. erasure request"></label></div><div class="arc-actions"><button id="r-check" type="button" class="secondary">Check what matches</button><button id="r-go" type="button" class="secondary">Remove</button><span id="r-result" class="small" role="status"></span></div></div></details>
<details id="o-tagging" class="o-sec o-erase" data-sec="tagging"><summary><span>Tag memories and files</span><span id="c-summary" class="o-sum"></span></summary><div class="o-sec-body">
<p class="muted small">Untagged material is <strong>General</strong> and visible in every chat. Tag a chat with a client (in the chat header) and uploads and memories from it inherit that client automatically. Separation settings (strict mode, external apps) are under <a href="/admin/rules">Rules → Client separation</a>.</p>
<div class="arc-actions"><button id="c-run" type="button">Tag untagged with Temple</button></div><p class="muted small">Names and aliases are matched first at no cost; Temple reads the rest. Confident matches (75%+) are applied using the same Auto-assign / Suggest mode as categories; Temple never overrides your choice.</p><p id="c-run-result" class="small" role="status"></p>
<div class="t-tabs"><button id="c-tab-memory" type="button" class="chip on">Memories</button><button id="c-tab-file" type="button" class="chip">Files</button></div>
<div class="mem-tools"><input id="c-query" type="search" maxlength="200" placeholder="Search" aria-label="Search items"></div><div id="c-filters" class="mem-cats"></div>
<div id="c-bulk" class="mem-bulk" hidden><strong id="c-selected"></strong><button id="c-accept" type="button" class="secondary">Accept suggestions</button><span class="bulk-cat"><select id="c-bulk-client" aria-label="Client for selected"></select><button id="c-set" type="button" class="secondary">Set client</button></span><button id="c-clear" type="button" class="secondary">Clear</button></div>
<div class="table-wrap"><table id="c-table" class="mem-table"></table></div><p id="c-count" class="muted small"></p><button id="c-more" type="button" class="secondary" hidden>Load more</button></div></details>
</div></div>''',
'knowledge': r'''<section><div class="mem-head"><h2>Knowledge library</h2><span id="k-summary" class="muted small"></span></div>
<div class="k-review-row small"><label>Review new and approved items after <input id="k-review-days" type="number" min="0" max="730" step="1" aria-label="Default review period in days"> days</label><button id="k-review-save" type="button" class="secondary mini-act">Save</button><span class="muted">0 = no default. Applies from now on; each item's own review date can still be changed.</span></div>
<div class="arc-actions"><button id="k-new-note" type="button">New note</button><button id="k-new-meeting" type="button" class="secondary">Add meeting extract</button><button id="k-categorise" type="button" class="secondary">Categorise with Temple</button><button id="k-find-replaced" type="button" class="secondary">Find replaced items</button><span id="k-cat-result" class="small" role="status"></span></div>
<div id="k-note" class="k-panel" hidden><h3>New note or summary</h3><label>Title<input id="kn-title" maxlength="200"></label><label>Content<textarea id="kn-content" rows="8" maxlength="90000"></textarea></label><label>Source<input id="kn-source" maxlength="500" value="Written by you"></label><div class="k-meta-row"><label>Category<select id="kn-category"></select></label><label>Client<select id="kn-client"></select></label><label>Security label<select id="kn-label"></select></label></div><div class="arc-actions"><button id="kn-save" type="button">Save note</button><button id="kn-cancel" type="button" class="secondary">Cancel</button></div></div>
<div id="k-meeting" class="k-panel" hidden><h3>Meeting extract</h3><p class="muted small">Paste a transcript or notes, or load a Teams .vtt, Word or text file. Temple drafts the summary, decisions and actions for you to check before saving. Secrets and protective markings are blocked before anything is sent to Temple.</p>
<div id="km-step1"><label>Transcript or notes<textarea id="km-transcript" rows="8" maxlength="90000"></textarea></label><div class="arc-actions"><input id="km-file" type="file" accept=".vtt,.docx,.txt" hidden><button id="km-load" type="button" class="secondary">Load file…</button><button id="km-extract" type="button">Extract with Temple</button><button id="km-cancel" type="button" class="secondary">Cancel</button></div></div>
<div id="km-step2" hidden><label>Title<input id="km-title" maxlength="200"></label><div class="k-meta-row"><label>Date<input id="km-date" type="date"></label><label>Attendees (comma separated)<input id="km-attendees" maxlength="2000"></label></div><label>Summary<textarea id="km-summary" rows="5"></textarea></label><label>Decisions (one per line)<textarea id="km-decisions" rows="4"></textarea></label><label>Actions (one per line: action | owner | due)<textarea id="km-actions" rows="4"></textarea></label><label>Source<input id="km-source" maxlength="500" value="Teams meeting transcript"></label><div class="k-meta-row"><label>Category<select id="km-category"></select></label><label>Client<select id="km-client"></select></label><label>Security label<select id="km-label"></select></label></div><label class="r-check"><input id="km-keep" type="checkbox" checked> Keep the transcript with the extract (searchable)</label><div class="arc-actions"><button id="km-save" type="button">Save meeting extract</button><button id="km-back" type="button" class="secondary">Back</button></div></div></div></section>
<section><div id="k-status" class="mem-tabs"></div><div class="mem-tools"><input id="k-query" type="search" maxlength="200" placeholder="Search titles, sources and summaries" aria-label="Search knowledge"><label>Category <select id="k-f-category"></select></label><label>Client <select id="k-f-client"></select></label><label>Owner <select id="k-f-owner"></select></label></div><div id="k-kinds" class="mem-cats"></div><div id="k-labels" class="mem-cats"></div>
<div id="k-bulk" class="mem-bulk" hidden><strong id="k-selected"></strong><button id="k-approve" type="button">Approve</button><button id="k-reject" type="button" class="secondary">Reject</button><span class="bulk-cat"><select id="k-b-category" aria-label="Category for selected"></select><button id="k-b-cat" type="button" class="secondary">Set category</button></span><span class="bulk-cat"><select id="k-b-client" aria-label="Client for selected"></select><button id="k-b-client-set" type="button" class="secondary">Set client</button></span><span class="bulk-cat"><select id="k-b-label" aria-label="Label for selected"></select><button id="k-b-label-set" type="button" class="secondary">Set label</button></span><span class="bulk-cat"><input id="k-b-owner" list="owner-list" maxlength="80" placeholder="Owner (blank = none)" aria-label="Owner for selected"><button id="k-b-owner-set" type="button" class="secondary">Set owner</button></span><button id="k-archive" type="button" class="secondary">Archive</button><button id="k-clear" type="button" class="secondary">Clear</button></div><datalist id="owner-list"></datalist>
<div class="table-wrap"><table id="k-table" class="mem-table"></table></div><p id="k-count" class="muted small"></p><button id="k-more" type="button" class="secondary" hidden>Load more</button>
<p class="muted small">Models only read <strong>Active</strong> items their label allows. Drafts proposed by models stay invisible until you approve them. Labels: General (any model) · Internal (providers allowed in Rules) · Client-confidential (client separation; never external apps) · Local only (never sent to any model).</p></section>''' ,
'memories': r'''<section id="categories"><div class="mem-head"><h2>Categories</h2><span id="cat-summary" class="muted small"></span></div>
<details id="cat-panel"><summary>Manage categories and Temple assignment</summary><div class="cat-grid">
<div><div id="cat-rows"></div><form id="cat-form" class="cat-form"><input id="cat-name" type="text" maxlength="40" placeholder="New category, e.g. Work" aria-label="New category name" required><input id="cat-desc" type="text" maxlength="300" placeholder="What belongs here? Temple uses this to decide" aria-label="Category description"><button>Add category</button></form></div>
<div class="temple-box"><h3>Temple assignment</h3><label>Mode <select id="cat-mode"><option value="auto">Auto-assign confident matches</option><option value="suggest">Suggest only</option><option value="off">Off</option></select></label><p class="muted small">Temple only fills uncategorised memories, only picks from your categories, and never overrides a category you chose. Matches at 75% confidence or above are applied and marked ✦; the rest become suggestions for you to accept or dismiss. New memories are categorised automatically.</p><button id="cat-run" type="button">Categorise uncategorised now</button><p id="cat-run-result" class="small" role="status"></p></div>
</div></details></section>
<section id="records"><div class="mem-head"><h2>Memories</h2><a href="/admin/temple">Temple recommendations ↗</a></div>
<p class="muted small">Only active (approved) memories are searchable by models. Resolve frictions by approving a replacement; retire memories that no longer apply. History is always kept.</p>
<div id="mem-tabs" class="mem-tabs" role="tablist" aria-label="Memory status"></div><div id="mem-kinds" class="mem-cats" aria-label="Memory type"></div>
<div class="mem-tools"><input id="mem-query" type="search" maxlength="200" placeholder="Search title, content or source" aria-label="Search memories"><label>Owner <select id="mem-owner"></select></label><label>Sort <select id="mem-sort"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="title">Title A–Z</option><option value="category">Category</option><option value="reviewed">Recently reviewed</option></select></label></div>
<div id="mem-cats" class="mem-cats" aria-label="Filter by category"></div>
<div id="mem-bulk" class="mem-bulk" hidden><strong id="mem-selected"></strong><button id="bulk-approve" type="button">Approve</button><button id="bulk-reject" type="button" class="secondary">Reject</button><button id="bulk-accept" type="button" class="secondary">Accept suggestions</button><span class="bulk-cat"><select id="bulk-cat" aria-label="Category for selected"></select><button id="bulk-set" type="button" class="secondary">Set category</button></span><span class="bulk-cat"><input id="bulk-owner" list="owner-list" maxlength="80" placeholder="Owner (blank = none)" aria-label="Owner for selected"><button id="bulk-owner-set" type="button" class="secondary">Set owner</button></span><button id="bulk-clear" type="button" class="secondary">Clear</button></div>
<datalist id="owner-list"></datalist>
<div class="table-wrap"><table id="mem-table" class="mem-table"></table></div>
<p id="mem-count" class="muted small"></p><button id="mem-more" type="button" class="secondary" hidden>Load more</button>
<details><summary>Propose a memory manually</summary><form id="proposal"><label>Title<input id="title" type="text" maxlength="200" required></label><label>Content<textarea id="content" maxlength="8000" rows="4" required></textarea></label><label>Source description<textarea id="source" maxlength="2000" rows="2" placeholder="User statement, or filename and page/row" required></textarea></label><label>Category <select id="proposal-category"></select></label><button>Submit for review</button></form></details></section>''' ,
'archive': r'''<section><div class="mem-head"><h2>Import from Claude</h2><span class="muted small">Verbatim copies of your Claude conversations</span></div>
<p class="muted small">In Claude: Settings → Privacy → Export data. You'll get an email with a zip, or for larger accounts a small manifest file. Choose the manifest and Alice downloads every batch (each link works once; copies are kept in data\\imports) and imports them. You can also select zips directly; several import one after another. Running it again later only adds new conversations and updates ones that have grown. Conversations containing credentials or protective markings are skipped and listed, never stored.</p>
<div class="arc-actions"><input id="imp-file" type="file" accept=".zip,.json" multiple hidden><label class="r-param">Only conversations updated since (optional)<input id="imp-since" type="date"></label><button id="imp-go" type="button">Choose export files and import…</button></div><div id="imp-progress" class="imp-progress" hidden><div class="imp-bar"><span id="imp-fill"></span></div><div id="imp-label" class="small" aria-live="polite"></div></div><div id="imp-result" class="small" role="status"></div></section>
<section id="archive"><div class="mem-tools"><input id="arc-query" type="search" maxlength="200" placeholder="Search chat titles" aria-label="Search archived chats"><label>Sort <select id="arc-sort"><option value="recent">Most recently used</option><option value="oldest">Longest inactive</option><option value="created">Newest created</option><option value="title">Title A–Z</option></select></label></div>
<div class="mem-head"><div id="arc-filters" class="mem-tabs"></div><button id="arc-review-flagged" type="button" class="secondary">Ask Temple to review flagged chats</button></div>
<div class="table-wrap"><table id="arc-table" class="mem-table"></table></div><p id="arc-count" class="muted small"></p><button id="arc-more" type="button" class="secondary" hidden>Load more</button>
<p class="muted small">Captured means memories proposed from the chat (by the model, from a saved conversation, or accepted from Temple) or knowledge notes saved from it. Files you uploaded into a chat are not counted. Temple's suggestions go to <a href="/admin/temple?tab=suggestions">Temple → Chat suggestions</a> for your approval.</p></section>''' ,
'rules': r'''<section><div class="mem-head"><h2>Rule sets</h2><span id="r-counts" class="muted small"></span></div>
<p class="muted small">Higher sets win: Security, then Organisation, Memory governance, Cost and Personal. <strong>Enforced</strong> rules run in code at the points where data moves, so no model can get round them. <strong>Guidance</strong> rules are sent to models as instructions; they shape answers but are advisory, especially in Claude Desktop.</p>
<div id="r-spend" class="spend"></div></section>
<section id="r-packs"><div class="mem-head"><h2>Applied rule packs</h2><a href="/admin/rule-packs" class="small">Rule packs ↗</a></div>
<p id="r-packs-scope" class="muted small"></p><div id="r-packs-list"></div>
<details class="r-svc"><summary>AI services: inside or outside your tenant</summary><p class="muted small">Packs block sensitive material going to services outside your tenant or the UK. Mark which of Alice's services count as inside. Auto routing counts as inside only if all three chat services are.</p><div id="r-packs-svc"></div></details></section>
<section id="pv"><div class="mem-head"><h2>Purview sensitivity labels</h2><span id="pv-summary" class="muted small"></span></div>
<p class="muted small">Files carrying a Microsoft Purview sensitivity label are handled by its mapping here. Alice reads the label; it never changes or removes it. A label not mapped yet: names that are protective markings (such as OFFICIAL-SENSITIVE) are blocked; anything else is treated as Internal until you map it.</p>
<div id="pv-list"></div>
<details><summary>Add a label before Alice has seen it</summary><div class="k-meta-row"><label>Label ID<input id="pv-id" maxlength="40" placeholder="GUID from the Purview portal"></label><label>Name<input id="pv-name" maxlength="120" placeholder="e.g. Confidential"></label><label>Handle as<select id="pv-action"></select></label></div><button id="pv-add" type="button" class="secondary">Add mapping</button></details></section>
<div id="r-sets"></div>
<section id="r-requests-box" hidden><h2>Rule requests from Temple</h2><p class="muted small">Behaviour you asked for in chat. Turn one into a guidance rule, or keep it as a note for a future enforced rule.</p><div id="r-requests"></div></section>
<section><h2>Additional guidance</h2><form id="rule-form"><label><input id="allow" type="checkbox"> Allow new memory proposals</label><label>Free-text guidance, added after the rule sets<textarea id="guidance" maxlength="8000" rows="4"></textarea></label><button>Save</button></form>
<details><summary>What models receive</summary><pre id="r-effective"></pre></details></section>
<section><h2>Recent rule blocks</h2><div id="r-blocks"></div></section>''' ,
'activity': r'''<section class="av-bar"><div class="mem-tools"><label>Period <select id="al-period"><option value="today">Today</option><option value="7d" selected>Last 7 days</option><option value="30d">Last 30 days</option><option value="all">All time</option><option value="custom">Custom…</option></select></label>
<span id="al-custom" hidden><label>From <input id="al-from" type="date"></label> <label>To <input id="al-to" type="date"></label></span>
<span class="av-views" id="av-views"></span></div></section>
<div id="av" class="av" aria-live="polite"></div>
<section id="al-log"><h2 class="av-h">Everything that happened</h2><div class="mem-tools"><input id="al-q" type="search" maxlength="200" placeholder="Search what happened, names and details" aria-label="Search activity"><a id="al-csv" class="button-link" href="#">Export CSV</a></div>
<div id="al-types" class="mem-cats"></div><div class="table-wrap"><table id="al-table" class="mem-table al-table"></table></div><p id="al-count" class="muted small"></p><button id="al-more" type="button" class="secondary" hidden>Load more</button>
<p class="muted small">Reads by Claude Desktop and Claude Code are not logged; their proposals, drafts and saved conversations are. Times are shown in your local time; the CSV uses UTC.</p></section>''' ,
}

CSS = r'''
/* Command centre: same look as the chat page (shared tokens, buttons and top bar from ui_theme). */
body{display:grid;grid-template-rows:52px minmax(0,1fr);height:100vh;overflow:hidden}
.page-title{position:absolute;left:calc(248px + (100% - 248px)/2);transform:translateX(-50%);margin:0;font-size:18px;line-height:24px;font-weight:700;color:#fff;white-space:nowrap;max-width:calc(100% - 640px);overflow:hidden;text-overflow:ellipsis}
.shell{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:0}
.sidebar{background:#fff;border-right:1px solid var(--line);padding:12px 10px;overflow:auto;display:flex;flex-direction:column;gap:1px}
.sidebar .grp{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:12px 10px 4px}.sidebar .grp:first-child{margin-top:2px}
.sidebar a{display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:14px}
.sidebar a:hover{background:#f1f6f9}.sidebar a[aria-current=page]{background:var(--teal2);font-weight:600}
#demo-toggle{font:inherit;font-size:13px;cursor:pointer}#demo-toggle.demo-on{background:#e2a33b;border-color:#e2a33b;color:#1b1203;font-weight:600}
.nav-count{margin-left:auto;font-size:11px;font-weight:700;line-height:17px;background:#fdf3e1;color:#6b4406;border:1px solid #e2bf85;border-radius:999px;padding:0 7px}
.content{overflow:auto;padding:20px 32px 48px;min-width:0}.content>.inner{max-width:1180px;margin:0 auto}
.page-desc{margin:0 0 14px;color:var(--muted);font-size:14px;line-height:1.5}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 16px}
h2{font-size:17px;line-height:1.35;margin:0 0 10px}h3{font-size:15px;margin:14px 0 6px}h4{font-size:14px;margin:12px 0 4px}section>h2:first-child{margin-top:0}
p,li{line-height:1.6}label{display:block;margin:10px 0}textarea,input[type=text]{width:100%;margin:6px 0}
.content button{margin:4px 6px 4px 0}
.content button:not(.secondary):not(.chip):not(.mini):not(.mem-title):not(.ghost):not(.ag-card):not(.o-item),.button{background:var(--teal);border:1px solid var(--teal);color:#fff;font-weight:600;border-radius:8px;padding:6px 14px;text-decoration:none;display:inline-block}
.content button:not(.secondary):not(.chip):not(.mini):not(.mem-title):not(.ghost):not(.ag-card):not(.o-item):hover:not(:disabled),.button:hover{background:var(--teal-d);border-color:var(--teal-d)}
.content button.secondary{background:#fff;color:var(--ink)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:500px;overflow:auto;font:13px/1.6 ui-monospace,Consolas,monospace}summary{cursor:pointer}
.card{border-top:1px solid var(--line);padding:16px 0;overflow-wrap:anywhere}.card p{overflow-wrap:anywhere}
.approved,.proposed,.rejected,.superseded,.retired{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;border:1px solid}
.approved{background:#e6f4ea;color:#1e5b31;border-color:#9fcfaf}.proposed{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.rejected{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}.superseded,.retired{background:#eef1f4;color:#4b5a66;border-color:#c1cbd3}
#notice{position:sticky;top:0;z-index:5;background:var(--teal2);border:1px solid #89b1bf;border-radius:8px;padding:10px 12px;margin:0 0 12px;white-space:pre-wrap}#notice:empty{display:none}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.stat{padding:18px 20px;background:#fff;border:1px solid var(--line);border-radius:10px;text-decoration:none;display:flex;flex-direction:column;gap:4px;color:var(--ink)}
.stat strong{font-size:30px;color:var(--teal);font-weight:600}.stat span{color:var(--muted);font-size:13px}.stat:hover{border-color:#89b1bf}
nav{display:flex;gap:20px;flex-wrap:wrap}.sidebar nav{display:contents}
@media(max-width:900px){body{height:auto;overflow:auto;display:block}.shell{display:block}.sidebar{flex-direction:row;flex-wrap:wrap;border-right:0;border-bottom:1px solid var(--line);padding:8px}.sidebar .grp{display:none}.sidebar a{padding:6px 9px;font-size:13px}
 .content{padding:16px}.page-title{position:static;transform:none;font-size:16px;max-width:none;flex:1}.brand{width:auto}.brand span{display:none}.stats{gap:10px}}
.usage-bar{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.usage-bar h2{margin:0 auto 0 0}.usage-bar label{margin:0}.usage-stats{grid-template-columns:repeat(4,minmax(0,1fr));margin-top:16px}.usage-stats .stat strong{font-size:28px;font-variant-numeric:tabular-nums}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #a9bdcb;vertical-align:top}thead th{font-weight:650;border-bottom-width:2px;white-space:nowrap}tfoot td{font-weight:700;border-top:2px solid #a9bdcb;border-bottom:0}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}tbody tr:hover{background:#00677a0d}#usage-savings td:nth-child(3){min-width:260px;color:var(--muted,#435a6d)}#usage-days td:last-child{width:40%}.bar{display:block;height:10px;min-width:2px;border-radius:3px;background:#00738c}
@media(max-width:760px){.usage-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.mem-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}.small{font-size:13px}
.mem-tabs,.mem-cats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.chip{text-transform:none!important;letter-spacing:normal!important;clip-path:none!important;box-shadow:none!important;font-family:system-ui,sans-serif!important;margin:0!important;padding:7px 13px!important;border-radius:999px!important;font-size:13px!important;background:#eef3f7!important;color:#1d3a50!important;border:1px solid #a9bdcb!important;font-weight:500}.chip.on,.chip.on:hover{background:#075e79!important;color:#fff!important;border-color:#075e79!important}.chip:hover:not(.on){background:#dde9f0!important;color:#1d3a50!important}.chip.attention:not(.on){border-color:#b7791f!important;background:#fdf3e1!important;color:#6b4406!important}.mem-cats .chip{font-size:12px!important;padding:5px 11px!important}
.mem-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.mem-tools input[type=search]{flex:1 1 280px;margin:0}.mem-tools label{margin:0;white-space:nowrap}
.mem-bulk[hidden]{display:none!important}.mem-bulk{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 12px;margin:10px 0;background:#e3f1f6;border:1px solid #75a4b3;border-radius:8px}.mem-bulk button{margin:0}.bulk-cat{display:inline-flex;gap:6px}.bulk-cat input{margin:0;width:170px}
.mem-table td{vertical-align:top}.mem-table th:first-child,.mem-table td:first-child{width:34px}.mem-title{all:unset;cursor:pointer;display:block;background:none!important;border:0!important;box-shadow:none!important;padding:0!important;margin:0!important;color:#102b40!important;font:600 15px/1.4 system-ui,sans-serif!important;text-transform:none!important;letter-spacing:normal!important;clip-path:none!important;text-align:left}.mem-title:hover{text-decoration:underline}.mem-title:focus-visible{outline:3px solid #67e8f9}.mem-row.open .mem-title{color:#075e79}.mem-preview{font-size:13px;color:#4b6376;margin-top:3px;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}.mem-row.open .mem-preview{display:none}
.tag{display:inline-block;font-size:12px;padding:3px 9px;border-radius:999px;background:#ede7f6;color:#4b2f73;border:1px solid #c7b8dd;white-space:nowrap}
.badge{display:inline-block;font-size:12px;padding:3px 9px;border-radius:5px;white-space:nowrap;border:1px solid}.badge.approved{background:#e6f4ea;color:#1e5b31;border-color:#9fcfaf}.badge.proposed{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.badge.superseded,.badge.retired{background:#eef1f4;color:#4b5a66;border-color:#c1cbd3}.badge.rejected{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}
.mem-detail-row>td{background:#f6f9fb}.mem-detail pre{background:#fff;border:1px solid #c9d7e1;border-radius:6px;padding:12px;margin:4px 0 10px}.cat-edit{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}.cat-edit input{width:200px;margin:0}
@media(max-width:760px){.mem-table th:nth-child(5),.mem-table td:nth-child(5){display:none}}
#cat-panel>summary{cursor:pointer;font-weight:600;margin:6px 0}.cat-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(260px,1fr);gap:22px;margin-top:14px}
.cat-row{padding:10px 0;border-bottom:1px solid #d3dee6}.cat-view{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.cat-view .cat-desc{flex:1 1 220px}.cat-count{color:#314d62;white-space:nowrap}.cat-view button,.cat-edit-form button{margin:0}
.cat-edit-form{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.cat-edit-form input{margin:0;flex:1 1 160px}.cat-form{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.cat-form input{margin:0;flex:1 1 180px}.cat-form button{margin:0}
.temple-box{background:#f4f0fa;border:1px solid #c7b8dd;border-radius:10px;padding:14px 16px}.temple-box h3{margin-top:0}.temple-box select{max-width:100%}
.temple-mark{color:#634394;margin-left:6px;font-size:13px;cursor:help}.suggest{display:flex;align-items:center;gap:6px;margin-top:6px;color:#634394}
.mini{margin:0!important;padding:2px 8px!important;font-size:12px!important;min-width:0;text-transform:none!important;clip-path:none!important;background:#ede7f6!important;color:#4b2f73!important;border:1px solid #c7b8dd!important;border-radius:5px!important}
@media(max-width:900px){.cat-grid{grid-template-columns:1fr}}
#arc-table th:first-child,#arc-table td:first-child{width:auto;min-width:260px}#arc-table th:nth-child(2),#arc-table th:nth-child(3),#arc-table td:nth-child(2),#arc-table td:nth-child(3){width:1%;white-space:nowrap}#arc-table th:nth-child(4){width:30%}.mem-title:hover,.mem-title:hover:not(:disabled),.mem-title:focus{background:none!important;color:#075e79!important}.flag{display:inline-block;font-size:12px;padding:3px 9px;border-radius:5px;background:#fdf3e1;color:#6b4406;border:1px solid #e2bf85;white-space:nowrap}.tag.know{background:#e3f1f6;color:#064b63;border-color:#89b1bf}#arc-table td .tag{margin:0 6px 4px 0}
.button-link[hidden],.arc-actions [hidden]{display:none!important}.transcript>strong{display:block;margin-top:10px}.arc-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}.arc-actions button{margin:0}.button-link{display:inline-block;padding:8px 14px;border:1px solid #075e79;border-radius:6px;text-decoration:none;font-size:14px}
.transcript{max-height:520px;overflow:auto;border:1px solid #c9d7e1;border-radius:8px;background:#fff;padding:12px}.t-msg{padding:10px 12px;border-radius:8px;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}.t-user{background:#eaf5f8;border-left:3px solid #21758b;margin-left:40px}.t-ai{background:#f3eff9;border-left:3px solid #786095}.t-label{font:600 11px system-ui;color:#4b6376;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em}.t-img{display:block;max-width:320px;max-height:240px;border-radius:6px;margin-top:8px}
.t-tabs{display:flex;gap:8px;margin-top:14px}.t-tabs .chip{font-size:14px!important;padding:8px 16px!important}#pane-reviews[hidden],#pane-suggestions[hidden]{display:none}#t-settings-panel>summary{cursor:pointer;font-weight:600;margin:4px 0 10px}
.badge.v-ok{background:#e6f4ea;color:#1e5b31;border-color:#9fcfaf}.badge.v-warn{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.badge.v-bad{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}.badge.v-none{background:#eef1f4;color:#4b5a66;border-color:#c1cbd3}.badge.v-run{background:#ede7f6;color:#4b2f73;border-color:#c7b8dd}
.t-reason{font-size:13px;color:#314d62;margin-top:5px;line-height:1.45;max-width:420px}#t-table td:nth-child(3){min-width:240px}#t-table td:nth-child(2),#s-table td:nth-child(2){min-width:260px}
.t-report,.t-quote{background:#fff;border:1px solid #c9d7e1;border-left:3px solid #786095;border-radius:6px;padding:10px 12px;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}.t-quote{border-left-color:#21758b}.t-related{border-left:2px solid #c7b8dd;padding:2px 0 2px 10px;margin:8px 0}.t-related p{margin:4px 0}
.tag.k-knowledge{background:#e3f1f6;color:#064b63;border-color:#89b1bf}.tag.k-guidance{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.tag.k-rule_request{background:#eef1f4;color:#4b5a66;border-color:#c1cbd3}
.mem-detail textarea{width:100%;margin:4px 0 8px}
.r-set h2{margin-bottom:4px}.r-row{border-top:1px solid #d3dee6;padding:12px 0}.r-row.off{opacity:.62}.r-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.r-desc{margin:6px 0 0 34px;color:#314d62}
.r-row textarea{width:calc(100% - 34px);margin:8px 0 0 34px}.r-params{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin:8px 0 0 34px}.r-params button,.r-add button{margin:0}.r-param{display:flex;flex-direction:column;font-size:13px;gap:4px;margin:0}.r-param input{width:140px;margin:0}.r-param.wide input{width:360px;max-width:70vw}
.r-toggle input{width:20px;height:20px;margin:0;accent-color:#075e79}.r-grid{display:flex;flex-direction:column;gap:6px;width:100%}.r-grid-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.r-grid-row select{margin:0;width:auto}.r-check{display:inline-flex;gap:4px;align-items:center;font-size:13px;margin:0 8px 0 0}.r-checks{display:flex;flex-wrap:wrap;gap:6px;width:100%}
.r-add{margin-top:10px}.r-add>summary{cursor:pointer;font-size:14px;color:#075e79}.r-add input,.r-add textarea{display:block;width:100%;margin:6px 0}
.spend-row{display:grid;grid-template-columns:100px 1fr 150px;gap:12px;align-items:center;margin:6px 0}.spend-bar{height:10px;background:#e3eaf0;border-radius:5px;overflow:hidden}.spend-fill{display:block;height:100%}.spend-fill.ok{background:#2e7d4f}.spend-fill.warn{background:#c08a1e}.spend-fill.bad{background:#b3261e}.spend-warning{color:#6b4406}.spend-blocked{color:#7a1f1f;font-weight:600}
.r-block{display:grid;grid-template-columns:130px 200px 1fr;gap:10px;padding:6px 0;border-top:1px solid #e3eaf0}#r-effective{white-space:pre-wrap}
.k-panel{border:1px solid #c9d7e1;border-radius:10px;padding:14px 16px;margin-top:12px;background:#f8fbfd}.k-panel[hidden],#km-step1[hidden],#km-step2[hidden]{display:none}.k-panel h3{margin-top:0}.k-panel label{display:block;margin:8px 0}.k-panel textarea,.k-panel input:not([type=checkbox]){width:100%}
.k-meta-row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}.k-meta-row label{flex:1 1 170px;margin:6px 0}.k-meta-row select,.k-meta-row input{width:100%}
.ag-tools{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px}#ag-search{flex:1;min-width:220px;max-width:460px}
.ag-group{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:0 18px;margin:12px 0}.ag-group[open]{padding-bottom:18px}
.ag-group>summary{list-style:none;display:flex;align-items:center;gap:10px;cursor:pointer;padding:14px 0}.ag-group>summary::-webkit-details-marker{display:none}
.ag-group>summary::before{content:'▸';color:var(--muted);transition:transform .15s}.ag-group[open]>summary::before{transform:rotate(90deg)}
.ag-group>summary h2{margin:0;font-size:17px}.ag-count{background:var(--teal2);color:var(--teal);border-radius:999px;padding:0 9px;font-size:12px;font-weight:700;line-height:20px}
.ag-attn{font-size:12px;color:#8a5a00;font-weight:600}.ag-empty{color:var(--muted);font-size:14px;padding:4px 0}
.ag-gabout{margin:-6px 0 12px}.ag-table{width:100%;table-layout:fixed}.ag-table th:nth-child(1){width:44%}.ag-table th:nth-child(2){width:10%}.ag-table th:nth-child(3){width:19%}.ag-table th:nth-child(5){width:13%;text-align:right}.ag-trow{cursor:pointer}.ag-trow:hover td{background:#f4f8fb}.ag-trow:focus-visible{outline:2px solid var(--teal)}.ag-trow.off td{background:#fffbf3}
.ag-trow-g td{background:var(--bg);padding-top:14px!important}.ag-trow-g strong{font-size:14px;margin-right:6px}.ag-tpurpose{max-width:640px;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical}.ag-tattn{color:#8a4b00;margin-top:2px}
@media(max-width:800px){.ag-table th:nth-child(4),.ag-table td:nth-child(4),.ag-table th:nth-child(5),.ag-table td:nth-child(5){display:none}}
.ag-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.ag-card{all:unset;box-sizing:border-box;cursor:pointer;display:flex;flex-direction:column;gap:8px;border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:#fff;min-width:0}
.ag-card:hover{border-color:#89b1bf;box-shadow:0 2px 10px #0b162612}.ag-card:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.ag-card.off{border-color:#e2bf85;background:#fffbf3}.ag-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.ag-card-top strong{font-size:15px}
.ag-card-purpose{font-size:13px;color:var(--muted);line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ag-card-foot{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:auto}.ag-card-stat{margin-left:auto}
.ag-card-flags{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12px;color:#6b4406}
.ag-head{padding-bottom:6px}.ag-head>button{margin:0 0 10px}.ag-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.ag-title h2{margin:0;font-size:20px}
.ag-ctl{display:flex;gap:6px;margin-top:10px}.ag-reason{margin:10px 0 0;padding:8px 12px;border-radius:8px;background:#fdf3e1;border:1px solid #e2bf85;color:#4a3004;font-size:13px}
.ag-tabs{margin:14px 0 0}.ag-purpose{font-size:15px;margin:0 0 14px}.ag-stats{grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:16px}
.ag-facts{display:grid;grid-template-columns:160px 1fr;gap:6px 14px;margin:0 0 16px;font-size:14px}.ag-facts dt{color:var(--muted)}.ag-facts dd{margin:0}
.ag-mini{display:grid;grid-template-columns:120px 90px 130px 1fr;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)}.ag-mini-sum{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ag-view{margin:0 0 12px}
.anat{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:22px;margin:4px 0 18px}
.anat-stage{position:relative;border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:#fff;font-size:13px;line-height:1.45;min-width:0}
.anat-stage:not(:last-child):after{content:'→';position:absolute;right:-19px;top:50%;transform:translateY(-50%);color:#7e95a6;font-size:16px}
.anat-title{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
.anat-stage ul{margin:0;padding-left:16px}.anat-stage li{margin:1px 0}.anat-sub{font-size:11px;color:var(--muted);margin:6px 0 2px}.anat-sub:first-of-type{margin-top:0}
.anat-model{font-weight:600;color:var(--teal);margin:2px 0}.anat-instr{color:var(--muted);font-style:italic;margin:4px 0}.anat-small{font-size:12px;color:var(--muted);margin-top:6px}.anat-empty{color:var(--faint)}
.t-agent{border-color:#89b1bf;background:var(--teal2)}.t-guard{border-color:#c7b8dd;background:var(--violet2)}.t-you{border-color:#9fcfaf;background:#eef8f1}
.anat-guards{list-style:none;padding-left:0!important}.anat-guards li.off{color:var(--faint);text-decoration:line-through}
.ag-map-svg{width:100%;height:auto;display:block}.m-head{font-size:13px;font-weight:600;fill:#5d7385;letter-spacing:.06em;text-transform:uppercase}
.m-rules{fill:#f1ebf7;stroke:#9d86c0;stroke-width:1.5;stroke-dasharray:6 5}.m-rules-label{font-size:12px;fill:#634394;font-weight:600}
.m-store{fill:#fff;stroke:#89b1bf}.m-outside{fill:#f6f8fa;stroke:#9fb2c1;stroke-width:1.2;stroke-dasharray:4 4}.m-outside-label{font-size:12px;fill:#4b5a66;font-weight:600}.m-src{fill:#fff;stroke:#b7a46a}.m-link.ext{stroke-dasharray:5 4;stroke:#8a6d1f}.m-link.ext.app{stroke:#634394}.m-store-t{font-size:13px;fill:#14324a;font-weight:600}
.m-link{fill:none;stroke:#075e79;stroke-opacity:.35;stroke-width:1.5}.m-link.app{stroke:#634394}.m-link.off{stroke:#b9c6cf;stroke-dasharray:3 4}
.m-node{cursor:pointer}.m-node rect{fill:#fff;stroke:#89b1bf}.m-node.app rect{stroke:#c7b8dd}.m-node:hover rect,.m-node:focus rect{stroke:#075e79;stroke-width:2}.m-node.off rect{fill:#f4f6f8;stroke:#c1cbd3}
.m-name{font-size:13px;font-weight:600;fill:#14324a}.m-node.off .m-name{fill:#8aa0b0}.m-sub{font-size:11px;fill:#5d7385}
.m-dot.active{fill:#55b987}.m-dot.paused{fill:#e2a33b}.m-dot.stopped{fill:#b3261e}
.m-gate{stroke:#7e95a6;stroke-width:1.5}.m-you{fill:#eef8f1;stroke:#9fcfaf}.m-you-t{font-size:13px;font-weight:600;fill:#1e5b31}.m-small{font-size:11px;fill:#5d7385}
.ag-anat-edit{border-top:1px solid var(--line);margin-top:16px;padding-top:4px}.ag-anat-edit input,.ag-anat-edit textarea{width:100%}
@media(max-width:1100px){.anat{grid-template-columns:repeat(3,minmax(0,1fr))}.anat-stage:nth-child(3):after{display:none}}
.ag-perms{display:grid;gap:10px;margin:6px 0 10px}.ag-perm strong{margin-right:6px}
.t-parker{background:#f6f2fb!important;border-color:#d6c8ea!important}.t-parker summary{color:#4b2f73!important}
.t-auto{margin:10px 0;background:#eef8f1;border:1px solid #9fcfaf;border-radius:10px;padding:8px 12px}.t-auto summary{cursor:pointer;font-weight:600;color:#1e5b31}.t-auto ul{margin:8px 0;padding-left:18px}
.hm-hero{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;background:linear-gradient(120deg,#0b3d5c,#075e79 60%,#1f6f8b);color:#fff;border:0!important;border-radius:14px!important;padding:22px 26px!important}
.hm-hero h2{margin:0 0 4px;font-size:24px;color:#fff}.hm-hero p{margin:0;color:#cfe3ee!important}
.hm-go{display:flex;gap:10px;flex-wrap:wrap}.hm-btn{display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:10px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);color:#fff!important;text-decoration:none;font-weight:600;font-size:14px}
.hm-btn:hover{background:rgba(255,255,255,.22)}.hm-btn.primary{background:#fff;color:#0b3d5c!important;border-color:#fff}.hm-btn span{font-size:15px;opacity:.85}
.hm{display:grid;gap:14px;margin-top:14px}.hm-row{display:grid;gap:14px}.hm-3{grid-template-columns:repeat(3,minmax(0,1fr))}.hm-2{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr)}
.hm-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;min-width:0;display:flex;flex-direction:column;gap:8px}
.hm-card h3{margin:0;font-size:15px;display:flex;justify-content:space-between;align-items:baseline;gap:8px}.hm-card h3 a{font-size:12.5px;font-weight:600;color:var(--teal);text-decoration:none}
.hm-wait{display:grid;gap:6px}.hm-wait a{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 12px;border-radius:9px;border:1px solid var(--line);text-decoration:none;color:var(--ink);background:#fff}
.hm-wait a:hover{border-color:var(--teal)}.hm-wait a.warn{background:#fdf3e1;border-color:#e2bf85}.hm-wait a.bad{background:#fbeaea;border-color:#e0aaaa}
.hm-n{font-weight:700;font-variant-numeric:tabular-nums;background:var(--teal2);color:var(--teal);border-radius:999px;padding:0 9px;font-size:13px;line-height:22px}
.hm-clear{display:flex;gap:10px;align-items:center;color:#1e5b31;background:#eef8f1;border:1px solid #9fcfaf;border-radius:10px;padding:12px 14px;font-weight:600}
.hm-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.hm-tile{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:#fff;text-decoration:none;color:var(--ink);display:grid;gap:1px}
a.hm-tile:hover{border-color:var(--teal)}.hm-tile b{font-size:24px;line-height:1.15;font-variant-numeric:tabular-nums}.hm-tile span{font-size:12.5px;color:var(--muted)}.hm-tile.alert b{color:#b3261e}
.hm-meter{display:grid;gap:4px;font-size:12.5px;color:var(--muted)}.hm-bar{height:8px;border-radius:4px;background:#e6ecf1;overflow:hidden}.hm-bar>div{height:100%;background:#2a78d6;border-radius:4px}
.hm-bar.warn>div{background:#eda100}.hm-bar.bad>div{background:#d03b3b}
.hm-spark{display:flex;align-items:flex-end;gap:8px;padding-top:4px}.hm-spark>div{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;font-size:11px;color:var(--muted)}.hm-bw{height:64px;width:100%;display:flex;align-items:flex-end;justify-content:center}
.hm-spark i{display:block;width:100%;max-width:34px;background:#2a78d6;border-radius:4px 4px 0 0;min-height:2px}.hm-spark div:last-child i{background:#075e79}
.hm-list{display:grid;gap:2px;margin:0;padding:0;list-style:none}.hm-list a{display:flex;justify-content:space-between;gap:10px;padding:8px 10px;border-radius:8px;text-decoration:none;color:var(--ink)}
.hm-list a:hover{background:#f4f8fb}.hm-list li{min-width:0}.hm-list a{min-width:0;align-items:center}.hm-list .muted,.hm-list .hm-pill{font-size:12.5px;white-space:nowrap;flex:none}.hm-list b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1 1 auto;min-width:0}
.hm-empty{color:var(--muted);font-size:13px;margin:4px 0}
.hm-stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px}.hm-stat{text-decoration:none;color:var(--ink);border-left:3px solid var(--teal);padding:4px 10px}.hm-stat b{display:block;font-size:20px}.hm-stat span{font-size:12.5px;color:var(--muted)}
.hm-pill{font-size:11.5px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:#4b5a66;background:#f4f6f8;white-space:nowrap}.hm-pill.ok{background:#eef8f1;color:#1e5b31;border-color:#9fcfaf}.hm-pill.warn{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}
@media(max-width:1100px){.hm-3,.hm-2{grid-template-columns:1fr}}
@media(max-width:600px){.hm-tiles{grid-template-columns:1fr 1fr}}
.av-bar{padding:12px 18px!important}.av-bar .mem-tools{margin:0}.av-views{margin-left:auto;display:flex;gap:6px}.av-h{margin:0 0 10px;font-size:17px}
.av{--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--good:#0ca30c;--bad:#d03b3b;--open:#c9d3dc;--grid:#e6ecf1;display:grid;gap:14px;margin-bottom:14px}
.av-tiles{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.av-tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:grid;gap:2px;text-decoration:none;color:var(--ink)}
a.av-tile:hover{border-color:var(--teal)}.av-tile b{font-size:28px;line-height:1.1;font-variant-numeric:tabular-nums}.av-tile span{font-size:13px;color:var(--muted)}.av-tile em{font-style:normal;font-size:12px;color:var(--muted)}
.av-tile.alert b{color:#b3261e}.av-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;min-width:0}
.av-card h3{margin:0 0 2px;font-size:15px}.av-card .av-sub{margin:0 0 10px;font-size:12.5px;color:var(--muted)}
.av-two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px}
.av-legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--muted);margin:0 0 6px}.av-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.av svg{display:block;width:100%;height:auto;overflow:visible}.av svg text{font-family:inherit}
.av-tip{position:fixed;z-index:50;pointer-events:none;background:#14324a;color:#fff;border-radius:8px;padding:8px 10px;font-size:12.5px;line-height:1.45;box-shadow:0 4px 14px rgba(0,0,0,.18);max-width:260px}
.av-tip b{display:block;margin-bottom:2px}.av-tip i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}
.av-rows{display:grid;gap:12px}.av-row{display:grid;gap:4px}.av-row-head{display:flex;justify-content:space-between;gap:10px;font-size:13.5px}.av-row-head span{color:var(--muted);font-size:12.5px;text-align:right}
.av-seg{display:flex;height:12px;gap:2px;border-radius:4px;overflow:hidden;background:var(--grid)}.av-seg>div{height:100%;min-width:3px}
.av-bars{display:grid;gap:8px}.av-bars .av-b{display:grid;grid-template-columns:minmax(120px,38%) minmax(0,1fr) auto;gap:10px;align-items:center;font-size:13px}
.av-bars .av-track{height:12px;background:var(--grid);border-radius:4px;overflow:hidden;display:flex;gap:2px}.av-bars .av-track>div{height:100%;border-radius:0 4px 4px 0}
.av-bars .av-n{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12.5px;white-space:nowrap}
.av-empty{color:var(--muted);font-size:13px;margin:6px 0}
.av-key{display:flex;gap:14px;font-size:12px;color:var(--muted);margin-top:8px;flex-wrap:wrap}.av-key i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.av details{margin-top:8px;font-size:13px}.av details table{width:100%;border-collapse:collapse;margin-top:6px;font-size:12.5px}.av details th,.av details td{padding:3px 6px;border-bottom:1px solid var(--line);text-align:right}.av details th:first-child,.av details td:first-child{text-align:left}
@media(max-width:1000px){.av-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}.av-two{grid-template-columns:1fr}}
.dt-bar{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px}.dt-group{margin:12px 0;border:1px solid var(--line);border-radius:8px;background:#fff}.dt-head{cursor:pointer;padding:9px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.dt-out{margin-left:auto}.dt-note{margin:0 12px 6px}.dt-table{margin:0}.dt-table{table-layout:fixed;width:100%}.dt-table th:nth-child(1){width:32%}.dt-table th:nth-child(2){width:24%}.dt-table th:nth-child(3){width:17%}.dt-table th:nth-child(4){width:13%}.dt-sent{display:inline-block;background:#f1ebf7;color:#4b2f73;border:1px solid #c7b8dd;border-radius:999px;padding:1px 8px;margin:0 0 3px;font-size:11.5px}.dt-table td{vertical-align:top;overflow-wrap:anywhere}.dt-loc{font-size:12px;margin-top:3px;overflow-wrap:anywhere}.dt-loc code{font-size:11.5px;background:#f4f6f8;padding:1px 4px;border-radius:4px}
@media(max-width:700px){.dt-table,.dt-table tbody,.dt-table tr,.dt-table td{display:block;width:auto!important}.dt-table tr:first-child{display:none}.dt-table tr{padding:8px 12px;border-top:1px solid var(--line)}.dt-table td{padding:2px 0!important;border:0!important}.dt-out{margin-left:0}}
.ds-how{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 14px}.ds-how div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;display:grid;gap:4px}.ds-how span{font-size:13px;color:var(--muted)}
.ds-kind.ds-sharepoint{background:#e3f1f6;color:#064b63;border-color:#89b1bf}.ds-kind.ds-fabric{background:#e6f4ea;color:#1e5b31;border-color:#9fcfaf}.ds-kind.ds-power_platform{background:#ede7f6;color:#4b2f73;border-color:#c7b8dd}.ds-files{margin-top:12px}.ds-table td{vertical-align:top}
@media(max-width:800px){.ds-how{grid-template-columns:1fr}}
''' + __import__('proposal_ui').PE_CSS + r'''
.dt-loc .mini-act{margin-left:6px!important;padding:1px 8px!important}.dt-bar .chips{display:flex;flex-wrap:wrap;gap:6px}
.ag-events{max-height:320px;overflow:auto;background:#fff;border:1px solid var(--line);border-radius:6px;padding:8px 10px;line-height:1.7}
@media(max-width:900px){.ag-stats{grid-template-columns:1fr 1fr}.ag-facts{grid-template-columns:1fr}.ag-mini{grid-template-columns:1fr 1fr}}
.k-text{max-height:360px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;border:1px solid #c9d7e1;border-radius:6px;padding:10px;font-size:13px}
.badge.k-lab-general{background:#e6f4ea;color:#1e5b31;border-color:#9fcfaf}.badge.k-lab-internal{background:#e3f1f6;color:#064b63;border-color:#89b1bf}.badge.k-lab-client{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.badge.k-lab-local{background:#fbeaea;color:#7a1f1f;border-color:#e0aaaa}
#k-table td:nth-child(2){min-width:260px}
.tag.k-decision{background:#ede7f6;color:#4b2f73;border-color:#c7b8dd}.t-report>strong{display:block;margin-top:8px}
.imp-progress{margin:10px 0}.imp-progress[hidden]{display:none}.imp-bar{height:12px;background:#e3eaf0;border-radius:6px;overflow:hidden;margin-bottom:6px}.imp-bar span{display:block;height:100%;width:0;background:#075e79;transition:width .3s}
.act-count{display:inline-block;min-width:26px;padding:2px 9px;border-radius:999px;background:#075e79;color:#fff;font-size:14px;text-align:center;vertical-align:middle}
.act-sec.act-warn{border-left:4px solid #c08a1e}.act-sec.act-bad{border-left:4px solid #b3261e}
.act-row{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:10px 0;border-top:1px solid #d3dee6;flex-wrap:wrap}.act-text{flex:1 1 380px;min-width:0}.act-text strong{overflow-wrap:anywhere}
.act-buttons{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.mini-act{margin:0!important;padding:6px 12px!important;font-size:12px!important}
#al-custom[hidden]{display:none}#al-custom label{margin:0}.al-table td:nth-child(1){white-space:nowrap;width:1%}.al-table td:nth-child(2){white-space:nowrap;width:1%}.al-target{color:#314d62;overflow-wrap:anywhere}.al-table td:nth-child(4){overflow-wrap:anywhere;max-width:520px}
#pane-ask[hidden]{display:none}.ask-log{max-height:520px;overflow:auto;margin:10px 0}.ask-msg{padding:10px 12px;border-radius:8px;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}.ask-user{background:#eaf5f8;border-left:3px solid #21758b;margin-left:60px}.ask-temple{background:#f3eff9;border-left:3px solid #786095;margin-right:30px}.ask-looked{margin-top:6px;color:#4b6376}.ask-looked summary{cursor:pointer;font-size:12px}.ask-form textarea{width:100%}
/* Organisations: list on the left, one organisation at a time on the right */
.o-shell{display:grid;grid-template-columns:310px minmax(0,1fr);gap:16px;align-items:start}@media(max-width:1000px){.o-shell{grid-template-columns:1fr}}
.o-side{position:sticky;top:0;max-height:calc(100vh - 84px);overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;display:grid;gap:10px}
.o-side-head{display:flex;gap:8px}.o-side-head input{flex:1;min-width:0}.o-chips{display:flex;flex-wrap:wrap;gap:6px}.o-chips .chip{font-size:12px!important;padding:5px 10px!important}
.o-side-sel{display:grid;grid-template-columns:1fr 1fr;gap:6px}.o-side-sel select{min-width:0;font-size:13px;padding:5px 6px}
.o-side-foot{display:flex;justify-content:space-between;align-items:center;gap:8px}.o-demo-toggle{font-size:13px;display:flex;gap:6px;align-items:center;cursor:pointer;white-space:nowrap}
.o-group>summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:6px 4px;border-bottom:1px solid var(--line)}.o-group>summary::-webkit-details-marker{display:none}
.o-group>summary::before{content:'▸';margin-right:6px;transition:transform .15s}.o-group[open]>summary::before{transform:rotate(90deg)}.o-group>summary span:first-child{flex:1}
.o-item{all:unset;box-sizing:border-box;display:grid;gap:2px;width:100%;padding:7px 8px;border-radius:8px;cursor:pointer}.o-item:hover{background:#eef5f8}.o-item.on{background:var(--teal2);box-shadow:inset 3px 0 0 var(--teal)}
.content button.o-item{margin:0;font:inherit;color:var(--ink);text-align:left}.o-item:focus-visible{outline:2px solid var(--teal);outline-offset:1px}.o-item .o-name{font-weight:600;font-size:14px}.o-item .o-sub{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;font-size:12px;color:var(--muted)}
.o-flag{font-size:11px;font-weight:700;padding:0 6px;border-radius:999px;background:#fdf3e1;color:#6b4406}.o-flag.o-opp{background:#ede7f6;color:#4b2f73}.o-flag.cl{background:#e3f1f6;color:#064b63}
.o-main{display:grid;gap:12px;min-width:0}.o-empty{color:var(--muted)}
.o-head-top{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;align-items:flex-start}.o-head h2{margin:0}.o-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;font-size:13px;color:var(--muted);align-items:center}
.o-head-act{display:flex;flex-wrap:wrap;gap:8px}.o-head p:empty{display:none}
.o-sec{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:0 16px}.o-sec>summary{cursor:pointer;list-style:none;display:flex;gap:12px;align-items:baseline;padding:13px 0;font-weight:700;font-size:15.5px}
.o-sec>summary::-webkit-details-marker{display:none}.o-sec>summary::before{content:'▸';color:var(--muted);transition:transform .15s}.o-sec[open]>summary::before{transform:rotate(90deg)}
.o-sum{font-weight:400;font-size:13px;color:var(--muted)}.o-sec-body{padding:0 0 16px}.o-erase{margin-top:8px}
.o-fsec>summary{cursor:pointer;font-weight:700;margin:10px 0 4px;font-size:14.5px}.o-fsec>summary .o-sum{margin-left:8px}
.o-demo-bar{background:#fdf3e1;border:1px solid #e2bf85;color:#6b4406;border-radius:10px;padding:9px 14px;margin-bottom:12px;font-size:14px}
.o-mini{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--line);font-size:14px}
#o-tagging[hidden],#o-tagged-sec[hidden],#o-aliases-wrap[hidden]{display:none}
.as-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:12px}.as-card h3{margin:0 0 2px}
.as-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.as-tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:grid;gap:2px;text-decoration:none;color:inherit}
.as-tile span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.as-tile b{font-size:22px;font-variant-numeric:tabular-nums}
a.as-tile.warn{border-color:#e2bf85;background:#fdf8ee}a.as-tile.warn b{color:#8a5a0f}a.as-tile:hover{border-color:var(--teal)}
.as-bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 14px}.as-bar input[type=search]{flex:1 1 220px;min-width:0}
.as-chips{display:flex;gap:4px;background:#eef3f7;border:1px solid var(--line);border-radius:999px;padding:3px}
.as-chips button{border:0!important;background:transparent!important;border-radius:999px!important;padding:5px 12px!important;font-size:13px;font-weight:600;color:var(--muted)!important;box-shadow:none!important;margin:0!important}
.as-chips button.on{background:#fff!important;color:var(--ink)!important;box-shadow:0 1px 3px rgba(16,42,67,.18)!important}
.as-form label.r-check{display:flex;gap:8px;align-items:center}.as-foot .demo{font-size:12.5px;padding:4px 10px}.as-chips button i{font-style:normal;color:var(--faint);margin-left:4px;font-weight:600}
.as-group{margin:18px 0 8px;display:flex;gap:10px;align-items:baseline}.as-group h3{margin:0;font-size:15px}.as-group span{color:var(--muted);font-size:13px}
.as-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.as-c{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;display:grid;gap:10px;grid-template-rows:auto auto 1fr auto;align-content:start;box-shadow:0 1px 2px rgba(16,42,67,.04),0 6px 16px -12px rgba(16,42,67,.25);transition:border-color .12s,transform .12s}
.as-c:hover{border-color:#9db7c6;transform:translateY(-1px)}.as-c.editing{border-color:var(--teal);box-shadow:0 0 0 3px rgba(7,94,121,.12)}
.as-c.paused{opacity:.75}
.as-top{display:flex;gap:12px;align-items:center;min-width:0}.as-top>div{min-width:0}.as-top h4{margin:0;font-size:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.as-kind{font-size:12px;color:var(--muted)}
.as-logo{flex:none;display:grid;place-items:center;border-radius:12px;color:#fff;font-weight:700}
.as-logo svg{display:block}
.as-st{margin-left:auto;flex:none;font-size:12px;font-weight:600;display:flex;gap:5px;align-items:center;color:var(--ok)}.as-st::before{content:'';width:8px;height:8px;border-radius:50%;background:#55b987}
.as-st.off{color:#8a5a0f}.as-st.off::before{background:#e2a33b}
.as-desc{margin:0;font-size:13.5px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.9em}
.as-foot{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:10px;margin-top:2px}.as-foot .button-link{margin:0}.as-foot .sp{flex:1}
.as-ed{background:var(--panel);border:1px solid var(--teal);border-radius:14px;padding:18px 20px;margin:0 0 16px;box-shadow:0 0 0 3px rgba(7,94,121,.10)}
.as-ed .as-top h4{font-size:18px;white-space:normal}.as-ed .as-form{margin-top:12px}
table.as-tbl{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:14px}
.as-tbl th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:9px 12px;border-bottom:1px solid var(--line);background:#f7fafc}
.as-tbl td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:middle}.as-tbl tr:last-child td{border-bottom:0}.as-tbl tr:hover td{background:#fafcfd}
.as-tbl .nm{display:flex;gap:10px;align-items:center;min-width:0}.as-tbl .nm b{display:block}.as-tbl .acts{white-space:nowrap;text-align:right}.as-tbl .acts>*{margin-left:6px}
.as-empty{padding:30px;text-align:center;color:var(--muted);background:var(--panel);border:1px dashed var(--line2);border-radius:14px}
@media(max-width:700px){.as-tbl .hide-s{display:none}}
.as-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.as-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.as-btns{display:flex;gap:8px;align-items:center}.as-btns .button-link{margin:0}
.as-form{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;margin-top:14px;padding-top:14px;border-top:1px solid var(--line)}.as-form label{display:grid;gap:4px}.as-two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.k-review-row{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:4px 0 12px}.k-review-row input{width:80px}
.as-checks{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:4px}.as-checks label{display:flex!important;gap:6px;align-items:center}
/* Opportunity tracker: slides out from the right */
.opp-tab{position:fixed;right:0;top:132px;z-index:30;writing-mode:vertical-rl;transform:rotate(180deg);background:var(--teal)!important;color:#fff!important;border:none!important;border-radius:0 10px 10px 0!important;padding:14px 9px!important;font-weight:700;letter-spacing:.04em;box-shadow:-2px 2px 10px #0002}
.opp-tab .badge-count{position:absolute;top:auto;bottom:-9px;right:auto;left:50%;margin-left:-11px;writing-mode:horizontal-tb;transform:rotate(180deg);min-width:22px;text-align:center}
.opp-drawer{position:fixed;top:52px;right:0;bottom:0;width:min(620px,100vw);background:var(--bg);border-left:1px solid var(--line2);box-shadow:-8px 0 24px #0b162633;z-index:40;transform:translateX(105%);transition:transform .25s ease;overflow:auto;padding:16px 18px 40px}
.opp-drawer.open{transform:none}.opp-scrim{position:fixed;inset:52px 0 0 0;background:#0b162633;z-index:35}
.opp-head{display:flex;align-items:center;justify-content:space-between}.opp-head h2{margin:0}.opp-filters{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.opp{background:#fff;border:1px solid var(--line);border-left:4px solid var(--teal);border-radius:10px;padding:12px 14px;margin:10px 0}.opp.suggested{border-left-color:#b7791f}.opp.won{border-left-color:#1e7a5a}.opp.lost,.opp.dismissed{border-left-color:#a7b4bf;opacity:.8}
.opp h3{margin:0 0 4px;font-size:15.5px}.opp .opp-meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:6px}.opp p{margin:4px 0;font-size:14px}.opp .opp-ev{font-size:13px}.opp .opp-ev a{margin-right:10px;overflow-wrap:anywhere}
.opp .opp-act{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}.opp textarea{width:100%;min-height:52px;margin-top:6px}
#opp-news li{margin:6px 0;font-size:14px}#opp-news .muted{font-size:12.5px}.opp-sched-row{display:grid;grid-template-columns:1.4fr .9fr 1.6fr auto;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.o-opp-row{margin-top:10px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff}
/* Organisation research */
.o-research-new{background:#f4f9fb;border:1px solid #cfe2ea;border-radius:10px;padding:12px 14px;margin:12px 0}.o-research-new h3{margin:0 0 4px;font-size:15px}
.o-run{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:12px 0;background:#fff}.o-run summary{cursor:pointer;font-weight:600}
.o-run ol{margin:6px 0 0;padding-left:20px}.o-run li{margin:3px 0;font-size:14px;overflow-wrap:anywhere}.o-run .uncited{color:var(--muted)}
.src-link{overflow-wrap:anywhere}.o-busy::before{content:'';display:inline-block;width:12px;height:12px;margin-right:6px;border:2px solid #9db7c6;border-top-color:var(--teal);border-radius:50%;animation:ospin .8s linear infinite;vertical-align:-2px}@keyframes ospin{to{transform:rotate(360deg)}}
/* Rule packs */
.rp-live{font-size:12px;font-weight:700;color:#1e5b31;background:#e6f4ea;border:1px solid #9fcfaf;border-radius:999px;padding:2px 10px}.rp-live-note{margin:10px 0 0;padding:8px 12px;border-radius:8px;background:#e6f4ea;color:#1e5b31;font-size:13.5px}
.rpa{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;border:1px solid var(--line);border-left:4px solid #1e7a5a;border-radius:10px;padding:10px 14px;margin:8px 0;background:#fff}
.rpa .rpa-rules{flex-basis:100%;font-size:13px;color:var(--muted)}.r-svc{margin-top:10px}.r-svc summary{cursor:pointer;font-weight:600}.r-svc-row{display:flex;gap:12px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)}.r-svc-row span{flex:1}
.rp-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(320px,1fr);gap:16px;align-items:start}@media(max-width:1100px){.rp-grid{grid-template-columns:1fr}}
.rp-try{position:sticky;top:0;max-height:calc(100vh - 84px);overflow:auto;border-radius:12px}.rp-try section{margin-top:0}.rp-try textarea,.rp-try select{width:100%;margin:4px 0 8px}.rp-try textarea{resize:vertical;min-height:96px}
#rp-head .rp-meta{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin-top:8px}#rp-head .rp-basis{font-size:13px;color:var(--muted);margin:6px 0 0}
.rp-stat{font-size:13px;color:var(--muted)}.rp-stat strong{color:var(--ink);font-size:15px}
.rp-theme{margin:14px 0 8px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.rp-rule{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 14px;background:#fff;border:1px solid var(--line);border-left:4px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:8px;transition:opacity .15s}
.rp-rule.on{border-left-color:var(--teal)}.rp-rule:not(.on){opacity:.62;background:#f8fafb}
.rp-rule.fired{box-shadow:0 0 0 2px #9fd3c3;border-left-color:#1e7a5a}.rp-rule.fired-block{box-shadow:0 0 0 2px #e0aaaa;border-left-color:#a33}.rp-rule.would{box-shadow:0 0 0 2px #e2bf85 inset;opacity:.9}
.rp-rule .rp-top{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px}.rp-rule h3{margin:0;font-size:15px}.rp-rule p{margin:2px 0 0;font-size:14px}.rp-rule .rp-why{font-size:12.5px;color:var(--muted)}
.rp-kind{font-size:11.5px;padding:2px 8px;border-radius:999px;border:1px solid;white-space:nowrap}.rp-kind.enforced{background:#e3f1f6;color:#064b63;border-color:#89b1bf}.rp-kind.gate{background:#fdf3e1;color:#6b4406;border-color:#e2bf85}.rp-kind.guidance{background:#ede7f6;color:#4b2f73;border-color:#c7b8dd}.rp-kind.locked{background:#eef1f4;color:#4b5a66;border-color:#c1cbd3}
.rp-act{font-size:12px;color:var(--muted)}.rp-hit{font-size:12px;font-weight:600;padding:2px 8px;border-radius:5px;background:#e6f4ea;color:#1e5b31}.rp-hit.blockish{background:#fbeaea;color:#7a1f1f}.rp-hit.would{background:#fdf3e1;color:#6b4406}
.rp-switch{position:relative;display:inline-block;width:44px;height:24px;margin-top:2px;flex:none}.rp-switch input{opacity:0;width:0;height:0;position:absolute}
.rp-switch span{position:absolute;inset:0;background:#c3cfd8;border-radius:999px;cursor:pointer;transition:background .15s}.rp-switch span::after{content:'';position:absolute;left:3px;top:3px;width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 1px 2px #0003;transition:transform .15s}
.rp-switch input:checked+span{background:var(--teal)}.rp-switch input:checked+span::after{transform:translateX(20px)}.rp-switch input:focus-visible+span{outline:2px solid var(--teal);outline-offset:2px}.rp-switch input:disabled+span{cursor:default;background:#7fa9b8}
.rp-out{margin-top:14px;border-radius:10px;border:1px solid var(--line);overflow:hidden}.rp-banner{padding:12px 14px;font-weight:700;font-size:15px;display:flex;gap:10px;align-items:center}
.rp-banner.escalated{background:#ede7f6;color:#3e2468}.rp-banner.blocked{background:#fbeaea;color:#7a1f1f}.rp-banner.held{background:#fdf3e1;color:#6b4406}.rp-banner.redacted{background:#e3f1f6;color:#064b63}.rp-banner.allowed{background:#e6f4ea;color:#1e5b31}
.rp-body{padding:10px 14px 14px;background:#fff}.rp-body h4{margin:12px 0 4px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.rp-body ul{margin:0;padding-left:18px}.rp-body li{margin:3px 0;font-size:14px}
.rp-sent{white-space:pre-wrap;background:#f4f7fa;border:1px solid var(--line);border-radius:8px;padding:10px;font-size:13.5px;margin:0}.rp-sent mark{background:#ffe9a8;border-radius:3px;padding:0 2px}
.rp-off li{color:#6b4406}
'''

SCRIPT = r'''
const $=id=>document.getElementById(id);let recordOffset=null,activityOffset=0;
async function api(path,method='GET',body){const r=await fetch(path,{method,headers:{'Content-Type':'application/json','X-Admin-Token':'__TOKEN__',...(window.ALICE_DATASET==='demo'?{'X-Alice-Dataset':'demo'}:{})},...(body?{body:JSON.stringify(body)}:{})});if(!r.ok){let text=await r.text();try{text=JSON.parse(text).detail}catch{}throw Error(typeof text==='string'?text:'Request rejected; check the fields.')}return r.json()}
function el(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e}
async function run(fn){try{await fn()}catch(e){$('notice').textContent=e.message}}
async function files(){const data=await api('/files');$('file-list').replaceChildren();if(!data.length)$('file-list').textContent='No saved files.';for(const f of data){const box=el('div','', 'card');box.append(el('strong',f.name),el('p',f.summary));const b=el('button','View extracted text');b.onclick=()=>run(async()=>{$('extract').textContent='Loading…';const d=await api('/admin/api/files/'+f.id);$('extract').textContent=d.text});box.append(b);$('file-list').append(box)}}
async function records(more=false){const offset=more?recordOffset:0;if(offset===null)return;const d=await api('/admin/api/records?status='+$('record-status').value+'&query='+encodeURIComponent($('record-query').value)+'&offset='+offset);if(!more)$('record-list').replaceChildren();if(!d.total)$('record-list').textContent='No matching records.';for(const r of d.records){const c=el('div','','card');c.append(el('h3',r.title),el('strong',r.status.toUpperCase(),r.status),el('pre',r.content),el('p','Source (as supplied): '+r.source),el('p','Created '+r.created_at+(r.reviewed_at?' · Reviewed '+r.reviewed_at:''),'muted'));if(r.status==='proposed'){for(const decision of ['approved','rejected']){const b=el('button',decision==='approved'?'Approve memory':'Reject');b.onclick=()=>run(async()=>{const note=askReason(decision);if(note===null)return;b.disabled=true;try{await api('/admin/api/records/'+r.id+'/review','POST',{decision,note});$('notice').textContent='Record '+decision+'.';await records();await activity()}finally{b.disabled=false}});c.append(b)}}c.append(memoryControls(r));$('record-list').append(c)}recordOffset=d.next_offset;$('more-records').hidden=recordOffset===null}
async function activity(more=false){if(!$('activity-list'))return;if(!more){activityOffset=0;$('activity-list').replaceChildren()}const rows=await api('/admin/api/activity?offset='+activityOffset);for(const r of rows){const c=el('div','','card');c.append(el('strong',r.action),el('p',r.created_at+' · '+r.target),el('p','Rule: '+r.rule+' · '+r.detail));$('activity-list').append(c)}if(!rows.length&&!more)$('activity-list').textContent='No activity yet.';activityOffset+=rows.length;$('more-activity').hidden=rows.length<50}
if(PAGE==='memories'){
 const TABS=[['proposed','Awaiting approval'],['approved','Active'],['superseded','Superseded'],['retired','Retired'],['rejected','Rejected'],['all','All']];
 const LABEL={proposed:'Awaiting approval',approved:'Active',superseded:'Superseded',retired:'Retired',rejected:'Rejected'};
 const params=new URLSearchParams(location.search);
 const state={status:TABS.some(t=>t[0]===params.get('status'))?params.get('status'):'approved',kind:params.get('kind')==='decision'?'decision':'',category:'',query:(params.get('q')||'').slice(0,200),sort:'newest',offset:0,rows:[],open:new Set(),owner:params.get('owner')||''};
 const picked=new Set();let known=[],timer=null;
 const MODE={auto:'Auto-assign',suggest:'Suggest only',off:'Off'};
 function fillSelect(sel,value,blank='Uncategorised'){sel.replaceChildren();const o=document.createElement('option');o.value='';o.textContent=blank;sel.append(o);for(const k of known){const x=document.createElement('option');x.value=k;x.textContent=k;sel.append(x)}sel.value=known.includes(value)?value:'';}
 async function loadCategories(){const d=await api('/admin/api/categories');known=d.categories.map(c=>c.name);$('cat-mode').value=d.temple_mode;
  $('cat-summary').textContent=d.categories.length+' categor'+(d.categories.length===1?'y':'ies')+' · Temple: '+MODE[d.temple_mode];if(!d.categories.length)$('cat-panel').open=true;
  const rows=$('cat-rows');rows.replaceChildren();if(!d.categories.length)rows.append(el('p','No categories yet. Add a few below — for example Work, Home, Family, Finance, Hobbies, Preferences.','muted small'));
  for(const c of d.categories){const row=el('div','','cat-row');const view=el('div','','cat-view');view.append(el('span',c.name,'tag'),el('span',c.description||'No description — Temple will guess from the name.','muted small cat-desc'),el('span',c.active+' active','small cat-count'));
   const edit=el('button','Edit');edit.className='secondary';edit.type='button';const del=el('button','Delete');del.className='secondary';del.type='button';view.append(edit,del);row.append(view);
   edit.onclick=()=>{const f=el('div','','cat-edit-form');const n=document.createElement('input');n.value=c.name;n.maxLength=40;n.setAttribute('aria-label','Category name');const ds=document.createElement('input');ds.value=c.description;ds.maxLength=300;ds.placeholder='What belongs here?';ds.setAttribute('aria-label','Description');const save=el('button','Save');save.type='button';const cancel=el('button','Cancel');cancel.className='secondary';cancel.type='button';cancel.onclick=()=>run(loadCategories);save.onclick=()=>run(async()=>{await api('/admin/api/categories/'+encodeURIComponent(c.name),'PUT',{name:n.value,description:ds.value});$('notice').textContent='Category saved.';await loadCategories();await load()});f.append(n,ds,save,cancel);row.replaceChildren(f);n.focus()};
   del.onclick=()=>{const f=el('div','','cat-edit-form');f.append(el('span','Delete '+c.name+'. Move its '+c.total+' memories to:','small'));const to=document.createElement('select');fillSelect(to,'','Uncategorised');[...to.options].forEach(o=>{if(o.value===c.name)o.remove()});const go=el('button','Delete category');go.type='button';const cancel=el('button','Cancel');cancel.className='secondary';cancel.type='button';cancel.onclick=()=>run(loadCategories);go.onclick=()=>run(async()=>{const r=await api('/admin/api/categories/'+encodeURIComponent(c.name)+'?move_to='+encodeURIComponent(to.value),'DELETE');$('notice').textContent='Deleted '+r.deleted+'; '+r.moved+' memories moved to '+(r.to||'Uncategorised')+'.';await loadCategories();await load()});f.append(to,go,cancel);row.replaceChildren(f)};
   rows.append(row)}
  fillSelect($('bulk-cat'),$('bulk-cat').value);fillSelect($('proposal-category'),$('proposal-category').value);}
 const fmt=d=>d?new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}):'';
 function chip(text,active,count,onclick){const b=el('button',text+(count!==undefined?' ('+count+')':''),'chip'+(active?' on':''));b.type='button';b.setAttribute('aria-pressed',active);b.onclick=onclick;return b}
 function bulkBar(){$('mem-bulk').hidden=!picked.size;$('mem-selected').textContent=picked.size+' selected';const proposals=state.rows.filter(r=>picked.has(r.id)&&r.status==='proposed').length;$('bulk-approve').hidden=$('bulk-reject').hidden=!proposals;$('bulk-accept').hidden=!state.rows.some(r=>picked.has(r.id)&&r.suggestion);}
 function suggestionControls(r){const box=el('div','','suggest');box.append(el('span','Suggested: '+r.suggestion+(r.confidence!=null?' · '+Math.round(r.confidence*100)+'%':''),'small'));if(r.suggestion_reason)box.title=r.suggestion_reason;
  for(const [label,action] of [['✓','accept'],['✕','dismiss']]){const b=el('button',label,'mini');b.type='button';b.setAttribute('aria-label',(action==='accept'?'Accept':'Dismiss')+' suggested category '+r.suggestion+' for '+r.title);b.onclick=()=>run(async()=>{await api('/admin/api/memories/suggestions','POST',{ids:[r.id],action});await loadCategories();await load()});box.append(b)}return box}
 function categoryCell(r){const td=categoryCellInner(r);if(r.client){const c=el('span',r.client,'tag k-knowledge');c.style.marginLeft='6px';c.title='Client';td.prepend(c)}return td}
 function categoryCellInner(r){const td=document.createElement('td');if(r.category){const t=el('span',r.category,'tag');td.append(t);if(r.assigned_by==='temple'){const m=el('span','✦','temple-mark');m.title='Assigned by Temple'+(r.confidence!=null?' ('+Math.round(r.confidence*100)+'% confident)':'')+'. Choose a category yourself to override.';td.append(m)}}else td.append(el('span','—','muted'));if(r.suggestion)td.append(suggestionControls(r));return td}
 function detail(r){const box=el('div','','mem-detail');
  if(r.kind==='decision'&&r.decision){const d=r.decision,t=el('div','','t-report');t.append(el('div','Decision'+(d.decided_on?' · decided '+d.decided_on:''),'t-label'),el('div',d.decision,'t-body'));
   if(d.rationale){t.append(el('strong','Why'),el('div',d.rationale))}if(d.options&&d.options.length){t.append(el('strong','Options considered'));for(const o of d.options)t.append(el('div','• '+o))}
   if(d.revisit){t.append(el('strong','Revisit when'),el('div',d.revisit))}if(r.review_by)t.append(el('div','Revisit date: '+r.review_by,'small muted'));box.append(t)}
  else box.append(el('pre',r.content));box.append(el('p','Source (as supplied): '+r.source,'small'));
  const meta='Created '+fmt(r.created_at)+(r.reviewed_at?' · Reviewed '+fmt(r.reviewed_at):'')+(r.archive_reason?' · '+LABEL[r.status]+': '+r.archive_reason:'')+' · ID '+r.id.slice(0,8);box.append(el('p',meta,'muted small'));
  const cat=el('div','','cat-edit');const input=document.createElement('select');fillSelect(input,r.category);input.setAttribute('aria-label','Category for '+r.title);const save=el('button','Save category');save.className='secondary';save.type='button';save.onclick=()=>run(async()=>{await api('/admin/api/memories/category','POST',{ids:[r.id],category:input.value});$('notice').textContent='Category saved.';await load()});cat.append(el('span','Category','small'),input,save);if(r.assigned_by==='temple')cat.append(el('span','✦ set by Temple','small muted'));else if(r.assigned_by==='model')cat.append(el('span','suggested by the model when proposing','small muted'));box.append(cat);
  const rb=el('div','','cat-edit');const d=document.createElement('input');d.type='date';d.value=r.review_by||'';d.setAttribute('aria-label','Review-by date for '+r.title);const sv=el('button','Save date');sv.className='secondary';sv.type='button';sv.onclick=()=>run(async()=>{await api('/admin/api/memories/'+r.id+'/review-by','PUT',{date:d.value});$('notice').textContent=d.value?'Review-by date set.':'Review-by date cleared.';await load()});rb.append(el('span','Review by','small'),d,sv,el('span','For time-bound facts: models are told it may be out of date after this.','small muted'));box.append(rb);
  box.append(ownerEditor(r.owner,r.title,async v=>{await api('/admin/api/memories/owner','POST',{ids:[r.id],owner:v});await load()}));if(r.decided)box.append(el('p',decidedText(r.decided),'small'));
  if(r.status==='proposed'){const act=el('div','');for(const decision of ['approved','rejected']){const b=el('button',decision==='approved'?'Approve memory':'Reject');if(decision==='rejected')b.className='secondary';b.type='button';b.onclick=()=>run(async()=>{const note=askReason(decision);if(note===null)return;b.disabled=true;try{await api('/admin/api/records/'+r.id+'/review','POST',{decision,note});$('notice').textContent='Memory '+(decision==='approved'?'approved.':'rejected.');await load()}finally{b.disabled=false}});act.append(b)}box.append(act)}
  box.append(memoryControls(r));return box}
 function render(append){const t=$('mem-table');if(!append){t.replaceChildren();const head=document.createElement('thead'),hr=document.createElement('tr');const all=document.createElement('input');all.type='checkbox';all.setAttribute('aria-label','Select all shown');all.onchange=()=>{for(const r of state.rows)all.checked?picked.add(r.id):picked.delete(r.id);render()};all.checked=state.rows.length>0&&state.rows.every(r=>picked.has(r.id));const c0=document.createElement('th');c0.append(all);hr.append(c0);for(const h of ['Memory','Category','Status','Date']){const th=el('th',h);th.scope='col';hr.append(th)}head.append(hr);t.append(head)}
  const body=document.createElement('tbody');
  if(!state.rows.length){const tr=document.createElement('tr'),td=el('td',state.query||state.category?'No memories match these filters.':'Nothing here yet.','muted');td.colSpan=5;tr.append(td);body.append(tr)}
  for(const r of state.rows){const tr=document.createElement('tr');tr.className='mem-row'+(state.open.has(r.id)?' open':'');
   const c0=document.createElement('td');const cb=document.createElement('input');cb.type='checkbox';cb.checked=picked.has(r.id);cb.setAttribute('aria-label','Select '+r.title);cb.onchange=()=>{cb.checked?picked.add(r.id):picked.delete(r.id);bulkBar()};c0.append(cb);
   const c1=document.createElement('td');const title=el('button',r.title,'mem-title');title.type='button';title.setAttribute('aria-expanded',state.open.has(r.id));title.onclick=()=>{state.open.has(r.id)?state.open.delete(r.id):state.open.add(r.id);render()};c1.append(title,el('div',(r.kind==='decision'&&r.decision?r.decision.decision:r.content).replace(/\s+/g,' ').slice(0,160),'mem-preview'));if(r.kind==='decision'){const db=el('span','Decision','badge v-run');db.style.marginLeft='8px';title.after(db)}
   const c2=categoryCell(r);
   const c3=document.createElement('td');c3.append(el('span',LABEL[r.status]||r.status,'badge '+r.status));if(r.review_by&&r.review_by<new Date().toISOString().slice(0,10)){const due=el('div','Review due','flag');due.title='Review-by date '+r.review_by+' has passed.';due.style.marginTop='5px';c3.append(due)}if(r.owner)c3.append(el('div',r.owner,'small muted'));
   const c4=el('td',fmt(r.reviewed_at||r.created_at),'num');tr.append(c0,c1,c2,c3,c4);body.append(tr);
   if(state.open.has(r.id)){const dr=document.createElement('tr');dr.className='mem-detail-row';const td=document.createElement('td');td.colSpan=5;td.append(detail(r));dr.append(td);body.append(dr)}}
  t.append(body);bulkBar()}
 async function load(more=false){const offset=more?state.offset:0;
  const d=await api('/admin/api/memories?status='+state.status+'&query='+encodeURIComponent(state.query)+'&category='+encodeURIComponent(state.category)+'&sort='+state.sort+'&offset='+offset+'&kind='+state.kind+'&owner='+encodeURIComponent(state.owner));
  state.rows=more?state.rows.concat(d.records):d.records;state.offset=d.next_offset;fillOwners($('mem-owner'),d.owners,state.owner);
  const url=new URL(location.href);url.searchParams.set('status',state.status);history.replaceState(null,'',url);
  $('mem-kinds').replaceChildren(...[['','All types',undefined],['fact','Facts and preferences',undefined],['decision','Decisions',d.decisions]].map(([k,l,n])=>chip(l,state.kind===k,n,()=>{state.kind=k;picked.clear();run(()=>load())})));
  $('mem-tabs').replaceChildren(...TABS.map(([k,label])=>{const n=k==='all'?Object.values(d.statuses).reduce((a,b)=>a+b,0):(d.statuses[k]||0);const b=chip(label,state.status===k,n,()=>{state.status=k;state.category='';picked.clear();state.open.clear();run(()=>load())});b.setAttribute('role','tab');b.setAttribute('aria-selected',state.status===k);if(k==='proposed'&&n)b.classList.add('attention');return b}));
  const total=d.categories.reduce((a,c)=>a+c.count,0);const cats=[chip('All categories',!state.category,total,()=>{state.category='';run(()=>load())})];
  if(d.expired){const ex=chip('⚑ Past review date',state.category==='__expired__',d.expired,()=>{state.category='__expired__';run(()=>load())});ex.classList.add('attention');cats.push(ex)}
  if(d.suggested){const sg=chip('✦ Temple suggestions',state.category==='__suggested__',d.suggested,()=>{state.category='__suggested__';run(()=>load())});sg.classList.add('attention');cats.push(sg)}
  for(const c of d.categories)cats.push(chip(c.category||'Uncategorised',state.category===(c.category||'__none__'),c.count,()=>{state.category=c.category||'__none__';run(()=>load())}));
  $('mem-cats').replaceChildren(...cats);
  render();$('mem-count').textContent='Showing '+state.rows.length+' of '+d.total;$('mem-more').hidden=state.offset===null}
 records=()=>load();
 if(state.query)$('mem-query').value=state.query;
 $('mem-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{state.query=$('mem-query').value.trim();run(()=>load())},300)};
 $('mem-sort').onchange=()=>{state.sort=$('mem-sort').value;run(()=>load())};
 $('mem-owner').onchange=()=>{state.owner=$('mem-owner').value;picked.clear();run(()=>load())};
 $('bulk-owner-set').onclick=()=>run(async()=>{const r=await api('/admin/api/memories/owner','POST',{ids:[...picked],owner:$('bulk-owner').value.trim()});$('notice').textContent=r.updated+' memories: owner '+(r.owner||'removed')+'.';picked.clear();$('bulk-owner').value='';await load()});
 $('mem-more').onclick=()=>run(()=>load(true));
 $('bulk-clear').onclick=()=>{picked.clear();render()};
 for(const [id,decision] of [['bulk-approve','approved'],['bulk-reject','rejected']])$(id).onclick=()=>run(async()=>{const ids=[...picked];if(!confirm((decision==='approved'?'Approve':'Reject')+' the selected proposals? Items that are not awaiting approval are skipped.'))return;const note=askReason(decision);if(note===null)return;const r=await api('/admin/api/memories/review','POST',{ids,decision,note});$('notice').textContent=r.changed+' '+(decision==='approved'?'approved':'rejected')+(r.skipped?', '+r.skipped+' skipped (not awaiting approval)':'')+(r.blocked?', '+r.blocked+' blocked by rules: '+r.block_reasons.join(' '):'')+'.';picked.clear();await load()});
 $('bulk-set').onclick=()=>run(async()=>{const r=await api('/admin/api/memories/category','POST',{ids:[...picked],category:$('bulk-cat').value});$('notice').textContent=r.updated+' memories set to '+(r.category||'Uncategorised')+'.';picked.clear();await loadCategories();await load()});
 $('bulk-accept').onclick=()=>run(async()=>{const r=await api('/admin/api/memories/suggestions','POST',{ids:[...picked],action:'accept'});$('notice').textContent=r.done+' Temple suggestions accepted.';picked.clear();await loadCategories();await load()});
 $('cat-form').onsubmit=e=>{e.preventDefault();run(async()=>{const r=await api('/admin/api/categories','POST',{name:$('cat-name').value,description:$('cat-desc').value});e.target.reset();$('notice').textContent='Added '+r.name+'.';await loadCategories();await load()})};
 $('cat-mode').onchange=()=>run(async()=>{await api('/admin/api/categories-mode','PUT',{mode:$('cat-mode').value});await loadCategories()});
 $('cat-run').onclick=()=>run(async()=>{const b=$('cat-run');b.disabled=true;$('cat-run-result').textContent='Temple is reading your uncategorised memories…';try{const r=await api('/admin/api/categories/temple-run','POST',{});$('cat-run-result').textContent=r.status==='paused'?r.message:r.status==='no_categories'?'Add at least one category first.':r.status==='busy'?'Temple is already categorising. Try again in a moment.':'Checked '+r.checked+': '+r.applied+' assigned, '+r.suggested+' suggested'+(r.checked-r.applied-r.suggested>0?', '+(r.checked-r.applied-r.suggested)+' with no clear fit.':'.');await loadCategories();await load()}catch(e){$('cat-run-result').textContent=e.message}finally{b.disabled=false}});
 $('proposal').onsubmit=e=>{e.preventDefault();run(async()=>{await api('/admin/api/records','POST',{title:$('title').value,content:$('content').value,source:$('source').value,category:$('proposal-category').value});e.target.reset();state.status='proposed';state.query='';$('mem-query').value='';$('notice').textContent='Proposal submitted. It is shown under Awaiting approval.';await load()})};
 run(async()=>{await loadCategories();await load()});
}
if(PAGE==='rules'){
 let data=null,dirty=false;
 const PROV={openai:'GPT-6 Luna',claude:'Claude (all)',grok:'Grok',copilot:'Microsoft Copilot'};
 const fmtD=v=>'$'+Number(v).toFixed(2);
 function num(label,value,min,max,step){const l=el('label',label,'r-param');const i=document.createElement('input');i.type='number';i.value=value;i.min=min;i.max=max;i.step=step;l.append(i);return [l,i]}
 function saveBtn(fn,label='Save'){const b=el('button',label);b.type='button';b.className='secondary';b.onclick=()=>run(fn);return b}
 async function patch(id,body,msg){await api('/admin/api/rules/'+id,'PUT',body);$('notice').textContent=msg||'Rule saved.';await load()}
 function paramsEditor(r){const box=el('div','','r-params');const p=r.params;
  if(r.id==='spend_cap'){const [a,ai]=num('Daily cap (USD)',p.daily_usd,0.1,1000,0.5),[b,bi]=num('Monthly cap (USD)',p.monthly_usd,1,10000,1),[c,ci]=num('Warn and pause Temple at (%)',p.warn_percent,10,99,5);box.append(a,b,c,saveBtn(()=>patch(r.id,{params:{daily_usd:+ai.value,monthly_usd:+bi.value,warn_percent:+ci.value}})))}
  else if(r.id==='retention'){const [a,ai]=num('Delete after (months)',p.months,1,120,1);const go=saveBtn(async()=>{if(!confirm('Delete archived chats older than '+ai.value+' months that had nothing captured? This cannot be undone.'))return;const res=await api('/admin/api/rules/retention/run','POST',{});$('notice').textContent=res.status==='off'?'Switch the rule on first.':res.deleted+' chats deleted.'},'Run now');go.disabled=!r.enabled;box.append(a,saveBtn(()=>patch(r.id,{params:{months:+ai.value}})),go)}
  else if(r.id==='quality'){const [a,ai]=num('Minimum content length',p.min_chars,1,200,1);box.append(a,saveBtn(()=>patch(r.id,{params:{min_chars:+ai.value}})))}
  else if(r.id==='duplicates'){const [a,ai]=num('Similarity threshold (0.5–1)',p.threshold,0.5,1,0.05);box.append(a,saveBtn(()=>patch(r.id,{params:{threshold:+ai.value}})))}
  else if(r.id==='protective_marking'){const l=el('label','Markings (comma separated)','r-param wide');const i=document.createElement('input');i.value=p.markings.join(', ');l.append(i);box.append(l,saveBtn(()=>patch(r.id,{params:{markings:i.value.split(',')}})))}
  else if(r.id==='provider_allow'){const rows=Object.entries(p.blocked||{});const table=el('div','','r-grid');const draw=()=>{table.replaceChildren();for(const [idx,[cat,provs]] of rows.entries()){const row=el('div','','r-grid-row');const sel=document.createElement('select');sel.setAttribute('aria-label','Category');for(const c of data.categories.concat(data.categories.includes(cat)||!cat?[]:[cat])){const o=document.createElement('option');o.value=o.textContent=c;sel.append(o)}sel.value=cat;sel.onchange=()=>rows[idx][0]=sel.value;row.append(el('span','Never send','small'),sel,el('span','to','small'));for(const k of data.providers){const l=el('label','','r-check');const c=document.createElement('input');c.type='checkbox';c.checked=provs.includes(k);c.onchange=()=>{rows[idx][1]=c.checked?[...new Set(rows[idx][1].concat(k))]:rows[idx][1].filter(x=>x!==k)};l.append(c,document.createTextNode(' '+PROV[k]));row.append(l)}const del=el('button','Remove');del.type='button';del.className='mini';del.onclick=()=>{rows.splice(idx,1);draw()};row.append(del);table.append(row)}};draw();
   const labs=el('div','','r-grid');labs.append(el('p','Knowledge by security label','small'));const LBL={general:'General',internal:'Internal',client:'Client-confidential'};const lab=JSON.parse(JSON.stringify(p.labels||{internal:['grok']}));for(const k of Object.keys(LBL)){const row=el('div','','r-grid-row');row.append(el('span','Never send '+LBL[k]+' knowledge to','small'));for(const pv of data.providers){const l=el('label','','r-check');const c=document.createElement('input');c.type='checkbox';c.checked=(lab[k]||[]).includes(pv);c.onchange=()=>{lab[k]=c.checked?[...new Set((lab[k]||[]).concat(pv))]:(lab[k]||[]).filter(x=>x!==pv)};l.append(c,document.createTextNode(' '+PROV[pv]));row.append(l)}labs.append(row)}
   const add=el('button','Add category rule');add.type='button';add.className='secondary';add.disabled=!data.categories.length;add.onclick=()=>{rows.push([data.categories[0],['grok']]);draw()};box.append(table,add,labs,saveBtn(()=>patch(r.id,{params:{blocked:Object.fromEntries(rows),labels:lab}})));if(!data.categories.length)box.append(el('p','Create categories on the Memories page first.','muted small'))}
  else if(r.id==='client_separation'){const l1=el('label','','r-check');const st=document.createElement('input');st.type='checkbox';st.checked=!!p.strict;l1.append(st,document.createTextNode(' Strict: untagged chats see General material only'));const l2=el('label','Claude Desktop and Claude Code see','r-param');const ex=document.createElement('select');for(const [v,t] of [['all','All material'],['general','General material only']]){const o=document.createElement('option');o.value=v;o.textContent=t;ex.append(o)}ex.value=p.external||'all';l2.append(ex);box.append(l1,l2,saveBtn(()=>patch(r.id,{params:{strict:st.checked,external:ex.value}})));const a=document.createElement('a');a.href='/admin/clients';a.textContent='Manage clients and tags ↗';a.className='small';box.append(a)}
  else if(r.id==='external_scope'){const wrap=el('div','','r-checks');const chosen=new Set(p.allowed_categories);for(const c of data.categories){const l=el('label','','r-check');const i=document.createElement('input');i.type='checkbox';i.checked=chosen.has(c);i.onchange=()=>i.checked?chosen.add(c):chosen.delete(c);l.append(i,document.createTextNode(' '+c));wrap.append(l)}box.append(el('p',chosen.size?'Only ticked categories are readable by Claude Desktop and Claude Code.':'Nothing ticked: all categories are readable.','small'),wrap,saveBtn(()=>patch(r.id,{params:{allowed_categories:[...chosen]}})));if(!data.categories.length)box.append(el('p','Create categories on the Memories page first.','muted small'))}
  return box.childElementCount?box:null}
 function ruleRow(r){const row=el('div','','r-row'+(r.enabled?'':' off'));const top=el('div','','r-top');
  const tl=el('label','','r-toggle');const t=document.createElement('input');t.type='checkbox';t.checked=r.enabled;t.disabled=r.locked;t.setAttribute('aria-label',(r.enabled?'Switch off ':'Switch on ')+r.name);
  t.onchange=()=>run(async()=>{if(!t.checked&&r.set_key==='security'&&!confirm('Switch off the security rule “'+r.name+'”?')){t.checked=true;return}await patch(r.id,{enabled:t.checked},r.name+(t.checked?' switched on.':' switched off.'))});tl.append(t);
  top.append(tl,el('strong',r.name),el('span',r.kind==='enforced'?'Enforced':'Guidance','badge '+(r.kind==='enforced'?'v-ok':'v-run')));if(r.locked)top.append(el('span','Core · always on','badge v-none'));if(!r.builtin)top.append(el('span','Yours','badge v-none'));row.append(top);
  if(r.description)row.append(el('p',r.description,'small r-desc'));
  if(r.kind==='guidance'){const a=document.createElement('textarea');a.rows=2;a.maxLength=1000;a.value=r.text;a.setAttribute('aria-label','Guidance text for '+r.name);const bar=el('div','','r-params');bar.append(saveBtn(()=>patch(r.id,{text:a.value}),'Save text'));if(!r.builtin){const d=el('button','Delete');d.type='button';d.className='secondary';d.onclick=()=>run(async()=>{if(!confirm('Delete “'+r.name+'”?'))return;await api('/admin/api/rules/'+r.id,'DELETE');await load()});bar.append(d)}row.append(a,bar)}
  const ed=paramsEditor(r);if(ed)row.append(ed);return row}
 function addForm(set){const d=document.createElement('details');d.className='r-add';d.append(el('summary','Add a guidance rule to '+set.name));const n=document.createElement('input');n.maxLength=60;n.placeholder='Name';n.setAttribute('aria-label','Rule name');const tx=document.createElement('textarea');tx.rows=2;tx.maxLength=1000;tx.placeholder='Instruction for the model';tx.setAttribute('aria-label','Rule text');d.append(n,tx,saveBtn(async()=>{await api('/admin/api/rules/custom','POST',{set_key:set.key,name:n.value,text:tx.value});$('notice').textContent='Guidance rule added.';await load()},'Add rule'));return d}
 function spend(sp){const box=$('r-spend');box.replaceChildren();if(sp.level==='off'){box.append(el('p','Spending caps are off.','small'));return}
  for(const [label,v,cap] of [['Today',sp.today_usd,sp.daily_usd],['This month',sp.month_usd,sp.monthly_usd]]){const pct=Math.min(100,v/cap*100);const r=el('div','','spend-row');const bar=el('div','','spend-bar');const fill=el('span','','spend-fill '+(pct>=100?'bad':pct>=sp.warn_percent?'warn':'ok'));fill.style.width=pct+'%';bar.append(fill);r.append(el('span',label,'small'),bar,el('span',fmtD(v)+' of '+fmtD(cap),'small num'));box.append(r)}
  box.append(el('p',{ok:'Within limits.',warning:'Warning level reached: Temple automations are paused.',blocked:'Cap reached: chat and Temple are paused.'}[sp.level],'small spend-'+sp.level))}
 async function load(){data=await api('/admin/api/rules');$('r-counts').textContent=data.counts.enforced+' enforced · '+data.counts.guidance+' guidance rules on';spend(data.spend);
  if(!dirty){$('guidance').value=data.guidance;$('allow').checked=data.allow_proposals}$('r-effective').textContent=data.effective_guidance||'(no guidance)';
  const sets=$('r-sets');sets.replaceChildren();for(const set of data.sets){const sec=el('section','','r-set r-'+set.key);sec.append(el('h2',set.name),el('p',set.description,'muted small'));for(const r of data.rules.filter(x=>x.set_key===set.key))sec.append(ruleRow(r));sec.append(addForm(set));sets.append(sec)}
  $('r-requests-box').hidden=!data.requests.length;$('r-requests').replaceChildren(...data.requests.map(q=>{const row=el('div','','r-row');row.append(el('strong',q.title),el('p',q.content,'small'),el('p','From “'+q.chat_title+'” · '+q.status,'muted small'));const sel=document.createElement('select');sel.setAttribute('aria-label','Rule set');for(const st of data.sets){const o=document.createElement('option');o.value=st.key;o.textContent=st.name;sel.append(o)}sel.value='personal';const bar=el('div','','r-params');bar.append(sel,saveBtn(async()=>{await api('/admin/api/rules/custom','POST',{set_key:sel.value,name:q.title.slice(0,60),text:q.content.slice(0,1000),source:q.id});$('notice').textContent='Guidance rule created from Temple request.';await load()},'Create guidance rule'));row.append(bar);return row}));
  $('r-blocks').replaceChildren(...(data.blocks.length?data.blocks.map(b=>{const r=el('div','','r-block');r.append(el('span',new Date(b.created_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}),'small muted'),el('strong',(data.rules.find(x=>x.id===b.rule)||{name:b.rule}).name),el('span',b.detail,'small'));return r}):[el('p','Nothing blocked yet.','muted small')]))}
 $('rule-form').oninput=()=>dirty=true;window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
 $('rule-form').onsubmit=e=>{e.preventDefault();run(async()=>{await api('/admin/api/rules','PUT',{guidance:$('guidance').value,allow_proposals:$('allow').checked});dirty=false;$('notice').textContent='Saved. Guidance applies from the next message.';await load()})};
 run(load);
}
if(PAGE==='activity'){
 const st={type:'',offset:0,rows:[]};let timer=null;
 const BADGE={memories:'v-ok',knowledge:'v-ok',organisations:'v-ok',agents:'v-run',temple:'v-run',blocks:'v-bad',rules:'v-warn',clients:'v-none',chats:'v-none',routing:'v-none',tools:'v-none',other:'v-none'};
 const qs=()=>'type='+st.type+'&preset='+$('al-period').value+'&start='+$('al-from').value+'&end='+$('al-to').value+'&q='+encodeURIComponent($('al-q').value.trim());
 const when=d=>new Date(d).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
 function chip(text,active,fn,cls=''){const b=el('button',text,'chip'+(active?' on':'')+(cls?' '+cls:''));b.type='button';b.onclick=fn;return b}
 function render(){const t=$('al-table');t.replaceChildren();const h=document.createElement('thead'),hr=document.createElement('tr');for(const x of ['When','Type','What happened','Details']){const th=el('th',x);th.scope='col';hr.append(th)}h.append(hr);t.append(h);
  const b=document.createElement('tbody');if(!st.rows.length){const tr=document.createElement('tr'),td=el('td','Nothing in this period matches.','muted');td.colSpan=4;tr.append(td);b.append(tr)}
  for(const r of st.rows){const tr=document.createElement('tr');const c1=el('td',when(r.created_at),'num');c1.title=r.created_at;
   const c2=document.createElement('td');c2.append(el('span',r.type_name,'badge '+(BADGE[r.type]||'v-none')));
   const c3=document.createElement('td');c3.append(el('strong',r.label));if(r.target_name)c3.append(el('div',r.target_name,'small al-target'));
   const det=[r.rule_name&&!['human_review','human_control'].includes(r.rule)?r.rule_name:'',r.detail,r.note?'Reason: “'+r.note+'”':'',r.actor?'by '+r.actor:''].filter(Boolean).join(' · ');
   const c4=el('td',det.length>220?det.slice(0,220)+'…':det,'small');if(det.length>220)c4.title=det;
   tr.append(c1,c2,c3,c4);b.append(tr)}t.append(b)}
 async function load(more=false){const d=await api('/admin/api/activity-log?'+qs()+'&offset='+(more?st.offset:0));st.rows=more?st.rows.concat(d.rows):d.rows;st.offset=d.next_offset;
  $('al-types').replaceChildren(chip('Everything ('+d.total_all+')',!st.type,()=>{st.type='';run(()=>load())}),...d.types.filter(([k])=>d.counts[k]).map(([k,n])=>chip(n+' ('+d.counts[k]+')',st.type===k,()=>{st.type=k;run(()=>load())},k==='blocks'?'attention':'')));
  render();$('al-count').textContent='Showing '+st.rows.length+' of '+d.total;$('al-more').hidden=st.offset===null;$('al-csv').href='/admin/api/activity-log.csv?'+qs()}
 // ---- the picture: what is happening in Alice
 const SV='http://www.w3.org/2000/svg';const S=(t,a,x)=>{const e=document.createElementNS(SV,t);for(const [k,v] of Object.entries(a||{}))e.setAttribute(k,v);if(x!=null)e.textContent=x;return e};
 const COL={knowledge:'var(--s1)',work:'var(--s2)',temple:'var(--s3)',orgs:'var(--s4)',settings:'var(--s5)'};
 const fmt=n=>Number(n||0).toLocaleString('en-GB');const usd=v=>'$'+(v>=1?v.toFixed(2):v.toFixed(v?3:2));
 let tip=null;function showTip(e,html){if(!tip){tip=el('div','','av-tip');document.body.append(tip)}tip.innerHTML=html;tip.hidden=false;const r=tip.getBoundingClientRect();let x=e.clientX+14,y=e.clientY+14;if(x+r.width>innerWidth-8)x=e.clientX-r.width-14;if(y+r.height>innerHeight-8)y=e.clientY-r.height-14;tip.style.left=x+'px';tip.style.top=y+'px'}
 function hideTip(){if(tip)tip.hidden=true}
 const esc=t=>String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 function card(title,sub){const c=el('section','','av-card');c.append(el('h3',title));if(sub)c.append(el('p',sub,'av-sub'));return c}
 function tiles(d){const t=d.totals,box=el('div','','av-tiles');
  const add=(n,label,extra,href,alert)=>{const x=el(href?'a':'div','','av-tile'+(alert?' alert':''));if(href)x.href=href;x.append(el('b',n),el('span',label));if(extra)x.append(el('em',extra));box.append(x)};
  add(fmt(t.events),'things recorded','every change, review and block');
  add(t.pending==null?'—':fmt(t.pending),'waiting for you','open Actions →','/admin/actions',t.pending>0);
  add(fmt(t.blocked),'stopped by the rules',t.blocked?'see what was blocked below':'nothing blocked',null,t.blocked>0);
  add(fmt(t.runs),'agent runs',t.failed_runs?t.failed_runs+' failed':'none failed','/admin/agents',t.failed_runs>0);
  add(fmt(t.model_calls),'AI calls',usd(t.cost_usd)+' estimated','/admin/usage');return box}
 function timeline(d){const c=card('Activity over time','What happened in Alice, by area. Blocks are counted separately, under Stopped by the rules.');
  const lg=el('div','','av-legend');for(const g of d.groups){const s=el('span');s.append(Object.assign(el('i'),{style:'background:'+COL[g.key]}),document.createTextNode(g.name));lg.append(s)}c.append(lg);
  const B=d.buckets,W=Math.max(300,Math.min(1200,($('av').clientWidth||900)-40)),H=W<500?200:230,L=36,R=8,T=8,Bm=26,n=Math.max(B.length,1),cw=(W-L-R)/n,bw=Math.max(2,Math.min(28,cw-4));
  const tot=B.map(b=>d.groups.reduce((a,g)=>a+b[g.key],0)),max=Math.max(1,...tot);const nice=m=>{const p=Math.pow(10,Math.floor(Math.log10(m))),f=m/p;return (f<=1?1:f<=2?2:f<=5?5:10)*p};const top=nice(max);
  const svg=S('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':'Activity over time, stacked by area'});
  for(let i=0;i<=4;i++){const v=top*i/4,y=T+(H-T-Bm)*(1-i/4);svg.append(S('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:i?'var(--grid)':'#b9cbd8','stroke-width':1}),S('text',{x:L-6,y:y+4,'text-anchor':'end','font-size':11,fill:'#5d7385'},fmt(Math.round(v))))}
  const every=Math.ceil(n/(W/70));
  B.forEach((b,i)=>{const x=L+i*cw+(cw-bw)/2;let y=H-Bm;const g=S('g');
   d.groups.forEach((gr,gi)=>{const v=b[gr.key];if(!v)return;const h=(H-T-Bm)*v/top;const top_=gi===d.groups.map(x=>b[x.key]>0).lastIndexOf(true);
    g.append(S('rect',{x,y:y-h+(gi?0:0),width:bw,height:Math.max(h-(y<H-Bm?2:0),1),fill:COL[gr.key],rx:top_?Math.min(4,bw/3):0}));y-=h});
   const hit=S('rect',{x:L+i*cw,y:T,width:cw,height:H-T-Bm,fill:'transparent'});
   hit.onmousemove=e=>showTip(e,'<b>'+esc(b.label)+' · '+fmt(tot[i])+' things</b>'+d.groups.filter(gr=>b[gr.key]).map(gr=>'<i style="background:'+COL[gr.key]+'"></i>'+esc(gr.name)+': '+fmt(b[gr.key])).join('<br>')+(b.blocks?'<br>Blocked by the rules: '+fmt(b.blocks):'')+(tot[i]?'':'Nothing happened'));hit.onmouseleave=hideTip;
   g.append(hit);svg.append(g);if(i%every===0)svg.append(S('text',{x:L+i*cw+cw/2,y:H-8,'text-anchor':'middle','font-size':11,fill:'#5d7385'},b.label))});
  c.append(svg);
  const det=document.createElement('details');det.append(el('summary','Show the numbers'));const tb=document.createElement('table');const hr=document.createElement('tr');for(const x of [d.unit==='hour'?'Hour':'Period',...d.groups.map(g=>g.name),'Blocked'])hr.append(el('th',x));tb.append(hr);
  for(const b of B){if(!d.groups.some(g=>b[g.key])&&!b.blocks)continue;const tr=document.createElement('tr');tr.append(el('td',b.label),...d.groups.map(g=>el('td',fmt(b[g.key]))),el('td',fmt(b.blocks)));tb.append(tr)}det.append(tb);c.append(det);return c}
 function bars(c,items,opts){if(!items.length){c.append(el('p',opts.empty,'av-empty'));return}const box=el('div','','av-bars');const max=Math.max(1,...items.map(opts.total));
  for(const it of items){const row=el('div','','av-b');const tr=el('div','','av-track');
   for(const [v,col,name] of opts.parts(it)){if(!v)continue;const seg=el('div');seg.style.width=(100*v/max)+'%';seg.style.background=col;tr.append(seg)}
   row.append(el('span',it.name),tr,el('span',opts.label(it),'av-n'));row.onmousemove=e=>showTip(e,opts.tip(it));row.onmouseleave=hideTip;box.append(row)}c.append(box);if(opts.key)c.append(opts.key)}
 function key(pairs){const k=el('div','','av-key');for(const [col,name] of pairs){const s=el('span');s.append(Object.assign(el('i'),{style:'background:'+col}),document.createTextNode(name));k.append(s)}return k}
 function gate(d){const c=card('The approval gate','What models, Temple and connected apps proposed, and what you decided. Nothing becomes approved without you.');const rows=el('div','','av-rows');
  const any=d.gate.some(g=>g.proposed||g.approved||g.rejected);if(!any){c.append(el('p','Nothing was proposed or decided in this period.','av-empty'));return c}
  for(const g of d.gate){const open=Math.max(0,g.proposed-g.approved-g.rejected),tot=Math.max(1,g.approved+g.rejected+open);const r=el('div','','av-row');const h=el('div','','av-row-head');
   h.append(el('strong',g.name),el('span',fmt(g.proposed)+' proposed · '+fmt(g.approved)+' approved · '+fmt(g.rejected)+' rejected'+(open?' · '+fmt(open)+' still open':'')));
   const seg=el('div','','av-seg');for(const [v,col,name] of [[g.approved,'var(--good)','approved'],[g.rejected,'var(--bad)','rejected'],[open,'var(--open)','still open']]){if(!v)continue;const x=el('div');x.style.flex=v+' 0 0';x.style.background=col;x.onmousemove=e=>showTip(e,'<b>'+esc(g.name)+'</b>'+fmt(v)+' '+name);x.onmouseleave=hideTip;seg.append(x)}
   if(!g.approved&&!g.rejected&&!open)seg.append(el('div'));r.append(h,seg);rows.append(r)}
  c.append(rows,key([['var(--good)','✓ Approved by you'],['var(--bad)','✕ Rejected by you'],['var(--open)','Still open (proposed in this period, not yet decided)']]));return c}
 function blocks(d){const c=card('Stopped by the rules','Every time a rule blocked something or sent it to a person, by rule.');
  bars(c,d.blocks,{empty:'Nothing was blocked in this period.',total:x=>x.n,parts:x=>[[x.n,'var(--bad)']],label:x=>fmt(x.n),tip:x=>'<b>'+esc(x.name)+'</b>'+fmt(x.n)+' blocked or escalated'});return c}
 function agentsCard(d){const c=card('Agents at work','Runs per agent in this period; failed and rule-blocked runs shown separately.');
  bars(c,d.agents.map(a=>({...a,ok:a.runs-a.failed-a.blocked})),{empty:'No agent ran in this period.',total:x=>x.runs,parts:x=>[[x.ok,'var(--s3)'],[x.blocked,'var(--s4)'],[x.failed,'var(--bad)']],
   label:x=>fmt(x.runs)+' run'+(x.runs===1?'':'s')+(x.cost&&!DEMO?' · '+usd(x.cost):''),tip:x=>'<b>'+esc(x.name)+'</b>'+fmt(x.ok)+' completed'+(x.blocked?'<br>'+fmt(x.blocked)+' stopped by a rule':'')+(x.failed?'<br>'+fmt(x.failed)+' failed':'')+(x.calls?'<br>'+fmt(x.calls)+' AI calls':'')+(x.cost&&!DEMO?'<br>'+usd(x.cost)+' estimated':''),
   key:key([['var(--s3)','Completed'],['var(--s4)','Stopped by a rule'],['var(--bad)','✕ Failed']])});return c}
 function modelsCard(d){const c=card('AI models used','Calls to each model in this period, from chat, Temple, agents and assistants.');
  bars(c,d.models,{empty:'No AI calls in this period.',total:x=>x.calls,parts:x=>[[x.calls,'var(--s1)']],label:x=>fmt(x.calls)+(DEMO?'':' · '+usd(x.cost)),tip:x=>'<b>'+esc(x.name)+'</b>'+fmt(x.calls)+' calls'+(DEMO?'':'<br>'+usd(x.cost)+' estimated')});return c}
 function heat(d){const c=card('When things happen','Activity by day of the week and hour, in your local time.');const W=Math.max(300,Math.min(520,(($('av').clientWidth||900)>1000?($('av').clientWidth-14)/2:$('av').clientWidth)-40)),cell=(W-44)/24,ch=24,H=7*ch+26;
  const svg=S('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':'Activity by weekday and hour'});const max=Math.max(1,...d.heat.flat());
  const RAMP=['#cde2fb','#9ec5f4','#6da7ec','#3987e5','#256abf','#184f95','#0d366b'];const col=v=>v?RAMP[Math.min(RAMP.length-1,Math.floor((v/max)*(RAMP.length-0.001)))]:'#f0f3f6';
  d.heat.forEach((row,w)=>{svg.append(S('text',{x:34,y:w*ch+ch/2+4,'text-anchor':'end','font-size':11,fill:'#5d7385'},d.weekdays[w]));
   row.forEach((v,h)=>{const r=S('rect',{x:44+h*cell+1,y:w*ch+1,width:cell-2,height:ch-2,rx:3,fill:col(v)});r.onmousemove=e=>showTip(e,'<b>'+d.weekdays[w]+' '+String(h).padStart(2,'0')+':00</b>'+fmt(v)+' thing'+(v===1?'':'s'));r.onmouseleave=hideTip;svg.append(r)})});
  for(let h=0;h<24;h+=6)svg.append(S('text',{x:44+h*cell+cell/2,y:7*ch+16,'text-anchor':'middle','font-size':11,fill:'#5d7385'},String(h).padStart(2,'0')+':00'));
  c.append(svg,key([['#f0f3f6','Nothing'],[RAMP[1],'Some'],[RAMP[3],'More'],[RAMP[6],'Busiest ('+fmt(max)+')']]));return c}
 function topCard(d){const c=card('Most frequent','The things that happened most often.');bars(c,d.top.map(x=>({name:x.label,n:x.n})),{empty:'Nothing yet.',total:x=>x.n,parts:x=>[[x.n,'var(--s1)']],label:x=>fmt(x.n),tip:x=>'<b>'+esc(x.name)+'</b>'+fmt(x.n)+' times'});return c}
 let lastD=null,lastW=0,rz=null;
 window.addEventListener('resize',()=>{clearTimeout(rz);rz=setTimeout(()=>{if(lastD&&Math.abs(($('av').clientWidth||0)-lastW)>40)draw(lastD)},200)});
 async function viz(){const p=$('al-period').value;const d=await api('/admin/api/activity-overview?preset='+p+'&start='+$('al-from').value+'&end='+$('al-to').value+'&tz='+new Date().getTimezoneOffset());draw(d)}
 function draw(d){lastD=d;lastW=$('av').clientWidth;hideTip();
  const r1=el('div','','av-two'),r2=el('div','','av-two'),r3=el('div','','av-two');r1.append(gate(d),blocks(d));r2.append(agentsCard(d),modelsCard(d));r3.append(heat(d),topCard(d));
  $('av').replaceChildren(tiles(d),timeline(d),r1,r2,r3)}
 let view=(()=>{try{return localStorage.getItem('alice-activity-view')||'both'}catch{return 'both'}})();
 function views(){$('av-views').replaceChildren(...[['both','Picture and log'],['picture','Picture'],['log','Log']].map(([k,l])=>chip(l,view===k,()=>{view=k;try{localStorage.setItem('alice-activity-view',k)}catch{}views()})));$('av').hidden=view==='log';$('al-log').hidden=view==='picture'}
 views();
 const reload=()=>{run(()=>load());run(viz)};
 $('al-period').onchange=()=>{$('al-custom').hidden=$('al-period').value!=='custom';if($('al-period').value!=='custom')reload()};
 for(const id of ['al-from','al-to'])$(id).onchange=reload;
 $('al-q').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>run(()=>load()),300)};
 $('al-more').onclick=()=>run(()=>load(true));
 const p=new URLSearchParams(location.search);if(p.get('type'))st.type=p.get('type');
 run(()=>load());run(viz);
}
'''

SCRIPT += r"""
if(PAGE==='knowledge'){
 const KQ=new URLSearchParams(location.search);
 const st={status:['active','draft','rejected','archived','replaced','all'].includes(KQ.get('status'))?KQ.get('status'):'active',kind:'',label:'',category:KQ.get('category')||'',client:'',owner:KQ.get('owner')||'',query:(KQ.get('q')||'').slice(0,200),offset:0,rows:[],open:new Set(),picked:new Set(),cache:{}};let D=null,timer=null;
 const KL={general:'General',internal:'Internal',client:'Client-confidential',local:'Local only'};
 const KIND={file:'File',note:'Note',meeting:'Meeting'};const STAT=[['active','Active'],['draft','Drafts'],['archived','Archived'],['replaced','Replaced'],['rejected','Rejected']];
 const WHO=p=>p.source==='temple'?'Temple':'The proposer';
 function repBox(r){const box=el('div','','t-report');
  if(r.replaced_by){box.append(el('strong','Replaced by “'+r.replaced_by.title+'”'+(r.superseded_at?' on '+fmt(r.superseded_at):'')));if(r.supersede_reason)box.append(el('div',r.supersede_reason,'small'));box.append(el('div','Models are pointed to the newer item. Restore undoes the replacement.','muted small'))}
  if(r.replaces&&r.replaces.length)box.append(el('div','Replaces: '+r.replaces.map(x=>'“'+x.title+'”').join(', '),'small'));
  for(const p of r.replacement_suggestions||[]){const mine=p.new_id===r.id;const row=el('div','','suggest');
   row.append(el('span',(mine?'May replace “'+p.old_title+'”':'May be replaced by “'+p.new_title+'”')+' · '+WHO(p)+(p.reason?': '+p.reason:''),'small'));
   if(p.new_status==='active'){for(const [lab,action] of [['Retire older','accept'],['Keep both','dismiss']]){const x=el('button',lab,'mini');x.type='button';x.onclick=()=>run(async()=>{await api('/admin/api/knowledge/replacements','POST',{ids:[p.id],action});$('notice').textContent=action==='accept'?'Retired “'+p.old_title+'”; it now points to “'+p.new_title+'”.':'Kept both.';await load()});row.append(x)}}
   else row.append(el('span','(decide when you approve the draft)','muted small'));
   box.append(row);if(p.quote)box.append(el('div','“'+p.quote+'”','small muted'))}
  if(r.status==='active'){const mk=el('button','Mark as replaced by…');mk.type='button';mk.className='secondary';const form=el('div','');
   mk.onclick=()=>run(async()=>{let off=0,all=[];do{const d=await api('/admin/api/knowledge?status=active&offset='+off);all.push(...d.items);off=d.next_offset}while(off!==null);all=all.filter(x=>x.id!==r.id);
    const sel=document.createElement('select');sel.setAttribute('aria-label','Newer item');const o0=document.createElement('option');o0.value='';o0.textContent='Choose the newer item…';sel.append(o0);for(const x of all){const o=document.createElement('option');o.value=x.id;o.textContent=x.title+' · '+fmt(x.created_at);sel.append(o)}
    const why=document.createElement('input');why.maxLength=500;why.placeholder='Why (e.g. newer version of the same summary)';why.setAttribute('aria-label','Reason');
    const go=el('button','Retire this item');go.type='button';go.onclick=()=>run(async()=>{if(!sel.value||!why.value.trim())throw Error('Choose the newer item and give a reason.');await api('/admin/api/knowledge/supersede','POST',{old_id:r.id,new_id:sel.value,reason:why.value});$('notice').textContent='Retired “'+r.title+'”.';await load()});
    form.replaceChildren(sel,why,go)});box.append(mk,form)}
  const hb=el('button','Version history');hb.type='button';hb.className='secondary';const hist=el('div','');hb.onclick=()=>run(async()=>{const h=await api('/admin/api/knowledge/'+r.id+'/history');hist.replaceChildren(...(h.items.length>1?h.items.map(x=>el('div',fmt(x.created_at)+' · '+x.title+' · '+(x.superseded_by?'replaced'+(x.superseded_at?' '+fmt(x.superseded_at):''):x.status)+(x.id===r.id?' (this item)':''),'small')):[el('div','No other versions linked.','muted small')]))});box.append(hb,hist);
  return box}
 const fmt=d=>d?new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}):'';
 function opts(sel,list,value,blank){sel.replaceChildren();if(blank!==undefined){const o=document.createElement('option');o.value='';o.textContent=blank;sel.append(o)}for(const [v,t] of list){const o=document.createElement('option');o.value=v;o.textContent=t;sel.append(o)}sel.value=value||''}
 const catList=()=>D.categories.map(c=>[c,c]),cliList=()=>D.clients.map(c=>[c,c]),labList=()=>Object.keys(KL).map(k=>[k,KL[k]]);
 function chip(text,active,onclick,cls=''){const b=el('button',text,'chip'+(active?' on':'')+(cls?' '+cls:''));b.type='button';b.onclick=onclick;return b}
 async function detail(r){const box=el('div','','mem-detail');
  const ed=el('div','','k-meta-row');const ti=document.createElement('input');ti.value=r.title;ti.maxLength=200;ti.setAttribute('aria-label','Title');const cs=document.createElement('select');opts(cs,catList(),r.category,'Uncategorised');const cl=document.createElement('select');opts(cl,cliList(),r.client,'General (no client)');const lb=document.createElement('select');opts(lb,labList(),r.label);const rb=document.createElement('input');rb.type='date';rb.value=r.review_by||'';
  for(const [lab,node] of [['Title',ti],['Category',cs],['Client',cl],['Security label',lb],['Review by',rb]]){const l=el('label',lab);l.append(node);ed.append(l)}
  const save=el('button','Save details');save.type='button';save.className='secondary';save.onclick=()=>run(async()=>{await api('/admin/api/knowledge','PUT',{ids:[r.id],title:ti.value,category:cs.value,label:lb.value,review_by:rb.value});if(cl.value!==r.client)await api('/admin/api/clients/tag','POST',{type:'file',ids:[r.id],client:cl.value});$('notice').textContent='Saved.';st.cache={};await load()});
  box.append(ed,save);
  box.append(ownerEditor(r.owner,r.title,async v=>{await api('/admin/api/knowledge','PUT',{ids:[r.id],owner:v});await load()}));
  if(r.purview_label)box.append(el('p','Purview sensitivity label on the original file: '+r.purview_label+'. Alice applied the mapping on the Rules page; it never changes the label itself.','small'));
  if(r.decided)box.append(el('p',decidedText(r.decided),'small'));
  box.append(el('p','Source: '+r.source+' · added by '+r.added_by+' · '+fmt(r.created_at)+(r.category_by==='temple'?' · category set by Temple':''),'muted small'));
  if(r.kind==='meeting'&&r.meeting&&(r.meeting.decisions||r.meeting.actions)){const mt=el('div','','t-report');if(r.meeting.date)mt.append(el('div','Meeting · '+r.meeting.date+(r.meeting.attendees&&r.meeting.attendees.length?' · '+r.meeting.attendees.join(', '):''),'t-label'));
   if(r.meeting.decisions&&r.meeting.decisions.length){mt.append(el('strong','Decisions'));for(const d of r.meeting.decisions)mt.append(el('div','• '+d))}
   if(r.meeting.decisions&&r.meeting.decisions.length){const pd=el('button','Propose these decisions');pd.type='button';pd.className='secondary';pd.onclick=()=>run(async()=>{const x=await api('/admin/api/knowledge/'+r.id+'/decisions','POST',{});$('notice').textContent=x.proposed+' decision'+(x.proposed===1?'':'s')+' proposed — approve them in Memories (Decisions).'+(x.notes.length?' '+x.notes.join(' '):'')});mt.append(pd)}
   if(r.meeting.actions&&r.meeting.actions.length){mt.append(el('strong','Actions'));for(const a of r.meeting.actions)mt.append(el('div','• '+a.action+(a.owner?' — '+a.owner:'')+(a.due?' (due '+a.due+')':'')))}box.append(mt)}
  box.append(repBox(r));
  const view=el('pre','Loading…','k-text');box.append(view);
  try{const f=st.cache[r.id]||(st.cache[r.id]=await api('/admin/api/files/'+r.id));view.textContent=f.text.length>12000?f.text.slice(0,12000)+'\n… (first 12,000 characters shown)':f.text}catch(e){view.textContent=e.message}
  const act=el('div','','arc-actions');
  const named=(r.replacement_suggestions||[]).filter(p=>p.new_id===r.id&&p.source==='proposer');
  if(r.status==='draft'&&named.length){const b=el('button','Approve and retire '+(named.length===1?'“'+named[0].old_title+'”':named.length+' older items'));b.type='button';b.onclick=()=>run(async()=>{const x=await api('/admin/api/knowledge/review','POST',{ids:[r.id],decision:'approved',retire_replaced:true});$('notice').textContent=x.blocked?x.block_reasons.join(' '):'“'+r.title+'” approved; '+x.retired+' older item'+(x.retired===1?'':'s')+' retired.';await load()});act.append(b)}
  if(r.status==='draft')for(const [label,decision] of [[named.length?'Approve only':'Approve','approved'],['Reject','rejected']]){const b=el('button',label);if(decision==='rejected'||named.length)b.className='secondary';b.type='button';b.onclick=()=>run(async()=>{const note=askReason(decision);if(note===null)return;const x=await api('/admin/api/knowledge/review','POST',{ids:[r.id],decision,note});$('notice').textContent=x.blocked?x.block_reasons.join(' '):'“'+r.title+'” '+decision+'.';await load()});act.append(b)}
  if(r.status==='active'||r.status==='archived'){const b=el('button',r.status==='active'?'Archive':(r.replaced_by?'Restore (undo replacement)':'Restore'));b.type='button';b.className='secondary';b.onclick=()=>run(async()=>{await api('/admin/api/knowledge','PUT',{ids:[r.id],status:r.status==='active'?'archived':'active'});await load()});act.append(b)}
  if(r.kind!=='file'){const wd=document.createElement('a');wd.href='/admin/api/knowledge/'+r.id+'/docx';wd.textContent='Download as Word';wd.className='button-link';act.append(wd)}
  const dl=document.createElement('a');dl.href='/files/'+r.id+'/download';dl.textContent=r.kind==='file'?'Download original':'Download text';dl.className='button-link';act.append(dl);
  const del=el('button','Delete');del.type='button';del.className='secondary';del.onclick=()=>run(async()=>{if(!confirm('Delete “'+r.title+'” permanently?'))return;await api('/files/'+r.id,'DELETE');$('notice').textContent='Deleted.';await load()});act.append(del);
  box.append(act);return box}
 async function render(){const t=$('k-table');t.replaceChildren();const h=document.createElement('thead'),hr=document.createElement('tr');const all=document.createElement('input');all.type='checkbox';all.setAttribute('aria-label','Select all shown');all.checked=st.rows.length>0&&st.rows.every(r=>st.picked.has(r.id));all.onchange=()=>{for(const r of st.rows)all.checked?st.picked.add(r.id):st.picked.delete(r.id);run(render)};const th0=document.createElement('th');th0.append(all);hr.append(th0);for(const x of ['Item','Type','Label','Tags','Added']){const th=el('th',x);th.scope='col';hr.append(th)}h.append(hr);t.append(h);
  const b=document.createElement('tbody');if(!st.rows.length){const tr=document.createElement('tr'),td=el('td',st.status==='draft'?'No drafts waiting.':'Nothing matches.','muted');td.colSpan=6;tr.append(td);b.append(tr)}
  for(const r of st.rows){const tr=document.createElement('tr');tr.className='mem-row'+(st.open.has(r.id)?' open':'');const c0=document.createElement('td');const cb=document.createElement('input');cb.type='checkbox';cb.checked=st.picked.has(r.id);cb.setAttribute('aria-label','Select '+r.title);cb.onchange=()=>{cb.checked?st.picked.add(r.id):st.picked.delete(r.id);bulk()};c0.append(cb);
   const c1=document.createElement('td');const tb=el('button',r.title,'mem-title');tb.type='button';tb.setAttribute('aria-expanded',st.open.has(r.id));tb.onclick=()=>{st.open.has(r.id)?st.open.delete(r.id):st.open.add(r.id);run(render)};c1.append(tb,el('div',(r.kind==='file'?r.summary:r.source)||'','mem-preview'));
   const c3=document.createElement('td');c3.append(el('span',KL[r.label],'badge k-lab-'+r.label));if(r.status==='draft')c3.append(el('div','Draft','flag'));
   if(r.replaced_by){const f=el('div','Replaced','badge superseded');f.title='Replaced by “'+r.replaced_by.title+'”';c3.append(f)}
   if((r.replacement_suggestions||[]).some(p=>p.new_status==='active')){const f=el('div','⇄ Replacement suggested','flag');c3.append(f)}
   const c4=document.createElement('td');if(r.client)c4.append(el('span',r.client,'tag k-knowledge'));if(r.category){const cg=el('span',r.category,'tag');cg.style.marginLeft='4px';c4.append(cg);if(r.category_by==='temple')c4.append(el('span','✦','temple-mark'))}
   if(r.category_suggestion){const sg=el('div','','suggest');sg.append(el('span','Suggested: '+r.category_suggestion,'small'));for(const [lab,action] of [['✓','accept'],['✕','dismiss']]){const x=el('button',lab,'mini');x.type='button';x.setAttribute('aria-label',(action==='accept'?'Accept ':'Dismiss ')+r.category_suggestion);x.onclick=()=>run(async()=>{await api('/admin/api/knowledge/suggestions','POST',{ids:[r.id],action});await load()});sg.append(x)}c4.append(sg)}
   if(!c4.childElementCount)c4.append(el('span','—','muted'));
   if(r.owner)c4.append(el('div',r.owner,'small muted'));if(r.purview_label){const pl=el('div','Purview: '+r.purview_label,'small muted');c3.append(pl)}
   const c5=el('td',fmt(r.created_at),'num');c5.title='Added by '+r.added_by;
   tr.append(c0,c1,el('td',KIND[r.kind],'small'),c3,c4,c5);b.append(tr);
   if(st.open.has(r.id)){const dr=document.createElement('tr');dr.className='mem-detail-row';const td=document.createElement('td');td.colSpan=6;dr.append(td);b.append(dr);td.append(await detail(r))}}
  t.append(b);bulk()}
 function bulk(){$('k-bulk').hidden=!st.picked.size;$('k-selected').textContent=st.picked.size+' selected';const drafts=st.rows.some(r=>st.picked.has(r.id)&&r.status==='draft');$('k-approve').hidden=$('k-reject').hidden=!drafts;$('k-archive').hidden=st.status!=='active'}
 async function load(more=false){D=await api('/admin/api/knowledge?status='+st.status+'&kind='+st.kind+'&label='+st.label+'&category='+encodeURIComponent(st.category)+'&client='+encodeURIComponent(st.client)+'&owner='+encodeURIComponent(st.owner)+'&query='+encodeURIComponent(st.query)+'&offset='+(more?st.offset:0));fillOwners($('k-f-owner'),D.owners,st.owner);if(document.activeElement!==$('k-review-days'))$('k-review-days').value=D.review_days;
  st.rows=more?st.rows.concat(D.items):D.items;st.offset=D.next_offset;const c=D.counts;
  $('k-summary').textContent=(c.status.active||0)+' active · '+(c.status.draft||0)+((c.status.draft||0)===1?' draft':' drafts')+' awaiting approval';
  $('k-status').replaceChildren(...STAT.map(([k,l])=>chip(l+' ('+(c.status[k]||0)+')',st.status===k,()=>{st.status=k;st.picked.clear();run(()=>load())},k==='draft'&&c.status.draft&&st.status!=='draft'?'attention':'')));
  $('k-kinds').replaceChildren(chip('All types',!st.kind,()=>{st.kind='';run(()=>load())}),...Object.keys(KIND).filter(k=>c.kind[k]).map(k=>chip(KIND[k]+' ('+c.kind[k]+')',st.kind===k,()=>{st.kind=k;run(()=>load())})));
  $('k-labels').replaceChildren(chip('Any label',!st.label,()=>{st.label='';run(()=>load())}),...Object.keys(KL).filter(k=>c.label[k]).map(k=>chip(KL[k]+' ('+c.label[k]+')',st.label===k,()=>{st.label=k;run(()=>load())})),...(c.suggested?[chip('✦ Category suggestions ('+c.suggested+')',st.category==='__suggested__',()=>{st.category='__suggested__';$('k-f-category').value='';run(()=>load())},'attention')]:[]));
  if(!more){opts($('k-f-category'),[['__none__','Uncategorised']].concat(catList()),st.category==='__suggested__'?'':st.category,'Any');opts($('k-f-client'),[['__general__','General (no client)']].concat(cliList()),st.client,'Any');
   for(const [id,list,blank] of [['k-b-category',catList(),'Uncategorised'],['k-b-client',cliList(),'General (no client)'],['kn-category',catList(),'Uncategorised'],['kn-client',cliList(),'General (no client)'],['km-category',catList(),'Uncategorised'],['km-client',cliList(),'General (no client)']])opts($(id),list,$(id).value,blank);
   for(const id of ['k-b-label','kn-label','km-label'])opts($(id),labList(),$(id).value||(id==='km-label'?'internal':'general'))}
  await render();$('k-count').textContent='Showing '+st.rows.length+' of '+D.total;$('k-more').hidden=st.offset===null}
 // filters and bulk
 if(st.query)$('k-query').value=st.query;
 $('k-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{st.query=$('k-query').value.trim();run(()=>load())},300)};
 $('k-f-category').onchange=()=>{st.category=$('k-f-category').value;run(()=>load())};$('k-f-client').onchange=()=>{st.client=$('k-f-client').value;run(()=>load())};
 $('k-review-save').onclick=()=>run(async()=>{const x=await api('/admin/api/knowledge-review-days','PUT',{days:Number($('k-review-days').value||0)});$('notice').textContent=x.days?'New and approved items are now due for review after '+x.days+' days.':'No default review date for new items.'});$('k-f-owner').onchange=()=>{st.owner=$('k-f-owner').value;st.picked.clear();run(()=>load())};
 $('k-b-owner-set').onclick=()=>run(async()=>{const x=await api('/admin/api/knowledge','PUT',{ids:[...st.picked],owner:$('k-b-owner').value.trim()});$('notice').textContent=(x.updated??1)+' updated: owner '+($('k-b-owner').value.trim()||'removed')+'.';st.picked.clear();$('k-b-owner').value='';await load()});
 $('k-more').onclick=()=>run(()=>load(true));$('k-clear').onclick=()=>{st.picked.clear();run(render)};
 for(const [id,decision] of [['k-approve','approved'],['k-reject','rejected']])$(id).onclick=()=>run(async()=>{const note=askReason(decision);if(note===null)return;const x=await api('/admin/api/knowledge/review','POST',{ids:[...st.picked],decision,note});$('notice').textContent=x.changed+' '+decision+(x.blocked?', '+x.blocked+' blocked: '+x.block_reasons.join(' '):'')+'.';st.picked.clear();await load()});
 $('k-b-cat').onclick=()=>run(async()=>{const x=await api('/admin/api/knowledge','PUT',{ids:[...st.picked],category:$('k-b-category').value});$('notice').textContent=(x.updated??1)+' updated.';st.picked.clear();await load()});
 $('k-b-label-set').onclick=()=>run(async()=>{const x=await api('/admin/api/knowledge','PUT',{ids:[...st.picked],label:$('k-b-label').value});$('notice').textContent=(x.updated??1)+' labelled '+KL[$('k-b-label').value]+'.';st.picked.clear();await load()});
 $('k-b-client-set').onclick=()=>run(async()=>{const x=await api('/admin/api/clients/tag','POST',{type:'file',ids:[...st.picked],client:$('k-b-client').value});$('notice').textContent=x.updated+' set to '+(x.client||'General')+'.';st.picked.clear();await load()});
 $('k-archive').onclick=()=>run(async()=>{await api('/admin/api/knowledge','PUT',{ids:[...st.picked],status:'archived'});$('notice').textContent='Archived. Archived items are hidden from models.';st.picked.clear();await load()});
 $('k-categorise').onclick=()=>run(async()=>{const b=$('k-categorise');b.disabled=true;$('k-cat-result').textContent='Temple is reading uncategorised items…';try{const r=await api('/admin/api/knowledge/categorise','POST',{});$('k-cat-result').textContent=r.status==='paused'?r.message:r.status==='no_categories'?'Create categories on the Memories page first.':r.status==='busy'?'Already running.':'Checked '+r.checked+': '+r.applied+' categorised, '+r.suggested+' suggested.';await load()}catch(e){$('k-cat-result').textContent=e.message}finally{b.disabled=false}});
 $('k-find-replaced').onclick=()=>run(async()=>{const b=$('k-find-replaced');b.disabled=true;$('k-cat-result').textContent='Temple is looking for older items that newer ones replace…';try{const r=await api('/admin/api/knowledge/find-replaced','POST',{});$('k-cat-result').textContent=r.status==='busy'?'Already running.':'Checked '+r.checked+' item'+(r.checked===1?'':'s')+': '+r.suggested+' replacement'+(r.suggested===1?'':'s')+' suggested'+(r.remaining?' · '+r.remaining+' still to check (run again)':'')+'.'+(r.message?' '+r.message:'');await load()}catch(e){$('k-cat-result').textContent=e.message}finally{b.disabled=false}});
 // note editor
 const show=(id,on)=>{$(id).hidden=!on};
 $('k-new-note').onclick=()=>{show('k-meeting',false);show('k-note',true);$('kn-title').focus()};$('kn-cancel').onclick=()=>show('k-note',false);
 $('kn-client').onchange=()=>{if($('kn-client').value&&$('kn-label').value==='general')$('kn-label').value='client'};
 $('kn-save').onclick=()=>run(async()=>{const r=await api('/admin/api/knowledge/note','POST',{title:$('kn-title').value,content:$('kn-content').value,source:$('kn-source').value,category:$('kn-category').value,client:$('kn-client').value,label:$('kn-label').value});$('notice').textContent=r.duplicate?'Identical content already exists.':'Note saved.';$('kn-title').value=$('kn-content').value='';show('k-note',false);st.status='active';await load()});
 // meeting extract
 $('k-new-meeting').onclick=()=>{show('k-note',false);show('k-meeting',true);show('km-step1',true);show('km-step2',false);$('km-transcript').focus()};
 $('km-cancel').onclick=()=>show('k-meeting',false);$('km-back').onclick=()=>{show('km-step2',false);show('km-step1',true)};
 $('km-load').onclick=()=>$('km-file').click();
 $('km-file').onchange=()=>run(async()=>{const f=$('km-file').files[0];if(!f)return;const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.onerror=()=>no(new Error('Could not read the file.'));r.readAsDataURL(f)});const x=await api('/admin/api/knowledge/meeting/transcript','POST',{name:f.name,data});$('km-transcript').value=x.transcript;$('notice').textContent=x.truncated?'Loaded the first 90,000 characters.':'Transcript loaded.';$('km-file').value=''});
 $('km-client').onchange=()=>{if($('km-client').value&&['general','internal'].includes($('km-label').value))$('km-label').value='client'};
 $('km-extract').onclick=()=>run(async()=>{const b=$('km-extract');b.disabled=true;b.textContent='Temple is reading…';try{const x=await api('/admin/api/knowledge/meeting/extract','POST',{transcript:$('km-transcript').value});
  $('km-title').value=x.title;$('km-date').value=/^\d{4}-\d{2}-\d{2}$/.test(x.date)?x.date:'';$('km-attendees').value=x.attendees.join(', ');$('km-summary').value=x.summary;$('km-decisions').value=x.decisions.join('\n');$('km-actions').value=x.actions.map(a=>[a.action,a.owner,a.due].filter((v,i)=>i===0||v).join(' | ')).join('\n');
  if(x.client){$('km-client').value=x.client;$('km-label').value='client'}show('km-step1',false);show('km-step2',true);$('km-title').focus()}finally{b.disabled=false;b.textContent='Extract with Temple'}});
 $('km-save').onclick=()=>run(async()=>{const actions=$('km-actions').value.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{const [action,owner,due]=l.split('|').map(x=>(x||'').trim());return {action,owner:owner||'',due:due||''}});
  const r=await api('/admin/api/knowledge/meeting','POST',{title:$('km-title').value,content:$('km-summary').value,source:$('km-source').value,date:$('km-date').value,attendees:$('km-attendees').value.split(',').map(x=>x.trim()).filter(Boolean),decisions:$('km-decisions').value.split('\n').map(x=>x.trim()).filter(Boolean),actions,transcript:$('km-keep').checked?$('km-transcript').value:'',category:$('km-category').value,client:$('km-client').value,label:$('km-label').value});
  $('notice').textContent=r.duplicate?'Identical content already exists.':'Meeting extract saved.';$('km-transcript').value='';show('k-meeting',false);st.status='active';st.kind='meeting';await load()});
 run(()=>load());
}
"""
SCRIPT += r"""
if(PAGE==='actions'){
 const V={approve:['Temple: approve','v-ok'],clarify:['Temple: clarify','v-warn'],reject:['Temple: reject','v-bad'],unreviewed:['Not reviewed','v-none'],running:['Reviewing…','v-run'],failed:['Review failed','v-bad'],unclear:['See report','v-none']};
 const ACCEPT={memory:'Propose memory',decision:'Propose decision',knowledge:'Save note',guidance:'Add to guidance',rule_request:'Log request'};
 function btn(label,fn,secondary){const b=el('button',label,secondary?'secondary mini-act':'mini-act');b.type='button';b.onclick=()=>run(async()=>{b.disabled=true;try{await fn();await load()}finally{b.disabled=false}});return b}
 function actionsFor(i){const box=el('div','','act-buttons');
  if(i.type==='proposal'){if(i.replaces)box.append(btn('Approve, replacing “'+i.replaces.title+'”',async()=>{await api('/admin/api/records/'+i.id+'/replace','POST',{old_id:i.replaces.id,reason:'Approved on Actions as a newer version (Temple suggested the replacement).'});$('notice').textContent='Approved: '+i.title+'. “'+i.replaces.title+'” is now superseded.'}));
   box.append(btn(i.replaces?'Approve only':'Approve',async()=>{await api('/admin/api/records/'+i.id+'/review','POST',{decision:'approved'});$('notice').textContent='Approved: '+i.title},!!i.replaces),btn('Reject',async()=>{await api('/admin/api/records/'+i.id+'/review','POST',{decision:'rejected'});$('notice').textContent='Rejected: '+i.title},true))}
  else if(i.type==='draft'){const n=(i.replaces||[]).length;if(n)box.append(btn('Approve and retire '+(n===1?'“'+i.replaces[0].title+'”':n+' older items'),async()=>{const x=await api('/admin/api/knowledge/review','POST',{ids:[i.id],decision:'approved',retire_replaced:true});$('notice').textContent=x.blocked?x.block_reasons.join(' '):'Approved: '+i.title+'; '+x.retired+' older item'+(x.retired===1?'':'s')+' retired.'}));
   box.append(btn(n?'Approve only':'Approve',async()=>{const x=await api('/admin/api/knowledge/review','POST',{ids:[i.id],decision:'approved'});$('notice').textContent=x.blocked?x.block_reasons.join(' '):'Approved: '+i.title},!!n),btn('Reject',async()=>{await api('/admin/api/knowledge/review','POST',{ids:[i.id],decision:'rejected'});$('notice').textContent='Rejected: '+i.title},true))}
  else if(i.type==='orgfact'){box.append(btn('Approve',async()=>{const x=await api('/admin/api/organisations/facts/review','POST',{ids:[i.id],decision:'approved'});$('notice').textContent=x.blocked?x.block_reasons.join(' '):'Approved: '+i.title}),btn('Reject',async()=>{await api('/admin/api/organisations/facts/review','POST',{ids:[i.id],decision:'rejected'});$('notice').textContent='Rejected: '+i.title},true))}
  else if(i.type==='replacement'){box.append(btn('Retire older',async()=>{await api('/admin/api/knowledge/replacements','POST',{ids:[i.id],action:'accept'});$('notice').textContent='Retired. The older item now points to its replacement.'}),btn('Keep both',async()=>{await api('/admin/api/knowledge/replacements','POST',{ids:[i.id],action:'dismiss'});$('notice').textContent='Kept both.'},true))}
  else if(i.type==='suggestion'){box.append(btn(ACCEPT[i.kind]||'Accept',async()=>{await api('/admin/api/temple-suggestions/'+i.id,'POST',{action:'accept',content:i.content});$('notice').textContent='Accepted: '+i.title+(i.kind==='memory'||i.kind==='decision'?' (now a proposal awaiting approval)':'')}),btn('Dismiss',async()=>{await api('/admin/api/temple-suggestions/'+i.id,'POST',{action:'dismiss',content:''})},true));const e=document.createElement('a');e.href='/admin/temple?tab=suggestions';e.textContent='Edit first ↗';e.className='small';box.append(e)}
  else if(i.type==='category'){box.append(btn('Accept',()=>api('/admin/api/memories/suggestions','POST',{ids:[i.id],action:'accept'})),btn('Dismiss',()=>api('/admin/api/memories/suggestions','POST',{ids:[i.id],action:'dismiss'}),true))}
  else if(i.type==='kcategory'){box.append(btn('Accept',()=>api('/admin/api/knowledge/suggestions','POST',{ids:[i.id],action:'accept'})),btn('Dismiss',()=>api('/admin/api/knowledge/suggestions','POST',{ids:[i.id],action:'dismiss'}),true))}
  else if(i.type==='client'){box.append(btn('Accept',()=>api('/admin/api/clients/suggestions','POST',{items:[{type:i.item_type,id:i.id}],action:'accept'})),btn('Dismiss',()=>api('/admin/api/clients/suggestions','POST',{items:[{type:i.item_type,id:i.id}],action:'dismiss'}),true))}
  else if(i.href){const a=document.createElement('a');a.href=i.href;a.textContent='Open ↗';a.className='small';box.append(a)}
  return box}
 async function load(){const d=await api('/admin/api/actions');$('act-total').textContent=d.total?d.total+(d.total===1?' action waiting':' actions waiting'):'Nothing waiting — all clear';
  const box=$('act-sections');box.replaceChildren();
  const open=d.sections.filter(s=>s.count),clear=d.sections.filter(s=>!s.count);
  for(const s of open){const sec=el('section','','act-sec act-'+s.level);const h=el('div','','mem-head');const t=el('h2','');t.append(document.createTextNode(s.title+' '),el('span',String(s.count),'act-count'));const a=document.createElement('a');a.href=s.link;a.textContent=s.count>s.items.length?'Open all '+s.count+' ↗':'Open ↗';h.append(t,a);sec.append(h);
   if(s.note)sec.append(el('p',s.note,'muted small'));
   for(const i of s.items){const row=el('div','','act-row');const txt=el('div','','act-text');const tl=el('strong',i.title);txt.append(tl);
    if(i.verdict){const [l,c]=V[i.verdict]||V.unclear;const bd=el('span',l,'badge '+c);bd.style.marginLeft='8px';txt.append(bd)}if(i.kind==='decision'&&i.type==='proposal'){const db=el('span','Decision','badge v-run');db.style.marginLeft='6px';txt.append(db)}
    if(i.type==='proposal'&&i.replaces)txt.append(el('div','Temple: replaces “'+i.replaces.title+'”','small'));
    if(i.detail)txt.append(el('div',i.detail,'small muted'));row.append(txt,actionsFor(i));sec.append(row)}
   box.append(sec)}
  if(clear.length){const sec=el('section','','act-sec');sec.append(el('h2','All clear'),el('p',clear.map(s=>s.title).join(' · '),'muted small'));box.append(sec)}}
 $('act-refresh').onclick=()=>run(load);run(load);
}
"""
SCRIPT += r"""
"""
SCRIPT += r"""
if(PAGE==='archive'){
 const st={query:'',flag:'all',sort:'recent',offset:0,rows:[],open:new Set(),cache:{}};let timer=null;
 const fmt=d=>new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
 const ago=d=>{const n=Math.floor((Date.now()-new Date(d))/864e5);return n+' days ago'};
 const SRC=s=>s==='alice'?'':s;
 function reviewLine(r){const v=r.review;if(!v)return null;const t={running:'Temple reviewing…',complete:v.suggestions?'Temple: '+v.suggestions+' suggestion'+(v.suggestions===1?'':'s'):'Temple: nothing to keep',blocked:'Not reviewed: '+v.error,failed:'Review failed'}[v.status]||v.status;
  if(v.status==='complete'&&v.suggestions){const a=document.createElement('a');a.href='/admin/temple?tab=suggestions';a.textContent=t+' ↗';a.className='small';const d=el('div','');d.append(a);return d}return el('div',t,'small muted')}
 function captured(r){const td=captured0(r);const rl=reviewLine(r);if(rl)td.append(rl);return td}
 function captured0(r){const td=document.createElement('td');if(!r.captured){const f=el('span','⚑ Nothing captured','flag');f.title='No memories or knowledge were captured from this chat.';td.append(f);return td}
  if(r.memories)td.append(el('span',r.memories+(r.memories===1?' memory':' memories'),'tag'));if(r.knowledge)td.append(el('span',r.knowledge+(r.knowledge===1?' knowledge note':' knowledge notes'),'tag know'));return td}
 function transcript(chat){const box=el('div','','transcript');if(!chat.turns.length)box.append(el('p','This chat has no messages.','muted'));
  for(const t of chat.turns){if(t.user_text){const u=el('div','','t-msg t-user');u.append(el('div','You','t-label'),el('div',t.user_text,'t-body'));box.append(u)}if(!t.reply&&t.status==='complete')continue;
   const a=el('div','','t-msg t-ai');a.append(el('div',t.status==='complete'?(t.model==='reproduced transcript'||t.model==='Claude export'?(t.provider||'Assistant'):(t.model||'Assistant'))+(t.route?' · '+t.route:''):'Not completed','t-label'),el('div',t.status==='complete'?t.reply:(t.error||'No answer was saved.'),'t-body'+(t.status==='complete'?'':' muted')));
   for(const p of (t.images||[])){const img=document.createElement('img');img.src='/images/'+p.path;img.alt=p.prompt||'Generated image';img.loading='lazy';img.className='t-img';a.append(img)}box.append(a)}return box}
 function savedView(chat){const rec=JSON.parse(chat.summary||'{}');const box=el('div','','transcript');
  if(rec.verbatim){box.append(el('div','Imported from your Claude data export · verbatim · '+rec.messages+' messages','t-label'));return box}
  box.append(el('div','Saved from '+(rec.app||chat.source)+' · written by that assistant, not a transcript','t-label'),el('div',rec.summary||'','t-body'));
  for(const [label,key] of [['Key points','key_points'],['Decisions','decisions'],['Asked to remember','remember'],['Your words','user_quotes']]){const xs=rec[key]||[];if(!xs.length)continue;box.append(el('strong',label));for(const x of xs)box.append(el('div',(key==='user_quotes'?'“'+x+'”':'• '+x),'small'))}
  const nm=(rec.proposed_memories||[]).length,nk=(rec.proposed_knowledge||[]).length;
  if(nm||nk){const cap=el('div','','small');cap.append(el('strong','Captured from this conversation: '),document.createTextNode([nm?nm+(nm===1?' memory or decision proposal':' memory or decision proposals'):'',nk?nk+(nk===1?' knowledge draft':' knowledge drafts'):''].filter(Boolean).join(' · ')+' '));const a=document.createElement('a');a.href='/admin/actions';a.textContent='Review in Actions ↗';cap.append(a);box.append(cap)}
  if((rec.memory_notes||[]).length){box.append(el('strong','Not proposed'));for(const x of rec.memory_notes)box.append(el('div',x,'small muted'))}return box}
 async function detail(r){const box=el('div','','arc-detail');const bar=el('div','','arc-actions');
  const ask=el('button',r.review&&r.review.status==='complete'?'Ask Temple again':'Ask Temple to review');ask.type='button';ask.disabled=!!(r.review&&r.review.status==='running');ask.onclick=()=>run(async()=>{ask.disabled=true;ask.textContent='Temple is reading…';try{const x=await api('/admin/api/archive/'+r.id+'/temple-review','POST',{});$('notice').textContent=x.status==='complete'?'Temple found '+x.suggestions+' suggestion'+(x.suggestions===1?'':'s')+(x.suggestions?' — review them in Temple → Chat suggestions.':'.')+(x.dropped?' '+x.dropped+' dropped because their quotes were not your words.':''):(x.message||('Review '+x.status+'.'));await load()}finally{ask.disabled=false}});bar.append(ask);
  const open=document.createElement('a');open.href='/#'+r.id;open.textContent='Open in chat ↗';open.className='button-link';open.hidden=r.source!=='alice';
  const restore=el('button','Restore to active');restore.type='button';restore.onclick=()=>run(async()=>{await api('/admin/api/archive/'+r.id+'/restore','POST',{});$('notice').textContent='“'+r.title+'” is back in your chat list.';await load()});
  const del=el('button','Delete chat');del.type='button';del.className='secondary';del.onclick=()=>run(async()=>{if(!confirm('Delete “'+r.title+'” and its messages? Memories and files captured from it remain.'))return;await api('/chats/'+r.id,'DELETE');$('notice').textContent='Chat deleted.';await load()});
  restore.hidden=r.source!=='alice';bar.append(open,restore,del);box.append(bar);const holder=el('div','Loading conversation…','muted small');box.append(holder);
  try{const chat=st.cache[r.id]||(st.cache[r.id]=await api('/chats/'+r.id));if(chat.source&&chat.source!=='alice'){const wrap=el('div','');wrap.append(savedView(chat));if(chat.turns.length){const rec=JSON.parse(chat.summary||'{}');if(!rec.verbatim)wrap.append(el('p','Transcript reproduced by '+(rec.app||chat.source)+(rec.transcript_complete===false?' (incomplete: more parts were expected)':'')+'. Not an exact export.','muted small'));wrap.append(transcript(chat))}holder.replaceWith(wrap)}else holder.replaceWith(transcript(chat))}catch(e){holder.textContent=e.message}return box}
 async function render(){const t=$('arc-table');t.replaceChildren();const head=document.createElement('thead'),hr=document.createElement('tr');for(const h of ['Chat','Created','Last used','Captured']){const th=el('th',h);th.scope='col';hr.append(th)}head.append(hr);t.append(head);
  const body=document.createElement('tbody');if(!st.rows.length){const tr=document.createElement('tr'),td=el('td',st.query||st.flag!=='all'?'No archived chats match.':'No archived chats yet. Chats appear here after 30 days without activity.','muted');td.colSpan=4;tr.append(td);body.append(tr)}
  for(const r of st.rows){const tr=document.createElement('tr');tr.className='mem-row'+(st.open.has(r.id)?' open':'');const c1=document.createElement('td');const b=el('button',r.title,'mem-title');b.type='button';b.setAttribute('aria-expanded',st.open.has(r.id));b.onclick=()=>{st.open.has(r.id)?st.open.delete(r.id):st.open.add(r.id);run(render)};c1.append(b,el('div',r.source!=='alice'?'Saved conversation':r.exchanges+(r.exchanges===1?' exchange':' exchanges'),'mem-preview'));if(SRC(r.source)){const sb=el('span',r.source,'tag k-knowledge');sb.style.marginLeft='6px';b.after(sb)}if(r.client){const cc=el('span',r.client,'tag');cc.style.marginLeft='6px';c1.append(cc)}
   const c3=el('td',fmt(r.updated_at),'num');c3.title=ago(r.updated_at);tr.append(c1,el('td',fmt(r.created_at),'num'),c3,captured(r));body.append(tr);
   if(st.open.has(r.id)){const dr=document.createElement('tr');dr.className='mem-detail-row';const td=document.createElement('td');td.colSpan=4;dr.append(td);body.append(dr);td.append(await detail(r))}}
  t.append(body)}
 async function load(more=false){const d=await api('/admin/api/archive?query='+encodeURIComponent(st.query)+'&flag='+st.flag+'&sort='+st.sort+'&offset='+(more?st.offset:0));
  st.rows=more?st.rows.concat(d.chats):d.chats;st.offset=d.next_offset;st.last=d;
  const all=el('button','All archived','chip'+(st.flag==='all'?' on':''));all.type='button';all.onclick=()=>{st.flag='all';run(()=>load())};
  const none=el('button','⚑ Nothing captured ('+d.uncaptured+')','chip'+(st.flag==='uncaptured'?' on':''));none.type='button';if(d.uncaptured&&st.flag!=='uncaptured')none.classList.add('attention');none.onclick=()=>{st.flag='uncaptured';run(()=>load())};
  const ext=el('button','From Claude apps ('+d.external+')','chip'+(st.flag==='external'?' on':''));ext.type='button';ext.onclick=()=>{st.flag='external';run(()=>load())};
  $('arc-filters').replaceChildren(all,none,ext);clearTimeout(st.poll);if(st.rows.some(r=>r.review&&r.review.status==='running')){st.cache={};st.poll=setTimeout(()=>run(()=>load()),5000)}await render();$('arc-count').textContent='Showing '+st.rows.length+' of '+d.total+' · archived after '+d.days+' days without activity';$('arc-more').hidden=st.offset===null}
 $('arc-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{st.query=$('arc-query').value.trim();run(()=>load())},300)};
 $('arc-sort').onchange=()=>{st.sort=$('arc-sort').value;run(()=>load())};
 $('imp-go').onclick=()=>$('imp-file').click();
 const MB=b=>Math.round(b/1048576*10)/10;
 function bar(pct,label){$('imp-progress').hidden=false;$('imp-fill').style.width=Math.max(0,Math.min(100,pct))+'%';$('imp-label').textContent=label}
 function showResult(x){const parts=[x.imported+' new',x.updated+' updated',x.unchanged+' unchanged'];if(x.older)parts.push(x.older+' older than your date');if(x.empty)parts.push(x.empty+' empty');
  $('imp-result').replaceChildren(el('div','Imported: '+parts.join(' · ')+'. They are under From Claude apps; ask Temple to review the ones that matter.'));
  if(x.skipped.length){const d=document.createElement('details');d.append(el('summary',x.skipped.length+' skipped by security rules'));for(const k of x.skipped)d.append(el('div','• '+k.title+': '+k.reason,'small'));$('imp-result').append(d)}}
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 async function waitImport(prefix){while(true){const j=await api('/admin/api/import/status');
   if(j.status==='running'){if(j.label)bar(j.pct||0,prefix+j.label);else if(j.total)bar(j.done/j.total*100,prefix+'Importing '+j.done+' of '+j.total+(j.current?': '+j.current:''));else bar(3,prefix+(j.current||'Reading the export…'));await sleep(700);continue}
   return j}}
 function upload(f,prefix){return new Promise((ok,fail)=>{const since=$('imp-since').value;const xhr=new XMLHttpRequest();xhr.open('POST','/admin/api/import/claude-export'+(since?'?since='+since:''));
  xhr.setRequestHeader('X-Admin-Token','__TOKEN__');xhr.setRequestHeader('Content-Type','application/octet-stream');
  xhr.upload.onprogress=e=>{if(e.lengthComputable)bar(e.loaded/e.total*100,prefix+'Uploading '+f.name+': '+MB(e.loaded)+' of '+MB(e.total)+' MB')};
  xhr.onload=()=>{let x={};try{x=JSON.parse(xhr.responseText)}catch{}if(xhr.status>=400)fail(new Error(f.name+': '+(x.detail||('import failed ('+xhr.status+')'))));else ok()};
  xhr.onerror=()=>fail(new Error(f.name+': upload failed. Check the app is running and try again.'));bar(0,prefix+'Uploading '+f.name+'…');xhr.send(f)})}
 async function pollImport(){const j=await waitImport('');$('imp-go').disabled=false;   // used when resuming after a refresh
  if(j.status==='complete'&&j.result){bar(100,'Finished: '+j.total+' conversations checked.');showResult(j.result);st.flag='external';await load()}
  else if(j.status==='failed'){$('imp-progress').hidden=true;$('imp-result').textContent=j.error}}
 $('imp-file').onchange=async()=>{const files=[...$('imp-file').files];$('imp-file').value='';if(!files.length)return;const b=$('imp-go');b.disabled=true;$('imp-result').textContent='';
  const total={imported:0,updated:0,unchanged:0,older:0,empty:0,skipped:[]},errors=[];let checked=0;
  for(const [i,f] of files.entries()){const prefix=files.length>1?'File '+(i+1)+' of '+files.length+' · ':'';
   try{await upload(f,prefix);const j=await waitImport(prefix);
    if(j.status==='complete'&&j.result){checked+=j.total;for(const k of ['imported','updated','unchanged','older','empty'])total[k]+=j.result[k];total.skipped.push(...j.result.skipped);
     if(j.result.failed)errors.push(...j.result.failed);if(j.result.saved_to)total.saved=j.result.saved_to}
    else if(j.status==='failed')errors.push(f.name+': '+j.error)}catch(e){errors.push(e.message)}}
  b.disabled=false;bar(100,'Finished: '+files.length+(files.length===1?' file, ':' files, ')+checked+' conversations checked.');showResult(total);
  if(errors.length){const d=el('div','','');for(const e of errors)d.append(el('div','⚠ '+e,'small'));$('imp-result').append(d)}
  if(total.saved)$('imp-result').append(el('div','Downloaded batches are saved in '+total.saved+', so you can re-import them without the links.','small muted'));
  st.flag='external';await load()};
 run(async()=>{const j=await api('/admin/api/import/status');if(j.status==='running')pollImport()});   // resume after a refresh
 $('arc-review-flagged').onclick=()=>run(async()=>{const n=st.last?st.last.unreviewed:0;if(!n){$('notice').textContent='Every flagged chat has already been reviewed.';return}if(!confirm('Ask Temple to review '+Math.min(n,50)+' of '+n+' flagged chats not yet reviewed? Each review is a separate API call (up to 50 per run; run it again for more). Chats with secrets or protective markings are skipped.'))return;const x=await api('/admin/api/archive/temple-review-flagged','POST',{});$('notice').textContent='Temple is reviewing '+x.started+' chats in the background. This page updates as they finish.';await load()});$('arc-more').onclick=()=>run(()=>load(true));
 run(()=>load());
}
"""
SCRIPT += r"""
if(PAGE==='temple'){
 const V={approve:['Temple: approve','ok'],clarify:['Temple: clarify','warn'],reject:['Temple: reject','bad'],unreviewed:['Not reviewed','none'],running:['Reviewing…','run'],failed:['Review failed','bad'],unclear:['See report','none']};
 const VIEWS=[['pending','Awaiting your decision'],['reviewed','Everything Temple reviewed'],['all','All memories']];
 const KIND={memory:'Memory',decision:'Decision',knowledge:'Knowledge note',guidance:'Guidance',rule_request:'Rule request'};
 const ACCEPT={memory:'Propose memory',decision:'Propose decision',knowledge:'Save knowledge note',guidance:'Add to guidance',rule_request:'Log rule request'};
 const t={view:'pending',verdict:'',query:'',offset:0,rows:[],open:new Set(),picked:new Set()};
 const s={status:'pending',kind:'',query:'',offset:0,rows:[],open:new Set(),picked:new Set()};
 let timer=null,poll=null;
 const fmt=d=>d?new Date(d).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'';
 function chip(text,active,onclick,cls=''){const b=el('button',text,'chip'+(active?' on':'')+(cls?' '+cls:''));b.type='button';b.setAttribute('aria-pressed',active);b.onclick=onclick;return b}
 function tab(name){for(const [id,pane] of [['tab-reviews','pane-reviews'],['tab-suggestions','pane-suggestions'],['tab-ask','pane-ask']]){const on=pane==='pane-'+name;$(id).classList.toggle('on',on);$(id).setAttribute('aria-selected',on);$(pane).hidden=!on}const u=new URL(location.href);u.searchParams.set('tab',name);history.replaceState(null,'',u)}
 function head(table,cols){const h=document.createElement('thead'),tr=document.createElement('tr');const all=document.createElement('input');all.type='checkbox';all.setAttribute('aria-label','Select all shown');const th0=document.createElement('th');th0.append(all);tr.append(th0);for(const c of cols){const th=el('th',c);th.scope='col';tr.append(th)}h.append(tr);table.replaceChildren(h);return all}
 // ---------- memory reviews ----------
 function reviewDetail(r){const box=el('div','','mem-detail');box.append(el('pre',r.content),el('p','Source (as supplied): '+r.source,'small'));
  const latest=r.reviews[0];
  if(latest){const rep=el('div','','t-report');rep.append(el('div','Temple · '+latest.model+' · '+fmt(latest.created_at),'t-label'),el('div',latest.report||latest.error||(latest.status==='running'?'Review running…':'No report.'),'t-body'));
   const ctx=latest.context||{};if(ctx.compared_count!==undefined)rep.append(el('p','Compared with '+ctx.compared_count+' of '+ctx.total_approved+' approved memories.','muted small'));box.append(rep)}
  if(r.related.length){const rel=document.createElement('details');rel.open=true;rel.append(el('summary','Related memories Temple cited ('+r.related.length+')'));for(const m of r.related){const d=el('div','','t-related');d.append(el('strong',m.title),el('p',m.content,'small'));rel.append(d)}box.append(rel)}
  if(r.reviews.length>1){const older=document.createElement('details');older.append(el('summary','Earlier reviews ('+(r.reviews.length-1)+')'));for(const v of r.reviews.slice(1))older.append(el('p',fmt(v.created_at)+' · '+v.model,'muted small'),el('pre',v.report||v.error||v.status));box.append(older)}
  const act=el('div','','arc-actions');
  if(r.status==='proposed'){for(const [label,decision] of [['Approve memory','approved'],['Reject','rejected']]){const b=el('button',label);if(decision==='rejected')b.className='secondary';b.type='button';b.onclick=()=>run(async()=>{await api('/admin/api/records/'+r.id+'/review','POST',{decision});$('notice').textContent='“'+r.title+'” '+decision+'.';await loadReviews()});act.append(b)}
   const again=el('button',latest?'Review again':'Review with Temple');again.className='secondary';again.type='button';again.disabled=r.verdict==='running';again.onclick=()=>run(async()=>{await api('/admin/api/temple/review-batch','POST',{ids:[r.id]});$('notice').textContent='Temple is reviewing “'+r.title+'”.';await loadReviews()});act.append(again)}
  box.append(act,memoryControls(r));return box}
 function renderReviews(){const table=$('t-table');const all=head(table,['Proposal','Temple','Related','Created']);all.checked=t.rows.length>0&&t.rows.every(r=>t.picked.has(r.id));all.onchange=()=>{for(const r of t.rows)all.checked?t.picked.add(r.id):t.picked.delete(r.id);renderReviews()};
  const body=document.createElement('tbody');if(!t.rows.length){const tr=document.createElement('tr'),td=el('td',t.view==='pending'&&!t.query&&!t.verdict?'Nothing awaiting a decision.':'Nothing matches these filters.','muted');td.colSpan=5;tr.append(td);body.append(tr)}
  for(const r of t.rows){const tr=document.createElement('tr');tr.className='mem-row'+(t.open.has(r.id)?' open':'');
   const c0=document.createElement('td');const cb=document.createElement('input');cb.type='checkbox';cb.checked=t.picked.has(r.id);cb.setAttribute('aria-label','Select '+r.title);cb.onchange=()=>{cb.checked?t.picked.add(r.id):t.picked.delete(r.id);bulkReviews()};c0.append(cb);
   const c1=document.createElement('td');const title=el('button',r.title,'mem-title');title.type='button';title.setAttribute('aria-expanded',t.open.has(r.id));title.onclick=()=>{t.open.has(r.id)?t.open.delete(r.id):t.open.add(r.id);renderReviews()};c1.append(title,el('div',r.content.replace(/\s+/g,' ').slice(0,160),'mem-preview'));
   const c2=document.createElement('td');const [label,cls]=V[r.verdict]||V.unclear;c2.append(el('span',label,'badge v-'+cls));if(r.reason)c2.append(el('div',r.reason,'t-reason'));if(r.status!=='proposed')c2.append(el('div','Memory: '+r.status,'muted small'));
   const c3=el('td',r.related.length?String(r.related.length):'—','num');if(r.related.length)c3.title=r.related.map(m=>m.title).join('\n');
   tr.append(c0,c1,c2,c3,el('td',fmt(r.created_at),'num'));body.append(tr);
   if(t.open.has(r.id)){const dr=document.createElement('tr');dr.className='mem-detail-row';const td=document.createElement('td');td.colSpan=5;td.append(reviewDetail(r));dr.append(td);body.append(dr)}}
  table.append(body);bulkReviews()}
 function bulkReviews(){$('t-bulk').hidden=!t.picked.size;$('t-selected').textContent=t.picked.size+' selected';const proposals=t.rows.some(r=>t.picked.has(r.id)&&r.status==='proposed');for(const id of ['t-approve','t-reject','t-review'])$(id).hidden=!proposals}
 async function loadReviews(more=false){const d=await api('/admin/api/temple/queue?view='+t.view+'&verdict='+t.verdict+'&query='+encodeURIComponent(t.query)+'&offset='+(more?t.offset:0));
  t.rows=more?t.rows.concat(d.items):d.items;t.offset=d.next_offset;
  $('t-views').replaceChildren(...VIEWS.map(([k,label])=>{const b=chip(label+' ('+d.views[k]+')',t.view===k,()=>{t.view=k;t.verdict='';t.picked.clear();run(()=>loadReviews())},k==='pending'&&d.views.pending&&t.view!=='pending'?'attention':'');return b}));
  const order=['approve','clarify','reject','unreviewed','running','failed','unclear'];const total=Object.values(d.counts).reduce((a,b)=>a+b,0);
  $('t-verdicts').replaceChildren(chip('Any verdict ('+total+')',!t.verdict,()=>{t.verdict='';run(()=>loadReviews())}),...order.filter(k=>d.counts[k]).map(k=>chip(V[k][0]+' ('+d.counts[k]+')',t.verdict===k,()=>{t.verdict=k;run(()=>loadReviews())},'v-chip v-'+V[k][1])));
  $('t-summary').textContent=d.views.pending+' awaiting decision · reviewer '+(d.settings.provider==='openai'?'GPT-6 Luna':'Haiku 4.5')+' · auto-review '+(d.settings.enabled?'on':'off');
  renderReviews();$('t-count').textContent='Showing '+t.rows.length+' of '+d.total;$('t-more').hidden=t.offset===null;
  clearTimeout(poll);if(t.rows.some(r=>r.verdict==='running'))poll=setTimeout(()=>run(()=>loadReviews()),5000)}
 // ---------- chat suggestions ----------
 function suggestionDetail(r){const box=el('div','','mem-detail');
  const q=el('div','','t-quote');q.append(el('div','You said · in “'+r.chat_title+'”','t-label'),el('div','“'+r.quote+'”','t-body'));box.append(q);
  const area=document.createElement('textarea');area.value=r.content;area.rows=4;area.maxLength=3000;area.setAttribute('aria-label','Suggested content');area.disabled=['accepted','dismissed'].includes(r.status);box.append(el('label','Suggested content (edit before accepting)','small'),area);
  box.append(el('p','Why: '+r.reason,'small'));if(r.related.length)box.append(el('p','Related memories: '+r.related.map(m=>m.title).join(' · '),'small muted'));
  const act=el('div','','arc-actions');const open=document.createElement('a');open.href='/#'+r.chat_id;open.textContent='Open chat ↗';open.className='button-link';
  if(!['accepted','dismissed'].includes(r.status)){const ok=el('button',ACCEPT[r.kind]||'Accept');ok.type='button';ok.onclick=()=>run(async()=>{const res=await api('/admin/api/temple-suggestions/'+r.id,'POST',{action:'accept',content:area.value});$('notice').textContent=KIND[r.kind]+' saved'+(r.kind==='memory'||r.kind==='decision'?' as a proposal — approve it in Memory reviews.':'.');await loadSuggestions();if(r.kind==='memory'||r.kind==='decision')loadReviews()});act.append(ok);
   for(const [label,action] of [['Later','later'],['Dismiss','dismiss']]){if(action==='later'&&r.status==='later')continue;const b=el('button',label);b.className='secondary';b.type='button';b.onclick=()=>run(async()=>{await api('/admin/api/temple-suggestions/'+r.id,'POST',{action,content:''});await loadSuggestions()});act.append(b)}}
  else act.append(el('span',r.status==='accepted'?'Accepted':'Dismissed','badge v-'+(r.status==='accepted'?'ok':'none')));
  act.append(open);box.append(act);return box}
 function renderSuggestions(){const table=$('s-table');const all=head(table,['Suggestion','Type','Chat','Suggested']);all.checked=s.rows.length>0&&s.rows.every(r=>s.picked.has(r.id));all.onchange=()=>{for(const r of s.rows)all.checked?s.picked.add(r.id):s.picked.delete(r.id);renderSuggestions()};
  const body=document.createElement('tbody');if(!s.rows.length){const tr=document.createElement('tr'),td=el('td',s.status==='pending'&&!s.kind&&!s.query?'No pending suggestions. Temple adds them after chat answers when conversation suggestions are on.':'Nothing matches these filters.','muted');td.colSpan=5;tr.append(td);body.append(tr)}
  for(const r of s.rows){const tr=document.createElement('tr');tr.className='mem-row'+(s.open.has(r.id)?' open':'');
   const c0=document.createElement('td');const cb=document.createElement('input');cb.type='checkbox';cb.checked=s.picked.has(r.id);cb.setAttribute('aria-label','Select '+r.title);cb.onchange=()=>{cb.checked?s.picked.add(r.id):s.picked.delete(r.id);bulkSuggestions()};c0.append(cb);
   const c1=document.createElement('td');const title=el('button',r.title,'mem-title');title.type='button';title.setAttribute('aria-expanded',s.open.has(r.id));title.title='Open to read, edit and accept';title.onclick=()=>{s.open.has(r.id)?s.open.delete(r.id):s.open.add(r.id);renderSuggestions()};c1.append(title,el('div',r.content.replace(/\s+/g,' ').slice(0,160),'mem-preview'));
   tr.append(c0,c1,(()=>{const td=document.createElement('td');td.append(el('span',KIND[r.kind]||r.kind,'tag k-'+r.kind));return td})(),el('td',r.chat_title,'small'),el('td',fmt(r.created_at),'num'));body.append(tr);
   if(s.open.has(r.id)){const dr=document.createElement('tr');dr.className='mem-detail-row';const td=document.createElement('td');td.colSpan=5;td.append(suggestionDetail(r));dr.append(td);body.append(dr)}}
  table.append(body);bulkSuggestions()}
 function bulkSuggestions(){$('s-bulk').hidden=!s.picked.size||s.status==='handled';$('s-selected').textContent=s.picked.size+' selected';$('s-later').hidden=s.status==='later'}
 async function loadSuggestions(more=false){const d=await api('/admin/api/temple/suggestions?status='+s.status+'&kind='+s.kind+'&query='+encodeURIComponent(s.query)+'&offset='+(more?s.offset:0));
  s.rows=more?s.rows.concat(d.items):d.items;s.offset=d.next_offset;
  $('tab-suggestions').textContent='Chat suggestions'+(d.counts.pending?' ('+d.counts.pending+')':'');$('tab-suggestions').classList.toggle('attention',!!d.counts.pending&&$('pane-suggestions').hidden);
  $('s-status').replaceChildren(...[['pending','Pending'],['later','Later'],['handled','Handled']].map(([k,label])=>chip(label+' ('+d.counts[k]+')',s.status===k,()=>{s.status=k;s.kind='';s.picked.clear();run(()=>loadSuggestions())})));
  const total=Object.values(d.kinds).reduce((a,b)=>a+b,0);$('s-kinds').replaceChildren(chip('All types ('+total+')',!s.kind,()=>{s.kind='';run(()=>loadSuggestions())}),...Object.keys(KIND).filter(k=>d.kinds[k]).map(k=>chip(KIND[k]+' ('+d.kinds[k]+')',s.kind===k,()=>{s.kind=k;run(()=>loadSuggestions())})));
  renderSuggestions();$('s-count').textContent='Showing '+s.rows.length+' of '+d.total;$('s-more').hidden=s.offset===null}
 // ---------- wiring ----------
 records=()=>loadReviews();
 $('tab-reviews').onclick=()=>tab('reviews');$('tab-ask').onclick=()=>{tab('ask');$('ask-q').focus()};
 const askHistory=[];const STARTERS=['What was blocked this week?',"What's waiting for me?",'Summarise yesterday\'s activity','Which model was slowest this week, and what did Temple cost?','What did Temple suggest from chats this month?'];
 function bubble(role,text,meta){const d=el('div','','ask-msg ask-'+role);d.append(el('div',role==='user'?'You':'Temple','t-label'),el('div',text,'t-body'));if(meta)d.append(meta);$('ask-log').append(d);d.scrollIntoView({block:'nearest'});return d}
 async function askTemple(q){q=q.trim();if(!q)return;$('ask-q').value='';bubble('user',q);const wait=bubble('temple','Looking…');$('ask-go').disabled=true;
  try{const r=await api('/admin/api/temple/ask','POST',{question:q,history:askHistory});wait.remove();
   let meta=null;if(r.looked_at.length){meta=document.createElement('details');meta.className='ask-looked';meta.append(el('summary','Checked: '+r.looked_at.length+(r.looked_at.length===1?' lookup':' lookups')+' · '+r.model));for(const x of r.looked_at)meta.append(el('div','• '+x,'small'))}
   bubble('temple',r.answer,meta);askHistory.push({role:'user',content:q},{role:'assistant',content:r.answer});if(askHistory.length>16)askHistory.splice(0,askHistory.length-16)}
  catch(e){wait.remove();bubble('temple','⚠ '+e.message)}finally{$('ask-go').disabled=false;$('ask-q').focus()}}
 $('ask-starters').replaceChildren(...STARTERS.map(q=>{const b=el('button',q,'chip');b.type='button';b.onclick=()=>run(()=>askTemple(q));return b}));
 $('ask-form').onsubmit=e=>{e.preventDefault();run(()=>askTemple($('ask-q').value))};
 $('ask-q').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('ask-form').requestSubmit()}};
 $('ask-clear').onclick=()=>{askHistory.length=0;$('ask-log').replaceChildren()};$('tab-suggestions').onclick=()=>{tab('suggestions');$('tab-suggestions').classList.remove('attention')};
 $('t-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{t.query=$('t-query').value.trim();run(()=>loadReviews())},300)};
 $('s-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{s.query=$('s-query').value.trim();run(()=>loadSuggestions())},300)};
 $('t-more').onclick=()=>run(()=>loadReviews(true));$('s-more').onclick=()=>run(()=>loadSuggestions(true));
 $('t-clear').onclick=()=>{t.picked.clear();renderReviews()};$('s-clear').onclick=()=>{s.picked.clear();renderSuggestions()};
 for(const [id,decision] of [['t-approve','approved'],['t-reject','rejected']])$(id).onclick=()=>run(async()=>{if(!confirm((decision==='approved'?'Approve':'Reject')+' '+t.picked.size+' selected? Items not awaiting a decision are skipped. Temple is advisory; this is your decision.'))return;const r=await api('/admin/api/memories/review','POST',{ids:[...t.picked],decision});$('notice').textContent=r.changed+' '+decision+(r.skipped?', '+r.skipped+' skipped':'')+(r.blocked?', '+r.blocked+' blocked by rules: '+r.block_reasons.join(' '):'')+'.';t.picked.clear();await loadReviews()});
 $('t-review').onclick=()=>run(async()=>{if(!confirm('Ask Temple to review '+t.picked.size+' selected proposals? Each review is a separate API call.'))return;const r=await api('/admin/api/temple/review-batch','POST',{ids:[...t.picked]});$('notice').textContent='Temple is reviewing '+r.started+' proposals. This page updates as they finish.';t.picked.clear();await loadReviews()});
 $('s-accept').onclick=()=>run(async()=>{const rows=s.rows.filter(r=>s.picked.has(r.id)&&!['accepted','dismissed'].includes(r.status));let ok=0;const errs=[];
  for(const r of rows){try{await api('/admin/api/temple-suggestions/'+r.id,'POST',{action:'accept',content:r.content});ok++}catch(e){errs.push(r.title+': '+e.message)}}
  $('notice').textContent=ok+(ok===1?' suggestion accepted':' suggestions accepted')+(rows.some(r=>r.kind==='memory'||r.kind==='decision')?'; memories and decisions are waiting in Memory reviews.':'.')+(errs.length?' Not accepted: '+errs.join(' · '):'');
  s.picked.clear();await loadSuggestions();loadReviews()});
 for(const [id,action] of [['s-later','later'],['s-dismiss','dismiss']])$(id).onclick=()=>run(async()=>{const r=await api('/admin/api/temple/suggestions/bulk','POST',{ids:[...s.picked],action});$('notice').textContent=r.done+(r.done===1?' suggestion ':' suggestions ')+(action==='later'?'moved to Later.':'dismissed.');s.picked.clear();await loadSuggestions()});
 $('temple-settings').onsubmit=e=>{e.preventDefault();run(async()=>{await api('/admin/api/temple/settings','PUT',{enabled:$('temple-enabled').checked,provider:$('temple-provider').value});$('notice').textContent='Temple settings saved.';await loadReviews()})};
 run(async()=>{const st=await api('/admin/api/temple/settings');$('temple-enabled').checked=st.enabled;$('temple-provider').value=st.provider;tab(({suggestions:'suggestions',ask:'ask'})[new URLSearchParams(location.search).get('tab')]||'reviews');await Promise.all([loadReviews(),loadSuggestions()])});
}
"""

SCRIPT += r'''
function decidedText(d){if(!d)return '';const L={record_approved:'Approved',record_rejected:'Rejected',friction_resolved:'Approved as a replacement',knowledge_approved:'Approved',knowledge_rejected:'Rejected',org_fact_approved:'Approved',org_fact_rejected:'Rejected',org_fact_added:'Added',memory_retired:'Retired',memory_superseded:'Replaced'};
 return (L[d.action]||d.action)+' by '+(d.actor||'(not recorded)')+' on '+new Date(d.at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})+(d.note?' · “'+d.note+'”':'')}
function ownerEditor(current,label,save){const row=el('div','','cat-edit');const i=document.createElement('input');i.value=current||'';i.maxLength=80;i.placeholder='Owner: a person\'s name';i.setAttribute('list','owner-list');i.setAttribute('aria-label','Owner of '+label);
 const b=el('button','Save owner');b.className='secondary';b.type='button';b.onclick=()=>run(async()=>{await save(i.value.trim());$('notice').textContent=i.value.trim()?'Owner set to '+i.value.trim()+'.':'Owner removed.'});const l=el('label','Owner ');l.append(i);row.append(l,b,el('span','Shown when its review date passes. Never sent to a model.','muted small'));return row}
function fillOwners(sel,owners,value){if(sel){sel.replaceChildren();for(const [v,t] of [['','Anyone'],['__none__','No owner'],...owners.map(o=>[o,o])]){const x=document.createElement('option');x.value=v;x.textContent=t;sel.append(x)}sel.value=value||''}
 const dl=$('owner-list');if(dl)dl.replaceChildren(...owners.map(o=>{const x=document.createElement('option');x.value=o;return x}))}
function askReason(decision){if(decision!=='rejected')return '';const r=prompt('Why reject it? Optional; kept in the activity log.');return r===null?null:r.trim()}
'''
SCRIPT += "\nfunction memoryControls(record){\n const wrap=el('div','');\n const historyButton=el('button','View memory history');historyButton.className='secondary';\n historyButton.onclick=()=>run(async()=>{const items=await api('/admin/api/records/'+record.id+'/history');const box=el('div','');for(const item of items){box.append(el('h4',item.title+' · '+item.status),el('pre',item.content),el('p','Source: '+item.source));if(item.reason)box.append(el('p','Reason: '+item.reason));for(const event of item.events)box.append(el('p',event.created_at+' · '+event.action+' · '+event.detail,'muted'));}historyBody.replaceChildren(el('summary','Memory history'),box);historyBody.open=true;});\n const historyBody=document.createElement('details');historyBody.append(el('summary','History'));\n wrap.append(historyButton,historyBody);\n async function reload(){if(PAGE==='memories')await records();else location.reload();}\n if(record.status==='approved'){const retire=el('button','Retire memory');retire.className='secondary';retire.onclick=()=>run(async()=>{const reason=prompt('Why is this memory no longer relevant?');if(!reason||!reason.trim())return;if(!confirm('Retire “'+record.title+'”? It will stop appearing in active memory searches, but its history remains.'))return;await api('/admin/api/records/'+record.id+'/retire','POST',{reason});await reload()});wrap.append(retire);}\n if(record.status==='proposed'){\n const open=el('button','Resolve friction / replace');const form=el('div','');\n open.onclick=()=>run(async()=>{open.disabled=true;try{let offset=0,all=[];do{const data=await api('/admin/api/records?status=approved&offset='+offset);all.push(...data.records);offset=data.next_offset;}while(offset!==null);form.replaceChildren();if(!all.length){form.textContent='No active approved memory to replace.';return;}\n form.append(el('h4','Resolve friction'),el('p','Choose the current memory this proposal replaces. Approval and replacement happen together.'));\n const choose=document.createElement('select');choose.setAttribute('aria-label','Memory to replace');choose.style.maxWidth='100%';const initial=document.createElement('option');initial.value='';initial.textContent='Choose an active memory…';choose.append(initial);for(const m of all){const o=document.createElement('option');o.value=m.id;o.textContent=m.title+' · '+m.id.slice(0,8);choose.append(o)}\n const preview=el('pre','');choose.onchange=()=>{const old=all.find(m=>m.id===choose.value);preview.textContent=old?'CURRENT: '+old.content+'\\n\\nSource: '+old.source+'\\n\\nREPLACEMENT: '+record.content:''};const reason=document.createElement('textarea');reason.maxLength=2000;reason.placeholder='Why should this replace the current memory?';reason.setAttribute('aria-label','Friction resolution reason');\n const submit=el('button','Approve as replacement');submit.onclick=()=>run(async()=>{if(!choose.value||!reason.value.trim())throw Error('Select a memory and enter a reason.');if(!confirm('Approve this proposal and supersede the selected memory?'))return;submit.disabled=true;try{await api('/admin/api/records/'+record.id+'/replace','POST',{old_id:choose.value,reason:reason.value});await reload()}finally{submit.disabled=false}});\n form.append(choose,preview,reason,submit);\n }finally{open.disabled=false}});wrap.append(open,form);\n }\n return wrap;\n}\n"

SCRIPT += r"""
if(PAGE==='usage'){
 const usd=v=>v===null||v===undefined?'—':'$'+(Math.abs(v)<0.01&&v!==0?v.toFixed(4):v.toFixed(2));
 const num=v=>v===null||v===undefined?'—':Number(v).toLocaleString('en-GB');
 const names={'gpt-6-luna':'GPT-6 Luna','grok-4.7':'Grok 4.7','claude-opus-5-5':'Opus 5.5','claude-sonnet-5-5':'Sonnet 5.5','claude-haiku-4-5-20251001':'Haiku 4.5','scribe_v2':'ElevenLabs Scribe v2','eleven_multilingual_v2':'ElevenLabs Multilingual v2'};
 const special=x=>x.workload==='Image generation'?x.images+' images':x.workload==='Voice output'?num(x.characters)+' characters':x.workload==='Voice input'?num(x.calls)+' recordings':null;
 function table(id,head,rows,numeric,foot){const t=$(id);t.replaceChildren();const h=document.createElement('thead'),tr=document.createElement('tr');
  head.forEach((x,i)=>{const th=el('th',x);th.scope='col';if(numeric.includes(i))th.className='num';tr.append(th)});h.append(tr);t.append(h);
  const b=document.createElement('tbody');for(const r of rows){const row=document.createElement('tr');r.forEach((x,i)=>{const td=x instanceof Node?document.createElement('td'):el('td',x);if(x instanceof Node)td.append(x);if(numeric.includes(i))td.className='num';row.append(td)});b.append(row)}
  if(!rows.length){const row=document.createElement('tr'),td=el('td','No usage in this period.','muted');td.colSpan=head.length;row.append(td);b.append(row)}t.append(b);
  if(foot){const f=document.createElement('tfoot'),row=document.createElement('tr');foot.forEach((x,i)=>{const td=el('td',x);if(numeric.includes(i))td.className='num';row.append(td)});f.append(row);t.append(f)}}
 function stat(value,label){const s=el('div','','stat');s.append(el('strong',value),el('span',label));return s}
 async function usage(){const d=await api('/admin/api/usage?period='+$('usage-period').value),t=d.totals;
  $('usage-stats').replaceChildren(stat(usd(t.estimate_usd),'Estimated cost'),stat(usd(t.saved_usd),'Estimated savings'),stat(num(t.calls),'API calls'),stat(num(t.images),'Images generated'));
  $('usage-caveat').textContent=(t.saved_usd>0?'Without optimisations this period would have cost about '+usd(t.without_usd)+'. ':'')+(t.unpriced_calls?t.unpriced_calls+' calls have no price yet (image generation, and ElevenLabs voice, which uses your plan credits), so the true cost is higher than shown.':'All logged calls in this period are priced.');
  const g=d.groups;const secs=x=>x==null?'—':x+' s';table('usage-groups',['Model','Workload','Calls','Input tokens','Cached','Output tokens','Avg / slowest','Est. cost'],
   g.map(x=>[names[x.model]||x.model,x.workload,num(x.calls),special(x)??num(x.input_tokens),special(x)?'—':num(x.cache_read_tokens),special(x)?'—':num(x.output_tokens),x.avg_seconds==null?'—':secs(x.avg_seconds)+' / '+secs(x.max_seconds),x.unpriced_calls===x.calls?'Unpriced':usd(x.estimate_usd)]),[2,3,4,5,6,7],
   ['Total','',num(t.calls),num(g.reduce((a,x)=>a+x.input_tokens,0)),num(g.reduce((a,x)=>a+x.cache_read_tokens,0)),num(g.reduce((a,x)=>a+x.output_tokens,0)),'',usd(t.estimate_usd)]);
  table('usage-savings',['Optimisation','Status','What it does','Est. saving'],d.savings.map(s=>[s.name,s.status,s.detail,s.saving===null?'Not measured':usd(s.saving)]),[3],['Total','','',usd(t.saved_usd)]);
  const peak=Math.max(0.000001,...d.days.map(x=>x.estimate_usd));
  table('usage-days',['Date','Calls','Est. cost',''],d.days.map(x=>{const bar=el('span','','bar');bar.style.width=(x.estimate_usd/peak*100)+'%';bar.setAttribute('aria-hidden','true');return[x.date,num(x.calls),usd(x.estimate_usd),bar]}),[1,2]);
  table('usage-recent',['Time (UTC)','Workload','Model','Input','Output','Took','Est. cost'],d.recent.map(r=>[r.created_at.slice(0,19).replace('T',' '),r.workload,names[r.model]||r.model,num(r.input_tokens),num(r.output_tokens),secs(r.seconds),r.estimate_usd===null?'Unpriced':usd(r.estimate_usd)]),[3,4,5,6]);}
 $('grok-check').onclick=()=>run(async()=>{const b=$('grok-check');b.disabled=true;$('grok-check-result').textContent='Connecting…';try{const r=await api('/admin/api/grok/check','POST',{});$('grok-check-result').textContent=r.message;await usage()}catch(e){$('grok-check-result').textContent=e.message}finally{b.disabled=false}});
 $('prov-check').onclick=()=>run(async()=>{const b=$('prov-check');b.disabled=true;$('prov-results').replaceChildren(el('p','Checking…','small'));
  try{const r=await api('/admin/api/providers/check','POST',{});$('prov-results').replaceChildren(...r.results.map(x=>{const row=el('div','','act-row');const t=el('div','','act-text');t.append(el('strong',x.provider+' · '+x.model),el('div',x.message,'small'));row.append(t,el('span',x.ok?'Connected':'Problem','badge '+(x.ok?'v-ok':'v-bad')));return row}));await usage()}
  catch(e){$('prov-results').replaceChildren(el('p',e.message,'small'))}finally{b.disabled=false}});
 $('usage-refresh').onclick=()=>run(usage);$('usage-period').onchange=()=>run(usage);run(usage);
}
"""



SCRIPT += r"""
if(PAGE==='organisations'){
 const store=(k,v)=>{try{if(v===undefined)return JSON.parse(localStorage.getItem(k)||'null');localStorage.setItem(k,JSON.stringify(v))}catch{return null}};
 const DEMO_ORG=DEMO||store('alice-org-demo')===true;window.ALICE_DATASET=DEMO_ORG?'demo':'live';
 const st={org:'',status:'approved',L:null,opps:[],filter:store('alice-org-filter')||'all',kind:'',mgr:'',q:'',groups:store('alice-org-groups')||{},secs:store('alice-org-secs')||{}};
 const KL={general:'General',internal:'Internal',client:'Client-confidential',local:'Local only'};
 const KN={council:'Councils',police:'Police',university:'Universities',college:'Colleges','public body':'Public bodies',health:'Health',company:'Companies',charity:'Charities',other:'Other'};
 const OPEN=['suggested','tracking','pursuing'];
 function opts(sel,list,val){sel.replaceChildren();for(const [v,t] of list){const o=document.createElement('option');o.value=v;o.textContent=t;sel.append(o)}if(val!==undefined&&val!==null)sel.value=val}
 function hint(){const s=st.L.sections.find(x=>x.key===$('f-section').value);$('f-hint').textContent=s?s.hint:''}
 const attention=o=>o.facts.proposed>0||o.facts.due>0;
 const openOpps=name=>st.opps.filter(x=>x.org.toLowerCase()===name.toLowerCase()&&OPEN.includes(x.status));
 const domain=u=>(u||'').replace(/^https?:\/\/(www\.)?/i,'').split('/')[0];
 $('o-demo').checked=DEMO_ORG;$('o-demo').disabled=DEMO;if(DEMO)$('o-demo').parentElement.title='Demo mode is on for the whole command centre';
 $('o-demo-bar').hidden=!DEMO_ORG;for(const id of ['o-research','o-opp-scan','o-r-go'])$(id).disabled=DEMO_ORG;
 if(DEMO_ORG){$('o-research').title=$('o-opp-scan').title=$('o-r-go').title='Off for demo data: no web searches or model calls.'}
 $('o-demo').onchange=()=>{store('alice-org-demo',$('o-demo').checked);const u=new URL(location.href);u.searchParams.delete('org');location.href=u.href};
 $('o-demo-reset').onclick=()=>run(async()=>{if(!confirm('Rebuild the demo data? Changes you made to the demo organisations are lost. Your real data is not touched.'))return;await api('/admin/api/demo-data/reset','POST');$('notice').textContent='Demo data rebuilt.';st.org='';await load()});
 function renderFilters(){const L=st.L.organisations;const n={all:L.length,clients:L.filter(o=>o.is_client).length,attention:L.filter(attention).length,opps:L.filter(o=>openOpps(o.name).length).length};
  $('o-filter').replaceChildren(...[['all','All'],['clients','Clients'],['attention','Needs attention'],['opps','Open opportunities']].map(([k,l])=>{const b=el('button',l+' ('+n[k]+')','chip'+(st.filter===k?' on':'')+(k==='attention'&&n[k]&&st.filter!==k?' attention':''));b.type='button';b.onclick=()=>{st.filter=k;store('alice-org-filter',k);renderList()};return b}));
  opts($('o-f-kind'),[['','All types'],...st.L.kinds.map(k=>[k,KN[k]||k])],st.kind);
  opts($('o-f-mgr'),[['','All account managers'],...st.L.managers.map(m=>[m,m]),['-','Unassigned']],st.mgr)}
 function matches(o){if(st.filter==='clients'&&!o.is_client)return false;if(st.filter==='attention'&&!attention(o))return false;if(st.filter==='opps'&&!openOpps(o.name).length)return false;
  if(st.kind&&o.kind!==st.kind)return false;if(st.mgr==='-'&&o.account_manager)return false;if(st.mgr&&st.mgr!=='-'&&o.account_manager!==st.mgr)return false;
  if(st.q){const hay=(o.name+' '+(o.account_manager||'')+' '+(o.website||'')+' '+(o.description||'')).toLowerCase();if(!st.q.split(/\s+/).every(w=>hay.includes(w)))return false}return true}
 function item(o){const b=el('button','','o-item'+(st.org===o.name?' on':''));b.type='button';b.append(el('span',o.name,'o-name'));const sub=el('span','','o-sub');
  if(o.is_client)sub.append(el('span','Client','o-flag cl'));sub.append(el('span',o.facts.approved+(o.facts.approved===1?' fact':' facts')));
  if(o.facts.proposed)sub.append(el('span',o.facts.proposed+' to approve','o-flag'));if(o.facts.due)sub.append(el('span',o.facts.due+' overdue','o-flag'));
  const op=openOpps(o.name).length;if(op)sub.append(el('span',op+(op===1?' opportunity':' opportunities'),'o-flag o-opp'));if(o.account_manager)sub.append(el('span',o.account_manager));
  b.append(sub);b.onclick=()=>{st.org=o.name;st.status='approved';history.replaceState(null,'','?org='+encodeURIComponent(o.name));run(load)};return b}
 function renderList(){renderFilters();const rows=st.L.organisations.filter(matches);const box=$('o-list');box.replaceChildren();
  $('o-summary').textContent=(rows.length===st.L.organisations.length?'':rows.length+' of ')+st.L.organisations.length+(st.L.organisations.length===1?' organisation':' organisations');
  if(!st.L.organisations.length){box.append(el('p','No organisations yet. Use + Add.','muted small'));return}
  if(!rows.length){box.append(el('p','Nothing matches.','muted small'));return}
  const groups={};for(const o of rows)(groups[o.kind]=groups[o.kind]||[]).push(o);
  for(const k of [...st.L.kinds,...Object.keys(groups).filter(x=>!st.L.kinds.includes(x))]){const g=groups[k];if(!g)continue;
   const d=el('details','','o-group');d.open=!!st.q||st.groups[k]!==false||g.some(o=>o.name===st.org);
   const sm=el('summary','');sm.append(el('span',KN[k]||k),el('span',String(g.length)+(g.filter(attention).length?' · '+g.filter(attention).length+' need attention':''),'o-sum'));d.append(sm);
   d.ontoggle=()=>{if(st.q)return;st.groups[k]=d.open;store('alice-org-groups',st.groups)};for(const o of g)d.append(item(o));box.append(d)}}
 $('o-search').oninput=()=>{st.q=$('o-search').value.trim().toLowerCase();renderList()};
 $('o-f-kind').onchange=()=>{st.kind=$('o-f-kind').value;renderList()};$('o-f-mgr').onchange=()=>{st.mgr=$('o-f-mgr').value;renderList()};
 document.querySelectorAll('.o-sec[data-sec]').forEach(d=>{const k=d.dataset.sec;if(k in st.secs)d.open=st.secs[k];d.addEventListener('toggle',()=>{st.secs[k]=d.open;store('alice-org-secs',st.secs)})});
 function initTagging(){
 const st={type:'memory',client:'__general__',query:'',offset:0,rows:[],picked:new Set()};let names=[],timer=null;
 const BY={human:'Set by you',chat:'Inherited from its chat',alias:'Name match',temple:'Set by Temple'};
 function fill(sel,value){sel.replaceChildren();const g=document.createElement('option');g.value='';g.textContent='General (no client)';sel.append(g);for(const n of names){const o=document.createElement('option');o.value=o.textContent=n;sel.append(o)}sel.value=names.includes(value)?value:''}
 function chip(text,active,onclick,cls=''){const b=el('button',text,'chip'+(active?' on':'')+(cls?' '+cls:''));b.type='button';b.onclick=onclick;return b}
 async function loadClients(){const d=await api('/admin/api/clients');names=d.clients.map(c=>c.name);
  $('c-summary').textContent=d.clients.length+(d.clients.length===1?' client':' clients')+' · separation '+(d.settings.enabled?(d.settings.strict?'on, strict':'on'):'off')+' · external apps see '+(d.settings.external==='general'?'General only':'all material')+(d.untagged.memory+d.untagged.file?' · '+(d.untagged.memory+d.untagged.file)+' untagged':'')+((d.suggested.memory+d.suggested.file)?' · '+(d.suggested.memory+d.suggested.file)+' suggestions':'');
  fill($('c-bulk-client'),$('c-bulk-client').value);return d}
 function render(){const t=$('c-table');t.replaceChildren();const h=document.createElement('thead'),hr=document.createElement('tr');const all=document.createElement('input');all.type='checkbox';all.setAttribute('aria-label','Select all shown');all.checked=st.rows.length>0&&st.rows.every(r=>st.picked.has(r.id));all.onchange=()=>{for(const r of st.rows)all.checked?st.picked.add(r.id):st.picked.delete(r.id);render()};const th0=document.createElement('th');th0.append(all);hr.append(th0);for(const x of [st.type==='memory'?'Memory':'File','Client','Change']){const th=el('th',x);th.scope='col';hr.append(th)}h.append(hr);t.append(h);
  const b=document.createElement('tbody');if(!st.rows.length){const tr=document.createElement('tr'),td=el('td','Nothing here.','muted');td.colSpan=4;tr.append(td);b.append(tr)}
  for(const r of st.rows){const tr=document.createElement('tr');tr.className='mem-row';const c0=document.createElement('td');const cb=document.createElement('input');cb.type='checkbox';cb.checked=st.picked.has(r.id);cb.setAttribute('aria-label','Select '+r.title);cb.onchange=()=>{cb.checked?st.picked.add(r.id):st.picked.delete(r.id);bulk()};c0.append(cb);
   const c1=document.createElement('td');c1.append(el('strong',r.title),el('div',(r.preview||'').replace(/\s+/g,' ').slice(0,150),'mem-preview'));
   const c2=document.createElement('td');if(r.client){c2.append(el('span',r.client,'tag k-knowledge'),el('div',(BY[r.assigned_by]||r.assigned_by)+(r.confidence!=null&&r.assigned_by==='temple'?' · '+Math.round(r.confidence*100)+'%':''),'muted small'))}else c2.append(el('span','General','muted'));
   if(r.suggestion){const sg=el('div','','suggest');sg.append(el('span','Suggested: '+r.suggestion+(r.confidence!=null?' · '+Math.round(r.confidence*100)+'%':''),'small'));if(r.suggestion_reason)sg.title=r.suggestion_reason;for(const [lab,action] of [['✓','accept'],['✕','dismiss']]){const bt=el('button',lab,'mini');bt.type='button';bt.setAttribute('aria-label',(action==='accept'?'Accept ':'Dismiss ')+r.suggestion+' for '+r.title);bt.onclick=()=>run(async()=>{await api('/admin/api/clients/suggestions','POST',{items:[{type:st.type,id:r.id}],action});await loadClients();await load()});sg.append(bt)}c2.append(sg)}
   const c3=document.createElement('td');const sel=document.createElement('select');fill(sel,r.client);sel.setAttribute('aria-label','Client for '+r.title);sel.onchange=()=>run(async()=>{await api('/admin/api/clients/tag','POST',{type:st.type,ids:[r.id],client:sel.value});$('notice').textContent=r.title+' → '+(sel.value||'General')+'.';await loadClients();await load()});c3.append(sel);
   tr.append(c0,c1,c2,c3);b.append(tr)}t.append(b);bulk()}
 function bulk(){$('c-bulk').hidden=!st.picked.size;$('c-selected').textContent=st.picked.size+' selected';$('c-accept').hidden=!st.rows.some(r=>st.picked.has(r.id)&&r.suggestion)}
 async function load(more=false){const d=await api('/admin/api/clients/items?type='+st.type+'&client='+encodeURIComponent(st.client)+'&query='+encodeURIComponent(st.query)+'&offset='+(more?st.offset:0));st.rows=more?st.rows.concat(d.items):d.items;st.offset=d.next_offset;
  const f=[chip('General · untagged ('+(d.counts.__general__||0)+')',st.client==='__general__',()=>{st.client='__general__';run(()=>load())})];if(d.counts.__suggested__)f.push(chip('✦ Temple suggestions ('+d.counts.__suggested__+')',st.client==='__suggested__',()=>{st.client='__suggested__';run(()=>load())},'attention'));
  for(const n of names)f.push(chip(n+' ('+(d.counts[n]||0)+')',st.client===n,()=>{st.client=n;run(()=>load())}));f.push(chip('Everything',st.client==='',()=>{st.client='';run(()=>load())}));$('c-filters').replaceChildren(...f);
  render();$('c-count').textContent='Showing '+st.rows.length+' of '+d.total;$('c-more').hidden=st.offset===null}
 for(const t of ['memory','file'])$('c-tab-'+t).onclick=()=>{st.type=t;st.picked.clear();for(const x of ['memory','file'])$('c-tab-'+x).classList.toggle('on',x===t);run(()=>load())};
 $('c-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{st.query=$('c-query').value.trim();run(()=>load())},300)};
 $('c-more').onclick=()=>run(()=>load(true));$('c-clear').onclick=()=>{st.picked.clear();render()};
 $('c-set').onclick=()=>run(async()=>{const r=await api('/admin/api/clients/tag','POST',{type:st.type,ids:[...st.picked],client:$('c-bulk-client').value});$('notice').textContent=r.updated+' set to '+(r.client||'General')+'.';st.picked.clear();await loadClients();await load()});
 $('c-accept').onclick=()=>run(async()=>{const r=await api('/admin/api/clients/suggestions','POST',{items:[...st.picked].map(id=>({type:st.type,id})),action:'accept'});$('notice').textContent=r.done+' suggestions accepted.';st.picked.clear();await loadClients();await load()});
 $('c-run').onclick=()=>run(async()=>{const b=$('c-run');b.disabled=true;$('c-run-result').textContent='Matching names, then asking Temple about the rest…';try{const r=await api('/admin/api/clients/temple-run','POST',{});$('c-run-result').textContent=r.status==='no_clients'?'Add a client first.':r.status==='busy'?'Tagging is already running.':(r.status==='paused'?r.message+' ':'')+'Checked '+r.checked+': '+r.applied+' tagged ('+r.by_alias+' by name match), '+r.suggested+' suggested; the rest stay General.';await loadClients();await load()}catch(e){$('c-run-result').textContent=e.message}finally{b.disabled=false}});
 return {refresh:async()=>{await loadClients();await load()},show:async(name,type)=>{st.client=name;if(type){st.type=type;for(const x of ['memory','file'])$('c-tab-'+x).classList.toggle('on',x===type)}st.picked.clear();await loadClients();await load()}}}
 function showAdd(on){$('o-add').hidden=!on;if(on){$('o-add').scrollIntoView({block:'start',behavior:'smooth'});$('o-r-name').focus()}}
 $('o-add-toggle').onclick=()=>showAdd($('o-add').hidden);$('o-add-close').onclick=()=>showAdd(false);
 async function loadList(){const [L,O]=await Promise.all([api('/admin/api/organisations'),api('/admin/api/opportunities').catch(()=>({opportunities:[]}))]);st.L=L;st.opps=O.opportunities||[];
  if(st.org&&!L.organisations.some(o=>o.name===st.org))st.org='';
  $('o-mgr-list').replaceChildren(...L.managers.map(m=>{const o=document.createElement('option');o.value=m;return o}));
  opts($('o-new-kind'),L.kinds.map(k=>[k,k]),$('o-new-kind').value||'other');opts($('o-kind'),L.kinds.map(k=>[k,k]));
  opts($('f-section'),L.sections.map(s=>[s.key,s.name]),$('f-section').value||'identity');opts($('f-label'),Object.entries(KL),$('f-label').value||'general');
  opts($('b-provider'),[['claude','Claude'],['openai','GPT-6 Luna'],['grok','Grok'],['copilot','Microsoft Copilot']],$('b-provider').value||'claude');hint();renderList()}
 function miniOpps(o){const rows=openOpps(o.name);const all=st.opps.filter(x=>x.org.toLowerCase()===o.name.toLowerCase());const box=$('o-opp-mini');box.replaceChildren();
  $('o-sum-opps').textContent=rows.length?rows.length+' open':(all.length?'none open · '+all.length+' closed':'none yet');
  if(!rows.length)box.append(el('p',all.length?'No open opportunities. Closed ones are in the tracker.':'None yet. Scan for opportunities above, or set a schedule.','muted small'));
  const SL={suggested:'Suggested',tracking:'Tracking',pursuing:'Pursuing'};
  for(const x of rows){const r=el('div','','o-mini');r.append(el('span',SL[x.status],'badge v-'+({suggested:'warn',pursuing:'run'}[x.status]||'none')),el('strong',x.title));
   if(x.offering)r.append(el('span',x.offering,'tag know'));if(x.confidence!==null&&x.confidence!==undefined)r.append(el('span',Math.round(x.confidence*100)+'%','small muted'));box.append(r)}}
 async function load(){await loadList();const o=st.L.organisations.find(x=>x.name===st.org);$('o-detail').hidden=!o;$('o-empty').hidden=!!o;if(!o)return;
  $('o-title').textContent=o.name;const meta=$('o-meta');meta.replaceChildren();
  if(o.is_client)meta.append(el('span','Client','o-flag cl'));meta.append(el('span',o.kind));meta.append(el('span',o.account_manager?'Account manager: '+o.account_manager:'No account manager','muted'));
  if(o.website){const a=link(o.website,domain(o.website));meta.append(a)}
  $('o-kind').value=o.kind;$('o-mgr').value=o.account_manager||'';$('o-client').checked=o.is_client;$('o-aliases').value=(o.aliases||[]).join(', ');$('o-aliases-wrap').hidden=!o.is_client;
  const tg=o.tagged;$('o-tagged-sec').hidden=!o.is_client||DEMO_ORG;if(tg){const parts=[[tg.memories,'memory','memories'],[tg.files,'file','files'],[tg.chats,'chat','chats']].map(([n,a,b])=>n+' '+(n===1?a:b));$('o-sum-tagged').textContent=parts.join(' · ');$('o-tagged-text').textContent=(tg.memories+tg.files+tg.chats)?'Tagged to '+o.name+': '+parts.join(', ')+'. In a chat for another client these are kept out.':'Nothing is tagged to '+o.name+' yet. Run Temple tagging, or tag a chat with this client.'}
$('o-desc').value=o.description||'';$('o-web').value=o.website||'';
  $('o-sum-details').textContent=[o.kind,o.account_manager||'no account manager',domain(o.website)].filter(Boolean).join(' · ');miniOpps(o);
  const rs=await api('/admin/api/organisations/research?org='+encodeURIComponent(st.org)).then(x=>x.runs).catch(()=>[]);runs(rs);
  $('o-sum-research').textContent=rs.length?'last '+new Date(rs[0].created_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}):'not researched yet';
  const d=await api('/admin/api/organisations/facts?org='+encodeURIComponent(st.org)+'&status=all');const counts={};for(const f of d.facts)counts[f.status]=(counts[f.status]||0)+1;
  $('o-sum-facts').textContent=(counts.approved||0)+' approved'+(counts.proposed?' · '+counts.proposed+' to approve':'')+(o.facts.due?' · '+o.facts.due+' overdue':'');
  $('o-status').replaceChildren(...[['approved','Approved'],['proposed','Awaiting approval'],['retired','Retired'],['rejected','Rejected']].map(([k,l])=>{const b=el('button',l+' ('+(counts[k]||0)+')','chip'+(st.status===k?' on':'')+(k==='proposed'&&counts[k]&&st.status!==k?' attention':''));b.type='button';b.onclick=()=>{st.status=k;run(load)};return b}));
  const names=Object.fromEntries(st.L.sections.map(s=>[s.key,s.name]));const box=$('o-facts');box.replaceChildren();const rows=d.facts.filter(f=>f.status===st.status);
  if(!rows.length)box.append(el('p',st.status==='approved'?'No approved facts yet. Research online above, or open Add a fact.':'None.','muted'));
  if(st.status==='proposed'&&rows.length>1){const bar=el('div','','arc-actions');const all=el('button','Approve all '+rows.length,'mini-act');all.type='button';all.title='Approve every fact shown. The rules are checked again for each.';
   all.onclick=()=>run(async()=>{if(!confirm('Approve all '+rows.length+' proposed facts? Check the sources first.'))return;const x=await api('/admin/api/organisations/facts/review','POST',{ids:rows.map(f=>f.id),decision:'approved'});$('notice').textContent=x.changed+' approved'+(x.blocked?'; '+x.blocked+' blocked: '+x.block_reasons.join(' '):'.');await load()});
   const rej=el('button','Reject all','secondary mini-act');rej.type='button';rej.onclick=()=>run(async()=>{if(!confirm('Reject all '+rows.length+' proposed facts?'))return;await api('/admin/api/organisations/facts/review','POST',{ids:rows.map(f=>f.id),decision:'rejected'});$('notice').textContent='Rejected.';await load()});bar.append(all,rej);box.append(bar)}
  const bySec={};for(const f of rows)(bySec[f.section]=bySec[f.section]||[]).push(f);
  for(const [sec,list] of Object.entries(bySec)){const fs=el('details','','o-fsec');fs.open=true;const sm=el('summary',names[sec]||sec);const due=list.filter(f=>f.overdue).length;sm.append(el('span',list.length+(due?' · '+due+' overdue':''),'o-sum'));fs.append(sm);
   for(const f of list){const row=el('div','','act-row');const txt=el('div','','act-text');txt.append(el('div',f.statement));
    const meta=el('div','Source: '+f.source_system+' · ','small muted');if(f.source_ref&&/^https?:\/\//i.test(f.source_ref))meta.append(link(f.source_ref,f.source_ref.replace(/^https?:\/\/(www\.)?/i,'').slice(0,80)),document.createTextNode(' · '));else if(f.source_ref)meta.append(document.createTextNode(f.source_ref+' · '));
    meta.append(document.createTextNode('as of '+f.as_of+' · review by '+f.review_by+' · '+KL[f.label]+' · '+f.proposed_by));txt.append(meta);
    if(f.overdue)txt.append(el('span','⚑ Review overdue','flag'));if(f.retired_reason)txt.append(el('div','Retired: '+f.retired_reason,'small'));
    const act=el('div','','act-buttons');
    if(f.status==='proposed')for(const [l,dec] of [['Approve','approved'],['Reject','rejected']]){const b=el('button',l,dec==='rejected'?'secondary mini-act':'mini-act');b.type='button';b.onclick=()=>run(async()=>{const x=await api('/admin/api/organisations/facts/review','POST',{ids:[f.id],decision:dec});$('notice').textContent=x.blocked?x.block_reasons.join(' '):(dec==='approved'?'Approved.':'Rejected.');await load()});act.append(b)}
    if(f.status==='approved'){const rb=document.createElement('input');rb.type='date';rb.value=f.review_by;rb.setAttribute('aria-label','Review by');const sv=el('button','Set review date','secondary mini-act');sv.type='button';sv.onclick=()=>run(async()=>{await api('/admin/api/organisations/facts/'+f.id,'PUT',{review_by:rb.value});$('notice').textContent='Review date saved.';await load()});
     const rt=el('button','Retire','secondary mini-act');rt.type='button';rt.onclick=()=>run(async()=>{const reason=prompt('Why is this fact no longer right?');if(!reason||!reason.trim())return;await api('/admin/api/organisations/facts/'+f.id+'/retire','POST',{reason});$('notice').textContent='Retired.';await load()});act.append(rb,sv,rt)}
    row.append(txt,act);fs.append(row)}box.append(fs)}
  $('b-text').textContent='';const w=OT.data&&OT.data.watch.find(x=>x.org===st.org);$('o-opp-freq').value=w?w.frequency:'off'}
 function link(href,text){const a=el('a',text,'src-link');a.href=href;a.target='_blank';a.rel='noopener noreferrer';return a}
 function runs(list){const box=$('o-research-box');box.replaceChildren();if(!list.length){box.append(el('p','Not researched yet. Use Research online at the top.','muted small'));return}const r=list[0];
  const d=el('div','','o-run');d.append(el('p','Last researched '+new Date(r.created_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+': '+(r.status==='complete'?r.summary:'failed ('+r.error+')')));
  const cited=r.sources.filter(x=>x.cited),other=r.sources.filter(x=>!x.cited);
  if(cited.length){d.append(el('div','Sources cited by the proposed facts','small'));const ol=el('ol','');cited.forEach(x=>{const li=el('li','');li.append(link(x.url,x.title||x.url),el('span',' · '+domain(x.url),'muted small'));ol.append(li)});d.append(ol)}
  if(other.length){const o=el('details','');o.append(el('summary','Also consulted ('+other.length+')','small'));const ol=el('ol','uncited');other.forEach(x=>{const li=el('li','');li.append(link(x.url,x.title||x.url));ol.append(li)});o.append(ol);d.append(o)}
  if(r.dropped.length){const o=el('details','');o.append(el('summary','Dropped ('+r.dropped.length+')','small'));const ul=el('ul','');r.dropped.forEach(x=>ul.append(el('li',x.statement+' — '+x.reason)));o.append(ul);d.append(o)}
  box.append(d)}
 async function research(name,website,statusEl,btn){btn.disabled=true;statusEl.className='muted small o-busy';statusEl.textContent='Temple is searching the web. This usually takes under a minute…';
  try{const x=await api('/admin/api/organisations/research','POST',{name,website});st.org=x.org;st.status='proposed';statusEl.className='muted small';statusEl.textContent='';showAdd(false);
   $('notice').textContent=x.org+': '+x.summary+'. Check the sources, then approve the facts you want to keep.';await load();$('o-detail').scrollIntoView({block:'start',behavior:'smooth'})}
  catch(e){statusEl.className='muted small';statusEl.textContent=e.message}finally{btn.disabled=DEMO_ORG}}
 $('o-r-go').onclick=()=>{const n=$('o-r-name').value.trim(),w=$('o-r-web').value.trim();if(!n&&!w){$('o-r-status').textContent='Type a name or a website.';return}research(n,w,$('o-r-status'),$('o-r-go')).then(()=>{$('o-r-name').value=$('o-r-web').value=''})};
 $('o-research').onclick=()=>research(st.org,$('o-web').value.trim(),$('o-research-status'),$('o-research'));
 $('f-section').onchange=hint;$('f-statement').oninput=()=>{$('f-count').textContent=$('f-statement').value.length+' / 400'};
 $('o-new-save').onclick=()=>run(async()=>{const x=await api('/admin/api/organisations','POST',{name:$('o-new-name').value,kind:$('o-new-kind').value,description:$('o-new-desc').value,client:$('o-new-client').checked});st.org=x.name;$('o-new-name').value=$('o-new-desc').value='';$('o-new-client').checked=false;if(TAG&&x.client)await TAG.refresh();$('notice').textContent='Added '+x.name+'.';showAdd(false);await load()});
 $('o-client').onchange=()=>{$('o-aliases-wrap').hidden=!$('o-client').checked};
 $('o-save').onclick=()=>run(async()=>{const o=st.L.organisations.find(x=>x.name===st.org);const cl=$('o-client').checked;
  if(o&&o.is_client&&!cl){const tg=o.tagged||{memories:0,files:0,chats:0};if(!confirm('Stop treating '+o.name+' as a client? Its '+tg.memories+' memories, '+tg.files+' files and '+tg.chats+' chats become General, visible in every chat including other clients\' chats.'))return}
  const x=await api('/admin/api/organisations','PUT',{name:st.org,kind:$('o-kind').value,description:$('o-desc').value,website:$('o-web').value.trim(),account_manager:$('o-mgr').value.trim(),client:cl,aliases:cl?$('o-aliases').value.split(','):null});
  $('notice').textContent=x.no_longer_client?st.org+' is no longer a client; '+x.no_longer_client.items+' items and '+x.no_longer_client.chats+' chats are now General.':(o&&!o.is_client&&cl?st.org+' is now a client. Run Temple tagging below to tag existing material.':'Saved.');await load();if(TAG)await TAG.refresh()});
 $('o-tagged-show').onclick=()=>run(async()=>{const t=$('o-tagging');t.open=true;await TAG.show(st.org);t.scrollIntoView({block:'start',behavior:'smooth'})});
 $('f-save').onclick=()=>run(async()=>{const x=await api('/admin/api/organisations/facts','POST',{org:st.org,section:$('f-section').value,statement:$('f-statement').value,source_system:$('f-system').value,source_ref:$('f-ref').value,as_of:$('f-asof').value,review_by:$('f-review').value,label:$('f-label').value});$('notice').textContent=x.duplicate?'That fact is already recorded.':'Fact added (review by '+x.review_by+').';$('f-statement').value='';$('f-count').textContent='';st.status='approved';await load()});
 $('b-show').onclick=()=>run(async()=>{const b=await api('/admin/api/organisations/brief?org='+encodeURIComponent(st.org)+'&provider='+$('b-provider').value+'&external='+$('b-external').checked);$('b-text').textContent=b.text?b.text+'\n\n('+b.facts+' facts · '+b.text.length+' characters · about '+Math.round(b.text.length/4)+' tokens)':(b.withheld||'Nothing would be sent: no approved facts this model may see.')});
 $('r-check').onclick=()=>run(async()=>{const x=await api('/admin/api/organisations/source?source_system='+encodeURIComponent($('r-system').value)+'&source_ref='+encodeURIComponent($('r-ref').value));$('r-result').textContent=x.facts.length+(x.facts.length===1?' fact matches':' facts match')+(x.facts.length?': '+x.facts.map(f=>f.org+' · '+f.statement.slice(0,60)).join(' | '):'')});
 $('r-go').onclick=()=>run(async()=>{if(!confirm('Retire every fact whose source matches? They stay in the history as retired.'))return;const x=await api('/admin/api/organisations/remove-source','POST',{source_system:$('r-system').value,source_ref:$('r-ref').value,reason:$('r-reason').value});$('r-result').textContent=x.removed+' removed.';await load()});
 // ---------- opportunity tracker (slide-out) ----------
 const OT={status:'suggested',org:'',open:false};const SL={suggested:'Suggested',tracking:'Tracking',pursuing:'Pursuing',won:'Won',lost:'Lost',dismissed:'Dismissed'};
 const when=d=>d?new Date(d).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'—';
 function drawer(open){const was=OT.open;OT.open=open;if(was&&!open)run(load);$('opp-drawer').classList.toggle('open',open);$('opp-drawer').setAttribute('aria-hidden',!open);$('opp-open').setAttribute('aria-expanded',open);$('opp-scrim').hidden=!open;if(open)run(loadOpps)}
 async function loadOpps(){const d=await api('/admin/api/opportunities?org='+encodeURIComponent(OT.org));OT.data=d;
  $('opp-badge').hidden=!d.counts.suggested;$('opp-badge').textContent=d.counts.suggested;
  if(!OT.open)return d;
  $('opp-status').replaceChildren(...[...d.statuses,''].map(k=>{const n=k?d.counts[k]:Object.values(d.counts).reduce((a,b)=>a+b,0);const b=el('button',(k?SL[k]:'All')+' ('+n+')','chip'+(OT.status===k?' on':'')+(k==='suggested'&&n&&OT.status!==k?' attention':''));b.type='button';b.onclick=()=>{OT.status=k;run(loadOpps)};return b}));
  const sel=$('opp-org');const cur=OT.org;sel.replaceChildren(el('option','All organisations'));sel.options[0].value='';for(const w of d.watch){const o=el('option',w.org);o.value=w.org;sel.append(o)}sel.value=cur;
  const list=$('opp-list');list.replaceChildren();const rows=d.opportunities.filter(o=>!OT.status||o.status===OT.status);
  if(!rows.length)list.append(el('p',OT.status==='suggested'?'No new suggestions. Scan an organisation, or wait for its schedule.':'Nothing here.','muted'));
  for(const o of rows){const c=el('div','','opp '+o.status);c.append(el('h3',o.title));const m=el('div','','opp-meta');m.append(el('span',o.org,'tag'),...(o.account_manager?[el('span',o.account_manager,'small muted')]:[]),el('span',SL[o.status],'badge v-'+({suggested:'warn',pursuing:'run',won:'ok',lost:'none',dismissed:'none'}[o.status]||'none')));
   if(o.offering)m.append(el('span',o.offering,'tag know'));if(o.size)m.append(el('span',o.size,'small muted'));if(o.confidence!==null&&o.confidence!==undefined)m.append(el('span','confidence '+Math.round(o.confidence*100)+'%','small muted'));c.append(m);
   if(o.why_now){const p=el('p','');p.append(el('strong','Why now: '),document.createTextNode(o.why_now));c.append(p)}c.append(el('p',o.summary));
   if(o.next_step){const p=el('p','');p.append(el('strong','Next step: '),document.createTextNode(o.next_step+(o.timing?' ('+o.timing+')':'')));c.append(p)}
   const ev=el('div','Evidence: ','opp-ev muted');o.evidence.forEach((u,i)=>ev.append(link(u,u.replace(/^https?:\/\/(www\.)?/i,'').split('/')[0]+(o.evidence.length>1?' ('+(i+1)+')':''))));c.append(ev);
   const act=el('div','','opp-act');
   if(o.status==='suggested'){const tr=el('button','Track','mini-act');tr.type='button';tr.onclick=()=>run(async()=>{await api('/admin/api/opportunities/'+o.id,'PUT',{status:'tracking'});$('notice').textContent='Tracking: '+o.title;await loadOpps()});
    const di=el('button','Dismiss','secondary mini-act');di.type='button';di.onclick=()=>run(async()=>{await api('/admin/api/opportunities/'+o.id,'PUT',{status:'dismissed'});await loadOpps()});act.append(tr,di)}
   else{const ss=document.createElement('select');ss.setAttribute('aria-label','Status');for(const k of d.statuses){const op=el('option',SL[k]);op.value=k;ss.append(op)}ss.value=o.status;ss.onchange=()=>run(async()=>{await api('/admin/api/opportunities/'+o.id,'PUT',{status:ss.value});await loadOpps()});act.append(ss)}
   act.append(el('span','Found '+when(o.created_at)+(o.trigger==='schedule'?' (scheduled)':''),'small muted'));c.append(act);
   if(o.status!=='suggested'){const ta=document.createElement('textarea');ta.value=o.notes||'';ta.placeholder='Notes: contacts in the account plan, value, dates…';ta.setAttribute('aria-label','Notes');ta.onchange=()=>run(async()=>{await api('/admin/api/opportunities/'+o.id,'PUT',{notes:ta.value});$('notice').textContent='Notes saved.'});c.append(ta)}
   list.append(c)}
  const nl=$('opp-news');nl.replaceChildren();$('opp-news-n').textContent='('+d.news.length+')';for(const n of d.news){const li=el('li','');li.append(link(n.url,n.title),el('div',(OT.org?'':n.org+' · ')+(n.published||'date unknown')+(n.summary?' · '+n.summary:''),'muted'));nl.append(li)}
  const sc=$('opp-sched');sc.replaceChildren();for(const w of d.watch){const r=el('div','','opp-sched-row');const fs=document.createElement('select');fs.setAttribute('aria-label','Scan frequency for '+w.org);for(const f of ['weekly','fortnightly','monthly','off']){const op=el('option',f);op.value=f;fs.append(op)}fs.value=w.frequency;
   fs.onchange=()=>run(async()=>{await api('/admin/api/opportunities/schedule','POST',{org:w.org,frequency:fs.value});$('notice').textContent=w.org+': scan '+fs.value+'.';await loadOpps()});
   const go=el('button','Run now','secondary mini-act');go.type='button';go.onclick=()=>scanOrg(w.org,go);
   r.append(el('strong',w.org+(w.is_client?'':' ')),fs,el('span',(w.last_run?'Last '+when(w.last_run)+(w.last_status&&w.last_status!=='complete'?' ('+w.last_status+')':''):'Not scanned yet')+(w.frequency!=='off'&&w.next_run?' · next '+when(w.next_run):''),'muted'),go);sc.append(r)}
  if(document.activeElement!==$('opp-offerings'))$('opp-offerings').value=d.offerings.join('\n');return d}
 async function scanOrg(org,btn,statusEl){btn.disabled=true;const old=btn.textContent;btn.textContent='Scanning…';if(statusEl){statusEl.className='muted small o-busy';statusEl.textContent='Temple is reading the profile and searching recent news…'}
  try{const x=await api('/admin/api/opportunities/scan','POST',{org});$('notice').textContent=org+': '+x.summary+'. Open the tracker to review.';if(statusEl){statusEl.className='muted small';statusEl.textContent=x.summary}OT.status='suggested';await loadOpps();if(!OT.open&&x.opportunities)drawer(true)}
  catch(e){$('notice').textContent=e.message;if(statusEl){statusEl.className='muted small';statusEl.textContent=e.message}}finally{btn.disabled=false;btn.textContent=old}}
 $('opp-open').onclick=()=>drawer(!OT.open);$('opp-close').onclick=()=>drawer(false);$('opp-scrim').onclick=()=>drawer(false);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&OT.open)drawer(false)});
 $('opp-org').onchange=()=>{OT.org=$('opp-org').value;run(loadOpps)};
 $('opp-off-save').onclick=()=>run(async()=>{const x=await api('/admin/api/opportunities-offerings','PUT',{offerings:$('opp-offerings').value.split('\n')});$('notice').textContent='Offerings saved ('+x.offerings.length+').'});
 $('o-opp-scan').onclick=()=>scanOrg(st.org,$('o-opp-scan'),$('o-opp-status'));
 $('o-opp-view').onclick=()=>{OT.org=st.org;OT.status='';drawer(true)};
 $('o-opp-freq').onchange=()=>run(async()=>{await api('/admin/api/opportunities/schedule','POST',{org:st.org,frequency:$('o-opp-freq').value});$('notice').textContent=st.org+': scan '+$('o-opp-freq').value+'.';await loadOpps()});
 const q=new URLSearchParams(location.search).get('org');if(q)st.org=q;
 const qf=new URLSearchParams(location.search).get('filter');if(['all','clients','attention','opps'].includes(qf))st.filter=qf;
 const TAG=DEMO_ORG?null:initTagging();$('o-tagging').hidden=DEMO_ORG;
 run(async()=>{await loadOpps();await load();if(TAG)await TAG.refresh()});
 if(new URLSearchParams(location.search).get('tracker')){OT.status='suggested';drawer(true)}
}
"""

SCRIPT += r"""
if(PAGE==='rules'){
 const PVA={'':'Not mapped yet',general:'General',internal:'Internal',client:'Client-confidential',local:'Local only',block:'Block: do not save'};
 function pvSelect(v){const s=document.createElement('select');for(const [k,t] of Object.entries(PVA)){const o=el('option',t);o.value=k;s.append(o)}s.value=v||'';return s}
 async function loadPv(){const d=await api('/admin/api/purview-labels');const box=$('pv-list');box.replaceChildren();
  const unmapped=d.labels.filter(l=>!l.action).length;$('pv-summary').textContent=d.labels.length?d.labels.length+' seen or mapped'+(unmapped?' · '+unmapped+' not mapped':''):'none seen yet';
  if(!d.labels.length)box.append(el('p','No labelled files uploaded yet. Labels appear here the first time Alice sees one.','muted small'));
  for(const l of d.labels){const row=el('div','','cat-row');const v=el('div','','cat-view');v.append(el('span',l.name||'(name not in the file)','tag'+(l.action?'':' attention')),el('span',l.label_id,'muted small cat-desc'),el('span',l.files+(l.files===1?' file':' files'),'small cat-count'));
   const sel=pvSelect(l.action);sel.setAttribute('aria-label','Handle '+(l.name||l.label_id)+' as');sel.onchange=()=>run(async()=>{await api('/admin/api/purview-labels','PUT',{label_id:l.label_id,action:sel.value});$('notice').textContent=(l.name||l.label_id)+': '+PVA[sel.value]+'.';await loadPv()});v.append(sel);row.append(v);box.append(row)}}
 const a=$('pv-action');a.replaceChildren(...Object.entries(PVA).filter(([k])=>k).map(([k,t])=>{const o=el('option',t);o.value=k;return o}));a.value='internal';
 $('pv-add').onclick=()=>run(async()=>{await api('/admin/api/purview-labels','PUT',{label_id:$('pv-id').value.trim(),name:$('pv-name').value.trim(),action:$('pv-action').value});$('pv-id').value=$('pv-name').value='';$('notice').textContent='Mapping added.';await loadPv()});
 run(loadPv);
}
"""

SCRIPT += r'''
if(PAGE==='home'){
 const fmt=n=>Number(n||0).toLocaleString('en-GB'),usd=v=>'$'+Number(v||0).toFixed(2);
 const ago=d=>{if(!d)return '';const m=(Date.now()-new Date(d))/60000;return m<1?'just now':m<60?Math.round(m)+' min ago':m<1440?Math.round(m/60)+' h ago':new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short'})};
 const card=(title,link,linkText)=>{const c=el('section','','hm-card');const h=el('h3',title);if(link){const a=document.createElement('a');a.href=link;a.textContent=linkText||'Open →';h.append(a)}c.append(h);return c};
 function waiting(d){const c=card('Waiting for you','/admin/actions','All actions →');if(!d.waiting.total){c.append(el('div','✓ All clear: nothing needs a decision.','hm-clear'));return c}
  const box=el('div','','hm-wait');for(const s of d.waiting.sections){const a=document.createElement('a');a.href=s.link;a.className=s.level==='bad'?'bad':s.level==='warn'?'warn':'';a.append(el('span',s.title),el('span',fmt(s.count),'hm-n'));box.append(a)}c.append(box);return c}
 function today(d){const t=d.today||{},c=card('Today','/admin/activity','Activity →');const tl=el('div','','hm-tiles');
  const tile=(n,l,href,alert)=>{const x=el(href?'a':'div','','hm-tile'+(alert?' alert':''));if(href)x.href=href;x.append(el('b',fmt(n)),el('span',l));tl.append(x)};
  tile(t.events,'things recorded','/admin/activity');tile(t.blocked,'stopped by the rules','/admin/activity?type=blocks',t.blocked>0);tile(t.runs,'agent runs'+(t.failed_runs?' · '+t.failed_runs+' failed':''),'/admin/agents',t.failed_runs>0);tile(t.model_calls,'AI calls','/admin/usage');c.append(tl);
  const sp=d.spend||{};if(sp.daily_usd){const m=el('div','','hm-meter');const lvl=sp.level==='blocked'?'bad':sp.level==='warning'?'warn':'';
   const row=(label,v,cap)=>{const r=el('div');r.append(el('div',label+': '+usd(v)+' of '+usd(cap)));const b=el('div','','hm-bar '+lvl);const f=el('div');f.style.width=Math.min(100,100*v/cap)+'%';b.append(f);r.append(b);return r};
   m.append(row('AI spend today',sp.today_usd,sp.daily_usd),row('This month',sp.month_usd,sp.monthly_usd));if(sp.level==='blocked')m.append(el('div','Chat is paused: the spending cap is reached.','hm-pill warn'));c.append(m)}
  return c}
 function week(d){const c=card('The last 7 days','/admin/activity','The picture →');const b=d.week.buckets.slice(-7);const mx=Math.max(1,...b.map(x=>x.n));const sp=el('div','','hm-spark');sp.setAttribute('role','img');sp.setAttribute('aria-label','Things recorded per day over the last 7 days');
  for(const x of b){const col=el('div');col.title=x.label+': '+fmt(x.n)+' things';const bar=document.createElement('i');bar.style.height=Math.max(2,100*x.n/mx)+'%';const bw=el('div','','hm-bw');bw.append(bar);col.append(el('span',fmt(x.n)),bw,el('span',x.label));sp.append(col)}c.append(sp);
  const g=(d.week.gate||[]).reduce((a,x)=>({p:a.p+x.proposed,ap:a.ap+x.approved,r:a.r+x.rejected}),{p:0,ap:0,r:0});c.append(el('p',g.p||g.ap||g.r?'Proposed '+fmt(g.p)+' · you approved '+fmt(g.ap)+' · rejected '+fmt(g.r)+'.':'Nothing proposed this week.','hm-empty'));return c}
 function chats(d){const c=card('Recent chats','/?new=1','New chat →');if(!d.chats.length){c.append(el('p','No chats yet.','hm-empty'));return c}const ul=el('ul','','hm-list');
  for(const x of d.chats){const li=document.createElement('li');const a=document.createElement('a');a.href='/#'+x.id;a.title=x.title||'';const l=el('b',x.title||'Untitled chat');a.append(l,el('span',(x.client?x.client+' · ':'')+ago(x.updated_at),'muted'));li.append(a);ul.append(li)}c.append(ul);return c}
 function props(d){const pw=d.assistants.find(a=>a.kind==='proposal');const c=card('Recent proposals',pw?'/assistant/'+encodeURIComponent(pw.id):null,'Write one →');if(!d.proposals.length){c.append(el('p','No proposals yet.','hm-empty'));return c}const ul=el('ul','','hm-list');
  for(const x of d.proposals){const li=document.createElement('li');const a=document.createElement('a');a.href='/assistant/'+encodeURIComponent(x.assistant_id)+'?p='+x.id;a.target='_blank';a.rel='noopener';
   const st=x.status==='running'?el('span','writing…','hm-pill'):x.status==='failed'?el('span','failed','hm-pill warn'):el('span',(x.verdict==='client_ready'?'client ready':'needs attention')+(x.score!=null?' · '+x.score:''),'hm-pill '+(x.verdict==='client_ready'?'ok':'warn'));
   a.append(el('b',x.title+(x.organisation?' · '+x.organisation:'')),st);li.append(a);ul.append(li)}c.append(ul);return c}
 function helpers(d){const c=card('Assistants and agents','/admin/agents','Agents →');const ul=el('ul','','hm-list');
  for(const x of d.assistants){const li=document.createElement('li');const a=document.createElement('a');a.href='/assistant/'+encodeURIComponent(x.id);a.target='_blank';a.rel='noopener';a.append(el('b',x.name),el('span',x.status==='active'?'open ↗':'paused','muted'));li.append(a);ul.append(li)}c.append(ul);
  const ag=d.agents;c.append(el('p',fmt(ag.active)+' of '+fmt(ag.total)+' agents active.','hm-empty'));for(const x of ag.attention){const a=document.createElement('a');a.href='/admin/agents?agent='+encodeURIComponent(x.id);a.className='hm-pill warn';a.textContent='⚑ '+x.name+': '+x.why;c.append(a)}return c}
 function substrate(d){const c=card('Your substrate');const g=el('div','','hm-stats');const s=d.substrate;
  for(const [n,l,h] of [[s.memories,'approved memories','/admin/memories'],[s.knowledge,'knowledge items','/admin/knowledge'],[s.documents,'documents in sources','/admin/documents'],[s.organisations,'organisations ('+s.clients+' clients)','/admin/organisations'],[d.agents.total,'agents','/admin/agents']]){const a=document.createElement('a');a.className='hm-stat';a.href=h;a.append(el('b',fmt(n)),el('span',l));g.append(a)}c.append(g);return c}
 run(async()=>{const d=await api('/admin/api/home?tz='+new Date().getTimezoneOffset());
  $('hm-hello').textContent=d.greeting+', '+d.name+'.';
  $('hm-sub').textContent=d.waiting.total?d.waiting.total+' thing'+(d.waiting.total===1?' needs':'s need')+' a decision from you. Everything else is running.':'Nothing is waiting for you. Here is what is happening in Alice.';
  const pw=d.assistants.find(a=>a.kind==='proposal');if(pw){$('hm-prop').href='/assistant/'+encodeURIComponent(pw.id);$('hm-prop').target='_blank'}
  const r1=el('div','','hm-row hm-2');r1.append(waiting(d),today(d));const r2=el('div','','hm-row hm-3');r2.append(chats(d),props(d),helpers(d));const r3=el('div','','hm-row hm-2');r3.append(week(d),substrate(d));
  $('hm').replaceChildren(r1,r2,r3)});
}
'''

SCRIPT += r'''
if(PAGE==='temple')run(async()=>{const d=await api('/admin/api/temple/parker');if(!d.items.length)return;const box=$('t-parker');box.hidden=false;
 const forms=new Set(d.items.map(x=>(x.detail||'').split(':')[0])).size;
 box.querySelector('summary').textContent='\u270e Parker: '+d.items.length+' update'+(d.items.length===1?'':'s')+' on '+forms+' proposal form'+(forms===1?'':'s')+' in the last '+d.days+' days';
 $('t-parker-list').replaceChildren(...d.items.slice(0,20).map(x=>{const li=document.createElement('li');li.append(document.createTextNode(x.detail),el('span',' · '+(x.actor?x.actor+' · ':'')+new Date(x.created_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}),'muted small'));return li}))});
if(PAGE==='temple')run(async()=>{const d=await api('/admin/api/temple/auto-approved');if(!d.items.length)return;const box=$('t-auto');box.hidden=false;
 box.querySelector('summary').textContent='✓ '+d.items.length+' reference summar'+(d.items.length===1?'y':'ies')+' auto-approved in the last '+d.days+' days';
 $('t-auto-list').replaceChildren(...d.items.map(x=>{const li=document.createElement('li');const a=document.createElement('a');const t=(x.detail||'').split(': summary of')[0];a.href='/admin/knowledge?status=all&q='+encodeURIComponent(t.slice(0,80));a.textContent=x.detail;li.append(a,el('span',' · '+new Date(x.created_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}),'muted small'));return li}))});
'''

SCRIPT += r"""
if(PAGE==='documents'){
 let D=null;const open=new Set();
 const size=n=>n>=1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
 const day=d=>new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
 function copyBtn(text){const b=el('button','Copy path','secondary mini-act');b.type='button';b.onclick=()=>{navigator.clipboard?.writeText(text);b.textContent='Copied'};return b}
 async function filesFor(src,box){const d=await api('/admin/api/document-sources/files?source='+encodeURIComponent(src.id));box.replaceChildren();
  if(!d.files.length){box.append(el('p','No documents yet. Put .docx, .pdf, .txt, .md or .csv files in '+src.path+'.','muted small'));return}
  const t=el('table','','mem-table ds-table');const h=document.createElement('tr');for(const x of ['Document','Modified','Size','Purview label','Summaries in Alice','Read by agents (30 days)'])h.append(el('th',x));t.append(h);
  for(const f of d.files){const tr=document.createElement('tr');const c=document.createElement('td');c.append(el('strong',f.name));if(f.path!==f.name)c.append(el('div',f.path,'muted small'));
   const sm=document.createElement('td');if(f.summaries){const a=el('a',f.summaries_active+' active'+(f.summaries>f.summaries_active?', '+(f.summaries-f.summaries_active)+' other':''));a.href='/admin/knowledge?status=all&q='+encodeURIComponent(f.name.replace(/\.[^.]+$/,'').replace(/-/g,' ').slice(0,60));sm.append(a)}else sm.append(el('span','None yet','muted'));
   tr.append(c,el('td',day(f.modified),'small'),el('td',size(f.size),'small'),el('td',f.label||'None','small'),sm,el('td',f.reads?String(f.reads):'—','num'));t.append(tr)}
  box.append(t)}
 function render(){const box=$('ds-list');box.replaceChildren();$('ds-root').textContent='Documents folder: '+D.root+(D.exists?'':' (not created yet: add a source to create it)');
  if(!D.sources.length)box.append(el('p','No document sources yet.','muted'));
  for(const src of D.sources){const c=el('div','','as-card');const h=el('div','','as-head');const t=el('div','');t.append(el('h3',src.name));
   const meta=el('div','','as-meta');meta.append(el('span',src.type_name,'tag ds-kind ds-'+src.type));if(src.simulated)meta.append(el('span','Simulated by a folder','tag'));meta.append(el('span',src.files+' document'+(src.files===1?'':'s'),'tag'));t.append(meta);
   if(src.simulates)t.append(el('p','Stands in for: '+src.simulates,'small'));if(src.description)t.append(el('p',src.description,'muted small'));
   t.append(el('p',src.simulated?'In Azure: a '+src.connector+' connector replaces this folder; nothing else changes.':'A local folder.','muted small'));
   const loc=el('div','','dt-loc');loc.append(el('code',src.path),copyBtn(src.path));t.append(loc);
   const btns=el('div','','as-btns');const sh=el('button',open.has(src.id)?'Hide documents':'Show documents','secondary');sh.type='button';sh.onclick=()=>{open.has(src.id)?open.delete(src.id):open.add(src.id);render()};btns.append(sh);
   h.append(t,btns);c.append(h);if(open.has(src.id)){const fb=el('div','','ds-files');fb.append(el('p','Loading…','muted small'));c.append(fb);run(()=>filesFor(src,fb))}box.append(c)}}
 async function load(){D=await api('/admin/api/document-sources');$('ds-type').replaceChildren(...Object.entries(D.kinds).map(([k,v])=>{const o=el('option',v);o.value=k;return o}));$('ds-type').value='sharepoint';render()}
 $('ds-new').onclick=()=>{$('ds-form').hidden=false;$('ds-name').focus()};$('ds-cancel').onclick=()=>{$('ds-form').hidden=true};
 $('ds-form').onsubmit=e=>{e.preventDefault();run(async()=>{const x=await api('/admin/api/document-sources','POST',{name:$('ds-name').value,type:$('ds-type').value,simulates:$('ds-sim').value,description:$('ds-desc').value});$('ds-form').reset();$('ds-form').hidden=true;$('notice').textContent='Created '+x.name+'. Put its documents in '+x.path+'.';open.add(x.id);await load()})};
 run(load);
}
"""

SCRIPT += r"""
""" + __import__('proposal_ui').PE_JS + r"""
if(PAGE==='assistants'){
 let L=null,T=[];const open=new Set();let newKind='qa';
 function field(label,node){const l=el('label',label);l.append(node);return l}
 function input(v,max,ph){const i=document.createElement('input');i.value=v||'';i.maxLength=max;if(ph)i.placeholder=ph;return i}
 function area(v,max,rows){const t=document.createElement('textarea');t.value=v||'';t.maxLength=max;t.rows=rows;return t}
 function checks(all,picked){const box=el('div','','as-checks');const get=[];for(const [k,t] of all){const l=el('label','','r-check');const c=document.createElement('input');c.type='checkbox';c.value=k;c.checked=picked.includes(k);l.append(c,document.createTextNode(' '+t));box.append(l);get.push(c)}box.value=()=>get.filter(c=>c.checked).map(c=>c.value);return box}
 function sel(opts,v){const x=document.createElement('select');for(const [k,t] of opts){const o=el('option',t);o.value=k;x.append(o)}x.value=v;return x}
 function form(a,isNew){const f=el('div','','as-form');const kind=isNew?newKind:(a.kind||'qa');
  if(isNew){const ty=sel(Object.entries(L.kinds),kind);ty.onchange=()=>{newKind=ty.value;render()};f.append(field('Type',ty))}
  const name=input(a.name,80,kind==='proposal'?'e.g. Proposal writer':'e.g. Alex (HR policy assistant)'),desc=input(a.description,500,'What it is for, in one line'),greet=area(a.greeting,800,2),guide=area(a.guidance,3000,4),contact=input(a.contact,120,'e.g. your HR business partner');
  const premium=new Set(L.models.filter(m=>m.premium).map(m=>m.key));
  const provOpts=keys=>keys.map(k=>[k,L.providers[k]+(premium.has(k)?' (premium)':'')]);
  const prov=sel(provOpts(kind==='proposal'?Object.keys(L.providers):L.qa_providers),a.provider||(kind==='proposal'?'claude_sonnet':'openai'));
  const st=sel([['active','Active'],['paused','Paused']],a.status||'active');
  const S=a.settings||{};let body=()=>({});
  if(kind==='proposal'){
   const qap=sel(provOpts(Object.keys(L.providers)),S.qa_provider||'claude_sonnet');
   const est=el('p','','muted small');const upd=()=>{const w=L.models.find(m=>m.key===prov.value),q=L.models.find(m=>m.key===qap.value);est.textContent=w&&q&&w.writer_cost!=null&&q.qa_cost!=null?'Roughly $'+(w.writer_cost+q.qa_cost).toFixed(2)+' per proposal with these defaults. Premium models write better and cost more; people can choose another model on each proposal.':''};prov.onchange=upd;qap.onchange=upd;
   const chp=sel(provOpts(Object.keys(L.providers)),S.chat_provider||'claude_sonnet');
   const r1=el('div','','k-meta-row');r1.append(field('Name',name),field('Writer model',prov),field('QA model',qap),field('Chat model (working with you on the form)',chp),field('Status',st));
   upd();f.append(r1,est,field('Description',desc),field('Greeting shown on its page',greet),field('Tone and style for the writer',guide));
   const tpl=sel([['','No template: Alice’s own Word layout']].concat(T.map(x=>[x.path,x.name+' ('+x.source+')'])),S.template||'');
   if(S.template&&!T.some(x=>x.path===S.template)){const o=el('option',S.template+' (not found)');o.value=S.template;tpl.append(o);tpl.value=S.template}
   const prev=el('div','','muted small as-tpl');
   const showTpl=()=>{prev.textContent='';if(!tpl.value){prev.textContent=T.length?'':'No Word documents in the document sources yet. Put your template in a folder on the Documents page.';return}
    run(async()=>{try{const o=await api('/admin/api/proposal-templates/outline?path='+encodeURIComponent(tpl.value));prev.textContent=o.sections.length?'Template sections: '+o.sections.map(x=>x.title+(x.keep?' (standard text)':'')).join(' · ')+'.'+(o.placeholders.length?' Placeholders filled in: '+o.placeholders.map(x=>'{{'+x+'}}').join(' ')+'.':''):'The template has no Heading 1 sections: your format and flow sections are added after its cover, in its styles.'}catch(e){prev.textContent=e.message}})};
   tpl.onchange=showTpl;const tf=field('Proposal template',tpl);tf.append(prev,el('span','Use Heading 1 for each section. Text under a heading is guidance for the writer; a section containing [keep] is copied word for word. Placeholders: {{title}} {{client}} {{date}} {{author}} {{reference}} {{total}}.','muted small'));f.append(tf);showTpl();
   const fb=el('div','');fb.append(el('strong','Format and flow'),el('p','Default sections for new proposals, added after the template’s own sections. A section with the same title as a template section adds your guidance to it. People can change all of this on each proposal.','muted small'));
   const sbox=el('div');fb.append(sbox);const secEd=PE.sections(sbox,(S.sections||[]).map(x=>({...x,source:'format and flow'})),{allowKeep:false,empty:'None: new proposals start from the template sections.'});
   const rb=el('div','');rb.append(el('strong','Rate card and price book'),el('p','Load your pricing tool or paste a table. Alice sets each sell rate from its cost at the target margin unless you override it. Ticked roles start ticked on new proposals; people can tick others and change rates per proposal. Cost rates never go to the AI or into the document.','muted small'));
   const rbox=el('div');rb.append(rbox);const rateEd=PE.rates(rbox,S.rate_card||[],['day','hour'],{target:S.target_margin??30,minMargin:S.min_margin??25,
    parse:a.id?async f=>{const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=no;r.readAsDataURL(f)});return api('/assistant/'+encodeURIComponent(a.id)+'/rates/parse','POST',{name:f.name,data})}:null});
   f.append(fb,rb);
   const mm=input(S.min_margin??25,5);mm.inputMode='decimal';const pn=input(S.pricing_note??'All prices exclude VAT.',200);const au=input(S.author||'',80,'Your name, on the cover');
   const r2=el('div','','k-meta-row');r2.append(field('Minimum margin (%)',mm),field('Note under the pricing table',pn),field('Author ({{author}})',au));f.append(r2);
   const aal=el('label','','r-check');const aac=document.createElement('input');aac.type='checkbox';aac.checked=S.auto_approve_references!==false;aal.append(aac,document.createTextNode(' Approve reference document summaries automatically'));
   f.append(aal,el('p','Summaries of documents someone uploads on the proposal page go straight into Knowledge; each one is logged on the Temple page and in Activity. Untick to review them first.','muted small'));
   body=()=>({kind:'proposal',settings:{template:tpl.value,sections:secEd.value(),rate_card:rateEd.value(),target_margin:rateEd.target(),qa_provider:qap.value,chat_provider:chp.value,min_margin:mm.value||0,pricing_note:pn.value,author:au.value,auto_approve_references:aac.checked}});
  } else {
  const packs=checks(Object.entries(L.packs),a.packs||[]);const cats=checks(L.categories.map(c=>[c,c]),a.categories||[]);
  const r1=el('div','','k-meta-row');r1.append(field('Name',name),field('Model',prov),field('Status',st));
  f.append(r1,field('Description',desc),field('Greeting shown to staff',greet),field('Guidance (how it should answer)',guide),field('Who to contact when it cannot help',contact));
  const pk=el('div','');pk.append(el('strong','Rule packs'),el('p','Applied to every question in code, whatever the global Rules settings say.','muted small'),packs);
  const ct=el('div','');ct.append(el('strong','Knowledge it may use'),el('p',L.categories.length?'Active knowledge in these categories. Client-tagged and Local only items are never used.':'No categories yet: create one (e.g. HR) on the Memories page and put the policies in it on the Knowledge page.','muted small'),cats);
  const two=el('div','','as-two');two.append(pk,ct);f.append(two);
  const dl=el('label','','r-check');const dc=document.createElement('input');dc.type='checkbox';dc.checked=a.allow_documents!==false;dl.append(dc,document.createTextNode(' Check the full documents when the summaries don’t answer'));
  f.append(dl,el('p','Answers come from the approved summaries first. Only if they don’t cover the question is the relevant section of the full document read from the document library for that one answer; nothing from it is stored in Alice.','muted small'));
  body=()=>({kind:'qa',packs:packs.value(),categories:cats.value(),allow_documents:dc.checked,contact:contact.value});
  }
  const save=el('button',isNew?'Create assistant':'Save');save.type='button';
  save.onclick=()=>run(async()=>{const b={name:name.value,description:desc.value,greeting:greet.value,guidance:guide.value,provider:prov.value,status:st.value,...body()};
   const x=isNew?await api('/admin/api/assistants','POST',b):await api('/admin/api/assistants/'+encodeURIComponent(a.id),'PUT',b);$('notice').textContent='Saved '+x.name+'.';open.clear();await load()});
  const cancel=el('button','Close');cancel.type='button';cancel.className='secondary';cancel.onclick=()=>{open.delete(isNew?'__new__':a.id);render()};
  const act=el('div','','arc-actions');act.append(save,cancel);f.append(act);return f}
 let Q='',KIND='all',STATUS='all',VIEW='cards',UID=0;
 const PALETTE=[['#1d8fb0','#075e79'],['#7a5bb5','#4b2f73'],['#2f9e6e','#1e5b31'],['#d08a2e','#8a5a0f'],['#3a6fc4','#1f3f7a'],['#c2557a','#7a1f45']];
 function logo(a,size){const w=el('span','','as-logo');w.style.width=w.style.height=size+'px';
  if(a.kind==='proposal'){const id='pk'+(++UID);w.innerHTML='<svg width="'+size+'" height="'+size+'" viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="'+id+'" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7a5bb5"/><stop offset="1" stop-color="#0a7f9f"/></linearGradient></defs><rect width="48" height="48" rx="13" fill="url(#'+id+')"/><path d="M17 8h14v5.5c0 1.6 2.2 4.2 2.2 9.2 0 2.4-.6 3.9-1.6 5.4L24 41l-7.6-12.9c-1-1.5-1.6-3-1.6-5.4 0-5 2.2-7.6 2.2-9.2z" fill="#fff"/><path d="M24 26v13" stroke="#3d72a6" stroke-width="1.9" stroke-linecap="round"/><circle cx="24" cy="23.5" r="2.9" fill="url(#'+id+')"/></svg>';return w}
  let h=0;for(const ch of a.name||'')h=(h*31+ch.charCodeAt(0))>>>0;const p=PALETTE[h%PALETTE.length];
  w.style.background='linear-gradient(135deg,'+p[0]+','+p[1]+')';w.style.fontSize=Math.round(size*.45)+'px';w.textContent=(a.name||'?').trim().charAt(0).toUpperCase();return w}
 const KINDNAME={qa:'Staff assistant',proposal:'Proposal writer'};
 function chips(box,opts,cur,set){box.replaceChildren();for(const [k,t,n] of opts){const b=el('button',t);b.type='button';if(n!=null)b.append(el('i',String(n)));b.className=k===cur?'on':'';b.setAttribute('aria-pressed',k===cur);b.onclick=()=>{set(k);render()};box.append(b)}}
 function uses(a){if(a.kind==='proposal'){const S=a.settings||{};return [S.template?'Template: '+S.template.split(/[\\/]/).pop().replace(/\.docx$/i,''):'No template yet',(S.rate_card||[]).length+' roles']}
  const kn=a.knowledge||{active:0,draft:0};return [(a.categories.join(', ')||'No knowledge yet'),kn.active+(kn.active===1?' item':' items')+(kn.draft?' · '+kn.draft+' waiting':'')]}
 function openBtn(a){const go=document.createElement('a');go.href='/assistant/'+encodeURIComponent(a.id);go.target='_blank';go.rel='noopener';go.className='button-link';go.textContent='Open ↗';return go}
 function editBtn(a){const ed=el('button',open.has(a.id)?'Close':'Edit');ed.type='button';ed.className='secondary';ed.onclick=()=>{const was=open.has(a.id);open.clear();if(!was)open.add(a.id);render();if(!was)$('as-editor').scrollIntoView({behavior:'smooth',block:'start'})};return ed}
 function demoBtn(a){if(a.id!=='hr-policy')return null;const dm=el('button','Load demo HR policy');dm.type='button';dm.className='secondary demo';dm.title='Adds summaries of a demonstration UK HR handbook as knowledge drafts (category HR). The full handbook stays in the policy library folder.';dm.onclick=()=>run(async()=>{const x=await api('/admin/api/assistants/demo-hr','POST',{});$('notice').textContent=x.added?x.added+' summaries of '+x.document+' added as drafts in '+x.category+'. Approve them on Knowledge (Drafts) and the assistant can use them. The full document stays at '+x.location+'.':'The demo summaries are already in Knowledge ('+x.already+').';await load()});return dm}
 function cardOf(a){const c=el('div','','as-c'+(a.status==='active'?'':' paused')+(open.has(a.id)?' editing':''));
  const top=el('div','','as-top');const tx=el('div');tx.append(el('h4',a.name),el('div',KINDNAME[a.kind]||a.kind,'as-kind'));top.append(logo(a,42),tx,el('span',a.status==='active'?'Active':'Paused','as-st'+(a.status==='active'?'':' off')));
  const meta=el('div','','as-meta');meta.append(el('span',L.providers[a.provider]||a.provider,'tag'));
  if(a.kind==='proposal'){const S=a.settings||{};meta.append(el('span','Writer + QA','tag k-knowledge'),el('span',S.template?'Template: '+S.template.split(/[\\/]/).pop().replace(/\.docx$/i,''):'No template yet','tag'+(S.template?'':' flag')),el('span',(S.rate_card||[]).length+' roles','tag'))}
  else{for(const p of a.packs)meta.append(el('span',(L.packs[p]||p)+' pack','tag k-knowledge'));for(const k of a.categories)meta.append(el('span',k,'tag'));if(!a.categories.length)meta.append(el('span','No knowledge yet','flag'));
   const kn=a.knowledge||{active:0,draft:0};meta.append(el('span',kn.active+(kn.active===1?' item it can use':' items it can use'),'small muted'));
   if(kn.draft){const w=document.createElement('a');w.className='flag';w.href='/admin/knowledge?status=draft'+(a.categories.length===1?'&category='+encodeURIComponent(a.categories[0]):'');w.textContent=kn.draft+' awaiting approval →';meta.append(w)}}
  const ft=el('div','','as-foot');ft.append(openBtn(a),editBtn(a),el('span','','sp'));const dm=demoBtn(a);if(dm)ft.append(dm);
  c.append(top,el('p',a.description||'No description yet.','as-desc'),meta,ft);return c}
 function tableOf(list){const t=el('table','','as-tbl');const hr=document.createElement('tr');for(const [h,cls] of [['Assistant',''],['Type','hide-s'],['Model','hide-s'],['Uses','hide-s'],['Status',''],['','']]){const th=el('th',h);if(cls)th.className=cls;hr.append(th)}t.append(hr);
  for(const a of list){const tr=document.createElement('tr');const nm=el('div','','nm');const tx=el('div');tx.append(el('b',a.name),el('span',a.description||'','small muted'));nm.append(logo(a,32),tx);
   const td=x=>{const d=document.createElement('td');if(x instanceof Node)d.append(x);else d.textContent=x;return d};
   const u=uses(a);const ut=td(u[0]);ut.append(el('div',u[1],'small muted'));ut.className='hide-s';const ty=td(KINDNAME[a.kind]||a.kind);ty.className='hide-s';const md=td(L.providers[a.provider]||a.provider);md.className='hide-s';
   const ac=td('');ac.className='acts';ac.append(openBtn(a),editBtn(a));
   tr.append(td(nm),ty,md,ut,td(el('span',a.status==='active'?'Active':'Paused','as-st'+(a.status==='active'?'':' off'))),ac);t.append(tr)}return t}
 function render(){const all=L.assistants;
  const kn=all.reduce((n,a)=>n+((a.kind!=='proposal'&&a.knowledge)?a.knowledge.draft:0),0);
  const tiles=$('as-tiles');tiles.replaceChildren();const tile=(k,v,href,warn)=>{const d=document.createElement(href?'a':'div');d.className='as-tile'+(warn?' warn':'');if(href)d.href=href;d.append(el('span',k),el('b',String(v)));tiles.append(d)};
  tile('Assistants',all.length);tile('Active',all.filter(a=>a.status==='active').length);tile('Staff assistants',all.filter(a=>a.kind!=='proposal').length);tile('Proposal writers',all.filter(a=>a.kind==='proposal').length);
  if(kn)tile('Summaries to approve',kn,'/admin/knowledge?status=draft',true);
  chips($('as-kinds'),[['all','All',all.length],['qa','Staff assistants',all.filter(a=>a.kind!=='proposal').length],['proposal','Proposal writers',all.filter(a=>a.kind==='proposal').length]],KIND,k=>KIND=k);
  chips($('as-status'),[['all','Any status'],['active','Active'],['paused','Paused']],STATUS,k=>STATUS=k);
  chips($('as-view'),[['cards','Cards'],['list','List']],VIEW,k=>{VIEW=k;try{localStorage.setItem('alice.as.view',k)}catch{}});
  const ed=$('as-editor');ed.replaceChildren();const eid=[...open][0];
  if(eid){const isNew=eid==='__new__';const a=isNew?{}:all.find(x=>x.id===eid);if(a){const c=el('div','','as-ed');const top=el('div','','as-top');const tx=el('div');
   tx.append(el('h4',isNew?'New assistant':'Edit '+a.name),el('div',isNew?'Choose the type first: a staff assistant answers questions from knowledge; a proposal writer writes proposals.':(KINDNAME[a.kind]||a.kind),'as-kind'));
   top.append(logo(isNew?{name:'+',kind:newKind}:a,42),tx);c.append(top,form(a,isNew));ed.append(c)}}
  const q=Q.trim().toLowerCase();const list=all.filter(a=>(KIND==='all'||(KIND==='proposal')===(a.kind==='proposal'))&&(STATUS==='all'||a.status===STATUS)
   &&(!q||(a.name+' '+(a.description||'')+' '+(a.categories||[]).join(' ')).toLowerCase().includes(q)));
  const box=$('as-list');box.replaceChildren();
  if(!all.length){box.append(el('div','No assistants yet. Create one with New assistant.','as-empty'));return}
  if(!list.length){box.append(el('div','No assistants match.','as-empty'));return}
  if(VIEW==='list'){box.append(tableOf(list));return}
  const groups=KIND==='all'?[['qa','Staff assistants','Answer staff questions from approved knowledge'],['proposal','Proposal writers','Write proposals into your template, checked by the QA agent']]:[[KIND,'','']];
  for(const [k,h,sub] of groups){const g=list.filter(a=>(k==='proposal')===(a.kind==='proposal'));if(!g.length)continue;
   if(h){const gh=el('div','','as-group');gh.append(el('h3',h),el('span',sub));box.append(gh)}const grid=el('div','','as-grid');g.forEach(a=>grid.append(cardOf(a)));box.append(grid)}}
 async function load(){L=await api('/admin/api/assistants');try{T=(await api('/admin/api/proposal-templates')).templates}catch{T=[]}render()}
 try{VIEW=localStorage.getItem('alice.as.view')||'cards'}catch{}
 $('as-q').oninput=()=>{Q=$('as-q').value;render()};
 $('as-new').onclick=()=>{newKind='qa';open.clear();open.add('__new__');render();$('as-editor').scrollIntoView({behavior:'smooth',block:'start'})};
 run(load);
}
"""

SCRIPT += r"""
if(PAGE==='agents'){
 const st={L:null,sel:'',tab:'overview',view:(()=>{try{return localStorage.getItem('alice-agents-view')||'cards'}catch{return 'cards'}})()};
 const STATUS={active:['Active','approved'],paused:['Paused','proposed'],stopped:['Stopped','rejected']};
 const RUNST={complete:'v-ok',failed:'v-bad',running:'v-run',skipped:'v-none',blocked:'v-warn',interrupted:'v-warn','failed (cleared)':'v-none'};
 const TABS=[['overview','Overview'],['runs','Runs'],['data','Data touched'],['settings','Settings'],['history','History']];
 const when=d=>d?new Date(d).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'—';
 const usd=v=>DEMO?'':'$'+(v||0).toFixed(v>=1?2:4);
 const dq=DEMO?'demo=1':'';
 const plural=(ty,n)=>n+' '+(n===1?ty:({memory:'memories'}[ty]||ty+'s'));
 const badge=(t,c)=>el('span',t,'badge '+c);
 const pill=a=>{const [l,c]=STATUS[a.status]||[a.status,''];return el('span',l,c)};
 const btn=(label,fn,cls)=>{const b=el('button',label);b.type='button';if(cls)b.className=cls;b.onclick=()=>run(fn);return b};
 function readUrl(){const q=new URLSearchParams(location.search);st.sel=q.get('agent')||'';st.tab=q.get('tab')||'overview'}
 function go(sel,tab='overview',push=true){st.sel=sel;st.tab=tab;const url=sel?'?agent='+sel+(tab!=='overview'?'&tab='+tab:''):location.pathname;push?history.pushState(null,'',url):history.replaceState(null,'',url);render()}
 window.addEventListener('popstate',()=>{readUrl();render()});
 async function load(){st.L=await api('/admin/api/agents');render()}
 function render(){const a=st.L.agents.find(x=>x.id===st.sel);$('ag-list').hidden=!!a;$('ag-detail').hidden=!a;if(a)detail(a);else list();window.scrollTo(0,0);document.querySelector('.content').scrollTop=0}
 // ---- list: two groups of compact cards
 function card(a){const c=el('button','','ag-card'+(a.status!=='active'?' off':'')+(a.review_overdue?' due':''));c.type='button';c.onclick=()=>go(a.id);
  const top=el('div','','ag-card-top');top.append(el('strong',a.name),pill(a));c.append(top);
  c.append(el('div',a.purpose,'ag-card-purpose'));
  const foot=el('div','','ag-card-foot');const lr=a.last_run;
  foot.append(el('span',lr?('Last run '+when(lr.started_at)):(a.kind==='app'?'No calls yet':'Not run yet')));
  if(lr)foot.append(badge(a.kind==='app'&&lr.status==='running'?'today':lr.status,RUNST[lr.status]||'v-none'));
  foot.append(el('span',a.kind==='app'?plural('call',a.calls_month)+' this month':plural('run',a.runs_month)+(DEMO?'':' · '+usd(a.cost_month)),'ag-card-stat'));
  c.append(foot);
  const flags=el('div','','ag-card-flags');if(a.status_reason&&a.status!=='active')flags.append(el('span',a.status_reason,'small'));if(a.external_content)flags.append(el('span','Reads outside content','tag'));if(a.review_overdue)flags.append(el('span','⚑ Review overdue','flag'));if(a.waiting)flags.append(el('span',a.waiting+' waiting for you','flag'));if(flags.childElementCount)c.append(flags);
  return c}
 function list(){$('ag-view').replaceChildren(...[['cards','Cards'],['list','List'],['map','System map']].map(([k,l])=>{const b=el('button',l,'chip'+(st.view===k?' on':''));b.type='button';b.onclick=()=>{st.view=k;try{localStorage.setItem('alice-agents-view',k)}catch{}list()};return b}));
  $('ag-cards-wrap').hidden=st.view==='map';$('ag-map-wrap').hidden=st.view!=='map';if(st.view==='map'){drawMap();return}
  const L=st.L,internal=L.agents.filter(a=>a.kind!=='app'),apps=L.agents.filter(a=>a.kind==='app'),off=L.agents.filter(a=>a.status!=='active').length;
  $('ag-summary').textContent=internal.length+' automations · '+apps.length+' connected apps'+(off?' · '+off+' paused or stopped':'');
  const q=($('ag-search').value||'').trim().toLowerCase();
  const attn=a=>a.status!=='active'||a.review_overdue||a.waiting>0||(a.last_run&&a.last_run.status==='failed');
  const gname=Object.fromEntries((L.groups||[]).map(g=>[g.id,g.name]));
  const match=a=>!q||(a.name+' '+a.purpose+' '+a.id+' '+(gname[a.group]||'')).toLowerCase().includes(q);
  const closed=(()=>{try{return JSON.parse(localStorage.getItem('alice-agents-closed')||'[]')}catch{return []}})();
  const groups=(L.groups||[]).map(g=>({...g,rows:L.agents.filter(a=>(a.group||(a.kind==='app'?'apps':'other'))===g.id)})).filter(g=>g.rows.length);
  const sorted=rows=>rows.filter(match).sort((a,b)=>attn(b)-attn(a)||(a.group_order??99)-(b.group_order??99)||a.name.localeCompare(b.name));
  $('ag-groups').hidden=st.view!=='cards';$('ag-table-wrap').hidden=st.view!=='list';
  if(st.view==='list'){const t=el('table','','mem-table ag-table');const h=document.createElement('tr');for(const x of ['Agent','Status','Last run','This month','Cost'])h.append(el('th',x));const th=document.createElement('thead');th.append(h);t.append(th);const tb=document.createElement('tbody');let any=false;
   for(const g of groups){const rows=sorted(g.rows);if(!rows.length)continue;any=true;const gr=document.createElement('tr');gr.className='ag-trow-g';const gc=el('td','');gc.colSpan=5;gc.append(el('strong',g.name),el('span',' '+rows.length,'ag-count'));gr.append(gc);tb.append(gr);
    for(const a of rows){const tr=document.createElement('tr');tr.className='ag-trow'+(a.status!=='active'?' off':'');tr.tabIndex=0;tr.onclick=()=>go(a.id);tr.onkeydown=e=>{if(e.key==='Enter')go(a.id)};
     const c1=document.createElement('td');c1.append(el('strong',a.name),el('div',a.purpose,'muted small ag-tpurpose'));if(attn(a))c1.append(el('div','⚑ needs attention'+(a.status_reason&&a.status!=='active'?': '+a.status_reason:a.waiting?': '+a.waiting+' waiting for you':''),'small ag-tattn'));
     const c2=document.createElement('td');c2.append(pill(a));const lr=a.last_run;const c3=document.createElement('td');c3.className='small';if(lr){c3.append(document.createTextNode(when(lr.started_at)+' '),badge(a.kind==='app'&&lr.status==='running'?'today':lr.status,RUNST[lr.status]||'v-none'))}else c3.append(el('span',a.kind==='app'?'No calls yet':'Not run yet','muted'));
     tr.append(c1,c2,c3,el('td',a.kind==='app'?plural('call',a.calls_month):plural('run',a.runs_month)+(a.failed_month?' · '+a.failed_month+' failed':''),'small'),el('td',DEMO?'—':usd(a.cost_month),'num'));tb.append(tr)}}
   if(!any){const tr=document.createElement('tr');const td=el('td',q?'No match.':'No agents yet.','muted');td.colSpan=5;tr.append(td);tb.append(tr)}
   t.append(tb);$('ag-table-wrap').replaceChildren(t);return}
  const box=$('ag-groups');box.replaceChildren();
  for(const g of groups){const rows=sorted(g.rows),n=g.rows.filter(attn).length,gid='ag-g-'+g.id;
   const d=document.createElement('details');d.className='ag-group';d.id=gid;const sm=document.createElement('summary');sm.append(el('h2',g.name),el('span',q?rows.length+' of '+g.rows.length:String(g.rows.length),'ag-count'),el('span',n?'⚑ '+n+' need'+(n===1?'s':'')+' attention':'','ag-attn'));d.append(sm);
   d.append(el('p',g.about,'muted small ag-gabout'));const cards=el('div','','ag-cards');cards.append(...(rows.length?rows.map(card):[el('div','No match.','ag-empty')]));d.append(cards);
   d.open=q?rows.length>0:!closed.includes(gid);
   d.ontoggle=()=>{if(q)return;try{const c=new Set(JSON.parse(localStorage.getItem('alice-agents-closed')||'[]'));d.open?c.delete(gid):c.add(gid);localStorage.setItem('alice-agents-closed',JSON.stringify([...c]))}catch{}};
   box.append(d)}}
 $('ag-search').oninput=()=>list();
 // ---- detail: header, tabs, one tab at a time
 function detail(a){const box=$('ag-detail');box.replaceChildren();
  const head=el('section','','ag-head');const back=el('button','← All agents','secondary');back.type='button';back.onclick=()=>go('');
  const title=el('div','','ag-title');title.append(el('h2',a.name),pill(a),el('span',a.kind==='app'?'Connected app':'Alice automation','tag k-knowledge'));
  const ctl=el('div','','ag-ctl');
  if(a.status!=='active')ctl.append(btn('Resume',async()=>{await api('/admin/api/agents/'+a.id+'/status','POST',{status:'active'});$('notice').textContent=a.name+' resumed.';await load()}));
  if(a.status==='active')ctl.append(btn('Pause',async()=>{const r=prompt('Why pause '+a.name+'? (optional)');if(r===null)return;await api('/admin/api/agents/'+a.id+'/status','POST',{status:'paused',reason:r});$('notice').textContent=a.name+' paused. It will not run until you resume it.';await load()},'secondary'));
  if(a.status!=='stopped')ctl.append(btn('Stop',async()=>{if(!confirm('Stop '+a.name+'? It will not run, and an app will be refused every call, until you resume it.'))return;await api('/admin/api/agents/'+a.id+'/status','POST',{status:'stopped',reason:'stopped by you'});await load()},'secondary'));
  head.append(back,title,ctl);
  if(a.status_reason&&a.status!=='active')head.append(el('p',a.status==='paused'?'Paused: '+a.status_reason:a.status_reason,'ag-reason'));
  const tabs=el('div','','mem-tabs ag-tabs');for(const [k,l] of TABS){const b=el('button',l,'chip'+(st.tab===k?' on':''));b.type='button';b.onclick=()=>go(a.id,k,false);tabs.append(b)}head.append(tabs);
  box.append(head);const body=el('section','');box.append(body);
  ({overview,runs:runsTab,data:dataTab,settings,history:historyTab}[st.tab]||overview)(a,body)}
 function overview(a,body){
  body.append(el('p',a.purpose,'ag-purpose'),anatomy(a));
  const tiles=el('div','','stats ag-stats');const tile=(n,l)=>{const t=el('div','','stat');t.append(el('strong',n),el('span',l));return t};
  if(a.kind==='app')tiles.append(tile(String(a.calls_month),'tool calls this month'),tile(String(a.waiting),'proposals waiting'));
  else{tiles.append(tile(String(a.runs_month),'runs this month'),tile(String(a.failed_month),'failed'));if(!DEMO)tiles.append(tile(usd(a.cost_month),a.budget_usd!=null?'of $'+a.budget_usd.toFixed(2)+' budget':'cost (no agent budget)'))}
  body.append(tiles);
  const facts=el('dl','','ag-facts');for(const [k,v] of [['Starts',a.trigger],['Reads',a.reads],['Writes',a.writes],['Owner',a.owner],['Review access by',a.review_by||'—'],['Settings version',String(a.version)]]){facts.append(el('dt',k),el('dd',v||'—'))}
  if(a.external_content){facts.append(el('dt','Outside content'),el('dd','Reads content from outside Alice. Keep it to proposing only.'))}
  body.append(facts);
  const recent=el('div','');body.append(el('h3','Latest '+(a.kind==='app'?'days':'runs')),recent);
  api('/admin/api/agents/'+a.id+'/runs').then(r=>{if(!r.runs.length){recent.append(el('p','Nothing yet.','muted small'));return}for(const x of r.runs.slice(0,5)){const row=el('div','','ag-mini');row.append(el('span',when(x.started_at),'small'),badge(a.kind==='app'&&x.status==='running'?'today':x.status,RUNST[x.status]||'v-none'),el('span',(x.cost_usd&&!DEMO?usd(x.cost_usd)+' · ':'')+x.calls+' calls','small muted'),el('span',DEMO?'':(x.error||x.summary||''),'small muted ag-mini-sum'));recent.append(row)}
   const all=el('button','All runs →','secondary');all.type='button';all.onclick=()=>go(a.id,'runs',false);recent.append(all)}).catch(e=>recent.append(el('p',e.message,'small')))}
 async function runsTab(a,body){const r=await api('/admin/api/agents/'+a.id+'/runs');
  if(!r.runs.length){body.append(el('p',a.kind==='app'?'No tool calls yet.':'No runs yet. Runs that had nothing to do are not kept.','muted'));return}
  const t=el('table','','mem-table');const h=document.createElement('tr');for(const x of ['Started','Trigger','Outcome','Cost / calls','Summary'])h.append(el('th',x));t.append(h);
  for(const x of r.runs){const tr=document.createElement('tr');const b=el('button',when(x.started_at),'mem-title');b.type='button';const c1=document.createElement('td');c1.append(b);const c3=document.createElement('td');c3.append(badge(a.kind==='app'&&x.status==='running'?'today':x.status,RUNST[x.status]||'v-none'));
   tr.append(c1,el('td',x.trigger,'small'),c3,el('td',(x.cost_usd&&!DEMO?usd(x.cost_usd)+' · ':'')+x.calls+' calls','small'),el('td',DEMO?'':(x.error||x.summary||''),'small'));t.append(tr);
   const dr=document.createElement('tr');dr.hidden=true;const dtd=document.createElement('td');dtd.colSpan=5;dr.append(dtd);t.append(dr);
   b.onclick=()=>run(async()=>{if(!dr.hidden){dr.hidden=true;return}const d=await api('/admin/api/agent-runs/'+x.id+(dq?'?'+dq:''));dtd.replaceChildren();
    const tch=Object.entries(d.touched).map(([k,v])=>(k==='read'?'Read ':'Wrote ')+Object.entries(v).map(([ty,n])=>plural(ty,n)).join(', ')).join(' · ');if(tch)dtd.append(el('p',tch,'small'));
    const l=el('div','','ag-events');for(const e of d.events.slice(-200)){const row=el('div','','small');row.append(el('span',new Date(e.at).toLocaleTimeString('en-GB')+'  ','muted'),el('strong',e.kind+' '),document.createTextNode((e.target_name||[e.target_type,e.target_id].filter(Boolean).join(' '))+(e.detail?' · '+e.detail:'')));l.append(row)}
    if(!d.events.length)l.append(el('p','No details recorded for this run.','muted small'));dtd.append(l);dr.hidden=false})}
  body.append(t)}
 const DT={days:30,kind:''};
 const STATUSNAME={approved:'Active',active:'Active',proposed:'Awaiting approval',draft:'Draft',rejected:'Rejected',retired:'Retired',superseded:'Superseded',archived:'Archived',replaced:'Replaced',suggested:'Suggested',deleted:'No longer in Alice'};
 const LABNAME={general:'General',internal:'Internal',client:'Client-confidential',local:'Local only'};
 async function dataTab(a,body){const d=await api('/admin/api/agents/'+a.id+'/touched?days='+DT.days+(dq?'&'+dq:''));
  const bar=el('div','','dt-bar');
  const chips=(opts,cur,set)=>{const g=el('div','','chips');for(const [k,l] of opts){const b=el('button',l,'chip'+(cur===k?' on':''));b.type='button';b.onclick=()=>{set(k);body.replaceChildren();run(()=>dataTab(a,body))};g.append(b)}return g};
  bar.append(chips([[7,'7 days'],[30,'30 days'],[90,'90 days'],[365,'A year']],DT.days,k=>DT.days=k),chips([['','Read and wrote'],['read','Read'],['wrote','Wrote']],DT.kind,k=>DT.kind=k));
  body.append(bar);
  const keep=i=>!DT.kind||i[DT.kind]>0;
  const groups=d.groups.map(g=>({...g,items:g.items.filter(keep)})).filter(g=>g.items.length);
  if(!groups.length){body.append(el('p','Nothing recorded in this period.','muted'));return}
  const total=groups.reduce((n,g)=>n+g.items.length,0);
  body.append(el('p',a.name+' touched '+total+' item'+(total===1?'':'s')+' from '+groups.length+' source'+(groups.length===1?'':'s')+' in the last '+(DT.days===365?'year':DT.days+' days')+': '+groups.map(g=>g.name+' ('+g.items.length+')').join(', ')+'.','muted small'));
  const sent={};for(const g of groups)for(const i of g.items)for(const m of (i.sent_to||[]))sent[m]=(sent[m]||0)+1;
  const sl=Object.entries(sent);body.append(el('p',sl.length?'Sent to: '+sl.map(([m,n])=>m+' ('+n+' item'+(n===1?'':'s')+')').join(', ')+'. Items count as sent when the run that read them called that model; a connected app receives what it reads.':'Nothing it read was sent to a model in this period.','muted small'));
  for(const g of groups){const sec=document.createElement('details');sec.open=true;sec.className='dt-group';
   const sm=el('summary','','dt-head');sm.append(el('strong',g.name),el('span',g.items.length+' item'+(g.items.length===1?'':'s')+(g.read?' · '+g.read+' read':'')+(g.wrote?' · '+g.wrote+' written':''),'muted small'));
   if(g.key==='web'||g.key==='library')sm.append(el('span','Outside Alice','tag dt-out'));sec.append(sm);
   if(g.note)sec.append(el('p',g.note,'muted small dt-note'));
   const t=el('table','','mem-table dt-table');const h=document.createElement('tr');for(const x of ['Item and where it is','What happened','Sent to','Status','Last'])h.append(el('th',x));t.append(h);
   for(const i of g.items){const tr=document.createElement('tr');const c1=document.createElement('td');
    const nm=i.href&&g.key!=='web'?Object.assign(el('a',i.target_name),{href:i.href}):el('strong',i.target_name);c1.append(nm,el('div',i.type_name,'muted small'));
    if(i.location){const loc=el('div','','dt-loc');
     if(g.key==='web'&&i.href){const u=el('a',i.location);u.href=i.href;u.target='_blank';u.rel='noopener noreferrer';loc.append(u)}
     else loc.append(el('code',i.location));
     if(i.where)c1.append(el('div',i.where,'muted small'));
     if(g.key==='library'||(g.key!=='web'&&/[\\\/]/.test(i.location)&&!/^https?:/.test(i.location))){const cp=el('button','Copy path','secondary mini-act');cp.type='button';cp.onclick=()=>{navigator.clipboard?.writeText(i.location);cp.textContent='Copied'};loc.append(cp)}
     c1.append(loc)}
    const c2=document.createElement('td');c2.className='small';
    const parts=[];if(i.read)parts.push('Read'+(i.read>1?' '+i.read+'×':''));if(i.wrote)parts.push((g.key==='organisations'||g.key==='memories'||g.key==='knowledge'?'Proposed or wrote':'Wrote')+(i.wrote>1?' '+i.wrote+'×':''));
    c2.append(el('div',parts.join(' · ')));for(const x of (i.details||[]))c2.append(el('div',x,'muted'));
    const c4=document.createElement('td');c4.className='small';
    if(i.sent_to&&i.sent_to.length)for(const m of i.sent_to)c4.append(el('div',m,'dt-sent'));else if(i.read)c4.append(el('span','Not sent to a model','muted'));
    if(i.produced_by&&i.produced_by.length)c4.append(el('div','Written using '+i.produced_by.join(', '),'muted'));
    if(!c4.childNodes.length)c4.append(el('span','—','muted'));
    const c3=document.createElement('td');if(i.status)c3.append(badge(i.status==='deleted'&&g.key==='library'?'File no longer there':(STATUSNAME[i.status]||i.status),i.status==='deleted'?'v-warn':'v-none'));if(i.label)c3.append(document.createTextNode(' '),el('span',LABNAME[i.label]||i.label,'badge k-lab-'+i.label));
    if(!i.status&&!i.label)c3.append(el('span',g.key==='web'||g.key==='library'?'Not stored':'—','muted small'));
    tr.append(c1,c2,c4,c3,el('td',when(i.last)+(i.first!==i.last?' (first '+when(i.first)+')':''),'small'));t.append(tr)}
   sec.append(t);body.append(sec)}
 }
 function settings(a,body){
  const pu=document.createElement('textarea');pu.value=a.purpose;pu.maxLength=1000;pu.rows=3;const lp=el('label','Purpose and tasks');lp.append(pu);body.append(lp);
  const lim=el('div','','k-meta-row');const extra={};
  const bud=document.createElement('input');bud.type='number';bud.min='0';bud.max='1000';bud.step='0.5';bud.placeholder='No agent limit';bud.value=a.budget_usd??'';
  const rb=document.createElement('input');rb.type='date';rb.value=a.review_by||'';
  if(a.kind!=='app'){const l1=el('label','Monthly budget (USD)');l1.append(bud);lim.append(l1)}
  const l2=el('label','Review access by');l2.append(rb);lim.append(l2);body.append(lim);
  if(a.kind==='app'){const p=a.permissions;
   const mode=document.createElement('select');for(const [v,t2] of [['propose','Read and propose'],['read','Read only']]){const o=document.createElement('option');o.value=v;o.textContent=t2;mode.append(o)}mode.value=p.mode||'propose';const lm=el('label','Mode');lm.append(mode);lim.append(lm);
   const calls=document.createElement('input');calls.type='number';calls.min='1';calls.max='100000';calls.value=p.max_calls_per_day??'';calls.placeholder='No limit';const lc=el('label','Tool calls per day');lc.append(calls);lim.append(lc);
   const perm=el('div','','ag-perms');const group=(title,all,chosen,hint)=>{const g=el('div','','ag-perm');g.append(el('strong',title),el('span',hint,'muted small'));const set=new Set(chosen||[]);const wrap=el('div','','r-checks');for(const v of all){const l=el('label','','r-check');const i=document.createElement('input');i.type='checkbox';i.checked=set.has(v);i.onchange=()=>i.checked?set.add(v):set.delete(v);l.append(i,document.createTextNode(' '+v));wrap.append(l)}g.append(wrap);perm.append(g);return set};
   extra.tools=group('Tools',st.L.tools,p.tools,' none ticked = all tools');extra.categories=group('Memory categories',st.L.categories,p.categories,' none ticked = everything the external rules allow');extra.labels=group('Knowledge labels',st.L.labels,p.labels,' none ticked = everything the external rules allow');
   extra.mode=mode;extra.calls=calls;body.append(el('h3','Permissions'),el('p','These only narrow what the rules already allow external apps; they can never widen it.','muted small'),perm)}
  const an=a.anatomy||{};const ae=el('div','','ag-anat-edit');ae.append(el('h3','How it is described'),el('p','Shown in the anatomy diagram and the system map. Describe what it really does.','muted small'));
  const inp=(label,val,rows)=>{const l=el('label',label);const i=document.createElement(rows?'textarea':'input');if(rows)i.rows=rows;i.value=val||'';l.append(i);ae.append(l);return i};
  const fModel=inp('Model',an.model==='temple'?'temple (Temple\'s reviewer setting)':an.model),fId=a.kind==='app'?inp('Identity',an.identity):null,fIns=inp('Instructions, in a line or two',an.instructions,2);
  const fTools=a.kind==='app'?null:inp('Tools (one per line)',(an.tools||[]).join('\n'),3),fOut=inp('Produces (one per line)',(an.outputs||[]).join('\n'),2),fGate=inp('Your decision',an.gate);
  const checks=(title,all,chosen)=>{const g=el('div','','ag-perm');g.append(el('strong',title));const set=new Set(chosen||[]);const w=el('div','','r-checks');for(const [v,t2] of all){const l=el('label','','r-check');const i=document.createElement('input');i.type='checkbox';i.checked=set.has(v);i.onchange=()=>i.checked?set.add(v):set.delete(v);l.append(i,document.createTextNode(' '+t2));w.append(l)}g.append(w);ae.append(g);return set};
  const fData=checks('Data it reaches',Object.entries(st.L.data_sources),an.data),fGuard=checks('Guardrails that apply',st.L.rules.map(r=>[r.id,r.name+(r.enabled?'':' (off)')]),an.guardrails);
  body.append(ae);
  const lines=v=>v.split('\n').map(x=>x.trim()).filter(Boolean);
  body.append(btn('Save settings',async()=>{const b={purpose:pu.value,review_by:rb.value,note:''};
   b.anatomy={model:fModel.value.startsWith('temple')?'temple':fModel.value,instructions:fIns.value,outputs:lines(fOut.value),gate:fGate.value,data:[...fData],guardrails:[...fGuard]};if(fId)b.anatomy.identity=fId.value;if(fTools)b.anatomy.tools=lines(fTools.value);
   if(a.kind!=='app'){if(bud.value==='')b.clear_budget=true;else b.budget_usd=+bud.value}
   else b.permissions={mode:extra.mode.value,max_calls_per_day:extra.calls.value===''?null:+extra.calls.value,tools:[...extra.tools],categories:[...extra.categories],labels:[...extra.labels]};
   const n=prompt('What changed and why? (kept in the history; optional)');if(n===null)return;b.note=n;
   await api('/admin/api/agents/'+a.id,'PUT',b);$('notice').textContent='Saved as version '+(a.version+1)+'.';await load()}))}
 async function historyTab(a,body){const d=await api('/admin/api/agents/'+a.id+'/versions');
  for(const v of d.versions){const p=el('div','','card');p.append(el('strong','Version '+v.version+' · '+when(v.changed_at)+' · '+v.changed_by));if(v.note)p.append(el('div',v.note,'small'));const det=document.createElement('details');det.append(el('summary','Settings'),el('pre',JSON.stringify(v.config,null,1)));p.append(det);body.append(p)}
  body.append(el('p','Pauses, resumes and stops are in the Activity log (type: Agents).','muted small'))}

 // ---- anatomy: the parts of one agent, left to right
 function anatomy(a){const an=a.anatomy_live||{};const wrap=el('div','','anat');
  const stage=(title,cls,fill)=>{const c=el('div','','anat-stage '+cls);c.append(el('div',title,'anat-title'));fill(c);wrap.append(c);return c};
  const items=(c,list,empty)=>{if(!list||!list.length){c.append(el('div',empty||'—','anat-empty'));return}const u=el('ul','');for(const x of list)u.append(el('li',x));c.append(u)};
  stage('Trigger','t-trigger',c=>c.append(el('div',a.trigger,'anat-text')));
  stage('Agent','t-agent',c=>{c.append(el('strong',a.name),el('div',an.model||'','anat-model'));if(an.identity)c.append(el('div','Identity: '+an.identity,'anat-small'));if(an.instructions)c.append(el('div','“'+an.instructions+'”','anat-instr'));
   c.append(el('div',a.kind==='app'?plural('tool call',a.calls_month)+' this month':plural('run',a.runs_month)+' this month'+(DEMO?'':' · '+usd(a.cost_month)),'anat-small'))});
  stage('Reaches','t-reach',c=>{c.append(el('div','Data','anat-sub'));items(c,(an.data||[]).map(d=>d.name));c.append(el('div','Tools','anat-sub'));items(c,an.tools)});
  stage('Guardrails','t-guard',c=>{const u=el('ul','','anat-guards');for(const g of an.guardrails||[]){const li=el('li',(g.on?'✓ ':'○ ')+g.name);if(!g.on){li.className='off';li.title='This rule is switched off'}u.append(li)}c.append(u);
   c.append(el('div',a.kind==='app'?'Plus this app\'s own limits (Settings)':(a.budget_usd!=null?'Plus a monthly budget':'Pauses itself after 3 failures'),'anat-small'))});
  stage('Produces','t-out',c=>items(c,an.outputs));
  stage('You decide','t-you',c=>c.append(el('div',an.gate||'You approve','anat-text')));
  return wrap}
 // ---- system map: agents around Alice's data, inside the rules, with you at the gate
 const SVGNS='http://www.w3.org/2000/svg';
 function S(tag,attrs,text){const e=document.createElementNS(SVGNS,tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(text!=null)e.textContent=text;return e}
 function drawMap(){const L=st.L,box=$('ag-map');box.replaceChildren();
  const left=L.agents.filter(a=>a.kind!=='app'),right=L.agents.filter(a=>a.kind==='app');
  const STORES=[['memories','Memories and decisions'],['knowledge','Knowledge and files'],['organisations','Organisation profiles'],['chats','Chats and conversations'],['activity','Activity and usage']];
  const OUTSIDE=[['web','The public web','web search, cited URLs'],['documents','Document sources','SharePoint, Fabric, Power Platform'],['input','What people type','questions, transcripts']];
  // left to right: data outside Alice → automations → Alice's data (inside the rules) ← connected apps; you at the gate
  const rowH=58,top=70,W=1320,srcX=115,autoX=410,cx=770,appX=W-150,coreW=290,coreY=top-10,coreH=STORES.length*rowH+20;
  const rows=Math.max(left.length,right.length,STORES.length+3),youY=coreY+coreH+70,H=Math.max(top+rows*rowH+40,youY+70);
  const svg=S('svg',{viewBox:'0 0 '+W+' '+H,class:'ag-map-svg',role:'img','aria-label':'System map: data sources outside Alice, Alice automations, Alice’s data and connected apps'});
  const defs=S('defs');const mk=S('marker',{id:'arw',viewBox:'0 0 10 10',refX:'9',refY:'5',markerWidth:'7',markerHeight:'7',orient:'auto-start-reverse'});mk.append(S('path',{d:'M0,0 L10,5 L0,10 z',fill:'#7e95a6'}));defs.append(mk);svg.append(defs);
  svg.append(S('text',{x:srcX,y:34,'text-anchor':'middle',class:'m-head'},'Outside Alice'),S('text',{x:autoX,y:34,'text-anchor':'middle',class:'m-head'},'Alice automations'),S('text',{x:appX,y:34,'text-anchor':'middle',class:'m-head'},'Connected apps'));
  // the rules boundary around Alice's own data
  svg.append(S('rect',{x:cx-coreW/2-40,y:coreY-34,width:coreW+80,height:coreH+68,rx:22,class:'m-rules'}));
  svg.append(S('text',{x:cx,y:coreY-14,'text-anchor':'middle',class:'m-rules-label'},'Alice’s data, rules enforced at the boundary'));
  const links=S('g',{class:'m-links'});svg.append(links);
  const ys={};STORES.forEach(([k,label],i)=>{const y=coreY+10+i*rowH;ys[k]=y+20;svg.append(S('rect',{x:cx-coreW/2,y,width:coreW,height:40,rx:9,class:'m-store'}),S('text',{x:cx,y:y+25,'text-anchor':'middle',class:'m-store-t'},label))});
  // data sources outside Alice, spread down the left: read when needed, never stored
  const span=Math.max(left.length,3)*rowH,srcW=190,srcY={};
  svg.append(S('rect',{x:srcX-srcW/2-12,y:top-12,width:srcW+24,height:span+8,rx:16,class:'m-outside'}));
  OUTSIDE.forEach(([k,label,sub],i)=>{const y=top+Math.round((i+0.5)*span/OUTSIDE.length)-28;srcY[k]=y+24;
   svg.append(S('rect',{x:srcX-srcW/2,y,width:srcW,height:48,rx:9,class:'m-src'}),S('text',{x:srcX,y:y+20,'text-anchor':'middle',class:'m-store-t'},label),S('text',{x:srcX,y:y+37,'text-anchor':'middle',class:'m-small'},sub))});
  svg.append(S('text',{x:srcX,y:top+span+14,'text-anchor':'middle',class:'m-small'},'Read when needed and checked'),S('text',{x:srcX,y:top+span+28,'text-anchor':'middle',class:'m-small'},'by the rules; never stored'));
  // you, at the gate
  svg.append(S('line',{x1:cx,y1:coreY+coreH+34,x2:cx,y2:youY-4,class:'m-gate','marker-end':'url(#arw)'}));
  svg.append(S('text',{x:cx+10,y:coreY+coreH+56,class:'m-small'},'proposals wait for you'));
  svg.append(S('rect',{x:cx-110,y:youY,width:220,height:40,rx:20,class:'m-you'}),S('text',{x:cx,y:youY+25,'text-anchor':'middle',class:'m-you-t'},'You: approve, retire, pause'));
  const node=(a,x,y,side)=>{const g=S('g',{class:'m-node'+(a.status!=='active'?' off':'')+(a.kind==='app'?' app':''),tabindex:'0',role:'link'});g.append(S('title',{},a.name+' · '+a.status));
   g.append(S('rect',{x:x-120,y,width:240,height:44,rx:10}));const nm=a.name.replace(/^Temple: /,'');g.append(S('text',{x:x-104,y:y+19,class:'m-name'},nm.length>26?nm.slice(0,25)+'…':nm));
   g.append(S('text',{x:x-104,y:y+35,class:'m-sub'},a.status!=='active'?a.status:(a.kind==='app'?plural('call',a.calls_month)+' this month':plural('run',a.runs_month)+' this month')));
   g.append(S('circle',{cx:x+104,cy:y+22,r:5,class:'m-dot '+a.status}));
   g.onclick=()=>go(a.id);g.onkeydown=e=>{if(e.key==='Enter')go(a.id)};
   const cls='m-link'+(a.kind==='app'?' app':'')+(a.status!=='active'?' off':'');
   for(const d of (a.anatomy_live?.data||[])){
    if(ys[d.key]!=null){const x1=side<0?x+120:x-120,x2=side<0?cx-coreW/2-2:cx+coreW/2+2;links.append(S('path',{d:`M${x1},${y+22} C${(x1+x2)/2},${y+22} ${(x1+x2)/2},${ys[d.key]} ${x2},${ys[d.key]}`,class:cls}))}
    else if(srcY[d.key]!=null&&side<0){const x1=srcX+srcW/2+2,x2=x-122;links.append(S('path',{d:`M${x1},${srcY[d.key]} C${(x1+x2)/2},${srcY[d.key]} ${(x1+x2)/2},${y+22} ${x2},${y+22}`,class:cls+' ext','marker-end':'url(#arw)'}))}}
   svg.append(g)};
  left.forEach((a,i)=>node(a,autoX,top+i*rowH,-1));right.forEach((a,i)=>node(a,appX,top+i*rowH,1));
  box.append(svg);
  $('ag-map-note').textContent='Left to right: data sources outside Alice (dashed) feed the automations that read them; solid lines show the Alice data each agent reaches, always through the rules. Connected apps only reach Alice’s data. Greyed agents are paused or stopped. Click one to open it.'}
 readUrl();run(load);
}
"""

SCRIPT += r"""
if(PAGE==='rule-packs'){
 const st={P:null,pack:new URLSearchParams(location.search).get('pack')||(()=>{try{return localStorage.getItem('alice-rp-pack')||'care'}catch{return 'care'}})(),res:null,ran:false};
 const KIND={enforced:'Enforced in code',gate:'Human sign-off',guidance:'Guidance to the AI'};
 const BLOCKISH=['block','escalate','review'];
 async function load(){st.P=await api('/admin/api/rule-packs');render()}
 function providers(P){const sel=$('rp-provider'),cur=sel.value||'tenant';sel.replaceChildren(...P.providers.map(p=>{const o=el('option',p.name);o.value=p.id;return o}));sel.value=cur}
 const pack=()=>st.P.packs.find(p=>p.id===st.pack)||st.P.packs[0];
 function render(){const P=pack(),on=st.P.state[P.id];providers(P);
  $('rp-packs').replaceChildren(...st.P.packs.map(p=>{const b=el('button',p.name+((st.P.applied||[]).includes(p.id)?' ●':''),'chip'+(p.id===P.id?' on':''));if((st.P.applied||[]).includes(p.id))b.title='Applied to live rules';b.type='button';b.setAttribute('role','tab');b.setAttribute('aria-selected',p.id===P.id);
   b.onclick=()=>{st.pack=p.id;st.res=null;st.ran=false;$('rp-text').value='';try{localStorage.setItem('alice-rp-pack',p.id)}catch{};render()};return b}));
  const n=P.rules.filter(r=>on[r.id]).length,enf=P.rules.filter(r=>on[r.id]&&r.kind!=='guidance').length;
  const h=$('rp-head');h.replaceChildren();const top=el('div','','mem-head');top.append(el('h2',P.name+' pack'),el('span',(st.P.applied||[]).includes(P.id)?'':'Sandbox until applied: Alice\'s own rules are not changed','muted small'));h.append(top,el('p',P.audience),el('p','Grounded in: '+P.basis,'rp-basis'));
  const meta=el('div','','rp-meta');const stat=el('span','','rp-stat');stat.append(el('strong',n+' of '+P.rules.length),document.createTextNode(' safeguards on · '+enf+' enforced or sign-off'));
  const live=(st.P.applied||[]).includes(P.id);
  const ap=el('button',live?'Remove from live rules':'Apply to live rules',live?'secondary':'primary');ap.type='button';
  ap.onclick=()=>run(async()=>{if(live?!confirm('Remove the '+P.name+' pack from Alice\'s live rules?'):!confirm('Apply the '+P.name+' pack to Alice\'s live rules?\n\nIts switched-on safeguards will check your chat messages and Temple\'s requests: identifiers removed, sensitive requests blocked or sent to a person, guidance added to every model. Alice\'s own rules stay in force. You can remove it at any time on this page or the Rules page.'))return;
   const r=await api('/admin/api/rule-packs/apply','POST',{pack:P.id,apply:!live});st.P.applied=r.applied.map(x=>x.id);$('notice').textContent=live?P.name+' pack removed from live rules.':P.name+' pack applied to live rules. Switches on this page now change live rules.';render()});
  if(live)top.append(el('span','● Live in Alice','rp-live'));
  const b1=el('button','All on','secondary'),b2=el('button','All off','secondary'),b3=el('button','Recommended','secondary');[b1,b2,b3].forEach(b=>b.type='button');
  b1.onclick=()=>change({all_on:true});b2.onclick=()=>change({all_on:false});b3.onclick=()=>change({reset:true});b3.title='Back to the recommended settings for this pack';meta.append(stat,b1,b2,b3,ap);h.append(meta);
  if(live)h.append(el('p','Applied to live rules: switching a safeguard here changes what Alice enforces, and is recorded in Activity. The test box below is still a sandbox.','rp-live-note'));
  const fired={},would={};if(st.res){for(const f of st.res.fired)fired[f.rule]=f;for(const f of st.res.off)would[f.rule]=f}
  const box=$('rp-rules');box.replaceChildren();let theme='';
  for(const r of P.rules){if(r.theme!==theme){theme=r.theme;box.append(el('div',theme,'rp-theme'))}
   const f=fired[r.id],w=would[r.id];const card=el('div','','rp-rule'+(on[r.id]?' on':'')+(f?(BLOCKISH.includes(r.action)?' fired-block':' fired'):'')+(w?' would':''));
   const sw=el('label','','rp-switch');const cb=document.createElement('input');cb.type='checkbox';cb.setAttribute('role','switch');cb.checked=!!on[r.id];cb.disabled=r.locked;cb.setAttribute('aria-label',(on[r.id]?'Turn off ':'Turn on ')+r.name);
   cb.onchange=()=>change({rule:r.id,enabled:cb.checked});sw.append(cb,el('span',''));
   const main=el('div','');const t=el('div','','rp-top');t.append(el('h3',r.name),el('span',r.locked?'Always on':KIND[r.kind],'rp-kind '+(r.locked?'locked':r.kind)),el('span',r.action_label,'rp-act'));
   if(f&&r.action!=='guide'&&r.action!=='log')t.append(el('span','Applied','rp-hit'+(BLOCKISH.includes(r.action)?' blockish':'')));
   if(w)t.append(el('span','Off: would have applied','rp-hit would'));
   main.append(t,el('p',r.what),el('p','Why: '+r.why,'rp-why'));if(f&&r.action!=='guide')main.append(el('p','→ '+f.message,'small'));if(w)main.append(el('p','→ '+w.message,'small'));
   card.append(sw,main);box.append(card)}
  $('rp-samples').replaceChildren(...P.samples.map(x=>{const b=el('button',x.label,'chip');b.type='button';b.onclick=()=>{$('rp-text').value=x.text;test()};return b}));
  result()}
 async function change(body){const r=await api('/admin/api/rule-packs/state','POST',{pack:st.pack,...body});st.P.state=r.state;if(st.ran)await test(true);else render()}
 async function test(quiet){const text=$('rp-text').value.trim();if(!text){if(!quiet)$('notice').textContent='Type a message or pick an example.';return}
  st.res=await api('/admin/api/rule-packs/test','POST',{pack:st.pack,text,provider:$('rp-provider').value});st.ran=true;render();if(!quiet)$('rp-result').scrollIntoView({block:'nearest',behavior:'smooth'})}
 function result(){const out=$('rp-result');out.replaceChildren();const R=st.res;if(!R)return;
  const w=el('div','','rp-out');const ICON={escalated:'⇢',blocked:'⛔',held:'⏸',redacted:'✂',allowed:'✓'};const bn=el('div','','rp-banner '+R.outcome);bn.append(el('span',ICON[R.outcome]||''),el('span',R.headline));w.append(bn);
  const b=el('div','','rp-body');const acts=R.fired.filter(f=>!['guide','log'].includes(f.action));
  if(acts.length){b.append(el('h4','What the safeguards did'));const u=el('ul','');for(const f of acts){const li=el('li','');li.append(el('strong',f.name+': '),document.createTextNode(f.message));u.append(li)}b.append(u)}
  if(R.sent!==null&&R.sent!==undefined){b.append(el('h4','What the AI receives ('+R.provider+')'));const pre=el('pre','','rp-sent');
   for(const part of R.sent.split(/(\[[^\]]+ removed\]|\[user [A-Z]\])/)){if(!part)continue;pre.append(/^\[([^\]]+ removed|user [A-Z])\]$/.test(part)?el('mark',part):document.createTextNode(part))}b.append(pre)}
  if(R.instructions.length){b.append(el('h4','Instructions added for the AI'));const u=el('ul','');R.instructions.forEach(i=>u.append(el('li',i)));b.append(u)}
  const offs=R.off.filter(f=>!['log'].includes(f.action));if(offs.length){b.append(el('h4','Switched off, so not applied'));const u=el('ul','','rp-off');offs.forEach(f=>{const li=el('li','');li.append(el('strong',f.name+': '),document.createTextNode(f.message));u.append(li)});b.append(u)}
  b.append(el('p','Recorded in the audit trail.','muted small'));w.append(b);out.append(w)}
 $('rp-run').onclick=()=>run(()=>test());$('rp-provider').onchange=()=>{if(st.ran)run(()=>test(true))};
 run(load);
}
"""

SCRIPT += r"""
if(PAGE==='rules'){
 async function packs(){const d=await api('/admin/api/rule-packs/applied');$('r-packs-scope').textContent=d.scope;const box=$('r-packs-list');box.replaceChildren();
  if(!d.applied.length)box.append(el('p','No rule packs applied. Alice is running on her own rules below. Open Rule packs to apply one.','muted'));
  for(const p of d.applied){const row=el('div','','rpa');const left=el('div','');left.append(el('strong',p.name+' pack'),el('div','Applied '+new Date(p.applied_at).toLocaleString('en-GB',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})+' · '+p.on+' of '+p.total+' safeguards on ('+p.enforced+' enforced or sign-off, '+p.guidance+' guidance)','small muted'));
   const right=el('div','','arc-actions');const ed=el('a','Change safeguards');ed.href='/admin/rule-packs?pack='+p.id;ed.className='button-link';const rm=el('button','Remove','secondary mini-act');rm.type='button';
   rm.onclick=()=>run(async()=>{if(!confirm('Remove the '+p.name+' pack from live rules?'))return;await api('/admin/api/rule-packs/apply','POST',{pack:p.id,apply:false});$('notice').textContent=p.name+' pack removed from live rules.';await packs()});
   right.append(ed,rm);const rules=el('div',p.rules.map(r=>r.name).join(' · '),'rpa-rules');row.append(left,right,rules);box.append(row)}
  const sv=$('r-packs-svc');sv.replaceChildren();for(const x of d.services){const r=el('label','','r-svc-row');const cb=document.createElement('input');cb.type='checkbox';cb.checked=x.inside;
   cb.onchange=()=>run(async()=>{await api('/admin/api/rule-packs/services','POST',{provider:x.id,inside:cb.checked});$('notice').textContent=x.name+(cb.checked?' counts as inside your tenant.':' counts as outside your tenant.');await packs()});
   r.append(cb,el('span',x.name),el('span',x.inside?'Inside your tenant (UK)':'Outside your tenant','small muted'));sv.append(r)}}
 run(packs);
}
"""

NAV_GROUPS = [('Work', ['home', 'actions', 'temple', 'memories', 'knowledge', 'documents', 'organisations', 'archive']),
              ('Records and settings', ['agents', 'assistants', 'rules', 'rule-packs', 'activity', 'usage'])]


def render_admin(page, token):
    from ui_theme import SHARED_CSS
    title, description = PAGES[page]
    href = lambda key: '/admin' + ('' if key == 'home' else '/' + key)
    listed = [k for _, keys in NAV_GROUPS for k in keys]
    groups = NAV_GROUPS + ([('More', [k for k in PAGES if k not in listed])] if any(k not in listed for k in PAGES) else [])
    nav = ''.join('<div class="grp">' + escape(name) + '</div>' + ''.join(
        '<a href="' + href(k) + '" data-page="' + k + '"' + (' aria-current="page"' if k == page else '') + '>' + escape(PAGES[k][0]) + '</a>'
        for k in keys if k in PAGES) for name, keys in groups)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="icon" href="/static/favicon.png" type="image/png">'
            '<title>' + escape(title) + ' · Alice</title><style>' + SHARED_CSS + CSS + '</style></head><body>'
            '<header class="topbar"><a class="brand" href="/" title="Back to chat"><img src="/static/favicon.png" alt=""><span>ALICE</span></a>'
            '<h1 class="page-title">' + escape(title) + '</h1><div class="sp"></div><button id="demo-toggle" class="bar-link" type="button" title="Demo mode: only the Agents, Rule packs and Organisations pages, with fictional or replaced names and costs hidden">Demo mode</button><a class="bar-link" href="/">← Chat</a></header>'
            '<div class="shell"><aside class="sidebar"><nav aria-label="Command centre">' + nav + '</nav></aside>'
            '<main class="content"><div class="inner"><p class="page-desc">' + escape(description) + '</p><div id="notice" role="status"></div>'
            + SECTIONS[page] + '</div></main></div><script>const PAGE=' + json.dumps(page) + ';'
            + DEMO_PRELUDE + SCRIPT.replace('__TOKEN__', token) + NAV_SCRIPT + '</script></body></html>')


DEMO_PRELUDE = r"""
const DEMO=(()=>{try{return localStorage.getItem('alice-demo')==='1'}catch{return false}})();
const DEMO_PAGES=['agents','rule-packs','organisations'];
if(DEMO&&!DEMO_PAGES.includes(PAGE)){location.replace('/admin/agents');throw new Error('Demo mode: only the Agents, Rule packs and Organisations pages are shown')}
"""

NAV_SCRIPT = r"""
(()=>{const t=document.getElementById('demo-toggle');if(!t)return;t.textContent=DEMO?'Demo mode: on':'Demo mode';t.classList.toggle('demo-on',DEMO);
 t.onclick=()=>{try{localStorage.setItem('alice-demo',DEMO?'0':'1')}catch{}location.href=DEMO?location.href:'/admin/agents'};
 if(!DEMO)return;document.body.classList.add('demo');
 document.querySelectorAll('.sidebar a').forEach(a=>{if(!DEMO_PAGES.includes(a.dataset.page))a.hidden=true});document.querySelectorAll('.sidebar .grp').forEach(g=>g.hidden=true);
 document.querySelectorAll('.bar-link[href="/"]').forEach(a=>a.hidden=true);
 if(!DEMO_PAGES.includes(PAGE)){const inner=document.querySelector('.content .inner');inner.replaceChildren();const s=document.createElement('section');const h=document.createElement('h2');h.textContent='Demo mode is on';const p=document.createElement('p');p.textContent='Only the Agents, Rule packs and Organisations pages are shown, with fictional or replaced names and costs hidden. Turn demo mode off in the top bar to see this page.';const a=document.createElement('a');a.href='/admin/agents';a.textContent='Go to Agents';s.append(h,p,a);inner.append(s)}})();
(async()=>{try{const d=await api('/admin/api/actions');const n={};for(const s of d.sections)n[s.key]=s.count;
 if(DEMO)return;const counts={agents:n.agents||0,actions:d.total,memories:n.proposals||0,knowledge:(n.drafts||0)+(n.replacements||0),organisations:(n.orgfacts||0)+(n.opportunities||0),temple:n.suggestions||0,archive:n.chats||0,rules:n.rules||0};
 for(const [k,v] of Object.entries(counts)){if(!v)continue;const a=document.querySelector('.sidebar a[data-page="'+k+'"]');if(!a)continue;const c=document.createElement('span');c.className='nav-count';c.textContent=v;a.append(c)}}catch{}})();
"""
