"""Activity log for the Console: every audited action, labelled, typed, named and filterable."""
import csv
import io
import re
import urllib.parse
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
    'category_suggestions_dismiss': ('memories', 'Category suggestions dismissed'), 'category_area_set': ('memories', 'Category area set'),
    'tag_created': ('memories', 'Tag created'), 'tag_updated': ('memories', 'Tag changed'), 'tag_deleted': ('memories', 'Tag deleted'),
    'tags_set': ('memories', 'Tags changed on memories'), 'tag_suggestions_accept': ('memories', 'Tag suggestions accepted'),
    'tag_suggestions_dismiss': ('memories', 'Tag suggestions dismissed'), 'references_assigned': ('memories', 'Reference numbers given'), 'mileage_imported': ('other', 'Mileage export imported'), 'mileage_place_saved': ('other', 'Mileage place saved'), 'mileage_place_deleted': ('other', 'Mileage place deleted'), 'mileage_vehicle_set': ('other', 'Mileage vehicle set'), 'mileage_fill_approved': ('other', 'Mileage entry approved for filling'), 'mileage_save_approved': ('other', 'Mileage entry approved for saving'), 'mileage_rejected': ('other', 'Mileage day not claimed'), 'opportunity_scan': ('clients', 'Opportunity scan'), 'opportunity_updated': ('clients', 'Opportunity updated'), 'opportunity_schedule': ('clients', 'Watch list changed'), 'opportunity_closed': ('clients', 'Opportunity closed (dismissed)'), 'opportunity_changed': ('clients', 'Opportunity changed'), 'opportunity_expired': ('clients', 'Opportunity went stale'), 'auto_approved': ('memories', 'Approved automatically'), 'auto_held': ('memories', 'Held back for you'), 'auto_undone': ('memories', 'Automatic approval undone'), 'auto_approve_setting': ('rules', 'Automatic approval switched'), 'decision_policy': ('rules', 'Decision approval settings changed'), 'proposal_retemplated': ('chats', 'Proposal moved to another template'), 'proposal_change_suggested': ('chats', 'A model suggested proposal changes'), 'proposal_change_applied': ('chats', 'Suggested proposal changes applied'), 'proposal_change_dismissed': ('chats', 'Suggested proposal changes dismissed'), 'decision_owner_emailed': ('memories', 'Decision owner emailed'), 'decision_owner_not_emailed': ('memories', 'Decision owner not emailed'), 'proposal_blocked': ('blocks', 'Proposal refused (proposals off)'),
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
    'temple_complete': ('temple', 'Temple reviewed a memory'), 'temple_failed': ('temple', 'Temple review failed'), 'temple_decision_chat': ('temple', 'Discussed a decision with Temple'), 'connector_memories_setting': ('rules', 'Memories from outside apps setting changed'), 'connector_knowledge_setting': ('rules', 'Notes from outside apps setting changed'), 'actions_approve_all': ('memories', 'Approve all on Actions'), 'temple_item_chat': ('temple', 'Discussed an item waiting for approval with Temple'), 'health_uploaded': ('other', 'Health report uploaded'), 'health_viewed': ('other', 'Health Insights opened'), 'health_edited': ('other', 'Health result changed'), 'health_deleted': ('other', 'Health report deleted'), 'health_settings': ('rules', 'Health Insights settings changed'), 'health_context_read': ('tools', 'Health context read by a model'), 'health_context_refused': ('blocks', 'Health context refused'), 'health_note_added': ('other', 'Health note added'), 'health_note_proposed': ('other', 'Health note proposed by a model'), 'health_note_approved': ('other', 'Health note approved'), 'health_note_rejected': ('other', 'Health note rejected'), 'health_note_doned': ('other', 'Health note marked done'), 'health_note_reopened': ('other', 'Health note reopened'), 'health_note_deleted': ('other', 'Health note deleted'), 'health_note_reviewed': ('other', 'Health note review date set'), 'taxonomy_applied': ('temple', 'Temple tidied categories and tags'), 'taxonomy_proposed': ('temple', 'Temple proposed a category or tag change'), 'taxonomy_approved': ('memories', 'Category or tag change approved'), 'taxonomy_rejected': ('memories', 'Category or tag change rejected'), 'taxonomy_undone': ('memories', 'Category or tag change undone'), 'temple_taxonomy_mode': ('rules', 'Temple housekeeping mode changed'),
    'temple_chat_complete': ('temple', 'Temple analysed a chat answer'), 'temple_chat_review_complete': ('temple', 'Temple reviewed a whole chat'),
    'temple_chat_review_failed': ('temple', 'Temple chat review failed'), 'temple_chat_review_blocked': ('temple', 'Temple chat review blocked by a rule'),
    'temple_suggestion_accepted': ('temple', 'Temple suggestion accepted'), 'temple_categorised': ('temple', 'Temple categorised items'), 'temple_tagged': ('temple', 'Temple tagged memories'), 'temple_tags_mode': ('rules', 'Temple tagging mode changed'),
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
    'document_source_added': ('knowledge', 'Document source added'), 'proposal_started': ('chats', 'Proposal started'), 'proposal_rechecked': ('chats', 'Proposal sent to QA again'), 'reference_added': ('knowledge', 'Reference document added'), 'reference_auto_approved': ('temple', 'Reference summary auto-approved'), 'proposal_starter': ('temple', 'Temple suggested a proposal starter'), 'parker_update': ('temple', 'Parker worked on a proposal form'), 'proposal_form_started': ('chats', 'Proposal form started'), 'proposal_form_discarded': ('chats', 'Proposal form discarded'), 'assistant_renamed': ('rules', 'Assistant renamed'), 'agent_renamed': ('agents', 'Agent renamed'), 'proposal_revised': ('chats', 'Proposal revised with your accepted fixes'), 'proposal_repriced': ('chats', 'Proposal repriced from the rate card'), 'proposal_written': ('chats', 'Proposal written'), 'proposal_failed': ('chats', 'Proposal failed'), 'document_created': ('chats', 'Document created'), 'assistant_answered': ('chats', 'Assistant answered'),
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
        m = REF.match(q or '')
        if m: where, args = ' WHERE id=?', [int(m.group(1))]
        else: where, args = _where(since, until, q.strip(), actions_all)
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
        r['type'], r['label'] = classify(r['action']); r['ref'] = ref_of(r['id'])
        r['type_name'] = TYPE_NAMES[r['type']]
        r['target_name'] = names.get(r['target'], '' if HEX.match(r['target'] or '') else r['target'])
        r['rule_name'] = RULE_NAMES.get(r['rule'], r['rule'].replace('_', ' '))
        if r['action'] == 'rule_blocked':        # the rule is the headline; details say what it caught
            r['label'] = 'Blocked: ' + (_control(r['rule'], 'blocks', '')[0][-1][0] if r['rule'].startswith('rule_pack:') else r['rule_name']); r['rule_name'] = ''
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


# ---------------- the information card (standard format, see CLAUDE.md "Information cards") ----------------
REF = re.compile(r'^\s*L-?0*(\d{1,12})\s*$', re.I)
AREA = {'memories': ('Memories', '/admin/memories'), 'knowledge': ('Knowledge summaries', '/admin/knowledge'),
        'organisations': ('Organisations', '/admin/organisations'), 'agents': ('Agents', '/admin/agents'), 'temple': ('Temple', '/admin/temple'),
        'rules': ('Rules', '/admin/rules'), 'clients': ('Organisations', '/admin/organisations'), 'chats': ('Chats', '/admin/archive'),
        'routing': ('Chat · model routing', '/'), 'tools': ('Chat · tools', '/'), 'blocks': ('Rules', '/admin/rules'), 'other': ('Alice', '/admin')}
PLACES = {'chat message': [('Chat', '/'), ('A message', '')], 'opportunity scan': [('Organisations', '/admin/organisations'), ('Opportunity scan', '/admin/organisations?tracker=1')],
          'external endpoint': [('Connected apps', '/admin/apps'), ('Outside connector (Copilot, Claude)', '/admin/agents')],
          'proposal writer': [('Assistants', '/admin/assistants'), ('Proposal writer (Parker)', '/admin/assistants')]}
HOW = {'human_review': 'Your decision at an approval gate', 'human_control': 'A change you made to a setting',
       'advisory_only': 'Temple (advisory: changes nothing)', 'assistant': 'An assistant', 'automatic': 'Alice, automatically'}


def ref_of(row_id):
    return 'L-%06d' % int(row_id)


def _place(target, kind):
    """Where it happened, as a path from Alice down to the item: [(label, href), ...]."""
    t = (target or '').strip()
    if not t: return [AREA.get(kind, AREA['other'])]
    if t.lower() in PLACES: return PLACES[t.lower()]
    if HEX.match(t):
        with store.db() as c:
            for sql, area, href in (('SELECT title FROM records WHERE id=?', ('Memories', '/admin/memories'), '/admin/memories?status=all&q='),
                                    ('SELECT title FROM chats WHERE id=?', ('Chats', '/admin/archive'), '/#'),
                                    ('SELECT title FROM knowledge_meta WHERE file_id=?', ('Knowledge summaries', '/admin/knowledge'), '/admin/knowledge?status=all&q='),
                                    ('SELECT title FROM temple_suggestions WHERE id=?', ('Temple', '/admin/temple?tab=suggestions'), '')):
                try: r = c.execute(sql, (t,)).fetchone()
                except Exception: r = None
                if r:
                    link = (href + t) if href == '/#' else (href + urllib.parse.quote(r[0][:40]) if href else '')
                    return [area, (r[0], link)]
        return [AREA.get(kind, AREA['other']), ('Item ' + t[:8] + ' (no longer exists)', '')]
    try:
        with store.db() as c:
            a = c.execute('SELECT id, name FROM assistants WHERE id=? OR lower(name)=lower(?)', (t, t)).fetchone()
        if a: return [('Assistants', '/admin/assistants'), (a['name'], '/assistant/' + a['id'])]
    except Exception: pass
    try:
        import agents
        for a in agents.listing():
            if t in (a.get('id'), a.get('name')): return [('Agents', '/admin/agents'), (a['name'], '/admin/agents?agent=' + a['id'])]
    except Exception: pass
    try:
        with store.db() as c:
            o = c.execute('SELECT name FROM organisations WHERE lower(name)=lower(?)', (t,)).fetchone()
        if o: return [('Organisations', '/admin/organisations'), (o[0], '/admin/organisations?org=' + urllib.parse.quote(o[0]))]
    except Exception: pass
    return [AREA.get(kind, AREA['other']), (t[:120], '')]


def _control(rule, kind, label):
    """What logged it: the rule (set › rule) or rule pack (pack › safeguard) that fired, or the part of Alice that acted."""
    rule = rule or ''
    if rule.startswith('rule_pack:'):
        try:
            import rule_packs
            for p in rule_packs.PACKS.values():
                for r in p['rules']:
                    if r['id'] == rule[10:]:
                        return ([('Rule packs', '/admin/rule-packs'), (p['name'] + ' pack', '/admin/rule-packs?pack=' + p['id']), (r['name'], '')],
                                r.get('why') or r.get('what') or '', 'Rule pack safeguard')
        except Exception: pass
        return [('Rule packs', '/admin/rule-packs'), (rule[10:].replace('_', ' '), '')], '', 'Rule pack safeguard'
    try:
        import rules_engine
        rules = {r['id']: r for r in rules_engine.all_rules()}
        if rule in rules:
            r = rules[rule]; sets = {k: n for k, n, _ in rules_engine.SETS}
            return ([('Rules', '/admin/rules#rules'), (sets.get(r['set_key'], r['set_key']), '/admin/rules#rules'), (r['name'], '/admin/rules?rule=' + r['id'] + '#rules')],
                    r.get('description') or r.get('text') or '', ('Enforced rule' if r['kind'] == 'enforced' else 'Guidance rule'))
    except Exception: pass
    area = AREA.get(kind, AREA['other'])
    return [area, (label, '')], '', HOW.get(rule, '')


def card(ref_or_id):
    """One activity row as a standard information card: ref, title, tone, sections in the standard order
    (What happened, Where, When, Who, Why, Related, Technical). Raises ValueError when not found."""
    m = REF.match(str(ref_or_id))
    if not m: raise ValueError('Give a log reference such as L-000123.')
    rid = int(m.group(1))
    with store.db() as c:
        r = c.execute('SELECT * FROM activity WHERE id=?', (rid,)).fetchone()
        if not r: raise ValueError('No log entry ' + ref_of(rid) + '.')
        r = dict(r)
        same = [dict(x) for x in c.execute('SELECT id, created_at, action, rule FROM activity WHERE target=? AND id<>? ORDER BY id DESC LIMIT 8',
                                           (r['target'], rid))] if r['target'] else []
    kind, label = classify(r['action'])
    rule_name = RULE_NAMES.get(r['rule'], (r['rule'] or '').replace('_', ' '))
    if r['action'] == 'rule_blocked': label = 'Blocked: ' + (rule_name if not r['rule'].startswith('rule_pack:') else _control(r['rule'], kind, '')[0][-1][0])
    place = _place(r['target'], kind)
    control, why_rule, control_kind = _control(r['rule'], kind, label)
    actor = (r.get('actor') or '').strip()
    who_how = ('Signed in with Microsoft (Entra ID)' if '@' in actor else 'The person using Alice on this computer' if actor else
               'Not recorded (logged before Alice recorded who acted, or by an automatic process)')
    blocked = kind == 'blocks'
    sections = [
        {'key': 'what', 'title': 'What happened', 'text': r['detail'] or label},
        {'key': 'where', 'title': 'Where', 'paths': [{'label': 'Happened in', 'path': [{'label': a, 'href': b} for a, b in [('Alice', '/admin')] + place]},
                                                    {'label': 'Logged by', 'path': [{'label': a, 'href': b} for a, b in [('Alice', '/admin')] + control]}]},
        {'key': 'when', 'title': 'When', 'rows': [['Time', {'time': r['created_at']}], ['Recorded (UTC)', r['created_at'][:19].replace('T', ' ')]]},
        {'key': 'who', 'title': 'Who', 'rows': [['Acting', actor or 'Not recorded'], ['How Alice knows', who_how]]},
        {'key': 'why', 'title': 'Why', 'rows': [x for x in [['Reason given', r.get('note')] if r.get('note') else None,
                                                             ['Triggered by', control_kind] if control_kind else None,
                                                             ['What the rule is for', why_rule] if why_rule else None,
                                                             ['Outcome', 'Stopped: nothing was sent or saved' if blocked else ''] if blocked else None] if x]
         or [['Reason given', 'None recorded']]},
        {'key': 'related', 'title': 'Related', 'items': [{'ref': ref_of(x['id']), 'label': classify(x['action'])[1] if x['action'] != 'rule_blocked'
                                                          else 'Blocked: ' + (_control(x['rule'], 'blocks', '')[0][-1][0] if x['rule'].startswith('rule_pack:') else RULE_NAMES.get(x['rule'], x['rule'].replace('_', ' '))), 'time': x['created_at']} for x in same],
         'empty': 'Nothing else logged for this item.'},
        {'key': 'technical', 'title': 'Technical', 'collapsed': True,
         'rows': [['Log entry', ref_of(rid)], ['Action code', r['action']], ['Rule code', r['rule'] or '–'], ['Target', r['target'] or '–']]},
    ]
    actions = [{'label': 'Open ' + place[-1][0], 'href': place[-1][1]}] if place[-1][1] else []
    if control[-1][1] and control[-1][1] != (place[-1][1] if place else ''): actions.append({'label': 'Open the rule', 'href': control[-1][1]})
    return {'ref': ref_of(rid), 'kind': 'log', 'kind_label': 'Activity log', 'title': label,
            'subtitle': place[-1][0], 'badge': TYPE_NAMES[kind], 'tone': 'bad' if blocked else 'warn' if kind == 'rules' else '',
            'sections': sections, 'actions': actions}
