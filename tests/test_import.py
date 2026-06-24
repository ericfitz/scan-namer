import scan_namer


def test_module_imports():
    assert hasattr(scan_namer, "ScanNamer")


def test_app_dir_is_set():
    assert isinstance(scan_namer.APP_DIR, str)
    assert scan_namer.APP_DIR
