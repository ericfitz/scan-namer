# Update Models Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `update_models.py` script (with `update-models` bash wrapper) that connects to each LLM provider in `config.json`, lists currently-available models, looks up PDF capability via the LiteLLM registry (with optional probing fallback), and rewrites the provider's `available_models` and `pdf_support` entries.

**Architecture:** Single-file script following the project's `scan_namer.py` convention (uv inline deps, monolithic file). Pure helpers (key resolution, registry lookup, model filtering, atomic write, output formatting) are independently unit-tested with `unittest`. Per-provider classes (LMStudio, XAI, Anthropic, OpenAI, Google) implement a small `list_models()` / `probe_pdf()` interface; HTTP-based providers are unit-tested with mocked `requests`, SDK-based providers are smoke-tested via dry-run.

**Tech Stack:** Python 3.8+, `requests`, `anthropic` SDK, `openai` SDK, `google-genai` SDK, `unittest` (stdlib), `uv` for dependency management. LiteLLM registry JSON fetched live from GitHub.

---

## File Structure

- **Create:** `update_models.py` — main script with all logic
- **Create:** `update-models` — bash wrapper (analogous to `scan-namer`)
- **Create:** `tests/__init__.py` — empty package marker
- **Create:** `tests/test_update_models.py` — unittest-based unit tests
- **Modify:** `config.json` — add `api_endpoint` to providers that lack one
- **Modify:** `scan-namer` — fix the source line that points to the now-renamed key file
- **Modify:** `.gitignore` — ignore the `*_API_KEY` files (they contain secrets)

---

## Task 1: Project housekeeping (key files, config, gitignore, wrapper fix)

**Files:**
- Modify: `.gitignore`
- Modify: `config.json`
- Modify: `scan-namer`

The API key files were renamed to uppercase (`ANTHROPIC_API_KEY`, etc.). They contain secrets and must be gitignored. The existing `scan-namer` wrapper still sources the lowercase name and is broken until fixed. Three providers (anthropic, openai, google) lack an `api_endpoint` field; add one so the script can print a uniform header line.

- [ ] **Step 1.1: Add `*_API_KEY` exclusion to `.gitignore`**

Append the following lines to `.gitignore`:

```
# API key files (sourced by wrapper scripts; contain secrets)
*_API_KEY
```

- [ ] **Step 1.2: Verify the key files are not tracked**

Run: `git ls-files | grep -E '_API_KEY|api_key' || echo "none tracked"`
Expected: `none tracked`

If any of the renamed files appears, run `git rm --cached <file>` for it before continuing.

- [ ] **Step 1.3: Add `api_endpoint` to anthropic, openai, google in `config.json`**

Insert these fields. The new entries should appear as the first key inside each provider object so the file is consistent with `lmstudio` and `xai`.

For `anthropic`:
```json
"api_endpoint": "https://api.anthropic.com",
```

For `openai`:
```json
"api_endpoint": "https://api.openai.com/v1",
```

For `google`:
```json
"api_endpoint": "https://generativelanguage.googleapis.com",
```

- [ ] **Step 1.4: Validate the JSON is still parseable**

Run: `python3 -c "import json; json.load(open('config.json'))"`
Expected: no output, exit 0

- [ ] **Step 1.5: Fix the `scan-namer` wrapper to point at the renamed key file**

Replace the `source` line. Currently it reads:

```bash
source ~/Projects/scan-namer/lmstudio_api_key
```

Change to:

```bash
source ~/Projects/scan-namer/LMSTUDIO_API_KEY
```

- [ ] **Step 1.6: Smoke-test the existing wrapper still works**

Run: `./scan-namer --list-models 2>&1 | head -5`
Expected: lists provider/model entries; no "no such file or directory" error referencing the api key.

- [ ] **Step 1.7: Commit**

```bash
git add .gitignore config.json scan-namer
git commit -m "chore: add api_endpoint fields, fix wrapper for renamed key files, gitignore key files"
```

---

## Task 2: Create script skeleton with uv inline deps and CLI

**Files:**
- Create: `update_models.py`

Establish the script's shape: shebang, uv inline dependencies, imports, argparse, logging setup, and a `main()` that just parses args and prints them. No provider logic yet — that lands in later tasks. This task gives every later task a stable place to attach code.

- [ ] **Step 2.1: Create `update_models.py` with skeleton**

```python
#!/usr/bin/env python3
"""
Update Models - Refresh available_models and pdf_support in config.json by
querying each LLM provider for currently-available models. PDF capability is
looked up in the LiteLLM model registry; unrecognized models can optionally
be probed with a tiny PDF.
"""
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "requests==2.31.0",
#     "anthropic>=0.7.0",
#     "openai>=1.0.0",
#     "google-genai>=0.1.0",
# ]
# ///

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


LITELLM_REGISTRY_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update available_models and pdf_support in config.json"
    )
    parser.add_argument(
        "--provider",
        help="Process only this provider (default: all providers in config.json)",
    )
    parser.add_argument(
        "--enable-probing",
        action="store_true",
        help="Probe unknown models with a tiny PDF to detect support (default: off)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written, don't modify config.json",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logging.debug("Args: %s", args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.2: Make it executable**

Run: `chmod +x update_models.py`

- [ ] **Step 2.3: Smoke-test the CLI**

Run: `./update_models.py --help`
Expected: argparse usage text listing the four flags above; exit 0.

Run: `./update_models.py --verbose`
Expected: a single DEBUG log line containing the parsed Namespace; exit 0.

- [ ] **Step 2.4: Commit**

```bash
git add update_models.py
git commit -m "feat(update-models): script skeleton with CLI parsing"
```

---

## Task 3: Implement and test API key resolution

**Files:**
- Modify: `update_models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_update_models.py`

The key files (`ANTHROPIC_API_KEY`, etc.) contain `export NAME=value` lines. The script must:
1. Try to read `<api_key_env>` as a filename in the project root and parse the export line
2. Fall back to `os.environ[<api_key_env>]`
3. Return None for anonymous (caller decides what to do)

- [ ] **Step 3.1: Create `tests/__init__.py`**

Create an empty file:

```python
```

(Empty contents are fine; this just marks the directory as a package.)

- [ ] **Step 3.2: Write the failing tests for `resolve_api_key`**

Create `tests/test_update_models.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3.3: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError or similar — `resolve_api_key` doesn't exist yet.

- [ ] **Step 3.4: Implement `resolve_api_key` in `update_models.py`**

Add this function after the constants (before `parse_args`):

```python
_EXPORT_LINE_RE = re.compile(
    r"""^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*?)\s*$"""
)


def resolve_api_key(env_name: str, project_root: str = PROJECT_ROOT) -> Optional[str]:
    """Resolve an API key by trying a same-named file in project_root, then the
    environment variable, then returning None.

    Files are expected to be in shell-sourceable form: `export NAME=value` or
    `NAME=value`. Surrounding single or double quotes are stripped.
    """
    file_path = os.path.join(project_root, env_name)
    if os.path.isfile(file_path):
        try:
            with open(file_path, "r") as f:
                for line in f:
                    m = _EXPORT_LINE_RE.match(line)
                    if not m or m.group("name") != env_name:
                        continue
                    value = m.group("value")
                    if (
                        len(value) >= 2
                        and value[0] == value[-1]
                        and value[0] in ("'", '"')
                    ):
                        value = value[1:-1]
                    return value
        except OSError as e:
            logging.warning("Could not read %s: %s", file_path, e)

    return os.environ.get(env_name)
```

- [ ] **Step 3.5: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all six `ResolveApiKeyTests` PASS.

- [ ] **Step 3.6: Commit**

```bash
git add update_models.py tests/__init__.py tests/test_update_models.py
git commit -m "feat(update-models): API key resolution with file/env fallback"
```

---

## Task 4: Implement and test LiteLLM registry fetch and lookup

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

The registry is a single JSON file. We fetch it once per run and look up each model id by trying both bare form and `{provider}/{model}` form. `supports_pdf_input` of `None` or missing means "unknown" — return `None` so the caller can decide whether to probe or default to `False`.

- [ ] **Step 4.1: Add tests for `fetch_litellm_registry` and `lookup_pdf_support`**

Append to `tests/test_update_models.py`:

```python
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
```

- [ ] **Step 4.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError — neither function exists yet.

- [ ] **Step 4.3: Implement `fetch_litellm_registry` and `lookup_pdf_support`**

Add to `update_models.py` after `resolve_api_key`:

```python
def fetch_litellm_registry(url: str = LITELLM_REGISTRY_URL) -> Dict[str, Any]:
    """Fetch the LiteLLM model registry JSON. Returns {} on any failure."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            logging.warning("LiteLLM registry was not a dict; treating as empty")
            return {}
        return data
    except (requests.RequestException, ValueError) as e:
        logging.warning("Could not fetch LiteLLM registry (%s); treating as empty", e)
        return {}


def lookup_pdf_support(
    registry: Dict[str, Any], model_id: str, provider: str
) -> Optional[bool]:
    """Look up `supports_pdf_input` for a model. Returns:
        True/False if the registry has a definitive answer.
        None if the model is unknown, or its entry has no/null pdf flag.
    """
    candidates = [model_id, f"{provider}/{model_id}"]
    for key in candidates:
        entry = registry.get(key)
        if not isinstance(entry, dict):
            continue
        flag = entry.get("supports_pdf_input")
        if isinstance(flag, bool):
            return flag
        return None
    return None
```

- [ ] **Step 4.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `FetchLiteLLMRegistryTests` and `LookupPdfSupportTests` PASS.

- [ ] **Step 4.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): LiteLLM registry fetch and pdf_support lookup"
```

---

## Task 5: Implement and test per-provider model filtering

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

Most providers' list-models endpoints return embeddings/TTS/image/etc. that we don't care about. We filter to chat-capable models by simple prefix rules. LMStudio is unfiltered (user-loaded models can be anything).

- [ ] **Step 5.1: Add tests for `filter_chat_models`**

Append to `tests/test_update_models.py`:

```python
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
```

- [ ] **Step 5.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on `filter_chat_models`.

- [ ] **Step 5.3: Implement `filter_chat_models`**

Add to `update_models.py`:

```python
_OPENAI_NON_CHAT_PREFIXES = (
    "text-embedding-",
    "whisper-",
    "tts-",
    "dall-e-",
    "omni-moderation-",
    "babbage-",
    "davinci-",
)


def filter_chat_models(provider: str, model_ids: List[str]) -> List[str]:
    """Keep only chat-capable model ids per provider rules. LMStudio and unknown
    providers are unfiltered.
    """
    def _norm(mid: str) -> str:
        # Some APIs return ids with a "models/" prefix (Google in particular)
        return mid[len("models/"):] if mid.startswith("models/") else mid

    if provider == "openai":
        kept = []
        for mid in model_ids:
            base = _norm(mid)
            if any(base.startswith(p) for p in _OPENAI_NON_CHAT_PREFIXES):
                continue
            if base.startswith("gpt-") or base.startswith("o"):
                kept.append(mid)
        return kept

    if provider == "anthropic":
        return [mid for mid in model_ids if _norm(mid).startswith("claude-")]

    if provider == "google":
        return [mid for mid in model_ids if _norm(mid).startswith("gemini-")]

    if provider == "xai":
        return [mid for mid in model_ids if _norm(mid).startswith("grok-")]

    # lmstudio + anything unrecognized: pass through
    return list(model_ids)
```

- [ ] **Step 5.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `FilterChatModelsTests` PASS.

- [ ] **Step 5.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): per-provider chat model filtering"
```

---

## Task 6: Implement and test atomic config write

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

Write to a temp file beside `config.json`, then `os.replace` to atomically swap. Indent with 2 spaces and trailing newline to match the existing file style.

- [ ] **Step 6.1: Add tests for `atomic_write_json`**

Append to `tests/test_update_models.py`:

```python
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
```

- [ ] **Step 6.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on `atomic_write_json`.

- [ ] **Step 6.3: Implement `atomic_write_json`**

Add to `update_models.py`:

```python
def atomic_write_json(path: str, data: Any) -> None:
    """Write `data` as pretty JSON to `path`, atomically.

    Stages to `path + ".tmp"`, then replaces the original. If serialization
    fails, the staging file is removed and the original is left untouched.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    except (TypeError, ValueError):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    os.replace(tmp_path, path)
```

- [ ] **Step 6.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `AtomicWriteJsonTests` PASS.

- [ ] **Step 6.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): atomic JSON config write"
```

---

## Task 7: Implement and test output formatting helpers

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

Three pure functions: header line, per-model line (success or error variant), and per-provider summary (✅ or ❌). The tests pin the exact emoji and surrounding format the user asked for.

- [ ] **Step 7.1: Add tests for the formatters**

Append to `tests/test_update_models.py`:

```python
class OutputFormattingTests(unittest.TestCase):
    def test_header(self):
        line = update_models.format_header("anthropic", "https://api.anthropic.com")
        self.assertEqual(
            line, "Probing provider anthropic at endpoint https://api.anthropic.com"
        )

    def test_model_line_success_true(self):
        line = update_models.format_model_line("claude-sonnet-4", supports_pdf=True)
        self.assertEqual(
            line, "\t✓  Model: claude-sonnet-4  [ Supports pdf: True ]"
        )

    def test_model_line_success_false(self):
        line = update_models.format_model_line("claude-haiku-3-5", supports_pdf=False)
        self.assertEqual(
            line, "\t✓  Model: claude-haiku-3-5  [ Supports pdf: False ]"
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
```

- [ ] **Step 7.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on the new formatters.

- [ ] **Step 7.3: Implement the formatters**

Add to `update_models.py`:

```python
GREEN_CHECK = "✅"
RED_X = "❌"
ASCII_CHECK = "✓"
ASCII_X = "✗"


def format_header(provider: str, endpoint: str) -> str:
    return f"Probing provider {provider} at endpoint {endpoint}"


def format_model_line(
    model: str,
    supports_pdf: Optional[bool] = None,
    error: Optional[str] = None,
) -> str:
    if error is not None:
        return f"\t{ASCII_X}  Model: {model}  [ Error: {error} ]"
    return f"\t{ASCII_CHECK}  Model: {model}  [ Supports pdf: {supports_pdf} ]"


def format_provider_summary(
    provider: str, success: bool, error: Optional[str] = None
) -> str:
    if success:
        return f"{GREEN_CHECK} {provider}  Model list updated"
    return f"{RED_X} {provider}  Error retrieving list of models: {error}"
```

- [ ] **Step 7.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `OutputFormattingTests` PASS.

- [ ] **Step 7.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): output formatting helpers"
```

---

## Task 8: Define ProbeResult dataclass and minimal PDF constant

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

Provider probe methods all return the same shape: did the probe succeed, does the model support PDF, what was the error if any. Hardcode a minimal valid PDF as base64 — the providers that accept PDF input only need the magic header and a parseable structure.

- [ ] **Step 8.1: Add tests for `MINIMAL_PDF_B64` and `ProbeResult`**

Append to `tests/test_update_models.py`:

```python
import base64


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


class ProbeResultTests(unittest.TestCase):
    def test_success_with_pdf(self):
        r = update_models.ProbeResult(succeeded=True, supports_pdf=True, error=None)
        self.assertTrue(r.succeeded)
        self.assertTrue(r.supports_pdf)
        self.assertIsNone(r.error)

    def test_failure_carries_error(self):
        r = update_models.ProbeResult(
            succeeded=False, supports_pdf=None, error="boom"
        )
        self.assertFalse(r.succeeded)
        self.assertEqual(r.error, "boom")
```

- [ ] **Step 8.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on `MINIMAL_PDF_B64` / `ProbeResult`.

- [ ] **Step 8.3: Add `MINIMAL_PDF_B64` and `ProbeResult` to `update_models.py`**

Add near the top constants:

```python
# Minimal valid 1-page PDF (612x792 / US Letter, no content stream).
# Generated once and pinned; verify integrity in tests.
MINIMAL_PDF_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiA"
    "wIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iag"
    "o8PC9UeXBlL1BhZ2UvTWVkaWFCb3hbMCAwIDYxMiA3OTJdL1BhcmVudCAyIDAgUi9SZXNvdXJjZ"
    "XM8PD4+Pj4KZW5kb2JqCnhyZWYKMCA0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAw"
    "MDAwMCBuIAowMDAwMDAwMDUyIDAwMDAwIG4gCjAwMDAwMDAwOTcgMDAwMDAgbiAKdHJhaWxlcgo"
    "8PC9TaXplIDQvUm9vdCAxIDAgUj4+CnN0YXJ0eHJlZgoxNTYKJSVFT0YK"
)
```

Add the dataclass alongside imports / after constants:

```python
@dataclass
class ProbeResult:
    """Outcome of a single PDF probe."""

    succeeded: bool
    supports_pdf: Optional[bool]
    error: Optional[str]
```

- [ ] **Step 8.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `MinimalPdfTests` and `ProbeResultTests` PASS.

- [ ] **Step 8.5: Verify the PDF is a valid, parseable file**

Run:
```bash
python3 -c "import base64, update_models, sys; \
sys.stdout.buffer.write(base64.b64decode(update_models.MINIMAL_PDF_B64))" > /tmp/probe.pdf
file /tmp/probe.pdf
```
Expected: `PDF document, version 1.4` (or similar). If `file` reports anything other than a PDF, the base64 string in the script needs to be regenerated.

- [ ] **Step 8.6: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): ProbeResult type and minimal PDF probe payload"
```

---

## Task 9: Implement and test LMStudio provider

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

LMStudio exposes an OpenAI-compatible HTTP API. List models with `GET <root>/models`. Probe with chat completion using `image_url: data:application/pdf;base64,...`. The endpoint configured is `.../v1/chat/completions`; derive root by replacing `/chat/completions` with `/models`.

- [ ] **Step 9.1: Add tests for endpoint derivation and the LMStudio client**

Append to `tests/test_update_models.py`:

```python
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


class LMStudioProviderTests(unittest.TestCase):
    def _make_client(self):
        return update_models.LMStudioProvider(
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
        fake_response.raise_for_status.side_effect = (
            update_models.requests.HTTPError("500 Server Error")
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
            result = client.probe_pdf("google/gemma-4-31b")
        self.assertTrue(result.succeeded)
        self.assertTrue(result.supports_pdf)
        self.assertIsNone(result.error)

    def test_probe_pdf_returns_false_on_input_rejection(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=400)
        fake_response.text = (
            '{"error":{"message":"This model does not support image inputs"}}'
        )
        fake_response.raise_for_status.side_effect = (
            update_models.requests.HTTPError("400 Bad Request")
        )
        with mock.patch(
            "update_models.requests.post", return_value=fake_response
        ):
            result = client.probe_pdf("text-only-model")
        self.assertTrue(result.succeeded)
        self.assertFalse(result.supports_pdf)
        self.assertIsNone(result.error)

    def test_probe_pdf_returns_error_on_other_failure(self):
        client = self._make_client()
        fake_response = mock.Mock(status_code=503)
        fake_response.text = "Service Unavailable"
        fake_response.raise_for_status.side_effect = (
            update_models.requests.HTTPError("503 Service Unavailable")
        )
        with mock.patch(
            "update_models.requests.post", return_value=fake_response
        ):
            result = client.probe_pdf("any-model")
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.supports_pdf)
        self.assertIn("503", result.error)
```

- [ ] **Step 9.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on `derive_models_url` / `LMStudioProvider`.

- [ ] **Step 9.3: Implement `derive_models_url` and the LMStudio client**

Add to `update_models.py`:

```python
_PDF_REJECTION_MARKERS = (
    "does not support image",
    "does not support file",
    "does not support pdf",
    "does not support document",
    "does not support multimodal",
    "image input is not supported",
    "file input is not supported",
    "unsupported content",
    "vision is not supported",
)


def derive_models_url(api_endpoint: str) -> str:
    """Given a chat-completions endpoint, return the corresponding /models URL."""
    suffix = "/chat/completions"
    if api_endpoint.endswith(suffix):
        return api_endpoint[: -len(suffix)] + "/models"
    return api_endpoint.rstrip("/") + "/models"


def _is_pdf_rejection(body_text: str) -> bool:
    lowered = (body_text or "").lower()
    return any(m in lowered for m in _PDF_REJECTION_MARKERS)


def _bearer_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _openai_compat_pdf_payload(model: str) -> Dict[str, Any]:
    return {
        "model": model,
        "max_tokens": 1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{MINIMAL_PDF_B64}"
                        },
                    },
                ],
            }
        ],
    }


class LMStudioProvider:
    name = "lmstudio"

    def __init__(self, api_endpoint: str, api_key: Optional[str]):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.models_url = derive_models_url(api_endpoint)

    def list_models(self) -> List[str]:
        response = requests.get(
            self.models_url, headers=_bearer_headers(self.api_key), timeout=15
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        return [item["id"] for item in items if isinstance(item, dict) and "id" in item]

    def probe_pdf(self, model: str) -> ProbeResult:
        try:
            response = requests.post(
                self.api_endpoint,
                headers=_bearer_headers(self.api_key),
                json=_openai_compat_pdf_payload(model),
                timeout=30,
            )
            response.raise_for_status()
            return ProbeResult(succeeded=True, supports_pdf=True, error=None)
        except requests.HTTPError as e:
            body = getattr(e.response, "text", "") if e.response is not None else ""
            if _is_pdf_rejection(body):
                return ProbeResult(succeeded=True, supports_pdf=False, error=None)
            status = (
                e.response.status_code if e.response is not None else "?"
            )
            return ProbeResult(
                succeeded=False,
                supports_pdf=None,
                error=f"HTTP {status} {body[:200]}".strip(),
            )
        except requests.RequestException as e:
            return ProbeResult(succeeded=False, supports_pdf=None, error=str(e))
```

- [ ] **Step 9.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `EndpointRootTests` and `LMStudioProviderTests` PASS.

- [ ] **Step 9.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): LMStudio provider with list+probe"
```

---

## Task 10: Implement and test XAI provider

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

XAI uses an OpenAI-compatible HTTP API. Same shape as LMStudio with a different endpoint and Authorization header. Subclass `LMStudioProvider` to keep the code DRY — the only difference is `name`.

- [ ] **Step 10.1: Add tests for `XAIProvider`**

Append to `tests/test_update_models.py`:

```python
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
```

- [ ] **Step 10.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on `XAIProvider`.

- [ ] **Step 10.3: Implement `XAIProvider`**

Add to `update_models.py` after `LMStudioProvider`:

```python
class XAIProvider(LMStudioProvider):
    name = "xai"
```

- [ ] **Step 10.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `XAIProviderTests` PASS.

- [ ] **Step 10.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): XAI provider (OpenAI-compatible)"
```

---

## Task 11: Implement Anthropic provider (no SDK unit tests; smoke test later)

**Files:**
- Modify: `update_models.py`

Uses the official `anthropic` SDK. List with `client.models.list()`. Probe with `client.messages.create(...)` using a `document` content block of `media_type: application/pdf`. We unit-test only the result-classification helper here; actual SDK calls are smoke-tested in Task 16.

- [ ] **Step 11.1: Implement `AnthropicProvider`**

Add to `update_models.py`:

```python
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_endpoint: str, api_key: Optional[str]):
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def _client(self):
        import anthropic

        # If api_key is None, the SDK will read ANTHROPIC_API_KEY from env;
        # if neither is set, the SDK raises on first call.
        return anthropic.Anthropic(api_key=self.api_key) if self.api_key else anthropic.Anthropic()

    def list_models(self) -> List[str]:
        client = self._client()
        ids: List[str] = []
        # SDK paginates automatically when iterating
        for entry in client.models.list():
            mid = getattr(entry, "id", None)
            if mid:
                ids.append(mid)
        return ids

    def probe_pdf(self, model: str) -> ProbeResult:
        try:
            client = self._client()
            client.messages.create(
                model=model,
                max_tokens=1,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": MINIMAL_PDF_B64,
                                },
                            },
                            {"type": "text", "text": "."},
                        ],
                    }
                ],
            )
            return ProbeResult(succeeded=True, supports_pdf=True, error=None)
        except Exception as e:  # noqa: BLE001 — SDK wraps a wide range of errors
            msg = str(e)
            if _is_pdf_rejection(msg) or (
                "document" in msg.lower() and "support" in msg.lower()
            ):
                return ProbeResult(succeeded=True, supports_pdf=False, error=None)
            return ProbeResult(succeeded=False, supports_pdf=None, error=msg[:300])
```

- [ ] **Step 11.2: Verify imports parse and basic instantiation works**

Run:
```bash
uv run --with anthropic python3 -c "import update_models; \
p = update_models.AnthropicProvider('https://api.anthropic.com', None); \
print(p.name)"
```
Expected: `anthropic`

(Real `list_models` / `probe_pdf` calls happen in the smoke test, Task 16.)

- [ ] **Step 11.3: Commit**

```bash
git add update_models.py
git commit -m "feat(update-models): Anthropic provider"
```

---

## Task 12: Implement OpenAI provider

**Files:**
- Modify: `update_models.py`

Uses the `openai` SDK. List with `client.models.list()`. Probe with `client.chat.completions.create(...)` using the same OpenAI-compatible PDF-as-image_url payload that scan_namer.py already uses for OpenAI in production — proves the path actually works against real OpenAI.

- [ ] **Step 12.1: Implement `OpenAIProvider`**

Add to `update_models.py`:

```python
class OpenAIProvider:
    name = "openai"

    def __init__(self, api_endpoint: str, api_key: Optional[str]):
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def _client(self):
        import openai

        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return openai.OpenAI(**kwargs)

    def list_models(self) -> List[str]:
        client = self._client()
        ids: List[str] = []
        for entry in client.models.list():
            mid = getattr(entry, "id", None)
            if mid:
                ids.append(mid)
        return ids

    def probe_pdf(self, model: str) -> ProbeResult:
        try:
            client = self._client()
            client.chat.completions.create(
                model=model,
                max_tokens=1,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        f"data:application/pdf;base64,"
                                        f"{MINIMAL_PDF_B64}"
                                    )
                                },
                            },
                        ],
                    }
                ],
            )
            return ProbeResult(succeeded=True, supports_pdf=True, error=None)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if _is_pdf_rejection(msg):
                return ProbeResult(succeeded=True, supports_pdf=False, error=None)
            return ProbeResult(succeeded=False, supports_pdf=None, error=msg[:300])
```

- [ ] **Step 12.2: Verify import + basic instantiation**

Run:
```bash
uv run --with openai python3 -c "import update_models; \
p = update_models.OpenAIProvider('https://api.openai.com/v1', None); \
print(p.name)"
```
Expected: `openai`

- [ ] **Step 12.3: Commit**

```bash
git add update_models.py
git commit -m "feat(update-models): OpenAI provider"
```

---

## Task 13: Implement Google provider

**Files:**
- Modify: `update_models.py`

Uses the `google-genai` SDK in API-key mode (the existing config has `GOOGLE_API_KEY`; Vertex AI mode requires a project_id and is out of scope for the model-listing script). List with `client.models.list()`. Probe with `client.models.generate_content(..., inline_data=application/pdf)`.

- [ ] **Step 13.1: Implement `GoogleProvider`**

Add to `update_models.py`:

```python
class GoogleProvider:
    name = "google"

    def __init__(self, api_endpoint: str, api_key: Optional[str]):
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def _client(self):
        from google import genai

        # API-key mode. If api_key is None, the SDK reads GEMINI_API_KEY /
        # GOOGLE_API_KEY from the environment.
        if self.api_key:
            return genai.Client(api_key=self.api_key)
        return genai.Client()

    def list_models(self) -> List[str]:
        client = self._client()
        ids: List[str] = []
        for entry in client.models.list():
            mid = getattr(entry, "name", None) or getattr(entry, "id", None)
            if mid:
                ids.append(mid)
        return ids

    def probe_pdf(self, model: str) -> ProbeResult:
        try:
            from google.genai import types

            client = self._client()
            pdf_bytes = base64.b64decode(MINIMAL_PDF_B64)
            client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    ".",
                ],
                config={"max_output_tokens": 1},
            )
            return ProbeResult(succeeded=True, supports_pdf=True, error=None)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if _is_pdf_rejection(msg):
                return ProbeResult(succeeded=True, supports_pdf=False, error=None)
            return ProbeResult(succeeded=False, supports_pdf=None, error=msg[:300])
```

Add `import base64` to the imports block at the top of `update_models.py` (it isn't yet — the skeleton only imported `json`, `os`, etc.).

- [ ] **Step 13.2: Verify import + basic instantiation**

Run:
```bash
uv run --with google-genai python3 -c "import update_models; \
p = update_models.GoogleProvider('https://generativelanguage.googleapis.com', None); \
print(p.name)"
```
Expected: `google`

- [ ] **Step 13.3: Commit**

```bash
git add update_models.py
git commit -m "feat(update-models): Google (Gen AI) provider"
```

---

## Task 14: Wire up orchestration and `main()`

**Files:**
- Modify: `update_models.py`
- Modify: `tests/test_update_models.py`

Tie the helpers and providers together. Per provider: build client → header → list → filter → for each model resolve pdf_support (registry → probe? → false) → write back into a deep-copied config → atomic write at the end.

- [ ] **Step 14.1: Add tests for `process_provider` (deterministic without network)**

Append to `tests/test_update_models.py`:

```python
class FakeProvider:
    """Test double matching the per-provider client interface."""

    name = "fake"

    def __init__(self, models, probe_results=None, list_error=None):
        self._models = models
        self._probe_results = probe_results or {}
        self._list_error = list_error

    def list_models(self):
        if self._list_error:
            raise self._list_error
        return list(self._models)

    def probe_pdf(self, model):
        return self._probe_results.get(
            model,
            update_models.ProbeResult(
                succeeded=True, supports_pdf=False, error=None
            ),
        )


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

    def test_probes_unknown_when_enabled(self):
        provider = FakeProvider(
            models=["claude-mystery"],
            probe_results={
                "claude-mystery": update_models.ProbeResult(
                    succeeded=True, supports_pdf=True, error=None
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
```

- [ ] **Step 14.2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: AttributeError on `process_provider` / `ProviderSummary`.

- [ ] **Step 14.3: Implement orchestration**

First, add `import copy` to the imports block at the top of `update_models.py` (alongside `argparse`, `json`, `logging`, etc.).

Then append the rest of the orchestration code:

```python
PROVIDER_CLASSES = {
    "lmstudio": LMStudioProvider,
    "xai": XAIProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
}


@dataclass
class ProviderSummary:
    provider: str
    success: bool
    error: Optional[str] = None


def build_client(provider_name: str, provider_block: Dict[str, Any]):
    cls = PROVIDER_CLASSES.get(provider_name)
    if cls is None:
        raise ValueError(f"No client class for provider {provider_name!r}")
    api_endpoint = provider_block.get("api_endpoint")
    if not api_endpoint:
        raise ValueError(
            f"Provider {provider_name!r} has no api_endpoint in config"
        )
    api_key_env = provider_block.get("api_key_env")
    api_key = resolve_api_key(api_key_env) if api_key_env else None
    return cls(api_endpoint=api_endpoint, api_key=api_key)


def process_provider(
    provider_name: str,
    provider_block: Dict[str, Any],
    client,
    registry: Dict[str, Any],
    enable_probing: bool,
) -> "tuple[Dict[str, Any], ProviderSummary]":
    """Drive one provider end-to-end. Returns (new_block, summary).

    On any failure to list models, returns the original block unchanged and a
    failed summary; otherwise rebuilds available_models and pdf_support from
    the provider's API response.
    """
    print(format_header(provider_name, provider_block.get("api_endpoint", "")))

    try:
        raw_ids = client.list_models()
    except Exception as e:  # noqa: BLE001
        msg = str(e) or e.__class__.__name__
        print(f"\t{ASCII_X}  Error: {msg}")
        summary = ProviderSummary(provider=provider_name, success=False, error=msg)
        return provider_block, summary

    filtered = sorted(set(filter_chat_models(provider_name, raw_ids)))

    new_pdf_support: Dict[str, bool] = {}
    kept_models: List[str] = []

    for mid in filtered:
        known = lookup_pdf_support(registry, mid, provider_name)
        if known is not None:
            print(format_model_line(mid, supports_pdf=known))
            kept_models.append(mid)
            new_pdf_support[mid] = known
            continue

        if enable_probing:
            result = client.probe_pdf(mid)
            if result.succeeded:
                print(format_model_line(mid, supports_pdf=bool(result.supports_pdf)))
                kept_models.append(mid)
                new_pdf_support[mid] = bool(result.supports_pdf)
            else:
                print(format_model_line(mid, error=result.error))
            continue

        # Unknown and probing disabled: include with False
        print(format_model_line(mid, supports_pdf=False))
        kept_models.append(mid)
        new_pdf_support[mid] = False

    new_block = copy.deepcopy(provider_block)
    new_block["available_models"] = kept_models
    new_block["pdf_support"] = new_pdf_support

    current_default = new_block.get("default_model")
    if current_default not in kept_models:
        new_block["default_model"] = kept_models[0] if kept_models else ""

    return new_block, ProviderSummary(provider=provider_name, success=True)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    providers = config.get("llm", {}).get("providers", {})
    if args.provider:
        if args.provider not in providers:
            print(
                f"{RED_X} {args.provider}  Error: provider not found in config.json"
            )
            return 2
        provider_names = [args.provider]
    else:
        provider_names = list(providers.keys())

    registry = fetch_litellm_registry()

    summaries: List[ProviderSummary] = []
    new_config = copy.deepcopy(config)

    for provider_name in provider_names:
        provider_block = providers[provider_name]
        try:
            client = build_client(provider_name, provider_block)
        except Exception as e:  # noqa: BLE001
            print(format_header(provider_name, provider_block.get("api_endpoint", "")))
            msg = str(e) or e.__class__.__name__
            summary = ProviderSummary(provider=provider_name, success=False, error=msg)
            summaries.append(summary)
            print(format_provider_summary(provider_name, success=False, error=msg))
            print()
            continue

        new_block, summary = process_provider(
            provider_name=provider_name,
            provider_block=provider_block,
            client=client,
            registry=registry,
            enable_probing=args.enable_probing,
        )
        summaries.append(summary)
        if summary.success:
            new_config["llm"]["providers"][provider_name] = new_block
            print(format_provider_summary(provider_name, success=True))
        else:
            print(
                format_provider_summary(
                    provider_name, success=False, error=summary.error
                )
            )
        print()

    if args.dry_run:
        logging.info("--dry-run: not writing config.json")
    else:
        any_success = any(s.success for s in summaries)
        if any_success:
            atomic_write_json(CONFIG_PATH, new_config)
        else:
            logging.warning("All providers failed; not writing config.json")

    # Exit non-zero if any provider failed
    return 0 if all(s.success for s in summaries) else 1
```

- [ ] **Step 14.4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_update_models -v`
Expected: all `ProcessProviderTests` PASS, plus all earlier tests.

- [ ] **Step 14.5: Commit**

```bash
git add update_models.py tests/test_update_models.py
git commit -m "feat(update-models): orchestration loop and main()"
```

---

## Task 15: Create `update-models` bash wrapper

**Files:**
- Create: `update-models`

Mirror the `scan-namer` wrapper conventions: check for `uv`, source the per-provider key files (so SDKs that read env vars directly still work for users who don't have a project-root file), exec the script with passthrough args.

- [ ] **Step 15.1: Create the wrapper**

```bash
#!/bin/bash
# Update Models wrapper - uses uv to run update_models.py with deps.

set -e

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Source any present per-provider key files so SDKs that fall through to env
# vars still work even when the user invokes update-models directly.
for keyfile in "$ROOT"/ANTHROPIC_API_KEY "$ROOT"/OPENAI_API_KEY \
               "$ROOT"/GOOGLE_API_KEY "$ROOT"/XAI_API_KEY \
               "$ROOT"/LMSTUDIO_API_KEY; do
    [ -f "$keyfile" ] && . "$keyfile"
done

exec uv run "$ROOT/update_models.py" "$@"
```

- [ ] **Step 15.2: Make it executable**

Run: `chmod +x update-models`

- [ ] **Step 15.3: Smoke-test wrapper invokes script**

Run: `./update-models --help`
Expected: same `argparse` help text as `./update_models.py --help`.

- [ ] **Step 15.4: Commit**

```bash
git add update-models
git commit -m "feat(update-models): bash wrapper analogous to scan-namer"
```

---

## Task 16: End-to-end smoke test

**Files:** none (verification only)

Validate the script against real provider APIs. Always use `--dry-run` first to inspect what would change. The user has at least LMStudio running locally and at least the Anthropic / OpenAI / Google / XAI keys present as files.

- [ ] **Step 16.1: Verify all unit tests still pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests PASS, no errors.

- [ ] **Step 16.2: Run against LMStudio (no network risk, free)**

Prerequisite: LMStudio is running locally on port 1234. If not, the user can start it; otherwise skip this step.

Run: `./update-models --provider lmstudio --dry-run --verbose`

Expected output shape:
```
Probing provider lmstudio at endpoint http://localhost:1234/v1/chat/completions
    ✓  Model: <whatever-is-loaded>  [ Supports pdf: False|True ]
✅ lmstudio  Model list updated
```

If a connection error appears with `--enable-probing` off, that is expected when LMStudio is not running — the provider summary will be ❌. Move on.

- [ ] **Step 16.3: Run against Anthropic, OpenAI, Google, XAI in dry-run**

Run: `./update-models --dry-run --verbose 2>&1 | tee /tmp/update-models-dry-run.log`

Expected:
- Header + per-model lines for each provider.
- Each provider ends with ✅ or ❌.
- `--dry-run: not writing config.json` near the end.
- `config.json` is unchanged: `git diff --stat config.json` shows no diff (or only the diff already present from Task 1).

If an SDK signature mismatch appears (e.g., `messages.create() got unexpected keyword 'document'`), check the provider's current SDK docs and patch the relevant probe payload in `update_models.py`. Re-run after fixing.

- [ ] **Step 16.4: Spot-check the `--enable-probing` path**

Pick one provider whose default-false branch will likely produce an unrecognized model (or use `--provider lmstudio` if running, since LMStudio always probes when LiteLLM doesn't know the model).

Run: `./update-models --provider lmstudio --enable-probing --dry-run --verbose`

Expected: at least one model line is followed by either `Supports pdf: True` or `Supports pdf: False` from a probe (visible because `--verbose` logs the request) rather than from the registry.

- [ ] **Step 16.5: Run for real (no `--dry-run`)**

Once dry-runs look right:

Run: `./update-models 2>&1 | tee /tmp/update-models-real.log`

Then: `git diff config.json | head -80`

Expected: changes to `available_models`, `pdf_support`, possibly `default_model` for at least one provider. No structural changes outside `llm.providers`.

- [ ] **Step 16.6: Final commit (config-only, if anything changed)**

If `git diff config.json` is non-empty:

```bash
git add config.json
git commit -m "chore: refresh available_models and pdf_support via update-models"
```

If it's empty, no commit is needed.

- [ ] **Step 16.7: Self-verify the script's exit codes**

Run: `./update-models --provider does-not-exist; echo "exit=$?"`
Expected: `❌ does-not-exist  Error: provider not found in config.json` and `exit=2`.

Run: `./update-models --dry-run; echo "exit=$?"`
Expected: exit `0` if every provider succeeded, exit `1` if any failed (e.g., a missing key for one provider).
