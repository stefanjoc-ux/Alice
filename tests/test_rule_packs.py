"""Rule packs: the HR and council social care safeguards, switches, and the sandboxed test."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import substrate_store as s
s.init()
import rule_packs as RP, rules_engine as R
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
HR, CARE = dict(RP.PACKS['hr']['samples']), dict(RP.PACKS['care']['samples'])

# 1. detectors
t('CHI number: valid date and check digit accepted, wrong check digit refused', RP._chi_valid('0101010001') and not RP._chi_valid('0101010002') and not RP._chi_valid('3213010001'))
txt, removed = RP.redact(CARE['Case note summary'], ['CHI number', 'date of birth', 'phone number'])
t('identifiers removed, never echoed', set(removed) == {'CHI number', 'date of birth', 'phone number'} and '0101010001' not in txt and '07700' not in txt)
t('a CHI number is not mistaken for a phone number', RP.redact('CHI 0101010001, tel 07700 900123', ['phone number'])[0] == 'CHI 0101010001, tel [phone number removed]')

# 2. outcomes for the samples, inside the tenant and on a public service
ev = lambda pack, text, prov='tenant', on=None: RP.evaluate(pack, text, prov, on)
r = ev('care', CARE['Disclosure on a visit'])
t('protection concern: stopped and sent to a person, no AI', r['outcome'] == 'escalated' and r['sent'] is None and 'duty social work' in r['headline'])
r = ev('care', CARE['Case note summary'])
t('case notes in the tenant: sent with CHI, date of birth and phone removed', r['outcome'] == 'redacted' and '[CHI number removed]' in r['sent'] and 'dementia' in r['sent'])
t('same case notes to a public AI service: blocked', ev('care', CARE['Case note summary'], 'public')['outcome'] == 'blocked')
t('eligibility decision refused', ev('care', CARE['Eligibility'])['outcome'] == 'blocked')
r = ev('care', CARE['Letter to a family'])
t('letter to a family: held for the social worker, with plain-language instructions', r['outcome'] == 'held' and any('plain English' in i for i in r['instructions']))
t('OFFICIAL-SENSITIVE to a public service: blocked by the marking rule', any(f['rule'] == 'sc_marking' for f in ev('care', CARE['Marked chronology'], 'public')['fired']))
r = ev('hr', HR['Shortlisting'])
t('shortlisting: automated decision and protected characteristics both refused', r['outcome'] == 'blocked' and {'hr_automated', 'hr_equality'} <= {f['rule'] for f in r['fired']})
t('sickness absence: allowed in the tenant with identifiers removed, blocked on a public service',
  ev('hr', HR['Sickness absence summary'])['outcome'] == 'redacted' and ev('hr', HR['Sickness absence summary'], 'public')['outcome'] == 'blocked')
t('disciplinary letter held for HR sign-off', ev('hr', HR['Disciplinary outcome'])['outcome'] == 'held')
t('an ordinary job advert goes through with guidance', ev('hr', HR['Job advert'])['outcome'] == 'allowed')

# 3. switches change the outcome and show what was not applied
on = {r['id']: True for r in RP.PACKS['care']['rules']}; on['sc_chi'] = False
r = ev('care', CARE['Case note summary'], on=on)
t('CHI rule off: the CHI number goes through and is listed as not applied', '0101010001' in r['sent'] and any(f['rule'] == 'sc_chi' for f in r['off']))
on = {k: False for k in on}
t('everything off: a protection concern would reach the AI', ev('care', CARE['Disclosure on a visit'], on=on)['outcome'] == 'allowed')

# 4. the page's API: state saved, locked rules, sandbox
d = cl.get('/admin/api/rule-packs').json()
t('both packs listed with samples and every rule on by default', {p['id'] for p in d['packs']} == {'hr', 'care'} and all(all(v for v in d['state'][p].values()) for p in d['state']))
cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'rule': 'sc_chi', 'enabled': False}, headers=H)
t('switching a rule off is saved', cl.get('/admin/api/rule-packs').json()['state']['care']['sc_chi'] is False)
res = cl.post('/admin/api/rule-packs/test', json={'pack': 'care', 'text': CARE['Case note summary'], 'provider': 'tenant'}, headers=H).json()
t('the test uses the saved switches', '0101010001' in res['sent'])
t('audit rule cannot be switched off', cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'rule': 'sc_audit', 'enabled': False}, headers=H).status_code == 400)
cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'all_on': False}, headers=H)
st = cl.get('/admin/api/rule-packs').json()['state']['care']
t('all off leaves the audit trail on', st['sc_audit'] is True and not st['sc_protection'])
cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'reset': True}, headers=H)
t('recommended restores every rule', all(cl.get('/admin/api/rule-packs').json()['state']['care'].values()))
t('changing switches needs the admin token', cl.post('/admin/api/rule-packs/state', json={'pack': 'care', 'all_on': False}).status_code in (401, 403))
before = json.dumps(R.all_rules(), sort_keys=True)
cl.post('/admin/api/rule-packs/state', json={'pack': 'hr', 'all_on': False}, headers=H)
t("Alice's own rules are untouched by the packs", json.dumps(R.all_rules(), sort_keys=True) == before)
t('empty test message refused', cl.post('/admin/api/rule-packs/test', json={'pack': 'hr', 'text': '  '}, headers=H).status_code == 400)
t('page renders', 'id="rp-rules"' in cl.get('/admin/rule-packs').text)
