"""No network or real credential is used by these transport checks."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zetaris_context import ZetarisContext


class ZetarisTests(unittest.TestCase):
    def context(self, directory, **overrides):
        values = dict(origin='http://127.0.0.1:8080', org_id='2', credential='test_private_token',
                      sql='SELECT topic, tip FROM demo.synthetic_context LIMIT 5', evidence=directory,
                      local_origin='http://127.0.0.1:8765')
        values.update(overrides)
        return ZetarisContext(**values)

    def test_refuses_remote_http_credentials_in_url_and_write_sql(self):
        for origin in ('http://zetaris.example', 'https://user:password@example.com', 'https://example.com/path'):
            with self.assertRaises(ValueError):
                self.context('.', origin=origin)
        for sql in ('SELECT 1', 'DELETE FROM demo.rows', 'SELECT * FROM demo.rows; DROP TABLE demo.rows', 'SELECT * INTO target FROM demo.rows'):
            with self.assertRaises(ValueError):
                self.context('.', sql=sql)

    def test_config_carries_only_local_capability_and_no_verified_claim(self):
        context = self.context('.')
        self.assertNotIn(context._credential, json.dumps(context.config()))
        self.assertFalse(context.config()['verified'])

    @patch('zetaris_context.subprocess.run')
    def test_foreign_origins_and_wrong_session_cannot_make_requests(self, run):
        context = self.context('.')
        for origin, auth in [('https://foreign.example', 'Bearer '+context.token), (context.local_origin, 'Bearer wrong')]:
            with self.assertRaises(PermissionError):
                context.retrieve(origin, auth)
        run.assert_not_called()

    @patch('zetaris_context.subprocess.run')
    def test_real_response_rows_are_returned_and_secret_is_only_in_stdin(self, run):
        with tempfile.TemporaryDirectory() as directory:
            context = self.context(directory)
            run.return_value = subprocess.CompletedProcess([], 0, json.dumps({'data':[{'topic':'speaking','tip':'Ask one question'}]})+'\n200', '')
            result = context.retrieve(context.local_origin, 'Bearer '+context.token)
            self.assertTrue(result['verified'])
            self.assertEqual(result['row_count'], 1)
            self.assertEqual(result['rows'][0]['topic'], 'speaking')
            args, kwargs = run.call_args
            self.assertNotIn(context._credential, json.dumps(args))
            self.assertIn(context._credential, kwargs['input'])
            record = json.loads((Path(directory)/result['evidence_id']).read_text())
            self.assertEqual(record['response']['data'], result['rows'])
            self.assertEqual(record['request']['pageLimit'], 5)
            self.assertNotIn(context._credential, json.dumps(record))
            self.assertNotIn(context.token, json.dumps(record))

    @patch('zetaris_context.subprocess.run')
    def test_error_empty_unreadable_and_unbounded_responses_fail_closed(self, run):
        with tempfile.TemporaryDirectory() as directory:
            context = self.context(directory)
            for raw in ('not-json\n200', '{"data":[]}\n200', '{"error":"no access"}\n403', json.dumps({'rows':[{}]*6})+'\n200'):
                run.return_value = subprocess.CompletedProcess([], 0, raw, '')
                with self.assertRaises(RuntimeError):
                    context.retrieve(context.local_origin, 'Bearer '+context.token)

    @patch('zetaris_context.subprocess.run')
    def test_current_platform_records_response_is_preserved_and_verified(self, run):
        with tempfile.TemporaryDirectory() as directory:
            context = self.context(directory)
            response = {"records": [{"seven": "7"}], "pageNumber": 1, "pageLimit": 5,
                        "totalCount": 1, "totalPages": 1, "queryToken": "opaque-demo"}
            run.return_value = subprocess.CompletedProcess([], 0, json.dumps(response)+'\n200', '')
            result = context.retrieve(context.local_origin, 'Bearer '+context.token)
            self.assertTrue(result['verified'])
            self.assertEqual(result['rows'], response['records'])
            record = json.loads((Path(directory)/result['evidence_id']).read_text())
            self.assertEqual(record['response'], response)
