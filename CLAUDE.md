# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based tool for automatically renaming scanned documents in Google Drive based on their content. The tool supports multiple LLM providers (X.AI, Anthropic, OpenAI, Google) with both text extraction and direct PDF upload capabilities for vision-enabled models. It generates meaningful filenames for generically named scanned documents like "20240108_Raven_Scan.pdf".

## Quick Development Commands

```bash
# Run in test mode (no actual renaming)
./scan-namer --dry-run

# Run with debug logging
./scan-namer --verbose

# Check available models and their capabilities
./scan-namer --list-models

# Test with specific provider/model
./scan-namer --provider anthropic --model claude-sonnet-4-20250514 --dry-run

# Test PDF upload mode (vision models only)
./scan-namer --no-ocr --dry-run

# Normal operation (requires setup)
./scan-namer
```

## Core Functionality

The script workflow:
- Lists files from a defined Google Drive path
- Identifies generically named documents using configurable patterns
- Downloads documents for analysis
- **OCR Detection**: If `--enable-ocr-embedding` is used, detects image-only PDFs and performs OCR
- **Text Extraction Mode**: Extracts text from PDFs, shortens large documents to first N pages
- **PDF Upload Mode**: For image-based PDFs or when `--no-ocr` flag is used, uploads PDF directly to vision models
- **Smart Fallback**: Automatically switches to PDF upload if text extraction fails
- Sends content to LLM with customizable prompts to suggest descriptive filenames
- Validates and cleans suggested filenames according to filesystem rules
- Renames documents in Google Drive with suggested titles (dry-run mode available)
- **OCR Embedding**: Creates and uploads searchable PDFs for image-only documents
- Comprehensive logging with RFC3339 timestamps and token usage tracking
- Cleans up temporary files (including shortened PDFs and OCR-processed files)

## Development Status

Core functionality is implemented in `scan_namer.py`. The script includes:
- **Multi-provider LLM support**: X.AI (Grok), Anthropic (Claude), OpenAI (GPT), Google (Gemini/Vertex AI with modern Gen AI SDK)
- **PDF processing**: Text extraction, page extraction, base64 encoding for API uploads
- **OCR capabilities**: Image-only PDF detection, Tesseract OCR integration, searchable PDF creation
- **Vision model integration**: Direct PDF upload support for image-based documents
- **Google Drive OAuth**: Authentication, file listing, downloading, renaming, updating
- **Flexible configuration**: JSON config with environment variable overrides
- **Comprehensive logging**: RFC3339 timestamps, token usage tracking, detailed operation logs
- **Model validation**: PDF capability checking, early warnings for incompatible model/flag combinations
- **Intelligent fallback**: Text extraction with automatic PDF upload fallback
- **Dry-run mode**: Testing without making actual changes

## Usage

Run with the bash wrapper:
```bash
./scan-namer --dry-run                    # Test mode
./scan-namer --no-ocr --dry-run          # Test PDF upload mode
./scan-namer --list-models               # Show models with PDF support
./scan-namer --provider anthropic --dry-run  # Test with specific provider
./scan-namer --verbose                   # Debug logging
./scan-namer                            # Normal operation (smart auto mode)
```

## Key Integrations

- **Google Drive API**: OAuth authentication, file listing, downloading, renaming, and updating
- **PDF Processing**: Text extraction, page extraction, base64 encoding, temporary file management
- **OCR Integration**: Tesseract OCR via pytesseract, pdf2image for PDF-to-image conversion
- **Multi-LLM Integration**: 
  - X.AI Grok API (vision models: Grok-4, Grok Vision Beta)
  - Anthropic Claude API (PDF support: Claude 4, 3.5/3.7 Sonnet)
  - OpenAI GPT API (vision models: GPT-4o, GPT-4o-mini, o3)
  - Google Vertex AI (vision models: Gemini 2.5 Pro/Flash/Flash-Lite)
- **Configuration Management**: JSON config with environment variable overrides
- **Logging**: RFC3339 formatted logs with token usage and cost tracking

## Code Architecture

The application follows object-oriented design with clear separation of concerns:

### Core Classes (scan_namer.py)
- **ConfigManager** (line 45): Handles JSON configuration and environment variable overrides
- **PromptManager** (line 148): Loads and formats LLM prompts from prompts.json
- **GoogleDriveManager** (line 175): OAuth authentication, file operations (list, download, rename)
- **PDFProcessor** (line 335): Text extraction, page shortening, base64 encoding for API uploads
- **BaseLLMClient** (line 423): Abstract base for LLM providers with standard interface
  - **XAIClient** (line 491): X.AI/Grok implementation with vision support
  - **AnthropicClient** (line 614): Claude implementation with PDF upload
  - **OpenAIClient** (line 721): GPT implementation with vision models
  - **GoogleClient** (line 834): Gemini implementation using google-genai SDK
- **LLMClientFactory** (line 953): Creates appropriate LLM client based on provider
- **ScanNamer** (line 1014): Main orchestrator coordinating all components

### Key Design Patterns
- **Factory Pattern**: LLMClientFactory for provider-agnostic client creation
- **Template Method**: BaseLLMClient defines interface, subclasses implement specifics
- **Configuration Management**: Centralized config with environment variable overrides
- **Separation of Concerns**: Each class handles one responsibility (PDF processing, Drive operations, LLM communication)

## Python Project Structure

Uses uv for package management with inline script metadata. Dependencies are declared in the Python script header and include:
- Google API libraries (Drive, OAuth, modern Google Gen AI SDK)
- LLM provider SDKs (anthropic, openai, requests for X.AI)
- PDF processing (PyPDF2)
- Utilities (python-dotenv, base64, logging)

All dependencies are automatically managed by uv when running the script. The Google integration uses the latest Google Gen AI SDK (google-genai) instead of the deprecated Vertex AI SDK, eliminating deprecation warnings.

## Project Files

- `scan_namer.py`: Main application with inline uv dependencies and multi-provider LLM support
- `scan-namer`: Bash wrapper script for easy execution
- `config.json`: Application configuration including provider settings, model lists, PDF support flags
- `prompts.json`: LLM prompt templates for document analysis
- `.env.example`: Template for environment variables with PDF capability indicators
- `credentials.json`: Google OAuth credentials (user must provide)
- `token.json`: Google OAuth token cache (generated automatically)
- `README.md`: Comprehensive documentation with feature overview
- `QUICKSTART.md`: Quick start guide with PDF mode examples
- `setup_instructions.md`: Detailed setup with provider-specific instructions

## Commands for Development

### Testing & Validation
- `./scan-namer --dry-run`: Test functionality without making changes
- `./scan-namer --no-ocr --dry-run`: Test PDF upload mode
- `./scan-namer --enable-ocr-embedding --dry-run`: Test OCR detection and processing
- `./scan-namer --list-models`: Check model PDF capabilities
- `./scan-namer --verbose`: Enable debug logging

### Provider Testing
- `./scan-namer --provider anthropic --model claude-sonnet-4-20250514 --dry-run`: Test Claude PDF support
- `./scan-namer --provider google --model gemini-2.5-flash --dry-run`: Test Gemini vision
- `./scan-namer --provider openai --model gpt-4o --dry-run`: Test GPT-4o vision
- `./scan-namer --provider xai --model grok-4-0709 --dry-run`: Test Grok-4 vision

### Configuration Testing
- Test with different models to validate PDF support flags
- Test environment variable overrides
- Test with various PDF types (text-rich vs image-heavy)

## Development Notes

### Testing Approach
- No automated testing framework - relies on manual testing with real Google Drive and LLM APIs
- Always use `--dry-run` flag when testing to avoid unintended file renames
- Test text extraction and PDF upload modes separately
- Verify model capabilities with `--list-models` before testing specific providers

### Key Configuration Points
- **Environment variables always override JSON config** - check `.env` first when debugging
- **Generic filename patterns** are configurable via `GENERIC_FILENAME_PATTERNS` env var
- **PDF processing thresholds** controlled by `PDF_MAX_PAGES_BEFORE_EXTRACTION` and `PDF_EXTRACTION_PAGES`
- **Model selection** can be overridden with `LLM_PROVIDER` and `LLM_MODEL` env vars

### Error Handling Patterns
- Text extraction failures automatically trigger PDF upload fallback (if model supports it)
- Model capability validation happens early with clear warnings
- Temporary files are cleaned up even on errors
- Google Drive operations use exponential backoff for retries

### Working with LLM Providers
- Each provider client inherits from BaseLLMClient for consistent interface
- PDF support is explicitly declared in config.json per model
- Vision models require base64-encoded PDF content
- Token usage and costs are logged for all providers