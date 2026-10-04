"""The Rules page layout: tiles over tabs, every section still on the page (the scripts find them by id)."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import app
from fastapi.testclient import TestClient
h = TestClient(app.app).get('/admin/rules').text
t('tiles and tabs', 'id="rl-tiles"' in h and 'id="rl-tabs"' in h and h.count('class="rl-panel"') == 6)
t('every section the scripts use is still there', all(f'id="{i}"' in h for i in
  ['r-sets', 'r-spend', 'r-packs-list', 'r-packs-svc', 'pv-list', 'rule-form', 'guidance', 'r-effective', 'r-blocks', 'r-requests', 'r-counts', 'rl-q']))
t('only the Rules tab shows before the script runs', h.count('role="tabpanel" hidden') == 5)
