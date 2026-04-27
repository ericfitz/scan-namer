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

# Minimal valid 1-page PDF (612x792 / US Letter, no content stream).
# Generated once and pinned; verify integrity in tests.
MINIMAL_PDF_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiA"
    "wIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iag"
    "o8PC9UeXBlL1BhZ2UvTWVkaWFCb3hbMCAwIDYxMiA3OTJdL1BhcmVudCAyIDAgUi9SZXNvdXJjZ"
    "XM8PD4+Pj4KZW5kb2JqCnhyZWYKMCA0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAw"
    "MDAwMCBuIAowMDAwMDAwMDUyIDAwMDAwIG4gCjAwMDAwMDAwOTcgMDAwMDAgbiAKdHJhaWxlcgo"
    "8PC9TaXplIDQvUm9vdCAxIDAgUj4+CnN0YXJ0eHJlZgoxNTYKJSVFT0YK"
)


@dataclass
class ProbeResult:
    """Outcome of a single PDF probe."""

    succeeded: bool
    supports_pdf: Optional[bool]
    error: Optional[str]


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


_OPENAI_NON_CHAT_PREFIXES = (
    "text-embedding-",
    "whisper-",
    "tts-",
    "dall-e-",
    "omni-moderation-",
    "babbage-",
    "davinci-",
)


def filter_chat_models(provider: str, model_ids: List[str]) -> List[str]:
    """Keep only chat-capable model ids per provider rules. LMStudio and unknown
    providers are unfiltered.
    """
    def _norm(mid: str) -> str:
        # Some APIs return ids with a "models/" prefix (Google in particular)
        return mid[len("models/"):] if mid.startswith("models/") else mid

    if provider == "openai":
        kept = []
        for mid in model_ids:
            base = _norm(mid)
            if any(base.startswith(p) for p in _OPENAI_NON_CHAT_PREFIXES):
                continue
            if base.startswith("gpt-") or (
                len(base) >= 2 and base[0] == "o" and base[1].isdigit()
            ):
                kept.append(mid)
        return kept

    if provider == "anthropic":
        return [mid for mid in model_ids if _norm(mid).startswith("claude-")]

    if provider == "google":
        return [mid for mid in model_ids if _norm(mid).startswith("gemini-")]

    if provider == "xai":
        return [mid for mid in model_ids if _norm(mid).startswith("grok-")]

    # lmstudio + anything unrecognized: pass through
    return list(model_ids)


def atomic_write_json(path: str, data: Any) -> None:
    """Write `data` as pretty JSON to `path`, atomically.

    Stages to `path + ".tmp"`, then replaces the original. If serialization
    fails, the staging file is removed and the original is left untouched.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    except (TypeError, ValueError):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    os.replace(tmp_path, path)


GREEN_CHECK = "✅"
RED_X = "❌"
ASCII_CHECK = "✓"
ASCII_X = "✗"


def format_header(provider: str, endpoint: str) -> str:
    return f"Probing provider {provider} at endpoint {endpoint}"


def format_model_line(
    model: str,
    supports_pdf: Optional[bool] = None,
    error: Optional[str] = None,
) -> str:
    if error is not None:
        return f"\t{ASCII_X}  Model: {model}  [ Error: {error} ]"
    return f"\t{ASCII_CHECK}  Model: {model}  [ Supports pdf: {supports_pdf} ]"


def format_provider_summary(
    provider: str, success: bool, error: Optional[str] = None
) -> str:
    if success:
        return f"{GREEN_CHECK} {provider}  Model list updated"
    return f"{RED_X} {provider}  Error retrieving list of models: {error}"


_PDF_REJECTION_MARKERS = (
    "does not support image",
    "does not support file",
    "does not support pdf",
    "does not support document",
    "does not support multimodal",
    "image input is not supported",
    "file input is not supported",
    "unsupported content",
    "vision is not supported",
)


def derive_models_url(api_endpoint: str) -> str:
    """Given a chat-completions endpoint, return the corresponding /models URL."""
    suffix = "/chat/completions"
    if api_endpoint.endswith(suffix):
        return api_endpoint[: -len(suffix)] + "/models"
    return api_endpoint.rstrip("/") + "/models"


def _is_pdf_rejection(body_text: str) -> bool:
    lowered = (body_text or "").lower()
    return any(m in lowered for m in _PDF_REJECTION_MARKERS)


def _bearer_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _openai_compat_pdf_payload(model: str) -> Dict[str, Any]:
    return {
        "model": model,
        "max_tokens": 1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{MINIMAL_PDF_B64}"
                        },
                    },
                ],
            }
        ],
    }


class LMStudioProvider:
    name = "lmstudio"

    def __init__(self, api_endpoint: str, api_key: Optional[str]):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.models_url = derive_models_url(api_endpoint)

    def list_models(self) -> List[str]:
        response = requests.get(
            self.models_url, headers=_bearer_headers(self.api_key), timeout=15
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        return [item["id"] for item in items if isinstance(item, dict) and "id" in item]

    def probe_pdf(self, model: str) -> ProbeResult:
        try:
            response = requests.post(
                self.api_endpoint,
                headers=_bearer_headers(self.api_key),
                json=_openai_compat_pdf_payload(model),
                timeout=30,
            )
            response.raise_for_status()
            return ProbeResult(succeeded=True, supports_pdf=True, error=None)
        except requests.HTTPError as e:
            body = getattr(e.response, "text", "") if e.response is not None else ""
            if _is_pdf_rejection(body):
                return ProbeResult(succeeded=True, supports_pdf=False, error=None)
            status = (
                e.response.status_code if e.response is not None else "?"
            )
            return ProbeResult(
                succeeded=False,
                supports_pdf=None,
                error=f"HTTP {status} {body[:200]}".strip(),
            )
        except requests.RequestException as e:
            return ProbeResult(succeeded=False, supports_pdf=None, error=str(e))


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
