# Export Safety Review

This review describes the publication gate for the Hermes compression mechanism
export.

## Safe To Export

- Curated source files under `source/`.
- Source excerpts that are clearly labeled as excerpts.
- Public-safe architecture notes and analysis under `docs/`.
- The upstream license file.

## Do Not Export

- `.env`, `.env.*`, `auth.json`, `config.yaml`, local provider settings, API
  keys, tokens, cookies, private URLs, webhook secrets, or signed URLs.
- `state.db`, `kanban.db`, SQLite WAL/SHM files, DB dumps, transcripts, message
  rows, session payloads, request dumps, or provider responses.
- Logs, PID files, stdout/stderr captures, recovery artifacts, request-watchdog
  artifacts, closure artifacts, active-session state, local dashboards, caches,
  virtual environments, or dependency directories.
- Monitoring prompts or run artifacts from the export process.

## Leakage Paths Reviewed

- Source comments and docs may contain words such as token, secret, password,
  and API key because the mechanism contains redaction logic. These matches
  require manual review but are not automatically leaks.
- Runtime databases remain private because compaction archives old rows rather
  than deleting them. This is correct for Hermes recovery, but it makes SQLite
  files categorically unsafe for publication.
- Request-watchdog and closeout helpers are designed to be value-free, but their
  generated runtime artifacts still belong outside the repository.
- The manual `/compress` excerpt is source-only and does not contain transcript
  content.
- Normal runtime compression can send private conversation content to the
  configured compression LLM provider. This export contains only source code,
  but operators should treat compression as a provider data-flow feature when
  deploying Hermes.

## Required Checks Before Publication

Run from the export repository root:

```powershell
git status --short
rg --files
rg -n --hidden -i "sk-proj-|sk-[A-Za-z0-9_-]{20,}|ghp_|github_pat_|xox[baprs]-|AKIA[0-9A-Z]{16}|BEGIN .*PRIVATE KEY"
rg -n --hidden -i "password\s*[:=]|token\s*[:=]|secret\s*[:=]|api[_-]?key\s*[:=]|webhook.*secret|signed[_-]?url"
python -m compileall source
```

Optional external scanners, when installed:

```powershell
gitleaks detect --source . --no-git --redact --verbose
trufflehog filesystem . --no-update --fail
```

Every scanner hit must be classified as one of:

- actual leak: remove before publication;
- test fixture or redaction pattern: safe only if no real value is present;
- source field name: safe if it contains no value;
- documentation warning: safe if it contains no private value.

## Final Publication Criteria

- The file list contains only curated source and docs.
- No runtime directories are present.
- No local DBs, logs, configs, auth files, or run artifacts are present.
- Secret scan hits are manually reviewed and contain no real credentials.
- Python source parses with `compileall`.
- Git remote points to the intended public repository.
