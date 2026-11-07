"""Storage failure recovery and bounded queue behavior; synthetic data only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

TEST_ROOT = tempfile.TemporaryDirectory()
os.environ['LOCALAPPDATA'] = TEST_ROOT.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json_store as store
import app

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'accounts.json'

    def test_legacy_shape_backup_and_recovery(self):
        old = {'42': {'session': 'DPAPI-fixture', 'username': 'fixture_user'}}
        self.path.write_text(json.dumps(old))
        store.write(self.path, {**old, '43': {}})
        self.assertEqual(json.loads(self.path.with_name('accounts.json.bak').read_text()), old)
        self.path.write_text('{broken')
        self.assertEqual(store.read(self.path, {}), old)
        self.assertEqual(json.loads(self.path.read_text()), old)
        self.assertTrue(store.notices())

    def test_corruption_without_backup_never_becomes_empty_vault(self):
        self.path.write_text('{broken')
        for action in (lambda: store.read(self.path, {}), lambda: store.write(self.path, {})):
            with self.assertRaises(ValueError): action()
        self.assertEqual(self.path.read_text(), '{broken')

    def test_default_is_independent_and_shape_validated(self):
        default = {'items': []}
        store.read(self.path, default)['items'].append(1)
        self.assertEqual(default, {'items': []})
        self.path.write_text('[]')
        with self.assertRaises(ValueError): store.read(self.path, {})

    def test_concurrent_replacements_are_valid_and_leave_no_temporary(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: store.write(self.path, {'value': i, 'payload': 'x' * 10000}), range(40)))
        self.assertIn(store.read(self.path, {})['value'], range(40))
        self.assertIsInstance(json.loads(self.path.with_name('accounts.json.bak').read_text()), dict)
        self.assertFalse(list(self.path.parent.glob('*.tmp')))

    def test_failed_replacement_preserves_previous_file(self):
        store.write(self.path, {'value': 1})
        original_replace = store.os.replace
        def fail(source, destination):
            if Path(destination) == self.path: raise OSError('fixture replace failure')
            return original_replace(source, destination)
        with patch.object(store.os, 'replace', side_effect=fail):
            with self.assertRaises(OSError): store.write(self.path, {'value': 2})
        self.assertEqual(store.read(self.path, {}), {'value': 1})
        self.assertFalse(list(self.path.parent.glob('*.tmp')))

    def test_nonfinite_json_rejected_without_changes(self):
        store.write(self.path, {'value': 1})
        with self.assertRaises(ValueError): store.write(self.path, {'value': float('nan')})
        self.assertEqual(store.read(self.path, {}), {'value': 1})

class QueueTests(unittest.TestCase):
    def setUp(self):
        app.BUSY = False
        app.WAITING = 0
        app.LIVE.clear(); app.STATUS.clear(); app.BINDINGS.clear()
        app.REJOIN.clear(); app.QUEUE_CANCEL.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = patch.object(app, 'SETTINGS', Path(self.temp.name) / 'settings.json')
        self.settings.start(); self.addCleanup(self.settings.stop)
        self.profiles = patch.object(app, 'PROFILES', Path(self.temp.name) / 'profiles.json')
        self.profiles.start(); self.addCleanup(self.profiles.stop)

    def test_slot_timeout_releases_queue_and_reports_error(self):
        class Inline:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        with patch.object(app.accounts, 'accounts', return_value=[{'userId': 1, 'username': 'fixture_user'}]), patch.object(app.threading, 'Thread', Inline), patch.object(app.windows, 'running', return_value={99}), patch.object(app, 'QUEUE_SLOT_TIMEOUT', 0), patch.object(app, 'record'), patch.object(app.accounts, 'launch') as launch:
            app.start_job({'ids': [1], 'place': 123, 'limit': 1})
            self.assertFalse(app.BUSY)
            self.assertEqual(app.WAITING, 0)
            self.assertIn('Tempo de espera', app.STATUS[1])
            launch.assert_not_called()

    def test_failure_after_process_launch_cannot_leave_opening_status(self):
        class Inline:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        with patch.object(app.accounts, 'accounts', return_value=[{'userId': 1, 'username': 'fixture_user'}]), patch.object(app.threading, 'Thread', Inline), patch.object(app.windows, 'running', return_value=set()), patch.object(app.accounts, 'launch'), patch.object(app, 'wait_new_pid', return_value=123), patch.object(app.windows, 'process_stamp', return_value=456), patch.object(app.windows, 'compact', side_effect=OSError('fixture window error')), patch.object(app, 'record'):
            app.start_job({'ids': [1], 'place': 123})
            self.assertFalse(app.BUSY)
            self.assertTrue(app.STATUS[1].startswith('Erro na abertura'))

class RedactionTests(unittest.TestCase):
    def test_diagnostic_tokens_urls_and_protocol_are_removed(self):
        from redaction import redact
        samples = [
            ('password="secret words"', 'secret words'),
            ('senha=fixture-pass', 'fixture-pass'),
            ('Cookie: fixture-cookie', 'fixture-cookie'),
            ('.ROBLOSECURITY=fixture-security-value', 'fixture-security-value'),
            ('Authorization: Bearer fixture-bearer', 'fixture-bearer'),
            ('https://example.invalid/?ticket=fixture-url-token', 'fixture-url-token'),
            ('roblox-player:1+gameinfo:fixture-protocol-token', 'fixture-protocol-token'),
            ('"x-csrf-token": "fixture-csrf-token"', 'fixture-csrf-token'),
        ]
        for message, secret in samples:
            with self.subTest(message=message):
                self.assertNotIn(secret, redact(message))
        self.assertEqual(redact('Ticket HTTP 403; etapa launcher'), 'Ticket HTTP 403; etapa launcher')

    def test_history_redacts_before_persisting(self):
        history = Path(TEST_ROOT.name) / 'redaction-history.json'
        with patch.object(app, 'HISTORY', history):
            app.record('fixture_user', 'password=fixture-secret')
        self.assertNotIn('fixture-secret', history.read_text())

if __name__ == '__main__':
    try: unittest.main()
    finally: TEST_ROOT.cleanup()
