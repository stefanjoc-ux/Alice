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

for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY'):
    os.environ[key] = 'test-key-not-real'
os.environ['OPENAI_BASE_URL'] = 'http://127.0.0.1:9/v1'
os.environ['ANTHROPIC_BASE_URL'] = 'http://127.0.0.1:9'
os.environ['SUBSTRATE_HOTKEY'] = 'off'
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
