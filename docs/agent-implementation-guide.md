# Agent Implementation Guide

This guide is for coding agents that want to implement a Hermes-style context
compression and recovery mechanism in another agent runtime.

It is intentionally public-safe. Do not add local runtime databases, transcripts,
logs, provider configuration, private URLs, credentials, or operator-specific
paths while following it.

## Implementation Goal

Build a bounded context-pressure system that can:

- detect when a conversation is too large for the next model request;
- preserve the newest task context and critical early instructions;
- summarize older middle history without turning stale tasks into new tasks;
- persist the compressed continuation safely;
- prevent repeated ineffective compaction loops;
- recover from high-context failures with bounded, value-free handoff packets.

## Non-Goals

- Do not implement a full transcript export feature.
- Do not publish or move local message databases.
- Do not treat summaries as authoritative user instructions.
- Do not rely on compression to fix output-token-cap errors.
- Do not make provider credentials or runtime config part of the compression
  artifact.

## Phase 1: Define The Context Engine Contract

Start with a small engine interface similar to `source/agent/context_engine.py`.
The runtime should not hard-code one compressor everywhere.

Minimum contract:

- `should_compress(token_count, message_count, state) -> bool`
- `compress(messages, state, force=False, focus=None) -> CompressionResult`
- `get_token_state() -> TokenState`
- `on_session_start(session_id)`
- `on_session_end(session_id, reason)`
- `on_compression_boundary(old_session_id, new_session_id, reason)`

Recommended result fields:

- compressed messages;
- rough token estimate before/after;
- whether compression was a no-op;
- whether summarization was aborted;
- metadata for logging that contains only scalar, value-free fields.

## Phase 2: Add Trigger Points

Implement compression triggers in more than one place:

1. Preflight request estimation before sending a model call.
2. Provider-error recovery for context overflow and payload-too-large errors.
3. Post-tool compression based on real provider prompt-token usage when
   available.
4. Manual user command, such as `/compress` or `/compress here`.
5. Optional UI/gateway hygiene checks for extremely long sessions.

Keep output-cap errors separate. If the provider says the requested output limit
is too high, reduce output tokens or report that issue; compression will not
solve it.

## Phase 3: Preserve The Right Context

The compressor should split history into:

- protected head: system prompt and a small number of early non-system messages;
- compressible middle: older conversation state to summarize;
- protected tail: recent user/assistant/tool turns needed for the current task.

The tail should include:

- the latest real user instruction;
- the latest visible assistant reply;
- complete tool-call/tool-result groups;
- enough recent context to avoid losing the active workflow.

Do not split provider-required tool message pairs. After compression, run a
message-shape sanitizer that fixes or removes orphaned tool calls/results.

## Phase 4: Summarize The Middle

Build a structured summarizer prompt that asks for operational state, not a
verbatim transcript.

Useful sections:

- historical task snapshot;
- current or last known goal;
- durable constraints and user preferences;
- completed actions;
- active state;
- blocked state;
- key decisions;
- relevant files or symbols;
- remaining work, clearly labeled as historical;
- critical caveats.

Before sending material to the summarizer:

- redact obvious credentials, tokens, private keys, signed URLs, and connection
  strings;
- strip or replace historical media payloads;
- truncate old tool outputs and tool-call arguments;
- avoid including raw provider payloads.

After receiving the summary:

- run redaction again;
- insert a defensive prefix that says the summary is reference-only;
- state that the latest user message after the summary wins;
- state that historical pending work must not be acted on unless the latest user
  message asks for it;
- keep local-only metadata under keys that will be stripped before provider
  requests.

Important: model-based summarization can send private conversation content to
the configured compression provider. Agents must document this provider data
flow and respect the host application's privacy policy.

## Phase 5: Persist The Continuation

Choose one or both persistence modes.

Split-session continuation:

- end the parent session with reason `compression`;
- create a child session with `parent_session_id`;
- copy or migrate active goal/task state;
- reset flush cursors so the compressed child history persists from index zero;
- make UI/resume surfaces follow the child tip.

In-place compaction:

- keep the same session id;
- mark old active message rows as archived/compacted;
- insert compacted messages as the new active rows;
- keep archived compacted rows searchable only if the product explicitly wants
  that local recovery behavior;
- never export those databases publicly.

## Phase 6: Add Concurrency Protection

Use a database-backed or otherwise atomic lock keyed by session id.

The lock should include:

- holder id;
- expiry timestamp;
- refresh during long summarization;
- release in `finally` paths.

If the lock is held by another actor, skip compression and return the original
messages. Do not race two compactions over the same session.

## Phase 7: Prevent Loops And Thrashing

Track:

- last compression token estimate;
- last real provider usage after compression;
- repeated no-op or low-savings compression attempts;
- cooldown state after ineffective compression;
- maximum compression attempts per provider error.

If compression does not materially reduce context, stop retrying and ask for a
fresh conversation, manual trim, or narrower task.

## Phase 8: Add Bounded Recovery Tools

Implement compact-mode guardrails for high-context turns:

- cap search/read/terminal output after a context warning;
- block broad repeated repository exploration once compact mode is active;
- preserve only head/tail slices of large terminal output;
- redact terminal output;
- validate handoff packets with required fields.

A useful handoff packet includes:

- task id;
- phase;
- touched files;
- recent diff summary;
- failing tests;
- missing symbols;
- blocked commands;
- declared artifacts;
- next small step;
- actions not to repeat.

For stalled high-context requests, write value-free recovery state only:
fingerprints, counters, timestamps, model/provider labels, and the next bounded
recovery instruction. Do not write raw prompts, transcripts, provider payloads,
or logs into recovery artifacts.

## Phase 9: Wire Manual Compression

A manual command should support:

- full-history compression;
- boundary-aware compression such as `/compress here`;
- optional focus topic;
- preview mode if the product needs it.

Boundary-aware compression should keep a recent tail beginning at a user turn
where possible. Rejoin head and tail only after validating role alternation and
tool-call shape.

## Phase 10: Test Before Shipping

Minimum tests:

- compressor preserves latest user instruction;
- compressor preserves latest assistant reply;
- compressor does not split tool-call/tool-result pairs;
- stale summarized tasks are marked historical/reference-only;
- sensitive strings are redacted before and after summarization;
- historical media payloads are stripped;
- compression aborts safely on auth/network summarizer failures;
- in-place compaction archives old rows and inserts compacted active rows;
- split-session compression creates a child and projects resume to the child;
- locks prevent concurrent compaction races;
- repeated ineffective compression does not loop forever;
- provider 413/context-overflow recovery retries within a bounded attempt limit;
- output-cap errors do not route into compression;
- usage guard caps broad read/search/terminal output;
- recovery packets reject obvious secret values.

Recommended verification commands depend on the host project, but include:

```powershell
python -m compileall source
python -m pytest -q <focused compression tests>
rg -n --hidden -g '!.git/**' -i "sk-proj-|sk-[A-Za-z0-9_-]{20,}|ghp_|github_pat_|xox[baprs]-|AKIA[0-9A-Z]{16}|BEGIN .*PRIVATE KEY"
rg --files --hidden -g '!.git/**' -g '.env*' -g '*.db' -g '*.sqlite*' -g '*.log' -g 'auth.json' -g 'config.yaml'
```

## Public Sharing Checklist

Before publishing an implementation sample:

- include source and docs only;
- remove local state, databases, transcripts, logs, configs, auth files, caches,
  virtual environments, request dumps, screenshots, media, and run artifacts;
- scan for secrets and manually review every hit;
- document the compression-provider data flow;
- document which tests passed and which checks were unavailable;
- keep example values synthetic and clearly fake.

## Agent Operating Rule

When implementing this mechanism, write the required artifact or tests early and
update them incrementally. Do not leave the first report, migration, or safety
artifact until the final tool call; high-context work is exactly where late
artifact creation fails.

