from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None


def load_env(env_path: str | None = None) -> None:
    """Load environment variables from `.env` without failing if dotenv is absent."""
    if load_dotenv is None:
        return

    if env_path is not None:
        load_dotenv(env_path)
        return

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
