"""A tiny writer for FICTIONAL drawing PDFs: each page is a content stream (lines, rectangles, Helvetica text), so tests can place a
scale bar, dimension lines and room outlines exactly. Import after _util."""
import io

A3 = (1190.55, 841.89)        # A3 landscape in points
PT_PER_M_1_100 = 28.3465      # one metre at 1:100 on paper, in points


def pdf(pages, size=A3):
    objs = []

    def add(b):
        objs.append(b)
        return len(objs)
    font = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    pages_id = len(objs) + 2 * len(pages) + 1
    kids = []
    for c in pages:
        cs = c.encode('latin-1')
        sid = add(b'<< /Length %d >>\nstream\n' % len(cs) + cs + b'\nendstream')
        kids.append(add(b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>'
                        % (pages_id, size[0], size[1], sid, font)))
    add(b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % k for k in kids), len(kids)))
    cat = add(b'<< /Type /Catalog /Pages %d 0 R >>' % pages_id)
    out = io.BytesIO()
    out.write(b'%PDF-1.4\n')
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(out.tell())
        out.write(b'%d 0 obj\n' % i + o + b'\nendobj\n')
    x = out.tell()
    out.write(b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1))
    for o in offs: out.write(b'%010d 00000 n \n' % o)
    out.write(b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, cat, x))
    return out.getvalue()


def text(x, y, s, size=9):
    return f'BT /F1 {size} Tf {x} {y} Td ({s}) Tj ET'


def line(x1, y1, x2, y2):
    return f'{x1} {y1} m {x2} {y2} l S'


def rect(x, y, w, h):
    return f'{x} {y} {w} {h} re S'


def plan_page(drawing_no='FIC-A-101', written='Scale 1:100 at A3', bar=True, extra=''):
    """A FICTIONAL ground floor plan at 1:100 on A3: a 0-5 m scale bar (top left), a hall 12 m x 8 m (centre left) with a 12000
    dimension line under it, the scale and drawing number in the title block (bottom right)."""
    m = PT_PER_M_1_100
    parts = [line(100, 700, round(100 + 5 * m, 2), 700), text(98, 705, '0'), text(round(96 + 5 * m, 2), 705, '5 m')] if bar else []
    parts += [rect(200, 300, round(12 * m, 2), round(8 * m, 2)), text(330, 410, 'Hall', 10),
              line(200, 280, round(200 + 12 * m, 2), 280), text(355, 268, '12000'),
              text(900, 80, written, 12), text(900, 60, f'Drawing No: {drawing_no}', 10), extra]
    return '\n'.join(p for p in parts if p)
