"""Handing over a departing person's work (Stefan, 9 Oct 2026; Users and permissions › Hand over).

When someone is suspended in Alice, or loses their Alice role in Entra, their personal space stays private and untouched.
An Owner (the Owner role) may hand over what is in it:
  - list it by type, titles only (memories, decisions, knowledge, organisations, proposals, teams, team jobs, pricing
    templates); the content is shown only when the Owner opens one item, and each opening is logged;
  - tick items and choose a shared space the Owner manages; give the reason; each ticked item then goes through the sharing
    gate (spaces.gate: the rule share_gate on the Rules page, then Temple), exactly as any share does. An item with no
    category confirmed by a person can be given one here first (that is the Owner's confirmation, logged as usual).
  - what the gate holds waits on Actions ("Hand-over items the sharing check held") with its reasons, for an Owner to share
    after all (with a reason) or keep in the person's personal space.
Nothing is deleted, nothing moves unless ticked, the person's account and history stay, and every step is logged with who
and why. Chats and generated documents are never in spaces and are not handed over.
"""
import substrate_store as store
import spaces

TYPES = ('record', 'file', 'organisation', 'proposal', 'team', 'team_job', 'pricing_template')
GROUP = {'memory': 'Memories', 'decision': 'Decisions', 'file': 'Knowledge', 'organisation': 'Organisations', 'proposal': 'Proposals',
         'team': 'Digital teams', 'team_job': 'Team jobs', 'pricing_template': 'Pricing templates'}
MAX_ITEMS = 200


def _actor():
    return store.viewer() or spaces._local()


def _owner_only():
    v = _actor()
    if not (v.full and v.role == 'owner'): raise PermissionError('Only an Owner of Alice can hand over someone\'s work.')
    return v


def _person(oid):
    import users
    p = users.person(oid)
    if not p: raise LookupError('No such person. They appear here after their first sign-in.')
    return p


def departing(p):
    """Why this person's work may be handed over ('' = it may not: they are still active with a role, or an owner)."""
    import users
    if users.is_owner(p['oid'], row=p): return ''
    if p['status'] == 'suspended': return 'Suspended in Alice'
    if users.use_app_roles() and not p.get('entra_role'): return 'No Alice role in Entra any more'
    return ''


def _eligible(oid):
    import users
    p = _person(oid)
    if users.is_owner(p['oid'], row=p): raise PermissionError('An owner of Alice\'s work is never handed over here.')
    why = departing(p)
    if not why:
        raise PermissionError(f'{p["name"] or p["email"] or oid} is still active in Alice. Suspend them first (or take their role away in Entra); '
                              'their personal space stays private until then.')
    return p, why


def _rows(key):
    with store.db() as c:
        return [(r[0], r[1]) for r in c.execute('SELECT item_type, item_id FROM item_spaces WHERE space_id=? ORDER BY placed_at',
                                                (spaces.personal_space(key),))]


def counts(people):
    """{oid: number of items in their personal space} for everyone in people (users.listing rows) whose work may be handed over."""
    out = {}
    for p in people:
        if departing(p):
            with store.db() as c:
                out[p['oid']] = c.execute('SELECT count(*) FROM item_spaces WHERE space_id=?', (spaces.personal_space(p['oid']),)).fetchone()[0]
    return out


def listing(oid):
    """The person's personal-space items by type, titles only, the shared spaces the Owner may hand over to, the categories,
    and what an earlier hand-over left waiting."""
    import refs
    v = _owner_only()
    p, why = _eligible(oid)
    key = p['oid']
    rows = _rows(key)
    rec_ids = [i for t, i in rows if t == 'record']
    kinds = store.record_kinds(rec_ids)
    rr, fr = refs.of('record', rec_ids), refs.of('file', [i for t, i in rows if t == 'file'])
    groups = {}
    for t, i in rows:
        try: title, _, classified, private = spaces._item(t, i)
        except LookupError: continue
        g = ('decision' if (kinds.get(i) or {}).get('kind') == 'decision' else 'memory') if t == 'record' else t
        groups.setdefault(g, []).append({'type': t, 'id': i, 'title': title[:200], 'ref': rr.get(i) or fr.get(i) or '',
                                         'classified': classified if t in ('record', 'file') else True, 'private': private})
    nm = spaces.names()
    targets = [{'id': sid, 'name': nm[sid]['name'], 'client': nm[sid]['client']} for sid, role in spaces.my_spaces(v).items()
               if role == 'manage' and (nm.get(sid) or {}).get('kind') == 'shared']
    with store.db() as c:
        cats = [r[0] for r in c.execute('SELECT name FROM categories ORDER BY lower(name)')]
    return {'person': {'oid': key, 'name': p['name'], 'email': p['email'], 'status': p['status'], 'why': why},
            'groups': [{'key': g, 'label': GROUP[g], 'items': groups[g]} for g in GROUP if g in groups],
            'total': sum(len(x) for x in groups.values()), 'spaces': targets, 'categories': cats,
            'held': spaces.handover_held(key),
            'note': 'Titles only. Open an item to read it (each opening is logged). Chats and generated documents stay theirs and are not handed over.'}


def open_item(oid, item_type, item_id):
    """One item's content, for the Owner deciding whether to hand it over. Logged (who opened whose item), never sent anywhere."""
    _owner_only()
    p, _ = _eligible(oid)
    if item_type not in TYPES: raise ValueError('That kind of item does not live in a space.')
    if spaces.space_of(item_type, item_id) != spaces.personal_space(p['oid']): raise LookupError('That item is not in their personal space.')
    title, text, classified, private = spaces._item(item_type, item_id)
    with store.db() as c:
        store.audit(c, 'handover_item_opened', str(item_id), 'spaces',
                    f'{spaces.TYPE_LABEL[item_type]} "{title[:120]}" in {p["name"] or p["email"] or p["oid"]}\'s personal space, opened to decide a hand-over')
    return {'type': item_type, 'id': item_id, 'title': title, 'text': text[:20000], 'classified': classified, 'private': private}


def _note(note):
    import rules_engine
    note = ' '.join((note or '').split())[:500]
    if len(note) < 3: raise ValueError('Say why you are handing these over (for example: "Mira left on 9 October; her bid notes go to the Bid team").')
    rules_engine.check_file(note, 'hand-over reason')         # no secrets or protective markings kept in the log
    return note


def move(oid, items, space, note, categories=None):
    """Hand over the ticked items (and only those) into a shared space the Owner manages. Each passes the sharing gate; an
    unclassified memory or knowledge item may be given a category here first (the Owner's confirmation). Returns what moved,
    what was held (and why) and what was refused."""
    _owner_only()
    p, why = _eligible(oid)
    note = _note(note)
    items = [x for x in (items or []) if isinstance(x, dict)][:MAX_ITEMS]
    if not items: raise ValueError('Tick at least one item to hand over.')
    if not space: raise ValueError('Choose the shared space to hand them over to.')
    tgt = spaces._space(space)
    if tgt['kind'] != 'shared' or spaces.role_in(_actor(), space) != 'manage':
        raise PermissionError('Hand work over only into a shared space you manage.')
    categories = categories or {}
    out = {'moved': [], 'held': [], 'refused': []}
    for it in items:
        t, i = str(it.get('type', '')), str(it.get('id', ''))
        if t not in TYPES or not i:
            out['refused'].append({'type': t, 'id': i, 'title': '', 'reasons': ['Not something that lives in a space.']}); continue
        try:
            cat = ' '.join(str(categories.get(i) or '').split())[:40]
            if cat and t in ('record', 'file') and spaces.space_of(t, i) == spaces.personal_space(p['oid']) and not spaces._item(t, i)[2]:
                with store.acting(note=note):
                    if t == 'record': store.set_category([i], cat)
                    else:
                        import knowledge
                        knowledge.update(i, category=cat)
            r = spaces.hand_over(t, i, space, p['oid'], note)
        except (LookupError, ValueError) as e:
            out['refused'].append({'type': t, 'id': i, 'title': '', 'reasons': [str(e)]}); continue
        out[r['status'] if r['status'] in out else 'refused'].append({'type': t, 'id': i, 'title': r.get('title', ''), 'reasons': r.get('reasons', [])})
    with store.db() as c, store.acting(note=note):
        store.audit(c, 'handover_run', p['oid'], 'spaces', f'{p["name"] or p["email"] or p["oid"]} ({why.lower()}): {len(out["moved"])} handed over, '
                    f'{len(out["held"])} held by the sharing check, {len(out["refused"])} refused')
    spaces.forget()
    return out


def decide(mid, action, note=''):
    """An Owner's decision on a held hand-over item (Actions, or the person's Hand over panel)."""
    _owner_only()
    if action == 'share': note = _note(note)
    else: note = ' '.join((note or '').split())[:500]
    return spaces.decide_handover(mid, action, note)
