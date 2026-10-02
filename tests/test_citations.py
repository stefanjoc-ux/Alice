"""Web search citation markup never ends up in organisation facts, opportunities or news."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import uuid
import substrate_store as s
s.init()
import organisations as O, opportunities as OP

raw = 'Kingspan (cite index="3-1">is a global building materials group</cite> with <cite index="5-2,5-3">22,000 employees</cite>. [cite: 4]'
t('citation markup is removed and the words kept', O.strip_citations(raw).split() == 'Kingspan is a global building materials group with 22,000 employees.'.split())
t('ordinary words are untouched', O._clean('We cite our sources; see the index="x" note.', 200) == 'We cite our sources; see the index="x" note.')
O.create('Kingspan', 'company')
f = O.propose_fact('Kingspan', 'identity', raw, 'Public web', 'https://example.com/kingspan')
with s.db() as c: st = c.execute('SELECT statement FROM org_facts WHERE id=?', (f['id'],)).fetchone()[0]
t('a proposed fact is stored without markup', 'cite' not in st and '22,000 employees' in st)

fid = uuid.uuid4().hex
with s.db() as c:
    c.execute("INSERT INTO org_facts(id,org,section,statement,source_system,as_of,review_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
              (fid, 'Kingspan', 'identity', raw, 'Public web', '2026-10-01', '2027-10-01', s.now()))
    oid = uuid.uuid4().hex
    c.execute("INSERT INTO opportunities(id,org,title,summary,why_now,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
              (oid, 'Kingspan', 'Fabric <cite index="1-1">pilot</cite>', raw, '(cite index="2-1">New CIO</cite>', s.now(), s.now()))
n = O.tidy_citations('org_facts', ['statement']); m = O.tidy_citations('opportunities', ['title', 'summary', 'why_now', 'next_step'])
with s.db() as c:
    a = c.execute('SELECT statement FROM org_facts WHERE id=?', (fid,)).fetchone()[0]
    o = dict(c.execute('SELECT title,summary,why_now FROM opportunities WHERE id=?', (oid,)).fetchone())
    logged = c.execute("SELECT count(*) FROM activity WHERE action='citations_tidied'").fetchone()[0]
t('markup already stored is tidied, words unchanged', n == 1 and 'cite' not in a and a.startswith('Kingspan is a global'))
t('opportunities are tidied too', m == 1 and o['title'] == 'Fabric pilot' and o['why_now'] == 'New CIO')
t('the tidy is logged', logged >= 2)
t('running it again changes nothing', O.tidy_citations('org_facts', ['statement']) == 0)
t('opportunity text from a scan is cleaned', OP._txt('A <cite index="1-1">new</cite> CIO', 100) == 'A new CIO')
