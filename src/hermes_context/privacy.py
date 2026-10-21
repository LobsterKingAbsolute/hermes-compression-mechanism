"""Best-effort redaction, not a DLP guarantee or a prompt-injection defense."""
from __future__ import annotations

import copy
import re

from .core import Message

REDACTED = "[REDACTED]"
SECRET_PATTERNS = (
    re.compile(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z]+ )?PRIVATE KEY-----"),
)
ASSIGNMENT = re.compile(r'''(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\b["']?\s*[:=]\s*["']?)([^\s"',;}\]\[]+)''')
BEARER = re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/-]{8,}=*")
URL_CREDENTIAL = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@")
QUERY_SECRET = re.compile(r"(?i)([?&](?:api[_-]?key|token|access_token|signature|sig|x-amz-signature|x-goog-signature|password)=)[^&#\s]+")
EMAIL = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")


def redact_text(text: str) -> str:
    """Mask recognizable credentials and emails. Arbitrary PII may remain."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    text = ASSIGNMENT.sub(lambda m: m[1] + REDACTED, text)
    text = BEARER.sub(lambda m: m[1] + REDACTED, text)
    text = URL_CREDENTIAL.sub(lambda m: m[1] + REDACTED + "@", text)
    text = QUERY_SECRET.sub(lambda m: m[1] + REDACTED, text)
    return EMAIL.sub(REDACTED, text)


def redact_messages(messages: list[Message]) -> list[Message]:
    """Copy and redact content/arguments; structural tool IDs stay intact."""
    result = copy.deepcopy(messages)
    for message in result:
        if isinstance(message.get("content"), str):
            message["content"] = redact_text(message["content"])
        for call in message.get("tool_calls", []):
            call["function"]["arguments"] = redact_text(call["function"]["arguments"])
    return result
