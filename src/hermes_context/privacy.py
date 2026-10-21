"""Best-effort redaction, not a DLP guarantee or a prompt-injection defense."""
from __future__ import annotations

import copy
import json
import re

from .core import Message

REDACTED = "[REDACTED]"
SECRET_PATTERNS = (
    re.compile(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z]+ )?PRIVATE KEY-----"),
)
SECRET_KEYS = {"apikey", "token", "accesstoken", "refreshtoken", "password",
               "secret", "clientsecret", "authorization", "cookie", "sessiontoken"}
ASSIGNMENT = re.compile(
    r"""(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|secret|token)\b["']?\s*[:=]\s*)"""
    r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s"',;}\]\[]+)"""
)
BEARER = re.compile(r"(?i)(\b(?:bearer|basic)\s+)[A-Za-z0-9._~+/-]{8,}=*")
URL_CREDENTIAL = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@")
QUERY_SECRET = re.compile(r"(?i)([?&](?:api[_-]?key|token|access_token|signature|sig|x-amz-signature|x-goog-signature|password)=)[^&#\s]+")
EMAIL = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")


def redact_text(text: str) -> str:
    """Mask recognizable credentials and emails. Arbitrary PII may remain."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    def mask_assignment(match: re.Match[str]) -> str:
        value = match[2]
        quote = value[0] if value[0] in ("\"", "'") else ""
        return match[1] + quote + REDACTED + quote
    text = ASSIGNMENT.sub(mask_assignment, text)
    text = BEARER.sub(lambda m: m[1] + REDACTED, text)
    text = URL_CREDENTIAL.sub(lambda m: m[1] + REDACTED + "@", text)
    text = QUERY_SECRET.sub(lambda m: m[1] + REDACTED, text)
    return EMAIL.sub(REDACTED, text)


def redact_arguments(text: str) -> str:
    """Mask secret-valued JSON fields while keeping valid JSON arguments valid."""
    def clean(value: object) -> object:
        if isinstance(value, dict):
            return {key: REDACTED if re.sub(r"[^a-z0-9]", "", key.lower()) in SECRET_KEYS else clean(item)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return redact_text(value) if isinstance(value, str) else value
    try:
        value = json.loads(text)
        return json.dumps(clean(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (ValueError, RecursionError):
        return redact_text(text)


def redact_messages(messages: list[Message]) -> list[Message]:
    """Copy and redact content/arguments; structural tool IDs stay intact."""
    result = copy.deepcopy(messages)
    for message in result:
        if isinstance(message.get("content"), str):
            message["content"] = redact_text(message["content"])
        for call in message.get("tool_calls", []):
            call["function"]["arguments"] = redact_arguments(call["function"]["arguments"])
    return result
