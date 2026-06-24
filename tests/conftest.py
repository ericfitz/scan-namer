import json
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable even when pytest is invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scan_namer  # noqa: E402

# A minimal but schema-valid config used across tests. Providers cover the
# cases the resolution tests need: a normal provider with a model list and
# default, a provider missing default_model, and a provider with an empty
# model list (validation bypass).
MINIMAL_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-5.5",
        "max_tokens": 1000,
        "temperature": 0.3,
        "providers": {
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
                "available_models": ["gpt-5.5", "gpt-4o"],
                "default_model": "gpt-5.5",
            },
            "anthropic": {
                "api_key_env": "ANTHROPIC_API_KEY",
                "available_models": ["claude-sonnet-4-6"],
                "default_model": "claude-sonnet-4-6",
            },
            "nodefault": {
                "api_key_env": "NODEFAULT_API_KEY",
                "available_models": ["m1"],
            },
            "openlist": {
                "api_key_env": "OPENLIST_API_KEY",
                "available_models": [],
                "default_model": "any-model",
            },
        },
    },
    "pdf": {"max_pages_before_extraction": 3, "extraction_pages": 3},
    "ocr": {
        "enable_embedding": False,
        "min_text_per_page": 50,
        "language": "eng",
        "dpi": 300,
    },
    "google_drive": {
        "credentials_file": "credentials.json",
        "token_file": "token.json",
        "folder_name": "",
        "scopes": ["https://www.googleapis.com/auth/drive"],
    },
    "logging": {
        "level": "INFO",
        "format": "%(message)s",
        "date_format": "%Y",
        "file": "scan_namer.log",
    },
}


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Clear config-affecting env vars so the host environment can't perturb
    tests. Secret/API-key env vars are managed explicitly per-test."""
    for var in [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "MAX_FILENAME_LENGTH",
        "GENERIC_FILENAME_PATTERNS",
        "PDF_MAX_PAGES_BEFORE_EXTRACTION",
        "PDF_EXTRACTION_PAGES",
    ]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def config_factory(tmp_path):
    """Return a builder that writes a config dict to a temp file and returns a
    ConfigManager for it."""

    def _make(cfg_dict):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(cfg_dict))
        return scan_namer.ConfigManager(str(path))

    return _make


@pytest.fixture
def config(config_factory):
    """A ConfigManager built from a fresh copy of MINIMAL_CONFIG."""
    return config_factory(json.loads(json.dumps(MINIMAL_CONFIG)))
