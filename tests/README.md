# Alice tests

Run everything (from `D:\AISubstrate`):

    .venv\Scripts\python.exe tests\run_tests.py

Run some suites by name:

    .venv\Scripts\python.exe tests\run_tests.py rules import

Run after every update, before relaunching. Exit code 0 means every check passed.

## Safe by design
- Every suite runs in its own throwaway data folder, deleted afterwards. Your `data\` is never opened.
- Every API key is replaced with a dummy, even if `.env` has real ones, and the OpenAI and Anthropic
  libraries are pointed at a dead local address, so an accidental real model call fails instantly and costs nothing.
- `test_zz_safety.py` checks these guarantees on every run.

## What is covered
| Suite | Covers |
|---|---|
| rules | Rule sets, governance, chat/upload blocks, MCP withholding, allow-lists, review-by, spending caps |
| detectors | Secrets, protective markings and personal identifiers, including ordinary text that must not be flagged |
| clients | Client separation, aliases, tagging precedence, strict mode, Claude Desktop scope |
| knowledge | Drafts, labels, .vtt/.docx, meeting extracts, duplicates, categorising |
| decisions | Decision proposals, filters, Temple suggestions, meeting decisions |
| conversations | Saved conversations, Temple whole-chat review, quote checks |
| import | Claude export import, security skips, re-import, retention guard |
| archive | Archiving, capture detection, restore, retention safeguards |
| actions | The Actions page counts and inline decisions |
| activity | Activity log labels, filters, search and CSV |
| temple_chat, temple_chat_errors | Temple's in-chat suggestions and failure handling |
| ask_temple | Ask Temple's tools and question loop |
| routing, provider_health | Auto routing rules, step-down, images, skipping a failing provider |
| providers | Plain-English provider errors and Check connections |
| mcp_stdio | The connector exactly as Claude Desktop uses it |
| quotes, desktop | Quote matching; hotkey and window-size parsing |
| external_mcp | The signed-in external endpoint: settings, every Entra token check, 401s over HTTP, external rules for Copilot |
| organisations | Organisation facts: sources, review dates, data minimisation, approval, the brief (labels, providers, external), removal by source |
| diagrams | Mermaid and SVG code blocks drawn as pictures (as images, never live SVG), local Mermaid library, static folder case |
| astra | GPT-6 Astra in chat: model and reasoning setting, no images, pricing, never chosen by Auto |
| opportunities | Opportunity scans: evidence checks, profile labels respected, contact details stripped, no duplicates, tracker statuses, schedule (due, first slot, off, paused agent), offerings, Actions |
| org_demo | Demo data kept apart from live (organisations, facts, opportunities), research and scans refused in demo, reset, rebuild on schema change, account manager validation, page layout |
| org_chat_tools | Chat and connector access to organisations and opportunities: filters, open/all statuses, evidence, notes only for Alice's web chat, account managers never returned, secrets and markings withheld, external and client separation |
| org_clients | Clients merged into Organisations: Client switch, other names, tagged counts, unticking makes material General, no duplicates, demo isolation, /admin/clients redirect |
| accountability | Owners on memories and knowledge (filters, validation, never sent to models), who approved and why (activity actor/note, Entra header only when trusted, CSV), JSON audit lines, Purview labels (Office and PDF, mapping, block, protective-marking names, never lowering a label) |
| assistants | HR policy assistant: own packs enforced before any model call (self-disclosure, special category, casework, automated decisions, identifiers removed, secrets), earlier turns re-checked, scoped knowledge only (no client or Local only), no transcript in the log, paused, admin validation, cross-origin |
| demo_hr | Default knowledge review period (30 days, changeable, 0 = none, set on activation/approval/upload), demo HR summaries as drafts with section pointers, full handbook not stored, assistant uses them only once approved |
| documents | Word/Excel/PDF built and read back, sheets/numbers/formulas, pagination, validation, secrets and markings refused, download route, not knowledge, chat tool call and download chip |
| doc_fallback | Summaries first, full document only when they don't answer: pointer parsing, library confinement (no path traversal, document types only), numbered sections, one call when summaries answer, NOT_IN_SOURCES → pointed-to section read and cited, nothing stored, logged, document-only questions reach it, not-found reply hides the marker, Purview-blocked documents skipped, switch off per assistant |
| data_touched | Data touched grouped by source, with Sent to (models called in the run; connected apps receive what they read; nothing when no model was called): web URLs as links, library documents with their file path, knowledge/memories/organisations with links, status and label, reads and writes merged per item, deleted items flagged, period choice, demo masking; outside sources on the system map |
| doc_sources | Documents folder and its sources: adding a source (folder + `_source.json`, names checked, nothing outside the folder), source types, listing documents (subfolders, no lock files or other types) with summaries pointing to them and agent reads, legacy pointer matching by unique name, source shown on extracts and Data touched, Documents page in the menu |
| proposals | Proposal writer: template outline ([keep], placeholders), settings validation, template + Format and flow merge, background job (writer, QA, one revision, QA), client's own memories in and other clients' out, cost never sent or printed, pricing and margin warnings, Word document from the template (header/footer, order, [keep], pricing table, styles untouched), agents and Data touched, Alice checks, refusals (short brief, secrets, markings, cross-origin, paused agent), failures reported, no-template layout, numbering restart, pasted structure and per-section text to include, your edits re-checked and the document rebuilt, a revised version uploaded for QA, QA-only for a proposal you already have |
| references | Reference documents: inspect suggestions (General vs client, several clients, folder, title), refusals (secrets, markings, no text, type, cross-origin, wrong assistant), save inside the source only, summary as a draft pointing to the document, tags, token used once, tracked agent, listing, the writer gets relevant passages and (once approved) the summary, other clients' references left out |
| activity_picture | Activity page picture: buckets by period (hour/day), counts only the period, approval gate, blocks by rule and kept out of the stack, areas add up, agent runs and failures, models by name, heatmap totals and time zone shift, empty periods, page wiring |
| home | Command centre home: opens on Home, menu order, old Overview redirects, waiting/today/week/spend/substrate data, assistants, recent chats only with turns, the chat page opens a new or empty chat, desktop opens on Home |
| citations | Web search citation markup removed from organisation facts, opportunities and news on the way in, and tidied where already stored (logged, idempotent) |
| org_research | Web research for organisations: facts proposed not approved, invented sources and personal data dropped, unsafe URLs refused, agent runs, both providers' search results |
| rule_packs_live | Packs applied to live rules: chat refused or identifiers removed before saving, Temple escalations, guidance, service classification, stacking, removal |
| rule_packs | HR and council social care packs: CHI and identifier detection, outcomes per sample and service, switches, locked audit rule, sandbox |
| dbcompat | PostgreSQL layer: SQL translation always; with a test server, rows, errors, rollback, read-only sessions, the write lock |
| agents | Agent register, runs and data touched, cost attribution, automatic pause (failures, budget), versions, app permissions on every tool call |
| supersede | Retiring replaced knowledge, the proposer's `supersedes`, Temple's replacement suggestions, what models see, memory replacements |

Not covered (needs a real Windows desktop or a person): the tray app, the hotkey and window resizing
themselves, voice, and page layouts. Check those by hand after changing them.

## Adding a test
Create `tests\test_<name>.py`, start it with `import _util` and `from _util import t` (before importing any
Alice module), then record checks with `t('what should be true', condition)`.

## Running against PostgreSQL
Alice uses SQLite unless `ALICE_DATABASE_URL` is set (Azure). To prove a change works on both, run the
same suites against a **test** PostgreSQL server; each suite gets its own throwaway schema, dropped afterwards:

    set ALICE_TEST_DATABASE_URL=postgresql://user:pass@host/testdb
    .venv\Scripts\python.exe tests\run_tests.py

`ALICE_DATABASE_URL` itself is always ignored by the tests, so the real database is never touched.
Needs the driver: `.venv\Scripts\python.exe -m pip install "psycopg[binary]" psycopg-pool`.
