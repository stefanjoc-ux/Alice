"""Rule sets for AI Substrate.

Ranked Security > Organisation > Memory governance > Cost > Personal. Each rule is either
ENFORCED (checked in Python at the points where data moves; no model can bypass it) or
GUIDANCE (compiled into the instructions models receive; advisory by nature).
Findings never echo the sensitive value itself.
"""
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
import substrate_store as store

SETS = [
    ('security', 'Security', 'Highest precedence. Protects credentials, classified material and personal data.'),
    ('organisation', 'Organisation', 'Insight and client obligations you apply to your own work.'),
    ('memory', 'Memory governance', 'How knowledge gets in and stays trustworthy.'),
    ('cost', 'Cost', 'Spending limits for every model call the substrate makes.'),
    ('personal', 'Personal', 'How you want answers written.'),
]
RANK = {k: i for i, (k, _, _) in enumerate(SETS)}
PROVIDERS = ['openai', 'claude', 'grok', 'copilot']   # copilot: Microsoft 365 Copilot via the external endpoint

# id, set, name, kind, description, default enabled, default params, guidance text, locked
BUILTIN = [
    ('secret_detection', 'security', 'Secret detection', 'enforced',
     'Blocks API keys, passwords, private keys, tokens and connection strings from chat messages sent to models, '
     'memories, knowledge notes and uploads.', True, {}, '', False),
    ('protective_marking', 'security', 'Protective marking guard', 'enforced',
     'Refuses to send material marked OFFICIAL-SENSITIVE, SECRET or TOP SECRET to any external model. Marked uploads '
     'are refused; previously saved marked files are withheld from every tool.', True,
     {'markings': ['OFFICIAL-SENSITIVE', 'SECRET', 'TOP SECRET']}, '', False),
    ('provider_allow', 'security', 'Provider allow-list by category', 'enforced',
     'Memories in a category, and knowledge with a security label, are never sent to the providers you block for them.', True,
     {'blocked': {'Work': ['grok']}, 'labels': {'internal': ['grok']}}, '', False),
    ('external_scope', 'security', 'External client scope', 'enforced',
     'Claude Desktop and Claude Code can only read memories in these categories. Empty means all categories.',
     True, {'allowed_categories': []}, '', False),
    ('pii', 'security', 'Personal identifiers', 'enforced',
     'Blocks payment card numbers, National Insurance numbers, UK sort code with account number, and IBANs '
     'from memories and knowledge notes.', True, {}, '', False),
    ('data_minimisation', 'security', 'Data minimisation', 'enforced',
     'Organisation facts hold organisational information and roles, not people: email addresses and phone numbers '
     'are refused (keep contact details in the source system), as is anything about a named person\'s health, '
     'beliefs, ethnicity, sexuality, union membership or criminal matters. Every organisation fact needs a source '
     'and a review-by date (default below, at most 24 months).', True, {'review_months': 12}, '', False),
    ('client_separation', 'organisation', 'Client separation', 'enforced',
     'In a chat tagged with a client, memory and file tools return only that client\'s material plus General '
     '(untagged) material. Strict mode also keeps client material out of untagged chats.', True,
     {'strict': False, 'external': 'all'}, '', False),
    ('client_documents', 'organisation', 'Client-facing documents use only that client\'s material', 'enforced',
     'Proposals written by Parker and digital team outputs marked client-facing use only General (untagged) material and material '
     'tagged to that document\'s own client; anything tagged to another client is left out and logged. A document with no client uses '
     'General material only. Works on its own, whatever the Client separation switch says.', True, {}, '', False),
    ('commercial_caution', 'organisation', 'Commercial caution', 'guidance', '', True, {},
     'Do not state prices, discounts, rates or Insight commitments unless they come from a saved file or approved '
     'memory, and cite that source.', False),
    ('ai_disclosure', 'organisation', 'AI disclosure', 'guidance', '', True, {},
     'When drafting material that will go to a client, remind me once that AI assisted so I can declare it if required.',
     False),
    ('retention', 'organisation', 'Chat retention', 'enforced',
     'Permanently deletes saved chats that had nothing captured once they are older than the set number of months. '
     'Chats with captured memories or knowledge are kept. Off by default because deletion cannot be undone.',
     False, {'months': 12}, '', False),
    ('approval_required', 'memory', 'Human approval', 'enforced',
     'Every new memory is a proposal until you approve it. Models and Temple can never approve, overwrite or delete.',
     True, {}, '', True),
    ('quality', 'memory', 'Quality check', 'enforced',
     'Rejects proposals whose content only repeats the title, is shorter than the minimum, or whose source is '
     'missing or just repeats the content.', True, {'min_chars': 12}, '', False),
    ('duplicates', 'memory', 'Duplicate block', 'enforced',
     'Rejects proposals that closely match an active memory.', True, {'threshold': 0.9}, '', False),
    ('expiry', 'memory', 'Review-by dates', 'enforced',
     'Memories past their review-by date are marked as possibly out of date whenever a model reads them, and '
     'flagged on the Memories page.', True, {}, '', False),
    ('spend_cap', 'cost', 'Spending caps', 'enforced',
     'Temple automations pause at the warning level; chat is blocked at the cap. Based on estimated spend; '
     'unpriced calls (voice) are not counted.', True, {'daily_usd': 5.0, 'monthly_usd': 50.0, 'warn_percent': 80}, '',
     False),
    ('opus_manual', 'cost', 'Opus only when chosen', 'enforced',
     'Auto routing never selects Opus 5.5; it runs only when you pick it.', True, {}, '', True),
    ('working_style', 'personal', 'Working style', 'guidance', '', True, {},
     'Give direct, honest pushback rather than validation. Skip unnecessary caveats, repeated disclaimers and '
     'unsolicited commentary on my decisions.', False),
    ('uk_conventions', 'personal', 'UK conventions', 'guidance', '', True, {},
     'Use UK English spelling and show amounts in GBP unless I ask otherwise.', False),
]


class RuleViolation(ValueError):
    """Raised when an enforced rule blocks an action. The message is safe to show the user."""


def _init():
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY, set_key TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL,
            params TEXT NOT NULL DEFAULT '{}', builtin INTEGER NOT NULL DEFAULT 0, locked INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        for rid, set_key, name, kind, desc, enabled, params, text, locked in BUILTIN:
            # INSERT OR IGNORE keeps your changes; descriptions refresh with each update.
            c.execute('INSERT OR IGNORE INTO rules VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?)',
                      (rid, set_key, name, kind, desc, text, int(enabled), json.dumps(params), int(locked), '',
                       store.now(), store.now()))
            c.execute('UPDATE rules SET description=?,locked=? WHERE id=? AND builtin=1', (desc, int(locked), rid))
        # Client separation started as guidance; it is enforced now that clients can be tagged.
        c.execute("UPDATE rules SET kind='enforced',text='',params=? WHERE id='client_separation' AND kind='guidance'",
                  (json.dumps({'strict': False, 'external': 'all'}),))
        cols = {r['name'] for r in c.execute('PRAGMA table_info(record_meta)')}
        if 'review_by' not in cols: c.execute('ALTER TABLE record_meta ADD COLUMN review_by TEXT')


_init()


# ---------------- rule access ----------------
def _load_rules():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM rules')]
    for r in rows:
        r['params'] = json.loads(r['params'] or '{}'); r['enabled'] = bool(r['enabled'])
        r['builtin'] = bool(r['builtin']); r['locked'] = bool(r['locked'])
    return sorted(rows, key=lambda r: (RANK.get(r['set_key'], 99), not r['builtin'], r['created_at'], r['name']))


def all_rules():
    """Every rule. Loaded once per web request (speed.memo; one page asks for them dozens of times) and handed out as copies,
    so nothing a caller changes leaks into the next caller; any change to the rules clears it (_rules_changed)."""
    import copy, speed
    return copy.deepcopy(speed.memo('rules', _load_rules))


def _rules_changed():
    import speed
    speed.forget('rules')


def rule(rid):
    return next((r for r in all_rules() if r['id'] == rid), None)


def on(rid):
    r = rule(rid)
    return bool(r and r['enabled'])


def params(rid):
    r = rule(rid)
    return r['params'] if r else {}


def log_block(rid, target, detail):
    with store.db() as c:
        store.audit(c, 'rule_blocked', target[:200], rid, detail[:500])


def update_rule(rid, enabled=None, new_params=None, text=None, name=None):
    r = rule(rid)
    if not r: raise ValueError('Rule not found.')
    if r['locked'] and enabled is False: raise ValueError(f'"{r["name"]}" is a core safeguard and cannot be switched off.')
    fields, args = [], []
    if enabled is not None: fields.append('enabled=?'); args.append(int(enabled))
    if new_params is not None: fields.append('params=?'); args.append(json.dumps(_clean_params(rid, new_params)))
    if text is not None:
        if r['kind'] != 'guidance': raise ValueError('Only guidance rules have editable text.')
        text = text.strip()
        if not text or len(text) > 1000: raise ValueError('Guidance text must be 1 to 1,000 characters.')
        fields.append('text=?'); args.append(text)
    if name is not None and not r['builtin']:
        name = ' '.join(name.split())[:60]
        if not name: raise ValueError('Enter a rule name.')
        fields.append('name=?'); args.append(name)
    if not fields: return rule(rid)
    with store.db() as c:
        c.execute(f"UPDATE rules SET {','.join(fields)},updated_at=? WHERE id=?", args + [store.now(), rid])
        store.audit(c, 'rule_updated', rid, 'human_control', ', '.join(f.split('=')[0] for f in fields))
    _rules_changed()
    return rule(rid)


def _clean_params(rid, p):
    if rid == 'spend_cap':
        out = {}
        for k, lo, hi in (('daily_usd', 0.1, 1000), ('monthly_usd', 1, 10000), ('warn_percent', 10, 99)):
            v = float(p.get(k, 0))
            if not lo <= v <= hi: raise ValueError(f'{k.replace("_", " ")} must be between {lo:g} and {hi:g}.')
            out[k] = round(v, 2)
        if out['daily_usd'] > out['monthly_usd']: raise ValueError('The daily cap cannot exceed the monthly cap.')
        return out
    if rid == 'retention':
        m = int(p.get('months', 12))
        if not 1 <= m <= 120: raise ValueError('Months must be between 1 and 120.')
        return {'months': m}
    if rid == 'quality':
        return {'min_chars': max(1, min(200, int(p.get('min_chars', 12))))}
    if rid == 'duplicates':
        t = float(p.get('threshold', 0.9))
        if not 0.5 <= t <= 1: raise ValueError('Threshold must be between 0.5 and 1.')
        return {'threshold': t}
    if rid == 'protective_marking':
        marks = [' '.join(str(m).split()).upper() for m in p.get('markings', []) if str(m).strip()][:20]
        if not marks: raise ValueError('Keep at least one marking.')
        return {'markings': marks}
    if rid == 'provider_allow':
        blocked = {}
        for cat, provs in (p.get('blocked') or {}).items():
            provs = [x for x in provs if x in PROVIDERS]
            if str(cat).strip() and provs: blocked[str(cat).strip()] = provs
        labels = {}
        for lab, provs in (p.get('labels') or {}).items():
            provs = [x for x in provs if x in PROVIDERS]
            if lab in ('general', 'internal', 'client') and provs: labels[lab] = provs
        return {'blocked': blocked, 'labels': labels}
    if rid == 'client_separation':
        ext = p.get('external', 'all')
        return {'strict': bool(p.get('strict', False)), 'external': ext if ext in ('all', 'general') else 'all'}
    if rid == 'data_minimisation':
        try: months = int(p.get('review_months', 12))
        except (TypeError, ValueError): months = 12
        return {'review_months': max(1, min(24, months))}
    if rid == 'external_scope':
        return {'allowed_categories': [str(x).strip() for x in p.get('allowed_categories', []) if str(x).strip()][:50]}
    return {}


def create_guidance(set_key, name, text, source=''):
    if set_key not in RANK: raise ValueError('Unknown rule set.')
    name, text = ' '.join((name or '').split())[:60], (text or '').strip()
    if not name or not text or len(text) > 1000: raise ValueError('Enter a name and guidance of up to 1,000 characters.')
    import uuid
    rid = 'custom_' + uuid.uuid4().hex[:10]
    with store.db() as c:
        c.execute('INSERT INTO rules VALUES (?,?,?,?,?,?,1,?,0,0,?,?,?)',
                  (rid, set_key, name, 'guidance', '', text, '{}', source, store.now(), store.now()))
        store.audit(c, 'rule_created', rid, 'human_control', f'{set_key}: {name}')
    _rules_changed()
    return rule(rid)


def delete_rule(rid):
    r = rule(rid)
    if not r: raise ValueError('Rule not found.')
    if r['builtin']: raise ValueError('Built-in rules can be switched off but not deleted.')
    with store.db() as c:
        c.execute('DELETE FROM rules WHERE id=?', (rid,))
        store.audit(c, 'rule_deleted', rid, 'human_control', r['name'])
    _rules_changed()
    return {'deleted': rid}


def effective_guidance(free_text):
    """Guidance rules in precedence order, then your free-text guidance."""
    parts = []
    for r in all_rules():
        if r['kind'] == 'guidance' and r['enabled'] and r['text']:
            parts.append(f"- [{dict((k, n) for k, n, _ in SETS)[r['set_key']]}] {r['text']}")
    try:
        import rule_packs
        parts += rule_packs.live_guidance()
    except Exception:
        pass
    if free_text.strip(): parts.append(free_text.strip())
    return '\n'.join(parts)


# ---------------- detectors (never return the matched value) ----------------
SECRET_PATTERNS = [
    ('Anthropic API key', r'\bsk-ant-[A-Za-z0-9_\-]{20,}'),
    ('OpenAI API key', r'\bsk-(?!ant-)(?:proj-|svcacct-)?[A-Za-z0-9_\-]{32,}'),
    ('xAI API key', r'\bxai-[A-Za-z0-9]{32,}'),
    ('ElevenLabs API key', r'\bsk_[a-f0-9]{40,}\b'),
    ('AWS access key', r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    ('GitHub token', r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}'),
    ('Slack token', r'\bxox[abposr]-[A-Za-z0-9\-]{10,}'),
    ('Private key', r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    ('JSON Web Token', r'\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'),
    ('Azure storage key', r'AccountKey=[A-Za-z0-9+/=]{40,}'),
    ('Connection string with password', r'(?i)\b(?:password|pwd)\s*=\s*[^;\s]{4,}\s*;'),
    ('Password', r'(?i)\b(?:password|passwd|passcode|pwd)\s*[:=]\s*\S{6,}'),
    ('API key assignment', r'(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*["\']?[A-Za-z0-9_\-/+]{16,}'),
]


def find_secrets(text):
    return sorted({name for name, pat in SECRET_PATTERNS if re.search(pat, text or '')})


def find_markings(text):
    """UK protective markings as they appear on documents: upper case, as a marking, not ordinary prose."""
    found = set()
    for mark in params('protective_marking').get('markings', []):
        m = re.escape(mark).replace(r'\-', r'[-\s]').replace(r'\ ', r'[-\s]')
        if mark in ('SECRET', 'TOP SECRET'):
            # Standalone marking line, or with a UK caveat, to avoid matching "SECRET_KEY" or shouted prose.
            pat = rf'(?m)^\s*(?:{m})(?:\s+UK\s+EYES\s+ONLY)?\s*$|\b{m}\s+UK\s+EYES\s+ONLY\b'
            if mark == 'SECRET': pat = rf'(?m)^\s*(?<!TOP )SECRET(?:\s+UK\s+EYES\s+ONLY)?\s*$|(?<!TOP )\bSECRET\s+UK\s+EYES\s+ONLY\b'
        else:
            pat = rf'\b{m}\b'
        if re.search(pat, text or ''): found.add(mark)
    return sorted(found)


def _luhn(digits):
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n *= 2
            if n > 9: n -= 9
        total += n; alt = not alt
    return total % 10 == 0


def find_pii(text):
    text = text or ''
    found = set()
    for m in re.finditer(r'\b(?:\d[ -]?){13,19}\b', text):
        digits = re.sub(r'\D', '', m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits) and len(set(digits)) > 1: found.add('Payment card number')
    if re.search(r'\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b', text):
        found.add('National Insurance number')
    if re.search(r'\b\d{2}-\d{2}-\d{2}\b[^\n]{0,30}?\b\d{8}\b|\b\d{8}\b[^\n]{0,30}?\b\d{2}-\d{2}-\d{2}\b', text) \
            and re.search(r'(?i)sort\s*code|account|a/c|acc\b', text):
        found.add('Sort code and account number')
    if re.search(r'\bGB\d{2}\s?[A-Z]{4}(?:\s?\d{4}){3}\s?\d{2}\b', text): found.add('IBAN')
    return sorted(found)


EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PHONE = re.compile(r'(?<![\w.])(?:\+44\s?\(?0?\)?\s?|\(?0)(?:\d[\s-]?){9,10}\b')
SPECIAL = re.compile(r'\b(diagnos\w*|illness|ill health|sick(?:ness)? leave|medical|medication|disab\w*|pregnan\w*|maternity|'
                     r'mental health|religio\w*|faith|ethnic\w*|race|sexual\w*|gay|lesbian|bisexual|transgender|'
                     r'trade union member\w*|union member\w*|criminal|convict\w*|arrest\w*|offen[cs]e\w*|political (?:views|beliefs))\b', re.I)
PERSON = re.compile(r'\b(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Cllr|Councillor|Sir|Dame)\.?\s+[A-Z][a-z]+|\b(?:he|she|his|her|him|hers)\b', re.I)


def find_personal(text):
    """Data minimisation: contact details, or special-category detail about a person (in the same sentence).
    Organisational wording ("mental health services", "disability access") is not flagged."""
    text = text or ''
    found = []
    if EMAIL.search(text): found.append('an email address')
    if PHONE.search(text): found.append('a phone number')
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+', text):
        if SPECIAL.search(sentence) and PERSON.search(sentence):
            found.append('personal details about someone (special category data)'); break
    return found


def check_org_fact(org, statement, source):
    """Organisation facts: secrets, markings, personal identifiers and data minimisation."""
    blob = f'{org}\n{statement}\n{source}'
    check_knowledge(org, f'{statement}\n{source}')
    if on('data_minimisation'):
        p = find_personal(blob)
        if p:
            log_block('data_minimisation', org, 'organisation fact blocked: ' + ', '.join(p))
            raise RuleViolation(f'Blocked by Data minimisation: this appears to contain {p[0]}. Organisation facts hold '
                                'organisational information and roles; keep personal details in the source system.')


# ---------------- enforcement points ----------------
def check_outbound(text, target='chat message', provider=None, packs=True):
    """Before text goes to any external model. Applied rule packs add their blocks and escalations (packs=False for
    paths that check packs separately, such as chat, or that do not send anything yet, such as uploads)."""
    if on('secret_detection'):
        s = find_secrets(text)
        if s:
            log_block('secret_detection', target, 'Blocked: ' + ', '.join(s))
            article = 'an' if s[0][0].upper() in 'AEIOU' else 'a'
            raise RuleViolation(f'Not sent: this looks like it contains {article} {s[0]}. Secret detection stops '
                                'credentials reaching any model. Remove it (and rotate it if it was real).')
    if on('protective_marking'):
        m = find_markings(text)
        if m:
            log_block('protective_marking', target, 'Blocked marking: ' + ', '.join(m))
            raise RuleViolation(f'Not sent: this contains a {m[0]} protective marking. Marked material is never sent '
                                'to external models.')
    if packs:
        import rule_packs
        if rule_packs.applied():
            if provider is None:
                with store.db() as c:
                    row = c.execute("SELECT value FROM settings WHERE key='temple_provider'").fetchone()
                provider = row[0] if row else 'openai'
            rule_packs.live_check(text, provider, target, redact_text=False)


def check_file(text, name):
    check_outbound(text, 'upload ' + name, packs=False)


def _norm(s):
    return re.sub(r'[^a-z0-9 ]', '', ' '.join((s or '').lower().split()))


def check_record(title, content, source, exclude_id=None, stage='proposal'):
    """Every route to a memory passes through here: proposals and approvals."""
    blob = f'{title}\n{content}\n{source}'
    if on('secret_detection') and find_secrets(blob):
        log_block('secret_detection', title, f'{stage} blocked')
        raise RuleViolation('Blocked by Secret detection: this memory appears to contain a credential.')
    if on('protective_marking') and find_markings(blob):
        log_block('protective_marking', title, f'{stage} blocked')
        raise RuleViolation('Blocked by the Protective marking guard: marked material cannot become a memory.')
    if on('pii'):
        p = find_pii(blob)
        if p:
            log_block('pii', title, f'{stage} blocked: ' + ', '.join(p))
            raise RuleViolation(f'Blocked by Personal identifiers: this memory appears to contain a {p[0].lower()}.')
    if on('quality'):
        n_title, n_content, n_source = _norm(title), _norm(content), _norm(source)
        min_chars = params('quality').get('min_chars', 12)
        problem = ('the content only repeats the title' if n_content == n_title or n_content in n_title else
                   f'the content is shorter than {min_chars} characters' if len(content.strip()) < min_chars else
                   'the source is missing or only repeats the content' if not n_source or n_source in (n_content, n_title) else '')
        if problem:
            log_block('quality', title, f'{stage} blocked: {problem}')
            raise RuleViolation(f'Blocked by the Quality check: {problem}. State the fact itself and where it came from.')
    if on('duplicates') and stage == 'proposal':
        threshold = params('duplicates').get('threshold', 0.9)
        target = _norm(title + ' ' + content)
        with store.db() as c:   # read everything first; logging while a read is open would lock the database
            rows = c.execute("SELECT r.id,r.title,r.content FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id "
                             "WHERE coalesce(a.state,r.status) IN ('approved','proposed') AND r.id<>?", (exclude_id or '',)).fetchall()
        for r in rows:
            if SequenceMatcher(None, target, _norm(r['title'] + ' ' + r['content'])).ratio() >= threshold:
                log_block('duplicates', title, f'duplicate of {r["id"]}')
                raise RuleViolation(f'Blocked by the Duplicate block: this closely matches "{r["title"]}". '
                                    'Replace that memory instead if this is an update.')


def filter_tool_output(output, provider):
    """search_records results in web chat: apply the provider allow-list before the model sees them."""
    try: blocks = json.loads(output)
    except ValueError: return output
    for b in blocks:
        if b.get('type') != 'text': continue
        try: data = json.loads(b['text'])
        except (ValueError, TypeError): continue
        if isinstance(data, dict) and isinstance(data.get('records'), list):
            kept, n = filter_records_for_provider(data['records'], provider)
            if n:
                data['records'] = kept
                data['withheld_by_rule'] = f'{n} memories withheld from this provider by the Provider allow-list rule.'
                log_block('provider_allow', provider, f'{n} memories withheld')
            b['text'] = json.dumps(data, ensure_ascii=False)
    return json.dumps(blocks, ensure_ascii=False)


def file_blocked(text):
    """Reason a saved file must not reach any model, or ''."""
    if on('protective_marking') and find_markings(text): return 'Withheld by the Protective marking guard.'
    if on('secret_detection') and find_secrets(text): return 'Withheld by Secret detection: the file appears to contain credentials.'
    return ''


def check_knowledge(title, text):
    """Notes, meeting extracts and model-proposed knowledge: secrets, markings and personal identifiers."""
    blob = f'{title}\n{text}'
    if on('secret_detection') and find_secrets(blob):
        log_block('secret_detection', title, 'knowledge blocked')
        raise RuleViolation('Blocked by Secret detection: this appears to contain a credential.')
    if on('protective_marking') and find_markings(blob):
        log_block('protective_marking', title, 'knowledge blocked')
        raise RuleViolation('Blocked by the Protective marking guard: marked material cannot be saved as knowledge.')
    if on('pii'):
        p = find_pii(blob)
        if p:
            log_block('pii', title, 'knowledge blocked: ' + ', '.join(p))
            raise RuleViolation(f'Blocked by Personal identifiers: this appears to contain a {p[0].lower()}.')


def filter_records_for_provider(records, provider):
    """Provider allow-list by category (web chat). Returns (kept, withheld_count)."""
    if not on('provider_allow'): return records, 0
    blocked = {k.lower(): v for k, v in params('provider_allow').get('blocked', {}).items()}
    kept = [r for r in records if provider not in blocked.get((r.get('category') or '').lower(), [])]
    return kept, len(records) - len(kept)


def filter_records_for_external(records):
    if not on('external_scope'): return records, 0
    allowed = {c.lower() for c in params('external_scope').get('allowed_categories', [])}
    if not allowed: return records, 0
    kept = [r for r in records if (r.get('category') or '').lower() in allowed]
    return kept, len(records) - len(kept)


def annotate_records(records):
    """Adds category and review-by status to records returned to models."""
    if not records: return records
    ids = [r['id'] for r in records]
    with store.db() as c:
        meta = {r['record_id']: dict(r) for r in c.execute(
            f"SELECT record_id,category,review_by FROM record_meta WHERE record_id IN ({','.join('?' * len(ids))})", ids)}
    today = datetime.now(timezone.utc).date().isoformat()
    for r in records:
        m = meta.get(r['id'], {})
        r['category'] = m.get('category') or ''
        if m.get('review_by'):
            r['review_by'] = m['review_by']
            if on('expiry') and m['review_by'] < today:
                r['possibly_out_of_date'] = True
                r['note'] = f'Review-by date {m["review_by"]} has passed; confirm before relying on this.'
    return records


def set_review_by(rid, date):
    date = (date or '').strip()
    if date and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date): raise ValueError('Use a date like 2026-12-31.')
    with store.db() as c:
        if not c.execute('SELECT 1 FROM records WHERE id=?', (rid,)).fetchone(): raise ValueError('Memory not found.')
        c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (rid,))
        c.execute('UPDATE record_meta SET review_by=? WHERE record_id=?', (date or None, rid))
        store.audit(c, 'review_by_set', rid, 'human_review', date or 'cleared')
    return {'review_by': date}


# ---------------- spending ----------------
def spend_status():
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    with store.db() as c:
        today = c.execute('SELECT coalesce(sum(estimate_usd),0) FROM model_usage WHERE created_at>=?', (day,)).fetchone()[0]
        mtd = c.execute('SELECT coalesce(sum(estimate_usd),0) FROM model_usage WHERE created_at>=?', (month,)).fetchone()[0]
    p = params('spend_cap') or {'daily_usd': 5, 'monthly_usd': 50, 'warn_percent': 80}
    frac = max(today / p['daily_usd'], mtd / p['monthly_usd'])
    level = 'off' if not on('spend_cap') else 'blocked' if frac >= 1 else 'warning' if frac * 100 >= p['warn_percent'] else 'ok'
    return {'today_usd': round(today, 4), 'month_usd': round(mtd, 4), 'daily_usd': p['daily_usd'],
            'monthly_usd': p['monthly_usd'], 'warn_percent': p['warn_percent'], 'level': level}


def check_spend(kind):
    """kind: 'chat' (blocked at the cap) or 'automation' (Temple features; paused from the warning level)."""
    s = spend_status()
    if s['level'] == 'blocked' or (kind == 'automation' and s['level'] == 'warning'):
        what = 'Chat' if kind == 'chat' else 'Temple automations'
        log_block('spend_cap', kind, f"today ${s['today_usd']:.2f}, month ${s['month_usd']:.2f}")
        raise RuleViolation(f"{what} paused by Spending caps: ${s['today_usd']:.2f} today of ${s['daily_usd']:.2f}, "
                            f"${s['month_usd']:.2f} this month of ${s['monthly_usd']:.2f}. Raise the cap in Rules to continue.")
    return s


# ---------------- retention ----------------
def run_retention():
    if not on('retention'): return {'status': 'off'}
    from datetime import timedelta
    months = params('retention').get('months', 12)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30 * months)).isoformat()
    deleted = []
    for chat in store.archived_chats(limit=100000)['chats']:
        if chat.get('source', 'alice') != 'alice' and not (chat.get('review') and chat['review']['status'] == 'complete'):
            continue   # saved or imported conversations are kept until Temple has had a chance to review them
        try:
            with store.db() as c:
                undecided = c.execute("SELECT count(*) FROM temple_suggestions WHERE chat_id=? AND status IN ('pending','later')",
                                      (chat['id'],)).fetchone()[0]
        except Exception:
            undecided = 0
        if undecided: continue   # Temple suggestions you haven't decided on yet keep the chat
        if chat['updated_at'] < cutoff and not chat['captured']:
            try:
                store.delete_chat(chat['id']); deleted.append(chat['id'])
                try:
                    import temple_chat; temple_chat.cleanup(chat['id'])
                except Exception: pass
                with store.db() as c: c.execute('DELETE FROM chat_files WHERE chat_id=?', (chat['id'],))
            except Exception:
                continue
    if deleted:
        with store.db() as c: store.audit(c, 'retention_deleted', f'{len(deleted)} chats', 'retention', f'older than {months} months, nothing captured')
    return {'status': 'complete', 'deleted': len(deleted)}


# ---------------- overview for the Rules page ----------------
def rule_requests():
    try:
        with store.db() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT s.id,s.title,s.content,s.created_at,s.status,coalesce(ch.title,'') AS chat_title FROM temple_suggestions s "
                "LEFT JOIN chats ch ON ch.id=s.chat_id WHERE s.kind='rule_request' AND s.status IN ('accepted','pending','later') "
                "ORDER BY s.created_at DESC")]
            used = {r[0] for r in c.execute("SELECT source FROM rules WHERE source<>''")}
    except Exception:
        return []
    return [r for r in rows if r['id'] not in used]


def recent_blocks(limit=15):
    with store.db() as c:
        return [dict(r) for r in c.execute("SELECT created_at,target,rule,detail FROM activity WHERE action='rule_blocked' "
                                           'ORDER BY id DESC LIMIT ?', (limit,))]


def overview():
    base = store.rules_base()
    rules = all_rules()
    return {'sets': [{'key': k, 'name': n, 'description': d} for k, n, d in SETS], 'rules': rules,
            'guidance': base['guidance'], 'allow_proposals': base['allow_proposals'],
            'effective_guidance': effective_guidance(base['guidance']), 'spend': spend_status(),
            'requests': rule_requests(), 'blocks': recent_blocks(),
            'categories': [c['name'] for c in store.list_categories()['categories']], 'providers': PROVIDERS,
            'counts': {'enforced': sum(1 for r in rules if r['enabled'] and r['kind'] == 'enforced'),
                       'guidance': sum(1 for r in rules if r['enabled'] and r['kind'] == 'guidance')}}
