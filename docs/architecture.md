# Architecture and integration contract

1. `core.prepare` validates bounded text messages, copies them and constructs whole
   user turns. Function-call batches must have exactly one result per ID before
   any next user/assistant message. IDs cannot be reused in one input history.
2. `Budget` subtracts output, request overhead and safety reservations. No model
   names or changing provider limits are hard-coded.
3. `Compactor` preserves control prefix, first N turns and last M turns. Overlap is
   counted once. Caller notes are inserted before the recent user request.
4. If the original request fits, return a copy without calling any summarizer.
5. If the protected skeleton alone is too large, raise `BudgetExceeded` with
   scalar counts only. The original input is untouched.
6. Remove oldest eligible turns until there is enough room for a summary or no
   middle remains. Summary reservation can discard more history than a shorter
   eventual summary strictly needs; the algorithm favors predictable behavior.
7. Redact recognizable credentials, call the explicitly selected summarizer at
   most once, redact its output, and bound the wrapped summary. Summary text is
   inserted as user-role untrusted historical data, never privileged instructions.
8. Validate the output and check the final budget again. Return messages plus
   value-free statistics. There is no internal provider retry, concurrency lock,
   global session state, database, recovery daemon, or implicit persistence.

## Counter contract
`counter(messages) -> int`: deterministic, nonnegative, side-effect-free; account
for every relevant message field. Inputs are copied before callbacks. The default
counter is approximate UTF-8 byte length / 3 plus framing. It is not an exact
vendor tokenizer and not a universal upper bound. Custom counters are responsible
for their model and framing; external request fields belong in `request_overhead`.
A stateful or inaccurate counter invalidates token-budget assumptions.

## Summary contract
`summarizer(redacted_messages, max_tokens) -> str`, synchronous. It is optional and
never called for an already fitting context or when no summary fits. Failure and
invalid output raise content-free `ContextError`. No hidden fallback API calls.
The token limit is enforced on the returned wrapped summary. Prompt labeling is
not a complete defense against malicious instructions in conversation history.

## State and privacy
`TaskState` contains explicit tuples of decisions, constraints and pending items.
These notes are not inferred and are preserved exactly in the in-memory result.
Input and returned messages can still contain credentials in protected turns:
compaction is not a DLP pipeline. Only summary inputs/outputs are automatically
redacted. Explicit CLI export masks known patterns in content/arguments but may
retain private data and structural IDs; treat all exports as private.

The version-1 export format is `{"schema_version": 1, "messages": [...]}`.
It is plain JSON, not a signed, encrypted, transactional or multi-writer checkpoint.
Do not use the CLI export for concurrent production session persistence.

## Known limits and next evidence to collect
- Real provider adapters and tokenizer parity are not shipped or tested here.
- No semantic-recall benchmark or live-model evaluation has been performed.
- Multimodal and reasoning blocks need explicit future adapters.
- Evaluate long repeated session compactions against task-completion quality before
  integrating into a production agent. Do not merely optimize token-count savings.
