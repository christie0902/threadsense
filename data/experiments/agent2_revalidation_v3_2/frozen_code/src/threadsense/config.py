"""Shared local configuration for the interpreter and topic analyst."""

import os
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def get_model_settings() -> tuple[str, str]:
    """Load this checkout's .env, preserving explicit terminal settings."""
    load_dotenv(ENV_FILE, override=False, encoding="utf-8-sig", interpolate=False)
    model = os.getenv("THREADSENSE_MODEL", "openai/gpt-4o-mini").strip()
    if not model:
        raise ValueError("THREADSENSE_MODEL must not be empty.")
    key_name = "OPENROUTER_API_KEY" if model.startswith("openrouter/") else "OPENAI_API_KEY"
    return model, key_name


def get_api_key(key_name: str) -> str:
    """Read the selected credential after get_model_settings loads the .env."""
    api_key = os.getenv(key_name, "").strip()
    if not api_key:
        raise RuntimeError(
            f"{key_name} is not configured. Add it to {ENV_FILE} and run again."
        )
    return api_key
