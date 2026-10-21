"""Explicit local plugin installation and offline diagnostics; no config rewrites."""
from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path
from typing import Any

from .core import ContextError, parse_json
from .hermes import HermesContextAdapter, PERSISTENCE_FIELDS

DEFAULT_OPTIONS: dict[str, Any] = {
    "threshold_percent": 0.75, "reserved_output": 1024, "request_overhead": 0,
    "safety_margin": 128, "keep_first_turns": 1, "keep_last_turns": 2, "summary_tokens": 384,
}


def validate_options(options: dict[str, Any] | None = None) -> dict[str, Any]:
    if options is not None and (not isinstance(options, dict) or options.keys() - DEFAULT_OPTIONS.keys()):
        raise ContextError("Unsupported plugin options.")
    merged = {**DEFAULT_OPTIONS, **(options or {})}
    HermesContextAdapter(**merged)
    return merged


def read_options(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = stream.read(16385)
        if len(data) > 16384:
            raise ContextError("Plugin options exceed the size limit.")
        return validate_options(parse_json(data.decode("utf-8")))
    except (OSError, UnicodeError):
        raise ContextError("Could not read plugin options.") from None


def create_engine(options: dict[str, Any] | None = None) -> HermesContextAdapter:
    """Bind to the actually installed Hermes ABC; only called by explicit opt-in."""
    try:
        from agent.context_engine import ContextEngine
        from agent.message_metadata import PERSISTENCE_ONLY_MESSAGE_FIELDS
    except ImportError:
        raise ContextError("A compatible Hermes installation is required in this Python environment.") from None
    class HermesContextEngine(HermesContextAdapter, ContextEngine):
        pass
    metadata = frozenset(PERSISTENCE_ONLY_MESSAGE_FIELDS) | PERSISTENCE_FIELDS
    return HermesContextEngine(metadata_fields=metadata, **validate_options(options))


def _write_new(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def install_plugin(destination: Path, *, apply: bool = False,
                   options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Preview by default. Creates a new directory; existing installs are untouched.

    The parent directory must be trusted. Portable symlink checks mitigate normal
    mistakes, not a malicious process racing filesystem operations.
    """
    from . import __version__
    options = validate_options(options)
    destination = Path(destination).expanduser().absolute()
    if destination.name != "hermes_context":
        raise ContextError("The plugin directory must be named hermes_context.")
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ContextError("Plugin installation through a symlink is not supported.")
    if destination.exists():
        raise ContextError("Plugin destination already exists; no files were replaced.")
    contents = {
        "__init__.py": files("hermes_context").joinpath("plugin_entry.py").read_text(encoding="utf-8"),
        "plugin.yaml": (f"name: hermes_context\nversion: '{__version__}'\n"
                        "description: Offline, whole-turn context compaction\n"),
        "options.json": json.dumps(options, indent=2, allow_nan=False) + "\n",
    }
    if apply:
        created: list[Path] = []
        owned = False
        try:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.mkdir(mode=0o700, exist_ok=False)
            owned = True
            for name, content in contents.items():
                path = destination / name
                _write_new(path, content)
                created.append(path)
        except OSError:
            for path in created:
                path.unlink(missing_ok=True)
            if owned:
                try:
                    destination.rmdir()
                except OSError:
                    pass  # Never remove files created by someone else.
            raise ContextError("Plugin installation failed; check directory access.") from None
    return {"engine": "hermes_context", "installed": apply, "files": len(contents),
            "activation_required": True, "config_changed": False}


def doctor(*, check_hermes: bool = False) -> dict[str, str | bool]:
    from . import __version__
    from .compact import Compactor
    from .core import Budget
    from .cli import demo_messages
    result = Compactor(Budget(4096, 512)).compact(demo_messages())
    passed = result.stats.after <= result.stats.input_limit and result.stats.lossy
    contract = "not_checked"
    if check_hermes:
        try:
            engine = create_engine()
            contract = "compatible" if engine.name == "hermes_context" else "incompatible"
        except Exception:
            # Import errors can contain local paths or provider values; never echo them.
            contract = "unavailable_or_incompatible"
    return {"version": __version__, "self_test": "passed" if passed else "failed",
            "network_used": False, "hermes_contract": contract}
