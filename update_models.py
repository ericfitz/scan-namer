#!/usr/bin/env python3
"""
Update Models - Refresh available_models and pdf_support in config.json by
querying each LLM provider for currently-available models. PDF capability is
looked up in the LiteLLM model registry; unrecognized models can optionally
be probed with a tiny PDF.
"""
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "requests==2.31.0",
#     "anthropic>=0.7.0",
#     "openai>=1.0.0",
#     "google-genai>=0.1.0",
# ]
# ///

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


LITELLM_REGISTRY_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")


_EXPORT_LINE_RE = re.compile(
    r"""^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*?)\s*$"""
)


def resolve_api_key(env_name: str, project_root: str = PROJECT_ROOT) -> Optional[str]:
    """Resolve an API key by trying a same-named file in project_root, then the
    environment variable, then returning None.

    Files are expected to be in shell-sourceable form: `export NAME=value` or
    `NAME=value`. Surrounding single or double quotes are stripped.
    """
    file_path = os.path.join(project_root, env_name)
    if os.path.isfile(file_path):
        try:
            with open(file_path, "r") as f:
                for line in f:
                    m = _EXPORT_LINE_RE.match(line)
                    if not m or m.group("name") != env_name:
                        continue
                    value = m.group("value")
                    if (
                        len(value) >= 2
                        and value[0] == value[-1]
                        and value[0] in ("'", '"')
                    ):
                        value = value[1:-1]
                    return value
        except OSError as e:
            logging.warning("Could not read %s: %s", file_path, e)

    return os.environ.get(env_name)


def fetch_litellm_registry(url: str = LITELLM_REGISTRY_URL) -> Dict[str, Any]:
    """Fetch the LiteLLM model registry JSON. Returns {} on any failure."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            logging.warning("LiteLLM registry was not a dict; treating as empty")
            return {}
        return data
    except (requests.RequestException, ValueError) as e:
        logging.warning("Could not fetch LiteLLM registry (%s); treating as empty", e)
        return {}


def lookup_pdf_support(
    registry: Dict[str, Any], model_id: str, provider: str
) -> Optional[bool]:
    """Look up `supports_pdf_input` for a model. Returns:
        True/False if the registry has a definitive answer.
        None if the model is unknown, or its entry has no/null pdf flag.
    """
    candidates = [model_id, f"{provider}/{model_id}"]
    for key in candidates:
        entry = registry.get(key)
        if not isinstance(entry, dict):
            continue
        flag = entry.get("supports_pdf_input")
        if isinstance(flag, bool):
            return flag
        return None
    return None


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update available_models and pdf_support in config.json"
    )
    parser.add_argument(
        "--provider",
        help="Process only this provider (default: all providers in config.json)",
    )
    parser.add_argument(
        "--enable-probing",
        action="store_true",
        help="Probe unknown models with a tiny PDF to detect support (default: off)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written, don't modify config.json",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logging.debug("Args: %s", args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
