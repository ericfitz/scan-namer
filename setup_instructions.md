# Setup Instructions for Scan Namer

## Prerequisites

1. **Python 3.8+** installed on your system
2. **uv** package manager installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
3. **Google Cloud Project** with Drive API enabled
4. **Grok API access** from X.AI

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

   **For X.AI (Grok):**
   ```
   XAI_API_KEY=your_xai_api_key_here
   ```

   **For Anthropic Claude:**
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

   **For OpenAI (GPT):**
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

   **For Google Vertex AI:**
   ```
   GOOGLE_PROJECT_ID=your_gcp_project_id
   GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
   ```

3. Optionally customize provider and model:
   ```
   LLM_PROVIDER=xai
   LLM_MODEL=grok-4-0709
   ```

### 4. Test the Setup

Run in dry-run mode to test without making changes:

```bash
./scan-namer --dry-run
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
- LLM configuration (model, temperature, max tokens)
- PDF processing settings (max pages before extraction)
- Logging preferences
- Generic filename patterns
- File paths and behavior

### Option 2: Configuration Files
- Edit `config.json` for persistent settings
- Edit `prompts.json` to customize the prompts sent to the LLM

**Note:** Environment variables in `.env` will override `config.json` settings.

## Command Line Options

- `--dry-run`: Test mode - analyzes one file but doesn't rename
- `--verbose`: Enable debug logging
- `--config FILE`: Use custom config file
- `--provider PROVIDER`: Choose LLM provider (xai, anthropic, openai, google)
- `--model MODEL`: Override the LLM model
- `--list-providers`: Show available providers
- `--list-models`: Show available models for all providers

All options are passed through to the Python script via the bash wrapper.

### Examples
```bash
./scan-namer --list-providers                 # Show available providers
./scan-namer --list-models                    # Show all models by provider
./scan-namer --provider anthropic --dry-run   # Test with Claude Sonnet 4
./scan-namer --provider anthropic --model claude-opus-4-20250514 --dry-run  # Test with Claude Opus 4
./scan-namer --provider openai --model gpt-4.1 --dry-run  # Test with GPT-4.1
./scan-namer --provider openai --model o3 --dry-run  # Test with o3 reasoning model
./scan-namer --provider google --model gemini-2.5-flash  # Use specific Google model
./scan-namer --model grok-4-0709  # Use specific model (auto-detects provider)
```

## Troubleshooting

- **Authentication issues**: Delete `token.json` to force re-authentication
- **API errors**: Check your API keys and rate limits
- **PDF processing errors**: Ensure PDFs are not corrupted or password-protected