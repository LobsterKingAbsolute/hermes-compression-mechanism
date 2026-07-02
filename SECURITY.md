# Security

This repository is intended to contain only source code and public-safe
analysis for the Hermes compression mechanism.

## Reporting

If you find a real secret, private transcript, provider credential, or runtime
artifact in this repository, treat it as a security issue and report it through
the repository owner rather than opening a public issue with the secret value.

## Export Boundary

The export boundary is source code plus explanatory documentation only. Runtime
state and local operator data are out of scope:

- No auth files or environment files.
- No SQLite databases or message rows.
- No provider request/response payloads.
- No logs, run captures, process metadata, or recovery artifacts.
- No local dashboards, caches, virtual environments, or generated build output.

## Known Safe Patterns

Some source files contain redaction regexes, field names such as `token` or
`secret`, and tests/docs that discuss secret handling. Those are code patterns,
not credentials. A publication scan should still inspect every match manually.

