# Hermes Context implementation plan

**Goal:** Ship a tested standalone library without altering the extracted runtime.
**Architecture:** Pure validated message processing and caller-supplied counters;
optional, explicit summarization callback; offline CLI and scalar reports.
**Tech stack:** Python >=3.11, standard library, setuptools with SPDX metadata.
**Spec:** `docs/design.md`.

## Constraints
No runtime dependencies, network calls, implicit environment access, paid services,
client content, or destructive Git operations. Existing `source/` is reference-only.

## Review focus
Tool chains crossing retention boundaries; insufficient protected-context budget;
Unicode and non-text fields; secrets in callbacks/errors; exclusive output creation.

## Task 1 — validated context core
- [ ] Write failing tests for budgets, strict message shapes and complete tool turns.
- [ ] Implement core models, validation and a clearly labeled approximate counter.
- [ ] Verify core tests; record results.

## Task 2 — bounded compaction
- [ ] Write failing tests for head/tail preservation, hard overflow and safe summaries.
- [ ] Implement compaction with one callback at most and immutable caller input.
- [ ] Test random synthetic histories and custom-counter failures.

## Task 3 — usable offline package
- [ ] Write failing CLI tests for safe reports and explicit, non-overwriting export.
- [ ] Add CLI, packaging, demonstration and reproducible benchmark.
- [ ] Build/install a wheel and run it outside the source tree.

## Task 4 — publish and verify
- [ ] Add licenses, provenance, security/contribution docs and CI.
- [ ] Scan new files locally; run full-repository/history checks in GitHub CI.
- [ ] Publish a verified commit without changing unrelated repositories.
- [ ] Re-read GitHub state and report actual outcomes and limitations.
