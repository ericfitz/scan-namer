import json

from conftest import MINIMAL_CONFIG

import scan_namer  # noqa: F401  (kept for symmetry / future use)


def test_env_override_wins_for_string(config, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "xai")
    assert config.get("llm.provider") == "xai"


def test_env_override_string_model(config, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "some-model")
    assert config.get("llm.model") == "some-model"


def test_int_conversion(config, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "2500")
    value = config.get("llm.max_tokens")
    assert value == 2500
    assert isinstance(value, int)


def test_temperature_setting_is_ignored_with_warning(config_factory, caplog):
    cfg = json.loads(json.dumps(MINIMAL_CONFIG))
    cfg["llm"]["temperature"] = 0.3
    config_factory(cfg)
    assert "llm.temperature / LLM_TEMPERATURE is no longer used" in caplog.text


def test_temperature_env_is_ignored_with_warning(config_factory, monkeypatch, caplog):
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    config_factory(json.loads(json.dumps(MINIMAL_CONFIG)))
    assert "llm.temperature / LLM_TEMPERATURE is no longer used" in caplog.text


def test_no_temperature_setting_no_warning(config_factory, caplog):
    config_factory(json.loads(json.dumps(MINIMAL_CONFIG)))
    assert "LLM_TEMPERATURE" not in caplog.text


def test_invalid_int_falls_back_to_file_value(config, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "not-a-number")
    # Conversion fails -> override returns None -> file value (1000) is used.
    assert config.get("llm.max_tokens") == 1000


def test_no_override_returns_file_value(config):
    assert config.get("llm.provider") == "openai"


def test_convert_bool_true_values(config):
    assert config._convert_env_value("true", "auto_select_first_folder") is True
    assert config._convert_env_value("yes", "auto_select_first_folder") is True
    assert config._convert_env_value("1", "auto_select_first_folder") is True


def test_convert_bool_false_value(config):
    assert config._convert_env_value("false", "auto_select_first_folder") is False
