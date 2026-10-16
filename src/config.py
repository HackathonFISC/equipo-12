"""Runtime configuration and secret redaction."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal


def ensure_banner_disabled() -> None:
    """os.environ.setdefault('PYDANTIC_AI_NO_BANNER', '1')"""
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


# Set the flag before pydantic-ai is imported so it cannot print its banner.
ensure_banner_disabled()

from pydantic import BaseModel
from pydantic_ai.usage import UsageLimits

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

_SECRET_NAME_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_KEY_SHAPED_RE = re.compile(
    r"sk-[A-Za-z0-9_\-]{10,}"
    r"|AIza[A-Za-z0-9_\-]{7,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9\-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
)


def _secret_env_values() -> list[str]:
    found: list[str] = []
    for name, value in os.environ.items():
        upper_name = name.upper()
        if not any(marker in upper_name for marker in _SECRET_NAME_MARKERS):
            continue
        value = value.strip()
        if not value:
            continue
        found.append(value)
    return sorted(set(found), key=len, reverse=True)


class RuntimeConfig(BaseModel):
    modo: Literal["test", "live"] = "test"
    model_name: str = "test"
    request_limit: int = 4
    tool_calls_limit: int = 5
    total_tokens_limit: int = 4000

    def usage_limits(self) -> UsageLimits:
        """Return pydantic_ai.usage.UsageLimits with the three limits above."""
        return UsageLimits(
            request_limit=self.request_limit,
            tool_calls_limit=self.tool_calls_limit,
            total_tokens_limit=self.total_tokens_limit,
        )


def load_runtime_config() -> RuntimeConfig:
    """Read MODO and MODEL_NAME from the environment.

    Default modo is test and model_name is test. Call ensure_banner_disabled().
    Never print env values.
    """
    ensure_banner_disabled()
    modo = os.environ.get("MODO", "test")
    model_name = os.environ.get("MODEL_NAME", "test")
    return RuntimeConfig(modo=modo, model_name=model_name)


def _long_secret_spans(text: str, secrets: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for secret in secrets:
        start = 0
        while True:
            index = text.find(secret, start)
            if index < 0:
                break
            spans.append((index, index + len(secret)))
            start = index + 1
    return spans


def _short_secret_spans(text: str, secrets: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for secret in secrets:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])"
        )
        spans.extend(match.span() for match in pattern.finditer(text))
    return spans


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent half-open spans."""
    if not spans:
        return []
    ordered = sorted(spans)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _secret_spans(text: str) -> list[tuple[int, int]]:
    secrets = _secret_env_values()
    long_secrets = [secret for secret in secrets if len(secret) >= 8]
    short_secrets = [secret for secret in secrets if len(secret) < 8]
    spans = [match.span() for match in _KEY_SHAPED_RE.finditer(text)]
    spans.extend(_long_secret_spans(text, long_secrets))
    spans.extend(_short_secret_spans(text, short_secrets))
    return _merge_spans(spans)


def redact_secrets(text: str) -> str:
    """Replace merged secret spans in the original text with [REDACTED].

    Env vars whose names contain KEY, TOKEN, SECRET, PASSWORD, or CREDENTIAL
    are stripped and treated as secrets. Key-shaped tokens, long secret
    substrings, and short standalone tokens are collected on the original
    text, then overlapping or adjacent spans are replaced together. The raw
    secret is never returned or printed.
    """
    parts: list[str] = []
    cursor = 0
    for start, end in _secret_spans(text):
        parts.append(text[cursor:start])
        parts.append("[REDACTED]")
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)
