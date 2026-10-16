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
        if not value or not value.strip():
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


def _replace_literals(text: str, secrets: list[str]) -> str:
    if not secrets:
        return text
    pattern = re.compile("|".join(re.escape(secret) for secret in secrets))
    return pattern.sub("[REDACTED]", text)


def _replace_standalone(text: str, secrets: list[str]) -> str:
    if not secrets:
        return text
    parts = [
        rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])" for secret in secrets
    ]
    return re.compile("|".join(parts)).sub("[REDACTED]", text)


def redact_secrets(text: str) -> str:
    """Replace key-shaped tokens, then secret env values, with [REDACTED].

    Env vars whose names contain KEY, TOKEN, SECRET, PASSWORD, or CREDENTIAL
    are treated as secrets. Values of length 8 or more are removed as
    substrings, longest first. Shorter values are removed only as standalone
    tokens. The raw secret is never returned or printed.
    """
    text = _KEY_SHAPED_RE.sub("[REDACTED]", text)
    secrets = _secret_env_values()
    long_secrets = [secret for secret in secrets if len(secret) >= 8]
    short_secrets = [secret for secret in secrets if len(secret) < 8]
    text = _replace_literals(text, long_secrets)
    return _replace_standalone(text, short_secrets)
