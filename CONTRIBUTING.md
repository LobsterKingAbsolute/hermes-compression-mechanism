# Contributing

Use Python 3.11+ and synthetic data. Work in a branch, write a regression test
before changing behavior, then run:

```bash
python -m pip install .
python -m unittest discover -s tests -v
python benchmarks/benchmark.py
python tools/publication_scan.py
```

Keep runtime dependencies at zero unless a concrete benefit justifies a reviewed
optional integration. Preserve tool-chain integrity, current user turns, explicit
budgets, content-free errors and the MIT notices. Never commit local runtime state.
Changes under `source/` need a clear explanation: it is a reference snapshot, not
the live library. Do not present upstream code as a new original implementation.

A useful pull request states the failing case, expected behavior, compatibility
impact, tests run, and limitations. Do not add unsupported performance claims,
star counts, fake testimonials, or a CI badge that does not reflect a real run.
