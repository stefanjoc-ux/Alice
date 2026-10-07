"""What a model provider said when it refused or failed a request, in a form that is safe to keep and show.

Every place that calls OpenAI, Anthropic or xAI uses this instead of the exception's class name, so a run, the activity
log, web.log and the page all carry the provider's own reason (HTTP status and its message, trimmed). Anything that looks
like a key, and any echo of what was sent, is removed first: the result never holds a credential or the request content.
"""
import logging
import re

LOG = logging.getLogger('alice.provider')
NAMES = {'openai': 'OpenAI', 'claude': 'Anthropic', 'anthropic': 'Anthropic', 'grok': 'xAI', 'xai': 'xAI'}
MAX_DETAIL = 220
_KEYLIKE = re.compile(r'(?i)\b(?:sk|sk-ant|sk-proj|xai|key)-[A-Za-z0-9_\-*.]{6,}|\bBearer\s+\S+|\b[A-Za-z0-9_\-]{40,}\b')


def provider_of(error, provider=''):
    """'openai', 'claude' or '' from the hint given, else from the library that raised it."""
    p = (provider or '').lower()
    if p.startswith('claude') or p == 'anthropic': return 'claude'
    if p.startswith('openai'): return 'openai'
    if p in ('grok', 'xai'): return 'grok'
    mod = type(error).__module__ or ''
    return 'claude' if mod.startswith('anthropic') else 'openai' if mod.startswith('openai') else ''


def is_provider_error(error):
    """True for errors raised by the OpenAI or Anthropic libraries (the request reached, or tried to reach, the provider)."""
    return (type(error).__module__ or '').split('.')[0] in ('openai', 'anthropic')


def scrub(text, sent=()):
    """Remove keys, secrets and any echo of what was sent; collapse whitespace; trim."""
    detail = ' '.join(str(text or '').split())
    for s in sent or ():
        for part in {s, *str(s).split('\n')} if s else ():
            part = ' '.join(str(part).split())
            if part and len(part) >= 12 and part in detail: detail = detail.replace(part, '[request]')
    detail = _KEYLIKE.sub('[removed]', detail)
    try:
        import rules_engine
        for _name, pat in rules_engine.SECRET_PATTERNS: detail = re.sub(pat, '[removed]', detail)
    except Exception:
        pass
    return detail if len(detail) <= MAX_DETAIL else detail[:MAX_DETAIL - 3].rstrip() + '…'


def describe(error, provider='', sent=(), what='request'):
    """{provider, name, status, kind, detail, text}: text is one plain sentence, e.g.
    'Anthropic rejected the request (HTTP 400): Your credit balance is too low to access the Anthropic API.'"""
    p = provider_of(error, provider)
    name = NAMES.get(p, 'The AI service')
    status = getattr(error, 'status_code', None)
    kind = type(error).__name__
    body, detail = getattr(error, 'body', None), ''
    if isinstance(body, dict):
        inner = body.get('error', body)
        detail = (inner.get('message') if isinstance(inner, dict) else str(inner)) or ''
    if not detail and is_provider_error(error):
        detail = getattr(error, 'message', '') or ''
        if re.fullmatch(r'Error code: \d+', detail.strip()): detail = ''
    detail = scrub(detail, sent)
    if status and 400 <= status < 500:
        why = {401: f'{name} did not accept the API key', 403: f'{name} refused access for this key or account',
               404: f'{name} says the model or feature is not available to this account',
               429: f'{name} rate limit or credit reached'}.get(status, f'{name} rejected the {what}')
        text = f'{why} (HTTP {status})'
    elif status: text = f'{name} had an error answering the {what} (HTTP {status}); usually temporary'
    elif 'Timeout' in kind: text = f'{name} took too long to answer the {what}'
    elif 'Connection' in kind: text = f'Could not reach {name} for the {what}'
    else: text = f'The {what} to {name} did not complete ({kind})' if p else f'The AI service did not answer ({kind})'
    return {'provider': p, 'name': name, 'status': status, 'kind': kind, 'detail': detail,
            'text': text + (f': {detail}' if detail and detail not in text else '')}


def message(error, provider='', sent=(), what='request', log=''):
    """describe()['text']; with log, also writes one line to web.log (logger alice.provider) without content or keys."""
    d = describe(error, provider, sent, what)
    if log: LOG.warning('%s: %s', log, d['text'])
    return d['text']
