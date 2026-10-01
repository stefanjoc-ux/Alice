"""Live check of Alice's external (Entra-signed-in) endpoint, before any Azure hosting.

Uses the Azure CLI as a stand-in for Copilot: it signs you in to the Tuduma tenant, asks Entra for an Alice token,
starts the external endpoint on this PC (localhost:8002, nothing exposed), and checks that:
  1. Alice's sign-in details are published (protected-resource metadata),
  2. a request with no token is refused,
  3. a forged token is refused,
  4. your real token is accepted and a read-only tool works.
Only read-only tools are called. The token itself is never printed or saved.
Run it with Test-External.cmd. Settings come from .env (ALICE_EXT_*); see external_auth.py.
"""
import base64, json, os, shutil, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
from dotenv import load_dotenv
load_dotenv(BASE / '.env')
import external_auth

AZURE_CLI = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''))


def claims_of(token):
    try:
        part = token.split('.')[1]
        return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
    except Exception:
        return {}


def az(*args):
    exe = shutil.which('az') or shutil.which('az.cmd')
    return subprocess.run([exe, *args], capture_output=True, text=True, timeout=180)


def get_token(cfg):
    scope = f'{cfg.app_id_uri}/{cfg.scope}'
    args = ('account', 'get-access-token', '--scope', scope, '--tenant', cfg.tenant_id, '--query', 'accessToken', '-o', 'tsv')
    r = az(*args)
    if r.returncode != 0:
        print('Signing you in to the Tuduma tenant (a browser window opens)...')
        login = az('login', '--tenant', cfg.tenant_id, '--allow-no-subscriptions', '--scope', scope, '--output', 'none')
        if login.returncode != 0:
            print(login.stderr.strip()[-1500:])
            return None
        r = az(*args)
    if r.returncode != 0:
        err = r.stderr.strip()
        print(err[-1500:])
        if 'AADSTS65001' in err:
            print('\nHint: add the Azure CLI as an authorised client app on Alice (Entra -> App registrations -> Alice -> '
                  f'Expose an API -> Add a client application -> {AZURE_CLI}, tick access_as_user).')
        if 'AADSTS50105' in err:
            print('\nHint: assignment is required and you are not assigned. Entra -> Enterprise applications -> Alice -> '
                  'Users and groups -> add yourself.')
        return None
    return r.stdout.strip()


def post(url, token=None):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'alice-check', 'version': '1'}}}).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
        **({'Authorization': 'Bearer ' + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status
    except urllib.error.HTTPError as e: return e.code


def main():
    print('Alice external endpoint: live check\n')
    try:
        cfg = external_auth.load_config(os.environ)
    except ValueError as e:
        print('Settings problem in .env:', e); return 2
    if AZURE_CLI not in cfg.callers:
        print(f'.env: ALICE_EXT_CALLERS must include the Azure CLI for this test, e.g.\n  ALICE_EXT_CALLERS={AZURE_CLI}=Azure CLI test:copilot')
        return 2
    if not (shutil.which('az') or shutil.which('az.cmd')):
        print('Azure CLI not found. Install it with:  winget install Microsoft.AzureCLI  then open a new window and run this again.')
        return 2

    token = get_token(cfg)
    if not token: print('\nCould not get a token; nothing else was tested.'); return 1
    c = claims_of(token)
    print('Token received (not shown). Its claims:')
    print(f"  audience {c.get('aud')} | token version {c.get('ver')} | scope {c.get('scp')} | "
          f"client app {c.get('azp') or c.get('appid')} | your user is {'ALLOWED' if str(c.get('oid', '')).lower() in cfg.allowed_users else 'NOT in ALICE_EXT_ALLOWED_USERS'}\n")

    url = f'http://localhost:{cfg.port}'
    log = open(BASE / 'data' / 'logs' / 'external-check.log', 'w', encoding='utf-8')
    server = subprocess.Popen([sys.executable, 'mcp_server.py', '--external'], stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try: urllib.request.urlopen(url + '/.well-known/oauth-protected-resource/mcp', timeout=1); break
            except urllib.error.HTTPError: break
            except Exception: time.sleep(0.5)
            if server.poll() is not None: break
        if server.poll() is not None:
            log.close(); print('The external endpoint did not start:\n' + (BASE / 'data' / 'logs' / 'external-check.log').read_text(encoding='utf-8')[-1500:]); return 1

        try:
            with urllib.request.urlopen(url + '/.well-known/oauth-protected-resource/mcp', timeout=10) as r: meta = json.load(r)
            check('sign-in details published', cfg.tenant_id in json.dumps(meta), 'protected-resource metadata')
        except Exception as e:
            check('sign-in details published', False, str(e)[:120])
        check('no token: refused', post(url + '/mcp') == 401)
        check('forged token: refused', post(url + '/mcp', 'eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJ4In0.c2ln') == 401)
        status = post(url + '/mcp', token)
        check('your Tuduma token: accepted', status == 200, f'HTTP {status}')
        if status == 200:
            import asyncio
            from fastmcp import Client
            async def call():
                async with Client(url + '/mcp', auth=token) as cl:
                    tools = await cl.list_tools()
                    res = await cl.call_tool('search_records', {'query': ''})
                    return len(tools), res
            try:
                n, res = asyncio.run(call())
                data = getattr(res, 'data', None) or getattr(res, 'structured_content', None) or {}
                count = len(data.get('records', [])) if isinstance(data, dict) else '?'
                check('read-only tool call works', True, f'{n} tools offered; search_records returned {count} memories')
            except Exception as e:
                check('read-only tool call works', False, str(e)[:200])
    finally:
        server.terminate()
        try: server.wait(10)
        except Exception: server.kill()
        log.close()

    ok = all(results)
    print('\n' + ('ALL CHECKS PASSED. Tuduma sign-in works; next is hosting and the Copilot agent.' if ok else
                  'SOME CHECKS FAILED. Refusal reasons are in Command centre -> Activity; send this output to Claude.'))
    print('The test calls appear on the Agents page as "Azure CLI test".')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
