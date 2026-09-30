"""Activity log for the Command centre: every audited action, labelled, typed, named and filterable."""
import csv
import io
import re
from datetime import datetime, timedelta, timezone
import substrate_store as store

TYPES = [
    ('memories', 'Memories and decisions'), ('knowledge', 'Knowledge'), ('temple', 'Temple'),
    ('blocks', 'Security blocks'), ('rules', 'Rules and settings'), ('clients', 'Clients'),
    ('chats', 'Chats and imports'), ('routing', 'Model routing'), ('tools', 'Tool use'), ('other', 'Other'),
]
TYPE_NAMES = dict(TYPES)

LABELS = {
    'record_proposed': ('memories', 'Memory proposed'), 'record_approved': ('memories', 'Memory approved'),
    'record_rejected': ('memories', 'Memory rejected'), 'memory_retired': ('memories', 'Memory retired'),
    'memory_superseded': ('memories', 'Memory replaced'), 'friction_resolved': ('memories', 'Replacement approved'),
    'review_by_set': ('memories', 'Review-by date set'), 'category_set': ('memories', 'Category set'),
    'category_created': ('memories', 'Category created'), 'category_updated': ('memories', 'Category changed'),
    'category_deleted': ('memories', 'Category deleted'), 'category_suggestions_accept': ('memories', 'Category suggestions accepted'),
    'category_suggestions_dismiss': ('memories', 'Category suggestions dismissed'), 'proposal_blocked': ('blocks', 'Proposal refused (proposals off)'),
    'knowledge_added': ('knowledge', 'Knowledge added'), 'knowledge_proposed': ('knowledge', 'Knowledge draft proposed'),
    'knowledge_approved': ('knowledge', 'Knowledge draft approved'), 'knowledge_rejected': ('knowledge', 'Knowledge draft rejected'),
    'knowledge_updated': ('knowledge', 'Knowledge details changed'),
    'temple_complete': ('temple', 'Temple reviewed a memory'), 'temple_failed': ('temple', 'Temple review failed'),
    'temple_chat_complete': ('temple', 'Temple analysed a chat answer'), 'temple_chat_review_complete': ('temple', 'Temple reviewed a whole chat'),
    'temple_chat_review_failed': ('temple', 'Temple chat review failed'), 'temple_chat_review_blocked': ('temple', 'Temple chat review blocked by a rule'),
    'temple_suggestion_accepted': ('temple', 'Temple suggestion accepted'), 'temple_categorised': ('temple', 'Temple categorised items'),
    'temple_settings': ('rules', 'Temple settings changed'), 'temple_chat_setting': ('rules', 'Temple chat suggestions switched'),
    'temple_categorise_mode': ('rules', 'Temple categorising mode changed'),
    'rule_blocked': ('blocks', 'Blocked by a rule'), 'rule_updated': ('rules', 'Rule changed'), 'rule_created': ('rules', 'Guidance rule added'),
    'rule_deleted': ('rules', 'Guidance rule deleted'), 'rules_updated': ('rules', 'Guidance saved'), 'retention_deleted': ('rules', 'Old chats deleted by retention'),
    'client_created': ('clients', 'Client added'), 'client_updated': ('clients', 'Client changed'), 'client_deleted': ('clients', 'Client deleted'),
    'client_tagged': ('clients', 'Client tag set'), 'chat_client_set': ('clients', 'Chat client set'),
    'conversation_saved': ('chats', 'Conversation saved from Claude'), 'claude_export_imported': ('chats', 'Claude export imported'),
    'chat_restored': ('chats', 'Chat restored from archive'),
    'model_routed': ('routing', 'Auto routing choice'), 'model_escalated': ('routing', 'Retried on another model'),
    'tool_completed': ('tools', 'Tool used'), 'tool_failed': ('tools', 'Tool failed'),
}
RULE_NAMES = {'secret_detection': 'Secret detection', 'protective_marking': 'Protective marking guard', 'pii': 'Personal identifiers',
              'provider_allow': 'Provider allow-list', 'external_scope': 'External client scope', 'client_separation': 'Client separation',
              'quality': 'Quality check', 'duplicates': 'Duplicate block', 'spend_cap': 'Spending caps', 'retention': 'Chat retention'}
HEX = re.compile(r'^[0-9a-f]{32}$')


def classify(action):
    if action in LABELS: return LABELS[action]
    return 'other', action.replace('_', ' ').capitalize()


def _codes_for(kind, actions):
    return [a for a in actions if classify(a)[0] == kind]


def _where(since, until, q, actions_all):
    clauses, args = [], []
    if since: clauses.append('created_at>=?'); args.append(since)
    if until: clauses.append('created_at<?'); args.append(until)
    if q:
        ql = q.lower()
        label_hits = [a for a in actions_all if ql in classify(a)[1].lower() or ql in RULE_NAMES.get(a, '').lower()]
        cond = "(instr(lower(action||' '||target||' '||rule||' '||detail),?)>0"
        args.append(ql)
        if label_hits: cond += f" OR action IN ({','.join('?' * len(label_hits))})"; args += label_hits
        rule_hits = [k for k, v in RULE_NAMES.items() if ql in v.lower()]
        if rule_hits: cond += f" OR rule IN ({','.join('?' * len(rule_hits))})"; args += rule_hits
        clauses.append(cond + ')')
    return (' WHERE ' + ' AND '.join(clauses)) if clauses else '', args


def period(preset='7d', start='', end=''):
    """(since, until) ISO bounds in UTC. preset: today | 7d | 30d | all | custom."""
    now = datetime.now(timezone.utc)
    if preset == 'today': return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), ''
    if preset == '7d': return (now - timedelta(days=7)).isoformat(), ''
    if preset == '30d': return (now - timedelta(days=30)).isoformat(), ''
    if preset == 'custom':
        ok = lambda d: bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', d or ''))
        since = start + 'T00:00:00+00:00' if ok(start) else ''
        until = (datetime.fromisoformat(end) + timedelta(days=1)).strftime('%Y-%m-%d') + 'T00:00:00+00:00' if ok(end) else ''
        return since, until
    return '', ''


def _names(targets):
    """Readable names for IDs that appear as targets (memories, chats, knowledge, suggestions)."""
    ids = [t for t in set(targets) if HEX.match(t or '')]
    if not ids: return {}
    names, marks = {}, ','.join('?' * len(ids))
    with store.db() as c:
        for sql, prefix in ((f'SELECT id,title FROM records WHERE id IN ({marks})', 'Memory'),
                            (f'SELECT id,title FROM chats WHERE id IN ({marks})', 'Chat'),
                            (f'SELECT id,name AS title FROM files WHERE id IN ({marks})', 'Knowledge'),
                            (f'SELECT file_id AS id,title FROM knowledge_meta WHERE file_id IN ({marks})', 'Knowledge'),
                            (f'SELECT id,title FROM temple_suggestions WHERE id IN ({marks})', 'Suggestion')):
            try:
                for r in c.execute(sql, ids): names[r['id']] = f'{prefix}: {r["title"]}'
            except Exception:
                pass
    return names


def query(kind='', preset='7d', start='', end='', q='', offset=0, limit=100, everything=False):
    since, until = period(preset, start, end)
    with store.db() as c:
        actions_all = [r[0] for r in c.execute('SELECT DISTINCT action FROM activity')]
        where, args = _where(since, until, q.strip(), actions_all)
        counts = {}
        for action, n in c.execute('SELECT action,count(*) FROM activity' + where + ' GROUP BY action', args):
            k = classify(action)[0]; counts[k] = counts.get(k, 0) + n
        total_all = sum(counts.values())
        if kind:
            codes = _codes_for(kind, actions_all) or ['__none__']
            where2 = (where + ' AND ' if where else ' WHERE ') + f"action IN ({','.join('?' * len(codes))})"
            args2 = args + codes
        else:
            where2, args2 = where, args
        total = c.execute('SELECT count(*) FROM activity' + where2, args2).fetchone()[0]
        sql = 'SELECT * FROM activity' + where2 + ' ORDER BY id DESC' + ('' if everything else ' LIMIT ? OFFSET ?')
        rows = [dict(r) for r in c.execute(sql, args2 + ([] if everything else [limit, offset]))]
    names = _names(r['target'] for r in rows)
    for r in rows:
        r['type'], r['label'] = classify(r['action'])
        r['type_name'] = TYPE_NAMES[r['type']]
        r['target_name'] = names.get(r['target'], '' if HEX.match(r['target'] or '') else r['target'])
        r['rule_name'] = RULE_NAMES.get(r['rule'], r['rule'].replace('_', ' '))
        if r['action'] == 'rule_blocked':        # the rule is the headline; details say what it caught
            r['label'] = 'Blocked: ' + r['rule_name']; r['rule_name'] = ''
    return {'rows': rows, 'total': total, 'total_all': total_all, 'counts': counts, 'types': TYPES,
            'next_offset': None if everything or offset + len(rows) >= total else offset + len(rows)}


def to_csv(**filters):
    data = query(everything=True, **filters)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Time (UTC)', 'Type', 'What happened', 'Item', 'Rule', 'Details', 'Code', 'Target ID'])
    for r in data['rows'][:50000]:
        w.writerow([r['created_at'][:19].replace('T', ' '), r['type_name'], r['label'], r['target_name'], r['rule_name'] or RULE_NAMES.get(r['rule'], r['rule']),
                    r['detail'], r['action'], r['target']])
    return out.getvalue()
