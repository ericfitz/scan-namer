import pytest

import scan_namer


def _client():
    """A BaseLLMClient with no __init__ side effects."""
    return object.__new__(scan_namer.BaseLLMClient)


def test_parse_export_form(tmp_path):
    f = tmp_path / "ANTHROPIC_API_KEY"
    f.write_text('export ANTHROPIC_API_KEY="sk-abc"\n')
    assert _client()._parse_secret_file(str(f), "ANTHROPIC_API_KEY") == "sk-abc"


def test_parse_bare_assignment(tmp_path):
    f = tmp_path / "ANTHROPIC_API_KEY"
    f.write_text("ANTHROPIC_API_KEY=sk-bare\n")
    assert _client()._parse_secret_file(str(f), "ANTHROPIC_API_KEY") == "sk-bare"


def test_parse_single_quotes_stripped(tmp_path):
    f = tmp_path / "K"
    f.write_text("K='sk-single'\n")
    assert _client()._parse_secret_file(str(f), "K") == "sk-single"


def test_parse_mismatched_quotes_not_stripped(tmp_path):
    f = tmp_path / "K"
    f.write_text("K='sk-x\"\n")
    # Opening ' and closing " do not match -> left intact.
    assert _client()._parse_secret_file(str(f), "K") == "'sk-x\""


def test_parse_raw_key_first_nonempty_line(tmp_path):
    f = tmp_path / "K"
    f.write_text("\n   \nsk-raw\nignored-second-line\n")
    assert _client()._parse_secret_file(str(f), "K") == "sk-raw"


def test_parse_empty_file_returns_none(tmp_path):
    f = tmp_path / "K"
    f.write_text("   \n\n")
    assert _client()._parse_secret_file(str(f), "K") is None


def test_parse_superstring_var_not_matched(tmp_path):
    f = tmp_path / "K"
    # A different variable whose name contains K as a prefix must not match;
    # the line is then treated as the raw first non-empty line.
    f.write_text("K_BACKUP=sk-other\n")
    assert _client()._parse_secret_file(str(f), "K") == "K_BACKUP=sk-other"


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
    (tmp_path / "ANTHROPIC_API_KEY").write_text('export ANTHROPIC_API_KEY="sk-file"\n')
    client = object.__new__(scan_namer.BaseLLMClient)
    client.config = config
    client.provider = "anthropic"
    assert client._get_api_key() == "sk-file"
