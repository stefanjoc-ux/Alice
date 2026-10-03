"""Memory organisation: areas on categories, tags you create, Temple tagging (mocked), human precedence, filters, routes."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
import json
import substrate_store as s, temple, memory_tags as MT
temple.save_settings(False, 'openai')
def t(label, cond): print(('PASS ' if cond else 'FAIL ') + label)
import temple_categorise as TC, clients as _C
TC.schedule = lambda ids: None; _C.schedule_tagging = lambda *a, **k: None
import temple_tags as TT
TT.schedule = lambda ids=None: None
import app, agents, mcp_server as M
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}

# 1. areas on categories
r = cl.post('/admin/api/categories', json={'name': 'Clients', 'description': 'Client work', 'area': 'work'}, headers=H)
t('category created with an area', r.status_code == 200 and MT.category_areas()['Clients'] == 'work')
cl.post('/admin/api/categories', json={'name': 'Home', 'description': 'House and family', 'area': 'personal'}, headers=H)
cl.post('/admin/api/categories', json={'name': 'Preferences', 'description': 'How I like things'}, headers=H)
cats = {c['name']: c['area'] for c in cl.get('/admin/api/categories').json()['categories']}
t('categories list carries areas', cats == {'Clients': 'work', 'Home': 'personal', 'Preferences': ''})
cl.put('/admin/api/categories/Preferences', json={'name': 'Preferences', 'description': 'How I like things', 'area': 'personal'}, headers=H)
t('area changed by editing', MT.category_areas()['Preferences'] == 'personal')
cl.put('/admin/api/categories/Preferences', json={'name': 'Preferences', 'description': 'How I like things', 'area': ''}, headers=H)

# 2. tags: create, validate, rename
t('tag created', cl.post('/admin/api/tags', json={'name': 'pricing', 'description': 'Rates, margins, quotes', 'area': 'work'}, headers=H).status_code == 200)
cl.post('/admin/api/tags', json={'name': 'family', 'description': 'Family members and plans', 'area': 'personal'}, headers=H)
cl.post('/admin/api/tags', json={'name': 'Microsoft 365', 'description': 'M365 products', 'area': ''}, headers=H)
t('duplicate tag refused (any case)', cl.post('/admin/api/tags', json={'name': 'Pricing'}, headers=H).status_code == 400)
t('commas refused in tag names', cl.post('/admin/api/tags', json={'name': 'a,b'}, headers=H).status_code == 400)
t('tag routes need the admin token', cl.post('/admin/api/tags', json={'name': 'x'}).status_code in (401, 403))
t('# is stripped', MT.clean_tag('#travel') == 'travel')

# memories
ids = {}
for title, content, cat in [('Day rate for architects', 'Architect day rate is 1100 GBP at a 35% margin', 'Clients'),
                            ('Sister birthday', 'Anna\'s birthday is 12 May; plan a family meal', 'Home'),
                            ('Prefers Teams', 'Stefan prefers Teams over email for quick questions', 'Preferences'),
                            ('Loose note', 'Something with no category yet about Copilot licences', '')]:
    rid = s.propose(title, content, 'Stefan said so', cat)['id']; s.review(rid, 'approved'); ids[title] = rid
    if cat: s.set_category([rid], cat)
arch, sis, teams, loose = ids['Day rate for architects'], ids['Sister birthday'], ids['Prefers Teams'], ids['Loose note']

def state(rid, tag):
    with s.db() as c:
        row = c.execute('SELECT assigned_by FROM record_tags WHERE record_id=? AND tag=?', (rid, tag)).fetchone()
    return row[0] if row else None

# 3. human tagging
r = cl.post('/admin/api/memories/tags', json={'ids': [arch], 'add': ['pricing']}, headers=H).json()
t('tag added by you', r['updated'] == 1 and MT.tags_for([arch])[arch]['tags'] == [{'name': 'pricing', 'by': 'human', 'confidence': None}])
t('unknown tag refused', cl.post('/admin/api/memories/tags', json={'ids': [arch], 'add': ['nope']}, headers=H).status_code == 400)
cl.post('/admin/api/memories/tags', json={'ids': [teams], 'remove': ['Microsoft 365']}, headers=H)
t('removing a tag that is not there still remembers it', MT.candidates([teams])[0]['not_these'] == ['Microsoft 365'])

# 4. Temple tagging (mocked): only your tags, never what you removed, never over yours
sent = []
def fake(payload):
    p = json.loads(payload); sent.append(p)
    out = []
    for m in p['memories']:
        out += [{'id': m['id'], 'tag': 'Microsoft 365', 'confidence': 0.9, 'reason': 'mentions Microsoft'},
                {'id': m['id'], 'tag': 'invented tag', 'confidence': 0.99, 'reason': 'x'},
                {'id': m['id'], 'tag': 'family', 'confidence': 0.5, 'reason': 'maybe'}]
    out.append({'id': 'not-a-memory', 'tag': 'pricing', 'confidence': 1, 'reason': 'x'})
    return json.dumps({'tags': out})
TT._ask = fake
agents.set_status('temple-memory-tags', 'active')
res = TT.run(manual=True)
print('   tag run:', res)
t('Temple run completed', res['status'] == 'complete' and res['checked'] >= 4)
t('Temple was given your tags with areas and descriptions', {x['name']: x['area'] for x in sent[0]['tags']} == {'family': 'personal', 'Microsoft 365': 'both', 'pricing': 'work'})
t('Temple was told what is already on each memory', next(m for m in sent[0]['memories'] if m['id'] == arch)['has_tags'] == ['pricing'])
tg = MT.tags_for(list(ids.values()))
t('confident match applied as Temple', {'name': 'Microsoft 365', 'by': 'temple', 'confidence': 0.9} in tg[loose]['tags'])
t('unsure match only suggested', [x['name'] for x in tg[loose]['suggested']] == ['family'])
t('invented tags and ids ignored', all(x['name'] != 'invented tag' for v in tg.values() for x in v['tags'] + v['suggested']))
t('a tag you removed is never put back', all(x['name'] != 'Microsoft 365' for x in tg[teams]['tags'] + tg[teams]['suggested']))
t('your tag untouched', {'name': 'pricing', 'by': 'human', 'confidence': None} in tg[arch]['tags'])
sent.clear(); res2 = TT.run()
t('nothing re-sent once looked at', res2['checked'] == 0 and not sent)

# 5. suggestions: accept and dismiss
cl.post('/admin/api/memories/tag-suggestions', json={'items': [{'id': loose, 'tag': 'family'}], 'action': 'dismiss'}, headers=H)
t('dismissed suggestion remembered as removed', MT.tags_for([loose])[loose]['suggested'] == [] and state(loose, 'family') == 'removed')
r = cl.post('/admin/api/memories/tag-suggestions', json={'ids': [sis], 'action': 'accept'}, headers=H).json()
cl.post('/admin/api/memories/tag-suggestions', json={'ids': [arch, teams], 'action': 'dismiss'}, headers=H)
t('accept and dismiss by memory ids', state(arch, 'family') == state(teams, 'family') == 'removed' and r['done'] == 1 and {'name': 'family', 'by': 'human', 'confidence': None} in MT.tags_for([sis])[sis]['tags'])
cl.post('/admin/api/memories/tags', json={'ids': [loose], 'remove': ['Microsoft 365']}, headers=H)
t('taking off a Temple tag', MT.tags_for([loose])[loose]['tags'] == [])
TT.run(manual=True)
t('…and Temple does not put it back on a manual re-run', MT.tags_for([loose])[loose]['tags'] == [])

# 6. suggest mode
cl.put('/admin/api/tags-mode', json={'mode': 'suggest'}, headers=H)
cl.post('/admin/api/tags', json={'name': 'licensing', 'description': 'Licences', 'area': 'work'}, headers=H)
TT._ask = lambda p: json.dumps({'tags': [{'id': m['id'], 'tag': 'licensing', 'confidence': 0.95, 'reason': 'licences'} for m in json.loads(p)['memories'] if 'licence' in m['content']]})
TT.run()
t('suggest mode: even a confident match waits for you', [x['name'] for x in MT.tags_for([loose])[loose]['suggested']] == ['licensing'] and MT.tags_for([loose])[loose]['tags'] == [])
cl.put('/admin/api/tags-mode', json={'mode': 'off'}, headers=H)
t('off: background runs do nothing', TT.run()['status'] == 'off')
cl.put('/admin/api/tags-mode', json={'mode': 'auto'}, headers=H)

# 7. secrets and markings never sent to Temple
mk = s.propose('Older note', 'Briefing about a council system, written before the marking guard existed', 'note')['id']
with s.db() as c: c.execute("UPDATE records SET content='OFFICIAL-SENSITIVE briefing about a council system' WHERE id=?", (mk,))   # an older memory
sent.clear(); TT._ask = fake
r = TT.run([mk], manual=True)
t('marked memory never sent to Temple, counted as skipped', not any(m['id'] == mk for p in sent for m in p['memories']) and r['skipped'] == 1)
s.review(mk, 'rejected')

# 8. the Memories page listing: area and tag filters
d = cl.get('/admin/api/memories?status=approved&area=work').json()
t('Work shows work and Both categories only', {r['id'] for r in d['records']} == {arch, teams})
d = cl.get('/admin/api/memories?status=approved&area=personal').json()
t('Personal shows personal and Both categories', {r['id'] for r in d['records']} == {sis, teams})
d = cl.get('/admin/api/memories?status=approved&tag=pricing').json()
t('tag filter', [r['id'] for r in d['records']] == [arch] and 'pricing' in [x['name'] for x in d['records'][0]['tags']])
d = cl.get('/admin/api/memories?status=approved&tag=__untagged__').json()
t('untagged filter', loose in {r['id'] for r in d['records']} and arch not in {r['id'] for r in d['records']})
d = cl.get('/admin/api/memories?status=approved&tag=__suggested__').json()
t('suggested filter', [r['id'] for r in d['records']] == [loose] and d['records'][0]['tag_suggestions'][0]['name'] == 'licensing')
d = cl.get('/admin/api/memories?status=approved').json()
t('counts for the tag chips', d['tag_counts'].get('pricing') == 1 and d['tag_counts'].get('family') == 1 and d['tag_suggested'] == 1)
t('known tags and category areas sent to the page', len(d['known_tags']) == 4 and d['category_areas']['Home'] == 'personal')
t('bad area refused', cl.get('/admin/api/memories?area=sideways').status_code == 422)

# 9. rename and delete
cl.put('/admin/api/tags/pricing', json={'name': 'Pricing and rates', 'description': 'Rates', 'area': 'work'}, headers=H)
t('rename carries the assignments', 'Pricing and rates' in [x['name'] for x in MT.tags_for([arch])[arch]['tags']] and state(arch, 'pricing') is None)
r = cl.delete('/admin/api/tags/family', headers=H).json()
t('delete takes the tag off, memory unchanged', r['untagged'] == 1 and 'family' not in [x['name'] for x in MT.tags_for([sis])[sis]['tags']]
  and s.organised_records('approved')['total'] >= 4)

# 10. models see tags; Ask Temple sees the organisation
rec = next(x for x in M.search_records('architects')['records'] if x['id'] == arch)
t('search_records returns tags', 'Pricing and rates' in rec.get('tags', []))
import temple_ask
o = temple_ask.run_tool('memory_organisation', {})
t('Ask Temple: memory organisation', {c['name']: c['area'] for c in o['categories']}['Clients'] == 'Work' and any(x['name'] == 'Pricing and rates' for x in o['tags']))

# 11. the agent is registered and grouped; activity labels
t('agent registered in a group', 'temple-memory-tags' in [b[0] for b in agents.BUILTIN] and agents._AGENT_GROUP.get('temple-memory-tags') == 'stewardship')
import activity_log
t('activity labels', all(a in activity_log.LABELS for a in ('tag_created', 'tags_set', 'temple_tagged', 'category_area_set', 'tag_suggestions_accept')))
