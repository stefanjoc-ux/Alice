"""Approval and library management (Stefan's decisions D-0042, D-0044 and D-0045, 10 Oct 2026).

The rule "Approval and library management" (id approval_required, Memory governance, Core) on the Rules page replaced "Human
approval". Its settings, never code, decide:
- who approves new memories, decisions and knowledge: Temple under each space's rules (approver 'temple', the default), a person for
  every item ('person', the old behaviour) or a person for the categories chosen in the decision policy ('categories');
- what Temple may do on its own (temple_may): approve, categorise (and tag), route, merge, supersede, archive;
- whether models and Temple may overwrite or delete library items (overwrite_delete, off): off, every attempt is refused and logged
  (guard), the raw captured item is always kept, and merged or superseded items link to it;
- what is always held for a person (hold): sensitive findings, clashes, anything Temple is unsure about.
Switched off, Temple manages nothing: every new item waits for a person.

Every change Temple makes to the library is a library action (table library_actions): what, which items, the reason, who, when, and
each item exactly as it was before and after (records, record_meta, memory_archive, record_tags, item_spaces, knowledge_meta,
org_facts). Logged in Activity ('library_<action>', with the reason) and listed on the Activity page, where Undo puts back exactly
what that action changed (undo)."""
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import substrate_store as store

RULE = 'approval_required'
LABELS = {'approve': 'Approved', 'categorise': 'Categorised', 'route': 'Routed', 'merge': 'Merged', 'supersede': 'Superseded',
          'archive': 'Archived', 'keep': 'Kept private'}
TYPE_LABEL = {'record': 'Memory', 'file': 'Knowledge item', 'orgfact': 'Organisation fact', 'taxonomy': 'Category or tag'}
UNDO_DAYS = 30

# What an item is, table by table: (table, column naming the item, fixed conditions, primary key columns).
SNAP = {
    'record': [('records', 'id', {}, ('id',)), ('record_meta', 'record_id', {}, ('record_id',)),
               ('memory_archive', 'record_id', {}, ('record_id',)), ('record_tags', 'record_id', {}, ('record_id', 'tag')),
               ('item_spaces', 'item_id', {'item_type': 'record'}, ('item_type', 'item_id'))],
    'file': [('knowledge_meta', 'file_id', {}, ('file_id',)), ('item_spaces', 'item_id', {'item_type': 'file'}, ('item_type', 'item_id'))],
    'orgfact': [('org_facts', 'id', {}, ('id',))],
}
APPROVAL_TYPE = {'record': 'memory', 'file': 'knowledge', 'orgfact': 'orgfact'}
# Bookkeeping, not the item: when Temple last looked, and its suggestions (which change nothing until someone accepts them).
# Left out of snapshots, so an undo never makes Temple look again or brings a suggestion back.
IGNORE = {'temple_checked_at', 'tags_checked_at', 'category_checked_at', 'suggestion', 'suggestion_reason', 'category_suggestion',
          'category_reason', 'confidence', 'category_confidence'}


def _schema():
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS library_actions (
            id TEXT PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL, item_type TEXT NOT NULL, item_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', items TEXT NOT NULL DEFAULT '[]',
            before TEXT NOT NULL DEFAULT '{}', after TEXT NOT NULL DEFAULT '{}', actor TEXT NOT NULL DEFAULT '',
            link TEXT NOT NULL DEFAULT '', undone_at TEXT, undone_by TEXT NOT NULL DEFAULT '', undo_note TEXT NOT NULL DEFAULT '')''')
        c.execute('CREATE INDEX IF NOT EXISTS library_actions_at ON library_actions(at)')
        c.execute('CREATE INDEX IF NOT EXISTS library_actions_item ON library_actions(item_type, item_id)')


_schema()


# ---------------- the setting ----------------
def settings():
    """The rule as features use it: {on, approver, temple_may{...}, overwrite_delete, hold{...}}."""
    import rules_engine
    r = rules_engine.rule(RULE)
    p = rules_engine.clean_approval((r or {}).get('params') or {})
    on = bool(r['enabled']) if r else True
    if not on:          # switched off: Temple manages nothing, every new item waits for a person
        p = {'approver': 'person', 'temple_may': {k: False for k in p['temple_may']}, 'overwrite_delete': False,
             'hold': {k: True for k in p['hold']}}
    return {'on': on, **p}


def temple_approves():
    s = settings()
    return s['approver'] != 'person' and s['temple_may']['approve']


def may(action):
    """Temple may do this on its own (approve, categorise, route, merge, supersede, archive)."""
    return bool(settings()['temple_may'].get(action))


def holds(kind):
    """This is held for a person (sensitive, clash, unsure)."""
    return bool(settings()['hold'].get(kind, True))


def person_categories():
    """Categories whose new items need a person (approver 'categories': the decision policy's categories)."""
    if settings()['approver'] != 'categories': return set()
    import autoapprove
    return {k.lower() for k in autoapprove.policy()['categories']}


def needs_person(category):
    return bool(category) and category.lower() in person_categories()


def describe():
    """One plain sentence for connector instructions and tool descriptions, from the current setting."""
    s = settings()
    held = [n for k, n in (('clash', 'clashes with what Alice holds'), ('sensitive', 'sensitive findings about a person'),
                           ('unsure', 'anything Temple is unsure about')) if s['hold'][k]]
    held_text = (' ' + _cap(_join(held)) + ' wait for a person (the managers of its space, or the user in their personal space).') if held else ''
    if s['approver'] == 'person' or not s['temple_may']['approve']:
        return ('Every new memory, decision and knowledge note waits for a person to approve it (the managers of its space, or the user '
                'in their personal space); Temple checks it first.')
    cats = sorted(person_categories()) if s['approver'] == 'categories' else []
    import autoapprove
    names = [k for k in autoapprove.policy()['categories'] if k.lower() in cats]
    return ('Temple checks every new memory, decision and knowledge note and approves it under the rules of the space it goes to'
            + (f', except items in {_join(names)}, which wait for a person' if names else '') + '.' + held_text)


def _cap(s): return s[:1].upper() + s[1:]


def _join(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1] if xs else ''


# ---------------- overwrite and delete ----------------
def machine():
    """Who is acting is a model or Temple, not a person: inside an agent run, a proposal through a connector, or Alice herself."""
    import agents, autoapprove
    return bool(agents.current() or autoapprove.outside() or store.actor() in ('Alice', 'Temple'))


def guard(action, item_type, item_id, title=''):
    """Before a model or Temple overwrites or deletes a library item. With overwrite and delete off (the default) the attempt is
    refused and logged by the rule; a person's own edits are never stopped here."""
    if not machine(): return
    import agents, autoapprove, rules_engine
    who = autoapprove.outside() or ('Temple' if agents.current() else store.actor())
    what = f'{TYPE_LABEL.get(item_type, item_type).lower()} "{(title or str(item_id))[:120]}"'
    if settings()['overwrite_delete']:
        with store.db() as c:
            store.audit(c, f'library_{action}', str(item_id), RULE, f'{who} {action} {what} (allowed by Approval and library management)')
        return
    rules_engine.log_block(RULE, title or str(item_id), f'{who} tried to {action} {what}: refused, overwrite and delete are off')
    raise rules_engine.RuleViolation(f'Refused by Approval and library management: models and Temple may not {action} library items. '
                                     'The original is kept; propose a new item instead (it can supersede the old one).')


# ---------------- snapshots ----------------
def _cols(c, table):
    try: return [r['name'] for r in c.execute(f'PRAGMA table_info({table})')]
    except Exception: return []


def snapshot(items):
    """{'record:<id>': {table: {pk: row}}} for each (item_type, item_id)."""
    out = {}
    with store.db() as c:
        have = {}
        for t, i in items:
            snap = {}
            for table, col, fixed, pk in SNAP.get(t, []):
                if table not in have: have[table] = bool(_cols(c, table))
                if not have[table]: continue
                where = ' AND '.join([f'{col}=?'] + [f'{k}=?' for k in fixed])
                rows = [{k: v for k, v in dict(r).items() if k not in IGNORE}
                        for r in c.execute(f'SELECT * FROM {table} WHERE {where}', (str(i), *fixed.values()))]
                if table == 'record_tags': rows = [r for r in rows if r.get('assigned_by') in ('human', 'temple')]
                snap[table] = {json.dumps([r[k] for k in pk]): r for r in rows}
            out[f'{t}:{i}'] = snap
    return out


def _restore(c, key, before, after):
    """Put back exactly what changed between before and after for one item (what changed since, elsewhere, is left alone)."""
    t, i = key.split(':', 1)
    for table, col, fixed, pk in SNAP.get(t, []):
        b, a = (before.get(table) or {}), (after.get(table) or {})
        for k in set(b) | set(a):
            rb, ra = b.get(k), a.get(k)
            if rb == ra: continue
            keyvals = json.loads(k)
            where = ' AND '.join(f'{p}=?' for p in pk)
            if rb is None:
                c.execute(f'DELETE FROM {table} WHERE {where}', keyvals)
            elif ra is None or not c.execute(f'SELECT 1 FROM {table} WHERE {where}', keyvals).fetchone():
                cols = list(rb)
                c.execute(f'DELETE FROM {table} WHERE {where}', keyvals)
                c.execute(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" * len(cols))})', [rb[x] for x in cols])
            else:
                diff = [x for x in rb if rb.get(x) != ra.get(x)]
                if diff: c.execute(f'UPDATE {table} SET {",".join(f"{x}=?" for x in diff)} WHERE {where}', [rb[x] for x in diff] + keyvals)


# ---------------- recording what Temple did ----------------
def _title(t, i):
    with store.db() as c:
        try:
            if t == 'record': r = c.execute('SELECT title FROM records WHERE id=?', (i,)).fetchone()
            elif t == 'file': r = c.execute('SELECT title FROM knowledge_meta WHERE file_id=?', (i,)).fetchone()
            else: r = c.execute("SELECT org || ': ' || statement FROM org_facts WHERE id=?", (i,)).fetchone()
        except Exception:
            r = None
    return (r[0] if r else '') or ''


def _record(action, items, before, after, reason, title='', link='', who=''):
    aid = uuid.uuid4().hex[:16]
    t, i = items[0]
    title = title or _title(t, i)
    reason = ' '.join((reason or '').split())[:500]
    with store.acting(who or 'Temple', note=reason or None):
        with store.db() as c:
            c.execute('INSERT INTO library_actions(id,at,action,item_type,item_id,title,reason,items,before,after,actor,link) '
                      'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      (aid, store.now(), action, t, str(i), title[:200], reason, json.dumps([f'{a}:{b}' for a, b in items]),
                       json.dumps(before, default=str), json.dumps(after, default=str), who or 'Temple', link))
            store.audit(c, f'library_{action}', str(i), RULE,
                        f'{LABELS.get(action, action)} {TYPE_LABEL.get(t, t).lower()} "{title[:120]}"' + (f': {reason}' if reason else ''))
    return aid


@contextmanager
def change(action, items, reason='', title='', per_item=False):
    """with library.change('approve', [('record', rid)], why): ... — records what the body changed, as one library action (or one
    per changed item with per_item; reason may then be {item_id: reason}). Nothing changed, or the body failed: nothing recorded.
    Never call it inside a write transaction (it reads before and after)."""
    items = [(t, str(i)) for t, i in items if t in SNAP and i]
    recs = [i for t, i in items if t == 'record']
    if recs:                  # a memory's metadata row, as it is when absent, so an undo resets it rather than deleting it
        with store.db() as c:
            for i in recs: c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (i,))
    before = snapshot(items) if items else {}
    box = {}
    yield box
    if not items: return
    after = snapshot(items)
    changed = [(t, i) for t, i in items if before.get(f'{t}:{i}') != after.get(f'{t}:{i}')]
    if not changed: return
    if per_item:
        for t, i in changed:
            k = f'{t}:{i}'
            why = reason.get(i, '') if isinstance(reason, dict) else reason
            box[i] = _record(action, [(t, i)], {k: before[k]}, {k: after[k]}, why)
    else:
        main = [x for x in items if x in changed] + [x for x in changed if x not in items]
        box['id'] = _record(action, main, {f'{t}:{i}': before[f'{t}:{i}'] for t, i in changed},
                            {f'{t}:{i}': after[f'{t}:{i}'] for t, i in changed}, reason if isinstance(reason, str) else '', title)


def note_linked(action, item_type, item_id, title, reason, link):
    """A library action whose undo lives elsewhere (Temple's category and tag housekeeping: link 'taxonomy:<change id>')."""
    return _record(action, [(item_type, item_id)], {}, {}, reason, title, link)


def undo(aid, note=''):
    """Put back exactly what one library action changed. Approvals undone wait for a person (Temple does not approve them again)."""
    note = ' '.join((note or '').split())[:300]
    with store.db() as c:
        r = c.execute('SELECT * FROM library_actions WHERE id=?', (aid,)).fetchone()
    if not r: raise ValueError('That library action was not found.')
    r = dict(r)
    if r['undone_at']: raise ValueError('That has already been undone.')
    if r['link'].startswith('taxonomy:'):
        import temple_taxonomy
        temple_taxonomy.decide(r['link'].split(':', 1)[1], 'undo')
    elif r['link'].startswith('move:'):         # Temple kept it private instead of holding it: it waits for a person now
        with store.db() as c:
            c.execute("UPDATE space_moves SET status='held',decided_at=NULL,decided_by='' WHERE id=? AND status='kept'", (r['link'].split(':', 1)[1],))
    elif r['link'].startswith('auto:'):         # made and approved in one step (Temple's note from chat): taken back out, history kept
        import autoapprove
        _, kind, iid = r['link'].split(':', 2)
        autoapprove.undo(kind, iid)
    else:
        before, after = json.loads(r['before'] or '{}'), json.loads(r['after'] or '{}')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for key in after:
                _restore(c, key, before.get(key) or {}, after[key])
    if r['action'] in ('approve', 'supersede') and not r['link']:   # it waits for a person again; Temple does not approve it a second time
        import autoapprove
        keys = json.loads(r['items'] or '[]')
        for key in (keys if r['action'] == 'approve' else keys[:1]):     # a supersession: the newer item (the older one is live again)
            t, i = key.split(':', 1)
            if t in APPROVAL_TYPE:
                autoapprove.hold(APPROVAL_TYPE[t], i, f'Temple\'s approval was undone by {store.actor()}: it waits for a person.')
    with store.acting(note=note or None):
        with store.db() as c:
            c.execute('UPDATE library_actions SET undone_at=?,undone_by=?,undo_note=? WHERE id=?', (store.now(), store.actor(), note, aid))
            store.audit(c, 'library_undone', r['item_id'], RULE,
                        f'Undone: {LABELS.get(r["action"], r["action"]).lower()} {TYPE_LABEL.get(r["item_type"], r["item_type"]).lower()} '
                        f'"{r["title"][:120]}"' + (f' ({note})' if note else ''))
    try:
        import spaces
        spaces.forget()
    except Exception:
        pass
    return {'undone': aid}


def recent(days=7, limit=200, action=''):
    """Temple's library actions, newest first, with titles, references and whether each can still be undone. Only items this person
    may see."""
    import refs
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT id,at,action,item_type,item_id,title,reason,items,actor,link,undone_at,undone_by FROM library_actions '
                                           'WHERE at>=? ' + ('AND action=? ' if action else '') + 'ORDER BY at DESC, id DESC LIMIT ?',
                                           (since, *([action] if action else []), max(1, min(1000, int(limit)))))]
    if store.viewer() is not None:
        def _vis(r):
            if r['item_type'] in ('record', 'file'): return store.can_see(r['item_type'], r['item_id'])
            if r['item_type'] == 'taxonomy': return bool(store.viewer().full)
            return store.can_see('organisation', (r['title'] or '').split(':')[0])
        rows = [r for r in rows if _vis(r)]
    rec, fil = refs.of('record', [r['item_id'] for r in rows if r['item_type'] == 'record']), refs.of('file', [r['item_id'] for r in rows if r['item_type'] == 'file'])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=UNDO_DAYS)).isoformat()
    for r in rows:
        r['items'] = json.loads(r['items'] or '[]')
        r['ref'] = rec.get(r['item_id']) or fil.get(r['item_id']) or ''
        r['label'] = LABELS.get(r['action'], r['action'])
        r['type_label'] = TYPE_LABEL.get(r['item_type'], r['item_type'])
        r['can_undo'] = not r['undone_at'] and r['at'] >= cutoff
    return rows
