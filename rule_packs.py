"""Rule packs: ready-made safeguards for teams adopting AI, for demonstrations and pilots.

Two packs: an HR team, and a Scottish council's social care service. Each rule is enforced in code (it blocks,
removes identifiers, sends the matter to a person, or holds the output for sign-off) or is guidance added to
the model's instructions. Rules can be switched on and off and a message tested against the pack.

This is a sandbox. Switching rules here changes nothing about Alice's own rules (rules_engine.py), and the test
never calls a model: it shows what would happen and what the model would receive. Findings name the kind of
information found, never the value itself.
"""
import json
import re

import substrate_store as store
from rules_engine import SPECIAL, PERSON, _luhn

STATE_KEY = 'rule_pack_demo'

PROVIDERS = {
    'tenant': {'name': 'Microsoft 365 Copilot (your tenant, UK data boundary)', 'in_tenant': True, 'uk': True},
    'azure_uk': {'name': 'Azure OpenAI in UK South (council subscription)', 'in_tenant': True, 'uk': True},
    'public': {'name': 'Public AI chatbot (consumer service, outside the UK)', 'in_tenant': False, 'uk': False},
}

ACTIONS = {   # strongest first: decides the overall outcome
    'escalate': ('Sends it to a person', 'escalated'),
    'block': ('Blocks', 'blocked'),
    'review': ('Holds for sign-off', 'held'),
    'redact': ('Removes identifiers', 'redacted'),
    'flag': ('Flags for the record', 'allowed'),
    'note': ('Applies a records rule', 'allowed'),
    'guide': ('Adds an instruction', 'allowed'),
    'log': ('Records everything', 'allowed'),
}
ORDER = ['escalate', 'block', 'review', 'redact', 'flag', 'note', 'guide', 'log']


# ---------------- detectors (return labels, never values) ----------------
def _sentences(text):
    return [s for s in re.split(r'(?<=[.!?;])\s+|\n+', text or '') if s.strip()]


def _chi_valid(d):
    """Community Health Index: DDMMYY + 3 digits + check digit (modulus 11, weights 10..2)."""
    dd, mm = int(d[0:2]), int(d[2:4])
    if not (1 <= dd <= 31 and 1 <= mm <= 12): return False
    total = sum(int(c) * w for c, w in zip(d[:9], range(10, 1, -1)))
    check = 11 - total % 11
    check = 0 if check == 11 else check
    return check != 10 and check == int(d[9])


IDENTIFIERS = {   # label -> (pattern, validator or None)
    'CHI number': (re.compile(r'(?<!\d)(\d{6}\s?\d{4})(?!\d)'), lambda m: _chi_valid(re.sub(r'\D', '', m.group(1)))),
    'National Insurance number': (re.compile(r'\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b'), None),
    'payment card number': (re.compile(r'\b(?:\d[ -]?){13,19}\b'), lambda m: _luhn(re.sub(r'\D', '', m.group()))),
    'date of birth': (re.compile(r'(?i)\b(?:DOB|d\.o\.b\.?|date of birth|born(?: on)?)\W{0,3}\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}'), None),
    'employee number': (re.compile(r'(?i)\b(?:EMP\d{4,}|(?:employee|staff|payroll)\s+(?:no\.?|number|id)\W{0,3}[A-Z]{0,3}\d{4,})\b'), None),
    'email address': (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), None),
    'phone number': (re.compile(r'(?<![\w.])(?:\+44\s?\(?0?\)?\s?|\(?0)(?:\d[\s-]?){9,10}\b'),
                     lambda m: not re.search(r'CHI(?:\s+(?:no\.?|number))?\W{0,4}$', m.string[max(0, m.start() - 16):m.start()], re.I)),
    'postcode': (re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[ABD-HJLNP-UW-Z]{2}\b'), None),
}


def find_ids(text, labels):
    spans = []
    for label in labels:
        pat, ok = IDENTIFIERS[label]
        for m in pat.finditer(text or ''):
            if ok is None or ok(m): spans.append((m.start(), m.end(), label))
    spans.sort()
    out, last = [], -1
    for s, e, l in spans:                  # drop overlaps (e.g. a CHI inside a longer number)
        if s >= last: out.append((s, e, l)); last = e
    return out


def redact(text, labels):
    spans = find_ids(text, labels)
    for s, e, l in reversed(spans): text = text[:s] + f'[{l} removed]' + text[e:]
    return text, sorted({l for _, _, l in spans})


HEALTH_EXTRA = re.compile(r'\b(dementia|depress\w*|anxiety|alcohol\w*|drug use|substance\w*|addict\w*|HIV|cancer|autis\w*|'
                          r'ADHD|learning disabilit\w*|stroke|dementia)\b', re.I)
SUBJECT = re.compile(r"\b(?:employee|colleague|staff member|candidate|applicant|service user|client|child|adult|resident|tenant|"
                     r"[A-Z][a-z]+'s|[A-Z][a-z]+ [A-Z][a-z]+)\b")


def special_about_person(text):
    for s in _sentences(text):
        if (SPECIAL.search(s) or HEALTH_EXTRA.search(s)) and (PERSON.search(s) or SUBJECT.search(s)):
            return True
    return False


def _any(pattern, text):
    return bool(re.search(pattern, text or '', re.I))


def _near(a, b, text, gap=80):
    t = text or ''
    return bool(re.search(rf'(?:{a})[\s\S]{{0,{gap}}}(?:{b})|(?:{b})[\s\S]{{0,{gap}}}(?:{a})', t, re.I))


PEOPLE_DECISION = r'\b(?:decide|decision|choose|pick|select|rank|score|shortlist|recommend which|which ones? to|who to|who should)\b'
HR_OUTCOME = r'\b(?:dismiss\w*|redundan\w*|hire|hiring|reject\w*|promot\w*|disciplin\w*|sack\w*|terminat\w*|appoint\w*|applicants?|candidates?)\b'
HIRING = r'\b(?:candidates?|applicants?|hire|hiring|recruit\w*|shortlist\w*|job advert|vacancy|role|interview\w*)\b'
BIASED = (r"\b(?:under|over)\s+\d{2}\b|\b(?:young|younger|older|recent graduates?|digital natives?|energetic|mature|"
          r"native english|british only|no women|male|female|men only|women only|childless|no kids|pregnan\w*|maternity|"
          r"religio\w*|nationality|wheelchair|disab\w*|age\s*:?\s*\d{2})\b")
CASEWORK = r'\b(?:grievance|disciplinary|investigation report|whistleblow\w*|tribunal|settlement agreement|capability hearing|misconduct)\b'
OUTBOUND = r'\b(?:draft|write|send|email|prepare)\b[\s\S]{0,60}\b(?:letter|email|message|offer|outcome|report|reply|chronology|minute|plan|summary)\b'
TO_PERSON = r'\b(?:employee|candidate|applicant|staff|him|her|them|family|parents?|carer|service user|Mr|Mrs|Ms|Miss|hearing|panel)\b'
PROTECTION = (r"\b(?:child protection|CP register|IRD|inter-?agency referral|adult support and protection|ASP (?:inquiry|investigation)|"
              r"significant harm|at risk of harm|non-?accidental|disclos\w* (?:of )?(?:abuse|that)|abuse\w*|neglect\w*|hits? (?:her|him|them)|"
              r"domestic abuse|self-?harm\w*|suicid\w*|grooming|exploitation)\b")
CARE_DECISION = (r"\b(?:eligib\w*|risk (?:score|level|rating)|what risk|care package|budget|approve|refuse|decide|prioriti[sz]e|"
                 r"should (?:we|the council) (?:remove|place|accommodate))\b")
CARE_CONTEXT = r'\b(?:care|support|service user|child|adult|placement|self-directed support|SDS|package|respite|assessment)\b'
THIRD_PARTY = (r"\b(?:mother|father|mum|dad|partner|ex-partner|boyfriend|girlfriend|husband|wife|neighbour|sibling|brother|sister|"
               r"grandparent|grandmother|grandfather|aunt|uncle|carer|friend)(?:'s)?(?: partner)?\s+(?:said|says|reported|told|has|have|was|is|hits?|called)\b")
MARKINGS = r'\bOFFICIAL[-\s]SENSITIVE\b|^\s*SECRET\s*$|\bTOP SECRET\b'


# ---------------- the packs ----------------
def R(id, theme, name, kind, action, what, why, detect=None, guidance='', locked=False, default=True):
    return dict(id=id, theme=theme, name=name, kind=kind, action=action, what=what, why=why, detect=detect,
                guidance=guidance, locked=locked, default=default)


def _hr_special(text, p):
    if not special_about_person(text): return None
    if not p['in_tenant']: return 'Health or other special category information about a person; not allowed outside your tenant.'
    return None


def _hr_special_note(text, p):
    if special_about_person(text) and p['in_tenant']:
        return 'Special category information about a person, processed in your tenant under HR\'s employment condition; recorded.'
    return None


HR = dict(
    id='hr', name='HR team', audience='An HR team using AI for drafting, summarising casework and recruitment admin.',
    basis='UK GDPR and Data Protection Act 2018, Equality Act 2010, the ICO\'s employment practices guidance, the ACAS Code of Practice.',
    samples=[
        ('Sickness absence summary', "Summarise Sarah Thomson's sickness absence. She was diagnosed with depression in March. "
                                     "NI number AB 12 34 56 C, employee no. EMP20417."),
        ('Shortlisting', 'Here are five applicants for the HR adviser role. Rank them and tell us which ones to reject. '
                         "We'd prefer someone under 30 who is a native English speaker."),
        ('Disciplinary outcome', "Draft the outcome letter for Mark's disciplinary hearing and email it to him at mark.r@example.com."),
        ('Job advert', 'Write a job advert for an HR adviser role based in Perth, hybrid working, 37 hours a week.'),
    ],
    rules=[
        R('hr_special', 'Personal data', 'Special category data stays in your tenant', 'enforced', 'block',
          'Health, disability, pregnancy, religion, ethnicity, sexual orientation and union membership about a person never go to an AI service outside your tenant.',
          'UK GDPR Article 9; Data Protection Act 2018 Schedule 1 (employment condition) and a DPIA.', _hr_special),
        R('hr_special_log', 'Personal data', 'Special category use is recorded', 'enforced', 'flag',
          'When special category information is used inside your tenant, the use is recorded against HR\'s lawful condition.',
          'UK GDPR Article 30 (records of processing) and the appropriate policy document required by the DPA 2018.', _hr_special_note),
        R('hr_ids', 'Personal data', 'Identifiers removed before the model sees them', 'enforced', 'redact',
          'National Insurance numbers, employee numbers, dates of birth and card numbers are replaced with a placeholder.',
          'UK GDPR Article 5(1)(c), data minimisation.',
          ('National Insurance number', 'employee number', 'date of birth', 'payment card number')),
        R('hr_contact', 'Personal data', 'Contact details removed', 'enforced', 'redact',
          'Personal email addresses, phone numbers and home postcodes are replaced with a placeholder.',
          'UK GDPR Article 5(1)(c), data minimisation.', ('email address', 'phone number', 'postcode')),
        R('hr_automated', 'Fairness', 'No automated decisions about people', 'enforced', 'block',
          'AI may summarise evidence, but it never decides or ranks who is hired, rejected, promoted, disciplined or dismissed. A manager decides.',
          'UK GDPR rules on automated decision-making (Article 22, as amended): meaningful human involvement in significant decisions.',
          lambda t, p: 'Asks the AI to decide or rank an outcome for people.' if _near(PEOPLE_DECISION, HR_OUTCOME, t) else None),
        R('hr_equality', 'Fairness', 'Protected characteristics kept out of selection', 'enforced', 'block',
          'Requests that select or exclude people by age, sex, pregnancy, race, nationality, religion or disability are refused.',
          'Equality Act 2010: the nine protected characteristics.',
          lambda t, p: 'Uses a protected characteristic as a selection criterion.' if _any(HIRING, t) and _any(BIASED, t) else None),
        R('hr_inclusive', 'Fairness', 'Inclusive wording', 'guidance', 'guide',
          'Adverts and letters use gender-neutral, plain wording and avoid age-coded terms.',
          'Equality Act 2010; good recruitment practice.',
          guidance='Use gender-neutral, plain language. Avoid age-coded words (young, energetic, digital native) and requirements that are not essential to the job.'),
        R('hr_casework', 'Confidentiality', 'Casework stays inside your tenant', 'enforced', 'block',
          'Grievance, disciplinary, investigation and tribunal material is only processed by AI inside your tenant.',
          'ACAS Code of Practice on disciplinary and grievance procedures; confidentiality and legal privilege.',
          lambda t, p: 'Disciplinary, grievance or investigation material sent outside your tenant.' if _any(CASEWORK, t) and not p['in_tenant'] else None),
        R('hr_signoff', 'Oversight', 'HR signs off anything sent to a person', 'gate', 'review',
          'Letters and emails to employees or candidates are held until an HR adviser approves them.',
          'Accountability (UK GDPR Article 5(2)); fair process.',
          lambda t, p: 'Drafts something that will be sent to a person.' if _any(OUTBOUND, t) and _any(TO_PERSON, t) else None),
        R('hr_disclosure', 'Oversight', 'Say when AI helped', 'guidance', 'guide',
          'Employee-facing documents say they were drafted with AI and reviewed by HR.',
          'Transparency (UK GDPR Articles 13 and 14); ICO guidance on explaining AI decisions.',
          guidance='End employee-facing letters with: "Drafted with AI assistance and reviewed by HR."'),
        R('hr_retention', 'Records', 'Candidate data deleted after six months', 'enforced', 'note',
          'CVs and applicant details used with AI are deleted six months after the recruitment campaign closes.',
          'UK GDPR Article 5(1)(e), storage limitation; ICO employment practices guidance.',
          lambda t, p: 'Candidate information: deleted six months after the campaign closes.' if _any(HIRING, t) and _any(r'\b(?:CV|applicants?|candidates?)\b', t) else None),
        R('hr_audit', 'Records', 'Every request is recorded', 'enforced', 'log',
          'Every request, block, redaction and approval is written to the audit trail.',
          'UK GDPR Article 5(2), accountability.', lambda t, p: 'Recorded in the audit trail.', locked=True),
    ])


def _sc_special(text, p):
    if (special_about_person(text) or _any(r'\b(?:convict\w*|offen[cs]e\w*|criminal record)\b', text)) and not p['in_tenant']:
        return 'Health, substance use or criminal information about a person; not allowed outside the council\'s tenant.'
    return None


CARE = dict(
    id='care', name='Council social care', audience='A Scottish council\'s adult and children\'s social work teams using AI for case notes, letters and summaries.',
    basis='UK GDPR and DPA 2018, Social Work (Scotland) Act 1968, Adult Support and Protection (Scotland) Act 2007, '
          'National Guidance for Child Protection in Scotland, Public Records (Scotland) Act 2011, SSSC Codes of Practice.',
    samples=[
        ('Case note summary', "Summarise the case notes for Mrs Agnes Reid, CHI 0101010001, DOB 01/01/1950, tel 07700 900123. "
                              "She has early dementia and her neighbour said she has been leaving the cooker on."),
        ('Disclosure on a visit', "During today's visit the child disclosed that her mother's partner hits her. What risk level should we give this?"),
        ('Eligibility', 'Is Mr Bell eligible for a care package under self-directed support? Decide and approve the budget.'),
        ('Letter to a family', 'Draft a letter to Mr and Mrs Kerr confirming the date and time of their review meeting.'),
        ('Marked chronology', 'OFFICIAL-SENSITIVE\nPrepare a chronology of contacts with the family for the Children\'s Hearing panel.'),
    ],
    rules=[
        R('sc_protection', 'Protection', 'Protection concerns go to a person, not a model', 'enforced', 'escalate',
          'Possible harm to a child or adult at risk is never assessed by AI. The request stops and goes to the duty social work team.',
          'Adult Support and Protection (Scotland) Act 2007; National Guidance for Child Protection in Scotland.',
          lambda t, p: 'Describes possible harm or a protection concern.' if _any(PROTECTION, t) else None),
        R('sc_decisions', 'Protection', 'No automated eligibility, risk or care decisions', 'enforced', 'block',
          'AI never decides eligibility, risk levels, budgets or placements. It can summarise; a social worker decides.',
          'UK GDPR automated decision-making; Social Work (Scotland) Act 1968; Social Care (Self-directed Support) (Scotland) Act 2013.',
          lambda t, p: 'Asks the AI to decide eligibility, risk, a budget or a placement.' if _near(CARE_DECISION, CARE_CONTEXT, t, 120) else None),
        R('sc_chi', 'Identifiers', 'CHI numbers removed', 'enforced', 'redact',
          'Community Health Index numbers are recognised (date and check digit) and removed before the model sees the text.',
          'CHI is the NHS Scotland identifier; health data is special category (UK GDPR Article 9).', ('CHI number',)),
        R('sc_ids', 'Identifiers', 'Other identifiers removed', 'enforced', 'redact',
          'Dates of birth, National Insurance numbers, phone numbers, email addresses and postcodes are replaced with placeholders.',
          'UK GDPR Article 5(1)(c), data minimisation.',
          ('date of birth', 'National Insurance number', 'phone number', 'email address', 'postcode')),
        R('sc_special', 'Sensitive information', 'Sensitive information stays in the council\'s tenant', 'enforced', 'block',
          'Health, disability, substance use and criminal information about a person is only processed by AI inside the council\'s tenant.',
          'UK GDPR Articles 9 and 10; Data Protection Act 2018 Schedule 1.', _sc_special),
        R('sc_marking', 'Sensitive information', 'OFFICIAL-SENSITIVE stays in the tenant', 'enforced', 'block',
          'Material marked OFFICIAL-SENSITIVE is never sent to an AI service outside the council\'s tenant.',
          'Government Security Classifications Policy; council information security policy.',
          lambda t, p: 'Marked OFFICIAL-SENSITIVE and sent outside the tenant.' if _any(MARKINGS, t) and not p['in_tenant'] else None),
        R('sc_third_party', 'Sensitive information', 'Third-party information flagged', 'enforced', 'flag',
          'Information from or about relatives, neighbours and others is flagged so it can be identified and, if needed, withheld in a subject access response.',
          'Data Protection Act 2018 Schedule 2 Part 3 (third-party information in subject access requests).',
          lambda t, p: 'Contains information from or about another person.' if _any(THIRD_PARTY, t) else None),
        R('sc_need_to_know', 'Access', 'Need to know: allocated cases only', 'enforced', 'flag',
          'Answers draw only on cases allocated to the worker asking. Nothing from other cases is used.',
          'Caldicott principles; the council\'s information sharing protocols.',
          lambda t, p: 'Limited to cases allocated to you.' if _any(r'\b(?:case|service user|client|family|child|Mr|Mrs|Ms)\b', t) else None),
        R('sc_residency', 'Access', 'Approved UK services only', 'enforced', 'block',
          'Only AI services covered by the council\'s DPIA and processing data in the UK may be used.',
          'UK GDPR Chapter V (international transfers); the council\'s DPIA.',
          lambda t, p: f'{p["name"]} is not on the approved list.' if not p['uk'] else None),
        R('sc_signoff', 'Oversight', 'Social worker signs off anything that leaves', 'gate', 'review',
          'Letters, reports and chronologies are held until the allocated social worker approves them, and are recorded as AI-assisted.',
          'SSSC Codes of Practice for Social Service Workers and Employers (accountability).',
          lambda t, p: 'Drafts something that will go to a family, a panel or the record.' if _any(OUTBOUND, t) else None),
        R('sc_plain', 'Oversight', 'Plain language and accessible formats', 'guidance', 'guide',
          'Writing for people uses plain English, and other languages and formats are offered.',
          'Equality Act 2010; British Sign Language (Scotland) Act 2015; Gaelic Language (Scotland) Act 2005.',
          guidance='Write for the person: plain English, short sentences, no jargon or acronyms. Offer other languages and formats, '
                   'including Gaelic and BSL, on request.'),
        R('sc_register', 'Oversight', 'Transparency about AI use', 'guidance', 'guide',
          'The service is listed on the Scottish AI Register, and letters to people say AI helped.',
          'Scottish AI Register; Scottish Government AI Strategy.',
          guidance='Letters to service users and families end with: "This letter was prepared with help from AI and checked by your social worker."'),
        R('sc_records', 'Records', 'AI output follows the records management plan', 'enforced', 'note',
          'Anything that becomes part of a case record follows the council\'s records management plan and retention schedule.',
          'Public Records (Scotland) Act 2011; Looked After Children (Scotland) Regulations 2009 for children\'s records.',
          lambda t, p: 'Will be held under the records management plan.' if _any(r'\b(?:case notes?|record|chronology|minute|report)\b', t) else None),
        R('sc_audit', 'Records', 'Every request is recorded', 'enforced', 'log',
          'Every request, block, redaction, escalation and sign-off is written to the audit trail.',
          'UK GDPR Article 5(2), accountability.', lambda t, p: 'Recorded in the audit trail.', locked=True),
    ])

PACKS = {p['id']: p for p in (HR, CARE)}
ESCALATE_TO = {'care': 'the duty social work team', 'hr': 'the HR business partner'}


# ---------------- state ----------------
def _defaults():
    return {pid: {r['id']: r['default'] for r in p['rules']} for pid, p in PACKS.items()}


def state():
    with store.db() as c:
        row = c.execute('SELECT value FROM settings WHERE key=?', (STATE_KEY,)).fetchone()
    s = _defaults()
    try:
        saved = json.loads(row[0]) if row else {}
    except ValueError:
        saved = {}
    for pid, rules in saved.items():
        if pid in s:
            for rid, on in rules.items():
                if rid in s[pid]: s[pid][rid] = bool(on)
    for p in PACKS.values():
        for r in p['rules']:
            if r['locked']: s[p['id']][r['id']] = True
    return s


def _save(s):
    with store.db() as c:
        c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (STATE_KEY, json.dumps(s)))


def set_rule(pack, rule=None, enabled=None, all_on=None, reset=False):
    if pack not in PACKS: raise ValueError('Unknown rule pack.')
    s = state()
    if reset:
        s[pack] = _defaults()[pack]
    elif all_on is not None:
        for r in PACKS[pack]['rules']:
            s[pack][r['id']] = True if r['locked'] else bool(all_on)
    else:
        r = next((x for x in PACKS[pack]['rules'] if x['id'] == rule), None)
        if not r: raise ValueError('Unknown rule.')
        if r['locked'] and not enabled: raise ValueError(f'"{r["name"]}" is always on.')
        s[pack][rule] = bool(enabled)
    _save(s)
    return s


def public():
    """Pack definitions for the page (no functions)."""
    out = []
    for p in PACKS.values():
        out.append({k: p[k] for k in ('id', 'name', 'audience', 'basis')} | {
            'samples': [{'label': a, 'text': b} for a, b in p['samples']],
            'rules': [{k: r[k] for k in ('id', 'theme', 'name', 'kind', 'action', 'what', 'why', 'locked', 'default')}
                      | {'action_label': ACTIONS[r['action']][0]} for r in p['rules']]})
    return {'packs': out, 'state': state(), 'providers': [{'id': k, 'name': v['name']} for k, v in PROVIDERS.items()]}


# ---------------- the test ----------------
def evaluate(pack, text, provider='tenant', enabled=None):
    if pack not in PACKS: raise ValueError('Unknown rule pack.')
    text = (text or '').strip()
    if not text: raise ValueError('Type or choose a message to test.')
    if len(text) > 5000: raise ValueError('Keep the test message under 5,000 characters.')
    p = PROVIDERS.get(provider) or PROVIDERS['tenant']
    on = enabled if enabled is not None else state()[pack]
    fired, off, guidance = [], [], []
    redact_labels = []
    for r in PACKS[pack]['rules']:
        hit = None
        if r['action'] == 'redact':
            found = sorted({l for _, _, l in find_ids(text, r['detect'])})
            if found: hit = 'Found: ' + ', '.join(found) + '.'
        elif r['action'] == 'guide':
            hit = r['guidance']
        elif r['detect']:
            hit = r['detect'](text, p)
        if not hit: continue
        item = {'rule': r['id'], 'name': r['name'], 'action': r['action'], 'action_label': ACTIONS[r['action']][0], 'message': hit, 'theme': r['theme']}
        if on.get(r['id']):
            fired.append(item)
            if r['action'] == 'redact': redact_labels += list(r['detect'])
            if r['action'] == 'guide': guidance.append(r['guidance'])
        elif r['action'] != 'guide':
            off.append(item)
    strongest = min((ORDER.index(f['action']) for f in fired), default=len(ORDER) - 1)
    action = ORDER[strongest] if fired else 'log'
    outcome = ACTIONS[action][1]
    sent, removed = None, []
    if outcome in ('allowed', 'redacted', 'held'):
        sent, removed = redact(text, redact_labels)
        if outcome == 'allowed' and removed: outcome = 'redacted'
    headline = {
        'escalated': f'Stopped and sent to {ESCALATE_TO[pack]}. No AI was used.',
        'blocked': 'Blocked before it reached the AI.',
        'held': 'Sent to the AI; the result is held until a person signs it off.',
        'redacted': 'Sent to the AI with identifiers removed.',
        'allowed': 'Sent to the AI.',
    }[outcome]
    return {'outcome': outcome, 'headline': headline, 'provider': p['name'], 'fired': fired, 'off': off,
            'sent': sent, 'removed': removed, 'instructions': guidance}
