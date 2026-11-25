"""Pluggable LLM backends (command-line tools) sharing one call shape: complete(system, user) -> text."""

import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

TIMEOUT_SECONDS = 600


class BackendError(RuntimeError):
    pass


class Backend(Protocol):
    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str: ...


def _run(argv: list[str], prompt: str | None) -> str:
    try:
        result = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except FileNotFoundError as error:
        raise BackendError(f"{argv[0]} is not installed or not on PATH") from error
    except subprocess.TimeoutExpired as error:
        raise BackendError(f"{argv[0]} timed out after {TIMEOUT_SECONDS}s") from error
    if result.returncode != 0:
        raise BackendError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()[-500:]}")
    return result.stdout


class CodexBackend:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "last-message.txt"
            argv = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never", "-o", str(out)]
            if self.model:
                argv += ["-m", self.model]
            _run(argv + ["-"], f"{system}\n\n---\n\n{user}")
            if not out.exists():
                raise BackendError("codex produced no output message")
            return out.read_text(encoding="utf-8").strip()


class GeminiBackend:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        argv = ["gemini", "-p", f"{system}\n\n---\n\n{user}"]
        if self.model:
            argv += ["-m", self.model]
        return _run(argv, None).strip()


class ClaudeBackend:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        argv = ["claude", "-p", "--no-session-persistence", "--system-prompt", system]
        if self.model:
            argv += ["--model", self.model]
        return _run(argv, user).strip()


BACKENDS = {"claude": ClaudeBackend, "codex": CodexBackend, "gemini": GeminiBackend}


def get_backend(name: str, model: str | None = None) -> Backend:
    try:
        return BACKENDS[name](model)
    except KeyError:
        raise BackendError(f"Unknown backend {name!r}; choose from {', '.join(sorted(BACKENDS))}") from None
