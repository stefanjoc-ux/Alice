"""The deploy job's image push (deploy/push_image.sh), run here with stand-in `az` and `docker` commands so the pull request's own
CI exercises it without Azure (10 Oct 2026: the #45 release stopped at `az acr login` with "JSON is invalid: Expecting value",
a one-off empty answer from Azure; the same step had passed 30 minutes earlier). The sign-in and the push are retried; a final
failure names the call, pushes nothing and never prints a token."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import gzip, os, shutil, stat, subprocess, tempfile
from pathlib import Path

ROOT = Path(_util.ROOT)
SCRIPT = ROOT / 'deploy' / 'push_image.sh'
BASH = shutil.which('bash')
SHA = '323cec194473449f3fee1dfd39ee5cffcec7f72f'
JWT = 'eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.c2lnbmF0dXJlLWZvci10ZXN0cw'

STUB_AZ = r'''#!/usr/bin/env bash
# Stand-in az: `az acr login` fails the first $AZ_FAILS times as the real one did on 10 Oct 2026
n=$(cat "$STATE/az" 2>/dev/null || echo 0); echo "az $*" >> "$STATE/calls"
if [ "$1 $2" = "acr login" ]; then
  if printf '%s\n' "$@" | grep -q -- '--debug'; then
    echo "DEBUG: Request URL: 'https://$4.azurecr.io/oauth2/exchange'" >&2
    echo "DEBUG: Response status: 200" >&2
    echo "DEBUG: refresh_token=__JWT__" >&2
    echo "DEBUG: Authorization: Bearer __JWT__" >&2
    echo "DEBUG: body __JWT__" >&2
    echo "ERROR: JSON is invalid: Expecting value: line 1 column 1 (char 0)" >&2; exit 1
  fi
  echo $((n+1)) > "$STATE/az"
  if [ "$n" -lt "${AZ_FAILS:-0}" ]; then echo "ERROR: JSON is invalid: Expecting value: line 1 column 1 (char 0)" >&2; exit 1; fi
  echo "Login Succeeded"; exit 0
fi
exit 0
'''.replace('__JWT__', JWT)

STUB_DOCKER = r'''#!/usr/bin/env bash
echo "docker $*" >> "$STATE/calls"
case "$1" in
  load) cat > /dev/null; echo "Loaded image: alice:__SHA__";;
  tag) ;;
  push) n=$(cat "$STATE/push" 2>/dev/null || echo 0); echo $((n+1)) > "$STATE/push"
        if [ "$n" -lt "${PUSH_FAILS:-0}" ]; then echo "error: unexpected status from PUT request: 503" >&2; exit 1; fi
        echo "digest: sha256:0000 size: 1";;
esac
'''.replace('__SHA__', SHA)


def run(az_fails=0, push_fails=0, tries=3, env_extra=None):
    d = Path(tempfile.mkdtemp(prefix='alice-push-'))
    bin_, state = d / 'bin', d / 'state'
    bin_.mkdir(); state.mkdir()
    for name, body in (('az', STUB_AZ), ('docker', STUB_DOCKER)):
        p = bin_ / name
        p.write_text(body, encoding='utf-8')
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    archive = d / 'image.tar.gz'
    with gzip.open(archive, 'wb') as f: f.write(b'not really an image')
    ghenv = d / 'github_env'
    env = {**os.environ, 'PATH': f'{bin_}{os.pathsep}{os.environ.get("PATH", "")}', 'STATE': str(state),
           'ACR': 'exampleacr', 'SHA': SHA, 'AZ_TRIES': str(tries), 'AZ_PAUSE': '0', 'AZ_FAILS': str(az_fails),
           'PUSH_FAILS': str(push_fails), 'GITHUB_ENV': str(ghenv), **(env_extra or {})}
    r = subprocess.run([BASH, str(SCRIPT), str(archive)], env=env, capture_output=True, text=True, timeout=60)
    calls = (state / 'calls').read_text(encoding='utf-8').splitlines() if (state / 'calls').exists() else []
    out = r.stdout + r.stderr
    written = ghenv.read_text(encoding='utf-8') if ghenv.exists() else ''
    shutil.rmtree(d, ignore_errors=True)
    return r.returncode, out, calls, written


if not BASH:
    t('bash is available to run the deploy script (skipped: no bash here)', True)
else:
    t('the script is valid bash', subprocess.run([BASH, '-n', str(SCRIPT)]).returncode == 0)

    code, out, calls, written = run()
    t('a normal release: loads, signs in once, tags and pushes the tested image under its short tag',
      code == 0 and calls == ['docker load', 'az acr login -n exampleacr --only-show-errors',
                              f'docker tag alice:{SHA} exampleacr.azurecr.io/alice:323cec1', 'docker push exampleacr.azurecr.io/alice:323cec1'])
    t('…and hands IMAGE and TAG to the next steps', written == 'IMAGE=exampleacr.azurecr.io/alice:323cec1\nTAG=323cec1\n')

    code, out, calls, written = run(az_fails=2)
    t('the #45 failure: an empty answer from Azure at `az acr login` is tried again and the release goes on',
      code == 0 and sum(c.startswith('az acr login') for c in calls) == 3 and 'docker push exampleacr.azurecr.io/alice:323cec1' in calls
      and 'JSON is invalid' in out and 'try 1 of 3' in out and 'IMAGE=' in written)

    code, out, calls, written = run(az_fails=9)
    t('a sign-in that keeps failing stops the release: nothing is pushed, and the log says which call failed',
      code == 1 and not any(c.startswith('docker push') for c in calls) and not any(c.startswith('docker tag') for c in calls)
      and 'Could not sign in to the registry exampleacr after 3 tries' in out and written == '')
    t('…with the Azure CLI\'s own diagnostics, never a token', 'oauth2/exchange' in out and 'Response status: 200' in out
      and JWT not in out and 'refresh_token' not in out and 'Bearer' not in out)

    code, out, calls, written = run(push_fails=1)
    t('a registry hiccup during the push is tried again', code == 0 and sum(c.startswith('docker push') for c in calls) == 2)

    code, out, calls, written = run(env_extra={'ACR': ''})
    t('no registry name: stops before touching anything', code != 0 and calls == [] and 'ACR' in out)

wf = (ROOT / '.github' / 'workflows' / 'deploy.yml').read_text(encoding='utf-8')
step = wf.split('- name: Push the tested image', 1)[1].split('- name:', 1)[0] if '- name: Push the tested image' in wf else ''
t('the deploy job pushes through deploy/push_image.sh with the registry and the commit', 'bash deploy/push_image.sh image.tar.gz' in step
  and 'ACR: ${{ vars.ACR_NAME }}' in step and 'SHA: ${{ github.sha }}' in step and 'az acr login' not in step)
