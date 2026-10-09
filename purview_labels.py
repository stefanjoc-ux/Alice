"""Microsoft Purview sensitivity labels on uploaded files: honour them instead of guessing.

Office files (.docx, .xlsx, .pptx) carry the label in docProps/custom.xml (MSIP_Label_<id>_Enabled/_Name) and, in newer
Office versions, docMetadata/LabelInfo.xml (label id only). PDFs carry MSIP_Label_* entries in their document
information. Alice reads the label, records it, and applies your mapping (Rules page → Purview sensitivity labels):
  general / internal / client / local  → that Alice label at least (never lowers what Alice already set)
  block                                 → the file is not saved
A label with no mapping yet: protective-marking names (e.g. OFFICIAL-SENSITIVE) are blocked; anything else is treated as
Internal until you map it. Alice never writes, changes or removes Purview labels: that stays in Purview.
"""
import io
import re
import zipfile
import xml.etree.ElementTree as ET

import substrate_store as store

ACTIONS = ('general', 'internal', 'client', 'local', 'block')
ORDER = {'general': 0, 'internal': 1, 'client': 2, 'local': 3}
DEFAULT_UNMAPPED = 'internal'
OFFICE = ('docx', 'docm', 'dotx', 'dotm', 'xlsx', 'xlsm', 'xltx', 'xltm', 'pptx', 'pptm', 'potx', 'potm', 'ppsx', 'ppsm')
_GUID = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

with store.db() as c:
    c.execute('''CREATE TABLE IF NOT EXISTS purview_labels (label_id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL DEFAULT '', files INTEGER NOT NULL DEFAULT 0, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL)''')


MAX_PART = 5 * 1024 * 1024        # a label part larger than this is not a real label part: not read


def _local(name):
    """An XML tag or attribute name without its namespace ('{ns}lpwstr' or 'vt:lpwstr' → 'lpwstr')."""
    return name.rsplit('}', 1)[-1].rsplit(':', 1)[-1]


def _attrs(el):
    return {_local(k): v for k, v in el.attrib.items()}


def _part(z, names, wanted, rel_type=None):
    """The bytes of a package part, found by its relationship type in _rels/.rels when there is one, else by its usual name,
    ignoring case and a leading slash. None when the part is missing or too large."""
    by_lower = {n.lower().lstrip('/'): n for n in names}
    found = None
    if rel_type and '_rels/.rels' in by_lower:
        try:
            root = ET.fromstring(z.read(by_lower['_rels/.rels']))
            for el in root.iter():
                a = _attrs(el)
                if _local(el.tag) == 'Relationship' and a.get('Type', '').rstrip('/').endswith(rel_type) and a.get('Target'):
                    found = by_lower.get(a['Target'].lower().lstrip('/'))
                    if found: break
        except (ET.ParseError, KeyError, zipfile.BadZipFile): found = None
    found = found or by_lower.get(wanted.lower())
    if not found or z.getinfo(found).file_size > MAX_PART: return None
    return z.read(found)


def _custom_props(data):
    """{(guid, key): value} for every MSIP_Label_<guid>_<key> custom property. Read as XML whatever the namespace prefixes, where
    the vt namespace is declared (on the root, as Office and openpyxl without lxml write it, or on each value, as openpyxl with
    lxml writes it) and however it is laid out; text that is not well-formed XML is read with a tolerant pattern instead."""
    found = {}
    try:
        for el in ET.fromstring(data).iter():
            if _local(el.tag) != 'property': continue
            m = re.fullmatch(r'MSIP_Label_(' + _GUID + r')_(\w+)', (_attrs(el).get('name') or '').strip())
            if not m: continue
            value = next((child.text or '' for child in el), el.text or '')
            found[(m.group(1).lower(), m.group(2))] = value.strip()
        return found
    except ET.ParseError:
        pass
    xml = data.decode('utf-8', 'replace')
    for m in re.finditer(r'name\s*=\s*["\']MSIP_Label_(' + _GUID + r')_(\w+)["\'][^>]*>\s*<[\w:.-]+(?:\s[^>]*)?>([^<]*)</', xml):
        found[(m.group(1).lower(), m.group(2))] = m.group(3).strip()
    return found


def _true(v, default=False):
    v = (v or '').strip().lower()
    return default if not v else v in ('true', '1', 'yes')


def _from_office(raw):
    """The label on a Word, Excel or PowerPoint file (any of their template and macro-enabled forms). Read straight from the
    zip with the standard library, so the result never depends on which XML library wrote or reads the file."""
    try: z = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, ValueError): return None
    with z:
        names = z.namelist()
        data = _part(z, names, 'docProps/custom.xml', '/custom-properties')
        if data:
            labels = {}
            for (g, k), v in _custom_props(data).items(): labels.setdefault(g, {})[k] = v
            enabled = [g for g, v in labels.items() if _true(v.get('Enabled')) and not _true(v.get('Removed'))]
            if enabled:
                g = enabled[0]
                return {'id': g, 'name': labels[g].get('Name', '')}
        data = _part(z, names, 'docMetadata/LabelInfo.xml', '/classificationlabels')
        if data:
            try: labels = [_attrs(el) for el in ET.fromstring(data).iter() if _local(el.tag) == 'label']
            except ET.ParseError:
                labels = [dict(re.findall(r'(\w+)\s*=\s*["\']([^"\']*)["\']', m.group(1)))
                          for m in re.finditer(r'<(?:\w+:)?label\b([^>]*)/?>', data.decode('utf-8', 'replace'))]
            for a in labels:
                lid = (a.get('id') or '').strip().strip('{}').lower()
                if re.fullmatch(_GUID, lid) and _true(a.get('enabled'), True) and not _true(a.get('removed')):
                    return {'id': lid, 'name': ''}
    return None


def _from_pdf(raw):
    try:
        from pypdf import PdfReader
        info = PdfReader(io.BytesIO(raw)).metadata or {}
    except Exception:
        return None
    found = {}
    for k, v in info.items():
        m = re.fullmatch(r'/?MSIP_Label_(' + _GUID + r')_(\w+)', str(k))
        if m: found.setdefault(m.group(1).lower(), {})[m.group(2)] = str(v).strip()
    for g, v in found.items():
        if v.get('Enabled', 'true').lower() == 'true': return {'id': g, 'name': v.get('Name', '')}
    return None


def read_label(name, raw):
    """The Purview label on a file, as {'id', 'name'}, or None."""
    ext = name.lower().rsplit('.', 1)[-1] if '.' in name else ''
    if ext in OFFICE: return _from_office(raw)
    if ext == 'pdf': return _from_pdf(raw)
    return None


def decide(label):
    """Record that the label was seen and return (alice_label, mapping_note). Raises ValueError when it blocks the file."""
    import rules_engine
    if not label: return None, ''
    lid, name = label['id'], ' '.join((label.get('name') or '').split())[:120]
    with store.db() as c:
        row = c.execute('SELECT name,action FROM purview_labels WHERE label_id=?', (lid,)).fetchone()
        if row:
            c.execute("UPDATE purview_labels SET files=files+1,last_seen=?,name=CASE WHEN ?<>'' THEN ? ELSE name END WHERE label_id=?",
                      (store.now(), name, name, lid))
            action, name = row['action'], name or row['name']
        else:
            c.execute('INSERT INTO purview_labels(label_id,name,action,files,first_seen,last_seen) VALUES (?,?,?,?,?,?)',
                      (lid, name, '', 1, store.now(), store.now()))
            store.audit(c, 'purview_label_seen', lid, 'purview_labels', name or '(name not in the file)')
            action = ''
    shown = name or lid
    if action == 'block' or (not action and name and rules_engine.find_markings(name)):
        with store.db() as c: store.audit(c, 'rule_blocked', shown, 'purview_labels', 'File not saved: Purview label ' + shown)
        raise ValueError(f'Not saved: this file carries the Purview label "{shown}", which is not allowed in Alice. '
                         'Change the mapping on the Rules page if that is wrong.')
    if action in ORDER: return action, f'Purview label "{shown}" → {action}'
    return DEFAULT_UNMAPPED, f'Purview label "{shown}" not mapped yet → internal until you map it on the Rules page'


def stricter(current, wanted):
    return wanted if ORDER.get(wanted, 0) > ORDER.get(current, 0) else current


def listing():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM purview_labels ORDER BY action<>\'\', lower(name), label_id')]
    return {'labels': rows, 'actions': list(ACTIONS), 'default_unmapped': DEFAULT_UNMAPPED}


def set_mapping(label_id, action, name=None):
    """Map a label (by its id) to an Alice label or to block. A label not seen yet can be added by id and name."""
    lid = (label_id or '').strip().strip('{}').lower()
    if not re.fullmatch(_GUID, lid): raise ValueError('Use the label ID from the Purview portal (a GUID such as 1a2b3c4d-…).')
    if action not in ACTIONS + ('',): raise ValueError('Choose General, Internal, Client-confidential, Local only or Block.')
    name = ' '.join((name or '').split())[:120] if name is not None else None
    with store.db() as c:
        if c.execute('SELECT 1 FROM purview_labels WHERE label_id=?', (lid,)).fetchone():
            c.execute('UPDATE purview_labels SET action=?' + (',name=?' if name else '') + ' WHERE label_id=?',
                      (action, name, lid) if name else (action, lid))
        else:
            c.execute('INSERT INTO purview_labels(label_id,name,action,files,first_seen,last_seen) VALUES (?,?,?,?,?,?)',
                      (lid, name or '', action, 0, store.now(), store.now()))
        store.audit(c, 'purview_label_mapped', lid, 'purview_labels', f'{name or lid} → {action or "not mapped"}')
    return {'label_id': lid, 'action': action}
