"""What changed in Alice (Stefan, 9 Oct 2026): CHANGELOG.md, read at each deploy.

- CHANGELOG.md at the repository root: a `## YYYY-MM-DD` heading per day, newest first, and one line per pull request,
  `- #<number> <what changed for Stefan>`, with "You need to: …" at the end when there is a manual step. `parse()` reads it
  and lists anything malformed; deploy/changelog_check.py (the pull request check) uses the same parser.
- At start-up of the web app (`record_release()`, once per process, outside any transaction) Alice imports the entries
  (`changelog_entries`, one row per pull request, so a restart or a second process never duplicates one) and records the
  release she is running (`releases`: the commit code from ui_theme.version_info, when this release first started and,
  once it serves its first request through the public address rather than its own revision address, when it went live,
  `note_live()`). The process that records a new release also writes ONE knowledge item for it in the category
  "Alice changes" (general, in the work space), listing the entries new in that release, through knowledge.create (its
  checks) and then the same approval call automatic approval uses (Stefan's say, 9 Oct 2026: approved automatically,
  logged auto_approved). A refused item is not stored; the reason is kept on the release. On the PC (release 'local') and
  on the demo Alice (its database holds only the fictional team, and its loader refuses a database with other knowledge)
  entries are imported but no knowledge item is written.
- The setup steps run in Azure (`setup_steps()`): the history that deploy/azure_state.py appends to the setup state and
  mirrors to the file share (setup/setup-history.json, read here from the share's mount), plus the steps run before
  the history existed (deploy/setup-history-start.json).
- Admin › What's new (`overview()`, Owner and Admin) and Ask Temple's `recent_changes` tool read the same data.

The parser is stdlib only and this module imports Alice's own modules inside its functions, so the pull request check
can import it without a database.
"""
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(ROOT, 'CHANGELOG.md')
SETUP_START = os.path.join(ROOT, 'deploy', 'setup-history-start.json')
CATEGORY = 'Alice changes'
CATEGORY_NOTE = "What changed in Alice: one item per release, from CHANGELOG.md. Written automatically at each deploy."
NEED = 'You need to:'
REPO = 'https://github.com/stefanjoc-ux/Alice'
_DAY = re.compile(r'^##\s+(\d{4}-\d{2}-\d{2})\s*$')
_ENTRY = re.compile(r'^- #(\d{1,6})\s+(\S.*)$')
_SETUP_FIELDS = ('id', 'at', 'step', 'who', 'params', 'result', 'error', 'from', 'note')


# ---------------- the file ----------------
def parse(text):
    """(entries, problems). Entries in file order: {date, pr, text, action}. Problems: plain sentences naming the line."""
    entries, problems, day, last_day, seen = [], [], '', '', set()
    for n, raw in enumerate((text or '').splitlines(), 1):
        line = raw.rstrip()
        if not line.strip(): continue
        m = _DAY.match(line)
        if m:
            try: date.fromisoformat(m.group(1))
            except ValueError: problems.append(f'line {n}: "{m.group(1)}" is not a real date (use YYYY-MM-DD).'); continue
            if last_day and m.group(1) > last_day: problems.append(f'line {n}: {m.group(1)} comes after {last_day}; newest dates go first.')
            day = last_day = m.group(1)
            continue
        if not day: continue                                   # the title and the opening paragraph
        if line.startswith('#'): problems.append(f'line {n}: use "## YYYY-MM-DD" headings only.'); continue
        m = _ENTRY.match(line)
        if not m:
            problems.append(f'line {n}: each entry is one line starting with "- #<pull request number> ", e.g. "- #34 What changed".')
            continue
        pr, body = int(m.group(1)), m.group(2).strip()
        if pr in seen: problems.append(f'line {n}: #{pr} has more than one line; one line per pull request.'); continue
        seen.add(pr)
        what, _, need = body.partition(NEED)
        if len(body) > 600: problems.append(f'line {n}: #{pr} is longer than 600 characters; keep it to one plain line.')
        if not what.strip(): problems.append(f'line {n}: #{pr} says what you need to do but not what changed.')
        entries.append({'date': day, 'pr': pr, 'text': ' '.join(what.split()), 'action': ' '.join(need.split())})
    if not entries: problems.append('No entries found: add "## YYYY-MM-DD" and a line "- #<number> What changed".')
    return entries, problems


def read(path=FILE):
    try:
        with open(path, encoding='utf-8') as f: return parse(f.read())
    except OSError:
        return [], [f'{os.path.basename(path)} could not be read.']


# ---------------- the database ----------------
def _schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS changelog_entries (pr INTEGER PRIMARY KEY, day TEXT NOT NULL, text TEXT NOT NULL, '
              "action TEXT NOT NULL DEFAULT '', release TEXT NOT NULL DEFAULT '', imported_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS releases (version TEXT PRIMARY KEY, built TEXT NOT NULL DEFAULT '', revision TEXT NOT NULL DEFAULT '', "
              "started_at TEXT NOT NULL, live_at TEXT, entries INTEGER NOT NULL DEFAULT 0, knowledge_id TEXT NOT NULL DEFAULT '', "
              "note TEXT NOT NULL DEFAULT '')")


_READY = False


def _ready():
    global _READY
    if _READY: return
    import substrate_store as store
    with store.db() as c: _schema(c)
    _READY = True


def _in_azure(env=None):
    env = os.environ if env is None else env
    return bool(env.get('CONTAINER_APP_REVISION'))


def record_release(path=FILE, env=None):
    """Import CHANGELOG.md and record the running release. Safe to call from every process at every start: only the first
    to see a release records it and writes its knowledge item. Returns what it did."""
    import substrate_store as store, ui_theme
    _ready()
    env = os.environ if env is None else env
    info = ui_theme.version_info(env)
    version = info['version']
    entries, problems = read(path)
    now = store.now()
    new, claimed = [], False
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        known = {r[0]: (r[1], r[2], r[3]) for r in c.execute('SELECT pr,day,text,action FROM changelog_entries')}
        for e in entries:
            if e['pr'] not in known:
                c.execute('INSERT INTO changelog_entries(pr,day,text,action,release,imported_at) VALUES (?,?,?,?,?,?)',
                          (e['pr'], e['date'], e['text'], e['action'], version, now))
                new.append(e)
            elif known[e['pr']] != (e['date'], e['text'], e['action']):        # wording corrected later: the line is updated, not added
                c.execute('UPDATE changelog_entries SET day=?,text=?,action=? WHERE pr=?', (e['date'], e['text'], e['action'], e['pr']))
        if not c.execute('SELECT 1 FROM releases WHERE version=?', (version,)).fetchone():
            claimed = True
            live = None if _in_azure(env) else now          # on the PC there is no traffic switch: live when it starts
            c.execute('INSERT INTO releases(version,built,revision,started_at,live_at,entries) VALUES (?,?,?,?,?,?)',
                      (version, info['built'], info['revision'], now, live, len(new)))
        elif new:
            c.execute('UPDATE releases SET entries=entries+? WHERE version=?', (len(new), version))
    out = {'version': version, 'new_entries': len(new), 'recorded': claimed, 'problems': problems, 'knowledge': ''}
    if claimed:
        with store.db() as c:
            store.audit(c, 'release_recorded', version, 'human_control',
                        f'Release {version} started' + (f' (built {info["built"]})' if info['built'] else '') + f': {len(new)} new change log entr'
                        + ('y' if len(new) == 1 else 'ies') + (f'; {len(problems)} change log problem(s)' if problems else ''))
    import demo_instance
    if claimed and new and version != 'local' and not demo_instance.ON:     # the demo Alice holds only its fictional team's material
        out['knowledge'] = _knowledge_item(version, info, new)
    return out


def _item_text(version, info, new):
    lines = [f'Release {version} of Alice' + (f', built {info["built"][:10]}' if info.get('built') else '') + '.',
             f'Commit: {REPO}/commit/{version}' if re.fullmatch(r'[0-9a-f]{7,40}', version) else '', '',
             'What changed in this release (from CHANGELOG.md, newest first):']
    day = ''
    for e in sorted(new, key=lambda e: (e['date'], e['pr']), reverse=True):
        if e['date'] != day:
            day = e['date']; lines += ['', _long(day)]
        lines.append(f"- #{e['pr']} {e['text']}" + (f" You need to: {e['action']}" if e['action'] else ''))
    lines += ['', "Every release and the setup steps run in Azure are on Admin › What's new."]
    return '\n'.join(l for l in lines if l is not None)


def _knowledge_item(version, info, new):
    """One knowledge item for the release, through the normal knowledge checks, approved automatically. Returns its id, or ''."""
    import substrate_store as store, knowledge, autoapprove
    title = f'Alice release {version}: ' + (f'{len(new)} changes' if len(new) != 1 else '1 change') + f' ({_long(max(e["date"] for e in new))})'
    note = ''
    try:
        _category()
        with store.acting('Alice', note=f'Release {version} recorded at deploy'):
            r = knowledge.create('note', title, _item_text(version, info, new), f'CHANGELOG.md, release {version}', 'Alice',
                                 status='draft', label='general', category=CATEGORY)
        fid = r.get('id') or ''
        if fid and not r.get('duplicate'):
            with store.acting('Alice', note='Release notes approved automatically'):
                done = knowledge.review([fid], 'approved')
            if done['changed']: autoapprove._approved('knowledge', fid, f'release notes for {version}')
            else: note = 'Not approved: ' + ' '.join(done['block_reasons'])
    except ValueError as e:
        fid, note = '', f'The release notes were not stored: {e}'
    with store.db() as c:
        c.execute('UPDATE releases SET knowledge_id=?,note=? WHERE version=?', (fid, note[:500], version))
        if note: store.audit(c, 'release_notes_refused', version, 'human_control', note[:500])
    return fid


def _category():
    """The category "Alice changes" (Work), made once if it is missing."""
    import substrate_store as store
    with store.db() as c:
        have = c.execute('SELECT 1 FROM categories WHERE name=?', (CATEGORY,)).fetchone()
    if not have:
        try: store.create_category(CATEGORY, CATEGORY_NOTE)
        except ValueError: pass                          # made by another process at the same moment
    with store.db() as c:
        cols = {r['name'] for r in c.execute('PRAGMA table_info(categories)')}
        if 'area' in cols: c.execute("UPDATE categories SET area='work' WHERE name=? AND coalesce(area,'')=''", (CATEGORY,))


# ---------------- went live ----------------
_LIVE_NOTED = False


def note_live(host, path, revision_hosts=(), env=None):
    """Called for each request until it succeeds once: the first request this release serves through the public address
    (not its own revision address, not /healthz) means the traffic is on it, so it is live. Cheap after the first time."""
    global _LIVE_NOTED
    if _LIVE_NOTED: return False
    env = os.environ if env is None else env
    if not _in_azure(env): _LIVE_NOTED = True; return False
    host = (host or '').split(':')[0].lower()
    if path == '/healthz' or not host or host in ('127.0.0.1', 'localhost', 'testserver') or host in revision_hosts: return False
    import substrate_store as store, ui_theme
    _ready()
    version = ui_theme.version_info(env)['version']
    with store.db() as c:
        cur = c.execute('UPDATE releases SET live_at=? WHERE version=? AND live_at IS NULL', (store.now(), version))
        changed = (cur.rowcount or 0) > 0
    _LIVE_NOTED = True
    if changed:
        with store.db() as c: store.audit(c, 'release_live', version, 'human_control', f'Release {version} went live (first request through the public address)')
    return changed


# ---------------- setup steps run in Azure ----------------
def setup_file(env=None):
    env = os.environ if env is None else env
    if env.get('ALICE_SETUP_HISTORY'): return env['ALICE_SETUP_HISTORY']
    data = env.get('AISUBSTRATE_DATA_DIR') or os.path.join(ROOT, 'data')
    return os.path.join(os.path.dirname(os.path.abspath(data)), 'setup', 'setup-history.json')


def _load_json(path):
    try:
        with open(path, encoding='utf-8-sig') as f: d = json.load(f)
    except (OSError, ValueError):
        return []
    d = d.get('setupHistory', []) if isinstance(d, dict) else d
    return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []


def setup_steps(env=None, limit=200):
    """The setup steps run, newest first: the history mirrored to the file share, plus the steps before it existed."""
    rows, order = {}, {}
    for i, x in enumerate(_load_json(SETUP_START) + _load_json(setup_file(env))):
        if not x.get('id'): continue
        clean = {k: x.get(k) for k in _SETUP_FIELDS if x.get(k) not in (None, '')}
        p = clean.get('params')
        clean['params'] = {str(k)[:40]: str(v)[:200] for k, v in p.items()} if isinstance(p, dict) else {}
        rows[str(x['id'])] = clean
        order.setdefault(str(x['id']), i)
    return sorted(rows.values(), key=lambda r: (str(r.get('at', '')), order[str(r['id'])]), reverse=True)[:limit]


# ---------------- reading ----------------
def _long(day):
    try: d = date.fromisoformat(str(day)[:10])
    except ValueError: return str(day)
    return f'{d.day} {d.strftime("%b %Y")}'


def entries(days=None, limit=500):
    import substrate_store as store
    _ready()
    q, a = 'SELECT pr,day,text,action,release,imported_at FROM changelog_entries', []
    if days:
        q += ' WHERE day>=?'; a.append((date.today() - timedelta(days=int(days))).isoformat())
    with store.db() as c:
        rows = [dict(r) for r in c.execute(q + ' ORDER BY day DESC, pr DESC LIMIT ?', (*a, int(limit)))]
    for r in rows: r['link'] = f"{REPO}/pull/{r['pr']}"
    return rows


def releases(limit=50):
    import substrate_store as store, refs
    _ready()
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT version,built,revision,started_at,live_at,entries,knowledge_id,note FROM releases '
                                           'ORDER BY started_at DESC LIMIT ?', (int(limit),))]
    known = {}
    try: known = refs.of('file', [r['knowledge_id'] for r in rows if r['knowledge_id']])
    except Exception: pass
    for r in rows:
        r['link'] = f"{REPO}/commit/{r['version']}" if re.fullmatch(r'[0-9a-f]{7,40}', r['version']) else ''
        r['knowledge_ref'] = known.get(r['knowledge_id'], '')
    return rows


def overview(env=None):
    """Admin › What's new: the running release, the releases, the entries by day and the setup steps run."""
    import ui_theme
    info = ui_theme.version_info(env)
    rels = releases()
    running = next((r for r in rels if r['version'] == info['version']), None)
    days = {}
    for e in entries():
        days.setdefault(e['day'], []).append(e)
    _f, problems = read()
    return {'running': {**info, 'started_at': (running or {}).get('started_at'), 'live_at': (running or {}).get('live_at')},
            'releases': rels, 'days': [{'day': d, 'label': _long(d), 'entries': days[d]} for d in sorted(days, reverse=True)],
            'setup': setup_steps(env), 'setup_file_found': os.path.exists(setup_file(env)), 'problems': problems}


def recent(days=14):
    """For Ask Temple: the change log entries of the last `days` days, the releases and the setup steps in that period."""
    import rules_engine
    since = (datetime.now(timezone.utc) - timedelta(days=int(days))).strftime('%Y-%m-%d')
    rels = [r for r in releases() if (r['started_at'] or '')[:10] >= since]
    steps = [s for s in setup_steps() if str(s.get('at', ''))[:10] >= since]
    # This goes to Temple's model: each line is checked on its own (rule 6, check_each); one that fails is left out and logged
    kept, left = rules_engine.check_each(entries(days), lambda e: f"{e['text']} {e['action']}", 'Ask Temple: recent changes')
    steps, left_steps = rules_engine.check_each(steps, lambda s: json.dumps(s, ensure_ascii=False), 'Ask Temple: setup steps')
    return {'since': since, 'left_out_by_the_rules': left + left_steps,
            'changes': [{'date': e['day'], 'pull_request': e['pr'], 'what_changed': e['text'], 'you_need_to': e['action'],
                         'release': e['release']} for e in kept],
            'releases': [{'release': r['version'], 'started_utc': (r['started_at'] or '')[:16].replace('T', ' '),
                          'live_utc': (r['live_at'] or '')[:16].replace('T', ' ') or 'not live yet', 'new_entries': r['entries'],
                          'knowledge_item': r['knowledge_ref']} for r in rels],
            'setup_steps': steps,
            'where': "Admin › What's new; each release is also a knowledge item in the category Alice changes"}
