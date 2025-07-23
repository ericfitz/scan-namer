# Setup Instructions for Scan Namer

## Prerequisites

1. **Python 3.8+** installed on your system
2. **uv** package manager installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
3. **Google Cloud Project** with Drive API enabled
4. **LLM API access** from your chosen provider:
   - X.AI (Grok) - supports PDF uploads with Grok-4 and Grok Vision
   - Anthropic (Claude) - supports PDF uploads with Claude 4, 3.5/3.7 Sonnet
   - OpenAI (GPT) - supports PDF uploads with GPT-4o, GPT-4o-mini, o3
   - Google (Gemini/Vertex AI) - supports PDF uploads with Gemini 2.5 series

## Setup Steps

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Dependencies are managed automatically by uv using inline metadata in the Python script.

### 2. Set up Google Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Drive API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Choose "Desktop application" as application type
6. Download the credentials JSON file
7. Rename it to `credentials.json` and place in project root

### 3. Set up API Credentials

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Choose your LLM provider and add the appropriate API key:

   **For X.AI (Grok) - PDF Support: ✓ Grok-4, Grok Vision:**
   ```
   XAI_API_KEY=your_xai_api_key_here
   LLM_PROVIDER=xai
   LLM_MODEL=grok-4-0709  # PDF capable
   ```

   **For Anthropic Claude - PDF Support: ✓ Claude 4, 3.5/3.7 Sonnet:**
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   LLM_PROVIDER=anthropic
   LLM_MODEL=claude-sonnet-4-20250514  # PDF capable (recommended)
   ```

   **For OpenAI (GPT) - PDF Support: ✓ GPT-4o, o3:**
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o  # PDF capable
   ```

   **For Google Vertex AI - PDF Support: ✓ Gemini 2.5 series:**
   ```
   GOOGLE_PROJECT_ID=your_gcp_project_id
   GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
   LLM_PROVIDER=google
   LLM_MODEL=gemini-2.5-flash  # PDF capable, fast & cost-effective
   ```

3. **Choose Your Strategy:**

   **Smart Auto Mode (Recommended)**: Works with any model, tries text first
   ```
   # No additional config needed - uses text extraction with PDF fallback
   ```

   **Vision-First Mode**: For image-heavy or poorly scanned documents
   ```
   # Add to .env for PDF-first processing:
   # Note: Requires PDF-capable model
   ```

   **Text-Only Mode**: For text-rich documents (cheaper/faster)
   ```
   # Use text-only models like:
   LLM_MODEL=gpt-4.1        # OpenAI text-only
   LLM_MODEL=grok-3         # X.AI text-only
   LLM_MODEL=gemini-2.0-flash  # Google text-only
   ```

### 4. Test the Setup

**Basic test** (recommended):
```bash
./scan-namer --dry-run
```

**Test PDF upload capability** (for image-based PDFs):
```bash
./scan-namer --no-ocr --dry-run  # Will warn if model doesn't support PDF
```

**Check your model's capabilities:**
```bash
./scan-namer --list-models  # Look for "PDF" indicator next to your model
```

### 5. Normal Usage

Once tested, run normally:

```bash
./scan-namer
```

## Configuration

You can customize the application in two ways:

### Option 1: Environment Variables (Recommended)
Edit `.env` file to override any settings:
- **LLM configuration**: Provider, model, temperature, max tokens
- **PDF processing**: Max pages before extraction, extraction page count
- **Document processing**: Generic filename patterns, max filename length
- **Logging**: Level, format, file location
- **Google Drive**: Credentials and token file paths

**Key PDF-related settings:**
```bash
# PDF Processing
PDF_MAX_PAGES_BEFORE_EXTRACTION=3  # Shorten docs larger than this
PDF_EXTRACTION_PAGES=3              # Pages to extract/upload

# Generic filename detection
GENERIC_FILENAME_PATTERNS=raven_scan,scan_,document_,img_
```

### Option 2: Configuration Files
- Edit `config.json` for persistent settings
- Edit `prompts.json` to customize the prompts sent to the LLM

**Note:** Environment variables in `.env` will override `config.json` settings.

## Command Line Options

### Core Options
- `--dry-run`: Test mode - analyzes one file but doesn't rename
- `--no-ocr`: Skip text extraction, upload PDFs directly (requires PDF-capable model)
- `--verbose`: Enable debug logging
- `--config FILE`: Use custom config file

### Model Selection
- `--provider PROVIDER`: Choose LLM provider (xai, anthropic, openai, google)
- `--model MODEL`: Override the LLM model
- `--list-providers`: Show available providers
- `--list-models`: Show available models (PDF-capable marked with "PDF")

### PDF Processing Modes
- **Default**: Try text extraction first, fallback to PDF upload
- **`--no-ocr`**: Force PDF upload (vision models only)
- **Text-only model**: Only processes text-extractable PDFs

All options are passed through to the Python script via the bash wrapper.

### Examples

**Discovery and Testing:**
```bash
./scan-namer --list-providers                 # Show available providers
./scan-namer --list-models                    # Show all models (PDF support indicated)
./scan-namer --dry-run                        # Test with default settings
```

**Provider-Specific Testing:**
```bash
./scan-namer --provider anthropic --dry-run   # Test with Claude Sonnet 4 (PDF capable)
./scan-namer --provider google --model gemini-2.5-flash --dry-run  # Test Gemini (PDF capable)
./scan-namer --provider openai --model gpt-4o --dry-run  # Test GPT-4o (PDF capable)
./scan-namer --provider xai --model grok-4-0709 --dry-run  # Test Grok-4 (PDF capable)
```

**PDF Upload Examples:**
```bash
./scan-namer --no-ocr --provider anthropic --model claude-sonnet-4-20250514  # Force PDF upload
./scan-namer --no-ocr --provider google --model gemini-2.5-flash             # Gemini PDF mode
./scan-namer --provider openai --model gpt-4.1 --dry-run                     # Text-only mode
```

**Production Usage:**
```bash
./scan-namer                                  # Smart auto mode (recommended)
./scan-namer --provider anthropic             # Use Claude with auto fallback
./scan-namer --no-ocr --provider google       # PDF-first with Gemini
```

## Troubleshooting

### Authentication Issues
- **Google Drive errors**: Delete `token.json` to force re-authentication
- **Missing credentials**: Ensure `credentials.json` is downloaded from Google Cloud Console
- **Permission denied**: Make sure `scan-namer` is executable (`chmod +x scan-namer`)

### API Issues
- **API key errors**: Check your API keys in `.env` file
- **Rate limiting**: Check provider rate limits and quotas
- **Model not found**: Use `--list-models` to see available models

### PDF Processing Issues
- **Text extraction fails**: Try `--no-ocr` with a PDF-capable model
- **PDF upload not working**: Ensure you're using a vision-enabled model (check for "PDF" in `--list-models`)
- **Large file errors**: Check PDF size limits for your provider
- **Corrupted PDFs**: Ensure PDFs are not password-protected or corrupted

### Model Selection Issues
- **"Model doesn't support PDF"**: Use `--list-models` to find PDF-capable models
- **No eligible files**: Check `GENERIC_FILENAME_PATTERNS` in `.env` 
- **Poor results**: Try different models or adjust prompts in `prompts.json`

### Performance Issues
- **Slow processing**: Use faster models like `gemini-2.5-flash` or `gpt-4o-mini`
- **High costs**: Use text extraction mode with cheaper models when possible
- **Memory issues**: Reduce `PDF_EXTRACTION_PAGES` in `.env`