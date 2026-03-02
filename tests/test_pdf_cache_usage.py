import asyncio

from app.services import pdf_service


def _print_props(top_margin: float = 1.0):
    return {
        "margins": {"top": top_margin, "right": 0.75, "bottom": 0.75, "left": 0.75},
        "fontFamily": "Times New Roman",
        "fontSize": 12,
        "lineHeight": 1.6,
        "pageSize": {"width": 8.5, "height": 11.0},
        "useDefaultFonts": False,
    }


def _clear_cache_for_identity(identity: str) -> None:
    safe = pdf_service._safe_cache_identity(identity)
    cache_dir = pdf_service._pdf_cache_dir()
    (cache_dir / f"{safe}_last_pdf.pdf").unlink(missing_ok=True)
    (cache_dir / f"{safe}_last_pdf.hash").unlink(missing_ok=True)


def test_generate_pdf_from_html_cache_hit_with_user_email(monkeypatch):
    identity = pdf_service._resolve_cache_identity(None, "cache-user@example.com")
    _clear_cache_for_identity(identity)
    calls = {"count": 0}

    def _fake_generate(_: str) -> bytes:
        calls["count"] += 1
        return b"%PDF-test-cache-email%"

    monkeypatch.setattr(pdf_service, "_generate_pdf_via_libreoffice_html", _fake_generate)

    out1 = asyncio.run(
        pdf_service.generate_pdf_from_html(
            "<p>Hello</p>",
            _print_props(),
            user_email="cache-user@example.com",
        )
    )
    out2 = asyncio.run(
        pdf_service.generate_pdf_from_html(
            "<p>Hello</p>",
            _print_props(),
            user_email="cache-user@example.com",
        )
    )

    assert out1 == out2
    assert calls["count"] == 1


def test_generate_pdf_from_html_return_debug_reports_cache_hit(monkeypatch):
    identity = pdf_service._resolve_cache_identity("debug-user", None)
    _clear_cache_for_identity(identity)
    calls = {"count": 0}

    def _fake_generate(_: str) -> bytes:
        calls["count"] += 1
        return b"%PDF-debug%"

    monkeypatch.setattr(pdf_service, "_generate_pdf_via_libreoffice_html", _fake_generate)

    first_b64, first_hit = asyncio.run(
        pdf_service.generate_pdf_from_html(
            "<p>Hello</p>",
            _print_props(),
            user_id="debug-user",
            return_debug=True,
        )
    )
    second_b64, second_hit = asyncio.run(
        pdf_service.generate_pdf_from_html(
            "<p>Hello</p>",
            _print_props(),
            user_id="debug-user",
            return_debug=True,
        )
    )

    assert first_b64 == second_b64
    assert first_hit is False
    assert second_hit is True
    assert calls["count"] == 1


def test_generate_pdf_from_html_cache_invalidates_on_print_properties_change(monkeypatch):
    identity = pdf_service._resolve_cache_identity("cache-user-2", None)
    _clear_cache_for_identity(identity)
    calls = {"count": 0}

    def _fake_generate(_: str) -> bytes:
        calls["count"] += 1
        return f"%PDF-{calls['count']}%".encode("utf-8")

    monkeypatch.setattr(pdf_service, "_generate_pdf_via_libreoffice_html", _fake_generate)

    out1 = asyncio.run(
        pdf_service.generate_pdf_from_html(
            "<p>Hello</p>",
            _print_props(top_margin=1.0),
            user_id="cache-user-2",
        )
    )
    out2 = asyncio.run(
        pdf_service.generate_pdf_from_html(
            "<p>Hello</p>",
            _print_props(top_margin=0.5),
            user_id="cache-user-2",
        )
    )

    assert out1 != out2
    assert calls["count"] == 2
