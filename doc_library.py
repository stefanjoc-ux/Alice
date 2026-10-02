"""The document library: full source documents that stay OUTSIDE Alice (a folder now, SharePoint or Blob later).

Knowledge holds approved summaries that point to a document and section. Assistants answer from the summaries; only when
those do not answer the question do they open the pointed-to document, read the relevant section on demand and use it
for that one answer. Nothing read here is stored in Alice (an in-memory cache keyed by the file's modified time only).

Before any extract reaches a model, the same rules as everything else apply: the file's Microsoft Purview label and its
mapping (Block and Local only are never sent; labels the model may not receive are skipped), then Alice's secret and
protective-marking checks on the extract itself.
"""
import io
import os
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('ALICE_DOCUMENT_LIBRARY') or (BASE / 'Policy library')).resolve()
TYPES = ('.docx', '.pdf', '.txt', '.md')
MAX_EXTRACT = 6000
_cache = {}


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
    """The file inside the library for a pointer, or None (never outside the library)."""
    if not rel: return None
    rel = rel.replace('\\', '/').strip()
    for prefix in (ROOT.name, 'Policy library'):                 # pointers written as "Policy library\file.docx"
        if rel.lower().startswith(prefix.lower() + '/'): rel = rel[len(prefix) + 1:]; break
    p = (ROOT / rel).resolve()
    if ROOT not in p.parents or p.suffix.lower() not in TYPES or not p.is_file(): return None
    return p


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
        out.append({'path': str(p.relative_to(ROOT)), 'name': p.name, 'section': sec or '', 'title': title, 'text': part})
    return out, skipped
