"""Run Alice's test suites. Safe: never touches your real data or API keys, never calls a real model.

    .venv\\Scripts\\python.exe tests\\run_tests.py              all suites
    .venv\\Scripts\\python.exe tests\\run_tests.py rules import  only suites whose names contain these words

Each suite runs in its own process with its own throwaway data folder. Exit code 0 means everything passed.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass


def main(filters):
    suites = sorted(glob.glob(os.path.join(HERE, 'test_*.py')))
    if filters: suites = [s for s in suites if any(f.lower() in os.path.basename(s).lower() for f in filters)]
    if not suites: print('No matching test suites.'); return 1
    totals = {'pass': 0, 'fail': 0, 'broken': 0}
    started = time.time()
    for suite in suites:
        name = os.path.basename(suite)[5:-3]
        data = tempfile.mkdtemp(prefix='alice-test-')
        env = {**os.environ, 'AISUBSTRATE_DATA_DIR': data, 'PYTHONPATH': ROOT, 'PYTHONIOENCODING': 'utf-8'}
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY'): env[key] = 'test-key-not-real'
        env['OPENAI_BASE_URL'] = 'http://127.0.0.1:9/v1'; env['ANTHROPIC_BASE_URL'] = 'http://127.0.0.1:9'
        t0 = time.time()
        try:
            out = subprocess.run([sys.executable, suite], cwd=ROOT, env=env, capture_output=True, timeout=300)
            text = out.stdout.decode('utf-8', 'replace'); err = out.stderr.decode('utf-8', 'replace'); code = out.returncode
        except subprocess.TimeoutExpired:
            text, err, code = '', 'Timed out after 300 seconds.', -1
        finally:
            shutil.rmtree(data, ignore_errors=True)
        passes = [l for l in text.splitlines() if l.startswith('PASS ')]
        fails = [l for l in text.splitlines() if l.startswith('FAIL ')]
        broken = code != 0
        totals['pass'] += len(passes); totals['fail'] += len(fails); totals['broken'] += broken
        mark = 'OK  ' if not fails and not broken else 'FAIL'
        print(f'{mark} {name:<16} {len(passes):>3} passed' + (f', {len(fails)} failed' if fails else '')
              + (' — crashed' if broken else '') + f'  ({time.time() - t0:.1f}s)')
        for l in fails: print('       ' + l)
        if broken:
            tail = [l for l in err.strip().splitlines() if l.strip()][-6:]
            for l in tail: print('       | ' + l)
    ok = not totals['fail'] and not totals['broken']
    print(f"\n{'All passed' if ok else 'PROBLEMS FOUND'}: {totals['pass']} checks passed, {totals['fail']} failed, "
          f"{totals['broken']} suite(s) crashed, in {time.time() - started:.0f}s.")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
