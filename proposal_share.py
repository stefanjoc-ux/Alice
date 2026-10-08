"""Parker's proposals for your other models (Stefan's decision, 5 Oct 2026: every model gets the same access).

Through Alice's connector tools any model can list the proposals (written ones and forms in progress), read one in full (brief,
notes, sections, the draft, the rate card with cost, sell and margin, the pricing and Argus's latest points) and propose changes.
A model never changes a proposal itself: what it proposes is checked by the same code as Parker's own suggestions
(`proposal_starter._validate`: only templates, documents, roles and draft sections that exist) and kept with the proposal
(`context.model_suggestions`) until you Apply or Dismiss it on the Parker page, where Apply fills the form or changes the draft in
place exactly as a Parker turn does (with Undo). Client separation and the secret and protective-marking checks still apply to
what is returned; a proposal that fails them is left out and counted."""
import json, os
import re
import uuid

import substrate_store as store

MAX_PENDING = 10
REF = re.compile(r'^\s*P-?([0-9a-f]{6})\s*$', re.I)


def ref(pid):
    return 'P-' + pid[:6].upper()


def _rows(qa_only=False):
    with store.db() as c:
        vc, va = store.viewer_clause('proposal', 'p.id')        # a person without the Owner role: only their own
        rows = [dict(r) for r in c.execute("SELECT p.*, a.name AS writer_name FROM proposals p JOIN assistants a ON a.id=p.assistant_id "
                                           "WHERE p.status <> 'discarded'" + vc + "ORDER BY p.updated_at DESC", va)]
    return rows if qa_only else [r for r in rows if '"qa_only": true' not in (r.get('inputs') or '')]


def _bids():
    """{proposal id: (current id, the bid's members in order)} over every proposal (checks of your own documents included, so a
    chain through one is not broken)."""
    import proposal_bids as pb
    rows = _rows(qa_only=True)
    out = {}
    for cur, members in pb.trees(rows).items():
        ms = pb.ordered(members, cur)
        for m in ms: out[m['id']] = (cur, ms)
    return out


def _load(r):
    for k in ('inputs', 'draft', 'qa', 'pricing', 'context'):
        try: r[k] = json.loads(r.get(k) or ('[]' if k == 'qa' else '{}'))
        except ValueError: r[k] = [] if k == 'qa' else {}
    return r


STATUS = {'form': 'in progress (form, not written yet)', 'running': 'being written or checked now', 'done': 'written',
          'failed': 'failed (see error)'}


def listing(query='', limit=20):
    """One entry per bid: its current version, with the references of its earlier (superseded) versions."""
    words = [w for w in re.split(r'\s+', (query or '').lower().strip()) if w]
    out, bids = [], _bids()
    for r in _rows():
        if r.get('superseded_by'): continue                  # an earlier version: listed under its bid's current version
        cur, ms = bids.get(r['id'], (r['id'], [r]))
        earlier = [m for m in reversed(ms) if m['id'] != r['id']]
        hay = ' '.join([r['title'] or '', r['organisation'] or '', ref(r['id']).lower(), r['brief'] or '']
                       + [ref(m['id']).lower() + ' ' + (m.get('title') or '') for m in earlier]).lower()
        if any(w not in hay for w in words): continue
        r = _load(r)
        qa = r['qa'][-1] if r['qa'] else {}
        out.append({'proposal': ref(r['id']), 'title': r['title'] or 'Untitled proposal', 'organisation': r['organisation'] or '',
                    'client': r['client'] or '', 'status': STATUS.get(r['status'], r['status']), 'writer': r['writer_name'],
                    'template': (r['inputs'].get('template') or '').split('/')[-1] or "Alice's own layout",
                    'qa': (f"{qa.get('verdict', '').replace('_', ' ')} {qa.get('score')}/100" if qa else ''),
                    'sell_total': (r['pricing'] or {}).get('sell') if (r['pricing'] or {}).get('lines') else None,
                    'updated': (r['updated_at'] or '')[:16].replace('T', ' '),
                    'version': (lambda v: f"v{v['version']}" + (f" via {v['edited_via']}" if v['edited_via'] else ''))(proposals_version(r)),
                    'pending_model_suggestions': len([s for s in (r['context'].get('model_suggestions') or []) if s.get('state') == 'pending']),
                    'version_in_bid': len(ms), 'versions_in_bid': len(ms),
                    'earlier_versions': [{'proposal': ref(m['id']), 'title': m.get('title') or 'Untitled proposal', 'organisation': m.get('organisation') or '',
                                          'version_in_bid': i + 1} for i, m in reversed(list(enumerate(ms[:-1])))]})
        if len(out) >= limit: break
    return out


def find(key):
    """A proposal by its reference (P-1A2B3C), its id, or words from its title."""
    key = (key or '').strip()
    rows = _rows()
    m = REF.match(key)
    if m: hits = [r for r in rows if r['id'].startswith(m.group(1).lower())]
    elif re.fullmatch(r'[0-9a-f]{32}', key): hits = [r for r in rows if r['id'] == key]
    else:
        words = [w for w in key.lower().split() if w]
        hits = [r for r in rows if words and all(w in ((r['title'] or '') + ' ' + (r['organisation'] or '')).lower() for w in words)]
        hits = [r for r in hits if not r.get('superseded_by')] or hits       # versions of one bid share a title: the current one
    if not hits: raise LookupError(f'No proposal matches "{key[:80]}". Use list_proposals to see them.')
    if len(hits) > 1 and not m: raise LookupError('More than one proposal matches: ' + '; '.join(f'{ref(r["id"])} {r["title"]}' for r in hits[:8]) + '. Give the reference.')
    return _load(hits[0])


def _fixes(qa):
    """Argus's latest points as one plain list, as the Parker page shows them."""
    items = []
    for r in qa.get('requirements') or []:
        if r.get('status') != 'met':
            items.append({'kind': 'brief gap', 'what': f"The brief asks for {r.get('requirement', '')}: {'not covered' if r.get('status') == 'missing' else 'only partly covered'}",
                          'section': r.get('where', ''), 'change': r.get('note', '')})
    for i in qa.get('issues') or []:
        items.append({'kind': {'high': 'must fix', 'medium': 'should fix', 'low': 'polish'}.get(i.get('severity'), 'should fix'),
                      'what': i.get('issue', ''), 'section': i.get('section', ''), 'change': i.get('fix', '')})
    return items


def detail(key):
    import proposals
    p = find(key)
    inp, draft, ctx = p['inputs'], p['draft'] or {}, p['context'] or {}
    qa = p['qa'][-1] if p['qa'] else {}
    card = [{'role': r.get('role'), 'unit': r.get('unit', 'day'), 'ticked': r.get('use', True) is not False, 'days': r.get('days'),
             'cost_rate': r.get('cost'), 'sell_rate': r.get('sell'),
             'margin_pct': round((r['sell'] - r['cost']) / r['sell'] * 100, 1) if isinstance(r.get('sell'), (int, float)) and r.get('sell')
                           and isinstance(r.get('cost'), (int, float)) else None} for r in inp.get('rate_card') or []]
    pr = p['pricing'] or {}
    reqs = qa.get('requirements') or []
    secs = inp.get('sections') or []
    if not secs and not draft.get('sections'):                    # a form in progress: the sections its template will give
        try:
            import assistants
            secs = proposals.outline(assistants.get(p['assistant_id']), inp.get('template') or '')
        except (ValueError, LookupError): secs = []
    return {'proposal': ref(p['id']), 'title': p['title'], 'organisation': p['organisation'], 'client': p['client'],
            'status': STATUS.get(p['status'], p['status']), 'stage': p.get('stage') or '', 'error': p.get('error') or '',
            'brief': p['brief'], 'notes': p['notes'], 'structure': inp.get('structure', ''),     # older proposals only: no longer set
            'template': inp.get('template') or '', 'template_name': (inp.get('template') or '').split('/')[-1] or "Alice's own layout",
            'sections': [{'title': s.get('title'), 'guidance': s.get('guidance', ''), 'standard_text': bool(s.get('keep')),
                          'include': s.get('include', '')} for s in secs],
            'references': inp.get('references') or [],
            'draft': [{'title': s.get('title'), 'body': '' if s.get('keep') else s.get('body', ''), 'standard_text': bool(s.get('keep'))}
                      for s in draft.get('sections') or []],
            'gaps': draft.get('gaps') or [],
            'rate_card': card,
            'pricing': {'lines': [{'role': l['role'], 'quantity': l['quantity'], 'unit': l['unit'], 'sell_rate': l['sell_rate'], 'sell': l['sell'],
                                   'cost_rate': l['cost_rate'], 'cost': l['cost'], 'margin_pct': round(l['margin'], 1) if l.get('margin') is not None else None}
                                  for l in pr.get('lines') or []],
                        'sell_total': pr.get('sell'), 'cost_total': pr.get('cost'),
                        'margin_pct': round(pr['margin'], 1) if pr.get('margin') is not None else None, 'warnings': pr.get('warnings') or []},
            'qa': ({'verdict': qa.get('verdict', '').replace('_', ' '), 'score': qa.get('score'), 'summary': qa.get('summary', ''),
                    'brief_requirements_met': f"{sum(1 for r in reqs if r.get('status') == 'met')} of {len(reqs)}", 'what_to_fix': _fixes(qa)} if qa else None),
            'model_suggestions_pending': [{'id': s['id'], 'from': s['from'], 'note': s['note'], 'changes': s['changed']}
                                          for s in ctx.get('model_suggestions') or [] if s.get('state') == 'pending'],
            'page': page_link(p),
            'version': (lambda v: {'number': v['version'], 'edited_at': v['edited_at'], 'edited_via': v['edited_via']})(proposals_version(p)),
            'history': [{k: x.get(k) for k in ('v', 'at', 'via', 'what')} for x in (p['context'] or {}).get('history') or []][-10:],
            **_bid_detail(p),
            'how_to_change': (f'This version is superseded and read-only: suggest changes to the current version, {ref(_current(p))}, instead.'
                              if p.get('superseded_by') else 'Use propose_proposal_changes: changes wait on the Parker page for the user to apply.')}


def _current(p):
    return _bids().get(p['id'], (p['id'], []))[0]


def _bid_detail(p):
    cur, ms = _bids().get(p['id'], (p['id'], [p]))
    d = {'bid': {'versions': [{'proposal': ref(m['id']), 'version_in_bid': i + 1, 'current': m['id'] == cur} for i, m in enumerate(ms)],
                 'current_version': ref(cur)}}
    if p.get('superseded_by'):
        d['superseded'] = True
        d['superseded_by'] = ref(cur)
        d['superseded_note'] = (f'{ref(p["id"])} is an earlier version: it was superseded and is kept read-only. The current version '
                                f'of this bid is {ref(cur)}: use get_proposal {ref(cur)} for it.')
    return d


def suggest(key, note, updates, by):
    """A model's proposed changes, kept with the proposal for the user to Apply or Dismiss on the Parker page."""
    import proposals, proposal_starter as ps, rules_engine
    p = find(key)
    if p.get('superseded_by'):
        raise ValueError(f'{ref(p["id"])} is an earlier version: it was superseded by {ref(_current(p))} and is read-only. '
                         f'Suggest the changes to {ref(_current(p))} instead (get_proposal {ref(_current(p))} shows it).')
    if p['status'] == 'running': raise ValueError('This proposal is being written or checked right now: try again when it has finished.')
    note = ' '.join(str(note or '').split())[:1000]
    if not isinstance(updates, dict) or not updates: raise ValueError('Give at least one change in updates.')
    if 'structure' in updates or 'sections' in updates:            # since 7 Oct 2026: the template decides the sections
        raise ValueError('A proposal\'s sections come from its template (or Alice\'s own layout), so structure and new sections are '
                         'not accepted. Put what to emphasise in notes, or change the text of existing draft sections with draft.')
    rules_engine.check_outbound(note + '\n' + json.dumps(updates)[:60000], 'Parker', packs=False)   # secrets and markings never go in
    tpls, tpl_paths, refs_, ref_paths = ps._offer(p['client'] or '', p['assistant_id'])
    card = p['inputs'].get('rate_card') or []
    roles_known = {r['role'].casefold(): r['role'] for r in card if r.get('role')}
    draft = (p['draft'] or {}).get('sections') or []
    clean = ps._validate({'updates': updates}, tpl_paths, ref_paths, roles_known, p['organisation'] or '', draft)
    if not clean:
        raise ValueError('None of those changes could be used. Change only: title, organisation, brief, notes, template (a path from the '
                         'templates offered), references, roles (roles already on the rate card: role, use, days, sell) or '
                         'draft (existing, non-standard sections: title and body).')
    changed = [ps.NAMES[k] for k in clean]
    s = {'id': uuid.uuid4().hex[:12], 'from': ' '.join(str(by or 'a model').split())[:60], 'at': store.now(), 'note': note,
         'updates': clean, 'changed': changed, 'state': 'pending'}
    with store.db() as c:
        r = c.execute('SELECT context FROM proposals WHERE id=?', (p['id'],)).fetchone()
        ctx = json.loads(r['context'] or '{}') if r else {}
        pend = [x for x in ctx.get('model_suggestions') or []]
        ctx['model_suggestions'] = (pend + [s])[-30:]
        if len([x for x in ctx['model_suggestions'] if x.get('state') == 'pending']) > MAX_PENDING:
            raise ValueError(f'There are already {MAX_PENDING} suggestions waiting on this proposal: ask the user to apply or dismiss some first.')
        c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), p['id']))
        store.audit(c, 'proposal_change_suggested', p['id'], 'approval_required', f'{s["from"]} suggested changes to {ref(p["id"])} ({", ".join(changed)})')
    dropped = sorted(set(k for k in updates) - set(clean))
    have = {x.get('title', '').casefold() for x in clean.get('draft') or []}
    for d in updates.get('draft') or [] if isinstance(updates.get('draft'), list) else []:
        t = ' '.join(str((d or {}).get('title') or '').split())[:120] if isinstance(d, dict) else ''
        if t and t.casefold() not in have: dropped.append(f'draft: "{t}" (not an existing section of the draft that can be changed; new sections cannot be added)')
    link = page_link(p)
    return {'proposal': ref(p['id']), 'suggestion': s['id'], 'changes': changed, 'left_out': dropped, 'open': link,
            'message': (f'Saved for the user, not applied yet. To see it: open {link}' if link.startswith('http') else
                        f'Saved for the user, not applied yet. To see it: on the Parker page, open {ref(p["id"])} from Proposals'
                        ' (it shows a suggestions badge)') + ', then Apply or Dismiss it in Parker\'s panel.'}


def proposals_version(p):
    import proposals
    return proposals.version_of(p, p['context'] or {})


def page_link(p):
    """Where the user opens this proposal on the Parker page (a full link when ALICE_PUBLIC_URL is set)."""
    return os.environ.get('ALICE_PUBLIC_URL', '').rstrip('/') + '/assistant/' + p['assistant_id'] + '?p=' + p['id']


def _suggestion(c, aid, pid, sid):
    r = c.execute('SELECT context,status FROM proposals WHERE id=? AND assistant_id=?', (pid, aid)).fetchone()
    if not r: raise LookupError('No such proposal.')
    ctx = json.loads(r['context'] or '{}')
    hit = next((x for x in ctx.get('model_suggestions') or [] if x.get('id') == sid), None)
    if not hit: raise LookupError('No such suggestion.')
    return ctx, hit, r['status']


def _mark(aid, pid, sid, **f):
    with store.db() as c:
        ctx, hit, _ = _suggestion(c, aid, pid, sid)
        hit.update(f)
        c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), pid))
    return hit


def decide(aid, pid, sid, action):
    """The user applied or dismissed a model's suggestion. On a proposal in progress the page applies it to the form, which saves
    itself; on a written proposal Alice stores its changes straight away (proposals.save_applied: checked like save_form, roles
    repriced, the draft marked as changed since Argus last checked)."""
    import proposals
    if action not in ('applied', 'dismissed'): raise ValueError('Apply or dismiss.')
    with store.db() as c:
        _, hit, st = _suggestion(c, aid, pid, sid)
    if hit.get('state') != 'pending': return {'state': hit['state']}
    res = {'state': action}
    if action == 'applied' and st != 'form':
        saved, before, left = proposals.save_applied(aid, pid, hit.get('updates') or {}, hit.get('from') or 'a model')
        now = store.now()
        _mark(aid, pid, sid, state='applied', decided_at=now, saved_at=now, on_written=True, saved=saved, before=before)
        with store.db() as c:
            store.audit(c, 'proposal_change_applied', pid, 'human_review', f'{hit["from"]}: {", ".join(saved)} (saved)')
        return dict(res, saved=saved, left_out=left, proposal=proposals.get(pid))
    with store.db() as c:
        ctx, hit, st = _suggestion(c, aid, pid, sid)
        if hit.get('state') != 'pending': return {'state': hit['state']}
        hit['state'], hit['decided_at'] = action, store.now()
        c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), pid))
        if action == 'applied':
            proposals.note_version(c, pid, hit['from'], f'Applied changes suggested by {hit["from"]} in the form: ' + ', '.join(hit['changed'])
                                   + ' (saved with the form)', 'applied')
        store.audit(c, 'proposal_change_' + action, pid, 'human_review', f'{hit["from"]}: {", ".join(hit["changed"])}')
    return res


def undo(aid, pid, sid):
    """Undo an applied suggestion on a written proposal: the stored values it replaced are put back (not just the form)."""
    import proposals
    with store.db() as c:
        _, hit, _ = _suggestion(c, aid, pid, sid)
    if hit.get('state') != 'applied' or not hit.get('saved_at') or not hit.get('before'):
        raise ValueError('Only a suggestion Alice saved on a written proposal can be undone here.')
    names = hit.get('saved') or hit.get('changed') or []
    proposals.undo_saved(aid, pid, hit['before'], hit.get('from') or 'a model',
                         f'Undid the changes suggested by {hit.get("from") or "a model"}: the stored ' + proposals._and(names) + ' put back as they were')
    _mark(aid, pid, sid, state='undone', undone_at=store.now(), saved_at='', before=None)
    return {'state': 'undone', 'proposal': proposals.get(pid)}


def _same(a, b): return ' '.join(str(a or '').split()) == ' '.join(str(b or '').split())


def _missing(p, u):
    """Which of a suggestion's changes are not in the stored proposal (keys of updates)."""
    import proposals
    inp, card = p['inputs'] or {}, {r['role'].casefold(): r for r in (p['inputs'] or {}).get('rate_card') or [] if r.get('role')}
    out = []
    for k, v in u.items():
        if k in ('title', 'brief', 'notes') and not _same(p.get(k), v): out.append(k)
        elif k == 'organisation' and str(p.get('organisation') or '').casefold() != str(v or '').casefold(): out.append(k)
        elif k == 'structure' and not _same(inp.get('structure'), proposals.structure_text(v)): out.append(k)
        elif k == 'references' and set(inp.get('references') or []) != set(v or []): out.append(k)
        elif k == 'roles':
            for g in v or []:
                r = card.get(str(g.get('role') or '').casefold())
                if g.get('use') is False:
                    if r and r.get('use', True): out.append(k); break
                elif not r or (g.get('days') and r.get('days') != g['days']) or (g.get('sell') and r.get('sell') != g['sell']):
                    out.append(k); break
        elif k == 'draft':
            have = {s['title']: s.get('body') for s in (p['draft'] or {}).get('sections') or []}
            if any(d['title'] in have and not _same(have[d['title']], d.get('body')) for d in v or []): out.append(k)
    return out


def lost(p):
    """Suggestions marked applied on a written proposal whose changes never reached the stored proposal (before Apply saved, the
    page only changed the form): each with the changes still missing, so the page can offer Re-apply. A change counts as missing
    only if nothing later (another saved suggestion, Check again) saved that field."""
    if p.get('status') in ('form', 'running', 'discarded') or p.get('superseded_by') or (p.get('inputs') or {}).get('qa_only'): return []
    ctx = p.get('context') or {}
    written = next((x.get('at') for x in ctx.get('history') or [] if isinstance(x, dict) and x.get('kind') == 'written'), None)
    if not written: return []
    later = ctx.get('saved_fields_at') or {}
    out = []
    for s in ctx.get('model_suggestions') or []:
        if s.get('state') != 'applied' or s.get('saved_at') or s.get('left_as_is'): continue
        at = s.get('decided_at') or ''
        if not (s.get('on_written') or at > written): continue          # applied in the form before it was written: saved with the form
        miss = [k for k in _missing(p, s.get('updates') or {}) if (later.get(k) or '') <= at]
        if miss:
            import proposal_starter as ps
            out.append({'id': s['id'], 'from': s.get('from') or 'a model', 'note': s.get('note') or '', 'applied_at': at,
                        'missing': miss, 'names': [ps.NAMES.get(k, k) for k in miss]})
    return sorted(out, key=lambda x: x['applied_at'])


def reapply(aid, pid, sid):
    """Re-apply an applied suggestion whose changes were never stored, from the suggestion itself (no need to ask the model again)."""
    import proposals
    p = proposals.get(pid)
    if p['assistant_id'] != aid: raise LookupError('No such proposal.')
    hit = next((x for x in lost(p) if x['id'] == sid), None)
    if not hit: raise ValueError('Nothing to re-apply: these changes are already in the saved proposal.')
    with store.db() as c:
        _, s, _ = _suggestion(c, aid, pid, sid)
    ups = {k: v for k, v in (s.get('updates') or {}).items() if k in hit['missing']}
    saved, before, _ = proposals.save_applied(aid, pid, ups, hit['from'], again=True, applied_at=hit['applied_at'])
    _mark(aid, pid, sid, saved_at=store.now(), reapplied=True, saved=saved, before=before)
    return {'state': 'applied', 'saved': saved, 'proposal': proposals.get(pid)}


def leave(aid, pid, sid):
    """Leave a lost change out on purpose: no more Re-apply for it."""
    _mark(aid, pid, sid, left_as_is=store.now())
    with store.db() as c:
        store.audit(c, 'proposal_change_left_out', pid, 'human_review', f'Suggestion {sid[:12]} left as it is (not re-applied)')
    return {'state': 'left'}
