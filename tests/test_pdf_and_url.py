import pypdf

import scan_namer


def _write_pdf(path, num_pages, width=200, height=200):
    """Create a real multi-page PDF on disk using pypdf."""
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=width, height=height)
    with open(path, "wb") as f:
        writer.write(f)
    return str(path)


def test_get_page_count_roundtrip(config, tmp_path):
    # Exercises the pypdf-backed PdfReader path end-to-end.
    pdf_path = _write_pdf(tmp_path / "five.pdf", 5)
    proc = scan_namer.PDFProcessor(config)
    assert proc.get_page_count(pdf_path) == 5


def test_extract_pages_roundtrip(config, tmp_path):
    # Writer.add_page + write, then re-read with PdfReader: full migrated path.
    src = _write_pdf(tmp_path / "src.pdf", 5)
    out = tmp_path / "out.pdf"
    proc = scan_namer.PDFProcessor(config)
    assert proc.extract_pages(src, str(out), num_pages=2) is True
    assert proc.get_page_count(str(out)) == 2


def test_extract_text_roundtrip_returns_str(config, tmp_path):
    # Blank pages carry no text; the call must still succeed and return a str.
    pdf_path = _write_pdf(tmp_path / "blank.pdf", 2)
    proc = scan_namer.PDFProcessor(config)
    assert proc.extract_text(pdf_path) == ""


def test_get_page_count_bad_file_returns_zero(config, tmp_path):
    # Error path: a non-PDF file should be handled, not raise.
    bad = tmp_path / "not.pdf"
    bad.write_text("this is not a pdf")
    proc = scan_namer.PDFProcessor(config)
    assert proc.get_page_count(str(bad)) == 0


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
