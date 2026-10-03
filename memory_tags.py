"""Memory organisation, second layer: areas and tags.

- Areas: each category belongs to Work, Personal or Both ('' = Both). The Memories page can show only Work or only
  Personal; a category in Both shows in either. Areas are a view, not a rule: nothing about who may read a memory changes.
- Tags: a list you create (name, description, optional area). A memory can carry several. Assignments live in
  record_tags with who set them: 'human' (you), 'temple' (applied by Temple), 'suggested' (Temple's suggestion waiting
  for you) or 'removed' (you took it off or dismissed it, so Temple never puts it back). Human > Temple, always.
- Temple tags new memories in the background (temple_tags.py) and on request, choosing only from your tags.
Schema is additive: new tables, a guarded column on categories and on record_meta."""
import re

import substrate_store as store

AREAS = {'work': 'Work', 'personal': 'Personal', '': 'Both'}
SHOWN = ('human', 'temple')
MAX_TAGS = 12            # per memory, all sources together


def _schema():
    with store.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS tags (name TEXT PRIMARY KEY COLLATE NOCASE, description TEXT NOT NULL DEFAULT '', "
                  "area TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS record_tags (record_id TEXT NOT NULL, tag TEXT NOT NULL COLLATE NOCASE, "
                  "assigned_by TEXT NOT NULL DEFAULT 'human', confidence REAL, reason TEXT NOT NULL DEFAULT '', "
                  "created_at TEXT NOT NULL, PRIMARY KEY (record_id, tag))")
        c.execute("CREATE TABLE IF NOT EXISTS record_meta (record_id TEXT PRIMARY KEY, category TEXT NOT NULL DEFAULT '')")
        if 'area' not in {r['name'] for r in c.execute('PRAGMA table_info(categories)')}:
            c.execute("ALTER TABLE categories ADD COLUMN area TEXT NOT NULL DEFAULT ''")
        if 'tags_checked_at' not in {r['name'] for r in c.execute('PRAGMA table_info(record_meta)')}:
            c.execute('ALTER TABLE record_meta ADD COLUMN tags_checked_at TEXT')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('temple_tags','auto')")


_schema()


def _area(a):
    a = (a or '').strip().lower()
    if a in ('both', 'shared'): a = ''
    if a not in AREAS: raise ValueError('Area must be Work, Personal or Both.')
    return a


def clean_tag(name):
    name = ' '.join(str(name or '').replace('#', ' ').split())[:30].strip()
    if name and not re.fullmatch(r"[\w][\w &/.'+-]*", name):
        raise ValueError('Tags use letters, numbers, spaces and - & / . \' + only (no commas).')
    return name


# ---------------- areas on categories ----------------
def category_areas():
    with store.db() as c:
        return {r['name']: r['area'] for r in c.execute('SELECT name,area FROM categories')}


def set_category_area(name, area):
    area = _area(area)
    with store.db() as c:
        row = c.execute('SELECT name FROM categories WHERE name=?', (store.clean_category(name),)).fetchone()
        if not row: raise ValueError(f'No category called "{name}".')
        c.execute('UPDATE categories SET area=? WHERE name=?', (area, row[0]))
        store.audit(c, 'category_area_set', row[0], 'human_review', AREAS[area])
    return {'name': row[0], 'area': area}


# ---------------- the tag list ----------------
def mode():
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='temple_tags'").fetchone()
    return row[0] if row else 'auto'


def set_mode(m):
    if m not in ('off', 'suggest', 'auto'): raise ValueError('Unknown mode.')
    with store.db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='temple_tags'", (m,))
        store.audit(c, 'temple_tags_mode', 'Temple', 'human_control', m)
    return {'temple_mode': m}


def list_tags():
    with store.db() as c:
        rows = c.execute("SELECT t.name,t.description,t.area,t.created_at,"
                         "(SELECT count(*) FROM record_tags x JOIN records r ON r.id=x.record_id LEFT JOIN memory_archive a ON a.record_id=r.id "
                         " WHERE x.tag=t.name AND x.assigned_by IN ('human','temple') AND coalesce(a.state,r.status)='approved') AS active,"
                         "(SELECT count(*) FROM record_tags x WHERE x.tag=t.name AND x.assigned_by IN ('human','temple')) AS total,"
                         "(SELECT count(*) FROM record_tags x WHERE x.tag=t.name AND x.assigned_by='suggested') AS suggested "
                         "FROM tags t ORDER BY lower(t.name)").fetchall()
    return {'tags': [dict(r) for r in rows], 'temple_mode': mode()}


def _canonical(c, name):
    name = clean_tag(name)
    row = c.execute('SELECT name FROM tags WHERE name=?', (name,)).fetchone() if name else None
    if not row: raise ValueError(f'No tag called "{name}". Create it first.')
    return row[0]


def create_tag(name, description='', area=''):
    name, area = clean_tag(name), _area(area)
    if not name: raise ValueError('Enter a tag name.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM tags WHERE name=?', (name,)).fetchone(): raise ValueError(f'"{name}" already exists.')
        c.execute('INSERT INTO tags(name,description,area,created_at) VALUES (?,?,?,?)', (name, (description or '').strip()[:300], area, store.now()))
        c.execute('UPDATE record_meta SET tags_checked_at=NULL')          # a new tag: Temple may look at everything again
        store.audit(c, 'tag_created', name, 'human_review', AREAS[area] + ((': ' + description.strip()[:200]) if description.strip() else ''))
    return {'name': name, 'area': area}


def update_tag(name, new_name, description='', area=''):
    new_name, area = clean_tag(new_name), _area(area)
    if not new_name: raise ValueError('Enter a tag name.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        old = _canonical(c, name)
        if new_name.lower() != old.lower() and c.execute('SELECT 1 FROM tags WHERE name=?', (new_name,)).fetchone():
            raise ValueError(f'"{new_name}" already exists.')
        c.execute('UPDATE tags SET name=?,description=?,area=? WHERE name=?', (new_name, (description or '').strip()[:300], area, old))
        c.execute('UPDATE record_tags SET tag=? WHERE tag=?', (new_name, old))
        c.execute('UPDATE record_meta SET tags_checked_at=NULL')
        store.audit(c, 'tag_updated', new_name, 'human_review', (f'{old} → {new_name}; ' if old != new_name else '') + AREAS[area])
    return {'name': new_name, 'area': area}


def delete_tag(name):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        old = _canonical(c, name)
        n = c.execute("SELECT count(*) FROM record_tags WHERE tag=? AND assigned_by IN ('human','temple')", (old,)).fetchone()[0]
        c.execute('DELETE FROM record_tags WHERE tag=?', (old,))
        c.execute('DELETE FROM tags WHERE name=?', (old,))
        store.audit(c, 'tag_deleted', old, 'human_review', f'taken off {n} memories (the memories are unchanged)')
    return {'deleted': old, 'untagged': n}


# ---------------- tags on memories ----------------
def _put(c, rid, tag, by, confidence=None, reason=''):
    c.execute('INSERT INTO record_tags(record_id,tag,assigned_by,confidence,reason,created_at) VALUES (?,?,?,?,?,?) '
              'ON CONFLICT(record_id,tag) DO UPDATE SET assigned_by=excluded.assigned_by,confidence=excluded.confidence,'
              'reason=excluded.reason,created_at=excluded.created_at', (rid, tag, by, confidence, reason[:200], store.now()))


def set_tags(ids, add=(), remove=()):
    """Your choice: added tags are yours; removed ones are remembered so Temple does not put them back."""
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, str) and i][:200]
    if not ids: raise ValueError('Select at least one memory.')
    if not add and not remove: raise ValueError('Choose a tag to add or remove.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        add = list(dict.fromkeys(_canonical(c, t) for t in add))
        remove = [t for t in dict.fromkeys(_canonical(c, t) for t in remove) if t not in add]
        found = [r[0] for r in c.execute(f"SELECT id FROM records WHERE id IN ({','.join('?' * len(ids))})", ids)]
        full = []
        for rid in found:
            for t in add:
                have = c.execute("SELECT count(*) FROM record_tags WHERE record_id=? AND assigned_by IN ('human','temple') AND tag<>?", (rid, t)).fetchone()[0]
                if have >= MAX_TAGS: full.append(rid); continue
                _put(c, rid, t, 'human')
            for t in remove: _put(c, rid, t, 'removed')
        bits = (['+' + ', +'.join(add)] if add else []) + (['−' + ', −'.join(remove)] if remove else [])
        store.audit(c, 'tags_set', ','.join(found)[:500], 'human_review', f'{len(found)} memories: ' + '; '.join(bits))
    return {'updated': len(found), 'added': add, 'removed': remove, 'full': len(set(full))}


def resolve_suggestions(items, action):
    """items: [(record_id, tag)]. accept = your tag; dismiss = removed (Temple will not suggest it again)."""
    if action not in ('accept', 'dismiss'): raise ValueError('Unknown action.')
    done = 0
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        for rid, tag in list(dict.fromkeys((str(a), str(b)) for a, b in items))[:400]:
            if not c.execute("SELECT 1 FROM record_tags WHERE record_id=? AND tag=? AND assigned_by='suggested'", (rid, tag)).fetchone(): continue
            _put(c, rid, tag, 'human' if action == 'accept' else 'removed'); done += 1
        store.audit(c, 'tag_suggestions_' + action, f'{done} suggestions', 'human_review', f'{done} Temple tag suggestions {action}ed')
    return {'done': done}


def suggestions_for(ids):
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids: return []
    with store.db() as c:
        return [(r[0], r[1]) for r in c.execute(f"SELECT record_id,tag FROM record_tags WHERE assigned_by='suggested' "
                                                 f"AND record_id IN ({','.join('?' * len(ids))})", ids)]


def tags_for(ids):
    """{record_id: {'tags': [{name, by, confidence}], 'suggested': [{name, confidence, reason}]}}"""
    ids = [i for i in dict.fromkeys(ids) if i]
    out = {i: {'tags': [], 'suggested': []} for i in ids}
    with store.db() as c:
        for k in range(0, len(ids), 500):
            chunk = ids[k:k + 500]
            for r in c.execute(f"SELECT record_id,tag,assigned_by,confidence,reason FROM record_tags WHERE record_id IN ({','.join('?' * len(chunk))}) "
                               "AND assigned_by IN ('human','temple','suggested') ORDER BY lower(tag)", chunk):
                if r['assigned_by'] == 'suggested':
                    out[r['record_id']]['suggested'].append({'name': r['tag'], 'confidence': r['confidence'], 'reason': r['reason']})
                else:
                    out[r['record_id']]['tags'].append({'name': r['tag'], 'by': r['assigned_by'], 'confidence': r['confidence']})
    return out


# ---------------- Temple's side ----------------
def candidates(ids=None, limit=40):
    """Proposed or active memories Temple has not looked at since the tags last changed, with what is already on them."""
    where = f"WHERE {store.ACTIVE_FOR_TEMPLE} AND m.tags_checked_at IS NULL "
    args = []
    if ids:
        where += f"AND r.id IN ({','.join('?' * len(ids))}) "
        args += list(ids)
        with store.db() as c:
            for i in ids: c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (i,))
    else:
        with store.db() as c:     # memories with no record_meta row yet
            c.execute("INSERT OR IGNORE INTO record_meta(record_id) SELECT r.id FROM records r LEFT JOIN record_meta m ON m.record_id=r.id WHERE m.record_id IS NULL")
    with store.db() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT r.id,r.title,substr(r.content,1,600) AS content,coalesce(m.category,'') AS category FROM records r "
            'LEFT JOIN memory_archive a ON a.record_id=r.id JOIN record_meta m ON m.record_id=r.id '
            + where + 'ORDER BY r.created_at DESC LIMIT ?', args + [limit])]
        for r in rows:
            got = c.execute('SELECT tag,assigned_by FROM record_tags WHERE record_id=?', (r['id'],)).fetchall()
            r['has_tags'] = [g[0] for g in got if g[1] in SHOWN]
            r['not_these'] = [g[0] for g in got if g[1] in ('removed', 'suggested')]
    return rows


def reset_checks(ids=None):
    with store.db() as c:
        if ids: c.execute(f"UPDATE record_meta SET tags_checked_at=NULL WHERE record_id IN ({','.join('?' * len(ids))})", list(ids))
        else: c.execute('UPDATE record_meta SET tags_checked_at=NULL')


def record_results(results, checked, mode, threshold=0.75, per_memory=3):
    """results: [(record_id, tag, confidence, reason)] already limited to your tags and the batch. Temple never touches a
    tag you set or removed, and never repeats a suggestion."""
    applied = suggested = 0
    per = {}
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        for rid, tag, conf, reason in sorted(results, key=lambda x: -x[2]):
            if per.get(rid, 0) >= per_memory: continue
            if c.execute('SELECT 1 FROM record_tags WHERE record_id=? AND tag=?', (rid, tag)).fetchone(): continue
            if c.execute("SELECT count(*) FROM record_tags WHERE record_id=? AND assigned_by IN ('human','temple')", (rid,)).fetchone()[0] >= MAX_TAGS: continue
            if mode == 'auto' and conf >= threshold:
                _put(c, rid, tag, 'temple', conf, reason); applied += 1
            else:
                _put(c, rid, tag, 'suggested', conf, reason); suggested += 1
            per[rid] = per.get(rid, 0) + 1
        for rid in dict.fromkeys(checked):
            c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (rid,))
            c.execute('UPDATE record_meta SET tags_checked_at=? WHERE record_id=?', (store.now(), rid))
        store.audit(c, 'temple_tagged', f'{len(set(checked))} memories', 'advisory_metadata', f'{applied} tags applied, {suggested} suggested, mode {mode}')
    return {'checked': len(set(checked)), 'applied': applied, 'suggested': suggested}


# ---------------- the Memories page listing ----------------
def organised(status='approved', query='', category='', sort='newest', offset=0, limit=50, kind='', owner='', area='', tag=''):
    """store.organised_records plus area and tag filters, each memory's tags and suggestions, and tag counts."""
    area = _area(area) if area else ''
    tag = (tag or '')[:40]
    if not area and not tag:
        d = store.organised_records(status, query, category, sort, offset, limit, kind, owner)
    else:
        full = store.organised_records(status, query, category, sort, 0, 100000, kind, owner)
        rows = full['records']
        if area:
            areas = category_areas()
            rows = [r for r in rows if r['category'] and areas.get(r['category'], '') in (area, '')]
        if tag:
            tg = tags_for([r['id'] for r in rows])
            if tag == '__untagged__': rows = [r for r in rows if not tg[r['id']]['tags']]
            elif tag == '__suggested__': rows = [r for r in rows if tg[r['id']]['suggested']]
            else: rows = [r for r in rows if any(x['name'].lower() == tag.lower() for x in tg[r['id']]['tags'])]
        d = full | {'records': rows[offset:offset + limit], 'total': len(rows),
                    'next_offset': offset + limit if offset + limit < len(rows) else None}
    tg = tags_for([r['id'] for r in d['records']])
    for r in d['records']:
        r['tags'], r['tag_suggestions'] = tg[r['id']]['tags'], tg[r['id']]['suggested']
    st = "(?='all' OR coalesce(a.state,r.status)=?)"
    with store.db() as c:
        d['tag_counts'] = {r[0]: r[1] for r in c.execute(
            "SELECT t.name,count(*) FROM record_tags x JOIN tags t ON t.name=x.tag JOIN records r ON r.id=x.record_id "
            f"LEFT JOIN memory_archive a ON a.record_id=r.id WHERE x.assigned_by IN ('human','temple') AND {st} GROUP BY t.name", (status, status))}
        d['tag_suggested'] = c.execute(
            "SELECT count(DISTINCT x.record_id) FROM record_tags x JOIN records r ON r.id=x.record_id "
            f"LEFT JOIN memory_archive a ON a.record_id=r.id WHERE x.assigned_by='suggested' AND {st}", (status, status)).fetchone()[0]
        d['untagged'] = c.execute(
            f"SELECT count(*) FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id WHERE {st} AND NOT EXISTS "
            "(SELECT 1 FROM record_tags x WHERE x.record_id=r.id AND x.assigned_by IN ('human','temple'))", (status, status)).fetchone()[0]
    d['known_tags'] = [{'name': t['name'], 'area': t['area'], 'description': t['description']} for t in list_tags()['tags']]
    d['category_areas'] = category_areas()
    return d
