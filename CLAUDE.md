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
4. **The approval gates are the product.** Models and Temple may only *propose*. Nothing becomes an approved
   memory, decision or active knowledge item without Stefan's explicit action. Never add an automatic
   approval path, even "just for testing" in production code.
5. **Temple is advisory.** It reviews, suggests, categorises and tags. It never approves, never overrides a
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
| `ui_theme.py` | Shared look for chat and Command centre: colours, type, buttons, inputs, top bar (`SHARED_CSS`) |
| `dbcompat.py` | PostgreSQL behind the SQLite-style calls (used when `ALICE_DATABASE_URL` is set) |
| `migrate_to_postgres.py` | One-off copy of SQLite into PostgreSQL with per-table verification |
| `substrate_store.py` | Database, chats, memories, categories, archive, decisions, quote matching |
| `rules_engine.py` | Rule sets, detectors, spending caps, retention, guidance compilation |
| `mcp_server.py` | MCP tools for models (read tools, including get_organisation, list_organisations and search_opportunities; propose_record/decision/knowledge, save/append_conversation); `--external` runs the signed-in endpoint. Alice's web chat uses the tools in `app.ALLOWED_TOOLS`; organisation and opportunity results pass client separation (`clients.filter_tool_output`) and secret/marking checks; account managers are never returned |
| `external_auth.py` | Entra ID sign-in for the external endpoint (Copilot): settings `ALICE_EXT_*`, token checks, caller label and provider |
| `temple.py` | Temple memory reviews, queue, settings, `reviewer()` (effective provider) |
| `temple_chat.py` | Temple's suggestions after chat answers |
| `temple_categorise.py` | Temple category assignment |
| `temple_ask.py` | Ask Temple: read-only tools over activity, actions, usage |
| `temple_supersede.py` | Temple finds older knowledge a newer item replaces (wording first, then a quoted model check); suggestions only |
| `conversations.py` | Saved conversations, Claude export import (incl. manifest download), whole-chat reviews |
| `knowledge.py` | Knowledge library: kinds, drafts, labels, meeting extracts, Word in/out, replacements (`supersede`, `history`), default review period (`review_days`, 30 by default; set when an item becomes active, never overwrites an existing date) |
| `agents.py` | Agents register: Temple automations (`@agents.tracked`) and connected apps (`app_call` in every MCP tool); runs, data touched, cost, pause/stop, versions. Data touched is grouped by source (`SOURCE_GROUPS`: Internet with URLs, Document library with file paths, then Alice's own data with links, status and label); record web reads as `note('read','web',url,...)` and library reads as `note('read','document',relative_path,...)`. `DATA_SOURCES` includes the outside sources (web, documents, input) drawn in the left column of the system map |
| `rule_packs.py` | Demo rule packs (HR team, council social care, security operations, personal data): switchable safeguards and a sandboxed test (never calls a model); a pack can be applied to live rules (`live_check` on chat before saving, blocks/escalations on Temple's requests via `check_outbound`, guidance via `effective_guidance`) with per-service inside/outside-tenant classification |
| `org_research.py` | Temple researches an organisation on the public web (provider web search) and proposes facts, each citing a page the search returned; agent `temple-org-research` |
| `opportunities.py` | Client opportunity scans (profile brief + news via web search), on each organisation's schedule (background thread, `start_scheduler`; off when `ALICE_NO_SCHEDULER` is set) or Run now; suggestions with evidence; the tracker; agent `temple-opportunities` |
| `organisations.py` | Organisation profiles: short approved facts with source pointers and review dates, the compiled brief, removal by source, account manager (typed now; `account_manager_oid` reserved for Entra ID), the Client switch and other names (`set_client`; unticking makes tagged material General) |
| `demo_data.py` | Fictional demo data for the Organisations page and tracker, in a separate store (data\demo\substrate-demo.db, or schema `alice_demo` on PostgreSQL); rebuilt when the live schema changes |
| `purview_labels.py` | Microsoft Purview sensitivity labels on uploaded Office files and PDFs: read (never changed), recorded, and mapped on the Rules page to an Alice label or Block; unmapped protective-marking labels are blocked, others treated as Internal; never lowers a label |
| `assistants.py`, `assistant_page.py` | Assistants: focused chat bots (seeded: HR policy assistant) with their own rule packs, model, knowledge categories and guidance; staff page `/assistant/{id}`, managed on the Assistants page; agent `alice-assistants`. `load_demo_hr()` adds summaries of the demo UK HR handbook (`demo_content/hr_policy_summaries.json`) as HR drafts; the full handbook stays in `Policy library\` and is never stored in Alice. Answers in two steps: the approved summaries first (the model replies `NOT_IN_SOURCES` if they do not answer); only then, if `allow_documents` is on, the pointed-to sections of the full documents are read on demand via `doc_library` and cited as [D1] |
| `doc_library.py` | The document library: full source documents kept OUTSIDE Alice (`Policy library\` by default; `ALICE_DOCUMENT_LIBRARY` overrides; SharePoint or Blob in Azure). Reads a summary's pointer (`full document: …`, `section N`), never outside the library, only .docx/.pdf/.txt/.md; checks the file's Purview label mapping and `check_outbound` on each extract; in-memory cache only, nothing stored |
| `documents.py` | Word, Excel and PDF created in chat via the local `create_document` tool (not MCP, so outside apps don't get it): Word and PDF from simple markdown (stdlib; PDF written by hand with Helvetica), Excel with openpyxl; `check_file` runs first; kept in `generated_documents` for download at `/documents/{id}/download`; never knowledge |
| `clients.py` | Clients (the separation list), tagging, alias detection, separation enforcement. There is no Clients page: a client is an organisation with Client ticked (`organisations.set_client` writes the clients table), and tagging lives in Organisations → Tag memories and files; `/admin/clients` redirects |
| `actions.py` | Everything awaiting a decision (Actions page) |
| `activity_log.py` | Activity log labels, types, filters, CSV |
| `router.py` | Auto model routing, provider failure memory |
| `usage_meter.py` | Token/cost ledger, timings, savings |
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
- **Quotes from Temple** are verified against Stefan's own words with `store.quote_found()`, which forgives
  typography but not rewording. Never loosen it to accept paraphrase.

## Conventions

- Python, stdlib first; dependencies are already in `.venv`. Do not add packages without asking.
- User-facing text: plain UK English, specific, no jargon. Errors say what happened and what to do.
- Admin API: non-GET routes need the `X-Admin-Token` header (the pages inject it). GET routes are
  unauthenticated because the app only listens on 127.0.0.1; keep it that way until the Azure step adds auth.
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

- Azure hosting: Container Apps, Entra ID sign-in, PostgreSQL + pgvector, remote MCP endpoint with OAuth
  for Claude web/mobile and ChatGPT. Test Entra OAuth with a Claude custom connector early (a known issue
  has been reported).
- TypeScript front end against the existing API; split `substrate_store.py` into modules.
- OpenAI image pricing once the usage export arrives (`IMAGE_PRICE_OPENAI`).
