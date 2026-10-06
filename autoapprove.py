"""Automatic approval (Stefan's decision, 3 Oct 2026): to keep Alice from being admin, memories, knowledge drafts,
organisation facts and Temple's memory/knowledge suggestions go live without a click. What still waits for him:

- Decisions: Temple manages them (Stefan's decision, 5 Oct 2026). They are working decisions made by signed-in people, not
  board decisions, so Temple records each one once checked, with who made it, clashes included (Alice records, she does not
  mediate: a clash is noted with the decision). The only decisions that wait are the ones the decision policy asks for:
  categories that always need approval, and/or Temple's impact rating at or above a level. Those are held on Actions and
  emailed to the category's owner (or the default approver) by notify.py. Settings key 'decision_policy' (JSON).
- Anything that changes behaviour or removes something: rule and guidance suggestions, and "this replaces that"
  suggestions (retiring older knowledge or memories). Their existing approval paths are unchanged.
- A new memory that clashes: Temple's review says it contradicts an approved memory or decision ('Conflict: yes'),
  recommends rejecting it, says it replaces an older memory, or could not check it.
- Anything proposed through the outside connector (Copilot, the signed-in endpoint): it reads documents and web pages
  Stefan does not control, so a page saying "remember that…" must not become a live memory. Exception (Stefan's decision
  D-0026, 6 Oct 2026): knowledge notes from an outside app switched on in 'connector_knowledge' (Claude and Copilot by
  default; switches on Actions) are approved after the same checks, unless Temple's free checks (`temple_supersede.overlaps`)
  or the proposer say it may replace or overlap something Alice holds: those wait for him.

The security rules still run when anything is proposed and again on approval (secrets, protective markings, personal
identifiers, duplicates, client separation): automatic approval never skips them. Each automatic approval is logged
('auto_approved', actor Alice) and listed on Actions for 7 days with Undo (retire or archive; history kept).
Switch: settings key 'auto_approve' ('true'/'false'), on the Actions page."""
import contextvars
import json
import os
import re
import threading

import substrate_store as store

_outside = contextvars.ContextVar('alice_auto_outside', default='')
_outside_provider = contextvars.ContextVar('alice_auto_outside_provider', default='')
CONNECTOR_APPS = {'claude': 'Claude', 'copilot': 'Microsoft Copilot'}
_deciding = contextvars.ContextVar('alice_auto_deciding', default=False)
TYPES = {'memory': 'Memory', 'knowledge': 'Knowledge', 'orgfact': 'Organisation fact', 'chat': 'Saved conversation'}
IMPACT = re.compile(r'^\W*impact\W*[:\-]?\s*(low|medium|high)\b', re.I | re.M)
LEVELS = {'low': 1, 'medium': 2, 'high': 3}
EMAIL = re.compile(r"[A-Za-z0-9._%+'\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
OLD_HOLD = 'A decision: decisions always wait for you.'
CONFLICT = re.compile(r'^\W*conflict\W*(yes|no)\b', re.I | re.M)
WHY = re.compile(r'^\W*why it is a decision\W*[:\-]\s*(.+)$', re.I | re.M)
FOR = re.compile(r'^\W*what it is for\W*[:\-]\s*(.+)$', re.I | re.M)


def _schema():
    with store.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS auto_approvals (item_type TEXT NOT NULL, item_id TEXT NOT NULL, state TEXT NOT NULL, "
                  "reason TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, undone_at TEXT, PRIMARY KEY (item_type,item_id))")
        default = 'false' if os.getenv('ALICE_AUTO_APPROVE_DEFAULT') == 'off' else 'true'   # only for a brand-new database
        c.execute("INSERT OR IGNORE INTO settings VALUES ('auto_approve',?)", (default,))
        c.execute("INSERT OR IGNORE INTO settings VALUES ('connector_knowledge',?)", (json.dumps({k: True for k in CONNECTOR_APPS}),))
        c.execute("INSERT OR IGNORE INTO settings VALUES ('decision_policy',?)",
                  (json.dumps({'auto': True, 'categories': {}, 'impact': 'off', 'approver': ''}),))


_schema()


def on():
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='auto_approve'").fetchone()
    return not row or row[0] == 'true'


def set_on(value):
    with store.db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='auto_approve'", ('true' if value else 'false',))
        store.audit(c, 'auto_approve_setting', 'Alice', 'human_control', 'Automatic approval ' + ('on' if value else 'off'))
    return {'on': bool(value)}


# ---------------- who proposed it ----------------
class from_outside:
    """with from_outside('Microsoft Copilot', 'copilot'): ... — proposals made inside are held for Stefan ('' = trusted caller),
    except knowledge notes from an app switched on in connector_knowledge()."""
    def __init__(self, label, provider=''): self.label, self.provider = label or '', (provider or '').lower()
    def __enter__(self): self.t = (_outside.set(self.label), _outside_provider.set(self.provider)); return self
    def __exit__(self, *a): _outside.reset(self.t[0]); _outside_provider.reset(self.t[1])


def connector_knowledge():
    """{app: True|False}: knowledge notes from that outside app are approved after Alice's checks (D-0026)."""
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='connector_knowledge'").fetchone()
    try: v = json.loads(row[0]) if row else {}
    except ValueError: v = {}
    return {k: bool(v.get(k, False)) for k in CONNECTOR_APPS}


def set_connector_knowledge(apps):
    cur = connector_knowledge()
    new = {k: bool(apps.get(k, cur[k])) for k in CONNECTOR_APPS}
    with store.db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='connector_knowledge'", (json.dumps(new),))
        store.audit(c, 'connector_knowledge_setting', 'Alice', 'human_control',
                    'Notes from outside apps approved after checks: ' + (', '.join(CONNECTOR_APPS[k] for k, v in new.items() if v) or 'none'))
    return new


def _app_of(label, provider=''):
    p = (provider or '').lower()
    if p in CONNECTOR_APPS: return p
    t = (label or '').lower()
    return 'copilot' if 'copilot' in t else 'claude' if 'claude' in t else ''


def deciding(): return _deciding.get()


def outside(): return _outside.get()


# ---------------- state ----------------
def _state(item_type, item_id):
    with store.db() as c:
        r = c.execute('SELECT state,reason FROM auto_approvals WHERE item_type=? AND item_id=?', (item_type, item_id)).fetchone()
    return dict(r) if r else None


def _mark(c, item_type, item_id, state, reason):
    c.execute('INSERT INTO auto_approvals(item_type,item_id,state,reason,at) VALUES (?,?,?,?,?) '
              'ON CONFLICT(item_type,item_id) DO UPDATE SET state=excluded.state,reason=excluded.reason,at=excluded.at,undone_at=NULL',
              (item_type, item_id, state, reason[:300], store.now()))


def hold(item_type, item_id, reason):
    with store.db() as c:
        _mark(c, item_type, item_id, 'held', reason)
        store.audit(c, 'auto_held', item_id, 'approval_required', f'{TYPES.get(item_type, item_type)} held for you: {reason}'[:500])


def _approved(item_type, item_id, note):
    with store.db() as c:
        _mark(c, item_type, item_id, 'approved', note)
        store.audit(c, 'auto_approved', item_id, 'automatic_safeguard', f'{TYPES.get(item_type, item_type)} approved automatically: {note}'[:500])


# ---------------- memories ----------------
def _latest_review(rid):
    with store.db() as c:
        r = c.execute('SELECT status,report,error FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC,id LIMIT 1', (rid,)).fetchone()
    return dict(r) if r else None


def _title(c, rid):
    r = c.execute('SELECT title FROM records WHERE id=?', (rid,)).fetchone()
    return r[0] if r else ''


def after_review(rid, reviewed=True):
    """Called once Temple's review of a new memory has finished (or straight away when reviews are off)."""
    import temple
    if not on(): return
    st = _state('memory', rid)
    if st and not (st['state'] == 'held' and st['reason'] == OLD_HOLD and managing_decisions()): return
    with store.db() as c:
        row = c.execute("SELECT r.status,coalesce(m.kind,'fact') AS kind FROM records r LEFT JOIN record_meta m ON m.record_id=r.id WHERE r.id=?", (rid,)).fetchone()
    if not row or row['status'] != 'proposed': return
    if row['kind'] == 'decision': decide_decision(rid, reviewed); return
    note = 'not checked for clashes (Temple reviews are off)'
    if reviewed:
        rv = _latest_review(rid)
        if not rv or rv['status'] != 'complete':
            hold('memory', rid, 'Temple could not check it for clashes' + (f": {rv['error']}" if rv and rv.get('error') else '') + '.'); return
        report, verdict = rv['report'] or '', temple.verdict(rv)
        rep = temple.REPLACES.search(report)
        if rep:
            with store.db() as c: old = _title(c, rep.group(1))
            hold('memory', rid, f'Temple thinks it replaces “{old or rep.group(1)[:8]}”: you choose whether to retire the older one.'); return
        clash = CONFLICT.search(report)
        if (clash and clash.group(1).lower() == 'yes') or verdict == 'reject':
            why = temple.reason_line(report) or 'Temple found a clash with what Alice already holds.'
            hold('memory', rid, ('Clashes with an approved memory: ' if clash and clash.group(1).lower() == 'yes' else 'Temple recommends rejecting it: ') + why); return
        note = f'Temple: {verdict}, no clash'
    try:
        with store.acting('Alice', note='Approved automatically: ' + note):
            store.review(rid, 'approved')
    except ValueError as e:
        hold('memory', rid, f'Not approved automatically: {e}'); return
    _approved('memory', rid, note)


def review_then_decide(rid):
    """Background: Temple reviews the memory, then automatic approval decides."""
    import temple
    def work():
        try: temple.review_record(rid)
        except Exception: pass
        try: after_review(rid)
        except Exception: pass
    threading.Thread(target=work, daemon=True).start()


# ---------------- knowledge drafts and organisation facts ----------------
OUTSIDE_HOLD = 'through the outside connector: it reads material you do not control.'
OLD_OUTSIDE_HOLD = 'Proposed through the outside connector before automatic approval.'


def knowledge_draft(fid, again=False):
    import knowledge
    if not fid or (_state('knowledge', fid) and not again): return 'already'
    if not on(): return 'off'
    note = 'draft from a trusted source'
    if outside():
        app = _app_of(outside(), _outside_provider.get())
        if not connector_knowledge().get(app):
            hold('knowledge', fid, f'Proposed by {outside()} {OUTSIDE_HOLD}'); return 'held'
        import temple_supersede      # Temple's free checks: does it say it replaces, or closely overlap, something Alice holds?
        named = [p['old_title'] for p in knowledge.replacements('pending', new_id=fid)]
        near = named + [t for t in temple_supersede.overlaps(fid) if t not in named]
        if near:
            hold('knowledge', fid, f'Proposed by {outside()} through the outside connector, and it may replace or overlap '
                 + ', '.join('“' + t + '”' for t in near[:3]) + ': you decide.'); return 'held'
        note = f'note from {outside()} (outside connector); Temple found no clash'
    with store.acting('Alice', note='Approved automatically'):
        r = knowledge.review([fid], 'approved')
    if r['changed']: _approved('knowledge', fid, note); return 'approved'
    if r['blocked']: hold('knowledge', fid, 'Not approved automatically: ' + ' '.join(r['block_reasons'])); return 'held'
    return 'skipped'


def org_fact(fid):
    import organisations
    if not fid or _state('orgfact', fid): return 'already'
    if not on(): return 'off'
    if outside():
        hold('orgfact', fid, f'Proposed by {outside()} through the outside connector.'); return 'held'
    with store.acting('Alice', note='Approved automatically'):
        r = organisations.review_facts([fid], 'approved')
    if r.get('changed'): _approved('orgfact', fid, 'proposed with a source'); return 'approved'
    if r.get('blocked'): hold('orgfact', fid, 'Not approved automatically: ' + ' '.join(r.get('block_reasons') or [])); return 'held'
    return 'skipped'


# ---------------- Temple's chat suggestions ----------------
def accept_suggestion(sid, content):
    """Accept one of Temple's chat suggestions (the same path as the Accept button). Returns the act() result."""
    import clients, knowledge, rules_engine, temple_chat
    with store.db() as c:
        srow = c.execute('SELECT s.*,ch.client FROM temple_suggestions s LEFT JOIN chats ch ON ch.id=s.chat_id WHERE s.id=?', (sid,)).fetchone()
    if not srow: raise ValueError('Suggestion not found.')
    if srow['kind'] in ('memory', 'knowledge'):
        rules_engine.check_record(srow['title'], content, 'Your words in chat: ' + srow['quote'], stage=srow['kind'])
    elif srow['kind'] != 'decision':
        rules_engine.check_outbound(content, 'guidance', packs=False)
    if srow['kind'] == 'decision':          # decisions become structured decision proposals (which wait for you)
        if srow['status'] in ('accepted', 'dismissed'): raise ValueError('This suggestion has already been handled.')
        d = store.parse_decision(content)
        r = store.propose_decision(srow['title'], d['decision'], f"Chat {srow['chat_id']}: {srow['quote']}", d['rationale'], d['options'], d['revisit'])
        with store.db() as c:
            c.execute("UPDATE temple_suggestions SET status='accepted',target=?,content=? WHERE id=?", (r.get('id', ''), content.strip(), sid))
            store.audit(c, 'temple_suggestion_accepted', sid, 'human_review', 'decision → ' + r.get('id', ''))
        if srow['client'] and r.get('id'): clients.tag('memory', [r['id']], srow['client'], 'chat')
        return {'status': 'accepted', 'target': r.get('id', '')}
    result = temple_chat.act(sid, 'accept', content)
    if result.get('target') and srow['client'] and srow['kind'] in ('memory', 'knowledge'):   # captures inherit the chat's client
        clients.tag('memory' if srow['kind'] == 'memory' else 'file', [result['target']], srow['client'], 'chat')
        if srow['kind'] == 'knowledge': knowledge.update(result['target'], label='client', audit_it=False)
    return result


def suggestions_for_chat(cid):
    """After Temple suggests things from a chat: memories and knowledge notes are accepted (memories then go through the
    same clash check), decisions become decision proposals for you; guidance and rule requests stay as suggestions."""
    if not on() or _state('chat', cid): return {'accepted': 0}      # a conversation saved through the outside connector: you decide
    with store.db() as c:
        rows = [dict(r) for r in c.execute("SELECT id,kind,content FROM temple_suggestions WHERE chat_id=? AND status='pending' "
                                           "AND kind IN ('memory','knowledge','decision')", (cid,))]
    done = 0
    for r in rows:
        try:
            with store.acting('Alice', note='Accepted automatically'):
                res = accept_suggestion(r['id'], r['content'])
            done += 1
            if r['kind'] == 'knowledge' and res.get('target'): _approved('knowledge', res['target'], "Temple's note from your own words")
        except Exception:
            pass                        # stays as a suggestion for you
    return {'accepted': done}


# ---------------- what was approved, what is held, undo ----------------
def recent(days=7, limit=200):
    from datetime import datetime, timedelta, timezone
    import refs
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store.db() as c:
        rows = [dict(r) for r in c.execute("SELECT item_type,item_id,reason,at FROM auto_approvals WHERE state='approved' AND undone_at IS NULL "
                                           "AND at>=? ORDER BY at DESC LIMIT ?", (since, limit))]
        for r in rows:
            if r['item_type'] == 'memory': x = c.execute('SELECT title FROM records WHERE id=?', (r['item_id'],)).fetchone()
            elif r['item_type'] == 'knowledge': x = (c.execute('SELECT title FROM knowledge_meta WHERE file_id=?', (r['item_id'],)).fetchone()
                                                     or c.execute('SELECT name FROM files WHERE id=?', (r['item_id'],)).fetchone())
            else: x = c.execute("SELECT org || ': ' || statement FROM org_facts WHERE id=?", (r['item_id'],)).fetchone()
            r['title'] = x[0] if x else '(deleted)'
    rec, fil = refs.of('record', [r['item_id'] for r in rows if r['item_type'] == 'memory']), refs.of('file', [r['item_id'] for r in rows if r['item_type'] == 'knowledge'])
    for r in rows: r['ref'] = rec.get(r['item_id']) or fil.get(r['item_id']) or ''
    return rows


def held():
    with store.db() as c:
        return {(r['item_type'], r['item_id']): r['reason'] for r in c.execute("SELECT item_type,item_id,reason FROM auto_approvals WHERE state='held'")}


def undo(item_type, item_id):
    import knowledge, organisations
    st = _state(item_type, item_id)
    if not st or st['state'] != 'approved': raise ValueError('That was not approved automatically, or has already been undone.')
    reason = 'Undone after automatic approval'
    with store.acting(note=reason):
        if item_type == 'memory': store.retire_memory(item_id, reason)
        elif item_type == 'knowledge': knowledge.update(item_id, status='archived')
        elif item_type == 'orgfact': organisations.retire_fact(item_id, reason)
        else: raise ValueError('Unknown item.')
    with store.db() as c:
        c.execute('UPDATE auto_approvals SET undone_at=? WHERE item_type=? AND item_id=?', (store.now(), item_type, item_id))
        store.audit(c, 'auto_undone', item_id, 'human_review', f'{TYPES.get(item_type, item_type)} taken back out (history kept)')
    return {'undone': True}


def backlog():
    """Apply automatic approval to what was already waiting before it was switched on (not decisions, not held items)."""
    import knowledge, organisations, temple
    if not on(): raise ValueError('Automatic approval is off.')
    hl = held()
    with store.db() as c:
        mems = [r[0] for r in c.execute("SELECT r.id FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id LEFT JOIN record_meta m ON m.record_id=r.id "
                                        "WHERE coalesce(a.state,r.status)='proposed' AND coalesce(m.kind,'fact')<>'decision'")]
        decs = [r[0] for r in c.execute("SELECT r.id FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id JOIN record_meta m ON m.record_id=r.id "
                                        "WHERE coalesce(a.state,r.status)='proposed' AND m.kind='decision'")]
        chats = [r[0] for r in c.execute("SELECT DISTINCT chat_id FROM temple_suggestions WHERE status='pending' AND kind IN ('memory','knowledge','decision')")]
    mems = [m for m in mems if ('memory', m) not in hl]
    started = 0
    for rid in mems:
        rv = _latest_review(rid)
        if rv and rv['status'] == 'complete': after_review(rid)
        elif temple.settings()['enabled']: review_then_decide(rid); started += 1
        else: after_review(rid, reviewed=False)
    allowed, drafts = connector_knowledge(), []
    for i in knowledge.listing(status='draft', limit=100000)['items']:
        fid, why = i['id'], hl.get(('knowledge', i['id']))
        m = knowledge.meta([fid]).get(fid) or {}
        who = m.get('added_by', '') + ' ' + m.get('source', '')
        app = _app_of(who) if ('via ' in who.lower() and 'web chat' not in who.lower()) else ''
        if why is not None and not (app and (why == OLD_OUTSIDE_HOLD or why.endswith(OUTSIDE_HOLD))): continue
        drafts.append(fid)
        if app:          # from an outside app: run again under D-0026 (or stay held if that app is switched off)
            label = CONNECTOR_APPS[app]
            if not allowed.get(app):
                if why is None: hold('knowledge', fid, f'Proposed by {label} {OUTSIDE_HOLD}')
                continue
            with from_outside(label, app): knowledge_draft(fid, again=True)
        else: knowledge_draft(fid)
    facts = [f['id'] for f in organisations.pending(limit=100000) if ('orgfact', f['id']) not in hl]
    for fid in facts: org_fact(fid)
    sugg = 0
    for cid in chats: sugg += suggestions_for_chat(cid)['accepted']
    ndec = 0
    if managing_decisions():                   # decisions waiting from before Temple managed them: same checks as new ones
        for rid in decs:
            st = _state('memory', rid)
            if st and st['state'] == 'held' and st['reason'] != OLD_HOLD: continue      # held by the policy: stays
            ndec += 1
            rv = _latest_review(rid)
            if rv and rv['status'] == 'complete': decide_decision(rid, force=True)
            elif temple.settings()['enabled']: review_then_decide(rid); started += 1
            else: decide_decision(rid, reviewed=False, force=True)
    return {'memories': len(mems), 'checking': started, 'drafts': len(drafts), 'facts': len(facts), 'suggestions': sugg, 'decisions': ndec}


# ---------------- decisions, explained ----------------
def explain_decision(item):
    """item: a temple.queue() row for a proposed decision. Adds why it is a decision, what it is for and the recommendation."""
    import clients, temple
    meta = (store.record_kinds([item['id']]).get(item['id']) or {}).get('decision') or store.parse_decision(item['content'])
    latest = (item.get('reviews') or [None])[0]
    report = latest['report'] if latest and latest.get('status') == 'complete' else ''
    why = WHY.search(report); what = FOR.search(report)
    opts = [o for o in meta.get('options') or [] if o]
    if why: why_text = why.group(1).strip()
    elif opts: why_text = 'It chooses one option over ' + ('the others considered' if len(opts) > 1 else 'an alternative') + ': later work should follow it.'
    else: why_text = 'It records a choice made, not just a fact: later work should follow it until it is revisited.'
    client = clients.clients_for('memory', [item['id']]).get(item['id'], '')
    source = item.get('source') or ''
    m = re.match(r'Chat ([0-9a-f]{32})', source)
    if m:
        with store.db() as c:
            t = c.execute('SELECT title FROM chats WHERE id=?', (m.group(1),)).fetchone()
        source = 'From the chat “' + (t[0] if t else 'deleted chat') + '”' + source[m.end():][:160]
    where = ', '.join(x for x in [client and f'client {client}', item.get('category') and f'category {item["category"]}'] if x)
    what_text = what.group(1).strip() if what else (f'Applies to {where}.' if where else 'General: not tied to a client.')
    rec = temple.verdict(latest)
    clash = CONFLICT.search(report)
    return {'decision': meta.get('decision') or item['content'], 'why_decision': why_text[:300], 'for': what_text[:300],
            'rationale': meta.get('rationale', ''), 'options': opts, 'revisit': meta.get('revisit', ''), 'review_by': item.get('review_by'),
            'source': source[:300], 'client': client, 'recommendation': rec, 'reason': temple.reason_line(report) if report else '',
            'clash': bool(clash and clash.group(1).lower() == 'yes')}


# ---------------- decisions: Temple manages them ----------------
def policy():
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='decision_policy'").fetchone()
    try: p = json.loads(row[0]) if row else {}
    except ValueError: p = {}
    return {'auto': p.get('auto', True) is not False, 'categories': dict(p.get('categories') or {}),
            'impact': p.get('impact') if p.get('impact') in ('off', 'high', 'medium') else 'off', 'approver': p.get('approver') or ''}


def set_policy(auto=True, categories=None, impact='off', approver=''):
    """categories: {category name: owner email ('' = the default approver)}; impact: 'off', 'high' or 'medium' (and above)."""
    known = {x['name'] for x in store.list_categories()['categories']}
    cats = {}
    for name, mail in (categories or {}).items():
        name = ' '.join(str(name).split())
        if name not in known: raise ValueError(f'No category called {name}.')
        mail = (mail or '').strip()
        if mail and not EMAIL.fullmatch(mail): raise ValueError(f'"{mail[:80]}" is not an email address (owner of {name}).')
        cats[name] = mail
    if impact not in ('off', 'high', 'medium'): raise ValueError('Impact is off, high, or medium (and above).')
    approver = (approver or '').strip()
    if approver and not EMAIL.fullmatch(approver): raise ValueError(f'"{approver[:80]}" is not an email address.')
    p = {'auto': bool(auto), 'categories': cats, 'impact': impact, 'approver': approver}
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES ('decision_policy',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(p),))
        store.audit(c, 'decision_policy', 'Alice', 'human_control',
                    ('Temple manages decisions' if p['auto'] else 'Decisions wait for you') +
                    (f"; approval needed in {', '.join(cats)}" if cats else '') + (f"; and at {impact} impact" + (' and above' if impact == 'medium' else '') if impact != 'off' else ''))
    return p


def managing_decisions():
    return on() and policy()['auto']


def _made_by(rid):
    meta = (store.record_kinds([rid]).get(rid) or {}).get('decision') or {}
    return meta.get('made_by') or store.owner_name(), meta.get('via') or ''


def decide_decision(rid, reviewed=True, force=False):
    """Once Temple has checked a decision: recorded (approved) with who made it, unless the decision policy asks for approval."""
    import temple
    if not on(): return 'off'
    st = _state('memory', rid)
    if st and st['state'] == 'approved': return 'already'
    if st and st['state'] == 'held' and not force and st['reason'] != OLD_HOLD: return 'held'
    with store.db() as c:
        row = c.execute("SELECT r.status,r.title,coalesce(m.category,'') AS category FROM records r "
                        "LEFT JOIN record_meta m ON m.record_id=r.id WHERE r.id=?", (rid,)).fetchone()
    if not row or row['status'] != 'proposed': return 'gone'
    p = policy()
    if not p['auto']:
        hold('memory', rid, 'A decision: decisions wait for you (Temple does not manage decisions).'); return 'held'
    rv = _latest_review(rid) if reviewed else None
    report = rv['report'] if rv and rv['status'] == 'complete' else ''
    im = IMPACT.search(report)
    impact = im.group(1).lower() if im else ''
    cat = row['category'] or ''
    why = ''
    if cat in p['categories']: why = f'Decisions in {cat} need approval.'
    elif p['impact'] != 'off':
        if not impact: why = 'Temple could not rate its impact, and impact-rated decisions need approval.'
        elif LEVELS[impact] >= LEVELS[p['impact']]: why = f'Temple rated it {impact} impact: decisions at that level need approval.'
    if why:
        hold('memory', rid, why)
        owner = p['categories'].get(cat) or p['approver']
        try:
            import notify
            notify.decision_held(rid, why, owner)
        except Exception:
            pass
        return 'held'
    who, via = _made_by(rid)
    clash = CONFLICT.search(report)
    note = f'Decision recorded by Temple for {who}' + (f' (via {via})' if via else '') + \
           (f', {impact} impact' if impact else '') + ('' if reviewed and report else ', not checked by Temple')
    if clash and clash.group(1).lower() == 'yes':
        note += '. Contradicts an earlier decision or memory, kept as made: ' + (temple.reason_line(report) or 'see Temple\'s review')
    try:
        with store.acting('Alice', note='Recorded automatically: ' + note):
            store.review(rid, 'approved')
    except ValueError as e:
        hold('memory', rid, f'Not recorded automatically: {e}'); return 'held'
    _approved('memory', rid, note)
    return 'approved'


_propose_decision = store.propose_decision


def propose_decision(*args, **kwargs):
    who, via = store.actor(), outside()
    token = _deciding.set(True)
    try: result = _propose_decision(*args, **kwargs)
    finally: _deciding.reset(token)
    rid = result.get('id')
    if rid and not result.get('duplicate') and not _state('memory', rid):
        with store.db() as c:          # who made it, kept with the decision
            r = c.execute('SELECT decision FROM record_meta WHERE record_id=?', (rid,)).fetchone()
            meta = json.loads(r[0]) if r and r[0] else {}
            meta.update(made_by=who, via=via)
            c.execute('UPDATE record_meta SET decision=? WHERE record_id=?', (json.dumps(meta), rid))
        import temple
        managed, reviewing = managing_decisions(), temple.settings()['enabled']
        if not managed: hold('memory', rid, 'A decision: decisions wait for you (Temple does not manage decisions).')
        if reviewing or managed:
            def work():
                if reviewing:
                    try: temple.review_record(rid)
                    except Exception: pass
                if managed:
                    try: decide_decision(rid, reviewed=reviewing)
                    except Exception: pass
            threading.Thread(target=work, daemon=True).start()
    return result


store.propose_decision = propose_decision
