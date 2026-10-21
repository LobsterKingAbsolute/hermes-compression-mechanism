# 0.2.0 verification — 2026-10-21

Baseline: `220cd5bf42750d1a9a568929157a38bf9483dbeb`.
Implementation commit: `fa43fc179204263818b61cee7f0e70545bfcb178`.
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
The wheel installed into an isolated environment with no runtime dependencies;
`doctor`, `demo`, and explicit plugin installation succeeded from outside the source
tree. The generated plugin contained exactly three files and no host config edits.
Uploaded code, tests, tools, workflow and changed document hashes were compared
against the tested local files. The reference snapshot subtree hash is unchanged.

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

[GitHub Actions run 39657592109](https://github.com/LobsterKingAbsolute/hermes-compression-mechanism/actions/runs/39657592109)
completed successfully for the implementation commit above. All seven jobs passed:
Linux Python 3.11, 3.12, 3.13 and 3.14; Windows Python 3.13; the pinned upstream
ABC contract; and Gitleaks. The test jobs also run doctor, the synthetic benchmark,
tracked-file publication checks, and wheel/license inspection. The two POSIX-only
symlink tests are intentionally skipped on Windows.

The actual pinned upstream ABC check returned `passed: true` after verifying its
Git blob hash. It exercised required compression behavior, inherited optional
no-op hooks, and clone/model isolation. This is not a full-runtime test.

Gitleaks 8.30.1 scanned all five reachable commits at that revision (about 1.45 MB)
and reported no detected leaks. A separate working-tree scan of about 1.43 MB
also reported no detected leaks. Potential secret values are redacted in logs.

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
