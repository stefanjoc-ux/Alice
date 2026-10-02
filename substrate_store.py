"""Shared persistence and enforced record policy. No model-facing approval tool."""
import contextvars
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
DB = Path(os.getenv('AISUBSTRATE_DATA_DIR', str(BASE / 'data'))) / 'substrate.db'
IMAGE_DIR = DB.parent / 'images'

DATABASE_URL = os.getenv('ALICE_DATABASE_URL', '').strip()
# Demo data lives apart from your real data: its own SQLite file (or its own PostgreSQL schema). A request is switched
# to it only for the Organisations and Opportunities pages (see demo_data.py); everything else always uses live data.
DATASET = contextvars.ContextVar('alice_dataset', default='live')
DEMO_DB = DB.parent / 'demo' / 'substrate-demo.db'
DEMO_SCHEMA = os.environ.get('ALICE_DEMO_SCHEMA', 'alice_demo')   # tests use their own


@contextmanager
def dataset(name):
    token = DATASET.set(name)
    try: yield
    finally: DATASET.reset(token)


def demo_active():
    return DATASET.get() == 'demo'   # set: PostgreSQL (Azure); unset: SQLite file in data\\


def connect(readonly=False):
    """A connection that behaves like sqlite3 (rows by name, ? placeholders, `with` commits). Close it when done.
    SQLite by default; PostgreSQL when ALICE_DATABASE_URL is set (see dbcompat.py)."""
    demo = DATASET.get() == 'demo'
    if DATABASE_URL:
        import dbcompat
        if demo:
            from psycopg.conninfo import make_conninfo
            return dbcompat.connect(make_conninfo(DATABASE_URL, options=f'-csearch_path={DEMO_SCHEMA},public'), readonly)
        return dbcompat.connect(DATABASE_URL, readonly)
    if demo:
        DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DEMO_DB, timeout=15)
        c.row_factory = sqlite3.Row
        return c
    DB.parent.mkdir(parents=True, exist_ok=True)
    if readonly:
        if not DB.is_file(): raise ValueError('No substrate database found. Start the web app and save a file first.')
        c = sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA query_only=ON')
        return c
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    return c


@contextmanager
def db(readonly=False):
    c = connect(readonly)
    try:
        with c: yield c
    finally: c.close()

def now(): return datetime.now(timezone.utc).isoformat()

def audit(c, action, target, rule, detail=''):
    c.execute('INSERT INTO activity(created_at,action,target,rule,detail) VALUES (?,?,?,?,?)',
              (now(), action, target, rule, detail))

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('proposed','approved','rejected')),
          created_at TEXT NOT NULL, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS memory_archive (record_id TEXT PRIMARY KEY,state TEXT NOT NULL,reason TEXT NOT NULL,changed_at TEXT NOT NULL,replaced_by TEXT);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL, action TEXT NOT NULL,target TEXT NOT NULL,rule TEXT NOT NULL,detail TEXT NOT NULL);
        ''')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('guidance',?)", ('Use UK English. Cite sources. Ask when information is ambiguous.',))
        c.execute("INSERT OR IGNORE INTO settings VALUES ('allow_proposals','true')")

def rules():
    with db() as c: settings = dict(c.execute('SELECT key,value FROM settings').fetchall())
    return {'guidance': settings['guidance'], 'allow_proposals': settings['allow_proposals']=='true',
            'enforced': ['All new records are proposals until approved in Admin.',
                         'Title, content and a source description are required.',
                         'MCP can never approve, overwrite or delete records.',
                         'Only approved records are returned by search_records.']}

def update_rules(guidance, allow_proposals):
    guidance=guidance.strip()
    if len(guidance)>8000: raise ValueError('Guidance exceeds 8,000 characters.')
    with db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='guidance'",(guidance,))
        c.execute("UPDATE settings SET value=? WHERE key='allow_proposals'",(json.dumps(allow_proposals),))
        audit(c,'rules_updated','settings','admin_only','Response guidance and proposal setting saved')
    return rules()

def propose(title, content, source):
    values=[title.strip(),content.strip(),source.strip()]
    if any(not v for v in values) or any(len(v)>limit for v,limit in zip(values,[200,8000,2000])):
        raise ValueError('A title (200 chars), content (8,000 chars), and source (2,000 chars) are required.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT value FROM settings WHERE key='allow_proposals'").fetchone()[0]!='true':
            audit(c,'proposal_blocked','','allow_proposals','New proposals are disabled')
            blocked=True
        else:
            blocked=False
            existing=c.execute("SELECT id,status FROM records WHERE title=? AND content=? AND source=? AND status IN ('proposed','approved') AND NOT EXISTS (SELECT 1 FROM memory_archive WHERE record_id=records.id)",values).fetchone()
            if existing: return dict(existing)|{'duplicate':True}
            rid=uuid.uuid4().hex
            c.execute('INSERT INTO records VALUES (?,?,?,?,?,?,NULL)',(rid,*values,'proposed',now()))
            audit(c,'record_proposed',rid,'approval_required','Awaiting human review; source description is unverified')
    if blocked: raise ValueError('New record proposals are disabled by the substrate rule.')
    # The proposal is committed before the advisory API call; failures cannot undo it.
    try:
        import temple
        temple.automatic_review(rid)
    except Exception:
        pass  # No review entry means Not reviewed in Temple; human review remains available.
    return {'id':rid,'status':'proposed','message':'Awaiting human approval in Substrate admin. Not yet an approved memory.'}

def review(rid, decision):
    if decision not in ('approved','rejected'): raise ValueError('Invalid decision.')
    with db() as c:
        changed=c.execute("UPDATE records SET status=?,reviewed_at=? WHERE id=? AND status='proposed'",(decision,now(),rid)).rowcount
        if not changed: raise ValueError('Record missing or already reviewed. Refresh the page.')
        audit(c,'record_'+decision,rid,'human_review','Reviewed in local admin page')
    return {'status':decision}

def records(status='all',query='',offset=0,limit=30):
    source="FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id "
    where="WHERE (?='all' OR coalesce(a.state,r.status)=?) AND (instr(lower(r.title),lower(?))>0 OR instr(lower(r.content),lower(?))>0)"
    args=(status,status,query,query)
    with db() as c:
        total=c.execute('SELECT count(*) '+source+where,args).fetchone()[0]
        rows=c.execute('SELECT r.*,a.state AS archived_status,a.reason AS archive_reason,a.changed_at,a.replaced_by '+source+where+' ORDER BY r.created_at DESC,r.id LIMIT ? OFFSET ?',args+(limit,offset)).fetchall()
    result=[]
    for row in rows:
        r=dict(row)
        if r['archived_status']:r['status']=r['archived_status']
        result.append(r)
    return {'records':result,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None}

def resolve_friction(proposal_id, old_id, reason):
    reason=reason.strip()
    if not reason or len(reason)>2000:raise ValueError('Give a reason of up to 2,000 characters.')
    if proposal_id==old_id:raise ValueError('Choose a different memory to replace.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        proposal=c.execute("SELECT 1 FROM records WHERE id=? AND status='proposed'",(proposal_id,)).fetchone()
        old=c.execute("SELECT 1 FROM records WHERE id=? AND status='approved' AND NOT EXISTS (SELECT 1 FROM memory_archive WHERE record_id=records.id)",(old_id,)).fetchone()
        if not proposal or not old:raise ValueError('Proposal or active memory changed. Refresh before resolving this friction.')
        c.execute('INSERT INTO memory_archive VALUES (?,?,?,?,?)',(old_id,'superseded',reason,now(),proposal_id))
        c.execute("UPDATE records SET status='approved',reviewed_at=? WHERE id=?",(now(),proposal_id))
        audit(c,'friction_resolved',proposal_id,'human_replacement','Replaces '+old_id+': '+reason)
        audit(c,'memory_superseded',old_id,'human_replacement','Replaced by '+proposal_id+': '+reason)
    return {'status':'approved','replaces':old_id}

def retire_memory(rid, reason):
    reason=reason.strip()
    if not reason or len(reason)>2000:raise ValueError('Give a reason of up to 2,000 characters.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT 1 FROM records WHERE id=? AND status='approved' AND NOT EXISTS (SELECT 1 FROM memory_archive WHERE record_id=records.id)",(rid,)).fetchone()
        if not row:raise ValueError('This is no longer an active approved memory. Refresh the page.')
        c.execute('INSERT INTO memory_archive VALUES (?,?,?,?,NULL)',(rid,'retired',reason,now()))
        audit(c,'memory_retired',rid,'human_review',reason)
    return {'status':'retired'}

def memory_history(rid):
    with db() as c:
        if not c.execute('SELECT 1 FROM records WHERE id=?',(rid,)).fetchone():raise ValueError('Memory not found.')
        ids={rid};pending=[rid]
        while pending:
            current=pending.pop()
            for row in c.execute('SELECT record_id,replaced_by FROM memory_archive WHERE record_id=? OR replaced_by=?',(current,current)):
                for related in row:
                    if related and related not in ids:ids.add(related);pending.append(related)
        items=[]
        for mid in ids:
            row=dict(c.execute('SELECT * FROM records WHERE id=?',(mid,)).fetchone())
            archive=c.execute('SELECT * FROM memory_archive WHERE record_id=?',(mid,)).fetchone()
            if archive:row.update(dict(archive));row['status']=archive['state']
            row['events']=[dict(e) for e in c.execute('SELECT * FROM activity WHERE target=? ORDER BY id',(mid,))]
            items.append(row)
    return sorted(items,key=lambda r:r['created_at'])


def log_tool(name,failed):
    with db() as c: audit(c,'tool_failed' if failed else 'tool_completed',name,'MCP tool access','Web chat invocation; file tools read only; proposals require approval')

def activity(offset=0):
    with db() as c: return [dict(r) for r in c.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 50 OFFSET ?',(offset,))]

init()

# Additive migration: existing knowledge, rules and records are untouched.
with db() as c:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS chats (
      id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
      provider TEXT NOT NULL DEFAULT 'openai',file_ids TEXT NOT NULL DEFAULT '[]');
    CREATE TABLE IF NOT EXISTS chat_turns (
      id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,user_text TEXT NOT NULL,reply TEXT NOT NULL DEFAULT '',
      provider TEXT NOT NULL,model TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,
      error TEXT NOT NULL DEFAULT '',activity TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS chat_turns_by_chat ON chat_turns(chat_id,created_at);
    ''')
    # Additive: generated image file paths per turn (the images themselves live in data/images).
    if 'images' not in {r['name'] for r in c.execute('PRAGMA table_info(chat_turns)')}:
        c.execute("ALTER TABLE chat_turns ADD COLUMN images TEXT NOT NULL DEFAULT '[]'")

def recover_chats():
    with db() as c:
        c.execute("UPDATE chat_turns SET status='interrupted',error='Server restarted before the answer completed.' WHERE status='pending'")

def create_chat():
    cid=uuid.uuid4().hex
    with db() as c: c.execute('INSERT INTO chats(id,title,created_at,updated_at) VALUES (?,?,?,?)',(cid,'New chat',now(),now()))
    return {'id':cid}

def list_chats():
    with db() as c: return [dict(r) for r in c.execute('SELECT * FROM chats ORDER BY updated_at DESC,id')]

def get_chat(cid):
    with db() as c:
        row=c.execute('SELECT * FROM chats WHERE id=?',(cid,)).fetchone()
        if row is None: raise ValueError('Chat not found.')
        turns=[dict(r) for r in c.execute('SELECT * FROM chat_turns WHERE chat_id=? ORDER BY created_at,rowid',(cid,))]
    result=dict(row);result['file_ids']=json.loads(result['file_ids'])
    for t in turns: t['activity']=json.loads(t['activity']); t['images']=json.loads(t.get('images') or '[]')
    return result|{'turns':turns}

def rename_chat(cid,title):
    title=title.strip()
    if not title: raise ValueError('Enter a chat title.')
    with db() as c:
        if not c.execute('UPDATE chats SET title=? WHERE id=?',(title,cid)).rowcount: raise ValueError('Chat not found.')
    return {'renamed':True}

def delete_chat(cid):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM chat_turns WHERE chat_id=? AND status='pending'",(cid,)).fetchone():
            raise ValueError('Wait for the current answer before deleting this chat.')
        c.execute('DELETE FROM chat_turns WHERE chat_id=?',(cid,))
        if not c.execute('DELETE FROM chats WHERE id=?',(cid,)).rowcount: raise ValueError('Chat not found.')
    import shutil
    if len(cid)==32 and all(ch in '0123456789abcdef' for ch in cid):
        shutil.rmtree(IMAGE_DIR/cid, ignore_errors=True)
    return {'deleted':True}

def begin_turn(cid,tid,text,provider,file_ids):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        chat=c.execute('SELECT * FROM chats WHERE id=?',(cid,)).fetchone()
        if not chat: raise ValueError('Chat not found.')
        if c.execute('SELECT 1 FROM chat_turns WHERE id=?',(tid,)).fetchone():
            raise ValueError('This message was already submitted. Reopen the chat to see its status.')
        if c.execute("SELECT 1 FROM chat_turns WHERE chat_id=? AND status='pending'",(cid,)).fetchone():
            raise ValueError('An answer is already running in this chat. Wait and reopen it.')
        prior=c.execute("SELECT user_text,reply FROM chat_turns WHERE chat_id=? AND status='complete' ORDER BY created_at DESC,rowid DESC LIMIT 10",(cid,)).fetchall()
        # Whole exchanges only, recent first selection, bounded stored context.
        pairs=[];budget=60000
        for r in prior:
            size=len(r['user_text'])+len(r['reply'])
            if size>budget: break
            pairs.append(r);budget-=size
        messages=[]
        for r in reversed(pairs): messages.extend([{'role':'user','content':r['user_text']},{'role':'assistant','content':r['reply']}])
        c.execute('INSERT INTO chat_turns(id,chat_id,user_text,provider,status,created_at) VALUES (?,?,?,?,?,?)',(tid,cid,text,provider,'pending',now()))
        title=text[:70] if chat['title']=='New chat' else chat['title']
        c.execute('UPDATE chats SET title=?,updated_at=?,provider=?,file_ids=? WHERE id=?',(title,now(),provider,json.dumps(file_ids),cid))
    return messages+[{'role':'user','content':text}]

def turn_event(tid,event):
    with db() as c:
        row=c.execute('SELECT * FROM chat_turns WHERE id=?',(tid,)).fetchone()
        if not row or row['status']!='pending': return
        if event['type']=='activity':
            events=json.loads(row['activity']);events.append(event)
            c.execute('UPDATE chat_turns SET activity=? WHERE id=?',(json.dumps(events),tid))
        elif event['type']=='answer':
            c.execute("UPDATE chat_turns SET reply=?,model=?,images=?,status='complete' WHERE id=?",
                      (event['reply'],event['model'],json.dumps(event.get('images',[])),tid))
        elif event['type']=='error':
            c.execute("UPDATE chat_turns SET error=?,status='failed' WHERE id=?",(event['message'],tid))
        c.execute('UPDATE chats SET updated_at=? WHERE id=?',(now(),row['chat_id']))

def interrupt_turn(tid):
    with db() as c: c.execute("UPDATE chat_turns SET status='interrupted',error='Connection closed before the answer completed. Any completed tool actions are retained; check activity before retrying.' WHERE id=? AND status='pending'",(tid,))


with db() as c:   # client tags (owned by clients.py; created here too so queries never depend on import order)
    c.execute("CREATE TABLE IF NOT EXISTS client_tags (item_type TEXT NOT NULL, item_id TEXT NOT NULL, client TEXT NOT NULL DEFAULT '', "
              "assigned_by TEXT NOT NULL DEFAULT '', confidence REAL, suggestion TEXT NOT NULL DEFAULT '', "
              "suggestion_reason TEXT NOT NULL DEFAULT '', checked_at TEXT, PRIMARY KEY (item_type,item_id))")

# ---- Memory organisation: categories are a managed list; assignments live in record_meta,
# separate from records, so existing positional INSERTs (store.propose, Temple capture) still work.
with db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS record_meta (record_id TEXT PRIMARY KEY, category TEXT NOT NULL DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY COLLATE NOCASE, description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
    cols = {r['name'] for r in c.execute('PRAGMA table_info(record_meta)')}
    for col, ddl in [('assigned_by', "TEXT NOT NULL DEFAULT ''"), ('confidence', 'REAL'), ('suggestion', "TEXT NOT NULL DEFAULT ''"),
                     ('suggestion_reason', "TEXT NOT NULL DEFAULT ''"), ('temple_checked_at', 'TEXT'), ('review_by', 'TEXT')]:
        if col not in cols: c.execute(f'ALTER TABLE record_meta ADD COLUMN {col} {ddl}')
    # Categories typed freely before this update become managed categories.
    for (name,) in c.execute("SELECT DISTINCT category FROM record_meta WHERE category<>''").fetchall():
        c.execute('INSERT OR IGNORE INTO categories(name,created_at) VALUES (?,?)', (name, now()))
    c.execute("INSERT OR IGNORE INTO settings VALUES ('temple_categorise','auto')")

SORTS = {'newest': 'r.created_at DESC,r.id', 'oldest': 'r.created_at ASC,r.id',
         'title': 'lower(r.title),r.id', 'category': "coalesce(nullif(m.category,''),'~'),lower(r.title)",
         'reviewed': 'coalesce(r.reviewed_at,r.created_at) DESC,r.id'}
ACTIVE_FOR_TEMPLE = "coalesce(a.state,r.status) IN ('proposed','approved')"


def clean_category(category):
    category = ' '.join((category or '').split())[:40]
    return category[:1].upper() + category[1:] if category else ''


def _canonical(c, name):
    """Existing category name with its stored capitalisation, '' for uncategorised, or ValueError."""
    name = clean_category(name)
    if not name: return ''
    row = c.execute('SELECT name FROM categories WHERE name=?', (name,)).fetchone()
    if not row: raise ValueError(f'No category called "{name}". Create it first.')
    return row[0]


def _assign(c, rid, category, by, confidence=None):
    c.execute("INSERT INTO record_meta(record_id,category,assigned_by,confidence,suggestion,suggestion_reason) VALUES (?,?,?,?,'','') "
              "ON CONFLICT(record_id) DO UPDATE SET category=excluded.category,assigned_by=excluded.assigned_by,"
              "confidence=excluded.confidence,suggestion='',suggestion_reason=''", (rid, category, by if category else '', confidence))


def list_categories():
    with db() as c:
        rows = c.execute("SELECT k.name,k.description,k.created_at,"
                         "(SELECT count(*) FROM record_meta m JOIN records r ON r.id=m.record_id LEFT JOIN memory_archive a ON a.record_id=r.id "
                         " WHERE m.category=k.name AND coalesce(a.state,r.status)='approved') AS active,"
                         "(SELECT count(*) FROM record_meta m WHERE m.category=k.name) AS total "
                         "FROM categories k ORDER BY lower(k.name)").fetchall()
        mode = c.execute("SELECT value FROM settings WHERE key='temple_categorise'").fetchone()[0]
    return {'categories': [dict(r) for r in rows], 'temple_mode': mode}


def create_category(name, description=''):
    name = clean_category(name)
    if not name: raise ValueError('Enter a category name.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM categories WHERE name=?', (name,)).fetchone(): raise ValueError(f'"{name}" already exists.')
        c.execute('INSERT INTO categories(name,description,created_at) VALUES (?,?,?)', (name, description.strip()[:300], now()))
        c.execute("UPDATE record_meta SET temple_checked_at=NULL WHERE category=''")   # new home: let Temple look again
        audit(c, 'category_created', name, 'human_review', description.strip()[:300])
    return {'name': name}


def update_category(name, new_name, description):
    new_name = clean_category(new_name)
    if not new_name: raise ValueError('Enter a category name.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old = _canonical(c, name)
        if new_name.lower() != old.lower() and c.execute('SELECT 1 FROM categories WHERE name=?', (new_name,)).fetchone():
            raise ValueError(f'"{new_name}" already exists.')
        c.execute('UPDATE categories SET name=?,description=? WHERE name=?', (new_name, description.strip()[:300], old))
        c.execute('UPDATE record_meta SET category=? WHERE category=?', (new_name, old))
        c.execute('UPDATE record_meta SET suggestion=? WHERE suggestion=?', (new_name, old))
        c.execute("UPDATE record_meta SET temple_checked_at=NULL WHERE category=''")
        audit(c, 'category_updated', new_name, 'human_review', f'{old} → {new_name}')
    return {'name': new_name}


def delete_category(name, move_to=''):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old = _canonical(c, name)
        target = _canonical(c, move_to) if move_to else ''
        if target and target.lower() == old.lower(): raise ValueError('Choose a different category to move memories into.')
        moved = c.execute("UPDATE record_meta SET category=?,assigned_by=CASE WHEN ?='' THEN '' ELSE 'human' END WHERE category=?",
                          (target, target, old)).rowcount
        c.execute("UPDATE record_meta SET suggestion='',suggestion_reason='' WHERE suggestion=?", (old,))
        c.execute('DELETE FROM categories WHERE name=?', (old,))
        audit(c, 'category_deleted', old, 'human_review', f'{moved} memories → {target or "Uncategorised"}')
    return {'deleted': old, 'moved': moved, 'to': target}


def set_temple_mode(mode):
    if mode not in ('off', 'suggest', 'auto'): raise ValueError('Unknown mode.')
    with db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='temple_categorise'", (mode,))
        audit(c, 'temple_categorise_mode', 'Temple', 'human_control', mode)
    return {'temple_mode': mode}


def set_category(ids, category):
    """Human assignment: always wins over Temple and model suggestions."""
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, str) and i][:200]
    if not ids: raise ValueError('Select at least one memory.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        category = _canonical(c, category)
        found = [r[0] for r in c.execute(f"SELECT id FROM records WHERE id IN ({','.join('?' * len(ids))})", ids)]
        for rid in found: _assign(c, rid, category, 'human')
        audit(c, 'category_set', ','.join(found)[:500], 'human_review', f'{len(found)} memories → {category or "Uncategorised"}')
    return {'updated': len(found), 'category': category}


def resolve_suggestions(ids, action):
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, str) and i][:200]
    if action not in ('accept', 'dismiss'): raise ValueError('Unknown action.')
    done = 0
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        for rid in ids:
            row = c.execute("SELECT suggestion FROM record_meta WHERE record_id=? AND suggestion<>''", (rid,)).fetchone()
            if not row: continue
            if action == 'accept' and c.execute('SELECT 1 FROM categories WHERE name=?', (row[0],)).fetchone():
                _assign(c, rid, row[0], 'human')
            else:
                c.execute("UPDATE record_meta SET suggestion='',suggestion_reason='' WHERE record_id=?", (rid,))
            done += 1
        audit(c, 'category_suggestions_' + action, ','.join(ids)[:500], 'human_review', f'{done} Temple suggestions {action}ed')
    return {'done': done}


def temple_candidates(ids=None, include_checked=False, limit=40):
    """Uncategorised active/proposed memories with no human or pending suggestion. Temple never overrides."""
    where = (f"WHERE {ACTIVE_FOR_TEMPLE} AND coalesce(m.category,'')='' AND coalesce(m.suggestion,'')='' "
             + ('' if include_checked else 'AND m.temple_checked_at IS NULL '))
    args = []
    if ids:
        where += f"AND r.id IN ({','.join('?' * len(ids))}) "; args += list(ids)
    with db() as c:
        return [dict(r) for r in c.execute(
            'SELECT r.id,r.title,substr(r.content,1,600) AS content FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id '
            'LEFT JOIN record_meta m ON m.record_id=r.id ' + where + 'ORDER BY r.created_at DESC LIMIT ?', args + [limit])]


def reset_temple_checks(ids=None):
    with db() as c:
        if ids: c.execute(f"UPDATE record_meta SET temple_checked_at=NULL WHERE category='' AND record_id IN ({','.join('?'*len(ids))})", list(ids))
        else: c.execute("UPDATE record_meta SET temple_checked_at=NULL WHERE category=''")


def record_temple_results(results, mode, threshold=0.75):
    """results: [(id, category|None, confidence, reason)] already validated against the category list."""
    applied = suggested = 0
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        for rid, category, confidence, reason in results:
            c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (rid,))
            current = c.execute('SELECT category,suggestion FROM record_meta WHERE record_id=?', (rid,)).fetchone()
            if current['category'] or current['suggestion']: continue      # a human (or earlier run) got there first
            if category and mode == 'auto' and confidence >= threshold:
                _assign(c, rid, category, 'temple', confidence); applied += 1
            elif category:
                c.execute('UPDATE record_meta SET suggestion=?,suggestion_reason=?,confidence=? WHERE record_id=?',
                          (category, reason[:200], confidence, rid)); suggested += 1
            c.execute('UPDATE record_meta SET temple_checked_at=? WHERE record_id=?', (now(), rid))
        audit(c, 'temple_categorised', f'{len(results)} memories', 'advisory_metadata', f'{applied} assigned, {suggested} suggested, mode {mode}')
    return {'checked': len(results), 'applied': applied, 'suggested': suggested}


def organised_records(status='approved', query='', category='', sort='newest', offset=0, limit=50):
    if sort not in SORTS: sort = 'newest'
    source = ('FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id '
              'LEFT JOIN record_meta m ON m.record_id=r.id ')
    where = ("WHERE (?='all' OR coalesce(a.state,r.status)=?) AND (?='' OR instr(lower(r.title),lower(?))>0 "
             "OR instr(lower(r.content),lower(?))>0 OR instr(lower(r.source),lower(?))>0) "
             "AND (?='' OR (?='__none__' AND coalesce(m.category,'')='') OR (?='__suggested__' AND coalesce(m.suggestion,'')<>'') "
             "OR (?='__expired__' AND m.review_by IS NOT NULL AND m.review_by<?) OR coalesce(m.category,'')=?)")
    today = datetime.now(timezone.utc).date().isoformat()
    args = (status, status, query, query, query, query, category, category, category, category, today, category)
    with db() as c:
        total = c.execute('SELECT count(*) ' + source + where, args).fetchone()[0]
        rows = c.execute('SELECT r.*,coalesce(a.state,r.status) AS status,a.reason AS archive_reason,a.changed_at,'
                         "a.replaced_by,coalesce(m.category,'') AS category,coalesce(m.assigned_by,'') AS assigned_by,"
                         "m.confidence,coalesce(m.suggestion,'') AS suggestion,coalesce(m.suggestion_reason,'') AS suggestion_reason,"
                         "(SELECT review_by FROM record_meta x WHERE x.record_id=r.id) AS review_by,"
                         "(SELECT client FROM client_tags ct WHERE ct.item_type='memory' AND ct.item_id=r.id) AS client "
                         + source + where + ' ORDER BY ' + SORTS[sort] + ' LIMIT ? OFFSET ?', args + (limit, offset)).fetchall()
        statuses = dict(c.execute('SELECT coalesce(a.state,r.status),count(*) FROM records r '
                                  'LEFT JOIN memory_archive a ON a.record_id=r.id GROUP BY 1').fetchall())
        categories = [{'category': r[0], 'count': r[1]} for r in c.execute(
            "SELECT coalesce(m.category,''),count(*) FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id "
            "LEFT JOIN record_meta m ON m.record_id=r.id WHERE (?='all' OR coalesce(a.state,r.status)=?) "
            "GROUP BY 1 ORDER BY coalesce(m.category,'')='', 1", (status, status))]
        suggested = c.execute("SELECT count(*) FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id "
                              "JOIN record_meta m ON m.record_id=r.id WHERE (?='all' OR coalesce(a.state,r.status)=?) "
                              "AND m.suggestion<>''", (status, status)).fetchone()[0]
        known = [r[0] for r in c.execute('SELECT name FROM categories ORDER BY lower(name)')]
        try:
            expired = c.execute("SELECT count(*) FROM records r LEFT JOIN memory_archive a ON a.record_id=r.id JOIN record_meta m ON m.record_id=r.id "
                                "WHERE (?='all' OR coalesce(a.state,r.status)=?) AND m.review_by IS NOT NULL AND m.review_by<?", (status, status, today)).fetchone()[0]
        except sqlite3.OperationalError:
            expired = 0
    return {'records': [dict(r) for r in rows], 'total': total,
            'next_offset': offset + len(rows) if offset + len(rows) < total else None,
            'statuses': statuses, 'categories': categories, 'suggested': suggested, 'expired': expired, 'known_categories': known}


def bulk_review(ids, decision):
    if decision not in ('approved', 'rejected'): raise ValueError('Invalid decision.')
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, str) and i][:200]
    changed = 0
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        for rid in ids:
            if c.execute("UPDATE records SET status=?,reviewed_at=? WHERE id=? AND status='proposed'", (decision, now(), rid)).rowcount:
                changed += 1
                audit(c, 'record_' + decision, rid, 'human_review', 'Bulk review in local admin page')
    return {'changed': changed, 'skipped': len(ids) - changed}


_propose_original = propose


def propose(title, content, source, category=''):
    """Same enforced proposal policy. A model's category is kept only if it names an existing category."""
    result = _propose_original(title, content, source)
    if category and result.get('id'):
        with db() as c:
            try: name = _canonical(c, category)
            except ValueError: name = ''
            # Precedence: human > model > Temple. Temple may have run first in the background.
            if name and not c.execute("SELECT 1 FROM record_meta WHERE record_id=? AND assigned_by='human'", (result['id'],)).fetchone():
                _assign(c, result['id'], name, 'model')
    return result


# ---- Chat archive: a chat is archived when it has had no activity for ARCHIVE_DAYS.
# Nothing is moved or flagged in the database; sending a message (or Restore) makes it active again.
ARCHIVE_DAYS = int(os.getenv('SUBSTRATE_ARCHIVE_DAYS', '30'))


def archive_cutoff():
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=ARCHIVE_DAYS)).isoformat()


with db() as c:   # chats saved from other apps (Claude Desktop, Claude Code) carry their source and summary
    _cols = {r['name'] for r in c.execute('PRAGMA table_info(chats)')}
    if 'source' not in _cols: c.execute("ALTER TABLE chats ADD COLUMN source TEXT NOT NULL DEFAULT 'alice'")
    if 'summary' not in _cols: c.execute("ALTER TABLE chats ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
    if 'client' not in _cols: c.execute("ALTER TABLE chats ADD COLUMN client TEXT NOT NULL DEFAULT ''")   # also created by clients.py


def active_chats():
    """The chat sidebar: your own Alice chats with recent activity."""
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM chats WHERE updated_at>=? AND source='alice' ORDER BY updated_at DESC,id", (archive_cutoff(),))]


def _captures(c, cid):
    """What was captured from a chat: model memory proposals plus accepted Temple memory/knowledge items."""
    proposals = 0
    for (activity,) in c.execute('SELECT activity FROM chat_turns WHERE chat_id=?', (cid,)):
        try: events = json.loads(activity or '[]')
        except ValueError: continue
        proposals += sum(1 for e in events if isinstance(e, dict) and e.get('tool') == 'propose_record')
    temple = {'memory': 0, 'knowledge': 0}
    try:
        for kind, n in c.execute("SELECT kind,count(*) FROM temple_suggestions WHERE chat_id=? AND status='accepted' "
                                 "AND kind IN ('memory','knowledge') GROUP BY kind", (cid,)):
            temple[kind] = n
    except sqlite3.OperationalError:
        pass   # Temple tables not created yet
    row = c.execute('SELECT summary FROM chats WHERE id=?', (cid,)).fetchone()
    try: rec = json.loads(row['summary']) if row and row['summary'] else {}
    except ValueError: rec = {}
    saved, saved_knowledge = rec.get('proposed_memories', []), rec.get('proposed_knowledge', [])
    return {'memories': proposals + temple['memory'] + len(saved), 'knowledge': temple['knowledge'] + len(saved_knowledge)}


def archived_chats(query='', only_uncaptured=False, sort='recent', offset=0, limit=50, source=''):
    order = {'recent': 'updated_at DESC', 'oldest': 'updated_at ASC', 'created': 'created_at DESC', 'title': 'lower(title)'}.get(sort, 'updated_at DESC')
    with db() as c:
        rows = [dict(r) for r in c.execute(
            'SELECT ch.id,ch.title,ch.created_at,ch.updated_at,ch.provider,ch.source,ch.client,'
            "(SELECT count(*) FROM chat_turns t WHERE t.chat_id=ch.id AND t.status='complete') AS exchanges "
            "FROM chats ch WHERE (ch.updated_at<? OR ch.source<>'alice') AND (?='' OR instr(lower(ch.title),lower(?))>0) ORDER BY " + order,
            (archive_cutoff(), query, query))]
        try:
            reviews = {r['chat_id']: dict(r) for r in c.execute('SELECT * FROM chat_reviews')}
        except sqlite3.OperationalError:
            reviews = {}
        for r in rows: r['review'] = reviews.get(r['id'])
        for r in rows: r.update(_captures(c, r['id'])); r['captured'] = r['memories'] + r['knowledge'] > 0
    uncaptured = sum(1 for r in rows if not r['captured'])
    unreviewed = sum(1 for r in rows if not r['captured'] and (not r['review'] or r['review']['status'] == 'failed'))
    external = sum(1 for r in rows if r['source'] != 'alice')
    if only_uncaptured: rows = [r for r in rows if not r['captured']]
    if source == 'external': rows = [r for r in rows if r['source'] != 'alice']
    page = rows[offset:offset + limit]
    return {'chats': page, 'total': len(rows), 'uncaptured': uncaptured, 'unreviewed': unreviewed, 'external': external, 'days': ARCHIVE_DAYS,
            'next_offset': offset + len(page) if offset + len(page) < len(rows) else None}


def restore_chat(cid):
    with db() as c:
        if not c.execute('UPDATE chats SET updated_at=? WHERE id=?', (now(), cid)).rowcount: raise ValueError('Chat not found.')
        audit(c, 'chat_restored', cid, 'human_review', 'Restored from archive')
    return {'restored': True}


def archive_count():
    with db() as c:
        return c.execute("SELECT count(*) FROM chats WHERE updated_at<? OR source<>'alice'", (archive_cutoff(),)).fetchone()[0]


# ---- Rule enforcement hooks (rules_engine). Imported lazily to avoid a circular import.
rules_base = rules


def rules():
    """Effective guidance = enabled guidance rules (in precedence order) + your free-text guidance."""
    base = rules_base()
    try:
        import rules_engine
        return base | {'guidance': rules_engine.effective_guidance(base['guidance']), 'free_guidance': base['guidance']}
    except Exception:
        return base


def _check_before_approval(rid):
    import rules_engine
    with db() as c:
        r = c.execute('SELECT title,content,source FROM records WHERE id=?', (rid,)).fetchone()
    if r: rules_engine.check_record(r['title'], r['content'], r['source'], exclude_id=rid, stage='approval')


_review_original = review


def review(rid, decision):
    if decision == 'approved': _check_before_approval(rid)
    return _review_original(rid, decision)


def bulk_review(ids, decision):
    if decision not in ('approved', 'rejected'): raise ValueError('Invalid decision.')
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, str) and i][:200]
    changed, blocked = 0, []
    for rid in ids:
        if decision == 'approved':
            try: _check_before_approval(rid)
            except ValueError as e: blocked.append(str(e)); continue
        with db() as c:
            if c.execute("UPDATE records SET status=?,reviewed_at=? WHERE id=? AND status='proposed'", (decision, now(), rid)).rowcount:
                changed += 1
                audit(c, 'record_' + decision, rid, 'human_review', 'Bulk review in local admin page')
    return {'changed': changed, 'skipped': len(ids) - changed - len(blocked), 'blocked': len(blocked),
            'block_reasons': sorted(set(blocked))[:5]}


_resolve_original = resolve_friction


def resolve_friction(proposal_id, old_id, reason):
    _check_before_approval(proposal_id)
    return _resolve_original(proposal_id, old_id, reason)


_propose_with_category = propose


def propose(title, content, source, category=''):
    import rules_engine
    rules_engine.check_record(title.strip(), content.strip(), source.strip(), stage='proposal')
    return _propose_with_category(title, content, source, category)


# ---- Decisions: a kind of memory with structure (decision, why, options considered, revisit).
# Same approval, categories, clients, Temple review, supersede/retire and review-by dates as other memories.
with db() as c:
    _mcols = {r['name'] for r in c.execute('PRAGMA table_info(record_meta)')}
    if 'kind' not in _mcols: c.execute("ALTER TABLE record_meta ADD COLUMN kind TEXT NOT NULL DEFAULT 'fact'")
    if 'decision' not in _mcols: c.execute("ALTER TABLE record_meta ADD COLUMN decision TEXT NOT NULL DEFAULT ''")


def format_decision(decision, rationale='', options=(), revisit=''):
    lines = ['Decision: ' + decision.strip()]
    if rationale.strip(): lines.append('Why: ' + rationale.strip())
    opts = [o.strip() for o in options if str(o).strip()]
    if opts: lines.append('Options considered: ' + '; '.join(opts))
    if revisit.strip(): lines.append('Revisit when: ' + revisit.strip())
    return '\n'.join(lines)


def parse_decision(text):
    """Inverse of format_decision; tolerant of edits. Lines without a label extend the decision."""
    out = {'decision': '', 'rationale': '', 'options': [], 'revisit': ''}
    key = 'decision'
    for line in (text or '').splitlines():
        low = line.strip().lower()
        for label, k in (('decision:', 'decision'), ('why:', 'rationale'), ('options considered:', 'options'),
                         ('options:', 'options'), ('revisit when:', 'revisit'), ('revisit:', 'revisit')):
            if low.startswith(label):
                key = k; line = line.strip()[len(label):]; break
        line = line.strip()
        if not line: continue
        if key == 'options': out['options'] += [o.strip() for o in line.split(';') if o.strip()]
        else: out[key] = (out[key] + ' ' + line).strip()
    return out


def propose_decision(title, decision, source, rationale='', options=(), revisit='', revisit_date='', decided_on='', category=''):
    import re as _re
    decision = (decision or '').strip()
    if len(decision) < 8: raise ValueError('State the decision itself (what was chosen).')
    if revisit_date and not _re.fullmatch(r'\d{4}-\d{2}-\d{2}', revisit_date): raise ValueError('revisit_date must look like 2027-03-31.')
    content = format_decision(decision, rationale, options, revisit)
    import rules_engine
    if rules_engine.on('duplicates'):   # for decisions, what matters is the chosen option itself
        from difflib import SequenceMatcher
        threshold = rules_engine.params('duplicates').get('threshold', 0.9)
        norm = lambda t: ' '.join(_re.sub(r'[^a-z0-9 ]', ' ', (t or '').lower()).split())
        with db() as c:
            rows = c.execute("SELECT r.id,r.title,m.decision FROM record_meta m JOIN records r ON r.id=m.record_id "
                             "LEFT JOIN memory_archive a ON a.record_id=r.id WHERE m.kind='decision' "
                             "AND coalesce(a.state,r.status) IN ('approved','proposed')").fetchall()
        for r in rows:
            existing = json.loads(r['decision'] or '{}').get('decision', '')
            if existing and SequenceMatcher(None, norm(decision), norm(existing)).ratio() >= threshold:
                rules_engine.log_block('duplicates', title, f'duplicate decision of {r["id"]}')
                raise rules_engine.RuleViolation(f'Blocked by the Duplicate block: this matches the decision "{r["title"]}". '
                                                 'Replace that decision instead if it has changed.')
    result = propose(title, content, source, category)     # all memory rules apply (quality, duplicates, security)
    if result.get('id') and not result.get('duplicate'):
        meta = {'decision': decision, 'rationale': rationale.strip(), 'options': [o.strip() for o in options if str(o).strip()],
                'revisit': revisit.strip(), 'decided_on': decided_on.strip()[:10]}
        with db() as c:
            c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (result['id'],))
            c.execute("UPDATE record_meta SET kind='decision',decision=?,review_by=coalesce(?,review_by) WHERE record_id=?",
                      (json.dumps(meta), revisit_date or None, result['id']))
    return result


def record_kinds(ids):
    ids = list(ids)
    if not ids: return {}
    with db() as c:
        return {r['record_id']: {'kind': r['kind'], 'decision': json.loads(r['decision']) if r['decision'] else None}
                for r in c.execute(f"SELECT record_id,kind,decision FROM record_meta WHERE record_id IN ({','.join('?' * len(ids))})", ids)}


_organised_before_decisions = organised_records


def organised_records(status='approved', query='', category='', sort='newest', offset=0, limit=50, kind=''):
    """kind: '' all, 'fact' or 'decision'."""
    if kind not in ('fact', 'decision'):
        d = _organised_before_decisions(status, query, category, sort, offset, limit)
    else:
        full = _organised_before_decisions(status, query, category, sort, 0, 100000)
        kinds = record_kinds(r['id'] for r in full['records'])
        rows = [r for r in full['records'] if kinds.get(r['id'], {}).get('kind', 'fact') == kind]
        d = full | {'records': rows[offset:offset + limit], 'total': len(rows),
                    'next_offset': offset + limit if offset + limit < len(rows) else None}
    kinds = record_kinds(r['id'] for r in d['records'])
    for r in d['records']:
        k = kinds.get(r['id'], {})
        r['kind'] = k.get('kind') or 'fact'
        r['decision'] = k.get('decision')
    with db() as c:
        d['decisions'] = c.execute("SELECT count(*) FROM record_meta m JOIN records r ON r.id=m.record_id LEFT JOIN memory_archive a ON a.record_id=r.id "
                                   "WHERE m.kind='decision' AND (?='all' OR coalesce(a.state,r.status)=?)", (status, status)).fetchone()[0]
    return d


# ---- Quote verification shared by Temple's reviews: forgiving about typography, strict about words.
def _plain(text):
    import re as _re, unicodedata
    t = unicodedata.normalize('NFKC', text or '').lower()
    t = t.translate(str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-'}))
    t = _re.sub(r"[^a-z0-9' ]+", ' ', t)
    return ' '.join(t.replace("'", '').split())


def quote_found(quote, texts):
    """Index of the text containing the quote (every '…'-separated fragment must be the user's own words), else -1."""
    import re as _re
    fragments = [_plain(f) for f in _re.split(r'\.\.\.|\u2026', quote or '')]
    fragments = [f for f in fragments if f]
    if not fragments or sum(len(f) for f in fragments) < 6: return -1
    for i, t in enumerate(texts):
        p = _plain(t)
        if all(f in p for f in fragments): return i
    return -1


# ---- Accountability: who did each thing, why, and who owns each item.
# ACTOR is set per request (app.py middleware): the signed-in person once Alice runs behind Entra
# (ALICE_TRUST_EASYAUTH=1), otherwise the owner's name (ALICE_OWNER_NAME). NOTE is an optional reason
# given with a decision (approve, reject). Both are written on every activity row by audit().
# Owners are people's names for your own tracking: never sent to a model.
import logging as _logging
import re as _re_acc

ACTOR = contextvars.ContextVar('alice_actor', default='')
NOTE = contextvars.ContextVar('alice_note', default='')
_audit_log = _logging.getLogger('alice.audit')
PERSON = _re_acc.compile(r"[A-Za-z][A-Za-z .'\-]{1,79}")


def owner_name():
    return ' '.join((os.environ.get('ALICE_OWNER_NAME') or 'Owner').split())[:80] or 'Owner'


def actor():
    return ACTOR.get() or owner_name()


@contextmanager
def acting(who=None, note=None):
    t1 = ACTOR.set(' '.join(str(who).split())[:120]) if who else None
    t2 = NOTE.set(' '.join(str(note).split())[:500]) if note is not None else None
    try: yield
    finally:
        if t2 is not None: NOTE.reset(t2)
        if t1 is not None: ACTOR.reset(t1)


def clean_person(name, what='Owner'):
    name = ' '.join((name or '').split())[:80]
    if name and not PERSON.fullmatch(name):
        raise ValueError(f"{what}: a person's name (letters, spaces, hyphens and apostrophes).")
    return name


def _accountability_schema():
    with db() as c:
        acols = {r['name'] for r in c.execute('PRAGMA table_info(activity)')}
        if acols and 'actor' not in acols: c.execute("ALTER TABLE activity ADD COLUMN actor TEXT NOT NULL DEFAULT ''")
        if acols and 'note' not in acols: c.execute("ALTER TABLE activity ADD COLUMN note TEXT NOT NULL DEFAULT ''")
        c.execute("CREATE TABLE IF NOT EXISTS record_meta (record_id TEXT PRIMARY KEY, category TEXT NOT NULL DEFAULT '')")
        if 'owner' not in {r['name'] for r in c.execute('PRAGMA table_info(record_meta)')}:
            c.execute("ALTER TABLE record_meta ADD COLUMN owner TEXT NOT NULL DEFAULT ''")


_accountability_schema()
_init_before_accountability = init


def init():
    _init_before_accountability()
    _accountability_schema()


def audit(c, action, target, rule, detail=''):
    """Every activity row records who (actor) and, for decisions, why (note). With ALICE_AUDIT_STDOUT=1 (Azure) each
    row is also written as one JSON line to the 'alice.audit' log, which Container Apps sends to Log Analytics."""
    at, who, note = now(), actor(), NOTE.get()
    c.execute('INSERT INTO activity(created_at,action,target,rule,detail,actor,note) VALUES (?,?,?,?,?,?,?)',
              (at, action, target, rule, detail, who, note))
    if os.environ.get('ALICE_AUDIT_STDOUT') == '1':
        _audit_log.info(json.dumps({'type': 'alice.audit', 'at': at, 'action': action, 'target': target, 'rule': rule,
                                    'detail': detail[:2000], 'actor': who, 'note': note}, ensure_ascii=False))


DECISION_ACTIONS = ('record_approved', 'record_rejected', 'friction_resolved', 'knowledge_approved', 'knowledge_rejected',
                    'org_fact_approved', 'org_fact_rejected', 'org_fact_added', 'memory_retired', 'memory_superseded')


def decisions_for(ids):
    """Latest approval-type decision per item: {id: {action, at, actor, note}} (actor '' = recorded before approvers were kept)."""
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids: return {}
    out = {}
    with db() as c:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            q = (f"SELECT target,action,created_at,actor,note FROM activity WHERE target IN ({','.join('?' * len(chunk))}) "
                 f"AND action IN ({','.join('?' * len(DECISION_ACTIONS))}) ORDER BY id")
            for r in c.execute(q, chunk + list(DECISION_ACTIONS)):
                out[r['target']] = {'action': r['action'], 'at': r['created_at'], 'actor': r['actor'], 'note': r['note']}
    return out


def set_owner(ids, owner):
    """Owner of memories and decisions (records)."""
    owner = clean_person(owner)
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, str) and i][:500]
    done = 0
    with db() as c:
        for rid in ids:
            if not c.execute('SELECT 1 FROM records WHERE id=?', (rid,)).fetchone(): continue
            c.execute('INSERT OR IGNORE INTO record_meta(record_id) VALUES (?)', (rid,))
            c.execute('UPDATE record_meta SET owner=? WHERE record_id=?', (owner, rid))
            done += 1
        if done: audit(c, 'owner_set', ids[0] if done == 1 else f'{done} memories', 'human_review', owner or '(no owner)')
    return {'updated': done, 'owner': owner}


def owners():
    """Names already used as owners (memories and knowledge), for suggestions."""
    names = set()
    with db() as c:
        names |= {r[0] for r in c.execute("SELECT DISTINCT owner FROM record_meta WHERE owner<>''")}
        try: names |= {r[0] for r in c.execute("SELECT DISTINCT owner FROM knowledge_meta WHERE owner<>''")}
        except sqlite3.OperationalError: pass
    return sorted(names, key=str.lower)


_organised_before_owners = organised_records


def organised_records(status='approved', query='', category='', sort='newest', offset=0, limit=50, kind='', owner=''):
    """owner: '' any, '__none__' no owner, or a name."""
    if not owner:
        d = _organised_before_owners(status, query, category, sort, offset, limit, kind)
    else:
        full = _organised_before_owners(status, query, category, sort, 0, 100000, kind)
        with db() as c:
            om = {r[0]: r[1] for r in c.execute("SELECT record_id,owner FROM record_meta")}
        rows = [r for r in full['records'] if (om.get(r['id'], '') == '' if owner == '__none__' else om.get(r['id'], '').lower() == owner.lower())]
        d = full | {'records': rows[offset:offset + limit], 'total': len(rows),
                    'next_offset': offset + limit if offset + limit < len(rows) else None}
    ids = [r['id'] for r in d['records']]
    om = {}
    if ids:
        marks = ','.join('?' * len(ids))
        with db() as c:
            om = {r[0]: r[1] for r in c.execute(f'SELECT record_id,owner FROM record_meta WHERE record_id IN ({marks})', ids)}
    dec = decisions_for(ids)
    for r in d['records']:
        r['owner'] = om.get(r['id'], '')
        r['decided'] = dec.get(r['id'])
    d['owners'] = owners()
    return d
