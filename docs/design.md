# Standalone context compaction: design

## Goal
Turn the extracted Hermes reference material into a useful, installable,
provider-independent Python library. Preserve the original `source/` snapshot,
its license, and its provenance; do not pretend to be the Nous Research project.

## Boundaries
The first release is text-only, synchronous, and stateless. It makes no network
calls, reads no environment variables, and does not execute tools. Support the
common role/content/tool_calls/tool_call_id message subset; reject unsupported
fields and multimodal payloads rather than silently stripping them. Do not claim
to implement the Responses API, a live Hermes plugin, or a lossless memory system.

## Invariants
- Preserve leading system/developer messages and configured first/recent whole
  user turns verbatim. Keep the latest user request and whole tool exchanges.
- Validate tool call IDs, complete results, roles, field types, and input size.
- Reserve room for output, tool/schema overhead and a safety margin.
- If protected content cannot fit, raise a content-free error; never silently
  truncate it. Budget guarantees are relative to the supplied token counter.
- Default counter is a documented approximation, not an exact provider tokenizer.
- Remove oldest eligible turns, optionally insert an explicitly untrusted user-role
  summary. Summaries never receive system/developer authority.
- Default summarizer is local and extractive. A custom callback is explicit opt-in,
  called at most once, with recognizable secrets redacted before and after it.
- Explicit caller notes preserve decisions/constraints exactly; do not infer
  semantic retention or benchmark model quality from token-count savings.
- Default CLI output is scalar metrics only. Transcript export is explicit,
  best-effort redacted, exclusive-create and owner-readable on POSIX.

## Layout
`src/hermes_context`: core models/validation, compaction, privacy, CLI.
`tests`: dependency-free unit, boundary, integration and randomized tests.
`benchmarks`: synthetic, reproducible, offline comparisons; no client data.
`tools`: publication checks. CI additionally scans full reachable Git history.

## Publication
MIT, original notices retained, new code under contributor copyright. No deploy,
PyPI upload, paid model calls, production changes, or rewriting Git history.
The existing author email in old commits is not silently removed. Report exactly
which security checks ran, and do not equate a clean automated scan with a proof
that no sensitive data can exist.
