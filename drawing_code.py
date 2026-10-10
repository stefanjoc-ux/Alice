"""Reading a drawing page in code first (10 Oct 2026; D-0049: code first, then a model only for what code cannot read).

From a PDF page's own text layer and its drawn lines (pypdf; nothing rendered, no model, no new package):
- every piece of text with where it sits on the page: a 3 x 3 grid of areas, columns A to C from left to right and rows 1 to 3
  from top to bottom (A1 = top left, B2 = centre, C3 = bottom right), so every reading and every quantity can cite page and area;
- the scale: from a scale bar (a straight line with "0" at one end and a length such as "5 m" at the other) when there is one,
  else from a written ratio such as "1:100"; a written ratio names the paper it was drawn for ("at A1"), and when the page is not
  that size the ratio is not used (the scale bar still is);
- dimensions as written, each with the line it labels measured at that scale, and whether the two agree;
- closed rectangles (room outlines) with their width, length and area at the scale, named by the text inside them;
- the areas with drawn content but no text, which code cannot read: those, or the whole page when it has no text at all (a scan),
  are what a vision model is asked to read (team_files), cropped to those areas.
All arithmetic is here, in Decimal. Only PDFs: an image file has no text layer, and cropping one needs an imaging package Alice does
not have, so an image is read whole by the vision model.
"""
import io
import re
from decimal import Decimal, ROUND_HALF_UP

GRID = 3
COLS = 'ABC'
AREA_WORDS = {'A1': 'top left', 'B1': 'top centre', 'C1': 'top right', 'A2': 'centre left', 'B2': 'centre', 'C2': 'centre right',
              'A3': 'bottom left', 'B3': 'bottom centre', 'C3': 'bottom right'}
PT_M = Decimal('0.0254') / Decimal('72')          # one PDF point on paper, in metres
PAPER_MM = {'A0': (841, 1189), 'A1': (594, 841), 'A2': (420, 594), 'A3': (297, 420), 'A4': (210, 297)}
AGREE = Decimal('0.02')                           # a written dimension and its drawn line agree within 2%
NEAR = 18                                         # points: how close a label must be to the line or bar end it belongs to
MIN_ROOM_M2 = Decimal('1')                        # smaller rectangles are symbols, not rooms

RATIO = re.compile(r'\b1\s*:\s*(\d{1,5})\b(?:\s*(?:at|@)\s*(A[0-4]))?', re.I)
LENGTH = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(m|mm)\s*$', re.I)
DIMENSION = re.compile(r'^\s*(\d{1,3}(?:[,\s]\d{3})+|\d+(?:\.\d+)?)\s*(mm|m)?\s*$', re.I)
DRAWING_NO = re.compile(r'\b(?:drawing|dwg)\s*(?:no\.?|number)?\s*[:#]?\s*([A-Z0-9][A-Z0-9_./-]{2,24})', re.I)


def _d(x):
    return Decimal(str(x))


def _q2(x):
    return x.quantize(Decimal('0.01'), ROUND_HALF_UP)


def area_of(x, y, box):
    """The grid area ('A1'..'C3') a point is in; box = (x0, y0, x1, y1) of the page, y up as in PDF."""
    x0, y0, x1, y1 = box
    col = min(GRID - 1, max(0, int((x - x0) / ((x1 - x0) / GRID))))
    row = min(GRID - 1, max(0, int((y1 - y) / ((y1 - y0) / GRID))))
    return f'{COLS[col]}{row + 1}'


def area_box(area, box):
    """The rectangle (x0, y0, x1, y1) of a grid area on the page."""
    x0, y0, x1, y1 = box
    col, row = COLS.index(area[0]), int(area[1]) - 1
    w, h = (x1 - x0) / GRID, (y1 - y0) / GRID
    return (x0 + col * w, y1 - (row + 1) * h, x0 + (col + 1) * w, y1 - row * h)


def _mul(a, b):
    """Two PDF matrices [a b c d e f]: a then b."""
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _pt(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def _paths(page):
    """Straight segments and rectangles drawn on the page (curves are skipped), in page coordinates."""
    segs, rects = [], []
    try: ops = page.get_contents().operations if page.get_contents() is not None else []
    except Exception: return segs, rects
    ctm, stack, cur, start, path = [1, 0, 0, 1, 0, 0], [], None, None, []
    for operands, op in ops:
        try: vals = [float(v) for v in operands] if op in (b'cm', b'm', b'l', b're', b'c', b'v', b'y') else []
        except (TypeError, ValueError): continue
        if op == b'q': stack.append(ctm)
        elif op == b'Q': ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
        elif op == b'cm' and len(vals) == 6: ctm = _mul(vals, ctm)
        elif op == b'm' and len(vals) == 2: cur = start = _pt(ctm, *vals)
        elif op == b'l' and len(vals) == 2 and cur:
            nxt = _pt(ctm, *vals); path.append(('seg', cur, nxt)); cur = nxt
        elif op in (b'c', b'v', b'y') and len(vals) >= 4 and cur: cur = _pt(ctm, *vals[-2:])
        elif op == b'h' and cur and start: path.append(('seg', cur, start)); cur = start
        elif op == b're' and len(vals) == 4:
            x, y, w, h = vals
            a, b = _pt(ctm, x, y), _pt(ctm, x + w, y + h)
            path.append(('rect', (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))))
        elif op in (b'S', b's', b'f', b'F', b'f*', b'B', b'B*', b'b', b'b*'):
            for p in path:
                if p[0] == 'seg': segs.append((p[1], p[2]))
                else: rects.append(p[1])
            path, cur = [], None
        elif op == b'n': path, cur = [], None
    return segs, rects


def _texts(page):
    out = []

    def visit(text, cm, tm, font, size):
        t = ' '.join((text or '').split())
        if not t: return
        m = _mul(tm, cm)
        vertical = abs(m[0]) < 1e-6 and abs(m[1]) > 1e-6
        out.append({'text': t, 'x': m[4], 'y': m[5], 'size': float(size or 0) * (abs(m[3]) or abs(m[1]) or 1), 'vertical': vertical})
    try: page.extract_text(visitor_text=visit)
    except Exception: return []
    return out


def _centre(t):
    w = 0.5 * t['size'] * len(t['text'])            # Helvetica-ish width: half the size per character
    return (t['x'], t['y'] + w / 2) if t['vertical'] else (t['x'] + w / 2, t['y'] + t['size'] / 3)


def _len_m(text, unit_default=''):
    m = LENGTH.match(text)
    if not m: return None
    v = _d(m.group(1))
    return v / 1000 if m.group(2).lower() == 'mm' else v


def _paper(box):
    """'A3 landscape' (and its name) when the page is a standard paper size within 2%, else ('', '')."""
    w, h = (_d(box[2] - box[0]) * PT_M * 1000, _d(box[3] - box[1]) * PT_M * 1000)
    for name, (a, b) in PAPER_MM.items():
        for pw, ph, orient in ((a, b, 'portrait'), (b, a, 'landscape')):
            if abs(w - pw) <= Decimal(pw) * Decimal('0.02') and abs(h - ph) <= Decimal(ph) * Decimal('0.02'):
                return name, f'{name} {orient}'
    return '', ''


def _scale_bar(segs, texts):
    """A horizontal line with '0' near one end and a length ('5 m', '10m', '5000 mm') near the other: metres per point."""
    best = None
    for (a, b) in segs:
        if abs(a[1] - b[1]) > 0.5: continue
        left, right = (a, b) if a[0] <= b[0] else (b, a)
        span = right[0] - left[0]
        if span < 20: continue
        zero = any(t['text'] == '0' and abs(_centre(t)[0] - left[0]) <= NEAR and abs(t['y'] - left[1]) <= NEAR for t in texts)
        if not zero: continue
        for t in texts:
            real = _len_m(t['text'])
            if real and abs(_centre(t)[0] - right[0]) <= NEAR * 1.5 and abs(t['y'] - right[1]) <= NEAR:
                if not best or span > best['span']:
                    best = {'span': span, 'm_per_pt': real / _d(span), 'label': t['text'], 'at': left}
    return best


def _dimension_value(text):
    """A dimension as written, in metres: '12000' or '12,000' (millimetres, the UK drawing convention for whole numbers of 100 or
    more), '12.0 m', '4500mm'. None when the text is not a dimension."""
    m = DIMENSION.match(text)
    if not m: return None
    num, unit = m.group(1).replace(',', '').replace(' ', ''), (m.group(2) or '').lower()
    v = _d(num)
    if unit == 'mm': return v / 1000
    if unit == 'm': return v
    if '.' not in num and v >= 100: return v / 1000          # a whole number without a unit: millimetres
    return None                                             # ambiguous (e.g. "12"): left as plain text


def read_page(page, number):
    """What code can read on one PDF page (see the module docstring). Returns a dict; nothing is sent anywhere."""
    mb = page.mediabox
    box = (float(mb.left), float(mb.bottom), float(mb.right), float(mb.top))
    texts = _texts(page)
    segs, rects = _paths(page)
    for t in texts: t['area'] = area_of(*_centre(t), box)
    paper, paper_label = _paper(box)
    out = {'page': number, 'paper': paper_label, 'texts': texts, 'scale': None, 'scale_note': '', 'dimensions': [], 'rooms': [],
           'drawing_number': '', 'drawn_areas': [], 'text_chars': sum(len(t['text']) for t in texts)}
    joined = ' '.join(t['text'] for t in texts)
    m = DRAWING_NO.search(joined)
    if m: out['drawing_number'] = m.group(1).rstrip('.,;')
    bar = _scale_bar(segs, texts)
    written = next(((t, RATIO.search(t['text'])) for t in texts if RATIO.search(t['text'])), None)
    if bar:
        out['scale'] = {'m_per_pt': bar['m_per_pt'], 'how': f'the scale bar (0 to {bar["label"]})', 'area': area_of(*bar['at'], box)}
        if written:
            ratio = _d(written[1].group(1))
            implied = PT_M * ratio
            if abs(implied - bar['m_per_pt']) > bar['m_per_pt'] * AGREE:
                out['scale_note'] = (f'The written scale "{written[0]["text"]}" does not match the scale bar on this page (the drawing may have been '
                                     f'printed at another size): the scale bar is used.')
    elif written:
        t, rm = written
        ratio, drawn_for = _d(rm.group(1)), (rm.group(2) or '').upper()
        if drawn_for and paper and drawn_for != paper:
            out['scale_note'] = f'"{t["text"]}" is for {drawn_for} paper but this page is {paper}: the written scale is not used, so nothing is measured off the drawing.'
        else:
            out['scale'] = {'m_per_pt': PT_M * ratio, 'how': f'the written scale {t["text"]}' + ('' if drawn_for else ' (assumes the page is at the size it was drawn for)'),
                            'area': t['area']}
    else:
        out['scale_note'] = 'No scale bar or written scale found: nothing is measured off the drawing.'
    mpp = out['scale']['m_per_pt'] if out['scale'] else None
    bar_seg = bar and bar['at']
    used = set()
    for t in texts:
        val = _dimension_value(t['text'])
        if val is None or RATIO.search(t['text']) or (bar and t['text'] == bar['label']): continue
        cx, cy = _centre(t)
        best, gap = None, None
        for i, (a, b) in enumerate(segs):
            if bar_seg and (a == bar_seg or b == bar_seg): continue
            horizontal = abs(a[1] - b[1]) <= 0.5
            vertical = abs(a[0] - b[0]) <= 0.5
            if t['vertical'] and not vertical or not t['vertical'] and not horizontal: continue
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            g = abs(cx - mx) + abs(cy - my)
            if g <= NEAR * 3 and (gap is None or g < gap): best, gap = i, g
        d = {'text': t['text'], 'value_m': _q2(val), 'area': t['area'], 'measured_m': None, 'agrees': None}
        if best is not None and mpp is not None:
            a, b = segs[best]
            used.add(best)
            length = _d(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5) * mpp
            d['measured_m'] = _q2(length)
            d['agrees'] = abs(length - val) <= val * AGREE
        out['dimensions'].append(d)
    page_w, page_h = box[2] - box[0], box[3] - box[1]
    for r in rects:
        w, h = r[2] - r[0], r[3] - r[1]
        if w >= page_w * 0.9 and h >= page_h * 0.9: continue          # the page border
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        inside = [t for t in texts if r[0] <= _centre(t)[0] <= r[2] and r[1] <= _centre(t)[1] <= r[3] and _dimension_value(t['text']) is None]
        room = {'name': inside[0]['text'] if inside else '', 'area': area_of(cx, cy, box), 'width_m': None, 'length_m': None, 'area_m2': None}
        if mpp is not None:
            wm, hm = _q2(_d(w) * mpp), _q2(_d(h) * mpp)
            if wm * hm < MIN_ROOM_M2: continue
            room.update(width_m=wm, length_m=hm, area_m2=_q2(_d(w) * mpp * _d(h) * mpp))
        elif not inside: continue
        out['rooms'].append(room)
    with_text = {t['area'] for t in texts}
    drawn = set()
    for a, b in segs: drawn.add(area_of((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, box))
    for r in rects:
        if not (r[2] - r[0] >= page_w * 0.9 and r[3] - r[1] >= page_h * 0.9): drawn.add(area_of((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, box))
    out['drawn_areas'] = sorted(drawn - with_text)
    return out


def read_pdf(raw, pages=None):
    """{page number: read_page(...)} for the given pages (default: all) of a PDF."""
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(raw))
    want = pages or range(1, len(rd.pages) + 1)
    return {n: read_page(rd.pages[n - 1], n) for n in want if 1 <= n <= len(rd.pages)}


def _m(x):
    return f'{x:.2f} m'


def render(r, doc_name):
    """The reading as text for the team, under the page's [Page n] marker: every line cites page and area."""
    p = r['page']
    cite = lambda area: f'({doc_name}, page {p}, area {area})'
    head = (f'[Page {p}, read from the drawing\'s text and lines by Alice in code (no model)'
            + (f'; drawing {r["drawing_number"]}' if r['drawing_number'] else '') + (f'; {r["paper"]}' if r['paper'] else '')
            + (f'; scale from {r["scale"]["how"]}' if r['scale'] else '; no usable scale') + ']')
    lines = [head]
    if r['scale_note']: lines.append(f'- Scale: {r["scale_note"]}')
    for d in r['dimensions']:
        if d['measured_m'] is None: lines.append(f'- Dimension: {d["text"]} = {_m(d["value_m"])} as written {cite(d["area"])}')
        else:
            lines.append(f'- Dimension: {d["text"]} = {_m(d["value_m"])} as written; its line measures {_m(d["measured_m"])} at the scale'
                         + (', agrees' if d['agrees'] else ', DOES NOT AGREE: use the written figure and flag it') + f' {cite(d["area"])}')
    for rm in r['rooms']:
        name = rm['name'] or 'Outline'
        if rm['area_m2'] is None: lines.append(f'- Room: {name} (no scale, not measured) {cite(rm["area"])}')
        else: lines.append(f'- Room: {name}, {_m(rm["width_m"])} x {_m(rm["length_m"])} = {rm["area_m2"]:.2f} m2 at the scale {cite(rm["area"])}')
    by_area = {}
    for t in r['texts']: by_area.setdefault(t['area'], []).append(t['text'])
    for a in sorted(by_area):
        lines.append(f'- Text in area {a} ({AREA_WORDS[a]}): ' + ' | '.join(by_area[a])[:1500])
    if r['drawn_areas']:
        lines.append('- Drawn content with no text in area' + ('s ' if len(r['drawn_areas']) > 1 else ' ') + ', '.join(r['drawn_areas'])
                     + ': read from the image where a model was allowed (see below).')
    return '\n'.join(lines)


def needs_model(r):
    """What a vision model is asked to read on this page, from what code could not: ('page', [])  for the whole page (no text at all,
    a scan), ('areas', [...]) for areas with drawn content but no text, or ('', []) when code read it all."""
    if r['text_chars'] == 0: return 'page', []
    if r['drawn_areas']: return 'areas', r['drawn_areas'][:4]
    return '', []
