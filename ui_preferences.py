"""UI-only preferences, intentionally separate from account/session/profile files."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import threading

LOCK = threading.Lock()
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

def save(data):
    with LOCK:
        path=location();path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as out:
                temporary=Path(out.name);json.dump(data,out,ensure_ascii=False)
            temporary.replace(path)
        finally:
            if temporary: temporary.unlink(missing_ok=True)
