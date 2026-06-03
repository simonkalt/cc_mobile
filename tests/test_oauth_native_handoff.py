from app.services.oauth_native_handoff import (
    consume_oauth_native_handoff,
    store_oauth_native_handoff,
)


def test_oauth_native_handoff_store_and_consume():
    store_oauth_native_handoff(
        state="test-state-1",
        provider="google",
        code="auth-code-xyz",
    )
    handoff = consume_oauth_native_handoff("test-state-1", "google")
    assert handoff is not None
    assert handoff.code == "auth-code-xyz"
    assert consume_oauth_native_handoff("test-state-1", "google") is None


def test_oauth_native_handoff_provider_mismatch():
    store_oauth_native_handoff(
        state="test-state-2",
        provider="google",
        code="c",
    )
    assert consume_oauth_native_handoff("test-state-2", "linkedin") is None
