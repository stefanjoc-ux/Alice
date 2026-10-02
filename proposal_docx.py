"""Write a proposal into a Word template, keeping the template's own look.

The template is an ordinary .docx kept in a document source (it is never stored in Alice). How it is read:
  - everything before the first top-level heading is the cover and front matter: kept as it is, with placeholders filled;
  - each top-level heading (Heading 1, or the highest heading level used) starts a section;
  - the text under a heading is guidance for the writer and is replaced by the written section;
  - a section whose guidance contains [keep] is standard text (e.g. About us, terms): kept word for word;
  - placeholders anywhere, including headers and footers: {{title}}, {{client}}, {{date}}, {{author}}, {{reference}},
    {{total}}.
Written content uses the template's own styles (headings, List Bullet, List Number, Table Grid) so it looks as if it was
typed into the template. Nothing here needs packages beyond the standard library: the XML is edited as text, element
by element, so everything Alice does not touch (logos, headers, footers, numbering, fonts) is byte-for-byte unchanged.
"""
import html
import io
import re
import zipfile

import documents

PLACEHOLDER = re.compile(r'\{\{\s*([a-z_]+)\s*\}\}', re.I)
KEEP = re.compile(r'\[\s*keep\s*\]', re.I)
PRICING = re.compile(r'commercial|pricing|price|investment|fees|costs?\b', re.I)


# ---------------- reading the template ----------------
def _elements(body):
    """Top-level elements of <w:body> as strings, in order."""
    out, depth, start = [], 0, 0
    for m in re.finditer(r'<[^>]+>', body):
        tag = m.group(0)
        if tag.startswith(('<?', '<!')): continue
        if tag.startswith('</'):
            depth -= 1
            if depth == 0: out.append(body[start:m.end()])
        elif tag.endswith('/>'):
            if depth == 0: out.append(tag)
        else:
            if depth == 0: start = m.start()
            depth += 1
    return out


def _styles(xml):
    """styleId -> {'name', 'level', 'type'}; level follows basedOn so custom heading styles count."""
    raw = {}
    for m in re.finditer(r'<w:style\b([^>]*)>(.*?)</w:style>', xml or '', re.S):
        attrs, inner = m.group(1), m.group(2)
        sid = re.search(r'w:styleId="([^"]+)"', attrs)
        if not sid: continue
        name = re.search(r'<w:name w:val="([^"]+)"', inner)
        based = re.search(r'<w:basedOn w:val="([^"]+)"', inner)
        lvl = re.search(r'<w:outlineLvl w:val="(\d)"', inner)
        typ = re.search(r'w:type="([^"]+)"', attrs)
        raw[sid.group(1)] = {'name': (name.group(1) if name else sid.group(1)).lower(), 'based': based.group(1) if based else '',
                             'outline': int(lvl.group(1)) + 1 if lvl else None, 'type': typ.group(1) if typ else 'paragraph'}
    def level(sid, seen=()):
        s = raw.get(sid)
        if not s or sid in seen: return None
        m = re.fullmatch(r'heading (\d)', s['name'])
        if m: return int(m.group(1))
        if s['name'] == 'title': return 0
        if s['outline']: return s['outline']
        return level(s['based'], seen + (sid,)) if s['based'] else None
    return {sid: {'name': s['name'], 'level': level(sid), 'type': s['type']} for sid, s in raw.items()}


def _style_id(styles, *names):
    for n in names:
        for sid, s in styles.items():
            if s['name'] == n: return sid
    return None


def _text(el):
    return ''.join(html.unescape(t) for t in re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', el, re.S))


def _para_level(el, styles):
    if not el.startswith('<w:p') or el.startswith('<w:proofErr'): return None
    ppr = re.search(r'<w:pPr>(.*?)</w:pPr>', el, re.S)
    if not ppr: return None
    st = re.search(r'<w:pStyle w:val="([^"]+)"', ppr.group(1))
    lvl = styles.get(st.group(1), {}).get('level') if st else None
    if lvl is None:
        o = re.search(r'<w:outlineLvl w:val="(\d)"', ppr.group(1))
        if o: lvl = int(o.group(1)) + 1
    return lvl


class Template:
    def __init__(self, raw):
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(raw))
            self.doc = self.zip.read('word/document.xml').decode('utf-8')
        except (zipfile.BadZipFile, KeyError):
            raise ValueError('The template is not a Word document (.docx).') from None
        try: self.styles = _styles(self.zip.read('word/styles.xml').decode('utf-8'))
        except KeyError: self.styles = {}
        m = re.search(r'<w:body>(.*)</w:body>', self.doc, re.S)
        if not m: raise ValueError('The template has no body.')
        self.body_span = m.span(1)
        els = _elements(m.group(1))
        self.sect = els.pop() if els and els[-1].startswith('<w:sectPr') else ''
        levels = [(_para_level(e, self.styles) if e.startswith('<w:p') else None) for e in els]
        heads = [l for l in levels if l]
        self.level = 1 if 1 in heads else (min(heads) if heads else None)
        self.cover, self.sections = [], []
        cur = None
        for e, l in zip(els, levels):
            if self.level and l is not None and 0 < l <= self.level:
                cur = {'title': ' '.join(_text(e).split()), 'heading': e, 'content': []}
                self.sections.append(cur)
            elif cur is None: self.cover.append(e)
            else: cur['content'].append(e)
        for s in self.sections:
            g = '\n'.join(t for t in (' '.join(_text(e).split()) for e in s['content']) if t)
            s['keep'] = bool(KEEP.search(g))
            s['guidance'] = KEEP.sub('', g).strip()[:1500]

    def outline(self):
        return [{'title': s['title'], 'guidance': s['guidance'], 'keep': s['keep']} for s in self.sections if s['title']]

    def placeholders(self):
        names = set()
        for n in self.zip.namelist():
            if re.fullmatch(r'word/(document|header\d*|footer\d*)\.xml', n):
                names |= {m.lower() for m in PLACEHOLDER.findall(_flat(self.zip.read(n).decode('utf-8')))}
        return sorted(names)


def _flat(xml):
    """Text of every paragraph, one per line (placeholders can be split across runs)."""
    return '\n'.join(_text(p) for p in re.findall(r'<w:p\b.*?</w:p>', xml, re.S))


def outline(raw):
    t = Template(raw)
    return {'sections': t.outline(), 'placeholders': t.placeholders(), 'styled': bool(t.level)}


# ---------------- writing ----------------
def _runs(text):
    return ''.join(f'<w:r>{"<w:rPr><w:b/></w:rPr>" if b else ""}<w:t xml:space="preserve">{documents._esc(t)}</w:t></w:r>'
                   for t, b in documents._runs(text))


def _p(text, style=None, prefix='', num=None):
    ppr = ('<w:pPr>' + (f'<w:pStyle w:val="{style}"/>' if style else '')
           + (f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>' if num else '') + '</w:pPr>') if style or num else ''
    return f'<w:p>{ppr}{_runs(prefix + text)}</w:p>'


def _table(rows, style, bold_last=False):
    cols = max(len(r) for r in rows)
    width = 9000 // cols
    grid = ''.join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))
    if style:
        tblpr = f'<w:tblPr><w:tblStyle w:val="{style}"/><w:tblW w:w="{width * cols}" w:type="dxa"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
    else:
        b = ''.join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>' for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
        tblpr = f'<w:tblPr><w:tblW w:w="{width * cols}" w:type="dxa"/><w:tblBorders>{b}</w:tblBorders></w:tblPr>'
    out = [f'<w:tbl>{tblpr}<w:tblGrid>{grid}</w:tblGrid>']
    for n, r in enumerate(rows):
        bold = n == 0 or (bold_last and n == len(rows) - 1)
        cells = ''.join(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>{_p(("**" + str(x) + "**") if bold and str(x) else str(x))}</w:tc>'
                        for x in list(r) + [''] * (cols - len(r)))
        out.append(f'<w:tr>{"<w:trPr><w:tblHeader/></w:trPr>" if n == 0 else ""}{cells}</w:tr>')
    out.append('</w:tbl>')
    return ''.join(out)


class Numbering:
    """Each numbered list restarts at 1: a new numbering instance per list, based on the List Number style's own."""
    def __init__(self, zf, styles_xml, number_style):
        self.base, self.next, self.added = None, None, []
        try: num = zf.read('word/numbering.xml').decode('utf-8')
        except KeyError: return
        m = re.search(r'<w:style\b[^>]*w:styleId="' + re.escape(number_style or '#') + r'"[^>]*>(.*?)</w:style>', styles_xml or '', re.S)
        nid = re.search(r'<w:numId w:val="(\d+)"', m.group(1)) if m else None
        if not nid: return
        a = re.search(r'<w:num w:numId="' + nid.group(1) + r'"[^>]*>.*?<w:abstractNumId w:val="(\d+)"', num, re.S)
        if not a: return
        self.base = a.group(1)
        self.next = max(int(x) for x in re.findall(r'<w:num w:numId="(\d+)"', num)) + 1
    def new(self):
        if self.base is None: return None
        n = self.next; self.next += 1
        self.added.append(f'<w:num w:numId="{n}"><w:abstractNumId w:val="{self.base}"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>')
        return n
    def apply(self, xml):
        return xml.replace('</w:numbering>', ''.join(self.added) + '</w:numbering>') if self.added else xml


def markdown_xml(text, styles, level=1, numbering=None):
    """Written section text (simple markdown) as paragraphs in the template's styles."""
    sub = _style_id(styles, f'heading {min(level + 1, 9)}', 'heading 2')
    bullet = _style_id(styles, 'list bullet')
    number = _style_id(styles, 'list number')
    lp = _style_id(styles, 'list paragraph')
    grid = _style_id(styles, 'table grid')
    out = []
    for b in documents.blocks(text):
        if b[0] == 'h': out.append(_p(b[2], sub) if sub else _p('**' + b[2] + '**'))
        elif b[0] == 'p': out.append(_p(b[1]))
        elif b[0] == 'ul': out += [_p(x, bullet) if bullet else _p(x, lp, '• ') for x in b[1]]
        elif b[0] == 'ol':
            nid = numbering.new() if (numbering and number) else None
            out += [_p(x, number, num=nid) if nid else _p(x, lp, f'{i}. ') for i, x in enumerate(b[1], 1)]
        elif b[0] == 'table': out += [_table(b[1], grid), '<w:p/>']
    return out


def _fill_placeholders(xml, values):
    def sub(text):
        return PLACEHOLDER.sub(lambda m: values.get(m.group(1).lower(), m.group(0)), text)
    def para(m):
        p = m.group(0)
        if '{{' not in _text(p) or not PLACEHOLDER.search(_text(p)): return p
        ts = list(re.finditer(r'(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)', p, re.S))
        whole = [html.unescape(t.group(2)) for t in ts]
        joined = sub(''.join(whole))
        if joined == ''.join(whole): return p
        if all(sub(x) != x or '{' not in x for x in whole) and sum(1 for x in whole if '{' in x) == sum(1 for x in whole if PLACEHOLDER.search(x)):
            out, last = [], 0                 # every placeholder sits inside one run: replace in place, keep each run's format
            for t in ts:
                out.append(p[last:t.start()] + t.group(1) + documents._esc(sub(html.unescape(t.group(2)))) + t.group(3)); last = t.end()
            return ''.join(out) + p[last:]
        out, last = [], 0
        for n, t in enumerate(ts):            # split across runs: all the text goes in the first run
            out.append(p[last:t.start()])
            out.append('<w:t xml:space="preserve">' + documents._esc(joined if n == 0 else '') + '</w:t>')
            last = t.end()
        out.append(p[last:])
        return ''.join(out)
    return re.sub(r'<w:p\b.*?</w:p>', para, xml, flags=re.S)


def fill(raw, sections, values, pricing_rows=None, pricing_note=''):
    """sections: [{'title', 'body'}] in the final order. Returns the finished .docx bytes."""
    t = Template(raw)
    by = {s['title'].casefold(): s for s in t.sections}
    lvl = t.level or 1
    h_style = _style_id(t.styles, f'heading {lvl}', 'heading 1')
    grid = _style_id(t.styles, 'table grid')
    body = list(t.cover)
    priced = False
    try: styles_xml = t.zip.read('word/styles.xml').decode('utf-8')
    except KeyError: styles_xml = ''
    numbering = Numbering(t.zip, styles_xml, _style_id(t.styles, 'list number'))
    for s in sections:
        src = by.get(s['title'].casefold())
        body.append(src['heading'] if src else (_p(s['title'], h_style) if h_style else _p('**' + s['title'] + '**')))
        if src and src['keep']:
            body += [KEEP.sub('', e) if '[' in e else e for e in src['content'] if not KEEP.fullmatch(_text(e).strip() or 'x')]
            continue
        body += markdown_xml(s.get('body') or '', t.styles, lvl, numbering)
        if pricing_rows and not priced and PRICING.search(s['title']):
            body += [_table(pricing_rows, grid, bold_last=True)] + ([_p(pricing_note)] if pricing_note else [])
            priced = True
    if pricing_rows and not priced:
        body.append(_p('Commercials', h_style) if h_style else _p('**Commercials**'))
        body += [_table(pricing_rows, grid, bold_last=True)] + ([_p(pricing_note)] if pricing_note else [])
    if not body or not body[-1].startswith('<w:p'): body.append('<w:p/>')   # Word wants a paragraph before sectPr
    a, b = t.body_span
    doc = t.doc[:a] + ''.join(body) + t.sect + t.doc[b:]
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for info in t.zip.infolist():
            data = t.zip.read(info.filename)
            n = info.filename
            if n == 'word/document.xml': data = _fill_placeholders(doc, values).encode('utf-8')
            elif n == 'word/numbering.xml': data = numbering.apply(data.decode('utf-8')).encode('utf-8')
            elif re.fullmatch(r'word/(header|footer)\d*\.xml', n): data = _fill_placeholders(data.decode('utf-8'), values).encode('utf-8')
            elif n == 'docProps/core.xml' and values.get('title'):
                data = re.sub(r'<dc:title>.*?</dc:title>|<dc:title/>', '<dc:title>' + documents._esc(values['title']) + '</dc:title>',
                              data.decode('utf-8'), flags=re.S).encode('utf-8')
            elif n == 'word/settings.xml' and ('TOC \\' in doc or 'Table of Contents' in doc) and b'updateFields' not in data:
                data = re.sub(r'(<w:settings\b[^>]*>)', r'\1<w:updateFields w:val="true"/>', data.decode('utf-8'), count=1).encode('utf-8')
            z.writestr(info, data)
    return out.getvalue()


def plain_docx(title, sections, pricing_rows=None, pricing_note=''):
    """No template: Alice's own Word layout, same sections and pricing."""
    md, priced = [], False
    def table(rows): return '\n'.join('| ' + ' | '.join(str(x) for x in r) + ' |' + ('\n|' + '---|' * len(r) if i == 0 else '') for i, r in enumerate(rows))
    for s in sections:
        md += ['# ' + s['title'], s.get('body') or '']
        if pricing_rows and not priced and PRICING.search(s['title']):
            md += [table(pricing_rows), pricing_note]; priced = True
    if pricing_rows and not priced: md += ['# Commercials', table(pricing_rows), pricing_note]
    return documents.to_docx(title, '\n\n'.join(x for x in md if x))
