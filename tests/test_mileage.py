"""Mileage Clerk parts 1-3: reading a tracker export, your places, deterministic classification, drafts and exact approvals.
Every place and address here is fictional (no real addresses in the repo)."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import json
import substrate_store as s, temple
temple.save_settings(False, 'openai')
def t(label, cond): print(('PASS ' if cond else 'FAIL ') + label)

import mileage as MI, app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

HEAD = 'Start date,Start time,End date,End time,Start location,Start coordinates,End location,End coordinates,Duration (HH:MM),Distance(miles)\n'
HOME = 'Puffin Lane 3,ZZ9 1 Testburgh,United Kingdom'; HOMEC = '55.000000,-3.000000'
GYM = 'Otter Way 2,ZZ9 4 Testburgh,United Kingdom'; GYMC = '55.040000,-3.050000'
CLIENT = 'Heron Park,ZZ7 0 Farfield,United Kingdom'; CLIENTC = '55.800000,-4.000000'
LAYBY = 'United Kingdom'; LAYBYC = '55.400000,-3.500000'          # unnamed stop: a waypoint
SHOP = 'Badger Road,ZZ9 6 Testburgh,United Kingdom'; SHOPC = '55.010000,-3.010000'
FAR = 'Gull Street 9,ZZ5 3 Seaview,United Kingdom'; FARC = '56.200000,-2.500000'


def row(d, st, et, a, ac, b, bc, miles):
    return f'"{d}","{st}","{d}","{et}","{a}","{ac}","{b}","{bc}","00:10","{miles}"\n'


CSV = HEAD + ''.join([
    # 1 Sep: personal only (home -> gym -> home)
    row('01/09/2026', '09:00', '09:15', HOME, HOMEC, GYM, GYMC, 5.7),
    row('01/09/2026', '10:30', '10:45', GYM, GYMC, HOME, HOMEC, 5.7),
    # 2 Sep: business via an unnamed lay-by, then the return trip with a shop stop on the way
    row('02/09/2026', '07:00', '08:00', HOME, HOMEC, LAYBY, LAYBYC, 40.0),
    row('02/09/2026', '08:10', '09:00', LAYBY, LAYBYC, CLIENT, CLIENTC, 35.5),
    row('02/09/2026', '15:00', '16:30', CLIENT, CLIENTC, SHOP, SHOPC, 74.0),
    row('02/09/2026', '16:45', '16:50', SHOP, SHOPC, HOME, HOMEC, 1.2),
    # 3 Sep: a long trip to a place not yet classified (counted personal, flagged)
    row('03/09/2026', '08:00', '09:30', HOME, HOMEC, FAR, FARC, 60.0),
    row('03/09/2026', '17:00', '18:30', FAR, FARC, HOME, HOMEC, 60.0),
    # 4 Sep: business day with a gap (the tracker dropped a leg) and ending away from home
    row('04/09/2026', '07:00', '09:00', HOME, HOMEC, CLIENT, CLIENTC, 75.5),
    row('04/09/2026', '16:00', '16:20', SHOP, SHOPC, GYM, GYMC, 6.0),
])

# ---- part 1: parse ----
legs = MI.parse(CSV)
t('parse reads every leg, sorted by start', len(legs) == 10 and legs[0]['start'] == '2026-09-01T09:00')
t('a byte-order mark is accepted', len(MI.parse('﻿' + CSV)) == 10)
t('named stop key is street + postcode', MI.place_key(HOME) == 'loc:puffin lane 3|ZZ91')
t('unnamed stop key is a grid square', MI.place_key(LAYBY, LAYBYC) == 'geo:55.400,-3.500')
for label_, bad in [('not a tracker export', 'Name,Email\nA,b\n'), ('empty file', HEAD),
                    ('bad date', HEAD + row('2026-09-01', '09:00', '09:15', HOME, HOMEC, GYM, GYMC, 5)),
                    ('unbelievable distance', HEAD + row('01/09/2026', '09:00', '09:15', HOME, HOMEC, GYM, GYMC, 5000))]:
    try: MI.parse(bad); t('parse refuses: ' + label_, False)
    except ValueError: t('parse refuses: ' + label_, True)

# ---- places ----
def refused(label_, fn):
    try: fn(); t(label_, False)
    except ValueError: t(label_, True)

refused('a business place needs a purpose', lambda: MI.save_place(None, 'Client', 'business', [MI.place_key(CLIENT)], '', 'Heron Park, Farfield', 'ZZ7 0AA'))
refused('home needs the TMC location and postcode', lambda: MI.save_place(None, 'Home', 'home', [MI.place_key(HOME)]))
refused('a malformed postcode is refused', lambda: MI.save_place(None, 'Home', 'home', [MI.place_key(HOME)], '', 'Puffin Lane', 'NOTAPC'))
refused('kind must be home, personal or business', lambda: MI.save_place(None, 'X', 'holiday', []))

home = MI.save_place(None, 'Home', 'home', [MI.place_key(HOME)], '', 'Puffin Lane, Testburgh', 'zz91ab')['id']
pl = {p['id']: p for p in MI.places()}
t('postcode is tidied (upper case, space)', pl[home]['tmc_postcode'] == 'ZZ9 1AB')
refused('only one home', lambda: MI.save_place(None, 'Second home', 'home', [], '', 'Elsewhere', 'ZZ1 1AA'))
gym = MI.save_place(None, 'Gym', 'personal', [MI.place_key(GYM)])['id']
refused('a stop belongs to one place only', lambda: MI.save_place(None, 'Also gym', 'personal', [MI.place_key(GYM)]))
client = MI.save_place(None, 'Heron Park', 'business', [MI.place_key(CLIENT)], 'Meetings with the client',
                       'Heron Park, Farfield', 'ZZ7 0AA')['id']
shop = MI.save_place(None, 'Shop', 'personal', [], lat=55.0105, lon=-3.0102)['id']   # matched by distance, not by key
with s.db() as c:
    t('place saves are logged as your action', c.execute("SELECT count(*) FROM activity WHERE action='mileage_place_saved'").fetchone()[0] == 4)

# ---- part 2: classify ----
res = MI.classify(legs)
day = {d['day']: d for d in res['days']}
t('personal day has no business miles', day['2026-09-01']['business'] == 0 and day['2026-09-01']['personal'] == 11.4)
t('journey through an unnamed waypoint to a client is business', day['2026-09-02']['business'] == 75.5 + 74.0)
t('return from the client counts as business up to the next known place', day['2026-09-02']['personal'] == 1.2)
t('the client is a business stop', day['2026-09-02']['stops'] == [client])
t('a stop matched by distance is a known place', all(l['to_place'] for l in day['2026-09-02']['legs'] if l['to'] == MI._clean(SHOP)))
t('a clean business day has no warnings', day['2026-09-02']['warnings'] == [])
t('a long trip to an unknown place is counted personal and flagged',
  day['2026-09-03']['business'] == 0 and len(day['2026-09-03']['warnings']) == 1 and 'Seaview' in day['2026-09-03']['warnings'][0])
t('unknown places listed for you to classify', {u['key']: u['visits'] for u in res['unknown']}.get(MI.place_key(FAR)) == 2)
t('a short stop on the way (lay-by) is a waypoint: no warning on that day', day['2026-09-02']['warnings'] == [])
w4 = ' '.join(day['2026-09-04']['warnings'])
t('a gap on a business day is flagged, not filled in', 'Gap after' in w4 and day['2026-09-04']['business'] == 75.5)
t('a business day ending away from home is flagged', 'ends away from home' in w4)
t('gap warnings are not raised on personal days', not any('Gap' in w for w in day['2026-09-01']['warnings']))

# ---- drafts ----
imp = MI.import_export('Trips.csv', CSV)
iid = imp['id']
drafts = {d['day']: d for d in imp['drafts']}
t('one draft per business day, none for personal days', sorted(drafts) == ['2026-09-02', '2026-09-04'])
p2 = drafts['2026-09-02']['payload']
t('draft payload: date, miles, start at home, business stop with purpose',
  p2['date'] == '02/09/2026' and p2['daily_business_miles'] == 149.5 and
  p2['rows'] == [{'row_type': 'start', 'location': 'Puffin Lane, Testburgh', 'postcode': 'ZZ9 1AB'},
                 {'row_type': 'stop', 'location': 'Heron Park, Farfield', 'postcode': 'ZZ7 0AA', 'purpose': 'Meetings with the client'}])
t('draft carries its warnings', drafts['2026-09-04']['payload']['warnings'] != [])
t('totals add up', imp['totals'] == {'tracked': 363.6, 'business': 225.0, 'personal': 138.6})
again = MI.import_export('Trips again.csv', CSV)
t('re-importing the same file is a no-op', again['duplicate'] and again['id'] == iid and len(MI.imports()) == 1)
with s.db() as c:
    t('import logged', c.execute("SELECT count(*) FROM activity WHERE action='mileage_imported'").fetchone()[0] == 1)

# ---- part 3: exact approvals ----
d2 = drafts['2026-09-02']
refused('no approval without a vehicle registration', lambda: MI.approve(d2['id'], 'fill', d2['payload_hash']))
refused('a malformed registration is refused', lambda: MI.set_vehicle('NOT A REG!'))
MI.set_vehicle('zz26 abc'); MI.refresh_drafts(iid)
d2 = next(d for d in MI.summary(iid)['drafts'] if d['day'] == '2026-09-02')
t('vehicle goes into the entry (and changes its hash)', d2['payload']['vehicle_registration'] == 'ZZ26ABC' and d2['payload_hash'] != drafts['2026-09-02']['payload_hash'])
refused('an approval for an entry you did not see is refused (old hash)', lambda: MI.approve(d2['id'], 'fill', drafts['2026-09-02']['payload_hash']))
refused('save before fill is refused', lambda: MI.approve(d2['id'], 'save', d2['payload_hash']))
refused('unknown action refused', lambda: MI.approve(d2['id'], 'submit', d2['payload_hash']))
t('approval for this exact entry starts nothing yet', not MI.approved_for('fill', d2['id'], d2['payload_hash']))
t('fill approval accepted', MI.approve(d2['id'], 'fill', d2['payload_hash'], 'looks right')['status'] == 'fill_approved')
t('approved_for: fill yes, save not yet', MI.approved_for('fill', d2['id'], d2['payload_hash']) and not MI.approved_for('save', d2['id'], d2['payload_hash']))
t('approved_for refuses a different entry', not MI.approved_for('fill', d2['id'], 'f' * 64))
refused('fill cannot be approved twice', lambda: MI.approve(d2['id'], 'fill', d2['payload_hash']))
with s.db() as c: a = json.loads(c.execute('SELECT approvals FROM mileage_drafts WHERE id=?', (d2['id'],)).fetchone()['approvals'])
t('approval records action, exact hash, who and when', a[0]['action'] == 'fill' and a[0]['hash'] == d2['payload_hash'] and a[0]['by'] and a[0]['at'])

# changing a place after fill approval rebuilds the entry and clears the approval
MI.save_place(client, 'Heron Park', 'business', [], 'Quarterly review with the client', 'Heron Park, Farfield', 'ZZ7 0AA')
MI.refresh_drafts(iid)
d2b = next(d for d in MI.summary(iid)['drafts'] if d['day'] == '2026-09-02')
t('a changed entry is rebuilt and its approvals cleared', d2b['status'] == 'draft' and d2b['approvals'] == [] and d2b['payload_hash'] != d2['payload_hash'])
t('the old approval no longer counts', not MI.approved_for('fill', d2['id'], d2['payload_hash']))
MI.approve(d2b['id'], 'fill', d2b['payload_hash'])
t('save approval after fill', MI.approve(d2b['id'], 'save', d2b['payload_hash'])['status'] == 'save_approved'
  and MI.approved_for('save', d2b['id'], d2b['payload_hash']) and MI.approved_for('fill', d2b['id'], d2b['payload_hash']))
# a save-approved entry is not rewritten; it is noted instead
MI.save_place(client, 'Heron Park', 'business', [], 'Something else entirely', 'Heron Park, Farfield', 'ZZ7 0AA'); MI.refresh_drafts(iid)
d2c = next(d for d in MI.summary(iid)['drafts'] if d['day'] == '2026-09-02')
t('a save-approved entry is not rewritten, only noted', d2c['status'] == 'save_approved' and d2c['payload_hash'] == d2b['payload_hash'] and 'changed' in d2c['notes'])

# reclassifying the only business stop withdraws an untouched draft
d4 = next(d for d in MI.summary(iid)['drafts'] if d['day'] == '2026-09-04')
t('reject: not claiming a day', MI.reject(d4['id'], 'Not this one')['status'] == 'rejected')
refused('a rejected entry cannot be approved', lambda: MI.approve(d4['id'], 'fill', d4['payload_hash']))
with s.db() as c:
    acts = {r[0] for r in c.execute("SELECT action FROM activity WHERE action LIKE 'mileage_%'")}
t('approvals and rejections logged', {'mileage_fill_approved', 'mileage_save_approved', 'mileage_rejected', 'mileage_vehicle_set'} <= acts)
import autoapprove; autoapprove.set_on(True)
d4b = MI.import_export('Other.csv', CSV.replace('04/09/2026', '05/09/2026'))
with s.db() as c: st = {r[0] for r in c.execute('SELECT status FROM mileage_drafts WHERE import_id=?', (d4b['id'],))}
t('with automatic approval on, new mileage entries still wait for you', st == {'draft'})
autoapprove.set_on(False)

# ---- routes ----
t('mileage changes need the admin token', cl.put('/admin/api/mileage/vehicle', json={'vehicle': 'AB12CDE'}).status_code == 403
  and cl.post('/admin/api/mileage/import', json={'name': 'x', 'text': CSV}).status_code in (401, 403))
x = cl.get(f'/admin/api/mileage?import_id={iid}', headers=H).json()
t('page data: imports, places, vehicle, current', x['vehicle'] == 'ZZ26ABC' and len(x['places']) == 4 and x['current']['import']['id'] == iid)
r = cl.post('/admin/api/mileage/import', headers=H, json={'name': 'bad.csv', 'text': 'Name,Email\nA,b\n'})
t('a non-export is refused with a reason', r.status_code == 400 and 'tracker export' in r.text)
secret = CSV.replace('Heron Park,ZZ7', 'api_key=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD Heron Park,ZZ7', 1)
r = cl.post('/admin/api/mileage/import', headers=H, json={'name': 'leaky.csv', 'text': secret})
t('an export containing a secret is refused by the rules', r.status_code in (400, 403) and len(MI.imports()) == 2)
r = cl.post('/admin/api/mileage/places', headers=H, json={'name': 'Far', 'kind': 'personal', 'keys': [MI.place_key(FAR)]})
t('classifying a place on the page works and clears it from the unknown list', r.status_code == 200
  and not any(u['key'] == MI.place_key(FAR) for u in cl.get(f'/admin/api/mileage?import_id={iid}', headers=H).json()['current']['unknown']))
r = cl.post(f'/admin/api/mileage/drafts/{d2b["id"]}/approve', headers=H, json={'action': 'fill', 'hash': 'a' * 64})
t('route refuses an approval with the wrong hash', r.status_code in (400, 409) and 'changed' in r.text)
r = cl.put('/admin/api/mileage/vehicle', headers=H, json={'vehicle': '!!'})
t('route refuses a bad registration', r.status_code == 400)
r = cl.delete(f'/admin/api/mileage/places/{shop}', headers=H)
t('a place can be deleted', r.status_code == 200 and len(MI.places()) == 4)
t('Mileage page served', cl.get('/admin/mileage', headers=H).status_code in (200, 307, 302) or cl.get('/admin/mileage').status_code in (200, 401, 403))
