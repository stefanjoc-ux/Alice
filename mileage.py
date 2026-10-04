"""Mileage Clerk, parts 1-3: read a vehicle tracker export, classify each day's journeys with YOUR place rules, and
prepare TMC mileage entries that wait for your approval. Filling in TMC itself (part 4) runs later in your own
signed-in browser, from an entry you approved here; nothing in Alice logs in to TMC or stores TMC credentials.

- Places are yours, kept in the database (never in code or git): home, personal (gym, shops, airport runs) and
  business (with the purpose wording and the TMC location and postcode). A place matches a tracker location by its
  street-and-postcode key, or by distance from where you were (for the exports' unnamed "United Kingdom" stops).
  You add and change places on the Mileage page; that is your action, logged. Places you have not classified count as
  personal, and a long trip to one is flagged, so a new client visit is never missed silently.
- Classification is deterministic (no model): legs are joined into journeys between known places (an unknown stop
  such as an A9 lay-by is a waypoint); a journey that starts or ends at a business place is business. Gaps are
  flagged, never invented: a day that starts or ends away from home gets a warning.
- Drafts: one per business day (date, daily business miles, vehicle, start row, business stops with purpose).
  Approvals are exact: each records the action (fill or save), who, when and a hash of the exact entry; changing the
  entry afterwards cancels them. Save approval needs fill approval first. Approvals are never automatic.
"""
import csv
import hashlib
import io
import json
import math
import re
import uuid
from datetime import datetime

import substrate_store as store

KINDS = ('home', 'personal', 'business')
LONG_UNKNOWN_MILES = 15.0          # a journey this long to or from an unclassified place is flagged
DESTINATION_MINUTES = 30          # stopping this long at an unclassified place makes it a destination, not a waypoint
MATCH_METRES = 300                 # how close a stop must be to a place's known spot to match it
FULL_POSTCODE = re.compile(r'[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}')
POSTCODE = re.compile(r'\b([A-Z]{1,2}\d[A-Z\d]?)(?:\s*(\d[A-Z]{2}|\d))?\b')
FIELDS = {'start date': 'start_date', 'start time': 'start_time', 'end date': 'end_date', 'end time': 'end_time',
          'start location': 'start_location', 'start coordinates': 'start_coords', 'end location': 'end_location',
          'end coordinates': 'end_coords', 'distance(miles)': 'miles'}


def _schema():
    with store.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS mileage_places (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, "
                  "match_keys TEXT NOT NULL DEFAULT '[]', lat REAL, lon REAL, purpose TEXT NOT NULL DEFAULT '', "
                  "tmc_location TEXT NOT NULL DEFAULT '', tmc_postcode TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS mileage_imports (id TEXT PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL, "
                  "legs TEXT NOT NULL, first_date TEXT, last_date TEXT, created_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS mileage_drafts (id TEXT PRIMARY KEY, import_id TEXT NOT NULL, day TEXT NOT NULL, "
                  "miles REAL NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', "
                  "approvals TEXT NOT NULL DEFAULT '[]', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS mileage_drafts_day ON mileage_drafts(import_id, day)')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('mileage_vehicle','')")


_schema()


def _clean(v, n=200): return ' '.join(str(v or '').split())[:n]


# ---------------- part 1: read the export ----------------
def _coords(text):
    try:
        lat, lon = (float(x) for x in str(text).split(','))
        return lat, lon
    except (TypeError, ValueError):
        return None, None


def place_key(location, coords=''):
    """Street (and number) plus postcode for named stops; a ~100 m grid square for the exports' unnamed stops."""
    parts = [p.strip() for p in str(location or '').split(',') if p.strip()]
    named = [p for p in parts if p.lower() not in ('united kingdom', 'uk')]
    if named:
        street = named[0].lower()
        pc = POSTCODE.search(named[1].upper()) if len(named) > 1 else None
        return 'loc:' + re.sub(r'\s+', ' ', street) + '|' + (pc.group(0).replace(' ', '') if pc else '')
    lat, lon = _coords(coords)
    return f'geo:{lat:.3f},{lon:.3f}' if lat is not None else 'unknown'


def label(location):
    parts = [p.strip() for p in str(location or '').split(',') if p.strip() and p.strip().lower() != 'united kingdom']
    return ', '.join(parts[:2]) if parts else 'Unnamed stop'


def parse(text):
    """Tracker CSV (comma separated, with a header row) -> legs sorted by start; refuses anything that is not one."""
    text = text.lstrip('﻿')
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows: raise ValueError('That file has no rows. Export the trips as CSV from the tracker and try again.')
    head = {k.strip().lower(): k for k in rows[0].keys() if k}
    missing = [f for f in FIELDS if f not in head]
    if missing: raise ValueError('This does not look like a tracker export: missing ' + ', '.join(missing) + '.')
    legs = []
    for i, r in enumerate(rows, 2):
        g = {FIELDS[f]: (r.get(head[f]) or '').strip() for f in FIELDS}
        try:
            start = datetime.strptime(g['start_date'] + ' ' + g['start_time'], '%d/%m/%Y %H:%M')
            miles = round(float(g['miles']), 1)
        except ValueError:
            raise ValueError(f'Row {i}: the date, time or distance is not in the expected format.') from None
        if miles < 0 or miles > 1000: raise ValueError(f'Row {i}: a distance of {miles} miles is not believable.')
        legs.append({'start': start.isoformat(timespec='minutes'), 'end_date': g['end_date'], 'end_time': g['end_time'],
                     'from': _clean(g['start_location']), 'from_key': place_key(g['start_location'], g['start_coords']),
                     'from_coords': g['start_coords'], 'to': _clean(g['end_location']),
                     'to_key': place_key(g['end_location'], g['end_coords']), 'to_coords': g['end_coords'], 'miles': miles})
    legs.sort(key=lambda x: x['start'])
    return legs


# ---------------- places (yours) ----------------
def places():
    with store.db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM mileage_places ORDER BY kind, lower(name)')]
    for r in rows: r['match_keys'] = json.loads(r['match_keys'] or '[]')
    return rows


def save_place(pid, name, kind, keys=(), purpose='', tmc_location='', tmc_postcode='', lat=None, lon=None):
    """Create or update a place. Your action on the Mileage page, logged; never done by a model."""
    name, kind = _clean(name, 80), (kind or '').strip()
    if not name: raise ValueError('Give the place a name.')
    if kind not in KINDS: raise ValueError('A place is home, personal or business.')
    purpose, tmc_location, tmc_postcode = _clean(purpose, 200), _clean(tmc_location, 200), _clean(tmc_postcode, 10).upper()
    if kind == 'business' and not purpose: raise ValueError('A business place needs the purpose wording for TMC.')
    if kind in ('home', 'business') and not (tmc_location and tmc_postcode):
        raise ValueError('Give the location and postcode as they should appear in TMC.')
    if tmc_postcode and not FULL_POSTCODE.fullmatch(tmc_postcode):
        raise ValueError('That postcode does not look right (e.g. PH13 9JJ).')
    if tmc_postcode and ' ' not in tmc_postcode: tmc_postcode = tmc_postcode[:-3] + ' ' + tmc_postcode[-3:]
    keys = [k for k in dict.fromkeys(_clean(k, 120) for k in keys) if k.startswith(('loc:', 'geo:'))][:40]
    now = store.now()
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if kind == 'home' and c.execute("SELECT 1 FROM mileage_places WHERE kind='home' AND id<>?", (pid or '',)).fetchone():
            raise ValueError('There is already a home. Edit that one instead.')
        for k in keys:      # a tracker location belongs to one place only
            for r in c.execute('SELECT id,name,match_keys FROM mileage_places WHERE id<>?', (pid or '',)).fetchall():
                if k in json.loads(r['match_keys']): raise ValueError(f'That stop already belongs to "{r["name"]}".')
        if pid:
            old = c.execute('SELECT match_keys FROM mileage_places WHERE id=?', (pid,)).fetchone()
            if not old: raise ValueError('Place not found.')
            keys = list(dict.fromkeys(json.loads(old['match_keys']) + keys))
            c.execute('UPDATE mileage_places SET name=?,kind=?,match_keys=?,purpose=?,tmc_location=?,tmc_postcode=?,'
                      'lat=coalesce(?,lat),lon=coalesce(?,lon),updated_at=? WHERE id=?',
                      (name, kind, json.dumps(keys), purpose, tmc_location, tmc_postcode, lat, lon, now, pid))
        else:
            pid = uuid.uuid4().hex
            c.execute('INSERT INTO mileage_places(id,name,kind,match_keys,lat,lon,purpose,tmc_location,tmc_postcode,created_at,updated_at) '
                      'VALUES (?,?,?,?,?,?,?,?,?,?,?)', (pid, name, kind, json.dumps(keys), lat, lon, purpose, tmc_location, tmc_postcode, now, now))
        store.audit(c, 'mileage_place_saved', pid, 'human_review', f'{name}: {kind}' + (f' ({purpose})' if purpose else ''))
    return {'id': pid}


def delete_place(pid):
    with store.db() as c:
        r = c.execute('SELECT name FROM mileage_places WHERE id=?', (pid,)).fetchone()
        if not r: raise ValueError('Place not found.')
        c.execute('DELETE FROM mileage_places WHERE id=?', (pid,))
        store.audit(c, 'mileage_place_deleted', pid, 'human_review', r['name'])
    return {'deleted': pid}


def set_vehicle(reg):
    reg = re.sub(r'\s+', '', str(reg or '')).upper()[:10]
    if reg and not re.fullmatch(r'[A-Z0-9]{2,8}', reg): raise ValueError('That registration does not look right.')
    with store.db() as c:
        c.execute("UPDATE settings SET value=? WHERE key='mileage_vehicle'", (reg,))
        store.audit(c, 'mileage_vehicle_set', 'settings', 'human_review', reg or '(none)')
    return {'vehicle': reg}


def vehicle():
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='mileage_vehicle'").fetchone()
    return row[0] if row else ''


def _metres(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def _matcher(pl):
    by_key = {k: p for p in pl for k in p['match_keys']}
    spots = [p for p in pl if p['lat'] is not None and p['lon'] is not None]
    def find(key, coords):
        if key in by_key: return by_key[key]
        lat, lon = _coords(coords)
        if lat is None: return None
        best = min(((_metres((lat, lon), (p['lat'], p['lon'])), p) for p in spots), default=(None, None), key=lambda x: x[0])
        return best[1] if best[0] is not None and best[0] <= MATCH_METRES else None
    return find


# ---------------- part 2: classify days, prepare drafts ----------------
def classify(legs, pl=None):
    """Days with their journeys, business and personal miles, warnings, and the stops not yet classified."""
    pl = places() if pl is None else pl
    find = _matcher(pl)
    days, unknown = {}, {}
    for leg in legs:
        a, b = find(leg['from_key'], leg['from_coords']), find(leg['to_key'], leg['to_coords'])
        leg = dict(leg, from_place=a and {'id': a['id'], 'name': a['name'], 'kind': a['kind']},
                   to_place=b and {'id': b['id'], 'name': b['name'], 'kind': b['kind']})
        for side, p in (('from', a), ('to', b)):
            if not p:
                u = unknown.setdefault(leg[side + '_key'], {'key': leg[side + '_key'], 'label': label(leg[side]), 'visits': 0, 'coords': leg[side + '_coords']})
                u['visits'] += 1
        days.setdefault(leg['start'][:10], []).append(leg)
    out = []
    for day, dl in sorted(days.items()):
        journeys, cur = [], []
        for leg in dl:                 # join legs through unknown stops (waypoints) into journeys between known places
            cur.append(leg)
            if leg['to_place']: journeys.append(cur); cur = []
        if cur: journeys.append(cur)
        warnings, biz, per, stops = [], 0.0, 0.0, []
        for j in journeys:
            ends = [j[0]['from_place'], j[-1]['to_place']]
            miles = round(sum(x['miles'] for x in j), 1)
            business = any(e and e['kind'] == 'business' for e in ends)
            for x in j: x['business'] = business
            if business:
                biz += miles
                for x in j:
                    for e in (x['from_place'], x['to_place']):
                        if e and e['kind'] == 'business' and (not stops or stops[-1] != e['id']): stops.append(e['id'])
            else:
                per += miles
                # an unclassified place you stayed at (not a lay-by on the way), or a journey ending at one
                stayed = [x for x, n in zip(j, j[1:]) if _dwell(x, n) >= DESTINATION_MINUTES]
                where = [x['to'] for x in stayed] + ([j[-1]['to']] if not j[-1]['to_place'] else []) + ([j[0]['from']] if not j[0]['from_place'] else [])
                if where and miles >= LONG_UNKNOWN_MILES:
                    warnings.append(f'{miles} miles to or from a place you have not classified ({label(where[0])}): counted as personal. Classify it if it was work.')
        if biz > 0:        # checks that matter for a claim: where the day starts and ends, and missing legs
            first, last = dl[0]['from_place'], dl[-1]['to_place']
            if not first or first['kind'] != 'home':
                warnings.append(f'The day starts away from home ({label(dl[0]["from"])}): a leg may be missing from the export.')
            if not last or last['kind'] != 'home':
                warnings.append(f'The day ends away from home ({label(dl[-1]["to"])}): a leg may be missing, or it carries on the next day.')
            for p, n in zip(dl, dl[1:]):
                if not _same_spot(p, n):
                    warnings.append(f'Gap after {p["end_time"]}: one leg ends at {label(p["to"])} and the next starts at {label(n["from"])} '
                                    '(the tracker may have dropped a short leg). Not added: check it.')
        out.append({'day': day, 'legs': dl, 'tracked': round(sum(x['miles'] for x in dl), 1), 'business': round(biz, 1),
                    'personal': round(per, 1), 'stops': stops, 'warnings': warnings})
    return {'days': out, 'unknown': sorted(unknown.values(), key=lambda u: -u['visits'])}


def _dwell(p, n):
    """Minutes between one leg ending and the next starting."""
    try:
        end = datetime.strptime(p['end_date'] + ' ' + p['end_time'], '%d/%m/%Y %H:%M')
        return (datetime.fromisoformat(n['start']) - end).total_seconds() / 60
    except ValueError:
        return 0


def _same_spot(p, n):
    if p['to_key'] == n['from_key']: return True
    if p['to_place'] and n['from_place'] and p['to_place']['id'] == n['from_place']['id']: return True
    a, b = _coords(p['to_coords']), _coords(n['from_coords'])
    return a[0] is not None and b[0] is not None and _metres(a, b) <= MATCH_METRES


def _payload(day, pl_by_id, home, miles):
    d = datetime.strptime(day['day'], '%Y-%m-%d').strftime('%d/%m/%Y')
    rows = [{'row_type': 'start', 'location': home['tmc_location'], 'postcode': home['tmc_postcode']}]
    for pid in day['stops']:
        p = pl_by_id[pid]
        rows.append({'row_type': 'stop', 'location': p['tmc_location'], 'postcode': p['tmc_postcode'], 'purpose': p['purpose']})
    return {'date': d, 'daily_business_miles': miles, 'vehicle_registration': vehicle(), 'rows': rows, 'warnings': day['warnings']}


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def import_export(name, text):
    """Read an export, store its legs, and prepare a draft for each business day. Re-importing the same file is a no-op."""
    legs = parse(text)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    pl = places()
    home = next((p for p in pl if p['kind'] == 'home'), None)
    with store.db() as c:
        dup = c.execute('SELECT id FROM mileage_imports WHERE sha256=?', (digest,)).fetchone()
    if dup: return {'id': dup[0], 'duplicate': True, **summary(dup[0])}
    iid = uuid.uuid4().hex
    with store.db() as c:
        c.execute('INSERT INTO mileage_imports(id,name,sha256,legs,first_date,last_date,created_at) VALUES (?,?,?,?,?,?,?)',
                  (iid, _clean(name, 120) or 'Trips.csv', digest, json.dumps(legs), legs[0]['start'][:10], legs[-1]['start'][:10], store.now()))
        store.audit(c, 'mileage_imported', iid, 'human_review', f'{len(legs)} legs, {legs[0]["start"][:10]} to {legs[-1]["start"][:10]}')
    if home: refresh_drafts(iid)
    return {'id': iid, 'duplicate': False, **summary(iid)}


def refresh_drafts(iid):
    """(Re)build the drafts after places change. An approved or saved entry is never changed: if its day's figures
    have moved, it is marked for you to look at instead."""
    with store.db() as c:
        r = c.execute('SELECT legs FROM mileage_imports WHERE id=?', (iid,)).fetchone()
    if not r: raise ValueError('Import not found.')
    pl = places()
    home = next((p for p in pl if p['kind'] == 'home'), None)
    if not home: raise ValueError('Add your home place first: every entry starts there.')
    by_id = {p['id']: p for p in pl}
    res = classify(json.loads(r['legs']), pl)
    made = changed = 0
    with store.db() as c:
        existing = {x['day']: dict(x) for x in c.execute('SELECT * FROM mileage_drafts WHERE import_id=?', (iid,))}
        for d in res['days']:
            ex = existing.get(d['day'])
            if d['business'] <= 0:
                if ex and ex['status'] == 'draft':
                    c.execute("UPDATE mileage_drafts SET status='withdrawn',updated_at=? WHERE id=?", (store.now(), ex['id']))
                continue
            payload = _payload(d, by_id, home, d['business'])
            h = _hash(payload)
            if not ex:
                c.execute('INSERT INTO mileage_drafts(id,import_id,day,miles,payload,payload_hash,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                          (uuid.uuid4().hex, iid, d['day'], d['business'], json.dumps(payload), h, 'draft', store.now(), store.now()))
                made += 1
            elif ex['payload_hash'] != h:
                if ex['status'] in ('draft', 'withdrawn', 'fill_approved'):      # not in TMC yet: rebuild; approvals no longer match
                    c.execute("UPDATE mileage_drafts SET miles=?,payload=?,payload_hash=?,status='draft',approvals='[]',updated_at=? WHERE id=?",
                              (d['business'], json.dumps(payload), h, store.now(), ex['id']))
                else:
                    c.execute('UPDATE mileage_drafts SET notes=?,updated_at=? WHERE id=?',
                              ('The figures for this day have changed since it was saved in TMC. Check TMC.', store.now(), ex['id']))
                changed += 1
    return {'created': made, 'changed': changed}


def summary(iid):
    with store.db() as c:
        r = c.execute('SELECT * FROM mileage_imports WHERE id=?', (iid,)).fetchone()
        drafts = [dict(x) for x in c.execute('SELECT * FROM mileage_drafts WHERE import_id=? ORDER BY day', (iid,))]
    if not r: raise ValueError('Import not found.')
    res = classify(json.loads(r['legs']))
    for d in drafts: d['payload'] = json.loads(d['payload']); d['approvals'] = json.loads(d['approvals'])
    days = res['days']
    return {'import': {k: r[k] for k in ('id', 'name', 'first_date', 'last_date', 'created_at')}, 'days': days, 'unknown': res['unknown'],
            'drafts': drafts, 'totals': {'tracked': round(sum(d['tracked'] for d in days), 1), 'business': round(sum(d['business'] for d in days), 1),
                                         'personal': round(sum(d['personal'] for d in days), 1)},
            'has_home': any(p['kind'] == 'home' for p in places()), 'vehicle': vehicle()}


def imports():
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT id,name,first_date,last_date,created_at FROM mileage_imports ORDER BY created_at DESC LIMIT 24')]


# ---------------- part 3: exact approvals ----------------
NEXT = {'fill': ('draft', 'fill_approved'), 'save': ('fill_approved', 'save_approved')}


def approve(draft_id, action, payload_hash, note=''):
    """Your approval of one exact action on one exact entry. The page sends the hash of the entry it showed you; if the
    entry has changed since, the approval is refused. Save needs fill first."""
    if action not in NEXT: raise ValueError('Unknown action.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        d = c.execute('SELECT * FROM mileage_drafts WHERE id=?', (draft_id,)).fetchone()
        if not d: raise ValueError('Entry not found.')
        if d['payload_hash'] != payload_hash: raise ValueError('This entry has changed since you looked at it. Refresh and check it again.')
        need, to = NEXT[action]
        if d['status'] != need:
            raise ValueError({'fill': 'Only a draft can be approved for filling.', 'save': 'Approve filling first; saving comes after the form is filled and checked.'}[action])
        if not json.loads(d['payload']).get('vehicle_registration'):
            raise ValueError('Set the vehicle registration first (top of the Mileage page).')
        approvals = json.loads(d['approvals']) + [{'action': action, 'hash': payload_hash, 'by': store.actor(), 'at': store.now(),
                                                   'note': _clean(note, 300)}]
        c.execute('UPDATE mileage_drafts SET status=?,approvals=?,updated_at=? WHERE id=?', (to, json.dumps(approvals), store.now(), draft_id))
        store.audit(c, 'mileage_' + action + '_approved', draft_id, 'human_review',
                    f"{json.loads(d['payload'])['date']}: {d['miles']} business miles; entry {payload_hash[:12]}")
    return {'status': to}


def reject(draft_id, note=''):
    with store.db() as c:
        d = c.execute('SELECT status FROM mileage_drafts WHERE id=?', (draft_id,)).fetchone()
        if not d: raise ValueError('Entry not found.')
        if d['status'] in ('saved', 'verified'): raise ValueError('This entry is already in TMC; change it there.')
        c.execute("UPDATE mileage_drafts SET status='rejected',approvals='[]',notes=?,updated_at=? WHERE id=?", (_clean(note, 300), store.now(), draft_id))
        store.audit(c, 'mileage_rejected', draft_id, 'human_review', _clean(note, 300) or 'Not claimed')
    return {'status': 'rejected'}


def approved_for(action, draft_id, payload_hash):
    """For the browser step (part 4): is this exact entry approved for this exact action right now?"""
    with store.db() as c:
        d = c.execute('SELECT status,payload_hash,approvals FROM mileage_drafts WHERE id=?', (draft_id,)).fetchone()
    if not d or d['payload_hash'] != payload_hash: return False
    want = {'fill': ('fill_approved', 'save_approved'), 'save': ('save_approved',)}.get(action, ())
    return d['status'] in want and any(a['action'] == action and a['hash'] == payload_hash for a in json.loads(d['approvals']))


def waiting():
    """For the Apps area and Actions: entries waiting for your fill approval (newest export first)."""
    with store.db() as c:
        rows = [dict(r) for r in c.execute("SELECT d.id, d.day, d.miles, d.import_id, i.name FROM mileage_drafts d "
                                            "JOIN mileage_imports i ON i.id = d.import_id WHERE d.status = 'draft' ORDER BY d.day")]
    return [{'title': datetime.strptime(r['day'], '%Y-%m-%d').strftime('%a %d %b %Y').replace(' 0', ' ') + f": {r['miles']} business miles",
             'detail': 'TMC entry waiting for your approval (' + r['name'] + ')', 'href': '/admin/mileage?import_id=' + r['import_id']} for r in rows]


# ---------------- overview (Apps tile and the top of the Mileage page) ----------------
def set_rate(pence):
    """Your claim rate in pence per mile, only to show what entries are worth (0 = don't show money)."""
    try: p = round(float(pence or 0), 1)
    except (TypeError, ValueError): raise ValueError('Give the rate in pence per mile, e.g. 45.') from None
    if not 0 <= p <= 200: raise ValueError('A rate between 0 and 200 pence per mile, please.')
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES ('mileage_rate_ppm',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(p),))
        store.audit(c, 'mileage_rate_set', 'settings', 'human_review', f'{p}p per mile')
    return {'rate': p}


def rate():
    with store.db() as c:
        r = c.execute("SELECT value FROM settings WHERE key='mileage_rate_ppm'").fetchone()
    try: return float(r[0]) if r else 0.0
    except (TypeError, ValueError): return 0.0


def _tax_year_start(d):
    start = d.replace(month=4, day=6)
    return start if d >= start else start.replace(year=d.year - 1)


def overview(today=None):
    """Mileage at a glance: business and personal miles per month for the last 12 months, this month, the tax year
    so far (HMRC's approved rate changes after 10,000 business miles in a tax year), and the entries: waiting for you,
    approved, in TMC, not claimed. A day covered by several exports is counted once, from the newest export."""
    from datetime import date
    today = today or date.today()
    pl = places()
    with store.db() as c:
        imps = [dict(r) for r in c.execute('SELECT id, legs, created_at, last_date FROM mileage_imports ORDER BY created_at')]
        drafts = [dict(r) for r in c.execute('SELECT import_id, day, miles, status FROM mileage_drafts')]
    by_day, newest = {}, {}
    for imp in imps:
        for d in classify(json.loads(imp['legs']), pl)['days']:
            by_day[d['day']] = (d['business'], d['personal']); newest[d['day']] = imp['id']
    status = {}
    for d in drafts:
        if newest.get(d['day']) == d['import_id']: status[d['day']] = (d['status'], d['miles'])
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append(f'{y:04d}-{m:02d}')
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    per = {k: [0.0, 0.0] for k in months}
    for day, (b, p) in by_day.items():
        if day[:7] in per: per[day[:7]][0] += b; per[day[:7]][1] += p
    ty0 = _tax_year_start(today).isoformat()
    tax_year = round(sum(b for day, (b, _p) in by_day.items() if ty0 <= day <= today.isoformat()), 1)
    groups = {'waiting': ('draft',), 'approved': ('fill_approved', 'save_approved'), 'in_tmc': ('saved', 'verified'), 'not_claimed': ('rejected',)}
    entries = {k: {'count': 0, 'miles': 0.0} for k in groups}
    for st, miles in status.values():
        for k, sts in groups.items():
            if st in sts: entries[k]['count'] += 1; entries[k]['miles'] = round(entries[k]['miles'] + miles, 1)
    r = rate()
    money = (lambda miles: round(miles * r / 100, 2)) if r else (lambda miles: None)
    last = max((i['last_date'] or '' for i in imps), default='')
    # 'this month' until it has any tracking; before that, the latest month the tracker covers (e.g. September in early October)
    focus = months[-1] if (sum(per[months[-1]]) or not last or last[:7] >= months[-1]) else (last[:7] if last[:7] in per else months[-1])
    this_month = per[focus]
    return {'months': [{'month': k, 'business': round(v[0], 1), 'personal': round(v[1], 1)} for k, v in per.items()],
            'this_month': {'business': round(this_month[0], 1), 'personal': round(this_month[1], 1), 'month': focus,
                           'label': 'this month' if focus == months[-1] else 'in ' + datetime.strptime(focus, '%Y-%m').strftime('%B')},
            'tax_year': {'business': tax_year, 'since': ty0, 'threshold': 10000},
            'last_12': {'business': round(sum(v[0] for v in per.values()), 1), 'personal': round(sum(v[1] for v in per.values()), 1)},
            'entries': entries, 'rate': r,
            'to_claim_value': money(entries['waiting']['miles'] + entries['approved']['miles']),
            'claimed_value': money(entries['in_tmc']['miles']),
            'tracked_to': last, 'has_data': bool(imps)}


def tile():
    """For the Apps page tile."""
    o = overview()
    return {'stats': [{'label': 'Business miles ' + o['this_month']['label'], 'value': f"{o['this_month']['business']:,.0f}"},
                      {'label': 'Tax year so far', 'value': f"{o['tax_year']['business']:,.0f}"}],
            'spark': [{'label': m['month'], 'value': m['business']} for m in o['months']],
            'note': ('Tracked to ' + _nice_date(o['tracked_to'])) if o['tracked_to'] else 'No tracker export yet'}


def _nice_date(iso):
    d = datetime.strptime(iso, '%Y-%m-%d')
    return f"{d.day} {d.strftime('%b %Y')}"
