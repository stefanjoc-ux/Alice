"""Everything waiting on the owner, in one place: counts, the top few items, and where to go for the rest."""
import json
from datetime import datetime, timezone
import substrate_store as store

import contextvars
TOP = 5
_FULL = contextvars.ContextVar('actions_full', default=False)     # approve_all needs every item, not the first few
APPROVE_ALL = ('decisions', 'held', 'waiting', 'taxonomy', 'replacements', 'suggestions', 'tags')


def _section(key, title, count, link, items=(), note='', level='normal', top=TOP, info=False):
    return {'key': key, 'title': title, 'count': count, 'link': link, 'items': list(items) if _FULL.get() else list(items)[:top],
            'note': note, 'level': level, 'info': info, 'approve_all': key in APPROVE_ALL and count > 0}


_CACHED = {}          # (dataset) -> (monotonic time, AUDIT_GEN, summary): the menu badges and Home reuse it briefly
CACHE_SECONDS = 15


def summary(cached=False):
    """Everything waiting. cached=True (the menu badges, Home, the Activity picture): the last answer is reused for up to
    CACHE_SECONDS while nothing has changed in this process (store.AUDIT_GEN); the Actions page itself always rebuilds."""
    import copy, time
    v = store.viewer()
    key = (store.DATASET.get(), v.oid if v is not None else '', store.SPACE.get())     # what each person sees is their own
    if cached and not _FULL.get():
        hit = _CACHED.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS and hit[1] == store.AUDIT_GEN[0]: return copy.deepcopy(hit[2])
    gen = store.AUDIT_GEN[0]
    out = _summary()
    if not _FULL.get(): _CACHED[key] = (time.monotonic(), gen, copy.deepcopy(out))
    return out


def _summary():
    import temple, knowledge, clients, rules_engine
    today = datetime.now(timezone.utc).date().isoformat()
    out = []

    import autoapprove, refs
    auto_on, held = autoapprove.on(), autoapprove.held()
    refs.ensure(fresh=False)

    # 1. Decisions: always yours, explained (why it is a decision, what it is for, Temple's recommendation)
    q = temple.queue('pending')
    # Approval goes to each space's managers (CR-4 phase 2): what belongs to a space the owner does not manage is theirs to decide,
    # on the Spaces page; here it is only counted (section 'space_managers' below).
    import spaces
    q['items'] = [i for i in q['items'] if not spaces.decided_by_others('record', i['id'])]
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
    drafts = [d for d in knowledge.listing(status='draft', limit=100000)['items'] if not spaces.decided_by_others('file', d['id'])]
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
                            'Held for a person under the rule Approval and library management: a clash with what Alice holds, a sensitive '
                            'finding, something Temple was unsure about or could not check, a category that needs a person, or a proposal '
                            'through the outside connector. Each says why.', top=20))
        w_items = ([_mem(i, 'Temple is checking it' if i['verdict'] == 'running' else '') for i in mems if ('memory', i['id']) not in held]
                   + [_draft(i) for i in drafts if ('knowledge', i['id']) not in held]
                   + [_fact(f) for f in facts if ('orgfact', f['id']) not in held])
        out.append(_section('waiting', 'Waiting for the automatic checks', len(w_items), '/admin/memories?status=proposed', w_items,
                            'Being checked now, or proposed before automatic approval was switched on. “Approve these automatically” '
                            'runs the same checks on them; anything that fails is held back for you.'))
    else:
        w_items = [_mem(i) for i in mems] + [_draft(i) for i in drafts] + [_fact(f) for f in facts]
        out.append(_section('waiting', 'Awaiting approval', len(w_items), '/admin/memories?status=proposed', w_items,
                            'Approval and library management says a person approves every new item: memories, knowledge and organisation facts wait for you.'))

    # 2-ii. What waits for other spaces' managers (counts only: theirs to decide; an Owner can step in on the Spaces page)
    try: sm = spaces.managers_summary()
    except Exception: sm = []
    out.append(_section('space_managers', 'Waiting for the managers of other spaces', sum(x['count'] for x in sm), '/admin/spaces',
                        [{'type': 'link', 'id': x['space'], 'title': f"{x['name']}: {x['count']} waiting", 'detail': 'Its managers decide on the Spaces page.',
                          'href': '/admin/spaces'} for x in sm],
                        'Approval goes to each space\'s managers. For your information: nothing here waits for you.' if sm else '', info=True))

    # 2c. Temple's category and tag housekeeping: changes waiting for you, and what it did itself (Undo for 7 days)
    import temple_taxonomy
    tx_wait = temple_taxonomy.changes('proposed', days=3650)
    out.append(_section('taxonomy', 'Category and tag changes to approve', len(tx_wait), '/admin/memories#organise',
                        [{'type': 'taxonomy', 'id': r['id'], 'title': r['summary'], 'detail': (r['why_waiting'] + ' ' if r['why_waiting'] else '') + r['reason']}
                         for r in tx_wait],
                        'Temple keeps categories and tags tidy. Changes to ones you created, or to a category a rule uses, wait for you.', top=20))
    # What Temple did on its own (approvals, categories, routing, merges, supersessions, archiving) is not listed here: Actions shows
    # only what waits for a person. It is on the Activity page as Temple's library actions, each with its reason and Undo (library.py).

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
        rc, ra = store.viewer_clause('record', 'r.id')
        mem_cat = [dict(r) for r in c.execute(
            "SELECT r.id,r.title,m.suggestion FROM record_meta m JOIN records r ON r.id=m.record_id LEFT JOIN memory_archive a ON a.record_id=r.id "
            "WHERE m.suggestion<>'' AND coalesce(a.state,r.status) IN ('approved','proposed')" + rc + "ORDER BY r.created_at DESC", ra)]
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
        kc, ka = store.viewer_clause('file', 'knowledge_meta.file_id')
        due_kn = [dict(r) for r in c.execute("SELECT file_id AS id,title,review_by,owner FROM knowledge_meta WHERE status='active' "
                                             "AND review_by IS NOT NULL AND review_by<?" + kc + "ORDER BY review_by", (today, *ka))]
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

    # 10. Digital teams: hand-offs, questions and sign-offs waiting for you, and Temple's suggested instructions
    try:
        import teams
        tw = teams.waiting()
    except Exception:
        tw = []
    if store.viewer() is not None: tw = [w for w in tw if not w.get('job_id') or store.can_see('team_job', w['job_id'])]
    out.append(_section('teams', 'Digital teams: waiting for you', len(tw), '/admin/teams', tw,
                        'Open an item for the full hand-off, and to discuss it with Temple.' if tw else '', top=10))

    # 10b. Shares the sharing check held (spaces.py): the item's author, the space's managers or an Owner decides, on the Spaces page.
    # Each one says why it cannot move yet; one held only for want of a category moves on its own once it has one.
    import spaces
    me = spaces._actor()
    sh = [h for h in spaces.held(me) if h['as'] in ('author', 'manager')]     # an Owner steps in on the Spaces page, not here
    AS = {'author': 'Your', 'manager': 'For a space you manage:', 'owner': 'As an Owner of Alice:'}
    out.append(_section('shares', 'Shares the sharing check held', len(sh), '/admin/spaces',
                        [{'type': 'link', 'id': h['id'], 'title': f"{h['title']} → {h['to_name'] or 'a shared space'}",
                          'detail': (f"Your {h['type_label']}" if h['as'] == 'author' else f"{AS[h['as']]} {h['author_name']}'s {h['type_label']}") +
                                    (' is waiting for a category: ' if h['needs_category'] else ' was held before it entered a shared space: ') +
                                    ' '.join(h['reasons'] or ['personal or private details.']),
                          'href': '/admin/spaces'} for h in sh],
                        'Before anything enters a shared space, Temple reviews it, then Alice and Temple check it for an actual finding: personal '
                        'data about a real person, special category data, or something marked private. Open Spaces to share one anyway or keep it '
                        'where it is (a manager or an Owner gives a reason). One waiting for a category moves on its own once it has one.' if sh else ''))

    # 10b2. The one-off sweep: work items stuck in your personal space (Temple lists them; nothing moves until you confirm)
    try:
        sw = spaces.sweep_list(me)
    except Exception:
        sw = None
    if sw and (sw['items'] or (not sw['scanned_at'] and sw['in_personal'])):
        out.append(_section('sweep', 'Work items in personal spaces', len(sw['items']) if sw['scanned_at'] else sw['in_personal'], '/admin/actions',
                            [{'type': 'sweep', 'id': r['id'], 'title': r['title'], 'detail': r['preview'], 'reason': r['reason'],
                              'target_name': r['target_name']} for r in sw['items']],
                            (f"Temple read your personal space and thinks these are about the work, not about you, and not sensitive. Move them to "
                             f"{sw['target_name'] or 'your team space'} so your team can find them; each still goes through the sharing check. "
                             f"Nothing moves until you say so." if sw['scanned_at'] else
                             f"{sw['in_personal']} items sit in your personal space. Ask Temple to look for the ones about the work, so they can go to "
                             f"{sw['target_name'] or 'your team space'}. Nothing moves until you confirm."), info=True) | {'sweep': sw})

    # 10b3. The move into the Organisation space (#42) waits for an Owner to preview and confirm it; until it has run it is
    # offered here, so it is not missed at the bottom of the Spaces page (10 Oct 2026: the Organisation space stayed empty).
    try:
        om = spaces.org_migration_offer() if me.full else None
    except Exception:
        om = None
    if om:
        c_ = om['counts']
        out.append(_section('org_move', 'Move shared material into the Organisation space', sum(c_.values()), '/admin/spaces#organisation',
                            [{'type': 'link', 'id': 'org-move', 'title': f"{c_['organisations']} organisations, {c_['knowledge']} general knowledge items "
                              f"and {c_['decisions']} decisions in {om['from_name']}", 'detail': 'Preview first: nothing moves until you confirm, and each '
                              'item goes through the sharing check.', 'href': '/admin/spaces#organisation'}],
                            'Everyone with an Alice role reads the Organisation space. It is empty until you move these from your work space.'))

    # 10c. Hand-over items the sharing check held (handover.py): an Owner decides, on Users and permissions
    try: ho = spaces.handover_held() if me.full and me.role == 'owner' else []
    except Exception: ho = []
    out.append(_section('handover', 'Hand-over items the sharing check held', len(ho), '/admin/users',
                        [{'type': 'link', 'id': h['id'], 'title': f"{h['title']} → {h['to_name'] or 'a shared space'}",
                          'detail': f"From {h['from_name']}'s personal space ({h['type_label']}). Held because: " + ' '.join(h['reasons'] or ['personal or private details.'])
                                    + (f" Your reason for handing it over: {h['note']}" if h.get('note') else ''),
                          'href': '/admin/users#handover=' + h['author_key']} for h in ho],
                        'When you hand over a departing person\'s work, each item goes through the same sharing check as any share. '
                        'These were held: open Users and permissions to share one anyway (with a reason) or keep it in their personal space.' if ho else ''))

    # 11. Research guidance Temple suggested in a discussion about a run: saved only when you approve it on the organisation's page
    try:
        from urllib.parse import quote
        import search_runs  # noqa: F401  (creates org_guidance)
        with store.db() as c:
            gp = [dict(r) for r in c.execute("SELECT id, org, reason FROM org_guidance WHERE status='proposed' ORDER BY created_at")]
    except Exception:
        gp = []
    out.append(_section('guidance', 'Research guidance Temple suggests', len(gp), '/admin/organisations',
                        [{'type': 'link', 'id': g['id'], 'title': g['org'] + ': suggested research guidance', 'detail': g['reason'],
                          'href': '/admin/organisations?org=' + quote(g['org'])} for g in gp],
                        'Approve or reject each one under Searches and guidance on the organisation\'s page.' if gp else ''))

    # 12. Spending
    sp = rules_engine.spend_status()
    if sp['level'] in ('warning', 'blocked'):
        out.insert(0, _section('spend', 'Spending cap ' + ('reached' if sp['level'] == 'blocked' else 'warning'), 1, '/admin/rules',
                               [{'type': 'link', 'id': 'spend', 'title': f"${sp['today_usd']:.2f} today of ${sp['daily_usd']:.2f} · ${sp['month_usd']:.2f} this month of ${sp['monthly_usd']:.2f}",
                                 'detail': 'Chat is paused.' if sp['level'] == 'blocked' else 'Temple automations are paused until the next day or month, or until you raise the cap.',
                                 'href': '/admin/rules'}], level='bad' if sp['level'] == 'blocked' else 'warn'))
    total = sum(s['count'] for s in out if not s.get('info'))
    import library
    return {'total': total, 'sections': out, 'auto_on': auto_on, 'approval': library.describe()}


def count():
    try: return summary(cached=True)['total']
    except Exception: return 0


def approve_all(key):
    """Stefan's Approve all on one section of Actions (6 Oct 2026): the same approval each item's own button gives, for every
    item in the section (not only those shown), each through its usual checks; anything a check refuses stays and is listed.
    Never for apps (mileage approvals stay per entry on the app's page), opportunities, agents or the information lists."""
    if key not in APPROVE_ALL: raise ValueError('That section cannot be approved all at once.')
    import knowledge, organisations, clients, temple_taxonomy, autoapprove
    t = _FULL.set(True)
    try: sec = next((x for x in summary()['sections'] if x['key'] == key), None)
    finally: _FULL.reset(t)
    if not sec or not sec['items']: return {'done': 0, 'failed': [], 'section': key}
    done, failed = 0, []
    def one(item, fn):
        nonlocal done
        try:
            r = fn()
            if isinstance(r, dict) and (r.get('blocked') or (r.get('errors') and not r.get('done'))):
                failed.append(f"{item.get('title', '')[:80]}: " + ' '.join(r.get('block_reasons') or r.get('errors') or ['not approved']))
            else: done += 1
        except Exception as e:
            failed.append(f"{item.get('title', '')[:80]}: {str(e)[:200]}")
    with store.acting(note='Approve all on Actions'):
        for i in sec['items']:
            ty = i.get('type')
            if ty in ('proposal', 'decision'): one(i, lambda i=i: store.review(i['id'], 'approved'))
            elif ty == 'draft': one(i, lambda i=i: knowledge.review([i['id']], 'approved'))
            elif ty == 'orgfact': one(i, lambda i=i: organisations.review_facts([i['id']], 'approved'))
            elif ty == 'taxonomy': one(i, lambda i=i: temple_taxonomy.decide(i['id'], 'approve', ''))
            elif ty == 'replacement': one(i, lambda i=i: knowledge.resolve_replacements([i['id']], 'accept'))
            elif ty == 'suggestion': one(i, lambda i=i: autoapprove.accept_suggestion(i['id'], i.get('content', '')))
            elif ty == 'category': one(i, lambda i=i: store.resolve_suggestions([i['id']], 'accept'))
            elif ty == 'kcategory': one(i, lambda i=i: knowledge.resolve_category_suggestions([i['id']], 'accept'))
            elif ty == 'client': one(i, lambda i=i: clients.resolve_suggestions([{'type': i['item_type'], 'id': i['id']}], 'accept'))
    with store.db() as c:
        store.audit(c, 'actions_approve_all', key, 'human_review', f"{sec['title']}: {done} approved" + (f", {len(failed)} not" if failed else ''))
    return {'done': done, 'failed': failed, 'section': key}
