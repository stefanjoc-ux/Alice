"""Core rules are settings, and "Human approval" became "Approval and library management" (Stefan's decisions D-0042, D-0044 and
D-0045, 10 Oct 2026). No rule is fixed in code: every rule's behaviour follows its setting; a Core rule is changed only by an Owner,
with a reason, logged in Activity with who, when and why, and reverted in one click; defaults come from config files, not code.
With the new default a routine connector memory is approved by Temple; "a person for every item" brings the old behaviour back without
a release; clashes and sensitive findings are held; overwrite and delete by models or Temple are refused and logged; Undo restores an
item exactly. Every name and item is fictional. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import asyncio, json, os, uuid
import substrate_store as store
import app
import rules_engine as R, library, autoapprove as A, temple, temple_categorise, spaces, knowledge as K, assistants, mcp_server
import clients, router, organisations
from fastapi.testclient import TestClient

cl = TestClient(app.app)
H = {'x-admin-token': app.ADMIN_TOKEN}
spaces.BACKGROUND = False
WHY = 'Test: checking the behaviour follows the setting'

# ---------------- stand-ins for Temple (no model is called) ----------------
REPORTS, ROUTES = {}, {}


def fake_review(rid):
    with store.db() as c: title = c.execute('SELECT title FROM records WHERE id=?', (rid,)).fetchone()[0]
    with store.db() as c:
        c.execute("INSERT INTO temple_reviews(id,record_id,status,provider,model,created_at,finished_at,report,context) VALUES (?,?,?,?,?,?,?,?,?)",
                  (uuid.uuid4().hex, rid, 'complete', 'openai', 'gpt-6-luna', store.now(), store.now(),
                   REPORTS.get(title, 'Recommendation: approve\nReasons: a new fact.\nConflict: no'), '{}'))
    return {'status': 'complete'}


def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='', meta=None):
    text = messages[0]['content']
    if workload == 'Temple routing':
        for k, v in ROUTES.items():
            if k in text: return json.dumps(v)
        return json.dumps({'route': 'work', 'reason': 'About the work.'})
    if workload == 'Temple sharing check':
        return json.dumps({'finding': False, 'findings': [], 'clear_because': 'Nothing personal.'})
    raise RuntimeError('no model in tests')


temple.review_record = fake_review
temple.save_settings(True, 'openai')
assistants._call = fake_call
temple_categorise.schedule = lambda ids: None          # categories are given by hand here, so nothing else changes an item meanwhile
SPAWNED = []
_spawn = store.spawn
def _tracked_spawn(*a, **k):
    th = _spawn(*a, **k); SPAWNED.append(th); return th
store.spawn = _tracked_spawn


def settle():
    while SPAWNED: SPAWNED.pop(0).join(timeout=30)


def status(rid):
    with store.db() as c: return c.execute('SELECT status FROM records WHERE id=?', (rid,)).fetchone()[0]


def activity(action, target=None):
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM activity WHERE action=? AND (? IS NULL OR target=?) ORDER BY id', (action, target, target))]


def raises(fn, kind=R.RuleViolation):
    try: fn(); return False
    except kind: return True


store.create_category('Work'); store.create_category('Family')

# ================= 1. a Core rule: an Owner, a reason, logged, reverted in one click =================
ap = R.rule('approval_required')
t('"Human approval" is now "Approval and library management", a Core rule in Memory governance',
  ap['name'] == 'Approval and library management' and ap['core'] and ap['set_key'] == 'memory')
t('its settings: who approves, what Temple may do, overwrite and delete, what is held', set(ap['params']) == {'approver', 'temple_may', 'overwrite_delete', 'hold'}
  and set(ap['params']['temple_may']) == {'approve', 'categorise', 'route', 'merge', 'supersede', 'archive'}
  and set(ap['params']['hold']) == {'sensitive', 'clash', 'unsure'} and ap['params']['overwrite_delete'] is False)
ADMIN = store.Viewer('0000e610-0000-4000-8000-0000000000aa', 'admin@northfield.example.org', 'Admin', 'admin', True)
with store.as_viewer(ADMIN):
    t('someone who is not an Owner cannot change a Core rule', raises(lambda: R.update_rule('approval_required', enabled=False, reason='I would like to'), PermissionError))
t('…and nothing changed', R.rule('approval_required')['enabled'])
r = cl.put('/admin/api/rules/approval_required', json={'enabled': False}, headers=H)
t('an Owner without a reason is refused', r.status_code == 400 and 'reason' in r.json()['detail'] and R.rule('approval_required')['enabled'])
r = cl.put('/admin/api/rules/approval_required', json={'enabled': False, 'reason': 'Pausing Temple while the library is migrated'}, headers=H)
t('an Owner with a reason changes it', r.status_code == 200 and not R.rule('approval_required')['enabled'])
log = activity('rule_updated', 'approval_required')
t('logged in Activity with who, when and why', log and log[-1]['actor'] == store.owner_name() and log[-1]['note'] == 'Pausing Temple while the library is migrated'
  and 'switched off' in log[-1]['detail'] and log[-1]['created_at'])
ch = R.history('approval_required')[0]
t('kept in the rule\'s history, with the setting before and after', ch['reason'] == 'Pausing Temple while the library is migrated'
  and ch['before']['enabled'] is True and ch['after']['enabled'] is False and ch['can_revert'] and ch['core'])
with store.as_viewer(ADMIN):
    t('someone who is not an Owner cannot revert a Core change', raises(lambda: R.revert(ch['id']), PermissionError))
r = cl.post(f"/admin/api/rules/changes/{ch['id']}/revert", json={}, headers=H)
t('reverted in one click (no reason to type: the revert says what it undid)', r.status_code == 200 and R.rule('approval_required')['enabled'])
t('…logged as a revert', activity('rule_reverted', 'approval_required') and R.history('approval_required')[1]['reverted_by'])
t('…and cannot be reverted twice', cl.post(f"/admin/api/rules/changes/{ch['id']}/revert", json={}, headers=H).status_code == 400)
t('the revert can itself be reverted', R.history('approval_required')[0]['reverts'] == ch['id'] and R.history('approval_required')[0]['can_revert'])
with store.as_viewer(ADMIN):
    R.update_rule('quality', new_params={'min_chars': 20})
t('a rule that is not Core: an Admin changes it without a reason, and it is still logged and revertible',
  R.params('quality')['min_chars'] == 20 and R.history('quality')[0]['can_revert'])
R.revert(R.history('quality')[0]['id']); t('…reverted', R.params('quality')['min_chars'] == 12)
for rid in ('share_gate', 'opus_manual', 'secret_detection', 'protective_marking'):
    t(f'{rid} is Core, and can be switched off by an Owner with a reason (no longer "always on")', R.rule(rid)['core']
      and R.update_rule(rid, enabled=False, reason=WHY)['enabled'] is False and R.update_rule(rid, enabled=True, reason=WHY)['enabled'])
page = cl.get('/admin/api/rules').json()
t('the Rules page has the history, who may change Core rules, and the approval choices', page['history'] and page['may_change_core'] is True
  and set(page['approval']['approvers']) == {'temple', 'person', 'categories'})

# ================= 2. defaults come from config files, not code =================
shipped = json.loads(R.SHIPPED_DEFAULTS.read_text(encoding='utf-8'))['rules']
t('every built-in rule\'s default is in config/rule-defaults.json', {x['id'] for x in shipped} == {b[0] for b in R.BUILTIN})
src = open(R.__file__, encoding='utf-8').read()
t('…and none is written into rules_engine.py any more', "'daily_usd': 5.0" not in src and "('secret_detection', 'security'" not in src)
saved = os.environ.pop('ALICE_AUTO_APPROVE_DEFAULT')
t('the shipped default: Temple approves under each space\'s rules, may do all six things, never overwrites or deletes, holds all three',
  next(d for d in R.defaults() if d['id'] == 'approval_required')['params'] == {'approver': 'temple', 'temple_may': {k: True for k in R.LIBRARY_ACTIONS},
                                                                                'overwrite_delete': False, 'hold': {k: True for k in R.LIBRARY_HOLDS}})
dep = _util.path('rule-defaults.json')
with open(dep, 'w', encoding='utf-8') as f:
    json.dump({'rules': {'approval_required': {'params': {'approver': 'person'}}, 'opus_manual': {'enabled': False}, 'quality': {'core': True, 'params': {'min_chars': 30}}}}, f)
d = {x['id']: x for x in R.defaults()}
t('a deployment sets its own defaults in rule-defaults.json in its data folder (only what it names changes)',
  d['approval_required']['params']['approver'] == 'person' and d['approval_required']['params']['temple_may']['route'] is True
  and d['opus_manual']['enabled'] is False and d['quality']['core'] and d['quality']['params'] == {'min_chars': 30} and d['pii']['enabled'])
os.environ['ALICE_RULE_DEFAULTS'] = _util.path('nowhere.json')
t('…or in the file ALICE_RULE_DEFAULTS names', next(x for x in R.defaults() if x['id'] == 'opus_manual')['enabled'] is True)
with open(_util.path('bad.json'), 'w') as f: f.write('{not json')
os.environ['ALICE_RULE_DEFAULTS'] = _util.path('bad.json')
t('a file that cannot be read: the shipped defaults apply, and the Rules page says why', next(x for x in R.defaults() if x['id'] == 'opus_manual')['enabled']
  and 'could not be read' in R.DEFAULTS_ERROR)
os.environ.pop('ALICE_RULE_DEFAULTS'); os.remove(dep); R.DEFAULTS_ERROR = ''
os.environ['ALICE_AUTO_APPROVE_DEFAULT'] = saved

# ================= 3. no rule's behaviour is fixed in code =================
def mem(title, content, category='', approved=True):
    rid = store.propose(title, content, 'Stefan said so')['id']; settle()
    if approved and status(rid) == 'proposed': store.review(rid, 'approved')
    if category: store.set_category([rid], category)
    return rid


R.update_rule('share_gate', new_params={'temple': False}, reason='Test: code checks only, no model')
SHARE = mem('Supplier contact', 'The supplier contact is reachable at orders@supplier.example.org for invoices.', 'Work')
TCAT = mem('Office plants', 'The office plants are watered on Mondays by whoever is in.')
store.record_temple_results([(TCAT, 'Work', 0.9, 'fits')], 'auto')
mem('Bee hives', 'Keeps four bee colonies at home in the garden.')
EXP = mem('Old printer', 'The office printer is on the second floor by the kitchen.')
R.set_review_by(EXP, '2020-01-01')
R.update_rule('external_scope', new_params={'allowed_categories': ['Work']})
CID = store.create_chat()['id']


def heavy_route():
    with store.db() as c: c.execute('UPDATE chats SET route_tier=NULL,route_calm=0 WHERE id=?', (CID,))
    return asyncio.run(router.route(CID, 'Analyse the variance in this budget and forecast next quarter', [], []))['selection']


def guidance(rid): return R.rule(rid)['text'] in R.effective_guidance('')


PROBES = {
    'secret_detection': lambda: raises(lambda: R.check_outbound('my key is sk-ant-api03-' + 'Q' * 40, 'probe', packs=False)),
    'protective_marking': lambda: raises(lambda: R.check_outbound('OFFICIAL-SENSITIVE\nDraft briefing', 'probe', packs=False)),
    'provider_allow': lambda: R.filter_records_for_provider([{'category': 'Work'}, {'category': 'Family'}], 'grok')[1],
    'external_scope': lambda: R.filter_records_for_external([{'category': 'Work'}, {'category': 'Family'}])[1],
    'pii': lambda: raises(lambda: R.check_record('Card', 'Card 4111 1111 1111 1111 for travel bookings', 'user said')),
    'data_minimisation': lambda: raises(lambda: R.check_org_fact('Northfield Council', 'Contact the team at team@northfield.example.org', 'website')),
    'share_gate': lambda: spaces.gate('record', SHARE)[0],
    'temple_category': lambda: spaces.classification('record', TCAT)[0],
    'client_separation': lambda: clients.item_filter('Acme', False)[0]('Other Co'),
    'client_documents': lambda: clients.item_filter('Acme', True)[0]('Other Co'),
    'open_spaces': lambda: spaces.open_rule(),
    'temple_router': lambda: spaces.router_on(),
    'commercial_caution': lambda: guidance('commercial_caution'),
    'ai_disclosure': lambda: guidance('ai_disclosure'),
    'working_style': lambda: guidance('working_style'),
    'uk_conventions': lambda: guidance('uk_conventions'),
    'rate_sources': lambda: 'estimate' in R.rate_sources()['allowed'],
    'retention': lambda: R.run_retention()['status'],
    'approval_required': lambda: (A.on(), library.may('route'), library.holds('clash')),
    'quality': lambda: raises(lambda: R.check_record('Short title', 'short title', 'short title')),
    'duplicates': lambda: raises(lambda: R.check_record('Bee hives', 'Keeps four bee colonies at home in the garden.', 'Stefan said so again')),
    'expiry': lambda: bool(R.annotate_records([{'id': EXP}])[0].get('possibly_out_of_date')),
    'spend_cap': lambda: R.spend_status()['level'],
    'opus_manual': heavy_route,
}
t('there is a behaviour check for every rule on the Rules page', set(PROBES) == {r['id'] for r in R.all_rules() if r['builtin']})
A.set_on(True, WHY)
for rid, probe in PROBES.items():
    was = R.rule(rid)['enabled']
    R.update_rule(rid, enabled=True, reason=WHY); on_val = probe()
    R.update_rule(rid, enabled=False, reason=WHY); off_val = probe()
    R.update_rule(rid, enabled=was, reason=WHY)
    t(f'{rid}: switching it off changes what Alice does ({on_val!r} → {off_val!r})', on_val != off_val)
R.update_rule('share_gate', new_params={'temple': True}, reason=WHY)
for rid in ('protective_marking', 'spend_cap', 'duplicates'):
    t(f'{rid}: its settings are settings too', R.history(rid)[0]['rule_id'] == rid)
R.update_rule('protective_marking', new_params={'markings': ['OFFICIAL-SENSITIVE', 'SECRET', 'TOP SECRET', 'NORTHFIELD RESTRICTED']}, reason='Our own marking')
t('protective_marking: a marking added on the Rules page is enforced', raises(lambda: R.check_outbound('NORTHFIELD RESTRICTED\nbriefing', 'probe', packs=False)))

# ================= 4. the new default: a routine connector memory is approved by Temple =================
default = next(d for d in json.loads(R.SHIPPED_DEFAULTS.read_text(encoding='utf-8'))['rules'] if d['id'] == 'approval_required')['params']
R.update_rule('approval_required', new_params=default, reason='Stefan\'s decision D-0044: Temple manages the library')
t('with the shipped default, Temple approves', A.on() and library.settings()['approver'] == 'temple')
with A.from_outside('Claude', 'claude'):
    m1 = store.propose('Meeting rooms', 'The fourth-floor meeting rooms are booked through the front desk.', 'Stefan in Claude [via Claude]')['id']
settle()
t('a routine memory from Claude is approved by Temple, with no click', status(m1) == 'approved' and A._state('memory', m1)['state'] == 'approved')
la = [x for x in library.recent() if x['item_id'] == m1 and x['action'] == 'approve']
t('…recorded as Temple\'s library action, with the reason, on Activity', la and la[0]['reason'] and la[0]['can_undo']
  and activity('library_approve', m1) and activity('library_approve', m1)[0]['actor'] == 'Temple')
acts = cl.get('/admin/api/actions', headers=H).json()
t('…and Actions does not list it (only what waits for a person)', not any(i.get('id') == m1 for s in acts['sections'] for i in s.get('items', []))
  and 'auto' not in {s['key'] for s in acts['sections']})


async def connector_texts():
    """The tool descriptions and instructions exactly as a connected app receives them (the older initialize handshake, and
    server/discover from MCP 2026-07-28)."""
    from fastmcp import Client
    async with Client(mcp_server.mcp, mode='legacy') as c:
        tools = {x.name: x.description for x in await c.list_tools()}
        instr = c.initialize_result.instructions
    async with Client(mcp_server.mcp) as c:
        d = getattr(c.session, 'discover_result', None) or getattr(c.session, '_discover_result', None)
        if d is not None and getattr(d, 'instructions', None): instr += ' ' + d.instructions
    return tools, instr


tools, instr = asyncio.run(connector_texts())
t('the connector\'s tool descriptions read the current setting', 'approves it under the rules of the space' in tools['propose_record']
  and '{approval' not in ''.join(tools.values()) and 'always wait for Stefan' not in ''.join(tools.values()))
t('…and so do its instructions', 'approves it under the rules of the space' in instr and '{approval' not in instr)
t('the tool\'s own reply says the same', 'approves it under the rules' in mcp_server.approval_text('memory'))

# ================= 5. "a person for every item" brings the old behaviour back, without a release =================
r = cl.put('/admin/api/rules/approval_required', headers=H, json={'params': {**default, 'approver': 'person'}, 'reason': 'Back to approving everything myself for a week'})
t('switched to "a person for every item" on the Rules page', r.status_code == 200 and not A.on())
with A.from_outside('Claude', 'claude'):
    m2 = store.propose('Car park', 'Visitors park in bays 12 to 20 behind the building.', 'Stefan in Claude [via Claude]')['id']
settle()
t('the next memory waits for a person, as it used to', status(m2) == 'proposed' and A._state('memory', m2) is None)
acts = cl.get('/admin/api/actions', headers=H).json()
t('…listed on Actions as awaiting approval', any(s['key'] == 'waiting' and s['title'] == 'Awaiting approval' and any(i['id'] == m2 for i in s['items']) for s in acts['sections']))
tools, instr = asyncio.run(connector_texts())
t('…and the connector now says every item waits for a person', 'waits for a person to approve it' in tools['propose_record'] and 'waits for a person' in instr)
k0 = K.create('note', 'Visitor wifi', 'Visitors use the guest network; the password is on the reception card.', 'Claude', 'model via Claude', status='draft')
t('…knowledge drafts wait too', A.knowledge_draft(k0['id']) == 'off')
cl.put('/admin/api/rules/approval_required', headers=H, json={'params': {**default, 'approver': 'categories'}, 'reason': 'Family items need me'})
A.set_policy(auto=True, categories={'Family': ''})
fam = store.propose('Dad visit', 'Dad visits in the last week of November.', 'Stefan said so')['id']
store.set_category([fam], 'Family'); settle()
with store.db() as c: c.execute('DELETE FROM auto_approvals WHERE item_id=?', (fam,))
A.after_review(fam)
t('"a person for chosen categories": an item in a chosen category waits for a person', status(fam) == 'proposed' and 'Family' in A._state('memory', fam)['reason'])
wk = store.propose('Desk booking', 'Desks are booked a day ahead in the office app.', 'Stefan said so')['id']; settle()
t('…anything else Temple approves', status(wk) == 'approved')
A.set_policy(auto=True, categories={})
R.update_rule('approval_required', new_params=default, reason='Back to the default')

# ================= 6. clashes and sensitive findings are held =================
REPORTS['Bee count'] = 'Recommendation: clarify\nReasons: says six colonies, an approved memory says four.\nConflict: yes'
m3 = store.propose('Bee count', 'Keeps six bee colonies at home now.', 'Stefan said so')['id']; settle()
t('a clash is held for a person, saying why', status(m3) == 'proposed' and 'Clashes' in A._state('memory', m3)['reason'])
R.update_rule('approval_required', new_params={**default, 'hold': {**default['hold'], 'clash': False}}, reason='Test: clashes noted, not held')
REPORTS['Bee count again'] = REPORTS['Bee count']
m3b = store.propose('Bee count again', 'Keeps five bee colonies at home now.', 'Stefan said so')['id']; settle()
t('…with "clashes" unticked, Temple approves it and notes the clash', status(m3b) == 'approved' and 'clash' in A._state('memory', m3b)['reason'])
R.update_rule('approval_required', new_params=default, reason='Back to the default')

for rid in ('temple_router', 'open_spaces'): R.update_rule(rid, enabled=True, reason=WHY)
ROUTES['Dev Patel'] = {'route': 'sensitive', 'reason': 'About a named employee\'s absence.'}
ROUTES['something or other'] = {'route': 'unsure', 'reason': 'Too vague to place.'}


ME = store.Viewer('', '', 'Owner', 'owner', True)       # whoever is at this computer, the owner: new items are captured for "Owner: work"


def capture(title, content):
    with store.as_viewer(ME):
        rid = store.propose(title, content, 'Stefan said so')['id']
        store.set_category([rid], 'Work'); settle()
    with store.db() as c:
        return rid, c.execute("SELECT * FROM space_moves WHERE item_id=? AND kind='capture' ORDER BY created_at DESC LIMIT 1", (rid,)).fetchone()


s1, mv = capture('Absence', 'Dev Patel has been off since Monday; cover is arranged.')
t('a sensitive finding is held for a person (no restricted space to route it to)', mv and mv['status'] == 'held' and mv['screened_by'] == 'route_sensitive'
  and spaces.space_of('record', s1) != spaces.WORK)
s2, mv = capture('Vague', 'something or other about the thing we said')
t('…and so is anything Temple is unsure about', mv and mv['status'] == 'held' and mv['screened_by'] == 'route_unsure')
R.update_rule('approval_required', new_params={**default, 'hold': {'sensitive': False, 'clash': True, 'unsure': False}}, reason='Test: not held')
s3, mv = capture('Absence 2', 'Dev Patel is back on Thursday; cover ends Wednesday.')
t('with "sensitive findings" unticked, it is never shared: it stays in its author\'s personal space', mv and mv['status'] == 'kept'
  and spaces.space_of('record', s3) == spaces.space_of('record', s1))
keep = [x for x in library.recent() if x['item_id'] == s3 and x['action'] == 'keep']
t('…Temple\'s action is on Activity with the reason', keep and 'named employee' in keep[0]['reason'])
cl.post(f"/admin/api/library/{keep[0]['id']}/undo", json={}, headers=H)
with store.db() as c: st = c.execute('SELECT status FROM space_moves WHERE id=?', (mv['id'],)).fetchone()[0]
t('…and Undo puts it back to wait for a person', st == 'held')
R.update_rule('approval_required', new_params=default, reason='Back to the default')
for rid in ('temple_router', 'open_spaces'): R.update_rule(rid, enabled=False, reason=WHY)

# ================= 7. overwrite and delete by models or Temple: off, refused and logged =================
note = K.create('note', 'Supplier list', 'Three fictional suppliers: Ash Ltd, Birch Ltd and Cedar Ltd.', 'Stefan', 'Stefan', status='active')['id']
with store.acting('Temple'):
    t('Temple cannot overwrite a library item', raises(lambda: K.update(note, title='Rewritten by Temple')))
    t('…or delete one', raises(lambda: K.forget(note)))
with A.from_outside('Microsoft Copilot', 'copilot'):
    t('…nor can a model through the connector', raises(lambda: K.update(note, title='Rewritten by Copilot')))
t('the original is kept', K.meta([note])[note]['title'] == 'Supplier list')
blocks = [b for b in activity('rule_blocked') if b['rule'] == 'approval_required']
t('each attempt is logged by the rule, saying who tried what', len(blocks) >= 3 and any('Temple tried to overwrite' in b['detail'] for b in blocks)
  and any('Temple tried to delete' in b['detail'] for b in blocks) and any('Microsoft Copilot tried to overwrite' in b['detail'] for b in blocks))
t('a person\'s own edit is never stopped by it', K.update(note, title='Supplier list 2026')['title'] == 'Supplier list 2026')
R.update_rule('approval_required', new_params={**default, 'overwrite_delete': True}, reason='Test: allowed for a moment')
with store.acting('Temple'): K.update(note, title='Supplier list (tidied by Temple)')
t('switched on: allowed, and logged', K.meta([note])[note]['title'] == 'Supplier list (tidied by Temple)' and activity('library_overwrite', note))
R.update_rule('approval_required', new_params=default, reason='Back to the default')
tools, _ = asyncio.run(connector_texts())

# ================= 8. Undo restores the item exactly =================
TABLES = (('records', 'id'), ('record_meta', 'record_id'), ('memory_archive', 'record_id'), ('item_spaces', 'item_id'))


def exact(*ids):
    out = {}
    with store.db() as c:
        for rid in ids:
            c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (rid,))   # a missing metadata row reads as its defaults
            for table, col in TABLES:
                out[(table, rid)] = [{k: v for k, v in dict(r).items() if k not in library.IGNORE}
                                     for r in c.execute(f'SELECT * FROM {table} WHERE {col}=?', (rid,))]
    return out


old = mem('Dog name', 'The dog is called Lexi.', 'Family')
REPORTS['Dog name update'] = f'Recommendation: approve\nReasons: newer.\nReplaces: {old}\nConflict: no'
new = store.propose('Dog name update', 'The dog Lexi is a spaniel.', 'Stefan said so')['id']
SPAWNED.pop(0).join(timeout=30) if SPAWNED else None
before = exact(new, old)
with store.db() as c: c.execute('DELETE FROM auto_approvals WHERE item_id=?', (new,))
A.after_review(new)
with store.db() as c: arch = c.execute('SELECT state,replaced_by FROM memory_archive WHERE record_id=?', (old,)).fetchone()
t('Temple supersedes the older memory: the new one approved, the old one kept and linked to it', status(new) == 'approved' and arch
  and arch['state'] == 'superseded' and arch['replaced_by'] == new)
sup = next(x for x in library.recent() if x['action'] == 'supersede' and x['item_id'] == new)
t('…a library action naming both, with the reason', set(sup['items']) == {f'record:{new}', f'record:{old}'} and 'replaces' in sup['reason'].lower())
r = cl.post(f"/admin/api/library/{sup['id']}/undo", json={'note': 'Lexi is a cocker spaniel; I will reword it'}, headers=H)
t('Undo puts both back exactly as they were, row for row', r.status_code == 200 and exact(new, old) == before)
t('…the undone approval waits for a person (Temple does not approve it again)', status(new) == 'proposed' and A._state('memory', new)['state'] == 'held')
t('…logged, and cannot be undone twice', activity('library_undone', new) and cl.post(f"/admin/api/library/{sup['id']}/undo", json={}, headers=H).status_code == 409)
cat = store.propose('Gym times', 'The office gym opens at 6am on weekdays.', 'Stefan said so')['id']; settle()
before = exact(cat)
temple_categorise._ask = lambda payload: json.dumps({'assignments': [{'id': m['id'], 'category': 'Work', 'confidence': 0.9, 'reason': 'An office matter.'}
                                                                     for m in json.loads(payload)['memories']]})
temple_categorise.run([cat])
c1 = next(x for x in library.recent() if x['action'] == 'categorise' and x['item_id'] == cat)
t('Temple\'s categorising is a library action too, with its reason', c1['reason'] == 'An office matter.')
library.undo(c1['id'])
t('…undone exactly, and Temple does not put it back', exact(cat) == before and temple_categorise.run([cat]).get('applied', 0) == 0)
R.update_rule('approval_required', new_params={**default, 'temple_may': {**default['temple_may'], 'categorise': False}}, reason='Test: suggest only')
cat2 = store.propose('Bike racks', 'Bike racks are in the basement car park.', 'Stefan said so')['id']; settle()
temple_categorise.run([cat2])
with store.db() as c: rm = c.execute('SELECT category,suggestion FROM record_meta WHERE record_id=?', (cat2,)).fetchone()
t('with "categorise" unticked, Temple only suggests a category', rm['category'] == '' and rm['suggestion'] == 'Work')
R.update_rule('approval_required', new_params=default, reason='Back to the default')
lib = cl.get('/admin/api/library?days=7', headers=H).json()
t('Activity lists Temple\'s library actions with their reasons', lib['items'] and all('reason' in x and 'label' in x for x in lib['items'])
  and 'approves it under the rules' in lib['describe'])
import activity_log
t('activity labels for the new actions', all(a in activity_log.LABELS for a in ('library_approve', 'library_supersede', 'library_undone', 'rule_reverted', 'library_keep')))
