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
t('"which one should we promote" is an automated decision', any(f['rule'] == 'hr_automated' for f in ev('hr', 'Two people applied for the team leader role. Which one should we promote?')['fired']))
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
t('all four packs listed with samples and every rule on by default', {p['id'] for p in d['packs']} == {'hr', 'care', 'sec', 'pd'} and all(all(v for v in d['state'][p].values()) for p in d['state']))
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

# 5. wider social care wording
care_review = ("Draft a summary of Mr John Paterson's care review for his file. CHI 1504470001, tel 01738 123456, PH2 8DY. "
               "He has Parkinson's and uses a wheelchair. His daughter said he has missed several meals since his carer left.")
r = ev('care', care_review)
t('care review: CHI, phone and postcode removed; daughter\'s account flagged; held for sign-off',
  r['outcome'] == 'held' and set(r['removed']) == {'CHI number', 'phone number', 'postcode'} and any(f['rule'] == 'sc_third_party' for f in r['fired']))
t('Parkinson\'s and wheelchair use count as health information outside the tenant', any(f['rule'] == 'sc_special' for f in ev('care', care_review, 'public')['fired']))
fin = "Mr Paterson's daughter told us his new partner has been taking money from his bank account and he seems frightened of her. Should we reduce his care package?"
r = ev('care', fin)
t('financial abuse is a protection concern; reducing a package is a care decision', r['outcome'] == 'escalated' and {'sc_protection', 'sc_decisions'} <= {f['rule'] for f in r['fired']})

# 6. security operations pack (Defender for Cloud, Entra ID sign-ins)
SEC = dict(RP.PACKS['sec']['samples'])
r = ev('sec', SEC['Risky sign-in triage'])
t('risky sign-in: user pseudonymised, internal IP masked, attacker IP and correlation ID kept',
  r['outcome'] == 'redacted' and '[user A]' in r['sent'] and '10.20.4.17' not in r['sent'] and '203.0.113.45' in r['sent'] and '6c1f0b9e' in r['sent'])
r = ev('sec', SEC['Defender alert with a key'])
t('storage key and subscription ID removed from the alert', 'AccountKey' not in r['sent'] and '3f2a9c1e' not in r['sent'] and set(r['removed']) == {'secret or key', 'subscription or tenant ID'})
r = ev('sec', SEC['Contain it automatically'])
t('containment of a Global Administrator: held for an analyst and two-person approval', r['outcome'] == 'held' and {'sec_contain', 'sec_privileged'} <= {f['rule'] for f in r['fired']})
t('planted instructions in a log are flagged', any(f['rule'] == 'sec_injection' for f in ev('sec', SEC['Poisoned log entry'])['fired']))
t('break-glass account cannot be disabled on AI advice', ev('sec', SEC['Break-glass sign-in'])['outcome'] == 'blocked')
t('live incident to a public AI: blocked', any(f['rule'] == 'sec_incident' for f in ev('sec', SEC['Live incident'], 'public')['fired']))
r = RP.redact('a@x.example then b@x.example then A@x.example', ['user name'])[0]
t('the same user always gets the same pseudonym', r == '[user A] then [user B] then [user A]')
t('security pack names its own services', any('Security Copilot' in p['name'] for p in [x for x in cl.get('/admin/api/rule-packs').json()['packs'] if x['id'] == 'sec'][0]['providers']))

# 7. personal data (UK GDPR) pack
PD = dict(RP.PACKS['pd']['samples'])
r = ev('pd', PD['Customer complaint'])
t('complaint: address, postcode, email, phone, card and bank details removed; name kept for the reply',
  r['outcome'] == 'redacted' and {'street address', 'postcode', 'email address', 'phone number', 'payment card number', 'bank account details'} <= set(r['removed'])
  and '4111' not in r['sent'] and 'Kinnoull' not in r['sent'] and 'Helen Dunn' in r['sent'] and 'removed] was' in r['sent'])
t('reusing clinic data for fundraising: blocked (purpose limitation)', ev('pd', PD['Reuse for marketing'])['outcome'] == 'blocked')
r = ev('pd', PD['Data breach'])
t('possible breach: sent to the DPO, 72-hour clock mentioned', r['outcome'] == 'escalated' and 'Data Protection Officer' in r['headline'] and any('72-hour' in f['message'] for f in r['fired']))
t('subject access request: held for the data protection team', ev('pd', PD['Subject access request'])['outcome'] == 'held')
t('loan decision: refused', any(f['rule'] == 'pd_profiling' for f in ev('pd', PD['Credit decision'])['fired']))
t("profiling children for adverts: refused", any(f['rule'] == 'pd_children' for f in ev('pd', PD["Children's app"])['fired']))
t('a list of people: refused as bulk personal data', any(f['rule'] == 'pd_bulk' for f in ev('pd', PD['Mailing list'])['fired']))
t('NHS number recognised only with a valid check digit', RP.find_ids('NHS number 943 476 5919', ['NHS number']) and not RP.find_ids('NHS number 943 476 5918', ['NHS number']))
t('IP addresses removed as online identifiers', RP.redact('login from 203.0.113.9', ['IP address'])[0] == 'login from [IP address removed]')
t('no AI instructions listed when nothing reaches the AI', ev('pd', PD['Data breach'])['instructions'] == [] and ev('hr', HR['Job advert'], on={r['id']: True for r in RP.PACKS['hr']['rules']})['instructions'])
