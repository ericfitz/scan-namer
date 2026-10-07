# scan-namer
Automatically rename scanned documents in Google Drive using AI analysis - supports both text extraction and direct PDF upload to vision models

## overview
I have a Raven document scanner.  It scans my documents, performs OCR on them, and then saves them in Google drive as PDFs.

All the PDFs have generic names like "20240108_Raven_Scan.pdf".

I wanted to build a tool that would read the documents and rename them to something meaningful and indicative of the contents of the document.

## features
- **Multi-provider LLM support**: X.AI (Grok), Anthropic (Claude), OpenAI (GPT), Google (Gemini), LM Studio (local, OpenAI-compatible)
- **Smart PDF processing**: Text extraction with automatic fallback to direct PDF upload
- **Vision model support**: Handles image-based PDFs when text extraction fails or if preferred
- **OCR embedding**: Automatically detects image-only PDFs and adds searchable text layer
- **Flexible configuration**: Environment variables override JSON config
- **Dry-run mode**: Test functionality without making changes
- **Intelligent file detection**: Configurable patterns for generic filenames
- **Comprehensive logging**: RFC3339 timestamps with detailed operation tracking

## script
This script does the following:

- Lists the files from a defined path in Google Drive
- For each file, checks if it has a "generic" document name using configurable heuristics
- If a generic file is found:
    - Downloads the document
    - **Text extraction approach**: Attempts to extract text from the PDF
        - If document has >N pages, extracts first N pages (default: 3)
        - Sends extracted text to LLM for analysis
    - **PDF upload fallback**: If text extraction fails or `--no-ocr` flag is used:
        - Uploads PDF directly to vision-enabled LLM models
        - Uses shortened PDF (first N pages) for large documents
        - Supports Claude, Gemini 2.5, GPT-4o, Grok-4, and other vision models
    - LLM suggests a new descriptive filename following naming conventions
    - **Dry run mode**: Shows suggested names without renaming
    - **Normal mode**: Renames the document in Google Drive and logs activity
    - Cleans up temporary files

## quick start
```bash
# 0. Install system dependencies (see setup_instructions.md for details)
#    macOS:        brew install poppler tesseract
#    Debian/Ubuntu: sudo apt-get install poppler-utils tesseract-ocr
#    poppler is required for image-based PDFs and any vision-only model;
#    tesseract is required only with --enable-ocr-embedding.

# 1. Set up API keys
cp .env.example .env
# Edit .env with your API key (XAI_API_KEY, ANTHROPIC_API_KEY, etc.)

# 2. Create the config file (edit it afterwards for your setup)
D="${XDG_CONFIG_HOME:-$HOME/.config}/scan-namer"; mkdir -p "$D" && cp config.json.example "$D/config.json"

# 3. Set up Google Drive credentials
# Download credentials.json from Google Cloud Console into this directory, or
# store it elsewhere and point google_drive.credentials_file at it (see below)

# 4. Test the setup
./scan-namer --dry-run

# 5. See available models (shows PDF support with * indicator)
./scan-namer --list-models

# 5. Use with PDF upload for image-based PDFs
./scan-namer --no-ocr --provider anthropic --model claude-sonnet-4-20250514
```

## model support

### PDF Upload Capable Models
- **Anthropic**: Claude 4 models, Claude 3.5 Sonnet, Claude 3.7 Sonnet
- **Google**: Gemini 2.5 Pro/Flash/Flash-Lite (vision models)
- **OpenAI**: GPT-4o, GPT-4o-mini, o3 reasoning model
- **X.AI**: Grok-4, Grok Vision Beta

### Text-Only Models
- **Anthropic**: Claude 3.5 Haiku
- **Google**: Gemini 2.0 Flash/Flash-Lite
- **OpenAI**: GPT-4.1 series, o4-mini
- **X.AI**: Grok-3, Grok-3-mini, Grok-beta

## command line options
```bash
./scan-namer --help                    # Show all options
./scan-namer --list-providers          # List available LLM providers
./scan-namer --list-models             # Show models with PDF support indicators
./scan-namer --dry-run                 # Test mode (no actual renaming)
./scan-namer --no-ocr                  # Skip text extraction, upload PDFs directly
./scan-namer --enable-ocr-embedding    # Enable OCR for image-only PDFs
./scan-namer --provider anthropic      # Use specific provider
./scan-namer --model claude-sonnet-4-20250514  # Use specific model
./scan-namer --folder "My Scans"       # Use named Google Drive root folder
./scan-namer --verbose                 # Enable debug logging
```

### Google Drive folder selection

By default, scan-namer presents an interactive menu to choose which Google Drive folder to scan. You can skip the menu in two ways:

- **`--folder NAME`** (CLI flag): specifies the folder name at runtime. A case-insensitive match against root-level Drive folders is performed; if exactly one folder matches, the menu is skipped. If no folder matches, or if more than one folder matches, a warning is shown and the interactive menu is displayed instead.
- **`google_drive.folder_name`** (config key in `config.json`): sets a persistent default folder name. `--folder` overrides this value when both are present. Leave the key empty (the default) to always show the menu.

```json
{
  "google_drive": {
    "folder_name": "My Scans"
  }
}
```

## testing

A pytest unit suite covers secret resolution, provider/model resolution, config loading, Drive folder selection, filename validation, and PDF/URL helpers. No network access or API keys are needed.

```bash
uv run pytest -q   # fast; no network or API keys required
```

## alternative uses
With small modifications, you could point this to any document store you want, and let it rename your documents more meaningfully. The multi-provider LLM support makes it adaptable to different AI services and use cases.

## configuration

The application supports flexible configuration through:

### Environment Variables (Recommended)
Edit `.env` file to override any setting:
```bash
# API Keys
XAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_PROJECT_ID=your_project_id

# Model Selection
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514

# PDF Processing
PDF_MAX_PAGES_BEFORE_EXTRACTION=3
PDF_EXTRACTION_PAGES=3

# Behavior
GENERIC_FILENAME_PATTERNS=raven_scan,scan_,document_
```

#### Per-provider key settings

Each provider block in `config.json` (`llm.providers.<provider>`) takes two key settings:

- `api_key_env`: the name of the environment variable that holds the provider's API key. The shipped defaults are `XAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` and `LMSTUDIO_API_KEY`; change it to read the key from a different variable.
- `api_key_file` (optional): an absolute path to a file holding the key. `~` and `$VAR` / `${VAR}` references are expanded. A relative path, an empty value or a reference to an unset variable is a configuration error. The file may hold the raw key or one shell assignment line, with an optional `export` or `source` prefix and optional quotes:

```
export ANTHROPIC_API_KEY='your-anthropic-key'
source ANTHROPIC_API_KEY="your-anthropic-key"
ANTHROPIC_API_KEY=your-anthropic-key
```

```json
"anthropic": {
  "api_key_env": "ANTHROPIC_API_KEY",
  "api_key_file": "~/.keys/ANTHROPIC_API_KEY"
}
```

The environment wins: if the variable named by `api_key_env` is set, scan-namer uses it and ignores the file. Otherwise, when `api_key_file` is set and readable, scan-namer loads its key into that variable and uses it. An assignment of that variable wins; a file with a single assignment of another upper-case name is also accepted. If the file is missing, holds no key, or assigns several other variables, scan-namer logs a warning and falls back to the secret file below. The path is validated even when the environment variable is set. `update_models.py` follows the same order (environment, `api_key_file`, then the app-directory file) without changing the environment.

#### Secret-file fallback

If a provider API key (or `GOOGLE_PROJECT_ID`) is not set in the environment, scan-namer also looks for a file named **exactly** like the environment variable (e.g. `ANTHROPIC_API_KEY`) in the application directory. The file may contain the raw key value, or a shell assignment line; the `export` (or `source`) keyword and surrounding quotes are optional. Both of the following forms are accepted:

```
export ANTHROPIC_API_KEY="your-anthropic-key"
ANTHROPIC_API_KEY=your-anthropic-key
```

The environment variable always takes precedence over the file. This fallback applies to each provider's API-key variable (`XAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`) and to `GOOGLE_PROJECT_ID`.

### JSON Configuration Files
- `$XDG_CONFIG_HOME/scan-namer/config.json` (`~/.config/scan-namer/config.json` when `XDG_CONFIG_HOME` is unset): Provider settings, model lists, PDF/logging config. Not in the repo: copy `config.json.example` there to create it, or point `--config` at another file. `scan-namer` and `update-models` run from any directory
- `prompts.json`: LLM prompt templates for document analysis
- `$XDG_STATE_HOME/scan-namer/scan_namer.log` (`~/.local/state/scan-namer/scan_namer.log` when `XDG_STATE_HOME` is unset): run log, rotated at 5 MB with 3 backups (`logging.file` / `LOG_FILE` override it)

**Note**: Environment variables override JSON configuration.

## ai-generated code
For this project:
- A human did:
    - specification and requirements
    - testing and validation
    - debugging and troubleshooting
    - documentation review and revision
    - code review and refinements
    - prompt engineering and tuning

- Claude 4 by Anthropic did:
    - initial coding and implementation
    - multi-provider LLM integration
    - documentation generation
