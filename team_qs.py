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
SOURCE_LABELS = {'web': 'Published rate (web)', 'library': 'Your rate library', 'built_up': 'Built-up rate (from cited published rates)',
                 'estimate': 'Team estimate (judgement)', 'yours': 'Your rate', 'unpriced': 'Unpriced: flagged as an assumption'}
RULE_SOURCE = {'published': 'web', 'library': 'library', 'built_up': 'built_up', 'estimate': 'estimate'}     # rule key -> the item's rate_source
# What each source means, shown on the team page in the order and with the allowed state read from the rule (price_rules), never retyped.
# 'yours' is not in it: a rate you enter for an unpriced item is your decision afterwards, recorded as "Your rate".
SOURCE_DETAIL = {
    'published': 'A rate found by web search counts only with the page the search returned, the page\'s date and the item\'s unit; each one is cited.',
    'library': 'The closest row of the team\'s rate library with the same unit (Knowledge tab); the rate is taken from the library, never from the model.',
    'built_up': 'Built up from published rates for its parts (labour, materials, plant), each part cited with its page and date; Alice adds them up and shows the working.',
    'estimate': 'The Cost Surveyor\'s professional judgement, with its reasoning, the assumptions it made and any comparable rates it found online, cited. '
                'Badged Estimate and listed as an assumption.',
}
UNPRICED_RULE = {'key': 'unpriced', 'title': 'Flagged as unpriced', 'allowed': True,
                 'detail': 'Otherwise the item is left unpriced and listed as an assumption: a rate is never invented. You can enter your own rate for it on the job page.'}


def price_rules():
    """Where prices come from, in the order the rule sets, each with whether the rule allows it; unpriced always last."""
    import rules_engine
    rs = rules_engine.rate_sources()
    return [{'key': k, 'title': rules_engine.RATE_SOURCES[k], 'detail': SOURCE_DETAIL[k], 'allowed': k in rs['allowed']} for k in rs['order']] + [UNPRICED_RULE]


PRICE_NOTE = ('A regional factor is applied only when a published one is found for the location (between 0.7 and 1.4), else national rates are used. '
              'Totals and amounts (quantity × rate, and built-up rates) are worked out by Alice, not by the models.')
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
    # Sonnet by default (Stefan, 8 Oct 2026): members that search the web and return structured lists should not default to Haiku.
    # A default only: each team's own choice of model is kept, and can be changed per member under Edit team.
    {'id': 'cost-surveyor', 'role': 'Cost Surveyor', 'provider': 'claude_sonnet', 'tools': {'web_search': True}, 'categories': ['Quantity surveying'],
     'purpose': 'Prices each item from current market rates: published rates first, then Stefan\'s rate library, else unpriced.',
     'instructions': 'Price each measured item at current UK market rates. First look for published rates on the web and cite the exact page and '
                     'its date. Where you find no published rate, choose the closest row of Stefan\'s rate library by its id (same unit). Otherwise '
                     'leave the item unpriced: never invent a rate. If a location is given, look for a published regional adjustment factor and cite it; '
                     'if none is found, say national rates were used.'},
    {'id': 'market-trends-qs', 'role': 'Market Trends QS', 'provider': 'claude_sonnet', 'tools': {'web_search': True}, 'categories': ['Quantity surveying'],
     'purpose': 'Looks at the market for the job\'s location (cost trends, inflation indices, regional differences, material and labour pressures) and '
                'compares the rates used with past projects held in Alice.',
     'instructions': 'Search the web for current UK construction cost trends for the job\'s location: tender and building cost indices, regional '
                     'differences, material and labour pressures. Cite every source with its date. If the evidence supports it, suggest one market '
                     'adjustment as a percentage with your reasoning, for the Lead QS to accept or reject; never apply it yourself. Then match each rate '
                     'used to comparable rates from past cost plans and team jobs held in Alice (same unit, same kind of work); say plainly when there is '
                     'nothing comparable. Do not calculate totals or percentage differences: Alice does that.'},
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
     'task': 'Report current cost trends for the location, with dated sources, and any market adjustment you suggest; then how the rates used '
             'compare with rates in past projects held in Alice.',
     'hands': 'The Market Trends report and any suggested market adjustment.', 'checks': 'The cost plan is complete, with assumptions, exclusions and risks.'},
    {'key': 'adjust', 'title': 'Decide the market adjustment', 'member': 'lead-qs', 'handler': 'qs_adjust',
     'task': 'Accept or reject the market adjustment the Market Trends QS suggested, with your reason.',
     'hands': 'The cost plan with the adjustment applied, or the reason it was not.', 'checks': 'Any suggested adjustment cites dated sources.'},
]
TEMPLATE_FILING = {'on': True, 'category': 'Quantity surveying'}     # suggested; the category is created only when Stefan asks
MARKET_RANGE = (-15.0, 25.0)         # a market adjustment outside this range is reported, never applied (fixed: it protects the output)
SETTINGS = {'prelims_pct': 12.0, 'contingency_pct': 10.0, 'fees_pct': 10.0}


def seed():
    with store.db() as c:
        if c.execute('SELECT 1 FROM teams WHERE id=?', (TEAM_ID,)).fetchone(): return
    with store.acting('Alice', note='Seeded the Quantity surveying team'):
        _seed_team()


def _seed_team():
    t = _template()
    teams.create(t['name'], t['description'], t['autonomy'], tid=TEAM_ID, members=t['members'], settings=t['settings'], job_types=t['job_types'],
                 colour=t['colour'], icon=t['icon'], discipline=t['discipline'], filing=t.get('filing'))


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
def _ask(job, member, ctx, stage, spec, extra='', include_docs=True, what='the answer asked for', docs_only=None):
    system = teams.member_prompt(member, stage, ctx) + '\nReturn JSON only, no prose, in exactly this shape:\n' + spec
    payload = teams.job_payload(job, member, ctx, include_docs=include_docs, extra=extra, docs_only=docs_only)
    return teams.ask_json(member, job, system, payload, spec, what)


def _extra_key(ctx, member):
    """What a part's result depends on besides the part itself: feedback to act on and the member's model."""
    return {'feedback': ctx.get('feedback'), 'provider': member.get('provider'), 'instructions': member.get('instructions')}


def _merge_common(results):
    """accept/reasons/questions/notes across the parts of a stage: one part refusing the work refuses it."""
    outs = [_common(d) for d in results]
    refused = [o for o in outs if not o['accept']]
    reasons = list(dict.fromkeys(r for o in refused for r in o['reasons'] if r))
    qs = list(dict.fromkeys(q for o in outs for q in o['questions']))[:4]
    note = ' '.join(dict.fromkeys(o['note'] for o in outs if o['note']))[:1000]
    changed = ' '.join(dict.fromkeys(o['what_changed'] for o in outs if o['what_changed']))[:400]
    return {'accept': not refused, 'reasons': reasons, 'summary': '', 'note': note, 'questions': qs, 'what_changed': changed}


def _common(data):
    return {'accept': data.get('accept') is not False, 'reasons': [teams._clean(x, 400) for x in data.get('reasons') or []],
            'summary': teams._clean(data.get('summary'), 300), 'note': teams._block(data.get('note'), 1000),
            'questions': [teams._clean(q, 600) for q in data.get('questions') or [] if teams._clean(q, 600)],
            'what_changed': teams._clean(data.get('what_changed'), 400)}


def qs_plan(job, stage, member, ctx):
    spec = ('{"plan": "how you will run the estimate", "elements": [{"name": "element name", "documents": ["exact names of the documents it is measured from"]}], '
            '"documents": [{"name": "exact document name", "use": "what for"}], '
            '"location": "town or region of the site, if known", "assumptions": [], "summary": "one sentence", "note": "hand-off note to the Measurement Surveyor", '
            '"questions": [], "what_changed": ""}')
    d = _ask(job, member, ctx, stage, spec, what='the plan as JSON')
    out = _common(d)
    loc = teams._clean(job.get('location') or d.get('location'), 120)
    names, ed = [], {}
    for x in d.get('elements') or []:
        n = teams._clean(x.get('name') if isinstance(x, dict) else x, 80)
        if not n or n in names: continue
        names.append(n)
        if isinstance(x, dict): ed[n] = [teams._clean(y, 120) for y in x.get('documents') or [] if teams._clean(y, 120)][:12]
    out['output'] = {'plan': teams._block(d.get('plan'), 4000), 'elements': names[:30], 'element_documents': {k: v for k, v in ed.items() if v and k in names[:30]},
                     'documents': [{'name': teams._clean(x.get('name'), 120), 'use': teams._clean(x.get('use'), 200)} for x in d.get('documents') or [] if isinstance(x, dict)][:12],
                     'location': loc, 'assumptions': [teams._clean(x, 300) for x in d.get('assumptions') or []][:20]}
    out['accept'] = True
    return out


MEASURE_BATCH = 3            # elements per part of the take-off
PRICE_ITEMS = 20             # items per part of the pricing (and of the comparison)
MEASURE_SPEC = ('{"accept": true, "reasons": [], "items": [{"ref": "Q1", "element": "", "description": "", "quantity": 0, "unit": "m2|m3|m|nr|item", '
                '"source": {"document": "exact document name", "page": "page number if the document has pages", "line": "schedule line, e.g. Line 4"}, '
                '"from_drawing": false, "note": ""}], "summary": "one sentence", "note": "hand-off note to the Cost Surveyor", "questions": [], "what_changed": ""}')


def _doc_named(docs, name):
    name = teams._clean(name, 120).lower()
    return docs.get(name) or next((x for k, x in docs.items() if Path(k).stem == Path(name).stem), None) if name else None


def _element_pieces(plan, docs):
    """One piece per element of the plan, with the documents it is measured from (all of the job's documents when the plan names none)."""
    every = [x['name'] for x in docs.values()]
    ed = plan.get('element_documents') or {}
    out = []
    for n in plan.get('elements') or []:
        mine = list(dict.fromkeys(d['name'] for d in (_doc_named(docs, x) for x in ed.get(n) or []) if d))
        out.append({'label': n, 'docs': mine or every})
    return out


def _split_docs(piece):
    if len(piece['docs']) < 2: return None
    h = len(piece['docs']) // 2
    return {**piece, 'docs': piece['docs'][:h]}, {**piece, 'docs': piece['docs'][h:]}


def qs_measure(job, stage, member, ctx):
    plan = (ctx['outputs'] or {}).get('plan') or {}
    if not ctx.get('must_accept') and not plan.get('elements'):
        return {'accept': False, 'reasons': ['The plan lists no elements to measure.'], 'summary': 'Sent the plan back: no elements to measure.'}
    docs = {x['name'].lower(): x for x in teams._docs_in(job['id'])}
    pieces = _element_pieces(plan, docs) or [{'label': 'General', 'docs': [x['name'] for x in docs.values()]}]
    every = ', '.join(p['label'] for p in pieces)
    rr = (ctx['outputs'] or {}).get('_rerun') or {}
    only = rr.get('elements') if rr.get('kind') == 'remeasure' else None        # Re-measure: only the elements Stefan chose
    if only is not None: pieces = [p for p in pieces if p['label'] in only]

    def run(part, info):
        mine = list(dict.fromkeys(p['label'] for p in part))
        names = list(dict.fromkeys(d for p in part for d in p['docs']))
        extra = (f'WHOLE PLAN: elements {every}.\nTHIS PART: take off ONLY these elements: {", ".join(mine)}, from the DOCUMENTS given '
                 f'({", ".join(names) or "none"}). The other elements are measured separately: do not measure them here.')
        return _ask(job, member, ctx, stage, MEASURE_SPEC, extra=extra, what='the list of measured items', docs_only=names)
    done, stats = teams.in_parts(job, stage, pieces, run, _split_docs, batch=MEASURE_BATCH, extra=_extra_key(ctx, member))
    out = _merge_common([d for _, d in done])
    if not out['accept'] and not ctx.get('must_accept'): return out
    items, rejected, seen = [], [], set()
    for part, d in done:
        mine = {p['label'].lower(): p['label'] for p in part}
        for it in d.get('items') or []:
            if not isinstance(it, dict): continue
            desc = teams._clean(it.get('description'), 300)
            q, unit = _num(it.get('quantity')), unit_key(it.get('unit'))
            src = it.get('source') if isinstance(it.get('source'), dict) else {}
            docname = teams._clean(src.get('document'), 120)
            doc = _doc_named(docs, docname)
            page, line = teams._clean(src.get('page'), 20), teams._clean(src.get('line'), 60)
            why = ('no description' if not desc else 'no quantity above zero' if not q or q <= 0 else 'no unit' if not unit
                   else 'no source document' if not docname else f'“{docname}” is not one of this job\'s documents' if not doc
                   else 'no page or schedule line' if not (page or line) else '')
            if why: rejected.append({'description': desc or '(none)', 'reason': why}); continue
            el = teams._clean(it.get('element'), 80)
            el = mine.get(el.lower()) or (part[0]['label'] if len(mine) == 1 else el) or 'General'
            key = (el.lower(), desc.lower(), round(q, 3), unit, doc['name'], page, line)
            if key in seen: continue                       # the same item from two parts (e.g. a halved element) is kept once
            seen.add(key)
            approx = bool(it.get('from_drawing')) or doc['kind'] == 'drawing'
            items.append({'ref': f'Q{len(items) + 1}', 'element': el, 'description': desc,
                          'quantity': round(q, 3), 'unit': unit, 'approximate': approx,
                          'source': {'document': doc['name'], 'page': page, 'line': line},
                          'source_text': doc['name'] + (f', page {page}' if page else '') + (f', {line}' if line else ''), 'note': teams._clean(it.get('note'), 300)})
    out['output'] = {'items': items, 'rejected': rejected}
    if only is not None:                  # the other elements' items are kept exactly as measured (same refs, so their prices stay)
        prev = (ctx['outputs'] or {}).get('measure') or (rr.get('previous') or {}).get('measure') or {}
        kept = [i for i in prev.get('items') or [] if i['element'] not in only]
        top = max([int(i['ref'][1:]) for i in prev.get('items') or [] if re.fullmatch(r'Q\d+', i['ref'])] + [0])
        for n, i in enumerate(items, 1): i['ref'] = f'Q{top + n}'
        out['output'] = {'items': kept + items, 'rejected': rejected,
                         'remeasured': {'elements': list(only), 'refs': [i['ref'] for i in items],
                                        'replaced': [i['ref'] for i in prev.get('items') or [] if i['element'] in only]}}
    out['parts'] = stats
    out['accept'] = True
    out['summary'] = (done[0][1].get('summary') if len(done) == 1 else '') or (f'{len(items)} items measured' + (f', {len(rejected)} left out without a source' if rejected else ''))
    if only is not None: out['summary'] = f'Re-measured {", ".join(only)}: {len(items)} item{"s" if len(items) != 1 else ""}; the other elements are kept as measured.'
    out['summary'] = teams._clean(out['summary'], 300)
    return out


def _item_pieces(items, per=PRICE_ITEMS):
    """Pieces of up to `per` items, one element at a time, in the take-off's order."""
    out = []
    for el in dict.fromkeys(i['element'] for i in items):
        mine = [i['ref'] for i in items if i['element'] == el]
        out += [{'label': el, 'refs': mine[k:k + per]} for k in range(0, len(mine), per)]
    return out


def _split_refs(piece):
    if len(piece['refs']) < 2: return None
    h = len(piece['refs']) // 2
    return {**piece, 'refs': piece['refs'][:h]}, {**piece, 'refs': piece['refs'][h:], 'factor': False}


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
manufacturers' and suppliers' published prices). Price each measured item from the FIRST source in RATE SOURCES that is allowed for it
and that you can support; never use a source marked not allowed, and never invent a rate.
- published: a rate per the item's unit, with the exact URL of the page that states it, its title and the page's date.
- library: the id of the closest row in Stefan's RATE LIBRARY (same unit).
- built_up: the item's rate built up from published rates for its components (labour, materials, plant), each component with how much of it
  goes into one unit of the item, its own published rate, the page that states it and the page's date. Alice adds them up; do not total them.
- estimate: only for items marked ESTIMATE ALLOWED: your professional judgement of the rate, with your reasoning, the assumptions you made
  (for example a wall height the drawings do not give) and any comparable rates you found online, each with its page and date.
If Stefan's FEEDBACK asks for a source that is not allowed, do not use it: say so in not_allowed, in one plain sentence each.
If a LOCATION is given and this part asks for it, look for a published regional adjustment factor (location factor) and cite it; if none is
found, leave location_factor empty.
Return JSON only, no prose:
{spec}'''
PRICE_SPEC = ('{"accept": true, "reasons": [], "rates": [{"ref": "Q1", "source": "published|library|built_up|estimate", "rate": 0, "unit": "", '
              '"source_url": "", "source_title": "", "source_date": "YYYY-MM-DD or YYYY-MM", "library_id": "", '
              '"built_up": {"components": [{"description": "", "quantity_per_unit": 1, "unit": "", "rate": 0, "source_url": "", "source_title": "", "source_date": ""}]}, '
              '"estimate": {"rate": 0, "reasoning": "", "assumptions": [""], "comparables": [{"rate": 0, "unit": "", "source_url": "", "source_date": "", "note": ""}]}, '
              '"note": ""}], "location_factor": {"factor": 1.0, "region": "", "source_url": "", "source_title": "", "source_date": ""}, '
              '"not_allowed": [], "searches": ["the searches you ran"], "summary": "one sentence", "note": "hand-off note to the Lead QS", "questions": [], "what_changed": ""}')


def _date_ok(s):
    s = teams._clean(s, 20)
    m = re.fullmatch(r'(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?', s)
    return s if m and '1990' <= m.group(1) and s[:10] <= date.today().isoformat() else ''


def estimates_allowed(outputs):
    """Items Stefan asked the team to estimate on this job (Ask the team to estimate these): allowed whatever the rule says."""
    return set(((outputs or {}).get('_estimates') or {}).get('refs') or [])


def estimates_on_job(outputs):
    """Team estimates allowed on this whole job (ticked on the Start a job screen)."""
    return bool(((outputs or {}).get('_estimates') or {}).get('all'))


def _source_lines(rs, allow_refs):
    lines = []
    for n, k in enumerate(rs['order'], 1):
        ok = k in rs['allowed']
        note = 'allowed' if ok else ('not allowed, except for items marked ESTIMATE ALLOWED' if k == 'estimate' and allow_refs else 'not allowed')
        lines.append(f'{n}. {k}: {note}')
    return '\n'.join(lines + [f'{len(rs["order"]) + 1}. otherwise leave the rate empty (unpriced)'])


def _cited(seen_norm, url, when):
    """(page url, title) when url is among the pages the search returned and has a date; else None."""
    import org_research
    hit = seen_norm.get(org_research._norm_url(url)) if url else None
    return hit if hit and when else None


def _built_up(r, it, seen_norm):
    """A built-up rate from cited components, worked out here: Σ quantity per unit × component rate, to the penny."""
    comps = (r.get('built_up') or {}).get('components') if isinstance(r.get('built_up'), dict) else None
    if not comps: return None, ''
    work, total = [], Decimal('0')
    for c_ in comps[:12]:
        if not isinstance(c_, dict): continue
        q, rate = _num(c_.get('quantity_per_unit')), _num(c_.get('rate'))
        url, when = str(c_.get('source_url') or '').strip(), _date_ok(c_.get('source_date'))
        hit = _cited(seen_norm, url, when)
        desc = teams._clean(c_.get('description'), 200)
        if not desc or not q or q <= 0 or not rate or rate <= 0: return None, f'component “{desc or "?"}” has no quantity or rate'
        if not hit: return None, f'component “{desc}” has no page the search returned, with a date'
        amount = money(Decimal(str(q)) * Decimal(str(rate)))
        total += amount
        work.append({'description': desc, 'quantity_per_unit': q, 'unit': unit_key(c_.get('unit')), 'rate': float(money(rate)), 'amount': float(amount),
                     'source_url': hit[0], 'source_title': teams._clean(c_.get('source_title') or hit[1], 200), 'source_date': when})
    if not work or total <= 0: return None, 'no components'
    return {'rate': float(money(total)), 'working': work}, ''


def _estimate(r, seen_norm):
    e = r.get('estimate') if isinstance(r.get('estimate'), dict) else None
    if not e: return None, ''
    rate, why = _num(e.get('rate')), teams._block(e.get('reasoning'), 1200)
    if not rate or rate <= 0: return None, 'no rate'
    if not why: return None, 'no reasoning given'
    comps, dropped = [], 0
    for c_ in (e.get('comparables') or [])[:8]:
        if not isinstance(c_, dict): continue
        url, when = str(c_.get('source_url') or '').strip(), _date_ok(c_.get('source_date'))
        hit, cr = _cited(seen_norm, url, when), _num(c_.get('rate'))
        if not hit or not cr: dropped += 1; continue                 # a comparable counts only with a returned page and its date
        comps.append({'rate': float(money(cr)), 'unit': unit_key(c_.get('unit')), 'source_url': hit[0], 'source_title': hit[1] or '',
                      'source_date': when, 'note': teams._clean(c_.get('note'), 200)})
    return {'rate': float(money(rate)), 'reasoning': why, 'assumptions': [teams._clean(a, 300) for a in e.get('assumptions') or [] if teams._clean(a, 300)][:8],
            'comparables': comps, 'comparables_dropped': dropped}, ''


def qs_price(job, stage, member, ctx):
    import assistants, org_research, rules_engine, rule_packs
    outs = ctx['outputs'] or {}
    rr = outs.get('_rerun') or {}
    prev = outs.get('price') or (rr.get('previous') or {}).get('price') or {}
    # Only some items are priced again: an estimate pass (Ask the team to estimate these), a Re-price (the items Stefan chose) or a
    # Re-measure (the items measured again); every other item keeps its price exactly, and the measured quantities are never changed.
    if prev.get('items') and prev.get('estimate_pass'): redo, partial = list(prev['estimate_pass']), True
    elif prev.get('items') and rr.get('kind') == 'reprice': redo, partial = list(rr.get('refs') or []), True
    elif prev.get('items') and rr.get('kind') == 'remeasure': redo, partial = list(((outs.get('measure') or {}).get('remeasured') or {}).get('refs') or []), True
    else: redo, partial = [], False
    if partial:
        old = {i['ref']: i for i in prev['items']}
        items = [old[m['ref']] if m['ref'] in old and m['ref'] not in redo else m for m in (outs.get('measure') or {}).get('items') or prev['items']]
    else:
        items = (outs.get('measure') or {}).get('items') or []
    if not items and not ctx.get('must_accept'):
        return {'accept': False, 'reasons': ['No measured items with a quantity, a unit and a source were handed on.'],
                'summary': 'Sent back: nothing measured with a source.'}
    plan = outs.get('plan') or {}
    location = teams._clean(plan.get('location') or job.get('location'), 120)
    rs = rules_engine.rate_sources()                          # which sources, in which order: the Rules page decides
    if rr.get('order'):                                       # a different order for this re-run only; what is allowed stays the rule's
        rs = {**rs, 'order': list(rr['order']) + [k for k in rs['order'] if k not in rr['order']]}
    allow_refs = estimates_allowed(outs) | (set(redo) if partial and rr.get('estimates') else set()) | ({i['ref'] for i in items} if estimates_on_job(outs) else set())
    lib = library(job['team_id'])
    prov = member['provider'] if member.get('provider') in assistants.PROVIDERS else 'claude_sonnet'
    fam = assistants.family(prov)
    model = assistants.PROVIDERS[prov][0] if fam in org_research.KEYS else ''
    fam = fam if fam in org_research.KEYS else 'claude'
    target = f'Digital team: {member["role"]}'
    byref = {i['ref']: i for i in items}
    todo = [i for i in items if i['ref'] in redo] if partial else items
    elements = ', '.join(dict.fromkeys(i['element'] for i in items))
    pieces = _item_pieces(todo)
    if pieces and not partial: pieces[0]['factor'] = True     # the regional factor is looked for once, in the first part
    prompt = PRICE_PROMPT.format(member=teams.member_prompt(member, stage, ctx), spec=PRICE_SPEC)
    web = teams.tool_on(member, 'web_search', 'qs_price')     # switched on or off per member under Edit team
    if not web: prompt += ('\nWEB SEARCH IS SWITCHED OFF for you on this team: you cannot cite pages, so published and built-up rates are not possible. '
                           'Use the RATE LIBRARY or, where allowed, a team estimate (without comparables); never invent a page.')
    past = teams._knowledge(job, member, fam)              # past cost plans filed in its categories: for comparison, never a rate source

    def run(part, info):
        mine = [byref[r] for p in part for r in p['refs']]
        _, cands = _library_candidates(job['team_id'], mine)
        factor = any(p.get('factor') for p in part)
        query = (f'JOB: {job["title"]}\nBRIEF\n{job["brief"][:3000]}\n\nLOCATION: {location or "not given (use national rates)"}\n'
                 f'ALL ELEMENTS OF THE ESTIMATE: {elements}\n'
                 + ('' if factor else 'THIS PART: leave location_factor empty; it is looked for separately.\n')
                 + f'RATE SOURCES (in this order)\n{_source_lines(rs, allow_refs)}\n\n'
                 + 'MEASURED ITEMS IN THIS PART (ref | element | description | quantity | unit)\n'
                 + '\n'.join(f'{i["ref"]} | {i["element"]} | {i["description"]} | {i["quantity"]} | {i["unit"]}'
                             + (' | ESTIMATE ALLOWED' if i['ref'] in allow_refs and 'estimate' not in rs['allowed'] else '') for i in mine)
                 + '\n\nRATE LIBRARY (id | description | unit | region | as of)\n'
                 + ('\n'.join(f'{r["id"]} | {r["description"]} | {r["unit"]} | {r["region"]} | {r["as_of"]}' for r in cands) or '(empty)')
                 + ('\n\nPAST COST PLANS IN ALICE (for comparison only, e.g. as comparables for an estimate; never a rate source)\n' + past if past else '')
                 + ('\n\nFEEDBACK TO ACT ON\n' + json.dumps(ctx['feedback'], ensure_ascii=False) if ctx.get('feedback') else ''))

        def query_for(p):
            rules_engine.check_outbound(query, target, provider=p)
            return rule_packs.live_check(query, p, target, packs=member['packs'])['text'] if member.get('packs') else query
        found = {'seen': {}, 'used': fam, 'failures': []}
        if not web:
            d = teams.ask_json(member, job, prompt, query, PRICE_SPEC, 'the list of priced items')
            return {'data': d, 'seen': {}, 'used': '', 'failures': [], 'factor': factor}

        def search(system, _payload):
            rules_engine.check_spend('chat')
            meta = {}
            raw, seen, used, failures = org_research.search(system, query_for, fam, workload=target, model=model,
                                                            max_tokens=teams.max_output(member), meta=meta)
            found['seen'].update(seen); found['used'], found['failures'] = used, failures
            if meta.get('truncated'): raise teams.CutOff(f'{member["role"]}\'s answer was cut off at the model\'s length limit.', raw=raw)
            return raw
        d = teams.ask_json(member, job, prompt, query, PRICE_SPEC, 'the list of priced items', call=search)
        return {'data': d, 'seen': found['seen'], 'used': found['used'], 'failures': found['failures'], 'factor': factor}
    done, stats = teams.in_parts(job, stage, pieces, run, _split_refs, batch=PRICE_ITEMS,
                                 extra={**_extra_key(ctx, member), 'location': location, 'rules': rs, 'allow': sorted(allow_refs), 'redo': redo,
                                        'partial': partial, 'web': web},
                                 size=lambda p: len(p['refs']))
    out = _merge_common([r['data'] for _, r in done])
    if not out['accept'] and not ctx.get('must_accept'): return out
    seen, d, queries, failures, used, asked = {}, {'rates': [], 'location_factor': {}}, [], [], fam, []
    for part, r in done:
        seen.update(r['seen'])
        mine = {x for p in part for x in p['refs']}             # a part answers only for its own items
        d['rates'] += [x for x in r['data'].get('rates') or [] if isinstance(x, dict) and str(x.get('ref')) in mine]
        if r['factor'] and isinstance(r['data'].get('location_factor'), dict): d['location_factor'] = r['data']['location_factor']
        queries += [q for q in r['data'].get('searches') or [] if isinstance(q, str)]
        asked += [teams._clean(x, 300) for x in r['data'].get('not_allowed') or [] if teams._clean(x, 300)]
        failures += r['failures']; used = r['used']
    d['searches'] = list(dict.fromkeys(queries))
    seen_norm = {org_research._norm_url(u): (u, t) for u, t in seen.items()}
    by_ref = {str(r.get('ref')): r for r in d.get('rates') or [] if isinstance(r, dict)}
    libmap = {r['id']: r for r in lib}
    priced, cited, blocked_est = [], set(), []
    refused = [x for x in prev.get('refused_rates') or [] if x.get('ref') not in set(redo)] if partial else []
    for it in items:
        if partial and it['ref'] not in redo:
            priced.append(it); continue                          # a partial pass prices only the items chosen
        r = by_ref.get(it['ref']) or {}
        row = {k: v for k, v in it.items() if k not in ('rate', 'rate_source', 'source_url', 'source_title', 'source_date', 'rate_note', 'library_row',
                                                         'working', 'estimate', 'decision')}
        cands, why = {}, {}
        rate, url = _num(r.get('rate')), str(r.get('source_url') or '').strip()
        when = _date_ok(r.get('source_date'))
        hit = _cited(seen_norm, url, when)
        web_why = ('' if rate and rate > 0 and hit and unit_key(r.get('unit') or it['unit']) == it['unit'] else
                   'no rate' if not rate or rate <= 0 else 'no source page' if not url else
                   'no date for the source' if not when else 'its page was not among the pages the search returned' if not hit else 'a different unit')
        if url and r.get('source', 'published') == 'published':
            if web_why: why['published'] = web_why
            else: cands['published'] = {'rate': round(rate, 2), 'rate_source': 'web', 'source_url': hit[0], 'source_title': teams._clean(r.get('source_title') or hit[1], 200),
                                        'source_date': when, 'rate_note': teams._clean(r.get('note'), 300)}
        lr = libmap.get(str(r.get('library_id') or ''))
        how = 'chosen by the Cost Surveyor'
        if not (lr and lr['unit'] == it['unit']):
            best = max(((_score(it['description'], x['description']), x) for x in lib if x['unit'] == it['unit']), key=lambda x: x[0], default=(0, None))
            lr, how = (best[1], 'matched by Alice on description and unit') if best[0] >= 0.5 else (None, '')
        if lr:
            cands['library'] = {'rate': round(float(lr['rate']), 2), 'rate_source': 'library', 'source_title': lr['source'] or lr['batch_name'], 'source_date': lr['as_of'],
                                'library_row': {k: lr[k] for k in ('id', 'code', 'description', 'unit', 'rate', 'region', 'as_of', 'source')}, 'rate_note': how}
        bu, bu_why = _built_up(r, it, seen_norm)
        if bu: cands['built_up'] = {'rate': bu['rate'], 'rate_source': 'built_up', 'working': bu['working'], 'source_title': 'Built up from cited published rates',
                                    'source_date': max(w['source_date'] for w in bu['working']), 'rate_note': teams._clean(r.get('note'), 300)}
        elif bu_why: why['built_up'] = bu_why
        es, es_why = _estimate(r, seen_norm)
        if es: cands['estimate'] = {'rate': es['rate'], 'rate_source': 'estimate', 'estimate': es, 'source_title': f'Estimate by the {member["role"]}',
                                    'source_date': date.today().isoformat(), 'rate_note': es['reasoning'][:300]}
        elif es_why: why['estimate'] = es_why
        ok = lambda k: k in rs['allowed'] or (k == 'estimate' and it['ref'] in allow_refs)
        pick = next((k for k in rs['order'] if k in cands and ok(k)), None)
        for k in cands:
            if k != pick and not ok(k):
                refused.append({'ref': it['ref'], 'rate': cands[k]['rate'], 'source': k, 'reason': 'not allowed by the rule “Where digital teams\' rates come from”'})
                if k == 'estimate': blocked_est.append(it['ref'])
        for k, w in why.items():
            refused.append({'ref': it['ref'], 'rate': rate if k == 'published' else None, 'source_url': url if k == 'published' else '', 'source': k, 'reason': w})
        if pick:
            row.update(cands[pick])
            if pick == 'published': cited.add(row['source_url'])
            if pick == 'library': agents.note('read', 'team_rate', row['library_row']['id'], f'{member["role"]}: {it["ref"]}')
            for w in row.get('working') or []: cited.add(w['source_url'])
            for c_ in (row.get('estimate') or {}).get('comparables') or []: cited.add(c_['source_url'])
        else:
            row.update({'rate': None, 'rate_source': 'unpriced', 'rate_note': 'No allowed source could price it: ' + (
                '; '.join(f'{rules_engine.RATE_SOURCES[k].lower()}: {w}' for k, w in why.items()) or 'none was found') + '.'})
        priced.append(row)
    if partial:
        loc = prev.get('location') or {'applied': False, 'factor': 1.0, 'note': 'National rates used.'}
    else:
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
    searches = [] if not web else [{'provider': org_research.PROVIDER_NAMES.get(used, used), 'queries': [teams._clean(q, 200) for q in d.get('searches') or []][:40],
                 'sources': [{'url': u, 'title': (t or '')[:200], 'cited': u in cited} for u, t in seen.items()][:60],
                 'fallback': [x['text'] for x in failures]}]
    counts = {k: sum(1 for x in priced if x['rate_source'] == k) for k in SOURCE_LABELS}
    out['output'] = {'items': priced, 'location': loc, 'refused_rates': refused,
                     'searched_with': org_research.searched_with(used, failures) if web else 'no web search (switched off for this member)',
                     'conflicts': _conflicts(asked, blocked_est, ctx, rs)}
    out['searches'] = searches
    out['parts'] = stats
    out['accept'] = True
    out['summary'] = out['summary'] or ', '.join(f'{counts[k]} {SUMMARY_WORDS[k]}' for k in SUMMARY_WORDS if counts.get(k) or k in ('web', 'unpriced'))
    if partial and rr and not prev.get('estimate_pass'):
        out['summary'] = teams._clean(f'Priced again: {", ".join(redo) or "nothing (no item changed)"}; the other items keep their prices. ' + out['summary'], 300)
    return out


SUMMARY_WORDS = {'web': 'priced from published rates', 'library': 'from your rate library', 'built_up': 'built up from cited rates',
                 'estimate': 'estimated by the team', 'yours': 'your rates', 'unpriced': 'unpriced'}


def _conflicts(asked, blocked_est, ctx, rs):
    """What Stefan asked for that the current rules do not allow, said plainly, with where to allow it (the rule, or the per-job button).
    Raised when the Cost Surveyor reports it (not_allowed), or when it offered estimates the rule refused after Stefan's feedback."""
    out = [{'what': a, 'rule': 'rate_sources'} for a in dict.fromkeys(asked)]
    stefan = any(f.get('from') == 'Stefan' or str(f.get('from', '')).startswith('Stefan') for f in ctx.get('feedback') or [])
    if blocked_est and (stefan or out):
        out.append({'what': f'Estimates for {", ".join(blocked_est)}', 'rule': 'rate_sources', 'refs': blocked_est})
    for c_ in out:
        c_['text'] = (f'{c_["what"]}: the rule “Where digital teams\' rates come from” does not allow '
                      + ('team estimates' if 'estimate' not in rs['allowed'] else 'this source')
                      + ' at the moment, so those items stay unpriced. To allow it, change the rule, or use “Ask the team to estimate these” on the items.')
        c_['links'] = [{'label': 'Open the rule', 'href': '/admin/rules?rule=rate_sources#rules'}, {'label': 'Ask the team to estimate these', 'href': '#estimate'}]
    return out


def compute(items, factor=1.0, settings=None, market_pct=0.0):
    """The cost plan's arithmetic, in code: quantity × rate × factor per line, subtotals per element, preliminaries,
    contingency and fees as percentages, the total. Money to the penny, rounded half up."""
    s = {**SETTINGS, **(settings or {})}
    f = Decimal(str(factor or 1))
    lines, elements, estimated = [], {}, Decimal('0')
    for it in items:
        if it.get('rate_source') == 'unpriced' or it.get('rate') is None: continue
        amount = money(Decimal(str(it['quantity'])) * Decimal(str(it['rate'])) * f)
        lines.append({'ref': it['ref'], 'element': it['element'], 'amount': float(amount)})
        elements[it['element']] = elements.get(it['element'], Decimal('0')) + amount
        if it.get('rate_source') == 'estimate': estimated += amount
    construction = sum(elements.values(), Decimal('0'))
    market = money(construction * Decimal(str(market_pct or 0)) / 100)     # an accepted market adjustment, on the construction cost
    base = construction + market
    prelims = money(base * Decimal(str(s['prelims_pct'])) / 100)
    contingency = money((base + prelims) * Decimal(str(s['contingency_pct'])) / 100)
    fees = money((base + prelims + contingency) * Decimal(str(s['fees_pct'])) / 100)
    total = base + prelims + contingency + fees
    return {'lines': lines, 'elements': [{'element': k, 'subtotal': float(v)} for k, v in elements.items()],
            'construction': float(construction), 'prelims': float(prelims), 'contingency': float(contingency), 'fees': float(fees),
            'total': float(total), 'factor': float(f), 'percentages': {k: s[k] for k in SETTINGS},
            'market_pct': float(market_pct or 0), 'market_adjustment': float(market),
            'estimated': float(estimated),
            'estimated_pct': float((estimated / construction * 100).quantize(Decimal('0.1'), ROUND_HALF_UP)) if construction else 0.0}


def estimated_line(cp):
    """How much of the construction cost comes from team estimates, in one sentence (or '' when none does)."""
    if not cp.get('estimated'): return ''
    return f'{_gbp(cp["estimated"])} of the {_gbp(cp["construction"])} construction cost ({cp["estimated_pct"]:g}%) comes from team estimates.'


def _sourced(i):
    """Every priced item says where its rate came from, with what that source needs (a code check the Lead QS makes before accepting)."""
    src = i.get('rate_source')
    return src in SOURCE_LABELS and not (
        (src == 'web' and not (i.get('source_url') and i.get('source_date'))) or (src == 'built_up' and not i.get('working'))
        or (src == 'estimate' and not (i.get('estimate') or {}).get('reasoning')))


def estimate_assumptions(items, plan):
    """Each team estimate as an assumption, with its reasoning and what was assumed, and the estimated share of the cost (fixed: they
    protect the output)."""
    out = []
    for i in items:
        if i.get('rate_source') != 'estimate': continue
        e = i.get('estimate') or {}
        out.append(f'{i["ref"]} {i["description"]}: team estimate of {_gbp(i["rate"])} per {i["unit"]}, not a published rate. Reasoning: {e.get("reasoning", "")}'
                   + (f' Assumed: {"; ".join(e["assumptions"])}.' if e.get('assumptions') else '')
                   + (f' Compared with: {"; ".join(_gbp(c_["rate"]) + " (" + c_["source_url"] + ", " + c_["source_date"] + ")" for c_ in e["comparables"])}.' if e.get('comparables') else ''))
    line = estimated_line(plan)
    return out + ([line] if line else [])


def qs_assemble(job, stage, member, ctx):
    price = (ctx['outputs'] or {}).get('price') or {}
    items = price.get('items') or []
    if not ctx.get('must_accept'):
        bad = [i['ref'] for i in items if not _sourced(i)]
        if not items or bad:
            return {'accept': False, 'reasons': ['No priced items were handed on.'] if not items else
                    [f'Items {", ".join(bad)} have a rate without a cited web source, a rate library row, a cited build-up, an estimate with its '
                     'reasoning, or an unpriced flag.'], 'summary': 'Sent the pricing back.'}
    loc = price.get('location') or {}
    plan = compute(items, loc.get('factor', 1.0), ctx.get('settings'))
    view = [{'ref': i['ref'], 'element': i['element'], 'description': i['description'], 'quantity': i['quantity'], 'unit': i['unit'],
             'approximate': i.get('approximate'), 'rate_source': SOURCE_LABELS[i['rate_source']]} for i in items]
    extra = ('COST PLAN FIGURES (calculated by Alice; do not recalculate)\n' + json.dumps({'items': view, 'totals': {k: plan[k] for k in ('construction', 'prelims', 'contingency', 'fees', 'total')},
                                                                                           'location': loc.get('note')}, ensure_ascii=False))
    spec = ('{"accept": true, "reasons": [], "summary": "two or three sentences describing the estimate (no figures)", "assumptions": [], "exclusions": [], '
            '"risks": [{"risk": "", "mitigation": ""}], "note": "hand-off note to the Market Trends QS", "questions": [], "what_changed": ""}')
    d = _ask(job, member, ctx, stage, spec, extra=extra, include_docs=False, what='the cost plan\'s assumptions, exclusions and risks')
    out = _common(d)
    if not out['accept'] and not ctx.get('must_accept'): return out
    auto = [f'{i["ref"]} {i["description"]}: ' + (f'left unpriced by {i["decision"]["by"]}' if i.get('decision') else
             'unpriced (no published rate with a source and date, and no rate library row)') + '; excluded from the total.' for i in items if i['rate_source'] == 'unpriced']
    auto += estimate_assumptions(items, plan)
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
        vc, va = store.viewer_clause('team_job', 'team_jobs.id')    # past rates only from jobs this job's person may see
        rows = [dict(r) for r in c.execute("SELECT id, title, client, outputs, updated_at, knowledge_id FROM team_jobs WHERE status='done' AND id<>?" + vc, (job['id'], *va))]
    for r in rows:
        if not keep(r['client'] or ''): withheld += 1; continue
        seen_k.add(r['knowledge_id'])
        for it in (json.loads(r['outputs'] or '{}').get('price') or {}).get('items') or []:
            if it.get('rate_source') in ('web', 'library', 'yours', 'built_up') and it.get('rate'):
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
                    if m.group('kind').strip() == 'estimate': continue        # a team's estimate is not a market rate to compare with
                    rate = _num(m.group('rate'))
                    if rate: out.append({'description': m.group('desc').strip(), 'unit': unit_key(m.group('unit')), 'rate': rate, 'date': m.group('date').strip(),
                                         'source': i['title'], 'kind': m.group('kind').strip()})
                agents.note('read', 'knowledge', i['id'], f'{member["role"]}: past rates')
    clients.log_withheld(rule_id, f'Digital team: {member["role"]} (past rates)', withheld)
    for n, h in enumerate(out, 1): h['hid'] = f'H{n}'
    return out[:400]


MARKET_PROMPT = '''{member}
Use web search to find CURRENT evidence of UK construction cost trends for the LOCATION: tender and building cost indices (inflation), regional
differences, and material and labour pressures. Every finding needs the exact URL of the page it comes from, the page's title and its date;
leave out anything you cannot cite. If the evidence supports adjusting this estimate for the market, suggest ONE adjustment as a percentage
of the construction cost (positive or negative) with your reasoning and the URLs it rests on; otherwise leave pct empty. You only suggest it:
the Lead QS accepts or rejects it, and Alice does the arithmetic.
Return JSON only, no prose:
{spec}'''
MARKET_SPEC = ('{"findings": [{"finding": "one sentence", "kind": "inflation|regional|materials|labour|other", "source_url": "", "source_title": "", '
               '"source_date": "YYYY-MM-DD or YYYY-MM"}], "adjustment": {"pct": null, "reasoning": "", "source_urls": []}, '
               '"commentary": "a short plain report of what the market evidence shows", "searches": ["the searches you ran"], "summary": "one sentence"}')


def _market(job, stage, member, ctx, location, cp):
    """Current cost trends for the location, from the member's own web search (switched on under Edit team): every finding cited with
    its date, and at most one suggested adjustment with its reasoning and cited sources (checked here; applied only if the Lead QS accepts)."""
    import assistants, org_research, rules_engine, rule_packs
    prov = member['provider'] if member.get('provider') in assistants.PROVIDERS else 'claude_sonnet'
    fam = assistants.family(prov)
    model = assistants.PROVIDERS[prov][0] if fam in org_research.KEYS else ''
    fam = fam if fam in org_research.KEYS else 'claude'
    target = f'Digital team: {member["role"]}'
    query = (f'JOB: {job["title"]}\nBRIEF\n{job["brief"][:3000]}\n\nLOCATION: {location or "not given: look at UK national trends"}\n'
             f'TODAY: {date.today().isoformat()}\nCONSTRUCTION COST OF THIS ESTIMATE (worked out by Alice): {_gbp(cp.get("construction"))}'
             + ('\n\nFEEDBACK TO ACT ON\n' + json.dumps(ctx['feedback'], ensure_ascii=False) if ctx.get('feedback') else ''))

    def query_for(p):
        rules_engine.check_outbound(query, target, provider=p)
        return rule_packs.live_check(query, p, target, packs=member['packs'])['text'] if member.get('packs') else query
    found = {'seen': {}, 'used': fam, 'failures': []}

    def search(system, _payload):
        rules_engine.check_spend('chat')
        meta = {}
        raw, seen, used, failures = org_research.search(system, query_for, fam, workload=target, model=model, max_tokens=teams.max_output(member), meta=meta)
        found['seen'].update(seen); found['used'], found['failures'] = used, failures
        if meta.get('truncated'): raise teams.CutOff(f'{member["role"]}\'s answer was cut off at the model\'s length limit.', raw=raw)
        return raw
    d = teams.ask_json(member, job, MARKET_PROMPT.format(member=teams.member_prompt(member, stage, ctx), spec=MARKET_SPEC), query, MARKET_SPEC,
                       'the market findings', call=search)
    seen_norm = {org_research._norm_url(u): (u, t) for u, t in found['seen'].items()}
    findings, dropped, cited = [], 0, set()
    for f in (d.get('findings') or [])[:20]:
        if not isinstance(f, dict): continue
        when = _date_ok(f.get('source_date'))
        hit = _cited(seen_norm, str(f.get('source_url') or '').strip(), when)
        text = teams._clean(f.get('finding'), 400)
        if not text or not hit: dropped += 1; continue                 # a finding counts only with a page the search returned and its date
        findings.append({'finding': text, 'kind': teams._clean(f.get('kind'), 20) or 'other', 'source_url': hit[0],
                         'source_title': teams._clean(f.get('source_title') or hit[1], 200), 'source_date': when})
        cited.add(hit[0])
    a = d.get('adjustment') if isinstance(d.get('adjustment'), dict) else {}
    pct, why = _num(a.get('pct')), teams._block(a.get('reasoning'), 1200)
    srcs = [hit[0] for u in a.get('source_urls') or [] for hit in [seen_norm.get(org_research._norm_url(str(u)))] if hit]
    adjustment, refused = None, ''
    if pct not in (None, 0):
        if not why: refused = 'no reasoning given'
        elif not srcs: refused = 'no source among the pages the search returned'
        elif not MARKET_RANGE[0] <= pct <= MARKET_RANGE[1]: refused = f'{pct:g}% is outside {MARKET_RANGE[0]:g}% to +{MARKET_RANGE[1]:g}%'
        else:
            adjustment = {'pct': round(pct, 1), 'reasoning': why, 'sources': list(dict.fromkeys(srcs))}
            cited.update(srcs)
    for u, t in found['seen'].items():
        agents.note('read', 'web', u, ((t or '')[:160] + ' · ' if t else '') + ('cited' if u in cited else 'returned by the search, not cited'))
    return {'location': location or 'UK (national)', 'findings': findings, 'dropped': dropped, 'adjustment': adjustment,
            'adjustment_refused': refused and {'pct': pct, 'reason': refused}, 'commentary': teams._block(d.get('commentary'), 3000),
            'searches': [{'provider': org_research.PROVIDER_NAMES.get(found['used'], found['used']), 'queries': [teams._clean(q, 200) for q in d.get('searches') or []][:20],
                          'sources': [{'url': u, 'title': (t or '')[:200], 'cited': u in cited} for u, t in found['seen'].items()][:60],
                          'fallback': [x['text'] for x in found['failures']]}]}


def qs_trends(job, stage, member, ctx):
    asm = (ctx['outputs'] or {}).get('assemble') or {}
    if not ctx.get('must_accept') and not asm.get('cost_plan'):
        return {'accept': False, 'reasons': ['The cost plan was not handed on.'], 'summary': 'Sent back: no cost plan.'}
    outs = ctx['outputs'] or {}
    items = [i for i in (outs.get('price') or {}).get('items') or [] if i.get('rate') is not None]
    location = teams._clean(((outs.get('plan') or {}).get('location')) or job.get('location'), 120)
    market = _market(job, stage, member, ctx, location, asm.get('cost_plan') or {}) if teams.tool_on(member, 'web_search', 'qs_trends') else None
    past = history(job, member)
    rr = outs.get('_rerun') or {}
    before = (rr.get('previous') or {}).get('trends') or {}
    only = None                                                     # a re-run compares only the items priced again; the rest keep theirs
    if rr and before:
        only = set(rr.get('refs') or []) if rr.get('kind') == 'reprice' else set(((outs.get('measure') or {}).get('remeasured') or {}).get('refs') or [])
    every = items
    if only is not None: items = [i for i in items if i['ref'] in only]
    out = {'accept': True, 'reasons': [], 'summary': '', 'note': '', 'questions': [], 'what_changed': ''}
    comps, matched, report = [], set(), ''
    if past:                                   # the second check: rates used against past projects held in Alice
        imap = {i['ref']: i for i in items}
        hmap = {h['hid']: h for h in past}
        spec = ('{"matches": [{"ref": "Q1", "history": ["H1"], "note": ""}], "commentary": "a short plain report of what the comparison shows, no percentages", '
                '"summary": "one sentence", "note": ""}')

        def run(part, info):
            mine = [imap[r] for p in part for r in p['refs']]
            units = {i['unit'] for i in mine}
            old = [h for h in past if h['unit'] in units]          # this part's own sources: past rates in the same units
            cur = '\n'.join(f'{i["ref"]} | {i["description"]} | {i["unit"]} | {i["rate"]} | {i.get("source_date") or ""}' for i in mine)
            hist = '\n'.join(f'{h["hid"]} | {h["description"]} | {h["unit"]} | {h["rate"]} | {h["date"]} | {h["source"]}' for h in old) or '(none in these units)'
            extra = (f'ALL ELEMENTS OF THE ESTIMATE: {", ".join(dict.fromkeys(i["element"] for i in items))}\n'
                     f'THIS PART: compare ONLY these rates.\nRATES USED NOW (ref | description | unit | rate | date)\n{cur}\n\n'
                     f'PAST RATES HELD IN ALICE (id | description | unit | rate | date | source)\n{hist}')
            return _ask(job, member, ctx, stage, spec, extra=extra, include_docs=False, what='the list of comparisons')
        done, stats = teams.in_parts(job, stage, _item_pieces(items), run, _split_refs, batch=PRICE_ITEMS, extra={**_extra_key(ctx, member), 'history': len(past)},
                                     size=lambda p: len(p['refs']))
        out.update({k: v for k, v in _merge_common([d for _, d in done]).items() if k in ('note', 'questions', 'what_changed')})
        for part, d in done:
            refs = {x for p in part for x in p['refs']}
            for m in d.get('matches') or []:
                if not isinstance(m, dict) or str(m.get('ref')) not in refs or str(m['ref']) in matched: continue
                it = imap[str(m['ref'])]
                hs = [hmap[h] for h in m.get('history') or [] if h in hmap and hmap[h]['unit'] == it['unit']]
                if not hs: continue
                rows = [{'rate': h['rate'], 'date': h['date'], 'source': h['source'], 'difference_pct': pct_change(it['rate'], h['rate'])} for h in hs]
                avg = float((sum((Decimal(str(r['difference_pct'])) for r in rows), Decimal('0')) / len(rows)).quantize(Decimal('0.1'), ROUND_HALF_UP))
                comps.append({'ref': it['ref'], 'description': it['description'], 'unit': it['unit'], 'rate_now': it['rate'], 'date_now': it.get('source_date') or '',
                              'past': rows, 'average_difference_pct': avg, 'note': teams._clean(m.get('note'), 300)})
                matched.add(it['ref'])
        if only is not None:
            live = {i['ref'] for i in every}
            for c_ in before.get('comparisons') or []:
                if c_['ref'] not in only and c_['ref'] in live and c_['ref'] not in matched: comps.append(c_); matched.add(c_['ref'])
        order = {i['ref']: n for n, i in enumerate(every)}
        comps.sort(key=lambda c_: order[c_['ref']])
        report = teams._block('\n\n'.join(dict.fromkeys(teams._block(d.get('commentary'), 3000) for _, d in done if d.get('commentary'))), 3000)
        if not comps: report = (report + '\n\n' if report else '') + 'None of the rates used has a comparable past rate (same unit and kind of work) in Alice.'
        out['parts'] = stats
    else:
        report = ('There are no past cost plans or team jobs in Alice to compare these rates with. This estimate will be filed in Knowledge once '
                  'you sign it off, so later estimates can be compared with it.')
    if only is not None and past:
        report = (report + '\n\n' if report else '') + f'Only the items priced again were compared this time ({", ".join(sorted(only)) or "none"}); the others keep their comparison from the last version.'
    out['output'] = {'history': len(past), 'comparisons': comps, 'unmatched': [i['ref'] for i in every if i['ref'] not in matched], 'report': report,
                     'market': market}
    if market: out['searches'] = market['searches']
    bits = ([f'{len(market["findings"])} market finding{"s" if len(market["findings"]) != 1 else ""} for {market["location"]}'
             + (f', suggests a {market["adjustment"]["pct"]:+g}% market adjustment' if market['adjustment'] else '')] if market else [])
    bits.append(f'{len(comps)} of {len(every)} rates compared with past projects' if past else 'no past projects in Alice to compare with')
    out['summary'] = teams._clean('; '.join(bits), 300)
    out['note'] = out['note'] or (f'Please accept or reject the suggested {market["adjustment"]["pct"]:+g}% market adjustment.' if market and market['adjustment'] else '')
    return out


ADJUST_SPEC = '{"accept": true, "reason": "one or two sentences", "summary": "one sentence"}'


def qs_adjust(job, stage, member, ctx):
    """The Lead QS accepts or rejects the market adjustment the Market Trends QS suggested; Alice applies it (in code) only when accepted."""
    tr = (ctx['outputs'] or {}).get('trends') or {}
    adj = (tr.get('market') or {}).get('adjustment')
    if not adj:
        return {'accept': True, 'summary': 'No market adjustment was suggested.', 'output': {'decision': 'none', 'accepted': False, 'pct': 0.0}}
    cp = ((ctx['outputs'] or {}).get('assemble') or {}).get('cost_plan') or {}
    extra = ('SUGGESTED MARKET ADJUSTMENT (from the Market Trends QS)\n' + json.dumps({'pct': adj['pct'], 'reasoning': adj['reasoning'], 'sources': adj['sources'],
             'findings': (tr.get('market') or {}).get('findings') or []}, ensure_ascii=False)
             + f'\n\nCONSTRUCTION COST NOW (worked out by Alice): {_gbp(cp.get("construction"))}. Decide only whether to accept it; do not calculate anything.')
    d = _ask(job, member, ctx, stage, ADJUST_SPEC, extra=extra, include_docs=False, what='your decision on the market adjustment')
    ok = d.get('accept') is True
    reason = teams._clean(d.get('reason'), 400) or ('Accepted.' if ok else 'Rejected.')
    return {'accept': True, 'summary': teams._clean(d.get('summary'), 300) or f'{"Accepted" if ok else "Rejected"} the {adj["pct"]:+g}% market adjustment.',
            'output': {'decision': 'accepted' if ok else 'rejected', 'accepted': ok, 'pct': adj['pct'] if ok else 0.0, 'suggested_pct': adj['pct'],
                       'reason': reason, 'by': member['role'], 'sources': adj['sources']}}


def final_plan(outs, settings=None):
    """The cost plan as it stands: the assembled figures, with the market adjustment applied (in code) only if the Lead QS accepted it."""
    price, asm, a = outs.get('price') or {}, outs.get('assemble') or {}, outs.get('adjust') or {}
    factor = (price.get('location') or {}).get('factor', 1.0)
    cp = asm.get('cost_plan') or compute(price.get('items') or [], factor, settings)
    if a.get('accepted') and a.get('pct'):
        cp = compute(price.get('items') or [], factor, cp.get('percentages') or settings, a['pct'])
    return cp


teams.PART_LABELS.update({'qs_measure': ('Measuring', 'element'), 'qs_price': ('Pricing', 'element'), 'qs_trends': ('Comparing', 'element')})
teams.HANDLERS.update({'qs_plan': qs_plan, 'qs_measure': qs_measure, 'qs_price': qs_price, 'qs_assemble': qs_assemble, 'qs_trends': qs_trends,
                       'qs_adjust': qs_adjust})
teams.TOOL_DEFAULTS.update({'qs_price': {'web_search': True}, 'qs_trends': {'web_search': False}})   # a member never set keeps how it worked before


# ---------------- outputs ----------------
def _gbp(x):
    return '' if x is None else f'£{x:,.2f}'


def _md(job, out):
    plan_o, price, asm, tr = out.get('plan') or {}, out.get('price') or {}, out.get('assemble') or {}, out.get('trends') or {}
    cp = final_plan(out)
    items = price.get('items') or []
    md = [f'**{DRAFT_MARK}**', '', f'Job {teams.ref(job["id"])} · prepared {date.today().strftime("%d %B %Y")}' + (f' · {job["location"]}' if job.get('location') else ''), '',
          '# Summary', asm.get('summary') or '', '', '# Cost summary',
          '| Element | Subtotal |', '|---|---|'] + [f'| {e["element"]} | {_gbp(e["subtotal"])} |' for e in cp['elements']] + [
          f'| Construction subtotal | {_gbp(cp["construction"])} |'] + ([f'| Market adjustment ({cp["market_pct"]:+g}%, accepted by the Lead QS) | {_gbp(cp["market_adjustment"])} |']
                                                                      if cp.get('market_adjustment') else []) + [f'| Preliminaries ({cp["percentages"]["prelims_pct"]}%) | {_gbp(cp["prelims"])} |',
          f'| Contingency ({cp["percentages"]["contingency_pct"]}%) | {_gbp(cp["contingency"])} |', f'| Fees ({cp["percentages"]["fees_pct"]}%) | {_gbp(cp["fees"])} |',
          f'| **Total (excluding VAT)** | **{_gbp(cp["total"])}** |', '', estimated_line(cp), '', (price.get('location') or {}).get('note', ''), '', '# Measured and priced items',
          '| Ref | Element | Description | Qty | Unit | Rate | Amount | Rate source |', '|---|---|---|---|---|---|---|---|']
    amounts = {l['ref']: l['amount'] for l in cp['lines']}
    for i in items:
        md.append(f'| {i["ref"]} | {i["element"]} | {i["description"]}{" (approx.)" if i.get("approximate") else ""} | {i["quantity"]:g} | {i["unit"]} | '
                  f'{_gbp(i.get("rate"))} | {_gbp(amounts.get(i["ref"]))} | {SOURCE_LABELS[i["rate_source"]]} |')
    md += ['', '# Where each rate came from']
    for i in items:
        if i['rate_source'] == 'web': md.append(f'- {i["ref"]}: {i.get("source_title") or ""}, {i["source_url"]} (dated {i["source_date"]})')
        elif i['rate_source'] == 'library': md.append(f'- {i["ref"]}: your rate library, “{i["library_row"]["description"]}” ({i["library_row"]["source"]}{", " + i["library_row"]["as_of"] if i["library_row"]["as_of"] else ""})')
        elif i['rate_source'] == 'yours': md.append(f'- {i["ref"]}: your rate, entered by {(i.get("decision") or {}).get("by", "you")} on {i.get("source_date") or ""}')
        elif i['rate_source'] == 'built_up':
            md.append(f'- {i["ref"]}: built up by Alice from cited published rates: ' + '; '.join(
                f'{w["description"]} {w["quantity_per_unit"]:g} × {_gbp(w["rate"])} = {_gbp(w["amount"])} ({w["source_url"]}, dated {w["source_date"]})' for w in i['working'])
                      + f'; total {_gbp(i["rate"])} per {i["unit"]}')
        elif i['rate_source'] == 'estimate':
            e = i.get('estimate') or {}
            md.append(f'- {i["ref"]}: ESTIMATE by the team (professional judgement), {_gbp(i["rate"])} per {i["unit"]}. {e.get("reasoning", "")}'
                      + (f' Comparables: {"; ".join(_gbp(c_["rate"]) + " " + c_["source_url"] + " (" + c_["source_date"] + ")" for c_ in e["comparables"])}.' if e.get('comparables') else ''))
        else: md.append(f'- {i["ref"]}: unpriced. {i.get("rate_note", "")}')
    md += ['', '# Where each quantity came from'] + [f'- {i["ref"]}: {i["source_text"]}' + (' (from a drawing: approximate)' if i.get('approximate') else '') for i in items]
    md += ['', '# Assumptions'] + [f'- {a}' for a in asm.get('assumptions') or []]
    md += ['', '# Exclusions'] + [f'- {a}' for a in asm.get('exclusions') or []]
    md += ['', '# Risks'] + [f'- {r["risk"]}' + (f' Mitigation: {r["mitigation"]}' if r.get('mitigation') else '') for r in asm.get('risks') or []]
    md += ['', '# Market trends']
    mk = tr.get('market') or {}
    if mk:
        md += [f'Current market evidence for {mk.get("location")}:'] + [f'- {f["finding"]} ({f["source_title"] or f["source_url"]}, {f["source_url"]}, dated {f["source_date"]})'
                                                                       for f in mk.get('findings') or []]
        if mk.get('commentary'): md += ['', mk['commentary']]
        adj = out.get('adjust') or {}
        if mk.get('adjustment'):
            md.append(f'Suggested market adjustment: {mk["adjustment"]["pct"]:+g}%. {mk["adjustment"]["reasoning"]} Sources: {", ".join(mk["adjustment"]["sources"])}. '
                      + (f'{adj.get("by", "The Lead QS")} {"accepted it" if adj.get("accepted") else "rejected it"}: {adj.get("reason", "")}' if adj.get('decision') in ('accepted', 'rejected')
                         else 'Not applied: no decision by the Lead QS.'))
        md.append('')
    md += ['Compared with past projects held in Alice:', tr.get('report') or '']
    for cmp_ in tr.get('comparisons') or []:
        md.append(f'- {cmp_["ref"]} {cmp_["description"]}: {_gbp(cmp_["rate_now"])} now; ' + '; '.join(f'{_gbp(p["rate"])} ({p["date"]}, {p["source"]}): {p["difference_pct"]:+.1f}%' for p in cmp_['past']))
    if plan_o.get('plan'): md += ['', '# How the team approached it', plan_o['plan']]
    md += ['', f'*{DRAFT_MARK}. All arithmetic was done by Alice from the team\'s structured answers. Rates without a source are not used; '
               'team estimates are marked ESTIMATE and listed as assumptions.*']
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
        {'name': 'Read me', 'rows': [[DRAFT_MARK], [f'Job {teams.ref(job["id"])}: {job["title"]}' + (f' (version v{job.get("version") or 1})' if (job.get('version') or 1) > 1 else '')], [f'Prepared {date.today().isoformat()} by the {team["name"]} team in Alice (team version v{job["team_version"]}).'],
                                      ['All arithmetic is done by Alice. Every rate has a source: a published web page with its date, your rate library, or it is unpriced and excluded.']]},
        {'name': 'Cost plan', 'rows': [['Ref', 'Element', 'Description', 'Quantity', 'Unit', 'Approximate', 'Rate (GBP)', 'Amount (GBP)', 'Rate source', 'Source', 'Source date']]
         + [[i['ref'], i['element'], i['description'], i['quantity'], i['unit'], 'Yes' if i.get('approximate') else '', i.get('rate'), amounts.get(i['ref']),
             SOURCE_LABELS[i['rate_source']], i.get('source_url') or (i.get('library_row') or {}).get('source')
             or '; '.join(w['source_url'] for w in i.get('working') or []) or (i.get('estimate') or {}).get('reasoning') or i.get('rate_note', ''),
             i.get('source_date', '')] for i in items]},
        {'name': 'Summary', 'rows': [['Line', 'GBP']] + [[e['element'], e['subtotal']] for e in cp['elements']]
         + [['Construction subtotal', cp['construction']], [f'Preliminaries {cp["percentages"]["prelims_pct"]}%', cp['prelims']],
            [f'Contingency {cp["percentages"]["contingency_pct"]}%', cp['contingency']], [f'Fees {cp["percentages"]["fees_pct"]}%', cp['fees']],
            ['Market adjustment (accepted by the Lead QS)', cp.get('market_adjustment', 0.0)],
            ['Total excluding VAT', cp['total']], ['From team estimates (construction)', cp.get('estimated', 0.0)],
            ['Share of construction from team estimates %', cp.get('estimated_pct', 0.0)], ['Regional factor applied', cp['factor']], [(price.get('location') or {}).get('note', ''), '']]},
        {'name': 'Quantities', 'rows': [['Ref', 'Description', 'Quantity', 'Unit', 'Document', 'Page', 'Line', 'From a drawing']]
         + [[i['ref'], i['description'], i['quantity'], i['unit'], i['source']['document'], i['source']['page'], i['source']['line'], 'Yes' if i.get('approximate') else ''] for i in items]},
        {'name': 'Market trends', 'rows': [['Ref', 'Description', 'Unit', 'Rate now', 'Past rate', 'Past date', 'Past source', 'Difference %']]
         + [[c_['ref'], c_['description'], c_['unit'], c_['rate_now'], p['rate'], p['date'], p['source'], p['difference_pct']] for c_ in tr.get('comparisons') or [] for p in c_['past']]
         + [[tr.get('report') or '']]
         + [['Market finding', f['finding'], f['kind'], '', '', f['source_date'], f['source_url'], ''] for f in (tr.get('market') or {}).get('findings') or []]},
        {'name': 'Assumptions', 'rows': [['Type', 'Text']] + [['Assumption', a] for a in asm.get('assumptions') or []] + [['Exclusion', a] for a in asm.get('exclusions') or []]
         + [['Risk', r['risk'] + (' Mitigation: ' + r['mitigation'] if r.get('mitigation') else '')] for r in asm.get('risks') or []]},
    ]
    ver = job.get('version') or 1
    title = f'Cost plan - {job["title"]}' + (f' v{ver}' if ver > 1 else '') + ' (draft)'
    rules_engine.check_file(md, title)
    word = documents.to_docx(title, md)
    xlsx = documents.to_xlsx(title, sheets)
    docs = [documents.keep('docx', documents._slug(title, '.docx'), word, md),
            documents.keep('xlsx', documents._slug(title, '.xlsx'), xlsx, md)]
    for d in docs: agents.note('wrote', 'document', d['id'], d['name'])
    import pricing_templates                                  # the job's own pricing template, filled from the same items and figures
    tf = pricing_templates.refill(job, team)
    if tf.get('document'): docs.append({**tf['document'], 'kind': 'Excel', 'template': True})
    n = {k: sum(1 for i in items if i['rate_source'] == k) for k in SUMMARY_WORDS}
    summary = (f'Estimated total {_gbp(cp["total"])} excluding VAT ({_gbp(cp["construction"])} construction, preliminaries {cp["percentages"]["prelims_pct"]}%, '
               f'contingency {cp["percentages"]["contingency_pct"]}%, fees {cp["percentages"]["fees_pct"]}%). '
               + ', '.join(f'{n[k]} {SUMMARY_WORDS[k]}' for k in SUMMARY_WORDS if n[k] or k in ('web', 'unpriced')) + '. '
               + (estimated_line(cp) + ' ' if cp.get('estimated') else '') + f'{(price.get("location") or {}).get("note", "")} {DRAFT_MARK}.')
    return {'documents': [{'id': d['id'], 'name': d['name'], 'kind': d['kind'], **({'template': True} if d.get('template') else {})} for d in docs],
            'summary': summary + (f' {tf["message"]}' if tf.get('message') else ''), 'total': cp['total'],
            'template_fill': {k: v for k, v in tf.items() if k != 'document'}}


def _rate_lines(items):
    return ['RATE | ref | description | unit | rate | source type | source | date'] + [
        f'RATE | {i["ref"]} | {i["description"].replace("|", "/")} | {i["unit"]} | {i["rate"]} | {i["rate_source"]} | '
        f'{(i.get("source_url") or (i.get("library_row") or {}).get("source") or "; ".join(w["source_url"] for w in i.get("working") or [])).replace("|", "/")} | '
        f'{i.get("source_date") or ""}' for i in items if i.get('rate') is not None]


def summary_note(job, team_name):
    """The short summary a signed-off job is filed as: scope, location, date, the rates used with their sources (as RATE lines, so later
    estimates can compare with them), the total, and what was estimated or left unpriced; with a link back to the job. Figures from code."""
    outs = job['outputs']
    items = (outs.get('price') or {}).get('items') or []
    cp = final_plan(outs)
    adj = outs.get('adjust') or {}
    est = [i for i in items if i.get('rate_source') == 'estimate']
    unp = [i for i in items if i.get('rate_source') == 'unpriced']
    ver = job.get('version') or 1
    lines = [f'Signed-off cost plan from the {team_name} team, job {teams.ref(job["id"])}' + (f' v{ver}' if ver > 1 else '')
             + f': {teams.job_url(job["team_id"], job["id"])}', '',
             f'Scope: {teams._clean(job["brief"], 600)}', f'Location: {job.get("location") or (outs.get("plan") or {}).get("location") or "not given"}',
             f'Signed off: {date.today().isoformat()}',
             f'Total excluding VAT: {_gbp(cp["total"])} (construction {_gbp(cp["construction"])}; preliminaries {cp["percentages"]["prelims_pct"]}%, '
             f'contingency {cp["percentages"]["contingency_pct"]}%, fees {cp["percentages"]["fees_pct"]}%)'
             + (f'; market adjustment {cp["market_pct"]:+g}% accepted by {adj.get("by", "the Lead QS")}' if cp.get('market_adjustment') else '') + '.',
             estimated_line(cp) or 'No item was priced by a team estimate.',
             'Estimated: ' + ('; '.join(f'{i["ref"]} {i["description"]} ({_gbp(i["rate"])} per {i["unit"]}): {(i.get("estimate") or {}).get("reasoning", "")[:200]}' for i in est) or 'none') + '.',
             'Left unpriced: ' + ('; '.join(f'{i["ref"]} {i["description"]}' for i in unp) or 'none') + '.',
             f'{DRAFT_MARK}.', '', '# RATES USED'] + _rate_lines(items)
    return f'Cost plan summary: {job["title"]} ({teams.ref(job["id"])})', '\n'.join(lines)


def complete(job, team, jt):
    """After sign-off: the job is proposed to Knowledge through the usual checks and approval path, tagged to the job's client (so the
    client-documents rule keeps it out of other clients' jobs). With the team's "File finished work in" on and its category there, it is
    the short summary filed in that category (Temple may tag it, never re-categorise it); otherwise the full cost plan, as before."""
    import knowledge, autoapprove
    job = teams._row(job['id'])
    f = teams.filing(teams.get(job['team_id']))
    source = f'Digital team {team["name"]}, job {teams.ref(job["id"])}, signed off {date.today().isoformat()}'
    if f['on'] and f['exists']:
        title, text = summary_note(job, team['name'])
        r = knowledge.create('note', title, text, source, 'Digital team', status='draft', category=f['category'], client=job['client'] or '')
        filed = {'category': f['category'], 'knowledge_id': r['id']}
    else:
        md, cp = _md(job, job['outputs'])
        r = knowledge.create('note', f'Cost plan: {job["title"]} ({teams.ref(job["id"])})', md + '\n\n# RATES USED\n' + '\n'.join(_rate_lines((job['outputs'].get('price') or {}).get('items') or [])),
                             source, 'Digital team', status='draft', client=job['client'] or '')
        filed = {'category': '', 'knowledge_id': r['id'], 'not_filed': (f'“{f["category"]}” does not exist yet: create it on the team\'s Knowledge tab.' if f['on']
                                                                        else 'File finished work is off for this team.')}
    if not r.get('duplicate'): autoapprove.knowledge_draft(r['id'])
    outs = teams._row(job['id'])['outputs']
    outs['filed'] = filed
    teams._set(job['id'], outputs=outs)
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
        if i['rate_source'] == 'yours': return 'your rate'
        if i['rate_source'] == 'built_up': return 'built up: ' + '; '.join(f'{w["description"]} {w["quantity_per_unit"]:g} × {_gbp(w["rate"])}' for w in i.get('working') or [])
        if i['rate_source'] == 'estimate': return 'ESTIMATE: ' + (i.get('estimate') or {}).get('reasoning', '')[:300]
        return 'unpriced'
    lines = [f'{i["ref"]} {i["description"]}: {_gbp(i["rate"]) + " per " + i["unit"] if i.get("rate") is not None else "no rate"} ({src(i)})' for i in o.get('items') or []]
    return '\n'.join(lines + [(o.get('location') or {}).get('note', '')] + [c_['text'] for c_ in o.get('conflicts') or []])


def _describe_assemble(o):
    cp = o.get('cost_plan') or {}
    return '\n'.join([o.get('summary', ''), f'Total excluding VAT {_gbp(cp.get("total"))} (construction {_gbp(cp.get("construction"))}).',
                      'Assumptions: ' + '; '.join(o.get('assumptions') or []), 'Exclusions: ' + '; '.join(o.get('exclusions') or []),
                      'Risks: ' + '; '.join(r['risk'] for r in o.get('risks') or [])])


def _describe_trends(o):
    mk = o.get('market') or {}
    lines = [f'{f["finding"]} ({f["source_url"]}, {f["source_date"]})' for f in mk.get('findings') or []]
    if mk.get('adjustment'): lines.append(f'Suggests a {mk["adjustment"]["pct"]:+g}% market adjustment: {mk["adjustment"]["reasoning"]}')
    if mk.get('adjustment_refused'): lines.append(f'An adjustment was not passed on: {mk["adjustment_refused"]["reason"]}.')
    return '\n'.join(lines + [o.get('report', '')])


teams.DESCRIBERS.update({'plan': _describe_plan, 'measure': _describe_measure, 'price': _describe_price, 'assemble': _describe_assemble,
                         'trends': _describe_trends,
                         'adjust': lambda o: (f'{o.get("by", "The Lead QS")} {o["decision"]} the {o.get("suggested_pct", 0):+g}% market adjustment: {o.get("reason", "")}'
                                              if o.get('decision') in ('accepted', 'rejected') else 'No market adjustment was suggested.')})
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


# ---------------- the job page: unpriced items you decide, and the cost plan so far (Stefan, 7 Oct 2026) ----------------
# The badges on the job page, one per source (fixed: they protect the output, so an estimate is never shown as anything else).
VIEW_SOURCES = {'web': 'Published', 'library': 'Library', 'built_up': 'Built up', 'estimate': 'Estimate', 'yours': 'Your rate', 'unpriced': 'Unpriced',
                'to_price': 'Not priced yet'}


def undecided(outputs):
    """Unpriced items you have not decided on yet (enter a rate, or leave unpriced)."""
    items = ((outputs or {}).get('price') or {}).get('items') or []
    return [i for i in items if i.get('rate_source') == 'unpriced' and not i.get('decision')]


def _price_stage(jt):
    return next((s for s in jt['stages'] if s.get('handler') == 'qs_price'), None)


def job_view(d, team, jt):
    """For the job page: the decision panel (unpriced items while the job waits on you) and the cost plan so far: each item
    with its quantity, rate, where the rate came from and its amount (worked out here), and a total only once every item is
    priced or marked unpriced."""
    outs = d['outputs']
    members = {m['id']: m for m in team['members']}
    ps = _price_stage(jt)
    lead = (members.get(teams.lead_id(team)) or {}).get('role', 'The lead')
    pricer = (members.get(ps['member']) or {}).get('role', 'The Cost Surveyor') if ps else 'The Cost Surveyor'
    done = d['status'] == 'done'
    open_ = [] if done else undecided(outs)
    decision = None
    if open_ and d['status'] == 'waiting' and d['pending']:
        p = d['pending'][0]
        state = 'handoff' if p['kind'] == 'handoff' and ps and p['stage'] == ps['key'] else 'signoff' if p['kind'] == 'signoff' else 'other'
        import rules_engine
        allowed = [rules_engine.RATE_SOURCES[k].lower() for k in rules_engine.rate_sources()['allowed']]
        decision = {'lead': lead, 'pricer': pricer, 'step_id': p['id'], 'state': state, 'count': len(open_),
                    'title': f'{lead} needs a decision on {len(open_)} item{"s" if len(open_) != 1 else ""}',
                    'why': (f'{pricer} could not price these from the sources your rules allow ({", ".join(allowed) or "none"}). '
                            'Enter a rate for an item, leave it unpriced (excluded from the total and listed as an assumption), or ask the team to '
                            'estimate them: a team estimate is badged Estimate and listed as an assumption with its reasoning.'),
                    'can_estimate': state in ('handoff', 'signoff'), 'estimate_rule_on': 'estimate' in rules_engine.rate_sources()['allowed'] or estimates_on_job(outs),
                    'rule_href': '/admin/rules?rule=rate_sources#rules',
                    'items': [{'ref': i['ref'], 'element': i['element'], 'description': i['description'], 'quantity': i['quantity'], 'unit': i['unit'],
                               'approximate': bool(i.get('approximate'))} for i in open_]}
    price, measure = outs.get('price') or {}, outs.get('measure') or {}
    plan = None
    if price.get('items'):
        loc = price.get('location') or {}
        cp = final_plan(outs, team.get('settings'))
        amounts = {l['ref']: l['amount'] for l in cp['lines']}
        rows = []
        for i in price['items']:
            src = i.get('rate_source')
            lib = i.get('library_row') or {}
            rows.append({'ref': i['ref'], 'element': i['element'], 'description': i['description'], 'quantity': i['quantity'], 'unit': i['unit'],
                         'approximate': bool(i.get('approximate')), 'rate': i.get('rate'), 'source': src, 'source_label': VIEW_SOURCES.get(src, src),
                         'source_url': i.get('source_url') if src == 'web' else '', 'source_title': i.get('source_title') or lib.get('source') or '',
                         'working': i.get('working') or None, 'estimate': i.get('estimate') or None,
                         'source_date': i.get('source_date') or '', 'note': i.get('rate_note') or '', 'amount': amounts.get(i['ref']),
                         'quantity_source': i.get('source_text') or '', 'decided_by': (i.get('decision') or {}).get('by', ''),
                         'undecided': src == 'unpriced' and not i.get('decision') and not done})
        n_open = sum(1 for r in rows if r['undecided'])
        plan = {'stage': 'price', 'rows': rows, 'counts': {k: sum(1 for r in rows if r['source'] == k) for k in VIEW_SOURCES if k != 'to_price'},
                'undecided': n_open, 'location_note': loc.get('note', ''), 'factor': cp.get('factor', 1.0),
                'totals': None if n_open else {k: cp.get(k, 0.0) for k in ('construction', 'prelims', 'contingency', 'fees', 'total', 'estimated', 'estimated_pct',
                                                                          'market_pct', 'market_adjustment')},
                'estimated_line': '' if n_open else estimated_line(cp),
                'elements': None if n_open else cp['elements'], 'percentages': cp.get('percentages'),
                'assembled': bool(outs.get('assemble')), 'labels': VIEW_SOURCES}
    elif measure.get('items'):
        rows = [{'ref': i['ref'], 'element': i['element'], 'description': i['description'], 'quantity': i['quantity'], 'unit': i['unit'],
                 'approximate': bool(i.get('approximate')), 'rate': None, 'source': 'to_price', 'source_label': VIEW_SOURCES['to_price'], 'source_url': '',
                 'source_title': '', 'source_date': '', 'note': '', 'amount': None, 'quantity_source': i.get('source_text') or '', 'decided_by': '',
                 'undecided': False} for i in measure['items']]
        plan = {'stage': 'measure', 'rows': rows, 'counts': {'to_price': len(rows)}, 'undecided': 0, 'location_note': '', 'totals': None,
                'elements': None, 'assembled': False, 'labels': VIEW_SOURCES}
    here = teams.job_url(d['team_id'], d['id'])
    conflicts = [] if done else [dict(c_, links=[dict(l, href=here + l['href'] if l['href'].startswith('#') else l['href']) for l in c_.get('links') or []])
                                 for c_ in price.get('conflicts') or []]
    return {'decision': decision, 'plan': plan, 'documents': outs.get('documents') or [], 'conflicts': conflicts, 'lead': lead,
            'estimates': (outs.get('_estimates') or {}).get('refs') or []}


def ask_estimates(jid, refs, note=''):
    """Ask the team to estimate these (Stefan, 8 Oct 2026): allows a team estimate for the chosen unpriced items on THIS job only, whatever
    the rate-source rule says; sends them back to the Cost Surveyor (only those items are priced again), then the Lead QS assembles the
    cost plan again with them listed as estimates, and it comes back for sign-off. Recorded in the job's history with who asked."""
    import rules_engine
    j = teams._row(jid)
    if j['status'] != 'waiting': raise ValueError('The team is working on this job: wait until it needs you.')
    team, jt = teams._job_team(j)
    ps = _price_stage(jt)
    if not ps: raise ValueError('This job has no pricing stage.')
    outs = j['outputs']
    open_ = {i['ref']: i for i in undecided(outs)}
    refs = [r for r in dict.fromkeys(str(x) for x in refs or []) if r]
    if not refs: refs = list(open_)
    bad = [r for r in refs if r not in open_]
    if bad: raise ValueError(f'{", ".join(bad)}: not an unpriced item waiting for a decision.')
    if not refs: raise ValueError('No unpriced items are waiting for a decision.')
    note = teams._block(note, 1000)
    if note: rules_engine.check_outbound(note, 'Digital team note', packs=False)
    p = next((s_ for s_ in teams._steps(jid) if s_['status'] == 'pending'), None)
    if not p or p['kind'] not in ('handoff', 'signoff') or (p['kind'] == 'handoff' and p['stage'] != ps['key']):
        raise ValueError('Estimates can be asked for when the pricing is handed on, or at sign-off.')
    who = teams._actor()
    keys = [s_['key'] for s_ in jt['stages']]
    i = keys.index(ps['key'])
    allow = outs.get('_estimates') or {'refs': []}
    allow = {'refs': list(dict.fromkeys(allow['refs'] + refs)), 'by': who, 'at': store.now()}
    outs['_estimates'] = allow
    outs['price']['estimate_pass'] = refs
    for k in keys[i + 1:] + ['_finished', 'documents', 'summary', 'total']: outs.pop(k, None)
    msg = (f'Estimate {", ".join(refs)}: no allowed source priced {"them" if len(refs) != 1 else "it"}, so give your professional judgement of the rate '
           'with your reasoning, the assumptions you make and any comparable rates you find, cited.' + (f' {note}' if note else ''))
    with store.db() as c:
        c.execute("UPDATE team_steps SET status='sent_back', stage=?, decided_at=?, decided_by=?, decision_note=? WHERE id=? AND status='pending'",
                  (ps['key'], store.now(), who, msg, p['id']))
        store.audit(c, 'team_estimates_asked', jid, 'human_review', f'{teams.ref(jid)} {j["title"]}: estimates allowed on this job for {", ".join(refs)}')
    pm = next((m for m in team['members'] if m['id'] == ps['member']), {})
    teams._add_step(jid, 'estimates', ps['key'], 'stefan', to_member=ps['member'], status='done',
                    note=f'You asked {pm.get("role", "the Cost Surveyor")} to estimate {", ".join(refs)} (allowed on this job only).' + (f' Your note: {note}' if note else ''),
                    content={'by': who, 'refs': refs, 'note': note})
    teams._set(jid, status='running', error='', stage=i, outputs=outs)
    teams.kick(jid)
    return teams.job_detail(jid)


# ---------------- Re-price and Re-measure: a new version of the job (Stefan, 8 Oct 2026) ----------------
def _rerun_ready(jid):
    """The job and its team for a re-run: only when the team is not working on it (waiting for you, stopped by a failure or by you,
    or signed off). A stopped job re-runs as a new version like any other (Stefan, 9 Oct 2026)."""
    j = teams._row(jid)
    if j['status'] == 'running' or jid in teams._ACTIVE: raise ValueError('The team is working on this job: wait until it needs you or is signed off.')
    team, jt = teams._job_team(j)
    return j, team, jt


def _clean_order(order):
    import rules_engine
    if not order: return None
    out = list(dict.fromkeys(str(k) for k in order if str(k) in rules_engine.RATE_SOURCES))
    if not out: raise ValueError('Choose the order of the rate sources from published, library, built up and estimate.')
    return out


def _restart(jid, j, jt, kind, stage_key, rerun, what, note, refs=None, elements=None, clear=()):
    """New version, the work in `clear` removed (stages kept from the last version carried instead), pending decisions withdrawn,
    the request in the job's history, and the team set going from `stage_key`."""
    import rules_engine
    note = teams._block(note, 1000)
    if note: rules_engine.check_outbound(note, 'Digital team note', packs=False)
    what = what[:1].upper() + what[1:]
    keys = [s_['key'] for s_ in jt['stages']]
    i = keys.index(stage_key)
    v = teams.new_version(jid, kind, what, note)
    outs = teams._row(jid)['outputs']
    carry = {k: outs[k] for k in rerun.pop('keep', []) if k in outs}
    rerun.update({'kind': kind, 'version': v, 'from_version': v - 1, 'by': teams._actor(), 'note': note, 'carry': carry})
    for k in list(clear) + list(carry) + ['_finished', 'documents', 'summary', 'total', 'filed', '_parts']: outs.pop(k, None)
    if isinstance(outs.get('price'), dict): outs['price'].pop('estimate_pass', None)
    outs['_rerun'] = rerun
    who = teams._actor()
    with store.db() as c:
        c.execute("UPDATE team_steps SET status='withdrawn', decided_at=?, decided_by=?, decision_note=? WHERE job_id=? AND status='pending'",
                  (store.now(), who, f'Replaced by v{v} ({VERSION_WORD[kind]}).', jid))
        store.audit(c, f'team_job_{kind}', jid, 'human_review', f'{teams.ref(jid)} {j["title"]}: v{v}, {what}' + (f' · {note[:200]}' if note else ''))
    stage = jt['stages'][i]
    teams._add_step(jid, kind, stage_key, 'stefan', to_member=stage['member'], status='done',
                    note=f'You asked for v{v}: {what}' + (f' Your note: {note}' if note else ''),
                    content={'by': who, 'version': v, 'refs': refs or [], 'elements': elements or [], 'note': note,
                             'order': rerun.get('order'), 'estimates': rerun.get('estimates', False), 'trends': rerun.get('trends', False)})
    teams._set(jid, status='running', error='', holder='', stage=i, outputs=outs)
    teams.kick(jid)
    return teams.job_detail(jid)


VERSION_WORD = {'reprice': 'a re-price', 'remeasure': 'a re-measure'}


def _stage_of(jt, handler):
    return next((s_ for s_ in jt['stages'] if s_.get('handler') == handler), None)


def reprice(jid, refs=None, estimates=False, order=None, trends=False, note=''):
    """Re-price a job (waiting, stopped, or signed off) as a new version: only the Cost Surveyor works again, on the chosen
    items (default: every unpriced and estimated item), keeping the measured quantities and every other item's price; Market Trends
    again only if asked; then the Lead QS reassembles the cost plan and it comes back for sign-off. `estimates` allows team estimates
    for these items on this re-run; `order` is a different order of the rate sources for this re-run (what is allowed stays the rule's)."""
    j, team, jt = _rerun_ready(jid)
    ps = _price_stage(jt)
    if not ps: raise ValueError('This job has no pricing stage.')
    outs = j['outputs']
    items = (outs.get('price') or {}).get('items') or []
    if not items: raise ValueError('Nothing has been priced on this job yet.')
    have = [i['ref'] for i in items]
    refs = [r for r in dict.fromkeys(str(x) for x in refs or []) if r]
    if not refs: refs = [i['ref'] for i in items if i.get('rate_source') in ('unpriced', 'estimate')]
    if not refs: raise ValueError('Every item has a rate that is not an estimate: choose the items to re-price.')
    bad = [r for r in refs if r not in have]
    if bad: raise ValueError(f'{", ".join(bad)}: not an item on this job.')
    order = _clean_order(order)
    ts, ad = _stage_of(jt, 'qs_trends'), _stage_of(jt, 'qs_adjust')
    keep = [x['key'] for x in (ts, ad) if x] if not trends else []
    rerun = {'refs': refs, 'order': order, 'estimates': bool(estimates), 'trends': bool(trends) and bool(ts), 'keep': keep,
             'previous': {'price': outs.get('price'), **({'trends': outs['trends']} if trends and outs.get('trends') else {})}}
    bits = [f're-price {", ".join(refs)}']
    if estimates: bits.append('team estimates allowed for them')
    if order: bits.append('rate sources in the order ' + ', '.join(order))
    if trends and ts: bits.append('Market Trends again')
    keys = [s_['key'] for s_ in jt['stages']]
    return _restart(jid, j, jt, 'reprice', ps['key'], rerun, '; '.join(bits) + '.', note, refs=refs, clear=keys[keys.index(ps['key']) + 1:])


def remeasure(jid, elements, estimates=False, order=None, trends=False, note=''):
    """Re-measure chosen elements as a new version: the Measurement Surveyor takes them off again (the other elements' items are kept),
    the Cost Surveyor prices only the items measured again, then the cost plan is reassembled and comes back for sign-off."""
    j, team, jt = _rerun_ready(jid)
    ms, ps = _stage_of(jt, 'qs_measure'), _price_stage(jt)
    if not ms or not ps: raise ValueError('This job has no measuring stage.')
    outs = j['outputs']
    plan = outs.get('plan') or {}
    have = plan.get('elements') or []
    elements = [e for e in dict.fromkeys(teams._clean(x, 80) for x in elements or []) if e]
    if not elements: raise ValueError('Choose the elements to re-measure.')
    bad = [e for e in elements if e not in have]
    if bad: raise ValueError(f'{", ".join(bad)}: not an element in the plan.')
    if not (outs.get('measure') or {}).get('items'): raise ValueError('Nothing has been measured on this job yet.')
    order = _clean_order(order)
    ts, ad = _stage_of(jt, 'qs_trends'), _stage_of(jt, 'qs_adjust')
    keep = [x['key'] for x in (ts, ad) if x] if not trends else []
    rerun = {'elements': elements, 'order': order, 'estimates': bool(estimates), 'trends': bool(trends) and bool(ts), 'keep': keep,
             'previous': {'measure': outs.get('measure'), 'price': outs.get('price'), **({'trends': outs['trends']} if trends and outs.get('trends') else {})}}
    bits = [f're-measure {", ".join(elements)}, then price the items measured again']
    if estimates: bits.append('team estimates allowed for them')
    if order: bits.append('rate sources in the order ' + ', '.join(order))
    if trends and ts: bits.append('Market Trends again')
    keys = [s_['key'] for s_ in jt['stages']]
    return _restart(jid, j, jt, 'remeasure', ms['key'], rerun, '; '.join(bits) + '.', note, elements=elements, clear=keys[keys.index(ms['key']):])


def decide_rates(jid, entries, save_to_library=True, go_on=False):
    """Your decision on unpriced items: a rate you enter (recorded as yours, source "Your rate", in the job's history, and saved to
    the team's rate library through its usual checks when save_to_library is on), or leave unpriced. Arithmetic is redone here.
    go_on: when the job waits on the hand-off out of the pricing stage, approve it once your rates are in."""
    j = teams._row(jid)
    if j['status'] in ('done', 'stopped'): raise ValueError('This job has finished.')
    team, jt = teams._job_team(j)
    outs = j['outputs']
    price = outs.get('price') or {}
    items = price.get('items') or []
    open_ = {i['ref']: i for i in undecided(outs)}
    if not open_: raise ValueError('No unpriced items are waiting for a decision.')
    rates, leave = {}, []
    for e in entries or []:
        r = str(e.get('ref') or '')
        if r not in open_: raise ValueError(f'{r or "An item"} is not an unpriced item waiting for a decision.')
        if e.get('unpriced'): leave.append(r); continue
        if e.get('rate') in (None, ''): continue
        v = _num(e.get('rate'))
        if v is None or not 0 < v < 10_000_000: raise ValueError(f'{r}: give a rate above zero in pounds per {open_[r]["unit"]}.')
        rates[r] = float(money(v))
    if not rates and not leave: raise ValueError('Enter a rate, or tick Leave unpriced, for at least one item.')
    who, now, today = teams._actor(), store.now(), date.today().isoformat()
    saved = 0
    if rates and save_to_library:                         # through the rate library's own import and checks; a refusal changes nothing
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Description', 'Unit', 'Rate', 'As of', 'Source'])
        for r, v in rates.items(): w.writerow([open_[r]['description'], open_[r]['unit'], v, today, f'Your rate ({teams.ref(jid)})'])
        saved = import_rates(j['team_id'], f'{teams.ref(jid)} rates.csv', buf.getvalue().encode('utf-8'), f'Your rates from {teams.ref(jid)}')['added']
    for i in items:
        if i['ref'] in rates:
            i.update({'rate': rates[i['ref']], 'rate_source': 'yours', 'source_title': 'Your rate', 'source_date': today,
                      'rate_note': f'Entered by {who}' + (' and saved to the rate library' if saved else ''), 'decision': {'by': who, 'at': now, 'action': 'rate'}})
        elif i['ref'] in leave:
            i.update({'rate_note': f'Left unpriced by {who}', 'decision': {'by': who, 'at': now, 'action': 'unpriced'}})
    outs['price'] = price
    asm = outs.get('assemble')
    if asm:                                               # already assembled: the cost plan is recalculated in code
        asm['cost_plan'] = compute(items, (price.get('location') or {}).get('factor', 1.0), team.get('settings'))
        priced = {f'{r} ' for r in rates}
        asm['assumptions'] = [a for a in asm.get('assumptions') or [] if not (any(a.startswith(p) for p in priced) and ': unpriced' in a)]
        for i in items:
            if i['ref'] in leave:
                asm['assumptions'] = [a for a in asm['assumptions'] if not (a.startswith(i['ref'] + ' ') and 'unpriced' in a)]
                asm['assumptions'].insert(0, f'{i["ref"]} {i["description"]}: left unpriced by {who}; excluded from the total.')
    rebuild = bool(outs.pop('_finished', None))
    if rebuild: outs.pop('documents', None)
    teams._set(jid, outputs=outs)
    if rebuild and teams.FINISHERS.get(jt.get('finish') or ''):        # the Word and Excel documents follow the new figures
        new = teams.FINISHERS[jt['finish']](teams._row(jid), team, jt) or {}
        outs = teams._row(jid)['outputs']
        outs.update(new)
        outs['_finished'] = True
        teams._set(jid, outputs=outs)
        with store.db() as c:
            for r in c.execute("SELECT id, content FROM team_steps WHERE job_id=? AND kind='signoff' AND status='pending'", (jid,)).fetchall():
                content = json.loads(r[1] or '{}')
                content['summary'] = (outs.get('summary') or '')[:600]
                c.execute('UPDATE team_steps SET content=? WHERE id=?', (json.dumps(content, ensure_ascii=False), r[0]))
    parts = [f'{len(rates)} rate{"s" if len(rates) != 1 else ""} entered as Your rate ({", ".join(f"{r} £{v:,.2f}" for r, v in rates.items())})'] if rates else []
    if leave: parts.append(f'{len(leave)} left unpriced ({", ".join(leave)})')
    if saved: parts.append(f'{saved} saved to the rate library')
    note = '; '.join(parts) + '.'
    ps = _price_stage(jt)
    sid = teams._add_step(jid, 'rates', ps['key'] if ps else 'price', 'stefan', status='done', note=note,
                          content={'by': who, 'rates': [{'ref': r, 'description': open_[r]['description'], 'unit': open_[r]['unit'], 'rate': v} for r, v in rates.items()],
                                   'unpriced': leave, 'saved_to_library': saved})
    with store.db() as c:
        c.execute('UPDATE team_steps SET decided_at=?, decided_by=? WHERE id=?', (now, who, sid))
        store.audit(c, 'team_rates_decided', jid, 'human_review', f'{teams.ref(jid)} {j["title"]}: {note}')
    if go_on:
        p = next((s for s in teams._steps(jid) if s['status'] == 'pending'), None)
        if p and p['kind'] == 'handoff' and ps and p['stage'] == ps['key']:
            return teams.decide(p['id'], 'approve')
    return teams.job_detail(jid)


def _template():
    return {'name': 'Quantity surveying', 'description': 'A small QS team that produces an early cost estimate (cost plan) from a brief, a specification, '
            'schedules and drawings. Every rate has a source; the arithmetic is done by Alice.', 'discipline': 'Quantity surveying', 'colour': 'teal',
            'icon': 'calculator', 'autonomy': 'approve', 'members': MEMBERS, 'settings': SETTINGS, 'filing': TEMPLATE_FILING,
            'job_types': [{'id': 'cost-estimate', 'name': 'Cost estimate', 'finish': 'cost_estimate', 'client_facing': True,
                           'description': 'From brief to a draft cost plan (Word and Excel) and a Market Trends report.', 'stages': STAGES}]}


def _talk_rules(team, job):
    import rules_engine
    rs = rules_engine.rate_sources()
    allow = sorted(estimates_allowed((job or {}).get('outputs'))) if job else []
    return {'rate_sources': f'Rates may come from, in this order: {", ".join(rules_engine.RATE_SOURCES[k] for k in rs["allowed"]) or "nothing"}; '
                            f'not allowed: {", ".join(rules_engine.RATE_SOURCES[k] for k in rs["order"] if k not in rs["allowed"]) or "nothing"}.'
                            + (f' On this job Stefan has allowed estimates for {", ".join(allow)}.' if allow else '')
                            + (' Stefan has allowed team estimates for every item on this job.' if job and estimates_on_job(job.get('outputs')) else '')}


teams.TALK_RULES['qs_price'] = _talk_rules
teams.JOB_VIEWS['cost_estimate'] = job_view
teams.UNDECIDED['cost_estimate'] = undecided
teams.PRICING['qs_price'] = lambda: {'order': price_rules(), 'note': PRICE_NOTE, 'rules': ['rate_sources', 'commercial_caution']}
teams.TEMPLATES['quantity-surveying'] = _template
teams.HANDLER_TOOLS.update({'qs_price': ['Web search', 'Rate library'], 'qs_trends': ['Past rates held in Alice']})


seed()
