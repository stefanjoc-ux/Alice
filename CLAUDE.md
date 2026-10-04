# CLAUDE.md: working on Alice (AI Substrate)

You are working on **Alice**, Stefan's personal AI substrate: a local Windows app giving one chat interface
across several model providers, with governed memory, a knowledge library, a steward called **Temple**,
enforced rule sets, client separation, and a connector for Claude Desktop and Claude Code.
Stefan is the owner and the only user. Write to him in UK English: direct, no filler, no unnecessary caveats.

Read this whole file before changing anything. For what Alice does feature by feature, read the approved
knowledge note "AI Substrate: status summary" through the `alice` connector, or ask Stefan for
`AI-Substrate-status-2026-09-30.txt`.

---

## Rules that must never be broken

1. **Never read, print, log, copy or commit `.env`.** It holds live API keys. Refer to settings by name only
   (e.g. `OPENAI_API_KEY`). Never put a key in code, tests, output or git.
2. **Never modify `data\` directly** (the SQLite database, generated images, imports, logs, browser profile).
   Change data only through the app's own functions. Before any change that alters the database schema,
   tell Stefan to back up `data\` first (copy the folder while the app is stopped).
3. **Schema changes are additive only.** `CREATE TABLE IF NOT EXISTS` and guarded
   `ALTER TABLE … ADD COLUMN` (check `PRAGMA table_info` first). Never drop, rename or rewrite columns or
   tables, and never delete user data in a migration.
4. **The approval gates are the product, and automatic approval is their only shortcut.** Models and Temple only *propose*.
   **Stefan's decision (3 Oct 2026): automatic approval** (`autoapprove.py`, switch on the Actions page, setting `auto_approve`):
   memories, knowledge drafts, organisation facts and Temple's memory/knowledge chat suggestions go live after the same
   security checks a person's approval runs, logged as `auto_approved` (actor Alice) and listed on Actions for 7 days with Undo.
   **Guard rails that must stay:** decisions always wait for Stefan; so does a memory Temple finds clashing (`Conflict: yes`),
   recommends rejecting, says replaces an older one, or could not check; anything proposed through the outside connector
   (`mcp_server.py --external`, i.e. Copilot: wrap proposals in `autoapprove.from_outside`), including conversations it saves;
   rule and guidance changes; retiring or replacing older items; and every mileage entry (Mileage Clerk approvals are
   always Stefan's, per exact entry and action). Do not widen automatic approval past these without his say.
   The older exception still stands: reference summaries uploaded on a Proposal writer page (`auto_approve_references`,
   logged `reference_auto_approved`). Test databases start with automatic approval off (`ALICE_AUTO_APPROVE_DEFAULT=off` in
   `tests/_util.py`); `test_autoapprove.py` switches it on.
5. **Temple is advisory.** It reviews, suggests, categorises and tags. It never approves (automatic approval reads its finished review; Temple itself approves nothing), never overrides a
   human choice (precedence: human > model > Temple), and never changes memory content or status.
6. **Enforced rules run in Python at the point data moves**, never only as model instructions. Any new path
   that sends text to a model, stores a memory or knowledge item, or returns tool output must go through the
   existing checks in `rules_engine.py` (secrets, protective markings, personal identifiers, provider
   allow-lists, external scope, client separation, spending caps). If you add a path, add the check and a test.
7. **Protectively marked material** (government protective markings, Official-Sensitive and above) must never
   reach an external model. Stefan holds SC clearance and works with Scottish public-sector clients; treat this as absolute.
8. **Run the tests before declaring anything done.** Never mark work complete with failing tests.

9. **The internal MCP endpoint (port 8001) trusts its caller and must never be exposed beyond 127.0.0.1.** Anything
   reached from outside goes through `mcp_server.py --external` (port 8002, Entra token on every request), and every
   tool decides what to return with `_who()`: external callers get the external rules and their own provider.

10. **Every automation that calls a model is an agent.** Wrap its entry point with `@agents.tracked('<agent-id>')`
    (register the id in `agents.BUILTIN`), record what it reads/writes with `agents.note()` *outside* any write
    transaction, and every external MCP tool must call `_app('<tool>')` first. Paused or stopped agents must not run.

## How Alice runs

- **Desktop app** (`desktop.py`): tray icon; starts the servers without console windows; opens the chat in
  its own Edge app window; global hotkey (`SUBSTRATE_HOTKEY`, default Ctrl+Alt+Space); window size
  (`SUBSTRATE_WINDOW_SIZE`, default 1440x780). Installed with `Install-Desktop.cmd`.
- **Web app** (`app.py`, FastAPI): http://127.0.0.1:8000. Command centre at `/admin` (opens on Actions).
- **MCP server** (`mcp_server.py`, FastMCP, named "Alice"): HTTP on 127.0.0.1:8001/mcp for the web chat;
  stdio (`--stdio --client "Claude Desktop"`) for Claude Desktop and Claude Code, where the connector is
  named `alice` (set up by `Connect-Claude.cmd`).
- **Data**: `data\substrate.db` (SQLite), `data\images\`, `data\imports\`, `data\logs\` (web.log, mcp.log,
  desktop.log). `AISUBSTRATE_DATA_DIR` overrides the data folder (the tests use this).
- **Settings**: `.env` (never read it; see rule 1).

### In Azure (Tuduma, UK South) — see `infra/main.bicep`, `deploy/`
- One image (`Dockerfile`, packages pinned in `requirements.txt`: add any new package there too, with Stefan's say),
  two Container Apps with one replica each: `alice-web` (`ALICE_ROLE=web`: uvicorn on 8000 plus the internal MCP server on
  127.0.0.1:8001 inside the container; Entra sign-in in front, Stefan only, `/healthz` excluded) and `alice-mcp`
  (`ALICE_ROLE=mcp`: `mcp_server.py --external` on 8002). `deploy/start.sh` starts the role; roles `migrate` and `test` too.
- PostgreSQL Flexible Server on a private network (point-in-time restore replaces "back up data\"); secrets in Key Vault,
  read by a managed identity; `Documents\` and `data\images` on an Azure Files share mounted at `/mnt/alice`.
- `deploy/azure-setup.ps1` builds it in steps (infra, secrets, image, files, migrate, signin, apps, github; `connector` on its own); it never reads .env. Steps deploy the LIVE image unless `-Step image` just built one (`Image-Ref`), so re-running a step never rolls back a promoted version.
- Pipeline (`.github/workflows/deploy.yml`): all suites inside the image (SQLite and PostgreSQL), push, then a new revision
  with no traffic; `deploy/promote.ps1` moves traffic (or `-Rollback`). The opportunity scheduler holds a database lease
  (`scheduler_lease`), so only one process runs it even while two revisions are up.

### Restarting after a change
1. Quit from the tray ("Quit (stops servers)").
2. Run the tests (below).
3. Relaunch from the Start menu.
4. If `mcp_server.py` changed, fully quit and reopen Claude Desktop.

A browser refresh is not enough: the old server process keeps running the old code.

## Checking and testing

```
.venv\Scripts\python.exe -c "import app, mcp_server; print('OK')"
.venv\Scripts\python.exe tests\run_tests.py
.venv\Scripts\python.exe tests\run_tests.py rules import      (only suites whose names match)
```

- The first command catches missing files and syntax errors in seconds.
- The test runner is safe: throwaway data folder per suite, dummy keys even if `.env` has real ones, and
  the OpenAI and Anthropic libraries pointed at a dead address. `test_zz_safety.py` verifies this.
- New tests: `tests\test_<name>.py`, starting with `import _util` then `from _util import t`, **before**
  importing any Alice module. Mock providers; never call a real model.
- Not covered by tests (check by hand): tray behaviour, hotkey, window sizing, voice, page layout.
- **JavaScript lives inside Python strings** (`app.py` for the chat page, `admin_ui.py` for the Command
  centre). Python compiling does not check it. After editing it, extract the rendered `<script>` and run
  `node --check` on it if Node is available; otherwise load the page and watch the browser console.

## Code map

| File | Role |
|---|---|
| `app.py` | Web app: chat page (HTML/JS), chat pipeline and tool loop, all HTTP routes |
| `admin_ui.py` | Command centre pages (HTML/JS per page in `SECTIONS` and `SCRIPT`) |
| `ui_theme.py` | Shared look for chat and Command centre: colours, type, buttons, inputs, top bar (`SHARED_CSS`); the brand block `brand_html()` with the signed-in badge under ALICE (`SIGNIN_CSS`, `SIGNIN_JS`, filled from `GET /me`: the Entra name and email from the Container Apps sign-in headers, trusted only with `ALICE_TRUST_EASYAUTH=1`; on the PC "This computer only"; click for details and Sign out) |
| `dbcompat.py` | PostgreSQL behind the SQLite-style calls (used when `ALICE_DATABASE_URL` is set) |
| `migrate_to_postgres.py` | One-off copy of SQLite into PostgreSQL with per-table verification |
| `substrate_store.py` | Database, chats, memories, categories, archive, decisions, quote matching |
| `rules_engine.py` | Rule sets, detectors, spending caps, retention, guidance compilation |
| `mcp_server.py` | MCP tools for models (read tools, including get_organisation, list_organisations and search_opportunities; propose_record/decision/knowledge, save/append_conversation); `--external` runs the signed-in endpoint. Alice's web chat uses the tools in `app.ALLOWED_TOOLS`; organisation and opportunity results pass client separation (`clients.filter_tool_output`) and secret/marking checks; account managers are never returned |
| `external_auth.py` | Entra ID sign-in for the external endpoint: settings `ALICE_EXT_*`, token checks (`EntraVerifier`: tenant, allowed user, scope, allowed client app), caller label and provider. Copilot sends Entra tokens directly. **Claude** cannot complete an Entra sign-in itself (open Claude issue), so with `ALICE_EXT_CONNECTOR_*` set Alice runs her own OAuth server in front of Entra (`connector_proxy`: FastMCP's `AzureProvider` OAuth proxy; Claude's published identity (CIMD) or registration; callback limited to `https://claude.ai/api/mcp/auth_callback`; consent page; `forward_resource=False` to avoid AADSTS9010010; sign-in records encrypted on the share in `<data>/oauth-connector`). The Entra token that comes back is checked by the same `EntraVerifier` (`proxy._token_validator`), so the same rules apply; `MultiAuth` keeps direct tokens working. Claude's proposals are labelled `[via Claude]` (provider `claude`). App registration "Alice connector sign-in", secret and signing key in Key Vault: `azure-setup.ps1 -Step connector`. Test: `test_claude_connector.py` runs the whole flow against a stand-in Microsoft |
| `temple.py` | Temple memory reviews, queue, settings, `reviewer()` (effective provider) |
| `temple_chat.py` | Temple's suggestions after chat answers |
| `temple_categorise.py` | Temple category assignment |
| `memory_tags.py` | Memory organisation beyond categories: each category has an area (`categories.area`: work, personal or '' = Both; the Memories page's Everything / Work / Personal switch is a view, not a permission), and tags you create (`tags`: name, description, area). Assignments in `record_tags` with `assigned_by` human, temple, suggested or removed (a tag you take off or a suggestion you dismiss is kept as `removed`, so Temple never puts it back). `organised()` wraps `store.organised_records` with area and tag filters and each memory's tags; `tags_for()` also feeds `search_records` (MCP returns tag names) |
| `refs.py` | Reference numbers: `M-0001` memories, `D-0001` decisions, `K-0001` knowledge (all kinds, files included). Proposals keep their own `P-xxxxxx` (from the ID, in `proposals.py`). The random IDs stay the keys; `item_refs` (ref, item_type record/file, item_id; unique both ways) and `ref_counters` (one row per prefix, taken inside BEGIN IMMEDIATE). Given at creation (`store.propose`, `store.propose_decision`, `knowledge.create` are wrapped and return `ref`), never changed or reused; anything inserted another way is numbered by `ensure()` on the next listing or search (which skips items under 5 seconds old so a decision is never numbered as a memory before its kind is set). Searchable on the Memories and Knowledge pages and in `search_records`, `read_file` and `search_files`; refs are returned by the connector tools |
| `temple_tags.py` | Temple tagging (agent `temple-memory-tags`): picks only from your tags, keeps to their areas, never touches your tags; mode `temple_tags` (auto applies at 75%+, suggest, off); each memory goes through `check_outbound` first (failures skipped); runs after categorising for a new memory (`temple_categorise.schedule`), in the background after you add or change a tag, and on Tag with Temple now |
| `temple_ask.py` | Ask Temple (the first tab of the Temple workspace): read-only tools over activity, actions, usage, the agents (`agents_overview`, `agent_runs`), the team of assistants and how they are used (`assistants_overview`, from activity counts; staff questions are never stored), proposals (`proposals_overview`, no cost rates) and how memories are organised (`memory_organisation`: categories and tags with areas and counts, no memory content) |
| `temple_supersede.py` | Temple finds older knowledge a newer item replaces (wording first, then a quoted model check); suggestions only |
| `conversations.py` | Saved conversations, Claude export import (incl. manifest download), whole-chat reviews |
| `knowledge.py` | Knowledge library: kinds, drafts, labels, meeting extracts, Word in/out, replacements (`supersede`, `history`), default review period (`review_days`, 30 by default; set when an item becomes active, never overwrites an existing date) |
| `agents.py` | Agents register: Temple automations (`@agents.tracked`) and connected apps (`app_call` in every MCP tool); runs, data touched, cost, pause/stop, versions. Every model call made inside a run is recorded as a `model` event (`add_cost(usd, provider, model)` from `usage_meter`), which gives Data touched its Sent to column; a connected app counts as the recipient of what it reads. Data touched is grouped by source (`SOURCE_GROUPS`: Internet with URLs, Document library with file paths, then Alice's own data with links, status and label); record web reads as `note('read','web',url,...)` and library reads as `note('read','document',relative_path,...)`. `DATA_SOURCES` includes the outside sources (web, documents, input) drawn in the left column of the system map. `GROUPS` puts each built-in agent in a group by shared job (Proposals, Clients and opportunities, Learning from conversations, Keeping memory and knowledge tidy, Answering questions; apps on their own): add every new agent id to a group. The page has Cards, List and System map views |
| `rule_packs.py` | Demo rule packs (HR team, council social care, security operations, personal data): switchable safeguards and a sandboxed test (never calls a model); a pack can be applied to live rules (`live_check` on chat before saving, blocks/escalations on Temple's requests via `check_outbound`, guidance via `effective_guidance`) with per-service inside/outside-tenant classification |
| `org_research.py` | Temple researches an organisation on the public web (provider web search) and proposes facts, each citing a page the search returned; agent `temple-org-research` |
| `opportunities.py` | Client opportunity scans (profile brief + news via web search) for the organisations you watch (the Watch tick box on each organisation and in the tracker's Watch list = `org_watch.frequency`, clients weekly by default; `set_watch`), on schedule (background thread, `start_scheduler`, only while Alice runs; off when `ALICE_NO_SCHEDULER` is set) or Run now; suggestions with evidence; the tracker; agent `temple-opportunities`. Freshness: each scan also re-checks the open opportunities (sent by short id) and returns `checks` (live, changed, closed; changed/closed need a URL the search returned, else treated as live) into `last_checked`, `freshness`, `freshness_note`, `freshness_evidence`; a closed suggestion is dismissed, a closed tracked/pursued one only flagged (`_apply_checks`). Suggestions nobody acted on and no scan confirmed as live go stale after `opportunity_expire_days` (30; 0 = never) and are dismissed, logged `opportunity_expired` (`expire_stale`, run each scheduler pass and when the tracker loads) |
| `organisations.py` | Organisation profiles: short approved facts with source pointers and review dates, the compiled brief, removal by source, account manager (typed now; `account_manager_oid` reserved for Entra ID), the Client switch and other names (`set_client`; unticking makes tagged material General). `_clean` strips web-search citation markup (`strip_citations`); `tidy_citations` removes markup already stored, at start-up |
| `demo_data.py` | Fictional demo data for the Organisations page and tracker, in a separate store (data\demo\substrate-demo.db, or schema `alice_demo` on PostgreSQL); rebuilt when the live schema changes |
| `purview_labels.py` | Microsoft Purview sensitivity labels on uploaded Office files and PDFs: read (never changed), recorded, and mapped on the Rules page to an Alice label or Block; unmapped protective-marking labels are blocked, others treated as Internal; never lowers a label |
| `assistants.py`, `assistant_page.py` | Assistants: focused chat bots (seeded: Alex, the HR policy assistant; `RENAMES` renamed the old default names once, logged as `assistant_renamed`, and never overrides a name you choose). The Assistants page shows tiles, search, type and status filters, Cards (grouped by type) or List view, and one editor panel at a time with their own rule packs, model, knowledge categories and guidance; staff page `/assistant/{id}`, managed on the Assistants page; agent `alice-assistants`. `load_demo_hr()` adds summaries of the demo UK HR handbook (`demo_content/hr_policy_summaries.json`) as HR drafts; the full handbook stays in `Policy library\` and is never stored in Alice. Answers in two steps (streamed to the staff page as NDJSON when it sends `Accept: application/x-ndjson`, so it can say it is checking the full document): the approved summaries first (the model replies `NOT_IN_SOURCES` if they do not answer); only then, if `allow_documents` is on, the pointed-to sections of the full documents are read on demand via `doc_library` and cited as [D1] |
| `proposals.py`, `proposal_docx.py`, `proposal_page.py`, `proposal_ui.py` | Proposal writer (assistant kind `proposal`, seeded `proposal-writer`, named **Parker**; its pen-nib mark is `proposal_page.parker_logo()`, also the tab icon): staff page `/assistant/{id}` takes a brief, client, Format and flow sections and a rate card; a background job runs agent `alice-proposal-writer` (context gathered in code: the client's approved profile, approved memories and active knowledge that are general or tagged to THIS client only, each piece through `check_outbound`), then agent `alice-proposal-qa`, named **Argus** (`AGENT_RENAMES` renamed it once, logged) (verdict, score, requirements, issues, plus `alice_checks` in code), one automatic revision if QA does not pass, then the Word document. The writer never sees cost rates and never writes prices: `price()` builds the sell table from its resource plan; cost and margin are shown on the page only. `proposal_docx` fills a .docx template from a document source with stdlib XML editing: cover kept, Heading 1 = section, text under a heading = guidance, `[keep]` = standard text, `{{title}} {{client}} {{date}} {{author}} {{reference}} {{total}}` in body/headers/footers, the template's own List Bullet/List Number/Table Grid styles, numbered lists restarted per list. `proposal_ui` holds the section and rate-card editors shared by both pages (sections carry optional `include` text the writer must work in). The page also takes a pasted structure (`inputs.structure`, or turned into sections in the browser). After a draft: `recheck()` sends your edited sections to QA and rebuilds the document; `qa_upload()` checks a revised Word/PDF version (split at its headings by `document_sections`, never kept); `qa_only()` checks a proposal you already have against a brief without writing. Each QA round records its `source`. The template is picked per proposal (`start(template=...)`, `outline_for`, `/assistant/{id}/outline`); the assistant's template is the default. The rate card is a price book: rows carry `days` (fixed quantity: overrides the writer's plan, added if missing, shown to the writer as FIXED), `use` (ticked for this proposal; only `used()` rows reach the writer and pricing) and `override` (sell rate set by hand, else sell = cost at `target_margin`, `sell_for`). `list` keeps the price book sell rate (from the spreadsheet or paste) so the page shows Price book, Sell rate and Change; pricing always uses `sell`. On the Parker page the rate card spans the full width below the form and Parker's panel; the Write proposal button is outside the form (`form="f"`). `rates_from_sheet` reads a pricing tool (.xlsx via openpyxl, or .csv) for `/assistant/{id}/rates/parse`; nothing is stored. The editor shows reference cost, sell and margin for ticked roles with days |
| `proposal_starter.py` | **Parker** (agent `parker`, `/assistant/{id}/parker`, `/assistant/{id}/parker/document`; Parker sees the roles on the page (including a price book loaded on the page) with ticks, days, COST and SELL rates and margins, and what the written proposal was priced at (Stefan's decision: costs are not sensitive for Parker; the writer, Argus and the document still never get them); roles may carry a `sell` rate only when you state it; a reply that is not JSON is shown as words, a cut-off one is asked for again once): the chat panel that stays in view beside the form on the Parker page. Each turn sends the message, the last 12 turns, the form (with cost and sell rates), and an added client brief (read once, rules checked, held in memory 30 minutes by token, never saved). Context from `proposals.gather` (same client separation as the writer); templates, documents and roles offered by name only; anything not on offer is dropped in code (`_validate`). Returns a reply, only the changed fields and open questions; the page outlines changes, tags the section "Updated by Parker" and offers Undo per turn. Each turn is logged as `parker_update` (what changed and what it asked, never the conversation) and listed on the Temple page (`/admin/api/temple/parker`). Model: the writer's `chat_provider` setting (Sonnet by default). The old `temple-proposal-starter` agent is in `agents.RETIRED` (kept for history, not listed). Form sections collapse (click a header; Expand all / Collapse all). Proposals in progress save themselves: the form is a `proposals` row with status `form` (`save_form`, `/assistant/{id}/work`, about a second after each change; secrets and markings refused; `inputs.form` holds the full rate card), listed with the written ones in the Proposals switcher at the top of the page (`discard_form` marks one `discarded`, never deleted); `start(work_id=…)` turns that row into the proposal; editing a written proposal does not autosave (Save as a new version starts a new form). Parker's conversation is kept with the proposal (`context.parker_chat`, last 40 messages, via `parker_turn` when the page sends `work_id`, `/parker/keep` for a turn that finished as the form was first saved, or `parker_chat` in the first `save_form`), so it follows you to another device; it is never written to the activity log. What each proposal's AI calls cost is kept in `context.ai_cost` (`writing` for the writer and Argus, via `agents.cost_box` around each background job; `parker` per turn) and shown in the Proposals list, on the result and on Home. Argus's fixes can be accepted or rejected one by one; `revise()` sends only the accepted ones to the writer (`Apply ONLY these fixes`), then Argus checks again and the document is rebuilt. After writing, a changed rate card is shown on the Commercials card against what was priced; Update the pricing (`reprice()`) reprices from the ticked roles (your days win, unticked roles come out), Argus checks the new price and the document is rebuilt; the words are left to Parker. Each decision can carry your note (how to apply an accepted fix, which the writer follows; why you rejected one, which Argus takes as context); rejections alone re-run Argus without rewriting (`_decided_job`). Notes are checked for secrets and markings before anything is kept. Your decisions are kept with the proposal (`context.fix_decisions`) and given to Argus on every later check (revise, re-check, upload); a rejected point Argus raises again in other words is dropped in code (`_same_point`) and counted as `rejected_not_raised`. Opening a proposal fills an empty form from its inputs (`loadIntoForm`; or the Load into the form button); Parker then also gets the draft as written (`form.draft`, the edit boxes when Edit the draft is open) and can rewrite named sections (`updates.draft`, only existing non-[keep] sections), which land in the edit boxes for you to Save changes and check again |
| `stage_ui.py` | The assistant stage: in the Command centre a click on any `/assistant/{id}` link grows the clicked tile into the assistant, full screen (Web Animations API: a clip-path from the tile's rectangle to the window, about 0.8 s; Alice scales back and blurs; a splash with the assistant's mark until its page loads; shorter and without blur when Windows animations are off), and shrinks back into the tile on the way out (an iframe of its page with `?embed=1`, which hides that page's top bar via `EMBED_HEAD`), with Back to Alice (also Esc and the browser's back) and Open in a new window |
| `references.py` | Reference documents for proposals: pick any document in the document sources (`listing`, with summary status and client tag); upload on the proposal page = `inspect` (read, rules checked, nothing saved; suggests title, save folder, category and tag: General when no client is named, else that client) then `save_and_summarise` (agent `alice-reference-summariser`: file saved via `doc_library.save` inside the Documents folder, summary in Knowledge pointing to it, tagged as chosen; approved automatically and logged when the writer's `auto_approve_references` is on, otherwise a draft). The page lists only the documents picked for this proposal until you choose Choose documents. `context()` gives the writer each reference's approved summary plus passages relevant to the brief via `doc_library.extracts` for both models' providers; documents whose summaries are tagged to another client are left out |
| `doc_library.py` | Document sources: full documents kept OUTSIDE Alice in the `Documents\` folder (`ALICE_DOCUMENT_LIBRARY` overrides). Each subfolder is a source and its `_source.json` says what it stands in for (`sharepoint`, `fabric`, `power_platform` or `folder`); in Azure each becomes a real connector (Graph, OneLake, Dataverse) behind the same calls (`sources`, `files`, `resolve`, `extracts`). Pointers never leave the folder; older pointers (`Policy library\…`) match by unique file name. Checks Purview label mappings and `check_outbound` on each extract; in-memory cache only, nothing stored. Documents page `/admin/documents` |
| `documents.py` | Word, Excel and PDF created in chat via the local `create_document` tool (not MCP, so outside apps don't get it): Word and PDF from simple markdown (stdlib; PDF written by hand with Helvetica), Excel with openpyxl; `check_file` runs first; kept in `generated_documents` for download at `/documents/{id}/download`; never knowledge |
| `clients.py` | Clients (the separation list), tagging, alias detection, separation enforcement. There is no Clients page: a client is an organisation with Client ticked (`organisations.set_client` writes the clients table), and tagging lives in Organisations → Tag memories and files; `/admin/clients` redirects |
| `home.py` | The Command centre home page (`/admin`, `/admin/api/home`): greeting, what is waiting, today's numbers and spend, the last 7 days, recent chats and proposals, assistants and agents needing attention, substrate counts. The desktop app opens here; Actions is at `/admin/actions`; the chat page (`/`) opens the empty chat or a new one unless a chat is named in the hash |
| `actions.py` | The Actions page: decisions to approve first (each explained by `autoapprove.explain_decision`: why it is a decision, what it is for, options, reason, revisit, where it came from, Temple's recommendation and any clash), then what automatic approval held back and why, what is still waiting for the checks (Approve these automatically = `autoapprove.backlog()`), replacements, suggestions and the rest; what went live automatically in the last 7 days is listed for information (not counted) with Undo |
| `apps.py` | The Apps area (`/admin/apps`, one menu entry): registry `APPS` (id, name, mark, page, agent, description, `waiting()`). An app's page keeps its own address (e.g. `/admin/mileage`), is left out of the menu, highlights Apps and shows an `Apps ›` breadcrumb (`render_admin`). `waiting()` feeds the Apps tiles and the Actions section `apps` (links only: approvals stay on the app's page with the full detail); a failing app is skipped. Optional `summary()` gives the tile its headline figures (`{stats, spark, note}`; failure-safe). **A new app = one `APPS` entry + its page in `admin_ui.PAGES`/`SECTIONS` + a `waiting()` function + tests** |
| `mileage.py` | Mileage Clerk parts 1-3 (deterministic, no model). Reads the vehicle tracker CSV export (`parse`; checked with `rules_engine.check_file` on upload), classifies each day with Stefan's places (`mileage_places`: home/personal/business, matched by street+postcode key `place_key` or within 300 m of a place's lat/lon), joins legs through unclassified stops into journeys (a stop of 30+ minutes at an unclassified place is a destination, flagged on long personal journeys), a journey with a business place at either end is business; one draft per business day (`mileage_drafts`, unique per import and day) holding the exact TMC entry (date, daily business miles, vehicle, start at home, business stops with purpose) and its sha256. Approvals are exact and never automatic: `approve(id, 'fill'|'save', hash)` (save needs fill first; changed entry = refused), `approved_for` for part 4. Changing a place rebuilds entries not yet save-approved and clears their approvals. Listed under Apps; `waiting()` = entries waiting for fill approval. `overview()` (top of the page and the Apps tile via `tile()`): business/personal miles per month for 12 months (each day from its newest export), this month (or the last tracked month early in a month), tax year from 6 April against HMRC's 10,000 mile mark, entries waiting/approved/in TMC/not claimed; optional claim rate `set_rate` (setting `mileage_rate_ppm`, display only). Chart: `mileageChart` in admin_ui (stacked SVG bars, class `mi-bar`, never `.bar` which is a global style). **Addresses live only in the database, entered by Stefan: never in code, tests (fictional fixtures only) or git.** Part 4 (filling TMC) runs later in Stefan's own signed-in browser, never with stored TMC credentials |
| `autoapprove.py` | Automatic approval and its guard rails (see rule 4): `after_review` (memories, once Temple's review is in; called from `temple.automatic_review` and `review_batch`), `knowledge_draft`, `org_fact`, `suggestions_for_chat` / `accept_suggestion` (the Accept path for Temple's chat suggestions, used by the route too), a wrapper on `store.propose_decision` that holds every decision and starts its review once its details are saved, `from_outside` (contextvar), `hold`, `recent`, `undo`, `backlog`; table `auto_approvals` (item_type memory/knowledge/orgfact/chat, state approved/held, reason). Temple's prompt asks for `Conflict: yes/no`, and for decisions `Why it is a decision:` and `What it is for:` |
| `activity_log.py` | Activity log labels, types, filters, CSV; `overview()` feeds the Activity page's picture (`/admin/api/activity-overview`): tiles, activity over time by area (blocks counted separately), the approval gate, blocks by rule, agent runs, AI calls by model, a weekday-by-hour heatmap in the browser's time zone, most frequent actions |
| `router.py` | Auto model routing, provider failure memory |
| `usage_meter.py` | Token/cost ledger, timings, savings |
| `speed.py` | The Speed page (`/admin/speed`, Records and settings): the `time_requests` middleware in app.py times every request (not static files or `/healthz`) and adds a `Server-Timing` header; `dbcompat.ON_QUERY`/`ON_CONNECT` and `store.ON_SQLITE_QUERY` count queries, database time and pool checkouts per request (context variable `speed.CURRENT`); each Command centre page reports its own load time from the browser (`/admin/api/speed/page`: until the page and its first API data are on screen). Kept in memory, written once a minute by a background thread to `speed_routes` (per day and route) and `speed_slow` (last 500 over 1 s); 30 days; routes and timings only, never query strings or content. Pages and JSON are gzip-compressed (`GZipMiddleware`, NDJSON streams excluded so answers still stream) |
| `images.py`, `voice.py` | Generated images; ElevenLabs speech |
| `desktop.py`, `connect_claude.py` | Tray launcher; Claude Desktop connector setup |

Models: GPT-6 Luna (`gpt-6-luna`, Responses API), GPT-6 Astra (`gpt-6-astra`, selection `openai_astra`; premium,
reasoning effort low..max with no `none`, no image generation set up; manual only), Claude Haiku 4.5, Sonnet 5.5,
Opus 5.5 (manual only; Auto never selects it), Grok 4.7 (xAI). Temple's reviewer is Luna or Haiku.

## Two databases: write SQL that works on both

SQLite (`data\substrate.db`) is the default; when `ALICE_DATABASE_URL` is set (Azure), `store.db()` returns a
PostgreSQL connection from `dbcompat.py` that accepts Alice's SQLite-style SQL and behaves like sqlite3 (rows by
name, sqlite3 exception types, `with` commits/rolls back, savepoint per statement, BEGIN IMMEDIATE = advisory lock).
It translates `?`, `instr`, `LIKE` (case-insensitive), `COLLATE NOCASE` (CITEXT), `INSERT OR IGNORE`,
`PRAGMA table_info`, REAL/BLOB/AUTOINCREMENT. Avoid what it cannot translate:
- `INSERT OR REPLACE` (use `INSERT … ON CONFLICT(key) DO UPDATE SET …`, valid in both).
- `rowid`, except on `chat_turns` (which keeps an explicit `rowid` column on PostgreSQL).
- Selecting columns that are neither grouped nor aggregated; ORDER BY expressions not in a GROUP BY.
- Summing comparisons (`sum(x='y')`): use `sum(CASE WHEN x='y' THEN 1 ELSE 0 END)`.
- Opening sqlite3 directly: always go through `store.db()` / `store.connect()`.
Run the suites against a test PostgreSQL server too (`ALICE_TEST_DATABASE_URL`, see tests\README.md).
`migrate_to_postgres.py` copies data\substrate.db into PostgreSQL and verifies every table (dry run by default).

## Demo data (Organisations)

`store.DATASET` (a context variable) picks the live or demo store. Only `/admin/api/organisations*` and
`/admin/api/opportunities*` switch, and only when the request carries `X-Alice-Dataset: demo` (the page sends it when
its Demo data box is ticked, or in global demo mode). Research and opportunity scans are refused in demo: they would
call real AI services. Never read the demo store anywhere else, and never let a scheduler or agent run against it.
`CREATE`/`ALTER` statements skip the LIKE→ILIKE translation so `CREATE TABLE … (LIKE …)` works.

## Accountability (who, why, owners)

- `store.audit()` writes `actor` (who) and `note` (why) on every activity row. `store.ACTOR` is set per request by the
  `who_is_acting` middleware: the signed-in person from Container Apps sign-in (`X-MS-CLIENT-PRINCIPAL-NAME`, trusted only
  with `ALICE_TRUST_EASYAUTH=1`), otherwise `ALICE_OWNER_NAME` (default "Owner"). Give a reason with
  `with store.acting(note=...)` around a decision; review routes accept an optional `note`.
- `ALICE_AUDIT_STDOUT=1` also writes each activity row as one JSON line to the `alice.audit` logger (stdout in Azure, so
  Container Apps sends it to Log Analytics).
- Owners (`record_meta.owner`, `knowledge_meta.owner`) are people's names for tracking (shown on overdue reviews in
  Actions). Validate with `store.clean_person()`. Never return owners or account managers in MCP tool output.

## Assistants (focused bots)

- `assistants.ask()` is the only path: active check and spending cap; `check_outbound` (secrets, markings) on every turn sent;
  first-person health or special category details sent to a person (`rule_packs.self_disclosure`); the assistant's own packs via
  `rule_packs.live_check(..., packs=…)` on every user turn (independent of the globally applied packs); knowledge only from its
  categories, never client-tagged or Local only, and only labels its model may receive. The model answers only from those sources.
- No transcript is stored. Activity rows record the outcome and the sources used, never the question.
- Validate input before calling `ask` (it is `@agents.tracked`); the staff page refuses cross-origin posts and never carries the admin token.
- Assistant models are `assistants.PROVIDERS` keys; rules use `assistants.family()` (claude/openai). Premium models (`claude_opus`,
  `openai_astra`, Astra always with reasoning on) are for proposal writers only. Each proposal can override the writer and QA model
  (stored in `inputs`); context is filtered for BOTH models' provider rules, since QA sees the draft.
- Proposal writers (`kind='proposal'`, settings JSON: template, sections, rate_card, qa_provider, min_margin, target_margin, auto_approve_references, pricing_note, author) never answer
  questions. Their job runs in a thread: call `write()` and `review()` separately (each is its own tracked run; nested tracked calls would
  merge into one run). Cost rates must never appear in the writer's or Argus's prompt or in the document (Parker, the form assistant, may see them); client separation for proposals is stricter than chat:
  only general material or material tagged to the proposal's own client.

## Lessons already learned (don't relearn them)

- **No module imports inside a write transaction.** Most modules create tables when first imported. Importing
  one (directly or via a helper like `temple.reviewer()`) inside `BEGIN IMMEDIATE` makes SQLite wait on
  itself for 15 seconds, then fail quietly. Resolve imports and helper calls before opening the transaction.
  The same goes for audit/logging calls while a read cursor is still open: fetch rows first, then write.
- **Changing a shared function's signature breaks callers silently in JS.** Example: the Memories page's
  `chip(text, active, count, onclick)` differs from other pages' `chip(text, active, onclick)`; passing the
  wrong order printed code into button labels.
- **CSS `display` overrides the `hidden` attribute.** Any element toggled with `hidden` that has a display
  rule needs `[hidden]{display:none}` (or `!important`).
- **Buttons shown during a streaming answer** go through `guard()`, which ignores clicks while busy. Use the
  `whenIdle()` pattern so clicks wait for the answer rather than vanishing.
- **Controls re-enabled by `controls()`**: any new control that is disabled while busy must be added there,
  or it stays greyed out.
- **Every file Stefan copies must be the whole current set.** A newer `app.py` imports newer modules
  (`actions`, `activity_log`, `temple_ask`, …). Deliver all changed files together, and remind him to run
  the import check.
- **Windows specifics**: guard Windows-only code with `os.name == 'nt'`; consoles may be cp1252, so
  reconfigure stdout to UTF-8 when printing non-ASCII; use `pathlib`/`os.path`, never hard-coded `/tmp`.
- **Provider errors**: never show a generic "request failed". Use `provider_error()` in `app.py`, which gives
  the HTTP status and the provider's own message.
- **Diagrams in chat**: ```mermaid and ```svg blocks are drawn by `diagram()` in the chat page and always shown as an
  `<img>` (a blob URL), never inserted as live SVG, so model-written drawings cannot run script or fetch anything. Mermaid is
  bundled in `Static/vendor/` (pinned version, served by `/static/vendor/{name}` from an allow-list); never load
  libraries from a CDN. In inline JS, never end a statement with a `//` comment on a line that continues: it swallows the rest.
- **The chat page declares `let history=[]`**, which shadows `window.history`: use `window.history.replaceState` there.
- **Quotes from Temple** are verified against Stefan's own words with `store.quote_found()`, which forgives
  typography but not rewording. Never loosen it to accept paraphrase.

## Conventions

- Python, stdlib first; dependencies are already in `.venv`. Do not add packages without asking.
- User-facing text: plain UK English, specific, no jargon. Errors say what happened and what to do.
- Admin API: non-GET routes need the `X-Admin-Token` header (the pages inject it). GET routes carry no token: on the PC the
  app only listens on 127.0.0.1, and in Azure Entra sign-in sits in front of everything except `/healthz`. Never add a
  route that bypasses that sign-in.
- Keep changes small and reviewable. Commit after the tests pass (see git below).

## Git

`.gitignore` excludes `.env`, `data\`, `.venv\`, caches and downloads. Commit after each passing change:
```
git add -A
git status          (check .env and data\ are NOT listed)
git commit -m "Short description of the change"
```
To undo uncommitted changes to a file: `git restore <file>`. To see what changed: `git diff`.

## Roadmap (not yet built)

- pgvector search in PostgreSQL; ChatGPT as a second connector client (it can use the same OAuth proxy).
- Build and release without the PC: Claude works on the GitHub repo directly; Promote and Rollback as manual GitHub
  workflows (promote also switches off all but the previous revision).
- TypeScript front end against the existing API; split `substrate_store.py` into modules.
- OpenAI image pricing once the usage export arrives (`IMAGE_PRICE_OPENAI`).
- Opportunity and news digests by email to each organisation's account manager (Stefan, 3 Oct 2026). Build on
  `opportunities.tracker()` (new suggestions, changed/closed checks, news since the last digest) per watched organisation;
  send through Microsoft Graph once Alice runs in Azure; resolve the recipient from `account_manager_oid` (reserved for
  Entra ID), not the typed name; an account manager only ever receives their own organisations (client separation);
  run the content through `check_outbound`; never include cost rates or Local only facts; log each send.
- Mileage Clerk part 4: fill the TMC mileage form in Stefan's own signed-in browser (Claude in Chrome / Cowork browser)
  from an entry approved for `fill` (`mileage.approved_for`), stop before Save, show him the filled form, save only after a
  `save` approval of the same hash, then verify and record it. Needs a connector tool for approved entries and a tracked agent.
