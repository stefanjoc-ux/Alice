"""Purview labels are read the same whichever XML library wrote the file (lxml or the standard library), for Word, Excel and
PowerPoint, and a blocked label is refused in every case. All files here are fictional and made in the test (or by openpyxl in
tests/fixtures: FICTIONAL-label-lxml.xlsx was written with lxml installed, FICTIONAL-label-stdlib.xlsx without)."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, io, os, subprocess, sys, zipfile
from pathlib import Path
import substrate_store as s
s.init()
import purview_labels as P, pricing_templates as PT
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app)

FIX = Path(__file__).parent / 'fixtures'
G = '7e5f0c1a-2b3c-4d5e-8f90-a1b2c3d4e5f6'          # the label in the openpyxl fixtures (OFFICIAL-SENSITIVE)
GB, GO = 'b10cced0-0000-4000-8000-00000000b10c', 'a11c0de0-1111-4111-8111-111111111111'
CP = 'http://schemas.openxmlformats.org/officeDocument/2006/custom-properties'
VT = 'http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'
FMT = '{D5CDD505-2E9C-101B-9397-08002B2CF9AE}'

# The main part of each kind of file, so each package looks like the real thing.
MAIN = {
    'docx': ('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                  '<w:body><w:p><w:r><w:t>FICTIONAL document for a label test.</w:t></w:r></w:p></w:body></w:document>'),
    'xlsx': ('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets/></workbook>'),
    'pptx': ('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>'),
}


def props(guid, name, style):
    """custom.xml as each writer lays it out. stdlib: vt declared on the root (Office, openpyxl without lxml); lxml: vt declared on
    every value (openpyxl with lxml); prefixed: ElementTree's own ns0:/ns1: prefixes; pretty: indented, single quotes, the
    Enabled value 'True'."""
    pairs = [('Enabled', 'true'), ('SetDate', '2026-10-09T09:00:00Z'), ('Method', 'Standard'), ('Name', name)]
    if style == 'stdlib':
        body = ''.join(f'<property fmtid="{FMT}" pid="{i + 2}" name="MSIP_Label_{guid}_{k}"><vt:lpwstr>{v}</vt:lpwstr></property>'
                       for i, (k, v) in enumerate(pairs))
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="{CP}" xmlns:vt="{VT}">{body}</Properties>'
    if style == 'lxml':
        body = ''.join(f'<property name="MSIP_Label_{guid}_{k}" fmtid="{FMT}" pid="{i + 2}"><vt:lpwstr xmlns:vt="{VT}">{v}</vt:lpwstr></property>'
                       for i, (k, v) in enumerate(pairs))
        return f'<Properties xmlns="{CP}">{body}</Properties>'
    if style == 'prefixed':
        body = ''.join(f'<ns0:property fmtid="{FMT}" pid="{i + 2}" name="MSIP_Label_{guid}_{k}"><ns1:lpwstr>{v}</ns1:lpwstr></ns0:property>'
                       for i, (k, v) in enumerate(pairs))
        return f'<ns0:Properties xmlns:ns0="{CP}" xmlns:ns1="{VT}">{body}</ns0:Properties>'
    body = ''.join(f"\n  <property\n     fmtid='{FMT}' pid='{i + 2}'\n     name='MSIP_Label_{guid}_{k}'>\n    <vt:lpwstr>  {'True' if k == 'Enabled' else v}  </vt:lpwstr>\n  </property>"
                   for i, (k, v) in enumerate(pairs))
    return f"<?xml version='1.0'?>\n<Properties xmlns='{CP}'\n    xmlns:vt='{VT}'>{body}\n</Properties>\n"


def package(kind, custom=None, labelinfo=None, custom_at='docProps/custom.xml'):
    part, xml = MAIN[kind]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        rels = f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{part}"/>'
        if custom:
            rels += f'<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties" Target="{custom_at}"/>'
        z.writestr('_rels/.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        z.writestr(part, xml)
        if custom: z.writestr(custom_at, custom)
        if labelinfo: z.writestr('docMetadata/LabelInfo.xml', labelinfo)
    return buf.getvalue()


def refused(label):
    try: P.decide(label)
    except ValueError as e: return 'not allowed in Alice' in str(e)
    return False


P.set_mapping(GB, 'block', 'FICTIONAL Board only')

# ---------------- every layout, every kind of file ----------------
for kind in ('docx', 'xlsx', 'pptx'):
    for style in ('stdlib', 'lxml', 'prefixed', 'pretty'):
        raw = package(kind, props(GB, 'FICTIONAL Board only', style))
        got = P.read_label(f'FICTIONAL.{kind}', raw)
        t(f'{kind}, custom.xml written {style}: the label is read', got == {'id': GB, 'name': 'FICTIONAL Board only'})
        t(f'{kind}, custom.xml written {style}: a label mapped to Block is refused', refused(got))
        raw = package(kind, props(GO, 'OFFICIAL-SENSITIVE', style))
        t(f'{kind}, custom.xml written {style}: an unmapped protective-marking label is refused',
          refused(P.read_label(f'FICTIONAL.{kind}', raw)))

for ext, kind in (('docm', 'docx'), ('dotx', 'docx'), ('xlsm', 'xlsx'), ('xltx', 'xlsx'), ('pptm', 'pptx'), ('potx', 'pptx')):
    t(f'.{ext} files are read too', P.read_label(f'FICTIONAL.{ext}', package(kind, props(GB, 'FICTIONAL Board only', 'lxml')))
      == {'id': GB, 'name': 'FICTIONAL Board only'})

# the custom properties found through the package's relationships, wherever they are kept
raw = package('xlsx', props(GB, 'FICTIONAL Board only', 'lxml'), custom_at='docProps/Custom.XML')
t('the custom properties part is found by its relationship and any letter case', P.read_label('x.xlsx', raw)['id'] == GB)

# LabelInfo.xml with another prefix and layout
li = (f"<?xml version='1.0'?>\n<x:labelList xmlns:x='http://schemas.microsoft.com/office/2020/mipLabelMetadata'>\n"
      f"  <x:label id='{{{GB.upper()}}}' enabled='1' method='Standard' removed='0' />\n</x:labelList>")
for kind in ('docx', 'xlsx', 'pptx'):
    got = P.read_label(f'x.{kind}', package(kind, labelinfo=li))
    t(f'{kind}: LabelInfo.xml with another prefix and layout is read, and its blocked label refused', got == {'id': GB, 'name': ''} and refused(got))

# a label switched off or removed is not a label; nothing is invented
off = props(GB, 'FICTIONAL Board only', 'lxml').replace('>true<', '>false<', 1)
t('a label not enabled is not read', P.read_label('x.xlsx', package('xlsx', off)) is None)
rem = props(GB, 'FICTIONAL Board only', 'lxml').replace('</Properties>',
      f'<property name="MSIP_Label_{GB}_Removed" fmtid="{FMT}" pid="9"><vt:lpwstr xmlns:vt="{VT}">true</vt:lpwstr></property></Properties>')
t('a removed label is not read', P.read_label('x.xlsx', package('xlsx', rem)) is None)
t('no label, nothing read', P.read_label('x.xlsx', package('xlsx')) is None)
t('custom.xml that is not well-formed is still read', P.read_label('x.docx', package('docx',
  props(GB, 'FICTIONAL Board only', 'stdlib').replace(f' xmlns:vt="{VT}"', ''))) == {'id': GB, 'name': 'FICTIONAL Board only'})
t('not a zip: nothing read, no crash', P.read_label('x.docx', b'FICTIONAL not a zip') is None)

# ---------------- workbooks openpyxl wrote, with and without lxml ----------------
for f in ('FICTIONAL-label-lxml.xlsx', 'FICTIONAL-label-stdlib.xlsx'):
    raw = (FIX / f).read_bytes()
    got = P.read_label(f, raw)
    t(f'{f}: the label openpyxl wrote is read', got == {'id': G, 'name': 'OFFICIAL-SENSITIVE'})
    t(f'{f}: and refused (a protective marking, not mapped)', refused(got))
t('the lxml fixture really is laid out as lxml writes it (vt declared on each value)',
  b'<vt:lpwstr xmlns:vt=' in zipfile.ZipFile(io.BytesIO((FIX / 'FICTIONAL-label-lxml.xlsx').read_bytes())).read('docProps/custom.xml'))

MAKE = r'''
import io, sys, openpyxl, openpyxl.xml
from openpyxl.packaging.custom import StringProperty
wb = openpyxl.Workbook(); wb.active.append(['FICTIONAL'])
for k, v in (('Enabled', 'true'), ('Name', 'FICTIONAL Board only')):
    wb.custom_doc_props.append(StringProperty(name='MSIP_Label_%s_%s' % (sys.argv[1], k), value=v))
b = io.BytesIO(); wb.save(b); sys.stdout.buffer.write((b'L' if openpyxl.xml.LXML else b'S') + b.getvalue())
'''
try: import lxml  # noqa: F401
except ImportError: lxml = None
for mode in ('False',) + (('True',) if lxml else ()):
    out = subprocess.run([sys.executable, '-c', MAKE, GB], capture_output=True, env={**os.environ, 'OPENPYXL_LXML': mode}, timeout=60).stdout
    t(f'openpyxl {"with" if mode == "True" else "without"} lxml, written now: the label is read and refused',
      out[:1] == (b'L' if mode == 'True' else b'S') and P.read_label('x.xlsx', out[1:]) == {'id': GB, 'name': 'FICTIONAL Board only'}
      and refused(P.read_label('x.xlsx', out[1:])))
print('  (lxml is ' + ('installed: workbooks written both ways now' if lxml else 'not installed: the lxml workbook is the fixture') + ')')

# ---------------- end to end: a blocked file is never saved or used ----------------
for f in ('FICTIONAL-label-lxml.xlsx', 'FICTIONAL-label-stdlib.xlsx'):
    raw = (FIX / f).read_bytes()
    r = cl.post('/files', json={'name': f, 'data': base64.b64encode(raw).decode()})
    t(f'{f}: an upload is refused naming the label', r.status_code == 400 and 'OFFICIAL-SENSITIVE' in r.text)
    try: PT._label_ok(f, raw); ok = False
    except ValueError as e: ok = 'Purview label' in str(e)
    t(f'{f}: a pricing template carrying it is never used', ok)
for kind in ('docx', 'pptx'):
    raw = package(kind, props(GB, 'FICTIONAL Board only', 'lxml'))
    r = cl.post('/files', json={'name': f'FICTIONAL.{kind}', 'data': base64.b64encode(raw).decode()})
    t(f'{kind} written with lxml\'s layout: an upload is refused', r.status_code == 400)
with s.db() as c: n = c.execute("SELECT count(*) FROM files").fetchone()[0]
t('nothing was saved', n == 0)

# the filled copy of a labelled template keeps the label, read back the same way
raw = (FIX / 'FICTIONAL-label-lxml.xlsx').read_bytes()
import openpyxl
plain = io.BytesIO(); openpyxl.Workbook().save(plain)
kept = PT._keep_label(raw, 'FICTIONAL.xlsx', plain.getvalue())
t('a filled copy keeps a template\'s label written with lxml', P.read_label('x.xlsx', kept) == {'id': G, 'name': 'OFFICIAL-SENSITIVE'})
