"""Unit tests for update_models.py pure helpers."""
import base64
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


class LookupVisionSupportTests(unittest.TestCase):
    REGISTRY = {
        "claude-sonnet-4-20250514": {
            "supports_vision": True,
            "litellm_provider": "anthropic",
        },
        "xai/grok-4-0709": {
            "supports_vision": None,
            "litellm_provider": "xai",
        },
        "gpt-4.1-2025-04-14": {
            "supports_vision": True,
            "litellm_provider": "openai",
        },
        "no-vision-flag": {"litellm_provider": "anthropic"},
    }

    def test_finds_by_bare_id(self):
        self.assertTrue(
            update_models.lookup_vision_support(
                self.REGISTRY, "claude-sonnet-4-20250514", "anthropic"
            )
        )

    def test_finds_by_namespaced_id(self):
        # bare lookup misses; provider-prefixed form should hit
        result = update_models.lookup_vision_support(
            self.REGISTRY, "grok-4-0709", "xai"
        )
        # supports_vision is None in registry → return None (unknown)
        self.assertIsNone(result)

    def test_unknown_model_returns_none(self):
        self.assertIsNone(
            update_models.lookup_vision_support(self.REGISTRY, "nonexistent", "openai")
        )

    def test_entry_without_vision_flag_returns_none(self):
        self.assertIsNone(
            update_models.lookup_vision_support(
                self.REGISTRY, "no-vision-flag", "anthropic"
            )
        )

    def test_false_flag_returns_false(self):
        registry = {"some-model": {"supports_vision": False}}
        self.assertEqual(
            update_models.lookup_vision_support(registry, "some-model", "openai"),
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
            sorted(["o3-mini"]),
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
        ids = [
            "grok-4-0709",
            "grok-3",
            "grok-imagine-image",
            "grok-imagine-image-pro",
            "grok-imagine-video",
            "not-grok",
        ]
        kept = update_models.filter_chat_models("xai", ids)
        self.assertEqual(sorted(kept), ["grok-3", "grok-4-0709"])

    def test_lmstudio_drops_known_non_chat_name_patterns(self):
        ids = [
            "google/gemma-4-31b",
            "qwen-coder",               # drop (code) — now caught by global filter
            "anything-loaded-locally",
            "totally-custom",
            "text-embedding-nomic-embed-code",  # drop (embed)
            "llama-embed-nemotron-8b",          # drop (embed)
            "jina-reranker-v3-mlx",             # drop (rerank)
            "stable-diffusion-xl",              # drop (stable-diffusion AND image)
            "flux-1-schnell",                   # drop (flux)
            "whisper-large-v3",                 # drop (whisper)
            "kokoro-tts",                       # drop (tts)
            "bark-small",                       # drop (bark)
            "facebook-musicgen",                # drop (musicgen)
            "sdxl-image-fix",                   # drop (image)
        ]
        kept = update_models.filter_chat_models("lmstudio", ids)
        self.assertEqual(
            sorted(kept),
            sorted([
                "google/gemma-4-31b",
                "anything-loaded-locally",
                "totally-custom",
            ]),
        )

    def test_global_name_filter_applies_to_all_providers(self):
        # Each provider should drop names containing the global substrings,
        # in addition to its own provider-specific rules.
        cases = [
            # (provider, input, expected_kept)
            ("anthropic", ["claude-sonnet-4", "claude-image-preview"],
             ["claude-sonnet-4"]),
            ("google", [
                "gemini-2.5-pro",
                "gemini-3.1-flash-image-preview",
                "gemini-robotics-er-1.5-preview",
                "gemini-embedding-001",
                "models/gemini-2.5-flash",
            ], ["gemini-2.5-pro", "models/gemini-2.5-flash"]),
            ("openai", ["gpt-4o", "gpt-5-codex", "gpt-5.1-codex-max"],
             ["gpt-4o"]),
            ("xai", ["grok-3", "grok-code-fast-1", "grok-imagine-image"],
             ["grok-3"]),
            ("lmstudio", ["google/gemma-4-31b", "qwen-coder", "jina-reranker"],
             ["google/gemma-4-31b"]),
        ]
        for provider, inputs, expected in cases:
            with self.subTest(provider=provider):
                self.assertEqual(
                    sorted(update_models.filter_chat_models(provider, inputs)),
                    sorted(expected),
                )

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

    def test_openai_excludes_audio_realtime_transcribe_tts_image(self):
        # gpt-prefixed but not text chat
        ids = [
            "gpt-4o",                        # keep
            "gpt-4o-audio-preview",          # drop
            "gpt-4o-mini-audio-preview",     # drop
            "gpt-4o-mini-realtime-preview",  # drop
            "gpt-4o-mini-transcribe",        # drop
            "gpt-4o-mini-tts",               # drop
            "gpt-image-1",                   # drop
            "gpt-4o-mini-search-preview",    # drop (global filter catches search)
        ]
        kept = update_models.filter_chat_models("openai", ids)
        self.assertIn("gpt-4o", kept)
        self.assertNotIn("gpt-4o-audio-preview", kept)
        self.assertNotIn("gpt-4o-mini-audio-preview", kept)
        self.assertNotIn("gpt-4o-mini-realtime-preview", kept)
        self.assertNotIn("gpt-4o-mini-transcribe", kept)
        self.assertNotIn("gpt-4o-mini-tts", kept)
        self.assertNotIn("gpt-image-1", kept)
        self.assertNotIn("gpt-4o-mini-search-preview", kept)

    def test_global_filter_drops_flash_live_multi_agent_search(self):
        cases = [
            ("google", ["gemini-2.5-pro", "gemini-3.1-flash-live-preview"],
             ["gemini-2.5-pro"]),
            ("xai", ["grok-3", "grok-4.20-multi-agent-0309"],
             ["grok-3"]),
            ("openai", [
                "gpt-4o",
                "gpt-4o-search-preview",
                "gpt-4o-mini-search-preview",
                "gpt-5-search-api",
             ], ["gpt-4o"]),
        ]
        for provider, inputs, expected in cases:
            with self.subTest(provider=provider):
                self.assertEqual(
                    sorted(update_models.filter_chat_models(provider, inputs)),
                    sorted(expected),
                )

    def test_global_filter_drops_computer_use_and_customtools(self):
        ids = [
            "gemini-2.5-pro",
            "gemini-2.5-computer-use-preview-10-2025",
            "gemini-3.1-pro-preview-customtools",
        ]
        kept = update_models.filter_chat_models("google", ids)
        self.assertEqual(kept, ["gemini-2.5-pro"])

    def test_openai_drops_dated_snapshots_and_legacy(self):
        ids = [
            "gpt-4o",                            # keep (alias)
            "gpt-4o-2024-08-06",                 # drop (dated)
            "gpt-4o-2024-11-20",                 # drop (dated)
            "gpt-4.1",                           # keep
            "gpt-4.1-2025-04-14",                # drop (dated)
            "gpt-5",                             # keep
            "gpt-5-2025-08-07",                  # drop (dated)
            "gpt-5-chat-latest",                 # keep (no date suffix)
            "o1",                                # keep
            "o1-2024-12-17",                     # drop (dated)
            "gpt-3.5-turbo",                     # drop (legacy prefix)
            "gpt-3.5-turbo-instruct",            # drop (legacy prefix)
            "gpt-4",                             # drop (legacy exact)
            "gpt-4-0613",                        # drop (legacy exact)
            "gpt-4-turbo",                       # keep
            "gpt-4-turbo-2024-04-09",            # drop (dated)
        ]
        kept = update_models.filter_chat_models("openai", ids)
        self.assertEqual(
            sorted(kept),
            sorted([
                "gpt-4o",
                "gpt-4.1",
                "gpt-5",
                "gpt-5-chat-latest",
                "o1",
                "gpt-4-turbo",
            ]),
        )

    def test_google_drops_deprecated_2_0_models(self):
        ids = [
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash-lite-001",
            "models/gemini-2.5-flash",
        ]
        kept = update_models.filter_chat_models("google", ids)
        self.assertEqual(
            sorted(kept),
            sorted(["gemini-2.5-pro", "models/gemini-2.5-flash"]),
        )


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


class OutputFormattingTests(unittest.TestCase):
    def test_header(self):
        line = update_models.format_header("anthropic", "https://api.anthropic.com")
        self.assertEqual(
            line, "Probing provider anthropic at endpoint https://api.anthropic.com"
        )

    def test_model_line_success_true(self):
        line = update_models.format_model_line(
            "claude-sonnet-4", supports_pdf=True, supports_vision=True
        )
        self.assertEqual(
            line, "\t✓  Model: claude-sonnet-4  [ pdf: True | vision: True ]"
        )

    def test_model_line_success_false(self):
        line = update_models.format_model_line(
            "claude-haiku-3-5", supports_pdf=False, supports_vision=False
        )
        self.assertEqual(
            line, "\t✓  Model: claude-haiku-3-5  [ pdf: False | vision: False ]"
        )

    def test_model_line_mixed_capabilities(self):
        line = update_models.format_model_line(
            "some-model", supports_pdf=False, supports_vision=True
        )
        self.assertEqual(
            line, "\t✓  Model: some-model  [ pdf: False | vision: True ]"
        )

    def test_model_line_error(self):
        line = update_models.format_model_line(
            "claude-experimental", error="HTTP 404 model not found"
        )
        self.assertEqual(
            line,
            "\t✗  Model: claude-experimental  [ Error: HTTP 404 model not found ]",
        )

    def test_provider_summary_success(self):
        line = update_models.format_provider_summary("anthropic", success=True)
        self.assertEqual(line, "✅ anthropic  Model list updated")

    def test_provider_summary_failure(self):
        line = update_models.format_provider_summary(
            "xai", success=False, error="HTTP 401 unauthorized"
        )
        self.assertEqual(
            line, "❌ xai  Error retrieving list of models: HTTP 401 unauthorized"
        )


class MinimalPdfTests(unittest.TestCase):
    def test_base64_decodes(self):
        raw = base64.b64decode(update_models.MINIMAL_PDF_B64)
        # Must start with the PDF magic header and end with %%EOF
        self.assertTrue(raw.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", raw)

    def test_size_is_reasonable(self):
        raw = base64.b64decode(update_models.MINIMAL_PDF_B64)
        # Few hundred bytes per the spec; not many KB
        self.assertLess(len(raw), 2048)


class MinimalPngTests(unittest.TestCase):
    def test_base64_decodes(self):
        raw = base64.b64decode(update_models.MINIMAL_PNG_B64)
        # PNG magic header is 8 bytes: \x89PNG\r\n\x1a\n
        self.assertTrue(raw.startswith(b"\x89PNG"))

    def test_size_is_reasonable(self):
        raw = base64.b64decode(update_models.MINIMAL_PNG_B64)
        self.assertLess(len(raw), 256)

    def test_dimensions_meet_xai_minimum(self):
        # xAI rejects images below 8x8 dimensions or below 512 total pixels.
        # IHDR chunk starts at byte 8: 4-byte length, 4-byte "IHDR" type,
        # then 4-byte big-endian width and 4-byte big-endian height.
        import struct
        raw = base64.b64decode(update_models.MINIMAL_PNG_B64)
        width, height = struct.unpack(">II", raw[16:24])
        self.assertGreaterEqual(width, 8)
        self.assertGreaterEqual(height, 8)
        self.assertGreaterEqual(width * height, 512)


class ProbeResultTests(unittest.TestCase):
    def test_success_with_pdf(self):
        r = update_models.ProbeResult(succeeded=True, supports=True, error=None)
        self.assertTrue(r.succeeded)
        self.assertTrue(r.supports)
        self.assertIsNone(r.error)

    def test_failure_carries_error(self):
        r = update_models.ProbeResult(
            succeeded=False, supports=None, error="boom"
        )
        self.assertFalse(r.succeeded)
        self.assertEqual(r.error, "boom")


class EndpointRootTests(unittest.TestCase):
    def test_replaces_chat_completions(self):
        self.assertEqual(
            update_models.derive_models_url(
                "http://localhost:1234/v1/chat/completions"
            ),
            "http://localhost:1234/v1/models",
        )

    def test_appends_models_when_no_chat_completions(self):
        self.assertEqual(
            update_models.derive_models_url("https://api.example.com/v1"),
            "https://api.example.com/v1/models",
        )


class OpenAICompatProviderTests(unittest.TestCase):
    def _make_client(self):
        return update_models.OpenAICompatProvider(
            api_endpoint="http://localhost:1234/v1/chat/completions",
            api_key=None,
        )

    def test_list_models_parses_data_array(self):
        client = self._make_client()
        body = {"data": [{"id": "google/gemma-4-31b"}, {"id": "custom-model"}]}
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = body
        fake_response.raise_for_status.return_value = None
        with mock.patch(
            "update_models.requests.get", return_value=fake_response
        ) as g:
            result = client.list_models()
        self.assertEqual(sorted(result), ["custom-model", "google/gemma-4-31b"])
        g.assert_called_once()
        called_url = g.call_args[0][0]
        self.assertEqual(called_url, "http://localhost:1234/v1/models")

    def test_list_models_raises_on_http_error(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=500)
        fake_response.raise_for_status.side_effect = update_models.requests.HTTPError(
            "500 Server Error", response=fake_response
        )
        with mock.patch(
            "update_models.requests.get", return_value=fake_response
        ):
            with self.assertRaises(update_models.requests.HTTPError):
                client.list_models()

    def test_probe_pdf_returns_true_on_2xx(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = {"choices": [{"message": {"content": "."}}]}
        fake_response.raise_for_status.return_value = None
        with mock.patch(
            "update_models.requests.post", return_value=fake_response
        ):
            result = client.probe("google/gemma-4-31b", "pdf")
        self.assertTrue(result.succeeded)
        self.assertTrue(result.supports)
        self.assertIsNone(result.error)

    def test_probe_image_returns_true_on_2xx(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = {"choices": [{"message": {"content": "."}}]}
        fake_response.raise_for_status.return_value = None
        with mock.patch(
            "update_models.requests.post", return_value=fake_response
        ):
            result = client.probe("google/gemma-4-31b", "image")
        self.assertTrue(result.succeeded)
        self.assertTrue(result.supports)
        self.assertIsNone(result.error)

    def test_probe_pdf_returns_false_on_input_rejection(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=400)
        fake_response.text = (
            '{"error":{"message":"This model does not support image inputs"}}'
        )
        fake_response.raise_for_status.side_effect = update_models.requests.HTTPError(
            "400 Bad Request", response=fake_response
        )
        with mock.patch(
            "update_models.requests.post", return_value=fake_response
        ):
            result = client.probe("text-only-model", "pdf")
        self.assertTrue(result.succeeded)
        self.assertFalse(result.supports)
        self.assertIsNone(result.error)

    def test_probe_pdf_returns_error_on_other_failure(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=503)
        fake_response.text = "Service Unavailable"
        fake_response.raise_for_status.side_effect = update_models.requests.HTTPError(
            "503 Service Unavailable", response=fake_response
        )
        with mock.patch(
            "update_models.requests.post", return_value=fake_response
        ):
            result = client.probe("any-model", "pdf")
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.supports)
        self.assertIn("503", result.error)

    def test_probe_raises_on_unknown_kind(self):
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.probe("some-model", "video")


class XAIProviderTests(unittest.TestCase):
    def _make_client(self, api_key="key"):
        return update_models.XAIProvider(
            api_endpoint="https://api.x.ai/v1/chat/completions",
            api_key=api_key,
        )

    def test_models_url_correct(self):
        client = self._make_client()
        self.assertEqual(client.models_url, "https://api.x.ai/v1/models")

    def test_list_models_passes_bearer_token(self):
        client = self._make_client(api_key="xai-secret")
        body = {"data": [{"id": "grok-4-0709"}, {"id": "grok-3"}]}
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = body
        fake_response.raise_for_status.return_value = None
        with mock.patch(
            "update_models.requests.get", return_value=fake_response
        ) as g:
            result = client.list_models()
        self.assertEqual(sorted(result), ["grok-3", "grok-4-0709"])
        called_kwargs = g.call_args.kwargs
        self.assertEqual(
            called_kwargs["headers"]["Authorization"], "Bearer xai-secret"
        )

    def test_name_is_xai(self):
        self.assertEqual(self._make_client().name, "xai")


class FakeProvider:
    """Test double matching the per-provider client interface."""

    name = "fake"

    def __init__(self, models, probe_results=None, list_error=None):
        self._models = models
        # probe_results may be keyed by (model, kind) or just model for backward compat
        self._probe_results = probe_results or {}
        self._list_error = list_error

    def list_models(self):
        if self._list_error:
            raise self._list_error
        return list(self._models)

    def probe(self, model, kind):
        # Try (model, kind) key first, then bare model key, then default
        result = self._probe_results.get(
            (model, kind),
            self._probe_results.get(
                model,
                update_models.ProbeResult(
                    succeeded=True, supports=False, error=None
                ),
            ),
        )
        return result


class ProcessProviderTests(unittest.TestCase):
    def test_uses_registry_when_known(self):
        provider = FakeProvider(models=["claude-known", "claude-unknown"])
        registry = {"claude-known": {"supports_pdf_input": True}}
        block = {
            "api_endpoint": "https://x.example",
            "api_key_env": "X",
            "available_models": [],
            "pdf_support": {},
            "default_model": "",
        }
        with mock.patch.object(
            update_models, "filter_chat_models",
            side_effect=lambda p, ids: ids,
        ):
            updated, summary = update_models.process_provider(
                provider_name="anthropic",
                provider_block=block,
                client=provider,
                registry=registry,
                enable_probing=False,
            )
        self.assertTrue(summary.success)
        self.assertEqual(
            sorted(updated["available_models"]),
            ["claude-known", "claude-unknown"],
        )
        self.assertEqual(
            updated["pdf_support"],
            {"claude-known": True, "claude-unknown": False},
        )
        # Vision not in registry → defaults to False
        self.assertEqual(
            updated["vision_support"],
            {"claude-known": False, "claude-unknown": False},
        )

    def test_probes_unknown_when_enabled(self):
        provider = FakeProvider(
            models=["claude-mystery"],
            probe_results={
                ("claude-mystery", "pdf"): update_models.ProbeResult(
                    succeeded=True, supports=True, error=None
                ),
                ("claude-mystery", "image"): update_models.ProbeResult(
                    succeeded=True, supports=True, error=None
                ),
            },
        )
        block = {
            "api_endpoint": "https://x.example",
            "api_key_env": "X",
            "available_models": [],
            "pdf_support": {},
        }
        with mock.patch.object(
            update_models, "filter_chat_models",
            side_effect=lambda p, ids: ids,
        ):
            updated, summary = update_models.process_provider(
                provider_name="anthropic",
                provider_block=block,
                client=provider,
                registry={},
                enable_probing=True,
            )
        self.assertTrue(summary.success)
        self.assertEqual(updated["pdf_support"], {"claude-mystery": True})
        self.assertEqual(updated["vision_support"], {"claude-mystery": True})

    def test_provider_failure_returns_unchanged_block_and_failure_summary(self):
        provider = FakeProvider(
            models=[],
            list_error=update_models.requests.HTTPError("HTTP 401 unauthorized"),
        )
        original_block = {
            "api_endpoint": "https://x.example",
            "api_key_env": "X",
            "available_models": ["existing-model"],
            "pdf_support": {"existing-model": True},
            "default_model": "existing-model",
        }
        updated, summary = update_models.process_provider(
            provider_name="anthropic",
            provider_block=original_block,
            client=provider,
            registry={},
            enable_probing=False,
        )
        self.assertFalse(summary.success)
        self.assertEqual(updated, original_block)
        self.assertIn("401", summary.error)

    def test_default_model_preserved_when_still_present(self):
        provider = FakeProvider(models=["a", "b", "c"])
        block = {
            "api_endpoint": "https://x.example",
            "api_key_env": "X",
            "available_models": [],
            "pdf_support": {},
            "default_model": "b",
        }
        with mock.patch.object(
            update_models, "filter_chat_models",
            side_effect=lambda p, ids: ids,
        ):
            updated, _ = update_models.process_provider(
                provider_name="anthropic",
                provider_block=block,
                client=provider,
                registry={},
                enable_probing=False,
            )
        self.assertEqual(updated["default_model"], "b")

    def test_default_model_reset_when_dropped(self):
        provider = FakeProvider(models=["x", "y"])
        block = {
            "api_endpoint": "https://x.example",
            "api_key_env": "X",
            "available_models": [],
            "pdf_support": {},
            "default_model": "z-removed",
        }
        with mock.patch.object(
            update_models, "filter_chat_models",
            side_effect=lambda p, ids: ids,
        ):
            updated, _ = update_models.process_provider(
                provider_name="anthropic",
                provider_block=block,
                client=provider,
                registry={},
                enable_probing=False,
            )
        # First model in sorted available_models becomes the new default
        self.assertEqual(updated["default_model"], "x")

    def test_both_registry_fields_flow_through(self):
        """Registry entries with both pdf and vision flags carry through correctly."""
        provider = FakeProvider(models=["model-a", "model-b"])
        registry = {
            "model-a": {"supports_pdf_input": True, "supports_vision": True},
            "model-b": {"supports_pdf_input": False, "supports_vision": False},
        }
        block = {
            "api_endpoint": "https://x.example",
            "api_key_env": "X",
            "available_models": [],
            "pdf_support": {},
        }
        with mock.patch.object(
            update_models, "filter_chat_models",
            side_effect=lambda p, ids: ids,
        ):
            updated, summary = update_models.process_provider(
                provider_name="fake",
                provider_block=block,
                client=provider,
                registry=registry,
                enable_probing=False,
            )
        self.assertTrue(summary.success)
        self.assertEqual(updated["pdf_support"], {"model-a": True, "model-b": False})
        self.assertEqual(
            updated["vision_support"], {"model-a": True, "model-b": False}
        )


class LMStudioProviderTests(unittest.TestCase):
    def _make_client(self):
        return update_models.LMStudioProvider(
            api_endpoint="http://localhost:1234/v1/chat/completions",
            api_key=None,
        )

    def test_list_models_uses_rich_endpoint_and_filters_embeddings(self):
        client = self._make_client()
        rich_body = {
            "data": [
                {"id": "google/gemma-4-31b", "type": "vlm"},
                {"id": "qwen-coder", "type": "llm"},
                {"id": "text-embedding-nomic-embed", "type": "embeddings"},
                {"id": "jina-reranker-v3-mlx", "type": "llm"},
            ]
        }
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = rich_body
        fake_response.raise_for_status.return_value = None
        with mock.patch(
            "update_models.requests.get", return_value=fake_response
        ) as g:
            result = client.list_models()
        self.assertEqual(
            sorted(result),
            sorted(["google/gemma-4-31b", "qwen-coder", "jina-reranker-v3-mlx"]),
        )
        called_url = g.call_args[0][0]
        self.assertEqual(called_url, "http://localhost:1234/api/v0/models")

    def test_list_models_falls_back_to_openai_compat_on_error(self):
        client = self._make_client()
        # First call (rich endpoint) raises; second call (compat endpoint) succeeds.
        compat_body = {"data": [{"id": "fallback-model"}]}
        compat_response = mock.Mock(status_code=200)
        compat_response.json.return_value = compat_body
        compat_response.raise_for_status.return_value = None

        rich_response = mock.Mock(status_code=404)
        rich_response.raise_for_status.side_effect = (
            update_models.requests.HTTPError("404", response=rich_response)
        )

        call_count = {"n": 0}
        def side_effect(url, *a, **kw):
            call_count["n"] += 1
            if "/api/v0/models" in url:
                return rich_response
            return compat_response

        with mock.patch(
            "update_models.requests.get", side_effect=side_effect
        ):
            result = client.list_models()
        self.assertEqual(result, ["fallback-model"])
        self.assertEqual(call_count["n"], 2)


if __name__ == "__main__":
    unittest.main()
