"""Bids and versions of Parker's proposals (Stefan, 7 Oct 2026).

A bid is a chain of versions of one proposal; its current version is the one nobody superseded. The link is two columns on
`proposals` (added in proposals.py): `superseded_by` (the proposal that replaced this one; '' = current) is the truth, and `bid_id`
(the id of the bid's first version; '' = a bid of its own) is kept in step by `_rebid` so a bid can be found by one value.

Links are only ever made by the user, never by matching titles:
  - Save as a new version (or writing from a written proposal) records `started_from`: the new proposal joins that bid and
    supersedes its current version as soon as it is first saved or written (`join`);
  - Make this replace... on a proposal: the user picks the current versions of other bids, which become its earlier versions (`link`);
  - Restore as a separate proposal undoes it (`restore`), and removing a proposal in progress that superseded others restores them.
Both sides are recorded in the version history ("Replaces P-540A70", "Superseded by P-6A32CB", when and who).

A superseded version is retired, not deleted: read-only (`refuse`), shown as "Superseded by P-..." with a link to the current version.
Its pending model suggestions move to the current version (`_carry`), each re-checked there with Parker's own rules
(proposal_starter._validate, as proposal_share.suggest); what no longer fits is listed on the suggestion as "No longer applies here",
never dropped. The user still applies or dismisses each one on the Parker page."""
import json

import proposals as P
import substrate_store as store

MAX_LINK = 20


def ref(pid): return 'P-' + (pid or '')[:6].upper()


def _rows(c, aid):
    return [dict(r) for r in c.execute("SELECT id,assistant_id,title,organisation,client,status,superseded_by,bid_id,created_at "
                                       "FROM proposals WHERE assistant_id=? AND status!='discarded'", (aid,))]


def trees(rows):
    """Group rows into bids: {current id: [members]}. A pointer to a row that is not there ends the chain (that row is current)."""
    by = {r['id']: r for r in rows}

    def cur(i):
        seen = set()
        while (by[i].get('superseded_by') or '') in by and i not in seen:
            seen.add(i); i = by[i]['superseded_by']
        return i
    out = {}
    for r in rows: out.setdefault(cur(r['id']), []).append(r)
    return out


def ordered(members, current):
    """The versions in order: earlier ones by when they were started, the current version last."""
    early = sorted((m for m in members if m['id'] != current), key=lambda m: (m.get('created_at') or '', m['id']))
    return early + [m for m in members if m['id'] == current]


def _bid_rows(c, pid):
    """(current id, the bid's members in order, all rows of that writer) for one proposal."""
    r = c.execute('SELECT assistant_id FROM proposals WHERE id=?', (pid,)).fetchone()
    if not r: raise LookupError('No such proposal.')
    rows = _rows(c, r['assistant_id'])
    for cur, members in trees(rows).items():
        if any(m['id'] == pid for m in members): return cur, ordered(members, cur), rows
    return pid, [], rows                                  # a discarded proposal: on its own


def current_id(pid):
    with store.db() as c: return _bid_rows(c, pid)[0]


def info(pid):
    """The bid around one proposal, for the Parker page and the connector tools."""
    with store.db() as c:
        cur, members, _ = _bid_rows(c, pid)
        me = c.execute('SELECT superseded_by FROM proposals WHERE id=?', (pid,)).fetchone()
    vers = [{'id': m['id'], 'ref': ref(m['id']), 'version': i + 1, 'title': m['title'] or 'Untitled proposal', 'status': m['status'],
             'current': m['id'] == cur} for i, m in enumerate(members)]
    pos = next((v['version'] for v in vers if v['id'] == pid), 1)
    sup = (me['superseded_by'] if me else '') or ''
    return {'current': cur, 'current_ref': ref(cur), 'is_current': not sup, 'version': pos, 'versions': vers,
            'superseded_by': sup, 'superseded_by_ref': ref(sup) if sup else ''}


def refuse(p, doing='changed'):
    """A superseded version is read-only: say so and name the current version."""
    if (p.get('superseded_by') or ''):
        cur = current_id(p['id'])
        raise ValueError(f'{ref(p["id"])} was superseded by {ref(cur)} and is kept read-only, so it cannot be {doing}. '
                         f'Work on {ref(cur)} instead, or restore {ref(p["id"])} as a separate proposal first.')


def _rebid(c, aid):
    """Keep bid_id in step with the links: the id of the bid's first version for every member; '' for a proposal on its own."""
    rows = _rows(c, aid)
    for cur, members in trees(rows).items():
        first = ordered(members, cur)[0]['id'] if len(members) > 1 else ''
        for m in members:
            if (m.get('bid_id') or '') != first: c.execute('UPDATE proposals SET bid_id=? WHERE id=?', (first, m['id']))


# ---------------- suggestions carried over to the current version ----------------
def _offers(p):
    """What the target version offers, worked out before any write transaction (it reads documents and imports modules)."""
    import proposal_starter as ps, organisations, clients            # noqa: F401  (imported here, never inside a transaction)
    _, tpl_paths, _, ref_paths = ps._offer(p['client'] or '', p['assistant_id'])
    card = (p['inputs'] or {}).get('rate_card') or []
    return {'tpl_paths': tpl_paths, 'ref_paths': ref_paths, 'roles': {r['role'].casefold(): r['role'] for r in card if r.get('role')},
            'org': p['organisation'] or '', 'draft': (p['draft'] or {}).get('sections') or []}


def recheck(updates, off):
    """A suggestion's changes checked against another version, as proposal_share.suggest checks them: (what still applies,
    what no longer applies here, in plain words)."""
    import proposal_starter as ps
    clean = ps._validate({'updates': updates or {}}, off['tpl_paths'], off['ref_paths'], off['roles'], off['org'], off['draft'])
    gone, writable = [], [d for d in off['draft'] if not d.get('keep')]
    for k, v in (updates or {}).items():
        kept = clean.get(k)
        if k == 'draft' and isinstance(v, list):
            have = {d['title'].casefold() for d in kept or []}
            for d in v:
                t = str((d or {}).get('title') or '').strip()
                if t and t.casefold() not in have:
                    gone.append(f'Draft section “{t}”: ' + ('this version has no written draft yet' if not writable
                                                                    else 'not a section of this version’s draft'))
        elif k == 'roles' and isinstance(v, list):
            have = {r['role'].casefold() for r in kept or []}
            for r in v:
                t = str((r or {}).get('role') or '').strip()
                if t and t.casefold() not in have: gone.append(f'Role “{t}”: not on this version’s rate card')
        elif k == 'references' and isinstance(v, list):
            have = {ps._slash(x) for x in kept or []}
            for x in v:
                if ps._slash(x) not in have: gone.append(f'Reference document “{ps._slash(x).split("/")[-1]}”: not offered for this version')
        elif k == 'template' and not kept:
            gone.append(f'Template “{ps._slash(v).split("/")[-1] or v}”: not offered for this version')
        elif kept is None:
            gone.append(f'{ps.NAMES.get(k, k).capitalize()}: could not be used on this version')
    return clean, gone


def _moved(s, target, off, src_ref, src_version):
    """A pending suggestion as it lands on the target version: re-checked there, marked where it was written."""
    import proposal_starter as ps
    orig = (s.get('carried_from') or {}).get('updates') or s.get('updates') or {}
    origin = s.get('carried_from') or {'id': s.get('origin_id') or '', 'ref': src_ref, 'version': src_version, 'updates': orig}
    if origin.get('id') == target:                          # back where it was written: exactly as it was
        x = {k: v for k, v in s.items() if k not in ('carried_from', 'no_longer')}
        x.update(updates=orig, changed=[ps.NAMES[k] for k in orig if k in ps.NAMES], state='pending')
        return x
    clean, gone = recheck(orig, off)
    return dict(s, updates=clean, changed=[ps.NAMES[k] for k in clean], no_longer=gone, state='pending',
                carried_from=dict(origin, at=store.now()))


def _pending(ctx): return [x for x in ctx.get('model_suggestions') or [] if x.get('state') == 'pending']


def _write_ctx(c, pid, fn):
    r = c.execute('SELECT context FROM proposals WHERE id=?', (pid,)).fetchone()
    try: ctx = json.loads(r['context'] or '{}') if r else {}
    except ValueError: ctx = {}
    fn(ctx)
    c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), pid))


def _carry(c, src, target, moved):
    """Move the pending suggestions in `moved` (already re-checked) from src to target, inside the caller's transaction."""
    if not moved: return 0
    ids = {m['id'] for m in moved}

    def out(ctx):
        for x in ctx.get('model_suggestions') or []:
            if x.get('id') in ids and x.get('state') == 'pending': x.update(state='carried', carried_to=target, decided_at=store.now())

    def into(ctx):
        lst = [x for x in ctx.get('model_suggestions') or [] if x.get('id') not in ids]
        ctx['model_suggestions'] = (lst + moved)[-60:]
    _write_ctx(c, src, out); _write_ctx(c, target, into)
    return len(moved)


# ---------------- linking and undoing ----------------
def _plan(aid, target, olds):
    """Before writing: the target, its offers, and for each proposal to be superseded its pending suggestions re-checked there."""
    t = P.get(target)
    if t['assistant_id'] != aid or t['status'] == 'discarded': raise LookupError('No such proposal.')
    with store.db() as c:
        _, _, rows = _bid_rows(c, target)
    tr = trees(rows)
    bid_of = {m['id']: cur for cur, ms in tr.items() for m in ms}
    merged = [m for cur in {bid_of.get(o) for o in olds} | {bid_of.get(target)} for m in tr.get(cur, [])]
    pos = {m['id']: i + 1 for i, m in enumerate(ordered(merged, target))}
    off = _offers(t)
    moves = {}
    for o in olds:
        src = P.get(o)
        moves[o] = [_moved(dict(s, origin_id=s.get('origin_id') or o), target, off, ref(o), pos.get(o, 1)) for s in _pending(src['context'] or {})]
    return t, moves


def link(aid, pid, olds, via='Parker page', record_new=True, starting=False):
    """Make `pid` replace the proposals in `olds` (each the current version of another bid): they and their earlier versions
    become its earlier versions. Their pending suggestions move to `pid`, re-checked there."""
    olds = list(dict.fromkeys(str(o or '').strip()[:40] for o in (olds or []) if str(o or '').strip()))
    if not olds: raise ValueError('Pick at least one proposal for this one to replace.')
    if len(olds) > MAX_LINK: raise ValueError(f'Pick at most {MAX_LINK} proposals at a time.')
    me = P.get(pid)
    if me['assistant_id'] != aid or me['status'] == 'discarded': raise LookupError('No such proposal.')
    refuse(me, 'made to replace another proposal')
    if me['status'] == 'running' and not starting: raise ValueError('This proposal is being written or checked right now: wait for it to finish.')
    with store.db() as c:
        cur_me, members, _ = _bid_rows(c, pid)
    mine = {m['id'] for m in members}
    for o in olds:
        try: x = P.get(o)
        except LookupError: raise LookupError(f'No proposal {ref(o)}.') from None
        if x['assistant_id'] != aid or x['status'] == 'discarded': raise LookupError(f'No proposal {ref(o)}.')
        if o in mine: raise ValueError(f'{ref(o)} is already a version of this bid.')
        if x.get('superseded_by'): raise ValueError(f'{ref(o)} is already superseded by {ref(current_id(o))}: pick the current version of that bid.')
        if x['status'] == 'running': raise ValueError(f'{ref(o)} is being written or checked right now: wait for it to finish.')
    t, moves = _plan(aid, pid, olds)
    carried = 0
    with store.db() as c:
        for o in olds:
            n = c.execute("UPDATE proposals SET superseded_by=?,updated_at=? WHERE id=? AND superseded_by=''", (pid, store.now(), o)).rowcount
            if not n: raise ValueError(f'{ref(o)} changed while you were linking it: try again.')
            P.note_version(c, o, via, f'Superseded by {ref(pid)}', 'superseded')
            if record_new: P.note_version(c, pid, via, f'Replaces {ref(o)}', 'linked')
            carried += _carry(c, o, pid, moves.get(o) or [])
        _rebid(c, aid)
        store.audit(c, 'proposal_versions_linked', pid, 'human_review', f'{ref(pid)} replaces ' + ', '.join(ref(o) for o in olds)
                    + (f'; {carried} suggestion(s) carried over' if carried else ''))
    return {'id': pid, 'replaces': [ref(o) for o in olds], 'carried': carried, 'bid': info(pid)}


def join(aid, pid, started_from, via='Parker page', record_new=False, starting=False):
    """A new version started from another proposal (Save as a new version, or writing from a written proposal): it supersedes the
    current version of that bid. Returns the reference it replaced, or ''."""
    sf = str(started_from or '').strip()[:40]
    if not sf or sf == pid: return ''
    try: x = P.get(sf)
    except LookupError: return ''
    if x['assistant_id'] != aid or x['status'] == 'discarded': return ''
    cur = current_id(sf)
    if cur == pid or P.get(cur)['status'] == 'running': return ''
    link(aid, pid, [cur], via, record_new, starting)
    return ref(cur)


def restore(aid, pid, via='Parker page', reason=''):
    """Restore a superseded version as a separate proposal: it (with its own earlier versions) becomes a bid of its own again.
    Suggestions that were carried from it and are still waiting go back with it."""
    p = P.get(pid)
    if p['assistant_id'] != aid or p['status'] == 'discarded': raise LookupError('No such proposal.')
    sup = p.get('superseded_by') or ''
    if not sup: raise ValueError(f'{ref(pid)} is not superseded: it is already the current version of its bid.')
    with store.db() as c:
        cur, _, rows = _bid_rows(c, pid)
    # what comes away with it: pid and every version that leads to it
    by = {r['id']: r for r in rows}
    sub = {pid} | {r['id'] for r in rows if _leads_to(by, r['id'], pid)}
    back = []
    if cur not in sub:
        p2 = dict(p, superseded_by='')
        off = _offers(p2)
        back = [_moved(s, pid, off, ref(cur), 0) for s in _pending(P.get(cur)['context'] or {})
                if (s.get('carried_from') or {}).get('id') in sub]
    with store.db() as c:
        c.execute("UPDATE proposals SET superseded_by='',updated_at=? WHERE id=?", (store.now(), pid))
        P.note_version(c, pid, via, reason or f'Restored as a separate proposal (was superseded by {ref(sup)})', 'restored')
        P.note_version(c, sup, via, f'No longer replaces {ref(pid)}' + (' (that version was restored as a separate proposal)' if not reason else ''), 'linked')
        n = _carry(c, cur, pid, back) if back else 0
        _rebid(c, aid)
        store.audit(c, 'proposal_version_restored', pid, 'human_review', f'{ref(pid)} restored as a separate proposal (was superseded by {ref(sup)})'
                    + (f'; {n} suggestion(s) went back with it' if n else ''))
    return {'id': pid, 'returned': len(back), 'bid': info(pid)}


def _leads_to(by, i, target):
    seen = set()
    while i in by and i not in seen:
        if i == target: return True
        seen.add(i); i = by[i].get('superseded_by') or ''
    return i == target


def on_discard(aid, pid):
    """A proposal in progress that superseded others is being removed: the versions it replaced become current again."""
    with store.db() as c:
        olds = [r['id'] for r in c.execute("SELECT id FROM proposals WHERE superseded_by=? AND assistant_id=? AND status!='discarded'", (pid, aid))]
    for o in olds:
        restore(aid, o, reason=f'Current again: {ref(pid)}, which had replaced it, was removed')
    return len(olds)


# ---------------- the Proposals list: one row per bid ----------------
def grouped(rows):
    """Summary rows (proposals.summary_row) as bids: the current version, its earlier versions, the AI cost across all of them.
    Each row also gets its place in the bid (bid_version, bid_versions)."""
    out = []
    for cur, members in trees(rows).items():
        ms = ordered(members, cur)
        for i, m in enumerate(ms): m.update(bid_version=i + 1, bid_versions=len(ms), bid_current=cur)
        c = ms[-1]
        total = round(sum(float(m.get('ai_cost') or 0) for m in ms), 6)
        out.append({'bid': ms[0]['id'] if len(ms) > 1 else c['id'], 'current': c['id'], 'organisation': c.get('organisation') or '',
                    'earlier': [m['id'] for m in reversed(ms[:-1])], 'versions': len(ms), 'ai_cost_total': total,
                    'ai_cost_current': float(c.get('ai_cost') or 0), 'group': c.get('group') or '',
                    'activity_at': c.get('activity_at') or c.get('updated_at') or ''})
    out.sort(key=lambda b: b['activity_at'], reverse=True)
    return out
