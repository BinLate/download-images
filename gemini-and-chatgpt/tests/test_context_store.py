import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from context_store import ContextStoreError, add_command, add_decision, init_context, load_context, require_env_name, save_context, validate_context


class ContextStoreTests(unittest.TestCase):
    def test_init_and_updates_preserve_normalized_context(self):
        with tempfile.TemporaryDirectory() as td:
            data = init_context(td, 'demo', 'owner/demo')
            data = add_command(data, 'test', 'python -m unittest discover -s tests')
            data = require_env_name(data, 'GITHUB_TOKEN_NAME_ONLY')
            data = add_decision(data, 'Use one .ai namespace', 'avoid split authority')
            save_context(td, data)
            loaded = load_context(td)
            self.assertEqual(loaded['project']['repository'], 'owner/demo')
            self.assertEqual(loaded['environment']['required_variable_names'], ['GITHUB_TOKEN_NAME_ONLY'])
            self.assertEqual(len(loaded['decisions']), 1)

    def test_environment_secret_value_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            data = init_context(td, 'demo')
            data['environment']['values'] = {'TOKEN': 'secret'}
            with self.assertRaises(ContextStoreError):
                validate_context(data)

    def test_invalid_env_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            data = init_context(td, 'demo')
            with self.assertRaises(ContextStoreError):
                require_env_name(data, 'TOKEN=value')


if __name__ == '__main__':
    unittest.main()
