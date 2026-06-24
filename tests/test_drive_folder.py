import scan_namer


def _manager(folders):
    """A GoogleDriveManager with no auth side effects and a stubbed listing."""
    mgr = object.__new__(scan_namer.GoogleDriveManager)
    mgr.list_folders = lambda: folders
    return mgr


def test_unique_match_returns_id():
    mgr = _manager([{"id": "id-1", "name": "Scans"}, {"id": "id-2", "name": "Other"}])
    assert mgr.resolve_folder("Scans") == "id-1"


def test_match_is_case_insensitive():
    mgr = _manager([{"id": "id-1", "name": "Scans"}])
    assert mgr.resolve_folder("scANS") == "id-1"


def test_no_match_returns_none():
    mgr = _manager([{"id": "id-1", "name": "Scans"}])
    assert mgr.resolve_folder("Missing") is None


def test_multiple_matches_returns_none():
    mgr = _manager(
        [{"id": "id-1", "name": "Scans"}, {"id": "id-2", "name": "scans"}]
    )
    assert mgr.resolve_folder("Scans") is None
