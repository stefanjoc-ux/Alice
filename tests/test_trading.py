"""Trading desk: paper portfolios from a Trading 212 export, paper trades, "what if I had sold", algo signals (by hand, CSV
and the TradingView webhook), prices from a stand-in for Twelve Data, how each signal turned out, and the analysis.
Simulation only. All figures are fictional."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import substrate_store as s
import trading as T
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

def refused(label, fn):
    try: fn(); t(label, False)
    except ValueError: t(label, True)

# ---- prices: a stand-in for Twelve Data ----
DAYS = ['2026-09-%02d' % d for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 28, 29, 30)] + ['2026-10-01', '2026-10-02']
def bars(start, step, wobble=1.0):
    out = []
    for i, d in enumerate(DAYS):
        c = round(start + step * i, 2)
        out.append((d, c, c + wobble, c - wobble, c))
    return out
SERIES = {('ZZNV', ''): (bars(100, 1.0), 'USD'),          # rises £/day
          ('ZZQC', ''): (bars(200, -2.0), 'USD'),         # falls
          ('GBP/USD', ''): ([(d, 1.25, 1.25, 1.25, 1.25) for d in DAYS], '')}
CALLS = []
def fake_fetch(symbol, exchange='', outputsize=400):
    CALLS.append(symbol)
    if (symbol, exchange) not in SERIES: raise ValueError('**symbol** not found')
    b, ccy = SERIES[(symbol, exchange)]
    return list(reversed(b)), ccy
T.FETCH = fake_fetch

# ---- paper portfolio from a Trading 212 export ----
pf = T.create_portfolio('T212 Invest (paper)')['id']
CSV = ('Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency (Price / share),Exchange rate,Result,Currency (Result),Total,Currency (Total),ID\n'
       'Deposit,2026-08-30 09:00:00,,,,,,,,,,1000.00,GBP,D1\n'
       'Market buy,2026-09-01 15:00:00,US0000000001,ZZNV,Fictional Nvidia,4,100.00,USD,1.25,,,320.00,GBP,EOF1\n'
       'Market buy,2026-09-02 15:00:00,US0000000001,ZZNV,Fictional Nvidia,4,101.00,USD,1.25,,,323.20,GBP,EOF2\n'
       'Market buy,2026-09-01 15:05:00,US0000000002,ZZQC,Fictional Qualcomm,2,200.00,USD,1.25,,,320.00,GBP,EOF3\n'
       'Market sell,2026-09-03 16:00:00,US0000000001,ZZNV,Fictional Nvidia,2,102.00,USD,1.25,1.20,GBP,163.20,GBP,EOF4\n'
       'Dividend (Dividend),2026-09-04 10:00:00,US0000000002,ZZQC,Fictional Qualcomm,2,0.5,USD,,,,0.80,GBP,DV1\n')
r = T.import_t212(pf, 't212.csv', CSV)
t('T212 import: buys and sells become paper trades, deposits and dividends are counted but not traded', r == {'added': 4, 'skipped': 0, 'other': 2})
t('importing the same export again adds nothing', T.import_t212(pf, 't212.csv', CSV)['added'] == 0)
refused('a file that is not a T212 export is refused', lambda: T.import_t212(pf, 'x.csv', 'Name,Email\nA,b\n'))
v = T.portfolio_view(pf)
nv = next(p for p in v['positions'] if p['symbol'] == 'ZZNV')
t('average cost from T212\'s pound totals: 8 bought for £643.20, 2 sold, 6 left at £80.40', nv['qty'] == 6 and nv['avg_cost_gbp'] == 80.4 and nv['cost_gbp'] == 482.4)
t('realised profit on the sell: £163.20 less 2 × £80.40', v['totals']['realised_gbp'] == 2.4)
t('no prices yet: value waits rather than guesses', set(v['totals']['missing_prices']) == {'ZZNV', 'ZZQC'} and v['totals']['unrealised_gbp'] is None)

# ---- prices ----
t('the desk knows what it needs prices for, including the currency rate', set(T.needed_symbols()) >= {('ZZNV', ''), ('ZZQC', ''), ('GBP/USD', 'FX')})
T.refresh_prices(pause=0)
t('prices fetched and stored', T.latest_close('ZZNV')['close'] == 123.0 and abs(T.latest_fx('USD') - 0.8) < 1e-9)
n = len(CALLS); T.refresh_prices(pause=0)
t('a second refresh within 6 hours fetches nothing', len(CALLS) == n)
v = T.portfolio_view(pf)
nv = next(p for p in v['positions'] if p['symbol'] == 'ZZNV')
t('valued in pounds at the latest close and rate: 6 × $123 × 0.8 = £590.40', nv['value_gbp'] == 590.4 and nv['pl_gbp'] == 108.0)

hist = T.history(pf)
t('value over time: one point per trading day from the first trade, in pounds', hist[0]['day'] == '2026-09-01' and hist[-1]['day'] == '2026-10-02'
  and hist[-1]['value_gbp'] == round(6 * 123 * 0.8 + 2 * 154 * 0.8, 2) and hist[-1]['cost_gbp'] == 802.4)
t('a sell on a day lowers the holding from that day', next(h for h in hist if h['day'] == '2026-09-03')['cost_gbp'] == 802.4
  and next(h for h in hist if h['day'] == '2026-09-02')['cost_gbp'] == 963.2)
t('each holding carries its last 30 closes for a small chart', len(nv['spark']) == 24 and nv['spark'][-1] == 123.0)

# ---- paper trades ----
refused('cannot sell more than is held', lambda: T.add_trade(pf, 'ZZNV', 'sell', 50, 120))
refused('a nonsense ticker is refused', lambda: T.add_trade(pf, 'NOT A TICKER!', 'buy', 1, 1))
tr = T.add_trade(pf, 'ZZNV', 'sell', 1, 120)
t('a paper sell uses the latest rate when none is given', tr['total_gbp'] == 96.0)
with s.db() as c: t('paper trades are logged', c.execute("SELECT 1 FROM activity WHERE action='trading_paper_trade'").fetchone() is not None)

# ---- what if I had sold ----
sc = T.simulate_sell(pf, '2026-09-10', rebuy_date='2026-09-24')
leg = {l['symbol']: l for l in sc['legs']}
t('simulated sell at the close on that day', leg['ZZNV']['sell_price'] == 107.0 and leg['ZZQC']['sell_price'] == 186.0)
t('compared with holding: worth now, and which was ahead', sc['held_gbp'] == round(5 * 123 * 0.8 + 2 * 154 * 0.8, 2)
  and sc['selling_vs_holding_gbp'] == round(sc['proceeds_gbp'] - sc['held_gbp'], 2))
t('round trip: buy back with the proceeds, worth now', leg['ZZNV']['rebuy_price'] == 117.0 and sc['round_trip_gbp'] is not None)
refused('a buy-back date before the sell is refused', lambda: T.simulate_sell(pf, '2026-09-10', rebuy_date='2026-09-01'))
refused('one holding that is not held is refused', lambda: T.simulate_sell(pf, '2026-09-10', symbol='ZZZZ'))

# ---- signals by hand and CSV ----
b1 = T.add_signal('ZZNV', 'buy', 100, 'RayAlgo', '240', '2026-09-01T14:00:00Z')
s1 = T.add_signal('ZZQC', 'short', 200, 'RayAlgo', '240', '2026-09-01T14:00:00Z')
t('signals logged; "short" counts as a sell', b1['id'] and s1['side'] == 'sell')
t('the same signal twice is ignored', T.add_signal('ZZNV', 'buy', 100, 'RayAlgo', '240', '2026-09-01T14:00:00Z').get('duplicate'))
refused('a signal must be a buy or a sell', lambda: T.add_signal('ZZNV', 'maybe'))
ci = T.import_signals_csv('symbol,side,price,signal,timeframe,time\nZZNV,buy,110,RayAlgo,240,2026-09-11T14:00:00Z\nZZNV,sell,,Other,D,2026-09-29T20:00:00Z\nBAD TICKER!,buy,1,x,1,2026-09-01\n')
t('CSV import: good rows added, a bad one refused', ci == {'added': 2, 'duplicates': 0, 'refused': 1})

# ---- following signals forward ----
T.update_outcomes()
sig = {x['id']: x for x in T.signals()}
ob, os_ = sig[b1['id']]['outcome'], sig[s1['id']]['outcome']
t('buy signal: returns after 1, 5 and 20 trading days from the signal price', ob['returns']['1'] == 1.0 and ob['returns']['5'] == 5.0 and ob['returns']['20'] == 20.0)
t('sell signal: a falling price counts as going its way', os_['returns']['1'] == 1.0 and os_['returns']['20'] == 20.0)
t('best and worst move within 20 days, in the signal\'s direction', ob['best_pct'] == 21.0 and ob['worst_pct'] == 0.0 and ob['status'] == 'complete')
late = next(x for x in T.signals() if x['signal'] == 'Other')['outcome']
t('a recent signal is still being followed', late['status'] == 'following' and '20' not in late['returns'])

an = T.analysis('signal')
ray_buy = next(r for r in an['rows'] if r['group'] == 'RayAlgo · buy')
t('analysis: how often each signal went its way, average and median move per horizon (one up 1%, one down 0.9%)',
  ray_buy['signals'] == 2 and ray_buy['horizons']['1'] == {'n': 2, 'hit_pct': 50, 'avg': 0.04, 'median': 0.04})
t('analysis by ticker, timeframe and side', {r['group'] for r in T.analysis('symbol')['rows']} == {'ZZNV', 'ZZQC'}
  and {r['group'] for r in T.analysis('side')['rows']} == {'buy', 'sell'})
refused('analysis only by known groupings', lambda: T.analysis('colour'))

# ---- the TradingView webhook ----
TV = '52.89.214.238'
body = lambda **k: json.dumps({'symbol': 'ZZNV', 'exchange': 'NASDAQ', 'side': 'buy', 'signal': 'RayAlgo', 'timeframe': '240', 'price': 121, 'time': '2026-10-01T14:00:00Z', **k})
t('no token made yet: the webhook refuses everything', T.webhook(body(token='x'), TV)[0] == 503)
tok = T.new_webhook_token()['token']
t('the token is long and random', len(tok) >= 40)
t('wrong token refused', T.webhook(body(token='nope'), TV)[0] == 403)
t('from an address that is not TradingView\'s: refused and logged', T.webhook(body(token=tok), '203.0.113.9')[0] == 403)
with s.db() as c: t('refusals are logged', c.execute("SELECT 1 FROM activity WHERE action='trading_webhook_refused'").fetchone() is not None)
t('from TradingView with the right token: recorded', T.webhook(body(token=tok), TV) == (200, 'Recorded.'))
t('the same alert twice: ignored', T.webhook(body(token=tok), TV) == (200, 'Duplicate, ignored.'))
t('not JSON: refused with a reason', T.webhook('buy NVDA', TV)[0] == 400)
t('too large: refused', T.webhook(json.dumps({'token': tok, 'note': 'x' * 5000}), TV)[0] == 413)
t('an unknown side in a correct alert: refused', T.webhook(body(token=tok, side='hold', time='2026-10-01T15:00:00Z'), TV)[0] == 400)
wh = next(x for x in T.signals() if x['source'] == 'webhook')
t('webhook signals are marked as from TradingView, with the US exchange dropped', wh['symbol'] == 'ZZNV' and wh['exchange'] == '' and wh['timeframe'] == '240')
T._hits.clear()
codes = [T.webhook(body(token=tok, time=f'2026-10-02T{h:02d}:{m:02d}:00Z'), TV)[0] for h in range(2) for m in range(16)]
t('more than 30 alerts a minute: the rest are turned away', codes.count(429) == 2)
T._hits.clear()
T.set_ip_check(False)
t('with the address check off, any address with the right token is accepted', T.webhook(body(token=tok, time='2026-10-02T03:00:00Z'), '203.0.113.9')[0] == 200)
T.set_ip_check(True); T._hits.clear()

# the route: outside the admin token, decides the caller's address from the end of the forwarding chain
r = cl.post('/hooks/tradingview', content=body(token=tok, time='2026-10-02T04:00:00Z'), headers={'x-forwarded-for': f'{TV}, 81.2.69.160'})
t('webhook route: a faked TradingView address at the start of the chain does not help', r.status_code == 403)
r = cl.post('/hooks/tradingview', content=body(token=tok, time='2026-10-02T04:00:00Z'), headers={'x-forwarded-for': f'198.51.100.1, {TV}, 10.0.0.5'})
t('webhook route: the address Azure added is used (private hops ignored)', r.status_code == 200 and r.json()['detail'] == 'Recorded.')
t('webhook route: wrong token refused', cl.post('/hooks/tradingview', content=body(token='nope'), headers={'x-forwarded-for': TV}).status_code == 403)

# ---- the page and routes ----
t('Trading desk changes need the admin token', cl.post('/admin/api/trading/portfolios', json={'name': 'x'}).status_code == 403
  and cl.post('/admin/api/trading/webhook-token').status_code == 403)
t('page data', cl.get('/admin/api/trading').json()['webhook_ready'] is True and 'tp-sig' in cl.get('/admin/trading').text)
t('portfolio route', cl.get(f'/admin/api/trading/portfolios/{pf}').json()['scenarios'][0]['sell_date'] == '2026-09-10')
t('refreshing prices without a Twelve Data key says how to add one', cl.post('/admin/api/trading/prices/refresh', headers=H).status_code == 400)
t('signals route with the analysis', cl.get('/admin/api/trading/signals').json()['analysis']['rows'])
t('a paper trade through the page', cl.post(f'/admin/api/trading/portfolios/{pf}/trades', headers=H, json={'symbol': 'ZZQC', 'side': 'buy', 'qty': 1, 'price': 150, 'ccy': 'USD'}).status_code == 200)
t('a bad paper trade through the page is refused with a reason', cl.post(f'/admin/api/trading/portfolios/{pf}/trades', headers=H, json={'symbol': 'ZZQC', 'side': 'sell', 'qty': 99, 'price': 150}).status_code == 400)
ap = next(a for a in cl.get('/admin/api/apps').json()['apps'] if a['id'] == 'trading')
t('Trading desk is listed under Apps with its figures', ap['name'] == 'Trading desk' and ap['summary']['stats'][1]['label'] == 'Signals logged')
import re
bicep = open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))), 'infra', 'main.bicep')).read()
t('the webhook is the only other address outside sign-in', re.search(r"excludedPaths: \['/healthz', '/signed-out', '/hooks/tradingview'\]", bicep) is not None)
