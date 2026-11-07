"""Existing FPS operation extracted from widgets. Invoke only in a worker."""
from ui_text import tr
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

def change_fps(fps):
    import winreg
    if fps is not None and (type(fps) is not int or not 1 <= fps <= 240):
        raise ValueError(tr('ui_51483ebeea8a'))
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'roblox\\DefaultIcon') as key:
        icon = winreg.QueryValueEx(key, '')[0]
    folder = Path(os.path.expandvars(icon.rsplit(',', 1)[0].strip().strip('"'))).parent
    if not folder.name.lower().startswith('version-') or not (folder / 'RobloxPlayerBeta.exe').is_file():
        raise ValueError(tr('ui_a5f54c711d2a'))
    target = folder / 'ClientSettings' / 'ClientAppSettings.json'
    settings = json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError(tr('ui_6000e7352080'))
    name = 'DFIntTaskSchedulerTargetFps'
    if fps is None:
        settings.pop(name, None)
    else:
        settings[name] = fps
    target.parent.mkdir(exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile('w', encoding='utf-8', dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(settings, output, indent=2)
        temporary.replace(target)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return tr('ui_863b91e37134') if fps is None else tr('ui_3c5cb105dd98', p0=fps)
