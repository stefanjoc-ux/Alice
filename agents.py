"""Agents: everything that acts on Alice without you typing it, registered, limited and logged.

Two kinds:
- internal: Alice's own automations (Temple's reviews, categorising, tagging, replacement checks...). Each run is
  recorded with what started it, what it touched, what it cost and how it ended.
- app: connected apps (Claude Desktop, Claude Code, Microsoft Copilot) acting through the MCP tools. Their tool calls
  are recorded per day; their permissions (tools, read-only, categories, labels, calls per day) are enforced on every call.

Every agent can be paused or stopped from the Agents page; an agent pauses itself after repeated failures or when it
reaches its monthly budget. Changes to an agent's settings are versioned. Nothing here can approve anything: agents
still only propose, and the existing rules (separation, labels, markings, spending caps) apply on top.
Identity today is the caller label (stdio) or the Entra client app (external endpoint); per-agent Entra identities
come with the Azure step.
"""
import contextvars
import functools
import deployment
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
import substrate_store as store

FAIL_LIMIT = 3                  # consecutive failed runs before an agent pauses itself
SKIP = {'off', 'busy', 'no_categories', 'no_clients', 'running', 'not_reviewed'}
TRANSIENT = {'APIConnectionError', 'APITimeoutError', 'RateLimitError', 'InternalServerError', 'ServiceUnavailableError',
             'ConnectError', 'ConnectTimeout', 'ReadTimeout', 'TimeoutError', 'OperationalError'}
TOOLS = ['list_files', 'read_file', 'search_files', 'search_records', 'get_organisation', 'list_organisations',
         'search_opportunities', 'propose_record',
         'propose_decision', 'propose_knowledge', 'propose_org_fact', 'save_conversation', 'append_conversation',
         'list_proposals', 'get_proposal', 'propose_proposal_changes', 'list_spaces']
WRITE_TOOLS = {'propose_record', 'propose_decision', 'propose_knowledge', 'propose_org_fact', 'save_conversation', 'append_conversation',
               'propose_proposal_changes'}
LABELS = ['general', 'internal', 'client']

# id, name, kind, purpose, trigger, usage workloads, reads, writes, reads outside content
# Agents replaced by another: kept (with their runs) for history, not listed. temple-proposal-starter became Parker.
RETIRED = {'temple-proposal-starter'}
AGENT_RENAMES = [('alice-proposal-qa', 'Proposal QA', 'Argus: proposal QA')]
BUILTIN = [
    ('temple-review', 'Temple: memory reviews', 'internal',
     'Reviews each proposed memory against approved ones for duplicates, contradictions, weak sources and replacements. Advisory only.',
     'When a memory is proposed (if automatic review is on), or when you ask', ['Temple record review'],
     'Proposed and approved memories', 'Review reports (advisory)', False),
    ('temple-chat', 'Temple: chat suggestions', 'internal',
     'After an answer in Alice chat, suggests memories, decisions, knowledge notes and guidance from your own words.',
     'After each chat answer (if switched on), or Analyse latest', ['Temple conversation'],
     'Recent exchanges in the chat; a sample of approved memories', 'Suggestions awaiting you', False),
    ('temple-chat-review', 'Temple: whole-chat reviews', 'internal',
     'Reviews saved and archived conversations for things worth keeping; suggestions must quote you.',
     'When a conversation is saved from a Claude app, or when you ask', ['Temple chat review'],
     'Saved conversations and transcripts', 'Suggestions awaiting you', True),
    ('temple-categorise', 'Temple: categorising', 'internal',
     'Assigns or suggests categories for uncategorised memories and knowledge.',
     'In the background after new items, or Categorise with Temple', ['Temple categorise'],
     'Titles and the start of uncategorised items', 'Categories (by your Temple mode) or suggestions', False),
    ('temple-tagging', 'Temple: client tagging', 'internal',
     'Matches client names and aliases (free), then asks Temple about the rest; confident matches applied, others suggested.',
     'In the background after new items, or Tag untagged with Temple', ['Temple client tagging'],
     'Untagged memories and files', 'Client tags or suggestions', False),
    ('temple-memory-tags', 'Temple: memory tags', 'internal',
     'Tags memories with the tags you created (Work, Personal or both); confident matches applied, the rest suggested. Never re-adds a tag you removed.',
     'In the background after a new memory or a tag change, or Tag with Temple', ['Temple memory tags'],
     'Titles, the start and the category of memories not yet looked at', 'Tags (by your Temple mode) or suggestions', False),
    ('temple-model-eval', 'Temple: model evaluation', 'internal',
     'Scores the local and cloud models for Temple\'s screening on fixed, fictional examples (sharing checks and categories), so you can compare them before choosing.',
     'When you ask (Agents > Temple\'s model > Run the evaluation)', ['Temple model evaluation'],
     'Fixed fictional examples only (never your data)', 'Scores for each model, kept on the Agents page', False),
    ('temple-share-gate', 'Temple: sharing check', 'internal',
     'Before an item goes into a shared space, reads it for personal or special category details and anything private; a hit waits for its author.',
     'When someone shares or moves an item into a shared space', ['Temple sharing check'],
     'The one item being shared', 'Clear, or held for its author (with reasons)', False),
    ('temple-space-sweep', 'Temple: work items in personal spaces', 'internal',
     'Reads the titles and starts of the items in a person\'s personal space and says which are about the work, so they can be moved to their team space. Nothing moves until the person confirms.',
     'When a person asks (Actions > Work items in personal spaces > Ask Temple to look)', ['Temple personal-space sweep'],
     'Titles and starts of the items in that person\'s personal space', 'A list of work items to confirm (moved only through the sharing check)', False),
    ('temple-router', 'Temple: router', 'internal',
     'Decides where a newly captured memory, decision or knowledge item belongs: the team space, the Organisation space, its author\'s personal space or the team\'s restricted space; unsure, it waits for its author.',
     'After Temple has reviewed a new item heading for a team space', ['Temple routing'],
     'The one item being routed', 'Where it goes, with the reason kept on the item', False),
    ('temple-replacements', 'Temple: replacement checks', 'internal',
     'Looks for older knowledge a newer item replaces; suggests retiring it, quoting the newer item.',
     'When knowledge becomes active, or Find replaced items', ['Temple replacement check'],
     'Active knowledge items of the same client', 'Replacement suggestions', False),
    ('demo-generator', 'Client demo: scenario writer', 'internal',
     'On the demo Alice only: designs a fictional team and writes illustrative memories, decisions, meetings and conversations around an organisation\'s public information.',
     'When you press Generate on the Client demo page', ['Demo scenario'],
     'Public facts found by Temple\'s research (with sources)', 'A scenario you check, then load into the demo Alice', False),
    ('health-extract', 'Health Insights: report reader', 'internal',
     'Reads a blood test report you upload (identifiers already removed) when Alice\'s own reader cannot, and lists the results for you to confirm.',
     'When you upload a report and tick Let a model read it', ['Health Insights extraction'],
     'One report, identifiers removed', 'Results waiting for your confirmation', False),
    ('temple-taxonomy', 'Temple: category and tag housekeeping', 'internal',
     'Creates, fills and tidies categories and tags (merge, rename, retire, split, describe). Its own changes apply with Undo; '
     'anything you created, or any category a rule uses, waits for you.',
     'Weekly, after 20 new memories, or Review now', ['Temple taxonomy review'],
     'Category and tag lists; titles and the start of up to 150 memories', 'Categories, tags and their assignments (with Undo), or proposals', False),
    ('temple-discuss', 'Temple: decision discussions', 'internal',
     'Talks a proposed decision through with you before you decide: explains clashes, suggests a note. Advisory; changes nothing.',
     'When you ask (Discuss with Temple on Actions)', ['Temple decision discussion'],
     'The decision, its review and the items that review compared', 'Nothing (the discussion is kept with the decision)', False),
    ('temple-ask', 'Ask Temple', 'internal', 'Answers your questions about activity, actions and usage with read-only tools.',
     'When you ask', ['Ask Temple'], 'Activity log, outstanding actions, usage', 'Nothing', False),
    ('temple-meeting', 'Temple: meeting extracts', 'internal',
     'Drafts a meeting record (summary, decisions, actions) from a transcript for you to check before saving.',
     'When you ask', ['Temple meeting extract'], 'The transcript you supply', 'A draft you edit and save', True),
    ('temple-org-research', 'Temple: organisation research', 'internal',
     'Searches the public web for an organisation and proposes profile facts, each citing the page it came from.',
     'When you ask (Research on the Organisations page)', ['Temple organisation research'],
     'Public web pages found by the search', 'Organisation facts awaiting your approval', True),
    ('temple-opportunities', 'Temple: client opportunities', 'internal',
     'Watches the organisations you tick: reads the approved profile, searches recent news, suggests opportunities citing the news, and re-checks open ones (still live, changed or closed).',
     'On each watched organisation\'s schedule (clients weekly by default), or Run now', ['Temple opportunity scan'],
     'Approved organisation facts; public news found by the search', 'Opportunity suggestions and news in the tracker', True),
    ('temple-search-discuss', 'Temple: research and scan explanations', 'internal',
     'Explains why one organisation research run or opportunity scan found what it found, from that run\'s record, and may suggest research '
     'guidance for the organisation. Advisory: changes nothing; guidance is saved only when you approve it.',
     'When you ask (Ask Temple on a run, Organisations page)', ['Temple research discussion'],
     'One run\'s record (searches, sources, found and rejected with reasons), the organisation\'s approved profile and its guidance',
     'Replies; suggested guidance waiting for your approval', False),
    ('alice-assistants', 'Assistants (e.g. HR policy assistant)', 'internal',
     'Focused chat bots built on Alice: each answers only from knowledge in its scope, with its own rule packs applied in code.',
     'When someone asks an assistant', ['Assistant'],
     'Knowledge in the assistant\'s categories; the question (checked by its rule packs first)', 'Nothing: answers only, no transcript kept', True),
    ('alice-proposal-writer', 'Proposal writer', 'internal',
     'Writes a proposal into your template from a brief, using the client\'s profile and relevant memories and knowledge; '
     'chooses the days per role from the rate card (Alice prices them). Revises once if the QA agent finds problems.',
     'When someone starts a proposal on the Proposal writer page', ['Proposal writer'],
     'The brief; the template\'s sections and guidance; the client profile, memories and knowledge for that client or general',
     'A draft proposal and a Word document for download (never knowledge)', True),
    ('alice-reference-summariser', 'Reference summariser', 'internal',
     'Summarises a reference document uploaded on the Proposal writer page; the summary lands in Knowledge as a draft '
     'pointing to the document, which stays in its document source.',
     'When someone uploads a reference document', ['Reference summary'],
     'The uploaded document (checked for secrets, markings and its Purview label first)', 'A knowledge draft awaiting your approval', True),
    ('parker', 'Parker: proposal assistant', 'internal',
     'Works through the proposal form with you in conversation: fills in title, client, brief, notes, template, structure, '
     'reference documents and roles with days from what you tell it, the client\'s brief and what Alice knows, and asks for '
     'what is missing (e.g. the named sponsor). Advisory: you see and can undo every change; nothing is saved.',
     'When someone chats with Parker on the Parker page', ['Parker'],
     'Your messages, the form (never rates) and any client brief you add; the client profile, memories and knowledge for that client or general; names of templates, reference documents and roles',
     'Nothing: changes to the form on the page only; a log line for Temple per turn', True),
    ('alice-proposal-qa', 'Argus: proposal QA', 'internal',
     'Argus checks each proposal draft against the brief and for client-ready quality: every requirement met, nothing invented, '
     'no placeholders, the right client, a consistent price. Advisory: the person decides.',
     'After every proposal draft and revision', ['Proposal QA'],
     'The brief, the draft, the sell-price summary and Alice\'s own checks (never cost rates)', 'A QA report with a verdict', False),
    ('team-member', 'Digital teams: member turns', 'internal',
     'Each turn of a digital team member (for example the Lead QS or the Cost Surveyor): reads the brief, the job documents and what it was '
     'handed, does its stage, checks incoming work and can send it back or ask you a question.',
     'When a digital team job runs (Teams page)', ['Digital team'],
     'The job brief and documents, the work handed on, knowledge in the member\'s categories (general or the job\'s client), public web pages for pricing',
     'Stage outputs, hand-offs (approved by you unless the team runs on its own), a draft cost plan in Word and Excel', True),
    ('team-talk', 'Digital teams: Talk to the team', 'internal',
     'Your messages to a digital team go to its lead, who answers from the team and the job and passes a note to another member when they '
     'should act on it the next time they work on the job. It cannot approve, change or restart anything.',
     'When you write in Talk to the team (a team or a job page)', ['Digital team'],
     'Your message, the team (roles and purposes), the job\'s brief, stages, outputs and recent steps, the conversation so far',
     'Replies, and notes passed to a member (kept with the job)', False),
    ('team-files-review', 'Digital teams: what new files change', 'internal',
     'When files are added to a job that has started, the team lead says what they change: a newer revision of a drawing (Alice\'s own code '
     'matches those first), new scope, or answers to flagged assumptions, and which elements each affects. Nothing is redone until you choose.',
     'When you add files to a job that has started (job page)', ['Digital team'],
     'The new files, the names of the job\'s documents, the plan\'s elements and the open flagged assumptions',
     'A report on the job page; you choose what to redo, with its estimated cost shown first', False),
    ('team-template-mapper', 'Digital teams: pricing template layout', 'internal',
     'Only when Alice\'s own code cannot find a pricing template\'s header row: the team lead\'s model reads the top rows of the template and '
     'says which columns hold the description, quantity, unit, rate and amount. Its answer is checked in code and you confirm the mapping.',
     'When a pricing template is added or used and code cannot read its layout', ['Digital team'],
     'The top rows of the pricing template (never job data)', 'A detected mapping for you to confirm', False),
    ('team-compare-matcher', 'Digital teams: match a reference cost plan', 'internal',
     'When a job is compared with a reference cost plan, Alice\'s own code parses it and matches its lines by code and by element, description '
     'and unit. Only the lines code cannot match go to the team lead\'s model, which proposes matches that code checks. All variance is worked '
     'out in code. The reference is never used by the team.',
     'When you compare a job with a reference cost plan (job page)', ['Digital team'],
     'The unmatched lines of the reference and of the team\'s cost plan: element, description, unit, quantity (no rates)',
     'Proposed matches, checked in code', False),
    ('team-compare-lessons', 'Digital teams: lessons from a reference cost plan', 'internal',
     'The team lead drafts short lessons from the differences you reviewed (reference right, team right, both acceptable or unclear), each '
     'citing its lines; they are filed as knowledge in the team\'s space through the usual checks and approval.',
     'When you ask the lead to draft lessons (comparison on the job page)', ['Digital team'],
     'The differences you reviewed, with both sides, your marks and notes', 'A knowledge note in the team\'s space', False),
    ('temple-compare-coach', 'Temple: instructions from a reference comparison', 'internal',
     'Temple proposes better standing instructions for each member whose work had differences you marked reference right or unclear, citing '
     'them. Each is a suggestion you accept, edit or reject; never applied on its own.',
     'When you ask Temple for instruction changes (comparison on the job page)', ['Temple team refinement'],
     'A member\'s standing instructions and the reviewed differences in its work', 'Suggested instructions waiting for you', False),
    ('temple-team-coach', 'Temple: digital team refinements', 'internal',
     'Talks a team member through with you and suggests better standing instructions from how its jobs went. A suggestion applies only when you approve it.',
     'When you ask (Ask Temple on a member, Teams page)', ['Temple team refinement'],
     'The member\'s settings and the notes, send-backs and answers from its recent jobs', 'Suggested instructions waiting for your approval', False),
    ('claude-desktop', 'Claude Desktop', 'app', 'Claude Desktop connected through the alice connector (stdio).',
     'When you use Claude Desktop', [], 'Files, memories and organisation profiles allowed to external apps',
     'Proposals, knowledge drafts, saved conversations', True),
    ('microsoft-copilot', 'Microsoft Copilot', 'app', 'Microsoft 365 Copilot through the signed-in external endpoint.',
     'When you use Copilot', [], 'Files, memories and organisation profiles allowed to external apps',
     'Proposals, knowledge drafts, saved conversations', True),
]
# The parts of each agent, for its anatomy diagram and the system map. model 'temple' = Temple's reviewer setting.
DATA_SOURCES = {'memories': 'Memories and decisions', 'knowledge': 'Knowledge', 'organisations': 'Organisation profiles',
                'chats': 'Chats and saved conversations', 'activity': 'Activity and usage', 'input': 'What you or staff type or paste',
                'web': 'The public web', 'documents': 'Document sources: SharePoint, Fabric, Power Platform (outside Alice)'}
_APP_ANATOMY = {'model': 'Its own model (the app decides)', 'instructions': 'Alice connector instructions plus your response guidance',
                'tools': TOOLS, 'data': ['memories', 'knowledge', 'organisations', 'chats'],
                'guardrails': ['external_scope', 'client_separation', 'provider_allow', 'protective_marking', 'secret_detection', 'pii',
                               'data_minimisation', 'approval_required'],
                'outputs': ['Memory, decision, knowledge and organisation-fact proposals', 'Saved conversations'],
                'gate': 'Everything it proposes waits for you on Actions', 'identity': 'Caller name on this computer'}
ANATOMY = {
    'temple-review': {'model': 'temple', 'instructions': 'Compare a proposed memory with up to 20 approved ones; report duplicates, contradictions and weak sources, and recommend approve, clarify or reject. Never approves.',
                      'tools': ['None: compares what it is given'], 'data': ['memories'],
                      'guardrails': ['spend_cap', 'approval_required', 'client_separation', 'secret_detection'],
                      'outputs': ['Review report with a recommendation', 'Suggested replacement of an older memory'],
                      'gate': 'You approve, reject or approve as a replacement'},
    'temple-chat': {'model': 'temple', 'instructions': 'Read the latest exchanges and suggest memories, decisions, knowledge or guidance, each quoting your own words.',
                    'tools': ['None: reads the chat it is given'], 'data': ['chats', 'memories'],
                    'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'pii', 'client_separation'],
                    'outputs': ['Suggestions in the chat and on Actions'], 'gate': 'You accept, edit or dismiss each suggestion'},
    'temple-chat-review': {'model': 'temple', 'instructions': 'Review a whole saved conversation for things worth keeping; every suggestion must quote you.',
                           'tools': ['Quote check against your own words'], 'data': ['chats', 'memories'],
                           'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'pii', 'client_separation'],
                           'outputs': ['Suggestions on Temple and Actions'], 'gate': 'You accept, edit or dismiss each suggestion'},
    'temple-categorise': {'model': 'temple', 'instructions': 'Choose the best of your categories for each uncategorised item, with a confidence.',
                          'tools': ['None'], 'data': ['memories', 'knowledge'], 'guardrails': ['spend_cap'],
                          'outputs': ['Category when 75%+ confident, otherwise a suggestion'], 'gate': 'Your category always wins; suggestions wait for you'},
    'temple-tagging': {'model': 'temple', 'instructions': 'Match each untagged item to one of your clients, or none.',
                       'tools': ['Name and alias matching (free, no model)'], 'data': ['memories', 'knowledge'],
                       'guardrails': ['spend_cap', 'client_separation'], 'outputs': ['Client tag when confident, otherwise a suggestion'],
                       'gate': 'Your tag always wins; suggestions wait for you'},
    'temple-memory-tags': {'model': 'temple', 'instructions': 'Choose which of your tags apply to each memory (usually one to three), with a confidence; respects each tag\'s area.',
                           'tools': ['None'], 'data': ['memories'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking'],
                           'outputs': ['Tags when 75%+ confident, otherwise suggestions'], 'gate': 'Your tags always win; a tag you remove is never put back'},
    'temple-model-eval': {'model': 'temple', 'instructions': 'The same prompts as the sharing check and categorising, on fixed fictional examples.',
                          'tools': ['None'], 'data': [], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking'],
                          'outputs': ['Right answers out of the examples, per model'], 'gate': 'Scores only: it changes nothing'},
    'temple-share-gate': {'model': 'temple', 'instructions': 'Say whether the item holds personal data about its author or others, special category data, or anything private.',
                          'tools': ['Personal identifier and special category checks (free, no model)'], 'data': ['memories', 'knowledge', 'organisations'],
                          'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'share_gate'],
                          'outputs': ['Clear, or held with reasons'], 'gate': 'The item\'s author shares anyway or keeps it personal'},
    'temple-space-sweep': {'model': 'temple', 'instructions': 'Say for each item in a personal space whether it is about the work, about the person themselves, sensitive or unsure.',
                           'tools': ['None'], 'data': ['memories', 'knowledge'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'share_gate'],
                           'outputs': ['Work items proposed for moving'], 'gate': 'The person confirms; each move goes through the sharing check'},
    'temple-router': {'model': 'temple', 'instructions': 'Say whether a new item is about the work, for the whole organisation, about its author, about a named person, or unsure.',
                      'tools': ['None'], 'data': ['memories', 'knowledge'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'temple_router', 'share_gate'],
                      'outputs': ['A route and its reason, kept on the item'], 'gate': 'The sharing check still runs on anything going into an open space'},
    'temple-replacements': {'model': 'temple', 'instructions': 'Decide whether a newer knowledge item replaces an older one; must quote the newer item.',
                            'tools': ['Wording and title matching (free, no model)', 'Quote check'], 'data': ['knowledge'],
                            'guardrails': ['spend_cap', 'provider_allow', 'protective_marking', 'secret_detection', 'client_separation'],
                            'outputs': ['Suggestion to retire the older item, with a quote'], 'gate': 'You retire it or keep both'},
    'demo-generator': {'model': 'Claude Sonnet 5.5 (or GPT-6 Luna)', 'instructions': 'A fictional team; public facts only; illustrative, never the organisation\'s real decisions; no real people.',
                       'tools': ['None'], 'data': ['organisations', 'web'], 'guardrails': ['secret_detection', 'protective_marking'],
                       'outputs': ['A demo scenario'], 'gate': 'You check it before loading; it only runs on the demo Alice'},
    'health-extract': {'model': 'Claude or GPT (only the ones you allow for health data)', 'instructions': 'Copy values, units and ranges exactly; never invent a range.',
                       'tools': ['None'], 'data': ['input'], 'guardrails': ['secret_detection', 'protective_marking', 'pii', 'spend_cap'],
                       'outputs': ['Results checked against the report text, waiting for you'], 'gate': 'You confirm every uncertain value'},
    'temple-taxonomy': {'model': 'temple', 'instructions': 'Keep categories few and broad, tags specific; prefer existing names; never name a client or person.',
                        'tools': ['None'], 'data': ['memories'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'client_separation'],
                        'outputs': ['Category and tag changes with Undo', 'Proposals on Actions'],
                        'gate': 'Yours and rule-protected categories wait for you; limits, names and near-duplicates checked in code'},
    'temple-discuss': {'model': 'temple', 'instructions': 'Discuss a waiting decision with the person deciding; explain clashes, say what would resolve them, '
                                                       'optionally a new recommendation and a suggested note. Never approves.',
                       'tools': ['None'], 'data': ['memories'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking'],
                       'outputs': ['Replies, a possible new recommendation, a suggested note'], 'gate': 'You still approve or reject'},
    'temple-ask': {'model': 'temple', 'instructions': 'Answer questions about what happened, using read-only tools and showing what it checked.',
                   'tools': ['Activity log search', 'Outstanding actions', 'Usage and costs'], 'data': ['activity'],
                   'guardrails': ['spend_cap', 'secret_detection'], 'outputs': ['An answer with what it checked'], 'gate': 'Nothing to approve: read-only'},
    'temple-meeting': {'model': 'temple', 'instructions': 'Turn a transcript into a title, date, attendees, summary, decisions and actions. Only what was said.',
                       'tools': ['None'], 'data': ['input'], 'guardrails': ['secret_detection', 'protective_marking', 'spend_cap'],
                       'outputs': ['Draft meeting record'], 'gate': 'You edit it, then save it'},
    'temple-org-research': {'model': 'temple', 'instructions': 'Find current public information about the organisation; one or two sentences per fact, '
                                                            'each with the exact page that supports it; roles, not people.',
                            'tools': ['Web search (provider built-in)'], 'data': ['web', 'organisations'],
                            'guardrails': ['secret_detection', 'protective_marking', 'data_minimisation', 'pii', 'spend_cap'],
                            'outputs': ['Proposed organisation facts with sources'], 'gate': 'You approve each fact on the Organisations page'},
    'temple-opportunities': {'model': 'temple', 'instructions': 'Find news from the last 60 days; suggest opportunities only where the news gives a '
                                                             'reason to engage now, mapped to your offerings, each with evidence.',
                             'tools': ['Web search (provider built-in)'], 'data': ['organisations', 'web'],
                             'guardrails': ['secret_detection', 'protective_marking', 'provider_allow', 'data_minimisation', 'spend_cap'],
                             'outputs': ['Opportunity suggestions with evidence', 'News items', 'Freshness checks on open opportunities'],
                             'gate': 'You accept or dismiss each suggestion; closed suggestions and stale ones (no action, not confirmed) are dismissed automatically and logged'},
    'temple-search-discuss': {'model': 'temple', 'instructions': 'Explain one research run or scan from its record: searches, sources, what was found and why things were rejected. '
                                                              'Optionally suggest research guidance; never relax the citation requirement or the rules.',
                              'tools': ['None'], 'data': ['organisations'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking', 'client_separation'],
                              'outputs': ['Replies; suggested guidance'], 'gate': 'You approve or reject suggested guidance'},
    'alice-assistants': {'model': 'Chosen per assistant (GPT-6 Luna or Claude Haiku 4.5)',
                         'instructions': 'Answer only from the sources in scope, cite them, never advise on individual cases; the assistant\'s guidance and its rule packs\' guidance.',
                         'tools': ['None: Alice picks the sources in code', 'Document source reader (only when the summaries do not answer)'],
                         'data': ['knowledge', 'documents', 'input'],
                         'guardrails': ['secret_detection', 'protective_marking', 'provider_allow', 'client_separation', 'data_minimisation', 'spend_cap'],
                         'outputs': ['Answers with cited sources'], 'gate': 'Rule packs block or escalate before any model sees the question'},
    'alice-proposal-writer': {'model': 'Chosen on the Proposal writer assistant (Claude Sonnet 5.5 by default)',
                              'instructions': 'Write every section of the template in order, only from the brief and the context given; '
                                              'never invent facts, figures, names or case studies; no prices (Alice adds the table); '
                                              'resource plan from the rate card roles only.',
                              'tools': ['Template reader (document sources)', 'Context gathering in code: client profile, memories, knowledge'],
                              'data': ['input', 'documents', 'organisations', 'memories', 'knowledge'],
                              'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'provider_allow', 'data_minimisation', 'spend_cap'],
                              'outputs': ['Draft proposal sections', 'Resource plan (days per role)', 'Gaps it could not fill'],
                              'gate': 'You review the QA report and the Word document before anything goes to a client'},
    'alice-reference-summariser': {'model': 'The Proposal writer\'s QA model (Claude Sonnet 5.5 by default)',
                                   'instructions': 'Summarise the document for a proposal team: what it is, the main points and frameworks, '
                                                   'key points and what it is useful for. Nothing that is not in it.',
                                   'tools': ['Suggests save location, title, category and tag in code (General when it names no client)'],
                                   'data': ['input', 'documents'],
                                   'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'spend_cap'],
                                   'outputs': ['Knowledge draft pointing to the document'],
                                   'gate': 'You approve the summary on the Knowledge page'},
    'parker': {'model': 'The Proposal writer\'s chat model (Claude Sonnet 5.5 by default)',
               'instructions': 'Complete the proposal form with the person: fill or improve fields from their messages, the client\'s document '
                               'and what Alice knows; never invent; choose only templates, documents and roles on offer; ask for what is missing.',
               'tools': ['Context gathering in code: client profile, memories, knowledge (same rules as the writer)',
                         'Checks in code: anything not on offer is dropped; rates are never sent'],
               'data': ['input', 'documents', 'organisations', 'memories', 'knowledge'],
               'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'provider_allow', 'data_minimisation', 'spend_cap'],
               'outputs': ['A reply, changes to the form, questions still open', 'A log line for Temple (what changed, never the conversation)'],
               'gate': 'Advisory: every change is outlined on the page and can be undone; nothing is written until you start the proposal'},
    'alice-proposal-qa': {'model': 'Chosen on the Proposal writer assistant (Claude Sonnet 5.5 by default)',
                          'instructions': 'Check the draft against the brief requirement by requirement and for client-ready quality; '
                                          'return a verdict, a score and specific fixes.',
                          'tools': ['Alice checks in code: placeholders, other clients named, prices in text, empty sections'],
                          'data': ['input'],
                          'guardrails': ['secret_detection', 'protective_marking', 'spend_cap'],
                          'outputs': ['QA report: verdict, score, requirements met, issues with fixes'],
                          'gate': 'Advisory: one automatic revision, then you decide'},
    'team-member': {'model': 'Chosen per member on the Teams page',
                    'instructions': 'The member\'s purpose and standing instructions, the stage\'s task, what it hands on and what it checks before accepting work.',
                    'tools': ['Web search (provider built-in), for the Cost Surveyor', 'Arithmetic and source checks in code'],
                    'data': ['input', 'documents', 'knowledge', 'web'],
                    'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'client_documents', 'provider_allow', 'rate_sources', 'spend_cap'],
                    'outputs': ['Stage outputs and hand-off notes', 'Questions for you', 'Word and Excel cost plan (draft)'],
                    'gate': 'You approve each hand-off (or only the final output) on Actions'},
    'team-talk': {'model': 'The lead\'s model, chosen on the team page',
                  'instructions': 'Answer the user for the team from the team and job data; route a faithful note to the member who should act on it. Never invent progress.',
                  'tools': ['None'], 'data': ['input'], 'guardrails': ['secret_detection', 'protective_marking', 'spend_cap'],
                  'outputs': ['Replies; notes passed to a member for their next turn'], 'gate': 'Advisory: it changes nothing; you act on the page'},
    'team-files-review': {'model': 'The team lead\'s model', 'instructions': 'Say what each new file changes (revision, new scope, answers, other) and which elements it affects. Never plan, measure or price.',
                          'tools': ['Revision matching in code (drawing number, name)'], 'data': ['documents'],
                          'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'provider_allow', 'spend_cap'],
                          'outputs': ['A report on the new files; the options and their estimated costs are worked out in code'], 'gate': 'You choose what to redo'},
    'team-template-mapper': {'model': 'The team lead\'s model', 'instructions': 'Find the header row and which column holds each role; list element headings.',
                             'tools': ['None'], 'data': ['documents'], 'guardrails': ['secret_detection', 'protective_marking', 'provider_allow', 'spend_cap'],
                             'outputs': ['A detected mapping, checked in code'], 'gate': 'You confirm or correct the mapping'},
    'team-compare-matcher': {'model': 'The team lead\'s model', 'instructions': 'Propose which reference line is the same work as which team item, only where confident.',
                             'tools': ['Parsing and matching in code (code, element, description, unit)'], 'data': ['documents'],
                             'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'provider_allow', 'spend_cap'],
                             'outputs': ['Proposed matches, checked in code; every figure worked out in code'], 'gate': 'You review each difference'},
    'team-compare-lessons': {'model': 'The team lead\'s model', 'instructions': 'Draft short lessons from the differences the user reviewed, citing them. Never invent figures.',
                             'tools': ['None'], 'data': ['documents', 'input'],
                             'guardrails': ['secret_detection', 'protective_marking', 'client_separation', 'provider_allow', 'spend_cap'],
                             'outputs': ['A knowledge note in the team\'s space'], 'gate': 'Knowledge checks and approval'},
    'temple-compare-coach': {'model': 'temple', 'instructions': 'Suggest complete new standing instructions for a member, citing reviewed differences. Never weaken a safeguard.',
                             'tools': ['None'], 'data': ['input'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking'],
                             'outputs': ['Suggested instructions'], 'gate': 'You accept, edit or reject each suggestion'},
    'temple-team-coach': {'model': 'temple', 'instructions': 'Explain how a team member\'s jobs went and, when it would help, suggest complete new standing instructions. Never weaken a safeguard.',
                          'tools': ['None'], 'data': ['input'], 'guardrails': ['spend_cap', 'secret_detection', 'protective_marking'],
                          'outputs': ['Replies; suggested instructions'], 'gate': 'You approve or reject each suggestion'},
    'claude-desktop': dict(_APP_ANATOMY, model='Claude (your Claude Desktop model)', identity='Caller name on this computer (stdio)'),
    'microsoft-copilot': dict(_APP_ANATOMY, model='Microsoft 365 Copilot', identity='Entra ID token from ' + deployment.tenant()),
}
# How the Agents page groups agents: (id, name, what the group is for, member agent ids). Apps form their own group.
GROUPS = [
    ('proposals', 'Proposals', 'Complete the form with Parker, write proposals into your template, check them against the brief, and summarise reference documents.',
     ['parker', 'alice-proposal-writer', 'alice-proposal-qa', 'alice-reference-summariser']),
    ('clients', 'Clients and opportunities', 'Research organisations on the public web and look for opportunities in the news.',
     ['temple-org-research', 'temple-opportunities', 'temple-search-discuss', 'demo-generator']),
    ('conversations', 'Learning from conversations', 'Suggest memories, decisions and knowledge from chats, saved conversations and meetings.',
     ['temple-chat', 'temple-chat-review', 'temple-meeting']),
    ('stewardship', 'Keeping memory and knowledge tidy', 'Review proposed memories, categorise and tag them, tag clients and spot replaced knowledge.',
     ['temple-review', 'temple-discuss', 'temple-taxonomy', 'temple-categorise', 'temple-memory-tags', 'temple-tagging', 'temple-replacements', 'temple-share-gate', 'temple-space-sweep', 'temple-router', 'temple-model-eval']),
    ('apps_agents', 'Inside your apps', 'Agents that do one job inside an app, such as reading a lab report for Health Insights.',
     ['health-extract']),
    ('teams', 'Digital teams', 'Members of your digital teams working jobs stage by stage, and Temple suggesting how to refine them.',
     ['team-member', 'team-talk', 'team-files-review', 'team-template-mapper', 'team-compare-matcher', 'team-compare-lessons', 'temple-team-coach',
      'temple-compare-coach']),
    ('answers', 'Answering questions', 'Staff assistants that answer from approved knowledge, and Ask Temple for your own questions.',
     ['alice-assistants', 'temple-ask']),
]
_AGENT_GROUP = {aid: g for g, _, _, ids in GROUPS for aid in ids}


def group_of(a):
    return 'apps' if a['kind'] == 'app' else _AGENT_GROUP.get(a['id'], 'other')


_ANATOMY_KEYS = ('model', 'identity', 'instructions', 'tools', 'data', 'guardrails', 'outputs', 'gate')
_current = contextvars.ContextVar('alice_agent_run', default=None)
_cost_sink = contextvars.ContextVar('alice_cost_sink', default=None)


class cost_box:
    """Add up the cost of every model call made inside the block (e.g. for one proposal), whichever agent makes it."""
    def __enter__(self):
        self.calls, self.usd = [], 0.0
        self._tok = _cost_sink.set(self)
        return self
    def __exit__(self, *a):
        _cost_sink.reset(self._tok)
        return False


def _now(): return store.now()


def slug(label):
    return re.sub(r'[^a-z0-9]+', '-', (label or '').lower()).strip('-')[:40] or 'external-app'


def _default_perms(kind):
    if kind == 'app':
        return {'tools': [], 'mode': 'propose', 'categories': [], 'labels': [], 'max_calls_per_day': 500}
    return {}


with store.db() as c:
    c.execute('''CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, owner TEXT NOT NULL DEFAULT 'Owner',
        purpose TEXT NOT NULL DEFAULT '', trigger TEXT NOT NULL DEFAULT '', workloads TEXT NOT NULL DEFAULT '[]', reads TEXT NOT NULL DEFAULT '',
        writes TEXT NOT NULL DEFAULT '', external_content INTEGER NOT NULL DEFAULT 0, permissions TEXT NOT NULL DEFAULT '{}',
        budget_usd REAL, status TEXT NOT NULL DEFAULT 'active', status_reason TEXT NOT NULL DEFAULT '', review_by TEXT,
        version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agent_versions (agent_id TEXT NOT NULL, version INTEGER NOT NULL, config TEXT NOT NULL,
        changed_at TEXT NOT NULL, changed_by TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', PRIMARY KEY (agent_id, version))''')
    c.execute('''CREATE TABLE IF NOT EXISTS agent_runs (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, trigger TEXT NOT NULL DEFAULT '',
        started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL DEFAULT 'running', summary TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', cost_usd REAL NOT NULL DEFAULT 0, calls INTEGER NOT NULL DEFAULT 0, day TEXT)''')
    c.execute('CREATE INDEX IF NOT EXISTS agent_runs_agent ON agent_runs(agent_id, started_at)')
    c.execute('''CREATE TABLE IF NOT EXISTS agent_events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, at TEXT NOT NULL,
        kind TEXT NOT NULL, target_type TEXT NOT NULL DEFAULT '', target_id TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '')''')
    c.execute('CREATE INDEX IF NOT EXISTS agent_events_run ON agent_events(run_id)')
    if 'anatomy' not in {r['name'] for r in c.execute('PRAGMA table_info(agents)')}:
        c.execute("ALTER TABLE agents ADD COLUMN anatomy TEXT NOT NULL DEFAULT '{}'")
    _run_cols = {r['name'] for r in c.execute('PRAGMA table_info(agent_runs)')}
    for _col, _ddl in (('ack_at', 'TEXT'), ('ack_kind', "TEXT NOT NULL DEFAULT ''"), ('ack_note', "TEXT NOT NULL DEFAULT ''")):
        if _col not in _run_cols: c.execute(f'ALTER TABLE agent_runs ADD COLUMN {_col} {_ddl}')
    for _aid, _name, _kind, _purpose, _trigger, _workloads, _reads, _writes, _ext in BUILTIN:
        if not c.execute('SELECT 1 FROM agents WHERE id=?', (_aid,)).fetchone():
            _perms = json.dumps(_default_perms(_kind))
            c.execute('INSERT INTO agents(id,name,kind,purpose,trigger,workloads,reads,writes,external_content,permissions,created_at,updated_at,review_by) '
                      'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (_aid, _name, _kind, _purpose, _trigger, json.dumps(_workloads), _reads, _writes, int(_ext),
                                                           _perms, _now(), _now(), (date.today() + timedelta(days=365)).isoformat()))
            c.execute('INSERT INTO agent_versions VALUES (?,?,?,?,?,?)', (_aid, 1, json.dumps({'permissions': json.loads(_perms)}), _now(), 'Alice', 'Registered'))
    for _aid, _old, _new in AGENT_RENAMES:            # named agents: renamed once if they still have the old name (logged)
        if c.execute('SELECT 1 FROM agents WHERE id=? AND name=?', (_aid, _old)).fetchone():
            c.execute('UPDATE agents SET name=?,updated_at=? WHERE id=?', (_new, _now(), _aid))
            store.audit(c, 'agent_renamed', _aid, 'human_control', f'{_old} renamed {_new} (owner\'s request)')


# ---------------- reading ----------------
def _row(r):
    d = dict(r)
    d['workloads'] = json.loads(d['workloads'] or '[]')
    perms = _default_perms(d['kind']); perms.update(json.loads(d['permissions'] or '{}')); d['permissions'] = perms
    d['external_content'] = bool(d['external_content'])
    base = dict(ANATOMY.get(d['id']) or (_APP_ANATOMY if d['kind'] == 'app' else {}))
    base.update({k: v for k, v in json.loads(d.get('anatomy') or '{}').items() if k in _ANATOMY_KEYS})
    d['anatomy'] = base
    return d


def live_anatomy(a):
    """The anatomy with today's facts filled in: Temple's current model, and each guardrail's name and whether it is on."""
    an = dict(a['anatomy'])
    if an.get('model') == 'temple':
        try:
            import temple, speed
            an['model'] = 'Temple reviewer: ' + ('GPT-6 Luna' if speed.memo('temple_reviewer', temple.reviewer) == 'openai' else 'Claude Haiku 4.5')
        except Exception:
            an['model'] = 'Temple reviewer'
    try:
        import rules_engine
        rules = {r['id']: r for r in rules_engine.all_rules()}
    except Exception:
        rules = {}
    an['guardrails'] = [{'id': g, 'name': rules[g]['name'] if g in rules else g, 'on': bool(rules.get(g, {}).get('enabled', True))}
                        for g in an.get('guardrails', [])]
    an['data'] = [{'key': k, 'name': DATA_SOURCES.get(k, k)} for k in an.get('data', [])]
    if a['id'] in ('alice-proposal-writer', 'alice-proposal-qa'):        # the model is set on each Proposal writer assistant
        try:
            import assistants, speed
            names = []
            for x in speed.memo('assistants_listing', assistants.listing)['assistants']:
                if x['kind'] != 'proposal': continue
                k = x['provider'] if a['id'] == 'alice-proposal-writer' else (x['settings'].get('qa_provider') or x['provider'])
                names.append(f"{assistants.PROVIDERS.get(k, (k, k))[1]} ({x['name']})")
            if names: an['model'] = ', '.join(names) + ' by default; change it on the Assistants page or on each proposal'
        except Exception:
            pass
    if a['kind'] == 'app' and a['permissions'].get('tools'): an['tools'] = a['permissions']['tools']
    return an


def get(aid):
    with store.db() as c:
        r = c.execute('SELECT * FROM agents WHERE id=?', (aid,)).fetchone()
    if not r: raise ValueError('Agent not found.')
    return _row(r)


def _month_start():
    n = datetime.now(timezone.utc)
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def tidy():
    """Runs left 'running' by a restart become 'interrupted'; an app's day of tool calls closes when the day ends."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    today = date.today().isoformat()
    with store.db() as c:
        c.execute("UPDATE agent_runs SET status='interrupted',finished_at=coalesce(finished_at,started_at),error='Alice stopped or restarted during the run' "
                  "WHERE status='running' AND day IS NULL AND started_at<?", (cutoff,))
        c.execute("UPDATE agent_runs SET status='complete' WHERE status='running' AND day IS NOT NULL AND day<?", (today,))


def listing():
    tidy()
    today = date.today().isoformat()
    month = _month_start()
    with store.db() as c:
        agents = [_row(r) for r in c.execute("SELECT * FROM agents ORDER BY kind='app', name") if r['id'] not in RETIRED]
        stats = {r['agent_id']: dict(r) for r in c.execute(
            "SELECT agent_id,count(*) AS runs,sum(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,sum(cost_usd) AS cost,sum(calls) AS calls "
            "FROM agent_runs WHERE started_at>=? GROUP BY agent_id", (month,))}
        last = {}
        for r in c.execute('SELECT * FROM agent_runs ORDER BY started_at'):
            last[r['agent_id']] = dict(r)
        proposals = {}
        for r in c.execute("SELECT source FROM records WHERE status='proposed' AND source LIKE '%[via %'"):
            m = re.search(r'\[via ([^\]]+)\]\s*$', r['source'])
            if m: proposals[slug(m.group(1))] = proposals.get(slug(m.group(1)), 0) + 1
    for a in agents:
        s = stats.get(a['id'], {})
        a.update(runs_month=s.get('runs') or 0, failed_month=s.get('failed') or 0, cost_month=round(s.get('cost') or 0, 4),
                 calls_month=s.get('calls') or 0, last_run=last.get(a['id']), waiting=proposals.get(a['id'], 0),
                 review_overdue=bool(a['review_by'] and a['review_by'] < today))
        a['failure_open'] = failure_open(a.get('last_run'))
    order = {aid: n for _, _, _, ids in GROUPS for n, aid in enumerate(ids)}
    for a in agents: a['anatomy_live'] = live_anatomy(a); a['group'] = group_of(a); a['group_order'] = order.get(a['id'], 99)
    try:
        import rules_engine
        rule_list = [{'id': r['id'], 'name': r['name'], 'enabled': r['enabled']} for r in rules_engine.all_rules() if r['kind'] == 'enforced']
    except Exception:
        rule_list = []
    groups = [{'id': g, 'name': n, 'about': d} for g, n, d, _ in GROUPS] + [
        {'id': 'other', 'name': 'Other automations', 'about': 'Automations not in a group yet.'},
        {'id': 'apps', 'name': 'Connected apps', 'about': 'Every tool call is checked against the app\'s permissions. New apps appear here when they first connect.'}]
    return {'agents': agents, 'groups': groups, 'tools': TOOLS, 'write_tools': sorted(WRITE_TOOLS), 'labels': LABELS, 'data_sources': DATA_SOURCES, 'rules': rule_list}


def runs(aid, limit=50, offset=0):
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM agent_runs WHERE agent_id=? ORDER BY started_at DESC LIMIT ? OFFSET ?', (aid, limit, offset))]
        total = c.execute('SELECT count(*) FROM agent_runs WHERE agent_id=?', (aid,)).fetchone()[0]
        for r in rows:
            r['events'] = c.execute('SELECT count(*) FROM agent_events WHERE run_id=?', (r['id'],)).fetchone()[0]
    return {'runs': rows, 'total': total, 'next_offset': offset + len(rows) if offset + len(rows) < total else None}


def _mask(rows, key='target_name'):
    """Demo mode: item names become neutral labels (Memory 1, Organisation A...), so nothing real shows on screen."""
    seen = {}
    for r in rows:
        t = r.get('target_type') or 'item'
        if not r.get('target_id'): continue
        n = seen.setdefault(t, {}).setdefault(r['target_id'], len(seen.get(t, {})) + 1)
        label = t.replace('_', ' ').capitalize() + ' ' + (chr(64 + n) if t == 'organisation' and n <= 26 else str(n))
        r[key] = label; r['target_id'] = ''
        if r.get('detail') and t in ('organisation',): r['detail'] = ''
    return rows


def run_detail(run_id, demo=False):
    with store.db() as c:
        r = c.execute('SELECT * FROM agent_runs WHERE id=?', (run_id,)).fetchone()
        if not r: raise ValueError('Run not found.')
        ev = [dict(e) for e in c.execute('SELECT * FROM agent_events WHERE run_id=? ORDER BY id', (run_id,))]
    names = {}
    try:
        import activity_log
        names = activity_log._names([e['target_id'] for e in ev])
    except Exception:
        pass
    for e in ev: e['target_name'] = names.get(e['target_id'], '')
    if demo:
        _mask(ev)
        for e in ev:
            if e['detail'].startswith('search: '): e['detail'] = 'search'
    touched = {}
    for e in ev:
        if e['kind'] in ('read', 'wrote') and e['target_id']:
            touched.setdefault(e['kind'], {}).setdefault(e['target_type'], set()).add(e['target_id'])
    return {'run': dict(r), 'events': ev,
            'touched': {k: {t: len(v) for t, v in d.items()} for k, d in touched.items()}}


# Where each kind of item comes from, for the Data touched tab. Order is the order shown.
SOURCE_GROUPS = [
    ('web', 'Internet', 'Public web pages, read during the run. Not stored in Alice except as a cited source URL.'),
    ('library', 'Document sources', 'Full documents in SharePoint, Fabric, Power Platform or folders (simulated by the Documents folder for now), read on demand for one answer. Not stored in Alice.'),
    ('knowledge', 'Files and knowledge', 'Uploaded files, notes and meeting records stored in Alice.'),
    ('memories', 'Memories and decisions', 'Approved and proposed memories and decisions in Alice.'),
    ('organisations', 'Organisations', 'Organisation profiles, facts and opportunities in Alice.'),
    ('chats', 'Chats', 'Chats and saved conversations in Alice.'),
    ('other', 'Other', ''),
]
_GROUP_OF = {'web': 'web', 'document': 'library', 'knowledge': 'knowledge', 'file': 'knowledge', 'memory': 'memories', 'decision': 'memories',
             'organisation': 'organisations', 'org_fact': 'organisations', 'opportunity': 'organisations', 'chat': 'chats'}
TYPE_NAMES = {'web': 'Web page', 'document': 'Document', 'knowledge': 'Knowledge', 'file': 'File', 'memory': 'Memory',
              'decision': 'Decision', 'organisation': 'Organisation', 'org_fact': 'Organisation fact', 'opportunity': 'Opportunity', 'chat': 'Chat'}
_HEX = re.compile(r'^[0-9a-f]{32}$')


def _describe(rows):
    """Fill in where each item lives: a URL, a file path or the Alice page that holds it, plus its current status and label."""
    from urllib.parse import quote, urlparse
    ids = lambda *types: [r['target_id'] for r in rows if r['target_type'] in types and _HEX.match(r['target_id'])]
    info = {}
    with store.db() as c:
        def q(sql, keys):
            if not keys: return []
            try: return [dict(x) for x in c.execute(sql.format(','.join('?' * len(keys))), keys)]
            except Exception: return []
        for x in q("SELECT f.id,f.name,m.title,m.kind,m.status,m.label,m.source FROM files f LEFT JOIN knowledge_meta m ON m.file_id=f.id WHERE f.id IN ({})",
                   ids('knowledge', 'file')):
            info[x['id']] = {'name': x['title'] or x['name'], 'status': x['status'] or 'active', 'label': x['label'] or 'general',
                             'location': (('Uploaded file: ' + x['name']) if (x['kind'] or 'file') == 'file' else (x['source'] or '')),
                             'href': '/admin/knowledge?status=all&q=' + quote((x['title'] or x['name'])[:80])}
        for x in q("SELECT r.id,r.title,r.status,r.source,a.state,m.kind FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id "
                   "LEFT JOIN record_meta m ON m.record_id=r.id WHERE r.id IN ({})", ids('memory', 'decision')):
            info[x['id']] = {'name': x['title'], 'status': x['state'] or x['status'], 'kind': x['kind'] or 'fact', 'location': x['source'] or '',
                             'href': '/admin/memories?status=all&q=' + quote(x['title'][:80])}
        for x in q('SELECT id,org,statement,status,label,source_ref FROM org_facts WHERE id IN ({})', ids('org_fact')):
            info[x['id']] = {'name': x['org'] + ': ' + x['statement'][:90], 'status': x['status'], 'label': x['label'],
                             'location': x['source_ref'] or '', 'href': '/admin/organisations?org=' + quote(x['org'])}
        for x in q('SELECT id,org,title,status FROM opportunities WHERE id IN ({})', ids('opportunity')):
            info[x['id']] = {'name': x['org'] + ': ' + x['title'], 'status': x['status'], 'href': '/admin/organisations?org=' + quote(x['org'])}
        for x in q('SELECT id,title FROM chats WHERE id IN ({})', ids('chat')):
            info[x['id']] = {'name': x['title'] or 'Untitled chat', 'location': 'Chat in Alice'}
    try:
        import doc_library
        root = str(doc_library.ROOT)
    except Exception:
        root = ''
    for r in rows:
        t, tid = r['target_type'], r['target_id']
        d = info.get(tid, {})
        r['group'] = _GROUP_OF.get(t, 'other')
        r['type_name'] = TYPE_NAMES.get('decision' if d.get('kind') == 'decision' else t, t.replace('_', ' ').capitalize() or 'Item')
        r['external'] = t in ('web', 'document')
        r['status'], r['label'], r['location'], r['href'] = d.get('status', ''), d.get('label', ''), d.get('location', ''), d.get('href', '')
        if t == 'web':
            u = urlparse(tid)
            r['target_name'] = r.get('target_name') or u.netloc or tid
            r['location'], r['href'] = tid, (tid if u.scheme in ('http', 'https') else '')
        elif t == 'document':
            r['target_name'] = tid.replace('\\', '/').rsplit('/', 1)[-1]
            r['location'] = (root.rstrip('\\/') + ('\\' if '\\' in root else '/') + tid) if root else tid
            try:
                import doc_library
                p = doc_library.resolve(tid)
                r['where'] = doc_library.describe(p) if p else 'No longer in the document sources'
                if not p: r['status'] = 'deleted'
            except Exception:
                pass
        elif t == 'organisation':
            r['target_name'] = tid; r['href'] = '/admin/organisations?org=' + quote(tid)
        elif d:
            r['target_name'] = d['name']
        elif _HEX.match(tid or ''):
            r['status'] = 'deleted'                                  # no longer in Alice
        if not r.get('target_name'): r['target_name'] = tid
    return rows


def touched_items(aid, days=30, demo=False):
    """Lineage: which items this agent read or wrote in the period, newest first, one row per item, with where it lives."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store.db() as c:
        ev = c.execute("SELECT e.run_id,e.kind,e.target_type,e.target_id,e.at,e.detail FROM agent_events e JOIN agent_runs r ON r.id=e.run_id "
                       "WHERE r.agent_id=? AND e.at>=? AND e.kind IN ('read','wrote') AND e.target_id<>'' ORDER BY e.at DESC LIMIT 5000",
                       (aid, since)).fetchall()
        run_ids = list({e['run_id'] for e in ev})
        models = {}
        for i in range(0, len(run_ids), 500):
            part = run_ids[i:i + 500]
            for m in c.execute(f"SELECT DISTINCT run_id,target_type,target_id FROM agent_events WHERE kind='model' AND run_id IN ({','.join('?' * len(part))})", part):
                models.setdefault(m['run_id'], set()).add(model_label(m['target_type'], m['target_id']))
        agent = c.execute('SELECT name,kind FROM agents WHERE id=?', (aid,)).fetchone()
    is_app = bool(agent and agent['kind'] == 'app')
    items = {}
    for e in ev:
        k = (e['target_type'], e['target_id'])
        i = items.get(k)
        if not i:
            i = items[k] = {'target_type': e['target_type'], 'target_id': e['target_id'], 'kind': e['kind'], 'last': e['at'], 'first': e['at'],
                            'read': 0, 'wrote': 0, 'times': 0, 'details': [], 'sent_to': set(), 'produced_by': set()}
        if e['kind'] == 'read':                  # what read it went to: the models its run called, or the app itself
            i['sent_to'] |= ({agent['name'] + ' (connected app)'} if is_app else models.get(e['run_id'], set()))
        else:
            i['produced_by'] |= models.get(e['run_id'], set())
        i[e['kind']] += 1; i['times'] += 1; i['first'] = e['at']
        if i['read'] and i['wrote']: i['kind'] = 'read and wrote'
        dt = (e['detail'] or '').strip()
        if dt and dt not in i['details'] and len(i['details']) < 3: i['details'].append(dt)
    rows = list(items.values())[:300]
    for r in rows: r['sent_to'], r['produced_by'] = sorted(r['sent_to']), sorted(r['produced_by'])
    try:
        import activity_log
        names = activity_log._names([r['target_id'] for r in rows])
    except Exception:
        names = {}
    for r in rows: r['target_name'] = names.get(r['target_id'], '').split(': ', 1)[-1] if names.get(r['target_id']) else ''
    _describe(rows)
    if demo:
        _mask(rows)
        for r in rows: r['location'] = r['href'] = r['where'] = ''; r['details'] = []
    return rows


def touched_groups(rows):
    """The rows grouped by where the data came from, in a fixed order, with counts."""
    out = []
    for key, name, note in SOURCE_GROUPS:
        g = [r for r in rows if r['group'] == key]
        if g: out.append({'key': key, 'name': name, 'note': note, 'items': g, 'read': sum(1 for r in g if r['read']),
                          'wrote': sum(1 for r in g if r['wrote'])})
    return out


def versions(aid):
    with store.db() as c:
        return [dict(r) | {'config': json.loads(r['config'])} for r in c.execute(
            'SELECT * FROM agent_versions WHERE agent_id=? ORDER BY version DESC', (aid,))]


# ---------------- your controls ----------------
def set_status(aid, status, reason='', by='you'):
    if status not in ('active', 'paused', 'stopped'): raise ValueError('Status must be active, paused or stopped.')
    a = get(aid)
    reason = ' '.join((reason or '').split())[:300]
    with store.db() as c:
        c.execute('UPDATE agents SET status=?,status_reason=?,updated_at=? WHERE id=?',
                  (status, reason if by != 'you' or reason else ('' if status == 'active' else 'by you'), _now(), aid))
        if status == 'active':      # resuming clears the failure streak
            c.execute("UPDATE agent_runs SET status='failed (cleared)' WHERE agent_id=? AND status='failed'", (aid,))
        store.audit(c, 'agent_' + status, aid, 'human_review' if by == 'you' else 'automatic_safeguard',
                    f'{a["name"]}: {status}' + (f' ({reason})' if reason else '') + f' by {by}')
    return get(aid)


def _clean_anatomy(an, a):
    out = {}
    clean = lambda v, n: ' '.join(str(v or '').split())[:n]
    for k in ('model', 'identity', 'instructions', 'gate'):
        if k in an: out[k] = clean(an[k], 400 if k == 'instructions' else 160)
    for k in ('tools', 'outputs'):
        if k in an: out[k] = [clean(x, 100) for x in (an[k] or []) if str(x).strip()][:20]
    if 'data' in an:
        bad = [x for x in an['data'] if x not in DATA_SOURCES]
        if bad: raise ValueError('Unknown data sources: ' + ', '.join(bad))
        out['data'] = list(dict.fromkeys(an['data']))
    if 'guardrails' in an:
        import rules_engine
        known = {r['id'] for r in rules_engine.all_rules()}
        bad = [x for x in an['guardrails'] if x not in known]
        if bad: raise ValueError('Unknown rules: ' + ', '.join(bad))
        out['guardrails'] = list(dict.fromkeys(an['guardrails']))
    return out


def update(aid, purpose=None, permissions=None, budget_usd=None, review_by=None, note='', clear_budget=False, anatomy=None):
    a = get(aid)
    fields, args = [], []
    if anatomy is not None:
        with store.db() as c:      # keep only your overrides, so built-in defaults can still improve later
            stored = json.loads(c.execute('SELECT anatomy FROM agents WHERE id=?', (aid,)).fetchone()[0] or '{}')
        stored.update(_clean_anatomy(anatomy, a))
        fields.append('anatomy=?'); args.append(json.dumps(stored))
    if purpose is not None:
        fields.append('purpose=?'); args.append(' '.join(purpose.split())[:1000])
    if permissions is not None:
        if a['kind'] != 'app': raise ValueError('Internal automations are limited by their rules and budget, not tool permissions.')
        p = dict(a['permissions'])
        if 'tools' in permissions:
            bad = [t for t in permissions['tools'] if t not in TOOLS]
            if bad: raise ValueError('Unknown tools: ' + ', '.join(bad))
            p['tools'] = sorted(set(permissions['tools']))
        if 'mode' in permissions:
            if permissions['mode'] not in ('read', 'propose'): raise ValueError('Mode must be read or propose.')
            p['mode'] = permissions['mode']
        if 'categories' in permissions:
            p['categories'] = [' '.join(str(x).split())[:40] for x in permissions['categories'] if str(x).strip()][:50]
        if 'labels' in permissions:
            bad = [x for x in permissions['labels'] if x not in LABELS]
            if bad: raise ValueError('Unknown labels: ' + ', '.join(bad))
            p['labels'] = sorted(set(permissions['labels']))
        if 'max_calls_per_day' in permissions:
            v = permissions['max_calls_per_day']
            p['max_calls_per_day'] = None if v in (None, '', 0) else max(1, min(100000, int(v)))
        fields.append('permissions=?'); args.append(json.dumps(p))
    if clear_budget:
        fields.append('budget_usd=NULL')
    elif budget_usd is not None:
        if budget_usd < 0 or budget_usd > 1000: raise ValueError('Budget must be between $0 and $1,000 a month.')
        fields.append('budget_usd=?'); args.append(round(float(budget_usd), 4))
    if review_by is not None:
        if review_by and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', review_by): raise ValueError('Use a date like 2027-03-31.')
        fields.append('review_by=?'); args.append(review_by or None)
    if not fields: return a
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        version = c.execute('SELECT version FROM agents WHERE id=?', (aid,)).fetchone()[0] + 1
        c.execute(f"UPDATE agents SET {','.join(fields)},version=?,updated_at=? WHERE id=?", args + [version, _now(), aid])
        row = _row(c.execute('SELECT * FROM agents WHERE id=?', (aid,)).fetchone())
        config = {'purpose': row['purpose'], 'permissions': row['permissions'], 'budget_usd': row['budget_usd'], 'review_by': row['review_by'],
                  'anatomy': row['anatomy']}
        c.execute('INSERT INTO agent_versions VALUES (?,?,?,?,?,?)', (aid, version, json.dumps(config), _now(), 'you', ' '.join(note.split())[:300]))
        store.audit(c, 'agent_updated', aid, 'human_review', f'{row["name"]}: version {version}' + (f' ({note})' if note else ''))
    return get(aid)


# ---------------- runs: internal automations ----------------
class AgentBlocked(ValueError):
    """Raised when an agent is paused, stopped, not allowed or over a limit. The message is safe to show."""


def _month_cost(aid):
    with store.db() as c:
        return c.execute('SELECT coalesce(sum(cost_usd),0) FROM agent_runs WHERE agent_id=? AND started_at>=?', (aid, _month_start())).fetchone()[0]


def _gate(a):
    if a['status'] != 'active':
        raise AgentBlocked(f'{a["name"]} is {a["status"]} on the Agents page' + (f' ({a["status_reason"]})' if a['status_reason'] else '') + '. Resume it there to run it.')
    if a['budget_usd'] is not None and _month_cost(a['id']) >= a['budget_usd']:
        set_status(a['id'], 'paused', f'reached its monthly budget of ${a["budget_usd"]:.2f}', by='Alice')
        raise AgentBlocked(f'{a["name"]} reached its monthly budget of ${a["budget_usd"]:.2f} and has been paused.')


def current():
    return _current.get()


def note(kind, target_type='', target_id='', detail=''):
    """Record what the running agent read or wrote (no-op outside a run)."""
    rid = _current.get()
    if not rid: return
    with store.db() as c:
        c.execute('INSERT INTO agent_events(run_id,at,kind,target_type,target_id,detail) VALUES (?,?,?,?,?,?)',
                  (rid, _now(), kind, target_type, str(target_id or '')[:500], str(detail or '')[:500]))


MODEL_NAMES = {'gpt-6-luna': 'GPT-6 Luna', 'gpt-6-astra': 'GPT-6 Astra', 'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
               'claude-sonnet-5-5': 'Claude Sonnet 5.5', 'claude-opus-5-5': 'Claude Opus 5.5', 'grok-4.7': 'Grok 4.7'}
PROVIDER_NAMES = {'openai': 'OpenAI', 'claude': 'Anthropic', 'anthropic': 'Anthropic', 'grok': 'xAI', 'copilot': 'Microsoft'}


def model_label(provider, model):
    name = MODEL_NAMES.get(model, model or 'model')
    org = PROVIDER_NAMES.get(provider, provider or '')
    return f'{name} ({org})' if org else name


COST_HOOKS = []              # function(usd, provider, model, run_id) called for every model call (team_costs records a digital team's calls)


def add_cost(usd, provider='', model=''):
    """Called by usage_meter for every model call: the cost lands on the agent run in progress, if any, and the run
    records which model it called (for 'Sent to' on Data touched)."""
    box = _cost_sink.get()
    if box is not None:
        box.usd += float(usd or 0); box.calls.append((provider, model, float(usd or 0)))
    rid = _current.get()
    for hook in COST_HOOKS:
        try: hook(usd, provider, model, rid or '')
        except Exception: logging.getLogger('alice.agents').exception('A cost record could not be saved')
    if not rid: return
    with store.db() as c:
        c.execute('UPDATE agent_runs SET cost_usd=cost_usd+?,calls=calls+1 WHERE id=?', (float(usd or 0), rid))
        if model or provider:
            c.execute('INSERT INTO agent_events(run_id,at,kind,target_type,target_id,detail) VALUES (?,?,?,?,?,?)',
                      (rid, _now(), 'model', str(provider or '')[:40], str(model or '')[:80], 'called ' + model_label(provider, model)))


def _summary(result):
    if not isinstance(result, dict): return ''
    parts = [f'{k}: {v}' for k, v in result.items() if isinstance(v, (int, float, str)) and k not in ('message', 'id', 'status') and len(str(v)) < 60]
    return ', '.join(parts)[:300]


def tracked(aid, trigger='automatic', subject=None):
    """Decorator for an internal automation: checks the agent may run, records the run, its subject, cost and outcome.
    Runs that turn out to have nothing to do are not kept."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if _current.get():                   # nested inside another run: count it there
                return fn(*args, **kwargs)
            a = get(aid)
            _gate(a)
            how = 'you asked' if kwargs.get('manual') else trigger
            rid = uuid.uuid4().hex
            with store.db() as c:
                c.execute('INSERT INTO agent_runs(id,agent_id,trigger,started_at) VALUES (?,?,?,?)', (rid, aid, how, _now()))
            token = _current.set(rid)
            status, error, result = 'complete', '', None
            try:
                if subject:
                    try:
                        t = subject(*args, **kwargs)
                        if t: note('read', t[0], t[1])
                    except Exception:
                        pass
                result = fn(*args, **kwargs)
                rs = result.get('status') if isinstance(result, dict) else None
                if rs == 'failed': status, error = 'failed', str(result.get('error') or result.get('message') or 'failed')[:500]
                elif rs == 'paused': status = 'skipped'
                return result
            except AgentBlocked:
                status = 'skipped'; raise
            except ValueError as e:
                # a rule stopped it (e.g. spending caps pause automations): not a failure of the agent
                status, error = ('blocked' if type(e).__name__ in ('RuleViolation', 'LocalModelHeld') else 'failed'), str(e)[:500]   # LocalModelHeld: the work waits (temple_model)
                raise
            except Exception as e:
                name = type(e).__name__
                import provider_errors      # the provider's own reason (status and message, no keys or content), not just the name
                reason = provider_errors.message(e, log=f'Agent {aid}') if provider_errors.is_provider_error(e) else name
                if name in TRANSIENT:            # provider or database briefly unavailable: not the agent's fault
                    status, error = 'blocked', ('Temporarily unavailable: ' + reason)[:500]
                else:
                    status, error = 'failed', (str(e) if isinstance(e, ValueError) else reason)[:500]
                raise
            finally:
                _current.reset(token)
                _finish(a, rid, status, error, result)
        return wrapper
    return deco


def _finish(a, rid, status, error, result):
    rs = result.get('status') if isinstance(result, dict) else None
    with store.db() as c:
        row = c.execute('SELECT cost_usd,calls FROM agent_runs WHERE id=?', (rid,)).fetchone()
        events = c.execute("SELECT count(*) FROM agent_events WHERE run_id=? AND kind<>'read'", (rid,)).fetchone()[0]
        idle = (rs in SKIP) or (isinstance(result, dict) and result.get('checked') == 0 and not row['calls'] and not events)
        if status == 'complete' and idle:        # nothing to do: no run worth keeping
            c.execute('DELETE FROM agent_events WHERE run_id=?', (rid,)); c.execute('DELETE FROM agent_runs WHERE id=?', (rid,))
            return
        c.execute('UPDATE agent_runs SET finished_at=?,status=?,error=?,summary=? WHERE id=?', (_now(), status, error, _summary(result), rid))
        streak = []
        for r in c.execute("SELECT status, ack_kind FROM agent_runs WHERE agent_id=? AND status NOT IN ('skipped','running','blocked') "
                           "ORDER BY started_at DESC LIMIT ?", (a['id'], FAIL_LIMIT)):
            if r[1] == 'fixed': break           # failures before a fix you recorded don't count towards pausing
            streak.append(r[0])
    if status == 'failed' and len(streak) == FAIL_LIMIT and all(s == 'failed' for s in streak):
        set_status(a['id'], 'paused', f'{FAIL_LIMIT} failed runs in a row; last error: {error[:120]}', by='Alice')


# ---------------- connected apps: every tool call ----------------
def app_for(label):
    """The registered app for a caller label, registering unknown apps on first use (you can pause them)."""
    aid = slug(label)
    with store.db() as c:
        if not c.execute('SELECT 1 FROM agents WHERE id=?', (aid,)).fetchone():
            perms = json.dumps(_default_perms('app'))
            c.execute('INSERT INTO agents(id,name,kind,purpose,trigger,reads,writes,external_content,permissions,created_at,updated_at,review_by) '
                      'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (aid, ' '.join(label.split())[:60], 'app', 'Registered automatically on first connection.',
                                                         'When you use it', 'As allowed to external apps', 'Proposals', 1, perms, _now(), _now(),
                                                         (date.today() + timedelta(days=365)).isoformat()))
            c.execute('INSERT INTO agent_versions VALUES (?,?,?,?,?,?)', (aid, 1, json.dumps({'permissions': json.loads(perms)}), _now(), 'Alice',
                                                                          'Registered on first connection'))
            store.audit(c, 'agent_registered', aid, 'automatic_safeguard', f'{label} connected for the first time')
    return get(aid)


def _day_run(aid):
    day = date.today().isoformat()
    with store.db() as c:
        r = c.execute("SELECT id FROM agent_runs WHERE agent_id=? AND day=?", (aid, day)).fetchone()
        if r: return r[0]
        rid = uuid.uuid4().hex
        c.execute("INSERT INTO agent_runs(id,agent_id,trigger,started_at,status,day) VALUES (?,?,?,?,?,?)",
                  (rid, aid, 'Tool calls on ' + day, _now(), 'running', day))
        return rid


def app_call(label, tool):
    """Before an app's tool call: refuse if paused/stopped, tool not allowed, read-only, or over today's call limit.
    Returns (agent, run_id) so the caller can record what the call touched."""
    a = app_for(label)
    if a['status'] != 'active':
        raise AgentBlocked(f'Alice access for {a["name"]} is {a["status"]}' + (f' ({a["status_reason"]})' if a['status_reason'] else '') +
                           '. The owner can resume it on the Agents page.')
    p = a['permissions']
    if p.get('tools') and tool not in p['tools']:
        raise AgentBlocked(f'{a["name"]} is not allowed to use {tool} (Agents page permissions).')
    if p.get('mode') == 'read' and tool in WRITE_TOOLS:
        raise AgentBlocked(f'{a["name"]} is read-only in Alice, so it cannot use {tool}.')
    rid = _day_run(a['id'])
    with store.db() as c:
        calls = c.execute('SELECT calls FROM agent_runs WHERE id=?', (rid,)).fetchone()[0]
        if p.get('max_calls_per_day') and calls >= p['max_calls_per_day']:
            raise AgentBlocked(f'{a["name"]} reached its limit of {p["max_calls_per_day"]} tool calls today (Agents page).')
        c.execute('UPDATE agent_runs SET calls=calls+1,finished_at=? WHERE id=?', (_now(), rid))
        c.execute('INSERT INTO agent_events(run_id,at,kind,target_type,target_id,detail) VALUES (?,?,?,?,?,?)', (rid, _now(), 'tool', '', '', tool))
    return a, rid


def app_note(rid, kind, target_type, ids, detail=''):
    if not rid: return
    ids = [i for i in (ids if isinstance(ids, (list, tuple, set)) else [ids]) if i][:100]
    with store.db() as c:
        for i in ids:
            c.execute('INSERT INTO agent_events(run_id,at,kind,target_type,target_id,detail) VALUES (?,?,?,?,?,?)',
                      (rid, _now(), kind, target_type, str(i)[:500], str(detail)[:500]))


def filter_records(a, records):
    """An app's own category limits, on top of the external rules."""
    cats = {x.lower() for x in (a['permissions'].get('categories') or [])}
    if not cats: return records, 0
    kept = [r for r in records if (r.get('category') or '').lower() in cats]
    return kept, len(records) - len(kept)


def label_allowed(a, label):
    labels = a['permissions'].get('labels') or []
    return not labels or label in labels


# ---------------- what needs your attention ----------------
ACK_KINDS = {'seen': 'Seen', 'fixed': 'Fixed', 'accepted': 'Accepted, no change needed'}


def failure_open(run):
    """A failed last run needs you until you acknowledge it (seen, fixed or accepted)."""
    return bool(run) and run.get('status') == 'failed' and not run.get('ack_at')


def acknowledge(aid, kind, note='', run_id='', decision=False):
    """Clear a failure once you have seen, fixed or accepted it, with an optional note. Without a run id, every failed run
    of this agent not yet acknowledged is covered. The run keeps its 'failed' outcome (history stays true); the note is kept
    on the run and in the activity log. With decision=True the note is also proposed as a decision (waits in Memories)."""
    if kind not in ACK_KINDS: raise ValueError('Choose seen, fixed or accepted.')
    a = get(aid)
    note = ' '.join((note or '').split())[:500]
    if note:
        import rules_engine
        if rules_engine.find_secrets(note): raise ValueError('The note looks like it contains a key or password. Leave that out.')
    if decision and len(note) < 8: raise ValueError('Write the decision in the note (what you decided), then save.')
    q, args = "SELECT id, started_at, error FROM agent_runs WHERE agent_id=? AND status='failed' AND ack_at IS NULL", [aid]
    if run_id: q += ' AND id=?'; args.append(run_id)
    with store.db() as c:
        rows = [dict(r) for r in c.execute(q + ' ORDER BY started_at', args)]
    if not rows: raise ValueError('There is no unacknowledged failure to clear.' if not run_id else 'That run is not an unacknowledged failure.')
    out = {'acknowledged': len(rows), 'kind': kind}
    if decision:          # first, so a decision the rules refuse leaves the failure as it was
        last = rows[-1]
        r = store.propose_decision(f'{a["name"]}: failed run {ACK_KINDS[kind].lower()}', note,
                                   f'Agents page, {a["name"]} run {last["id"]} ({last["started_at"][:10]}); error: {(last["error"] or "")[:160]}')
        out['decision'] = r.get('id')
    at = _now()
    with store.db() as c:
        for r in rows:
            c.execute('UPDATE agent_runs SET ack_at=?, ack_kind=?, ack_note=? WHERE id=? AND ack_at IS NULL', (at, kind, note, r['id']))
        store.audit(c, 'agent_failure_' + kind, aid, 'human_review',
                    f'{a["name"]}: {len(rows)} failed run{"s" if len(rows) != 1 else ""} marked {ACK_KINDS[kind].lower()}' + (f' ({note})' if note else ''))
    return out


def alerts():
    out = []
    for a in listing()['agents']:
        if a['status'] == 'paused' and a['status_reason'] and a['status_reason'] != 'by you':
            out.append({'id': a['id'], 'title': a['name'] + ' paused itself', 'detail': a['status_reason']})
        elif a['failure_open'] and a['status'] == 'active':
            out.append({'id': a['id'], 'title': a['name'] + ': last run failed', 'detail': (a['last_run'].get('error') or 'Failed.')[:200] + ' · Acknowledge it on the agent\'s page once seen or fixed.'})
        elif a['review_overdue'] and a['status'] != 'stopped':
            out.append({'id': a['id'], 'title': a['name'] + ': review its access', 'detail': 'Review-by date ' + a['review_by'] + ' has passed.'})
    return out
