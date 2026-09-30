"""Auto routing: rules first, the classifier only when needed, step-down after light asks, image routing."""
import _util
from _util import t
import asyncio, json
import app, router, substrate_store as s

t('focus files go to the strong model', router.rules('what does this say?', ['f1'])[0] == router.HEAVY)
t('code or analysis goes to the strong model', router.rules('write a python function to parse this CSV and total the spend by supplier', [])[0] == router.HEAVY)
t('greetings stay light', router.rules('thanks!', [])[0] == router.LIGHT)
t('ambiguous text defers to the classifier', router.rules('I need to think about the migration timeline and what the council expects from us next quarter', [])[0] is None)

calls = []
async def fake_classifier(prompt, payload):
    calls.append(payload); return {'tier': 'light', 'reason': 'casual'}
router._haiku_json = fake_classifier
cid = s.create_chat()['id']
run = lambda text, files=(), images=False: asyncio.run(router.route(cid, text, list(files), images))
r = run('please analyse the attached spreadsheet and summarise supplier spend', ['f1'])
t('heavy request routed to Sonnet', r['selection'] == 'claude_sonnet' and r['method'] == 'rule')
steps = [run('ok thanks') for _ in range(3)]
t('stays on Sonnet for the first light asks', [x['selection'] for x in steps[:2]] == ['claude_sonnet', 'claude_sonnet'])
t('steps back down after 3 light asks', steps[2]['selection'] == 'openai')
before = len(calls)
run('I need to think about the migration timeline and what the council expects from us next quarter')
t('classifier used only for ambiguous text', len(calls) == before + 1)
t('never picks Opus automatically', 'claude_opus' not in router.TIER_SELECTION.values())
t('fun image goes to Grok', run('make a funny cartoon of my dog in a kayak', images=True)['selection'] == 'grok')
t('work image goes to Luna', run('create a slide graphic of our migration roadmap for the council', images=True)['selection'] == 'openai')
