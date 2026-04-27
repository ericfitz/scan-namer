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
