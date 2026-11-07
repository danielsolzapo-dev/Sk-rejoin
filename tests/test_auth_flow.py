"""Authentication stages with synthetic sessions; no account or network access."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import accounts as a
cookie = 'fixture-cookie-' * 4
ticket = 'fixture-ticket-123456789'
csrf = 'fixture-csrf'
metadata = {'userId': 42, 'username': 'fixture_user'}
with patch.object(a, 'load_session', return_value=(metadata, {'cookie': cookie, 'ua': 'fixture-browser'})), patch.object(a, 'authenticated', return_value=metadata), patch.object(a, 'SUPPORTED', True), patch.object(a, 'open_game') as opened:
    with patch.object(a, 'request_roblox', side_effect=[(403, {'X-CSRF-TOKEN': csrf}, b''), (200, {'rbx-authentication-ticket': ticket}, b'')]) as request:
        assert a.launch('fixture_user', 2753915549)
        assert request.call_count == 2 and request.call_args.kwargs['csrf'] == csrf
        assert opened.call_count == 1
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
with patch.object(a, 'build_opener') as opener:
    response = MagicMock(status=200, headers={})
    response.read.return_value = b'{}'
    opener.return_value.open.return_value.__enter__.return_value = response
    a.request_roblox('ticket', cookie, 'fixture-browser', csrf=csrf, place=123)
    request = opener.return_value.open.call_args.args[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers['rbxauthenticationnegotiation'] == '1'
    assert headers['x-csrf-token'] == csrf
    assert request.full_url == a.URLS['ticket'] and request.method == 'POST'
print('Authentication flow checks passed (synthetic sessions only).')
