"""Security detectors: what must be caught, and ordinary text that must NOT be flagged."""
import _util
from _util import t
import app, rules_engine as R

cases = [
    ('secret: Anthropic key', 'sk-ant-api03-' + 'A' * 40, R.find_secrets, True),
    ('secret: OpenAI project key', 'key is sk-proj-' + 'b' * 48, R.find_secrets, True),
    ('secret: password assignment', 'password: Hunter2024!', R.find_secrets, True),
    ('secret: private key', '-----BEGIN RSA PRIVATE KEY-----', R.find_secrets, True),
    ('ok: talking about keys', 'The API key is stored in .env, never in chat.', R.find_secrets, False),
    ('ok: password as a word', 'My password policy is 14 characters minimum.', R.find_secrets, False),
    ('ok: SECRET_KEY setting name', 'Set SECRET_KEY in settings.py', R.find_secrets, False),
    ('marking: OFFICIAL-SENSITIVE header', 'OFFICIAL-SENSITIVE: COMMERCIAL\nFife Council bid', R.find_markings, True),
    ('marking: SECRET line', 'SECRET\nOperation details', R.find_markings, True),
    ('marking: SECRET UK EYES ONLY', 'Classification: SECRET UK EYES ONLY', R.find_markings, True),
    ('ok: lower-case prose', 'This is official sensitive stuff, keep it secret', R.find_markings, False),
    ('ok: OFFICIAL alone', 'OFFICIAL\nRoutine memo', R.find_markings, False),
    ('ok: SECRET_KEY', 'SECRET_KEY=abc', R.find_markings, False),
    ('pii: test card number', 'card 4111 1111 1111 1111', R.find_pii, True),
    ('pii: NI number', 'NI: AB 12 34 56 C', R.find_pii, True),
    ('pii: sort code + account', 'Sort code 12-34-56 account 12345678', R.find_pii, True),
    ('ok: date near an order reference', 'Meeting 30-09-26, ref 20260930 confirmed', R.find_pii, False),
    ('ok: phone number', 'Call 07700 900123', R.find_pii, False),
    ('ok: 16 digits failing the card check', 'Order 1234 5678 9012 3456', R.find_pii, False),
    ('ok: all zeros', '0000 0000 0000 0000', R.find_pii, False),
]
for label, text, fn, expect in cases:
    t(label, bool(fn(text)) == expect)
t('Anthropic key not also labelled as OpenAI', R.find_secrets('sk-ant-api03-' + 'A' * 40) == ['Anthropic API key'])
