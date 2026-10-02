"""Activity log for the Command centre: every audited action, labelled, typed, named and filterable."""
import csv
import io
import re
from datetime import datetime, timedelta, timezone
import substrate_store as store

TYPES = [
    ('memories', 'Memories and decisions'), ('knowledge', 'Knowledge'), ('organisations', 'Organisations'), ('agents', 'Agents'), ('temple', 'Temple'),
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
    'agent_active': ('agents', 'Agent resumed'), 'agent_paused': ('agents', 'Agent paused'), 'agent_stopped': ('agents', 'Agent stopped'),
    'agent_updated': ('agents', 'Agent settings changed'), 'agent_registered': ('agents', 'Agent registered'),
    'org_created': ('organisations', 'Organisation added'), 'org_updated': ('organisations', 'Organisation details changed'),
    'org_fact_added': ('organisations', 'Organisation fact added by you'), 'org_fact_proposed': ('organisations', 'Organisation fact proposed'),
    'org_fact_approved': ('organisations', 'Organisation fact approved'), 'org_fact_rejected': ('organisations', 'Organisation fact rejected'),
    'org_fact_retired': ('organisations', 'Organisation fact retired'), 'org_fact_updated': ('organisations', 'Organisation fact details changed'),
    'org_source_removed': ('organisations', 'Facts from a source removed'),
    'knowledge_superseded': ('knowledge', 'Knowledge retired: replaced by a newer item'),
    'knowledge_replaces': ('knowledge', 'Knowledge now replaces an older item'),
    'knowledge_replacement_proposed': ('knowledge', 'Replacement named by the proposer'),
    'knowledge_replacement_dismissed': ('knowledge', 'Replacement suggestion dismissed (kept both)'),
    'temple_replacement_suggested': ('temple', 'Temple suggested retiring a replaced item'),
    'temple_replacements_checked': ('temple', 'Temple checked for replaced items'),
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
    'document_source_added': ('knowledge', 'Document source added'), 'proposal_started': ('chats', 'Proposal started'), 'proposal_rechecked': ('chats', 'Proposal sent to QA again'), 'reference_added': ('knowledge', 'Reference document added'), 'reference_auto_approved': ('temple', 'Reference summary auto-approved'), 'proposal_starter': ('temple', 'Temple suggested a proposal starter'), 'parker_update': ('temple', 'Parker worked on a proposal form'), 'proposal_form_started': ('chats', 'Proposal form started'), 'proposal_form_discarded': ('chats', 'Proposal form discarded'), 'assistant_renamed': ('rules', 'Assistant renamed'), 'proposal_written': ('chats', 'Proposal written'), 'proposal_failed': ('chats', 'Proposal failed'), 'document_created': ('chats', 'Document created'), 'assistant_answered': ('chats', 'Assistant answered'),
    'assistant_blocked': ('blocks', 'Assistant question blocked'), 'assistant_escalated': ('blocks', 'Assistant question sent to a person'),
    'assistant_saved': ('rules', 'Assistant changed'), 'demo_hr_loaded': ('knowledge', 'Demo HR policy loaded'), 'knowledge_review_days': ('rules', 'Knowledge review period changed'),
    'owner_set': ('memories', 'Owner set'), 'purview_label_seen': ('rules', 'New Purview label seen'), 'citations_tidied': ('organisations', 'Web citation markup removed'),
    'purview_label_mapped': ('rules', 'Purview label mapping changed'), 'purview_label_applied': ('knowledge', 'Purview label applied to an upload'),
}
RULE_NAMES = {'secret_detection': 'Secret detection', 'protective_marking': 'Protective marking guard', 'pii': 'Personal identifiers',
              'provider_allow': 'Provider allow-list', 'external_scope': 'External client scope', 'client_separation': 'Client separation',
              'quality': 'Quality check', 'duplicates': 'Duplicate block', 'spend_cap': 'Spending caps', 'retention': 'Chat retention',
              'purview_labels': 'Purview sensitivity labels'}
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
                            (f'SELECT id,title FROM temple_suggestions WHERE id IN ({marks})', 'Suggestion'),
                            (f"SELECT id,org || ' · ' || substr(statement,1,60) AS title FROM org_facts WHERE id IN ({marks})", 'Organisation fact')):
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
    w.writerow(['Time (UTC)', 'Type', 'What happened', 'Item', 'Rule', 'Details', 'By', 'Reason given', 'Code', 'Target ID'])
    for r in data['rows'][:50000]:
        w.writerow([r['created_at'][:19].replace('T', ' '), r['type_name'], r['label'], r['target_name'], r['rule_name'] or RULE_NAMES.get(r['rule'], r['rule']),
                    r['detail'], r.get('actor') or '', r.get('note') or '', r['action'], r['target']])
    return out.getvalue()


# ---------------- the picture: what is happening in Alice ----------------
GROUPS = [('knowledge', 'Memories and knowledge', {'memories', 'knowledge'}),
          ('work', 'Chats, assistants and tools', {'chats', 'tools', 'routing'}),
          ('temple', 'Temple and agents', {'temple', 'agents'}),
          ('orgs', 'Organisations and clients', {'organisations', 'clients'}),
          ('settings', 'Rules and settings', {'rules', 'other'})]
GATE = {'memories': ('Memories and decisions', 'record_proposed', 'record_approved', 'record_rejected'),
        'knowledge': ('Knowledge drafts', 'knowledge_proposed', 'knowledge_approved', 'knowledge_rejected'),
        'org_facts': ('Organisation facts', 'org_fact_proposed', 'org_fact_approved', 'org_fact_rejected')}
BLOCK_ACTIONS = ('rule_blocked', 'assistant_blocked', 'assistant_escalated', 'proposal_blocked', 'temple_chat_review_blocked')
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _parse(ts):
    try: d = datetime.fromisoformat(ts)
    except (TypeError, ValueError): return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def overview(preset='7d', start='', end='', tz=0):
    """Counts for the Activity page's graphical view. tz: the browser's getTimezoneOffset() in minutes."""
    since, until = period(preset, start, end)
    shift = timedelta(minutes=-max(-840, min(840, int(tz or 0))))
    where, args = _where(since, until, '', [])
    with store.db() as c:
        rows = [(r['created_at'], r['action'], r['rule']) for r in c.execute('SELECT created_at,action,rule FROM activity' + where + ' ORDER BY created_at', args)]
        rw, ra = (' WHERE started_at>=?', [since]) if since else ('', [])
        if until: rw, ra = (rw + (' AND ' if rw else ' WHERE ') + 'started_at<?', ra + [until])
        runs = [dict(r) for r in c.execute('SELECT r.agent_id,a.name,r.status,r.cost_usd,r.calls FROM agent_runs r LEFT JOIN agents a ON a.id=r.agent_id' + rw.replace('started_at', 'r.started_at'), ra)]
        uw, ua = (' WHERE created_at>=?', [since]) if since else ('', [])
        if until: uw, ua = (uw + (' AND ' if uw else ' WHERE ') + 'created_at<?', ua + [until])
        models = [dict(r) for r in c.execute('SELECT provider,model,count(*) AS calls,sum(coalesce(estimate_usd,0)) AS cost FROM model_usage' + uw
                                             + ' GROUP BY provider,model ORDER BY count(*) DESC', ua)]
    try:
        import actions
        pending = actions.count()
    except Exception:
        pending = None
    now = datetime.now(timezone.utc) + shift
    first = (_parse(since) + shift) if since else ((_parse(rows[0][0]) + shift) if rows else now)
    last = (_parse(until) + shift - timedelta(seconds=1)) if until else now
    span = (last - first).days
    unit = 'hour' if preset == 'today' else ('day' if span <= 92 else 'week')
    def key(d):
        if unit == 'hour': return d.strftime('%Y-%m-%dT%H')
        if unit == 'day': return d.strftime('%Y-%m-%d')
        return (d - timedelta(days=d.weekday())).strftime('%Y-%m-%d')
    order, labels = [], {}
    step = {'hour': timedelta(hours=1), 'day': timedelta(days=1), 'week': timedelta(days=7)}[unit]
    d = first.replace(minute=0, second=0, microsecond=0)
    if unit != 'hour': d = d.replace(hour=0)
    if unit == 'week': d -= timedelta(days=d.weekday())
    while d <= last and len(order) < 400:
        k = key(d); order.append(k)
        labels[k] = d.strftime('%H:00') if unit == 'hour' else (f'{d.day} {d:%b}' if unit == 'day' else f'w/c {d.day} {d:%b}')
        d += step
    group_of = {t: g for g, _, ts in GROUPS for t in ts}
    buckets = {k: {g: 0 for g, _, _ in GROUPS} | {'blocks': 0} for k in order}
    heat = [[0] * 24 for _ in range(7)]
    gate = {k: {'name': v[0], 'proposed': 0, 'approved': 0, 'rejected': 0} for k, v in GATE.items()}
    blocks, top = {}, {}
    for ts, action, rule in rows:
        dt = _parse(ts)
        if not dt: continue
        local = dt + shift
        kind, label = classify(action)
        b = buckets.get(key(local))
        if b is not None:
            b['blocks' if kind == 'blocks' else group_of.get(kind, 'settings')] += 1
        heat[local.weekday()][local.hour] += 1
        top[label] = top.get(label, 0) + 1
        for g, (name, p, a, r) in GATE.items():
            if action == p: gate[g]['proposed'] += 1
            elif action == a: gate[g]['approved'] += 1
            elif action == r: gate[g]['rejected'] += 1
        if action in BLOCK_ACTIONS:
            name = RULE_NAMES.get(rule, rule.replace('_', ' ').capitalize()) if action == 'rule_blocked' and rule else label
            blocks[name] = blocks.get(name, 0) + 1
    agents_out = {}
    for r in runs:
        a = agents_out.setdefault(r['agent_id'], {'id': r['agent_id'], 'name': r['name'] or r['agent_id'], 'runs': 0, 'failed': 0, 'blocked': 0, 'cost': 0.0, 'calls': 0})
        a['runs'] += 1; a['cost'] += r['cost_usd'] or 0; a['calls'] += r['calls'] or 0
        if r['status'] == 'failed': a['failed'] += 1
        elif r['status'] == 'blocked': a['blocked'] += 1
    try:
        import agents as _ag
        mname = lambda p, m: _ag.model_label(p, m)
    except Exception:
        mname = lambda p, m: m
    nblocks = sum(blocks.values())
    return {'unit': unit, 'groups': [{'key': g, 'name': n} for g, n, _ in GROUPS],
            'buckets': [{'key': k, 'label': labels[k], **buckets[k]} for k in order],
            'totals': {'events': len(rows), 'blocked': nblocks, 'pending': pending, 'runs': len(runs),
                       'failed_runs': sum(1 for r in runs if r['status'] == 'failed'),
                       'model_calls': sum(m['calls'] for m in models), 'cost_usd': round(sum(m['cost'] or 0 for m in models), 4)},
            'gate': list(gate.values()),
            'blocks': sorted(({'name': k, 'n': v} for k, v in blocks.items()), key=lambda x: -x['n']),
            'agents': sorted(agents_out.values(), key=lambda x: -x['runs'])[:12],
            'models': [{'name': mname(m['provider'], m['model']), 'calls': m['calls'], 'cost': round(m['cost'] or 0, 4)} for m in models][:8],
            'heat': heat, 'weekdays': WEEKDAYS,
            'top': sorted(({'label': k, 'n': v} for k, v in top.items()), key=lambda x: -x['n'])[:8]}
