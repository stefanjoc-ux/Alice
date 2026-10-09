"""The pull request check: a change to Alice's code carries its line in CHANGELOG.md (Stefan, 9 Oct 2026).

    python3 deploy/changelog_check.py --base origin/main

Lists the files the pull request changes (git diff against where it branched from the base) and fails when code changed
but CHANGELOG.md did not. Exempt: documentation only (*.md, *.txt, docs/) and tests only (tests/), or both. When
CHANGELOG.md changed it must also read cleanly (changelog.parse: a "## YYYY-MM-DD" heading per day, newest first, and
"- #<number> what changed" one line per pull request). Run by deploy/github/deploy.yml (job changelog) on pull requests.
Stdlib only. Exit codes: 0 fine, 1 refused, 2 git could not list the changes.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = 'CHANGELOG.md'
DOC_SUFFIXES = ('.md', '.txt')
DOC_DIRS = ('docs/',)
TEST_DIRS = ('tests/',)


def kind(path):
    """'changelog', 'docs', 'tests' or 'code' for one changed path (repository-relative, forward slashes)."""
    p = path.strip().replace('\\', '/')
    if p == CHANGELOG: return 'changelog'
    if p.startswith(TEST_DIRS): return 'tests'
    if p.startswith(DOC_DIRS) or p.lower().endswith(DOC_SUFFIXES): return 'docs'
    return 'code'


def decide(files, changelog_text=None):
    """(ok, message) for the list of changed files; changelog_text = CHANGELOG.md as the pull request leaves it."""
    files = [f for f in (x.strip() for x in files) if f]
    kinds = {f: kind(f) for f in files}
    code = sorted(f for f, k in kinds.items() if k == 'code')
    touched = CHANGELOG in kinds
    if touched and changelog_text is not None:
        sys.path.insert(0, ROOT)
        import changelog
        _entries, problems = changelog.parse(changelog_text)
        if problems:
            return False, 'CHANGELOG.md does not read cleanly:\n  ' + '\n  '.join(problems[:10])
    if code and not touched:
        shown = ', '.join(code[:8]) + (f' and {len(code) - 8} more' if len(code) > 8 else '')
        return False, ('This pull request changes code (' + shown + ') but not CHANGELOG.md. Add one line under today\'s date, '
                       'e.g. "- #<pull request number> What changed for Stefan. You need to: … (only when there is a manual step)". '
                       'Documentation-only and test-only changes do not need one.')
    if not files: return True, 'No changed files.'
    if code: return True, f'Code changed ({len(code)} file(s)) and CHANGELOG.md has its entry.'
    return True, 'Documentation or tests only' + (' (CHANGELOG.md updated too)' if touched else '') + ': no change log entry needed.'


def changed_files(base, run=subprocess.run):
    p = run(['git', 'diff', '--name-only', f'{base}...HEAD'], cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0: raise RuntimeError((p.stderr or '').strip()[:300] or 'git diff failed')
    return p.stdout.splitlines()


def main(argv=None):
    ap = argparse.ArgumentParser(description='A code change carries its CHANGELOG.md entry.')
    ap.add_argument('--base', default='origin/main', help='the branch the pull request goes into, as git knows it')
    ap.add_argument('--files', nargs='*', help='the changed files (instead of asking git)')
    a = ap.parse_args(argv)
    try:
        files = a.files if a.files is not None else changed_files(a.base)
    except (RuntimeError, OSError) as e:
        print(f'Could not list the changed files against {a.base}: {e}'); return 2
    text = None
    if CHANGELOG in [f.strip() for f in files]:
        try:
            with open(os.path.join(ROOT, CHANGELOG), encoding='utf-8') as f: text = f.read()
        except OSError:
            text = ''
    ok, message = decide(files, text)
    print(message)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
