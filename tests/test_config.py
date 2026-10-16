"""Runtime config and secret hygiene."""

from __future__ import annotations

import io
import os
import re
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic import ValidationError
from pydantic_ai.usage import UsageLimits

from src.config import (
    PROJECT_ROOT,
    RuntimeConfig,
    ensure_banner_disabled,
    load_runtime_config,
    redact_secrets,
)

_CONTEXT_FILES = (
    "01_CONTEXTO_MAESTRO.md",
    "02_EQUIPO_Y_METODOLOGIA.md",
    "03_PROMPT_MAESTRO_OPENCODE.md",
)
_GITIGNORE_PATTERNS = (
    ".env",
    "*.key",
    "*.pem",
    "*.log",
    "__pycache__/",
    "*.db",
    "*.sqlite3",
)
_ENV_EXAMPLE = (
    "MODO=test\n"
    "MODEL_NAME=test\n"
    "GOOGLE_API_KEY=your-google-api-key\n"
    "OPENAI_API_KEY=your-openai-api-key\n"
    "ANTHROPIC_API_KEY=your-anthropic-api-key\n"
)


@contextmanager
def _temporary_env(updates: dict[str, str | None]):
    previous: dict[str, str | None] = {}
    for key, value in updates.items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def _captured_call(func, *args):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = func(*args)
    return result, stdout.getvalue() + stderr.getvalue()


class RuntimeConfigTests(unittest.TestCase):
    def test_project_root_is_absolute_and_contains_readme(self) -> None:
        import importlib
        import src.config as config_module

        original = os.getcwd()
        try:
            os.chdir(os.environ.get("TEMP") or os.environ.get("TMP") or original)
            reloaded = importlib.reload(config_module)
            root = reloaded.PROJECT_ROOT
            self.assertTrue(root.is_absolute())
            self.assertEqual(root, root.resolve())
            self.assertTrue((root / "README.md").is_file())
            self.assertEqual(root, Path(__file__).resolve().parent.parent)
            self.assertNotEqual(root.resolve(), Path.cwd().resolve())
        finally:
            os.chdir(original)
            importlib.reload(config_module)

    def test_load_runtime_config_defaults_when_modo_and_model_absent(self) -> None:
        with _temporary_env({"MODO": None, "MODEL_NAME": None}):
            config, printed = _captured_call(load_runtime_config)
        self.assertEqual(config.modo, "test")
        self.assertEqual(config.model_name, "test")
        self.assertEqual(printed, "")

    def test_load_runtime_config_honors_environment(self) -> None:
        updates = {
            "MODO": "live",
            "MODEL_NAME": "google-gla:gemini-2.0-flash",
        }
        with _temporary_env(updates):
            config, printed = _captured_call(load_runtime_config)
        self.assertEqual(config.modo, "live")
        self.assertEqual(config.model_name, "google-gla:gemini-2.0-flash")
        self.assertNotIn("google-gla:gemini-2.0-flash", printed)
        self.assertNotIn("live", printed)

    def test_usage_limits_match_budget(self) -> None:
        limits = RuntimeConfig().usage_limits()
        self.assertIsInstance(limits, UsageLimits)
        self.assertEqual(limits.request_limit, 4)
        self.assertEqual(limits.tool_calls_limit, 5)
        self.assertEqual(limits.total_tokens_limit, 4000)

        custom = RuntimeConfig(
            request_limit=2,
            tool_calls_limit=3,
            total_tokens_limit=100,
        ).usage_limits()
        self.assertEqual(custom.request_limit, 2)
        self.assertEqual(custom.tool_calls_limit, 3)
        self.assertEqual(custom.total_tokens_limit, 100)

    def test_redact_secrets_hides_env_value(self) -> None:
        fake = "fake-google-key-not-real-xyz987"
        line = f"start {fake} middle {fake} end"
        with _temporary_env({"GOOGLE_API_KEY": fake}):
            redacted, printed = _captured_call(redact_secrets, line)
        self.assertIn("[REDACTED]", redacted)
        self.assertEqual(redacted.count("[REDACTED]"), 2)
        if fake in redacted or fake in printed:
            self.fail("secret value was exposed")

    def test_redact_secrets_masks_key_shaped_substrings(self) -> None:
        openai_like = "sk-" + ("abCD12" * 4)
        google_like = "AIza" + ("SyD987" * 4)
        line = f"openai={openai_like} google={google_like}"
        redacted, printed = _captured_call(redact_secrets, line)
        self.assertIn("[REDACTED]", redacted)
        if openai_like in redacted or google_like in redacted:
            self.fail("key-shaped substring was exposed")
        if openai_like in printed or google_like in printed:
            self.fail("key-shaped substring was printed")

    def test_redact_secrets_hides_short_env_value(self) -> None:
        fake = "q7z4"
        with _temporary_env({"API_TOKEN": fake}):
            redacted, printed = _captured_call(redact_secrets, f"token={fake}")
        if "[REDACTED]" not in redacted or fake in redacted or fake in printed:
            self.fail("short secret value was exposed")

    def test_redact_secrets_keeps_text_when_secret_value_blank(self) -> None:
        sample = "hello   world"
        for blank in ("", "   "):
            with _temporary_env({"EMPTY_API_KEY": blank}):
                redacted, _printed = _captured_call(redact_secrets, sample)
            self.assertEqual(redacted, sample)

    def test_redact_secrets_ignores_unrelated_env_values(self) -> None:
        marker = "plain-color-value-not-a-secret"
        with _temporary_env({"APP_COLOR": marker}):
            redacted, printed = _captured_call(
                redact_secrets,
                f"color={marker}",
            )
        self.assertEqual(redacted, f"color={marker}")
        self.assertNotIn(marker, printed)

    def test_ensure_banner_disabled_when_unset(self) -> None:
        with _temporary_env({"PYDANTIC_AI_NO_BANNER": None}):
            ensure_banner_disabled()
            self.assertEqual(os.environ.get("PYDANTIC_AI_NO_BANNER"), "1")

    def test_load_runtime_config_disables_banner(self) -> None:
        with _temporary_env(
            {"MODO": None, "MODEL_NAME": None, "PYDANTIC_AI_NO_BANNER": None}
        ):
            load_runtime_config()
            self.assertEqual(os.environ.get("PYDANTIC_AI_NO_BANNER"), "1")

    def test_gitignore_preserves_context_files_and_blocks_secrets(self) -> None:
        text = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines()]
        for entry in _CONTEXT_FILES + _GITIGNORE_PATTERNS:
            self.assertIn(entry, lines)

    def test_env_example_has_placeholders_only(self) -> None:
        path = PROJECT_ROOT / ".env.example"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn("MODO=test", text)
        self.assertEqual(text, _ENV_EXAMPLE)
        self.assertIsNone(re.search(r"sk-\S{10,}", text))
        for token in re.findall(r"AIza\S*", text):
            self.assertLessEqual(len(token), 10)

    def test_invalid_modo_banana_raises(self) -> None:
        with _temporary_env({"MODO": "banana"}):
            with self.assertRaises(ValidationError):
                load_runtime_config()


if __name__ == "__main__":
    unittest.main()
