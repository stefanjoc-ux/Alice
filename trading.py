"""Trading desk: paper trading, a log of algo signals, and how those signals turned out. Simulation only.

Nothing here places, changes or cancels a real order, and nothing connects to a broker. Paper portfolios start from a
Trading 212 history export (or by hand); simulated trades and "what if I had sold" scenarios are tracked against simply
holding. Algo signals (RayAlgo on TradingView, and later the Market Watcher) arrive through the TradingView webhook or by
hand, and each one is followed forward with daily prices: the return after 1, 3, 5, 10 and 20 trading days in the
signal's direction, and the best and worst move within 20 days. The analysis describes what happened; it never says
what to do.

- Money: every amount is also kept in GBP. A trade stores its price, the price currency and the GBP per unit of that
  currency at the time (fx_gbp). GBX (pence, LSE) counts as GBP / 100.
- Positions are worked out from the trades (average cost, as UK pooling does); realised profit is proceeds minus the
  average cost of what was sold.
- Prices: Twelve Data (key ALICE_TWELVEDATA_KEY, from Key Vault), daily bars cached in tp_prices. The free plan allows
  8 calls a minute, so a refresh runs in the background and paces itself.
- The webhook (/hooks/tradingview) is the one address outside Microsoft sign-in, by the owner's decision (4 Oct 2026). It
  only records a signal. It needs the secret token inside the alert message (ALICE_TV_WEBHOOK_TOKEN), accepts at most
  4 KB, 30 alerts a minute, and (unless switched off) only TradingView's published sending addresses.
"""
import csv
import io
import json
import os
import re
import secrets
import statistics
import threading
import time
import urllib.parse
import urllib.request
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

import substrate_store as store

HORIZONS = (1, 3, 5, 10, 20)                 # trading days after the signal
EXCURSION_DAYS = 20
TV_IPS = ('52.89.214.238', '34.212.75.30', '54.218.53.128', '52.32.178.7')   # TradingView's published webhook senders
US_EXCHANGES = {'NASDAQ', 'NYSE', 'AMEX', 'NYSEARCA', 'BATS', 'CBOE', 'ARCA', 'OTC', ''}
SYMBOL = re.compile(r'^[A-Z0-9][A-Z0-9.\-]{0,14}$')
EXCH = re.compile(r'^[A-Z0-9_]{0,12}$')
TD_URL = 'https://api.twelvedata.com/time_series'


def _now(): return store.now()
def _clean(v, n=200): return ' '.join(str(v or '').split())[:n]


def _schema():
    with store.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS tp_portfolios (id TEXT PRIMARY KEY, name TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', "
                  "created_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS tp_trades (id TEXT PRIMARY KEY, portfolio_id TEXT NOT NULL, symbol TEXT NOT NULL, "
                  "exchange TEXT NOT NULL DEFAULT '', side TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL, "
                  "ccy TEXT NOT NULL DEFAULT 'USD', fx_gbp REAL NOT NULL DEFAULT 1, total_gbp REAL NOT NULL, fee_gbp REAL NOT NULL DEFAULT 0, "
                  "at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual', ext_id TEXT NOT NULL DEFAULT '', signal_id TEXT NOT NULL DEFAULT '', "
                  "note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
        c.execute('CREATE INDEX IF NOT EXISTS tp_trades_pf ON tp_trades(portfolio_id, at)')
        c.execute("CREATE TABLE IF NOT EXISTS tp_signals (id TEXT PRIMARY KEY, symbol TEXT NOT NULL, exchange TEXT NOT NULL DEFAULT '', "
                  "side TEXT NOT NULL, signal TEXT NOT NULL DEFAULT '', timeframe TEXT NOT NULL DEFAULT '', price REAL, "
                  "bar_time TEXT NOT NULL, received_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual', note TEXT NOT NULL DEFAULT '', "
                  "dedupe TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT '{}', outcome_at TEXT)")
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS tp_signals_dedupe ON tp_signals(dedupe)')
        c.execute("CREATE TABLE IF NOT EXISTS tp_scenarios (id TEXT PRIMARY KEY, portfolio_id TEXT NOT NULL, symbol TEXT NOT NULL DEFAULT '', "
                  "sell_date TEXT NOT NULL, rebuy_date TEXT, legs TEXT NOT NULL DEFAULT '[]', proceeds_gbp REAL NOT NULL DEFAULT 0, "
                  "note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS tp_prices (symbol TEXT NOT NULL, exchange TEXT NOT NULL DEFAULT '', day TEXT NOT NULL, "
                  "open REAL, high REAL, low REAL, close REAL NOT NULL, ccy TEXT NOT NULL DEFAULT '', PRIMARY KEY (symbol, exchange, day))")
        c.execute("CREATE TABLE IF NOT EXISTS tp_price_status (symbol TEXT NOT NULL, exchange TEXT NOT NULL DEFAULT '', checked_at TEXT, "
                  "error TEXT NOT NULL DEFAULT '', ccy TEXT NOT NULL DEFAULT '', PRIMARY KEY (symbol, exchange))")
        if 'kind' not in {r['name'] for r in c.execute('PRAGMA table_info(tp_portfolios)')}:   # paper (practice) or live (mirrors a real account)
            try: c.execute("ALTER TABLE tp_portfolios ADD COLUMN kind TEXT NOT NULL DEFAULT 'paper'")
            except sqlite3.OperationalError as e:      # web and mcp start together: the other one may have just added it
                if 'already exists' not in str(e) and 'duplicate column' not in str(e).lower(): raise
        c.execute("INSERT OR IGNORE INTO settings VALUES ('trading_tv_ip_check','true')")


_schema()


# ---------------- portfolios and trades ----------------
# A paper portfolio is practice: trades are recorded by hand or imported. A live portfolio mirrors a real Trading 212 account
# (decision 6 Oct 2026): it changes only by importing that account's history export, never by a trade typed here, and
# Alice never connects to the broker or places an order. "What if I had sold" scenarios work on both: they are simulations.
KINDS = ('paper', 'live')
LIVE_ONLY_IMPORT = ('This portfolio mirrors your real Trading 212 account, so it changes only when you import that account\'s '
                    'history. Record practice trades in a paper portfolio.')


def create_portfolio(name, note='', kind='paper'):
    name = _clean(name, 80)
    if kind not in KINDS: raise ValueError('A portfolio is paper or live.')
    if not name: raise ValueError('Give the portfolio a name.')
    pid = uuid.uuid4().hex[:12]
    with store.db() as c:
        c.execute('INSERT INTO tp_portfolios (id,name,note,created_at,kind) VALUES (?,?,?,?,?)', (pid, name, _clean(note, 300), _now(), kind))
        store.audit(c, 'trading_portfolio_created', pid, 'human_control', f'{name} ({kind})')
    return {'id': pid, 'name': name, 'kind': kind}


def set_kind(pid, kind):
    """Mark a portfolio live (a mirror of the real account) or paper. Live only when every trade in it came from an import."""
    if kind not in KINDS: raise ValueError('A portfolio is paper or live.')
    with store.db() as c:
        pf = _portfolio(c, pid)
        if kind == 'live':
            n = c.execute("SELECT count(*) FROM tp_trades WHERE portfolio_id=? AND source<>'import'", (pid,)).fetchone()[0]
            if n: raise ValueError(f'This portfolio has {n} trade(s) typed in by hand, so it is not a copy of your real account. '
                                   'Create a live portfolio and import your Trading 212 history into it.')
        if pf['kind'] == kind: return {'id': pid, 'kind': kind}
        c.execute('UPDATE tp_portfolios SET kind=? WHERE id=?', (kind, pid))
        store.audit(c, 'trading_portfolio_kind', pid, 'human_control', f'{pf["name"]}: {pf["kind"]} to {kind}')
    return {'id': pid, 'kind': kind}


def portfolios():
    with store.db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM tp_portfolios ORDER BY CASE kind WHEN 'live' THEN 0 ELSE 1 END, created_at")]


def _portfolio(c, pid):
    r = c.execute('SELECT * FROM tp_portfolios WHERE id=?', (pid,)).fetchone()
    if not r: raise ValueError('No such portfolio.')
    return dict(r)


def _sym(symbol, exchange=''):
    s, e = _clean(symbol, 20).upper(), _clean(exchange, 12).upper()
    if ':' in s and not e: e, s = s.split(':', 1)
    if not SYMBOL.match(s): raise ValueError(f'"{symbol}" does not look like a ticker.')
    if not EXCH.match(e): raise ValueError(f'"{exchange}" does not look like an exchange.')
    return s, ('' if e in US_EXCHANGES else e)


def _gbp_rate(ccy, fx=None):
    ccy = (ccy or 'USD').upper()
    if ccy == 'GBP': return 1.0
    if ccy == 'GBX': return 0.01
    if fx: return float(fx)
    rate = latest_fx(ccy)
    if not rate: raise ValueError(f'No {ccy} to GBP rate yet: refresh prices, or give the rate.')
    return rate


def add_trade(pid, symbol, side, qty, price, ccy='USD', fx_gbp=None, at=None, fee_gbp=0.0, note='', source='manual',
              exchange='', signal_id='', ext_id='', total_gbp=None, _c=None):
    side = (side or '').lower()
    if side not in ('buy', 'sell'): raise ValueError('A trade is a buy or a sell.')
    s, e = _sym(symbol, exchange)
    try: qty, price, fee = float(qty), float(price), float(fee_gbp or 0)
    except (TypeError, ValueError): raise ValueError('Quantity, price and fee must be numbers.') from None
    if not (qty > 0 and price > 0 and fee >= 0): raise ValueError('Quantity and price must be above zero.')
    ccy = _clean(ccy or 'USD', 3).upper()
    rate = _gbp_rate(ccy, fx_gbp)
    total = float(total_gbp) if total_gbp is not None else qty * price * rate
    at = at or _now()
    tid = uuid.uuid4().hex[:12]

    def write(c):
        pf = _portfolio(c, pid)
        if pf.get('kind') == 'live' and source != 'import': raise ValueError(LIVE_ONLY_IMPORT)
        if side == 'sell':
            held = _positions(c, pid).get((s, e), {}).get('qty', 0.0)
            if qty > held + 1e-9: raise ValueError(f'Only {held:g} {s} held in this portfolio.')
        c.execute('INSERT INTO tp_trades (id,portfolio_id,symbol,exchange,side,qty,price,ccy,fx_gbp,total_gbp,fee_gbp,at,source,ext_id,signal_id,note,created_at) '
                  'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (tid, pid, s, e, side, qty, price, ccy, rate, round(total, 2), fee, at, source, ext_id, signal_id, _clean(note, 300), _now()))
        if source != 'import':
            store.audit(c, 'trading_paper_trade', tid, 'human_control', f'Paper {side} {qty:g} {s} at {price:g} {ccy}')
    if _c is not None: write(_c)
    else:
        with store.db() as c: write(c)
    return {'id': tid, 'symbol': s, 'side': side, 'qty': qty, 'total_gbp': round(total, 2)}


def _positions(c, pid):
    """Average cost per holding, in GBP, from the trades in order; realised profit on sells."""
    pos = {}
    for t in c.execute('SELECT symbol,exchange,side,qty,total_gbp,fee_gbp,ccy FROM tp_trades WHERE portfolio_id=? ORDER BY at, created_at', (pid,)):
        p = pos.setdefault((t['symbol'], t['exchange']), {'qty': 0.0, 'cost_gbp': 0.0, 'realised_gbp': 0.0, 'ccy': t['ccy']})
        if t['side'] == 'buy':
            p['qty'] += t['qty']; p['cost_gbp'] += t['total_gbp'] + t['fee_gbp']
        else:
            avg = p['cost_gbp'] / p['qty'] if p['qty'] else 0.0
            p['realised_gbp'] += t['total_gbp'] - t['fee_gbp'] - avg * t['qty']
            p['cost_gbp'] -= avg * t['qty']; p['qty'] -= t['qty']
            if p['qty'] < 1e-9: p['qty'], p['cost_gbp'] = 0.0, 0.0
    return pos


def _fx_series(ccy):
    """GBP per unit of ccy by day (as of each day's latest rate)."""
    ccy = (ccy or 'USD').upper()
    if ccy in ('GBP', 'GBX'): return None
    return {b['day']: 1.0 / b['close'] for b in _bars('GBP/' + ccy, 'FX') if b['close']}


def history(pid, days=365):
    """The portfolio's value and cost in GBP for each trading day with prices, oldest first (up to `days`)."""
    with store.db() as c:
        _portfolio(c, pid)
        trades = [dict(r) for r in c.execute('SELECT symbol,exchange,side,qty,total_gbp,fee_gbp,ccy,at FROM tp_trades WHERE portfolio_id=? ORDER BY at, created_at', (pid,))]
    if not trades: return []
    syms = {(t['symbol'], t['exchange']): t['ccy'] for t in trades}
    closes = {k: {b['day']: b['close'] for b in _bars(*k)} for k in syms}
    fxs = {ccy: _fx_series(ccy) for ccy in set(syms.values())}
    all_days = sorted({d for v in closes.values() for d in v if d >= trades[0]['at'][:10]})[-days:]
    out, i, pos, last_px, last_fx = [], 0, {}, {}, {}
    # walk the days; apply each trade on its day (average cost, as in _positions)
    for d in all_days:
        while i < len(trades) and trades[i]['at'][:10] <= d:
            t = trades[i]; k = (t['symbol'], t['exchange']); p = pos.setdefault(k, [0.0, 0.0])
            if t['side'] == 'buy': p[0] += t['qty']; p[1] += t['total_gbp'] + t['fee_gbp']
            else:
                avg = p[1] / p[0] if p[0] else 0.0; p[1] -= avg * t['qty']; p[0] -= t['qty']
                if p[0] < 1e-9: p[0], p[1] = 0.0, 0.0
            i += 1
        value, cost, complete = 0.0, 0.0, True
        for k, (qty, cst) in pos.items():
            if qty <= 0: continue
            if d in closes[k]: last_px[k] = closes[k][d]
            ccy = syms[k].upper()
            if ccy in ('GBP', 'GBX'): rate = 1.0 if ccy == 'GBP' else 0.01
            else:
                fx = fxs.get(ccy) or {}
                if d in fx: last_fx[ccy] = fx[d]
                rate = last_fx.get(ccy)
            if k not in last_px or not rate: complete = False; continue
            value += qty * last_px[k] * rate; cost += cst
        if complete and cost: out.append({'day': d, 'value_gbp': round(value, 2), 'cost_gbp': round(cost, 2)})
    return out


def portfolio_view(pid):
    """Holdings with average cost, latest close, value and unrealised profit in GBP; totals."""
    with store.db() as c:
        pf = _portfolio(c, pid)
        pos = _positions(c, pid)
        trades = [dict(r) for r in c.execute('SELECT * FROM tp_trades WHERE portfolio_id=? ORDER BY at DESC, created_at DESC LIMIT 200', (pid,))]
    rows, value, cost, realised, missing = [], 0.0, 0.0, 0.0, []
    for (s, e), p in sorted(pos.items()):
        realised += p['realised_gbp']
        if p['qty'] <= 0: continue
        last = latest_close(s, e)
        rate = _rate_or_none(p['ccy'])
        val = (last['close'] * p['qty'] * rate) if (last and rate) else None
        if val is None: missing.append(s)
        else: value += val
        cost += p['cost_gbp']
        spark = [b['close'] for b in _bars(s, e)][-30:]
        rows.append({'spark': spark, 'symbol': s, 'exchange': e, 'qty': round(p['qty'], 6), 'ccy': p['ccy'], 'avg_cost_gbp': round(p['cost_gbp'] / p['qty'], 4),
                     'cost_gbp': round(p['cost_gbp'], 2), 'last': last['close'] if last else None, 'last_day': last['day'] if last else None,
                     'value_gbp': round(val, 2) if val is not None else None,
                     'pl_gbp': round(val - p['cost_gbp'], 2) if val is not None else None,
                     'pl_pct': round(100 * (val - p['cost_gbp']) / p['cost_gbp'], 1) if val is not None and p['cost_gbp'] else None})
    return {'portfolio': pf, 'positions': rows, 'trades': trades,
            'totals': {'value_gbp': round(value, 2), 'cost_gbp': round(cost, 2), 'unrealised_gbp': round(value - cost, 2) if not missing else None,
                       'realised_gbp': round(realised, 2), 'missing_prices': missing}}


# ---------------- Trading 212 history import ----------------
T212_BUY = ('market buy', 'limit buy', 'stop buy', 'stop limit buy')
T212_SELL = ('market sell', 'limit sell', 'stop sell', 'stop limit sell')


def import_t212(pid, name, text):
    """Trading 212 'Export history' CSV: buys and sells become the portfolio's trades (GBP totals as T212 reports them);
    deposits, dividends and interest are counted but not traded. Rows already imported (same T212 ID) are skipped."""
    import rules_engine
    rules_engine.check_file(text, name)
    rows = list(csv.DictReader(io.StringIO(text.lstrip('﻿'))))
    if not rows or 'Action' not in rows[0] or 'Ticker' not in rows[0]:
        raise ValueError('This does not look like a Trading 212 history export (it needs Action and Ticker columns).')
    def num(r, *keys):
        for k in keys:
            v = (r.get(k) or '').replace(',', '').strip()
            if v not in ('', 'Not available'):
                try: return float(v)
                except ValueError: pass
        return None
    added = skipped = other = 0
    with store.db() as c:
        _portfolio(c, pid)
        seen = {r[0] for r in c.execute("SELECT ext_id FROM tp_trades WHERE portfolio_id=? AND ext_id<>''", (pid,))}
        for r in sorted(rows, key=lambda r: r.get('Time') or ''):
            act = (r.get('Action') or '').strip().lower()
            if act not in T212_BUY + T212_SELL: other += 1; continue
            ext = (r.get('ID') or '').strip() or f"{r.get('Time')}|{r.get('Ticker')}|{r.get('No. of shares')}"
            if ext in seen: skipped += 1; continue
            qty, price = num(r, 'No. of shares'), num(r, 'Price / share')
            total = num(r, 'Total', 'Total (GBP)')
            ccy = (r.get('Currency (Price / share)') or 'USD').strip().upper()
            rate_t212 = num(r, 'Exchange rate')
            fx = (1.0 / rate_t212) if rate_t212 else None
            if ccy in ('GBP', 'GBX'): fx = None
            if not qty or not price: other += 1; continue
            try:
                add_trade(pid, r.get('Ticker'), 'buy' if act in T212_BUY else 'sell', qty, price, ccy, fx,
                          at=(r.get('Time') or '').strip().replace(' ', 'T') or _now(), source='import', ext_id=ext,
                          total_gbp=abs(total) if total is not None else None, note=_clean(r.get('Name'), 80), _c=c)
                seen.add(ext); added += 1
            except ValueError:
                other += 1
        store.audit(c, 'trading_t212_import', pid, 'human_control', f'{name}: {added} trades added, {skipped} already there, {other} other rows')
    return {'added': added, 'skipped': skipped, 'other': other}


# ---------------- signals ----------------
def add_signal(symbol, side, price=None, signal='', timeframe='', bar_time=None, exchange='', source='manual', note=''):
    side = (side or '').lower()
    side = {'long': 'buy', 'short': 'sell', 'bull': 'buy', 'bear': 'sell'}.get(side, side)
    if side not in ('buy', 'sell'): raise ValueError('A signal is a buy or a sell.')
    s, e = _sym(symbol, exchange)
    try: price = float(price) if price not in (None, '') else None
    except (TypeError, ValueError): raise ValueError('The price must be a number.') from None
    if price is not None and price <= 0: raise ValueError('The price must be above zero.')
    bt = _clean(bar_time, 40) or _now()
    try: bt = datetime.fromisoformat(bt.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat(timespec='seconds')
    except ValueError: raise ValueError('The signal time is not a date and time.') from None
    sig, tf = _clean(signal, 60) or 'Signal', _clean(timeframe, 12)
    dedupe = f'{s}|{e}|{side}|{sig.lower()}|{tf}|{bt[:16]}'
    sid = uuid.uuid4().hex[:12]
    with store.db() as c:
        if c.execute('SELECT 1 FROM tp_signals WHERE dedupe=?', (dedupe,)).fetchone():
            return {'id': None, 'duplicate': True}
        c.execute('INSERT INTO tp_signals (id,symbol,exchange,side,signal,timeframe,price,bar_time,received_at,source,note,dedupe) '
                  'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (sid, s, e, side, sig, tf, price, bt, _now(), source, _clean(note, 300), dedupe))
        store.audit(c, 'trading_signal_' + ('received' if source == 'webhook' else 'logged'), sid, 'information',
                    f'{sig} {side} {s}' + (f' {tf}' if tf else '') + (f' at {price:g}' if price else ''))
    return {'id': sid, 'symbol': s, 'side': side}


def signals(limit=200):
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM tp_signals ORDER BY bar_time DESC LIMIT ?', (limit,))]
    for r in rows: r['outcome'] = json.loads(r['outcome'] or '{}')
    return rows


def import_signals_csv(text, name='signals.csv'):
    """Signals by hand in bulk: columns symbol, side, price, signal, timeframe, time (and optionally exchange)."""
    import rules_engine
    rules_engine.check_file(text, name)
    rows = list(csv.DictReader(io.StringIO(text.lstrip('﻿'))))
    if not rows or not {'symbol', 'side'} <= {k.strip().lower() for k in rows[0]}:
        raise ValueError('The CSV needs at least symbol and side columns (plus price, signal, timeframe, time).')
    added = dup = bad = 0
    for r in rows:
        r = {k.strip().lower(): v for k, v in r.items() if k}
        try:
            out = add_signal(r.get('symbol'), r.get('side'), r.get('price'), r.get('signal'), r.get('timeframe'), r.get('time'),
                             r.get('exchange', ''), source='csv')
            if out.get('duplicate'): dup += 1
            else: added += 1
        except ValueError: bad += 1
    return {'added': added, 'duplicates': dup, 'refused': bad}


# ---------------- the TradingView webhook ----------------
_hits = []
_hits_lock = threading.Lock()


def webhook_token():
    """ALICE_TV_WEBHOOK_TOKEN if set, else the token made on the Trading desk page (kept in settings, never logged)."""
    env = (os.environ.get('ALICE_TV_WEBHOOK_TOKEN') or '').strip()
    if env: return env
    with store.db() as c:
        r = c.execute("SELECT value FROM settings WHERE key='trading_tv_token'").fetchone()
    return (r[0] if r else '').strip()


def new_webhook_token():
    """Make (or replace) the webhook token. Alerts using the old one stop being accepted."""
    if (os.environ.get('ALICE_TV_WEBHOOK_TOKEN') or '').strip():
        raise ValueError('The token is set in Azure (ALICE_TV_WEBHOOK_TOKEN); change it there.')
    tok = secrets.token_urlsafe(32)
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES ('trading_tv_token',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (tok,))
        store.audit(c, 'trading_webhook_token', 'settings', 'human_control', 'New TradingView webhook token made (old one no longer accepted)')
    return {'token': tok}


def webhook(body, client_ip=''):
    """One TradingView alert. Returns (status_code, message). Records a signal only; never anything else."""
    token = webhook_token()
    if len(token) < 32: return 503, 'The TradingView webhook is not set up.'
    with store.db() as c:
        ip_check = (c.execute("SELECT value FROM settings WHERE key='trading_tv_ip_check'").fetchone() or ['true'])[0] == 'true'
    if ip_check and client_ip not in TV_IPS:
        with store.db() as c:
            store.audit(c, 'trading_webhook_refused', 'webhook', 'blocked', f'from {client_ip or "unknown"}: not a TradingView sending address')
        return 403, 'Not accepted.'
    now = time.time()
    with _hits_lock:
        _hits[:] = [t for t in _hits if now - t < 60]
        if len(_hits) >= 30: return 429, 'Too many alerts this minute.'
        _hits.append(now)
    if len(body) > 4096: return 413, 'Alert too large.'
    try: data = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
    except (ValueError, UnicodeDecodeError): return 400, 'The alert message must be JSON (see the Trading desk set-up).'
    if not isinstance(data, dict): return 400, 'The alert message must be a JSON object.'
    if not secrets.compare_digest(str(data.get('token') or ''), token): return 403, 'Not accepted.'
    try:
        out = add_signal(data.get('symbol') or data.get('ticker'), data.get('side') or data.get('action'), data.get('price'),
                         data.get('signal') or 'TradingView alert', data.get('timeframe') or data.get('interval'),
                         data.get('time') or None, data.get('exchange') or '', source='webhook', note=data.get('note') or '')
    except ValueError as e:
        return 400, str(e)
    return 200, 'Duplicate, ignored.' if out.get('duplicate') else 'Recorded.'


def set_ip_check(on):
    with store.db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='trading_tv_ip_check'", ('true' if on else 'false',))
        store.audit(c, 'trading_webhook_ip_check', 'settings', 'human_control', 'on' if on else 'off')
    return {'ip_check': bool(on)}


# ---------------- prices (Twelve Data, daily bars) ----------------
def td_key():
    import keyvault
    return keyvault.get('ALICE_TWELVEDATA_KEY')


def _td_fetch(symbol, exchange='', outputsize=400):
    """Daily bars from Twelve Data: [(day, open, high, low, close)], currency. Raises ValueError with Twelve Data's message."""
    key = td_key()
    if not key: raise ValueError('No Twelve Data key: add the secret alice-twelvedata-key in Key Vault (Azure portal).')
    q = {'symbol': symbol, 'interval': '1day', 'outputsize': outputsize, 'apikey': key, 'format': 'JSON'}
    if exchange: q['exchange'] = exchange
    with urllib.request.urlopen(TD_URL + '?' + urllib.parse.urlencode(q), timeout=20) as r:
        d = json.loads(r.read().decode('utf-8'))
    if d.get('status') != 'ok': raise ValueError(str(d.get('message') or 'Twelve Data refused the request.')[:200])
    bars = []
    for v in d.get('values') or []:
        try: bars.append((v['datetime'][:10], float(v['open']), float(v['high']), float(v['low']), float(v['close'])))
        except (KeyError, TypeError, ValueError): continue
    return bars, ((d.get('meta') or {}).get('currency') or '').upper()


FETCH = _td_fetch           # replaced in tests


def store_bars(symbol, exchange, bars, ccy=''):
    with store.db() as c:
        for day, o, h, l, cl in bars:
            c.execute('INSERT INTO tp_prices (symbol,exchange,day,open,high,low,close,ccy) VALUES (?,?,?,?,?,?,?,?) '
                      'ON CONFLICT(symbol,exchange,day) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,'
                      'close=excluded.close,ccy=excluded.ccy', (symbol, exchange, day, o, h, l, cl, ccy))
        c.execute('INSERT INTO tp_price_status (symbol,exchange,checked_at,error,ccy) VALUES (?,?,?,?,?) ON CONFLICT(symbol,exchange) '
                  "DO UPDATE SET checked_at=excluded.checked_at,error='',ccy=excluded.ccy", (symbol, exchange, _now(), '', ccy))


def _bars(symbol, exchange, since='0000'):
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT day,open,high,low,close FROM tp_prices WHERE symbol=? AND exchange=? AND day>=? ORDER BY day',
                                           (symbol, exchange, since))]


def latest_close(symbol, exchange=''):
    with store.db() as c:
        r = c.execute('SELECT day, close FROM tp_prices WHERE symbol=? AND exchange=? ORDER BY day DESC LIMIT 1', (symbol, exchange)).fetchone()
    return dict(r) if r else None


def close_on(symbol, exchange, day):
    """The close on that day, or the last close before it (a weekend or holiday)."""
    with store.db() as c:
        r = c.execute('SELECT day, close FROM tp_prices WHERE symbol=? AND exchange=? AND day<=? ORDER BY day DESC LIMIT 1',
                      (symbol, exchange, day)).fetchone()
    return dict(r) if r else None


def latest_fx(ccy):
    """GBP per one unit of ccy, from the cached GBP/<ccy> daily close (e.g. GBP/USD 1.27 -> 0.787)."""
    r = latest_close('GBP/' + ccy.upper(), 'FX')
    return (1.0 / r['close']) if r and r['close'] else None


def _rate_or_none(ccy):
    try: return _gbp_rate(ccy)
    except ValueError: return None


def needed_symbols():
    """What the desk needs prices for: holdings, signals still being followed, scenarios, and the currencies involved."""
    out, ccys = set(), set()
    for p in portfolios():
        with store.db() as c:
            for (s, e), pos in _positions(c, p['id']).items():
                if pos['qty'] > 0: out.add((s, e)); ccys.add(pos['ccy'])
    with store.db() as c:
        for r in c.execute("SELECT DISTINCT symbol, exchange FROM tp_signals"): out.add((r[0], r[1]))
        for r in c.execute("SELECT legs FROM tp_scenarios"):
            for leg in json.loads(r[0] or '[]'): out.add((leg['symbol'], leg.get('exchange', ''))); ccys.add(leg.get('ccy', 'USD'))
    for ccy in ccys - {'GBP', 'GBX', ''}: out.add(('GBP/' + ccy, 'FX'))
    return sorted(out)


_refresh = {'running': False, 'done': 0, 'total': 0, 'errors': [], 'finished_at': None}


def refresh_prices(force=False, pause=8.0):
    """Fetch daily bars for everything needed, at most 8 a minute (Twelve Data's free plan). Symbols checked in the last
    6 hours are skipped unless force. Then follow every signal forward."""
    if _refresh['running']: return dict(_refresh)
    syms = needed_symbols()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    with store.db() as c:
        fresh = {(r[0], r[1]) for r in c.execute("SELECT symbol, exchange FROM tp_price_status WHERE checked_at>? AND error=''", (cutoff,))}
    todo = [s for s in syms if force or s not in fresh]
    _refresh.update(running=True, done=0, total=len(todo), errors=[], finished_at=None)
    try:
        for i, (s, e) in enumerate(todo):
            if i and pause: time.sleep(pause)
            try:
                bars, ccy = FETCH(s, '' if e == 'FX' else e)
                store_bars(s, e, bars, ccy)
            except Exception as err:   # one bad symbol never stops the rest
                msg = str(err)[:200]
                _refresh['errors'].append(f'{s}: {msg}')
                with store.db() as c:
                    c.execute('INSERT INTO tp_price_status (symbol,exchange,checked_at,error) VALUES (?,?,?,?) ON CONFLICT(symbol,exchange) '
                              'DO UPDATE SET checked_at=excluded.checked_at,error=excluded.error', (s, e, _now(), msg))
            _refresh['done'] = i + 1
        update_outcomes()
    finally:
        _refresh.update(running=False, finished_at=_now())
    return dict(_refresh)


def refresh_in_background(force=False):
    if _refresh['running']: return dict(_refresh)
    threading.Thread(target=refresh_prices, kwargs={'force': force}, daemon=True, name='trading-prices').start()
    return {**_refresh, 'running': True}


def refresh_status(): return dict(_refresh)


# ---------------- following signals forward ----------------
def outcome_for(sig):
    """Direction-adjusted returns (a sell signal 'worked' if the price fell) after each horizon in trading days, and the
    best and worst move within 20 trading days, measured from the signal price (or that day's close)."""
    day = sig['bar_time'][:10]
    bars = _bars(sig['symbol'], sig['exchange'], day)
    if not bars: return {'status': 'no_prices'}
    entry = sig['price'] or (bars[0]['close'] if bars[0]['day'] == day else None)
    if not entry: return {'status': 'no_prices'}
    after = [b for b in bars if b['day'] > day]
    d = 1 if sig['side'] == 'buy' else -1
    out = {'status': 'complete' if len(after) >= max(HORIZONS) else 'following', 'entry': entry, 'days_seen': len(after), 'returns': {}}
    for h in HORIZONS:
        if len(after) >= h: out['returns'][str(h)] = round(100 * d * (after[h - 1]['close'] - entry) / entry, 2)
    window = after[:EXCURSION_DAYS]
    if window:
        hi, lo = max(b['high'] or b['close'] for b in window), min(b['low'] or b['close'] for b in window)
        fav, adv = ((hi, lo) if d == 1 else (lo, hi))
        out['best_pct'] = round(100 * d * (fav - entry) / entry, 2)
        out['worst_pct'] = round(100 * d * (adv - entry) / entry, 2)
    return out


def update_outcomes():
    with store.db() as c:
        sigs = [dict(r) for r in c.execute("SELECT * FROM tp_signals")]
    for s in sigs:
        o = outcome_for(s)
        with store.db() as c:
            c.execute('UPDATE tp_signals SET outcome=?, outcome_at=? WHERE id=?', (json.dumps(o), _now(), s['id']))
    return len(sigs)


def analysis(group_by='signal'):
    """How the signals turned out, grouped (signal and side, symbol, timeframe or side). For each horizon: how many
    have a result, how often the move went the signal's way, the average and median move; and the average best and
    worst move within 20 days. Descriptive only."""
    keyf = {'signal': lambda s: f"{s['signal']} · {s['side']}", 'symbol': lambda s: s['symbol'],
            'timeframe': lambda s: s['timeframe'] or '(none)', 'side': lambda s: s['side']}.get(group_by)
    if not keyf: raise ValueError('Group by signal, symbol, timeframe or side.')
    groups = {}
    for s in signals(5000):
        groups.setdefault(keyf(s), []).append(s)
    out = []
    for k, ss in sorted(groups.items()):
        row = {'group': k, 'signals': len(ss), 'horizons': {}}
        for h in HORIZONS:
            vals = [s['outcome']['returns'][str(h)] for s in ss if str(h) in (s['outcome'].get('returns') or {})]
            if vals:
                row['horizons'][str(h)] = {'n': len(vals), 'hit_pct': round(100 * sum(v > 0 for v in vals) / len(vals)),
                                           'avg': round(statistics.fmean(vals), 2), 'median': round(statistics.median(vals), 2)}
        best = [s['outcome']['best_pct'] for s in ss if 'best_pct' in s['outcome']]
        worst = [s['outcome']['worst_pct'] for s in ss if 'worst_pct' in s['outcome']]
        row['avg_best'] = round(statistics.fmean(best), 2) if best else None
        row['avg_worst'] = round(statistics.fmean(worst), 2) if worst else None
        out.append(row)
    return {'group_by': group_by, 'horizons': list(HORIZONS), 'rows': out}


# ---------------- "what if I had sold" ----------------
def simulate_sell(pid, sell_date, symbol='', rebuy_date=None, note=''):
    """Sell the whole paper portfolio (or one holding) at the close on sell_date, on paper. Compared later with simply
    holding; with a rebuy date, also the round trip (sell, then buy back with the proceeds)."""
    try: sd = date.fromisoformat(sell_date).isoformat()
    except (TypeError, ValueError): raise ValueError('Give the sell date as YYYY-MM-DD.') from None
    rd = None
    if rebuy_date:
        try: rd = date.fromisoformat(rebuy_date).isoformat()
        except ValueError: raise ValueError('Give the buy-back date as YYYY-MM-DD.') from None
        if rd <= sd: raise ValueError('The buy-back date must be after the sell date.')
    with store.db() as c:
        _portfolio(c, pid)
        pos = {k: v for k, v in _positions(c, pid).items() if v['qty'] > 0}
    if symbol:
        s, e = _sym(symbol)
        pos = {k: v for k, v in pos.items() if k[0] == s}
        if not pos: raise ValueError(f'{s} is not held in this paper portfolio.')
    if not pos: raise ValueError('Nothing is held in this paper portfolio.')
    legs, proceeds, missing = [], 0.0, []
    for (s, e), p in sorted(pos.items()):
        px = close_on(s, e, sd)
        rate = _rate_or_none(p['ccy'])
        if not px or not rate: missing.append(s); continue
        g = p['qty'] * px['close'] * rate
        proceeds += g
        legs.append({'symbol': s, 'exchange': e, 'qty': p['qty'], 'ccy': p['ccy'], 'sell_price': px['close'], 'sell_day': px['day'], 'proceeds_gbp': round(g, 2)})
    if missing: raise ValueError('No price on that date yet for ' + ', '.join(missing) + ': refresh prices first.')
    sid = uuid.uuid4().hex[:12]
    with store.db() as c:
        c.execute('INSERT INTO tp_scenarios (id,portfolio_id,symbol,sell_date,rebuy_date,legs,proceeds_gbp,note,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                  (sid, pid, symbol.upper() if symbol else '', sd, rd, json.dumps(legs), round(proceeds, 2), _clean(note, 300), _now()))
        store.audit(c, 'trading_scenario', sid, 'human_control', f'Simulated sell of {symbol.upper() or "the whole portfolio"} on {sd}')
    return scenario(sid)


def scenario(sid):
    with store.db() as c:
        r = c.execute('SELECT * FROM tp_scenarios WHERE id=?', (sid,)).fetchone()
    if not r: raise ValueError('No such scenario.')
    sc = dict(r); legs = json.loads(sc['legs'])
    held, held_ok, rebuy, rebuy_ok = 0.0, True, 0.0, bool(sc['rebuy_date'])
    for leg in legs:
        last, rate = latest_close(leg['symbol'], leg['exchange']), _rate_or_none(leg['ccy'])
        if last and rate:
            leg['now_price'], leg['now_day'] = last['close'], last['day']
            leg['held_gbp'] = round(leg['qty'] * last['close'] * rate, 2); held += leg['held_gbp']
        else: held_ok = False
        if sc['rebuy_date']:
            rb = close_on(leg['symbol'], leg['exchange'], sc['rebuy_date'])
            if rb and last and rate:
                shares = leg['proceeds_gbp'] / (rb['close'] * rate)
                leg['rebuy_price'], leg['rebuy_qty'] = rb['close'], round(shares, 6)
                leg['round_trip_gbp'] = round(shares * last['close'] * rate, 2); rebuy += leg['round_trip_gbp']
            else: rebuy_ok = False
    sc['legs'] = legs
    sc['held_gbp'] = round(held, 2) if held_ok else None
    sc['round_trip_gbp'] = round(rebuy, 2) if rebuy_ok else None
    sc['selling_vs_holding_gbp'] = round(sc['proceeds_gbp'] - held, 2) if held_ok else None
    sc['round_trip_vs_holding_gbp'] = round(rebuy - held, 2) if (rebuy_ok and held_ok) else None
    return sc


def scenarios(pid=None):
    with store.db() as c:
        ids = [r[0] for r in c.execute('SELECT id FROM tp_scenarios ' + ('WHERE portfolio_id=? ' if pid else '') + 'ORDER BY created_at DESC',
                                       ((pid,) if pid else ()))]
    return [scenario(i) for i in ids]


# ---------------- the page ----------------
def overview():
    pfs = portfolios()
    with store.db() as c:
        n_sig = c.execute('SELECT count(*) FROM tp_signals').fetchone()[0]
        last_sig = c.execute('SELECT bar_time FROM tp_signals ORDER BY bar_time DESC LIMIT 1').fetchone()
        ip_check = (c.execute("SELECT value FROM settings WHERE key='trading_tv_ip_check'").fetchone() or ['true'])[0] == 'true'
        price_errors = [dict(r) for r in c.execute("SELECT symbol, exchange, error FROM tp_price_status WHERE error<>''")]
    return {'portfolios': pfs, 'signals': n_sig, 'last_signal': last_sig[0] if last_sig else None,
            'webhook_ready': len(webhook_token()) >= 32, 'ip_check': ip_check, 'prices_ready': bool(td_key()),
            'price_errors': price_errors, 'refresh': refresh_status(), 'horizons': list(HORIZONS)}


def tile():
    o = overview()
    totals = {}
    for p in sorted(o['portfolios'], key=lambda p: p.get('kind') != 'live'):   # live first
        try: totals[p.get('kind') or 'paper'] = totals.get(p.get('kind') or 'paper', 0.0) + portfolio_view(p['id'])['totals']['value_gbp']
        except ValueError: pass
    if not totals: totals['paper'] = 0.0
    stats = [{'label': ('Live' if k == 'live' else 'Paper') + ' portfolios value', 'value': f'£{v:,.0f}'} for k, v in totals.items()]
    return {'stats': stats + [{'label': 'Signals logged', 'value': str(o['signals'])}],
            'note': ('Last signal ' + o['last_signal'][:10]) if o['last_signal'] else 'No signals yet'}


def waiting():
    return []
