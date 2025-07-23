# Quick Start Guide

Since uv is already installed, you can start using scan-namer right away!

This tool automatically renames scanned documents using AI analysis. It supports both text extraction and direct PDF upload to vision models for image-based documents.

## Setup Steps (5 minutes)

### 1. Set up API Keys
```bash
cp .env.example .env
# Edit .env and add API key for your chosen provider:
# XAI_API_KEY=... (X.AI Grok)
# ANTHROPIC_API_KEY=... (Claude)
# OPENAI_API_KEY=... (OpenAI GPT)
# GOOGLE_API_KEY=... (Google Gemini)
```

**💡 Tip**: Choose a provider with PDF-capable models for best results with image-based scans:
- **Anthropic Claude 4/3.5/3.7 Sonnet** (recommended for quality)
- **Google Gemini 2.5 Flash** (recommended for speed/cost)
- **OpenAI GPT-4o** (good balance)
- **X.AI Grok-4** (latest capabilities)

### 2. Set up Google Drive API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select project → Enable Google Drive API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download as `credentials.json` in this directory

### 3. Test the setup
```bash
./scan-namer --dry-run
```

This will:
- Authenticate with Google Drive (opens browser)
- Let you select a folder
- Analyze the first generic-named PDF using text extraction
- Show what it would rename it to (without actually renaming)
- If text extraction fails, automatically try PDF upload (if model supports it)

## Ready to go!
If the dry run works, remove `--dry-run` to start renaming files:
```bash
./scan-namer
```

## Troubleshooting
- **Permission errors**: Make sure `scan-namer` is executable (`chmod +x scan-namer`)
- **Missing credentials**: Download `credentials.json` from Google Cloud Console
- **API errors**: Check your API keys in `.env`
- **No eligible files**: Script only processes files with generic names (containing "raven_scan" by default)
- **PDF upload fails**: Ensure you're using a vision-enabled model (check `--list-models` for "PDF" indicator)
- **Text extraction fails**: Try `--no-ocr` flag with a PDF-capable model
- **Model not supported**: Use `--list-models` to see which models support PDF uploads

## Key Options
- `--dry-run`: Test mode - analyze without renaming
- `--no-ocr`: Skip text extraction, upload PDFs directly (requires vision model)
- `--tokens N`: Override max tokens per request (e.g., `--tokens 3000`)
- `--verbose`: See detailed debug output
- `--provider PROVIDER`: Choose LLM provider (xai, anthropic, openai, google)
- `--model MODEL_NAME`: Use specific LLM model
- `--list-providers`: Show available providers
- `--list-models`: Show available models (PDF-capable marked with "PDF")
- `--config custom.json`: Use different config file

## Provider & Model Selection
```bash
./scan-namer --list-providers                 # See available providers
./scan-namer --list-models                    # See all models (PDF support shown)
./scan-namer --provider anthropic --dry-run   # Test with Claude Sonnet 4
./scan-namer --provider xai --model grok-4-0709 --dry-run  # Test with Grok-4
./scan-namer --provider openai --model gpt-4o --dry-run  # Test with GPT-4o (PDF capable)
./scan-namer --provider google --model gemini-2.5-flash --dry-run  # Test with Gemini
```

## PDF Upload Mode
For image-based PDFs or when text extraction fails:
```bash
# Force PDF upload (skips text extraction)
./scan-namer --no-ocr --provider anthropic --model claude-sonnet-4-20250514

# PDF upload with Google Gemini (fast & cost-effective)
./scan-namer --no-ocr --provider google --model gemini-2.5-flash

# PDF upload with OpenAI GPT-4o
./scan-namer --no-ocr --provider openai --model gpt-4o

# Use more tokens for detailed analysis
./scan-namer --tokens 4000 --provider anthropic --model claude-sonnet-4-20250514
```

**⚠️ Note**: PDF upload requires vision-enabled models. The system will warn you if you try to use `--no-ocr` with a text-only model.

## Workflow Modes

### 1. **Smart Auto Mode** (Recommended)
```bash
./scan-namer  # Tries text extraction first, falls back to PDF upload
```
- Attempts text extraction from PDFs
- Automatically uploads PDF to vision model if text extraction fails
- Works with any provider/model combination

### 2. **Text-Only Mode**
```bash
./scan-namer --provider openai --model gpt-4.1  # Text-only model
```
- Only processes PDFs with extractable text
- Skips image-based or corrupted PDFs
- Faster and cheaper for text-rich documents

### 3. **Vision-Only Mode**
```bash
./scan-namer --no-ocr --provider anthropic --model claude-sonnet-4-20250514
```
- Skips text extraction entirely
- Uploads PDFs directly to vision models
- Best for image-heavy or poorly scanned documents