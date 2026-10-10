"""Temple's model for screening and categories (Stefan, 9 Oct 2026): Cloud or Local.

The setting "Temple's model for screening and categories" (Agents page, setting `temple_screen_model`: cloud, or local) decides
which model does Temple's screening work: the sharing check before an item enters a shared space (spaces.py), categories
(temple_categorise), tags (temple_tags) and keeping categories and tags tidy (temple_taxonomy). Everything else stays on the cloud
models: writing, judgement, Temple's reviews and discussions, Argus and the digital teams.

Local = a small open model served by an Ollama-style container inside Alice's own Container Apps environment (infra/local-model.bicep,
azure-setup.ps1 -Step localmodel), reached only on internal ingress (ALICE_LOCAL_MODEL_URL, e.g. http://alice-local-model) and named
by ALICE_LOCAL_MODEL. Nothing about the checks changes with the choice: every caller runs the same rules (check_outbound, spending
caps) on what it sends whichever model answers. Only where it goes changes.

If the local model does not answer, the work is held (never sent to a cloud model) unless the switch "If the local model does not
answer, use the cloud model" is on (setting `temple_local_fallback`, off by default). Held work is listed on the Agents page with
Try again. Every screening records which model did it (`temple_screenings`), and the sharing check also keeps it on the move and
in the activity log. An evaluation on fixed, fictional examples compares the local and cloud models (agent temple-model-eval)."""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

import substrate_store as store

TASKS = {'share_gate': ('Sharing check', 'temple-share-gate'), 'categorise': ('Categories', 'temple-categorise'),
         'tags': ('Tags', 'temple-memory-tags'), 'taxonomy': ('Keeping categories and tags tidy', 'temple-taxonomy')}
CHOICES = ('cloud', 'local')
TIMEOUT = {'share_gate': 120, 'categorise': 300, 'tags': 300, 'taxonomy': 300}   # a small model on CPU: background work may take minutes
HTTP = None            # tests replace this: function(method, url, body_or_None, timeout) -> dict


class LocalModelHeld(ValueError):
    """The local model did not answer and falling back to the cloud is off: the work waits (agents record it as blocked)."""


class Unavailable(Exception):
    pass


def _schema(c):
    c.execute("CREATE TABLE IF NOT EXISTS temple_screenings (id TEXT PRIMARY KEY, task TEXT NOT NULL, at TEXT NOT NULL, place TEXT NOT NULL, "
              "model TEXT NOT NULL DEFAULT '', fallback INTEGER NOT NULL DEFAULT 0, outcome TEXT NOT NULL DEFAULT 'done', "
              "reason TEXT NOT NULL DEFAULT '', items TEXT NOT NULL DEFAULT '[]')")
    c.execute('CREATE INDEX IF NOT EXISTS temple_screenings_at ON temple_screenings(at)')
    c.execute("CREATE TABLE IF NOT EXISTS temple_held (id TEXT PRIMARY KEY, task TEXT NOT NULL, item_type TEXT NOT NULL DEFAULT '', "
              "item_id TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '', "
              "resolved_how TEXT NOT NULL DEFAULT '')")


with store.db() as _c: _schema(_c)


# ---------------- settings ----------------
def _setting(key, default=''):
    with store.db() as c:
        r = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return r[0] if r else default


def _put(c, key, value):
    c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))


def url():
    return (os.environ.get('ALICE_LOCAL_MODEL_URL') or '').strip().rstrip('/')


def model():
    return (os.environ.get('ALICE_LOCAL_MODEL') or '').strip()


def configured():
    return bool(url() and model())


def choice():
    v = _setting('temple_screen_model', 'cloud')
    return v if v in CHOICES else 'cloud'


def fallback():
    return _setting('temple_local_fallback', '0') == '1'


def set_choice(where=None, allow_fallback=None):
    """Stefan's choice on the Agents page. Local only when a local model is set up (else everything would wait)."""
    if where is not None and where not in CHOICES: raise ValueError('Choose Cloud or Local.')
    if where == 'local' and not configured():
        raise ValueError('No local model is set up yet. Run azure-setup.ps1 -Step localmodel -LocalModel on first, then choose Local.')
    changes = []
    with store.db() as c:
        if where is not None and where != choice():
            _put(c, 'temple_screen_model', where); changes.append(f'model for screening and categories: {where}')
        if allow_fallback is not None and bool(allow_fallback) != fallback():
            _put(c, 'temple_local_fallback', '1' if allow_fallback else '0')
            changes.append('if the local model does not answer: ' + ('use the cloud model' if allow_fallback else 'hold the work'))
        if changes: store.audit(c, 'temple_model_set', 'Temple', 'human_control', '; '.join(changes))
    return status(check=False)


def cloud_model():
    """The cloud model Temple's screening uses when it is not local (Temple's reviewer: Luna or Haiku)."""
    import temple, assistants
    p = temple.reviewer()
    return p, assistants.PROVIDERS.get(p, (p,))[0]


# ---------------- the local model ----------------
def _http(method, address, body, timeout):
    if HTTP is not None: return HTTP(method, address, body, timeout)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(address, data=data, method=method, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read().decode() or '{}').get('error') or ''
        except Exception: msg = ''
        raise Unavailable(f'HTTP {e.code}' + (f': {str(msg)[:160]}' if msg else '')) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise Unavailable(str(getattr(e, 'reason', e))[:160] or type(e).__name__) from None


def local(system, user, max_tokens, task='share_gate'):
    """The local model's answer: (text, cut off at the length limit?). Raises Unavailable when it does not answer."""
    if not configured(): raise Unavailable('no local model is set up')
    body = {'model': model(), 'stream': False, 'format': 'json', 'think': False,
            'options': {'num_predict': int(max_tokens), 'temperature': 0},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    d = _http('POST', url() + '/api/chat', body, TIMEOUT.get(task, 120))
    text = ((d or {}).get('message') or {}).get('content')
    if not isinstance(text, str) or not text.strip(): raise Unavailable('it gave an empty answer')
    try:
        import agents
        agents.add_cost(0, 'local', model())        # the run records which model it called (Data touched: Sent to)
    except Exception:
        pass
    return text, (d or {}).get('done_reason') == 'length'


def reachable():
    """(answering?, reason). A quick look (GET /api/tags) for the Agents page; never sends Alice's data."""
    if not configured(): return False, 'not set up'
    try:
        d = _http('GET', url() + '/api/tags', None, 3)
    except Unavailable as e:
        return False, str(e)
    names = {m.get('name') or m.get('model') for m in (d or {}).get('models') or []}
    want = model()
    if want not in names and f'{want}:latest' not in names:
        return False, f'answering, but {want} is not loaded yet (it is downloaded when the container starts)'
    return True, ''


# ---------------- the one path for screening work ----------------
def _items(items):
    return [[str(t)[:20], str(i)[:80]] for t, i in list(items or [])[:50]]


def _record(task, place, name, fell_back, items, outcome='done', reason=''):
    with store.db() as c:
        c.execute('INSERT INTO temple_screenings(id,task,at,place,model,fallback,outcome,reason,items) VALUES (?,?,?,?,?,?,?,?,?)',
                  (uuid.uuid4().hex, task, store.now(), place, name or '', int(bool(fell_back)), outcome, (reason or '')[:300],
                   json.dumps(_items(items))))


def _hold(task, items, reason):
    t = store.now()
    rows = _items(items) or [['', '']]
    with store.db() as c:
        for it, iid in rows:
            if c.execute("SELECT 1 FROM temple_held WHERE task=? AND item_type=? AND item_id=? AND resolved_at=''", (task, it, iid)).fetchone(): continue
            c.execute('INSERT INTO temple_held(id,task,item_type,item_id,reason,at) VALUES (?,?,?,?,?,?)', (uuid.uuid4().hex, task, it, iid, reason[:300], t))
        store.audit(c, 'temple_model_held', task, 'temple_model',
                    f'{TASKS[task][0]}: {len(rows) if rows[0][1] else 1} item(s) waiting. Temple\'s local model did not answer ({reason[:160]}) '
                    'and falling back to the cloud is switched off.')


def held_message(reason):
    return (f'Temple\'s local model did not answer ({reason}), and falling back to the cloud is switched off, so this waits. '
            'It is listed on the Agents page, with Try again.')


def answer(task, system, user, max_tokens, cloud, items=()):
    """Temple's answer for screening work, from the model chosen on the Agents page. cloud: a function giving the cloud answer
    (the caller's own cloud call), as text or (text, cut off?). The caller has already run the rules on what it sends.
    Returns (text, cut off?, label of the model that answered). Raises LocalModelHeld when the work must wait."""
    if task not in TASKS: raise ValueError('Unknown screening task.')
    if choice() == 'local':
        name = model()
        try:
            text, cut = local(system, user, max_tokens, task)
            _record(task, 'local', name, False, items)
            return text, cut, f'local model {name}'
        except Unavailable as e:
            reason = str(e)
            if not fallback():
                _record(task, 'local', name, False, items, 'held', reason)
                _hold(task, items, reason)
                raise LocalModelHeld(held_message(reason)) from None
            out = cloud()
            text, cut = out if isinstance(out, tuple) else (out, False)
            _, cm = cloud_model()
            _record(task, 'cloud', cm, True, items, 'done', reason)
            return text, cut, f'cloud model {cm} (the local model did not answer: {reason})'
    out = cloud()
    text, cut = out if isinstance(out, tuple) else (out, False)
    _, cm = cloud_model()
    _record(task, 'cloud', cm, False, items)
    return text, cut, f'cloud model {cm}'


# ---------------- held work ----------------
def held():
    with store.db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM temple_held WHERE resolved_at='' ORDER BY at")]
    by = {}
    for r in rows: by[r['task']] = by.get(r['task'], 0) + 1
    return {'count': len(rows), 'by_task': [{'task': k, 'label': TASKS[k][0], 'count': n} for k, n in by.items() if k in TASKS],
            'since': rows[0]['at'] if rows else '', 'last_reason': rows[-1]['reason'] if rows else '', 'rows': rows[:200]}


def _resolve(c, task, ids, how):
    t = store.now()
    if ids is None:
        c.execute("UPDATE temple_held SET resolved_at=?,resolved_how=? WHERE task=? AND resolved_at=''", (t, how, task))
    for i in ids or []:
        c.execute("UPDATE temple_held SET resolved_at=?,resolved_how=? WHERE task=? AND item_id=? AND resolved_at=''", (t, how, task, i))


def retry():
    """Try the held work again (the Agents page's Try again). Each task runs through its own agent, so the checks are the same;
    anything still held stays listed. Returns {task: outcome}."""
    h = held()['rows']
    if not h: return {'status': 'nothing', 'results': {}}
    ids = {}
    for r in h: ids.setdefault(r['task'], []).append(r['item_id'])
    out = {}
    if 'categorise' in ids:
        out['categorise'] = _again('categorise', lambda: __import__('temple_categorise').run([i for i in ids['categorise'] if i], manual=True), ids['categorise'])
    if 'tags' in ids:
        out['tags'] = _again('tags', lambda: __import__('temple_tags').run([i for i in ids['tags'] if i], manual=True), ids['tags'])
    if 'taxonomy' in ids:
        out['taxonomy'] = _again('taxonomy', lambda: __import__('temple_taxonomy').review(manual=True), None)
    if 'share_gate' in ids:
        import spaces
        out['share_gate'] = _again('share_gate', lambda: spaces.recheck_held(), ids['share_gate'])
    with store.db() as c:
        store.audit(c, 'temple_model_retry', 'Temple', 'temple_model', '; '.join(f'{TASKS[k][0]}: {v}' for k, v in out.items()))
    return {'status': 'done', 'results': out}


def _again(task, fn, ids):
    try:
        r = fn()
    except LocalModelHeld:
        return 'still waiting: the local model did not answer'
    except Exception as e:
        return f'did not finish: {str(e)[:160]}'
    if isinstance(r, dict) and r.get('status') in ('failed', 'busy'): return f"did not finish: {r.get('error') or r.get('status')}"
    with store.db() as c:
        _resolve(c, task, ids, 'tried again')
    return 'done'


# ---------------- what the Agents page shows ----------------
def recent(days=30):
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store.db() as c:
        rows = c.execute('SELECT task, place, model, fallback, outcome, count(*) AS n FROM temple_screenings WHERE at>=? '
                         'GROUP BY task, place, model, fallback, outcome ORDER BY n DESC', (since,)).fetchall()
    return [{'task': r['task'], 'label': TASKS.get(r['task'], (r['task'],))[0], 'place': r['place'], 'model': r['model'],
             'fallback': bool(r['fallback']), 'outcome': r['outcome'], 'count': r['n']} for r in rows]


def status(check=True):
    p, cm = cloud_model()
    ok, why = reachable() if check and configured() else (None, '' if configured() else 'not set up')
    ev = _setting('temple_model_eval', '')
    try: ev = json.loads(ev) if ev else None
    except ValueError: ev = None
    return {'choice': choice(), 'fallback': fallback(), 'configured': configured(), 'local_model': model(), 'local_url': url(),
            'reachable': ok, 'reachable_reason': why, 'cloud_model': cm, 'cloud_provider': p,
            'tasks': [{'task': k, 'label': v[0], 'agent': v[1]} for k, v in TASKS.items()],
            'held': {k: v for k, v in held().items() if k != 'rows'}, 'recent': recent(), 'evaluation': ev}


# ---------------- the evaluation: fixed, fictional examples ----------------
# Every name, address and number here is made up (07700 900xxx is Ofcom's range for drama). The answers are what a careful
# person would say: the sharing check should hold personal, special category or private details, and pass ordinary work.
SHARE_EXAMPLES = [
    ('Bid style', 'Bids lead with the outcome for the client, then the method and the team.', False),
    ('Cover for approvals', 'Priya Shah in Finance is off sick with depression until March, so route her approvals to Sam.', True),
    ('Day rates', 'Our standard day rates are reviewed every April by the bid board.', False),
    ('Contact details', 'My home address is 14 Larch Close, Fernley, and my mobile is 07700 900123.', True),
    ('Deadlines', 'Tom in delivery is going through a divorce, so go easy on his deadlines this month.', True),
    ('Tender portal', 'Fernley Council\'s procurement portal closes tenders at noon on Fridays.', False),
    ('Reminder', 'Personal: book the dentist for the children before half term.', True),
    ('House style', 'Use UK English and show amounts in GBP in every client document.', False),
]
CATEGORY_SET = [('Bids', 'How we write and price bids and proposals'), ('Delivery', 'Running projects for clients once won'),
                ('Finance', 'Invoicing, rates, budgets and payments'), ('Personal', 'Home and family life')]
CATEGORY_EXAMPLES = [
    ('e1', 'Proposal openings', 'Open every proposal with the client\'s outcome in one sentence.', 'Bids'),
    ('e2', 'Invoice terms', 'Invoices go out on the last working day of the month with 30-day terms.', 'Finance'),
    ('e3', 'Weekly client call', 'Project managers hold a 30-minute progress call with each client every Tuesday.', 'Delivery'),
    ('e4', 'School holidays', 'The children are off school for the October week; keep that week free.', 'Personal'),
    ('e5', 'Win themes', 'Pick three win themes before writing a bid and repeat them in the summary.', 'Bids'),
    ('e6', 'Change requests', 'Any change to agreed scope on a live project needs a written change request.', 'Delivery'),
]


def _share_verdict(reply, item):
    """True (hold) / False (clear) / None (unreadable): Temple's structured answer read exactly as the real sharing check reads it
    (spaces.findings_from: only a finding with a quoted passage holds)."""
    import spaces
    try: return bool(spaces.findings_from(reply, item)[0])
    except (ValueError, TypeError): return None


def _evaluate(place):
    """Score one model on the examples. place: 'cloud' or 'local'. Same prompts as the real work."""
    import assistants, spaces, temple_categorise, rules_engine
    res = {'place': place, 'model': model() if place == 'local' else cloud_model()[1], 'tasks': [], 'error': ''}
    provider = cloud_model()[0]

    def ask(system, user, max_tokens, task):
        rules_engine.check_outbound(user, 'Temple model evaluation', packs=False)
        if place == 'local': return local(system, user, max_tokens, task)[0]
        return assistants._call(provider, system, [{'role': 'user', 'content': user}], max_tokens=max_tokens, workload='Temple model evaluation')

    start, rows = time.monotonic(), []
    try:
        for title, text, want in SHARE_EXAMPLES:
            got = _share_verdict(ask(spaces.SCREEN_PROMPT, f'ITEM (memory or decision): {title}\n\n{text}', 600, 'share_gate'), f'{title}\n{text}')
            rows.append({'item': title, 'expected': 'hold' if want else 'clear', 'got': ('hold' if got else 'clear') if got is not None else 'unreadable',
                         'right': got is want})
        res['tasks'].append({'task': 'share_gate', 'label': TASKS['share_gate'][0], 'right': sum(r['right'] for r in rows), 'total': len(rows),
                             'seconds': round(time.monotonic() - start, 1), 'rows': rows})
        start = time.monotonic()
        payload = json.dumps({'categories': [{'name': n, 'description': d} for n, d in CATEGORY_SET],
                              'memories': [{'id': i, 'title': t, 'content': c} for i, t, c, _ in CATEGORY_EXAMPLES]}, ensure_ascii=False)
        raw = ask(temple_categorise.PROMPT, payload, 3000, 'categorise')
        try:
            got = {a.id: a.category for a in temple_categorise.Assignments.model_validate_json(
                raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()).assignments}
        except Exception:
            got = {}
        rows = [{'item': t, 'expected': want, 'got': got.get(i) or ('unreadable' if not got else 'none'), 'right': (got.get(i) or '').lower() == want.lower()}
                for i, t, _, want in CATEGORY_EXAMPLES]
        res['tasks'].append({'task': 'categorise', 'label': TASKS['categorise'][0], 'right': sum(r['right'] for r in rows), 'total': len(rows),
                             'seconds': round(time.monotonic() - start, 1), 'rows': rows})
    except Unavailable as e:
        res['error'] = f'the local model did not answer ({e})'
    except Exception as e:
        import provider_errors
        res['error'] = provider_errors.message(e) if provider_errors.is_provider_error(e) else str(e)[:200]
    res['right'] = sum(t['right'] for t in res['tasks']); res['total'] = sum(t['total'] for t in res['tasks'])
    return res


def evaluate():
    import agents

    @agents.tracked('temple-model-eval', trigger='you asked')
    def run(manual=True):
        import rules_engine
        rules_engine.check_spend('automation')
        agents.note('read', 'evaluation', 'fixed fictional examples', f'{len(SHARE_EXAMPLES)} sharing checks, {len(CATEGORY_EXAMPLES)} categories')
        out = {'at': store.now(), 'running': False, 'results': [_evaluate('cloud')]}
        out['results'].append(_evaluate('local') if configured() else {'place': 'local', 'model': '', 'tasks': [], 'right': 0, 'total': 0,
                                                                       'error': 'no local model is set up (azure-setup.ps1 -Step localmodel)'})
        with store.db() as c:
            _put(c, 'temple_model_eval', json.dumps(out))
            store.audit(c, 'temple_model_eval', 'Temple', 'temple_model',
                        '; '.join(f"{r['place']} ({r['model'] or 'none'}): {r['right']}/{r['total']}" + (f" ({r['error']})" if r['error'] else '') for r in out['results']))
        return {'status': 'complete', 'cloud': f"{out['results'][0]['right']}/{out['results'][0]['total']}", 'local': f"{out['results'][1]['right']}/{out['results'][1]['total']}"}
    return run(manual=True)


def start_evaluation():
    """Runs in the background (a small model on CPU can take minutes); the Agents page polls status()."""
    ev = status(check=False)['evaluation'] or {}
    if ev.get('running'): raise ValueError('An evaluation is already running.')
    with store.db() as c:
        _put(c, 'temple_model_eval', json.dumps({**ev, 'running': True, 'started': store.now()}))

    def work():
        try: evaluate()
        except Exception as e:
            with store.db() as c:
                _put(c, 'temple_model_eval', json.dumps({**ev, 'running': False, 'error': str(e)[:200], 'at': store.now()}))
    store.spawn(work)
    return {'status': 'started'}
