import json
import logging

import pytest

import scan_namer
from tests.conftest import MINIMAL_CONFIG


def _write_config(path):
    path.write_text(json.dumps(MINIMAL_CONFIG))


def test_config_file_path_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path / "cfg.json")
    cm = scan_namer.ConfigManager("~/cfg.json")
    assert cm.config_file == str(tmp_path / "cfg.json")


def test_config_file_path_expands_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_CFG_DIR", str(tmp_path))
    _write_config(tmp_path / "cfg.json")
    cm = scan_namer.ConfigManager("${SCAN_CFG_DIR}/cfg.json")
    assert cm.config_file == str(tmp_path / "cfg.json")


def test_config_file_path_unset_var_exits(monkeypatch):
    monkeypatch.delenv("SCAN_NAMER_UNSET_VAR", raising=False)
    with pytest.raises(SystemExit):
        scan_namer.ConfigManager("$SCAN_NAMER_UNSET_VAR/cfg.json")


def test_download_dir_expands_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SCANS_DIR", str(tmp_path))
    assert scan_namer.ScanNamer._resolve_download_dir("$SCANS_DIR") == str(tmp_path)


def test_download_dir_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Downloads").mkdir()
    got = scan_namer.ScanNamer._resolve_download_dir("~/Downloads")
    assert got == str(tmp_path / "Downloads")


def test_download_dir_none_stays_none():
    assert scan_namer.ScanNamer._resolve_download_dir(None) is None


def test_download_dir_unset_var_exits(monkeypatch):
    monkeypatch.delenv("SCAN_NAMER_UNSET_VAR", raising=False)
    with pytest.raises(SystemExit):
        scan_namer.ScanNamer._resolve_download_dir("$SCAN_NAMER_UNSET_VAR/x")


def test_download_dir_missing_exits(tmp_path):
    with pytest.raises(SystemExit):
        scan_namer.ScanNamer._resolve_download_dir(str(tmp_path / "nope"))


@pytest.mark.parametrize("raw", ["~/logs/scan.log", "$LOGS_HOME/logs/scan.log"])
def test_log_file_expanded(config, monkeypatch, tmp_path, raw):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOGS_HOME", str(tmp_path))
    (tmp_path / "logs").mkdir()
    config.config["logging"]["file"] = raw
    namer = object.__new__(scan_namer.ScanNamer)
    namer.config = config

    captured = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: captured.update(kw))
    namer._setup_logging()
    for h in captured["handlers"]:
        h.close()
    assert (tmp_path / "logs" / "scan.log").exists()


def test_log_file_env_override_expanded(config, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOG_FILE", "~/env.log")
    namer = object.__new__(scan_namer.ScanNamer)
    namer.config = config

    captured = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: captured.update(kw))
    namer._setup_logging()
    for h in captured["handlers"]:
        h.close()
    assert (tmp_path / "env.log").exists()


def test_log_file_unset_var_exits(config, monkeypatch):
    monkeypatch.delenv("SCAN_NAMER_UNSET_VAR", raising=False)
    config.config["logging"]["file"] = "$SCAN_NAMER_UNSET_VAR/scan.log"
    namer = object.__new__(scan_namer.ScanNamer)
    namer.config = config
    with pytest.raises(SystemExit):
        namer._setup_logging()
