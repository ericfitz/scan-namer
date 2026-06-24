import scan_namer


def _scan_namer():
    return object.__new__(scan_namer.ScanNamer)


def test_clean_strips_quotes_invalid_chars_and_extension():
    sn = _scan_namer()
    assert sn._clean_filename('  "Hello: World/Test.pdf"  ') == "Hello_World_Test"


def test_clean_collapses_repeats_and_trims_underscores():
    sn = _scan_namer()
    assert sn._clean_filename("__a   b__") == "a_b"


def test_clean_truncates_to_max_length(monkeypatch):
    monkeypatch.setenv("MAX_FILENAME_LENGTH", "5")
    sn = _scan_namer()
    assert sn._clean_filename("abcdefghij") == "abcde"


def test_clean_empty_returns_empty_string():
    sn = _scan_namer()
    assert sn._clean_filename("   ") == ""


def test_generic_default_matches_raven_scan():
    sn = _scan_namer()
    assert sn._is_generic_filename("20240108_Raven_Scan.pdf") is True


def test_generic_non_match_returns_false():
    sn = _scan_namer()
    assert sn._is_generic_filename("Tax_Return_2023.pdf") is False


def test_generic_env_patterns_override(monkeypatch):
    monkeypatch.setenv("GENERIC_FILENAME_PATTERNS", "invoice,receipt")
    sn = _scan_namer()
    assert sn._is_generic_filename("Invoice_001.pdf") is True
    assert sn._is_generic_filename("20240108_Raven_Scan.pdf") is False
