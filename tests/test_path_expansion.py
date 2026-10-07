import json
import logging
import os

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


def test_default_config_file_without_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert scan_namer.default_config_file() == str(
        tmp_path / ".config" / "scan-namer" / "config.json"
    )


def test_default_config_file_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert scan_namer.default_config_file() == str(
        tmp_path / "xdg" / "scan-namer" / "config.json"
    )


@pytest.mark.parametrize("xdg", ["", "relative/dir"])
def test_default_config_file_ignores_empty_or_relative_xdg(monkeypatch, tmp_path, xdg):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg)
    assert scan_namer.default_config_file() == str(
        tmp_path / ".config" / "scan-namer" / "config.json"
    )


def test_config_manager_default_reads_xdg_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "scan-namer").mkdir()
    _write_config(tmp_path / "scan-namer" / "config.json")
    cm = scan_namer.ConfigManager()
    assert cm.config_file == str(tmp_path / "scan-namer" / "config.json")


def test_config_manager_default_reads_home_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    cfg_dir = tmp_path / ".config" / "scan-namer"
    cfg_dir.mkdir(parents=True)
    _write_config(cfg_dir / "config.json")
    monkeypatch.chdir(tmp_path)  # no ./config.json to fall back on
    cm = scan_namer.ConfigManager()
    assert cm.config_file == str(cfg_dir / "config.json")


def test_config_manager_missing_default_exits(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit):
        scan_namer.ConfigManager()


def test_prompts_default_is_beside_script(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no ./prompts.json here
    pm = scan_namer.PromptManager()
    assert pm.prompts_file == os.path.join(scan_namer.APP_DIR, "prompts.json")
