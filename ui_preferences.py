"""UI-only preferences, intentionally separate from account/session/profile files."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import threading

LOCK = threading.Lock()
_LAST_SAVED = 0
DEFAULTS = {'theme':'dark','columns':['account','status','age'], 'widths':{},
            'destinations':[], 'minimizeToTray':True, 'onboarded':False, 'compact':True}

def location():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'RejoinDesk' / 'sk-ui.json'

def load():
    try:
        data=json.loads(location().read_text(encoding='utf-8'))
        if not isinstance(data,dict): return dict(DEFAULTS)
        return {**DEFAULTS, **data}
    except (OSError,ValueError): return dict(DEFAULTS)

def save(data, revision=None):
    global _LAST_SAVED
    with LOCK:
        if revision is not None and revision < _LAST_SAVED:return
        path=location();path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as out:
                temporary=Path(out.name);json.dump(data,out,ensure_ascii=False)
            temporary.replace(path)
            if revision is not None:_LAST_SAVED=revision
        finally:
            if temporary: temporary.unlink(missing_ok=True)
