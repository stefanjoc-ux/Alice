"""API keys straight from Key Vault while Alice runs, so a key added in the Azure portal (on any device) works within
minutes, with no setup script and no redeploy.

Only for optional keys that Alice can work without (prices, news, notifications). A setting is looked up in this
order: the environment (the PC's .env, or a Key Vault reference set by the setup script), then Key Vault through the
app's own managed identity (Container Apps provides IDENTITY_ENDPOINT and IDENTITY_HEADER; ALICE_KEY_VAULT_URI and
ALICE_IDENTITY_CLIENT_ID come from Bicep). Only names in ALLOWED can be read this way, never anything else in the
vault. Values are cached for 10 minutes, never logged, never returned to a page.
"""
import json
import os
import threading
import time
import urllib.parse
import urllib.request

ALLOWED = {'ALICE_TWELVEDATA_KEY': 'alice-twelvedata-key', 'ALICE_FINNHUB_KEY': 'alice-finnhub-key',
           'ALICE_TEAMS_WEBHOOK_URL': 'alice-teams-webhook-url'}
TTL = 600
_cache = {}
_lock = threading.Lock()
_token = {'value': '', 'until': 0.0}


def available():
    return bool(os.environ.get('ALICE_KEY_VAULT_URI') and os.environ.get('IDENTITY_ENDPOINT') and os.environ.get('IDENTITY_HEADER'))


def _http_json(url, headers, timeout=10):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


HTTP = _http_json            # replaced in tests


def _access_token():
    now = time.time()
    if _token['value'] and now < _token['until'] - 60: return _token['value']
    q = {'resource': 'https://vault.azure.net', 'api-version': '2019-08-01'}
    cid = os.environ.get('ALICE_IDENTITY_CLIENT_ID', '')
    if cid: q['client_id'] = cid
    d = HTTP(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), {'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']})
    _token['value'] = d['access_token']
    _token['until'] = float(d.get('expires_on') or now + 3000)
    return _token['value']


def _from_vault(secret_name):
    vault = os.environ['ALICE_KEY_VAULT_URI'].rstrip('/') + '/'
    d = HTTP(vault + 'secrets/' + secret_name + '?api-version=7.4', {'Authorization': 'Bearer ' + _access_token()})
    return (d.get('value') or '').strip()


def get(env_name):
    """The value of an optional key: the environment first, then Key Vault (cached). '' when not set anywhere."""
    v = (os.environ.get(env_name) or '').strip()
    if v: return v
    if env_name not in ALLOWED or not available(): return ''
    now = time.time()
    with _lock:
        hit = _cache.get(env_name)
        if hit and now - hit[1] < TTL: return hit[0]
    try: v = _from_vault(ALLOWED[env_name])
    except Exception: v = ''           # not in the vault yet (404) or the vault unreachable: treated as not set
    with _lock: _cache[env_name] = (v, now)
    return v


def forget():
    with _lock: _cache.clear()
