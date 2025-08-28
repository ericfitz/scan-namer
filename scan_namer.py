#!/usr/bin/env python3
"""
Scan Namer - Automatically rename scanned documents in Google Drive
using LLM analysis of document content.
"""
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "google-auth-oauthlib==1.2.0",
#     "google-auth==2.29.0",
#     "google-api-python-client==2.133.0",
#     "google-genai>=0.1.0",
#     "anthropic>=0.7.0",
#     "openai>=1.0.0",
#     "PyPDF2==3.0.1",
#     "requests==2.31.0",
#     "python-dotenv==1.0.1",
# ]
# ///

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import base64
import io

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2
from dotenv import load_dotenv


class ConfigManager:
    """Manages configuration loading and validation."""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Configuration file {self.config_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in {self.config_file}: {e}")
            sys.exit(1)

    def _validate_config(self):
        """Validate required configuration sections exist."""
        required_sections = ["llm", "pdf", "google_drive", "logging"]
        for section in required_sections:
            if section not in self.config:
                logging.error(f"Missing required config section: {section}")
                sys.exit(1)

    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation (e.g., 'llm.api_key')."""
        # Check for environment variable override first
        env_value = self._get_env_override(key_path)
        if env_value is not None:
            return env_value

        # Fall back to config file value
        keys = key_path.split(".")
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def _get_env_override(self, key_path: str):
        """Check for environment variable override for a config key."""
        # Map config keys to environment variable names
        env_mappings = {
            "llm.provider": "LLM_PROVIDER",
            "llm.model": "LLM_MODEL",
            "llm.max_tokens": "LLM_MAX_TOKENS",
            "llm.temperature": "LLM_TEMPERATURE",
            "pdf.max_pages_before_extraction": "PDF_MAX_PAGES_BEFORE_EXTRACTION",
            "pdf.extraction_pages": "PDF_EXTRACTION_PAGES",
            "google_drive.credentials_file": "GOOGLE_DRIVE_CREDENTIALS_FILE",
            "google_drive.token_file": "GOOGLE_DRIVE_TOKEN_FILE",
            "logging.level": "LOG_LEVEL",
            "logging.format": "LOG_FORMAT",
            "logging.date_format": "LOG_DATE_FORMAT",
            "logging.file": "LOG_FILE",
        }

        env_var = env_mappings.get(key_path)
        if env_var:
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                return self._convert_env_value(env_value, key_path)

        return None

    def _convert_env_value(self, value: str, key_path: str):
        """Convert environment variable string to appropriate type."""
        # Integer conversions
        if key_path in [
            "llm.max_tokens",
            "pdf.max_pages_before_extraction",
            "pdf.extraction_pages",
        ]:
            try:
                return int(value)
            except ValueError:
                logging.warning(f"Invalid integer value for {key_path}: {value}")
                return None

        # Float conversions
        if key_path in ["llm.temperature"]:
            try:
                return float(value)
            except ValueError:
                logging.warning(f"Invalid float value for {key_path}: {value}")
                return None

        # Boolean conversions
        if key_path in ["auto_select_first_folder"]:
            return value.lower() in ("true", "1", "yes", "on")

        # String values (no conversion needed)
        return value


class PromptManager:
    """Manages prompt templates from JSON file."""

    def __init__(self, prompts_file: str = "prompts.json"):
        self.prompts_file = prompts_file
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> Dict:
        """Load prompts from JSON file."""
        try:
            with open(self.prompts_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Prompts file {self.prompts_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in {self.prompts_file}: {e}")
            sys.exit(1)

    def get_prompt(self, prompt_key: str) -> Dict:
        """Get prompt configuration by key."""
        if prompt_key not in self.prompts:
            raise ValueError(f"Prompt key '{prompt_key}' not found")
        return self.prompts[prompt_key]


class GoogleDriveManager:
    """Handles Google Drive authentication and operations."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        token_file = self.config.get("google_drive.token_file")
        creds_file = self.config.get("google_drive.credentials_file")
        scopes = self.config.get("google_drive.scopes")

        # Load existing token
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, scopes)

        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logging.info("Refreshed Google Drive credentials")
                except Exception as e:
                    logging.warning(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(creds_file):
                    logging.error(
                        f"Google Drive credentials file {creds_file} not found"
                    )
                    logging.error(
                        "Please download OAuth 2.0 credentials from Google Cloud Console"
                    )
                    sys.exit(1)

                flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
                creds = flow.run_local_server(port=0)
                logging.info("Completed Google Drive OAuth flow")

            # Save the credentials
            with open(token_file, "w") as token:
                token.write(creds.to_json())
            logging.info(f"Saved credentials to {token_file}")

        self.service = build("drive", "v3", credentials=creds)
        logging.info("Successfully authenticated with Google Drive")

    def list_folders(self, parent_id: str = "root") -> List[Dict]:
        """List folders in Google Drive."""
        try:
            query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.service.files()
                .list(q=query, fields="files(id,name,parents)")
                .execute()
            )
            return results.get("files", [])
        except HttpError as e:
            logging.error(f"Error listing folders: {e}")
            return []

    def select_folder(self) -> Optional[str]:
        """Allow user to select a Google Drive folder."""
        print("\nAvailable folders in your Google Drive:")
        folders = self.list_folders()

        if not folders:
            print("No folders found in root directory.")
            return None

        for i, folder in enumerate(folders, 1):
            print(f"{i}. {folder['name']}")

        print(f"{len(folders) + 1}. Enter custom folder path")

        try:
            choice = input(f"\nSelect folder (1-{len(folders) + 1}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(folders):
                selected = folders[choice_num - 1]
                logging.info(
                    f"Selected folder: {selected['name']} (ID: {selected['id']})"
                )
                return selected["id"]
            elif choice_num == len(folders) + 1:
                folder_path = input("Enter folder path or ID: ").strip()
                return folder_path
            else:
                print("Invalid selection")
                return None
        except (ValueError, KeyboardInterrupt):
            print("Invalid input or cancelled")
            return None

    def list_pdfs(self, folder_id: str) -> List[Dict]:
        """List PDF files in a Google Drive folder."""
        try:
            query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
            results = (
                self.service.files()
                .list(
                    q=query,
                    fields="files(id,name,size,modifiedTime)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
            files = results.get("files", [])
            logging.info(f"Found {len(files)} PDF files in folder")
            return files
        except HttpError as e:
            logging.error(f"Error listing PDFs: {e}")
            return []

    def download_file(self, file_id: str, output_path: str) -> bool:
        """Download a file from Google Drive."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            with open(output_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            logging.debug(f"Downloaded file to {output_path}")
            return True
        except HttpError as e:
            logging.error(f"Error downloading file: {e}")
            return False

    def rename_file(self, file_id: str, new_name: str) -> bool:
        """Rename a file in Google Drive."""
        try:
            self.service.files().update(
                fileId=file_id, body={"name": new_name}
            ).execute()
            logging.info(f"Renamed file to: {new_name}")
            return True
        except HttpError as e:
            logging.error(f"Error renaming file: {e}")
            return False


class PDFProcessor:
    """Handles PDF processing operations."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.max_pages = config.get("pdf.max_pages_before_extraction", 3)
        self.extraction_pages = config.get("pdf.extraction_pages", 3)

    def get_page_count(self, pdf_path: str) -> int:
        """Get the number of pages in a PDF."""
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                return len(reader.pages)
        except Exception as e:
            logging.error(f"Error reading PDF {pdf_path}: {e}")
            return 0

    def extract_pages(
        self, input_path: str, output_path: str, num_pages: int = None
    ) -> bool:
        """Extract first N pages from PDF to a new file."""
        if num_pages is None:
            num_pages = self.extraction_pages

        try:
            with open(input_path, "rb") as input_file:
                reader = PyPDF2.PdfReader(input_file)
                writer = PyPDF2.PdfWriter()

                pages_to_extract = min(num_pages, len(reader.pages))
                for i in range(pages_to_extract):
                    writer.add_page(reader.pages[i])

                with open(output_path, "wb") as output_file:
                    writer.write(output_file)

            logging.debug(f"Extracted {pages_to_extract} pages to {output_path}")
            return True
        except Exception as e:
            logging.error(f"Error extracting pages: {e}")
            return False

    def extract_text(self, pdf_path: str, max_pages: int = None) -> str:
        """Extract text content from PDF for LLM analysis."""
        if max_pages is None:
            max_pages = self.extraction_pages

        try:
            text_content = []
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                pages_to_process = min(max_pages, len(reader.pages))

                for i in range(pages_to_process):
                    page = reader.pages[i]
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_content.append(
                            f"--- Page {i + 1} ---\n{page_text.strip()}"
                        )

            full_text = "\n\n".join(text_content)
            logging.debug(
                f"Extracted {len(full_text)} characters of text from {pages_to_process} pages"
            )
            return full_text

        except Exception as e:
            logging.error(f"Error extracting text from PDF {pdf_path}: {e}")
            return ""

    def should_extract(self, page_count: int) -> bool:
        """Determine if PDF should be truncated based on page count."""
        return page_count > self.max_pages


class BaseLLMClient:
    """Base class for LLM clients."""

    def __init__(
        self, config: ConfigManager, provider: str, model: str, max_tokens: int = None
    ):
        self.config = config
        self.provider = provider
        self.model = model
        # Use command line override if provided, otherwise fall back to config
        if max_tokens is not None:
            self.max_tokens = max_tokens
            logging.info(f"Using command line override: max_tokens = {max_tokens}")
        else:
            self.max_tokens = config.get("llm.max_tokens", 1000)
        self.temperature = config.get("llm.temperature", 0.3)
        self.token_costs = []

    def analyze_document(
        self,
        document_text: str = None,
        prompt_config: Dict = None,
        pdf_path: str = None,
    ) -> Tuple[Optional[str], Dict]:
        """Send document text or PDF to LLM for analysis.

        Args:
            document_text: Extracted text content (if available)
            prompt_config: Prompt configuration dictionary
            pdf_path: Path to PDF file for direct upload (if text extraction failed)
        """
        raise NotImplementedError("Subclasses must implement analyze_document")

    def _encode_pdf_to_base64(self, pdf_path: str) -> str:
        """Encode PDF file to base64 for API upload."""
        try:
            with open(pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                return base64.b64encode(pdf_bytes).decode("utf-8")
        except Exception as e:
            logging.error(f"Error encoding PDF to base64: {e}")
            return ""

    def supports_pdf(self) -> bool:
        """Check if the current model supports PDF upload."""
        pdf_support = self.config.get(f"llm.providers.{self.provider}.pdf_support", {})
        return pdf_support.get(self.model, False)

    def get_total_costs(self) -> Dict:
        """Get total token costs for all requests."""
        if not self.token_costs:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        return {
            "prompt_tokens": sum(cost["prompt_tokens"] for cost in self.token_costs),
            "completion_tokens": sum(
                cost["completion_tokens"] for cost in self.token_costs
            ),
            "total_tokens": sum(cost["total_tokens"] for cost in self.token_costs),
        }


class XAIClient(BaseLLMClient):
    """X.AI (Grok) API client."""

    def __init__(
        self, config: ConfigManager, provider: str, model: str, max_tokens: int = None
    ):
        super().__init__(config, provider, model, max_tokens)
        self.api_key = self._get_api_key()
        self.endpoint = config.get(f"llm.providers.{provider}.api_endpoint")

    def _get_api_key(self) -> str:
        api_key_env = self.config.get(f"llm.providers.{self.provider}.api_key_env")
        api_key = os.getenv(api_key_env)
        if not api_key:
            logging.error(f"API key not found in environment variable: {api_key_env}")
            sys.exit(1)
        return api_key

    def analyze_document(
        self,
        document_text: str = None,
        prompt_config: Dict = None,
        pdf_path: str = None,
    ) -> Tuple[Optional[str], Dict]:
        """Send document text or PDF to Grok for analysis."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Prepare message content based on available input
            if document_text:
                user_message = f"{prompt_config.get('user_prompt', '')}\n\nDocument content:\n{document_text}"
                messages = [
                    {
                        "role": "system",
                        "content": prompt_config.get("system_prompt", ""),
                    },
                    {"role": "user", "content": user_message},
                ]
            elif pdf_path and self.supports_pdf():
                # For vision models, encode PDF as base64
                pdf_base64 = self._encode_pdf_to_base64(pdf_path)
                if not pdf_base64:
                    return None, {}

                user_message = f"{prompt_config.get('user_prompt', '')}\n\nPlease analyze this PDF document:"
                messages = [
                    {
                        "role": "system",
                        "content": prompt_config.get("system_prompt", ""),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_message},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:application/pdf;base64,{pdf_base64}"
                                },
                            },
                        ],
                    },
                ]
            else:
                if pdf_path and not self.supports_pdf():
                    logging.error(
                        f"Model {self.model} does not support PDF uploads. PDF support available in: grok-4-0709, grok-vision-beta"
                    )
                else:
                    logging.error("Neither document text nor PDF path provided")
                return None, {}

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            response = requests.post(
                self.endpoint, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            result = response.json()

            usage = result.get("usage", {})
            cost_info = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
            self.token_costs.append(cost_info)

            suggested_name = result["choices"][0]["message"]["content"].strip()
            logging.info(f"X.AI suggested filename: {suggested_name}")

            return suggested_name, cost_info

        except Exception as e:
            logging.error(f"X.AI API error: {e}")
            return None, {}


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client."""

    def __init__(
        self, config: ConfigManager, provider: str, model: str, max_tokens: int = None
    ):
        super().__init__(config, provider, model, max_tokens)
        self.api_key = self._get_api_key()
        self._setup_client()

    def _get_api_key(self) -> str:
        api_key_env = self.config.get(f"llm.providers.{self.provider}.api_key_env")
        api_key = os.getenv(api_key_env)
        if not api_key:
            logging.error(f"API key not found in environment variable: {api_key_env}")
            sys.exit(1)
        return api_key

    def _setup_client(self):
        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            logging.error(
                "Anthropic library not installed. Please install with: pip install anthropic"
            )
            sys.exit(1)

    def analyze_document(
        self,
        document_text: str = None,
        prompt_config: Dict = None,
        pdf_path: str = None,
    ) -> Tuple[Optional[str], Dict]:
        """Send document text or PDF to Claude for analysis."""
        try:
            # Prepare message content based on available input
            if document_text:
                user_message = f"{prompt_config.get('user_prompt', '')}\n\nDocument content:\n{document_text}"
                messages = [{"role": "user", "content": user_message}]
            elif pdf_path and self.supports_pdf():
                # Claude supports PDF uploads via base64 encoding
                pdf_base64 = self._encode_pdf_to_base64(pdf_path)
                if not pdf_base64:
                    return None, {}

                user_message = f"{prompt_config.get('user_prompt', '')}\n\nPlease analyze this PDF document:"
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_message},
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64,
                                },
                            },
                        ],
                    }
                ]
            else:
                if pdf_path and not self.supports_pdf():
                    logging.error(
                        f"Model {self.model} does not support PDF uploads. PDF support available in: claude-opus-4-20250514, claude-sonnet-4-20250514, claude-3-7-sonnet-20250219, claude-3-5-sonnet-20241022"
                    )
                else:
                    logging.error("Neither document text nor PDF path provided")
                return None, {}

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=prompt_config.get("system_prompt", ""),
                messages=messages,
            )

            cost_info = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            }
            self.token_costs.append(cost_info)

            suggested_name = response.content[0].text.strip()
            logging.info(f"Claude suggested filename: {suggested_name}")

            return suggested_name, cost_info

        except Exception as e:
            logging.error(f"Anthropic API error: {e}")
            return None, {}


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT API client."""

    def __init__(
        self, config: ConfigManager, provider: str, model: str, max_tokens: int = None
    ):
        super().__init__(config, provider, model, max_tokens)
        self.api_key = self._get_api_key()
        self._setup_client()

    def _get_api_key(self) -> str:
        api_key_env = self.config.get(f"llm.providers.{self.provider}.api_key_env")
        api_key = os.getenv(api_key_env)
        if not api_key:
            logging.error(f"API key not found in environment variable: {api_key_env}")
            sys.exit(1)
        return api_key

    def _setup_client(self):
        try:
            import openai

            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            logging.error(
                "OpenAI library not installed. Please install with: pip install openai"
            )
            sys.exit(1)

    def analyze_document(
        self,
        document_text: str = None,
        prompt_config: Dict = None,
        pdf_path: str = None,
    ) -> Tuple[Optional[str], Dict]:
        """Send document text or PDF to OpenAI for analysis."""
        try:
            # Prepare message content based on available input
            if document_text:
                user_message = f"{prompt_config.get('user_prompt', '')}\n\nDocument content:\n{document_text}"
                messages = [
                    {
                        "role": "system",
                        "content": prompt_config.get("system_prompt", ""),
                    },
                    {"role": "user", "content": user_message},
                ]
            elif pdf_path and self.supports_pdf():
                # Vision-enabled models support PDF uploads
                pdf_base64 = self._encode_pdf_to_base64(pdf_path)
                if not pdf_base64:
                    return None, {}

                user_message = f"{prompt_config.get('user_prompt', '')}\n\nPlease analyze this PDF document:"
                messages = [
                    {
                        "role": "system",
                        "content": prompt_config.get("system_prompt", ""),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_message},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:application/pdf;base64,{pdf_base64}"
                                },
                            },
                        ],
                    },
                ]
            else:
                if pdf_path and not self.supports_pdf():
                    logging.error(
                        f"Model {self.model} does not support PDF uploads. PDF support available in: o3, gpt-4o, gpt-4o-mini"
                    )
                else:
                    logging.error("Neither document text nor PDF path provided")
                return None, {}

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            cost_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            self.token_costs.append(cost_info)

            suggested_name = response.choices[0].message.content.strip()
            logging.info(f"OpenAI suggested filename: {suggested_name}")

            return suggested_name, cost_info

        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return None, {}


class GoogleClient(BaseLLMClient):
    """Google Vertex AI API client."""

    def __init__(
        self, config: ConfigManager, provider: str, model: str, max_tokens: int = None
    ):
        super().__init__(config, provider, model, max_tokens)
        self.project_id = self._get_project_id()
        self.location = config.get(f"llm.providers.{provider}.location", "us-central1")
        self._setup_client()

    def _get_project_id(self) -> str:
        project_env = self.config.get(f"llm.providers.{self.provider}.project_id_env")
        project_id = os.getenv(project_env)
        if not project_id:
            logging.error(
                f"Project ID not found in environment variable: {project_env}"
            )
            sys.exit(1)
        return project_id

    def _setup_client(self):
        try:
            from google import genai

            # Initialize Google Gen AI client for Vertex AI
            self.client = genai.Client(
                project=self.project_id,
                location=self.location,
            )

        except ImportError:
            logging.error(
                "Google Gen AI library not installed. Please install with: pip install google-genai"
            )
            sys.exit(1)

    def analyze_document(
        self,
        document_text: str = None,
        prompt_config: Dict = None,
        pdf_path: str = None,
    ) -> Tuple[Optional[str], Dict]:
        """Send document text or PDF to Google Gen AI for analysis."""
        try:
            system_prompt = prompt_config.get("system_prompt", "")
            user_prompt = prompt_config.get("user_prompt", "")

            # Prepare content based on available input
            if document_text:
                full_prompt = f"{system_prompt}\n\n{user_prompt}\n\nDocument content:\n{document_text}"
                contents = [full_prompt]
            elif pdf_path and self.supports_pdf():
                # Upload PDF file using new SDK
                try:
                    uploaded_file = self.client.files.upload(file=pdf_path)
                    full_prompt = f"{system_prompt}\n\n{user_prompt}\n\nPlease analyze this PDF document:"
                    contents = [full_prompt, uploaded_file]
                except Exception as upload_error:
                    logging.error(f"Failed to upload PDF: {upload_error}")
                    return None, {}
            else:
                if pdf_path and not self.supports_pdf():
                    logging.error(
                        f"Model {self.model} does not support PDF uploads. PDF support available in: gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite"
                    )
                else:
                    logging.error("Neither document text nor PDF path provided")
                return None, {}

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config={
                    "max_output_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )

            # Google Gen AI SDK doesn't provide detailed token usage
            # Approximate token count (rough estimate)
            if document_text:
                estimated_prompt_tokens = (
                    len(
                        f"{system_prompt}\n\n{user_prompt}\n\nDocument content:\n{document_text}"
                    )
                    // 4
                )
            else:
                estimated_prompt_tokens = (
                    len(f"{system_prompt}\n\n{user_prompt}") // 4 + 1000
                )  # Estimate for PDF
            estimated_completion_tokens = len(response.text) // 4

            cost_info = {
                "prompt_tokens": estimated_prompt_tokens,
                "completion_tokens": estimated_completion_tokens,
                "total_tokens": estimated_prompt_tokens + estimated_completion_tokens,
            }
            self.token_costs.append(cost_info)

            suggested_name = response.text.strip()
            logging.info(f"Google AI suggested filename: {suggested_name}")

            return suggested_name, cost_info

        except Exception as e:
            logging.error(f"Google AI API error: {e}")
            return None, {}


class LLMClientFactory:
    """Factory for creating LLM clients."""

    @staticmethod
    def create_client(
        config: ConfigManager,
        provider: str = None,
        model: str = None,
        max_tokens: int = None,
    ) -> BaseLLMClient:
        """Create appropriate LLM client based on provider."""
        if provider is None:
            provider = config.get("llm.provider", "xai")

        if model is None:
            # Try to get model from config, fallback to provider default
            model = config.get("llm.model")
            if not model:
                model = config.get(f"llm.providers.{provider}.default_model")

        # Validate provider exists
        providers_config = config.get("llm.providers", {})
        if provider not in providers_config:
            logging.error(
                f"Unknown provider: {provider}. Available: {list(providers_config.keys())}"
            )
            sys.exit(1)

        # Validate model is available for provider
        available_models = config.get(f"llm.providers.{provider}.available_models", [])
        if available_models and model not in available_models:
            logging.warning(
                f"Model '{model}' not in available models for {provider}: {available_models}"
            )
            logging.warning("Proceeding anyway - model list may be outdated")

        logging.info(f"Using {provider} provider with model: {model}")

        # Create appropriate client
        if provider == "xai":
            return XAIClient(config, provider, model, max_tokens)
        elif provider == "anthropic":
            return AnthropicClient(config, provider, model, max_tokens)
        elif provider == "openai":
            return OpenAIClient(config, provider, model, max_tokens)
        elif provider == "google":
            return GoogleClient(config, provider, model, max_tokens)
        else:
            logging.error(f"No client implementation for provider: {provider}")
            sys.exit(1)


class ScanNamer:
    """Main application class."""

    def __init__(
        self,
        config_file: str = "config.json",
        dry_run: bool = False,
        model: str = None,
        provider: str = None,
        no_ocr: bool = False,
        max_tokens: int = None,
    ):
        self.config = ConfigManager(config_file)
        self.prompts = PromptManager()
        self.dry_run = dry_run
        self.no_ocr = no_ocr
        self._setup_logging()

        # Initialize components
        self.drive_manager = GoogleDriveManager(self.config)
        self.pdf_processor = PDFProcessor(self.config)
        self.llm_client = LLMClientFactory.create_client(
            self.config, provider=provider, model=model, max_tokens=max_tokens
        )

        # Validate --no-ocr flag with model capabilities
        if self.no_ocr and not self.llm_client.supports_pdf():
            logging.warning(
                f"Warning: --no-ocr flag used with model '{self.llm_client.model}' which does not support PDF uploads."
            )
            logging.warning(
                f"PDF fallback will not work. Consider using a vision-enabled model."
            )
            self._print_pdf_capable_models()

    def _setup_logging(self):
        """Set up logging configuration."""
        import datetime

        log_level = getattr(logging, self.config.get("logging.level", "INFO"))
        log_format = self.config.get(
            "logging.format", "%(asctime)s - %(levelname)s - %(message)s"
        )
        log_file = self.config.get("logging.file", "scan_namer.log")

        # Create custom formatter for RFC3339/ISO8601 with milliseconds
        class RFC3339Formatter(logging.Formatter):
            def formatTime(self, record, datefmt=None):
                dt = datetime.datetime.fromtimestamp(
                    record.created, tz=datetime.timezone.utc
                )
                # Format with 3 decimal places for milliseconds
                return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        formatter = RFC3339Formatter(log_format)

        # Create handlers
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Configure root logger
        logging.basicConfig(level=log_level, handlers=[file_handler, console_handler])

    def _is_generic_filename(self, filename: str) -> bool:
        """Check if filename appears to be generic/auto-generated."""
        # Get patterns from environment variable or use defaults
        patterns_env = os.getenv("GENERIC_FILENAME_PATTERNS")
        if patterns_env:
            generic_patterns = [pattern.strip() for pattern in patterns_env.split(",")]
        else:
            generic_patterns = [
                "raven_scan",
                # 'scan_',
                # 'document_',
                # 'img_',
                # 'file_',
            ]

        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in generic_patterns)

    def _clean_filename(self, filename: str) -> str:
        """Clean and validate filename from LLM response."""
        import re

        # Remove any quotes or extra whitespace
        filename = filename.strip().strip("\"'")

        # Remove any file extension if present (we'll add .pdf later)
        if filename.lower().endswith(".pdf"):
            filename = filename[:-4]

        # Replace invalid characters with underscores
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

        # Replace multiple underscores/spaces with single underscore
        filename = re.sub(r"[_\s]+", "_", filename)

        # Remove leading/trailing underscores
        filename = filename.strip("_")

        # Limit length to reasonable size
        max_length = int(os.getenv("MAX_FILENAME_LENGTH", "100"))
        if len(filename) > max_length:
            filename = filename[:max_length]

        # Ensure it's not empty
        if not filename or filename.isspace():
            return ""

        return filename

    def _print_pdf_capable_models(self):
        """Print models that support PDF uploads for current provider."""
        provider = self.llm_client.provider
        pdf_support = self.config.get(f"llm.providers.{provider}.pdf_support", {})
        capable_models = [model for model, supports in pdf_support.items() if supports]

        if capable_models:
            logging.info(
                f"PDF-capable models for {provider}: {', '.join(capable_models)}"
            )
        else:
            logging.info(f"No PDF-capable models configured for {provider}")

    def process_document(self, file_info: Dict, temp_dir: str) -> bool:
        """Process a single document."""
        file_id = file_info["id"]
        original_name = file_info["name"]

        logging.info(f"Processing: {original_name}")

        # Check if filename is generic
        if not self._is_generic_filename(original_name):
            logging.info(f"Skipping non-generic filename: {original_name}")
            return True

        # Download the file
        temp_pdf_path = os.path.join(temp_dir, f"temp_{file_id}.pdf")
        if not self.drive_manager.download_file(file_id, temp_pdf_path):
            return False

        try:
            # Get page count
            page_count = self.pdf_processor.get_page_count(temp_pdf_path)
            logging.info(f"Document has {page_count} pages")

            # Determine if we should use OCR or direct PDF upload
            use_pdf_upload = self.no_ocr
            document_text = None
            pdf_path_for_upload = None

            if not use_pdf_upload:
                # Try to extract text from PDF for LLM analysis
                if self.pdf_processor.should_extract(page_count):
                    logging.info(
                        f"Document has {page_count} pages, extracting text from first {self.pdf_processor.extraction_pages}"
                    )
                    document_text = self.pdf_processor.extract_text(
                        temp_pdf_path, self.pdf_processor.extraction_pages
                    )
                else:
                    logging.info(
                        f"Document has {page_count} pages, extracting all text"
                    )
                    document_text = self.pdf_processor.extract_text(temp_pdf_path)

                # Check if text extraction failed
                if not document_text.strip():
                    logging.warning(
                        "No text content extracted from PDF - falling back to PDF upload"
                    )
                    use_pdf_upload = True
                    document_text = None

            if use_pdf_upload:
                # Prepare PDF for upload (use shortened version if applicable)
                if self.pdf_processor.should_extract(page_count):
                    # Create a shortened PDF for upload
                    shortened_pdf_path = os.path.join(
                        temp_dir, f"shortened_{file_id}.pdf"
                    )
                    if self.pdf_processor.extract_pages(
                        temp_pdf_path,
                        shortened_pdf_path,
                        self.pdf_processor.extraction_pages,
                    ):
                        pdf_path_for_upload = shortened_pdf_path
                        logging.info(
                            f"Using shortened PDF ({self.pdf_processor.extraction_pages} pages) for upload"
                        )
                    else:
                        pdf_path_for_upload = temp_pdf_path
                        logging.warning(
                            "Failed to create shortened PDF, using full document"
                        )
                else:
                    pdf_path_for_upload = temp_pdf_path
                    logging.info("Using full PDF for upload")

            # Analyze with LLM
            prompt_config = self.prompts.get_prompt("document_naming")
            if document_text:
                logging.info("Analyzing document using extracted text")
                suggested_name, cost_info = self.llm_client.analyze_document(
                    document_text=document_text, prompt_config=prompt_config
                )
            elif pdf_path_for_upload:
                logging.info("Analyzing document using PDF upload")
                suggested_name, cost_info = self.llm_client.analyze_document(
                    pdf_path=pdf_path_for_upload, prompt_config=prompt_config
                )
            else:
                logging.error("No document content available for analysis")
                return False

            if not suggested_name:
                logging.error("Failed to get filename suggestion from LLM")
                return False

            # Clean and validate the suggested filename
            suggested_name = self._clean_filename(suggested_name)
            if not suggested_name:
                logging.error("LLM returned invalid filename")
                return False

            # Ensure the filename has .pdf extension
            if not suggested_name.lower().endswith(".pdf"):
                suggested_name += ".pdf"

            # Log token costs
            logging.info(
                f"Token usage - Prompt: {cost_info.get('prompt_tokens', 0)}, "
                f"Completion: {cost_info.get('completion_tokens', 0)}, "
                f"Total: {cost_info.get('total_tokens', 0)}"
            )

            if self.dry_run:
                print(f"DRY RUN - Would rename:")
                print(f"  From: {original_name}")
                print(f"  To:   {suggested_name}")
                return True
            else:
                # Rename the file
                if self.drive_manager.rename_file(file_id, suggested_name):
                    logging.info(
                        f"Successfully renamed: {original_name} -> {suggested_name}"
                    )
                    return True
                else:
                    logging.error(f"Failed to rename file: {original_name}")
                    return False

        finally:
            # Clean up temp files
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            # Clean up shortened PDF if it was created
            shortened_pdf_path = os.path.join(temp_dir, f"shortened_{file_id}.pdf")
            if os.path.exists(shortened_pdf_path):
                os.unlink(shortened_pdf_path)

    def run(self):
        """Main execution method."""
        try:
            logging.info("Starting Scan Namer")

            # Validate required files exist
            if not os.path.exists(self.config.get("google_drive.credentials_file")):
                logging.error(
                    f"Google Drive credentials file not found: {self.config.get('google_drive.credentials_file')}"
                )
                logging.error(
                    "Please download OAuth 2.0 credentials from Google Cloud Console"
                )
                return

            if self.dry_run:
                logging.info("Running in DRY RUN mode - no files will be renamed")

            # Select folder
            folder_id = self.drive_manager.select_folder()
            if not folder_id:
                logging.error("No folder selected")
                return

            # Get PDF files
            pdf_files = self.drive_manager.list_pdfs(folder_id)
            if not pdf_files:
                logging.info("No PDF files found in selected folder")
                return

            eligible_files = [
                f for f in pdf_files if self._is_generic_filename(f["name"])
            ]
            logging.info(
                f"Found {len(eligible_files)} eligible files with generic names"
            )

            if not eligible_files:
                logging.info("No files with generic names found")
                return

            # In dry run mode, only process the first file
            if self.dry_run:
                eligible_files = eligible_files[:1]

            # Process files
            with tempfile.TemporaryDirectory() as temp_dir:
                processed = 0
                failed = 0

                for file_info in eligible_files:
                    try:
                        if self.process_document(file_info, temp_dir):
                            processed += 1
                        else:
                            failed += 1
                    except Exception as e:
                        logging.error(
                            f"Unexpected error processing {file_info['name']}: {e}"
                        )
                        failed += 1

                # Summary
                total_costs = self.llm_client.get_total_costs()
                logging.info(
                    f"Processing complete - Processed: {processed}, Failed: {failed}"
                )
                logging.info(
                    f"Total token usage - Prompt: {total_costs['prompt_tokens']}, "
                    f"Completion: {total_costs['completion_tokens']}, "
                    f"Total: {total_costs['total_tokens']}"
                )

        except KeyboardInterrupt:
            logging.info("Process interrupted by user")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise


def main():
    """Entry point."""
    load_dotenv()  # Load environment variables from .env file

    parser = argparse.ArgumentParser(
        description="Automatically rename scanned documents in Google Drive"
    )
    parser.add_argument(
        "--config", default="config.json", help="Configuration file path"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test mode - process one file without renaming",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--provider", help="LLM provider (xai, anthropic, openai, google)"
    )
    parser.add_argument(
        "--model",
        help="Override LLM model (e.g., grok-4-0709, claude-sonnet-4-20250514, gpt-4.1, gemini-2.5-flash)",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List available providers and exit",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models for all providers and exit",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip text extraction and upload PDF files directly to LLM (requires PDF-capable model)",
    )
    parser.add_argument(
        "--tokens",
        type=int,
        help="Override max_tokens limit for LLM requests (e.g., --tokens 3000)",
        metavar="N",
    )

    args = parser.parse_args()

    # Handle list-providers command
    if args.list_providers:
        try:
            config = ConfigManager(args.config)
            providers = config.get("llm.providers", {})
            current_provider = config.get("llm.provider")

            print("Available LLM providers:")
            for provider in providers.keys():
                marker = " (current)" if provider == current_provider else ""
                print(f"  - {provider}{marker}")

            if not providers:
                print("  No providers configured in config.json")
            return
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)

    # Handle list-models command
    if args.list_models:
        try:
            config = ConfigManager(args.config)
            providers = config.get("llm.providers", {})
            current_provider = config.get("llm.provider")
            current_model = config.get("llm.model")

            print("Available LLM models by provider:")
            for provider, provider_config in providers.items():
                marker = " (current provider)" if provider == current_provider else ""
                print(f"\n{provider}{marker}:")

                models = provider_config.get("available_models", [])
                default_model = provider_config.get("default_model")
                pdf_support = provider_config.get("pdf_support", {})

                for model in models:
                    markers = []
                    if model == current_model and provider == current_provider:
                        markers.append("current")
                    if model == default_model:
                        markers.append("default")
                    if pdf_support.get(model, False):
                        markers.append("PDF")

                    marker_str = f" ({', '.join(markers)})" if markers else ""
                    print(f"  - {model}{marker_str}")

                if not models:
                    print("  No models configured")

            if not providers:
                print("  No providers configured in config.json")
            return
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)

    # Override log level if verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        app = ScanNamer(
            config_file=args.config,
            dry_run=args.dry_run,
            model=args.model,
            provider=args.provider,
            no_ocr=args.no_ocr,
            max_tokens=args.tokens,
        )
        app.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
