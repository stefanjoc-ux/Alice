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
7. **Protectively marked material** (OFFICIAL-SENSITIVE, SECRET, TOP SECRET) must never reach an external
   model. Stefan holds SC clearance and works with Scottish public-sector clients; treat this as absolute.
8. **Run the tests before declaring anything done.** Never mark work complete with failing tests.

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
| `substrate_store.py` | Database, chats, memories, categories, archive, decisions, quote matching |
| `rules_engine.py` | Rule sets, detectors, spending caps, retention, guidance compilation |
| `mcp_server.py` | MCP tools for models (read tools + propose_record/decision/knowledge, save/append_conversation) |
| `temple.py` | Temple memory reviews, queue, settings, `reviewer()` (effective provider) |
| `temple_chat.py` | Temple's suggestions after chat answers |
| `temple_categorise.py` | Temple category assignment |
| `temple_ask.py` | Ask Temple: read-only tools over activity, actions, usage |
| `conversations.py` | Saved conversations, Claude export import (incl. manifest download), whole-chat reviews |
| `knowledge.py` | Knowledge library: kinds, drafts, labels, meeting extracts, Word in/out |
| `clients.py` | Clients, tagging, alias detection, separation enforcement |
| `actions.py` | Everything awaiting a decision (Actions page) |
| `activity_log.py` | Activity log labels, types, filters, CSV |
| `router.py` | Auto model routing, provider failure memory |
| `usage_meter.py` | Token/cost ledger, timings, savings |
| `images.py`, `voice.py` | Generated images; ElevenLabs speech |
| `desktop.py`, `connect_claude.py` | Tray launcher; Claude Desktop connector setup |

Models: GPT-6 Luna (`gpt-6-luna`, Responses API), Claude Haiku 4.5, Sonnet 5.5, Opus 5.5 (manual only; Auto
never selects it), Grok 4.7 (xAI). Temple's reviewer is Luna or Haiku.

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
