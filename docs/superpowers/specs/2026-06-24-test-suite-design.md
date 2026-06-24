# Design: Automated Test Suite + pyproject Migration

Date: 2026-06-24
Status: Approved

## Overview

`scan_namer.py` currently has no automated tests — CLAUDE.md documents "manual
testing with real Google Drive and LLM APIs." This adds a focused `pytest` unit
suite covering the pure business logic (the three features added on the
`cli-overrides-and-defaults` branch plus adjacent untested helpers), and migrates
the app from a single-file PEP 723 inline-metadata script to a `pyproject.toml`
project so a test runner has an environment in which it can `import scan_namer`.

Scope is deliberately limited to logic that runs without network or external
binaries. Google Drive API calls, LLM HTTP/SDK calls, and OCR/PDF-rasterization
paths (tesseract/poppler) remain manually tested.

## 1. Packaging Migration

The app is a single module, `scan_namer.py`, currently carrying PEP 723 inline
script metadata (the `# /// script ... # ///` block, lines 6-23). `uv run
scan_namer.py` uses that inline metadata to build an isolated environment. A test
runner invoked separately (`uv run pytest`) would NOT get those dependencies, so
`import scan_namer` would fail on the import-time libraries (Google API client,
PyPDF2, pytesseract, pdf2image, requests, python-dotenv).

### Changes
- **Create `pyproject.toml`** at the repo root:
  - `[project]`: `name = "scan-namer"`, `version = "0.1.0"`,
    `requires-python = ">=3.8"`, and `dependencies` copied **verbatim** from the
    current inline metadata:
    - `google-auth-oauthlib==1.4.0`
    - `google-auth==2.53.0`
    - `google-api-python-client==2.196.0`
    - `google-genai>=0.1.0`
    - `anthropic>=0.7.0`
    - `openai>=1.0.0`
    - `PyPDF2==3.0.1`
    - `requests>=2.31.0`
    - `python-dotenv==1.2.2`
    - `types-requests`
    - `pytesseract==0.3.13`
    - `pdf2image==1.17.0`
    - `Pillow>=10.0.0`
  - `[dependency-groups]`: `dev = ["pytest>=8"]`. uv syncs the `dev` group by
    default for `uv run`, so `uv run pytest` works with no extra flags.
  - `[tool.uv]`: `package = false` (this is an application, not an installable
    library; uv installs dependencies but does not build/install the project).
  - `[tool.pytest.ini_options]`: `pythonpath = ["."]` (so `import scan_namer`
    resolves from the repo root without installing the project) and
    `testpaths = ["tests"]`.
- **Remove the PEP 723 inline metadata block** (lines 6-23) from `scan_namer.py`.
  With no inline metadata present, `uv run scan_namer.py` resolves dependencies
  from `pyproject.toml`, so the `scan-namer` bash wrapper continues to work
  unchanged.
- `update_models.py` keeps its own inline metadata and is unaffected — `uv run
  update_models.py` still runs it in PEP 723 script mode.

### Verification
- `./scan-namer --list-providers` still works (wrapper resolves deps via pyproject).
- `uv run update_models.py --help` (or its no-arg/`--list` equivalent) still works.
- `uv run pytest` discovers and runs the suite.

## 2. Test Scope & Structure

All tests live under `tests/`, one file per cohesive unit. Every target is pure
logic reachable without network or external binaries.

| File | Unit(s) under test | Cases |
|---|---|---|
| `tests/test_secret_resolution.py` | `BaseLLMClient._parse_secret_file`, `_resolve_secret`, `_get_api_key` | `export VAR=val` form; bare `VAR=val`; single- and double-quote stripping; mismatched quotes NOT stripped; raw-key (first non-empty line); empty/whitespace-only file → None; superstring var name not matched (`VAR_BACKUP=` when resolving `VAR`); env value wins over file; file used when env unset/empty; both missing → `_get_api_key` exits |
| `tests/test_provider_model_resolution.py` | `LLMClientFactory.create_client` | unknown provider → SystemExit; model not in `available_models` → SystemExit; provider with no `default_model` → SystemExit; provider-only → provider's `default_model`; model-only mismatch vs default provider → SystemExit; explicit provider+valid model → that model; neither flag → config `llm.model`; empty `available_models` list → any model accepted |
| `tests/test_config_manager.py` | `ConfigManager.get`, `_get_env_override`, `_convert_env_value` | env override wins over file value; int conversion; float conversion; invalid int env → falls back to file value; bool conversion (`auto_select_first_folder`); string passthrough |
| `tests/test_drive_folder.py` | `GoogleDriveManager.resolve_folder` | unique case-insensitive match → folder id; zero matches → None (+ warning); multiple matches → None (+ warning) |
| `tests/test_filename.py` | `ScanNamer._clean_filename`, `ScanNamer._is_generic_filename` | clean: strip quotes/whitespace, drop `.pdf`, replace invalid chars with `_`, collapse repeats, trim leading/trailing `_`, truncate to `MAX_FILENAME_LENGTH`, empty/space → `""`; generic: default `raven_scan` match (case-insensitive), `GENERIC_FILENAME_PATTERNS` env override, non-match → False |
| `tests/test_pdf_and_url.py` | `PDFProcessor.should_extract`, `XAIClient._files_url` | should_extract: page_count below/at/above `max_pages_before_extraction`; _files_url: derives the Files API URL by replacing the `/chat/completions` suffix on the configured endpoint |

## 3. Test Techniques

Use only built-in `pytest` fixtures (`monkeypatch`, `tmp_path`) — no
`unittest.mock`, no `pytest-mock`, no network.

- **Bypass heavy constructors.** Classes whose `__init__` authenticates or builds
  SDK clients (`GoogleDriveManager`, `XAIClient`, `ScanNamer`) are instantiated
  with `object.__new__(Cls)`; the test sets only the attributes the method under
  test reads. Example: for `resolve_folder`, create a bare `GoogleDriveManager`
  and assign `inst.list_folders = lambda: [{"id": "...", "name": "..."}]`.
- **Control `APP_DIR`.** Secret-file tests do
  `monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))` and write key files
  into `tmp_path`, so tests never read from or pollute the repo directory.
- **Stub client classes for resolution success paths.** A recording stub
  capturing `(provider, model)` replaces the real client classes:
  `monkeypatch.setattr(scan_namer, "XAIClient", StubClient)` (and the other four).
  `create_client` then returns the stub, and the test asserts the captured
  provider/model. Error paths assert `pytest.raises(SystemExit)`.
- **Minimal config fixture.** A fixture writes a minimal but valid `config.json`
  (containing the required `llm`, `pdf`, `google_drive`, `logging` sections and a
  couple of providers with `available_models`/`default_model`) into `tmp_path` and
  returns `ConfigManager(str(path))`. Tests `monkeypatch.delenv` the `LLM_PROVIDER`
  / `LLM_MODEL` (and any other relevant) overrides so the host environment cannot
  perturb results.
- **Secret-resolution instances.** `_parse_secret_file` and `_resolve_secret` use
  no instance state beyond `self`, so a bare `object.__new__(BaseLLMClient)` is
  sufficient; `_get_api_key` additionally needs `inst.config` and `inst.provider`,
  which the test sets.

## 4. Documentation Updates

- **`CLAUDE.md`**: replace the "No automated testing framework - relies on manual
  testing" note (in the Development Notes / Testing Approach section) with: pure
  logic is unit-tested via `uv run pytest`; Google Drive and LLM integration, and
  OCR/PDF-rasterization paths, remain manually tested with `--dry-run`.
- **`README.md`**: add a short "Running tests" subsection documenting `uv run pytest`.

## 5. Non-Goals

- No mocked Google Drive API or LLM HTTP/SDK integration tests.
- No tests for OCR or PDF-rasterization paths requiring real `tesseract`/`poppler`.
- No CI configuration.
- No refactor of `scan_namer.py` beyond removing the inline metadata block (the
  units listed are already testable as-is).

## Files Touched

- Create: `pyproject.toml`
- Create: `tests/test_secret_resolution.py`, `tests/test_provider_model_resolution.py`,
  `tests/test_config_manager.py`, `tests/test_drive_folder.py`,
  `tests/test_filename.py`, `tests/test_pdf_and_url.py`
- Create (if needed): `tests/conftest.py` (shared `config.json` fixture)
- Modify: `scan_namer.py` (remove inline metadata block only)
- Modify: `CLAUDE.md`, `README.md`

## Manual Validation Plan

- `uv run pytest` → all tests pass, output pristine.
- `./scan-namer --list-providers` and `./scan-namer --help` → still work post-migration.
- `uv run update_models.py` (its list/help path) → still works (inline metadata intact).
