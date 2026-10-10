"""JSON output from OpenAI's Responses API (10 Oct 2026).

OpenAI refuses (HTTP 400) a request that asks for text.format {"type": "json_object"} unless the INPUT messages contain the
word "json": "Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'".
The instructions do not count. Temple's category and tag housekeeping paused itself on exactly this, because its input is the
memories as data and only its instructions said "Return JSON only".

Every call that asks OpenAI for JSON goes through create() here, never client.responses.create(..., text={'format': ...}) directly
(tests/test_openai_json.py fails the build otherwise): it adds a plain instruction to the input when nothing in it mentions JSON.
"""
import re

INSTRUCTION = 'Reply with one JSON object only, in the shape the instructions give.'
JSON_MODE = {'format': {'type': 'json_object'}}
_WORD = re.compile('json', re.I)


def _texts(inp):
    """Every piece of text in a Responses API input: a string, or a list of messages whose content is a string or content parts."""
    if isinstance(inp, str): yield inp; return
    for m in inp or []:
        if not isinstance(m, dict): continue
        c = m.get('content')
        if isinstance(c, str): yield c
        elif isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and isinstance(p.get('text'), str): yield p['text']


def mentions_json(inp):
    return any(_WORD.search(t) for t in _texts(inp))


def with_json_word(inp):
    """The input, with INSTRUCTION added when no input message mentions JSON (a string gets it after a blank line; a list of
    messages gets it as a last user message). Never changes what was there."""
    if mentions_json(inp): return inp
    if isinstance(inp, str): return (inp + '\n\n' if inp else '') + INSTRUCTION
    return list(inp or []) + [{'role': 'user', 'content': INSTRUCTION}]


def wants_json(kw):
    fmt = ((kw.get('text') or {}).get('format') or {}) if isinstance(kw.get('text'), dict) else {}
    return isinstance(fmt, dict) and fmt.get('type') == 'json_object'


def create(client, json_mode=True, **kw):
    """client.responses.create(**kw), asking for a JSON object (json_mode) with the word the API needs in the input."""
    if json_mode: kw['text'] = {**(kw.get('text') or {}), **JSON_MODE}
    if wants_json(kw): kw['input'] = with_json_word(kw.get('input'))
    return client.responses.create(**kw)
