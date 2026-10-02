"""The Command centre home page and opening a new chat by default."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import substrate_store as s
s.init()
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

page = cl.get('/admin').text
t('the Command centre opens on Home', 'const PAGE="home"' in page and 'New chat' in page and 'Write a proposal' in page)
t('Home is first in the menu and Actions has its own address', page.index('data-page="home"') < page.index('data-page="actions"') and 'href="/admin/actions"' in page)
r = cl.get('/admin/overview', follow_redirects=False)
t('the old Overview page goes to Home', r.status_code == 307 and r.headers['location'] == '/admin')
mem = s.propose('Carport roof', 'Clear twinwall polycarbonate for the carport roof.', 'Stefan said')['id']
d = cl.get('/admin/api/home?tz=-60', headers=H).json()
t('home lists what is waiting, with links', d['waiting']['total'] >= 1 and any(x['key'] == 'proposals' and x['link'].startswith('/admin/') for x in d['waiting']['sections']))
t('home has today, the week, spend and the substrate', {'events', 'blocked', 'runs', 'model_calls'} <= set(d['today']) and len(d['week']['buckets']) >= 7
  and 'daily_usd' in d['spend'] and {'memories', 'knowledge', 'documents', 'organisations', 'clients'} <= set(d['substrate']))
t('assistants are listed, including the proposal writer', any(a['kind'] == 'proposal' for a in d['assistants']) and any(a['id'] == 'hr-policy' for a in d['assistants']))
t('a greeting with your name', d['greeting'] in ('Good morning', 'Good afternoon', 'Good evening') and d['name'])
t('empty chats are not listed as recent', all(x['turns'] for x in d['chats']))
t('the chat sidebar list carries how many turns each chat has', all('turns' in x for x in cl.get('/chats').json()))
chat = cl.get('/').text
t('the chat page opens a new (or the empty) chat unless one is asked for', "const empty=chats.find(c=>!c.turns)" in chat and 'createChat()' in chat)
import desktop
t('the desktop app opens Alice on the Command centre home', desktop.open_window.__defaults__ == ('admin',))
t('the chat page clears ?new=1 with window.history (history is a chat variable there)', 'window.history.replaceState' in chat)
