"""Optional API keys read from Key Vault while Alice runs (added in the portal, no redeploy). A stand-in replaces Azure's
identity endpoint and the vault; nothing leaves this machine."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import os
import keyvault as K

for k in ('ALICE_KEY_VAULT_URI', 'IDENTITY_ENDPOINT', 'IDENTITY_HEADER', 'ALICE_TWELVEDATA_KEY'): os.environ.pop(k, None)
CALLS = []
VAULT = {'alice-twelvedata-key': 'td-test-value', 'database-url': 'postgres://not-for-you'}
def fake_http(url, headers, timeout=10):
    CALLS.append(url)
    if url.startswith('http://identity'):
        assert headers.get('X-IDENTITY-HEADER') == 'hdr' and 'client_id=cid-1' in url and 'resource=https%3A%2F%2Fvault.azure.net' in url
        return {'access_token': 'tok', 'expires_on': '9999999999'}
    assert headers.get('Authorization') == 'Bearer tok'
    name = url.split('/secrets/')[1].split('?')[0]
    if name not in VAULT: raise OSError('404 SecretNotFound')
    return {'value': VAULT[name]}
K.HTTP = fake_http

t('on the PC (no vault): not set, nothing called', K.get('ALICE_TWELVEDATA_KEY') == '' and not CALLS)
os.environ.update({'ALICE_KEY_VAULT_URI': 'https://alice-kv.vault.azure.net/', 'IDENTITY_ENDPOINT': 'http://identity/msi/token',
                   'IDENTITY_HEADER': 'hdr', 'ALICE_IDENTITY_CLIENT_ID': 'cid-1'})
t('in Azure: read from the vault with the app\'s own identity', K.get('ALICE_TWELVEDATA_KEY') == 'td-test-value')
n = len(CALLS)
t('cached: no second call within 10 minutes', K.get('ALICE_TWELVEDATA_KEY') == 'td-test-value' and len(CALLS) == n)
os.environ.pop('DATABASE_URL', None); os.environ.pop('ALICE_NOT_ALLOWED', None)
t('only allow-listed names: nothing else in the vault can be read this way', K.get('ALICE_NOT_ALLOWED') == '' and K.get('DATABASE_URL') == ''
  and not any('database-url' in c for c in CALLS))
t('a key not added yet counts as not set', K.get('ALICE_FINNHUB_KEY') == '')
os.environ['ALICE_TWELVEDATA_KEY'] = 'from-env'
t('the environment wins (the PC\'s .env, or a reference set by the setup script)', K.get('ALICE_TWELVEDATA_KEY') == 'from-env')
del os.environ['ALICE_TWELVEDATA_KEY']
import trading
K.forget(); VAULT['alice-twelvedata-key'] = 'rotated'
t('the Trading desk uses it; a changed key is picked up once the cache expires', trading.td_key() == 'rotated')
