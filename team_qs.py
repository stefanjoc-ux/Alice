"""The quantity surveying team (Stefan, 7 Oct 2026): a digital team whose job type "Cost estimate" produces a cost plan.

Stages: Lead QS plans → Measurement Surveyor takes quantities off (each with its source; quantities from drawings are
approximate) → Cost Surveyor prices each item (a) from published rates found by web search, each citing the page and its date,
(b) else from Stefan's rate library, (c) else unpriced and flagged as an assumption, never invented; a regional factor only
when a sourced one is found → Lead QS assembles (assumptions, exclusions, risks) → Market Trends QS compares the rates with
past cost plans and team jobs held in Alice. All arithmetic (quantity × rate, subtotals, preliminaries, contingency, fees,
comparisons) is done here in code from the members' structured answers, never by a model.

Outputs: a Word cost plan and an Excel workbook, both marked DRAFT_MARK, plus the Market Trends report. A signed-off job is
saved to Knowledge with its rates in a machine-readable block (RATE | …) so later estimates can compare with it.
"""
import csv
import io
import json
import re
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import agents
import substrate_store as store
import teams

TEAM_ID = 'quantity-surveying'
DRAFT_MARK = 'Draft: AI-assisted, for review by a qualified quantity surveyor'
DEMO_DIR = Path(__file__).resolve().parent / 'demo_content' / 'teams' / 'community_hall'
SOURCE_LABELS = {'web': 'Published rate (web)', 'library': 'Your rate library', 'unpriced': 'Unpriced: flagged as an assumption'}
FACTOR_RANGE = (0.7, 1.4)

UNITS = {'m2': 'm2', 'm²': 'm2', 'sqm': 'm2', 'sq m': 'm2', 'square metre': 'm2', 'square metres': 'm2', 'm3': 'm3', 'm³': 'm3', 'cu m': 'm3',
         'cubic metre': 'm3', 'm': 'm', 'lm': 'm', 'metre': 'm', 'metres': 'm', 'linear metre': 'm', 'nr': 'nr', 'no': 'nr', 'no.': 'nr',
         'each': 'nr', 'ea': 'nr', 'item': 'item', 'sum': 'item', 'ls': 'item', 'lump sum': 'item', 'kg': 'kg', 't': 't', 'tonne': 't',
         'tonnes': 't', 'hr': 'hr', 'hour': 'hr', 'day': 'day'}


def unit_key(u):
    u = ' '.join(str(u or '').lower().replace('^2', '2').replace('^3', '3').split()).strip('. ')
    return UNITS.get(u, u)


def _num(v):
    try:
        x = float(str(v).replace(',', '').replace('£', '').strip())
        return x if x == x and x not in (float('inf'), float('-inf')) else None
    except (TypeError, ValueError):
        return None


def money(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def pct_change(now, past):
    """(now - past) / past as a percentage to one decimal place, in code."""
    return float(((Decimal(str(now)) - Decimal(str(past))) / Decimal(str(past)) * 100).quantize(Decimal('0.1'), ROUND_HALF_UP))


def _words(t):
    return {w for w in re.findall(r'[a-z0-9]+', str(t or '').lower()) if len(w) > 2 and w not in {'and', 'the', 'with', 'for', 'from', 'including'}}


def _score(a, b):
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / max(1, len(wa | wb)) if wa and wb else 0.0


# ---------------- the seeded team ----------------
MEMBERS = [
    {'id': 'lead-qs', 'role': 'Lead QS', 'provider': 'claude_sonnet',
     'purpose': 'Reads the brief, plans the job, hands out the work, reviews it and assembles the final cost plan.',
     'instructions': 'You lead a small quantity surveying team producing an early cost estimate (a cost plan) for a building project in the UK. '
                     'Plan the work by building elements (substructure, frame, upper floors, roof, external walls, windows and doors, internal walls, '
                     'finishes, fittings, services, external works). Name the documents each element comes from. When you assemble the cost plan, '
                     'state assumptions, exclusions and risks plainly; never calculate or restate totals yourself: Alice does the arithmetic. '
                     'Ask Stefan only when the brief leaves out something essential, such as what the building is for.'},
    {'id': 'measurement-surveyor', 'role': 'Measurement Surveyor', 'provider': 'claude_sonnet',
     'purpose': 'Takes quantities off the specification, schedules and drawings, each with its source.',
     'instructions': 'Take off quantities element by element in standard units (m2, m3, m, nr, item). Every quantity must name its source: the '
                     'document and page, or the schedule and line it came from. Quantities read or scaled from drawings are approximate and must be '
                     'marked as from a drawing. Do not guess a quantity that no document supports: leave it out and say so in your note.'},
    {'id': 'cost-surveyor', 'role': 'Cost Surveyor', 'provider': 'claude',
     'purpose': 'Prices each item from current market rates: published rates first, then Stefan\'s rate library, else unpriced.',
     'instructions': 'Price each measured item at current UK market rates. First look for published rates on the web and cite the exact page and '
                     'its date. Where you find no published rate, choose the closest row of Stefan\'s rate library by its id (same unit). Otherwise '
                     'leave the item unpriced: never invent a rate. If a location is given, look for a published regional adjustment factor and cite it; '
                     'if none is found, say national rates were used.'},
    {'id': 'market-trends-qs', 'role': 'Market Trends QS', 'provider': 'claude',
     'purpose': 'Compares the rates used with rates in past projects held in Alice.',
     'instructions': 'Match each rate used to comparable rates from past cost plans and team jobs held in Alice (same unit and the same kind of '
                     'work). Say plainly when there is nothing comparable. Do not calculate percentages: Alice does that.'},
]
STAGES = [
    {'key': 'plan', 'title': 'Plan the job', 'member': 'lead-qs', 'handler': 'qs_plan',
     'task': 'Read the brief and the documents; plan the estimate by element, say which documents to use and note the location.',
     'hands': 'The plan: elements to measure, documents to use, the location.', 'checks': ''},
    {'key': 'measure', 'title': 'Take off quantities', 'member': 'measurement-surveyor', 'handler': 'qs_measure',
     'task': 'Take off the quantities for each element in the plan.',
     'hands': 'A list of measured items with quantity, unit and source.',
     'checks': 'The plan lists the elements to measure and the documents to use.'},
    {'key': 'price', 'title': 'Price the items', 'member': 'cost-surveyor', 'handler': 'qs_price',
     'task': 'Price every measured item; apply a regional factor only when a sourced one is found.',
     'hands': 'Each item priced, with where its rate came from (web, rate library or unpriced).',
     'checks': 'Every item has a quantity, a unit and a source (document and page, or schedule line).'},
    {'key': 'assemble', 'title': 'Assemble the cost plan', 'member': 'lead-qs', 'handler': 'qs_assemble',
     'task': 'Review the priced items and write the assumptions, exclusions and risks for the cost plan.',
     'hands': 'The cost plan with assumptions, exclusions and risks.',
     'checks': 'Every item is priced from a cited web source, the rate library, or listed as unpriced.'},
    {'key': 'trends', 'title': 'Market trends report', 'member': 'market-trends-qs', 'handler': 'qs_trends',
     'task': 'Report how the rates used compare with rates in past projects held in Alice, with dates and sources.',
     'hands': 'The Market Trends report.', 'checks': 'The cost plan is complete, with assumptions, exclusions and risks.'},
]
SETTINGS = {'prelims_pct': 12.0, 'contingency_pct': 10.0, 'fees_pct': 10.0}


def seed():
    with store.db() as c:
        if c.execute('SELECT 1 FROM teams WHERE id=?', (TEAM_ID,)).fetchone(): return
    with store.acting('Alice', note='Seeded the Quantity surveying team'):
        _seed_team()


def _seed_team():
    teams.create('Quantity surveying', 'A small QS team that produces an early cost estimate (cost plan) from a brief, a specification, '
                 'schedules and drawings. Every rate has a source; the arithmetic is done by Alice.', 'approve', tid=TEAM_ID,
                 members=MEMBERS, settings=SETTINGS,
                 job_types=[{'id': 'cost-estimate', 'name': 'Cost estimate', 'finish': 'cost_estimate', 'client_facing': True,
                             'description': 'From brief to a draft cost plan (Word and Excel) and a Market Trends report.', 'stages': STAGES}])


# ---------------- rate library ----------------
HEADERS = {'description': ('description', 'item', 'desc', 'work'), 'unit': ('unit', 'units', 'uom'), 'rate': ('rate', 'price', 'cost', 'unit rate', 'gbp'),
           'code': ('code', 'ref', 'reference', 'id'), 'region': ('region', 'location', 'area'), 'as_of': ('as of', 'date', 'as_of', 'priced'),
           'source': ('source', 'from', 'project')}


def _rows_of(name, raw):
    ext = Path(name).suffix.lower()
    if ext in ('.xlsx', '.xlsm'):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
        return [['' if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
    if ext in ('.csv', '.txt'):
        return list(csv.reader(io.StringIO(raw.decode('utf-8-sig', 'replace'))))
    raise ValueError('Upload the rate library as a CSV or Excel file.')


def import_rates(tid, name, raw, label=''):
    """Add rows to the team's rate library (description, unit, rate; optional code, region, date, source). Checked first."""
    import rules_engine
    teams.get(tid)
    rows = _rows_of(name, raw)
    text = '\n'.join(','.join(r) for r in rows)
    rules_engine.check_file(text, name)
    head_at = next((i for i, r in enumerate(rows[:10]) if any(c.strip().lower() in HEADERS['description'] for c in r)), None)
    if head_at is None: raise ValueError('Alice could not find a header row with Description, Unit and Rate.')
    head = [c.strip().lower() for c in rows[head_at]]
    col = {k: next((i for i, h in enumerate(head) if h in names), None) for k, names in HEADERS.items()}
    if col['unit'] is None or col['rate'] is None: raise ValueError('The rate library needs Unit and Rate columns.')
    batch, added, skipped = uuid.uuid4().hex[:12], 0, 0
    label = teams._clean(label or name, 120)
    with store.db() as c:
        for r in rows[head_at + 1:head_at + 5001]:
            get = lambda k: (r[col[k]].strip() if col[k] is not None and col[k] < len(r) else '')
            desc, unit, rate = teams._clean(get('description'), 300), unit_key(get('unit')), _num(get('rate'))
            if not desc or not unit or rate is None or rate <= 0: skipped += 1 if any(x.strip() for x in r) else 0; continue
            c.execute('INSERT INTO team_rates(id,team_id,batch,batch_name,code,description,unit,rate,region,as_of,source,added_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      ('r' + uuid.uuid4().hex[:11], tid, batch, label, teams._clean(get('code'), 40), desc, unit, rate, teams._clean(get('region'), 60),
                       teams._clean(get('as_of'), 20), teams._clean(get('source'), 200) or label, store.now()))
            added += 1
        store.audit(c, 'team_rates_imported', tid, 'human_review', f'{label}: {added} rates added' + (f', {skipped} rows skipped' if skipped else ''))
    if not added: raise ValueError('No usable rows: each needs a description, a unit and a rate above zero.')
    return {'added': added, 'skipped': skipped, 'batch': batch}


def remove_rates(tid, batch):
    with store.db() as c:
        n = c.execute('DELETE FROM team_rates WHERE team_id=? AND batch=?', (tid, batch)).rowcount
        store.audit(c, 'team_rates_removed', tid, 'human_control', f'{n} rates removed from the rate library')
    return {'removed': n}


def library(tid):
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT id, code, description, unit, rate, region, as_of, source, batch_name FROM team_rates WHERE team_id=? ORDER BY description', (tid,))]


# ---------------- the stages ----------------
def _ask(job, member, ctx, stage, spec, extra='', include_docs=True):
    system = teams.member_prompt(member, stage, ctx) + '\nReturn JSON only, no prose, in exactly this shape:\n' + spec
    payload = teams.job_payload(job, member, ctx, include_docs=include_docs, extra=extra)
    return teams.parse_json(teams.call_model(member, job, system, payload), member['role'])


def _common(data):
    return {'accept': data.get('accept') is not False, 'reasons': [teams._clean(x, 400) for x in data.get('reasons') or []],
            'summary': teams._clean(data.get('summary'), 300), 'note': teams._block(data.get('note'), 1000),
            'questions': [teams._clean(q, 600) for q in data.get('questions') or [] if teams._clean(q, 600)]}


def qs_plan(job, stage, member, ctx):
    spec = ('{"plan": "how you will run the estimate", "elements": ["element names"], "documents": [{"name": "exact document name", "use": "what for"}], '
            '"location": "town or region of the site, if known", "assumptions": [], "summary": "one sentence", "note": "hand-off note to the Measurement Surveyor", '
            '"questions": []}')
    d = _ask(job, member, ctx, stage, spec)
    out = _common(d)
    loc = teams._clean(job.get('location') or d.get('location'), 120)
    out['output'] = {'plan': teams._block(d.get('plan'), 4000), 'elements': [teams._clean(x, 80) for x in d.get('elements') or [] if teams._clean(x, 80)][:30],
                     'documents': [{'name': teams._clean(x.get('name'), 120), 'use': teams._clean(x.get('use'), 200)} for x in d.get('documents') or [] if isinstance(x, dict)][:12],
                     'location': loc, 'assumptions': [teams._clean(x, 300) for x in d.get('assumptions') or []][:20]}
    out['accept'] = True
    return out


def qs_measure(job, stage, member, ctx):
    plan = (ctx['outputs'] or {}).get('plan') or {}
    if not ctx.get('must_accept') and not plan.get('elements'):
        return {'accept': False, 'reasons': ['The plan lists no elements to measure.'], 'summary': 'Sent the plan back: no elements to measure.'}
    spec = ('{"accept": true, "reasons": [], "items": [{"ref": "Q1", "element": "", "description": "", "quantity": 0, "unit": "m2|m3|m|nr|item", '
            '"source": {"document": "exact document name", "page": "page number if the document has pages", "line": "schedule line, e.g. Line 4"}, '
            '"from_drawing": false, "note": ""}], "summary": "one sentence", "note": "hand-off note to the Cost Surveyor", "questions": []}')
    d = _ask(job, member, ctx, stage, spec)
    out = _common(d)
    if not out['accept'] and not ctx.get('must_accept'): return out
    docs = {x['name'].lower(): x for x in teams._docs_in(job['id'])}
    items, rejected = [], []
    for n, it in enumerate(d.get('items') or [], 1):
        if not isinstance(it, dict): continue
        desc = teams._clean(it.get('description'), 300)
        q, unit = _num(it.get('quantity')), unit_key(it.get('unit'))
        src = it.get('source') if isinstance(it.get('source'), dict) else {}
        docname = teams._clean(src.get('document'), 120)
        doc = docs.get(docname.lower()) or next((x for k, x in docs.items() if Path(k).stem == Path(docname.lower()).stem), None)
        page, line = teams._clean(src.get('page'), 20), teams._clean(src.get('line'), 60)
        why = ('no description' if not desc else 'no quantity above zero' if not q or q <= 0 else 'no unit' if not unit
               else 'no source document' if not docname else f'“{docname}” is not one of this job\'s documents' if not doc
               else 'no page or schedule line' if not (page or line) else '')
        if why: rejected.append({'description': desc or '(none)', 'reason': why}); continue
        approx = bool(it.get('from_drawing')) or doc['kind'] == 'drawing'
        items.append({'ref': f'Q{len(items) + 1}', 'element': teams._clean(it.get('element'), 80) or 'General', 'description': desc,
                      'quantity': round(q, 3), 'unit': unit, 'approximate': approx,
                      'source': {'document': doc['name'], 'page': page, 'line': line},
                      'source_text': doc['name'] + (f', page {page}' if page else '') + (f', {line}' if line else ''), 'note': teams._clean(it.get('note'), 300)})
    out['output'] = {'items': items, 'rejected': rejected}
    out['accept'] = True
    out['summary'] = out['summary'] or f'{len(items)} items measured' + (f', {len(rejected)} left out without a source' if rejected else '')
    return out


def _library_candidates(tid, items):
    lib = library(tid)
    picks = {}
    for it in items:
        same = sorted(((_score(it['description'], r['description']), r) for r in lib if r['unit'] == it['unit']), key=lambda x: -x[0])
        for sc, r in same[:3]:
            if sc > 0: picks[r['id']] = r
    return lib, list(picks.values())


PRICE_PROMPT = '''{member}
Use web search to find CURRENT published UK construction rates (price books, cost data services, published tender price indices,
manufacturers' and suppliers' published prices). For each measured item give a rate per the item's unit, the exact URL of the page that
states it, the page title and the page's date. Where you find no published rate for an item, give the id of the closest row in Stefan's
RATE LIBRARY instead (same unit). Otherwise leave rate empty: never invent a rate. If a LOCATION is given, look for a published regional
adjustment factor (location factor) for it and cite it; if none is found, leave location_factor empty.
Return JSON only, no prose:
{{"accept": true, "reasons": [], "rates": [{{"ref": "Q1", "rate": 0, "unit": "", "source_url": "", "source_title": "", "source_date": "YYYY-MM-DD or YYYY-MM",
"library_id": "", "note": ""}}], "location_factor": {{"factor": 1.0, "region": "", "source_url": "", "source_title": "", "source_date": ""}},
"searches": ["the searches you ran"], "summary": "one sentence", "note": "hand-off note to the Lead QS", "questions": []}}'''


def _date_ok(s):
    s = teams._clean(s, 20)
    m = re.fullmatch(r'(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?', s)
    return s if m and '1990' <= m.group(1) and s[:10] <= date.today().isoformat() else ''


def qs_price(job, stage, member, ctx):
    import assistants, org_research, rules_engine, rule_packs
    items = ((ctx['outputs'] or {}).get('measure') or {}).get('items') or []
    if not items and not ctx.get('must_accept'):
        return {'accept': False, 'reasons': ['No measured items with a quantity, a unit and a source were handed on.'],
                'summary': 'Sent back: nothing measured with a source.'}
    plan = (ctx['outputs'] or {}).get('plan') or {}
    location = teams._clean(plan.get('location') or job.get('location'), 120)
    lib, cands = _library_candidates(job['team_id'], items)
    fam = assistants.family(member['provider'])
    fam = fam if fam in org_research.KEYS else 'claude'
    target = f'Digital team: {member["role"]}'
    query = (f'JOB: {job["title"]}\nLOCATION: {location or "not given (use national rates)"}\n'
             'MEASURED ITEMS (ref | element | description | quantity | unit)\n'
             + '\n'.join(f'{i["ref"]} | {i["element"]} | {i["description"]} | {i["quantity"]} | {i["unit"]}' for i in items)
             + '\n\nRATE LIBRARY (id | description | unit | region | as of)\n'
             + ('\n'.join(f'{r["id"]} | {r["description"]} | {r["unit"]} | {r["region"]} | {r["as_of"]}' for r in cands) or '(empty)')
             + ('\n\nFEEDBACK TO ACT ON\n' + json.dumps(ctx['feedback'], ensure_ascii=False) if ctx.get('feedback') else ''))

    def query_for(p):
        rules_engine.check_outbound(query, target, provider=p)
        return rule_packs.live_check(query, p, target, packs=member['packs'])['text'] if member.get('packs') else query
    rules_engine.check_spend('chat')
    prompt = PRICE_PROMPT.format(member=teams.member_prompt(member, stage, ctx))
    raw, seen, used, failures = org_research.search(prompt, query_for, fam, workload=target)
    d = teams.parse_json(raw, member['role'])
    out = _common(d)
    if not out['accept'] and not ctx.get('must_accept'): return out
    seen_norm = {org_research._norm_url(u): (u, t) for u, t in seen.items()}
    by_ref = {str(r.get('ref')): r for r in d.get('rates') or [] if isinstance(r, dict)}
    libmap = {r['id']: r for r in lib}
    priced, refused, cited = [], [], set()
    for it in items:
        r = by_ref.get(it['ref']) or {}
        row = dict(it)
        rate, url = _num(r.get('rate')), str(r.get('source_url') or '').strip()
        hit = seen_norm.get(org_research._norm_url(url)) if url else None
        when = _date_ok(r.get('source_date'))
        web_why = ('' if rate and rate > 0 and hit and when and unit_key(r.get('unit') or it['unit']) == it['unit'] else
                   'no rate' if not rate or rate <= 0 else 'no source page' if not url else
                   'its page was not among the pages the search returned' if not hit else 'no date for the source' if not when else 'a different unit')
        if url or rate:
            if web_why: refused.append({'ref': it['ref'], 'rate': rate, 'source_url': url, 'reason': web_why})
        if not web_why:
            row.update({'rate': round(rate, 2), 'rate_source': 'web', 'source_url': hit[0], 'source_title': teams._clean(r.get('source_title') or hit[1], 200),
                        'source_date': when, 'rate_note': teams._clean(r.get('note'), 300)})
            cited.add(hit[0]); priced.append(row); continue
        lr = libmap.get(str(r.get('library_id') or ''))
        how = 'chosen by the Cost Surveyor'
        if not (lr and lr['unit'] == it['unit']):
            best = max(((_score(it['description'], x['description']), x) for x in lib if x['unit'] == it['unit']), key=lambda x: x[0], default=(0, None))
            lr, how = (best[1], 'matched by Alice on description and unit') if best[0] >= 0.5 else (None, '')
        if lr:
            row.update({'rate': round(float(lr['rate']), 2), 'rate_source': 'library', 'library_row': {k: lr[k] for k in ('id', 'code', 'description', 'unit', 'rate', 'region', 'as_of', 'source')},
                        'source_title': lr['source'] or lr['batch_name'], 'source_date': lr['as_of'], 'rate_note': how})
            agents.note('read', 'team_rate', lr['id'], f'{member["role"]}: {it["ref"]}')
            priced.append(row); continue
        row.update({'rate': None, 'rate_source': 'unpriced', 'rate_note': 'No published rate with a source and date was found, and no rate library row matches.'})
        priced.append(row)
    lf = d.get('location_factor') if isinstance(d.get('location_factor'), dict) else {}
    f, furl = _num(lf.get('factor')), str(lf.get('source_url') or '').strip()
    fhit = seen_norm.get(org_research._norm_url(furl)) if furl else None
    if location and f and FACTOR_RANGE[0] <= f <= FACTOR_RANGE[1] and fhit and f != 1.0:
        loc = {'applied': True, 'factor': round(f, 3), 'region': teams._clean(lf.get('region') or location, 80), 'source_url': fhit[0],
               'source_title': teams._clean(lf.get('source_title') or fhit[1], 200), 'source_date': _date_ok(lf.get('source_date')),
               'note': f'Regional factor {round(f, 3)} for {teams._clean(lf.get("region") or location, 80)} applied, from {fhit[0]}.'}
        cited.add(fhit[0])
    else:
        loc = {'applied': False, 'factor': 1.0, 'region': location,
               'note': (f'National rates used: no sourced regional factor was found for {location}.' if location else 'No location given: national rates used.')}
        if f and f != 1.0: refused.append({'ref': 'location factor', 'rate': f, 'source_url': furl, 'reason': 'not applied: no source among the pages the search returned' if not fhit else 'outside a plausible range'})
    for u, t in seen.items():
        agents.note('read', 'web', u, ((t or '')[:160] + ' · ' if t else '') + ('cited' if u in cited else 'returned by the search, not cited'))
    searches = [{'provider': org_research.PROVIDER_NAMES.get(used, used), 'queries': [teams._clean(q, 200) for q in d.get('searches') or []][:12],
                 'sources': [{'url': u, 'title': (t or '')[:200], 'cited': u in cited} for u, t in seen.items()][:60],
                 'fallback': [x['text'] for x in failures]}]
    counts = {k: sum(1 for x in priced if x['rate_source'] == k) for k in SOURCE_LABELS}
    out['output'] = {'items': priced, 'location': loc, 'refused_rates': refused, 'searched_with': org_research.searched_with(used, failures)}
    out['searches'] = searches
    out['accept'] = True
    out['summary'] = out['summary'] or f'{counts["web"]} priced from the web, {counts["library"]} from your rate library, {counts["unpriced"]} unpriced'
    return out


def compute(items, factor=1.0, settings=None):
    """The cost plan's arithmetic, in code: quantity × rate × factor per line, subtotals per element, preliminaries,
    contingency and fees as percentages, the total. Money to the penny, rounded half up."""
    s = {**SETTINGS, **(settings or {})}
    f = Decimal(str(factor or 1))
    lines, elements = [], {}
    for it in items:
        if it.get('rate_source') == 'unpriced' or it.get('rate') is None: continue
        amount = money(Decimal(str(it['quantity'])) * Decimal(str(it['rate'])) * f)
        lines.append({'ref': it['ref'], 'element': it['element'], 'amount': float(amount)})
        elements[it['element']] = elements.get(it['element'], Decimal('0')) + amount
    construction = sum(elements.values(), Decimal('0'))
    prelims = money(construction * Decimal(str(s['prelims_pct'])) / 100)
    contingency = money((construction + prelims) * Decimal(str(s['contingency_pct'])) / 100)
    fees = money((construction + prelims + contingency) * Decimal(str(s['fees_pct'])) / 100)
    total = construction + prelims + contingency + fees
    return {'lines': lines, 'elements': [{'element': k, 'subtotal': float(v)} for k, v in elements.items()],
            'construction': float(construction), 'prelims': float(prelims), 'contingency': float(contingency), 'fees': float(fees),
            'total': float(total), 'factor': float(f), 'percentages': {k: s[k] for k in SETTINGS}}


def qs_assemble(job, stage, member, ctx):
    price = (ctx['outputs'] or {}).get('price') or {}
    items = price.get('items') or []
    if not ctx.get('must_accept'):
        bad = [i['ref'] for i in items if i.get('rate_source') not in SOURCE_LABELS or (i.get('rate_source') == 'web' and not (i.get('source_url') and i.get('source_date')))]
        if not items or bad:
            return {'accept': False, 'reasons': ['No priced items were handed on.'] if not items else
                    [f'Items {", ".join(bad)} have a rate without a cited web source, a rate library row or an unpriced flag.'], 'summary': 'Sent the pricing back.'}
    loc = price.get('location') or {}
    plan = compute(items, loc.get('factor', 1.0), ctx.get('settings'))
    view = [{'ref': i['ref'], 'element': i['element'], 'description': i['description'], 'quantity': i['quantity'], 'unit': i['unit'],
             'approximate': i.get('approximate'), 'rate_source': SOURCE_LABELS[i['rate_source']]} for i in items]
    extra = ('COST PLAN FIGURES (calculated by Alice; do not recalculate)\n' + json.dumps({'items': view, 'totals': {k: plan[k] for k in ('construction', 'prelims', 'contingency', 'fees', 'total')},
                                                                                           'location': loc.get('note')}, ensure_ascii=False))
    spec = ('{"accept": true, "reasons": [], "summary": "two or three sentences describing the estimate (no figures)", "assumptions": [], "exclusions": [], '
            '"risks": [{"risk": "", "mitigation": ""}], "note": "hand-off note to the Market Trends QS", "questions": []}')
    d = _ask(job, member, ctx, stage, spec, extra=extra, include_docs=False)
    out = _common(d)
    if not out['accept'] and not ctx.get('must_accept'): return out
    auto = [f'{i["ref"]} {i["description"]}: unpriced (no published rate with a source and date, and no rate library row); excluded from the total.' for i in items if i['rate_source'] == 'unpriced']
    auto += [f'{i["ref"]} {i["description"]}: quantity read from a drawing, approximate.' for i in items if i.get('approximate')]
    auto.append(loc.get('note') or 'National rates used.')
    out['output'] = {'cost_plan': plan, 'summary': teams._block(d.get('summary'), 1500),
                     'assumptions': auto + [teams._clean(x, 400) for x in d.get('assumptions') or [] if teams._clean(x, 400)][:30],
                     'exclusions': [teams._clean(x, 400) for x in d.get('exclusions') or [] if teams._clean(x, 400)][:30],
                     'risks': [{'risk': teams._clean(r.get('risk'), 300), 'mitigation': teams._clean(r.get('mitigation'), 300)} for r in d.get('risks') or [] if isinstance(r, dict) and r.get('risk')][:20]}
    if not out['output']['exclusions']: out['output']['exclusions'] = ['VAT.', 'Land, legal and planning costs.']
    out['accept'] = True
    out['summary'] = out['summary'] or f'Cost plan assembled: £{plan["total"]:,.2f} including preliminaries, contingency and fees'
    return out


# ---------------- history for Market Trends ----------------
RATE_LINE = re.compile(r'^RATE \| (?P<ref>[^|]*) \| (?P<desc>[^|]+) \| (?P<unit>[^|]+) \| (?P<rate>[\d.,]+) \| (?P<kind>[^|]*) \| (?P<src>[^|]*) \| (?P<date>[^|]*)$', re.M)


def history(job, member):
    """Past rates held in Alice: finished team jobs, and cost plans in Knowledge carrying a RATES USED block. Which clients' material
    counts follows the Rules page (teams.client_rule); Local only and items this model may not read are left out."""
    import assistants, clients, knowledge
    fam = assistants.family(member['provider'])
    out, seen_k = [], set()
    keep, rule_id = teams.client_rule(job)                    # client-facing: 'Client-facing documents…'; else Client separation
    withheld = 0
    with store.db() as c:
        rows = [dict(r) for r in c.execute("SELECT id, title, client, outputs, updated_at, knowledge_id FROM team_jobs WHERE status='done' AND id<>?", (job['id'],))]
    for r in rows:
        if not keep(r['client'] or ''): withheld += 1; continue
        seen_k.add(r['knowledge_id'])
        for it in (json.loads(r['outputs'] or '{}').get('price') or {}).get('items') or []:
            if it.get('rate_source') in ('web', 'library') and it.get('rate'):
                out.append({'description': it['description'], 'unit': it['unit'], 'rate': it['rate'], 'date': it.get('source_date') or r['updated_at'][:10],
                            'source': f'{teams.ref(r["id"])} {r["title"]}', 'kind': it['rate_source']})
    items = [i for i in knowledge.listing(status='active', limit=100000)['items']
             if i['id'] not in seen_k and i['label'] != 'local' and not knowledge.model_block(i['id'], fam)]
    if items:
        with store.db() as c:
            for i in items:
                text = (c.execute('SELECT text FROM files WHERE id=?', (i['id'],)).fetchone() or [''])[0] or ''
                if 'RATE |' not in text: continue
                if not keep(i.get('client') or ''): withheld += 1; continue
                for m in RATE_LINE.finditer(text):
                    rate = _num(m.group('rate'))
                    if rate: out.append({'description': m.group('desc').strip(), 'unit': unit_key(m.group('unit')), 'rate': rate, 'date': m.group('date').strip(),
                                         'source': i['title'], 'kind': m.group('kind').strip()})
                agents.note('read', 'knowledge', i['id'], f'{member["role"]}: past rates')
    clients.log_withheld(rule_id, f'Digital team: {member["role"]} (past rates)', withheld)
    for n, h in enumerate(out, 1): h['hid'] = f'H{n}'
    return out[:400]


def qs_trends(job, stage, member, ctx):
    asm = (ctx['outputs'] or {}).get('assemble') or {}
    if not ctx.get('must_accept') and not asm.get('cost_plan'):
        return {'accept': False, 'reasons': ['The cost plan was not handed on.'], 'summary': 'Sent back: no cost plan.'}
    items = [i for i in ((ctx['outputs'] or {}).get('price') or {}).get('items') or [] if i.get('rate') is not None]
    past = history(job, member)
    if not past:
        return {'accept': True, 'summary': 'No past projects in Alice to compare with.', 'note': 'No history to compare with yet.',
                'output': {'history': 0, 'comparisons': [], 'unmatched': [i['ref'] for i in items],
                           'report': 'There are no past cost plans or team jobs in Alice to compare these rates with, so no trend can be '
                                     'reported yet. This estimate will be saved to Knowledge once you sign it off, so later estimates can be compared with it.'}}
    cur = '\n'.join(f'{i["ref"]} | {i["description"]} | {i["unit"]} | {i["rate"]} | {i.get("source_date") or ""}' for i in items)
    old = '\n'.join(f'{h["hid"]} | {h["description"]} | {h["unit"]} | {h["rate"]} | {h["date"]} | {h["source"]}' for h in past)
    extra = f'RATES USED NOW (ref | description | unit | rate | date)\n{cur}\n\nPAST RATES HELD IN ALICE (id | description | unit | rate | date | source)\n{old}'
    spec = ('{"matches": [{"ref": "Q1", "history": ["H1"], "note": ""}], "commentary": "a short plain report of what the comparison shows, no percentages", '
            '"summary": "one sentence", "note": ""}')
    d = _ask(job, member, ctx, stage, spec, extra=extra, include_docs=False)
    out = _common(d)
    out['accept'] = True
    hmap = {h['hid']: h for h in past}
    imap = {i['ref']: i for i in items}
    comps, matched = [], set()
    for m in d.get('matches') or []:
        if not isinstance(m, dict) or str(m.get('ref')) not in imap: continue
        it = imap[str(m['ref'])]
        hs = [hmap[h] for h in m.get('history') or [] if h in hmap and hmap[h]['unit'] == it['unit']]
        if not hs: continue
        rows = [{'rate': h['rate'], 'date': h['date'], 'source': h['source'], 'difference_pct': pct_change(it['rate'], h['rate'])} for h in hs]
        avg = float((sum((Decimal(str(r['difference_pct'])) for r in rows), Decimal('0')) / len(rows)).quantize(Decimal('0.1'), ROUND_HALF_UP))
        comps.append({'ref': it['ref'], 'description': it['description'], 'unit': it['unit'], 'rate_now': it['rate'], 'date_now': it.get('source_date') or '',
                      'past': rows, 'average_difference_pct': avg, 'note': teams._clean(m.get('note'), 300)})
        matched.add(it['ref'])
    report = teams._block(d.get('commentary'), 3000)
    if not comps: report = (report + '\n\n' if report else '') + 'None of the rates used has a comparable past rate (same unit and kind of work) in Alice.'
    out['output'] = {'history': len(past), 'comparisons': comps, 'unmatched': [i['ref'] for i in items if i['ref'] not in matched], 'report': report}
    out['summary'] = out['summary'] or f'{len(comps)} of {len(items)} rates compared with past projects'
    return out


teams.HANDLERS.update({'qs_plan': qs_plan, 'qs_measure': qs_measure, 'qs_price': qs_price, 'qs_assemble': qs_assemble, 'qs_trends': qs_trends})


# ---------------- outputs ----------------
def _gbp(x):
    return '' if x is None else f'£{x:,.2f}'


def _md(job, out):
    plan_o, price, asm, tr = out.get('plan') or {}, out.get('price') or {}, out.get('assemble') or {}, out.get('trends') or {}
    cp = asm.get('cost_plan') or compute(price.get('items') or [], (price.get('location') or {}).get('factor', 1.0))
    items = price.get('items') or []
    md = [f'**{DRAFT_MARK}**', '', f'Job {teams.ref(job["id"])} · prepared {date.today().strftime("%d %B %Y")}' + (f' · {job["location"]}' if job.get('location') else ''), '',
          '# Summary', asm.get('summary') or '', '', '# Cost summary',
          '| Element | Subtotal |', '|---|---|'] + [f'| {e["element"]} | {_gbp(e["subtotal"])} |' for e in cp['elements']] + [
          f'| Construction subtotal | {_gbp(cp["construction"])} |', f'| Preliminaries ({cp["percentages"]["prelims_pct"]}%) | {_gbp(cp["prelims"])} |',
          f'| Contingency ({cp["percentages"]["contingency_pct"]}%) | {_gbp(cp["contingency"])} |', f'| Fees ({cp["percentages"]["fees_pct"]}%) | {_gbp(cp["fees"])} |',
          f'| **Total (excluding VAT)** | **{_gbp(cp["total"])}** |', '', (price.get('location') or {}).get('note', ''), '', '# Measured and priced items',
          '| Ref | Element | Description | Qty | Unit | Rate | Amount | Rate source |', '|---|---|---|---|---|---|---|---|']
    amounts = {l['ref']: l['amount'] for l in cp['lines']}
    for i in items:
        md.append(f'| {i["ref"]} | {i["element"]} | {i["description"]}{" (approx.)" if i.get("approximate") else ""} | {i["quantity"]:g} | {i["unit"]} | '
                  f'{_gbp(i.get("rate"))} | {_gbp(amounts.get(i["ref"]))} | {SOURCE_LABELS[i["rate_source"]]} |')
    md += ['', '# Where each rate came from']
    for i in items:
        if i['rate_source'] == 'web': md.append(f'- {i["ref"]}: {i.get("source_title") or ""}, {i["source_url"]} (dated {i["source_date"]})')
        elif i['rate_source'] == 'library': md.append(f'- {i["ref"]}: your rate library, “{i["library_row"]["description"]}” ({i["library_row"]["source"]}{", " + i["library_row"]["as_of"] if i["library_row"]["as_of"] else ""})')
        else: md.append(f'- {i["ref"]}: unpriced. {i.get("rate_note", "")}')
    md += ['', '# Where each quantity came from'] + [f'- {i["ref"]}: {i["source_text"]}' + (' (from a drawing: approximate)' if i.get('approximate') else '') for i in items]
    md += ['', '# Assumptions'] + [f'- {a}' for a in asm.get('assumptions') or []]
    md += ['', '# Exclusions'] + [f'- {a}' for a in asm.get('exclusions') or []]
    md += ['', '# Risks'] + [f'- {r["risk"]}' + (f' Mitigation: {r["mitigation"]}' if r.get('mitigation') else '') for r in asm.get('risks') or []]
    md += ['', '# Market trends', tr.get('report') or '']
    for cmp_ in tr.get('comparisons') or []:
        md.append(f'- {cmp_["ref"]} {cmp_["description"]}: {_gbp(cmp_["rate_now"])} now; ' + '; '.join(f'{_gbp(p["rate"])} ({p["date"]}, {p["source"]}): {p["difference_pct"]:+.1f}%' for p in cmp_['past']))
    if plan_o.get('plan'): md += ['', '# How the team approached it', plan_o['plan']]
    md += ['', f'*{DRAFT_MARK}. All arithmetic was done by Alice from the team\'s structured answers. Rates without a source are not used.*']
    return '\n'.join(md), cp


def finish(job, team, jt):
    """Before sign-off: the Word cost plan and the Excel workbook, both marked as a draft for a qualified QS to review."""
    import documents, rules_engine
    job = teams._row(job['id'])
    out = job['outputs']
    md, cp = _md(job, out)
    price, asm, tr = out.get('price') or {}, out.get('assemble') or {}, out.get('trends') or {}
    items = price.get('items') or []
    amounts = {l['ref']: l['amount'] for l in cp['lines']}
    sheets = [
        {'name': 'Read me', 'rows': [[DRAFT_MARK], [f'Job {teams.ref(job["id"])}: {job["title"]}'], [f'Prepared {date.today().isoformat()} by the {team["name"]} team in Alice (team version v{job["team_version"]}).'],
                                      ['All arithmetic is done by Alice. Every rate has a source: a published web page with its date, your rate library, or it is unpriced and excluded.']]},
        {'name': 'Cost plan', 'rows': [['Ref', 'Element', 'Description', 'Quantity', 'Unit', 'Approximate', 'Rate (GBP)', 'Amount (GBP)', 'Rate source', 'Source', 'Source date']]
         + [[i['ref'], i['element'], i['description'], i['quantity'], i['unit'], 'Yes' if i.get('approximate') else '', i.get('rate'), amounts.get(i['ref']),
             SOURCE_LABELS[i['rate_source']], i.get('source_url') or (i.get('library_row') or {}).get('source') or i.get('rate_note', ''), i.get('source_date', '')] for i in items]},
        {'name': 'Summary', 'rows': [['Line', 'GBP']] + [[e['element'], e['subtotal']] for e in cp['elements']]
         + [['Construction subtotal', cp['construction']], [f'Preliminaries {cp["percentages"]["prelims_pct"]}%', cp['prelims']],
            [f'Contingency {cp["percentages"]["contingency_pct"]}%', cp['contingency']], [f'Fees {cp["percentages"]["fees_pct"]}%', cp['fees']],
            ['Total excluding VAT', cp['total']], ['Regional factor applied', cp['factor']], [(price.get('location') or {}).get('note', ''), '']]},
        {'name': 'Quantities', 'rows': [['Ref', 'Description', 'Quantity', 'Unit', 'Document', 'Page', 'Line', 'From a drawing']]
         + [[i['ref'], i['description'], i['quantity'], i['unit'], i['source']['document'], i['source']['page'], i['source']['line'], 'Yes' if i.get('approximate') else ''] for i in items]},
        {'name': 'Market trends', 'rows': [['Ref', 'Description', 'Unit', 'Rate now', 'Past rate', 'Past date', 'Past source', 'Difference %']]
         + [[c_['ref'], c_['description'], c_['unit'], c_['rate_now'], p['rate'], p['date'], p['source'], p['difference_pct']] for c_ in tr.get('comparisons') or [] for p in c_['past']]
         + [[tr.get('report') or '']]},
        {'name': 'Assumptions', 'rows': [['Type', 'Text']] + [['Assumption', a] for a in asm.get('assumptions') or []] + [['Exclusion', a] for a in asm.get('exclusions') or []]
         + [['Risk', r['risk'] + (' Mitigation: ' + r['mitigation'] if r.get('mitigation') else '')] for r in asm.get('risks') or []]},
    ]
    title = f'Cost plan - {job["title"]} (draft)'
    rules_engine.check_file(md, title)
    word = documents.to_docx(title, md)
    xlsx = documents.to_xlsx(title, sheets)
    docs = [documents.keep('docx', documents._slug(title, '.docx'), word, md),
            documents.keep('xlsx', documents._slug(title, '.xlsx'), xlsx, md)]
    for d in docs: agents.note('wrote', 'document', d['id'], d['name'])
    summary = (f'Estimated total {_gbp(cp["total"])} excluding VAT ({_gbp(cp["construction"])} construction, preliminaries {cp["percentages"]["prelims_pct"]}%, '
               f'contingency {cp["percentages"]["contingency_pct"]}%, fees {cp["percentages"]["fees_pct"]}%). '
               f'{sum(1 for i in items if i["rate_source"] == "web")} rates from published sources, {sum(1 for i in items if i["rate_source"] == "library")} from your rate library, '
               f'{sum(1 for i in items if i["rate_source"] == "unpriced")} unpriced. {(price.get("location") or {}).get("note", "")} {DRAFT_MARK}.')
    return {'documents': [{'id': d['id'], 'name': d['name'], 'kind': d['kind']} for d in docs], 'summary': summary, 'total': cp['total']}


def complete(job, team, jt):
    """After sign-off: saved to Knowledge (a note through the usual approval path) with a RATES USED block for Market Trends."""
    import knowledge, autoapprove
    job = teams._row(job['id'])
    md, cp = _md(job, job['outputs'])
    items = (job['outputs'].get('price') or {}).get('items') or []
    rates = ['', '# RATES USED', 'RATE | ref | description | unit | rate | source type | source | date'] + [
        f'RATE | {i["ref"]} | {i["description"].replace("|", "/")} | {i["unit"]} | {i["rate"]} | {i["rate_source"]} | '
        f'{(i.get("source_url") or (i.get("library_row") or {}).get("source") or "").replace("|", "/")} | {i.get("source_date") or ""}'
        for i in items if i.get('rate') is not None]
    r = knowledge.create('note', f'Cost plan: {job["title"]} ({teams.ref(job["id"])})', md + '\n' + '\n'.join(rates),
                         f'Digital team {team["name"]}, job {teams.ref(job["id"])}, signed off {date.today().isoformat()}', 'Digital team',
                         status='draft', client=job['client'] or '')
    if not r.get('duplicate'): autoapprove.knowledge_draft(r['id'])
    return r['id']


def _describe_plan(o):
    return '\n'.join(x for x in [o.get('plan', ''), 'Elements: ' + ', '.join(o.get('elements') or []) if o.get('elements') else '',
                                 'Documents: ' + '; '.join(f'{d["name"]} ({d["use"]})' for d in o.get('documents') or []) if o.get('documents') else '',
                                 'Location: ' + o['location'] if o.get('location') else 'No location given.'] if x)


def _describe_measure(o):
    lines = [f'{i["ref"]} {i["element"]}: {i["description"]}, {i["quantity"]:g} {i["unit"]} ({i["source_text"]}{"; from a drawing, approximate" if i.get("approximate") else ""})'
             for i in o.get('items') or []]
    lines += [f'Left out: {r["description"]} ({r["reason"]})' for r in o.get('rejected') or []]
    return '\n'.join(lines) or 'No items measured.'


def _describe_price(o):
    def src(i):
        if i['rate_source'] == 'web': return f'published: {i.get("source_title") or ""} {i["source_url"]} ({i["source_date"]})'
        if i['rate_source'] == 'library': return f'your rate library: {i["library_row"]["description"]}'
        return 'unpriced'
    lines = [f'{i["ref"]} {i["description"]}: {_gbp(i["rate"]) + " per " + i["unit"] if i.get("rate") is not None else "no rate"} ({src(i)})' for i in o.get('items') or []]
    return '\n'.join(lines + [(o.get('location') or {}).get('note', '')])


def _describe_assemble(o):
    cp = o.get('cost_plan') or {}
    return '\n'.join([o.get('summary', ''), f'Total excluding VAT {_gbp(cp.get("total"))} (construction {_gbp(cp.get("construction"))}).',
                      'Assumptions: ' + '; '.join(o.get('assumptions') or []), 'Exclusions: ' + '; '.join(o.get('exclusions') or []),
                      'Risks: ' + '; '.join(r['risk'] for r in o.get('risks') or [])])


teams.DESCRIBERS.update({'plan': _describe_plan, 'measure': _describe_measure, 'price': _describe_price, 'assemble': _describe_assemble,
                         'trends': lambda o: o.get('report', '')})
teams.FINISHERS['cost_estimate'] = finish
teams.COMPLETERS['cost_estimate'] = complete


# ---------------- the demo project (fictional) ----------------
def demo_project():
    """A fictional single-storey community hall: brief, specification, room and finishes schedules, and a small fictional rate library."""
    if not DEMO_DIR.is_dir(): raise ValueError('The demo project files are missing.')
    meta = json.loads((DEMO_DIR / 'project.json').read_text(encoding='utf-8'))
    docs = [{'name': d['name'], 'kind': d['kind'], 'text': (DEMO_DIR / d['file']).read_text(encoding='utf-8')} for d in meta['documents']]
    return {'title': meta['title'], 'brief': meta['brief'], 'location': meta['location'], 'documents': docs, 'rate_library': meta['rate_library']}


def load_demo_rates(tid=TEAM_ID):
    meta = json.loads((DEMO_DIR / 'project.json').read_text(encoding='utf-8'))
    raw = (DEMO_DIR / meta['rate_library']).read_bytes()
    with store.db() as c:
        if c.execute("SELECT 1 FROM team_rates WHERE team_id=? AND batch_name=?", (tid, 'FICTIONAL demo rate library')).fetchone():
            raise ValueError('The fictional demo rate library is already loaded.')
    return import_rates(tid, meta['rate_library'], raw, 'FICTIONAL demo rate library')


seed()
