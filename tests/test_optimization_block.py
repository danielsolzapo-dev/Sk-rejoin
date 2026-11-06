"""Reversible flags and server separation through the authenticated app API."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request
from unittest.mock import patch

with tempfile.TemporaryDirectory() as temporary:
    os.environ['LOCALAPPDATA'] = temporary
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app
    import optimization as opt
    import server_picker as picker

    folder = Path(temporary) / 'custom-roblox'
    folder.mkdir()
    (folder / 'RobloxPlayerBeta.exe').write_bytes(b'MZ-fixture-not-executed')
    target = folder / 'ClientSettings' / 'ClientAppSettings.json'
    target.parent.mkdir()
    target.write_text(json.dumps({'unrelated': 7, 'DFIntTaskSchedulerTargetFps': 120}))
    opt.apply(str(folder), 10)
    flags = json.loads(target.read_text())
    assert flags['unrelated'] == 7 and flags['DFIntTaskSchedulerTargetFps'] == 10
    opt.apply(str(folder), 15)
    flags = json.loads(target.read_text())
    flags['unrelated'] = 42
    target.write_text(json.dumps(flags))
    opt.restore()
    assert json.loads(target.read_text()) == {'unrelated': 42, 'DFIntTaskSchedulerTargetFps': 120}
    original = target.read_bytes()
    with patch.object(opt.accounts, 'write', side_effect=OSError('fixture write failure')):
        try:
            opt.apply(str(folder))
            raise AssertionError('Write failure ignored')
        except OSError:
            pass
    assert target.read_bytes() == original
    target.write_text('[]')
    try:
        opt.apply(str(folder))
        raise AssertionError('Invalid JSON object accepted')
    except ValueError:
        pass
    assert target.read_text() == '[]'
    target.write_bytes(original)
    app.accounts.accounts = lambda: [{'userId': i, 'username': 'user_' + str(i)} for i in (1, 2, 3)]
    server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    app.PORT = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def request(path, value):
        key = 'X-Heartbeat-Key' if path == '/heartbeat' else 'X-Rejoin-Key'
        token = app.KEY if path == '/heartbeat' else app.ADMIN
        req = urllib.request.Request(f'http://127.0.0.1:{app.PORT}' + path, data=json.dumps(value).encode(), headers={key: token})
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def beat(identity, job):
        value = {'userId': identity, 'placeId': 10, 'jobId': job, 'session': 's' + str(identity), 'readyForBlock': True}
        request('/heartbeat', value)
        app.LIVE[identity]['joined'] -= 11
        return request('/heartbeat', value)

    try:
        assert request('/block-acc', {'enabled': True})['enabled']
        beat(1, '')
        with patch.object(picker, 'candidates', side_effect=AssertionError('Must reject old heartbeat before network')):
            try:
                app.choose_server(2, 10)
                raise AssertionError('Unidentified server admitted')
            except ValueError:
                pass
        beat(1, 'server-A')
        with patch.object(picker, 'candidates', lambda place: ['server-A', 'server-B', 'server-C']):
            assert app.choose_server(2, 10) == 'server-B'
            value = {'userId': 2, 'placeId': 10, 'jobId': 'server-A', 'session': 's2', 'readyForBlock': True}
            assert 'relocate' not in request('/heartbeat', value), 'Wait at least 10 seconds'
            app.LIVE[2]['joined'] -= 11
            assert 'relocate' not in request('/heartbeat', {**value, 'readyForBlock': False}), 'Wait for loaded character'
            reply = request('/heartbeat', value)
            assert reply['relocate']['jobId'] == 'server-B'
            assert 'relocate' not in beat(1, 'server-A'), 'First account must retain its server'
            beat(2, 'server-B')
            assert app.choose_server(3, 10) == 'server-C'
            assert app.public_state()['accounts'][1]['jobId'] == 'server-B'
        with patch.object(picker, 'candidates', lambda place: ['server-A', 'server-B', 'server-C', 'server-D']):
            app.SERVER_TARGETS.clear()
            assert app.choose_server(3, 10, excluded={'server-C'}) == 'server-D', 'Avoid last failed destination'
        from concurrent.futures import ThreadPoolExecutor
        app.SERVER_TARGETS.clear()
        with patch.object(picker, 'candidates', lambda place: ['server-A', 'server-B', 'server-C', 'server-D']):
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = list(pool.map(lambda i: app.choose_server(i, 10), (3, 4)))
            assert set(jobs) == {'server-C', 'server-D'}, 'Concurrent requests must not reserve the same job'
        with patch.object(picker, 'candidates', lambda place: ['server-A']):
            reply = beat(2, 'server-A')
            assert reply.get('retry') is True and 'stop' not in reply, 'Retry without kick when no server is available'
        assert app.public_state()['accounts'][1]['status'].startswith('BLOCK ACC')
        assert not request('/block-acc', {'enabled': False})['enabled']
        assert not app.SERVER_TARGETS
        assert not app.public_state()['accounts'][1]['status'].startswith('BLOCK ACC')
        with patch.object(app.windows, 'running', lambda: set()):
            assert request('/optimization', {'action': 'apply', 'folder': str(folder), 'fps': 10})['applied']
            assert app.accounts.read(app.SETTINGS, {})['economy']
            assert not request('/optimization', {'action': 'restore'})['applied']
        assert json.loads(target.read_text()) == {'unrelated': 42, 'DFIntTaskSchedulerTargetFps': 120}
        fixture = {'data': [{'id': 'server-Z', 'playing': 1, 'maxPlayers': 5}, {'id': 'full', 'playing': 5, 'maxPlayers': 5}], 'nextPageCursor': 'unused'}
        with patch.object(picker, 'urlopen', lambda *args, **kwargs: io.BytesIO(json.dumps(fixture).encode())):
            assert picker.candidates(100) == ['server-Z']
        print('PASS: selective flag backup/restore, repeat apply, failure preservation, authenticated optimization, BLOCK ACC reservations, old heartbeat rejection, collision relocation, delayed loaded rejoin without kick and disable cleanup')
    finally:
        server.shutdown()
        server.server_close()
