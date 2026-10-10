"""This deployment's own names, places and platform (decision D-0052: no personal names in the product).

Alice never carries a person's name, email or object ID, an organisation's or tenant's name, a domain or a repository in its code,
prompts, tool descriptions or defaults. They are read here, from configuration:
  1. the environment: ALICE_<KEY> (e.g. ALICE_ORGANISATION, ALICE_TENANT, ALICE_REPO_URL; ALICE_OWNER_NAME for the owner's name);
  2. deployment.json in the data folder (a file of the same shape as config/deployment.json, naming only what it changes);
  3. the shipped defaults in config/deployment.json, which are roles and neutral words ("the owner", "your organisation").
People's own names come from the signed-in user (users.py), never from here. Existing data (a space called "<name>: work") is
data and stays as it is.

platform() says which kind of deployment this is ('azure' or 'pc'), so advice such as backing up before a change says what applies
to the deployment the person is on (backup_advice())."""
import json
import os
from pathlib import Path

SHIPPED = Path(__file__).resolve().with_name('config') / 'deployment.json'
KEYS = ('product', 'owner_name', 'organisation', 'tenant', 'domain', 'repo_url')


def _data_file():
    data = os.environ.get('AISUBSTRATE_DATA_DIR') or str(Path(__file__).resolve().parent / 'data')
    return Path(data) / 'deployment.json'


def _read(path):
    try:
        d = json.loads(Path(path).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def settings():
    """Every setting, the environment first, then the data folder's deployment.json, then the shipped defaults."""
    out = {k: v for k, v in _read(SHIPPED).items() if k in KEYS}
    out.update({k: v for k, v in _read(_data_file()).items() if k in KEYS and isinstance(v, str)})
    for k in KEYS:
        v = os.environ.get('ALICE_' + k.upper())
        if v is not None and v.strip(): out[k] = v.strip()
    return {k: ' '.join(str(out.get(k) or '').split())[:200] for k in KEYS}


def get(key):
    return settings().get(key, '')


def owner_name():
    """What Alice calls the owner: the configured name, else "Owner" (a role, never a person's name in code)."""
    return get('owner_name') or 'Owner'


def organisation():
    return get('organisation') or 'your organisation'


def tenant():
    return get('tenant') or 'your Microsoft 365 tenant'


def repo_url():
    url = get('repo_url').rstrip('/')
    return url if url.startswith('https://') else ''


def platform(env=None):
    """'azure' in Azure Container Apps (or with a PostgreSQL database), else 'pc'."""
    env = os.environ if env is None else env
    return 'azure' if (env.get('CONTAINER_APP_NAME') or env.get('CONTAINER_APP_REVISION') or env.get('ALICE_DATABASE_URL')) else 'pc'


def backup_advice(env=None):
    """What to do about backups before a change that alters stored data, for the deployment this is."""
    if platform(env) == 'azure':
        return ('Nothing to do first: in Azure the database keeps point-in-time backups for 35 days and the nightly off-site copy runs '
                'at 02:00 UK time (see the Backup page); a release can be rolled back with the Go live button.')
    return 'Before updating, stop Alice and copy its data folder somewhere safe.'
