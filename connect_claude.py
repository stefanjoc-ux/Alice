"""Connect Claude Desktop to AI Substrate as the "alice" connector (local, via MCP over stdio).

Run:  .venv\\Scripts\\python.exe connect_claude.py          (adds or updates the 'ai-substrate' entry)
      .venv\\Scripts\\python.exe connect_claude.py --remove (removes it)
Backs up your existing Claude Desktop config first. Restart Claude Desktop afterwards.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCRIPTS = BASE / '.venv' / 'Scripts'
PYTHON = SCRIPTS / 'python.exe' if (SCRIPTS / 'python.exe').is_file() else Path(sys.executable)
NAME = 'alice'
LEGACY_NAMES = ('ai-substrate',)   # earlier connector name, replaced on connect


def config_paths():
    """Standard install and Microsoft Store install locations."""
    paths = []
    if os.environ.get('APPDATA'):
        paths.append(Path(os.environ['APPDATA']) / 'Claude' / 'claude_desktop_config.json')
    packages = Path(os.environ.get('LOCALAPPDATA', '')) / 'Packages'
    if packages.is_dir():
        for pkg in packages.glob('Claude_*'):
            paths.append(pkg / 'LocalCache' / 'Roaming' / 'Claude' / 'claude_desktop_config.json')
    return paths


def entry():
    return {'command': str(PYTHON),
            'args': [str(BASE / 'mcp_server.py'), '--stdio', '--client', 'Claude Desktop']}


def update(path, remove=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {}
    if path.is_file():
        text = path.read_text(encoding='utf-8').strip()
        if text:
            try:
                config = json.loads(text)
            except json.JSONDecodeError:
                raise SystemExit(f'{path} is not valid JSON. Fix or rename it, then run this again.')
        shutil.copy2(path, path.with_name(f'claude_desktop_config.backup-{time.strftime("%Y%m%d-%H%M%S")}.json'))
    servers = config.setdefault('mcpServers', {})
    for old in LEGACY_NAMES: servers.pop(old, None)
    if remove:
        servers.pop(NAME, None)
    else:
        servers[NAME] = entry()
    path.write_text(json.dumps(config, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    paths = [p for p in config_paths() if p.parent.is_dir()] or config_paths()[:1]
    if not paths:
        raise SystemExit('Could not find where Claude Desktop keeps its settings (APPDATA is not set).')
    for path in paths:
        update(path, args.remove)
        print(('Removed from ' if args.remove else 'Connected in ') + str(path))
    if not args.remove:
        print('\nNext: fully quit Claude Desktop (right-click its tray icon > Quit) and open it again.')
        print('The connector now appears as "alice" in the chat tools menu.\n')
        print('For Claude Code, run these once in a terminal (the first removes the old name, if present):')
        print('  claude mcp remove ai-substrate --scope user')
        print(f'  claude mcp add {NAME} --scope user -- "{PYTHON}" "{BASE / "mcp_server.py"}" --stdio --client "Claude Code"')


if __name__ == '__main__':
    main()
