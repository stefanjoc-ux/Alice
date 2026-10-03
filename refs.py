"""Reference numbers: M-0001 for memories, D-0001 for decisions, K-0001 for knowledge items (notes, meeting extracts,
reference summaries and uploaded files alike). Proposals keep their existing P-xxxxxx reference (proposals.py).

- The random IDs stay the keys everything joins on; a reference is a second, human-readable name for the same item,
  held in item_refs (unique both ways). Additive schema only.
- Numbers come from ref_counters, taken inside a write transaction, so two saves at once never get the same number.
- A reference is given when the item is created (a proposal or draft included), never changes and is never reused.
  Rejected items keep theirs, so the series has gaps.
- The prefix is fixed when the number is given: a decision is a memory of kind 'decision' and draws from D.
- Items created by paths that insert directly (Temple capture, imports) are numbered the next time anything lists or
  searches (ensure()); the first run numbers existing items in the order they were created."""
import contextvars
import re
from datetime import datetime, timedelta, timezone

import substrate_store as store

PREFIX = {'fact': 'M', 'decision': 'D', 'knowledge': 'K'}
PATTERN = re.compile(r'\s*([MDKmdk])\s*-?\s*0*(\d{1,7})\s*')
_deciding = contextvars.ContextVar('alice_ref_deciding', default=False)


def _schema():
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS ref_counters (prefix TEXT PRIMARY KEY, next INTEGER NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS item_refs (ref TEXT PRIMARY KEY, item_type TEXT NOT NULL, item_id TEXT NOT NULL, created_at TEXT NOT NULL)')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS item_refs_item ON item_refs(item_type,item_id)')
        for p in PREFIX.values(): c.execute('INSERT OR IGNORE INTO ref_counters(prefix,next) VALUES (?,1)', (p,))


_schema()


def fmt(prefix, n): return f'{prefix}-{n:04d}'


def parse(text):
    """'M-0042', 'm42', 'D 7' -> 'M-0042' / 'D-0007'; anything else -> ''."""
    m = PATTERN.fullmatch(text or '')
    return fmt(m.group(1).upper(), int(m.group(2))) if m else ''


def _take(c, prefix):
    n = c.execute('SELECT next FROM ref_counters WHERE prefix=?', (prefix,)).fetchone()[0]
    c.execute('UPDATE ref_counters SET next=? WHERE prefix=?', (n + 1, prefix))
    return fmt(prefix, n)


def ensure(fresh=True):
    """Number every memory, decision and knowledge item that has no reference yet. fresh=False (listings) leaves items
    created in the last few seconds to the call made by the code that created them, so a decision is never numbered as
    a memory in the moment before its kind is set."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat() if not fresh else '9999'
    q_rec = ("SELECT r.id,coalesce(m.kind,'fact') AS kind FROM records r LEFT JOIN record_meta m ON m.record_id=r.id "
             "LEFT JOIN item_refs x ON x.item_type='record' AND x.item_id=r.id WHERE x.ref IS NULL AND r.created_at<? ORDER BY r.created_at,r.id")
    q_file = ("SELECT f.id FROM files f LEFT JOIN item_refs x ON x.item_type='file' AND x.item_id=f.id "
              "WHERE x.ref IS NULL AND f.created_at<? ORDER BY f.created_at,f.id")
    with store.db() as c:
        if not c.execute(q_rec, (cutoff,)).fetchone() and not c.execute(q_file, (cutoff,)).fetchone(): return 0
    done = 0
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        recs = c.execute(q_rec, (cutoff,)).fetchall()
        files = c.execute(q_file, (cutoff,)).fetchall()
        for r in recs:
            c.execute('INSERT INTO item_refs(ref,item_type,item_id,created_at) VALUES (?,?,?,?)',
                      (_take(c, PREFIX['decision' if r['kind'] == 'decision' else 'fact']), 'record', r['id'], store.now())); done += 1
        for f in files:
            c.execute('INSERT INTO item_refs(ref,item_type,item_id,created_at) VALUES (?,?,?,?)',
                      (_take(c, 'K'), 'file', f['id'], store.now())); done += 1
        if done > 50: store.audit(c, 'references_assigned', f'{done} items', 'system', 'Reference numbers given to existing memories, decisions and knowledge')
    return done


def of(item_type, ids):
    """{id: ref} for 'record' or 'file' ids."""
    ids = [i for i in dict.fromkeys(ids) if i]
    out = {}
    with store.db() as c:
        for k in range(0, len(ids), 500):
            chunk = ids[k:k + 500]
            out.update({r[0]: r[1] for r in c.execute(
                f"SELECT item_id,ref FROM item_refs WHERE item_type=? AND item_id IN ({','.join('?' * len(chunk))})", [item_type] + chunk)})
    return out


def find(text):
    """('record'|'file', id) for a reference like M-0042, else (None, None)."""
    ref = parse(text)
    if not ref: return None, None
    ensure(fresh=False)
    with store.db() as c:
        row = c.execute('SELECT item_type,item_id FROM item_refs WHERE ref=?', (ref,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


# ---------------- numbering at the moment of creation ----------------
_propose = store.propose
_propose_decision = store.propose_decision


def propose(title, content, source, category=''):
    result = _propose(title, content, source, category)
    if result.get('id') and not _deciding.get():
        ensure(); result['ref'] = of('record', [result['id']]).get(result['id'], '')
    return result


def propose_decision(*args, **kwargs):
    token = _deciding.set(True)
    try: result = _propose_decision(*args, **kwargs)
    finally: _deciding.reset(token)
    if result.get('id'):
        ensure(); result['ref'] = of('record', [result['id']]).get(result['id'], '')
    return result


store.propose, store.propose_decision = propose, propose_decision


def _wrap_knowledge():
    import knowledge
    if getattr(knowledge.create, '_refs', False): return
    original = knowledge.create

    def create(*args, **kwargs):
        result = original(*args, **kwargs)
        if isinstance(result, dict) and result.get('id'):
            ensure(); result['ref'] = of('file', [result['id']]).get(result['id'], '')
        return result
    create._refs = True
    knowledge.create = create


_wrap_knowledge()
