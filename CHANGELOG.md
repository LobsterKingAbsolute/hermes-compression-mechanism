# Changelog

## 0.2.0 — 2026-10-21

- Add an opt-in Hermes context-engine adapter, explicit installer and offline doctor.
- Preserve exact retained message identity and metadata, including identical text
  and repeated tool IDs across completed exchanges.
- Isolate per-agent state, invalidate in-flight results after reset/model switch,
  suppress identical no-op retries and respect output reservations in preflight.
- Keep unknown media/reasoning fields and data-use constrained histories intact
  by passing unsupported inputs through; report outcomes without content.
- Remove repeated full-suffix counting from the default estimator path.
- Mask full quoted secret values and redact JSON tool arguments structurally.
- Reject ambiguous duplicate JSON keys and nonstandard numeric constants.
- Add tests for adapter/installer behavior and a pinned upstream ABC contract check.

Limitations: alpha, approximate default counting, lossy summaries, no complete
live-provider/agent certification. Focus guidance and nonempty provider memory
are not implemented; the latter passes through unchanged.

## 0.1.0 — 2026-10-21

- Add an independently installable, dependency-free context compaction library.
- Preserve protected whole turns and validate parallel tool-call/result chains.
- Add explicit budgets, custom counters, caller notes, and a bounded optional
  summarization callback with best-effort redaction.
- Add an offline demo and metrics-first CLI with explicit non-overwriting export.
- Add tests, a synthetic benchmark, modern package metadata and publication checks.
- Preserve the historical Hermes extraction and original MIT attribution.
