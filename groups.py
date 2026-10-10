"""Entra groups decide who is in which space (decision D-0040, design CR-4 phase 1, 10 Oct 2026).

An Owner or Admin maps an Entra group (its object ID, as Entra puts it in the sign-in's `groups` claim) to one or more spaces, each
with a role (View, Contribute, Manage), and optionally to a permission profile. The mapping is applied when the person signs in
(their groups come with the sign-in) and again every day from the groups Alice last saw, and whenever a mapping changes. A
membership that came from a group is marked as such (space_members.via 'group:<id>'), so leaving the group removes exactly that
membership: memberships set by hand are never touched, and nothing the person created moves. A profile set by hand on Users and
permissions wins over a group's (users.profile_via). Owners keep full access whatever their groups say. Every change is logged.

Entra puts groups in the token only when the web sign-in app's token configuration has a groups claim (Security groups); see the
pull request for the step.
"""
import json
import re
import threading
import time
import uuid

import substrate_store as store

GUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
DAY_S = 24 * 3600


def _schema(c):
    c.execute("CREATE TABLE IF NOT EXISTS group_mappings (id TEXT PRIMARY KEY, group_id TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', "
              "spaces TEXT NOT NULL DEFAULT '[]', profile TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0, "
              "updated_at TEXT NOT NULL, updated_by TEXT NOT NULL DEFAULT '')")
    cols = {r['name'] for r in c.execute('PRAGMA table_info(users)')}
    for col, ddl in (('groups', "TEXT NOT NULL DEFAULT '[]'"), ('groups_applied_at', "TEXT NOT NULL DEFAULT ''"),
                     ('profile_via', "TEXT NOT NULL DEFAULT ''")):
        if col not in cols: c.execute(f'ALTER TABLE users ADD COLUMN {col} {ddl}')


import users  # noqa: E402  (the users table first)
with store.db() as _c: _schema(_c)


def _actor():
    return store.viewer() or users.local_owner()


def _who():
    v = _actor()
    return v.email or v.name or store.actor()


def _check_admin():
    v = _actor()
    if not (v.full or v.role == 'admin'): raise PermissionError('Only an Owner or an Admin of Alice can map Entra groups.')
    return v


# ---------------- the mappings (Admin › Users and permissions › Entra groups) ----------------
def mappings():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM group_mappings ORDER BY position, lower(label), group_id')]
    for r in rows: r['spaces'] = json.loads(r['spaces'] or '[]')
    return rows


def listing():
    import spaces
    _check_admin()
    nm = spaces.names()
    rows = mappings()
    for r in rows:
        for s in r['spaces']: s['name'] = (nm.get(s['space']) or {}).get('name', 'a space that no longer exists')
    with store.db() as c:
        seen = {}
        for u in c.execute("SELECT oid, groups FROM users WHERE status='active'"):
            for g in json.loads(u['groups'] or '[]'): seen[g] = seen.get(g, 0) + 1
    return {'mappings': rows, 'spaces': [{'id': k, 'name': x['name'], 'kind': x['kind']} for k, x in nm.items() if x['kind'] in spaces.SHARED_KINDS],
            'profiles': [{'id': p['id'], 'name': p['name']} for p in users.profiles_list()],
            'roles': [{'key': r, 'label': spaces.ROLE_LABEL[r]} for r in spaces.ROLES], 'groups_seen': seen,
            'applied_at': _last_applied()}


def save(mid, group_id, label, space_roles, profile=''):
    """Create (mid '') or change a mapping: an Entra group's object ID, a label, [{space, role}], an optional profile."""
    import spaces
    _check_admin()
    group_id = (group_id or '').strip().lower()
    if not GUID.fullmatch(group_id): raise ValueError('Give the Entra group\'s object ID (a GUID, from Entra › Groups › the group › Overview).')
    label = ' '.join((label or '').split())[:80]
    nm = spaces.names()
    clean = {}
    for x in (space_roles or [])[:20]:
        sid, role = str((x or {}).get('space', '')), str((x or {}).get('role', ''))
        if (nm.get(sid) or {}).get('kind') not in spaces.SHARED_KINDS: raise ValueError('Choose shared spaces (never someone\'s personal space).')
        if role not in spaces.RANK: raise ValueError('Role must be View, Contribute or Manage.')
        if spaces.RANK[role] > spaces.RANK.get(clean.get(sid), -1): clean[sid] = role
    if profile:
        if not any(p['id'] == profile for p in users.profiles_list()): raise ValueError('No such permission profile.')
    if not clean and not profile: raise ValueError('Map the group to at least one space or a profile.')
    out = [{'space': k, 'role': v} for k, v in clean.items()]
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if mid:
            if not c.execute('SELECT 1 FROM group_mappings WHERE id=?', (mid,)).fetchone(): raise LookupError('No such mapping.')
            c.execute('UPDATE group_mappings SET group_id=?,label=?,spaces=?,profile=?,updated_at=?,updated_by=? WHERE id=?',
                      (group_id, label, json.dumps(out), profile, store.now(), _who(), mid))
        else:
            mid = uuid.uuid4().hex
            pos = (c.execute('SELECT max(position) FROM group_mappings').fetchone()[0] or 0) + 1
            c.execute('INSERT INTO group_mappings(id,group_id,label,spaces,profile,position,updated_at,updated_by) VALUES (?,?,?,?,?,?,?,?)',
                      (mid, group_id, label, json.dumps(out), profile, pos, store.now(), _who()))
        store.audit(c, 'group_mapping_saved', group_id, 'users', f'{label or group_id}: ' + (', '.join(f"{(nm.get(k) or {}).get('name', k)} "
                    f"({spaces.ROLE_LABEL[v]})" for k, v in clean.items()) or 'no spaces') + (f'; profile {profile}' if profile else ''))
    apply_all()
    return listing()


def delete(mid):
    _check_admin()
    with store.db() as c:
        r = c.execute('SELECT * FROM group_mappings WHERE id=?', (mid,)).fetchone()
        if not r: raise LookupError('No such mapping.')
        c.execute('DELETE FROM group_mappings WHERE id=?', (mid,))
        store.audit(c, 'group_mapping_deleted', r['group_id'], 'users', f"{r['label'] or r['group_id']}: memberships it gave are removed")
    apply_all()
    return listing()


# ---------------- applying them ----------------
_lock = threading.Lock()


def desired(groups):
    """({space id: role}, profile or '', the group that gave the profile) for this set of groups."""
    groups = set(groups or [])
    want, profile, via = {}, '', ''
    import spaces
    for m in mappings():
        if m['group_id'] not in groups: continue
        for s in m['spaces']:
            if spaces.RANK[s['role']] > spaces.RANK.get(want.get(s['space'], (None, ''))[0], -1):
                want[s['space']] = (s['role'], m['group_id'])
        if m['profile'] and not profile: profile, via = m['profile'], m['group_id']
    return want, profile, via


def apply(oid, groups=None):
    """Put one person's memberships and profile in step with their groups (the ones given, else the ones Alice last saw).
    Returns what changed. Memberships set by hand and items the person created are never touched."""
    import spaces
    oid = (oid or '').strip().lower()
    row = users.person(oid)
    if not row: return {'changed': []}
    if groups is None: groups = json.loads(row.get('groups') or '[]')
    groups = sorted({str(g).strip().lower() for g in groups if GUID.fullmatch(str(g).strip().lower())})
    key = spaces.key_for(oid)
    want, profile, pvia = desired(groups)
    owner = users.is_owner(oid, row=row)
    names = spaces.names()
    changed = []
    with _lock, store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        have = {r['space_id']: dict(r) for r in c.execute('SELECT space_id, role, via FROM space_members WHERE member_key=?', (key,))}
        for sid, (role, gid) in want.items():
            if sid not in names: continue
            cur = have.get(sid)
            if cur and not (cur['via'] or '').startswith('group:'): continue          # set by hand: theirs stays as it is
            if cur and cur['role'] == role and cur['via'] == 'group:' + gid: continue
            c.execute('INSERT INTO space_members(space_id,member_key,role,added_at,added_by,via) VALUES (?,?,?,?,?,?) '
                      'ON CONFLICT(space_id,member_key) DO UPDATE SET role=excluded.role,via=excluded.via',
                      (sid, key, role, store.now(), 'Entra group', 'group:' + gid))
            changed.append(f"{names[sid]['name']}: {spaces.ROLE_LABEL[role]} (group {gid[:8]}…)")
        for sid, cur in have.items():
            if (cur['via'] or '').startswith('group:') and sid not in want:
                c.execute('DELETE FROM space_members WHERE space_id=? AND member_key=?', (sid, key))
                changed.append(f"{(names.get(sid) or {}).get('name', sid)}: removed (no longer in the group)")
        if not owner and row.get('profile_via') != 'hand':
            if profile and (row['profile'] != profile or row.get('profile_via') != 'group:' + pvia):
                c.execute('UPDATE users SET profile=?,profile_via=? WHERE oid=?', (profile, 'group:' + pvia, oid))
                changed.append(f'profile {profile} (group {pvia[:8]}…)')
            elif not profile and (row.get('profile_via') or '').startswith('group:'):
                c.execute("UPDATE users SET profile=?,profile_via='' WHERE oid=?", (users.DEFAULT_PROFILE, oid))
                changed.append(f'profile back to {users.DEFAULT_PROFILE} (no longer in the group)')
        c.execute('UPDATE users SET groups=?,groups_applied_at=? WHERE oid=?', (json.dumps(groups), store.now(), oid))
        if changed:
            store.audit(c, 'group_access_applied', oid, 'users', f"{row['email'] or oid}: " + '; '.join(changed)[:600])
    users._forget(oid)
    spaces.forget()
    return {'changed': changed, 'groups': groups}


def on_signin(oid, groups):
    """From the sign-in (users.identify): apply when their groups changed, or once a day."""
    row = users.person(oid)
    if not row: return
    stored = json.loads(row.get('groups') or '[]')
    fresh = sorted({str(g).strip().lower() for g in groups if GUID.fullmatch(str(g).strip().lower())})
    if fresh == stored and row.get('groups_applied_at') and _age(row['groups_applied_at']) < DAY_S: return
    try: apply(oid, fresh)
    except Exception:
        import logging
        logging.getLogger('alice.groups').warning('Group mapping not applied for %s', oid[:8], exc_info=True)


def _age(iso):
    from datetime import datetime, timezone
    try: return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except ValueError: return DAY_S * 2


def _last_applied():
    with store.db() as c:
        r = c.execute("SELECT value FROM settings WHERE key='groups_applied_at'").fetchone()
    return r[0] if r else ''


def apply_all():
    """Every active person, from the groups Alice last saw for them (daily, and when a mapping changes)."""
    with store.db() as c:
        oids = [r[0] for r in c.execute("SELECT oid FROM users WHERE status='active'")]
    n = 0
    for oid in oids:
        try:
            if apply(oid)['changed']: n += 1
        except Exception:
            pass
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES ('groups_applied_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (store.now(),))
    return {'people': len(oids), 'changed': n}


_checked = [0.0]


def maybe_daily():
    """Called on requests (cheap): once a day, apply every mapping again in the background."""
    now = time.monotonic()
    if now - _checked[0] < 600: return
    _checked[0] = now
    last = _last_applied()
    if last and _age(last) < DAY_S: return
    store.spawn(lambda: _quiet(apply_all))


def _quiet(fn):
    try: fn()
    except Exception: pass
