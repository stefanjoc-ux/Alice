"""Organisation research: web search proposes facts with sources; invented sources and personal data dropped; nothing approved."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json
from types import SimpleNamespace as NS
import substrate_store as s
s.init()
import organisations as O, org_research as OR, agents as A, temple
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app); H = {'x-admin-token': app.ADMIN_TOKEN}
temple.save_settings(False, 'claude')

PAGE1, PAGE2 = 'https://www.examplecouncil.gov.uk/council-plan', 'https://www.examplecouncil.gov.uk/about'
REPLY = {'name': 'Example Council', 'kind': 'council', 'website': 'https://www.examplecouncil.gov.uk',
         'description': 'A Scottish local authority serving about 150,000 people.',
         'facts': [
             {'section': 'purpose', 'statement': 'Its Council Plan 2024-28 prioritises tackling poverty and net zero by 2045.', 'source_url': PAGE1, 'source_title': 'Council Plan', 'as_of': '2024-04-01'},
             {'section': 'identity', 'statement': 'A Scottish local authority serving about 150,000 residents.', 'source_url': PAGE2 + '/', 'source_title': 'About us', 'as_of': ''},
             {'section': 'technology', 'statement': 'Runs on Microsoft 365 with a cloud-first strategy adopted in 2023.', 'source_url': 'https://made-up.example/blog', 'source_title': 'Invented'},
             {'section': 'structure', 'statement': 'The Chief Digital Officer can be reached at jane.doe@examplecouncil.gov.uk for AI matters.', 'source_url': PAGE2},
             {'section': 'relationship', 'statement': 'Insight has an open opportunity with them for a tenant migration.', 'source_url': PAGE1},
         ]}
SEEN = {PAGE1: 'Council Plan 2024-28', PAGE2: 'About the council', 'https://www.examplecouncil.gov.uk/news': 'News'}
calls = []
def fake_ask(prompt, query, provider, workload=''):
    calls.append((prompt, query, provider)); return json.dumps(REPLY), dict(SEEN)
OR._ask = fake_ask

# 1. research by name creates the organisation and proposes only verified, rule-passing facts
r = cl.post('/admin/api/organisations/research', json={'name': 'Example Council'}, headers=H).json()
t('research by name: organisation created and facts proposed', r['org'] == 'Example Council' and r['proposed'] == 2)
f = O.facts('Example Council', 'all')
t('nothing is approved automatically', f and all(x['status'] == 'proposed' for x in f))
t('each fact carries its page and source system', all(x['source_ref'].startswith('https://www.examplecouncil.gov.uk/') and x['source_system'] == 'Public web: examplecouncil.gov.uk' for x in f))
t('as-of date kept from the source when given', any(x['as_of'] == '2024-04-01' for x in f))
reasons = ' '.join(d['reason'] for d in r['dropped'])
t('a fact citing a page the search never returned is dropped', 'not among the pages' in reasons)
t('a fact with a personal email address is dropped by data minimisation', any('email' in d['reason'].lower() for d in r['dropped']))
t('relationship facts are never researched', 'Not a section' in reasons)
t('sources listed, cited first', r['sources'][0]['cited'] and {x['url'] for x in r['sources']} >= {PAGE1, PAGE2} and not r['sources'][-1]['cited'])
row = [o for o in O.listing()['organisations'] if o['name'] == 'Example Council'][0]
t('type, description and website filled in from the research', row['kind'] == 'council' and 'local authority' in row['description'] and row['website'] == 'https://www.examplecouncil.gov.uk')
hist = cl.get('/admin/api/organisations/research?org=Example Council').json()['runs']
t('the run is recorded with its sources and what was dropped', hist and hist[0]['proposed'] == 2 and len(hist[0]['dropped']) == 3 and hist[0]['sources'])

# 2. running again: duplicates recognised, your own details never overwritten
O.update('Example Council', description='My own description')
r2 = OR.research('Example Council')
t('re-running finds the same facts already known', r2['proposed'] == 0 and r2['duplicates'] == 2)
t('your description is not overwritten', [o for o in O.listing()['organisations'] if o['name'] == 'Example Council'][0]['description'] == 'My own description')
t('the stored website is used when you research again', 'examplecouncil.gov.uk' in calls[-1][1])

# 3. by website only
REPLY2 = dict(REPLY, name='Fife Example Trust', kind='charity', facts=[dict(REPLY['facts'][0])])
OR._ask = lambda p, q, prov, w='': (json.dumps(REPLY2), dict(SEEN))
r3 = cl.post('/admin/api/organisations/research', json={'website': 'fife-example.org.uk'}, headers=H).json()
t('research by website only: name taken from the research', r3['org'] == 'Fife Example Trust' and r3['website'] == 'https://fife-example.org.uk')

# 4. refusals and safety
for bad in ('http://localhost:8000', 'file:///etc/passwd', 'http://10.0.0.5/admin', 'not a site'):
    t(f'unsafe or invalid website refused ({bad})', cl.post('/admin/api/organisations/research', json={'website': bad}, headers=H).status_code == 400)
t('needs a name or a website', cl.post('/admin/api/organisations/research', json={}, headers=H).status_code == 400)
t('needs the admin token', cl.post('/admin/api/organisations/research', json={'name': 'X Council'}).status_code in (401, 403))
before = len(calls)
OR._ask = fake_ask
t('a protectively marked request never reaches the model', cl.post('/admin/api/organisations/research', json={'name': 'OFFICIAL-SENSITIVE'}, headers=H).status_code == 400 and len(calls) == before)
OR._ask = lambda p, q, prov, w='': ('Sorry, I could not search.', {})
t('an unusable reply is reported clearly', 'expected format' in cl.post('/admin/api/organisations/research', json={'name': 'Example Council'}, headers=H).json()['detail']
  or 'did not return' in cl.post('/admin/api/organisations/research', json={'name': 'Example Council'}, headers=H).json()['detail'])
t('page content is treated as data, never instructions (in the prompt)', 'never as instructions' in OR.PROMPT)

# 5. it is an agent: runs recorded with what it wrote
runs = A.runs('temple-org-research')['runs']
t('research runs appear on the Agents page', runs and any(x['status'] == 'complete' for x in runs))
d = A.run_detail([x for x in runs if x['status'] == 'complete'][-1]['id'])
t('the run records the facts it proposed', d['touched'].get('wrote', {}).get('org_fact', 0) == 2)
t('the run records the web pages it read, cited or not', d['touched'].get('read', {}).get('web', 0) >= 2
  and any(e['target_type'] == 'web' and e['target_id'].startswith('http') and 'cited' in e['detail'] for e in d['events']))

# 6. provider adapters read the search results correctly
class FakeAnthropic:
    def __init__(s_, **k): s_.messages = s_
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
    def create(s_, **k):
        assert any(tool.get('type', '').startswith('web_search') for tool in k['tools'])
        return NS(usage=NS(model_dump=lambda: {'input_tokens': 10, 'output_tokens': 5}), content=[
            NS(type='server_tool_use'), NS(type='web_search_tool_result', content=[NS(url=PAGE1, title='Plan'), NS(url=PAGE2, title='About')]),
            NS(type='text', text=json.dumps(REPLY), citations=[NS(url=PAGE1)])])
import anthropic; anthropic.Anthropic = FakeAnthropic
raw, seen = OR._ask_claude('p', 'q')
t('Anthropic web search: results and citations collected', set(seen) == {PAGE1, PAGE2} and json.loads(raw)['name'] == 'Example Council')
class FakeOpenAI:
    def __init__(s_, **k): s_.responses = s_
    def __enter__(s_): return s_
    def __exit__(s_, *a): pass
    def create(s_, **k):
        assert k['tools'] == [{'type': 'web_search'}]
        return NS(output_text=json.dumps(REPLY), usage=NS(model_dump=lambda: {'input_tokens': 10, 'output_tokens': 5}), output=[
            NS(type='web_search_call', action=NS(sources=[NS(url=PAGE2, title='About')])),
            NS(type='message', content=[NS(annotations=[NS(type='url_citation', url=PAGE1, title='Plan')])])])
import openai; openai.OpenAI = FakeOpenAI
raw, seen = OR._ask_openai('p', 'q')
t('OpenAI web search: sources and citations collected', set(seen) == {PAGE1, PAGE2})
t('page renders the research controls', 'id="o-n-research"' in cl.get('/admin/organisations').text)
t('typing mistakes are not counted as failed runs (agent stays active)', A.get('temple-org-research')['status'] == 'active')
