from types import SimpleNamespace
from unittest import mock

import pytest

import scan_namer

PROMPT = {"system_prompt": "sys", "user_prompt": "Name this document."}


def _response():
    return SimpleNamespace(
        usage=SimpleNamespace(input_tokens=10, output_tokens=2),
        content=[SimpleNamespace(text="2024-01-08_Invoice.pdf")],
    )


@pytest.fixture
def client(config, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    c = scan_namer.AnthropicClient(config, "anthropic", "claude-sonnet-4-6")
    # Autospec against the installed SDK, so a keyword the SDK no longer
    # accepts (API version 2026-10-21 removed temperature) raises TypeError.
    create = mock.create_autospec(c.client.messages.create, return_value=_response())
    monkeypatch.setattr(c.client.messages, "create", create)
    return c


def test_text_request_matches_sdk_signature(client):
    name, cost = client.analyze_document(document_text="text", prompt_config=PROMPT)

    assert name == "2024-01-08_Invoice.pdf"
    assert cost["total_tokens"] == 12
    assert "temperature" not in client.client.messages.create.call_args.kwargs


def test_rasterized_request_matches_sdk_signature(client, monkeypatch):
    monkeypatch.setattr(client, "_rasterize_pdf_to_pngs", lambda _path: [b"png"])

    name, _ = client._analyze_via_rasterized_pages("scan.pdf", PROMPT)

    assert name == "2024-01-08_Invoice.pdf"
    assert "temperature" not in client.client.messages.create.call_args.kwargs
