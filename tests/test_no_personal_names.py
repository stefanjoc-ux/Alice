"""No personal names in the product (decision D-0052, 10 Oct 2026). Alice's code, prompts, tool descriptions, defaults, seed and demo
data, setup scripts, infrastructure and the documents she shows carry no real person's name, email or object ID, and no real
organisation's, tenant's or domain's name: those come from configuration (deployment.py, the setup parameters) or the signed-in user.

Fails the build on any of them in a file git tracks, except tests/ (fixtures), CHANGELOG.md (the history, read by Alice as data) and
CLAUDE.md (instructions for whoever works on the code, never shown in Alice). The workflows in .github/ are checked like any other file. Fictional
people in demo data and examples use reserved addresses (example.com, example.org, *.example), and every GUID is one of Microsoft's
fixed IDs or Alice's own (listed below with what each is)."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import os, re, subprocess

GUID = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')

EXEMPT = ('tests/', 'CHANGELOG.md', 'CLAUDE.md', 'Static/vendor/')
# Names that must never appear again: the person and the organisations that were in the code before D-0052.
DENY = re.compile(r"stefan|o['’]?connor|tuduma|es3cloud|northants|\bInsight\b(?!s)|\bRGU\b|f955e821|e610cc9b", re.I)
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})')
EMAIL_OK = re.compile(r'^(?:example\.(?:com|org|net)|[a-z0-9.-]+\.example|anthropic\.com)$', re.I)
GUID_OK = {
    '00000000-0000-0000-0000-000000000000',   # an empty GUID (a placeholder)
    '00000003-0000-0000-c000-000000000000',   # Microsoft Graph
    '37f7f235-527c-4136-accd-4a02d197296e',   # Graph scope openid
    '7427e0e9-2fba-42fe-b0c0-848c9e6a8182',   # Graph scope offline_access
    'b633e1c5-b582-4048-a93e-9f11b44c7e96',   # Graph application permission Mail.Send
    '04b07795-8ddb-461a-bbee-02f9e1bf7b46',   # the Azure CLI's public client ID
    'ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b',   # Microsoft's Enterprise token store (Copilot)
    '388aff1f-7b8b-4bcf-bde1-0df23a400f6e',   # Alice.Owner app role (Alice's own, fixed)
    '5fc72aad-c175-48b3-89ef-0d7f38675c1c',   # Alice.Admin app role
    '63e492a6-c40b-4485-b412-3ed386f849d6',   # Alice.Member app role
    'a11ce000-5ab5-4c0e-9a11-ce0000000001',   # Alice's Copilot app (live)
    'a11ce000-5ab5-4c0e-9a11-ce0000000002',   # Alice's Copilot app (demo)
    '6c1f0b9e-2d4a-4f0e-9a51-3e2b7f4c8d11',   # a fictional correlation ID in a rule pack example
    '3f2a9c1e-7b4d-4c2a-8e6f-1a2b3c4d5e6f',   # a fictional subscription ID in a rule pack example
}
# Azure's built-in role IDs, each named in test_infra_roles.BUILT_IN (read from the file: importing it would run its checks)
GUID_OK |= {g.lower() for g in GUID.findall(open(os.path.join(_util.ROOT, 'tests', 'test_infra_roles.py'), encoding='utf-8').read())}


SKIP_DIRS = {'.git', 'data', 'Documents', '.venv', '__pycache__', 'Downloads', 'Claude outputs', 'dist', 'node_modules', '.pytest_cache'}
SKIP_FILES = re.compile(r'(^|/)(\.env(\..*)?|deploy/azure-state\.json|deploy/run-all\.local\.json)$|\.(pyc|zip|bak)$')


def files():
    """The files git tracks; where there is no git (the pipeline runs the suites inside the image), the source tree as the image
    has it, leaving out what .gitignore and .dockerignore leave out."""
    try:
        out = subprocess.run(['git', 'ls-files'], cwd=_util.ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        out = []
        for d, dirs, names in os.walk(_util.ROOT):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            out += [os.path.relpath(os.path.join(d, n), _util.ROOT).replace(os.sep, '/') for n in names]
        out = [f for f in out if not SKIP_FILES.search(f)]
    return [f for f in out if not f.startswith(EXEMPT) and os.path.isfile(os.path.join(_util.ROOT, f))]


def text(f):
    raw = open(os.path.join(_util.ROOT, f), 'rb').read()
    if b'\0' in raw[:4096] and not raw.startswith((b'\xff\xfe', b'\xfe\xff')): return None      # binary (images, fonts)
    for enc in ('utf-8', 'utf-16'):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return None


found = {'name': [], 'email': [], 'guid': []}
scanned = 0
for f in files():
    s = text(f)
    if s is None: continue
    scanned += 1
    for n, line in enumerate(s.splitlines(), 1):
        for m in DENY.finditer(line): found['name'].append(f'{f}:{n}: {m.group(0)}')
        for m in EMAIL.finditer(line):
            if not EMAIL_OK.match(m.group(1)) and m.group(0).lower() != 'noreply@anthropic.com': found['email'].append(f'{f}:{n}: {m.group(0)}')
        for m in GUID.finditer(line):
            if m.group(0).lower() not in GUID_OK: found['guid'].append(f'{f}:{n}: {m.group(0)}')

for k, v in found.items():
    for x in v[:40]: print(f'  {k}: {x}')
t('the scan read the product (code, prompts, scripts, infrastructure, documents)', scanned > 100)
t('no person\'s or organisation\'s name in the product (decision D-0052)', not found['name'])
t('no real email address: fictional ones use example.com, example.org or *.example', not found['email'])
t('no object ID but Microsoft\'s fixed IDs and Alice\'s own (named above)', not found['guid'])

# Names come from configuration: the shipped defaults are roles and neutral words; a deployment sets its own.
import json, deployment
shipped = json.load(open(os.path.join(_util.ROOT, 'config', 'deployment.json'), encoding='utf-8'))
t('the shipped deployment settings name no one', not any(v for k, v in shipped.items() if not k.startswith('_') and k != 'product'))
for k in ('ALICE_REPO_URL', 'ALICE_OWNER_NAME', 'ALICE_ORGANISATION', 'ALICE_TENANT'): os.environ.pop(k, None)   # the image sets ALICE_REPO_URL at build
t('without configuration Alice calls the owner "Owner" and the organisation "your organisation"',
  deployment.owner_name() == 'Owner' and deployment.organisation() == 'your organisation' and deployment.repo_url() == '')
os.environ['ALICE_ORGANISATION'] = 'FICTIONAL Example Ltd'
t('…a deployment names them in its own settings', deployment.organisation() == 'FICTIONAL Example Ltd')
del os.environ['ALICE_ORGANISATION']
t('backup advice says what applies to the deployment: nothing to copy in Azure, the data folder on a PC',
  'point-in-time' in deployment.backup_advice({'CONTAINER_APP_NAME': 'alice-web'}) and 'data folder' in deployment.backup_advice({}))

# The digital teams' key for the person stored before D-0052 still reads as "you", without the name being in the code
import teams
t('a step stored with the old key reads as you', teams.is_you('stefan') and teams.is_you(teams.YOU) and not teams.is_you('lead-qs')
  and teams._you({'member': 'stefan', 'to_member': ''})['member'] == 'you')
