"""Desktop launcher settings: hotkey parsing and window size (the Windows-only parts need a real desktop)."""
import _util
from _util import t
import os, desktop as d

t('default hotkey parses', d.parse_hotkey('Ctrl+Alt+Space') == (0x4003, 0x20))
t('letters, spaces and case', d.parse_hotkey('ctrl + shift + a') == (0x4006, 0x41))
t('function keys', d.parse_hotkey('Win+F12') == (0x4008, 0x7B))
for bad in ('Space', 'Ctrl+Alt', 'Ctrl+Hyper+X'):
    try: d.parse_hotkey(bad); t(f'rejects {bad}', False)
    except ValueError: t(f'rejects {bad}', True)
os.environ['SUBSTRATE_WINDOW_SIZE'] = '1440x740'; t('window size from setting', d.window_size() == (1440, 740))
os.environ['SUBSTRATE_WINDOW_SIZE'] = '1600×900'; t('accepts ×', d.window_size() == (1600, 900))
os.environ['SUBSTRATE_WINDOW_SIZE'] = 'tiny'; t('bad value falls back to default', d.window_size() == (1440, 780))
os.environ['SUBSTRATE_WINDOW_SIZE'] = '300x200'; t('clamped to a usable minimum', d.window_size() == (600, 400))
