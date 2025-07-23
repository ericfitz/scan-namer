# scan-namer
Automatically rename scanned documents in Google Drive using AI analysis - supports both text extraction and direct PDF upload to vision models

## overview
I have a Raven document scanner.  It scans my documents, performs OCR on them, and then saves them in Google drive as PDFs.

All the PDFs have generic names like "20240108_Raven_Scan.pdf".

I wanted to build a tool that would read the documents and rename them to something meaningful and indicative of the contents of the document.

## features
- **Multi-provider LLM support**: X.AI (Grok), Anthropic (Claude), OpenAI (GPT), Google (Gemini)
- **Smart PDF processing**: Text extraction with automatic fallback to direct PDF upload
- **Vision model support**: Handles image-based PDFs when text extraction fails or if preferred
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
# 1. Set up API keys
cp .env.example .env
# Edit .env with your API key (XAI_API_KEY, ANTHROPIC_API_KEY, etc.)

# 2. Set up Google Drive credentials
# Download credentials.json from Google Cloud Console

# 3. Test the setup
./scan-namer --dry-run

# 4. See available models (shows PDF support with * indicator)
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
./scan-namer --provider anthropic      # Use specific provider
./scan-namer --model claude-sonnet-4-20250514  # Use specific model
./scan-namer --verbose                 # Enable debug logging
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

### JSON Configuration Files
- `config.json`: Provider settings, model lists, PDF/logging config
- `prompts.json`: LLM prompt templates for document analysis

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
