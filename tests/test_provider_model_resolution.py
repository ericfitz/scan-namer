import json

import pytest

import scan_namer
from conftest import MINIMAL_CONFIG


class StubClient:
    """Recording stand-in for the real provider clients."""

    def __init__(self, config, provider, model, max_tokens=None):
        self.config = config
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens


@pytest.fixture
def stub_clients(monkeypatch):
    for name in [
        "XAIClient",
        "AnthropicClient",
        "OpenAIClient",
        "GoogleClient",
        "LMStudioClient",
    ]:
        monkeypatch.setattr(scan_namer, name, StubClient)


@pytest.fixture
def cfg(config_factory):
    return config_factory(json.loads(json.dumps(MINIMAL_CONFIG)))


def test_unknown_provider_exits(cfg):
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(cfg, provider="bogus")


def test_model_not_in_list_exits(cfg, stub_clients):
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(
            cfg, provider="openai", model="not-a-real-model"
        )


def test_provider_without_default_model_exits(cfg, stub_clients):
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(cfg, provider="nodefault")


def test_provider_only_uses_provider_default(cfg, stub_clients):
    client = scan_namer.LLMClientFactory.create_client(cfg, provider="anthropic")
    assert client.provider == "anthropic"
    assert client.model == "claude-sonnet-4-6"


def test_model_only_mismatch_against_default_provider_exits(cfg, stub_clients):
    # No --provider: default provider is openai; an anthropic model is invalid.
    with pytest.raises(SystemExit):
        scan_namer.LLMClientFactory.create_client(cfg, model="claude-sonnet-4-6")


def test_explicit_provider_and_valid_model(cfg, stub_clients):
    client = scan_namer.LLMClientFactory.create_client(
        cfg, provider="openai", model="gpt-4o"
    )
    assert client.provider == "openai"
    assert client.model == "gpt-4o"


def test_neither_flag_uses_config_model(cfg, stub_clients):
    client = scan_namer.LLMClientFactory.create_client(cfg)
    assert client.provider == "openai"
    assert client.model == "gpt-5.5"


def test_empty_available_models_accepts_any(config_factory, stub_clients):
    # An empty available_models list bypasses model validation (any model is
    # accepted). Use a REAL provider name (openai) with its model list emptied,
    # so create_client's hardcoded provider dispatch reaches the stubbed client
    # rather than the unknown-provider exit branch.
    cfg_dict = json.loads(json.dumps(MINIMAL_CONFIG))
    cfg_dict["llm"]["providers"]["openai"]["available_models"] = []
    cfg = config_factory(cfg_dict)
    client = scan_namer.LLMClientFactory.create_client(
        cfg, provider="openai", model="whatever-model"
    )
    assert client.provider == "openai"
    assert client.model == "whatever-model"
