"""What each person may do: sections, levels and the one central check for every route.

Levels: None < View < Use < Manage. A permission profile (users.py) holds a level per section; Assistants, Digital teams
and Apps hold one per assistant, team or app ('*' = every one not named). Digital teams also hold four switches per team:
run jobs, re-price, see costs and manage pricing templates.

Who gets what:
  Owner role      everything (Manage everywhere) and everyone's items.
  Admin role      their profile, plus Users and permissions, Rules and Rule packs (Manage) and other people's sign-ins.
  Member role     their profile only.
  Owner only      Health, Trading, Mileage and Backups: only an owner (users.is_owner: the Alice.Owner role in Entra, or
                  the configured owner object ID while app roles are off), whatever a profile or role on the page says.
Until Spaces arrive, anyone without the Owner role sees only the items they created themselves (substrate_store
.viewer_clause), and the parts of Alice that show everyone's material at once are Owner only (FULL below).

Every route declares its section and level in ROUTES (the test test_users_permissions fails on any route that does not).
The check runs in app.py's middleware before the route: never only by hiding a menu item. Every refusal is logged.
"""
import json
import os
import re

import substrate_store as store

LEVELS = ('none', 'view', 'use', 'manage')
RANK = {l: i for i, l in enumerate(LEVELS)}
NONE, VIEW, USE, MANAGE = 0, 1, 2, 3
TEAM_CAPS = ('run', 'reprice', 'costs', 'templates')
CAP_LABEL = {'run': 'run jobs', 'reprice': 're-price', 'costs': 'see costs', 'templates': 'manage pricing templates'}

# (key, label, menu group, levels a profile may give). Order = the Users and permissions page.
SECTIONS = [
    ('home', 'Home', '', ('none', 'view')),
    ('actions', 'Actions', '', ('none', 'view', 'manage')),
    ('chat', 'Chat', '', ('none', 'use')),
    ('temple', 'Temple', 'Workspace', ('none', 'view', 'use', 'manage')),
    ('assistants', 'Assistants page (set up assistants)', 'Workspace', ('none', 'view', 'manage')),
    ('teams', 'Digital teams page', 'Workspace', ('none', 'view', 'manage')),
    ('apps', 'Apps page', 'Workspace', ('none', 'view')),
    ('organisations', 'Organisations', 'Workspace', LEVELS),
    ('memories', 'Memories', 'Knowledge', LEVELS),
    ('knowledge', 'Knowledge', 'Knowledge', LEVELS),
    ('documents', 'Documents', 'Knowledge', LEVELS),
    ('archive', 'Saved chats (their own)', 'Knowledge', ('none', 'view', 'use', 'manage')),
    ('agents', 'Agents', 'Admin', LEVELS),
    ('activity', 'Activity (their own actions)', 'Admin', ('none', 'view')),
    ('usage', 'Usage & costs', 'Admin', ('none', 'view')),
    ('speed', 'Speed', 'Admin', ('none', 'view')),
    ('signins', 'Sign-ins (their own devices)', 'Admin', ('none', 'view', 'use')),
]
SECTION_KEYS = [s[0] for s in SECTIONS]
ROLE_SECTIONS = {'users': 'Users and permissions', 'rules': 'Rules', 'rule-packs': 'Rule packs'}   # Admin or Owner role
OWNER_ONLY = {'health': 'Health Insights', 'trading': 'Trading desk', 'mileage': 'Mileage', 'backup': 'Backups'}
# Parts of Alice that show everyone's material at once: Owner role only until Spaces (what a profile gives is not enough).
FULL_ONLY_PAGES = {'organisations', 'temple', 'actions', 'demo'}
FULL_ONLY_REASON = ('This part of Alice shows material from everyone, so until shared Spaces arrive only an Owner can use it.')


def default_levels():
    """The default Member profile: Chat, and their own saved chats. Nothing of anyone else's."""
    return clean_levels({'sections': {'chat': 'use', 'archive': 'use'}})


def clean_levels(d):
    """A profile's levels, validated: unknown sections dropped, levels limited to what each section allows."""
    d = d if isinstance(d, dict) else {}
    out = {'sections': {}, 'assistants': {}, 'teams': {}, 'apps': {}}
    sec = d.get('sections') if isinstance(d.get('sections'), dict) else {}
    for key, _label, _group, allowed in SECTIONS:
        v = str(sec.get(key, 'none')).lower()
        out['sections'][key] = v if v in allowed else ('none' if v not in LEVELS else max((a for a in allowed if RANK[a] <= RANK[v]), key=RANK.get))
    ident = re.compile(r'^(\*|[A-Za-z0-9_-]{1,80})$')
    for group in ('assistants', 'apps'):
        g = d.get(group) if isinstance(d.get(group), dict) else {}
        for k, v in list(g.items())[:200]:
            v = str(v).lower()
            if ident.fullmatch(str(k)) and v in LEVELS and not (group == 'apps' and k in OWNER_ONLY):
                out[group][str(k)] = 'use' if v == 'manage' and group == 'apps' else v
    g = d.get('teams') if isinstance(d.get('teams'), dict) else {}
    for k, v in list(g.items())[:200]:
        if not ident.fullmatch(str(k)): continue
        v = v if isinstance(v, dict) else {'level': v}
        lvl = str(v.get('level', 'none')).lower()
        if lvl not in LEVELS: lvl = 'none'
        out['teams'][str(k)] = {'level': lvl, **{c: bool(v.get(c)) and lvl != 'none' for c in TEAM_CAPS}}
    return out


def describe(levels):
    """One line for the activity log: what a profile gives (sections above None)."""
    parts = [f'{k} {v}' for k, v in levels.get('sections', {}).items() if v != 'none']
    for g in ('assistants', 'apps'):
        parts += [f'{g[:-1]} {k} {v}' for k, v in levels.get(g, {}).items() if v != 'none']
    for k, v in levels.get('teams', {}).items():
        if v['level'] != 'none':
            parts.append(f"team {k} {v['level']}" + ''.join(f' +{c}' for c in TEAM_CAPS if v.get(c)))
    return ', '.join(parts) or 'nothing'


# ---------------- levels for a person ----------------
def _trusted():
    return os.environ.get('ALICE_TRUST_EASYAUTH') == '1'


def is_owner_person(v):
    """The owner themselves (Health, Trading, Mileage, Backups and the drill, the owner rules on Users and permissions). On the
    PC whoever is at this computer is the owner. In Azure: users.is_owner, the one owner check (the Alice.Owner role in Entra,
    or the configured owner object ID only while app roles are off; never a name or email), as worked out when they were identified."""
    if not _trusted(): return v is None or v.full
    if v is None: return False
    import users
    return bool(getattr(v, 'owner', False)) or users.is_owner(v.oid, roles=[])


def full(v):
    return v is None or v.full


def _levels(v):
    import users
    with store.db() as c:
        r = c.execute('SELECT profile,status FROM users WHERE oid=?', (v.oid,)).fetchone()
    if not r or r['status'] != 'active': return clean_levels({})     # unknown or suspended: nothing at all
    return users.profile_levels(r['profile'])


def profile_of(v):
    """The person's profile levels (memoised per request)."""
    if full(v): return None
    try:
        import speed
        return speed.memo(('profile', v.oid), lambda: _levels(v))
    except Exception:
        return _levels(v)


def level(v, section, item=None):
    """0..3 for this person on a section (item: an assistant, team or app id)."""
    if section in OWNER_ONLY: return MANAGE if is_owner_person(v) else NONE
    if full(v): return MANAGE
    if section in ROLE_SECTIONS: return MANAGE if v.role == 'admin' else NONE
    if section == 'signins' and v.role == 'admin': return MANAGE        # Admins look after everyone's sign-ins
    p = profile_of(v)
    if section in ('assistant', 'app'):
        g = p['assistants' if section == 'assistant' else 'apps']
        if section == 'app' and item in OWNER_ONLY: return MANAGE if is_owner_person(v) else NONE
        return RANK[g.get(item, g.get('*', 'none'))]
    if section == 'team':
        e = p['teams'].get(item) or p['teams'].get('*') or {'level': 'none'}
        return RANK[e['level']]
    return RANK[p['sections'].get(section, 'none')]


def team_cap(v, tid, cap):
    if full(v): return True
    e = profile_of(v)['teams'].get(tid) or profile_of(v)['teams'].get('*') or {}
    return e.get('level', 'none') != 'none' and bool(e.get(cap))


def library_ok(v=None):
    """May this person read the document sources (the Documents section at View or more)?"""
    v = store.viewer() if v is None else v
    return full(v) or level(v, 'documents') >= VIEW


def can(v, section, need=VIEW, item=None):
    return level(v, section, item) >= need


def page_allowed(v, page):
    """May this person open the Console page (the menu shows only these)?"""
    if page == 'spaces': return True                       # everyone has their personal space
    if page in OWNER_ONLY: return is_owner_person(v)
    if page in ROLE_SECTIONS: return full(v) or v.role == 'admin'
    if page in FULL_ONLY_PAGES: return full(v)
    if page in SECTION_KEYS: return level(v, page) >= VIEW
    return full(v)


def allowed_pages(v, pages):
    return [p for p in pages if page_allowed(v, p)]


def first_page(v, pages):
    """Where to send someone who opened a page they may not see: the first page they may, else the chat, else nothing."""
    for p in pages:
        if page_allowed(v, p): return '/admin' + ('' if p == 'home' else '/' + p)
    return '/' if level(v, 'chat') >= USE else ''


# ---------------- the route map ----------------
# 'open'   no sign-in needed (excluded from Entra sign-in, or static files)
# 'any'    any signed-in, active person
# 'owner'  the owner only (Health, Trading, Mileage, Backups)
# 'full'   Owner role only: shows or changes everyone's material, or Alice-wide settings
# 'admin'  Admin or Owner role
# '<section>:<level>'             a section from SECTIONS at least at this level
# 'assistant:<level>'             the assistant in the path ({aid})
# 'team:<level>[:<cap>]'          the team in the path ({tid}), or in the 'team' query parameter
# 'job:<level>[:<cap>]'           the job in the path ({jid}): its team's level, and the job must be theirs
# 'page'                          /admin/{page}: the page's own section
# then any number of ' own=<item type>:<path parameter>': a person without the Owner role must have created that item.
ROUTES = {
    # no sign-in needed
    'GET /healthz': 'open', 'GET /signed-out': 'open', 'GET /signout': 'open', 'GET /static/vendor/{name}': 'open',
    'GET /static/{name}': 'open', 'GET /favicon.ico': 'open', 'GET /manifest.webmanifest': 'open', 'GET /sw.js': 'open',
    'GET /static/substrate-banner-slim.webp': 'open', 'POST /hooks/tradingview': 'open',
    'GET /me': 'any', 'POST /admin/api/speed/page': 'any',
    # chat
    'GET /': 'chat:use', 'POST /chat': 'chat:use',
    'GET /files': 'chat:use', 'POST /files': 'chat:use',
    'GET /files/{file_id}/download': 'chat:use own=file:file_id', 'DELETE /files/{file_id}': 'chat:use own=file:file_id',
    'GET /documents/{did}/download': 'any own=document:did',
    'GET /spend': 'usage:view', 'GET /chats': 'chat:use', 'GET /clients-list': 'chat:use',
    'PUT /chats/{cid}/client': 'chat:use own=chat:cid', 'GET /chats-archive-count': 'chat:use', 'POST /chats': 'chat:use',
    'GET /chats/{cid}': 'chat:use own=chat:cid', 'PATCH /chats/{cid}': 'chat:use own=chat:cid', 'DELETE /chats/{cid}': 'chat:use own=chat:cid',
    'GET /chats/{cid}/files': 'chat:use own=chat:cid', 'POST /chats/{cid}/files/{fid}': 'chat:use own=chat:cid own=file:fid',
    'DELETE /chats/{cid}/files/{fid}': 'chat:use own=chat:cid',
    'GET /voice/status': 'chat:use', 'GET /voice/voices': 'chat:use', 'POST /voice/transcribe': 'chat:use', 'POST /voice/speak': 'chat:use',
    'PUT /voice/default': 'full',
    'GET /images/{cid}/{name}': 'chat:use own=chat:cid',
    'GET /actions-count': 'full',
    'GET /admin/api/temple-chat/{cid}': 'chat:use own=chat:cid', 'POST /admin/api/temple-chat/{cid}/analyse': 'chat:use own=chat:cid',
    'PUT /admin/api/temple-chat-setting': 'full', 'POST /admin/api/temple-suggestions/{sid}': 'chat:use own=suggestion:sid',
    # pages
    'GET /admin': 'page', 'GET /admin/{page}': 'page', 'GET /admin/overview': 'any', 'GET /admin/clients': 'full',
    'GET /admin/teams/{tid}': 'team:view', 'GET /admin/teams/{tid}/start': 'team:use:run', 'GET /admin/teams/{tid}/jobs/{jid}': 'job:view',
    # owner only
    'GET /admin/api/backup': 'owner', 'GET /admin/api/backup/runbook': 'owner', 'POST /admin/api/backup/drill': 'owner',
    'GET /admin/api/mileage': 'owner', 'POST /admin/api/mileage/import': 'owner', 'POST /admin/api/mileage/places': 'owner',
    'DELETE /admin/api/mileage/places/{pid}': 'owner', 'PUT /admin/api/mileage/rate': 'owner', 'PUT /admin/api/mileage/vehicle': 'owner',
    'POST /admin/api/mileage/drafts/{did}/approve': 'owner', 'POST /admin/api/mileage/drafts/{did}/reject': 'owner',
    'GET /admin/api/trading': 'owner', 'GET /admin/api/trading/portfolios/{pid}': 'owner', 'POST /admin/api/trading/portfolios': 'owner',
    'PUT /admin/api/trading/portfolios/{pid}/kind': 'owner', 'POST /admin/api/trading/portfolios/{pid}/trades': 'owner',
    'POST /admin/api/trading/portfolios/{pid}/import': 'owner', 'POST /admin/api/trading/portfolios/{pid}/scenarios': 'owner',
    'GET /admin/api/trading/signals': 'owner', 'GET /admin/api/trading/analysis': 'owner', 'POST /admin/api/trading/signals': 'owner',
    'POST /admin/api/trading/signals/import': 'owner', 'POST /admin/api/trading/prices/refresh': 'owner',
    'POST /admin/api/trading/webhook-token': 'owner', 'GET /admin/api/trading/webhook-token': 'owner', 'PUT /admin/api/trading/ip-check': 'owner',
    'GET /admin/api/health': 'owner', 'GET /admin/api/health/documents/{did}': 'owner', 'POST /admin/api/health/upload': 'owner',
    'PUT /admin/api/health/settings': 'owner', 'PUT /admin/api/health/documents/{did}': 'owner', 'POST /admin/api/health/documents/{did}/confirm': 'owner',
    'DELETE /admin/api/health/documents/{did}': 'owner', 'POST /admin/api/health/markers/{mid}': 'owner', 'POST /admin/api/health/entries': 'owner',
    'POST /admin/api/health/entries/{eid}': 'owner',
    # users and permissions
    'GET /admin/api/users': 'admin', 'PUT /admin/api/users/{oid}': 'admin', 'POST /admin/api/permission-profiles': 'admin',
    'PUT /admin/api/permission-profiles/{pid}': 'admin', 'DELETE /admin/api/permission-profiles/{pid}': 'admin',
    'GET /admin/api/permissions/catalogue': 'admin', 'GET /admin/api/my-access': 'any',
    # spaces: everyone has at least their personal space; spaces.py decides who may manage, share or move what
    'GET /admin/api/spaces': 'any', 'GET /admin/api/spaces/mine': 'any', 'POST /admin/api/spaces': 'any', 'PUT /admin/api/spaces/default': 'any',
    'POST /admin/api/spaces/move': 'any', 'POST /admin/api/spaces/held/{mid}': 'any', 'PUT /admin/api/spaces/{sid}/members': 'any',
    'DELETE /admin/api/spaces/{sid}/members/{member}': 'any',
    # sign-ins (the handler shows other people's sessions to Admins and Owners only)
    'GET /admin/api/signins': 'signins:view', 'POST /admin/api/signins/{sid}/signout': 'signins:use', 'POST /admin/api/signout-everywhere': 'full',
    # memories (lists show a person without the Owner role only their own)
    'GET /admin/api/memories': 'memories:view', 'POST /admin/api/memories/review': 'memories:manage', 'POST /admin/api/memories/owner': 'full',
    'GET /admin/api/records': 'memories:view', 'POST /admin/api/records': 'memories:use',
    'POST /admin/api/records/{rid}/review': 'memories:manage own=record:rid', 'POST /admin/api/records/{rid}/replace': 'full',
    'POST /admin/api/records/{rid}/retire': 'memories:manage own=record:rid', 'GET /admin/api/records/{rid}/history': 'memories:view own=record:rid',
    'PUT /admin/api/memories/{rid}/review-by': 'memories:use own=record:rid',
    'GET /admin/api/categories': 'memories:view', 'POST /admin/api/categories': 'full', 'PUT /admin/api/categories/{name}': 'full',
    'DELETE /admin/api/categories/{name}': 'full', 'PUT /admin/api/categories-mode': 'full', 'POST /admin/api/categories/temple-run': 'full',
    'GET /admin/api/tags': 'memories:view', 'POST /admin/api/tags': 'full', 'PUT /admin/api/tags/{name}': 'full', 'DELETE /admin/api/tags/{name}': 'full',
    'PUT /admin/api/tags-mode': 'full', 'POST /admin/api/tags/temple-run': 'full', 'POST /admin/api/memories/tags': 'full',
    'POST /admin/api/memories/tag-suggestions': 'full', 'POST /admin/api/memories/suggestions': 'full', 'POST /admin/api/memories/category': 'full',
    'GET /admin/api/owners': 'full', 'GET /admin/api/records/{rid}/discussion': 'full', 'POST /admin/api/records/{rid}/discussion': 'full',
    # automatic approval and the approval queue
    'GET /admin/api/auto-approve': 'full', 'PUT /admin/api/auto-approve': 'full', 'GET /admin/api/decision-policy': 'full',
    'PUT /admin/api/decision-policy': 'full', 'GET /admin/api/auto-approve/connectors': 'full', 'PUT /admin/api/auto-approve/connectors': 'full',
    'POST /admin/api/actions/approve-all': 'full', 'POST /admin/api/auto-approve/undo': 'full', 'POST /admin/api/auto-approve/backlog': 'full',
    'GET /admin/api/actions': 'full', 'GET /admin/api/cards/{kind}/{ref}': 'full',
    'GET /admin/api/review-items/{key}/discussion': 'full', 'POST /admin/api/review-items/{key}/discussion': 'full',
    # home, apps, speed, usage, activity
    'GET /admin/api/home': 'home:view', 'GET /admin/api/apps': 'apps:view', 'GET /admin/api/speed': 'speed:view',
    'GET /admin/api/usage': 'usage:view', 'GET /admin/api/overview': 'full',
    'GET /admin/api/activity': 'full', 'GET /admin/api/activity-log': 'activity:view', 'GET /admin/api/activity-overview': 'full',
    'GET /admin/api/activity-log.csv': 'activity:view',
    # saved chats
    'GET /admin/api/archive': 'archive:view', 'POST /admin/api/archive/{cid}/temple-review': 'archive:use own=chat:cid',
    'POST /admin/api/import/claude-export': 'archive:manage', 'GET /admin/api/import/status': 'archive:view',
    'POST /admin/api/archive/temple-review-flagged': 'full', 'POST /admin/api/archive/{cid}/restore': 'archive:use own=chat:cid',
    # knowledge (lists show a person without the Owner role only their own)
    'GET /admin/api/knowledge': 'knowledge:view', 'GET /admin/api/knowledge/{fid}/docx': 'knowledge:view own=file:fid',
    'POST /admin/api/knowledge/{fid}/decisions': 'full', 'POST /admin/api/knowledge/note': 'knowledge:use',
    'POST /admin/api/knowledge/meeting/extract': 'knowledge:use', 'POST /admin/api/knowledge/meeting/transcript': 'knowledge:use',
    'POST /admin/api/knowledge/meeting': 'knowledge:use', 'PUT /admin/api/knowledge': 'knowledge:manage',
    'GET /admin/api/files/{fid}': 'knowledge:view own=file:fid',
    'POST /admin/api/knowledge/review': 'full', 'GET /admin/api/knowledge/{fid}/history': 'knowledge:view own=file:fid',
    'POST /admin/api/knowledge/supersede': 'full', 'GET /admin/api/knowledge/replacements': 'full', 'POST /admin/api/knowledge/replacements': 'full',
    'POST /admin/api/knowledge/find-replaced': 'full', 'POST /admin/api/knowledge/categorise': 'full', 'POST /admin/api/knowledge/suggestions': 'full',
    'GET /admin/api/knowledge-review-days': 'knowledge:view', 'PUT /admin/api/knowledge-review-days': 'full',
    # clients and organisations (everyone's: Owner role until Spaces)
    'GET /admin/api/clients': 'full', 'POST /admin/api/clients': 'full', 'PUT /admin/api/clients/{name}': 'full', 'DELETE /admin/api/clients/{name}': 'full',
    'GET /admin/api/clients/items': 'full', 'POST /admin/api/clients/tag': 'full', 'POST /admin/api/clients/suggestions': 'full',
    'POST /admin/api/clients/temple-run': 'full',
    'GET /admin/api/organisations': 'full', 'POST /admin/api/organisations': 'full', 'PUT /admin/api/organisations': 'full',
    'POST /admin/api/organisations/research': 'full', 'POST /admin/api/organisations/context': 'full', 'POST /admin/api/organisations/add': 'full',
    'GET /admin/api/organisations/research': 'full', 'GET /admin/api/organisations/searches': 'full', 'PUT /admin/api/organisations/guidance': 'full',
    'POST /admin/api/organisations/guidance/{gid}': 'full', 'GET /admin/api/search-runs/{rid}/discussion': 'full',
    'POST /admin/api/search-runs/{rid}/discussion': 'full', 'GET /admin/api/opportunities': 'full', 'POST /admin/api/opportunities/scan': 'full',
    'POST /admin/api/opportunities/schedule': 'full', 'PUT /admin/api/opportunities-expiry': 'full', 'PUT /admin/api/opportunities/{oid}': 'full',
    'PUT /admin/api/opportunities-offerings': 'full', 'GET /admin/api/organisations/facts': 'full', 'POST /admin/api/organisations/facts': 'full',
    'POST /admin/api/organisations/facts/review': 'full', 'PUT /admin/api/organisations/facts/{fid}': 'full',
    'POST /admin/api/organisations/facts/{fid}/retire': 'full', 'GET /admin/api/organisations/brief': 'full',
    'GET /admin/api/organisations/source': 'full', 'POST /admin/api/organisations/remove-source': 'full',
    'POST /admin/api/demo-data/reset': 'full',
    # rules and rule packs (Admin or Owner)
    'GET /admin/api/rules': 'admin', 'PUT /admin/api/rules': 'admin', 'PUT /admin/api/rules/{rid}': 'admin', 'POST /admin/api/rules/custom': 'admin',
    'DELETE /admin/api/rules/{rid}': 'admin', 'POST /admin/api/rules/retention/run': 'admin',
    'GET /admin/api/purview-labels': 'admin', 'PUT /admin/api/purview-labels': 'admin',
    'GET /admin/api/rule-packs/applied': 'admin', 'POST /admin/api/rule-packs/apply': 'admin', 'POST /admin/api/rule-packs/services': 'admin',
    'GET /admin/api/rule-packs': 'admin', 'POST /admin/api/rule-packs/state': 'admin', 'POST /admin/api/rule-packs/test': 'admin',
    # agents (what an agent touched lists everyone's items: Owner role)
    'GET /admin/api/agents': 'agents:view', 'GET /admin/api/agents/{aid}/runs': 'full', 'GET /admin/api/agents/{aid}/touched': 'full',
    'GET /admin/api/agents/{aid}/versions': 'agents:view', 'GET /admin/api/agent-runs/{rid}': 'full', 'PUT /admin/api/agents/{aid}': 'full',
    'POST /admin/api/agents/{aid}/acknowledge': 'agents:manage', 'POST /admin/api/agents/{aid}/status': 'agents:manage',
    # Temple (its lists and Ask Temple read everyone's material: Owner role until Spaces)
    'GET /admin/api/temple/settings': 'full', 'PUT /admin/api/temple/settings': 'full', 'GET /admin/api/temple': 'full',
    'GET /admin/api/temple/queue': 'full', 'POST /admin/api/temple/review-batch': 'full', 'GET /admin/api/temple/suggestions': 'full',
    'POST /admin/api/temple/suggestions/bulk': 'full', 'POST /admin/api/temple/{rid}/review': 'full', 'POST /admin/api/temple/ask': 'full',
    'GET /admin/api/temple/parker': 'full', 'GET /admin/api/temple/auto-approved': 'full',
    'GET /admin/api/taxonomy': 'full', 'PUT /admin/api/taxonomy/mode': 'full', 'POST /admin/api/taxonomy/review': 'full',
    'POST /admin/api/taxonomy/{cid}': 'full',
    'POST /admin/api/providers/check': 'full', 'POST /admin/api/grok/check': 'full',
    # client demo (the demo Alice only)
    'GET /admin/api/demo': 'full', 'POST /admin/api/demo/generate': 'full', 'POST /admin/api/demo/reset': 'full',
    'POST /admin/api/demo/{sid}/load': 'full', 'DELETE /admin/api/demo/{sid}': 'full',
    # documents
    'GET /admin/api/document-sources': 'documents:view', 'GET /admin/api/document-sources/files': 'documents:view',
    'POST /admin/api/document-sources': 'documents:manage',
    # assistants: the Assistants page, and each assistant's own page
    'GET /admin/api/assistants': 'assistants:view', 'POST /admin/api/assistants': 'assistants:manage',
    'PUT /admin/api/assistants/{aid}': 'assistants:manage', 'POST /admin/api/assistants/demo-hr': 'full',
    'GET /admin/api/proposal-templates': 'assistants:view', 'GET /admin/api/proposal-templates/outline': 'assistants:view',
    'GET /assistant/{aid}': 'assistant:use', 'GET /assistant/{aid}/setup': 'assistant:use', 'POST /assistant/{aid}/ask': 'assistant:use',
    'POST /assistant/{aid}/proposals': 'assistant:use', 'GET /assistant/{aid}/references': 'assistant:use',
    'POST /assistant/{aid}/references/inspect': 'assistant:use', 'POST /assistant/{aid}/references': 'assistant:use',
    'GET /assistant/{aid}/templates': 'assistant:use', 'POST /assistant/{aid}/templates/folder': 'assistants:manage',
    'POST /assistant/{aid}/templates': 'assistants:manage', 'GET /assistant/{aid}/outline': 'assistant:use',
    'POST /assistant/{aid}/rates/parse': 'assistant:use', 'POST /assistant/{aid}/parker': 'assistant:use',
    'POST /assistant/{aid}/parker/keep': 'assistant:use', 'POST /assistant/{aid}/parker/document': 'assistant:use',
    'POST /assistant/{aid}/proposals/qa-only': 'assistant:use',
    'POST /assistant/{aid}/proposals/{pid}/recheck': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/qa-upload': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/reprice': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/revise': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/template': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/suggestions/{sid}': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/suggestions/{sid}/saved': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/work': 'assistant:use', 'POST /assistant/{aid}/work/{pid}/discard': 'assistant:use own=proposal:pid',
    'GET /assistant/{aid}/proposals': 'assistant:use', 'POST /assistant/{aid}/proposals/{pid}/replaces': 'assistant:use own=proposal:pid',
    'POST /assistant/{aid}/proposals/{pid}/restore': 'assistant:use own=proposal:pid', 'GET /assistant/{aid}/proposals/{pid}': 'assistant:use own=proposal:pid',
    # digital teams
    'GET /admin/api/teams': 'teams:view', 'POST /admin/api/teams': 'teams:manage', 'GET /admin/api/teams/board': 'teams:view',
    'PUT /admin/api/teams/costs/rate': 'full',
    'GET /admin/api/teams/pricing-templates/mapping': 'team:view:templates', 'POST /admin/api/teams/pricing-templates/mapping/detect': 'full',
    'PUT /admin/api/teams/pricing-templates/mapping': 'full', 'PUT /admin/api/teams/pricing-templates/client': 'full',
    'GET /admin/api/teams/pricing-templates/all': 'full', 'PUT /admin/api/teams/pricing-templates/org-default': 'full',
    'GET /admin/api/teams/demo-project': 'teams:view', 'GET /admin/api/teams/library-files': 'documents:view',
    'POST /admin/api/teams/suggestions/{sid}': 'full',
    'GET /admin/api/teams/jobs/{jid}': 'job:view', 'GET /admin/api/teams/jobs/{jid}/page': 'job:view',
    'POST /admin/api/teams/jobs/{jid}/rates': 'job:use:reprice', 'POST /admin/api/teams/jobs/{jid}/estimate': 'job:use:reprice',
    'POST /admin/api/teams/jobs/{jid}/reprice': 'job:use:reprice', 'POST /admin/api/teams/jobs/{jid}/remeasure': 'job:use:reprice',
    'POST /admin/api/teams/jobs/{jid}/copy': 'job:use:run', 'GET /admin/api/teams/jobs/{jid}/versions': 'job:view',
    'GET /admin/api/teams/jobs/{jid}/versions/{v}': 'job:view', 'PUT /admin/api/teams/jobs/{jid}/template': 'job:use:run',
    'POST /admin/api/teams/jobs/{jid}/template/fill': 'job:use:run', 'POST /admin/api/teams/jobs/{jid}/resume': 'job:use:run',
    'POST /admin/api/teams/jobs/{jid}/stop': 'job:use:run', 'POST /admin/api/teams/steps/{sid}': 'job:use:run',
    'GET /admin/api/teams/{tid}': 'team:view', 'GET /admin/api/teams/{tid}/page': 'team:view', 'POST /admin/api/teams/{tid}/seen': 'team:view',
    'PUT /admin/api/teams/{tid}/pin': 'team:view', 'PUT /admin/api/teams/{tid}/identity': 'team:manage',
    'GET /admin/api/teams/{tid}/talk': 'team:use', 'POST /admin/api/teams/{tid}/talk': 'team:use',
    'GET /admin/api/teams/{tid}/start': 'team:use:run', 'POST /admin/api/teams/{tid}/inspect': 'team:use:run',
    'POST /admin/api/teams/{tid}/start-check': 'team:use:run', 'GET /admin/api/teams/{tid}/pricing-templates': 'team:view:templates',
    'PUT /admin/api/teams/{tid}/pricing-templates': 'team:manage:templates', 'PUT /admin/api/teams/{tid}/pricing-templates/hidden': 'team:manage',
    'POST /admin/api/teams/{tid}/pricing-templates': 'team:use:templates',
    'GET /admin/api/teams/{tid}/costs': 'team:view:costs', 'PUT /admin/api/teams/{tid}/staff/{mid}': 'full',
    'PUT /admin/api/teams/{tid}/filing': 'team:manage', 'POST /admin/api/teams/{tid}/filing/category': 'full',
    'PUT /admin/api/teams/{tid}/autonomy': 'team:manage', 'PUT /admin/api/teams/{tid}/settings': 'team:manage',
    'POST /admin/api/teams/{tid}/members': 'team:manage', 'PUT /admin/api/teams/{tid}/members/{mid}': 'team:manage',
    'DELETE /admin/api/teams/{tid}/members/{mid}': 'team:manage', 'POST /admin/api/teams/{tid}/job-types': 'team:manage',
    'PUT /admin/api/teams/{tid}/job-types/{jt}': 'team:manage', 'POST /admin/api/teams/{tid}/restore': 'team:manage',
    'GET /admin/api/teams/{tid}/members/{mid}/discussion': 'full', 'POST /admin/api/teams/{tid}/members/{mid}/discussion': 'full',
    'POST /admin/api/teams/{tid}/jobs': 'team:use:run', 'GET /admin/api/teams/{tid}/rates': 'team:view',
    'POST /admin/api/teams/{tid}/rates': 'team:manage', 'POST /admin/api/teams/{tid}/rates/demo': 'team:manage',
    'DELETE /admin/api/teams/{tid}/rates/{batch}': 'team:manage',
}
LEVEL_WORD = {'view': 'see', 'use': 'use', 'manage': 'manage'}


def _item_ok(item_type, ident, write=False):
    """Is this item in one of the person's spaces (chats and documents: theirs), and for a change, may they contribute there?"""
    if item_type == 'suggestion':          # Temple's suggestion after a chat answer: the chat must be theirs
        with store.db() as c:
            r = c.execute('SELECT chat_id FROM temple_suggestions WHERE id=?', (ident,)).fetchone()
        return bool(r) and store.can_see('chat', r[0])
    if item_type == 'step':                # a digital team's step: its job must be in their spaces
        with store.db() as c:
            r = c.execute('SELECT job_id FROM team_steps WHERE id=?', (ident,)).fetchone()
        return bool(r) and (store.can_change if write else store.can_see)('team_job', r[0])
    return (store.can_change if write else store.can_see)(item_type, ident)


def step_job(sid):
    if not sid: return ''
    with store.db() as c:
        r = c.execute('SELECT job_id FROM team_steps WHERE id=?', (sid,)).fetchone()
    return r[0] if r else ''


def job_team(jid):
    with store.db() as c:
        r = c.execute('SELECT team_id FROM team_jobs WHERE id=?', (jid,)).fetchone()
    return r[0] if r else ''


def _section_label(key):
    for k, label, _g, _l in SECTIONS:
        if k == key: return label
    return ROLE_SECTIONS.get(key) or OWNER_ONLY.get(key) or key


def check(v, spec, params, query=None, method='GET'):
    """None if this person may go ahead, else the plain reason they may not. v: store.Viewer (None = the system).
    Owners skip the section levels, never the spaces: an item outside their spaces is refused to them too."""
    if spec in ('open', 'any'): return None
    if spec == 'owner' or (spec == 'page' and (params.get('page') or 'home') in OWNER_ONLY):     # owner-only pages too, whatever the role
        return None if is_owner_person(v) else 'This part of Alice belongs to its owner only.'
    if v is None: return None
    whole = v.full
    if spec == 'full': return None if whole else FULL_ONLY_REASON
    if spec == 'admin': return None if whole or v.role == 'admin' else 'Only an Admin or an Owner of Alice can do this.'
    write = method not in ('GET', 'HEAD')
    head, *owns = spec.split()
    parts = head.split(':')
    kind = parts[0]
    if kind == 'any': parts = ['any', 'none']
    elif kind == 'page':
        if whole: return None
        page = params.get('page') or 'home'
        return None if page_allowed(v, page) else (FULL_ONLY_REASON if page in FULL_ONLY_PAGES and level(v, page) >= VIEW
                                                    else f'You do not have access to {_section_label(page)}.')
    need = RANK[parts[1]]
    if kind == 'any': pass
    elif kind == 'assistant':
        aid = params.get('aid', '')
        if not whole and level(v, 'assistant', aid) < need: return 'You do not have access to this assistant.'
    elif kind in ('team', 'job'):
        tid = params.get('tid') or (query or {}).get('team', '')
        if kind == 'job':
            jid = params.get('jid') or step_job(params.get('sid', ''))
            tid = job_team(jid)
            if not tid: return None if whole and not write else 'No such job in your spaces.'     # the route itself says "not found"
            if not (store.can_change if write else store.can_see)('team_job', jid):
                return 'This job is not in any of your spaces.'
        if not tid: return None if whole else FULL_ONLY_REASON
        if not store.can_see('team', tid): return 'This team is not in any of your spaces.'
        if not whole:
            if level(v, 'team', tid) < need: return f'You do not have permission to {LEVEL_WORD[parts[1]]} this team.'
            if len(parts) > 2 and not team_cap(v, tid, parts[2]):
                return f'Your access to this team does not include permission to {CAP_LABEL[parts[2]]}.'
    elif not whole and level(v, kind) < need:
        return f'You do not have permission to {LEVEL_WORD[parts[1]]} {_section_label(kind)}.'
    for o in owns:
        item_type, param = o[4:].split(':')
        if not _item_ok(item_type, params.get(param, ''), write):
            return 'That is not in a space you may change.' if write else 'That is not yours, or not in any of your spaces.'
    return None


def log_refusal(v, method, path, reason):
    """Every refusal goes to the activity log, with who and what (never the content of the request)."""
    try:
        import rules_engine
        if rules_engine.PREVIEW.get(): return
        with store.db() as c:
            store.audit(c, 'access_refused', f'{method} {path}'[:200], 'permissions', f"{(v.email or v.oid) if v else 'unknown'}: {reason}"[:500])
    except Exception:
        pass


def my_access(v, pages):
    """What this person may do: their role, pages and levels, for the page and the menu."""
    return {'role': 'owner' if full(v) else v.role, 'owner_person': is_owner_person(v),
            'pages': allowed_pages(v, pages), 'levels': None if full(v) else profile_of(v),
            'restricted': not full(v), 'note': '' if full(v) else 'You see only what you created yourself, until shared Spaces arrive.'}


def catalogue():
    """The sections, levels and items a profile can set (for the Users and permissions page)."""
    import assistants, teams, apps
    try: alist = [{'id': a['id'], 'name': a['name']} for a in assistants.listing()]
    except Exception: alist = []
    try: tlist = [{'id': t['id'], 'name': t['name']} for t in teams.listing()]
    except Exception: tlist = []
    return {'sections': [{'key': k, 'label': l, 'group': g, 'levels': list(lv)} for k, l, g, lv in SECTIONS],
            'role_sections': ROLE_SECTIONS, 'owner_only': OWNER_ONLY, 'full_only': sorted(FULL_ONLY_PAGES),
            'full_only_reason': FULL_ONLY_REASON,
            'assistants': alist, 'teams': tlist, 'team_caps': [{'key': c, 'label': CAP_LABEL[c]} for c in TEAM_CAPS],
            'apps': [{'id': a['id'], 'name': a['name'], 'owner_only': a['id'] in OWNER_ONLY} for a in apps.APPS],
            'levels': [{'key': l, 'label': l.capitalize()} for l in LEVELS]}
