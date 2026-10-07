import os

import pytest

import scan_namer


def _manager(config):
    """A GoogleDriveManager with no auth side effects."""
    mgr = object.__new__(scan_namer.GoogleDriveManager)
    mgr.config = config
    return mgr


def _set(config, key, value):
    config.config["google_drive"][key] = value


def test_expand_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    got = scan_namer.expand_config_path("k", "~/.keys/credentials.json")
    assert got == str(tmp_path / ".keys" / "credentials.json")


def test_expand_env_var(monkeypatch):
    monkeypatch.setenv("SN_KEYS", "/keys")
    assert scan_namer.expand_config_path("k", "${SN_KEYS}/c.json") == "/keys/c.json"
    assert scan_namer.expand_config_path("k", "$SN_KEYS/c.json") == "/keys/c.json"


def test_expand_strips_whitespace():
    assert scan_namer.expand_config_path("k", "  /a/b.json \n") == "/a/b.json"


def test_expand_unset_var_exits(monkeypatch):
    monkeypatch.delenv("SN_UNSET", raising=False)
    with pytest.raises(SystemExit):
        scan_namer.expand_config_path("k", "$SN_UNSET/c.json")


@pytest.mark.parametrize("raw", ["", "   ", 42, ["a"]])
def test_expand_rejects_non_path(raw):
    with pytest.raises(SystemExit):
        scan_namer.expand_config_path("k", raw)


def test_expand_relative_allowed_by_default():
    assert scan_namer.expand_config_path("k", "credentials.json") == "credentials.json"


def test_expand_relative_rejected_when_absolute_required():
    with pytest.raises(SystemExit):
        scan_namer.expand_config_path("k", "credentials.json", require_absolute=True)


def test_drive_credentials_path_expands_tilde(config, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _set(config, "credentials_file", "~/.keys/credentials.json")
    got = _manager(config)._drive_file_path("credentials_file")
    assert got == str(tmp_path / ".keys" / "credentials.json")


def test_drive_token_path_expands_tilde(config, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _set(config, "token_file", "~/state/token.json")
    got = _manager(config)._drive_file_path("token_file")
    assert got == str(tmp_path / "state" / "token.json")


def test_drive_path_relative_kept(config):
    assert _manager(config)._drive_file_path("credentials_file") == "credentials.json"


def test_drive_path_env_override_expanded(config, monkeypatch, tmp_path):
    # dotenv does not expand ~, so a .env value must be expanded here.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "~/elsewhere/c.json")
    got = _manager(config)._drive_file_path("credentials_file")
    assert got == str(tmp_path / "elsewhere" / "c.json")


def test_drive_path_unset_returns_none(config):
    del config.config["google_drive"]["token_file"]
    assert _manager(config)._drive_file_path("token_file") is None


def test_drive_path_unset_var_exits(config, monkeypatch):
    monkeypatch.delenv("SN_UNSET", raising=False)
    _set(config, "credentials_file", "$SN_UNSET/credentials.json")
    with pytest.raises(SystemExit):
        _manager(config)._drive_file_path("credentials_file")


def test_drive_path_empty_exits(config):
    _set(config, "credentials_file", "")
    with pytest.raises(SystemExit):
        _manager(config)._drive_file_path("credentials_file")


def test_authenticate_missing_credentials_exits(config, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _set(config, "credentials_file", "~/.keys/credentials.json")
    _set(config, "token_file", str(tmp_path / "token.json"))
    with pytest.raises(SystemExit):
        _manager(config)._authenticate()
    assert not os.path.exists(tmp_path / "token.json")


def test_authenticate_uses_expanded_paths(config, monkeypatch, tmp_path):
    """The OAuth flow reads the expanded credentials path and the token is
    written to the expanded token path, not a literal '~' directory."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    keys = tmp_path / ".keys"
    keys.mkdir()
    (keys / "credentials.json").write_text("{}")
    _set(config, "credentials_file", "~/.keys/credentials.json")
    _set(config, "token_file", "~/token.json")

    seen = {}

    class FakeCreds:
        def to_json(self):
            return '{"fake": true}'

    class FakeFlow:
        def run_local_server(self, port):
            return FakeCreds()

    def fake_from_client_secrets_file(path, scopes):
        seen["creds_path"] = path
        return FakeFlow()

    monkeypatch.setattr(
        scan_namer.InstalledAppFlow,
        "from_client_secrets_file",
        fake_from_client_secrets_file,
    )
    monkeypatch.setattr(scan_namer, "build", lambda *a, **k: object())

    _manager(config)._authenticate()

    assert seen["creds_path"] == str(keys / "credentials.json")
    assert (tmp_path / "token.json").read_text() == '{"fake": true}'
    assert (tmp_path / "token.json").stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / "~").exists()


def test_write_token_creates_mode_600(tmp_path):
    path = tmp_path / "token.json"
    scan_namer.GoogleDriveManager._write_token(str(path), '{"t": 1}')
    assert path.read_text() == '{"t": 1}'
    assert path.stat().st_mode & 0o777 == 0o600


def test_write_token_tightens_existing_file(tmp_path):
    path = tmp_path / "token.json"
    path.write_text("old-and-longer-content")
    path.chmod(0o644)
    scan_namer.GoogleDriveManager._write_token(str(path), "new")
    assert path.read_text() == "new"
    assert path.stat().st_mode & 0o777 == 0o600
