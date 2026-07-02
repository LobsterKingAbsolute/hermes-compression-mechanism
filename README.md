# Hermes Compression Mechanism

This repository is a public-safe extraction of the Hermes context compression
and high-context recovery mechanism. It is a source snapshot plus analysis, not
a runnable Hermes distribution.

The export intentionally contains no local runtime state, no message database,
no transcripts, no provider configuration, no auth files, no logs, and no
operator-specific secrets.

## What Is Included

- `source/agent/context_engine.py` - pluggable context-engine contract.
- `source/agent/context_compressor.py` - default lossy summarization engine.
- `source/agent/conversation_compression.py` - compression orchestration,
  session rotation, in-place compaction, persistence hooks, and lineage events.
- `source/agent/turn_context.py` - preflight context-pressure compression gate.
- `source/agent/conversation_loop.py` - provider-error recovery and post-tool
  compression triggers.
- `source/agent/agent_init.py` - configuration wiring for compression and
  context-engine selection.
- `source/hermes_state.py` - SessionDB methods used by compression locks,
  compaction archival, and session-tip projection.
- `source/hermes_cli/usage_guard.py` - compact-mode guardrails and handoff
  packet validation.
- `source/tools/tool_output_limits.py` - output caps used during compact and
  recovery modes.
- `source/agent/request_watchdog.py` - value-free recovery artifacts for
  oversized model requests.
- `source/hermes_cli/closeout_state.py` and
  `source/hermes_cli/finalization_mode.py` - bounded closeout/finalization
  prompts.
- `source/hermes_cli/partial_compress.py` and
  `source/cli_manual_compress_excerpt.py` - manual `/compress` command surface.
- `source/website/docs/developer-guide/context-compression-and-caching.md` -
  upstream developer documentation snapshot.
- `docs/combined-analysis.md` - end-to-end mechanism explanation.
- `docs/export-safety-review.md` - publication safety review.
- `docs/publication-checks.md` - checks run before initial publication.
- `docs/source-file-manifest.md` - file-by-file export manifest.

## Mechanism Summary

Hermes treats compression as a layered recovery system:

1. Configuration creates a `ContextCompressor` or a configured context-engine
   plugin.
2. Preflight checks estimate request size before a model call and may compress
   before sending the request.
3. Provider-error recovery catches context overflow, long-context-tier failures,
   and 413 payload-size errors and retries after compression.
4. Post-tool checks use real API prompt-token usage, when available, to compact
   after large tool results.
5. Manual `/compress` supports whole-history and boundary-aware compression.
6. The compressor preserves a protected head and recent tail, summarizes the
   middle, prunes old tool payloads, strips historical media, sanitizes tool
   pairs, and marks summaries as reference-only.
7. Persistence either rotates into a child session or performs in-place
   compaction by archiving old active rows and inserting compacted active rows.
8. Compression locks and lineage events keep concurrent compactions and UI
   session projection predictable.
9. Usage guard, output caps, request watchdog, and closeout/finalization helpers
   keep high-context recovery bounded and value-free.

## Not Included

Do not add local Hermes runtime artifacts to this repository:

- `.env`, `.env.*`, `auth.json`, `config.yaml`, provider credentials, API keys,
  tokens, or private URLs.
- `state.db`, `kanban.db`, SQLite WAL/SHM files, transcripts, message exports,
  session dumps, or request payload dumps.
- `logs/`, `runs/`, PID files, stdout/stderr captures, recovery artifacts,
  closure artifacts, request-watchdog artifacts, or active-session state.
- Virtual environments, caches, build artifacts, and dependency directories.

## Verification

The export was prepared from a local Hermes source checkout and should be
reviewed as a curated source snapshot. Before publishing or republishing, run:

```powershell
git status --short
rg --files
rg -n --hidden -i "sk-proj-|sk-[A-Za-z0-9_-]{20,}|ghp_|xox[baprs]-|AKIA[0-9A-Z]{16}|BEGIN .*PRIVATE KEY|password\s*[:=]|token\s*[:=]|secret\s*[:=]|api[_-]?key\s*[:=]"
python -m compileall source
```

See `docs/export-safety-review.md` for the exact publication checklist.
