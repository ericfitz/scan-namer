"""Unit tests for update_models.py pure helpers."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

import update_models


class ResolveApiKeyTests(unittest.TestCase):
    def test_reads_value_from_export_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write("export MY_KEY=abc123\n")
            result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "abc123")

    def test_strips_surrounding_quotes(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write('export MY_KEY="abc 123"\n')
            result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "abc 123")

    def test_falls_back_to_environ_when_file_missing(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {"MY_KEY": "from-env"}):
                result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "from-env")

    def test_returns_none_when_neither_file_nor_env(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {}, clear=True):
                result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertIsNone(result)

    def test_file_takes_precedence_over_env(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write("export MY_KEY=from-file\n")
            with mock.patch.dict(os.environ, {"MY_KEY": "from-env"}):
                result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "from-file")

    def test_handles_file_without_export_keyword(self):
        # Some users may write `MY_KEY=value` without the export prefix
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write("MY_KEY=plain\n")
            result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "plain")

    def test_strips_single_quotes(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write("export MY_KEY='abc 123'\n")
            result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "abc 123")

    def test_handles_value_with_embedded_equals(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write("export MY_KEY=base64==value\n")
            result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "base64==value")

    def test_handles_empty_value(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "MY_KEY")
            with open(path, "w") as f:
                f.write("export MY_KEY=\n")
            result = update_models.resolve_api_key("MY_KEY", project_root=root)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
