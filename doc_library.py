"""Document sources: full documents that stay OUTSIDE Alice.

Each source is a connector. Today every source is a folder under the Documents folder (ALICE_DOCUMENT_LIBRARY overrides
it), and a folder can say which system it stands in for, in a _source.json file: a SharePoint library, Microsoft Fabric
(OneLake) or Power Platform (Dataverse). In Azure the same sources become real connectors (Microsoft Graph for
SharePoint, OneLake for Fabric, Dataverse for Power Platform) behind the same three calls: list the files, read one,
read its label. Nothing else in Alice changes when that happens.

Knowledge holds approved summaries that point to a document and section. Assistants answer from the summaries; only
when those do not answer the question do they open the pointed-to document, read the relevant section on demand and use
it for that one answer. Nothing read here is stored in Alice (an in-memory cache keyed by the file's modified time only).

Before any extract reaches a model, the same rules as everything else apply: the file's Microsoft Purview label and its
mapping (Block and Local only are never sent; labels the model may not receive are skipped), then Alice's secret and
protective-marking checks on the extract itself.
"""
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('ALICE_DOCUMENT_LIBRARY') or (BASE / 'Documents')).resolve()
TYPES = ('.docx', '.pdf', '.txt', '.md', '.csv')
MAX_EXTRACT = 6000
CONFIG = '_source.json'
KINDS = {'folder': 'Folder', 'sharepoint': 'SharePoint library', 'fabric': 'Microsoft Fabric (OneLake)',
         'power_platform': 'Power Platform (Dataverse)'}
CONNECTOR = {'folder': 'Local folder', 'sharepoint': 'Microsoft Graph', 'fabric': 'OneLake', 'power_platform': 'Dataverse Web API'}
_cache = {}


# ---------------- sources (connectors) ----------------
def _config(folder):
    try: c = json.loads((folder / CONFIG).read_text(encoding='utf-8'))
    except Exception: c = {}
    kind = c.get('type') if c.get('type') in KINDS else 'folder'
    return {'type': kind, 'name': ' '.join(str(c.get('name') or folder.name).split())[:80],
            'simulates': ' '.join(str(c.get('simulates') or '').split())[:200], 'description': ' '.join(str(c.get('description') or '').split())[:300]}


def _documents(folder, recursive=True):
    it = folder.rglob('*') if recursive else folder.iterdir()
    for p in it:
        if p.is_file() and p.suffix.lower() in TYPES and not any(x.startswith(('.', '_', '~$')) for x in p.relative_to(ROOT).parts):
            yield p


def sources():
    """Every document source: one per folder in the Documents folder, plus loose files at the top as 'Documents'."""
    out = []
    if not ROOT.is_dir(): return out
    for f in sorted((p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(('.', '_'))), key=lambda p: p.name.lower()):
        c = _config(f)
        out.append(dict(c, id=f.name, path=str(f), type_name=KINDS[c['type']], connector=CONNECTOR[c['type']],
                        simulated=c['type'] != 'folder', files=sum(1 for _ in _documents(f))))
    loose = list(_documents(ROOT, recursive=False))
    if loose:
        out.insert(0, {'id': '', 'name': 'Documents', 'type': 'folder', 'type_name': KINDS['folder'], 'connector': CONNECTOR['folder'],
                       'simulates': '', 'description': 'Files at the top of the Documents folder', 'path': str(ROOT), 'simulated': False,
                       'files': len(loose)})
    return out


def source_of(p):
    """The source a resolved file belongs to: (id, config)."""
    rel = p.relative_to(ROOT)
    if len(rel.parts) == 1: return '', {'type': 'folder', 'name': 'Documents', 'simulates': '', 'description': ''}
    return rel.parts[0], _config(ROOT / rel.parts[0])


def describe(p):
    """How to show where a document lives, e.g. 'SharePoint library "HR Policies" (simulated by a folder)'."""
    sid, c = source_of(p)
    what = KINDS[c['type']] + f' "{c["name"]}"'
    return what + (' (simulated by a folder)' if c['type'] != 'folder' else '')


def add_source(name, kind='folder', simulates='', description=''):
    """A new source: a folder under Documents with its _source.json. Files are added to the folder directly."""
    name = ' '.join((name or '').split())
    if not name or len(name) > 60 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 &'()_.,-]*", name) or name.endswith('.'):
        raise ValueError('Give the source a name of up to 60 letters, numbers, spaces or simple punctuation.')
    if kind not in KINDS: raise ValueError('Unknown source type.')
    folder = (ROOT / name).resolve()
    if folder.parent != ROOT: raise ValueError('Give the source a plain name.')
    if folder.exists(): raise ValueError('There is already a source with that name.')
    folder.mkdir(parents=True)
    (folder / CONFIG).write_text(json.dumps({'type': kind, 'name': name, 'simulates': ' '.join((simulates or '').split())[:200],
                                             'description': ' '.join((description or '').split())[:300]}, indent=1), encoding='utf-8')
    return next(x for x in sources() if x['id'] == name)


def files(source_id):
    """The documents in one source, with their Purview label and how many knowledge summaries point to each."""
    folder = ROOT if source_id == '' else (ROOT / source_id).resolve()
    if folder != ROOT and folder.parent != ROOT or not folder.is_dir(): raise ValueError('No such document source.')
    import knowledge, purview_labels
    pointed = {}
    for i in knowledge.listing(status='all', limit=100000)['items']:
        rel, _ = pointer(i)
        p = resolve(rel) if rel else None
        if p: pointed.setdefault(str(p), []).append(i['status'])
    out = []
    for p in sorted(_documents(folder, recursive=folder != ROOT), key=lambda x: str(x).lower()):
        st = p.stat()
        try: lbl = purview_labels.read_label(p.name, p.read_bytes()) if p.suffix.lower() in ('.docx', '.pdf') else None
        except Exception: lbl = None
        refs = pointed.get(str(p), [])
        out.append({'path': str(p.relative_to(ROOT)), 'name': p.name, 'full_path': str(p), 'size': st.st_size,
                    'modified': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(), 'label': (lbl or {}).get('name') or (lbl or {}).get('id') or '',
                    'summaries': len(refs), 'summaries_active': sum(1 for x in refs if x == 'active')})
    return out


def pointer(item):
    """(relative path, section) for a knowledge item that summarises a library document, else (None, None)."""
    path = (item.get('source_document') or '').strip()
    sec = (item.get('source_section') or '').strip()
    src = item.get('source') or ''
    if not path:
        m = re.search(r'full document:\s*([^;)]+)', src)
        if m: path = m.group(1).strip()
    if not sec:
        m = re.search(r'\bsection\s+(\d+(?:\.\d+)*)', src, re.I)
        if m: sec = m.group(1)
    return (path or None), (sec or None)


def resolve(rel):
    """The file inside the Documents folder for a pointer, or None (never outside it). Older pointers that name another
    folder (e.g. "Policy library\\file.docx") are matched by their file name when exactly one document has that name."""
    if not rel: return None
    rel = rel.replace('\\', '/').strip().strip('/')
    if rel.lower().startswith(ROOT.name.lower() + '/'): rel = rel[len(ROOT.name) + 1:]
    p = (ROOT / rel).resolve()
    if ROOT in p.parents and p.suffix.lower() in TYPES and p.is_file(): return p
    name = rel.rsplit('/', 1)[-1]
    if not name or name.startswith(('.', '_')) or Path(name).suffix.lower() not in TYPES or not ROOT.is_dir(): return None
    hits = [x for x in _documents(ROOT) if x.name.lower() == name.lower()]
    return hits[0] if len(hits) == 1 else None


def _read(p):
    key = (str(p), p.stat().st_mtime_ns)
    if key in _cache: return _cache[key]
    raw = p.read_bytes()
    ext = p.suffix.lower()
    if ext == '.docx':
        import knowledge
        text = knowledge.docx_to_text(raw)
    elif ext == '.pdf':
        from pypdf import PdfReader
        text = '\n'.join(pg.extract_text() or '' for pg in PdfReader(io.BytesIO(raw)).pages)
    else:
        text = raw.decode('utf-8', 'replace')
    for k in [k for k in _cache if k[0] == str(p)]: _cache.pop(k)
    _cache[key] = (raw, text)
    return raw, text


def section(text, sec):
    """The text of one numbered section ('3' or '3.2'): from its heading to the next heading at the same or a higher level."""
    if not sec: return ''
    start = re.compile(r'^(#+)\s*' + re.escape(sec) + r'(?:[.)]|\s)')
    out, level = [], None
    for line in text.split('\n'):
        h = re.match(r'^(#+)\s', line)
        if level is None:
            m = start.match(line)
            if m: level = len(m.group(1)); out.append(line)
            continue
        if h and len(h.group(1)) <= level: break
        out.append(line)
    return '\n'.join(out).strip()


def _words(t):
    return [w for w in re.findall(r"[a-z0-9']+", (t or '').lower()) if len(w) > 2]


def best_passages(text, question, n=3, size=1200):
    q = set(_words(question)) - {'the', 'and', 'for', 'with', 'what', 'how', 'can', 'does', 'policy', 'policies'}
    paras, buf = [], ''
    for p in re.split(r'\n(?=#)|\n\s*\n', text):
        if len(buf) + len(p) > size and buf: paras.append(buf); buf = ''
        buf += ('\n' if buf else '') + p.strip()
    if buf: paras.append(buf)
    scored = sorted(((sum(1 for w in _words(p) if w in q), i, p) for i, p in enumerate(paras)), key=lambda x: (-x[0], x[1]))
    return [p for s, i, p in scored[:n] if s]


def _label_action(p, raw, provider):
    """None if the document may go to this model, else the reason it may not."""
    import purview_labels, knowledge, rules_engine
    lbl = purview_labels.read_label(p.name, raw)
    if not lbl: return None
    with __import__('substrate_store').db() as c:
        row = c.execute('SELECT action FROM purview_labels WHERE label_id=?', (lbl['id'],)).fetchone()
    action = row['action'] if row else ''
    name = lbl.get('name') or lbl['id']
    if action == 'block' or (not action and lbl.get('name') and rules_engine.find_markings(lbl['name'])): return f'Purview label "{name}" is blocked'
    alice = action or purview_labels.DEFAULT_UNMAPPED
    if alice == 'local': return f'Purview label "{name}" is Local only'
    if provider in knowledge._labels_blocked().get(alice, []): return f'Purview label "{name}" may not go to this model'
    return None


def extracts(pointers, question, provider, target='assistant'):
    """Read the pointed-to sections on demand. pointers: [(rel, section, title)]. Returns (extracts, skipped notes)."""
    import rules_engine
    out, skipped, seen = [], [], set()
    for rel, sec, title in pointers:
        p = resolve(rel)
        if not p: skipped.append(f'{rel}: not found in the document library'); continue
        key = (str(p), sec)
        if key in seen: continue
        seen.add(key)
        raw, text = _read(p)
        why = _label_action(p, raw, provider)
        if why: skipped.append(f'{p.name}: {why}'); continue
        part = section(text, sec) if sec else ''
        if not part: part = '\n\n'.join(best_passages(text, question))
        if not part: continue
        part = part[:MAX_EXTRACT]
        try: rules_engine.check_outbound(part, target, packs=False)
        except rules_engine.RuleViolation as e: skipped.append(f'{p.name}: {e}'); continue
        out.append({'path': str(p.relative_to(ROOT)), 'name': p.name, 'section': sec or '', 'title': title, 'text': part, 'where': describe(p)})
    return out, skipped
