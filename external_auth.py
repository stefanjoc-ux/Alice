"""Microsoft Entra ID sign-in for Alice's EXTERNAL MCP endpoint (Microsoft 365 Copilot; later Claude web/mobile).

Every request must carry an Entra access token for the Alice API app, issued by the configured tenant to an
allowed user, through an allowed client app, with the required delegated scope. Anything else gets 401.
The internal endpoint (port 8001, web chat) is unchanged and must never be exposed publicly.

Settings (names only; values live in .env, never in code or git):
  ALICE_EXT_TENANT_ID       Directory (tenant) ID of the Tuduma tenant
  ALICE_EXT_APP_ID          Application (client) ID of the Alice API app registration
  ALICE_EXT_APP_ID_URI      Optional; defaults to api://<ALICE_EXT_APP_ID>
  ALICE_EXT_AUDIENCES       Optional; more Application ID URIs accepted as the token audience, comma separated (e.g. the one
                            Microsoft 365 Copilot's Entra SSO registration gives: tokens from Copilot are issued to it)
  ALICE_EXT_SCOPE           Optional; delegated scope required, default access_as_user
  ALICE_EXT_ALLOWED_USERS   Object IDs (oid) of the users allowed in, comma separated
  ALICE_EXT_CALLERS         Client apps allowed to call, as  <client app id>=<label>:<provider>  separated by ';'
                            e.g. 1111...=Microsoft Copilot:copilot . provider is used by the Provider allow-list.
  ALICE_EXT_BASE_URL        Public https URL of the endpoint (e.g. https://alice.example.com)
  ALICE_EXT_HOST / _PORT    Bind address, default 127.0.0.1:8002 (put a TLS reverse proxy in front)
  ALICE_EXT_ALLOWED_HOSTS   Optional; Host headers accepted (defaults to the BASE_URL host plus localhost)

Claude connector (optional; all three or none). Claude's custom connectors cannot complete an Entra sign-in directly, so
Alice runs a small OAuth server in front of Entra (FastMCP's OAuth proxy): Claude signs in with Alice, Alice sends the
person to Entra, and every token is then checked exactly as above (tenant, allowed user, scope, this connector's app).
  ALICE_EXT_CONNECTOR_CLIENT_ID  Application (client) ID of the "Alice connector sign-in" app registration
  ALICE_EXT_CONNECTOR_SECRET     Its client secret (Key Vault)
  ALICE_EXT_CONNECTOR_KEY        Random key (32+ characters) that signs Alice's own tokens and encrypts stored sign-ins (Key Vault)
  ALICE_EXT_CONNECTOR_LABEL      Optional; shown on proposals, default Claude
  ALICE_EXT_CONNECTOR_REDIRECTS  Optional; client callback addresses allowed, comma separated (default: Claude's)
  ALICE_EXT_CONNECTOR_STORE      Optional; folder for the encrypted sign-in records (default <data folder>/oauth-connector)
"""
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from fastmcp.server.auth.providers.jwt import JWTVerifier

GUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
PROVIDER = re.compile(r'^[a-z][a-z0-9_-]{1,30}$')
CLOCK_SKEW = 120          # seconds allowed for clock differences on nbf/iat
CLAUDE_CALLBACK = 'https://claude.ai/api/mcp/auth_callback'     # the hosted Claude apps: web, Desktop, mobile, Cowork


@dataclass(frozen=True)
class Caller:
    label: str            # shown on proposals: [via <label>]
    provider: str         # used by the Provider allow-list (e.g. 'copilot', 'claude')


@dataclass
class Config:
    tenant_id: str
    app_id: str
    app_id_uri: str
    scope: str
    allowed_users: frozenset
    callers: dict = field(default_factory=dict)      # client app id -> Caller
    base_url: str = ''
    host: str = '127.0.0.1'
    port: int = 8002
    allowed_hosts: tuple = ()
    connector_client_id: str = ''      # empty = no Claude connector, only direct Entra tokens (Copilot)
    connector_secret: str = field(default='', repr=False)
    connector_key: str = field(default='', repr=False)
    connector_redirects: tuple = ()
    connector_store: str = ''
    extra_audiences: tuple = ()

    @property
    def issuers(self):     # v2.0 and v1.0 access tokens for this tenant only
        return [f'https://login.microsoftonline.com/{self.tenant_id}/v2.0', f'https://sts.windows.net/{self.tenant_id}/']

    @property
    def audiences(self):
        return list(dict.fromkeys([self.app_id, self.app_id_uri, *self.extra_audiences]))

    @property
    def jwks_uri(self):
        return f'https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys'


def parse_callers(text):
    out = {}
    for part in (text or '').split(';'):
        part = part.strip()
        if not part: continue
        if '=' not in part or ':' not in part.split('=', 1)[1]:
            raise ValueError(f'ALICE_EXT_CALLERS entry "{part[:60]}" should look like <client app id>=<label>:<provider>.')
        app, rest = part.split('=', 1)
        label, provider = rest.rsplit(':', 1)
        app, label, provider = app.strip().lower(), ' '.join(label.split())[:40], provider.strip().lower()
        if not GUID.match(app): raise ValueError(f'ALICE_EXT_CALLERS: "{app}" is not a client app ID (GUID).')
        if not label or not PROVIDER.match(provider): raise ValueError(f'ALICE_EXT_CALLERS: give a label and a provider for {app}.')
        out[app] = Caller(label, provider)
    return out


def load_config(env):
    """Read and check the settings. Refuses to start with anything missing or malformed."""
    g = lambda k, d='': (env.get(k) or d).strip()
    missing = [k for k in ('ALICE_EXT_TENANT_ID', 'ALICE_EXT_APP_ID', 'ALICE_EXT_ALLOWED_USERS', 'ALICE_EXT_CALLERS', 'ALICE_EXT_BASE_URL') if not g(k)]
    if missing: raise ValueError('The external endpoint is not configured. Set in .env: ' + ', '.join(missing) + '.')
    tenant, app = g('ALICE_EXT_TENANT_ID').lower(), g('ALICE_EXT_APP_ID').lower()
    for name, v in (('ALICE_EXT_TENANT_ID', tenant), ('ALICE_EXT_APP_ID', app)):
        if not GUID.match(v): raise ValueError(f'{name} must be a GUID.')
    if tenant in ('common', 'organizations', 'consumers'): raise ValueError('Use your own tenant ID, not a multi-tenant alias.')
    users = frozenset(u.strip().lower() for u in g('ALICE_EXT_ALLOWED_USERS').split(',') if u.strip())
    bad = [u for u in users if not GUID.match(u)]
    if bad or not users: raise ValueError('ALICE_EXT_ALLOWED_USERS must be user object IDs (GUIDs), comma separated.')
    base = g('ALICE_EXT_BASE_URL').rstrip('/')
    u = urlparse(base)
    local = u.hostname in ('127.0.0.1', 'localhost')
    if u.scheme != 'https' and not (u.scheme == 'http' and local):
        raise ValueError('ALICE_EXT_BASE_URL must be https (http only for localhost testing).')
    hosts = tuple(h.strip() for h in g('ALICE_EXT_ALLOWED_HOSTS').split(',') if h.strip()) or \
        tuple(dict.fromkeys([u.hostname or '', '127.0.0.1', 'localhost']))
    callers = parse_callers(g('ALICE_EXT_CALLERS'))
    import rules_engine
    unknown = sorted({c.provider for c in callers.values()} - set(rules_engine.PROVIDERS))
    if unknown: raise ValueError('ALICE_EXT_CALLERS: unknown provider ' + ', '.join(unknown) + ' (use one of ' + ', '.join(rules_engine.PROVIDERS) + ').')
    port = g('ALICE_EXT_PORT', '8002')
    if not port.isdigit() or not 1 <= int(port) <= 65535: raise ValueError('ALICE_EXT_PORT must be a port number.')
    host = g('ALICE_EXT_HOST', '127.0.0.1')
    cid, secret, key = g('ALICE_EXT_CONNECTOR_CLIENT_ID').lower(), g('ALICE_EXT_CONNECTOR_SECRET'), g('ALICE_EXT_CONNECTOR_KEY')
    redirects, store = (), ''
    if cid or secret or key:
        if not (cid and secret and key):
            raise ValueError('Claude connector: set all of ALICE_EXT_CONNECTOR_CLIENT_ID, ALICE_EXT_CONNECTOR_SECRET and ALICE_EXT_CONNECTOR_KEY, or none.')
        if not GUID.match(cid): raise ValueError('ALICE_EXT_CONNECTOR_CLIENT_ID must be a GUID.')
        if cid == app: raise ValueError('The connector needs its own app registration, not the Alice API app.')
        if len(key) < 32: raise ValueError('ALICE_EXT_CONNECTOR_KEY must be at least 32 characters.')
        redirects = tuple(r.strip() for r in g('ALICE_EXT_CONNECTOR_REDIRECTS', CLAUDE_CALLBACK).split(',') if r.strip())
        for r in redirects:
            ru = urlparse(r)
            if not (ru.scheme == 'https' or (ru.scheme == 'http' and ru.hostname in ('127.0.0.1', 'localhost'))):
                raise ValueError(f'ALICE_EXT_CONNECTOR_REDIRECTS: "{r[:80]}" must be https (or a localhost address).')
        label = ' '.join(g('ALICE_EXT_CONNECTOR_LABEL', 'Claude').split())[:40] or 'Claude'
        callers.setdefault(cid, Caller(label, 'claude'))
        import os
        store = g('ALICE_EXT_CONNECTOR_STORE') or os.path.join(env.get('AISUBSTRATE_DATA_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'), 'oauth-connector')
    extra = tuple(dict.fromkeys(a.strip() for a in g('ALICE_EXT_AUDIENCES').split(',') if a.strip()))
    for a in extra:
        if not (a.startswith('api://') or GUID.match(a.lower())) or len(a) > 300 or re.search(r'[\s"<>]', a):
            raise ValueError(f'ALICE_EXT_AUDIENCES: "{a[:80]}" should be an Application ID URI (api://...).')
    return Config(tenant, app, g('ALICE_EXT_APP_ID_URI') or f'api://{app}', g('ALICE_EXT_SCOPE', 'access_as_user'),
                  users, callers, base, host, int(port), hosts, cid, secret, key, redirects, store, extra)


def _log(detail):
    try:
        import rules_engine
        rules_engine.log_block('external_auth', 'External endpoint', detail[:500])
    except Exception:
        pass


class EntraVerifier(JWTVerifier):
    """JWT checks (signature via the tenant's published keys, issuer, audience, expiry, scope) plus Alice's own:
    tenant ID, a delegated user token, an allowed user and an allowed client app."""

    def __init__(self, cfg, public_key=None):
        kw = {'public_key': public_key} if public_key else {'jwks_uri': cfg.jwks_uri}
        super().__init__(issuer=cfg.issuers, audience=cfg.audiences, algorithm='RS256', required_scopes=[cfg.scope],
                         base_url=cfg.base_url or None, **kw)
        self.cfg = cfg

    def check_claims(self, c):
        """Reason the (signature-checked) claims are not acceptable, or ''."""
        now = time.time()
        if not isinstance(c.get('exp'), (int, float)): return 'token has no expiry'
        if c['exp'] < now: return 'token expired'
        if isinstance(c.get('nbf'), (int, float)) and c['nbf'] > now + CLOCK_SKEW: return 'token not yet valid'
        if str(c.get('tid', '')).lower() != self.cfg.tenant_id: return 'wrong tenant'
        if not c.get('scp'): return 'not a delegated user token (no scp claim)'
        oid = str(c.get('oid', '')).lower()
        if oid not in self.cfg.allowed_users: return f'user {oid or "(none)"} is not allowed'
        app = str(c.get('azp') or c.get('appid') or '').lower()
        if app not in self.cfg.callers: return f'client app {app or "(none)"} is not in ALICE_EXT_CALLERS'
        return ''

    async def load_access_token(self, token):
        at = await super().load_access_token(token)
        if at is None:
            _log('Token rejected: invalid signature, issuer, audience, expiry or scope.')
            return None
        reason = self.check_claims(at.claims)
        if reason:
            _log('Token rejected: ' + reason + '.')
            return None
        return at

    def caller(self, claims):
        return self.cfg.callers[str(claims.get('azp') or claims.get('appid') or '').lower()]


def connector_store(cfg):
    """Where the proxy keeps client registrations and sign-ins: a folder on Alice's persistent share, every record
    encrypted with a key derived from ALICE_EXT_CONNECTOR_KEY (records it cannot decrypt are treated as absent)."""
    import os
    from cryptography.fernet import Fernet
    from key_value.aio.stores.filetree import FileTreeStore, FileTreeV1CollectionSanitizationStrategy, FileTreeV1KeySanitizationStrategy
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
    from fastmcp.server.auth.jwt_issuer import derive_jwt_key
    os.makedirs(cfg.connector_store, exist_ok=True)
    try: os.chmod(cfg.connector_store, 0o700)
    except OSError: pass
    from pathlib import Path
    root = Path(cfg.connector_store)
    files = FileTreeStore(data_directory=root, key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(root),
                          collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(root))
    fkey = derive_jwt_key(high_entropy_material=cfg.connector_key, salt='alice-connector-storage')
    return FernetEncryptionWrapper(key_value=files, fernet=Fernet(key=fkey), raise_on_decryption_error=False)


def connector_proxy(verifier):
    """Alice's own OAuth server for Claude (FastMCP's OAuth proxy to Entra). Claude identifies itself with its published
    Client ID Metadata Document (or registers), may only return to the allowed callback addresses, sees a consent page,
    and is sent to Entra with Alice's connector app. The Entra token that comes back is checked by Alice's EntraVerifier,
    so the same tenant, user, scope and caller rules apply as for direct tokens."""
    from fastmcp.server.auth.providers.azure import AzureProvider
    cfg = verifier.cfg
    proxy = AzureProvider(client_id=cfg.connector_client_id, client_secret=cfg.connector_secret, tenant_id=cfg.tenant_id,
                          identifier_uri=cfg.app_id_uri, required_scopes=[cfg.scope], base_url=cfg.base_url,
                          allowed_client_redirect_uris=list(cfg.connector_redirects), client_storage=connector_store(cfg),
                          jwt_signing_key=cfg.connector_key, require_authorization_consent=True,
                          forward_resource=False,           # Entra rejects a resource it does not own (AADSTS9010010)
                          enable_cimd=True)
    proxy._token_validator = verifier                       # Alice's checks, not the library's looser ones
    return proxy


def auth_provider(verifier):
    """The verifier plus standard protected-resource metadata, so MCP clients can discover that Alice signs in
    with the Tuduma tenant's Entra ID and which scope to ask for."""
    from fastmcp.server.auth import RemoteAuthProvider
    cfg = verifier.cfg
    full_scope = f'{cfg.app_id_uri}/{cfg.scope}'
    if cfg.connector_client_id:      # Claude signs in through Alice; direct Entra tokens (Copilot) are still accepted
        from fastmcp.server.auth import MultiAuth
        return MultiAuth(server=connector_proxy(verifier), verifiers=[verifier])
    return RemoteAuthProvider(token_verifier=verifier, authorization_servers=[cfg.issuers[0]], base_url=cfg.base_url,
                              scopes_supported=[full_scope], challenge_scopes=[full_scope], resource_name='Alice')
