from app.utils.docx_generator import _plain_text_to_blocks


def _collect_text_runs(block):
    return [r for r in block["runs"] if not r.get("line_break")]


def test_spaced_asterisk_bold_is_converted():
    blocks = _plain_text_to_blocks("Start * * test text text * * end")
    runs = _collect_text_runs(blocks[0])
    assert any(r.get("bold") and r.get("text", "").strip() == "test text text" for r in runs)


def test_spaced_underscore_bold_is_converted():
    blocks = _plain_text_to_blocks("Before _ _ alpha beta _ _ after")
    runs = _collect_text_runs(blocks[0])
    assert any(r.get("bold") and r.get("text", "").strip() == "alpha beta" for r in runs)
