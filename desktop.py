"""AI Substrate desktop: tray icon, background servers, app window and start-with-Windows.

Run once:   Install-Desktop.cmd   (installs pystray + pillow, adds Start menu entry, starts it)
Normal use: starts automatically at login, or from the Start menu. No console windows.
Options:    pythonw desktop.py [--no-window] [--startup on|off] [--install]
"""
import argparse
import re
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('AISUBSTRATE_DATA_DIR', str(BASE / 'data')))
LOGS = DATA / 'logs'
PROFILE = DATA / 'desktop-profile'          # own browser profile: own taskbar icon, remembered mic permission
SCRIPTS = BASE / '.venv' / 'Scripts'
PYTHON = SCRIPTS / 'python.exe' if (SCRIPTS / 'python.exe').is_file() else Path(sys.executable)
PYTHONW = SCRIPTS / 'pythonw.exe' if (SCRIPTS / 'pythonw.exe').is_file() else PYTHON
ICON = BASE / 'static' / 'app.ico'
URL = 'http://127.0.0.1:8000/'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'AISubstrate'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
SERVERS = {  # started in this order: chat needs MCP
    'mcp': (8001, [str(PYTHON), 'mcp_server.py']),
    'web': (8000, [str(PYTHON), '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '8000']),
}


def port_open(port, timeout=0.4):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait_for(port, seconds=40):
    end = time.time() + seconds
    while time.time() < end:
        if port_open(port): return True
        time.sleep(0.4)
    return False


class Servers:
    """Starts servers that are not already running. Only stops the ones it started."""

    def __init__(self):
        self.owned = {}
        self.restarts = {}
        self.lock = threading.Lock()
        self.stopping = False

    def start(self, name):
        port, command = SERVERS[name]
        if port_open(port): return 'running'            # e.g. started by Start-AISubstrate.cmd
        LOGS.mkdir(parents=True, exist_ok=True)
        log = open(LOGS / f'{name}.log', 'a', encoding='utf-8', buffering=1)
        log.write(f'\n--- started {time.strftime("%Y-%m-%d %H:%M:%S")} ---\n')
        self.owned[name] = subprocess.Popen(command, cwd=BASE, stdout=log, stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        return 'started' if wait_for(port) else 'failed'

    def start_all(self):
        with self.lock:
            return {name: self.start(name) for name in SERVERS}

    def stop_all(self):
        with self.lock:
            for proc in self.owned.values():
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(8)
                    except subprocess.TimeoutExpired: proc.kill()
            self.owned.clear()

    def restart_all(self):
        self.stop_all()
        for port, _ in SERVERS.values():   # give sockets a moment to free
            end = time.time() + 8
            while port_open(port) and time.time() < end: time.sleep(0.3)
        return self.start_all()

    def watch(self, notify):
        """Restart an owned server that crashes, at most 3 times per session."""
        while not self.stopping:
            time.sleep(10)
            with self.lock:
                crashed = [n for n, p in self.owned.items() if p.poll() is not None]
            for name in crashed:
                if self.stopping: return
                count = self.restarts.get(name, 0)
                if count >= 3:
                    notify(f'The {name} server keeps stopping. See the logs folder.'); self.owned.pop(name, None); continue
                self.restarts[name] = count + 1
                with self.lock:
                    self.owned.pop(name, None)
                    self.start(name)


def browser():
    """Edge or Chrome for a chromeless app window; None falls back to the default browser."""
    candidates = [shutil.which('msedge'), shutil.which('chrome')]
    for root in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LocalAppData')):
        if root:
            candidates += [Path(root) / 'Microsoft/Edge/Application/msedge.exe',
                           Path(root) / 'Google/Chrome/Application/chrome.exe']
    return next((str(c) for c in candidates if c and Path(c).is_file()), None)


def env_setting(name, default):
    """A value from the process environment or .env beside this file."""
    value = os.environ.get(name)
    if value is None:
        env = BASE / '.env'
        if env.is_file():
            for line in env.read_text(encoding='utf-8', errors='ignore').splitlines():
                if line.strip().startswith(name + '='):
                    value = line.split('=', 1)[1].strip().strip('"').strip("'")
    return value or default


def window_size():
    """SUBSTRATE_WINDOW_SIZE, e.g. 1440x780 (width x height). Falls back to 1440x780."""
    m = re.fullmatch(r'\s*(\d{3,5})\s*[xX×,]\s*(\d{3,5})\s*', env_setting('SUBSTRATE_WINDOW_SIZE', '1440x780'))
    w, h = (int(m.group(1)), int(m.group(2))) if m else (1440, 780)
    return max(600, min(w, 7680)), max(400, min(h, 4320))


def _substrate_windows():
    if os.name != 'nt': return []
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value.startswith('AI Substrate'): found.append(hwnd)
        return True
    user32.EnumWindows(callback, 0)
    return found


def fit_new_window(before):
    """Size the newly opened window (Edge may otherwise restore an old size). Keeps it within the screen."""
    if os.name != 'nt': return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    w, h = window_size()
    area = wintypes.RECT()
    if user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0):      # SPI_GETWORKAREA: screen minus taskbar
        w, h = min(w, area.right - area.left), min(h, area.bottom - area.top)
    for _ in range(60):                                                    # wait up to 15 s for it to appear
        time.sleep(0.25)
        new = [hwnd for hwnd in _substrate_windows() if hwnd not in before]
        if new:
            rect = wintypes.RECT()
            user32.GetWindowRect(new[0], ctypes.byref(rect))
            x = max(area.left, min(rect.left, area.right - w))            # nudge back on-screen if needed
            y = max(area.top, min(rect.top, area.bottom - h))
            user32.SetWindowPos(new[0], 0, x, y, w, h, 0x0004 | 0x0010)   # SWP_NOZORDER | SWP_NOACTIVATE
            return


def open_window(path='admin'):          # Alice opens on the Command centre home page
    exe = browser()
    if exe:
        PROFILE.mkdir(parents=True, exist_ok=True)
        before = set(_substrate_windows())
        w, h = window_size()
        # --disable-extensions: the app window only talks to your local substrate, so no browser
        # extension (ad blockers, toolbars) needs to load into it or be able to read your chats.
        subprocess.Popen([exe, f'--app={URL}{path}', f'--user-data-dir={PROFILE}', '--no-first-run',
                          '--no-default-browser-check', '--disable-extensions', f'--window-size={w},{h}'],
                         creationflags=NO_WINDOW)
        threading.Thread(target=fit_new_window, args=(before,), daemon=True).start()
    else:
        webbrowser.open(URL + path)


# ---------------- global hotkey ----------------
MODIFIERS = {'alt': 0x1, 'ctrl': 0x2, 'control': 0x2, 'shift': 0x4, 'win': 0x8}
MOD_NOREPEAT = 0x4000
NAMED_KEYS = {'space': 0x20, 'enter': 0x0D, 'tab': 0x09, 'escape': 0x1B, 'esc': 0x1B, 'home': 0x24, 'end': 0x23,
              'insert': 0x2D, 'pause': 0x13, '`': 0xC0, ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF}


def hotkey_setting():
    """SUBSTRATE_HOTKEY from .env (e.g. Ctrl+Alt+Space); 'off' disables it."""
    return env_setting('SUBSTRATE_HOTKEY', 'Ctrl+Alt+Space')


def parse_hotkey(text):
    """'Ctrl+Alt+Space' -> (modifier flags, virtual-key code). Needs at least one modifier and one key."""
    parts = [p.strip().lower() for p in text.split('+') if p.strip()]
    mods, keys = 0, []
    for p in parts:
        if p in MODIFIERS: mods |= MODIFIERS[p]
        else: keys.append(p)
    if len(keys) != 1: raise ValueError(f'"{text}": use modifiers plus one key, e.g. Ctrl+Alt+Space.')
    if not mods: raise ValueError(f'"{text}": include Ctrl, Alt, Shift or Win.')
    k = keys[0]
    if len(k) == 1 and (k.isalpha() or k.isdigit()): vk = ord(k.upper())
    elif re.fullmatch(r'f([1-9]|1[0-9]|2[0-4])', k): vk = 0x70 + int(k[1:]) - 1
    elif k in NAMED_KEYS: vk = NAMED_KEYS[k]
    else: raise ValueError(f'"{text}": unknown key "{k}".')
    return mods | MOD_NOREPEAT, vk


def focus_window():
    """Bring an open AI Substrate window to the front (restoring it if minimised). True if one was found."""
    if os.name != 'nt': return False
    import ctypes
    user32 = ctypes.windll.user32
    found = _substrate_windows()
    if not found: return False
    hwnd = found[0]
    if user32.IsIconic(hwnd): user32.ShowWindow(hwnd, 9)      # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def hotkey_loop(text, on_press, on_error):
    """Register the hotkey on this thread and wait for presses (Windows only)."""
    if os.name != 'nt' or text.lower() == 'off': return
    try: mods, vk = parse_hotkey(text)
    except ValueError as e: on_error(str(e)); return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, mods, vk):
        on_error(f'{text} is already used by another app. Set SUBSTRATE_HOTKEY in .env to choose another.'); return
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:                   # WM_HOTKEY
                try: on_press()
                except Exception: pass
    finally:
        user32.UnregisterHotKey(None, 1)


def show_substrate():
    if not focus_window(): open_window()


def startup_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
            return True
    except OSError:
        return False


def set_startup(enabled):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, f'"{PYTHONW}" "{BASE / "desktop.py"}"')
        else:
            try: winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError: pass


def start_menu_shortcut():
    """Start menu entry with the app icon, via Windows' own shortcut API."""
    folder = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs'
    link = folder / 'AI Substrate.lnk'
    script = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
              f"$s.TargetPath='{PYTHONW}';$s.Arguments='\"{BASE / 'desktop.py'}\"';"
              f"$s.WorkingDirectory='{BASE}';$s.IconLocation='{ICON}';$s.Description='AI Substrate';$s.Save()")
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                   check=True, creationflags=NO_WINDOW)
    return link


def single_instance():
    """True if this is the only tray instance. Uses a named Windows mutex."""
    if os.name != 'nt': return True
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\AISubstrateDesktop')
    return ctypes.windll.kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS


def run_tray(show_window):
    import pystray
    from PIL import Image
    servers = Servers()
    icon = pystray.Icon('AISubstrate', Image.open(ICON), 'AI Substrate — starting…')
    hotkey = hotkey_setting()

    def notify(message):
        try: icon.notify(message, 'AI Substrate')
        except Exception: pass

    def boot():
        result = servers.start_all()
        ok = all(v in ('started', 'running') for v in result.values())
        icon.title = 'AI Substrate' if ok else 'AI Substrate — a server failed to start'
        if not ok: notify('A server failed to start. Open the logs folder from the tray menu.')
        elif show_window: open_window()
        threading.Thread(target=servers.watch, args=(notify,), daemon=True).start()
        threading.Thread(target=hotkey_loop, args=(hotkey, show_substrate, notify), daemon=True).start()

    def restart(_icon, _item):
        icon.title = 'AI Substrate — restarting…'
        result = servers.restart_all()
        icon.title = 'AI Substrate'
        notify('Servers restarted.' if all(v in ('started', 'running') for v in result.values())
               else 'Restart failed. Check the logs folder.')

    def toggle_startup(_icon, _item):
        set_startup(not startup_enabled())

    def quit_app(_icon, _item):
        servers.stopping = True
        servers.stop_all()
        icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem(f'Open AI Substrate ({hotkey})' if hotkey.lower() != 'off' else 'Open AI Substrate',
                         lambda *_: show_substrate(), default=True),
        pystray.MenuItem('New chat', lambda *_: open_window('?new=1')),
        pystray.MenuItem('Command centre', lambda *_: open_window('admin')),
        pystray.MenuItem('Usage & costs', lambda *_: open_window('admin/usage')),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Restart servers', restart),
        pystray.MenuItem('Start with Windows', toggle_startup, checked=lambda _: startup_enabled()),
        pystray.MenuItem('Open logs folder', lambda *_: (LOGS.mkdir(parents=True, exist_ok=True), os.startfile(LOGS))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit (stops servers)', quit_app),
    )
    threading.Thread(target=boot, daemon=True).start()
    icon.run()


def main():
    parser = argparse.ArgumentParser(description='AI Substrate desktop launcher')
    parser.add_argument('--no-window', action='store_true', help='start in the tray without opening the window')
    parser.add_argument('--startup', choices=['on', 'off'], help='enable or disable start with Windows, then exit')
    parser.add_argument('--install', action='store_true', help='Start menu entry + start with Windows, then launch')
    args = parser.parse_args()
    if args.startup:
        set_startup(args.startup == 'on'); return
    if args.install:
        start_menu_shortcut(); set_startup(True)
        subprocess.Popen([str(PYTHONW), str(BASE / 'desktop.py')], cwd=BASE, creationflags=NO_WINDOW)
        return
    if not single_instance():
        open_window(); return          # already in the tray: just show the window
    run_tray(show_window=not args.no_window)


if __name__ == '__main__':
    main()
