"""Everything waiting on the owner, in one place: counts, the top few items, and where to go for the rest."""
import json
from datetime import datetime, timezone
import substrate_store as store

TOP = 5


def _section(key, title, count, link, items=(), note='', level='normal'):
    return {'key': key, 'title': title, 'count': count, 'link': link, 'items': list(items)[:TOP], 'note': note, 'level': level}


def summary():
    import temple, knowledge, clients, rules_engine
    today = datetime.now(timezone.utc).date().isoformat()
    out = []

    # 1. Memory proposals and decisions, with Temple's verdict
    q = temple.queue('pending')
    kinds = store.record_kinds(i['id'] for i in q['items'])
    items = [{'type': 'proposal', 'id': i['id'], 'title': i['title'],
              'detail': (i['reason'] or i['content'].replace('\n', ' ')[:160]),
              'verdict': i['verdict'], 'kind': (kinds.get(i['id']) or {}).get('kind', 'fact'),
              'replaces': i.get('replaces')} for i in q['items']]
    decisions = sum(1 for i in items if i['kind'] == 'decision')
    out.append(_section('proposals', 'Memories and decisions awaiting approval', q['views']['pending'],
                        '/admin/memories?status=proposed', items,
                        f'{decisions} of these are decisions.' if decisions else ''))

    # 2. Knowledge drafts proposed by models
    d = knowledge.listing(status='draft')
    def _draft(i):
        rep = [{'id': p['old_id'], 'title': p['old_title']} for p in i['replacement_suggestions']
               if p['new_id'] == i['id'] and p['source'] == 'proposer']
        return {'type': 'draft', 'id': i['id'], 'title': i['title'], 'replaces': rep,
                'detail': i['source'] + ' · ' + i['added_by'] + (' · replaces ' + ', '.join('“' + x['title'] + '”' for x in rep) if rep else '')}
    out.append(_section('drafts', 'Knowledge drafts awaiting approval', d['total'], '/admin/knowledge', [_draft(i) for i in d['items']]))

    # 2b. Older knowledge that a newer, approved item replaces (proposer's word or Temple's suggestion)
    reps = [p for p in knowledge.replacements('pending') if p['new_status'] == 'active']
    out.append(_section('replacements', 'Older knowledge that may be replaced', len(reps), '/admin/knowledge',
                        [{'type': 'replacement', 'id': p['id'], 'title': f"Retire “{p['old_title']}”",
                          'detail': f"Replaced by “{p['new_title']}” · " + ('Temple' if p['source'] == 'temple' else 'the proposer')
                                    + (': ' + p['reason'] if p['reason'] else '') + (f" · quote: “{p['quote'][:160]}”" if p['quote'] else '')}
                         for p in reps],
                        'Retiring archives the older item with a link to its replacement; models are pointed to the new one. Restore undoes it.'))

    # 2c. Organisation facts proposed by models
    import organisations
    of = organisations.pending()
    out.append(_section('orgfacts', 'Organisation facts awaiting approval', len(of), '/admin/organisations',
                        [{'type': 'orgfact', 'id': f['id'], 'title': f"{f['org']} · {organisations.SECTION_NAMES.get(f['section'], f['section'])}",
                          'detail': f"{f['statement']} · source: {f['source_system']}" + (f" ({f['source_ref'][:80]})" if f['source_ref'] else '')
                                    + f" · {f['proposed_by']}"} for f in of]))

    # 2c-ii. Client opportunities Temple has suggested
    import opportunities
    ops = opportunities.tracker('suggested')['opportunities']
    out.append(_section('opportunities', 'Client opportunities suggested', len(ops), '/admin/organisations?tracker=1',
                        [{'type': 'link', 'id': o['id'], 'title': f"{o['org']} · {o['title']}", 'detail': (o['why_now'] or o['summary'])[:200],
                          'href': '/admin/organisations?tracker=1&org=' + o['org']} for o in ops[:20]]))

    # 2d. Agents that paused themselves or are past their review date
    import agents
    al = agents.alerts()
    out.append(_section('agents', 'Agents needing attention', len(al), '/admin/agents',
                        [{'type': 'link', 'id': a['id'], 'title': a['title'], 'detail': a['detail'], 'href': '/admin/agents?agent=' + a['id']} for a in al],
                        level='warn' if al else 'normal'))

    # 3. Temple's chat suggestions
    s = temple.chat_suggestions('pending')
    out.append(_section('suggestions', "Temple's suggestions from chats", s['counts']['pending'], '/admin/temple?tab=suggestions',
                        [{'type': 'suggestion', 'id': i['id'], 'title': i['title'], 'kind': i['kind'], 'content': i['content'],
                          'detail': f"{i['kind'].replace('_', ' ')} · from “{i['chat_title']}”"} for i in s['items']]))

    # 4. Category and client suggestions from Temple
    with store.db() as c:
        mem_cat = [dict(r) for r in c.execute(
            "SELECT r.id,r.title,m.suggestion FROM record_meta m JOIN records r ON r.id=m.record_id LEFT JOIN memory_archive a ON a.record_id=r.id "
            "WHERE m.suggestion<>'' AND coalesce(a.state,r.status) IN ('approved','proposed') ORDER BY r.created_at DESC")]
    kn = knowledge.listing(status='active', category='__suggested__', limit=100)
    cm, cf = clients.items('memory', '__suggested__', limit=100), clients.items('file', '__suggested__', limit=100)
    tag_items = ([{'type': 'category', 'id': r['id'], 'title': r['title'], 'detail': 'Category: ' + r['suggestion']} for r in mem_cat]
                 + [{'type': 'kcategory', 'id': i['id'], 'title': i['title'], 'detail': 'Category: ' + i['category_suggestion']} for i in kn['items']]
                 + [{'type': 'client', 'item_type': 'memory', 'id': i['id'], 'title': i['title'], 'detail': 'Client: ' + i['suggestion']} for i in cm['items']]
                 + [{'type': 'client', 'item_type': 'file', 'id': i['id'], 'title': i['title'], 'detail': 'Client: ' + i['suggestion']} for i in cf['items']])
    out.append(_section('tags', 'Category and client suggestions', len(mem_cat) + kn['total'] + cm['total'] + cf['total'],
                        '/admin/memories', tag_items,
                        'Knowledge suggestions are on the Knowledge page, client suggestions on Clients.' if (kn['total'] or cm['total'] or cf['total']) else ''))

    # 5. Past their review-by date (memories, decisions to revisit, knowledge)
    due_mem = store.organised_records('approved', category='__expired__', limit=TOP)
    with store.db() as c:
        due_kn = [dict(r) for r in c.execute("SELECT file_id AS id,title,review_by FROM knowledge_meta WHERE status='active' "
                                             "AND review_by IS NOT NULL AND review_by<? ORDER BY review_by", (today,))]
    due_items = ([{'type': 'link', 'id': r['id'], 'title': r['title'], 'detail': ('Decision to revisit' if r.get('kind') == 'decision' else 'Memory')
                   + ' · review by ' + (r['review_by'] or ''), 'href': '/admin/memories?status=approved'} for r in due_mem['records']]
                 + [{'type': 'link', 'id': r['id'], 'title': r['title'], 'detail': 'Knowledge · review by ' + r['review_by'], 'href': '/admin/knowledge'} for r in due_kn])
    out.append(_section('due', 'Past their review date', due_mem['total'] + len(due_kn), '/admin/memories?status=approved', due_items,
                        'Filter Memories by “⚑ Past review date” to see them all.' if due_mem['total'] else ''))

    # 6. Temple reviews that failed
    failed = temple.queue('reviewed', 'failed')
    out.append(_section('failed', 'Temple reviews that failed', failed['total'], '/admin/temple',
                        [{'type': 'link', 'id': i['id'], 'title': i['title'], 'detail': (i['reviews'][0]['error'] if i['reviews'] else ''),
                          'href': '/admin/temple'} for i in failed['items']], level='warn' if failed['total'] else 'normal'))

    # 7. Archived chats not yet reviewed by Temple
    a = store.archived_chats(only_uncaptured=True, limit=100000)
    unreviewed = [c for c in a['chats'] if not c['review'] or c['review']['status'] == 'failed']
    out.append(_section('chats', 'Chats with nothing captured and no Temple review', len(unreviewed), '/admin/archive',
                        [{'type': 'link', 'id': c['id'], 'title': c['title'], 'detail': (c['source'] if c['source'] != 'alice' else 'Alice chat'),
                          'href': '/admin/archive'} for c in unreviewed],
                        'Use “Ask Temple to review flagged chats” on the Archive page (up to 50 per run).' if unreviewed else ''))

    # 8. Rule requests from Temple
    rr = rules_engine.rule_requests()
    out.append(_section('rules', 'Rule requests to consider', len(rr), '/admin/rules',
                        [{'type': 'link', 'id': r['id'], 'title': r['title'], 'detail': r['content'][:140], 'href': '/admin/rules'} for r in rr]))

    # 9. Spending
    sp = rules_engine.spend_status()
    if sp['level'] in ('warning', 'blocked'):
        out.insert(0, _section('spend', 'Spending cap ' + ('reached' if sp['level'] == 'blocked' else 'warning'), 1, '/admin/rules',
                               [{'type': 'link', 'id': 'spend', 'title': f"${sp['today_usd']:.2f} today of ${sp['daily_usd']:.2f} · ${sp['month_usd']:.2f} this month of ${sp['monthly_usd']:.2f}",
                                 'detail': 'Chat is paused.' if sp['level'] == 'blocked' else 'Temple automations are paused until the next day or month, or until you raise the cap.',
                                 'href': '/admin/rules'}], level='bad' if sp['level'] == 'blocked' else 'warn'))
    total = sum(s['count'] for s in out)
    return {'total': total, 'sections': out}


def count():
    try: return summary()['total']
    except Exception: return 0
