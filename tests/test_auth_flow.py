"""Authentication stages with synthetic sessions; no account or network access."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import accounts as a
cookie = 'fixture-cookie-' * 4
ticket = 'fixture-ticket-123456789/=='
csrf = 'fixture-csrf'
metadata = {'userId': 42, 'username': 'fixture_user'}
with patch.object(a, 'load_session', return_value=(metadata, {'cookie': cookie, 'ua': 'fixture-browser'})), patch.object(a, 'authenticated', return_value=metadata), patch.object(a, 'SUPPORTED', True), patch.object(a, 'open_game') as opened:
    with patch.object(a, 'request_roblox', side_effect=[(403, {'X-CSRF-TOKEN': csrf}, b''), (200, {'rbx-authentication-ticket': ticket}, b'')]) as request:
        assert a.launch('fixture_user', 2753915549)
        assert request.call_count == 2 and request.call_args.kwargs['csrf'] == csrf
        assert opened.call_count == 1
        uri = opened.call_args.args[0]
        assert '+gameinfo:' + ticket + '+launchtime:' in uri
        from urllib.parse import unquote, urlparse, parse_qs
        tracker = uri.split('+browsertrackerid:')[1].split('+')[0]
        destination = unquote(uri.split('+placelauncherurl:')[1].split('+browsertrackerid:')[0])
        assert parse_qs(urlparse(destination).query)['browserTrackerId'] == [tracker]
        assert tracker.isdigit() and tracker != '0'
        assert parse_qs(urlparse(destination).query)['placeId'] == ['2753915549']
        assert a.auth_diagnostics()[0]['handedOff']
    opened.reset_mock()
    with patch.object(a, 'request_roblox', return_value=(403, {}, b'')) as request:
        result = a.check_launch_auth('fixture_user', 2753915549)
        assert not result['ticketIssued'] and result['ticketHTTP'] == 403
        assert request.call_count == 1
    with patch.object(a, 'request_roblox', return_value=(403, {'rblx-challenge-id': 'synthetic', 'x-csrf-token': csrf}, b'')) as request:
        result = a.check_launch_auth('fixture_user', 2753915549)
        assert result['challenge'] and request.call_count == 1
    with patch.object(a, 'request_roblox', return_value=(200, {'rbx-authentication-ticket': ticket}, b'')):
        assert a.check_launch_auth('fixture_user', 2753915549)['ticketIssued']
        try:
            a.launch('fixture_user', 2753915549, before_open=lambda: False)
            raise AssertionError('Cancellation ignored')
        except a.LaunchCancelled:
            pass
    opened.assert_not_called()
    report = json.dumps(a.auth_diagnostics())
    assert all(secret not in report for secret in (cookie, ticket, csrf))
with patch.object(a, 'build_opener') as opener, patch.object(a, 'ProxyHandler', return_value=object()) as proxy_handler:
    response = MagicMock(status=200, headers={})
    response.read.return_value = b'{}'
    opener.return_value.open.return_value.__enter__.return_value = response
    a.request_roblox('ticket', cookie, 'fixture-browser', csrf=csrf, place=123)
    proxy_handler.assert_called_once_with()
    request = opener.return_value.open.call_args.args[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert 'rbxauthenticationnegotiation' not in headers
    assert 'origin' not in headers
    assert headers['content-type'] == 'application/json'
    assert json.loads(request.data) == {}
    assert headers['referer'] == 'https://www.roblox.com/games/123'
    assert headers['x-csrf-token'] == csrf
    assert request.full_url == a.URLS['ticket'] and request.method == 'POST'
print('Authentication flow checks passed (synthetic sessions only).')

with patch.object(a, 'getproxies', return_value={'https': 'http://fixture-user:fixture-password@proxy.invalid:3128'}):
    summary = a.network_diagnostic()
    assert 'detectado: sim' in summary
    assert all(secret not in summary for secret in ('fixture-user', 'fixture-password', 'proxy.invalid'))
with patch.object(a, 'getproxies', return_value={}):
    assert 'detectado: não' in a.network_diagnostic()

# A diagnostic ticket must never be cached or reused for an actual launch.
with patch.object(a, 'load_session', return_value=(metadata, {'cookie': cookie})), patch.object(a, 'authenticated', return_value=metadata), patch.object(a, 'SUPPORTED', True), patch.object(a, 'open_game') as opened:
    with patch.object(a, 'request_roblox', side_effect=[
            (403, {'x-csrf-token': csrf}, b''),
            (200, {'rbx-authentication-ticket': 'diagnostic_fixture_123'}, b''),
            (403, {'x-csrf-token': csrf}, b''),
            (200, {'rbx-authentication-ticket': 'launch_fixture_456'}, b'')]) as request:
        assert a.check_launch_auth('fixture_user', 123)['ticketIssued']
        a.launch('fixture_user', 123)
        assert request.call_count == 4
        assert '+gameinfo:launch_fixture_456+' in opened.call_args.args[0]
        assert 'diagnostic_fixture_123' not in opened.call_args.args[0]
print('Native ticket request and diagnostic/launch separation passed.')

# Exercise the actual urllib transport against a local strict JSON endpoint.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
class JSONEndpoint(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        valid = self.headers.get('Content-Type') == 'application/json' and body == b'{}'
        self.send_response(200 if valid else 415)
        self.send_header('rbx-authentication-ticket', 'local_fixture_ticket')
        self.end_headers()
server = ThreadingHTTPServer(('127.0.0.1', 0), JSONEndpoint)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with patch.dict(a.URLS, {'ticket': f'http://127.0.0.1:{server.server_port}/ticket'}), patch.object(a, 'ProxyHandler', side_effect=lambda: __import__('urllib.request', fromlist=['ProxyHandler']).ProxyHandler({})):
        assert a.request_roblox('ticket', cookie, place=123)[0] == 200
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
print('Strict JSON transport check passed (local endpoint only).')
