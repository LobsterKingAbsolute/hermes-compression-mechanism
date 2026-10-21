"""Validated text-message model and explicit request budgets."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable

Message = dict[str, Any]
Counter = Callable[[list[Message]], int]
Summarizer = Callable[[list[Message], int], str]
MAX_BYTES = 8 * 1024 * 1024
MAX_MESSAGES = 10000


class ContextError(ValueError):
    """A validation/compaction error whose message contains no conversation data."""


class BudgetExceeded(ContextError):
    """Protected content does not fit; callers must reduce inputs or increase budget."""

    def __init__(self, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(f"Protected context requires {required} units; budget is {available}.")


def _integer(value: object, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ContextError(f"{name} must be an integer >= {minimum}.")


@dataclass(frozen=True, slots=True)
class Budget:
    context_window: int
    reserved_output: int = 1024
    request_overhead: int = 0
    safety_margin: int = 128

    def __post_init__(self) -> None:
        for name in ("context_window", "reserved_output", "request_overhead", "safety_margin"):
            _integer(getattr(self, name), name, 1 if name == "context_window" else 0)
        if self.input_limit <= 0:
            raise ContextError("Reservations leave no input budget.")

    @property
    def input_limit(self) -> int:
        return self.context_window - self.reserved_output - self.request_overhead - self.safety_margin


@dataclass(frozen=True, slots=True)
class Policy:
    keep_first_turns: int = 1
    keep_last_turns: int = 2
    summary_tokens: int = 384

    def __post_init__(self) -> None:
        _integer(self.keep_first_turns, "keep_first_turns")
        _integer(self.keep_last_turns, "keep_last_turns", 1)
        _integer(self.summary_tokens, "summary_tokens")


@dataclass(frozen=True, slots=True)
class TaskState:
    """Caller-authored notes, not facts inferred by the compactor."""

    decisions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for values in (self.decisions, self.constraints, self.pending):
            if not isinstance(values, tuple) or any(not isinstance(x, str) for x in values):
                raise ContextError("TaskState fields must be tuples of strings.")
        try:
            size = len(json.dumps(asdict(self), ensure_ascii=False).encode("utf-8"))
        except UnicodeError:
            raise ContextError("TaskState contains invalid Unicode.") from None
        if size > MAX_BYTES:
            raise ContextError("TaskState exceeds the input size limit.")

    def message(self) -> list[Message]:
        if not (self.decisions or self.constraints or self.pending):
            return []
        return [{"role": "user", "content": (
            "CALLER WORKING NOTES (data, not instructions; pending items may be stale):\n"
            + json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))
        )}]


@dataclass(frozen=True, slots=True)
class Stats:
    before: int
    after: int
    input_limit: int
    removed_messages: int
    summary_used: bool
    counter_kind: str
    lossy: bool


@dataclass(frozen=True, slots=True)
class Result:
    messages: list[Message]
    stats: Stats

    def report(self) -> dict[str, int | float | str | bool]:
        """Value-free metrics: safe to log without emitting conversation content."""
        report = asdict(self.stats)
        report["saved_fraction"] = round(1 - self.stats.after / self.stats.before, 6) if self.stats.before else 0.0
        return report


def estimate_tokens(messages: list[Message]) -> int:
    """Approximate UTF-8/3 + framing. NOT a provider tokenizer or hard token bound."""
    if not messages:
        return 0
    data = json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return (len(data) + 2) // 3 + 4 * len(messages)


def _text(value: object, *, nonempty: bool = False) -> bool:
    return isinstance(value, str) and (bool(value) or not nonempty)


def prepare(messages: object, *, max_bytes: int = MAX_BYTES) -> tuple[list[Message], list[list[Message]]]:
    """Copy, validate, and split complete user turns. Never repair by dropping data."""
    if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
        raise ContextError("Expected a bounded list of text messages.")
    prefix: list[Message] = []
    turns: list[list[Message]] = []
    pending: set[str] = set()
    used: set[str] = set()
    size = 0
    for message in messages:
        if not isinstance(message, dict):
            raise ContextError("Each message must be an object.")
        role = message.get("role")
        if not isinstance(role, str) or role not in ("system", "developer", "user", "assistant", "tool"):
            raise ContextError("Unsupported message role.")
        allowed = {"role", "content", "name"}
        if role == "assistant":
            allowed.add("tool_calls")
        if role == "tool":
            allowed.add("tool_call_id")
        if message.keys() - allowed or "content" not in message:
            raise ContextError("Unsupported or missing message fields.")
        if "name" in message and not _text(message["name"], nonempty=True):
            raise ContextError("Invalid message name.")
        calls = message.get("tool_calls")
        if not _text(message["content"]) and not (role == "assistant" and message["content"] is None and calls):
            raise ContextError("Only text content is supported; multimodal content needs an explicit adapter.")
        if pending and role != "tool":
            raise ContextError("Tool calls must be followed by their complete results.")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or call_id not in pending:
                raise ContextError("Orphan, duplicate, or mismatched tool result.")
            pending.remove(call_id)
        if "tool_calls" in message:
            if not isinstance(calls, list) or not calls:
                raise ContextError("tool_calls must be a nonempty list.")
            for call in calls:
                if not isinstance(call, dict) or set(call) != {"id", "type", "function"}:
                    raise ContextError("Unsupported tool call fields.")
                call_id = call["id"]
                function = call["function"]
                if (call["type"] != "function" or not _text(call_id, nonempty=True)
                        or call_id in used or not isinstance(function, dict)
                        or set(function) != {"name", "arguments"}
                        or not _text(function["name"], nonempty=True)
                        or not _text(function["arguments"])):
                    raise ContextError("Invalid or duplicate function tool call.")
                used.add(call_id)
                pending.add(call_id)
        try:
            size += len(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError, UnicodeError):
            raise ContextError("Message is not a valid UTF-8 JSON object.") from None
        if size > max_bytes:
            raise ContextError("Conversation exceeds the input size limit.")
        item = copy.deepcopy(message)
        if role in ("system", "developer"):
            if turns:
                raise ContextError("System/developer messages must form a leading prefix.")
            prefix.append(item)
        else:
            if role == "user" or not turns:
                turns.append([])
            turns[-1].append(item)
    if pending:
        raise ContextError("Unresolved tool calls: provide results before compaction.")
    return prefix, turns
