# Combined Analysis

This document explains the Hermes compression mechanism as a public-safe source
review. It intentionally avoids local transcripts, runtime databases, provider
configuration values, secrets, and private session content.

## Architecture

Hermes separates compression into an engine, orchestration layer, trigger
points, persistence model, and bounded recovery tools.

The engine contract lives in `source/agent/context_engine.py`. A context engine
can decide when to compress, perform compression, receive session lifecycle
events, expose optional tools, and report token state. The default engine is
`ContextCompressor` in `source/agent/context_compressor.py`; plugin engines are
selected only through explicit configuration.

`source/agent/agent_init.py` wires configuration into the runtime:

- `compression.enabled`
- `compression.threshold`
- `compression.target_ratio`
- `compression.protect_last_n`
- `compression.protect_first_n`
- `compression.abort_on_summary_failure`
- `compression.in_place`
- optional auxiliary compression context length
- optional configured context engine

## Trigger Points

Compression can be triggered in several places:

- Preflight turn setup in `source/agent/turn_context.py` estimates full request
  size before a model call. If the estimate crosses the compressor threshold,
  Hermes activates usage guard and tries up to three compression passes.
- Runtime provider-error handling in `source/agent/conversation_loop.py` catches
  context overflow, long-context-tier failures, and 413 payload-too-large
  errors. It retries after compression, while avoiding compression for pure
  output-cap errors.
- Post-tool checks in `source/agent/conversation_loop.py` use real prompt-token
  usage when the provider returns it. If real usage is unavailable, Hermes falls
  back to a rough estimate.
- Manual `/compress` uses the CLI flow excerpted in
  `source/cli_manual_compress_excerpt.py` plus the split/rejoin helpers in
  `source/hermes_cli/partial_compress.py`.
- Gateway and UI surfaces can request compression and follow projected session
  tips, but runtime state is intentionally not included in this export.

## Compression Algorithm

The default compressor is lossy and deliberately conservative around the newest
instructions.

It preserves a protected head, preserves a recent tail, and summarizes the
middle. The tail is anchored around recent user/assistant turns so that the
current task stays intact. Old tool results are pruned, historical media is
stripped, and role/tool-call pairs are normalized so provider message ordering
remains valid.

The generated summary is marked as reference-only. The prompt tells future
turns that the latest user message wins and that historical tasks in the summary
are stale unless the user explicitly revives them. Summary metadata is stored
under an underscore-prefixed key so provider transport sanitizers remove it
before sending model requests.

The summarizer prompt also instructs the model not to include credentials or
private tokens. The resulting summary is passed through sensitive-text
redaction. If the summary call fails due to auth or network conditions, Hermes
aborts compression and keeps the original messages unchanged. Bounded fallback
summaries exist for non-auth failures, and they are marked as possibly
incomplete.

Operationally, real private conversation content can still be sent to the
configured compression LLM provider during normal compression. The source
contains redaction and media handling, but provider data flow remains an
important deployment policy decision.

## Persistence

`source/agent/conversation_compression.py` owns the session-level operation.
Before compressing, it can call memory pre-compress hooks, rebuild the system
prompt, include todo snapshots, and emit value-free compression lineage events.

Hermes supports two persistence modes:

- Split-session continuation: the parent session is ended with reason
  `compression`, a child session is created with `parent_session_id`, runtime
  session identifiers are updated, `/goal` state is migrated, and the flush
  cursor is reset so the compressed child history is persisted cleanly.
- In-place compaction: `SessionDB.archive_and_compact` marks existing active
  rows as `active=0, compacted=1`, inserts compacted messages as fresh active
  rows, and updates live message counts while keeping compacted-away rows
  searchable.

`source/hermes_state.py` also projects compression roots to live tips so resume
and session lists can point at the current child rather than an ended parent.

## Race Handling

Compression uses database-backed locks keyed by session id. The lock table has a
holder and expiry; acquisition deletes expired locks and inserts a new holder
atomically. The compressor refreshes and releases the lock around the operation.
If another holder owns the lock, Hermes leaves messages unchanged and warns
rather than racing a second compaction.

## Bounded Recovery

Compression is paired with high-context recovery helpers:

- `source/hermes_cli/usage_guard.py` activates compact mode after context
  pressure, caps broad reads/searches/terminal output, denies unsafe broad
  repeated exploration, and validates compact handoff packets with required
  fields.
- `source/tools/tool_output_limits.py` provides mode-specific output caps for
  terminal, search, monitor, compact, and synthesizer modes.
- `source/agent/request_watchdog.py` writes value-free recovery state for long
  high-context model requests. It stores fingerprints and counters, not raw
  prompts or provider payloads.
- `source/hermes_cli/closeout_state.py` and
  `source/hermes_cli/finalization_mode.py` build bounded resume/finalization
  prompts with allowlisted fields.

## Known Limits

- Compression is lossy; it preserves operational continuity, not perfect
  transcript fidelity.
- Summary quality depends on the auxiliary or main model used for compression.
- If the agent keeps reading broadly after compression, context can grow again.
  Usage guard mitigates this but does not replace task discipline.
- Split-session continuation requires UI, resume, and logging surfaces to follow
  the child session tip.
- In-place compaction keeps archived rows searchable; that is useful locally but
  also means databases must never be exported.
- Existing upstream docs may lag behind source behavior. The included source
  files are the authority for this snapshot.

## Independent Review Cross-Check

An independent Hermes review of the same mechanism agreed with the architecture
above and added several publication-relevant checks:

- Treat compression as an LLM provider data-flow surface, because the summary
  model can receive private conversation and tool context.
- Export a curated subset only; do not publish a local Hermes home directory or
  a blind repository dump.
- Keep databases out of scope because compaction preserves archived rows for
  local search/recovery.
- Include manual compression, gateway/session projection, usage guard, output
  limits, watchdog, and closeout/finalization helpers as part of the mechanism,
  not as unrelated utilities.
- Validate with focused compressor, persistence, gateway, manual CLI,
  usage-guard, watchdog, finalization, and output-limit tests in the upstream
  Hermes checkout when available.

## Verdict

The mechanism can be safely shared as source plus documentation when the export
boundary is kept strict and a manual secret/runtime-artifact scan passes. The
safe public unit is the curated source snapshot in this repository, not a copy
of a local Hermes home directory or runtime state.
