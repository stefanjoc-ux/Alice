"""What changed (changelog.py, deploy/changelog_check.py, the setup history in deploy/azure_state.py; Stefan, 9 Oct 2026).
The pull request check (code without a CHANGELOG.md line fails; documentation or tests only pass), the entries imported once
per release and never duplicated, the release's knowledge item through the knowledge checks, the setup history written
without secrets, the What's new page refused to Members, and Ask Temple's recent_changes. No real model or Azure is used."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import base64, json, os, re, sys, tempfile

ROOT = _util.ROOT
sys.path.insert(0, os.path.join(ROOT, 'deploy'))
import changelog_check as CC
import azure_state as S
import changelog

# ---------------- the file itself ----------------
entries, problems = changelog.read()
prs = {e['pr'] for e in entries}
t('CHANGELOG.md reads cleanly', not problems)
if problems: print('   ', problems[:5])
t('…it covers every pull request since the GitHub flow began (#1 to #33)', all(n in prs for n in range(1, 34)))
t('…newest date first, one line per pull request', [e['date'] for e in entries] == sorted([e['date'] for e in entries], reverse=True)
  and len(prs) == len(entries))
t('…manual steps are split out as "You need to"', any(e['pr'] == 19 and 'Step backup' in e['action'] for e in entries)
  and all('You need to' not in e['text'] for e in entries))
bad, why = changelog.parse('# Changelog\n\n## 2026-10-08\n\n- #2 Older\n\n## 2026-10-09\n\n- #3 Newer\nA loose line\n- #3 Again\n- no number\n')
t('the parser names what is wrong: date order, loose lines, repeats, missing numbers', len(why) == 4 and any('newest dates go first' in w for w in why)
  and any('more than one line' in w for w in why) and any('starting with "- #' in w for w in why))

# ---------------- the pull request check ----------------
ok, msg = CC.decide(['app.py', 'admin_ui.py'])
t('check: a code change without a CHANGELOG.md line fails, naming the files', not ok and 'app.py' in msg and 'CHANGELOG.md' in msg)
t('check: …and the same with a test changed too', not CC.decide(['changelog.py', 'tests/test_changelog.py'])[0])
t('check: a change to the pipeline, infrastructure or setup script is code too',
  not CC.decide(['.github/workflows/deploy.yml'])[0] and not CC.decide(['infra/main.bicep'])[0] and not CC.decide(['deploy/azure-setup.ps1'])[0])
good = open(os.path.join(ROOT, 'CHANGELOG.md'), encoding='utf-8').read()
t('check: code with its CHANGELOG.md line passes', CC.decide(['app.py', 'CHANGELOG.md'], good)[0])
t('check: documentation only passes', CC.decide(['CLAUDE.md', 'docs/restore.md', 'INSTALL.txt'])[0])
t('check: tests only passes', CC.decide(['tests/test_rules.py', 'tests/js/draft_doc_test.js', 'tests/fixtures/x.csv'])[0])
t('check: documentation and tests together pass', CC.decide(['tests/README.md', 'tests/test_rules.py', 'CLAUDE.md'])[0])
ok, msg = CC.decide(['app.py', 'CHANGELOG.md'], '# Changelog\n\n## 2026-10-09\n\n- no number here\n')
t('check: a CHANGELOG.md that does not read cleanly fails', not ok and 'does not read cleanly' in msg)


class Git:
    def __init__(self, out, code=0): self.out, self.code, self.args = out, code, None
    def __call__(self, args, **kw):
        self.args = args
        return type('P', (), {'returncode': self.code, 'stdout': self.out, 'stderr': 'fatal: bad revision'})()


g = Git('app.py\nCHANGELOG.md\n')
t('check: the changed files come from git, against where the branch left the base', CC.changed_files('origin/main', run=g) == ['app.py', 'CHANGELOG.md']
  and g.args == ['git', 'diff', '--name-only', 'origin/main...HEAD'])
t('check: the command line exits 1 for a code change without its line, 0 with it',
  CC.main(['--files', 'app.py']) == 1 and CC.main(['--files', 'app.py', 'CHANGELOG.md']) == 0 and CC.main(['--files', 'docs/restore.md']) == 0)
wf = open(os.path.join(ROOT, '.github', 'workflows', 'deploy.yml'), encoding='utf-8').read()
t('check: the workflow for Stefan to copy runs it on pull requests, with the full history',
  'python3 deploy/changelog_check.py --base "origin/${{ github.base_ref }}"' in wf and "github.event_name == 'pull_request'" in wf and 'fetch-depth: 0' in wf)

# ---------------- release entries, imported once per deploy ----------------
import substrate_store as store, knowledge, refs, app, temple_ask
from fastapi.testclient import TestClient

def q(sql, *a):
    with store.db() as c: return c.execute(sql, a).fetchall()
small = tempfile.mkdtemp(prefix='alice-test-cl-')
v1 = os.path.join(small, 'v1.md'); v2 = os.path.join(small, 'v2.md')
open(v1, 'w', encoding='utf-8').write('# Changelog\n\n## 2026-10-08\n\n- #10 Parker writes faster.\n- #9 The Rules page has tabs. You need to: run -Step apps.\n')
open(v2, 'w', encoding='utf-8').write('# Changelog\n\n## 2026-10-09\n\n- #11 Spaces for shared memory.\n\n## 2026-10-08\n\n- #10 Parker writes faster than before.\n'
                                      '- #9 The Rules page has tabs. You need to: run -Step apps.\n')
AZ1 = {'ALICE_VERSION': 'a1b2c3d', 'ALICE_BUILT': '2026-10-09T10:00:00Z', 'CONTAINER_APP_REVISION': 'alice-web--ra1b2c3d',
       'CONTAINER_APP_ENV_DNS_SUFFIX': 'blue.uksouth.azurecontainerapps.io'}
r1 = changelog.record_release(v1, AZ1)
t('a new release imports its entries and records itself', r1['recorded'] and r1['new_entries'] == 2 and r1['version'] == 'a1b2c3d')
fid = r1['knowledge']
m = knowledge.meta([fid]).get(fid) if fid else None
t('…and writes one knowledge item: approved, general, in "Alice changes"', m and m['status'] == 'active' and m['label'] == 'general'
  and m['category'] == changelog.CATEGORY)
text = q('SELECT text FROM files WHERE id=?', fid)[0][0] if fid else ''
t('…listing the release\'s changes, with what you need to do', '#10 Parker writes faster.' in text and 'You need to: run -Step apps.' in text and 'a1b2c3d' in text)
t('…approved through the same path as automatic approval (logged auto_approved, actor Alice), though the switch is off',
  q("SELECT count(*) FROM activity WHERE action='auto_approved' AND target=?", fid)[0][0] == 1)
import spaces
t('…in the work space (system-made, so no personal space)', spaces.space_of('file', fid) in ('', spaces.WORK))
cat = (q('SELECT area FROM categories WHERE name=?', changelog.CATEGORY) or [None])[0]
t('…the category "Alice changes" exists, in the Work area', cat is not None and cat[0] == 'work')
t('…and it has a K- reference connected apps can quote', refs.of('file', [fid]).get(fid, '').startswith('K-'))
r_again = changelog.record_release(v1, AZ1)
t('the same release starting again (a restart, a second process) adds nothing', not r_again['recorded'] and r_again['new_entries'] == 0
  and q('SELECT count(*) FROM changelog_entries')[0][0] == 2
  and q("SELECT count(*) FROM knowledge_meta WHERE category=?", changelog.CATEGORY)[0][0] == 1)
AZ2 = {**AZ1, 'ALICE_VERSION': 'e4f5a6b', 'CONTAINER_APP_REVISION': 'alice-web--re4f5a6b'}
r2 = changelog.record_release(v2, AZ2)
fid2 = r2['knowledge']
text2 = q('SELECT text FROM files WHERE id=?', fid2)[0][0] if fid2 else ''
rows = {r['pr']: dict(r) for r in q('SELECT * FROM changelog_entries')}
t('the next release imports only its new entry, and its item lists only that', r2['new_entries'] == 1 and '#11 Spaces' in text2 and '#10' not in text2
  and len(rows) == 3 and rows[11]['release'] == 'e4f5a6b' and rows[10]['release'] == 'a1b2c3d')
t('…a line reworded later is updated, never added twice', rows[10]['text'] == 'Parker writes faster than before.')
r3 = changelog.record_release(v2, AZ2)
t('…and a restart of that release changes nothing', not r3['recorded'] and r3['new_entries'] == 0
  and q("SELECT count(*) FROM knowledge_meta WHERE category=?", changelog.CATEGORY)[0][0] == 2)
import temple_supersede
items = temple_supersede._items()
t('release notes never suggest replacing one another', temple_supersede.check_one(fid2, items, 'claude', use_model=False) == (0, 0))

# the knowledge checks apply: a release whose notes carry a protective marking is not stored
v3 = os.path.join(small, 'v3.md')
open(v3, 'w', encoding='utf-8').write(open(v2, encoding='utf-8').read().replace('## 2026-10-09\n', '## 2026-10-09\n\n- #12 Notes from the OFFICIAL-SENSITIVE briefing are in.\n', 1))
AZ3 = {**AZ1, 'ALICE_VERSION': 'c7d8e9f', 'CONTAINER_APP_REVISION': 'alice-web--rc7d8e9f'}
r4 = changelog.record_release(v3, AZ3)
note = q('SELECT note,knowledge_id FROM releases WHERE version=?', 'c7d8e9f')[0]
t('a release whose notes fail the knowledge checks stores no item and says why', r4['recorded'] and not r4['knowledge'] and note['knowledge_id'] == ''
  and note['note'] and q("SELECT count(*) FROM knowledge_meta WHERE category=?", changelog.CATEGORY)[0][0] == 2
  and q("SELECT count(*) FROM activity WHERE action='release_notes_refused'")[0][0] == 1)
try:
    import rules_engine
    rules_engine.check_knowledge('Alice release x', changelog._item_text('x', {}, entries)); real_ok = True
except ValueError as e:
    real_ok = False; print('   ', e)
t('the real CHANGELOG.md passes the knowledge checks, every line as a release item would hold it', real_ok)
import demo_instance
demo_instance.ON = True
vd = os.path.join(small, 'vd.md')
open(vd, 'w', encoding='utf-8').write(open(v2, encoding='utf-8').read().replace('## 2026-10-09\n', '## 2026-10-09\n\n- #13 The demo shows a new page.\n', 1))
r_demo = changelog.record_release(vd, {**AZ1, 'ALICE_VERSION': 'dddd123', 'CONTAINER_APP_REVISION': 'alice-demo-web--rdddd123'})
demo_instance.ON = False
t('the demo Alice records the release but writes no knowledge item (its database holds only the fictional team)',
  r_demo['recorded'] and r_demo['new_entries'] == 1 and not r_demo['knowledge'])
r_local = changelog.record_release(v2, {})
t('on the PC (release local) entries are kept but no knowledge item is written', r_local['version'] == 'local' and not r_local['knowledge'])

# ---------------- went live ----------------
changelog._LIVE_NOTED = False
rh = app.revision_hosts(AZ2)
t('not live from its own revision address or /healthz', not changelog.note_live('alice-web--re4f5a6b.blue.uksouth.azurecontainerapps.io', '/admin', rh, AZ2)
  and not changelog.note_live('alice.example.org', '/healthz', rh, AZ2)
  and q('SELECT live_at FROM releases WHERE version=?', 'e4f5a6b')[0][0] is None)
t('live from the first request through the public address, once', changelog.note_live('alice.example.org', '/admin', rh, AZ2)
  and q('SELECT live_at FROM releases WHERE version=?', 'e4f5a6b')[0][0]
  and not changelog.note_live('alice.example.org', '/admin', rh, AZ2))

# ---------------- the setup history (deploy/azure_state.py) ----------------
FILES, SHARE, KEY = 'aliceabc123files', 'alice', 'c3RvcmFnZS1rZXktbm90LXJlYWw='


class FakeAzure:
    def __init__(self): self.calls, self.blobs, self.share, self.n = [], {}, {}, 0

    def __call__(self, args, env=None):
        self.calls.append((list(args), dict(env or {})))
        a = [x for x in args if x not in ('-o', 'json')]
        opt = lambda k: a[a.index(k) + 1] if k in a else None
        ok = lambda obj: (0, json.dumps(obj), '')
        if a[:2] == ['group', 'show']: return ok({'name': 'alice-rg'})
        if a[:2] == ['resource', 'list']: return ok([{'type': 'Microsoft.Storage/storageAccounts', 'name': FILES}])
        if a[:3] == ['deployment', 'group', 'list']: return ok([{'name': 'alice-apps', 'properties': {'timestamp': '2026-10-09T10:00:00+00:00', 'outputs': {}}}])
        if a[:4] == ['storage', 'account', 'keys', 'list']: return ok([{'value': KEY}])
        if a[0] == 'storage': assert (env or {}).get('AZURE_STORAGE_KEY') == KEY
        if a[:3] == ['storage', 'container', 'create']: return ok({})
        if a[:3] == ['storage', 'blob', 'show']:
            b = self.blobs.get(opt('-n'))
            return ok({'properties': {'etag': b['etag'], 'lastModified': '2026-10-09'}}) if b else (3, '', 'BlobNotFound')
        if a[:3] == ['storage', 'blob', 'upload']:
            self.n += 1; self.blobs[opt('-n')] = {'text': open(opt('--file'), encoding='utf-8').read(), 'etag': f'"e{self.n}"'}; return ok({})
        if a[:3] == ['storage', 'directory', 'create']: return ok({'created': True})
        if a[:3] == ['storage', 'file', 'upload']:
            self.share[(opt('--share-name'), opt('--path'))] = open(opt('--source'), encoding='utf-8').read(); return ok({})
        raise AssertionError('unexpected az call: ' + ' '.join(a))


az = FakeAzure()
sp = _util.path('state.json')
open(sp, 'w', encoding='utf-8').write(json.dumps({'storageAccount': FILES, 'shareName': SHARE, 'backup': True}))
SECRET = 'sk-ant-api03-Zx9Yw8Vu7Ts6Rq5Po4Nm3Lk2Ji1Hg0Fe'
lines = []
code = S.history(az, 'alice-rg', sp, who='11111111-1111-1111-1111-111111111111', who_name='stefan@example.org', step='mail',
                 params=['MailFrom=alice@example.org', 'NoLock=True', f'CopilotAuthId={SECRET}', 'SqlPassword=Hunter2Hunter2', 'Weird=1',
                         'SubscriptionId=0000-sub', f'ExtCallers=ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b=Microsoft Copilot:copilot'],
                 error='', out=lines.append)
st = json.loads(az.blobs[S.BLOB]['text'])
hist = st.get(S.HISTORY) or []
last = hist[-1] if hist else {}
t('history: the step is appended to the setup state in Azure: who, when, step, settings, result', code == 0 and last.get('step') == 'mail'
  and last.get('who') == 'stefan@example.org' and last.get('result') == 'ok' and last.get('at', '').startswith('20')
  and last['params'].get('MailFrom') == 'alice@example.org' and last['params'].get('NoLock') == 'True')
everything = json.dumps(az.blobs) + json.dumps(list(az.share.values())) + ' '.join(' '.join(c) for c, _ in az.calls)
t('history: no secret is recorded, whatever its name; unknown and secret-named settings are not recorded',
  SECRET not in everything and 'Hunter2' not in everything and last['params'].get('CopilotAuthId') == S.NOT_RECORDED
  and last['params'].get('SqlPassword') == S.NOT_RECORDED and last['params'].get('Weird') == S.NOT_RECORDED and 'SubscriptionId' not in last['params'])
t('history: IDs and names are kept as given', 'ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b=Microsoft Copilot:copilot' == last['params'].get('ExtCallers'))
t('history: the storage key never appears on a command line', not any(KEY in ' '.join(c) for c, _ in az.calls))
t('history: the steps run before it existed are the first entries (backup, users, apps, users -UseAppRoles on, apps)',
  [h['step'] for h in hist[:5]] == ['backup', 'users', 'apps', 'users', 'apps'] and 'off-site storage account' in hist[0]['note'] and 'alice-do-not-delete' in hist[0]['note'] and 'alice-backup-vault' in hist[0]['note']
  and hist[3]['params'].get('UseAppRoles') == 'on')
mirror = az.share.get((SHARE, 'setup/setup-history.json'))
t('history: copied to the file share for the What\'s new page', mirror and json.loads(mirror)[S.HISTORY][-1]['id'] == last['id'])
code = S.history(az, 'alice-rg', sp, who='x', step='backup', result='failed', params=[],
                 error=f'az storage account create failed: key {SECRET} rejected\nsecond line', out=lines.append)
hist2 = json.loads(az.blobs[S.BLOB]['text'])[S.HISTORY]
t('history: a failed step is recorded with the first line of its error, scrubbed', hist2[-1]['result'] == 'failed' and SECRET not in hist2[-1]['error']
  and 'rejected' in hist2[-1]['error'] and 'second line' not in hist2[-1]['error'] and len([h for h in hist2 if h['id'].startswith('2026-10-09-')]) == 5)
t('history: a different history never stops a step (it is not compared)', S.HISTORY in S.NOT_COMPARED and not S.differences({S.HISTORY: [1]}, {S.HISTORY: [2]}))
setup = open(os.path.join(ROOT, 'deploy', 'azure-setup.ps1'), encoding='utf-8').read()
t('setup script: every step but check records itself at the end, and a failed step from its trap',
  "Record-Step 'ok'" in setup and "Record-Step 'failed'" in setup and setup.index("if ($Step -eq 'check')") < setup.index('trap {')
  and "'history'" in setup and '--param' in setup)

# What's new reads the share's copy plus the steps from before
os.environ['ALICE_SETUP_HISTORY'] = _util.path('share-history.json')
open(os.environ['ALICE_SETUP_HISTORY'], 'w', encoding='utf-8').write(mirror)
steps = changelog.setup_steps()
t('What\'s new lists the setup steps newest first, the hand-recorded ones once', steps[0]['step'] == 'mail' and len([s for s in steps if s['id'].startswith('2026-10-09-')]) == 5)

# ---------------- the page: Owner and Admin, never a Member ----------------
cl = TestClient(app.app)
TOKEN = {'x-admin-token': app.ADMIN_TOKEN}
OWNER, MEMBER, ADMIN = '0000aaaa-0000-0000-0000-000000000001', '0000bbbb-0000-0000-0000-000000000002', '0000cccc-0000-0000-0000-000000000003'


def who(oid, email, roles):
    claims = [{'typ': 'name', 'val': email.split('@')[0]}] + [{'typ': 'roles', 'val': r} for r in roles]
    return {'x-ms-client-principal-id': oid, 'x-ms-client-principal-name': email,
            'x-ms-client-principal': base64.b64encode(json.dumps({'claims': claims, 'role_typ': 'roles'}).encode()).decode(), **TOKEN}


d = cl.get('/admin/api/whats-new').json()
t('on the PC the page shows the release, the changes by day and the setup steps', cl.get('/admin/whats-new').status_code == 200
  and d['days'] and d['days'][0]['entries'] and any(r['version'] == 'e4f5a6b' and r['knowledge_ref'].startswith('K-') for r in d['releases'])
  and d['setup'] and d['running']['version'] == __import__('ui_theme').version_info()['version'])
os.environ.update({'ALICE_TRUST_EASYAUTH': '1', 'ALICE_USE_APP_ROLES': '1', 'ALICE_OWNER_OBJECT_ID': OWNER})
O, M, A = who(OWNER, 'stefan@example.org', ['Alice.Owner']), who(MEMBER, 'mira@example.org', ['Alice.Member']), who(ADMIN, 'ada@example.org', ['Alice.Admin'])
t('the Owner sees What\'s new', cl.get('/admin/api/whats-new', headers=O).status_code == 200 and cl.get('/admin/whats-new', headers=O).status_code == 200)
t('an Admin sees What\'s new', cl.get('/admin/api/whats-new', headers=A).status_code == 200 and cl.get('/admin/whats-new', headers=A).status_code == 200)
mp = cl.get('/admin/whats-new', headers=M, follow_redirects=False)
t('a Member is refused the page and its data', cl.get('/admin/api/whats-new', headers=M).status_code == 403 and mp.status_code in (302, 303, 307, 403))
ma, mm = cl.get('/admin/rules', headers=A), cl.get('/admin/archive', headers=M)
t('…and the menu shows it to the Admin, not to the Member', ma.status_code == 200 and 'href="/admin/whats-new"' in ma.text
  and mm.status_code == 200 and 'href="/admin/whats-new"' not in mm.text)
for k in ('ALICE_TRUST_EASYAUTH', 'ALICE_USE_APP_ROLES', 'ALICE_OWNER_OBJECT_ID'): os.environ.pop(k, None)

# ---------------- Ask Temple ----------------
out = temple_ask.run_tool('recent_changes', {'days': 3650})
t('Ask Temple: recent_changes gives the changes, releases and setup steps', any(c['pull_request'] == 11 and c['what_changed'].startswith('Spaces') for c in out['changes'])
  and any(r['release'] == 'e4f5a6b' for r in out['releases']) and out['setup_steps'] and 'recent_changes' in [x['name'] for x in temple_ask.TOOLS]
  and 'recent_changes' in temple_ask.PROMPT)
t('Ask Temple: each line is checked before it reaches the model; one with a protective marking is left out',
  not any(c['pull_request'] == 12 for c in out['changes']) and out['left_out_by_the_rules'] >= 1)
