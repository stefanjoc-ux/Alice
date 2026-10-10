"""Temple's category and tag housekeeping: it creates and fills what memories need, tidies its own, and anything you
created or a rule uses waits for you. Limits, client names and near-duplicates are checked in code. No real model call."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
import app, substrate_store as s, memory_tags as MT, temple_taxonomy as X, actions, rules_engine
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

X.set_mode('auto')
def mem(title, content):
    rid = s._propose_original(title, content, 'User said')['id']; s.review(rid, 'approved'); return rid
car = [mem(f'Carport {i}', f'Larch carport build detail {i}') for i in range(3)]
bees = [mem(f'Hive {i}', f'Beekeeping note {i}') for i in range(2)]
mine = mem('Carport roof', 'Carport roof is clear polycarbonate')
s.create_category('Home'); s.set_category([mine], 'Home')
MT.create_tag('pricing', 'Prices and rates')
import organisations; organisations.create('Fictional Council', client=True)

REPLY = {'changes': []}
X._ask = lambda payload: ((SENT.update(p=json.loads(payload)) or json.dumps(REPLY)), False)
SENT = {}

REPLY['changes'] = [
    {'op': 'create', 'kind': 'category', 'name': 'Projects', 'description': 'Building work', 'members': car + [mine], 'confidence': 0.9, 'reason': 'Carport memories need a home'},
    {'op': 'create', 'kind': 'tag', 'name': 'bees', 'members': bees, 'confidence': 0.9, 'reason': 'Beekeeping'},
    {'op': 'create', 'kind': 'tag', 'name': 'prices', 'members': bees[:1], 'confidence': 0.9, 'reason': 'near-duplicate of pricing'},
    {'op': 'create', 'kind': 'tag', 'name': 'fictional council', 'members': bees, 'confidence': 0.9, 'reason': 'a client name'},
    {'op': 'create', 'kind': 'category', 'name': 'Tiny', 'members': bees, 'confidence': 0.9, 'reason': 'too few'},
    {'op': 'rename', 'kind': 'category', 'name': 'Home', 'new_name': 'House', 'confidence': 0.9, 'reason': 'clearer'},
    {'op': 'merge', 'kind': 'tag', 'from': ['nonexistent'], 'into': 'pricing', 'confidence': 0.9, 'reason': 'invented name'},
]
r = cl.post('/admin/api/taxonomy/review', headers=H).json()
t('a review applies Temple\'s own changes and holds yours', r['status'] == 'complete' and r['applied'] == 3 and r['proposed'] == 1)
print('REVIEW', r)
cats = {c['name']: c for c in s.list_categories()['categories']}
with s.db() as c:
    by = {x[0]: x[1] for x in c.execute('SELECT name, created_by FROM categories')}
    assigned = {x[0]: (x[1], x[2]) for x in c.execute('SELECT record_id, category, assigned_by FROM record_meta')}
t('a new category is created by Temple and filled', by.get('Projects') == 'temple' and all(assigned[i] == ('Projects', 'temple') for i in car))
t('Temple never moves a memory you categorised', assigned[mine] == ('Home', 'human'))
tags = {x['name']: x for x in MT.list_tags()['tags']}
t('a new tag is created and applied', 'bees' in tags and tags['bees']['total'] == 2)
t('a near-duplicate uses the existing tag instead', 'prices' not in tags and tags['pricing']['total'] == 1)
t('never a client or organisation name; never under the minimum', 'fictional council' not in tags and 'Tiny' not in cats)
st = cl.get('/admin/api/taxonomy').json()
wait = [x for x in st['changes'] if x['state'] == 'proposed']
t('renaming one you created waits for you, and says why', len(wait) == 1 and 'You created' in wait[0]['why_waiting'] and wait[0]['summary'] == 'Rename category “Home” to “House”')
t('the memories sent to Temple are titles and starts only', all(set(m) == {'id', 'title', 'content', 'category', 'tags'} for m in SENT['p']['memories']))
sec = {x['key']: x for x in actions.summary()['sections']}
import library
done = [x for x in library.recent() if x['link'].startswith('taxonomy:')]
t('Actions lists the change to approve; what Temple did is on Activity as library actions (with Undo)', sec['taxonomy']['count'] == 1
  and 'taxonomy_done' not in sec and len(done) == 3 and all(x['can_undo'] for x in done))

# reject: never proposed again; approve: applied
cl.post('/admin/api/taxonomy/' + wait[0]['id'], json={'action': 'reject'}, headers=H)
REPLY['changes'] = [{'op': 'rename', 'kind': 'category', 'name': 'Home', 'new_name': 'House', 'confidence': 0.9, 'reason': 'again'},
                    {'op': 'merge', 'kind': 'tag', 'from': ['bees'], 'into': 'pricing', 'confidence': 0.9, 'reason': 'test merge into yours'}]
r = X.review(manual=True)
waiting = X.changes('proposed')
t('a rejected change is never proposed again', r['proposed'] == 1 and len(waiting) == 1 and waiting[0]['op'] == 'merge')
t('merging Temple\'s tag into one of yours waits for you', 'You created “pricing”' in waiting[0]['why_waiting'])
cl.post('/admin/api/taxonomy/' + waiting[0]['id'], json={'action': 'approve'}, headers=H)
tags = {x['name']: x for x in MT.list_tags()['tags']}
t('approving applies it (memories already tagged keep one tag)', 'bees' not in tags and tags['pricing']['total'] == 2)

# undo Temple's category: memories go back to uncategorised, the category goes
done = next(x for x in X.changes('applied') if x['op'] == 'create' and x['kind'] == 'category')
cl.post('/admin/api/taxonomy/' + done['id'], json={'action': 'undo'}, headers=H)
with s.db() as c:
    gone = not c.execute("SELECT 1 FROM categories WHERE name='Projects'").fetchone()
    back = all((c.execute('SELECT category FROM record_meta WHERE record_id=?', (i,)).fetchone() or [''])[0] == '' for i in car)
t('Undo puts things back as they were', gone and back and next(x for x in X.changes() if x['id'] == done['id'])['state'] == 'undone')

# a category a rule uses is protected, even one Temple made
X._ask = lambda p: (json.dumps({'changes': [{'op': 'create', 'kind': 'category', 'name': 'Projects', 'members': car, 'confidence': 0.9, 'reason': 'again'}]}), False)
t('an undone change is not repeated', X.review(manual=True)['applied'] == 0)
X._ask = lambda p: (json.dumps({'changes': [{'op': 'create', 'kind': 'category', 'name': 'Builds', 'members': car, 'confidence': 0.9, 'reason': 'x'}]}), False)
X.review(manual=True)
with s.db() as c:
    p = json.loads(c.execute("SELECT params FROM rules WHERE id='provider_allow'").fetchone()[0]); p['blocked'] = {'Builds': ['grok']}
    c.execute("UPDATE rules SET params=? WHERE id='provider_allow'", (json.dumps(p),))
X._ask = lambda p: (json.dumps({'changes': [{'op': 'retire', 'kind': 'category', 'name': 'Builds', 'confidence': 0.95, 'reason': 'tidy'}]}), False)
X.review(manual=True)
w = [x for x in X.changes('proposed') if x['target'] == 'Builds']
t('a category a rule uses waits for you, even Temple\'s own', len(w) == 1 and 'A rule uses' in w[0]['why_waiting'])

X.set_mode('suggest')
X._ask = lambda p: (json.dumps({'changes': [{'op': 'describe', 'kind': 'tag', 'name': 'pricing', 'description': 'Rates and prices', 'confidence': 0.9, 'reason': 'r'},
                                           {'op': 'create', 'kind': 'tag', 'name': 'carport', 'members': car, 'confidence': 0.9, 'reason': 'r'}]}), False)
r = X.review(manual=True)
t('suggest only: nothing changes on its own', r['applied'] == 0 and r['proposed'] == 2)
X.set_mode('off')
t('off: no automatic review', X.review() == {'status': 'off'} and not X.due())
t('the page shows Temple\'s housekeeping', 'id="tx-panel"' in cl.get('/admin/memories').text)

# answers that are hard to read: words around the JSON are fine; a cut-off answer is asked again with fewer memories
X.set_mode('auto')
calls = []
def flaky(p):
    calls.append(json.loads(p))
    if len(calls) == 1: return '{"changes": [{"op": "create", "kind": "tag", "name": "half', True
    return 'Here you go:\n```json\n{"changes": [{"op": "describe", "kind": "tag", "name": "pricing", "description": "Prices and rates", "confidence": 0.9, "reason": "r"}]}\n```', False
X._ask = flaky
r = X.review(manual=True)
t('a cut-off answer is asked again, with fewer memories, and words around the JSON are tolerated', len(calls) == 2 and r.get('status') != 'error'
  and len(calls[1]['memories']) <= len(calls[0]['memories']) and 'note' in calls[1])
t('memories go to Temple as short ids, mapped back to the real ones', all(m['id'].startswith('m') and len(m['id']) < 6 for m in calls[0]['memories']))
X._ask = lambda p: ('not json at all', False)
try: X.review(manual=True); t('two unreadable answers: a clear error and nothing changed', False)
except ValueError as e: t('two unreadable answers: a clear error and nothing changed', 'could not be read' in str(e))
X.set_mode('off')
