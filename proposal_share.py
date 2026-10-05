"""Parker's proposals for your other models (Stefan's decision, 5 Oct 2026: every model gets the same access).

Through Alice's connector tools any model can list the proposals (written ones and forms in progress), read one in full (brief,
notes, sections, the draft, the rate card with cost, sell and margin, the pricing and Argus's latest points) and propose changes.
A model never changes a proposal itself: what it proposes is checked by the same code as Parker's own suggestions
(`proposal_starter._validate`: only templates, documents, roles and draft sections that exist) and kept with the proposal
(`context.model_suggestions`) until you Apply or Dismiss it on the Parker page, where Apply fills the form or the draft's edit
boxes exactly as a Parker turn does (with Undo). Client separation and the secret and protective-marking checks still apply to
what is returned; a proposal that fails them is left out and counted."""
import json
import re
import uuid

import substrate_store as store

MAX_PENDING = 10
REF = re.compile(r'^\s*P-?([0-9a-f]{6})\s*$', re.I)


def ref(pid):
    return 'P-' + pid[:6].upper()


def _rows():
    with store.db() as c:
        return [dict(r) for r in c.execute("SELECT p.*, a.name AS writer_name FROM proposals p JOIN assistants a ON a.id=p.assistant_id "
                                           "WHERE p.status <> 'discarded' AND coalesce(p.inputs,'') NOT LIKE '%\"qa_only\": true%' "
                                           "ORDER BY p.updated_at DESC")]


def _load(r):
    for k in ('inputs', 'draft', 'qa', 'pricing', 'context'):
        try: r[k] = json.loads(r.get(k) or ('[]' if k == 'qa' else '{}'))
        except ValueError: r[k] = [] if k == 'qa' else {}
    return r


STATUS = {'form': 'in progress (form, not written yet)', 'running': 'being written or checked now', 'done': 'written',
          'failed': 'failed (see error)'}


def listing(query='', limit=20):
    words = [w for w in re.split(r'\s+', (query or '').lower().strip()) if w]
    out = []
    for r in _rows():
        hay = ' '.join([r['title'] or '', r['organisation'] or '', ref(r['id']).lower(), r['brief'] or '']).lower()
        if any(w not in hay for w in words): continue
        r = _load(r)
        qa = r['qa'][-1] if r['qa'] else {}
        out.append({'proposal': ref(r['id']), 'title': r['title'] or 'Untitled proposal', 'organisation': r['organisation'] or '',
                    'client': r['client'] or '', 'status': STATUS.get(r['status'], r['status']), 'writer': r['writer_name'],
                    'template': (r['inputs'].get('template') or '').split('/')[-1] or "Alice's own layout",
                    'qa': (f"{qa.get('verdict', '').replace('_', ' ')} {qa.get('score')}/100" if qa else ''),
                    'sell_total': (r['pricing'] or {}).get('sell') if (r['pricing'] or {}).get('lines') else None,
                    'updated': (r['updated_at'] or '')[:16].replace('T', ' '),
                    'pending_model_suggestions': len([s for s in (r['context'].get('model_suggestions') or []) if s.get('state') == 'pending'])})
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
    return {'proposal': ref(p['id']), 'title': p['title'], 'organisation': p['organisation'], 'client': p['client'],
            'status': STATUS.get(p['status'], p['status']), 'stage': p.get('stage') or '', 'error': p.get('error') or '',
            'brief': p['brief'], 'notes': p['notes'], 'structure': inp.get('structure', ''),
            'template': inp.get('template') or '', 'template_name': (inp.get('template') or '').split('/')[-1] or "Alice's own layout",
            'sections': [{'title': s.get('title'), 'guidance': s.get('guidance', ''), 'standard_text': bool(s.get('keep')),
                          'include': s.get('include', '')} for s in inp.get('sections') or []],
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
            'page': '/assistant/' + p['assistant_id'] + '?p=' + p['id'],
            'how_to_change': 'Use propose_proposal_changes: changes wait on the Parker page for the user to apply.'}


def suggest(key, note, updates, by):
    """A model's proposed changes, kept with the proposal for the user to Apply or Dismiss on the Parker page."""
    import proposals, proposal_starter as ps, rules_engine
    p = find(key)
    if p['status'] == 'running': raise ValueError('This proposal is being written or checked right now: try again when it has finished.')
    note = ' '.join(str(note or '').split())[:1000]
    if not isinstance(updates, dict) or not updates: raise ValueError('Give at least one change in updates.')
    rules_engine.check_outbound(note + '\n' + json.dumps(updates)[:60000], 'Parker', packs=False)   # secrets and markings never go in
    tpls, tpl_paths, refs_, ref_paths = ps._offer(p['client'] or '', p['assistant_id'])
    card = p['inputs'].get('rate_card') or []
    roles_known = {r['role'].casefold(): r['role'] for r in card if r.get('role')}
    draft = (p['draft'] or {}).get('sections') or []
    clean = ps._validate({'updates': updates}, tpl_paths, ref_paths, roles_known, p['organisation'] or '', draft)
    if not clean:
        raise ValueError('None of those changes could be used. Change only: title, organisation, brief, notes, template (a path from the '
                         'templates offered), structure, references, roles (roles already on the rate card: role, use, days, sell) or '
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
    return {'proposal': ref(p['id']), 'suggestion': s['id'], 'changes': changed,
            'left_out': dropped, 'message': 'Saved for the user: it waits on the Parker page until they Apply or Dismiss it.'}


def decide(aid, pid, sid, action):
    """The user applied or dismissed a model's suggestion (the page applies it to the form itself)."""
    if action not in ('applied', 'dismissed'): raise ValueError('Apply or dismiss.')
    with store.db() as c:
        r = c.execute('SELECT context FROM proposals WHERE id=? AND assistant_id=?', (pid, aid)).fetchone()
        if not r: raise LookupError('No such proposal.')
        ctx = json.loads(r['context'] or '{}')
        hit = next((x for x in ctx.get('model_suggestions') or [] if x.get('id') == sid), None)
        if not hit: raise LookupError('No such suggestion.')
        if hit.get('state') != 'pending': return {'state': hit['state']}
        hit['state'], hit['decided_at'] = action, store.now()
        c.execute('UPDATE proposals SET context=? WHERE id=?', (json.dumps(ctx), pid))
        store.audit(c, 'proposal_change_' + action, pid, 'human_review', f'{hit["from"]}: {", ".join(hit["changed"])}')
    return {'state': action}
