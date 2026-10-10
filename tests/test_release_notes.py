"""Release notes after #38 (10 Oct 2026): every release had its knowledge item, but titled "Alice release <commit>: 1 change", so a
search for "Alice changes" (search is literal) found only the first one and none named its pull requests. Items now say "Alice changes:
release <commit> (#n, …)" and name each pull request first; old-form items are rewritten once and superseded (kept, linked); a
release whose item was never written is written at the next start. Every value here is fictional."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import os, tempfile
import app            # with the release record off at start-up (tests/_util.py); record_release is called below
import substrate_store as store, changelog, knowledge, mcp_server

small = tempfile.mkdtemp(prefix='alice-test-rn-')
log = os.path.join(small, 'CHANGELOG.md')
open(log, 'w', encoding='utf-8').write('# Changelog\n\n## 2026-10-10\n\n- #42 Open by default: an Organisation space.\n'
                                       '- #41 Work items no longer get stuck. You need to: link your accounts.\n\n## 2026-10-09\n\n'
                                       '- #37 What changed in Alice, at each deploy.\n')
AZ = {'ALICE_BUILT': '2026-10-10T10:00:00Z', 'CONTAINER_APP_REVISION': 'alice-web--r1'}


def q(sql, *a):
    with store.db() as c: return [dict(r) for r in c.execute(sql, a).fetchall()]


# The state the live Alice was in: one release item per release in the old form, and one release whose item was never written.
with store.db() as c:
    changelog._schema(c)
    for v, prs, day in (('b30bcd0', [37], '2026-10-09'), ('03e52ef', [41], '2026-10-10')):
        c.execute('INSERT INTO releases(version,built,revision,started_at,entries) VALUES (?,?,?,?,?)', (v, '2026-10-09', 'r', store.now(), len(prs)))
    c.execute('INSERT INTO releases(version,built,revision,started_at,entries) VALUES (?,?,?,?,?)', ('ae24310', '2026-10-10', 'r', store.now(), 1))
    for pr, day, text, rel in ((37, '2026-10-09', 'What changed in Alice, at each deploy.', 'b30bcd0'),
                               (41, '2026-10-10', 'Work items no longer get stuck.', '03e52ef'),
                               (42, '2026-10-10', 'Open by default: an Organisation space.', 'ae24310')):
        c.execute('INSERT INTO changelog_entries(pr,day,text,action,release,imported_at) VALUES (?,?,?,?,?,?)', (pr, day, text, '', rel, store.now()))
changelog._category()
olds = {}
for v, pr, text in (('b30bcd0', 37, 'What changed in Alice, at each deploy.'), ('03e52ef', 41, 'Work items no longer get stuck.')):
    r = knowledge.create('note', f'Alice release {v}: 1 change (9 Oct 2026)', f'Release {v} of Alice.\n\n- #{pr} {text}', f'CHANGELOG.md, release {v}',
                         'Alice', status='active', category=changelog.CATEGORY)
    olds[v] = r['id']
    with store.db() as c: c.execute('UPDATE releases SET knowledge_id=? WHERE version=?', (r['id'], v))
found = mcp_server.search_files('Alice changes')
t('the old form: a search for "Alice changes" finds none of the release items', not found.get('matches'))

# The next release starts: it records itself, then writes what is missing and rewrites the old form
r = changelog.record_release(log, {**AZ, 'ALICE_VERSION': '4a26653'})
t('the backfill ran at start-up', r.get('backfilled') == {'written': 1, 'rewritten': 2})
items = q("SELECT m.file_id, m.title, m.status, m.superseded_by FROM knowledge_meta m WHERE m.category=?", changelog.CATEGORY)
live = {i['title']: i for i in items if i['status'] == 'active'}
t('every release has one item titled "Alice changes: release <commit> (#n)"',
  any(k.startswith('Alice changes: release b30bcd0 (#37)') for k in live) and any(k.startswith('Alice changes: release 03e52ef (#41)') for k in live)
  and any(k.startswith('Alice changes: release ae24310 (#42)') for k in live))
text = q('SELECT f.text FROM files f JOIN knowledge_meta m ON m.file_id=f.id WHERE m.title LIKE ?', 'Alice changes: release 03e52ef%')[0]['text']
t('…naming its pull requests first, then what each one did', 'Pull requests in this release (1): #41.' in text and '- #41 Work items no longer get stuck.' in text)
t('the old-form items are superseded, kept and linked to the new ones', all(
  knowledge.meta([olds[v]])[olds[v]]['status'] == 'archived' and knowledge.meta([olds[v]])[olds[v]]['superseded_by'] for v in olds))
found = mcp_server.search_files('Alice changes release')
names = {m['name'] for m in found.get('matches', [])}
t('a search for "Alice changes" now finds every release', len({n for n in names if 'release' in n.lower()}) >= 3)
r2 = changelog.record_release(log, {**AZ, 'ALICE_VERSION': '4a26653'})
t('…and running again changes nothing', r2.get('backfilled') == {'written': 0, 'rewritten': 0})
t('the release that just started has its own item, naming its pull requests', any(k.startswith('Alice changes: release 4a26653') for k in
  {i['title'] for i in q("SELECT title FROM knowledge_meta WHERE category=? AND status='active'", changelog.CATEGORY)}) or not r['new_entries'])
