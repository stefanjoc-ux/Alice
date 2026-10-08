"""Talking to Azure with a managed identity, stdlib only: tokens, Blob storage (write new blobs, list, read, stream) and
Azure Resource Manager. Used by the nightly off-site copy (backup.py), the restore (restore.py) and the restore drill
(drill.py). It never imports the rest of Alice, so a restore can run before the target database has any tables.
Every call goes through HTTP / STREAM, which the tests replace."""
import base64
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BLOCK = 8 * 1024 * 1024          # one Put Block request: 8 MiB (50,000 blocks = 390 GiB per blob)
STORAGE_VERSION = '2023-11-03'
ARM = 'https://management.azure.com'
_token = {}


def _http(method, url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() or b''


def _stream(url, headers=None, timeout=300):
    """A GET whose body is read as a file (large blobs). Raises on anything but 200."""
    r = urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout)
    if r.status != 200: raise RuntimeError(f'HTTP {r.status}')
    return r


HTTP = _http
STREAM = _stream


def token_for(resource):
    now = time.time()
    hit = _token.get(resource)
    if hit and now < hit[1] - 120: return hit[0]
    if not (os.environ.get('IDENTITY_ENDPOINT') and os.environ.get('IDENTITY_HEADER')):
        raise RuntimeError('no managed identity here (IDENTITY_ENDPOINT is not set): this runs in Azure only')
    q = {'resource': resource, 'api-version': '2019-08-01'}
    cid = os.environ.get('ALICE_IDENTITY_CLIENT_ID', '')
    if cid: q['client_id'] = cid
    status, _, body = HTTP('GET', os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), None,
                           {'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}, 15)
    if status != 200: raise RuntimeError(f'the managed identity endpoint answered {status}')
    d = json.loads(body.decode('utf-8'))
    _token[resource] = (d['access_token'], float(d.get('expires_on') or now + 3000))
    return d['access_token']


def azure_message(status, body):
    """What Azure said, briefly, without echoing anything sent."""
    text = (body or b'').decode('utf-8', 'replace') if isinstance(body, (bytes, bytearray)) else str(body or '')
    m = re.search(r'<Message>(.*?)</Message>', text, re.S) or re.search(r'"message"\s*:\s*"([^"]{0,300})', text)
    msg = ' '.join((m.group(1) if m else '').split())[:220]
    return f'HTTP {status}' + (f': {msg}' if msg else '')


# ---------------- Blob storage ----------------
class Blobs:
    """One container in one storage account, reached with the managed identity (no keys). Writes only ever create new
    blobs (If-None-Match: *), so nothing is overwritten."""

    def __init__(self, account, container, refuse=()):
        account = (account or '').strip().lower()
        if not re.fullmatch(r'[a-z0-9]{3,24}', account):
            raise RuntimeError('the storage account name is not set or not valid')
        if account in {a for a in refuse if a}:
            raise RuntimeError('refusing to use the live file share\'s storage account here')
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])', container or ''):
            raise RuntimeError('the container name is not valid')
        self.account, self.container = account, container
        self.host = f'{account}.blob.core.windows.net'
        self.base = f'https://{self.host}/{container}/'

    def _headers(self, extra=None):
        h = {'Authorization': 'Bearer ' + token_for('https://storage.azure.com/'), 'x-ms-version': STORAGE_VERSION,
             'x-ms-date': datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}
        h.update(extra or {})
        return h

    def _url(self, name, query=''):
        return self.base + urllib.parse.quote(name) + query

    # reading
    def list(self, prefix=''):
        """Blob names under a prefix, in name order."""
        names, marker = [], ''
        while True:
            q = '?restype=container&comp=list&maxresults=5000' + (f'&prefix={urllib.parse.quote(prefix)}' if prefix else '') + (f'&marker={urllib.parse.quote(marker)}' if marker else '')
            status, _, body = HTTP('GET', self.base.rstrip('/') + q, None, self._headers(), 60)
            if status != 200: raise RuntimeError(f'could not list {self.account}/{self.container} ({azure_message(status, body)})')
            text = body.decode('utf-8', 'replace')
            names += re.findall(r'<Name>(.*?)</Name>', text)
            m = re.search(r'<NextMarker>(.+?)</NextMarker>', text)
            if not m: return sorted(names)
            marker = m.group(1)

    def get(self, name):
        status, _, body = HTTP('GET', self._url(name), None, self._headers(), 120)
        if status != 200: raise RuntimeError(f'could not read {name} ({azure_message(status, body)})')
        return body

    def stream(self, name):
        return STREAM(self._url(name), self._headers(), 600)

    # writing (new blobs only)
    def put_block(self, name, block_id, data):
        for attempt in range(3):
            try:
                status, _, body = HTTP('PUT', self._url(name, '?comp=block&blockid=' + urllib.parse.quote(block_id)), data,
                                       self._headers({'Content-Length': str(len(data))}), 300)
            except OSError as e:
                status, body = 0, str(e).encode()
            if status == 201: return
            if attempt == 2: raise RuntimeError(f'{self.account} refused a block of {name} ({azure_message(status, body)})')
            time.sleep(2 * (attempt + 1))

    def commit(self, name, block_ids, content_type):
        xml = ('<?xml version="1.0" encoding="utf-8"?><BlockList>' + ''.join(f'<Latest>{b}</Latest>' for b in block_ids)
               + '</BlockList>').encode('utf-8')
        status, _, body = HTTP('PUT', self._url(name, '?comp=blocklist'), xml,
                               self._headers({'Content-Type': 'application/xml', 'Content-Length': str(len(xml)),
                                              'x-ms-blob-content-type': content_type, 'If-None-Match': '*'}), 120)
        if status != 201: raise RuntimeError(f'{self.account} refused to save {name} ({azure_message(status, body)})')

    def writer(self, name, content_type='application/octet-stream'):
        return BlockWriter(self, name, content_type)

    def put(self, name, data, content_type):
        w = self.writer(name, content_type); w.write(data); w.close()
        return w.size, w.sha256


class BlockWriter(io.RawIOBase):
    """A write-only file that streams to one blob in BLOCK-sized blocks (nothing is written to local disk)."""

    def __init__(self, blob, name, content_type):
        super().__init__()
        self.blob, self.name, self.content_type = blob, name, content_type
        self.buf = bytearray(); self.ids = []; self.size = 0; self._h = hashlib.sha256(); self.sha256 = ''; self.done = False

    def writable(self): return True

    def write(self, b):
        b = bytes(b); self.buf += b; self.size += len(b); self._h.update(b)
        while len(self.buf) >= BLOCK:
            self._send(bytes(self.buf[:BLOCK])); del self.buf[:BLOCK]
        return len(b)

    def _send(self, data):
        bid = base64.b64encode(f'{len(self.ids):08d}'.encode()).decode()
        self.blob.put_block(self.name, bid, data); self.ids.append(bid)

    def close(self):
        if self.done: return super().close()
        self.done = True
        if self.buf: self._send(bytes(self.buf)); self.buf = bytearray()
        self.blob.commit(self.name, self.ids, self.content_type)
        self.sha256 = self._h.hexdigest()
        return super().close()


# ---------------- Azure Resource Manager ----------------
def arm(method, path, api, body=None, ok=(200, 201, 202, 204), timeout=60):
    """One Resource Manager call on a resource path (/subscriptions/...). Returns (status, headers, parsed JSON)."""
    url = ARM + path + ('&' if '?' in path else '?') + 'api-version=' + api
    data = json.dumps(body).encode('utf-8') if body is not None else (b'' if method in ('POST', 'PUT') else None)
    headers = {'Authorization': 'Bearer ' + token_for(ARM + '/')}
    if data is not None: headers['Content-Type'] = 'application/json'
    status, h, raw = HTTP(method, url, data, headers, timeout)
    if status not in ok: raise RuntimeError(f'Azure answered {azure_message(status, raw)} to {method} {path.rsplit("/providers/", 1)[-1]}')
    try: parsed = json.loads((raw or b'').decode('utf-8') or '{}')
    except ValueError: parsed = {}
    return status, h, parsed


def arm_get(path, api):
    return arm('GET', path, api, ok=(200,))[2]


# ---------------- PostgreSQL addresses ----------------
def pg_conninfo(url):
    """(conninfo without the password, password) for a libpq keyword string or a postgresql:// address, so pg_dump,
    pg_restore and psql get the password in PGPASSWORD, never on their command line."""
    url = (url or '').strip()
    parts = {}
    if url.startswith(('postgres://', 'postgresql://')):
        u = urllib.parse.urlsplit(url)
        parts = {'host': u.hostname or '', 'port': str(u.port or ''), 'dbname': (u.path or '/').lstrip('/'),
                 'user': urllib.parse.unquote(u.username or ''), 'password': urllib.parse.unquote(u.password or '')}
        for k, v in urllib.parse.parse_qsl(u.query): parts[k] = v
    else:
        for item in url.split():
            if '=' in item:
                k, v = item.split('=', 1); parts[k.strip()] = v.strip().strip("'")
    if not parts.get('host') or not parts.get('dbname'): raise RuntimeError('not a PostgreSQL address')
    password = parts.pop('password', '')
    keep = {k: v for k, v in parts.items() if k in ('host', 'port', 'dbname', 'user', 'sslmode') and v}
    return ' '.join(f'{k}={v}' for k, v in keep.items()), password
