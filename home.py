"""The Console home page: what needs you, what happened today, what you were working on, and the way in to everything."""
from datetime import datetime, timezone

import substrate_store as store


def _safe(fn, default):
    try: return fn()
    except Exception: return default


def backup_status():
    import backup
    return backup.home_status()


def summary(tz=0):
    if store.restricted() is not None: return _own(tz)
    import actions, activity_log, agents, assistants, knowledge, organisations, rules_engine, doc_library
    acts = _safe(lambda: actions.summary(cached=True), {'total': 0, 'sections': []})
    today = _safe(lambda: activity_log.overview('today', tz=tz), {'totals': {}})
    week = _safe(lambda: activity_log.overview('7d', tz=tz), {'buckets': [], 'groups': [], 'gate': []})
    spend = _safe(rules_engine.spend_status, {})
    rc, ra = store.viewer_clause('record', 'r.id')            # what is in this person's spaces (spaces.py)
    cc, ca = store.viewer_clause('chat', 'c.id')
    pc, pa = store.viewer_clause('proposal', 'proposals.id')
    with store.db() as c:
        mem = c.execute("SELECT count(*) FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id WHERE coalesce(a.state,r.status)='approved'" + rc, ra).fetchone()[0]
        chats = [dict(r) for r in c.execute(
            'SELECT c.id,c.title,c.updated_at,c.client,(SELECT count(*) FROM chat_turns t WHERE t.chat_id=c.id) AS turns FROM chats c WHERE 1=1'
            + cc + 'ORDER BY c.updated_at DESC LIMIT 25', ca)]
        props = [dict(r) for r in _safe(lambda: list(c.execute(
            "SELECT id,assistant_id,title,organisation,status,qa,context,created_at FROM proposals WHERE status!='discarded'" + pc + "ORDER BY updated_at DESC LIMIT 4", pa)), [])]
    for p in props:
        try:
            import json
            qa = json.loads(p.pop('qa') or '[]')
        except ValueError:
            qa = []
        try: p['ai_cost'] = (json.loads(p.pop('context') or '{}').get('ai_cost') or {}).get('total', 0)
        except ValueError: p['ai_cost'] = 0
        p['verdict'] = qa[-1]['verdict'] if qa else ''
        p['score'] = qa[-1].get('score') if qa else None
    kn = _safe(lambda: knowledge.listing(status='active', limit=1)['total'], 0)
    orgs = _safe(lambda: organisations.listing()['organisations'], [])
    docs = _safe(lambda: sum(s['files'] for s in doc_library.sources()), 0)
    ag = _safe(lambda: agents.listing()['agents'], [])
    attention = [{'id': a['id'], 'name': a['name'],
                  'why': (a['status'] + (': ' + a['status_reason'] if a['status_reason'] else '')) if a['status'] != 'active'
                  else 'last run failed' if a.get('failure_open') else 'review date passed'}
                 for a in ag if a['status'] != 'active' or a.get('failure_open') or a.get('review_overdue')]
    asst = _safe(lambda: assistants.listing()['assistants'], [])
    hour = (datetime.now(timezone.utc).hour - (tz or 0) // 60) % 24
    return {
        'name': store.owner_name(), 'greeting': 'Good morning' if 5 <= hour < 12 else 'Good afternoon' if hour < 18 else 'Good evening',
        'waiting': {'total': acts['total'], 'sections': [{k: s[k] for k in ('key', 'title', 'count', 'link', 'level')} for s in acts['sections'] if s['count'] and not s.get('info')]},
        'today': today.get('totals', {}), 'spend': spend,
        'week': {'buckets': [{'label': b['label'], 'n': sum(b[g['key']] for g in week['groups']) + b.get('blocks', 0)} for b in week.get('buckets', [])],
                 'gate': week.get('gate', [])},
        'chats': [x for x in chats if x['turns']][:5],
        'proposals': props,
        'assistants': [{'id': a['id'], 'name': a['name'], 'kind': a['kind'], 'status': a['status'], 'description': a['description']} for a in asst],
        'agents': {'total': len(ag), 'active': sum(1 for a in ag if a['status'] == 'active'), 'attention': attention[:5]},
        'backup': _safe(backup_status, None),
        'substrate': {'memories': mem, 'knowledge': kn, 'organisations': len(orgs), 'clients': sum(1 for o in orgs if o.get('is_client')),
                      'documents': docs},
    }


def _own(tz=0):
    """Home for a person without the Owner role (users.py): the same page, filled only with their own chats, proposals and items,
    and the parts of Alice their profile lets them see. Nothing waiting on Actions, nobody else's activity, no backups."""
    import assistants, knowledge, permissions, rules_engine, doc_library
    v = store.viewer()
    vc, va = store.viewer_clause('chat', 'c.id')
    pc, pa = store.viewer_clause('proposal', 'proposals.id')
    with store.db() as c:
        chats = [dict(r) for r in c.execute('SELECT c.id,c.title,c.updated_at,c.client,(SELECT count(*) FROM chat_turns t WHERE t.chat_id=c.id) AS turns '
                                            'FROM chats c WHERE 1=1' + vc + 'ORDER BY c.updated_at DESC LIMIT 25', va)]
        props = [dict(r) for r in c.execute("SELECT id,assistant_id,title,organisation,status,created_at FROM proposals WHERE status!='discarded'" + pc +
                                            'ORDER BY updated_at DESC LIMIT 4', pa)]
    for p in props: p.update(verdict='', score=None, ai_cost=0)
    mem = _safe(lambda: store.organised_records('approved', '', '', 'newest', 0, 1)['total'], 0)
    kn = _safe(lambda: knowledge.listing(status='active', limit=1)['total'], 0)
    asst = [a for a in _safe(lambda: assistants.listing()['assistants'], []) if permissions.can(v, 'assistant', permissions.USE, a['id'])]
    hour = (datetime.now(timezone.utc).hour - (tz or 0) // 60) % 24
    return {
        'name': (v.name or v.email or 'there').split(' ')[0], 'greeting': 'Good morning' if 5 <= hour < 12 else 'Good afternoon' if hour < 18 else 'Good evening',
        'waiting': {'total': 0, 'sections': []}, 'today': {},
        'spend': _safe(rules_engine.spend_status, {}) if permissions.can(v, 'usage') else {},
        'week': {'buckets': [], 'gate': []},
        'chats': [x for x in chats if x['turns']][:5] if permissions.can(v, 'chat', permissions.USE) else [],
        'proposals': props,
        'assistants': [{'id': a['id'], 'name': a['name'], 'kind': a['kind'], 'status': a['status'], 'description': a['description']} for a in asst],
        'agents': {'total': 0, 'active': 0, 'attention': []}, 'backup': None,
        'substrate': {'memories': mem, 'knowledge': kn, 'organisations': 0, 'clients': 0,
                      'documents': _safe(lambda: sum(s['files'] for s in doc_library.sources()), 0) if permissions.library_ok(v) else 0},
        'restricted': True, 'note': 'You see your personal space, the Organisation space, team spaces open to the organisation and the spaces you are a member of.',
    }
