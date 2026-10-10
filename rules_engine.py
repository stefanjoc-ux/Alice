"""Rule sets for AI Substrate.

Ranked Security > Organisation > Memory governance > Cost > Personal. Each rule is either
ENFORCED (checked in Python at the points where data moves; no model can bypass it) or
GUIDANCE (compiled into the instructions models receive; advisory by nature).
Findings never echo the sensitive value itself.
"""
import contextvars
import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from difflib import SequenceMatcher
import substrate_store as store

SETS = [
    ('security', 'Security', 'Highest precedence. Protects credentials, classified material and personal data.'),
    ('organisation', 'Organisation', 'Obligations to your organisation and its clients that you apply to your own work.'),
    ('memory', 'Memory governance', 'How knowledge gets in and stays trustworthy.'),
    ('cost', 'Cost', 'Spending limits for every model call the substrate makes.'),
    ('personal', 'Personal', 'How you want answers written.'),
]
RANK = {k: i for i, (k, _, _) in enumerate(SETS)}
PROVIDERS = ['openai', 'claude', 'grok', 'copilot']   # copilot: Microsoft 365 Copilot via the external endpoint

# The shipped defaults live in config/rule-defaults.json, not in code (decision D-0045: no rule is hard-coded). A deployment
# sets its own defaults in a file of the same shape: ALICE_RULE_DEFAULTS (a path), else rule-defaults.json in the data folder. Only the
# rules and fields it names change; params merge into the shipped ones. Defaults apply when a rule is first created; the wording and
# whether a rule is Core apply at every start. What anyone changes on the Rules page is kept, and logged (rule_changes).
SHIPPED_DEFAULTS = Path(__file__).resolve().with_name('config') / 'rule-defaults.json'
DEFAULTS_ERROR = ''
_log = logging.getLogger('alice.rules')


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def deployment_defaults_path():
    p = os.environ.get('ALICE_RULE_DEFAULTS', '').strip()
    if p: return Path(p)
    return store.DB.parent / 'rule-defaults.json'


def _deployment_overrides():
    """{rule id: {enabled, params, text, core}} from this deployment's own defaults file (none: {})."""
    global DEFAULTS_ERROR
    path = deployment_defaults_path()
    if not path.is_file(): return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        rules_in = data.get('rules', data) if isinstance(data, dict) else data
        if isinstance(rules_in, list): rules_in = {r['id']: r for r in rules_in if isinstance(r, dict) and r.get('id')}
        if not isinstance(rules_in, dict): raise ValueError('expected {"rules": {rule id: {...}}}')
        return {k: v for k, v in rules_in.items() if isinstance(v, dict) and not k.startswith('_')}
    except (OSError, ValueError, KeyError, TypeError) as e:
        DEFAULTS_ERROR = f'This deployment\'s rule defaults ({path.name}) could not be read, so the shipped defaults apply: {str(e)[:200]}'
        _log.warning(DEFAULTS_ERROR)
        return {}


def defaults():
    """Every built-in rule as shipped, with this deployment's defaults applied: [{id, set, name, kind, description, text, enabled,
    params, core}]."""
    shipped = json.loads(SHIPPED_DEFAULTS.read_text(encoding='utf-8'))['rules']
    over = _deployment_overrides()
    # Test databases (tests/_util.py) start with these off, as a deployment's defaults would set them.
    env = {'open_spaces': {'enabled': False} if os.environ.get('ALICE_OPEN_SPACES_DEFAULT') == 'off' else {},
           'temple_router': {'enabled': False} if os.environ.get('ALICE_ROUTER_DEFAULT') == 'off' else {},
           'approval_required': {'params': {'approver': 'person'}} if os.environ.get('ALICE_AUTO_APPROVE_DEFAULT') == 'off' else {}}
    out = []
    for d in shipped:
        d = {'description': '', 'text': '', 'params': {}, 'core': False, **d}
        for extra in (env.get(d['id']) or {}, over.get(d['id']) or {}):
            for k in ('enabled', 'core'):
                if k in extra: d[k] = bool(extra[k])
            if isinstance(extra.get('text'), str) and extra['text'].strip() and d['kind'] == 'guidance': d['text'] = extra['text'].strip()[:1000]
            if isinstance(extra.get('params'), dict): d['params'] = _merge(d['params'], extra['params'])
        out.append(d)
    return out


# id, set, name, kind, description, default enabled, default params, guidance text, core (read from the defaults above)
BUILTIN = [(d['id'], d['set'], d['name'], d['kind'], d['description'], d['enabled'], d['params'], d['text'], d['core']) for d in defaults()]


# Where a digital team's rates may come from (rule rate_sources). 'Unpriced' is not a source: it is always last.
RATE_SOURCES = {'published': 'Published rate', 'library': 'Your rate library', 'built_up': 'Built-up rate', 'estimate': 'Team estimate',
                'provisional': 'Provisional sum'}
RATE_SOURCES_DEFAULT_ALLOWED = ('published', 'library', 'built_up', 'provisional')
# Sources added after the rule first shipped, with whether they are allowed until the saved settings name them (the owner, 9 Oct 2026:
# provisional sums are allowed by default, so a rule saved before they existed allows them until it is changed and saved again).
RATE_SOURCES_ADDED = {'provisional': True}


def rate_sources():
    """The rate-source rule as features use it: {'on', 'order', 'allowed'} (switched off: every source, in the order set)."""
    r = rule('rate_sources') or {'enabled': True, 'params': {}}
    p = _clean_params('rate_sources', r['params'] or {'order': list(RATE_SOURCES), 'allowed': list(RATE_SOURCES_DEFAULT_ALLOWED)})
    return {'on': bool(r['enabled']), 'order': p['order'], 'allowed': p['allowed'] if r['enabled'] else list(p['order'])}


class RuleViolation(ValueError):
    """Raised when an enforced rule blocks an action. The message is safe to show the user."""


def _init():
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY, set_key TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL,
            params TEXT NOT NULL DEFAULT '{}', builtin INTEGER NOT NULL DEFAULT 0, locked INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        # Every change to a rule, with who, when, why and the settings before and after: shown on the Rules page and reverted in one click.
        c.execute('''CREATE TABLE IF NOT EXISTS rule_changes (
            id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, changed_at TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '', core INTEGER NOT NULL DEFAULT 0, what TEXT NOT NULL DEFAULT '',
            before TEXT NOT NULL DEFAULT '{}', after TEXT NOT NULL DEFAULT '{}', reverts TEXT NOT NULL DEFAULT '',
            reverted_by TEXT NOT NULL DEFAULT '')''')
        c.execute('CREATE INDEX IF NOT EXISTS rule_changes_by_rule ON rule_changes(rule_id, changed_at)')
        old_approval = c.execute("SELECT params FROM rules WHERE id='approval_required'").fetchone()
        for rid, set_key, name, kind, desc, enabled, params, text, core in BUILTIN:
            # INSERT OR IGNORE keeps your changes; the wording and whether a rule is Core refresh at every start.
            c.execute('INSERT OR IGNORE INTO rules VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?)',
                      (rid, set_key, name, kind, desc, text, int(enabled), json.dumps(params), int(core), '',
                       store.now(), store.now()))
            c.execute('UPDATE rules SET name=?,description=?,locked=? WHERE id=? AND builtin=1', (name, desc, int(core), rid))
        # "Human approval" became "Approval and library management" (D-0044): its settings start from the automatic approval switch
        # it replaces (on = Temple approves; off = a person approves every item), the rest at their defaults.
        if old_approval is not None and 'approver' not in json.loads(old_approval[0] or '{}'):
            row = c.execute("SELECT value FROM settings WHERE key='auto_approve'").fetchone()
            p = dict(next(b[6] for b in BUILTIN if b[0] == 'approval_required'))
            if row is not None: p['approver'] = 'temple' if row[0] == 'true' else 'person'
            c.execute("UPDATE rules SET params=?,enabled=1 WHERE id='approval_required'", (json.dumps(p),))
            store.audit(c, 'rule_migrated', 'approval_required', 'approval_required',
                        f"Human approval became Approval and library management: {APPROVER_NAMES[p['approver']].lower()}")
        # Client separation started as guidance; it is enforced now that clients can be tagged.
        c.execute("UPDATE rules SET kind='enforced',text='',params=? WHERE id='client_separation' AND kind='guidance'",
                  (json.dumps({'strict': False, 'external': 'all'}),))
        cols = {r['name'] for r in c.execute('PRAGMA table_info(record_meta)')}
        if 'review_by' not in cols: c.execute('ALTER TABLE record_meta ADD COLUMN review_by TEXT')


APPROVER_NAMES = {'temple': 'Temple approves new items under each space\'s rules', 'person': 'A person approves every new item',
                  'categories': 'Temple approves, except in the categories that need a person'}
LIBRARY_ACTIONS = {'approve': 'Approve', 'categorise': 'Categorise and tag', 'route': 'Route to a space', 'merge': 'Merge',
                   'supersede': 'Supersede', 'archive': 'Archive'}
LIBRARY_HOLDS = {'sensitive': 'Sensitive findings', 'clash': 'Clashes', 'unsure': 'Anything Temple is unsure about',
                 'no_category': 'Anything Temple could not give a category'}


_init()


# ---------------- rule access ----------------
def _load_rules():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM rules')]
    for r in rows:
        r['params'] = json.loads(r['params'] or '{}'); r['enabled'] = bool(r['enabled'])
        r['builtin'] = bool(r['builtin']); r['locked'] = r['core'] = bool(r['locked'])   # 'locked' is the column; it means Core
        if r['id'] == 'rate_sources' and r['params']:          # a source added since the settings were saved shows, in its default state
            r['params'] = _clean_params('rate_sources', r['params'])
    return sorted(rows, key=lambda r: (RANK.get(r['set_key'], 99), not r['builtin'], r['created_at'], r['name']))


def all_rules():
    """Every rule. Loaded once per web request (speed.memo; one page asks for them dozens of times) and handed out as copies,
    so nothing a caller changes leaks into the next caller; any change to the rules clears it (_rules_changed)."""
    import copy, speed
    return copy.deepcopy(speed.memo('rules', _load_rules))


def _rules_changed():
    import speed, sys
    speed.forget('rules')
    if 'spaces' in sys.modules: sys.modules['spaces'].forget()      # its rule switches are cached for a few seconds


def rule(rid):
    return next((r for r in all_rules() if r['id'] == rid), None)


def on(rid):
    r = rule(rid)
    return bool(r and r['enabled'])


def params(rid):
    r = rule(rid)
    return r['params'] if r else {}


# A preview (research_context.preview) runs the same checks as the real thing but must save nothing: no block lines.
PREVIEW = contextvars.ContextVar('alice_rules_preview', default=False)


def log_block(rid, target, detail):
    if PREVIEW.get(): return
    with store.db() as c:
        store.audit(c, 'rule_blocked', target[:200], rid, detail[:500])


def _state(r):
    return {'enabled': bool(r['enabled']), 'params': r['params'], 'text': r['text'], 'name': r['name']}


def may_change_core():
    """Core rules are an Owner's (permissions.is_owner_person: Alice.Owner in Entra; on the PC, whoever is at this computer)."""
    import permissions
    return permissions.is_owner_person(store.viewer())


def _clean_reason(reason, core, what='change'):
    reason = ' '.join((reason or '').split())[:500]
    if core and len(reason) < 3:
        raise ValueError(f'Give a reason: this is a Core rule, so every {what} needs one (it is kept in Activity with who and when).')
    if reason and (find_secrets(reason) or find_markings(reason)): raise RuleViolation('The reason looks like it contains a credential or a protective marking.')
    return reason


def _describe_change(r, before, after):
    parts = []
    if before['enabled'] != after['enabled']: parts.append('switched ' + ('on' if after['enabled'] else 'off'))
    if before['params'] != after['params']:
        keys = sorted({k for k in set(before['params']) | set(after['params']) if before['params'].get(k) != after['params'].get(k)})
        parts.append('settings changed' + (f" ({', '.join(k.replace('_', ' ') for k in keys)})" if keys else ''))
    if before['text'] != after['text']: parts.append('guidance text changed')
    if before['name'] != after['name']: parts.append('renamed')
    return ', '.join(parts) or 'no change'


def _apply_state(rid, r, new, reason, reverts=''):
    """Write a rule's new state, record the change (before and after, who, when, why) and log it in Activity."""
    import uuid
    before = _state(r)
    after = {**before, **new}
    if after == before: return None
    what = _describe_change(r, before, after)
    cid = uuid.uuid4().hex[:16]
    with store.acting(note=reason or None):
        with store.db() as c:
            c.execute('UPDATE rules SET enabled=?,params=?,text=?,name=?,updated_at=? WHERE id=?',
                      (int(after['enabled']), json.dumps(after['params']), after['text'], after['name'], store.now(), rid))
            c.execute('INSERT INTO rule_changes(id,rule_id,changed_at,actor,reason,core,what,before,after,reverts) VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (cid, rid, store.now(), store.actor(), reason, int(r['core']), what, json.dumps(before), json.dumps(after), reverts))
            if reverts: c.execute('UPDATE rule_changes SET reverted_by=? WHERE id=?', (cid, reverts))
            store.audit(c, 'rule_reverted' if reverts else 'rule_updated', rid, rid if r['core'] else 'human_control',
                        f'{r["name"]}' + (' (Core)' if r['core'] else '') + f': {what}' + (f'. Why: {reason}' if reason else ''))
    _rules_changed()
    return cid


def update_rule(rid, enabled=None, new_params=None, text=None, name=None, reason=None):
    """Change a rule. A Core rule only by an Owner, with a reason. Every change is kept (history) and can be reverted."""
    r = rule(rid)
    if not r: raise ValueError('Rule not found.')
    if r['core'] and not may_change_core():
        raise PermissionError(f'"{r["name"]}" is a Core rule: only an Owner can change it.')
    new = {}
    if enabled is not None: new['enabled'] = bool(enabled)
    if new_params is not None: new['params'] = _clean_params(rid, new_params)
    if text is not None:
        if r['kind'] != 'guidance': raise ValueError('Only guidance rules have editable text.')
        text = text.strip()
        if not text or len(text) > 1000: raise ValueError('Guidance text must be 1 to 1,000 characters.')
        new['text'] = text
    if name is not None and not r['builtin']:
        name = ' '.join(name.split())[:60]
        if not name: raise ValueError('Enter a rule name.')
        new['name'] = name
    if not new or {**_state(r), **new} == _state(r): return rule(rid)
    reason = _clean_reason(reason, r['core'])
    _apply_state(rid, r, new, reason)
    return rule(rid)


def history(rid=None, limit=50):
    """Changes to one rule (or every rule), newest first, each with whether it can still be reverted."""
    with store.db() as c:
        where, args = ('WHERE rule_id=? ', [rid]) if rid else ('', [])
        rows = [dict(x) for x in c.execute('SELECT * FROM rule_changes ' + where + 'ORDER BY changed_at DESC, id DESC LIMIT ?',
                                           args + [max(1, min(500, int(limit)))])]
    names = {r['id']: r['name'] for r in all_rules()}
    for x in rows:
        x['before'], x['after'] = json.loads(x['before'] or '{}'), json.loads(x['after'] or '{}')
        x['core'] = bool(x['core']); x['rule_name'] = names.get(x['rule_id'], x['rule_id'])
        x['can_revert'] = not x['reverted_by'] and x['rule_id'] in names
    return rows


def revert(change_id, reason=''):
    """Put a rule back as it was before one change, in one click. The revert is itself a change (logged, and revertible)."""
    with store.db() as c:
        ch = c.execute('SELECT * FROM rule_changes WHERE id=?', (change_id,)).fetchone()
    if not ch: raise ValueError('That change was not found.')
    ch = dict(ch)
    if ch['reverted_by']: raise ValueError('That change has already been reverted.')
    r = rule(ch['rule_id'])
    if not r: raise ValueError('That rule no longer exists.')
    if r['core'] and not may_change_core():
        raise PermissionError(f'"{r["name"]}" is a Core rule: only an Owner can revert a change to it.')
    before = json.loads(ch['before'] or '{}')
    new = {k: before[k] for k in ('enabled', 'params', 'text', 'name') if k in before}
    if 'params' in new: new['params'] = _clean_params(r['id'], new['params']) if new['params'] else {}
    reason = ' '.join((reason or '').split())[:500] or f'Reverted the change made {ch["changed_at"][:16].replace("T", " ")} UTC by {ch["actor"] or "someone"}'
    reason = _clean_reason(reason, r['core'], 'revert')
    cid = _apply_state(r['id'], r, new, reason, reverts=change_id)
    if cid is None:                      # already as it was: mark the change reverted all the same
        with store.db() as c:
            c.execute('UPDATE rule_changes SET reverted_by=? WHERE id=?', ('-', change_id))
    return rule(r['id'])


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
    if rid == 'rate_sources':
        named = [k for k in dict.fromkeys(p.get('order') or []) if k in RATE_SOURCES]
        order = named + [k for k in RATE_SOURCES if k not in named]
        allowed = [k for k in order if k in set(p.get('allowed') or []) or (k not in named and RATE_SOURCES_ADDED.get(k))]
        return {'order': order, 'allowed': allowed}
    if rid == 'external_scope':
        return {'allowed_categories': [str(x).strip() for x in p.get('allowed_categories', []) if str(x).strip()][:50]}
    if rid == 'approval_required':
        return clean_approval(p)
    if rid == 'share_gate':
        return {'temple': bool(p.get('temple', True))}
    return {}


def clean_approval(p):
    """Approval and library management: who approves new items, what Temple may do, overwrite and delete, what is held for a person.
    A setting left out keeps the shipped default."""
    base = next((b[6] for b in BUILTIN if b[0] == 'approval_required'), {})
    p = p or {}
    approver = p.get('approver', base.get('approver', 'temple'))
    if approver not in APPROVER_NAMES: raise ValueError('Who approves: temple, person or categories.')
    may_in, hold_in = p.get('temple_may') or {}, p.get('hold') or {}
    return {'approver': approver,
            'temple_may': {k: bool(may_in.get(k, (base.get('temple_may') or {}).get(k, True))) for k in LIBRARY_ACTIONS},
            'overwrite_delete': bool(p.get('overwrite_delete', base.get('overwrite_delete', False))),
            'hold': {k: bool(hold_in.get(k, (base.get('hold') or {}).get(k, True))) for k in LIBRARY_HOLDS}}


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


def check_share(text):
    """The Sharing check's code part (rule share_gate): reasons an item should not go into a shared space without its
    author confirming. Uses the same detectors as the other rules, never copies of them."""
    import rule_packs
    reasons = []
    pii = find_pii(text)
    if pii: reasons.append('It contains ' + ', '.join(pii).lower() + '.')
    personal = find_personal(text)
    if personal: reasons.append('It contains ' + ' and '.join(personal) + '.')
    if rule_packs.self_disclosure(text) and not any('special category' in r for r in reasons):
        reasons.append('It contains health or other special category details about its author.')
    elif rule_packs.special_about_person(text) and not any('special category' in r for r in reasons):
        reasons.append('It contains health or other special category details about someone.')
    return reasons


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


def passes(text, target, provider=None, packs=True):
    """check_outbound as a yes/no for one item of a batch: False means it must not be sent (its rule has logged the block)."""
    try:
        check_outbound(text, target, provider=provider, packs=packs)
        return True
    except RuleViolation:
        return False


def check_each(items, text_of, target, provider=None, packs=True):
    """Before a batch of memories (or other items) goes to a model: check_outbound on EACH one, as Temple's tagging does.
    Returns (the items that pass, how many were left out). Each one left out is logged by the rule that stopped it (log_block)
    and is never sent. The rules are read once for the whole batch (speed.scope), not once per item."""
    import speed
    kept, skipped = [], 0
    with speed.scope():
        for it in items:
            if passes(text_of(it), target, provider, packs): kept.append(it)
            else: skipped += 1
    return kept, skipped


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
        vc, va = store.viewer_clause('record', 'r.id')    # compared only with what the proposer may see (never names someone else's)
        with store.db() as c:   # read everything first; logging while a read is open would lock the database
            rows = c.execute("SELECT r.id,r.title,r.content FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id "
                             "WHERE coalesce(a.state,r.status) IN ('approved','proposed') AND r.id<>?" + vc, (exclude_id or '', *va)).fetchall()
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


def _decision_categories():
    try:
        import autoapprove
        return sorted(autoapprove.policy()['categories'])
    except Exception:
        return []


def overview():
    base = store.rules_base()
    rules = all_rules()
    return {'sets': [{'key': k, 'name': n, 'description': d} for k, n, d in SETS], 'rules': rules,
            'guidance': base['guidance'], 'allow_proposals': base['allow_proposals'],
            'effective_guidance': effective_guidance(base['guidance']), 'spend': spend_status(),
            'requests': rule_requests(), 'blocks': recent_blocks(),
            'categories': [c['name'] for c in store.list_categories()['categories']], 'providers': PROVIDERS,
            'rate_source_names': RATE_SOURCES,
            'approval': {'approvers': APPROVER_NAMES, 'actions': LIBRARY_ACTIONS, 'holds': LIBRARY_HOLDS, 'decision_categories': _decision_categories()},
            'history': history(limit=30), 'may_change_core': may_change_core(), 'defaults_error': DEFAULTS_ERROR,
            'defaults_file': str(deployment_defaults_path()),
            'counts': {'enforced': sum(1 for r in rules if r['enabled'] and r['kind'] == 'enforced'),
                       'guidance': sum(1 for r in rules if r['enabled'] and r['kind'] == 'guidance')}}
