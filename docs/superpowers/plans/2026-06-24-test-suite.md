# Automated Test Suite + pyproject Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a focused `pytest` unit suite for `scan_namer.py`'s pure business logic, and migrate the app from PEP 723 inline-metadata to a `pyproject.toml` project so the test runner can import the module.

**Architecture:** Migrate dependencies into `pyproject.toml` (with a `dev` group carrying `pytest`), remove the inline-metadata block from `scan_namer.py`, then add `tests/` files that import `scan_namer` and exercise pure logic. Heavy constructors are bypassed with `object.__new__`; `monkeypatch`/`tmp_path` control `APP_DIR`, env vars, and a temp `config.json`; real client classes are replaced by a recording stub for resolution success paths. No network, no external binaries.

**Tech Stack:** Python 3.8+, uv, pytest (built-in `monkeypatch`/`tmp_path` fixtures only — no `unittest.mock`, no `pytest-mock`), ruff 0.9.6.

## Global Constraints

- These tests characterize EXISTING behavior: each test is expected to PASS against the current code. A test that fails reveals either a wrong assertion (fix the test) or a real bug (stop and report it — do not "fix" production code to match a guessed assertion).
- Tests use only `pytest` with built-in `monkeypatch` and `tmp_path`. No `unittest.mock`, no `pytest-mock`, no network calls, no real Google/LLM/tesseract/poppler.
- `pyproject.toml` `[project].dependencies` are copied VERBATIM from the current inline metadata (exact pins preserved).
- `[tool.uv] package = false`; `[dependency-groups] dev = ["pytest>=8"]`; `[tool.pytest.ini_options]` sets `pythonpath = ["."]` and `testpaths = ["tests"]`.
- The only production-code change is removing the inline-metadata block (lines 6-23) from `scan_namer.py`. Do not modify any other production logic.
- Test command: `uv run pytest`. Lint: `ruff check` must stay clean (tests included).
- Branch off `main` first; commit locally per task; do not push.

---

## File Structure

- `pyproject.toml` — project metadata, dependencies, dev group, pytest config.
- `scan_namer.py` — remove inline-metadata block only.
- `tests/conftest.py` — shared `MINIMAL_CONFIG`, `config`/`config_factory` fixtures, env-isolation autouse fixture, module import.
- `tests/test_import.py` — smoke test (import + `APP_DIR`).
- `tests/test_secret_resolution.py` — `BaseLLMClient` secret helpers.
- `tests/test_provider_model_resolution.py` — `LLMClientFactory.create_client`.
- `tests/test_config_manager.py` — `ConfigManager` env override/conversion.
- `tests/test_drive_folder.py` — `GoogleDriveManager.resolve_folder`.
- `tests/test_filename.py` — `ScanNamer._clean_filename` / `_is_generic_filename`.
- `tests/test_pdf_and_url.py` — `PDFProcessor.should_extract`, `XAIClient._files_url`.
- `CLAUDE.md`, `README.md` — doc updates.

---

## Task 0: Create working branch

**Files:** none (git only)

- [ ] **Step 1: Branch off main**

```bash
git checkout main
git checkout -b feat/test-suite
```

- [ ] **Step 2: Confirm clean start**

Run: `git status`
Expected: `On branch feat/test-suite`, clean tree.

---

## Task 1: pyproject migration + test harness foundation

Migrate packaging, remove inline metadata, and establish the test harness with a smoke test that proves `uv run pytest` can import the module.

**Files:**
- Create: `pyproject.toml`
- Modify: `scan_namer.py` (remove lines 6-23, the `# /// script ... # ///` block)
- Create: `tests/conftest.py`
- Create: `tests/test_import.py`

**Interfaces:**
- Produces: `tests/conftest.py` exporting (as fixtures) `config` → a `scan_namer.ConfigManager` built from `MINIMAL_CONFIG`; `config_factory` → `callable(cfg_dict) -> ConfigManager`; an autouse env-isolation fixture. `MINIMAL_CONFIG` is a module-level dict in `conftest.py`.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "scan-namer"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = [
    "google-auth-oauthlib==1.4.0",
    "google-auth==2.53.0",
    "google-api-python-client==2.196.0",
    "google-genai>=0.1.0",
    "anthropic>=0.7.0",
    "openai>=1.0.0",
    "PyPDF2==3.0.1",
    "requests>=2.31.0",
    "python-dotenv==1.2.2",
    "types-requests",
    "pytesseract==0.3.13",
    "pdf2image==1.17.0",
    "Pillow>=10.0.0",
]

[dependency-groups]
dev = ["pytest>=8"]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Remove the inline-metadata block from `scan_namer.py`**

Delete lines 6-23 — the entire block beginning with `# /// script` and ending with `# ///` (inclusive), including the dependency list between them. Leave the module docstring (lines 1-5) and the `import` lines that follow intact. After deletion, the file should go from the closing `"""` of the docstring straight to the blank line and `import argparse`.

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import json
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable even when pytest is invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scan_namer  # noqa: E402

# A minimal but schema-valid config used across tests. Providers cover the
# cases the resolution tests need: a normal provider with a model list and
# default, a provider missing default_model, and a provider with an empty
# model list (validation bypass).
MINIMAL_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-5.5",
        "max_tokens": 1000,
        "temperature": 0.3,
        "providers": {
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
                "available_models": ["gpt-5.5", "gpt-4o"],
                "default_model": "gpt-5.5",
            },
            "anthropic": {
                "api_key_env": "ANTHROPIC_API_KEY",
                "available_models": ["claude-sonnet-4-6"],
                "default_model": "claude-sonnet-4-6",
            },
            "nodefault": {
                "api_key_env": "NODEFAULT_API_KEY",
                "available_models": ["m1"],
            },
            "openlist": {
                "api_key_env": "OPENLIST_API_KEY",
                "available_models": [],
                "default_model": "any-model",
            },
        },
    },
    "pdf": {"max_pages_before_extraction": 3, "extraction_pages": 3},
    "ocr": {
        "enable_embedding": False,
        "min_text_per_page": 50,
        "language": "eng",
        "dpi": 300,
    },
    "google_drive": {
        "credentials_file": "credentials.json",
        "token_file": "token.json",
        "folder_name": "",
        "scopes": ["https://www.googleapis.com/auth/drive"],
    },
    "logging": {
        "level": "INFO",
        "format": "%(message)s",
        "date_format": "%Y",
        "file": "scan_namer.log",
    },
}


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Clear config-affecting env vars so the host environment can't perturb
    tests. Secret/API-key env vars are managed explicitly per-test."""
    for var in [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "MAX_FILENAME_LENGTH",
        "GENERIC_FILENAME_PATTERNS",
        "PDF_MAX_PAGES_BEFORE_EXTRACTION",
        "PDF_EXTRACTION_PAGES",
    ]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def config_factory(tmp_path):
    """Return a builder that writes a config dict to a temp file and returns a
    ConfigManager for it."""

    def _make(cfg_dict):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(cfg_dict))
        return scan_namer.ConfigManager(str(path))

    return _make


@pytest.fixture
def config(config_factory):
    """A ConfigManager built from a fresh copy of MINIMAL_CONFIG."""
    return config_factory(json.loads(json.dumps(MINIMAL_CONFIG)))
```

- [ ] **Step 4: Create `tests/test_import.py`**

```python
import scan_namer


def test_module_imports():
    assert hasattr(scan_namer, "ScanNamer")


def test_app_dir_is_set():
    assert isinstance(scan_namer.APP_DIR, str)
    assert scan_namer.APP_DIR
```

- [ ] **Step 5: Run the suite**

Run: `uv run pytest -q`
Expected: 2 tests pass, no errors, output pristine. (uv installs project deps + the `dev` group on first run; allow for an initial dependency-resolution delay.)

- [ ] **Step 6: Verify the app wrapper still works post-migration**

Run: `./scan-namer --list-providers`
Expected: prints the provider list (proves `uv run scan_namer.py` resolves deps from `pyproject.toml` with no inline metadata).

- [ ] **Step 7: Verify `update_models.py` is unaffected**

Run: `uv run update_models.py --help`
Expected: prints its help/usage (its own inline metadata still drives script-mode execution). If `--help` is not supported, run the script's documented no-op/list path; the point is that it still launches without a dependency error.

- [ ] **Step 8: Lint**

Run: `ruff check scan_namer.py tests/`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml scan_namer.py tests/conftest.py tests/test_import.py
git commit -m "build(scan_namer): migrate to pyproject and add pytest harness"
```

---

## Task 2: Secret resolution tests

**Files:**
- Create: `tests/test_secret_resolution.py`

**Interfaces:**
- Consumes: `scan_namer.BaseLLMClient` (`_parse_secret_file(path, env_var_name)`, `_resolve_secret(env_var_name)`, `_get_api_key()`), module global `scan_namer.APP_DIR`, `scan_namer.ConfigManager`.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests**

```python
import pytest

import scan_namer


def _client():
    """A BaseLLMClient with no __init__ side effects."""
    return object.__new__(scan_namer.BaseLLMClient)


def test_parse_export_form(tmp_path):
    f = tmp_path / "ANTHROPIC_API_KEY"
    f.write_text('export ANTHROPIC_API_KEY="sk-abc"\n')
    assert _client()._parse_secret_file(str(f), "ANTHROPIC_API_KEY") == "sk-abc"


def test_parse_bare_assignment(tmp_path):
    f = tmp_path / "ANTHROPIC_API_KEY"
    f.write_text("ANTHROPIC_API_KEY=sk-bare\n")
    assert _client()._parse_secret_file(str(f), "ANTHROPIC_API_KEY") == "sk-bare"


def test_parse_single_quotes_stripped(tmp_path):
    f = tmp_path / "K"
    f.write_text("K='sk-single'\n")
    assert _client()._parse_secret_file(str(f), "K") == "sk-single"


def test_parse_mismatched_quotes_not_stripped(tmp_path):
    f = tmp_path / "K"
    f.write_text("K='sk-x\"\n")
    # Opening ' and closing " do not match -> left intact.
    assert _client()._parse_secret_file(str(f), "K") == "'sk-x\""


def test_parse_raw_key_first_nonempty_line(tmp_path):
    f = tmp_path / "K"
    f.write_text("\n   \nsk-raw\nignored-second-line\n")
    assert _client()._parse_secret_file(str(f), "K") == "sk-raw"


def test_parse_empty_file_returns_none(tmp_path):
    f = tmp_path / "K"
    f.write_text("   \n\n")
    assert _client()._parse_secret_file(str(f), "K") is None


def test_parse_superstring_var_not_matched(tmp_path):
    f = tmp_path / "K"
    # A different variable whose name contains K as a prefix must not match;
    # the line is then treated as the raw first non-empty line.
    f.write_text("K_BACKUP=sk-other\n")
    assert _client()._parse_secret_file(str(f), "K") == "K_BACKUP=sk-other"


def test_resolve_env_wins_over_file(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    (tmp_path / "K").write_text("from-file\n")
    monkeypatch.setenv("K", "from-env")
    assert _client()._resolve_secret("K") == "from-env"


def test_resolve_uses_file_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("K", raising=False)
    (tmp_path / "K").write_text("from-file\n")
    assert _client()._resolve_secret("K") == "from-file"


def test_resolve_none_when_neither(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("K", raising=False)
    assert _client()._resolve_secret("K") is None


def test_get_api_key_exits_when_unresolved(tmp_path, monkeypatch, config):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = object.__new__(scan_namer.BaseLLMClient)
    client.config = config
    client.provider = "anthropic"
    with pytest.raises(SystemExit):
        client._get_api_key()


def test_get_api_key_resolves_from_file(tmp_path, monkeypatch, config):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "ANTHROPIC_API_KEY").write_text('export ANTHROPIC_API_KEY="sk-file"\n')
    client = object.__new__(scan_namer.BaseLLMClient)
    client.config = config
    client.provider = "anthropic"
    assert client._get_api_key() == "sk-file"
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_secret_resolution.py -q`
Expected: all pass. (If `test_parse_mismatched_quotes_not_stripped` or `test_parse_superstring_var_not_matched` fails, the parser behaves differently than documented — STOP and report, do not silently adjust the assertion to whatever the code emits without confirming it is correct behavior.)

- [ ] **Step 3: Lint**

Run: `ruff check tests/test_secret_resolution.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_secret_resolution.py
git commit -m "test(scan_namer): cover secret env/file resolution and parsing"
```

---

## Task 3: Provider/model resolution tests

**Files:**
- Create: `tests/test_provider_model_resolution.py`

**Interfaces:**
- Consumes: `scan_namer.LLMClientFactory.create_client(config, provider=None, model=None, max_tokens=None)`; the `config_factory` fixture; `scan_namer.MINIMAL_CONFIG` via conftest (imported as a fresh copy).
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests**

```python
import json

import pytest

import scan_namer
from conftest import MINIMAL_CONFIG


class StubClient:
    """Recording stand-in for the real provider clients."""

    def __init__(self, config, provider, model, max_tokens=None):
        self.config = config
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens


@pytest.fixture
def stub_clients(monkeypatch):
    for name in [
        "XAIClient",
        "AnthropicClient",
        "OpenAIClient",
        "GoogleClient",
        "LMStudioClient",
    ]:
        monkeypatch.setattr(scan_namer, name, StubClient)


@pytest.fixture
def cfg(config_factory):
    return config_factory(json.loads(json.dumps(MINIMAL_CONFIG)))


def test_unknown_provider_exits(cfg):
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(cfg, provider="bogus")


def test_model_not_in_list_exits(cfg, stub_clients):
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(
            cfg, provider="openai", model="not-a-real-model"
        )


def test_provider_without_default_model_exits(cfg, stub_clients):
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(cfg, provider="nodefault")


def test_provider_only_uses_provider_default(cfg, stub_clients):
    client = scan_namer.LLMClientFactory.create_client(cfg, provider="anthropic")
    assert client.provider == "anthropic"
    assert client.model == "claude-sonnet-4-6"


def test_model_only_mismatch_against_default_provider_exits(cfg, stub_clients):
    # No --provider: default provider is openai; an anthropic model is invalid.
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(cfg, model="claude-sonnet-4-6")


def test_explicit_provider_and_valid_model(cfg, stub_clients):
    client = scan_namer.LLMClientFactory.create_client(
        cfg, provider="openai", model="gpt-4o"
    )
    assert client.provider == "openai"
    assert client.model == "gpt-4o"


def test_neither_flag_uses_config_model(cfg, stub_clients):
    client = scan_namer.LLMClientFactory.create_client(cfg)
    assert client.provider == "openai"
    assert client.model == "gpt-5.5"


def test_empty_available_models_accepts_any(config_factory, stub_clients):
    # An empty available_models list bypasses model validation (any model is
    # accepted). Use a REAL provider name (openai) with its model list emptied,
    # so create_client's hardcoded provider dispatch reaches the stubbed client
    # rather than the unknown-provider exit branch.
    cfg_dict = json.loads(json.dumps(MINIMAL_CONFIG))
    cfg_dict["llm"]["providers"]["openai"]["available_models"] = []
    cfg = config_factory(cfg_dict)
    client = scan_namer.LLMClientFactory.create_client(
        cfg, provider="openai", model="whatever-model"
    )
    assert client.provider == "openai"
    assert client.model == "whatever-model"
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_provider_model_resolution.py -q`
Expected: all pass.

- [ ] **Step 3: Lint**

Run: `ruff check tests/test_provider_model_resolution.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_provider_model_resolution.py
git commit -m "test(scan_namer): cover provider/model resolution and validation"
```

---

## Task 4: ConfigManager tests

**Files:**
- Create: `tests/test_config_manager.py`

**Interfaces:**
- Consumes: `scan_namer.ConfigManager` (`get(key_path, default)`, `_convert_env_value(value, key_path)`); the `config` fixture.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests**

```python
import scan_namer  # noqa: F401  (kept for symmetry / future use)


def test_env_override_wins_for_string(config, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "xai")
    assert config.get("llm.provider") == "xai"


def test_env_override_string_model(config, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "some-model")
    assert config.get("llm.model") == "some-model"


def test_int_conversion(config, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "2500")
    value = config.get("llm.max_tokens")
    assert value == 2500
    assert isinstance(value, int)


def test_float_conversion(config, monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    value = config.get("llm.temperature")
    assert value == 0.7
    assert isinstance(value, float)


def test_invalid_int_falls_back_to_file_value(config, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "not-a-number")
    # Conversion fails -> override returns None -> file value (1000) is used.
    assert config.get("llm.max_tokens") == 1000


def test_no_override_returns_file_value(config):
    assert config.get("llm.provider") == "openai"


def test_convert_bool_true_values(config):
    assert config._convert_env_value("true", "auto_select_first_folder") is True
    assert config._convert_env_value("yes", "auto_select_first_folder") is True
    assert config._convert_env_value("1", "auto_select_first_folder") is True


def test_convert_bool_false_value(config):
    assert config._convert_env_value("false", "auto_select_first_folder") is False
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_config_manager.py -q`
Expected: all pass.

- [ ] **Step 3: Lint**

Run: `ruff check tests/test_config_manager.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_config_manager.py
git commit -m "test(scan_namer): cover ConfigManager env overrides and conversions"
```

---

## Task 5: Drive folder resolution tests

**Files:**
- Create: `tests/test_drive_folder.py`

**Interfaces:**
- Consumes: `scan_namer.GoogleDriveManager.resolve_folder(name)`, which calls `self.list_folders()` (returns a list of `{"id": ..., "name": ...}` dicts).
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests**

```python
import scan_namer


def _manager(folders):
    """A GoogleDriveManager with no auth side effects and a stubbed listing."""
    mgr = object.__new__(scan_namer.GoogleDriveManager)
    mgr.list_folders = lambda: folders
    return mgr


def test_unique_match_returns_id():
    mgr = _manager([{"id": "id-1", "name": "Scans"}, {"id": "id-2", "name": "Other"}])
    assert mgr.resolve_folder("Scans") == "id-1"


def test_match_is_case_insensitive():
    mgr = _manager([{"id": "id-1", "name": "Scans"}])
    assert mgr.resolve_folder("scANS") == "id-1"


def test_no_match_returns_none():
    mgr = _manager([{"id": "id-1", "name": "Scans"}])
    assert mgr.resolve_folder("Missing") is None


def test_multiple_matches_returns_none():
    mgr = _manager(
        [{"id": "id-1", "name": "Scans"}, {"id": "id-2", "name": "scans"}]
    )
    assert mgr.resolve_folder("Scans") is None
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_drive_folder.py -q`
Expected: all pass.

- [ ] **Step 3: Lint**

Run: `ruff check tests/test_drive_folder.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_drive_folder.py
git commit -m "test(scan_namer): cover Google Drive folder resolution"
```

---

## Task 6: Filename helper tests

**Files:**
- Create: `tests/test_filename.py`

**Interfaces:**
- Consumes: `scan_namer.ScanNamer._clean_filename(filename)`, `scan_namer.ScanNamer._is_generic_filename(filename)` (both read only env vars, no instance state).
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests**

```python
import scan_namer


def _scan_namer():
    return object.__new__(scan_namer.ScanNamer)


def test_clean_strips_quotes_invalid_chars_and_extension():
    sn = _scan_namer()
    assert sn._clean_filename('  "Hello: World/Test.pdf"  ') == "Hello_World_Test"


def test_clean_collapses_repeats_and_trims_underscores():
    sn = _scan_namer()
    assert sn._clean_filename("__a   b__") == "a_b"


def test_clean_truncates_to_max_length(monkeypatch):
    monkeypatch.setenv("MAX_FILENAME_LENGTH", "5")
    sn = _scan_namer()
    assert sn._clean_filename("abcdefghij") == "abcde"


def test_clean_empty_returns_empty_string():
    sn = _scan_namer()
    assert sn._clean_filename("   ") == ""


def test_generic_default_matches_raven_scan():
    sn = _scan_namer()
    assert sn._is_generic_filename("20240108_Raven_Scan.pdf") is True


def test_generic_non_match_returns_false():
    sn = _scan_namer()
    assert sn._is_generic_filename("Tax_Return_2023.pdf") is False


def test_generic_env_patterns_override(monkeypatch):
    monkeypatch.setenv("GENERIC_FILENAME_PATTERNS", "invoice,receipt")
    sn = _scan_namer()
    assert sn._is_generic_filename("Invoice_001.pdf") is True
    assert sn._is_generic_filename("20240108_Raven_Scan.pdf") is False
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_filename.py -q`
Expected: all pass.

- [ ] **Step 3: Lint**

Run: `ruff check tests/test_filename.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_filename.py
git commit -m "test(scan_namer): cover filename cleaning and generic-name detection"
```

---

## Task 7: PDF threshold + URL derivation tests

**Files:**
- Create: `tests/test_pdf_and_url.py`

**Interfaces:**
- Consumes: `scan_namer.PDFProcessor(config)` with `should_extract(page_count)`; `scan_namer.XAIClient._files_url()` (reads `self.endpoint`); the `config` fixture.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests**

```python
import scan_namer


def test_should_extract_below_threshold(config):
    proc = scan_namer.PDFProcessor(config)
    assert proc.should_extract(2) is False


def test_should_extract_at_threshold_is_false(config):
    proc = scan_namer.PDFProcessor(config)
    # max_pages_before_extraction == 3; only strictly greater triggers extraction.
    assert proc.should_extract(3) is False


def test_should_extract_above_threshold(config):
    proc = scan_namer.PDFProcessor(config)
    assert proc.should_extract(4) is True


def test_files_url_strips_chat_completions_suffix():
    client = object.__new__(scan_namer.XAIClient)
    client.endpoint = "https://api.x.ai/v1/chat/completions"
    assert client._files_url() == "https://api.x.ai/v1/files"


def test_files_url_without_suffix():
    client = object.__new__(scan_namer.XAIClient)
    client.endpoint = "https://api.x.ai/v1"
    assert client._files_url() == "https://api.x.ai/v1/files"
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_pdf_and_url.py -q`
Expected: all pass.

- [ ] **Step 3: Lint**

Run: `ruff check tests/test_pdf_and_url.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pdf_and_url.py
git commit -m "test(scan_namer): cover PDF extraction threshold and files-URL derivation"
```

---

## Task 8: Full-suite check + documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Interfaces:** none.

- [ ] **Step 1: Run the entire suite**

Run: `uv run pytest -q`
Expected: all tests across all files pass, output pristine (no warnings).

- [ ] **Step 2: Update `CLAUDE.md` testing note**

In the "Development Notes" → "Testing Approach" section, replace the bullet
`- No automated testing framework - relies on manual testing with real Google Drive and LLM APIs`
with:

```markdown
- Pure business logic is unit-tested with pytest: run `uv run pytest`
- Google Drive and LLM integration, and OCR/PDF-rasterization paths, are still verified manually (use `--dry-run`)
```

- [ ] **Step 3: Add a "Running tests" subsection to `README.md`**

Add a short subsection near the existing usage/development docs, matching the
file's existing heading levels and code-fence style:

```markdown
## Running tests

Unit tests cover the pure business logic (provider/model resolution, secret
resolution, Drive folder matching, filename cleaning, config overrides):

```bash
uv run pytest
```

Google Drive and LLM integration are not unit-tested; verify those manually
with `./scan-namer --dry-run`.
```

- [ ] **Step 4: Verify doc references**

Run: `rg -n "uv run pytest" README.md CLAUDE.md`
Expected: the command appears in both files.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs(scan_namer): document the pytest unit suite"
```

---

## Self-Review Notes

- **Spec coverage:**
  - §1 pyproject migration (verbatim deps, dev group, `package = false`, pytest config, inline-metadata removal, wrapper + update_models verification) → Task 1.
  - §2 test scope: secret resolution → Task 2; provider/model resolution → Task 3; ConfigManager → Task 4; resolve_folder → Task 5; filename helpers → Task 6; should_extract + _files_url → Task 7.
  - §3 techniques (object.__new__, APP_DIR monkeypatch, stub client classes, minimal config fixture, env isolation) → embedded across Tasks 1-7.
  - §4 doc updates → Task 8.
  - §5 non-goals respected (no mocked integration, no OCR/rasterization tests, no CI, no production refactor beyond metadata removal).
- **Type/name consistency:** `config`, `config_factory`, `MINIMAL_CONFIG`, and the autouse `_isolate_env` fixture are defined in Task 1's `conftest.py` and consumed by Tasks 2-7. `StubClient`/`stub_clients` are local to Task 3. `cfg` fixture in Task 3 mirrors the `config` fixture but is named distinctly to allow a fresh deep copy per test.
- **Characterization caveat** is called out in Global Constraints and in Task 2 Step 2: a failing assertion means investigate, never silently retrofit the test to buggy output.
- **No placeholders:** every test step contains complete, runnable code; every command has an expected result.
