# Source File Manifest

The export is intentionally narrow. Large files are included only when the
compression mechanism depends on embedded methods or runtime wiring inside them.

| File | Why it belongs |
| --- | --- |
| `source/run_agent.py` | Runtime agent wrapper and source context for compression wiring. |
| `source/agent/context_engine.py` | Defines the context-engine interface and lifecycle hooks. |
| `source/agent/context_compressor.py` | Implements the default summarizing compressor. |
| `source/agent/conversation_compression.py` | Orchestrates compression, locks, persistence, session rotation, and lineage events. |
| `source/agent/turn_context.py` | Runs preflight request-size estimation and compression passes. |
| `source/agent/conversation_loop.py` | Handles runtime overflow/413 recovery and post-tool compression triggers. |
| `source/agent/agent_init.py` | Reads compression config and selects the context engine. |
| `source/agent/request_watchdog.py` | Provides value-free high-context request recovery artifacts. |
| `source/agent/manual_compression_feedback.py` | Builds bounded user feedback for manual compression. |
| `source/hermes_state.py` | Contains SessionDB compression locks, in-place compaction, search behavior, and session-tip projection. |
| `source/hermes_cli/usage_guard.py` | Enforces compact-mode read/search/output guardrails and validates handoff packets. |
| `source/hermes_cli/partial_compress.py` | Splits and rejoins histories for `/compress here` and keep-tail flows. |
| `source/hermes_cli/closeout_state.py` | Builds bounded closeout/resume state for recovery. |
| `source/hermes_cli/finalization_mode.py` | Builds bounded finalization prompts after high-context pressure. |
| `source/tools/tool_output_limits.py` | Defines output caps used by compact and recovery modes. |
| `source/cli_manual_compress_excerpt.py` | Labeled source excerpt for the manual `/compress` CLI command. |
| `source/website/docs/developer-guide/context-compression-and-caching.md` | Upstream docs snapshot; source files remain authoritative for current behavior. |
| `source/LICENSE` | Upstream license copied with the source snapshot. |
| `docs/agent-implementation-guide.md` | Public-safe implementation instructions for agents porting the mechanism. |

## Excluded On Purpose

- Full `cli.py`: only the `/compress` command surface is included as an excerpt.
- Tests: the public mechanism is source plus analysis; test commands are listed
  in documentation, but local test fixtures are not required for understanding
  the extraction.
- Runtime state: all databases, logs, configs, run artifacts, and transcripts
  are excluded.
