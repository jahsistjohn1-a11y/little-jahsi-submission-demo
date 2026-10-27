import sys
import json
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deepseek_relay import DeepSeekRelay


class RelayTests(unittest.TestCase):
    def test_credentials_origin_model_and_paid_budget_are_enforced_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relay = DeepSeekRelay('test_value_not_secret', root / 'evidence', 'http://127.0.0.1:8765', limit=0)
            self.assertNotIn('test_value_not_secret', str(relay.config()))
            payload = {'model': 'deepseek-v4-flash', 'messages': [{'role': 'system', 'content': 'You grade candidates against numbered criteria.'}]}
            with self.assertRaises(PermissionError):
                relay.judge(payload, 'https://untrusted.example', 'Bearer '+relay.token)
            with self.assertRaises(PermissionError):
                relay.judge(payload, relay.origin, 'Bearer incorrect')
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                relay.judge(payload, relay.origin, 'Bearer '+relay.token)
            with self.assertRaisesRegex(ValueError, 'Only the configured'):
                relay.judge({'model': 'other-model'}, relay.origin, 'Bearer '+relay.token)
            self.assertEqual(relay.calls, 0)

    def test_empty_or_injected_key_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                DeepSeekRelay('bad key with spaces', root, 'http://127.0.0.1:8765')


class RelayTransportTests(unittest.TestCase):
    def test_real_transport_contract_preserves_answer_and_redacts_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relay = DeepSeekRelay('test_value_not_secret', root / 'evidence', 'http://127.0.0.1:8765')
            payload = {'model': 'deepseek-v4-pro', 'messages': [{'role': 'user', 'content': 'Synthetic goal'}]}
            answer = {'model': 'deepseek-v4-pro', 'choices': [{'message': {'content': 'Original answer'}}],
                      'test_echo': 'test_value_not_secret '+relay.token}
            result = SimpleNamespace(stdout=json.dumps(answer)+'\n200', returncode=0)
            with patch('deepseek_relay.subprocess.run', return_value=result) as call:
                response = relay.judge(payload, relay.origin, 'Bearer '+relay.token)
            args, kwargs = call.call_args
            self.assertNotIn('test_value_not_secret', str(args))
            self.assertIn('test_value_not_secret', kwargs['input'])
            self.assertEqual(response['model'], 'meterless-proxy/deepseek-v4-pro')
            self.assertEqual(response['choices'], answer['choices'])
            saved = next((root / 'evidence').glob('*.json')).read_text()
            self.assertNotIn('test_value_not_secret', saved)
            self.assertNotIn(relay.token, saved)
            record = json.loads(saved)
            self.assertEqual(record['provider_request']['messages'], payload['messages'])
            self.assertEqual(record['provider_response']['model'], 'deepseek-v4-pro')
            self.assertEqual(record['http_status'], 200)
            self.assertEqual(relay.calls, 1)

    def test_non_native_verifier_request_is_rejected_before_spending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relay = DeepSeekRelay('test_value_not_secret', root / 'evidence', 'http://127.0.0.1:8765')
            payload = {'model': 'deepseek-v4-flash', 'messages': [{'role': 'user', 'content': 'Do something else'}]}
            with patch('deepseek_relay.subprocess.run') as call:
                with self.assertRaisesRegex(ValueError, 'native Nightshift judge'):
                    relay.judge(payload, relay.origin, 'Bearer '+relay.token)
                call.assert_not_called()
            self.assertEqual(relay.calls, 0)
