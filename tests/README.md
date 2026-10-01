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
| supersede | Retiring replaced knowledge, the proposer's `supersedes`, Temple's replacement suggestions, what models see, memory replacements |

Not covered (needs a real Windows desktop or a person): the tray app, the hotkey and window resizing
themselves, voice, and page layouts. Check those by hand after changing them.

## Adding a test
Create `tests\test_<name>.py`, start it with `import _util` and `from _util import t` (before importing any
Alice module), then record checks with `t('what should be true', condition)`.
