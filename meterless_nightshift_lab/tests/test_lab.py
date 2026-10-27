"""Security and reproducibility checks for the local launcher."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("lab", Path(__file__).parents[1] / "lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LabTests(unittest.TestCase):
    def test_rejects_escape_and_remote_assets(self):
        for name in ("../secret", "/etc/passwd", "https://example.com/x", "x\\..\\secret"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                lab.asset_path(name)

    def test_refuses_drift_before_execution(self):
        with self.assertRaises(ValueError):
            lab.checked_bytes(b"changed", {"bytes": 7, "sha256": "0" * 64})

    def test_cloud_and_relay_are_unconfigured(self):
        text = lab.local_environment().decode()
        env = json.loads(text.removeprefix('window.NS_WEB_ENV=').strip().removesuffix(';'))
        self.assertEqual(env['proxyBase'], '')
        self.assertEqual(env['byokProviders'], [])
        self.assertFalse(env['hotspot'])

    def test_deepseek_uses_separate_generator_and_verifier_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relay = lab.DeepSeekRelay('test_value_not_secret', root / 'evidence', 'http://127.0.0.1:8765')
            config = relay.config()
            self.assertEqual(config['generator_model'], 'deepseek-v4-pro')
            self.assertEqual(config['judge_model'], 'deepseek-v4-flash')
            self.assertNotEqual(config['generator_model'], config['judge_model'])




class LauncherPromptTests(unittest.TestCase):
    def test_cloud_start_prompts_without_using_files_or_local_models(self):
        with patch('lab.sys.stdin.isatty', return_value=True), patch('lab.getpass.getpass', return_value='fake_test_key') as prompt, patch.object(lab, 'serve') as serve, patch.object(lab, 'model_server') as local:
            lab.main(['start', '--deepseek'])
            prompt.assert_called_once()
            serve.assert_called_once_with(8765, 'fake_test_key')
            local.assert_not_called()

    def test_cloud_mode_refuses_noninteractive_key_input(self):
        with patch('sys.stderr', new_callable=io.StringIO), patch('lab.sys.stdin.isatty', return_value=False), patch('lab.getpass.getpass') as prompt, patch.object(lab, 'serve') as serve:
            with self.assertRaises(SystemExit):
                lab.main(['start', '--deepseek'])
            prompt.assert_not_called()
            serve.assert_not_called()

    def test_empty_key_does_not_start_server(self):
        with patch('sys.stderr', new_callable=io.StringIO), patch('lab.sys.stdin.isatty', return_value=True), patch('lab.getpass.getpass', return_value=''), patch.object(lab, 'serve') as serve:
            with self.assertRaises(SystemExit):
                lab.main(['start', '--deepseek'])
            serve.assert_not_called()

    def test_key_is_never_entered_with_terminal_echo_enabled(self):
        with patch('sys.stderr', new_callable=io.StringIO), patch('lab.sys.stdin.isatty', return_value=True), patch('lab.getpass.getpass', side_effect=lab.getpass.GetPassWarning), patch.object(lab, 'serve') as serve:
            with self.assertRaises(SystemExit):
                lab.main(['start', '--deepseek'])
            serve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
