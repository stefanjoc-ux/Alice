"""Everything waiting on the owner, in one place: counts, the top few items, and where to go for the rest."""
import json
from datetime import datetime, timezone
import substrate_store as store

TOP = 5


def _section(key, title, count, link, items=(), note='', level='normal', top=TOP, info=False):
    return {'key': key, 'title': title, 'count': count, 'link': link, 'items': list(items)[:top], 'note': note, 'level': level, 'info': info}


def summary():
    import temple, knowledge, clients, rules_engine
    today = datetime.now(timezone.utc).date().isoformat()
    out = []

    import autoapprove, refs
    auto_on, held = autoapprove.on(), autoapprove.held()
    refs.ensure(fresh=False)

    # 1. Decisions: always yours, explained (why it is a decision, what it is for, Temple's recommendation)
    q = temple.queue('pending')
    kinds = store.record_kinds(i['id'] for i in q['items'])
    rmap = refs.of('record', [i['id'] for i in q['items']])
    dec = [i for i in q['items'] if (kinds.get(i['id']) or {}).get('kind') == 'decision']
    import temple_discuss
    talked = temple_discuss.counts(i['id'] for i in dec)
    out.append(_section('decisions', 'Decisions to approve', len(dec), '/admin/memories?status=proposed&kind=decision',
                        [{'type': 'decision', 'id': i['id'], 'title': i['title'], 'ref': rmap.get(i['id'], ''), 'verdict': i['verdict'],
                          'replaces': i.get('replaces'), 'discussion': talked.get(i['id'], 0), **autoapprove.explain_decision(i)} for i in dec],
                        ('Temple records decisions once checked, with who made them; these are being checked, or need approval under your '
                         'Decisions settings (a category or Temple\'s impact rating).' if autoapprove.managing_decisions() else
                         'Decisions wait for you. Temple checks each one against your earlier decisions and memories.'), top=20))

    # 2. Held back: automatic approval stopped, and says why
    mems = [i for i in q['items'] if i not in dec]
    drafts = knowledge.listing(status='draft', limit=100000)['items']
    import organisations
    facts = organisations.pending(limit=100000)
    def _mem(i, why=''):
        return {'type': 'proposal', 'id': i['id'], 'title': i['title'], 'ref': rmap.get(i['id'], ''), 'verdict': i['verdict'], 'replaces': i.get('replaces'),
                'detail': why or (i['reason'] or i['content'].replace('\n', ' ')[:160])}
    def _draft(i, why=''):
        rep = [{'id': p['old_id'], 'title': p['old_title']} for p in i['replacement_suggestions']
               if p['new_id'] == i['id'] and p['source'] == 'proposer']
        return {'type': 'draft', 'id': i['id'], 'title': i['title'], 'replaces': rep, 'ref': i.get('ref', ''),
                'detail': why or (i['source'] + ' · ' + i['added_by'] + (' · replaces ' + ', '.join('“' + x['title'] + '”' for x in rep) if rep else ''))}
    def _fact(f, why=''):
        return {'type': 'orgfact', 'id': f['id'], 'title': f"{f['org']} · {organisations.SECTION_NAMES.get(f['section'], f['section'])}",
                'detail': (why + ' · ' if why else '') + f"{f['statement']} · source: {f['source_system']}" + (f" ({f['source_ref'][:80]})" if f['source_ref'] else '')}
    fref = refs.of('file', [i['id'] for i in drafts])
    for i in drafts: i['ref'] = fref.get(i['id'], '')
    if auto_on:
        h_items = ([_mem(i, held[('memory', i['id'])]) for i in mems if ('memory', i['id']) in held]
                   + [_draft(i, held[('knowledge', i['id'])]) for i in drafts if ('knowledge', i['id']) in held]
                   + [_fact(f, held[('orgfact', f['id'])]) for f in facts if ('orgfact', f['id']) in held])
        out.append(_section('held', 'Held back for you', len(h_items), '/admin/memories?status=proposed', h_items,
                            'Automatic approval stopped at these: a clash with what Alice holds, a possible replacement, '
                            'something Temple could not check, or a proposal through the outside connector. Each says why.', top=20))
        w_items = ([_mem(i, 'Temple is checking it' if i['verdict'] == 'running' else '') for i in mems if ('memory', i['id']) not in held]
                   + [_draft(i) for i in drafts if ('knowledge', i['id']) not in held]
                   + [_fact(f) for f in facts if ('orgfact', f['id']) not in held])
        out.append(_section('waiting', 'Waiting for the automatic checks', len(w_items), '/admin/memories?status=proposed', w_items,
                            'Being checked now, or proposed before automatic approval was switched on. “Approve these automatically” '
                            'runs the same checks on them; anything that fails is held back for you.'))
    else:
        w_items = [_mem(i) for i in mems] + [_draft(i) for i in drafts] + [_fact(f) for f in facts]
        out.append(_section('waiting', 'Awaiting approval', len(w_items), '/admin/memories?status=proposed', w_items,
                            'Automatic approval is off: memories, knowledge and organisation facts wait for you.'))

    # 2a. What went live automatically (for information; each can be undone)
    if auto_on:
        recent = autoapprove.recent()
        by = {}
        for r in recent: by[r['item_type']] = by.get(r['item_type'], 0) + 1
        names = {'memory': ('memory', 'memories'), 'knowledge': ('knowledge item', 'knowledge items'), 'orgfact': ('organisation fact', 'organisation facts')}
        out.append(_section('auto', 'Approved automatically in the last 7 days', len(recent), '/admin/activity?type=memories',
                            [{'type': 'auto', 'item_type': r['item_type'], 'id': r['item_id'], 'title': r['title'], 'ref': r['ref'],
                              'detail': names.get(r['item_type'], (r['item_type'],))[0].capitalize() + ' · ' + r['reason'] + ' · ' + r['at'][:16].replace('T', ' ')}
                             for r in recent],
                            ' · '.join(f'{n} {names[k][0] if n == 1 else names[k][1]}' for k, n in by.items() if k in names)
                            + ('. Undo retires it (history kept).' if recent else ''), top=60, info=True))

    # 2c. Temple's category and tag housekeeping: changes waiting for you, and what it did itself (Undo for 7 days)
    import temple_taxonomy
    tx_wait = temple_taxonomy.changes('proposed', days=3650)
    out.append(_section('taxonomy', 'Category and tag changes to approve', len(tx_wait), '/admin/memories#organise',
                        [{'type': 'taxonomy', 'id': r['id'], 'title': r['summary'], 'detail': (r['why_waiting'] + ' ' if r['why_waiting'] else '') + r['reason']}
                         for r in tx_wait],
                        'Temple keeps categories and tags tidy. Changes to ones you created, or to a category a rule uses, wait for you.', top=20))
    tx_done = [r for r in temple_taxonomy.changes('applied', days=7) if r['decided_by'] == 'Temple']
    out.append(_section('taxonomy_done', 'Category and tag housekeeping by Temple in the last 7 days', len(tx_done), '/admin/memories#organise',
                        [{'type': 'taxonomy_done', 'id': r['id'], 'title': r['summary'], 'detail': r['reason'] + ' · ' + r['created_at'][:16].replace('T', ' '),
                          'can_undo': r['can_undo']} for r in tx_done],
                        'For information. Undo puts things back as they were.', top=40, info=True))

    # 2b. Older knowledge that a newer, approved item replaces (proposer's word or Temple's suggestion)
    reps = [p for p in knowledge.replacements('pending') if p['new_status'] == 'active']
    out.append(_section('replacements', 'Older knowledge that may be replaced', len(reps), '/admin/knowledge',
                        [{'type': 'replacement', 'id': p['id'], 'title': f"Retire “{p['old_title']}”",
                          'detail': f"Replaced by “{p['new_title']}” · " + ('Temple' if p['source'] == 'temple' else 'the proposer')
                                    + (': ' + p['reason'] if p['reason'] else '') + (f" · quote: “{p['quote'][:160]}”" if p['quote'] else '')}
                         for p in reps],
                        'Retiring archives the older item with a link to its replacement; models are pointed to the new one. Restore undoes it.'))

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
                        'Knowledge suggestions are on the Knowledge page, client suggestions under Organisations → Tag memories and files.' if (kn['total'] or cm['total'] or cf['total']) else ''))

    # 5. Past their review-by date (memories, decisions to revisit, knowledge)
    due_mem = store.organised_records('approved', category='__expired__', limit=TOP)
    with store.db() as c:
        due_kn = [dict(r) for r in c.execute("SELECT file_id AS id,title,review_by,owner FROM knowledge_meta WHERE status='active' "
                                             "AND review_by IS NOT NULL AND review_by<? ORDER BY review_by", (today,))]
    due_items = ([{'type': 'link', 'id': r['id'], 'title': r['title'], 'detail': ('Decision to revisit' if r.get('kind') == 'decision' else 'Memory')
                   + ' · review by ' + (r['review_by'] or '') + (' · owner ' + r['owner'] if r.get('owner') else ''), 'href': '/admin/memories?status=approved'} for r in due_mem['records']]
                 + [{'type': 'link', 'id': r['id'], 'title': r['title'], 'detail': 'Knowledge · review by ' + r['review_by'] + (' · owner ' + r['owner'] if r.get('owner') else ''), 'href': '/admin/knowledge'} for r in due_kn])
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
                        'Use “Ask Temple to review flagged chats” on the Saved chats page (up to 50 per run).' if unreviewed else ''))

    # 8. Rule requests from Temple
    rr = rules_engine.rule_requests()
    out.append(_section('rules', 'Rule requests to consider', len(rr), '/admin/rules',
                        [{'type': 'link', 'id': r['id'], 'title': r['title'], 'detail': r['content'][:140], 'href': '/admin/rules'} for r in rr]))

    # 9. Apps (Mileage and others): their approvals happen on the app's own page, with the full detail
    import apps
    aw = apps.waiting()
    out.append(_section('apps', 'Waiting in your apps', len(aw), '/admin/apps',
                        [{'type': 'link', 'id': f'app{n}', 'title': i['app'] + ': ' + i['title'], 'detail': i['detail'], 'href': i['href']}
                         for n, i in enumerate(aw)], 'Open the app to check and approve each one.' if aw else ''))

    # 10. Spending
    sp = rules_engine.spend_status()
    if sp['level'] in ('warning', 'blocked'):
        out.insert(0, _section('spend', 'Spending cap ' + ('reached' if sp['level'] == 'blocked' else 'warning'), 1, '/admin/rules',
                               [{'type': 'link', 'id': 'spend', 'title': f"${sp['today_usd']:.2f} today of ${sp['daily_usd']:.2f} · ${sp['month_usd']:.2f} this month of ${sp['monthly_usd']:.2f}",
                                 'detail': 'Chat is paused.' if sp['level'] == 'blocked' else 'Temple automations are paused until the next day or month, or until you raise the cap.',
                                 'href': '/admin/rules'}], level='bad' if sp['level'] == 'blocked' else 'warn'))
    total = sum(s['count'] for s in out if not s.get('info'))
    return {'total': total, 'sections': out, 'auto_on': auto_on}


def count():
    try: return summary()['total']
    except Exception: return 0
