"""Apps area: registry, Apps page, Mileage under Apps (not in the menu), waiting items on the Apps page and on Actions."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import re
import temple
temple.save_settings(False, 'openai')
def t(label, cond): print(('PASS ' if cond else 'FAIL ') + label)

import apps, mileage as MI, app, actions
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

t('Mileage is registered as an app with its page', apps.by_page('mileage')['name'] == 'Mileage' and 'mileage' in apps.PAGES)
x = cl.get('/admin/api/apps').json()
t('Apps listing: Mileage, the Trading desk and Health Insights, nothing waiting yet', [a['id'] for a in x['apps']] == ['mileage', 'trading', 'health'] and x['apps'][0]['waiting'] == 0
  and x['apps'][0]['href'] == '/admin/mileage')

# the menu: Apps instead of Mileage; an app's page highlights Apps and carries a breadcrumb
page = cl.get('/admin/apps').text
nav = re.search(r'<nav aria-label="Console">(.*?)</nav>', page, re.S).group(1)
t('Apps is in the menu and Mileage is not', 'data-page="apps"' in nav and 'data-page="mileage"' not in nav and '>More<' not in nav)
t('Apps page is current on the Apps page', 'href="/admin/apps" data-page="apps" aria-current="page"' in nav)
mp = cl.get('/admin/mileage').text
t('Mileage page still opens at its address', 'Tracker export' in mp)
t('Mileage page highlights Apps and shows the breadcrumb', 'data-page="apps" aria-current="page"' in mp and '<a class="crumb" href="/admin/apps">Apps</a> › Mileage' in mp)
t('other pages keep their own highlight', 'data-page="memories" aria-current="page"' in cl.get('/admin/memories').text)

# a waiting mileage entry shows on the Apps page and on Actions (as a link: approval stays on the app's page)
HEAD = 'Start date,Start time,End date,End time,Start location,Start coordinates,End location,End coordinates,Duration (HH:MM),Distance(miles)\n'
A, B = 'Puffin Lane 3,ZZ9 1 Testburgh,United Kingdom', 'Heron Park,ZZ7 0 Farfield,United Kingdom'
CSV = HEAD + '"02/09/2026","07:00","02/09/2026","08:30","%s","55.0,-3.0","%s","55.8,-4.0","01:30","75.5"\n' % (A, B) \
      + '"02/09/2026","16:00","02/09/2026","17:30","%s","55.8,-4.0","%s","55.0,-3.0","01:30","74.0"\n' % (B, A)
MI.save_place(None, 'Home', 'home', [MI.place_key(A)], '', 'Puffin Lane, Testburgh', 'ZZ9 1AB')
MI.save_place(None, 'Heron Park', 'business', [MI.place_key(B)], 'Meetings with the client', 'Heron Park, Farfield', 'ZZ7 0AA')
imp = MI.import_export('Trips.csv', CSV)
w = MI.waiting()
t('mileage reports the entry waiting for you', len(w) == 1 and '149.5 business miles' in w[0]['title'] and w[0]['href'] == '/admin/mileage?import_id=' + imp['id'])
x = cl.get('/admin/api/apps').json()
t('Apps listing counts it', x['apps'][0]['waiting'] == 1)
sec = next(s for s in actions.summary()['sections'] if s['key'] == 'apps')
t('Actions shows it under Waiting in your apps, linking to the app', sec['count'] == 1 and sec['items'][0]['type'] == 'link'
  and sec['items'][0]['title'].startswith('Mileage: ') and sec['items'][0]['href'].startswith('/admin/mileage?import_id='))
t('it counts towards the Actions total', actions.summary()['total'] >= 1)
MI.set_vehicle('ZZ26ABC'); MI.refresh_drafts(imp['id'])
d = MI.summary(imp['id'])['drafts'][0]
MI.approve(d['id'], 'fill', d['payload_hash'])
t('once approved it is no longer waiting', MI.waiting() == [] and cl.get('/admin/api/apps').json()['apps'][0]['waiting'] == 0
  and next(s for s in actions.summary()['sections'] if s['key'] == 'apps')['count'] == 0)

# an app that fails to answer never breaks Apps or Actions
real = apps.APPS[0]['waiting']
apps.APPS[0]['waiting'] = lambda: 1 / 0
t('a failing app is skipped, not fatal', apps.waiting() == [] and cl.get('/admin/api/apps').status_code == 200 and cl.get('/admin/api/actions').status_code == 200)
apps.APPS[0]['waiting'] = real
