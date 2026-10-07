# CLAUDE.md

Python tool that renames generically named scanned documents in Google Drive (e.g. `20240108_Raven_Scan.pdf`) based on their content, using an LLM. Supports X.AI, Anthropic, OpenAI, Google (google-genai SDK), and LM Studio (local, OpenAI-compatible); documents go to the model as extracted text or, for vision models, as the PDF itself.

## Commands

```bash
./scan-namer --dry-run                          # test without renaming (always use when testing)
./scan-namer --no-ocr --dry-run                 # force PDF-upload mode (vision models only)
./scan-namer --enable-ocr-embedding --dry-run   # test OCR detection and embedding
./scan-namer --list-models                      # models and their PDF support
./scan-namer --provider anthropic --model <model> --dry-run   # specific provider/model
./scan-namer --verbose                          # debug logging
./scan-namer                                    # normal operation (smart auto mode)
uv run pytest -q                                # unit tests (hermetic: no network or API keys)
```

## Workflow

1. List files under the configured Drive path; select generically named ones by configurable patterns
2. Download; with `--enable-ocr-embedding`, detect image-only PDFs and OCR them (Tesseract via pytesseract, pdf2image)
3. Get content to the LLM: extract text (shortening long documents to the first N pages) or, for image-only PDFs / `--no-ocr`, upload the PDF (base64) directly to a vision model. Text-extraction failure falls back to PDF upload automatically when the model supports it
4. Ask the LLM for a filename using prompts from `prompts.json`; validate and clean it for filesystem rules
5. Rename in Drive (skipped under `--dry-run`); upload a searchable PDF for OCR'd documents
6. Log with RFC3339 timestamps, token usage, and cost; clean up temp files even on errors. Drive operations retry with exponential backoff

PDF support is declared per model in `config.json` and validated early, with warnings for incompatible model/flag combinations.

## Architecture (`scan_namer.py`)

- **ConfigManager** — JSON config with environment-variable overrides
- **PromptManager** — loads and formats prompts from `prompts.json`
- **GoogleDriveManager** — OAuth, list/download/rename/update
- **PDFProcessor** — text extraction, page shortening, base64 encoding
- **BaseLLMClient** — abstract provider interface (template method); subclasses `XAIClient`, `AnthropicClient`, `OpenAIClient`, `GoogleClient`
- **LLMClientFactory** — builds the client for the configured provider
- **ScanNamer** — orchestrator

## Files

- `scan-namer` — bash wrapper; `scan_namer.py` — application; `update_models.py` — standalone PEP 723 script
- `pyproject.toml` — dependencies (managed by uv) and pytest config; `tests/` — unit suite
- `${XDG_CONFIG_HOME:-~/.config}/scan-namer/config.json` — provider settings, model lists, PDF-support flags (outside the repo; `--config` overrides; template `config.json.example`); `prompts.json` — LLM prompts, read from the script's directory
- `.env.example` — environment template; `credentials.json` — Google OAuth credentials (user-supplied; path set by `google_drive.credentials_file`, `~`/`$VAR` expanded); `token.json` — OAuth token cache (generated)
- `README.md`, `QUICKSTART.md`, `setup_instructions.md` — user docs

## Configuration notes

- **Environment variables override JSON config** — check `.env` first when debugging
- `LLM_PROVIDER` / `LLM_MODEL` override model selection; `GENERIC_FILENAME_PATTERNS` sets the generic-name patterns
- `PDF_MAX_PAGES_BEFORE_EXTRACTION` and `PDF_EXTRACTION_PAGES` control page shortening

## Testing

Done gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`

Live testing runs against real Drive and LLM APIs: always pass `--dry-run`, test text-extraction and PDF-upload modes separately, and check `--list-models` before testing a specific provider.

## Learned Preferences

- No pull requests in this repo: commit small fixes straight to main and merge feature branches/worktrees into main directly (take MODE=direct in deps:bump); ask before pushing unusually large or destructive work.
