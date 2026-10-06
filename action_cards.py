"""Information cards for the items waiting on Actions (Stefan, 6 Oct 2026: "to approve and reject with this limited data would be
hard"): a memory or decision, a knowledge draft, an organisation fact and Temple's category and tag changes each open as a standard
information card (see CLAUDE.md, Information cards) with the full content, where it came from, why it waits, Temple's review and the
items it was compared with, plus Discuss with Temple (`temple_discuss`, keyed by `key()`) while it still waits.

Keys: r-<record id> (memory or decision), k-<file id> (knowledge), o-<fact id> (organisation fact), t-<change id> (taxonomy), or a
reference (M-0001, D-0001, K-0001) for items reached from a card's Related list."""
import json
import re

import substrate_store as store

KEY = re.compile(r'^([rkot])-([0-9a-f]{6,40})$')
REF = re.compile(r'^[MDK]-\d{4,6}$')
DISCUSS = '/admin/api/review-items/{key}/discussion'


def split(key):
    """('record'|'knowledge'|'orgfact'|'taxonomy', id) for a card key or a reference."""
    key = (key or '').strip()
    m = KEY.match(key)
    if m: return {'r': 'record', 'k': 'knowledge', 'o': 'orgfact', 't': 'taxonomy'}[m.group(1)], m.group(2)
    if REF.match(key.upper()):
        import refs
        t, i = refs.find(key.upper())
        if t == 'record': return 'record', i
        if t == 'file': return 'knowledge', i
    raise ValueError('No such item.')


def card(key):
    kind, iid = split(key)
    return {'record': _record, 'knowledge': _knowledge, 'orgfact': _orgfact, 'taxonomy': _taxonomy}[kind](iid)


def _sec(key, title, **kw):
    return {'key': key, 'title': title, **{k: v for k, v in kw.items() if v not in (None, '', [])}}


def _held(item_type, iid):
    import autoapprove
    return autoapprove.held().get((item_type, iid), '')


def _discuss(key, starters):
    return {'url': DISCUSS.format(key=key), 'starters': starters}


# ---------------- memories and decisions ----------------
def _record(rid):
    import temple, refs, clients, memory_tags
    with store.db() as c:
        r = c.execute("SELECT r.*, coalesce(a.state, r.status) AS state, coalesce(m.category,'') AS category FROM records r "
                      "LEFT JOIN memory_archive a ON a.record_id=r.id LEFT JOIN record_meta m ON m.record_id=r.id WHERE r.id=?", (rid,)).fetchone()
        if not r: raise ValueError('That memory no longer exists.')
        r = dict(r)
        revs = [dict(v) for v in c.execute('SELECT * FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC, id', (rid,))]
    kind = store.record_kinds([rid]).get(rid) or {}
    is_dec = kind.get('kind') == 'decision'
    ref = refs.of('record', [rid]).get(rid, '')
    latest = revs[0] if revs else None
    done = latest and latest['status'] == 'complete'
    report = latest['report'] if done else ''
    ctx = json.loads(latest['context'] or '{}') if latest else {}
    compared = {m['id']: m for m in ctx.get('compared_memories') or [] if m.get('id')}
    cited = [compared[i] for i in dict.fromkeys(temple.ID_PATTERN.findall(report)) if i in compared]
    related = cited or list(compared.values())[:8]
    rrefs = refs.of('record', [m['id'] for m in related])
    titles = {m['id']: m.get('title', '') for m in related}
    nice = lambda text: re.sub(temple.ID_PATTERN, lambda m: '“' + titles[m.group(0)] + '”' if m.group(0) in titles else m.group(0), text or '')
    verdict = temple.verdict(latest)
    replaces = temple.REPLACES.search(report or '')
    tags = memory_tags.tags_for([rid]).get(rid, {})
    client = clients.clients_for('memory', [rid]).get(rid, '')
    pending = r['state'] == 'proposed'
    held = _held('memory', rid)
    what = r['content']
    rows = [('Category', r['category'] or 'None yet'), ('Tags', ', '.join(t['name'] for t in tags.get('tags', [])) or 'None'),
            ('Client', client or 'General (no client)'), ('Status', {'proposed': 'Waiting for you', 'approved': 'Approved'}.get(r['state'], r['state'].capitalize()))]
    if is_dec:
        d = kind.get('decision') or store.parse_decision(r['content'])
        what = d.get('decision') or r['content']
        rows = [('Reason given', d.get('rationale') or ''), ('Options considered', ' · '.join(o for o in d.get('options') or [] if o)),
                ('Revisit', ' · '.join(x for x in [d.get('revisit') or '', ('by ' + d['review_by']) if d.get('review_by') else ''] if x))] + rows
    why = [('Held back because', held)] if held else []
    why += [("Temple recommends", {'approve': 'Approve', 'clarify': 'Clarify first', 'reject': 'Reject', 'running': 'Still checking',
                                   'unreviewed': 'Not reviewed yet', 'failed': 'Could not check it'}.get(verdict, 'See the review'))]
    if done: why.append(('In short', nice(temple.reason_line(report))))
    if replaces and replaces.group(1) in titles: why.append(('Replaces', titles[replaces.group(1)]))
    elif replaces: why.append(('Replaces', 'an older memory (see the review)'))
    secs = [_sec('what', 'Decision' if is_dec else 'What it says', text=what, rows=rows),
            _sec('who', 'Who and where from', rows=[('Proposed by', r['source']), ('Proposed', {'time': r['created_at']})]),
            _sec('why', 'Why it waits, and what Temple thinks', rows=why)]
    if report: secs.append(_sec('why', "Temple's full review", text=nice(report)[:6000], collapsed=True))
    secs.append(_sec('related', 'What Temple compared it with', items=[{'ref': rrefs.get(m['id'], ''), 'label': m.get('title', ''), 'time': ''}
                                                                         for m in related if rrefs.get(m['id'])],
                     empty='Temple did not find anything close to it.'))
    secs.append(_sec('technical', 'Technical', rows=[('ID', rid), ('Reviews', str(len(revs)))], collapsed=True))
    out = {'ref': ref, 'kind': 'review', 'kind_label': ('Decision' if is_dec else 'Memory') + (' waiting for you' if pending else ''),
           'title': r['title'], 'subtitle': ('Held back: ' + held) if held else '', 'badge': ref,
           'tone': 'warn' if verdict in ('clarify', 'failed') else 'bad' if verdict == 'reject' else '', 'sections': secs,
           'actions': [{'label': 'Open in Memories', 'href': '/admin/memories?q=' + (ref or rid)}]}
    if pending:
        out['discuss'] = _discuss('r-' + rid, ['What does it overlap with?', 'Is anything in it wrong or out of date?',
                                               'Should I approve it as it is?'])
    return out


# ---------------- knowledge drafts ----------------
def _knowledge(fid):
    import knowledge, refs, clients
    m = knowledge.meta([fid]).get(fid)
    if not m: raise ValueError('That knowledge item no longer exists.')
    with store.db() as c:
        f = c.execute('SELECT name, text, size FROM files WHERE id=?', (fid,)).fetchone()
    ref = refs.of('file', [fid]).get(fid, '')
    reps = [p for p in knowledge.replacements('pending', new_id=fid)]
    olds = refs.of('file', [p['old_id'] for p in reps])
    held = _held('knowledge', fid)
    text = (f['text'] if f else '') or ''
    pending = m['status'] == 'draft'
    kinds = getattr(knowledge, 'KINDS', {})
    secs = [_sec('what', 'What it says', text=text[:8000] + ('\n\n… (shortened here: the full item is on the Knowledge page)' if len(text) > 8000 else ''),
                 rows=[('Kind', kinds.get(m['kind'], m['kind'])), ('Category', m.get('category') or 'None yet'), ('Label', m.get('label') or ''),
                       ('Client', clients.clients_for('file', [fid]).get(fid, '') or 'General (no client)')]),
            _sec('who', 'Who and where from', rows=[('Added by', m.get('added_by') or ''), ('Source', m.get('source') or ''), ('Added', {'time': m['created_at']})]),
            _sec('why', 'Why it waits', rows=[('Held back because', held or ('Waiting for the automatic checks' if pending else ''))]
                 + [('Would replace', '“' + p['old_title'] + '”' + (' (' + p['reason'] + ')' if p.get('reason') else '')) for p in reps]),
            _sec('related', 'Older items it would replace', items=[{'ref': olds.get(p['old_id'], ''), 'label': p['old_title'], 'time': ''}
                                                                   for p in reps if olds.get(p['old_id'])], empty='It replaces nothing.'),
            _sec('technical', 'Technical', rows=[('ID', fid), ('File', f['name'] if f else ''), ('Size', f'{f["size"]:,} bytes' if f else '')], collapsed=True)]
    out = {'ref': ref, 'kind': 'review', 'kind_label': 'Knowledge draft' if pending else 'Knowledge', 'title': m['title'], 'badge': ref,
           'subtitle': ('Held back: ' + held) if held else '', 'tone': '', 'sections': secs,
           'actions': [{'label': 'Open in Knowledge', 'href': '/admin/knowledge?q=' + (ref or fid)}]}
    if pending:
        out['discuss'] = _discuss('k-' + fid, ['Summarise it in three lines', 'Does it clash with anything Alice holds?',
                                               'Is anything in it sensitive or client material?'])
    return out


# ---------------- organisation facts ----------------
def _orgfact(oid):
    import organisations
    with store.db() as c:
        f = c.execute('SELECT * FROM org_facts WHERE id=?', (oid,)).fetchone()
    if not f: raise ValueError('That organisation fact no longer exists.')
    f = dict(f)
    held = _held('orgfact', oid)
    src = [('Source', f['source_system'])] + ([('Reference', {'text': f['source_ref'][:120], 'href': f['source_ref']} if f['source_ref'].startswith('https://')
                                                else f['source_ref'][:300])] if f['source_ref'] else [])
    secs = [_sec('what', 'The fact', text=f['statement'], rows=[('Organisation', f['org']),
                                                                ('Section', organisations.SECTION_NAMES.get(f['section'], f['section'])),
                                                                ('As of', f['as_of']), ('Review by', f['review_by'])]),
            _sec('who', 'Who and where from', rows=[('Proposed by', f['proposed_by'] or '')] + src + [('Proposed', {'time': f['created_at']})]),
            _sec('why', 'Why it waits', rows=[('Held back because', held or 'Waiting for the automatic checks')]),
            _sec('technical', 'Technical', rows=[('ID', oid), ('Label', f['label'])], collapsed=True)]
    out = {'ref': '', 'kind': 'review', 'kind_label': 'Organisation fact', 'title': f['org'] + ' · ' + organisations.SECTION_NAMES.get(f['section'], f['section']),
           'subtitle': ('Held back: ' + held) if held else '', 'tone': '', 'sections': secs,
           'actions': [{'label': 'Open the organisation', 'href': '/admin/organisations?org=' + f['org']}]}
    if f['status'] == 'proposed':
        out['discuss'] = _discuss('o-' + oid, ['Does the source support this?', 'Does it clash with what Alice holds on them?'])
    return out


# ---------------- Temple's category and tag changes ----------------
def _taxonomy(tid):
    import temple_taxonomy, refs
    with store.db() as c:
        r = c.execute('SELECT * FROM taxonomy_changes WHERE id=?', (tid,)).fetchone()
        if not r: raise ValueError('That change no longer exists.')
        r = dict(r)
        d = json.loads(r['detail'] or '{}')
        name = d.get('name') or d.get('into') or r['target']
        members = list(d.get('members') or [])
        if not members and name:      # the memories it affects now: those in the category or with the tag
            q = ('SELECT record_id FROM record_meta WHERE category=?' if r['kind'] == 'category'
                 else "SELECT record_id FROM record_tags WHERE tag=? AND assigned_by IN ('human','temple')")
            names = [name] + list(d.get('from') or [])
            for n in dict.fromkeys(names): members += [x[0] for x in c.execute(q, (n,))]
        titles = {x['id']: x['title'] for x in c.execute(
            f"SELECT id, title FROM records WHERE id IN ({','.join('?' * len(members[:60])) or 'NULL'})", members[:60])} if members else {}
    r['detail'] = d
    mrefs = refs.of('record', list(titles))
    rows = [('Change', temple_taxonomy.describe(r)), ('Applies to', r['kind'].capitalize() + ' “' + r['target'] + '”')]
    if d.get('description'): rows.append(('New description', d['description']))
    if d.get('new_name'): rows.append(('New name', d['new_name']))
    if d.get('parts'): rows.append(('Split into', ' · '.join(p['name'] for p in d['parts'])))
    if d.get('area'): rows.append(('Area', d['area']))
    secs = [_sec('what', 'What Temple wants to change', rows=rows),
            _sec('why', 'Why', rows=[("Temple's reason", r['reason']), ('Why it waits for you', r['why_waiting']),
                                    ('Confidence', f"{round(100 * float(d['confidence']))}%" if d.get('confidence') is not None else '')]),
            _sec('who', 'Who', rows=[('Suggested by', 'Temple'), ('Suggested', {'time': r['created_at']})]),
            _sec('related', f'Memories it affects ({len(members)})', items=[{'ref': mrefs[i], 'label': titles.get(i, ''), 'time': ''}
                                                                         for i in members[:40] if i in mrefs],
                 empty='No memories are moved by this change.'),
            _sec('technical', 'Technical', rows=[('ID', tid), ('Operation', r['op']), ('State', r['state'])], collapsed=True)]
    out = {'ref': '', 'kind': 'review', 'kind_label': 'Category and tag change', 'title': temple_taxonomy.describe(r), 'tone': '',
           'subtitle': r['why_waiting'], 'sections': secs, 'actions': [{'label': 'Open Memories', 'href': '/admin/memories#organise'}]}
    if r['state'] == 'proposed':
        out['discuss'] = _discuss('t-' + tid, ['What would change for my memories?', 'Is there a better name?', 'What happens if I reject it?'])
    return out
