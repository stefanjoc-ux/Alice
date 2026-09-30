"""Generated images: extract from Responses API output and store as files, not database blobs."""
import base64
import binascii
import re
import uuid
import substrate_store as store

MAX_BYTES = 20_000_000
HEX32 = re.compile(r'[0-9a-f]{32}')
NAME = re.compile(r'[0-9a-f]{32}\.(png|jpg|webp)')


def _extension(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if raw.startswith(b'\xff\xd8\xff'): return 'jpg'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP': return 'webp'
    return None


def save_generated(response, chat_id):
    """Save every image_generation_call result. Returns [{'path','prompt'}]. Never writes unrecognised bytes."""
    if not HEX32.fullmatch(chat_id or ''):
        raise ValueError('Invalid chat ID for image storage.')
    saved = []
    for item in getattr(response, 'output', None) or []:
        if getattr(item, 'type', None) != 'image_generation_call':
            continue
        data = getattr(item, 'result', None)
        if not data:
            continue
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            continue
        ext = _extension(raw)
        if not ext or len(raw) > MAX_BYTES:
            continue
        folder = store.IMAGE_DIR / chat_id
        folder.mkdir(parents=True, exist_ok=True)
        name = f'{uuid.uuid4().hex}.{ext}'
        (folder / name).write_bytes(raw)
        saved.append({'path': f'{chat_id}/{name}', 'prompt': (getattr(item, 'revised_prompt', None) or '')[:1000]})
    return saved


def file_path(chat_id, name):
    """Resolve a stored image path, or None. Strict patterns prevent path traversal."""
    if not HEX32.fullmatch(chat_id) or not NAME.fullmatch(name):
        return None
    path = store.IMAGE_DIR / chat_id / name
    return path if path.is_file() else None
