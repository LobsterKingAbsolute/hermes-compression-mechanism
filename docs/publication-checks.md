# Publication Checks

Checks run before the initial public publication of this curated snapshot:

## Export Inventory

- `rg --files` showed only curated source, docs, `.gitignore`, `README.md`,
  `SECURITY.md`, and `LICENSE`.
- Runtime-artifact glob scan for env files, SQLite databases, logs, PID files,
  auth/config files, run directories, session directories, runtime directories,
  closure artifacts, and request-watchdog artifacts returned no export files.

## Secret Pattern Review

Regex scans for common key/token/private-key patterns produced only expected
source/documentation hits:

- scanner commands documented in `README.md` and `docs/export-safety-review.md`;
- redaction regexes in `source/hermes_cli/usage_guard.py`;
- source field names and assignments such as `api_key`, `token`, and
  `_anthropic_api_key`.

No real credential values, private keys, tokens, `.env` files, auth files,
provider configs, runtime databases, logs, transcripts, or request dumps were
found in the export.

External scanners `gitleaks` and `trufflehog` were not installed in the local
environment used for this publication check.

## Parse Check

`python -m compileall -q source` passed after the CLI excerpt was wrapped as a
parseable review artifact.

Generated `__pycache__` directories were removed before staging.

## Upstream Focused Tests

In the upstream Hermes checkout, this focused green subset passed:

```powershell
python -m pytest -q tests\agent\test_context_compressor.py tests\agent\test_context_compressor_summary_continuity.py tests\agent\test_context_compressor_cross_session_guard.py tests\agent\test_context_compressor_session_end_clears_state.py tests\run_agent\test_413_compression.py tests\hermes_cli\test_usage_guard.py tests\tools\test_tool_output_limits.py
```

Result: `221 passed`.

A broader targeted set also ran and produced `226 passed, 11 failed`. The
failures were all Windows cleanup failures where temporary SQLite files remained
locked during `TemporaryDirectory` cleanup (`WinError 32`) in DB-heavy
in-place/persistence tests. Those failures are residual upstream verification
risk, not evidence of secrets in this export.

