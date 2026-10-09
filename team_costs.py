"""What digital teams cost (Stefan, 8 Oct 2026).

Every model call made for a team (a member's turn on a job, Talk to the team) is recorded against the team, the member (role),
the job and the job's version, in `team_costs`, from the same figure usage_meter writes to the Usage ledger and agents adds to
the agent run (agents.COST_HOOKS), so team totals match Usage and the Agents page. Calls made before tracking began are never
split or guessed: they are shown as one figure, "before tracking began".

Costs are kept in US dollars (what the providers charge). Pounds are shown only at an exchange rate Stefan sets (setting
`usd_gbp_rate`), with the rate and the date it was set beside every figure; without one, figures stay in dollars and say so.
Alice never fetches or invents a rate. All arithmetic is here, in Decimal.

"Your figures" (optional, off by default, per member): a day rate Stefan enters for the human role and the days a job would take
(setting `team_staff:<team id>`), shown beside the AI cost. Never a market rate from Alice.
"""
import contextvars
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import agents
import substrate_store as store

PERIODS = [('7d', 'Last 7 days'), ('30d', 'Last 30 days'), ('quarter', 'This quarter'), ('12m', 'Last 12 months')]
RUN_RATE_MIN_DAYS = 7        # an annual run rate needs at least a week of tracked costs in the last 30 days
_scope = contextvars.ContextVar('alice_team_cost_scope', default=None)

with store.db() as c:
    c.execute('''CREATE TABLE IF NOT EXISTS team_costs (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, team_id TEXT NOT NULL,
        member_id TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT '', job_id TEXT NOT NULL DEFAULT '', job_version INTEGER NOT NULL DEFAULT 0,
        kind TEXT NOT NULL DEFAULT 'job', agent_id TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '', usd REAL NOT NULL DEFAULT 0)''')
    c.execute('CREATE INDEX IF NOT EXISTS team_costs_team ON team_costs(team_id, at)')
    c.execute('CREATE INDEX IF NOT EXISTS team_costs_job ON team_costs(job_id)')
    # When tracking began in this database: costs from before it are shown as "before tracking began", never split.
    c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO NOTHING', ('team_costs_since', store.now()))


class scope:
    """Every model call made inside the block is recorded against this team, member, job and job version."""
    def __init__(self, team_id, member_id='', role='', job_id='', job_version=0, kind='job', agent_id=''):
        self.v = {'team_id': team_id, 'member_id': member_id or '', 'role': role or '', 'job_id': job_id or '',
                  'job_version': int(job_version or 0), 'kind': kind, 'agent_id': agent_id}

    def __enter__(self):
        self._tok = _scope.set(self.v)
        return self

    def __exit__(self, *a):
        _scope.reset(self._tok)
        return False


def _record(usd, provider, model, run_id):
    s = _scope.get()
    if s is None: return
    with store.db() as c:
        c.execute('INSERT INTO team_costs(at,team_id,member_id,role,job_id,job_version,kind,agent_id,run_id,provider,model,usd) '
                  'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (store.now(), s['team_id'], s['member_id'], s['role'][:80], s['job_id'], s['job_version'],
                                                       s['kind'], s['agent_id'], run_id or '', str(provider or '')[:40], str(model or '')[:80], float(usd or 0)))


agents.COST_HOOKS.append(_record)


# ---------------- settings: when tracking began, the exchange rate, your figures ----------------
def _setting(key):
    with store.db() as c:
        r = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return r[0] if r else None


def _put(c, key, value):
    c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))


def since():
    return _setting('team_costs_since') or store.now()


def _day(iso):
    try: d = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
    except ValueError: return str(iso)[:10]
    return f'{d.day} {d:%b %Y}'


def fx():
    """The exchange rate Stefan set (never fetched or invented): {rate, set_at, set_by, currency, note}."""
    try: v = json.loads(_setting('usd_gbp_rate') or 'null')
    except ValueError: v = None
    if isinstance(v, dict) and v.get('rate'):
        rate = Decimal(str(v['rate']))
        return {'rate': float(rate), 'set_at': v.get('set_at', ''), 'set_by': v.get('set_by', ''), 'currency': 'GBP',
                'note': f'at $1 = £{rate.normalize():f}, set {_day(v.get("set_at", ""))}'}
    return {'rate': None, 'set_at': '', 'set_by': '', 'currency': 'USD', 'note': 'in US dollars: no exchange rate set'}


def set_fx(rate):
    """Set (or, with None, clear) the dollar-to-pound rate used to show team costs in pounds. Logged with who and when."""
    with store.db() as c:
        if rate in (None, '', 0):
            c.execute("DELETE FROM settings WHERE key='usd_gbp_rate'")
            store.audit(c, 'team_costs_rate_set', 'usd_gbp_rate', 'human_control', 'Exchange rate cleared: team costs shown in US dollars')
            return fx()
        try: r = Decimal(str(rate)).quantize(Decimal('0.0001'), ROUND_HALF_UP)
        except Exception: raise ValueError('Give the rate as a number of pounds per dollar, e.g. 0.79.') from None
        if not Decimal('0.1') <= r <= Decimal('5'): raise ValueError('Give the rate as pounds per dollar, between 0.1 and 5 (e.g. 0.79).')
        _put(c, 'usd_gbp_rate', json.dumps({'rate': float(r), 'set_at': store.now(), 'set_by': store.actor()}))
        store.audit(c, 'team_costs_rate_set', 'usd_gbp_rate', 'human_control', f'Exchange rate for team costs set: $1 = £{r.normalize():f}')
    return fx()


def staff(tid):
    """Your figures for a team: {member id: {day_rate (GBP), days}}; empty unless you entered them."""
    try: v = json.loads(_setting('team_staff:' + tid) or '{}')
    except ValueError: v = {}
    return {k: x for k, x in v.items() if isinstance(x, dict) and x.get('day_rate') and x.get('days')} if isinstance(v, dict) else {}


def set_staff(tid, mid, on, day_rate=None, days=None):
    """Turn the comparison on for a member (your day rate for the human role, in pounds, and the days a job would take) or off."""
    import teams
    t = teams.get(tid)
    m = next((x for x in t['members'] if x['id'] == mid), None)
    if not m: raise ValueError('No such member in this team.')
    cur = staff(tid)
    if on:
        try: rate, n = Decimal(str(day_rate)), Decimal(str(days))
        except Exception: raise ValueError('Give a day rate in pounds and a number of days.') from None
        if not Decimal('0') < rate <= Decimal('100000'): raise ValueError('Give a day rate above £0, in pounds.')
        if not Decimal('0') < n <= Decimal('1000'): raise ValueError('Give the days a job would take, above 0.')
        cur[mid] = {'day_rate': float(rate.quantize(Decimal('0.01'), ROUND_HALF_UP)), 'days': float(n.quantize(Decimal('0.01'), ROUND_HALF_UP))}
        what = f'{t["name"]}: your figures for {m["role"]} set to £{cur[mid]["day_rate"]:,.2f} a day × {cur[mid]["days"]:g} days a job'
    else:
        cur.pop(mid, None)
        what = f'{t["name"]}: your figures for {m["role"]} removed'
    with store.db() as c:
        _put(c, 'team_staff:' + tid, json.dumps(cur))
        store.audit(c, 'team_staff_figures', tid, 'human_control', what)
    return staff(tid)


# ---------------- money ----------------
def _d(x):
    return Decimal(str(x or 0))


def _fmt(sym, v):
    """Money to the penny, rounded half up; a cost under a penny says so rather than showing 0.00."""
    if v == 0: return f'{sym}0.00'
    if abs(v) < Decimal('0.005'): return f'<{sym}0.01'
    q = abs(v).quantize(Decimal('0.01'), ROUND_HALF_UP)
    return f'{"-" if v < 0 else ""}{sym}{q:,.2f}'


def money(usd, f=None):
    """One figure: the dollars as recorded, pounds at the rate you set (or None), the text to show and the rate it was shown at."""
    f = f or fx()
    u = _d(usd)
    if f['rate']:
        g = (u * Decimal(str(f['rate']))).quantize(Decimal('0.01'), ROUND_HALF_UP)
        return {'usd': float(u), 'gbp': float(g), 'text': _fmt('£', u * Decimal(str(f['rate']))), 'note': f['note']}
    return {'usd': float(u), 'gbp': None, 'text': _fmt('$', u), 'note': f['note']}


def _gbp_text(v):
    return f'£{Decimal(str(v)):,.2f}'


def your_figures(fig, ai_usd=None, f=None):
    """Your figures for a member beside an AI cost: £ day rate × days. Never a rate from Alice."""
    if not fig: return None
    cost = (_d(fig['day_rate']) * _d(fig['days'])).quantize(Decimal('0.01'), ROUND_HALF_UP)
    out = {'label': 'Your figures', 'day_rate': fig['day_rate'], 'days': fig['days'], 'per_job_gbp': float(cost),
           'text': f'{_gbp_text(fig["day_rate"])} a day × {Decimal(str(fig["days"])).normalize():f} days = {_gbp_text(cost)} a job'}
    f = f or fx()
    if ai_usd is not None and not f['rate']:
        out['note'] = 'The AI cost is in US dollars: set an exchange rate to compare in pounds.'
    return out


# ---------------- periods ----------------
def periods(now=None):
    """[(key, label, start)] in UTC: the last 7 and 30 days, this calendar quarter, the last 12 months."""
    now = now or datetime.now(timezone.utc)
    q = datetime(now.year, 3 * ((now.month - 1) // 3) + 1, 1, tzinfo=timezone.utc)
    try: y = now.replace(year=now.year - 1)
    except ValueError: y = now.replace(year=now.year - 1, day=28)
    starts = {'7d': now - timedelta(days=7), '30d': now - timedelta(days=30), 'quarter': q, '12m': y}
    return [(k, l, starts[k]) for k, l in PERIODS]


def _periods_info(now, began):
    out = []
    for k, l, start in periods(now):
        out.append({'key': k, 'label': l, 'start': start.isoformat(),
                    'since': f'since {_day(began)}' if start.isoformat() < began else ''})
    return out


def _before(c, tid, began, jid=''):
    """What digital team work cost before tracking began (from the job steps and Talk to the team), as one figure."""
    if jid:
        s = c.execute('SELECT coalesce(sum(cost_usd),0) FROM team_steps WHERE job_id=? AND created_at<?', (jid, began)).fetchone()[0]
        m = c.execute("SELECT coalesce(sum(cost_usd),0) FROM team_messages WHERE job_id=? AND created_at<?", (jid, began)).fetchone()[0]
    else:
        s = c.execute('SELECT coalesce(sum(s.cost_usd),0) FROM team_steps s JOIN team_jobs j ON j.id=s.job_id WHERE j.team_id=? AND s.created_at<?',
                      (tid, began)).fetchone()[0]
        m = c.execute('SELECT coalesce(sum(cost_usd),0) FROM team_messages WHERE team_id=? AND created_at<?', (tid, began)).fetchone()[0]
    return _d(s) + _d(m)


def by_team(days=30, now=None):
    """Each team's tracked cost over the last `days` days (USD, Decimal), for the All teams page."""
    now = now or datetime.now(timezone.utc)
    vc, va = store.viewer_clause('team_job', 'team_costs.job_id')     # a person without the Owner role: their own jobs' costs only
    with store.db() as c:
        rows = c.execute('SELECT team_id, usd FROM team_costs WHERE at>=? AND at<=?' + vc, ((now - timedelta(days=days)).isoformat(), now.isoformat(), *va)).fetchall()
    out = {}
    for r in rows: out[r[0]] = out.get(r[0], Decimal('0')) + _d(r[1])
    return out


def board(tids, now=None):
    """The All teams page: each team's cost over the last 30 days and the total, at the rate you set."""
    f = fx()
    began = since()
    sums = by_team(30, now)
    per = {tid: money(sums.get(tid, Decimal('0')), f) for tid in tids}
    total = sum((sums.get(tid, Decimal('0')) for tid in tids), Decimal('0'))
    start = ((now or datetime.now(timezone.utc)) - timedelta(days=30)).isoformat()
    return {'teams': per, 'total': money(total, f), 'fx': f, 'label': 'Last 30 days',
            'since': f'since {_day(began)}' if start < began else '', 'since_iso': began}


def run_rate(cost30, now, began):
    """An annual run rate from the last 30 days, labelled Estimate; it needs a week of tracking (else None, with why)."""
    now = now or datetime.now(timezone.utc)
    try: b = datetime.fromisoformat(began.replace('Z', '+00:00'))
    except ValueError: b = now - timedelta(days=30)
    days = Decimal(str(max(0.0, min(30.0, (now - b).total_seconds() / 86400))))
    if days < RUN_RATE_MIN_DAYS:
        return None, f'An annual estimate needs {RUN_RATE_MIN_DAYS} days of tracked costs; tracking began {_day(began)}.'
    return cost30 * Decimal('365') / days, ('from the last 30 days' if days >= 30 else f'from the {int(days)} days tracked since {_day(began)}')


def _rows(tid, now):
    """The team's tracked costs up to now (a person without the Owner role: their own jobs' costs only)."""
    vc, va = store.viewer_clause('team_job', 'team_costs.job_id')
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT member_id, role, job_id, at, usd FROM team_costs WHERE team_id=? AND at<=?' + vc, (tid, now.isoformat(), *va))]


def team(tid, now=None):
    """A team's running cost: each member over the four periods, the team total, the annual run rate (Estimate), the cost of each
    job, your figures where entered, and what was spent before tracking began."""
    import teams
    t = teams.get(tid)
    now = now or datetime.now(timezone.utc)
    f, began = fx(), since()
    ps = periods(now)
    mine = store.restricted() is not None
    rows = _rows(tid, now)
    with store.db() as c:
        before = Decimal('0') if mine else _before(c, tid, began)
        jb = {} if mine else {r[0]: _d(r[1]) for r in c.execute('SELECT s.job_id, sum(s.cost_usd) FROM team_steps s JOIN team_jobs j ON j.id=s.job_id '
                                                                 'WHERE j.team_id=? AND s.created_at<? GROUP BY s.job_id', (tid, began))}
        for r in ([] if mine else c.execute('SELECT job_id, sum(cost_usd) FROM team_messages WHERE team_id=? AND job_id<>? AND created_at<? GROUP BY job_id', (tid, '', began))):
            jb[r[0]] = jb.get(r[0], Decimal('0')) + _d(r[1])
    current = {m['id']: m['role'] for m in t['members']}
    order = [m['id'] for m in t['members']]
    sums, jobs_of, job_tot = {}, {}, {}
    for r in rows:
        mid = r['member_id'] or '_'
        sums.setdefault(mid, {k: Decimal('0') for k, _, _ in ps})
        for k, _, start in ps:
            if r['at'] >= start.isoformat(): sums[mid][k] += _d(r['usd'])
        if r['job_id']:
            job_tot[r['job_id']] = job_tot.get(r['job_id'], Decimal('0')) + _d(r['usd'])
            if r['at'] >= ps[3][2].isoformat(): jobs_of.setdefault(mid, set()).add(r['job_id'])
        if mid not in current and mid not in order: order.append(mid)
    roles = {r['member_id'] or '_': r['role'] for r in rows}
    figs = staff(tid)
    members, total = [], {k: Decimal('0') for k, _, _ in ps}
    for mid in order:
        s = sums.get(mid, {k: Decimal('0') for k, _, _ in ps})
        for k in total: total[k] += s[k]
        n = len(jobs_of.get(mid, ()))
        year = s['12m']
        per_job = (year / n) if n else None
        members.append({'id': mid, 'role': current.get(mid) or roles.get(mid) or 'Unknown member', 'current': mid in current,
                        'costs': {k: money(v, f) for k, v in s.items()}, 'jobs': n, 'per_job': money(per_job, f) if per_job is not None else None,
                        'your_figures': your_figures(figs.get(mid), per_job, f) if mid in current else None})
    rr, rr_basis = run_rate(total['30d'], now, began)
    job_cost = {j: money(v + jb.get(j, Decimal('0')), f) for j, v in job_tot.items()}
    for j, v in jb.items():
        if j not in job_cost: job_cost[j] = money(v, f)
    return {'team_id': tid, 'fx': f, 'since': began, 'since_text': _day(began), 'periods': _periods_info(now, began), 'members': members,
            'total': {k: money(v, f) for k, v in total.items()},
            'run_rate': {'value': money(rr, f), 'label': 'Estimate', 'basis': rr_basis} if rr is not None else {'value': None, 'label': 'Estimate', 'basis': rr_basis},
            'before_tracking': money(before, f) if before else None, 'before_text': f'Before tracking began ({_day(began)})',
            'jobs': job_cost, 'staff_on': bool(figs)}


MEMBER_PERIODS = PERIODS + [('all', 'Since tracking began')]
TREND_WEEKS = 12             # the small trend line on each member's card: the last 12 weeks, week by week
LAST_JOBS = 10               # the member's last jobs, with what each cost, in its editor


def members(tid, now=None, base=None):
    """The Members tab (Stefan, 9 Oct 2026): for each member, the cost in every period (the Running cost card's four, plus since
    tracking began), its share of the team total, the jobs it worked on and the average per job in each period, the last 12 weeks
    week by week, and its last 10 jobs with what each cost. From the same rows as team(), so the figures agree with the Running cost
    card, Usage and the Agents page. `base` is team()'s result when the caller already has it (its rate and team total are used)."""
    now = now or datetime.now(timezone.utc)
    base = base or team(tid, now)
    f, began = base['fx'], base['since']
    rows = _rows(tid, now)
    starts = {k: st.isoformat() for k, _, st in periods(now)}
    starts['all'] = ''
    keys = [k for k, _ in MEMBER_PERIODS]
    week0 = now - timedelta(weeks=TREND_WEEKS)
    total = {k: Decimal('0') for k in keys}
    per = {}
    for r in rows:
        mid = r['member_id'] or '_'
        m = per.setdefault(mid, {'sums': {k: Decimal('0') for k in keys}, 'jobs': {k: set() for k in keys},
                                 'weeks': [Decimal('0')] * TREND_WEEKS, 'by_job': {}})
        usd = _d(r['usd'])
        for k in keys:
            if r['at'] >= starts[k]:
                m['sums'][k] += usd
                total[k] += usd
                if r['job_id']: m['jobs'][k].add(r['job_id'])
        try: at = datetime.fromisoformat(str(r['at']).replace('Z', '+00:00'))
        except ValueError: at = None
        if at is not None and at.tzinfo is None: at = at.replace(tzinfo=timezone.utc)
        if at is not None and week0 <= at <= now:
            m['weeks'][min(TREND_WEEKS - 1, int((at - week0).total_seconds() // (7 * 86400)))] += usd
        if r['job_id']:
            u, last = m['by_job'].get(r['job_id'], (Decimal('0'), ''))
            m['by_job'][r['job_id']] = (u + usd, max(last, str(r['at'])))
    ids = {j for m in per.values() for j in m['by_job']}
    titles = {}
    if ids:
        import teams
        with store.db() as c:
            for r in c.execute('SELECT id, title, status, created_at FROM team_jobs WHERE id IN (' + ','.join('?' * len(ids)) + ')', tuple(ids)):
                titles[r['id']] = {'ref': teams.ref(r['id']), 'title': r['title'], 'status': r['status'], 'created_at': r['created_at']}
    info = [{'key': k, 'label': f'{l} ({_day(began)})' if k == 'all' else l, 'start': starts[k],
             'since': '' if k == 'all' else (f'since {_day(began)}' if starts[k] < began else '')} for k, l in MEMBER_PERIODS]
    out = {}
    for mid, m in per.items():
        jobs = sorted(m['by_job'].items(), key=lambda kv: kv[1][1], reverse=True)[:LAST_JOBS]
        out[mid] = {'costs': {k: money(m['sums'][k], f) for k in keys},
                    'share_pct': {k: (float((m['sums'][k] / total[k] * 100).quantize(Decimal('0.1'), ROUND_HALF_UP)) if total[k] else None) for k in keys},
                    'jobs': {k: len(m['jobs'][k]) for k in keys},
                    'per_job': {k: (money(m['sums'][k] / len(m['jobs'][k]), f) if m['jobs'][k] else None) for k in keys},
                    'trend': [{'start': (week0 + timedelta(weeks=i)).isoformat(), **money(v, f)} for i, v in enumerate(m['weeks'])],
                    'last_jobs': [{'job_id': j, **titles.get(j, {'ref': '', 'title': 'A job you cannot see', 'status': '', 'created_at': ''}),
                                   'cost': money(u, f), 'at': at} for j, (u, at) in jobs if j in titles]}
    empty = {'costs': {k: money(0, f) for k in keys}, 'share_pct': {k: (0.0 if total[k] else None) for k in keys}, 'jobs': {k: 0 for k in keys},
             'per_job': {k: None for k in keys}, 'trend': [{'start': (week0 + timedelta(weeks=i)).isoformat(), **money(0, f)} for i in range(TREND_WEEKS)],
             'last_jobs': []}
    import teams
    current = [m['id'] for m in teams.get(tid)['members']]
    return {'fx': f, 'since': began, 'since_text': _day(began), 'periods': info, 'total': {k: money(v, f) for k, v in total.items()},
            'members': {mid: out.get(mid, empty) for mid in current},
            'former': {k: money(sum((per[mid]['sums'][k] for mid in per if mid not in current), Decimal('0')), f) for k in keys}}


def job(jid):
    """One job: its total, each member's share and each version's cost (tracked), and anything spent before tracking began."""
    import teams
    j = teams._row(jid)
    f, began = fx(), since()
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT member_id, role, job_version, usd FROM team_costs WHERE job_id=?', (jid,))]
        before = _before(c, j['team_id'], began, jid)
    try: current = {m['id']: m['role'] for m in teams.get(j['team_id'], j['team_version'])['members']}
    except ValueError: current = {}
    mem, ver = {}, {}
    for r in rows:
        mid = r['member_id'] or '_'
        mem[mid] = mem.get(mid, Decimal('0')) + _d(r['usd'])
        ver[r['job_version'] or 1] = ver.get(r['job_version'] or 1, Decimal('0')) + _d(r['usd'])
    roles = {r['member_id'] or '_': r['role'] for r in rows}
    tracked = sum(mem.values(), Decimal('0'))
    figs = staff(j['team_id'])
    members = [{'id': mid, 'role': current.get(mid) or roles.get(mid) or 'Unknown member', 'cost': money(v, f),
                'share_pct': float((v / tracked * 100).quantize(Decimal('0.1'), ROUND_HALF_UP)) if tracked else 0.0,
                'your_figures': your_figures(figs.get(mid), v, f)} for mid, v in sorted(mem.items(), key=lambda kv: -kv[1])]
    return {'fx': f, 'total': money(tracked + before, f), 'tracked': money(tracked, f), 'members': members,
            'versions': {int(v): money(x, f) for v, x in ver.items()},
            'before_tracking': money(before, f) if before else None, 'before_text': f'Before tracking began ({_day(began)})', 'since': began}


def describe_for_temple(tid='', jid=''):
    """For Ask Temple: the same figures and labels as the pages (team or job; with neither, every team's last 30 days)."""
    import teams
    if jid:
        j = teams._row(jid)
        x = job(jid)
        return {'job': f'{teams.ref(jid)} {j["title"]}', 'currency_note': x['fx']['note'], 'total': x['total']['text'],
                'members': [{'role': m['role'], 'cost': m['cost']['text'], 'share_pct': m['share_pct'],
                             **({'your_figures': m['your_figures']['text']} if m['your_figures'] else {})} for m in x['members']],
                'versions': {f'v{v}': m['text'] for v, m in sorted(x['versions'].items())},
                'before_tracking': x['before_tracking']['text'] if x['before_tracking'] else None, 'where': teams.job_url(j['team_id'], jid)}
    if tid:
        x = team(tid)
        labels = {p['key']: p['label'] + (f' ({p["since"]})' if p['since'] else '') for p in x['periods']}
        return {'team': teams.get(tid)['name'], 'currency_note': x['fx']['note'], 'tracking_began': x['since_text'],
                'members': [{'role': m['role'] + ('' if m['current'] else ' (no longer in the team)'), **{labels[k]: v['text'] for k, v in m['costs'].items()},
                             'average_per_job_last_12_months': m['per_job']['text'] if m['per_job'] else None,
                             **({'your_figures': m['your_figures']['text']} if m['your_figures'] else {})} for m in x['members']],
                'team_total': {labels[k]: v['text'] for k, v in x['total'].items()},
                'annual_run_rate': ({'Estimate': x['run_rate']['value']['text'], 'basis': x['run_rate']['basis']} if x['run_rate']['value']
                                    else {'Estimate': None, 'why': x['run_rate']['basis']}),
                'before_tracking': x['before_tracking']['text'] if x['before_tracking'] else None, 'where': teams.team_url(tid) + '#overview'}
    b = board([d['id'] for d in teams.listing()])
    names = {d['id']: d['name'] for d in teams.listing()}
    return {'period': b['label'] + (f' ({b["since"]})' if b['since'] else ''), 'currency_note': b['fx']['note'], 'total': b['total']['text'],
            'teams': [{'team': names[k], 'cost': v['text']} for k, v in sorted(b['teams'].items(), key=lambda kv: -kv[1]['usd'])], 'where': '/admin/teams'}
