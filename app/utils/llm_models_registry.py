"""
Canonical list of LLM model ids and which one is the default for new users / UI.

Source of truth: llm-models-registry.json (override path with LLM_MODELS_REGISTRY_PATH).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _registry_path() -> Path:
    """Project root llm-models-registry.json unless LLM_MODELS_REGISTRY_PATH is set."""
    env = os.getenv("LLM_MODELS_REGISTRY_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent / "llm-models-registry.json"


def load_models_registry() -> Dict[str, Any]:
    """
    Load the models registry JSON.

    Returns:
        Parsed object (expects top-level \"models\": [ {\"name\", \"default\"}, ... ]).

    Raises:
        FileNotFoundError: If the registry file is missing.
        ValueError: If structure is invalid.
    """
    path = _registry_path()
    if not path.exists():
        raise FileNotFoundError(f"LLM models registry not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Models registry root must be a JSON object")
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("Models registry must contain a non-empty 'models' array")
    for i, entry in enumerate(models):
        if not isinstance(entry, dict):
            raise ValueError(f"models[{i}] must be an object")
        if "name" not in entry or not str(entry["name"]).strip():
            raise ValueError(f"models[{i}] must have a non-empty 'name'")
        if "default" not in entry or not isinstance(entry["default"], bool):
            raise ValueError(f"models[{i}] must have boolean 'default'")
    return data


def list_registry_model_names() -> List[str]:
    """Return all model ids declared in the registry."""
    data = load_models_registry()
    return [str(m["name"]).strip() for m in data["models"] if isinstance(m, dict)]


def get_default_model_name_from_registry() -> Optional[str]:
    """
    Return the model `name` for the single entry with default: true.

    Returns None if the file is missing, malformed, or does not define exactly one default.
    """
    try:
        data = load_models_registry()
    except FileNotFoundError as e:
        logger.warning("%s", e)
        return None
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.warning("Invalid LLM models registry: %s", e)
        return None

    defaults = [
        str(m["name"]).strip()
        for m in data["models"]
        if isinstance(m, dict) and m.get("default") is True
    ]
    if len(defaults) != 1:
        logger.error(
            "Models registry must have exactly one default model; found %d (%s)",
            len(defaults),
            defaults,
        )
        return None
    return defaults[0]
