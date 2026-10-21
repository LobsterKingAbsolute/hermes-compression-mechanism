# 0.2.0 integration and hardening

Baseline: remote commit `220cd5bf42750d1a9a568929157a38bf9483dbeb`.
Reference: NousResearch/hermes-agent `4d04303818b61bf3aa09278af48356315515965b`.

## Goal
Make the standalone library usable as an opt-in Hermes context-engine plugin,
without silently dropping host metadata or provider-specific content. Improve
large-history performance and redaction correctness. No paid calls, deployments,
user configuration changes, runtime transcripts, or history rewrites.

## Slices and verification
1. Reproduce repeated-tool-ID rejection, quoted-secret leakage, and loss of origin
   identity. Fix these with tests. Optimize only the exact built-in estimator;
   preserve the arbitrary custom-counter path and final budget verification.
2. Add a per-agent, thread-safe adapter with the current ContextEngine signatures,
   usage/model reset, metadata restoration by source index, fail-open passthrough
   for unsupported histories, and no-op retry suppression. Unsupported content
   must be returned intact, never sanitized into accidental data loss.
3. Add explicit plugin installation (dry run by default, exclusive directory,
   no automatic config edits), doctor/self-test, version flag, and docs.
4. Test locally, then run the full matrix and secret/history scans in GitHub.
   Verify the actual upstream ABC contract from a pinned revision in CI. Mark
   that as a contract check, not a real-agent/live-provider certification.

## Important decisions
- Repeated call IDs across complete exchanges are valid; duplicate IDs inside
  one assistant batch remain rejected by the core. Hermes-specific unsupported
  duplicate batches pass through unchanged in the adapter.
- Only known persistence metadata is separated and restored. Unknown provider
  fields, media, and reasoning blocks are returned unchanged by the adapter.
- Output budgeting remains approximate unless the host supplies a suitable
  counter. Reduction of repetitive fixtures is not model-quality evidence.
- Full historical snapshot is not executed locally. Package/tests were recreated
  from the pinned GitHub content and verified against Git blob/tree hashes after
  direct network clone was unavailable. CI scans the complete repository.
