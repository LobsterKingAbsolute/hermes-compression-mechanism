"""Offline CLI. Reports are content-free; file export is explicit and redacted."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .compact import Compactor
from .core import MAX_BYTES, Budget, BudgetExceeded, ContextError, Message, Policy
from .privacy import redact_messages


def demo_messages(turns: int = 30) -> list[Message]:
    messages: list[Message] = [{"role": "system", "content": "Use synthetic data only. Do not execute tools."}]
    for i in range(turns):
        messages.extend([
            {"role": "user", "content": f"Inspect synthetic item {i}."},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"demo_{i}", "type": "function", "function": {"name": "inspect", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": f"demo_{i}", "content": "synthetic fixture row; " * 60},
            {"role": "assistant", "content": f"Synthetic item {i} inspected."},
        ])
    return messages


def _load(path: Path) -> list[Message]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ContextError("Input file exceeds the size limit.")
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ContextError):
            raise
        raise ContextError("Could not read a valid UTF-8 JSON input file.") from None
    if isinstance(value, dict):
        if (set(value) != {"schema_version", "messages"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1):
            raise ContextError("Unsupported context file schema.")
        value = value["messages"]
    if not isinstance(value, list):
        raise ContextError("Expected a message list or version-1 context file.")
    return value


def _export(path: Path, messages: list[Message]) -> None:
    # Never overwrite an existing file or follow an existing destination symlink.
    data = json.dumps({"schema_version": 1, "messages": redact_messages(messages)},
                      ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise ContextError("Output already exists; choose a new file.") from None
    except OSError:
        raise ContextError("Could not create the output file.") from None
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise ContextError("Output write failed; discard the incomplete file.") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, turn-aware context compaction. Default output: metrics only.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="Run a synthetic demonstration without a model or key.")
    compact = commands.add_parser("compact", help="Read local text-message JSON and print safe metrics.")
    compact.add_argument("input", type=Path)
    compact.add_argument("--context-window", type=int, default=4096)
    compact.add_argument("--reserved-output", type=int, default=512)
    compact.add_argument("--request-overhead", type=int, default=0)
    compact.add_argument("--safety-margin", type=int, default=128)
    compact.add_argument("--keep-first-turns", type=int, default=1)
    compact.add_argument("--keep-last-turns", type=int, default=2)
    compact.add_argument("--summary-tokens", type=int, default=384)
    compact.add_argument("--output", type=Path, help="Explicit redacted export; may still contain private text. Never overwrite.")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = Compactor(Budget(4096, 512)).compact(demo_messages())
        else:
            budget = Budget(args.context_window, args.reserved_output, args.request_overhead, args.safety_margin)
            policy = Policy(args.keep_first_turns, args.keep_last_turns, args.summary_tokens)
            result = Compactor(budget, policy=policy).compact(_load(args.input))
            if args.output is not None:
                _export(args.output, result.messages)
        print(json.dumps(result.report(), sort_keys=True))
        return 0
    except BudgetExceeded as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except ContextError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
