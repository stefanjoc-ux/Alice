"""Microsoft Entra ID sign-in for Alice's EXTERNAL MCP endpoint (Microsoft 365 Copilot; later Claude web/mobile).

Every request must carry an Entra access token for the Alice API app, issued by the configured tenant to an
allowed user, through an allowed client app, with the required delegated scope. Anything else gets 401.
The internal endpoint (port 8001, web chat) is unchanged and must never be exposed publicly.

Settings (names only; values live in .env, never in code or git):
  ALICE_EXT_TENANT_ID       Directory (tenant) ID of the Tuduma tenant
  ALICE_EXT_APP_ID          Application (client) ID of the Alice API app registration
  ALICE_EXT_APP_ID_URI      Optional; defaults to api://<ALICE_EXT_APP_ID>
  ALICE_EXT_SCOPE           Optional; delegated scope required, default access_as_user
  ALICE_EXT_ALLOWED_USERS   Object IDs (oid) of the users allowed in, comma separated
  ALICE_EXT_CALLERS         Client apps allowed to call, as  <client app id>=<label>:<provider>  separated by ';'
                            e.g. 1111...=Microsoft Copilot:copilot . provider is used by the Provider allow-list.
  ALICE_EXT_BASE_URL        Public https URL of the endpoint (e.g. https://alice.example.com)
  ALICE_EXT_HOST / _PORT    Bind address, default 127.0.0.1:8002 (put a TLS reverse proxy in front)
  ALICE_EXT_ALLOWED_HOSTS   Optional; Host headers accepted (defaults to the BASE_URL host plus localhost)
"""
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from fastmcp.server.auth.providers.jwt import JWTVerifier

GUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
PROVIDER = re.compile(r'^[a-z][a-z0-9_-]{1,30}$')
CLOCK_SKEW = 120          # seconds allowed for clock differences on nbf/iat


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

    @property
    def issuers(self):     # v2.0 and v1.0 access tokens for this tenant only
        return [f'https://login.microsoftonline.com/{self.tenant_id}/v2.0', f'https://sts.windows.net/{self.tenant_id}/']

    @property
    def audiences(self):
        return [self.app_id, self.app_id_uri]

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
    return Config(tenant, app, g('ALICE_EXT_APP_ID_URI') or f'api://{app}', g('ALICE_EXT_SCOPE', 'access_as_user'),
                  users, callers, base, host, int(port), hosts)


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


def auth_provider(verifier):
    """The verifier plus standard protected-resource metadata, so MCP clients can discover that Alice signs in
    with the Tuduma tenant's Entra ID and which scope to ask for."""
    from fastmcp.server.auth import RemoteAuthProvider
    cfg = verifier.cfg
    full_scope = f'{cfg.app_id_uri}/{cfg.scope}'
    return RemoteAuthProvider(token_verifier=verifier, authorization_servers=[cfg.issuers[0]], base_url=cfg.base_url,
                              scopes_supported=[full_scope], challenge_scopes=[full_scope], resource_name='Alice')
