from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")

NEXT_KEY_STATUS_CODES = {429, 492}
RESET_KEY_STATUS_CODES = {503}
_DEFAULT_MANAGER: GeminiManager | None = None
_DEFAULT_MANAGER_KEYS: tuple[str, ...] = ()


def _split_keys(raw_values: Sequence[str | None]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        if not raw_value:
            continue
        for key in re.split(r"[\s,;]+", raw_value):
            key = key.strip().strip("\"'")
            if key and key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


def load_google_api_keys() -> list[str]:
    """Load Gemini keys from single-key or comma-separated environment vars."""
    indexed_names = sorted(
        (
            name
            for name in os.environ
            if re.fullmatch(r"(?:GOOGLE_API_KEY|GEMINI_API_KEY)_\d+", name)
        ),
        key=lambda name: int(name.rsplit("_", 1)[1]),
    )
    return _split_keys(
        [
            os.environ.get("GOOGLE_API_KEYS"),
            os.environ.get("GEMINI_API_KEYS"),
            os.environ.get("GOOGLE_API_KEY"),
            os.environ.get("GEMINI_API_KEY"),
            *(os.environ.get(name) for name in indexed_names),
        ]
    )


def error_status_code(exc: BaseException) -> int | None:
    """Best-effort status extraction across google-genai and legacy SDK errors."""
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    text = f"{type(exc).__name__}: {exc}"
    match = re.search(r"\b(429|492|503)\b", text)
    if match:
        return int(match.group(1))
    if "RESOURCE_EXHAUSTED" in text.upper():
        return 429
    if "UNAVAILABLE" in text.upper():
        return 503
    return None


@dataclass
class GeminiManager:
    """Small key-rotation helper for Gemini calls.

    492/429 advances to the next key. 503 rebuilds and retries the current key
    once, then advances if that key keeps failing.
    """

    keys: Sequence[str]
    index: int = 0
    _reset_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.keys = [key.strip() for key in self.keys if key and key.strip()]
        if not self.keys:
            raise ValueError(
                "No Gemini API key found. Set GOOGLE_API_KEYS, GEMINI_API_KEYS, "
                "GOOGLE_API_KEY, or GEMINI_API_KEY."
            )
        self.index %= len(self.keys)

    @classmethod
    def from_env(cls) -> "GeminiManager":
        return cls(load_google_api_keys())

    @property
    def current_key(self) -> str:
        return self.keys[self.index]

    def next_key(self) -> str:
        self.index = (self.index + 1) % len(self.keys)
        return self.current_key

    def reset_key(self) -> str:
        key = self.current_key
        self._reset_counts[key] = self._reset_counts.get(key, 0) + 1
        return key

    def run(self, call: Callable[[str], T]) -> T:
        attempts = 0
        max_attempts = max(1, len(self.keys) * 2)
        last_error: BaseException | None = None

        while attempts < max_attempts:
            key = self.current_key
            try:
                return call(key)
            except Exception as exc:
                status_code = error_status_code(exc)
                if status_code not in (NEXT_KEY_STATUS_CODES | RESET_KEY_STATUS_CODES):
                    raise

                last_error = exc
                attempts += 1

                if status_code in NEXT_KEY_STATUS_CODES:
                    self.next_key()
                    continue

                if self._reset_counts.get(key, 0) == 0:
                    self.reset_key()
                    continue

                if len(self.keys) > 1:
                    self.next_key()
                    continue

        if last_error is not None:
            raise last_error
        raise RuntimeError("Gemini manager exhausted attempts without running a call.")


def get_default_gemini_manager() -> GeminiManager:
    """Return a process-level manager so key rotation persists across calls."""
    global _DEFAULT_MANAGER, _DEFAULT_MANAGER_KEYS

    keys = tuple(load_google_api_keys())
    if _DEFAULT_MANAGER is None or keys != _DEFAULT_MANAGER_KEYS:
        _DEFAULT_MANAGER = GeminiManager(keys)
        _DEFAULT_MANAGER_KEYS = keys
    return _DEFAULT_MANAGER
