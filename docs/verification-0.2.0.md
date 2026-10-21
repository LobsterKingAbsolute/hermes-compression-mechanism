# 0.2.0 verification — 2026-10-21

Baseline: `220cd5bf42750d1a9a568929157a38bf9483dbeb`.
Upstream contract reference: `4d04303818b61bf3aa09278af48356315515965b`.

## Local evidence

The baseline package files and original tests were materialized from the pinned
GitHub content after direct clone networking was unavailable. Package blob hashes
and test-tree hash `c93ae52f170840fdf77d3e00e859a67689eb8d67` matched the source.
All 51 baseline tests passed before changes.

New regression tests failed first for repeated completed tool IDs, origin mapping,
quoted-secret leakage, structured argument masking, repeated suffix counting,
missing adapter/installer, and preflight reservation accounting. They passed after
implementation. Local suite: 87 test methods, including 150 deterministic random
histories and 60 consecutive compaction cycles. Tests include per-agent cloning,
concurrent reset, same-instance concurrency, metadata preservation, installation
rollback, no-overwrite behavior, and content-free diagnostics.

Branch-enabled local coverage on Python 3.13: 96% aggregate as rounded by coverage.
The copied plugin entry point is executed from a temporary installation in tests;
its original package-source file is not credited by the coverage mapper. Module
entry-point behavior is additionally checked using a separately installed wheel.

## Performance probe

One same-environment measurement, synthetic text turns, output budget 1000 units:

| Turns | 0.1.0 seconds | 0.2.0 seconds |
| --- | ---: | ---: |
| 100 | 0.023679 | 0.006043 |
| 400 | 0.303760 | 0.023441 |
| 800 | 1.188474 | 0.045820 |

The 800-turn sample is about 26 times faster; this is a one-run local microbenchmark,
not a production speed guarantee. The regression test instead checks bounded
counter invocations, avoiding a hardware-dependent timing assertion. Matching
counter inputs produce the same compacted messages through optimized and custom
counter paths. No claim of semantic recall or live API cost reduction is made.

## Remote checks

The workflow runs Linux Python 3.11-3.14, Windows Python 3.13, wheel verification,
a pinned upstream ABC contract check, and Gitleaks on the full reachable history
and checkout. The POSIX-only symlink tests are skipped on Windows. Actual run
results must be inspected before release; this document's local evidence alone
is not a claim that remote jobs have finished.

## Limits

The upstream check extracts the real pinned `ContextEngine` class and binds the
adapter to it. It does not run the full Hermes runtime or a provider. Your local
Hermes installation was not modified or exercised. No paid API calls, production
deployments, PyPI publication, or changes to the separate `hermes-agent` fork.

The original `source/` tree remains unchanged. Local scans cover the materialized
library/tests/docs; GitHub CI scans the complete repository and reachable history.
A clean scan is not proof that all possible private information is absent. Git
commit author/committer metadata still uses the connected account's identity;
no history rewrite or account privacy change was performed.
