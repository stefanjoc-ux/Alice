"""People who use Alice: who is signed in, their role, their permission profile and whether they are suspended.

Roles (highest first): Owner, Admin, Member. In Azure the signed-in person comes from Container Apps sign-in
(X-MS-CLIENT-PRINCIPAL*, trusted only with ALICE_TRUST_EASYAUTH=1). On the PC there is no sign-in: whoever is at this
computer is the owner and sees everything, exactly as before.

Two ways in, switched by ALICE_USE_APP_ROLES (Bicep useAppRoles):
  off (as today)  Entra's allowedPrincipals list (the owner plus the accounts in allowedUserObjectIds) decides who gets in,
                  and everyone it lets in is the owner's own account: Owner, unless the Users page has set them lower.
  on              the web sign-in app's roles decide: Alice.Owner, Alice.Admin or Alice.Member, assigned in Entra (the
                  enterprise application has "Assignment required"). Someone with none of them is refused.
The role Alice uses is the LOWER of the Entra role (a ceiling: take it away in Entra and they drop at once) and the role
set on the Users and permissions page (which starts at the Entra role on first sign-in). ENTRA DECIDES THE OWNER (Stefan,
9 Oct 2026), through ONE check, is_owner(): anyone assigned the Alice.Owner app role is an owner of Alice (full access,
including Health, Trading, Mileage and Backups). The configured owner object ID (ALICE_OWNER_OBJECT_ID, the setup state's
ownerObjectId) is only a bootstrap fallback while app roles are off. Never an account name or email. An owner is always
Owner and cannot be demoted, suspended or removed here (take the role away in Entra); an Admin never sees the personal areas;
there is always at least one active Owner.

A permission profile is a named set of levels per section (permissions.py). Owners see and manage everything; Admins and
Members get their profile (Admins also Users and permissions, Rules and Rule packs). A new person gets the default Member
profile: Chat and their own saved chats, nothing else. Adding a person never shares anything by itself.
"""
import base64
import json
import os
import re
import threading
import time
import uuid

import substrate_store as store

ROLES = ('member', 'admin', 'owner')                    # lowest first
RANK = {r: i for i, r in enumerate(ROLES)}
ROLE_LABEL = {'owner': 'Owner', 'admin': 'Admin', 'member': 'Member'}
ENTRA_ROLES = {'Alice.Owner': 'owner', 'Alice.Admin': 'admin', 'Alice.Member': 'member'}
OWNER_ROLE = 'Alice.Owner'          # the app role that makes an account an owner of Alice (is_owner)
STATUSES = ('active', 'suspended')
DEFAULT_PROFILE = 'member'          # the default profile id for anyone new
TEAM_PROFILE = 'team-member'        # built in: what an Entra group mapping usually gives (CR-4 phase 1)
CACHE_S = 15                        # a change on the Users page reaches every request within this (same process: at once)
TOUCH_S = 300                       # last seen is written at most every 5 minutes per person
OID = re.compile(r'^[0-9a-z][0-9a-z-]{0,63}$')       # Entra object IDs are GUIDs; anything else odd is refused
PROFILE_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')


class Refused(Exception):
    """This person may not use Alice (no role, suspended, or not identifiable). The message is shown to them."""
    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


def _schema(c):
    c.execute("CREATE TABLE IF NOT EXISTS users (oid TEXT PRIMARY KEY, email TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '', "
              "role TEXT NOT NULL DEFAULT 'member', profile TEXT NOT NULL DEFAULT 'member', status TEXT NOT NULL DEFAULT 'active', "
              "entra_role TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, "
              "updated_at TEXT NOT NULL DEFAULT '', updated_by TEXT NOT NULL DEFAULT '')")
    # entra_owner: 1 when their last sign-in carried the Alice.Owner role (is_owner for background work and the connector,
    # which have no sign-in to read). Additive; read again at every sign-in, so taking the role away in Entra clears it.
    if 'entra_owner' not in {r['name'] for r in c.execute('PRAGMA table_info(users)')}:
        c.execute('ALTER TABLE users ADD COLUMN entra_owner INTEGER NOT NULL DEFAULT 0')
    # Linked accounts (Stefan, 10 Oct 2026): one person, several Entra accounts (e.g. an everyday account and a tenant admin
    # account). A linked account counts as the same author as its primary account and shares that person's space memberships.
    # Only an Owner links accounts, on Users and permissions; never automatically by name or email.
    c.execute("CREATE TABLE IF NOT EXISTS user_links (oid TEXT PRIMARY KEY, primary_oid TEXT NOT NULL, linked_at TEXT NOT NULL, "
              "linked_by TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS permission_profiles (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', "
              "levels TEXT NOT NULL DEFAULT '{}', builtin INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL DEFAULT '')")


with store.db() as _c: _schema(_c)


def _seed():
    import permissions
    with store.db() as c:
        if not c.execute('SELECT 1 FROM permission_profiles WHERE id=?', (DEFAULT_PROFILE,)).fetchone():
            c.execute('INSERT INTO permission_profiles(id,name,description,levels,builtin,updated_at) VALUES (?,?,?,?,1,?)',
                      (DEFAULT_PROFILE, 'Member (default)', 'Chat and their own saved chats. Nothing of anyone else\'s.',
                       json.dumps(permissions.default_levels()), store.now()))
        if not c.execute('SELECT 1 FROM permission_profiles WHERE id=?', (TEAM_PROFILE,)).fetchone():
            c.execute('INSERT INTO permission_profiles(id,name,description,levels,builtin,updated_at) VALUES (?,?,?,?,1,?)',
                      (TEAM_PROFILE, 'Team member', 'Chat, assistants, digital teams and Knowledge to use; Organisations, Memories and '
                       'Decisions to view. For people who join through an Entra group.', json.dumps(permissions.team_member_levels()), store.now()))


# ---------------- settings from the environment ----------------
def trusted():
    return os.environ.get('ALICE_TRUST_EASYAUTH') == '1'


def use_app_roles():
    return os.environ.get('ALICE_USE_APP_ROLES') == '1'


def owner_oid():
    return (os.environ.get('ALICE_OWNER_OBJECT_ID') or '').strip().lower()


def fallback_oid():
    """The configured owner object ID, while it counts: only while app roles are off (the bootstrap, before Entra decides)."""
    return '' if use_app_roles() else owner_oid()


def is_owner(oid='', roles=None, row=None):
    """THE owner check (every owner-only area and rule uses it, through permissions.is_owner_person): the Alice.Owner app role
    in Entra, or, only while app roles are off, the configured owner object ID (fallback_oid). roles: the role claims of the
    sign-in being handled now; without one (background work, the connector), the role as recorded at their last sign-in (row,
    else read). Never by name or email."""
    oid = (oid or '').strip().lower()
    ow = fallback_oid()
    if oid and ow and oid == ow: return True
    if roles is not None: return OWNER_ROLE in roles
    if not oid: return False
    row = row if row is not None else _row(oid)
    return bool(row and row.get('entra_owner'))


def local_owner():
    """The owner at this computer (no sign-in): sees everything."""
    return store.Viewer('', '', store.owner_name(), 'owner', True, True)


def owner_oids():
    """The object IDs that count as the owner of Alice now, by the one owner check (is_owner): everyone whose last sign-in
    carried Alice.Owner, and the fallback ID while app roles are off. Spaces key all of them as the owner ('owner')."""
    out = {fallback_oid()} - {''}
    with store.db() as c:
        out |= {r[0] for r in c.execute('SELECT oid FROM users WHERE entra_owner=1')}
    return sorted(out)


def owner_viewer():
    """The owner, for background work on the owner's own items: on the PC the owner here; in Azure an owner by is_owner
    (never ALICE_OWNER_OBJECT_ID on its own once app roles are on)."""
    if not trusted(): return local_owner()
    o = owner_oids()
    return store.Viewer(o[0] if o else '', '', store.owner_name(), 'owner', True, True)


# ---------------- the sign-in headers ----------------
def principal(headers):
    """{oid, email, name, roles} from Container Apps sign-in headers ({} when not behind trusted sign-in)."""
    if not trusted(): return {}
    email = ' '.join((headers.get('x-ms-client-principal-name') or '').split())[:200].lower()
    oid = (headers.get('x-ms-client-principal-id') or '').strip().lower()
    name, roles, groups = '', [], None
    try:
        p = json.loads(base64.b64decode((headers.get('x-ms-client-principal') or '') + '==').decode('utf-8'))
        role_typ = p.get('role_typ') or 'roles'
        for c in p.get('claims') or []:
            typ, val = str(c.get('typ', '')), str(c.get('val', ''))
            if typ == 'name' and not name: name = val
            elif typ in (role_typ, 'roles', 'http://schemas.microsoft.com/ws/2008/06/identity/claims/role'): roles.append(val)
            elif typ in ('groups', 'http://schemas.microsoft.com/ws/2008/06/identity/claims/groups'): groups = (groups or []) + [val.strip().lower()]
            elif typ in ('http://schemas.microsoft.com/identity/claims/objectidentifier', 'oid') and not oid: oid = val.strip().lower()
            elif typ in ('preferred_username', 'email') and not email: email = ' '.join(val.split())[:200].lower()
    except Exception:
        pass
    if oid and not OID.fullmatch(oid): oid = ''
    return {'oid': oid, 'email': email, 'name': ' '.join(str(name).split())[:120], 'roles': roles, 'groups': groups}


def entra_ceiling(p):
    """The highest Alice role Entra gives this person ('' = none)."""
    if is_owner(p.get('oid'), p.get('roles', [])): return 'owner'
    if not use_app_roles(): return 'owner'                 # allowedPrincipals mode: Entra let in only the owner's own accounts
    got = [ENTRA_ROLES[r] for r in p.get('roles', []) if r in ENTRA_ROLES]
    return max(got, key=RANK.get) if got else ''


# ---------------- people (cached briefly; this process sees its own changes at once) ----------------
_lock = threading.Lock()
_cache = {}          # oid -> (time read, row dict or None)
_touched = {}


def _forget(oid=None):
    with _lock:
        if oid: _cache.pop(oid, None)
        else: _cache.clear()


def _row(oid):
    now = time.time()
    with _lock:
        hit = _cache.get(oid)
        if hit and now - hit[0] < CACHE_S: return hit[1]
    with store.db() as c:
        r = c.execute('SELECT * FROM users WHERE oid=?', (oid,)).fetchone()
    row = dict(r) if r else None
    with _lock: _cache[oid] = (now, row)
    return row


def profile_levels(pid):
    import permissions
    with store.db() as c:
        r = c.execute('SELECT levels FROM permission_profiles WHERE id=?', (pid or DEFAULT_PROFILE,)).fetchone()
        if not r and pid != DEFAULT_PROFILE:
            r = c.execute('SELECT levels FROM permission_profiles WHERE id=?', (DEFAULT_PROFILE,)).fetchone()
    try: return permissions.clean_levels(json.loads(r[0]) if r else {})
    except ValueError: return permissions.clean_levels({})


def effective_role(row, ceiling, owner=None):
    """owner: is_owner() for this sign-in (None = read from the row)."""
    if row and (owner if owner is not None else is_owner(row['oid'], row=row)): return 'owner'
    stored = (row or {}).get('role') or 'member'
    if stored not in RANK: stored = 'member'
    if not ceiling: return ''
    return min(stored, ceiling, key=RANK.get)


def _viewer(row, role, owner=False):
    return store.Viewer(row['oid'], row.get('email', ''), row.get('name', ''), role, role == 'owner', bool(owner))


def identify(headers):
    """The signed-in person as a store.Viewer, recording them on first sight. Raises Refused when they may not use Alice."""
    if not trusted(): return local_owner()
    p = principal(headers)
    if not p.get('oid'):
        if not use_app_roles() and not owner_oid():
            # Behind sign-in with no object ID and no owner configured (allowedPrincipals mode, as before roles): the owner.
            return store.Viewer('', p.get('email', ''), p.get('name', ''), 'owner', True, is_owner('', p.get('roles', [])))
        raise Refused('Alice could not tell who you are from your sign-in. Sign out and sign in again; if this keeps happening, '
                      'ask the owner of Alice to check your account.', 'no_object_id')
    ceiling = entra_ceiling(p)
    row = _row(p['oid'])
    owner = is_owner(p['oid'], p.get('roles', []))
    if row is None:
        if not ceiling:
            raise Refused('You do not have access to Alice. Ask its owner to give you a role (Alice Member, Admin or Owner).', 'no_role')
        row = _first_sight(p, ceiling)
    else:
        _touch(row, p, ceiling)
    if row['status'] == 'suspended' and not owner:
        raise Refused('Your access to Alice is suspended. Ask its owner if you think this is wrong.', 'suspended')
    if p.get('groups') is not None or (row.get('groups') or '[]') != '[]':
        # Entra group mappings (groups.py): when their groups changed, or once a day. Entra leaves the claim out when someone is
        # in no group, so once Alice has seen groups for them, no claim means they have left them all.
        import groups
        groups.on_signin(p['oid'], p.get('groups') or [])
        row = _row(p['oid']) or row
    role = effective_role(row, ceiling, owner)
    if not role:
        raise Refused('You do not have access to Alice. Ask its owner to give you a role (Alice Member, Admin or Owner).', 'no_role')
    return _viewer(row, role, owner)


def _first_sight(p, ceiling):
    t = store.now()
    role = 'owner' if is_owner(p['oid'], p.get('roles', [])) else ceiling
    with store.db() as c:
        c.execute('INSERT INTO users(oid,email,name,role,profile,status,entra_role,entra_owner,first_seen,last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) '
                  'ON CONFLICT(oid) DO NOTHING', (p['oid'], p.get('email', ''), p.get('name', ''), role, DEFAULT_PROFILE, 'active', ceiling,
                                                  int(OWNER_ROLE in p.get('roles', [])), t, t))
        store.audit(c, 'user_first_signin', p['oid'], 'users', f"{p.get('email') or p['oid']} signed in for the first time as {ROLE_LABEL[role]} "
                    f"(profile {DEFAULT_PROFILE}); nothing is shared with them until someone decides to")
    _touched[p['oid']] = time.time()
    _forget(p['oid'])
    return _row(p['oid'])


def _touch(row, p, ceiling):
    now = time.time()
    entra_owner = int(OWNER_ROLE in p.get('roles', []))
    changed = ((p.get('email') and p['email'] != row['email']) or (p.get('name') and p['name'] != row['name']) or ceiling != row['entra_role']
               or entra_owner != int(row.get('entra_owner') or 0))
    if not changed and now - _touched.get(row['oid'], 0) < TOUCH_S: return
    _touched[row['oid']] = now
    try:
        with store.db() as c:
            c.execute('UPDATE users SET email=?,name=?,entra_role=?,entra_owner=?,last_seen=? WHERE oid=?',
                      (p.get('email') or row['email'], p.get('name') or row['name'], ceiling, entra_owner, store.now(), row['oid']))
        _forget(row['oid'])
    except Exception:
        pass


def viewer_for(oid):
    """The viewer for a known person (background work on their items; the external connector's caller). The owner's
    object ID is always the owner. Unknown or suspended people get a viewer that sees nothing of anyone else's."""
    oid = (oid or '').strip().lower()
    if not oid: return None
    if oid == fallback_oid(): return store.Viewer(oid, '', store.owner_name(), 'owner', True, True)
    row = _row(oid)
    if not row or row['status'] != 'active':
        return store.Viewer(oid, '', '', 'member', False)
    owner = is_owner(oid, row=row)
    ceiling = 'owner' if owner or not use_app_roles() else row['entra_role']
    role = effective_role(row, ceiling, owner) or 'member'
    return _viewer(row, role, owner)


def connector_viewer(oid):
    """The viewer for a signed-in connector call (the external MCP endpoint, which has its own allowed-users list too).
    Suspended people are refused. Someone Alice has not seen yet: in allowedPrincipals mode the endpoint's own list admits only
    the owner's accounts, so they are the owner; with app roles they must sign in to Alice on the web once first."""
    oid = (oid or '').strip().lower()
    if not oid: raise Refused('Alice could not tell who you are from this sign-in.', 'no_object_id')
    if oid == fallback_oid(): return store.Viewer(oid, '', store.owner_name(), 'owner', True, True)
    row = _row(oid)
    if row is None:
        if not use_app_roles(): return store.Viewer(oid, '', '', 'owner', True, True)     # the owner's own account (said so, not inferred per process)
        raise Refused('Sign in to Alice on the web once, so the owner can set up your access, then try again.', 'unknown_person')
    if row['status'] != 'active': raise Refused('Your access to Alice is suspended.', 'suspended')
    return viewer_for(oid)


def person(oid):
    """The users row for an object ID (or None)."""
    return _row((oid or '').strip().lower())


# ---------------- linked accounts: one person, one author (Stefan, 10 Oct 2026) ----------------
_links_cache = []          # [(time read, {linked oid: primary oid})]


def links():
    """{linked oid: primary oid}. Cached briefly (a link made here clears it at once)."""
    now = time.time()
    with _lock:
        if _links_cache and now - _links_cache[0][0] < CACHE_S: return _links_cache[0][1]
    with store.db() as c:
        m = {r[0]: r[1] for r in c.execute('SELECT oid, primary_oid FROM user_links')}
    with _lock:
        _links_cache[:] = [(now, m)]
    return m


def _forget_links():
    with _lock: _links_cache.clear()


def primary(oid):
    """The person's primary account: the account this one is linked to, else itself. Links never chain."""
    oid = (oid or '').strip().lower()
    return links().get(oid, oid)


def group(oid):
    """Every account of the same person: the primary first, then the accounts linked to it."""
    p = primary(oid)
    if not p: return []
    return [p] + sorted(o for o, q in links().items() if q == p)


def link(oid, to, note):
    """Link account oid to the person whose primary account is `to`. Owner only; a reason is required and logged. Both accounts
    must have signed in to Alice. Never done automatically, by name or email or anything else."""
    actor = _actor_viewer()
    if actor.role != 'owner': raise PermissionError('Only an Owner of Alice can link accounts.')
    oid, to = (oid or '').strip().lower(), (to or '').strip().lower()
    note = ' '.join((note or '').split())[:300]
    if len(note) < 3: raise ValueError('Say why these accounts are the same person (kept in the activity log).')
    if oid == to: raise ValueError('Choose a different account to link to.')
    a, b = person(oid), person(to)
    if not a or not b: raise LookupError('Both accounts must have signed in to Alice once.')
    to = primary(to)                                    # link to the person's primary account, never to another linked one
    if to == oid: raise ValueError('That account is already linked to this one.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM user_links WHERE primary_oid=?', (oid,)).fetchone():
            raise ValueError('Other accounts are linked to this one. Unlink them first, or link them to the other account.')
        c.execute('INSERT INTO user_links(oid,primary_oid,linked_at,linked_by,note) VALUES (?,?,?,?,?) '
                  'ON CONFLICT(oid) DO UPDATE SET primary_oid=excluded.primary_oid,linked_at=excluded.linked_at,linked_by=excluded.linked_by,note=excluded.note',
                  (oid, to, store.now(), _who(), note))
        with store.acting(note=note):
            store.audit(c, 'user_linked', oid, 'users', f"{a['email'] or oid} linked to {b['email'] or to}: the same person, one author, "
                        'the same space memberships')
    _forget_links(); _forget()
    return {'linked': oid, 'to': to}


def unlink(oid, note=''):
    actor = _actor_viewer()
    if actor.role != 'owner': raise PermissionError('Only an Owner of Alice can unlink accounts.')
    oid = (oid or '').strip().lower()
    with store.db() as c:
        r = c.execute('SELECT primary_oid FROM user_links WHERE oid=?', (oid,)).fetchone()
        if not r: raise LookupError('That account is not linked.')
        c.execute('DELETE FROM user_links WHERE oid=?', (oid,))
        with store.acting(note=' '.join((note or '').split())[:300]):
            store.audit(c, 'user_unlinked', oid, 'users', f'{oid} unlinked from {r[0]}: it is its own author again')
    _forget_links(); _forget()
    return {'unlinked': oid}


# ---------------- the Users and permissions page ----------------
def _actor_viewer():
    return store.VIEWER.get() or local_owner()


def listing():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM users ORDER BY CASE role WHEN \'owner\' THEN 0 WHEN \'admin\' THEN 1 ELSE 2 END, lower(name), lower(email)')]
        profiles = {r['id']: r['name'] for r in c.execute('SELECT id,name FROM permission_profiles')}
    ow = fallback_oid()
    lk = links()
    for r in rows:
        r['linked_to'] = lk.get(r['oid'], '')
        owner = is_owner(r['oid'], row=r)
        ceiling = 'owner' if owner or not use_app_roles() else r['entra_role']
        r['effective_role'] = effective_role(r, ceiling, owner)
        r['is_owner'] = owner
        r['owner_by'] = ('the configured owner (until app roles are on)' if ow and r['oid'] == ow else 'the Alice.Owner role in Entra') if owner else ''
        r['profile_name'] = profiles.get(r['profile'], profiles.get(DEFAULT_PROFILE, 'Member (default)'))
        r['limited_by_entra'] = bool(ceiling) and RANK.get(r['role'], 0) > RANK.get(ceiling, 0)
    return {'users': rows, 'profiles': profiles_list(), 'app_roles': use_app_roles(), 'owner_configured': bool(ow),
            'roles': [{'id': r, 'label': ROLE_LABEL[r]} for r in reversed(ROLES)], 'me': _actor_viewer().oid}


def _active_owners(c, exclude=''):
    return [r[0] for r in c.execute("SELECT oid FROM users WHERE role='owner' AND status='active' AND oid<>?", (exclude,))]


def _who():
    v = _actor_viewer()
    return v.email or v.name or store.actor()


def _check_can_change(actor, target):
    """Owners change anyone (except the owner's own record); Admins change Members and Admins but not Owners, and never
    themselves (no raising your own access)."""
    if is_owner(target['oid'], row=target):
        raise PermissionError('An owner of Alice (anyone with the Alice.Owner role in Entra) always has full access: their role, '
                              'profile and status cannot be changed here. Change their role in Entra instead.')
    if actor.role == 'owner': return
    if actor.role != 'admin': raise PermissionError('Only an Owner or an Admin can change people.')
    if target['oid'] == actor.oid: raise PermissionError('You cannot change your own role, profile or status. Ask an Owner.')
    if target['role'] == 'owner': raise PermissionError('Only an Owner can change another Owner.')


def update(oid, role=None, profile=None, status=None):
    """Set a person's role, profile or status (suspend/restore). Logged with who did it."""
    import groups  # noqa: F401  (its columns on users exist before the write below; never import inside a transaction)
    actor = _actor_viewer()
    oid = (oid or '').strip().lower()
    target = person(oid)
    if not target: raise LookupError('No such person. They appear here after their first sign-in.')
    _check_can_change(actor, target)
    changes = []
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if role is not None:
            if role not in RANK: raise ValueError('Role must be Owner, Admin or Member.')
            if role == 'owner' and actor.role != 'owner': raise PermissionError('Only an Owner can make someone an Owner.')
            if target['role'] == 'owner' and role != 'owner' and not _active_owners(c, exclude=oid) and not fallback_oid():
                raise ValueError('There must always be at least one Owner.')
            if role != target['role']: changes.append(f"role {ROLE_LABEL.get(target['role'], target['role'])} → {ROLE_LABEL[role]}")
        if profile is not None:
            if not c.execute('SELECT 1 FROM permission_profiles WHERE id=?', (profile,)).fetchone(): raise ValueError('No such permission profile.')
            if profile != target['profile']: changes.append(f"profile {target['profile']} → {profile}")
        if status is not None:
            if status not in STATUSES: raise ValueError('Status must be active or suspended.')
            if status == 'suspended' and target['role'] == 'owner' and not _active_owners(c, exclude=oid) and not fallback_oid():
                raise ValueError('There must always be at least one active Owner.')
            if status != target['status']: changes.append('suspended' if status == 'suspended' else 'access restored')
        if not changes: return {'changed': False, 'user': person(oid)}
        c.execute('UPDATE users SET role=coalesce(?,role),profile=coalesce(?,profile),status=coalesce(?,status),updated_at=?,updated_by=? WHERE oid=?',
                  (role, profile, status, store.now(), _who(), oid))
        if profile is not None and profile != target['profile']:      # set by hand: an Entra group mapping no longer changes it
            c.execute("UPDATE users SET profile_via='hand' WHERE oid=?", (oid,))
        store.audit(c, 'user_changed', oid, 'users', f"{target['email'] or oid}: " + '; '.join(changes))
    _forget(oid)
    return {'changed': True, 'user': person(oid)}


# ---------------- permission profiles ----------------
def profiles_list():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM permission_profiles ORDER BY builtin DESC, lower(name)')]
        used = {r[0]: r[1] for r in c.execute('SELECT profile,count(*) FROM users GROUP BY profile')}
    for r in rows:
        r['levels'] = json.loads(r['levels'] or '{}')
        r['people'] = used.get(r['id'], 0)
    return rows


def save_profile(pid, name, levels, description=''):
    """Create (pid '') or change a profile. Owner and Admin only (the route checks); Admins cannot change the profile they use."""
    import permissions
    actor = _actor_viewer()
    name = ' '.join((name or '').split())[:60]
    if len(name) < 2: raise ValueError('Give the profile a name.')
    description = ' '.join((description or '').split())[:300]
    clean = permissions.clean_levels(levels)
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if pid:
            old = c.execute('SELECT * FROM permission_profiles WHERE id=?', (pid,)).fetchone()
            if not old: raise LookupError('No such profile.')
            if actor.role != 'owner':
                mine = c.execute('SELECT profile FROM users WHERE oid=?', (actor.oid,)).fetchone()
                if mine and mine[0] == pid: raise PermissionError('You cannot change the profile you use yourself. Ask an Owner.')
            c.execute('UPDATE permission_profiles SET name=?,description=?,levels=?,updated_at=?,updated_by=? WHERE id=?',
                      (name, description, json.dumps(clean), store.now(), _who(), pid))
            what = 'changed'
        else:
            base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:30] or 'profile'
            pid = base if PROFILE_ID.fullmatch(base) and not c.execute('SELECT 1 FROM permission_profiles WHERE id=?', (base,)).fetchone() \
                else base[:24] + '-' + uuid.uuid4().hex[:6]
            c.execute('INSERT INTO permission_profiles(id,name,description,levels,builtin,updated_at,updated_by) VALUES (?,?,?,?,0,?,?)',
                      (pid, name, description, json.dumps(clean), store.now(), _who()))
            what = 'created'
        store.audit(c, 'permission_profile_' + what, pid, 'users', f'{name}: ' + permissions.describe(clean))
    _forget()
    return {'id': pid, 'name': name, 'levels': clean}


def delete_profile(pid):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        r = c.execute('SELECT * FROM permission_profiles WHERE id=?', (pid,)).fetchone()
        if not r: raise LookupError('No such profile.')
        if r['builtin']: raise ValueError('A built-in profile cannot be deleted.')
        n = c.execute('SELECT count(*) FROM users WHERE profile=?', (pid,)).fetchone()[0]
        if n: raise ValueError(f'{n} {"person uses" if n == 1 else "people use"} this profile: give them another one first.')
        c.execute('DELETE FROM permission_profiles WHERE id=?', (pid,))
        store.audit(c, 'permission_profile_deleted', pid, 'users', r['name'])
    return {'deleted': pid}


_seed()
