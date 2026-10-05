"""Long proposals: the writer's answer is never silently cut off. Up to 12 sections are written in one call; if that answer
stops at the model's length limit, or the template has more sections, the draft is written a few sections at a time, each part
seeing the whole outline and what is already written, with the resource plan from the last part. A section too long even on
its own fails with a message naming it. Line breaks inside the JSON strings are accepted. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, re
import substrate_store as s
s.init()
import app, assistants as AS, proposals as P

calls = []
LIMIT = {'n': 99}           # the "model" can write this many sections before it is cut off
def fake_call(provider, system, messages, max_tokens=1500, timeout=60, workload='Assistant', meta=None):
    msg = messages[0]['content']
    calls.append(msg)
    want = [ln[2:].split(' [KEEP]')[0] for ln in msg.split('SECTIONS\n')[1].split('\n\nRATE CARD')[0].split('\n') if ln.startswith('- ')]
    if len(want) > LIMIT['n']:
        if meta is not None: meta['truncated'] = True
        return '{"sections": [{"title": "' + want[0] + '", "body": "Half a sent'           # cut off mid-answer
    last = 'Give the resource_plan for the whole proposal' in msg or 'THIS PART' not in msg
    body = lambda x: f'{x} body.\nWith a line break written straight into the string.'
    return ('{"sections": [' + ', '.join('{"title": "%s", "body": "%s"}' % (x, body(x)) for x in want) + '], "resource_plan": '
            + ('[{"role": "Consultant", "quantity": 5, "purpose": "Delivery"}]' if last else '[]') + ', "gaps": ["gap for ' + want[0] + '"]}')
AS._call = fake_call

aid = 'proposal-writer'
def job(n, keep=()):
    return {'title': 'Fictional bid', 'brief': 'Fictional Borough Council wants a discovery.', 'organisation': 'Fictional Borough Council',
            'client': '', 'use_memory': False, 'notes': '', 'structure': '', 'template': '', 'references': [], 'writer': 'claude_sonnet',
            'qa': 'claude_sonnet', 'rate_card': [{'role': 'Consultant', 'unit': 'day', 'cost': 400, 'sell': 800}],
            'sections': [{'title': f'Section {i + 1}', 'guidance': '', 'keep': i in keep} for i in range(n)]}

calls.clear(); r = P.write(aid, job(8))
t('a short proposal is one call', len(calls) == 1 and [x['title'] for x in r['sections']] == [f'Section {i + 1}' for i in range(8)])
t('line breaks inside the answer\'s strings are accepted', '\n' in r['sections'][0]['body'] and r['resource_plan'][0]['quantity'] == 5)

LIMIT['n'] = 6; calls.clear(); r = P.write(aid, job(8))
t('a cut-off answer is written again in parts', len(calls) == 3 and all(x['body'].startswith(x['title']) for x in r['sections']))
t('the plan comes from the last part, gaps from every part', r['resource_plan'] and r['resource_plan'][0]['role'] == 'Consultant' and len(r['gaps']) == 2)
t('each part sees the whole outline and what is already written', 'WHOLE PROPOSAL OUTLINE' in calls[2] and '8. Section 8' in calls[2]
  and '\n\nALREADY WRITTEN\n### Section 1' in calls[2] and '\n\nALREADY WRITTEN\n' not in calls[1])

LIMIT['n'] = 99; calls.clear(); r = P.write(aid, job(20, keep=(1, 2)))
t('a long template goes straight to parts (18 to write, 6 at a time)', len(calls) == 3 and len(r['sections']) == 20
  and r['sections'][1]['body'] == '' and r['sections'][19]['body'].startswith('Section 20'))
t('standard-text sections are never sent to be written', all('- Section 2\n' not in c and not c.split('SECTIONS\n')[1].startswith('- Section 2 ') for c in calls))

LIMIT['n'] = 3; calls.clear(); r = P.write(aid, job(20))
t('a part that is still cut off is halved again', len(r['sections']) == 20 and all(x['body'] for x in r['sections']) and len(calls) > 4)

LIMIT['n'] = 0
try: P.write(aid, job(3)); t('a section too long on its own fails, naming it', False)
except ValueError as e: t('a section too long on its own fails, naming it', '"Section 1"' in str(e) and 'ran out of room' in str(e))

# a revision in parts sends each part only its own sections of the previous draft, with the QA feedback
LIMIT['n'] = 99; calls.clear()
j = job(14); j['context'] = ''
prev = {'sections': [{'title': f'Section {i + 1}', 'body': f'old {i + 1}'} for i in range(14)], 'resource_plan': [], 'gaps': []}
r = P.write(aid, j, previous=prev, feedback={'issues': [{'issue': 'Too vague'}]})
t('a revision in parts carries the QA feedback and only its own previous sections', len(calls) == 3 and all('Too vague' in c for c in calls)
  and '"old 1"' in calls[0] and '"old 13"' not in calls[0] and '"old 13"' in calls[2])

# not JSON and not cut off: a clear message
AS._call = lambda *a, **k: 'Sorry, I cannot help with that.'
try: P.write(aid, job(3)); t('an answer that is not JSON fails clearly', False)
except ValueError as e: t('an answer that is not JSON fails clearly', 'usable answer' in str(e) and 'expected format' in str(e))
