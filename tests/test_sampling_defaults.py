"""Requests leave sampling parameters out so every model uses its default."""

import json
from types import SimpleNamespace
from unittest import mock

import pytest
from conftest import MINIMAL_CONFIG

import scan_namer

PROMPT = {"system_prompt": "sys", "user_prompt": "Name this document."}
SAMPLING = {"temperature", "top_p", "top_k"}
NAME = "2024-01-08_Invoice.pdf"


@pytest.fixture
def cfg(config_factory):
    data = json.loads(json.dumps(MINIMAL_CONFIG))
    data["llm"]["providers"]["xai"] = {
        "api_key_env": "XAI_API_KEY",
        "api_endpoint": "https://api.x.ai/v1/chat/completions",
        "available_models": ["grok-4.7"],
        "default_model": "grok-4.7",
    }
    data["llm"]["providers"]["google"] = {
        "project_id_env": "GOOGLE_PROJECT_ID",
        "available_models": ["gemini-2.5-flash"],
        "default_model": "gemini-2.5-flash",
    }
    return config_factory(data)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_PROJECT_ID", "test-project")


def _rasterize(client, monkeypatch):
    monkeypatch.setattr(client, "_rasterize_pdf_to_pngs", lambda _path: [b"png"])
    return client._analyze_via_rasterized_pages("scan.pdf", PROMPT)


def test_xai_text_request_omits_sampling(cfg, monkeypatch):
    client = scan_namer.XAIClient(cfg, "xai", "grok-4.7")
    response = mock.Mock()
    response.json.return_value = {
        "usage": {},
        "choices": [{"message": {"content": NAME}}],
    }
    post = mock.Mock(return_value=response)
    monkeypatch.setattr(scan_namer.requests, "post", post)

    name, _ = client.analyze_document(document_text="text", prompt_config=PROMPT)

    assert name == NAME
    assert not SAMPLING & post.call_args.kwargs["json"].keys()


@pytest.mark.parametrize("rasterized", [False, True])
def test_openai_request_omits_sampling(cfg, monkeypatch, rasterized):
    client = scan_namer.OpenAIClient(cfg, "openai", "gpt-5.5")
    reply = SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content=NAME))],
    )
    create = mock.Mock(return_value=reply)
    monkeypatch.setattr(client.client.chat.completions, "create", create)

    if rasterized:
        name, _ = _rasterize(client, monkeypatch)
    else:
        name, _ = client.analyze_document(document_text="text", prompt_config=PROMPT)

    assert name == NAME
    assert not SAMPLING & create.call_args.kwargs.keys()


@pytest.mark.parametrize("rasterized", [False, True])
def test_google_request_omits_sampling(cfg, monkeypatch, rasterized):
    # The real genai.Client needs Vertex credentials; the request is what matters.
    monkeypatch.setattr(scan_namer.GoogleClient, "_setup_client", lambda _self: None)
    client = scan_namer.GoogleClient(cfg, "google", "gemini-2.5-flash")
    generate = mock.Mock(return_value=SimpleNamespace(text=NAME))
    client.client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))

    if rasterized:
        name, _ = _rasterize(client, monkeypatch)
    else:
        name, _ = client.analyze_document(document_text="text", prompt_config=PROMPT)

    assert name == NAME
    assert not SAMPLING & generate.call_args.kwargs["config"].keys()
