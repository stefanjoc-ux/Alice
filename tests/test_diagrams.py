"""Diagrams in chat: Mermaid and SVG code blocks shown as pictures, safely; the library is served locally."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import app
from fastapi.testclient import TestClient
cl = TestClient(app.app)

r = cl.get('/static/vendor/mermaid-11.17.2.min.js')
t('Mermaid is served locally (no third-party script host)', r.status_code == 200 and 'javascript' in r.headers['content-type'] and len(r.content) > 1_000_000)
t('only listed vendor files are served', cl.get('/static/vendor/other.js').status_code == 404 and cl.get('/static/vendor/..%2Fapp.ico').status_code == 404)
t('icons still served (folder name case handled)', cl.get('/static/favicon.png').status_code == 200)
page = cl.get('/').text
t('the chat page draws mermaid and svg code blocks', 'function diagram(' in page and "lang==='mermaid'" in page)
t('drawings are shown as images, never inserted as live SVG', 'new Image()' in page and 'innerHTML' not in page.split('function diagram(')[1].split('function renderMarkdown')[0])
t('Mermaid runs in strict security mode', "securityLevel:'strict'" in page)
src = open(app.__file__, encoding='utf-8').read()
t('models are told they can draw diagrams', 'in a ```mermaid code block' in src and '```svg code block' in src)
