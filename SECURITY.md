# Security and privacy

## Scope
The installable `hermes_context` package is a new alpha library. The `source/`
directory is historical reference code, not a supported runnable agent runtime.
No claim is made that the entire extracted upstream runtime has been hardened.

The library does not make network requests, read provider credentials, run tools,
or persist messages implicitly. Supplying your own summarizer can change the data
flow: it receives conversation excerpts with recognizable secrets masked, not a
guaranteed de-identified dataset. Obtain appropriate consent in the host.

## Boundaries
- Strict text-only schema; reject unsupported fields instead of silent data loss.
- Complete tool chains and a bounded input size are required.
- Protected-context overflow fails rather than discarding current instructions.
- Summaries remain untrusted history. A label is not a prompt-injection sandbox.
- `report()` does not include content, paths, IDs, or credentials.
- Protected in-memory context is not automatically redacted. Export is explicit,
  best-effort redacted, unencrypted, and must never be committed.
- Existing destination files/symlinks are not overwritten. POSIX mode is 0600;
  Windows privacy depends on directory ACLs. Interrupted writes can be incomplete.

## Repository hygiene
Do not add real conversations, client records, credentials, `.env*`, private keys,
provider configs, runtime databases, media, logs, or context exports. Tests must
construct synthetic secrets at runtime rather than storing usable credentials.

CI uses read-only permissions and pinned action revisions. The publication check
rejects sensitive file types and high-signal credential formats; a separate Gitleaks
job scans all reachable Git history. These are complementary automated checks, not
a proof of absence of sensitive information. Commit authorship metadata is a
separate privacy surface; old metadata is not rewritten automatically.

## Reporting
Do not paste a secret or private transcript into a public issue. Use GitHub's
private vulnerability reporting when available. Otherwise open a content-free
issue asking the maintainer for a private reporting channel. Rotate exposed
credentials first; removing a file does not revoke a credential or erase history.
