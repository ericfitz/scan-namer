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


class FetchLiteLLMRegistryTests(unittest.TestCase):
    def test_returns_parsed_dict_on_success(self):
        sample = {"claude-x": {"supports_pdf_input": True}}
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = sample
        fake_response.raise_for_status.return_value = None
        with mock.patch("update_models.requests.get", return_value=fake_response):
            result = update_models.fetch_litellm_registry()
        self.assertEqual(result, sample)

    def test_returns_empty_dict_on_network_error(self):
        with mock.patch(
            "update_models.requests.get",
            side_effect=update_models.requests.ConnectionError("boom"),
        ):
            result = update_models.fetch_litellm_registry()
        self.assertEqual(result, {})

    def test_returns_empty_dict_on_bad_json(self):
        fake_response = mock.Mock(status_code=200)
        fake_response.raise_for_status.return_value = None
        fake_response.json.side_effect = ValueError("not json")
        with mock.patch("update_models.requests.get", return_value=fake_response):
            result = update_models.fetch_litellm_registry()
        self.assertEqual(result, {})

    def test_returns_empty_dict_on_non_dict_response(self):
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = [1, 2, 3]  # array, not dict
        fake_response.raise_for_status.return_value = None
        with mock.patch("update_models.requests.get", return_value=fake_response):
            result = update_models.fetch_litellm_registry()
        self.assertEqual(result, {})


class LookupPdfSupportTests(unittest.TestCase):
    REGISTRY = {
        "claude-sonnet-4-20250514": {
            "supports_pdf_input": True,
            "litellm_provider": "anthropic",
        },
        "xai/grok-4-0709": {
            "supports_pdf_input": None,
            "litellm_provider": "xai",
        },
        "gpt-4.1-2025-04-14": {
            "supports_pdf_input": True,
            "litellm_provider": "openai",
        },
        "no-pdf-flag": {"litellm_provider": "anthropic"},
    }

    def test_finds_by_bare_id(self):
        self.assertTrue(
            update_models.lookup_pdf_support(
                self.REGISTRY, "claude-sonnet-4-20250514", "anthropic"
            )
        )

    def test_finds_by_namespaced_id(self):
        # bare lookup misses; provider-prefixed form should hit
        result = update_models.lookup_pdf_support(
            self.REGISTRY, "grok-4-0709", "xai"
        )
        # supports_pdf_input is None in registry → return None (unknown)
        self.assertIsNone(result)

    def test_unknown_model_returns_none(self):
        self.assertIsNone(
            update_models.lookup_pdf_support(self.REGISTRY, "nonexistent", "openai")
        )

    def test_entry_without_pdf_flag_returns_none(self):
        self.assertIsNone(
            update_models.lookup_pdf_support(self.REGISTRY, "no-pdf-flag", "anthropic")
        )

    def test_false_flag_returns_false(self):
        registry = {"some-model": {"supports_pdf_input": False}}
        self.assertEqual(
            update_models.lookup_pdf_support(registry, "some-model", "openai"),
            False,
        )


class FilterChatModelsTests(unittest.TestCase):
    def test_openai_keeps_gpt_and_o_models(self):
        ids = [
            "gpt-5-2025-08-07",
            "gpt-4.1-2025-04-14",
            "o3-mini",
            "text-embedding-3-large",
            "whisper-1",
            "tts-1",
            "dall-e-3",
            "omni-moderation-latest",
        ]
        kept = update_models.filter_chat_models("openai", ids)
        self.assertEqual(
            sorted(kept),
            sorted(["gpt-5-2025-08-07", "gpt-4.1-2025-04-14", "o3-mini"]),
        )

    def test_anthropic_keeps_only_claude(self):
        ids = ["claude-sonnet-4-20250514", "non-claude-model"]
        kept = update_models.filter_chat_models("anthropic", ids)
        self.assertEqual(kept, ["claude-sonnet-4-20250514"])

    def test_google_keeps_only_gemini(self):
        ids = ["gemini-2.5-pro", "models/gemini-2.5-flash", "embedding-001"]
        kept = update_models.filter_chat_models("google", ids)
        # accepts the bare and the "models/" prefixed form
        self.assertIn("gemini-2.5-pro", kept)
        self.assertIn("models/gemini-2.5-flash", kept)
        self.assertNotIn("embedding-001", kept)

    def test_xai_keeps_only_grok(self):
        ids = ["grok-4-0709", "grok-3", "not-grok"]
        kept = update_models.filter_chat_models("xai", ids)
        self.assertEqual(sorted(kept), ["grok-3", "grok-4-0709"])

    def test_lmstudio_keeps_everything(self):
        ids = ["google/gemma-4-31b", "anything-loaded-locally", "totally-custom"]
        kept = update_models.filter_chat_models("lmstudio", ids)
        self.assertEqual(sorted(kept), sorted(ids))

    def test_unknown_provider_keeps_everything(self):
        ids = ["a", "b"]
        kept = update_models.filter_chat_models("never-heard-of-it", ids)
        self.assertEqual(sorted(kept), sorted(ids))

    def test_openai_excludes_o_prefix_without_digit(self):
        # The "o" matcher must require a digit follow (o1, o3, o4) — bare "o"
        # words like a hypothetical "octopus-3" should NOT be kept.
        ids = ["o1-mini", "o3", "octopus-3", "omni-foo", "gpt-4o"]
        kept = update_models.filter_chat_models("openai", ids)
        # o1-mini and o3 keep (digit after o); gpt-4o keeps (gpt- prefix).
        # octopus-3 and omni-foo must be dropped.
        self.assertIn("o1-mini", kept)
        self.assertIn("o3", kept)
        self.assertIn("gpt-4o", kept)
        self.assertNotIn("octopus-3", kept)
        self.assertNotIn("omni-foo", kept)

    def test_filter_handles_empty_list(self):
        for provider in ("openai", "anthropic", "google", "xai", "lmstudio"):
            self.assertEqual(update_models.filter_chat_models(provider, []), [])


class AtomicWriteJsonTests(unittest.TestCase):
    def test_writes_pretty_json(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "out.json")
            update_models.atomic_write_json(path, {"a": 1, "b": [2, 3]})
            with open(path) as f:
                content = f.read()
        self.assertIn('"a": 1', content)
        self.assertTrue(content.endswith("\n"))

    def test_no_partial_file_on_serialization_error(self):
        class Unserializable:
            pass

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "out.json")
            # Pre-existing content should survive a failed write
            with open(path, "w") as f:
                f.write('{"original": true}\n')
            with self.assertRaises(TypeError):
                update_models.atomic_write_json(path, {"bad": Unserializable()})
            with open(path) as f:
                self.assertEqual(f.read(), '{"original": true}\n')
            # The .tmp staging file should not be left behind
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "out.json")
            with open(path, "w") as f:
                f.write('{"old": true}\n')
            update_models.atomic_write_json(path, {"new": True})
            with open(path) as f:
                content = f.read()
        self.assertIn('"new": true', content)
        self.assertNotIn("old", content)


if __name__ == "__main__":
    unittest.main()
