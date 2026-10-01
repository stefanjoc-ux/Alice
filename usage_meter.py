"""Local token ledger. Estimates are not provider invoices or spending limits."""
import json
import sqlite3
import logging
import substrate_store as store
with store.db() as c:
    c.execute('''CREATE TABLE IF NOT EXISTS model_usage (
      id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,provider TEXT NOT NULL,
      model TEXT NOT NULL,workload TEXT NOT NULL,input_tokens INTEGER,output_tokens INTEGER,
      estimate_usd REAL,raw_usage TEXT NOT NULL)''')

def log(response,provider,model,workload,duration=None):
    usage=getattr(response,'usage',None)
    raw=usage.model_dump() if hasattr(usage,'model_dump') else (usage if isinstance(usage,dict) else {})
    raw=dict(raw or {})
    if duration is not None: raw['duration_s']=round(float(duration),2)   # how long the provider took to answer
    i=raw.get('input_tokens');o=raw.get('output_tokens');estimate=None
    details=raw.get('input_tokens_details') or {}
    reads=raw.get('cache_read_input_tokens',details.get('cached_tokens',0)) or 0
    writes=raw.get('cache_creation_input_tokens',details.get('cache_write_tokens',0)) or 0
    if isinstance(i,int) and isinstance(o,int):
        if model=='gpt-6-luna':
            # Missing write detail: conservatively price all non-read input as writes.
            w=details.get('cache_write_tokens')
            w=max(0,i-reads) if w is None else w
            estimate=((max(0,i-reads-w)*.10+reads*.01+w*.125)*(2 if i>272000 else 1)+o*.50*(1.5 if i>272000 else 1))/1000000
        elif model=='grok-4.7':
            estimate=(max(0,i-reads)*2+reads*.50+o*6)*(2 if i>=200000 else 1)/1000000
        elif model in ('claude-opus-5-5','claude-sonnet-5-5','claude-haiku-4-5-20251001'):
            rate={'claude-opus-5-5':4,'claude-sonnet-5-5':2}.get(model,1)
            hourly=(raw.get('cache_creation') or {}).get('ephemeral_1h_input_tokens',0) or 0
            estimate=(i*rate+reads*rate*.1+max(0,writes-hourly)*rate*1.25+hourly*rate*2+o*rate*5)/1000000
            i+=reads+writes  # Claude input_tokens excludes cached input.
    try:
        with store.db() as c:c.execute('INSERT INTO model_usage(created_at,provider,model,workload,input_tokens,output_tokens,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?,?,?)',
          (store.now(),provider,model,workload,i,o,estimate,json.dumps(raw)))
    except sqlite3.Error:
        logging.exception('Usage could not be saved; check provider billing for this call')
    try:
        import agents; agents.add_cost(estimate)    # the cost also lands on the agent run in progress, if any
    except Exception:
        pass

# USD per million tokens: input, cache read, cache write, output. Standard rates checked 2026-09-29.
RATES = {
    'gpt-6-luna': (0.10, 0.01, 0.125, 0.50),
    'grok-4.7': (2.00, 0.50, 2.00, 6.00),
    'claude-opus-5-5': (4.00, 0.40, 5.00, 20.00),
    'claude-sonnet-5-5': (2.00, 0.20, 2.50, 10.00),
    'claude-haiku-4-5-20251001': (1.00, 0.10, 1.25, 5.00),
}
SONNET = 'claude-sonnet-5-5'


def _since(period):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if period == '7d': return (now - timedelta(days=7)).isoformat()
    if period == '30d': return (now - timedelta(days=30)).isoformat()
    if period == 'month': return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    return ''


def _tokens(row):
    raw = json.loads(row['raw_usage'] or '{}')
    details = raw.get('input_tokens_details') or {}
    reads = raw.get('cache_read_input_tokens', details.get('cached_tokens', 0)) or 0
    writes = raw.get('cache_creation_input_tokens', details.get('cache_write_tokens', 0)) or 0
    return reads, writes


def _savings(rows):
    """Estimated savings from measurable optimisations. Estimates, not invoices."""
    cache = cache_premium = routed_actual = routed_sonnet = classifier = 0.0
    routed_calls = 0
    for r in rows:
        rate = RATES.get(r['model'])
        if not rate or r['input_tokens'] is None: continue
        reads, writes = _tokens(r)
        cache += reads * (rate[0] - rate[1]) / 1e6
        if r['provider'] == 'claude':  # Claude charges a premium to write the cache.
            cache_premium += writes * (rate[2] - rate[0]) / 1e6
        if r['workload'] == 'Routing classifier':
            classifier += r['estimate_usd'] or 0
        if r['workload'] == 'chat · auto' and r['model'] != SONNET and r['estimate_usd'] is not None:
            s = RATES[SONNET]
            uncached = max(0, r['input_tokens'] - reads)
            routed_sonnet += (uncached * s[0] + reads * s[1] + (r['output_tokens'] or 0) * s[3]) / 1e6
            routed_actual += r['estimate_usd']
            routed_calls += 1
    routing_gross = routed_sonnet - routed_actual
    return [
        {'name': 'Prompt caching', 'status': 'Active',
         'detail': 'Repeated history, instructions and tool definitions billed at cache-read rates. Net of Claude cache-write premiums.',
         'saving': cache - cache_premium},
        {'name': 'Auto routing', 'status': 'Active' if routed_calls else 'No Auto calls yet',
         'detail': f'{routed_calls} Auto calls answered by a cheaper model instead of Sonnet 5.5, net of classifier cost. '
                   'Assumes Sonnet would use the same tokens; failed attempts that were retried count as routed.',
         'saving': routing_gross - classifier},
        {'name': 'Classifier only when rules cannot decide', 'status': 'Active',
         'detail': 'Python rules route most messages free; Haiku is called only for ambiguous asks. Cost already deducted above.',
         'saving': None},
        {'name': 'Images not resent between tool rounds', 'status': 'Active',
         'detail': 'Generated image data is replaced with a short note before the next round. Not measurable after the fact.',
         'saving': None},
        {'name': 'Images only when ticked', 'status': 'Active',
         'detail': 'The image tool is sent only when Generate images is ticked, so models cannot create unrequested images.',
         'saving': None},
    ]


def summary(period='30d'):
    since = _since(period)
    where, args = ('WHERE created_at>=?', (since,)) if since else ('', ())
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM model_usage ' + where + ' ORDER BY id', args)]
    groups = {}
    days = {}
    for r in rows:
        reads, writes = _tokens(r)
        g = groups.setdefault((r['provider'], r['model'], r['workload']), {
            'provider': r['provider'], 'model': r['model'], 'workload': r['workload'], 'calls': 0,
            'input_tokens': 0, 'cache_read_tokens': 0, 'cache_write_tokens': 0, 'output_tokens': 0,
            'estimate_usd': 0.0, 'unpriced_calls': 0, 'images': 0, 'characters': 0, '_times': []})
        g['calls'] += 1
        g['input_tokens'] += r['input_tokens'] or 0
        g['output_tokens'] += r['output_tokens'] or 0
        g['cache_read_tokens'] += reads
        g['cache_write_tokens'] += writes
        took = json.loads(r['raw_usage'] or '{}').get('duration_s')
        if took is not None: g['_times'].append(took)
        if r['provider'] == 'elevenlabs':
            g['characters'] += json.loads(r['raw_usage'] or '{}').get('characters', 0)
        if r['workload'] == 'Image generation':
            g['images'] += json.loads(r['raw_usage'] or '{}').get('images', 0)
        if r['estimate_usd'] is None: g['unpriced_calls'] += 1
        else: g['estimate_usd'] += r['estimate_usd']
        d = days.setdefault(r['created_at'][:10], {'date': r['created_at'][:10], 'calls': 0, 'estimate_usd': 0.0})
        d['calls'] += 1
        d['estimate_usd'] += r['estimate_usd'] or 0
    for g in groups.values():
        times = g.pop('_times')
        g['avg_seconds'] = round(sum(times) / len(times), 1) if times else None
        g['max_seconds'] = round(max(times), 1) if times else None
    groups = sorted(groups.values(), key=lambda g: g['estimate_usd'], reverse=True)
    savings = _savings(rows)
    spent = sum(g['estimate_usd'] for g in groups)
    saved = sum(s['saving'] for s in savings if s['saving'])
    recent = [{**{k: r[k] for k in ('created_at', 'provider', 'model', 'workload', 'input_tokens', 'output_tokens', 'estimate_usd')},
               'seconds': json.loads(r['raw_usage'] or '{}').get('duration_s')} for r in reversed(rows[-50:])]
    return {'period': period, 'groups': groups, 'days': sorted(days.values(), key=lambda d: d['date'], reverse=True),
            'recent': recent, 'savings': savings,
            'totals': {'calls': len(rows), 'estimate_usd': spent, 'saved_usd': saved, 'without_usd': spent + saved,
                       'unpriced_calls': sum(g['unpriced_calls'] for g in groups),
                       'images': sum(g['images'] for g in groups)},
            'rate_date': '2026-09-29'}

# USD per generated image. Grok: xAI Imagine 2.0 at 1K "low" quality, which the Sept 2026 rate card lists
# as the auto default. Override in .env if your xAI bill shows otherwise. OpenAI stays unpriced until set.
def image_rate(provider):
    import os
    key = {'grok': 'IMAGE_PRICE_GROK', 'openai': 'IMAGE_PRICE_OPENAI'}.get(provider)
    default = {'grok': '0.04'}.get(provider, '')
    try: return float(os.getenv(key, default)) if key and os.getenv(key, default) else None
    except ValueError: return None


def log_images(provider,model,count):
    """Image generation is billed per image, separately from text tokens."""
    if not count:return
    rate=image_rate(provider)
    try:
        with store.db() as c:c.execute('INSERT INTO model_usage(created_at,provider,model,workload,input_tokens,output_tokens,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?,?,?)',
          (store.now(),provider,model,'Image generation',None,None,count*rate if rate is not None else None,json.dumps({'images':count,'rate_per_image':rate})))
    except sqlite3.Error:
        logging.exception('Image usage could not be saved; check provider billing')


def _backfill_images():
    """Price image rows logged before a rate existed. Never changes rows that already have a price."""
    for provider in ('grok', 'openai'):
        rate = image_rate(provider)
        if rate is None: continue
        with store.db() as c:
            for row in c.execute("SELECT id,raw_usage FROM model_usage WHERE workload='Image generation' AND provider=? AND estimate_usd IS NULL", (provider,)).fetchall():
                count = json.loads(row['raw_usage'] or '{}').get('images', 0)
                c.execute('UPDATE model_usage SET estimate_usd=? WHERE id=?', (count * rate, row['id']))


try: _backfill_images()
except Exception: logging.exception('Image price backfill skipped')


def log_voice(workload, model, raw):
    """ElevenLabs uses plan credits rather than per-token rates; logged unpriced with characters or bytes."""
    try:
        with store.db() as c:c.execute('INSERT INTO model_usage(created_at,provider,model,workload,input_tokens,output_tokens,estimate_usd,raw_usage) VALUES (?,?,?,?,?,?,?,?)',
          (store.now(),'elevenlabs',model,workload,None,None,None,json.dumps(raw)))
    except sqlite3.Error:
        logging.exception('Voice usage could not be saved')
