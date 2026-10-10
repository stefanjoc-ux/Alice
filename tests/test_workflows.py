"""Deploying is locked to main (10 Oct 2026): every GitHub Actions job that signs in to Azure or deploys runs in the GitHub
environment "production" (which the repository's settings limit to the main branch), checks it is on main, and is the only
kind of job given `id-token: write` (the OIDC token azure/login exchanges with Entra). Pull request runs can never sign in to
Azure. The workflows live in .github/workflows and change in pull requests like any other file (the deploy/github copies are
retired). Read with the standard library: no YAML package in the image."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import re
from pathlib import Path

ROOT = Path(_util.ROOT)
WF = ROOT / '.github' / 'workflows'
AZURE = re.compile(r'azure/login@|(^|[\s;&|(`$])az (acr|containerapp|login|account|deployment|group|role|ad|storage|keyvault)\b'
                   r'|deploy/(promote|push_image)\.sh', re.M)


def jobs(text):
    """{job name: its lines} from a workflow's top-level `jobs:` block (two-space indentation, as GitHub's own files are)."""
    out, cur, inside = {}, None, False
    for line in text.splitlines():
        if re.match(r'^jobs:\s*$', line): inside = True; continue
        if inside and re.match(r'^\S', line): inside = False
        if not inside: continue
        m = re.match(r'^  ([A-Za-z0-9_-]+):\s*$', line)
        if m: cur = m.group(1); out[cur] = []; continue
        if cur: out[cur].append(line)
    return out


def top_permissions(text):
    m = re.search(r'^permissions:(.*)\n((?:[ \t]+.*\n)*)', text, re.M)
    return (m.group(1) + m.group(2)) if m else ''


def problems(name, text):
    """Why a workflow breaks the lock, as plain sentences ([] = fine)."""
    out = []
    if re.search(r'id-token:\s*write', top_permissions(text)):
        out.append(f'{name}: id-token: write is given to every job (move it to the jobs in the production environment)')
    for job, lines in jobs(text).items():
        body = '\n'.join(lines)
        env = re.search(r'^    environment:\s*(\{[^}]*name:\s*)?["\']?([A-Za-z0-9_-]+)', body, re.M)
        in_prod = bool(env and env.group(2) == 'production')
        cond = re.search(r'^    if:\s*(.*)$', body, re.M)
        on_main = bool(cond and "github.ref == 'refs/heads/main'" in cond.group(1))
        token = bool(re.search(r'^\s+id-token:\s*write|^    permissions:.*id-token:\s*write', body, re.M))
        if AZURE.search(body):
            if not in_prod: out.append(f'{name}: job {job} signs in to Azure or deploys outside the production environment')
            if not on_main: out.append(f"{name}: job {job} signs in to Azure without checking it runs on main (github.ref == 'refs/heads/main')")
            if not token: out.append(f'{name}: job {job} signs in to Azure but has no id-token: write of its own')
        elif token:
            out.append(f'{name}: job {job} gets id-token: write but does not deploy')
        if token and not in_prod:
            out.append(f'{name}: job {job} gets id-token: write outside the production environment')
    return out


files = sorted(WF.glob('*.yml')) + sorted(WF.glob('*.yaml'))
names = {f.name for f in files}
t('the workflows are in .github/workflows: test and deploy, Go live, the restore drill', {'deploy.yml', 'promote.yml', 'restore-drill.yml'} <= names)
t('the deploy/github copies are retired (workflows change in pull requests like any other file)', not (ROOT / 'deploy' / 'github').exists())

found = []
for f in files: found += problems(f.name, f.read_text(encoding='utf-8'))
for p in found: print('  ' + p)
t('every job that signs in to Azure or deploys runs in the production environment, on main, with its own id-token', not found)

deploy = (WF / 'deploy.yml').read_text(encoding='utf-8')
dj = jobs(deploy)
t('test and deploy: the deploy job is in production and needs the tested image', 'deploy' in dj and 'needs: test-image' in '\n'.join(dj['deploy'])
  and not problems('deploy.yml', deploy))
t('…the pull request jobs (tests, CHANGELOG check) never sign in and get no id-token',
  all(not AZURE.search('\n'.join(dj[j])) and 'id-token' not in '\n'.join(dj[j]) for j in ('test-image', 'changelog')))
t('…the deploy job never runs for a pull request', "github.event_name != 'pull_request'" in '\n'.join(dj['deploy']))

# The check itself catches what it is for (examples it must refuse)
BAD = {
    'no environment': "permissions:\n  contents: read\njobs:\n  ship:\n    if: ${{ github.ref == 'refs/heads/main' }}\n    permissions:\n      id-token: write\n    steps:\n      - uses: azure/login@v3\n",
    'id-token for all': "permissions:\n  id-token: write\n  contents: read\njobs:\n  ship:\n    if: ${{ github.ref == 'refs/heads/main' }}\n    environment: production\n    steps:\n      - run: az containerapp update -n x\n",
    'no main check': "permissions:\n  contents: read\njobs:\n  ship:\n    environment: production\n    permissions:\n      id-token: write\n    steps:\n      - run: bash deploy/promote.sh promote\n",
    'other environment': "jobs:\n  ship:\n    if: ${{ github.ref == 'refs/heads/main' }}\n    environment: staging\n    permissions:\n      id-token: write\n    steps:\n      - uses: azure/login@v3\n",
    'token for tests': "jobs:\n  test:\n    permissions:\n      id-token: write\n    steps:\n      - run: python3 tests/run_tests.py\n",
}
t('the check refuses a deploy job outside production, id-token for every job, no main check, another environment, a token for tests',
  all(problems(k, v) for k, v in BAD.items()))
GOOD = ("permissions:\n  contents: read\njobs:\n  test:\n    steps:\n      - run: echo ok\n  ship:\n    if: ${{ github.ref == 'refs/heads/main' }}\n"
        "    environment: production\n    permissions:\n      id-token: write\n      contents: read\n    steps:\n      - uses: azure/login@v3\n")
t('…and accepts the shape the workflows use', problems('good', GOOD) == [])

# Azure's side (deploy/azure-setup.ps1 -Step github): sign-in records for the production environment, the older main-branch record kept
# until -RemoveBranchSignIn, which never removes it while no production record exists.
setup = (ROOT / 'deploy' / 'azure-setup.ps1').read_text(encoding='utf-8')
gh = setup.split("if (Want 'github')", 1)[1].split('\nif (Want ', 1)[0]
t('setup: -Step github adds the production environment sign-in record (name and ID forms) alongside the main-branch one',
  '"repo:${GitHubRepo}:environment:production"' in gh and "'github-production-ids', $GitHubSubject" in gh and '"repo:${GitHubRepo}:ref:refs/heads/main"' in gh)
t('setup: -RemoveBranchSignIn is remembered, removes only the main-branch record, and refuses while no production record exists',
  '[switch]$RemoveBranchSignIn' in setup and "Set-Prop $State 'githubBranchSignInRemoved' $true" in gh
  and "-like '*:environment:production'" in gh and "-like '*:ref:refs/heads/main'" in gh
  and gh.index("-like '*:environment:production'") < gh.index('federated-credential delete'))
