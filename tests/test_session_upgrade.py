"""Profile persistence, targeted recovery and opt-in startup through the real API."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.error import HTTPError

with tempfile.TemporaryDirectory() as temp:
    os.environ['LOCALAPPDATA'] = temp
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app
    import startup
    app.accounts.accounts = lambda: [{'userId': 1, 'username': 'account_one'}, {'userId': 2, 'username': 'account_two'}]
    server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    app.PORT = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    def request(path, data, token=None):
        heartbeat = path == '/heartbeat'
        req = Request(f'http://127.0.0.1:{app.PORT}' + path, data=json.dumps(data).encode(),
                      headers={'X-Heartbeat-Key' if heartbeat else 'X-Rejoin-Key': token or (app.KEY if heartbeat else app.ADMIN)})
        with urlopen(req) as response:
            return json.load(response)
    try:
        profile = {'ids': [1], 'place': 10, 'delay': 60, 'max_attempts': 3, 'width': 400, 'height': 300, 'fps': 12}
        request('/profile', profile)
        request('/rejoin', {'ids': [1], 'place': 10, 'rejoin_delay': 60, 'max_attempts': 3})
        app.save_profiles()
        saved = app.accounts.read(app.PROFILES, {})['1']
        assert saved['width'] == 400 and saved['fps'] == 12
        reply = request('/heartbeat', {'userId': 1, 'placeId': 10, 'session': 's1', 'readyForBlock': True, 'errorCode': 773})
        assert reply['fps'] == 12
        calls = []
        app.BINDINGS[1] = (101, 99)
        with patch.object(app, 'start_job', lambda value, **kw: calls.append(value)):
            app.watch_once()
        assert calls == [{'ids': [1], 'place': 10, 'recover': True}]
        assert app.REJOIN[1]['attempts'] == 1
        with patch.object(app.windows, 'same_process', lambda *a: True):
            assert app.public_state()['accounts'][0]['connection'] == 'Erro 773'
        request('/tracker/state', {}, app.TRACKER_KEY)
        try:
            request('/profile', profile, app.TRACKER_KEY)
            raise AssertionError('Bridge key must not permit arbitrary configuration')
        except HTTPError as error:
            assert error.code == 401
        with patch.object(startup, 'set_enabled') as register:
            request('/startup', {'startWithWindows': True, 'companionEnabled': False, 'companionPath': ''})
            register.assert_called_once_with(True)
        executable = Path(temp) / 'my tool.exe'
        executable.write_bytes(b'MZ-test-not-executed')
        assert startup.executable(str(executable)) == str(executable.resolve())
        with patch.object(startup, 'os', SimpleNamespace(name='nt')), patch.object(app.windows, 'executable_running', return_value=False), patch.object(startup.subprocess, 'Popen') as popen:
            startup.launch({'companionEnabled': True, 'companionPath': str(executable)})
            assert popen.call_args.args[0] == [str(executable.resolve())]
            assert popen.call_args.kwargs['shell'] is False
        with patch.object(startup, 'os', SimpleNamespace(name='nt')), patch.object(app.windows, 'executable_running', return_value=True), patch.object(startup.subprocess, 'Popen') as popen:
            startup.launch({'companionEnabled': True, 'companionPath': str(executable)})
            popen.assert_not_called()
        fake = MagicMock()
        with patch.dict(sys.modules, {'winreg': fake}), patch.object(startup.sys, 'frozen', True, create=True), patch.object(startup.os, 'name', 'nt'):
            startup.set_enabled(True)
            assert fake.SetValueEx.call_args.args[-1] == startup.subprocess.list2cmdline([sys.executable])
            startup.set_enabled(False)
            fake.DeleteValue.assert_called_once()

        # Run real queue logic. Only the selected bound PID may be closed.
        app.LIVE.clear(); app.REJOIN.clear(); app.STATUS.clear()
        app.BINDINGS = {1: (101, 99), 2: (202, 88)}
        active = {101, 202}
        closed, launched = [], []
        def close(pid, stamp):
            closed.append((pid, stamp)); active.remove(pid)
        def launch(name, place, job='', before_open=None):
            assert before_open()
            launched.append((name, place)); active.add(303)
        def compact(*args):
            now = time.monotonic()
            app.LIVE[1] = {'received': now, 'place': 10, 'since': now, 'session': 'new'}
            return (400, 300)
        class Inline:
            def __init__(self, target, **kw): self.target = target
            def start(self): self.target()
        with patch.object(app.threading, 'Thread', Inline), patch.object(app.windows, 'running', lambda: active.copy()), patch.object(app.windows, 'same_process', lambda pid, stamp: pid in active), patch.object(app.windows, 'close_bound', close), patch.object(app.accounts, 'launch', launch), patch.object(app, 'wait_new_pid', lambda before: 303), patch.object(app.windows, 'process_stamp', lambda pid: 77), patch.object(app.windows, 'compact', compact), patch.object(app.QUEUE_CANCEL, 'wait', lambda s: False):
            app.start_job({'ids': [1], 'place': 10, 'recover': True, 'limit': 2})
        assert closed == [(101, 99)] and launched == [('account_one', 10)]
        assert 202 in active and app.BINDINGS[2] == (202, 88)
        assert app.STATUS[1] == 'Online'
        events = []
        class Wait:
            def is_set(self): return False
            def wait(self, seconds): events.append(('wait', seconds)); return False
        settings = {'startupWebLauncher': True, 'companionEnabled': True, 'startupAccounts': True,
                    'startupAccountIds': [1, 2], 'webLauncherDelay': 10, 'executorDelay': 20}
        with patch.object(app.bootstrapper, 'state', return_value={'installed': True, 'path': 'weblauncher.exe'}), patch.object(app.windows, 'executable_running', return_value=False), patch.object(app.bootstrapper, 'open_tool', lambda: events.append('web')), patch.object(startup, 'launch', lambda settings: events.append('executor') or 'opened'):
            startup.sequence(settings, lambda text: None, lambda ids: events.append(('accounts', ids)), Wait())
        assert events == ['web', ('wait', 10), 'executor', ('wait', 20), ('accounts', [1, 2])]
        events.clear()
        with patch.object(app.bootstrapper, 'state', return_value={'installed': False}), patch.object(startup, 'launch', side_effect=AssertionError('Must not start executor after failed WebLauncher')):
            try:
                startup.sequence(settings, lambda text: None, lambda ids: events.append('accounts'), Wait())
                raise AssertionError('Missing WebLauncher accepted')
            except ValueError:
                pass
        assert not events and not startup.SEQUENCE_LOCK.locked()
        class Cancel(Wait):
            def wait(self, seconds): return True
        with patch.object(app.bootstrapper, 'state', return_value={'installed': True, 'path': 'weblauncher.exe'}), patch.object(app.windows, 'executable_running', return_value=True), patch.object(startup, 'launch', side_effect=AssertionError('Must stop after cancellation')):
            startup.sequence(settings, lambda text: None, lambda ids: events.append('accounts'), Cancel())
        assert not events
        print('PASS profiles survive reconnect settings; fresh 773 triggers targeted recovery; bridge key restricted; startup opt-in and quoted command; selected PID closed before instance admission')
    finally:
        server.shutdown()
        server.server_close()
