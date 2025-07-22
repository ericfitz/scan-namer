# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based tool for automatically renaming scanned documents in Google Drive based on their content. The tool uses OCR and LLM analysis (currently Grok) to generate meaningful filenames for generically named scanned documents like "20240108_Raven_Scan.pdf".

## Core Functionality

The planned script workflow:
- Lists files from a defined Google Drive path
- Identifies generically named documents 
- Downloads documents for analysis
- Extracts first N pages if document is too large
- Sends content to LLM with prompt to suggest descriptive titles
- Renames documents in Google Drive with suggested titles
- Logs activity and cleans up temporary files

## Development Status

Core functionality is implemented in `scan_namer.py`. The script includes:
- Google Drive OAuth authentication and file operations
- PDF processing with page extraction
- Grok API integration for document analysis
- Configuration management and logging
- Dry-run mode for testing

## Usage

Run with the bash wrapper:
```bash
./scan-namer --dry-run    # Test mode
./scan-namer --verbose    # Debug logging
./scan-namer             # Normal operation
```

## Key Integrations

- **Google Drive API**: For listing, downloading, and renaming files
- **PDF Processing**: For handling multi-page documents and extraction
- **LLM Integration**: For file name generation

## Python Project Structure

Uses uv for package management with inline script metadata. Dependencies are declared in the Python script header.

## Project Files

- `scan_namer.py`: Main application with inline uv dependencies
- `scan-namer`: Bash wrapper script for easy execution
- `config.json`: Application configuration (LLM, PDF, logging settings)
- `prompts.json`: LLM prompt templates
- `.env.example`: Template for environment variables
- `credentials.json`: Google OAuth credentials (user must provide)
- `token.json`: Google OAuth token cache (generated automatically)

## Commands for Development

- `./scan-namer --dry-run`: Test functionality without making changes
- `./scan-namer --verbose`: Enable debug logging
- No testing framework - manual testing only