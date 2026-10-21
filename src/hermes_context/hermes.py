"""Opt-in Hermes adapter. Importing this module does not import Hermes itself."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import threading
from typing import Any

from .compact import Compactor
from .core import (MAX_MESSAGES, Budget, BudgetExceeded, ContextError,
                   Message, Policy, _integer, estimate_tokens, prepare)

# Explicitly recognized durable fields, not a rule that trusts every underscore key.
# The installed plugin additionally uses the selected host's own persistence set.
PERSISTENCE_FIELDS = frozenset({
    "message_uid", "_row_id", "_absorbed_message_uids", "_tool_call_uids", "_tool_call_uid",
    "timestamp", "display_kind", "display_metadata", "_submit_row_session_id",
    "_db_row_snapshot", "_canonical_row", "_merged_turn_prefix", "_compressed_summary",
})
WIRE_FIELDS = frozenset({"role", "content", "name", "tool_calls", "tool_call_id"})


class HermesContextAdapter:
    """Mixin implementing the ContextEngine contract with isolated per-agent state.

    The installed entry point combines this class with Hermes' actual ABC. Unknown
    message content is returned unchanged. This is safe passthrough, not a promise
    that an oversized/unsupported request will fit or succeed at the provider.
    """

    def __init__(self, context_length: int = 0, *, threshold_percent: float = 0.75,
                 reserved_output: int = 1024, request_overhead: int = 0,
                 safety_margin: int = 128, keep_first_turns: int = 1,
                 keep_last_turns: int = 2, summary_tokens: int = 384,
                 metadata_fields: frozenset[str] = PERSISTENCE_FIELDS) -> None:
        _integer(context_length, "context_length")
        if (isinstance(threshold_percent, bool) or not isinstance(threshold_percent, (int, float))
                or not math.isfinite(threshold_percent) or not 0 < threshold_percent <= 1):
            raise ContextError("threshold_percent must be finite and in (0, 1].")
        for key, value in (("reserved_output", reserved_output), ("request_overhead", request_overhead),
                           ("safety_margin", safety_margin)):
            _integer(value, key)
        if (not isinstance(metadata_fields, frozenset)
                or any(not isinstance(key, str) for key in metadata_fields)
                or metadata_fields & WIRE_FIELDS):
            raise ContextError("Invalid persistence metadata field set.")
        self.policy = Policy(keep_first_turns, keep_last_turns, summary_tokens)
        self.threshold_percent = float(threshold_percent)
        self.context_length = context_length
        self.threshold_tokens = int(context_length * self.threshold_percent)
        self.reserved_output = reserved_output
        self.request_overhead = request_overhead
        self.safety_margin = safety_margin
        self.metadata_fields = metadata_fields
        # Host hints count messages, not turns. Retention itself remains whole-turn.
        self.protect_first_n = keep_first_turns
        self.protect_last_n = keep_last_turns
        self.emit_automatic_compaction_status = True
        self._lock = threading.RLock()
        self._epoch = 0
        self._inflight: object | None = None
        self._reset()

    @property
    def name(self) -> str:
        return "hermes_context"

    def _reset(self) -> None:
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0
        self._blocked_digest: str | None = None
        self._last_outcome = "idle"
        self._before = 0
        self._after = 0
        self._inflight = None
        self._epoch += 1

    def on_session_reset(self) -> None:
        with self._lock:
            self._reset()

    def on_session_start(self, session_id: str, **kwargs: Any) -> None:
        # No session identifier or host configuration is stored or logged.
        self.on_session_reset()

    def on_session_end(self, session_id: str, messages: list[Message]) -> None:
        self.on_session_reset()

    def update_model(self, model: str, context_length: int, base_url: str = "", api_key: str = "",
                     provider: str = "", api_mode: str = "") -> None:
        _integer(context_length, "context_length", 1)
        with self._lock:
            self.context_length = context_length
            # This adapter owns its threshold policy; built-in compressor model maps
            # are intentionally not applied. Credentials are neither used nor stored.
            self.threshold_tokens = int(context_length * self.threshold_percent)
            self._reset()

    def update_from_response(self, usage: dict[str, Any]) -> None:
        if not isinstance(usage, dict):
            raise ContextError("Usage must be an object.")
        # Prefer legacy aggregates: canonical buckets may exclude cached tokens.
        prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
        _integer(prompt, "prompt_tokens")
        _integer(completion, "completion_tokens")
        total = usage.get("total_tokens", prompt + completion)
        _integer(total, "total_tokens")
        with self._lock:
            self.last_prompt_tokens = prompt
            self.last_completion_tokens = completion
            self.last_total_tokens = total
            self._blocked_digest = None

    def _target_limit(self) -> int:
        try:
            hard = Budget(self.context_length, self.reserved_output, self.request_overhead, self.safety_margin)
            return min(hard.input_limit, max(1, self.threshold_tokens))
        except ContextError:
            return 0

    def should_compress(self, prompt_tokens: int | None = None) -> bool:
        with self._lock:
            tokens = self.last_prompt_tokens if prompt_tokens is None else prompt_tokens
            target = self._target_limit()
            return (type(tokens) is int and tokens > 0 and target > 0
                    and tokens >= target and self._blocked_digest is None)

    def should_compress_info(self, prompt_tokens: int | None = None) -> tuple[bool, str | None]:
        with self._lock:
            if self._blocked_digest is not None:
                return False, "unchanged_context"
            return self.should_compress(prompt_tokens), None

    def _project(self, messages: list[Message]) -> list[Message]:
        if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
            raise ContextError("Unsupported host history.")
        projected: list[Message] = []
        for message in messages:
            if not isinstance(message, dict):
                raise ContextError("Unsupported host message.")
            metadata = message.get("display_metadata")
            if message.get("data_use") or (isinstance(metadata, dict) and metadata.get("data_use")):
                # Do not erase a data-use constraint when replacing source rows by a summary.
                raise ContextError("Data-use constrained history needs a host-specific adapter.")
            projected.append({k: v for k, v in message.items() if k not in self.metadata_fields})
        prefix, turns = prepare(projected)
        return prefix + [m for turn in turns for m in turn]

    @staticmethod
    def _digest(projected: list[Message]) -> str:
        raw = json.dumps(projected, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def has_content_to_compress(self, messages: list[Message]) -> bool:
        try:
            _, turns = prepare(self._project(messages))
            return len(turns) > self.policy.keep_first_turns + self.policy.keep_last_turns
        except (ContextError, TypeError, RecursionError):
            return False

    def should_compress_preflight(self, messages: list[Message]) -> bool:
        try:
            projected = self._project(messages)
            digest = self._digest(projected)
        except (ContextError, TypeError, RecursionError):
            return False
        with self._lock:
            target = self._target_limit()
            return (digest != self._blocked_digest and target > 0
                    and estimate_tokens(projected) >= target)

    def should_defer_preflight_to_real_usage(self, rough_tokens: int) -> bool:
        return False  # Previous usage alone cannot prove that a new request fits.

    def compress(self, messages: list[Message], current_tokens: int | None = None,
                 focus_topic: str | None = None, force: bool = False,
                 memory_context: str = "") -> list[Message]:
        with self._lock:
            if memory_context:
                self._last_outcome = "unsupported_memory_context"
                return messages
            if not self.context_length:
                self._last_outcome = "unconfigured"
                return messages
            if self._inflight is not None:
                return messages
            token = object()
            self._inflight = token
            epoch = self._epoch
            try:
                hard = Budget(self.context_length, self.reserved_output, self.request_overhead, self.safety_margin)
                budget = Budget(min(hard.input_limit, max(1, self.threshold_tokens)), 0, 0, 0)
            except ContextError:
                self._last_outcome = "invalid_budget"
                self._inflight = None
                return messages
        digest = None
        outcome = "unsupported_input"
        before = after = 0
        result_messages = messages
        try:
            try:
                projected = self._project(messages)
                digest = self._digest(projected)
                with self._lock:
                    if not force and digest == self._blocked_digest:
                        if epoch == self._epoch:
                            self._last_outcome = "unchanged_context"
                        return messages
                before = estimate_tokens(projected)
                # Preserve original occurrences, including metadata, only for retained rows.
                result = Compactor(budget, policy=self.policy).compact(projected)
                after = result.stats.after
                result_messages = [copy.deepcopy(messages[index]) if index is not None
                                   else {**message, "_compressed_summary": True}
                                   for message, index in zip(result.messages, result.source_indices)]
                outcome = "compressed" if result.stats.lossy else "no_change"
            except BudgetExceeded:
                outcome = "protected_overflow"
            except (ContextError, TypeError, ValueError, RecursionError):
                outcome = "unsupported_input"
            with self._lock:
                # A reset/model switch while this pass ran invalidates its result and stats.
                if epoch != self._epoch:
                    return messages
                self._last_outcome = outcome
                self._before, self._after = before, after
                if outcome == "compressed":
                    self.compression_count += 1
                    self.last_prompt_tokens = -1  # Hermes' awaiting-real-usage sentinel.
                    self._blocked_digest = None
                else:
                    self._blocked_digest = digest
                return result_messages
        finally:
            with self._lock:
                if self._inflight is token:
                    self._inflight = None

    def get_status(self) -> dict[str, int | float | str | bool]:
        with self._lock:
            prompt = max(0, self.last_prompt_tokens)
            return {"last_prompt_tokens": prompt, "threshold_tokens": self.threshold_tokens,
                    "context_length": self.context_length, "compression_count": self.compression_count,
                    "usage_percent": min(100.0, prompt / self.context_length * 100) if self.context_length else 0.0,
                    "last_outcome": self._last_outcome, "estimated_before": self._before,
                    "estimated_after": self._after, "counter_kind": "approximate", "focus_supported": False}

    def clone_for_agent(self) -> HermesContextAdapter:
        with self._lock:
            clone = type(self).__new__(type(self))
            HermesContextAdapter.__init__(clone, context_length=self.context_length,
                threshold_percent=self.threshold_percent, reserved_output=self.reserved_output,
                request_overhead=self.request_overhead, safety_margin=self.safety_margin,
                keep_first_turns=self.policy.keep_first_turns, keep_last_turns=self.policy.keep_last_turns,
                summary_tokens=self.policy.summary_tokens, metadata_fields=self.metadata_fields)
            return clone
