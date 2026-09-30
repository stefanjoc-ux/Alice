"""Archive: inactive chats leave the sidebar, capture detection, restore, retention and its safeguards."""
import _util
from _util import t
import json, uuid
from datetime import datetime, timezone, timedelta
import app, substrate_store as s, rules_engine as R

def chat(title, days, turns, activity=None, temple=None):
    cid = s.create_chat()['id']; when = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with s.db() as c:
        for u, a in turns:
            c.execute("INSERT INTO chat_turns(id,chat_id,user_text,reply,provider,model,status,activity,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (uuid.uuid4().hex, cid, u, a, 'auto', 'claude-sonnet-5-5', 'complete', json.dumps(activity or []), when))
        for kind, status in (temple or []):
            c.execute("INSERT INTO temple_suggestions(id,chat_id,turn_id,kind,title,content,quote,quote_turn,reason,related,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (uuid.uuid4().hex, cid, 't', kind, 'x', 'x', 'q', 't', 'r', '[]', status, when))
        c.execute('UPDATE chats SET title=?,created_at=?,updated_at=? WHERE id=?', (title, when, when, cid))
    return cid

active = chat('This week: carport roof', 3, [('What finish for larch?', 'Oil it annually.')])
proposed = chat('Fife business case draft', 45, [('Remember the deadline', 'Proposed.')],
                activity=[{'type': 'activity', 'tool': 'propose_record', 'message': 'x'}])
knowledge = chat('Beehive winter prep', 62, [('Wrap hives?', 'Insulate.')], temple=[('knowledge', 'accepted'), ('memory', 'accepted')])
nothing = chat('Random question about Peru', 90, [('Capital of Peru?', 'Lima.')])
pending = chat('Weekend kayaking ideas', 120, [('Where to paddle?', 'Loch Tay.')], temple=[('memory', 'pending')])

t('only recent chats in the sidebar', [c['id'] for c in s.active_chats()] == [active])
a = s.archived_chats()
by = {c['id']: c for c in a['chats']}
t('four chats archived', a['total'] == 4 and active not in by)
t('model proposal counts as captured', by[proposed]['captured'] and by[proposed]['memories'] == 1)
t('accepted Temple items count as captured', by[knowledge]['captured'] and by[knowledge]['knowledge'] == 1)
t('nothing captured is flagged', not by[nothing]['captured'] and not by[pending]['captured'] and a['uncaptured'] == 2)
t('filter: nothing captured', {c['id'] for c in s.archived_chats(only_uncaptured=True)['chats']} == {nothing, pending})
s.restore_chat(proposed)
t('restore brings a chat back to the sidebar', proposed in [c['id'] for c in s.active_chats()])
R.update_rule('retention', enabled=True, new_params={'months': 2})
r = R.run_retention()
left = {c['id'] for c in s.archived_chats()['chats']}
t('retention deletes only old chats with nothing captured', r['deleted'] == 1 and nothing not in left)
t('a chat with an undecided Temple suggestion is kept', pending in left)
t('captured chats are kept', knowledge in left)
R.update_rule('retention', enabled=False)
