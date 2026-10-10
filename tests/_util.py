"""Shared setup for Alice's tests. Import this FIRST in every test file, before any Alice module.

Guarantees, whether a test is run through run_tests.py or on its own:
- Your real data folder is never used: every run gets a throwaway data folder, deleted afterwards.
- Your real API keys are never used: every provider key is replaced with a dummy, and the OpenAI and
  Anthropic libraries are pointed at a dead local address, so an accidental real call fails instantly.
"""
import atexit
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
os.chdir(ROOT)

_real = os.path.abspath(os.path.join(ROOT, 'data'))
DATA = os.environ.get('AISUBSTRATE_DATA_DIR', '')
if not DATA or os.path.abspath(DATA) == _real or not os.path.basename(DATA).startswith('alice-test-'):
    DATA = tempfile.mkdtemp(prefix='alice-test-')
    os.environ['AISUBSTRATE_DATA_DIR'] = DATA
    atexit.register(shutil.rmtree, DATA, True)

# Database: SQLite in the throwaway folder by default. To run the same suites against PostgreSQL, set
# ALICE_TEST_DATABASE_URL to a TEST server; each run gets its own throwaway schema, dropped afterwards.
# ALICE_DATABASE_URL (the real database) is always ignored here.
os.environ.pop('ALICE_DATABASE_URL', None)
_TEST_PG = os.environ.get('ALICE_TEST_DATABASE_URL', '').strip()
if _TEST_PG:
    import uuid
    import psycopg
    from psycopg.conninfo import make_conninfo
    _SCHEMA = 'alice_test_' + uuid.uuid4().hex[:12]
    with psycopg.connect(_TEST_PG, autocommit=True) as _c:
        _c.execute(f'CREATE SCHEMA {_SCHEMA}')
        _c.execute('CREATE EXTENSION IF NOT EXISTS citext SCHEMA public')
    os.environ['ALICE_DATABASE_URL'] = make_conninfo(_TEST_PG, options=f'-csearch_path={_SCHEMA},public')
    os.environ['ALICE_DEMO_SCHEMA'] = _SCHEMA + '_demo'

    def _drop_schema():
        try:
            import dbcompat; dbcompat.close_pools()
        except Exception: pass
        try:
            with psycopg.connect(_TEST_PG, autocommit=True) as c: c.execute(f'DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE'); c.execute(f'DROP SCHEMA IF EXISTS {_SCHEMA}_demo CASCADE')
        except Exception: pass
    atexit.register(_drop_schema)

for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY'):
    os.environ[key] = 'test-key-not-real'
os.environ['OPENAI_BASE_URL'] = 'http://127.0.0.1:9/v1'
os.environ['ANTHROPIC_BASE_URL'] = 'http://127.0.0.1:9'
os.environ['SUBSTRATE_HOTKEY'] = 'off'
os.environ['ALICE_NO_SCHEDULER'] = '1'   # no background schedules during tests
os.environ['ALICE_NO_RELEASE_RECORD'] = '1'   # CHANGELOG.md is not imported at app start; test_changelog runs it
os.environ['ALICE_TAXONOMY_DEFAULT'] = 'off'      # Temple's category/tag housekeeping; test_taxonomy switches it on
os.environ['ALICE_AUTO_APPROVE_DEFAULT'] = 'off'   # suites test the approval gates; test_autoapprove switches it on
os.environ['ALICE_OPEN_SPACES_DEFAULT'] = 'off'    # team spaces members-only in tests; test_spaces_teams switches the rule on
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import logging
logging.getLogger().setLevel(logging.CRITICAL)   # expected failures inside tests shouldn't flood the output


def t(label, condition):
    """Record one check. The runner counts the PASS and FAIL lines."""
    print(('PASS ' if condition else 'FAIL ') + label, flush=True)
    return bool(condition)


def path(*parts):
    """A path inside this run's throwaway data folder."""
    return os.path.join(DATA, *parts)
