import pytest

import scan_namer


def _client():
    """A BaseLLMClient with no __init__ side effects."""
    return object.__new__(scan_namer.BaseLLMClient)


def test_parse_export_form(tmp_path):
    f = tmp_path / "ANTHROPIC_API_KEY"
    f.write_text('export ANTHROPIC_API_KEY="key-abc"\n')
    assert _client()._parse_secret_file(str(f), "ANTHROPIC_API_KEY") == "key-abc"


def test_parse_bare_assignment(tmp_path):
    f = tmp_path / "ANTHROPIC_API_KEY"
    f.write_text("ANTHROPIC_API_KEY=key-bare\n")
    assert _client()._parse_secret_file(str(f), "ANTHROPIC_API_KEY") == "key-bare"


def test_parse_single_quotes_stripped(tmp_path):
    f = tmp_path / "K"
    f.write_text("K='key-single'\n")
    assert _client()._parse_secret_file(str(f), "K") == "key-single"


def test_parse_mismatched_quotes_not_stripped(tmp_path):
    f = tmp_path / "K"
    f.write_text("K='key-x\"\n")
    # Opening ' and closing " do not match -> left intact.
    assert _client()._parse_secret_file(str(f), "K") == "'key-x\""


def test_parse_raw_key_first_nonempty_line(tmp_path):
    f = tmp_path / "K"
    f.write_text("\n   \nkey-raw\nignored-second-line\n")
    assert _client()._parse_secret_file(str(f), "K") == "key-raw"


def test_parse_empty_file_returns_none(tmp_path):
    f = tmp_path / "K"
    f.write_text("   \n\n")
    assert _client()._parse_secret_file(str(f), "K") is None


def test_parse_superstring_var_not_matched(tmp_path):
    f = tmp_path / "K"
    # A different variable whose name contains K as a prefix must not match;
    # the line is then treated as the raw first non-empty line.
    f.write_text("K_BACKUP=key-other\n")
    assert _client()._parse_secret_file(str(f), "K") == "K_BACKUP=key-other"


def test_resolve_env_wins_over_file(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    (tmp_path / "K").write_text("from-file\n")
    monkeypatch.setenv("K", "from-env")
    assert _client()._resolve_secret("K") == "from-env"


def test_resolve_uses_file_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("K", raising=False)
    (tmp_path / "K").write_text("from-file\n")
    assert _client()._resolve_secret("K") == "from-file"


def test_resolve_none_when_neither(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("K", raising=False)
    assert _client()._resolve_secret("K") is None


def test_get_api_key_exits_when_unresolved(tmp_path, monkeypatch, config):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = object.__new__(scan_namer.BaseLLMClient)
    client.config = config
    client.provider = "anthropic"
    with pytest.raises(SystemExit):
        client._get_api_key()


def test_get_api_key_resolves_from_file(tmp_path, monkeypatch, config):
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "ANTHROPIC_API_KEY").write_text('export ANTHROPIC_API_KEY="key-file"\n')
    client = object.__new__(scan_namer.BaseLLMClient)
    client.config = config
    client.provider = "anthropic"
    assert client._get_api_key() == "key-file"


def test_parse_source_form(tmp_path):
    f = tmp_path / "K"
    f.write_text('source K="key-sourced"\n')
    assert _client()._parse_secret_file(str(f), "K") == "key-sourced"


def test_parse_any_name_lone_assignment(tmp_path):
    f = tmp_path / "OTHER"
    f.write_text("export OTHER='key-other'\n")
    assert _client()._parse_secret_file(str(f), "K", any_name=True) == "key-other"


def test_parse_any_name_prefers_matching_assignment(tmp_path):
    f = tmp_path / "K"
    f.write_text("export OTHER=key-other\nexport K=key-mine\n")
    assert _client()._parse_secret_file(str(f), "K", any_name=True) == "key-mine"


def test_parse_any_name_ambiguous_returns_none(tmp_path):
    f = tmp_path / "K"
    f.write_text("A=key-a\nB=key-b\n")
    assert _client()._parse_secret_file(str(f), "K", any_name=True) is None


def _keyfile_client(config, monkeypatch, tmp_path, key_file, provider="anthropic"):
    """A client whose provider block sets api_key_file, with no ambient key."""
    monkeypatch.setattr(scan_namer, "APP_DIR", str(tmp_path))
    # setenv first so monkeypatch restores the variable the client writes.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    config.config["llm"]["providers"][provider]["api_key_file"] = key_file
    client = object.__new__(scan_namer.BaseLLMClient)
    client.config = config
    client.provider = provider
    return client


def test_api_key_file_sets_env_and_is_used(tmp_path, monkeypatch, config):
    key = tmp_path / "keys" / "ANTHROPIC_API_KEY"
    key.parent.mkdir()
    key.write_text("export ANTHROPIC_API_KEY='key-keyfile'\n")
    client = _keyfile_client(config, monkeypatch, tmp_path, str(key))
    assert client._get_api_key() == "key-keyfile"
    assert scan_namer.os.environ["ANTHROPIC_API_KEY"] == "key-keyfile"


def test_env_wins_over_api_key_file(tmp_path, monkeypatch, config):
    key = tmp_path / "k"
    key.write_text('source ANTHROPIC_API_KEY="key-keyfile"\n')
    client = _keyfile_client(config, monkeypatch, tmp_path, str(key))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-env")
    assert client._get_api_key() == "key-env"


def test_api_key_file_wins_over_app_dir_file(tmp_path, monkeypatch, config):
    key = tmp_path / "keys" / "k"
    key.parent.mkdir()
    key.write_text("key-keyfile\n")
    client = _keyfile_client(config, monkeypatch, tmp_path, str(key))
    (tmp_path / "ANTHROPIC_API_KEY").write_text("key-appdir\n")
    assert client._get_api_key() == "key-keyfile"


def test_api_key_file_expands_env_vars_and_tilde(tmp_path, monkeypatch, config):
    (tmp_path / "ANTHROPIC_API_KEY").write_text("key-expanded\n")
    monkeypatch.setenv("SCAN_NAMER_TEST_KEYS", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    client = _keyfile_client(
        config,
        monkeypatch,
        tmp_path / "appdir",
        "$SCAN_NAMER_TEST_KEYS/ANTHROPIC_API_KEY",
    )
    assert client._get_api_key() == "key-expanded"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    client = _keyfile_client(
        config, monkeypatch, tmp_path / "appdir", "~/ANTHROPIC_API_KEY"
    )
    assert client._get_api_key() == "key-expanded"


def test_api_key_file_missing_falls_back_to_app_dir(
    tmp_path, monkeypatch, config, caplog
):
    client = _keyfile_client(config, monkeypatch, tmp_path, str(tmp_path / "absent"))
    (tmp_path / "ANTHROPIC_API_KEY").write_text("key-appdir\n")
    assert client._get_api_key() == "key-appdir"
    assert "not found" in caplog.text


def test_api_key_file_without_key_falls_back_to_app_dir(tmp_path, monkeypatch, config):
    key = tmp_path / "k"
    key.write_text("A=1\nB=2\n")
    client = _keyfile_client(config, monkeypatch, tmp_path, str(key))
    (tmp_path / "ANTHROPIC_API_KEY").write_text("key-appdir\n")
    assert client._get_api_key() == "key-appdir"


@pytest.mark.parametrize(
    "bad",
    [
        "relative/ANTHROPIC_API_KEY",
        "",
        "   ",
        42,
        ["/a"],
        "$SCAN_NAMER_UNSET_VAR_XYZ/k",
    ],
)
def test_api_key_file_invalid_value_exits(tmp_path, monkeypatch, config, bad):
    monkeypatch.delenv("SCAN_NAMER_UNSET_VAR_XYZ", raising=False)
    client = _keyfile_client(config, monkeypatch, tmp_path, bad)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-env")
    with pytest.raises(SystemExit):
        client._get_api_key()


def test_api_key_file_null_is_unset(tmp_path, monkeypatch, config):
    client = _keyfile_client(config, monkeypatch, tmp_path, None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-env")
    assert client._get_api_key() == "key-env"


def test_lmstudio_uses_api_key_file(tmp_path, monkeypatch, config):
    key = tmp_path / "k"
    key.write_text("export LMSTUDIO_API_KEY=key-lm\n")
    monkeypatch.setenv("LMSTUDIO_API_KEY", "")
    monkeypatch.delenv("LMSTUDIO_API_KEY")
    config.config["llm"]["providers"]["lmstudio"] = {
        "api_key_env": "LMSTUDIO_API_KEY",
        "api_key_file": str(key),
    }
    client = object.__new__(scan_namer.LMStudioClient)
    client.config = config
    client.provider = "lmstudio"
    assert client._get_api_key() == "key-lm"


@pytest.mark.parametrize("raw", ["abc123==", "abc123="])
def test_parse_any_name_raw_key_with_equals(tmp_path, raw):
    f = tmp_path / "K"
    f.write_text(raw + "\n")
    assert _client()._parse_secret_file(str(f), "K", any_name=True) == raw
