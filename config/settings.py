"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer from the environment, falling back safely."""
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings whose defaults may be overridden by environment variables."""

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "")
    ollama_timeout_seconds: int = _positive_int("OLLAMA_TIMEOUT_SECONDS", 120)
    review_chunk_size: int = _positive_int("REVIEW_CHUNK_SIZE", 6000)
    ollama_allowed_hosts: tuple[str, ...] = tuple(
        host.strip().lower()
        for host in os.getenv(
            "OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1,::1"
        ).split(",")
        if host.strip()
    )


SETTINGS = Settings()

