"""External multi-instance admission and verified bootstrapper downloads."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

with tempfile.TemporaryDirectory() as temporary:
    os.environ['LOCALAPPDATA'] = temporary
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app
    import bootstrapper as tool

    app.accounts.accounts = lambda: [{'userId': 1, 'username': 'first'}, {'userId': 2, 'username': 'second'}]
    app.MULTI_HANDLE = None
    running = {99}
    launches = []
    active = {}

    def launch(name, place, before_open=None):
        assert before_open()
        pid = 100 + len(launches)
        identity = 1 if name == 'first' else 2
        active.update(pid=pid, identity=identity, place=place)
        launches.append(name)
        running.add(pid)

    def compact(*args):
        now = time.monotonic()
        app.LIVE[active['identity']] = {'received': now, 'since': now, 'place': active['place'], 'session': str(active['pid'])}
        return (320, 240)

    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()

    with patch.object(app.threading, 'Thread', InlineThread), patch.object(app.windows, 'running', lambda: running.copy()), \
            patch.object(app.accounts, 'launch', launch), patch.object(app, 'wait_new_pid', lambda before: active['pid']), \
            patch.object(app.windows, 'process_stamp', lambda pid: pid * 10), patch.object(app.windows, 'compact', compact), \
            patch.object(app.QUEUE_CANCEL, 'wait', lambda seconds: False):
        app.start_job({'ids': [1, 2], 'place': 10, 'limit': 9})
    assert launches == ['first', 'second']
    assert len(running) == 3 and app.MULTI_OBSERVED and not app.BUSY and app.WAITING == 0
    assert all(app.STATUS[identity] == 'Online' for identity in (1, 2))

    raw = b'MZ-test-release'
    info = {'version': '2.1.5', 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'url': 'https://github.com/vnnaworks/weblauncher/releases/download/2.1.5/weblauncher.exe'}
    with patch.object(tool, 'release', lambda: info), patch.object(tool, 'urlopen', lambda *a, **k: io.BytesIO(raw)):
        result = tool.download()
    assert result['installed'] and Path(result['path']).read_bytes() == raw
    original = Path(result['path']).read_bytes()
    with patch.object(tool, 'release', lambda: info), patch.object(tool, 'urlopen', lambda *a, **k: io.BytesIO(b'corrupted')):
        try:
            tool.download()
            raise AssertionError('Bad release accepted')
        except ValueError:
            pass
    assert Path(result['path']).read_bytes() == original
    assert not list(tool.TOOLS.glob('**/*.download'))
    asset = {'name': 'weblauncher.exe', 'browser_download_url': info['url'], 'size': len(raw), 'digest': 'sha256:' + info['sha256']}
    valid = {'tag_name': '2.1.5', 'assets': [asset]}
    with patch.object(tool, 'urlopen', lambda *a, **k: io.BytesIO(json.dumps(valid).encode())):
        assert tool.release()['sha256'] == info['sha256']
    for bad in [{**asset, 'browser_download_url': 'https://example.com/weblauncher.exe'}, {**asset, 'digest': None}, {**asset, 'size': True}]:
        with patch.object(tool, 'urlopen', lambda *a, **k: io.BytesIO(json.dumps({'tag_name': '2.1.5', 'assets': [bad]}).encode())):
            try:
                tool.release()
                raise AssertionError('Invalid metadata accepted')
            except ValueError:
                pass
    print('PASS: external multi opens both accounts without reserved mutex; new processes and heartbeat confirmed; bounded verified release download; corrupted download preserves existing executable')
