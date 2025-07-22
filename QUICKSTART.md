# Quick Start Guide

Since uv is already installed, you can start using scan-namer right away!

## Setup Steps (5 minutes)

### 1. Set up API Keys
```bash
cp .env.example .env
# Edit .env and add API key for your chosen provider:
# XAI_API_KEY=... (X.AI)
# ANTHROPIC_API_KEY=... (Claude)
# OPENAI_API_KEY=... (OpenAI GPT)
# GOOGLE_PROJECT_ID=... (Google Vertex AI)
```

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
- Analyze the first generic-named PDF
- Show what it would rename it to (without actually renaming)

## Ready to go!
If the dry run works, remove `--dry-run` to start renaming files:
```bash
./scan-namer
```

## Troubleshooting
- **Permission errors**: Make sure `scan-namer` is executable (`chmod +x scan-namer`)
- **Missing credentials**: Download `credentials.json` from Google Cloud Console
- **API errors**: Check your API keys in `.env`
- **No eligible files**: Script only processes files with generic names (containing "raven_scan", "scan_", etc.)

## Options
- `--verbose`: See detailed debug output
- `--config custom.json`: Use different config file
- `--provider PROVIDER`: Choose LLM provider (xai, anthropic, openai, google)
- `--model MODEL_NAME`: Use specific LLM model
- `--list-providers`: Show available providers
- `--list-models`: Show available models

## Provider & Model Selection
```bash
./scan-namer --list-providers                 # See available providers
./scan-namer --list-models                    # See all models by provider
./scan-namer --provider anthropic --dry-run   # Test with Claude Sonnet 4
./scan-namer --provider xai --model grok-4-0709 --dry-run  # Test with Grok-4
./scan-namer --provider openai --model gpt-4.1 --dry-run  # Test with GPT-4.1
./scan-namer --provider google --model gemini-2.5-flash --dry-run  # Test with Gemini
```