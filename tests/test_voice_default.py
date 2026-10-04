"""The chat's reading voice: Bella unless you choose another, and your choice is kept in Alice (every device), not only
in one browser. No real call to ElevenLabs."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import os
import app, voice
from fastapi.testclient import TestClient
cl = TestClient(app.app)

os.environ.pop('ELEVENLABS_VOICE_ID', None)
voice.configured = lambda: True
async def fake_voices():
    return [{'voice_id': 'AAAAAAAAAAAAAAAAAAAA', 'name': 'Adam'}, {'voice_id': 'BBBBBBBBBBBBBBBBBBBB', 'name': 'Bella - soft'},
            {'voice_id': 'CCCCCCCCCCCCCCCCCCCC', 'name': 'Charlie'}]
voice.voices = fake_voices

t('nothing chosen yet: Bella', cl.get('/voice/status').json()['default_voice'] == 'BBBBBBBBBBBBBBBBBBBB')
t('choosing a voice needs the page token', cl.put('/voice/default', json={'voice_id': 'CCCCCCCCCCCCCCCCCCCC'}).status_code == 403)
t('a malformed voice id is refused', cl.put('/voice/default', json={'voice_id': '../x'}, headers={'x-admin-token': app.ADMIN_TOKEN}).status_code == 422)
r = cl.put('/voice/default', json={'voice_id': 'CCCCCCCCCCCCCCCCCCCC'}, headers={'x-admin-token': app.ADMIN_TOKEN})
t('your choice is kept in Alice and used on every device', r.status_code == 200 and cl.get('/voice/status').json()['default_voice'] == 'CCCCCCCCCCCCCCCCCCCC')
page = cl.get('/').text
t('the chat page saves a new choice and prefers the saved one', "fetch('/voice/default'" in page and '__CHAT_ADMIN_TOKEN__' not in page)
