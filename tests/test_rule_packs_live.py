"""Rule packs applied to live rules: chat checks, Temple's requests, guidance, service classification, Rules page API."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import uuid
import substrate_store as s
s.init()
import rule_packs as RP, rules_engine as R
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
CARE = dict(RP.PACKS['care']['samples'])
NOTES = "Summarise the case notes for Mr Bell, CHI 0101010001, tel 07700 900123. He uses a wheelchair."
PROTECT = "During today's visit the child disclosed that her mother's partner hits her."

def chat(text, provider='claude'):
    cid = cl.post('/chats').json()['id']
    r = cl.post('/chat', json={'chat_id': cid, 'request_id': uuid.uuid4().hex, 'text': text, 'provider': provider})
    with s.db() as c: row = c.execute('SELECT user_text FROM chat_turns WHERE chat_id=?', (cid,)).fetchone()
    return r, (row[0] if row else None)

# 1. nothing applied: Alice behaves as before
t('no packs applied by default', RP.applied() == {} and cl.get('/admin/api/rule-packs/applied').json()['applied'] == [])
r, saved = chat(NOTES)
t('without packs, chat text is saved unchanged', saved == NOTES)
R.check_outbound(PROTECT, 'Temple chat review')
t('without packs, Temple requests are not affected', True)

# 2. apply the social care pack
d = cl.post('/admin/api/rule-packs/apply', json={'pack': 'care', 'apply': True}, headers=H).json()
t('applying a pack lists it with its safeguards', d['applied'][0]['id'] == 'care' and d['applied'][0]['on'] == len(RP.PACKS['care']['rules']))
t('the Rule packs page knows it is live', 'care' in cl.get('/admin/api/rule-packs').json()['applied'])
r, saved = chat(PROTECT)
t('chat: a protection concern is refused and never saved', r.status_code == 400 and 'duty social work team' in r.json()['detail'] and saved is None)
r, saved = chat(NOTES, 'claude')
t('chat: health details to a service outside the tenant are refused', r.status_code == 400 and 'tenant' in r.json()['detail'])
cl.post('/admin/api/rule-packs/services', json={'provider': 'claude', 'inside': True}, headers=H)
r, saved = chat(NOTES, 'claude')
t('Claude marked inside: sent with CHI and phone removed before saving', saved and '[CHI number removed]' in saved and '07700' not in saved and 'wheelchair' in saved)
t('the chat shows what the pack did', 'removed before sending' in r.text)
r, saved = chat(NOTES, 'auto')
t('Auto routing counts as inside only when every chat service is', r.status_code == 400)
with s.db() as c: acts = {x[0] for x in c.execute("SELECT DISTINCT action FROM activity")}
t('blocks and pack actions are in Activity', {'rule_blocked', 'rule_pack_applied', 'rule_pack_applied_to', 'rule_pack_service'} <= acts)

# 3. Temple's requests and guidance
try: R.check_outbound(PROTECT, 'Temple chat review'); t('Temple requests: escalations apply', False)
except R.RuleViolation as e: t('Temple requests: escalations apply', 'duty social work' in str(e))
R.check_file(PROTECT, 'notes.txt')
t('uploads are not blocked by packs (nothing is sent yet)', True)
g = R.effective_guidance('')
t('pack guidance is added to every model\'s instructions', 'Council social care pack' in g and 'plain English' in g)
cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'rule': 'sc_plain', 'enabled': False}, headers=H)
t('switching a safeguard off changes live guidance', 'plain English' not in R.effective_guidance(''))
with s.db() as c: changed = c.execute("SELECT count(*) FROM activity WHERE action='rule_pack_changed'").fetchone()[0]
t('changes to a live pack are recorded', changed == 1)
cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'rule': 'sc_protection', 'enabled': False}, headers=H)
cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'rule': 'sc_decisions', 'enabled': False}, headers=H)
r, saved = chat(PROTECT)
t('a switched-off safeguard no longer applies live', r.status_code != 400 or 'duty social work' not in r.text)

# 4. stacking, removal, permissions
cl.post('/admin/api/rule-packs/apply', json={'pack': 'pd', 'apply': True}, headers=H)
t('packs stack', {p['id'] for p in cl.get('/admin/api/rule-packs/applied').json()['applied']} == {'care', 'pd'})
r, saved = chat('I accidentally emailed the tenant list to the wrong landlord this morning.')
t('the personal data pack sends a breach to the DPO', r.status_code == 400 and 'Data Protection Officer' in r.json()['detail'])
cl.post('/admin/api/rule-packs/apply', json={'pack': 'care', 'apply': False}, headers=H)
cl.post('/admin/api/rule-packs/apply', json={'pack': 'pd', 'apply': False}, headers=H)
r, saved = chat(NOTES, 'claude')
t('removing the packs restores normal behaviour', saved == NOTES and 'Council social care pack' not in R.effective_guidance(''))
t('applying needs the admin token', cl.post('/admin/api/rule-packs/apply', json={'pack': 'care', 'apply': True}).status_code in (401, 403))
t('unknown pack or service refused', cl.post('/admin/api/rule-packs/apply', json={'pack': 'nope', 'apply': True}, headers=H).status_code == 400
  and cl.post('/admin/api/rule-packs/services', json={'provider': 'nope', 'inside': True}, headers=H).status_code == 400)
t('secrets are still caught by Alice\'s own rules', cl.post('/chat', json={'chat_id': cl.post('/chats').json()['id'], 'request_id': 'x1', 'text': 'key sk-ant-' + 'a' * 40, 'provider': 'claude'}).status_code == 400)
t('Rules page shows the applied packs section', 'id="r-packs"' in cl.get('/admin/rules').text)
