"""Every model path that sends memories checks EACH memory with rules_engine.check_outbound first (Stefan, 9 Oct 2026), as
Temple's tagging always has: one that fails (a secret, a protective marking) is never sent, the rest still are, and its rule
logs the block. Covers Temple's categorising, client tagging, memory reviews (the memory itself and those it is compared with),
chat suggestions, whole-chat reviews and the search_records connector tool; the whole-chat review also reads only the chat
person's spaces. A memory can only pick up a marking after it was saved (the rules check it on the way in), so the test plants
one directly in this throwaway database. No real model is called: the providers are stand-ins that record what they were sent."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import json, uuid
import substrate_store as store
import app
import clients, conversations, mcp_server, rules_engine, temple, temple_categorise, temple_chat

temple.save_settings(False, 'openai')
store.set_temple_mode('off')   # no background categorising or client tagging after each new memory: the runs below are explicit (manual)
SENT = []                    # every payload a stand-in provider received


class _Reply:
    def __init__(self, text): self.output_text = text; self.usage = None


class _OpenAI:
    """Records what it is sent and answers with nothing to suggest, in the shape each prompt asks for."""
    def __init__(self, **k): self.responses = self
    def __enter__(self): return self
    def __exit__(self, *a): pass

    def create(self, **k):
        SENT.append(str(k.get('input', '')))
        ins = k.get('instructions')
        if ins == temple.PROMPT: return _Reply('Recommendation: approve\nReasons: no clash.\nConflict: no')
        if ins == temple_chat.PROMPT: return _Reply(json.dumps({'suggestions': []}))
        return _Reply(json.dumps({'assignments': []}))


import openai
openai.OpenAI = _OpenAI
conversations._ask = lambda payload: (SENT.append(payload) or (json.dumps({'suggestions': []}), 'openai'))


def mem(title, content, status='approved'):
    r = store.propose(title, content, 'the owner said so')
    if status == 'approved': store.review(r['id'], 'approved')
    return r['id']


def plant(rid, content):
    with store.db() as c: c.execute('UPDATE records SET content=? WHERE id=?', (content, rid))


MARKED = 'OFFICIAL-SENSITIVE: the council restructure plans for next year.'
SECRET = 'The pipeline key is sk-proj-' + 'z' * 48 + ' for the deploy.'
ok = mem('Bid style', 'Bids lead with the outcome for the client, then the method and the team.')
marked = mem('Restructure', 'The council is planning changes next year.'); plant(marked, MARKED)
secret = mem('Deploy key', 'Where the deploy key is kept.'); plant(secret, SECRET)


def leaked():
    return [p for p in SENT if 'restructure plans' in p or 'sk-proj-' in p]


def blocks(target):
    with store.db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM activity WHERE action='rule_blocked'") if target in json.dumps(dict(r))]


# ---------------- one helper, used by every path ----------------
kept, n = rules_engine.check_each([{'t': 'fine'}, {'t': MARKED}, {'t': SECRET}], lambda x: x['t'], 'helper test')
t('check_each keeps what passes and counts what fails', [x['t'] for x in kept] == ['fine'] and n == 2)
t('…and each one left out is logged by its rule', len(blocks('helper test')) == 2)

# ---------------- Temple's categorising ----------------
store.create_category('Work')
SENT.clear()
r = temple_categorise.run(None, manual=True)
t('categorising sends the memories that pass', any('Bid style' in p for p in SENT))
t('…and never a memory that fails the check', not leaked())
t('…it counts them as left out and logs each block', r.get('skipped') == 2 and len(blocks('Temple categorise')) == 2)
with store.db() as c:
    checked = {row[0] for row in c.execute('SELECT record_id FROM record_meta WHERE temple_checked_at IS NOT NULL')}
t('…and marks them checked, so they are not tried again on every run', {marked, secret} <= checked)

# ---------------- client tagging ----------------
clients.create_client('Fernley Council', ['Fernley'])
SENT.clear()
r = clients.run_tagging(manual=True)
t('client tagging sends the memories that pass and never one that fails', any('Bid style' in p for p in SENT) and not leaked())
t('…counted and logged', r.get('skipped', 0) >= 2 and len(blocks('Temple client tagging')) >= 2)

# ---------------- Temple's memory review ----------------
SENT.clear()
p_ok = mem('Bid summaries', 'Every bid ends with a one-page summary for the client.', status='proposed')
res = temple.review_record(p_ok)
t('a review compares with the memories that pass, never one that fails', SENT and not leaked() and 'Bid style' in SENT[-1])
with store.db() as c:
    ctx = json.loads(c.execute('SELECT context FROM temple_reviews WHERE record_id=? ORDER BY created_at DESC', (p_ok,)).fetchone()[0])
t('…the stored context says how many were left out', 'left out by the rules check' in ctx['selection']
  and all(m['id'] not in (marked, secret) for m in ctx['compared_memories']))
SENT.clear()
p_bad = mem('Marked proposal', 'A plain proposal.', status='proposed'); plant(p_bad, MARKED)
res = temple.review_record(p_bad)
t('a proposed memory that fails the check is never sent: the review fails and says why', not SENT and res['status'] == 'failed'
  and 'Not reviewed' in res['error'] and 'Nothing was sent' in res['error'])
with store.db() as c:
    status = c.execute('SELECT status FROM records WHERE id=?', (p_bad,)).fetchone()[0]
t('…and the memory itself is left as it was', status == 'proposed')

# ---------------- Temple's chat suggestions ----------------
SENT.clear()
cid = store.create_chat()['id']; tid = uuid.uuid4().hex
with store.db() as c:
    c.execute('INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,status,created_at) VALUES (?,?,?,?,?,?,?)',
              (tid, cid, 'We always lead bids with the outcome for the client.', 'Noted.', 'openai', 'complete', store.now()))
temple_chat.reserve(cid, tid, True); temple_chat.analyse(cid, tid)
t('chat suggestions send the approved memories that pass, never one that fails', SENT and 'Bid style' in SENT[-1] and not leaked())

# ---------------- whole-chat review ----------------
SENT.clear()
mcp_server.CLIENT = 'Claude Desktop'
saved = mcp_server.save_conversation(title='Bid planning', summary='We planned how bids open: the outcome for the client first, then the method.',
                                     user_quotes=['lead with the outcome for the client'])
res = conversations.review_chat(saved['id'], manual=True)
t('a whole-chat review sends the memories that pass, never one that fails', SENT and 'Bid style' in SENT[-1] and not leaked())

# ---------------- the search_records connector tool ----------------
out = mcp_server.search_records('')
ids = {x['id'] for x in out['records']}
t('search_records returns the memories that pass and withholds one that fails', ok in ids and marked not in ids and secret not in ids
  and '2 memories are not sent' in out.get('withheld_by_checks', ''))
t('…logged by their rules', len(blocks('connector search_records')) == 2)

# ---------------- the whole-chat review reads only the chat person's spaces ----------------
SENT.clear()
member = store.Viewer('0000b1b1-0000-4000-8000-000000000009', 'mira@example.org', 'Mira', 'member', False)
with store.as_viewer(member):
    conversations.review_chat(saved['id'], manual=True)
t('a review done with a Member\'s eyes never sees the owner\'s memories', SENT and 'Bid style' not in SENT[-1])
