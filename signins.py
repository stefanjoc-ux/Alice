"""Sign-ins and devices: where Alice is signed in, and signing out one device or all of them.

In Azure, Container Apps sign-in (Entra ID) keeps each browser's session in that browser's own cookie, so Alice cannot
reach into another device to delete it. Instead she recognises each session by who signed in and when (the 'iat' claim
in the X-MS-CLIENT-PRINCIPAL header that sign-in passes on, trusted only with ALICE_TRUST_EASYAUTH=1), notes the device
and address it is used from, and turns a session away once you sign it out here:
  one device   its session is marked signed out (signin_sessions.signed_out_at)
  everywhere   every session that signed in before that moment (setting signout_everywhere_at), this one included
Entra back-dates 'iat' by up to 5 minutes, so a session counts as older only if its 'iat' is more than SKEW seconds
before the moment you pressed it. A session last used more than SESSION_HOURS ago has expired on its own.
Only the browser, the operating system and the network address are kept, never what was done. 30 days kept.
"""
import base64
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone, timedelta

import substrate_store as store

SKEW = 300
SESSION_HOURS = 8               # Container Apps sign-in cookie lifetime (default)
TOUCH_EVERY = 300               # write "last used" at most every 5 minutes per session
KEEP_DAYS = 30
OPEN = ('/healthz', '/signout', '/signed-out', '/static/', '/favicon', '/manifest.webmanifest', '/icon-')


def _schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS signin_sessions (id TEXT PRIMARY KEY, email TEXT NOT NULL, signed_in_at INTEGER NOT NULL, '
              'first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, device TEXT NOT NULL DEFAULT \'\', address TEXT NOT NULL DEFAULT \'\', '
              'requests INTEGER NOT NULL DEFAULT 0, signed_out_at TEXT, signed_out_how TEXT NOT NULL DEFAULT \'\')')


with store.db() as _c: _schema(_c)


def trusted():
    return os.environ.get('ALICE_TRUST_EASYAUTH') == '1'


def principal(headers):
    """(email, signed-in time in seconds) from the sign-in headers; ('', 0) when not behind sign-in or unknown."""
    if not trusted(): return '', 0
    email = ' '.join(headers.get('x-ms-client-principal-name', '').split())[:200].lower()
    try:
        claims = json.loads(base64.b64decode(headers.get('x-ms-client-principal', '') + '==').decode('utf-8')).get('claims', [])
        iat = int(next((c.get('val') for c in claims if c.get('typ') == 'iat'), 0) or 0)
    except Exception:
        iat = 0
    return email, iat


def session_id(email, iat):
    return hashlib.sha256(f'{email}|{iat}'.encode()).hexdigest()[:20]


def device_name(ua):
    """A short, readable name for the browser and system, e.g. 'Edge on Windows', 'Chrome on Android tablet'."""
    ua = ua or ''
    if 'Edg/' in ua or 'EdgA/' in ua or 'EdgiOS/' in ua: b = 'Edge'
    elif 'SamsungBrowser/' in ua: b = 'Samsung Internet'
    elif 'Firefox/' in ua or 'FxiOS/' in ua: b = 'Firefox'
    elif 'Chrome/' in ua or 'CriOS/' in ua: b = 'Chrome'
    elif 'Safari/' in ua: b = 'Safari'
    else: b = 'A browser'
    if 'Windows' in ua: s = 'Windows'
    elif 'iPad' in ua: s = 'iPad'
    elif 'iPhone' in ua: s = 'iPhone'
    elif 'Android' in ua: s = 'Android phone' if 'Mobile' in ua else 'Android tablet'
    elif 'CrOS' in ua: s = 'Chromebook'
    elif 'Mac OS X' in ua or 'Macintosh' in ua: s = 'Mac'
    elif 'Linux' in ua: s = 'Linux'
    else: s = 'an unknown system'
    return f'{b} on {s}'


def address(headers, client_host=''):
    """The network address the request came from (the first one Azure's front door saw)."""
    xff = (headers.get('x-forwarded-for') or '').split(',')[0].strip()
    a = xff or client_host or ''
    return a if re.fullmatch(r'[0-9a-fA-F.:\[\]]{3,60}', a) else ''


# ---------------- the check on every request (cached; one small read every 15 s) ----------------
_lock = threading.Lock()
_cache = {'at': 0.0, 'cut': 0, 'out': frozenset()}
_touched = {}


def _state():
    now = time.time()
    if now - _cache['at'] > 15:
        with store.db() as c:
            r = c.execute("SELECT value FROM settings WHERE key='signout_everywhere_at'").fetchone()
            out = frozenset(x[0] for x in c.execute('SELECT id FROM signin_sessions WHERE signed_out_at IS NOT NULL'))
        try: cut = int(float(r[0])) if r else 0
        except (TypeError, ValueError): cut = 0
        _cache.update(at=now, cut=cut, out=out)
    return _cache['cut'], _cache['out']


def _forget_cache():
    _cache['at'] = 0.0


def check(headers, user_agent='', client_host=''):
    """Called for every request behind sign-in. Returns 'ok', or 'out' if this session was signed out here.
    Also notes the session (device, address, last used), at most every few minutes."""
    email, iat = principal(headers)
    if not email or not iat: return 'ok'
    cut, out = _state()
    sid = session_id(email, iat)
    if (cut and iat < cut - SKEW) or sid in out: return 'out'
    now = time.time()
    if now - _touched.get(sid, 0) >= TOUCH_EVERY:
        _touched[sid] = now
        try: _touch(sid, email, iat, device_name(user_agent), address(headers, client_host))
        except Exception: pass
    return 'ok'


def _touch(sid, email, iat, device, addr):
    t = store.now()
    with store.db() as c:
        c.execute('INSERT INTO signin_sessions (id,email,signed_in_at,first_seen,last_seen,device,address,requests) VALUES (?,?,?,?,?,?,?,1) '
                  'ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen, device=excluded.device, address=excluded.address, '
                  'requests=signin_sessions.requests+1', (sid, email, iat, t, t, device, addr))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
        c.execute('DELETE FROM signin_sessions WHERE last_seen < ?', (cutoff,))


# ---------------- the page ----------------
def _mine_only():
    """Other people's sessions are shown (and signed out) by Admins and Owners only (permissions.py); everyone else sees their own."""
    v = store.viewer()
    return None if v is None or v.full or v.role == 'admin' else (v.email or '-').lower()


def listing(headers):
    """Every session seen in the last 30 days, newest first: active, expired or signed out; which one is this device."""
    email, iat = principal(headers)
    me = session_id(email, iat) if email and iat else ''
    cut, _ = _state()
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM signin_sessions ORDER BY last_seen DESC')]
    only = _mine_only()
    if only is not None: rows = [r for r in rows if r['email'] == only]
    expire = (datetime.now(timezone.utc) - timedelta(hours=SESSION_HOURS)).isoformat()
    for r in rows:
        if r['signed_out_at']: r['state'] = 'signed_out'
        elif cut and r['signed_in_at'] < cut - SKEW: r['state'] = 'signed_out'; r['signed_out_how'] = r['signed_out_how'] or 'everywhere'
        elif r['last_seen'] < expire: r['state'] = 'expired'
        else: r['state'] = 'active'
        r['this_device'] = r['id'] == me
        r['signed_in'] = datetime.fromtimestamp(r['signed_in_at'], timezone.utc).isoformat()
    return {'sessions': rows, 'active': sum(1 for r in rows if r['state'] == 'active'), 'behind_signin': trusted(),
            'can_tell_sessions_apart': bool(me), 'signout_everywhere_at': datetime.fromtimestamp(cut, timezone.utc).isoformat() if cut else '',
            'session_hours': SESSION_HOURS}


def sign_out(sid):
    """Sign out one device: its session is turned away from its next request."""
    with store.db() as c:
        r = c.execute('SELECT device, address, signed_out_at, email FROM signin_sessions WHERE id=?', (sid,)).fetchone()
        only = _mine_only()
        if not r or (only is not None and r['email'] != only): raise ValueError('No such session.')
        if r['signed_out_at']: return {'ok': True, 'already': True}
        c.execute("UPDATE signin_sessions SET signed_out_at=?, signed_out_how='this device' WHERE id=?", (store.now(), sid))
        store.audit(c, 'signed_out_device', 'sign-in', 'human_control', f'Signed out {r["device"]}' + (f' ({r["address"]})' if r['address'] else ''))
    _forget_cache()
    return {'ok': True}


def sign_out_everywhere(headers):
    if not trusted(): raise ValueError('Alice is running on this computer only; there is nothing to sign out elsewhere.')
    if not principal(headers)[1]:
        raise ValueError('Sign-in did not pass on a sign-in time, so Alice cannot tell sessions apart. Nothing was changed.')
    now = int(time.time())
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES ('signout_everywhere_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
        c.execute("UPDATE signin_sessions SET signed_out_at=?, signed_out_how='everywhere' WHERE signed_out_at IS NULL", (store.now(),))
        store.audit(c, 'signed_out_everywhere', 'sign-in', 'human_control', 'Every Alice session signed in before now must sign in again')
    _forget_cache()
    return {'ok': True, 'next': '/signout?everywhere=1'}
