"""Grok model id constants and helpers (shared to avoid import cycles)."""

GROK_MODEL_ID = "grok-4.3"

LEGACY_GROK_MODEL_IDS = frozenset(
    {
        "grok-4-fast-reasoning",
        "grok-4-fast-reasoning".lower(),
        "xai.grok-4.3",
        "xai.grok-4.3".lower(),
    }
)


def is_grok_model(model: str) -> bool:
    m = (model or "").strip()
    if not m:
        return False
    if m == GROK_MODEL_ID or m.lower() == GROK_MODEL_ID.lower():
        return True
    if m in LEGACY_GROK_MODEL_IDS or m.lower() in LEGACY_GROK_MODEL_IDS:
        return True
    return "grok" in m.lower()
