import scan_namer


def test_should_extract_below_threshold(config):
    proc = scan_namer.PDFProcessor(config)
    assert proc.should_extract(2) is False


def test_should_extract_at_threshold_is_false(config):
    proc = scan_namer.PDFProcessor(config)
    # max_pages_before_extraction == 3; only strictly greater triggers extraction.
    assert proc.should_extract(3) is False


def test_should_extract_above_threshold(config):
    proc = scan_namer.PDFProcessor(config)
    assert proc.should_extract(4) is True


def test_files_url_strips_chat_completions_suffix():
    client = object.__new__(scan_namer.XAIClient)
    client.endpoint = "https://api.x.ai/v1/chat/completions"
    assert client._files_url() == "https://api.x.ai/v1/files"


def test_files_url_without_suffix():
    client = object.__new__(scan_namer.XAIClient)
    client.endpoint = "https://api.x.ai/v1"
    assert client._files_url() == "https://api.x.ai/v1/files"
