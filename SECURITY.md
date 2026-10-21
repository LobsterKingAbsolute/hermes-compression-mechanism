# Security and privacy

## Scope
The installable `hermes_context` package and optional adapter are alpha software.
The historical `source/` snapshot is not a supported runnable agent distribution.
No claim is made that the entire upstream runtime has been hardened.

Normal library use does not make network requests, read provider credentials,
execute tools, or persist conversations. Custom summarizers can change the data
flow and require host consent. Masked excerpts are not guaranteed anonymous data.

## Core boundaries
- Strict text schema and complete tool chains; no silent dropping of unknown fields.
- Protected-context overflow raises rather than discarding current instructions.
- Summaries are untrusted history, not a prompt-injection sandbox.
- Reports omit content, identifiers and credentials. Exact origin indices are
  separate from reports and are not saved in CLI exports.
- Quoted secrets and secret-valued JSON argument fields are masked best-effort.
  Arbitrary private text, unusual credentials and structural IDs may remain.
- Protected in-memory content is not redacted. Export is explicit, unencrypted,
  exclusive-create and private by default on POSIX; Windows uses directory ACLs.
- Duplicate JSON keys and nonstandard numeric constants are rejected at file input.

## Optional Hermes plugin
Installation is preview-first and explicit. It never edits host configuration,
provider authentication or runtime databases. Existing destinations and symlink
paths are refused. The parent directory must be trusted: portable filesystem
checks are not a defense against a hostile local process racing the installer.

The adapter preserves retained host metadata by exact source occurrence. It does
not erase unknown reasoning/media fields or data-use requirements to force a fit:
unsupported inputs pass through intact. Nonempty provider memory also passes
through. Such requests may still overflow at the provider; inspect the outcome.
Clones isolate per-agent state; model/session reset invalidates in-flight results.

`doctor --hermes` explicitly imports the installed host interface. Ordinary package
import and the default offline doctor do not import Hermes. No diagnostic command
starts an agent, executes tools or invokes a model.

## Repository hygiene
Never add real conversations, client records, `.env*`, provider configs, keys,
runtime databases, media, logs or context exports. Tests use synthetic fixtures.

CI has read-only permissions and pinned action revisions. The tracked-file check
and Gitleaks repository/history scans complement each other; neither proves absence
of every form of private data. Git author email is a separate privacy surface.
Existing account metadata is not rewritten or anonymized by this project.

## Reporting
Do not paste a secret or transcript into a public issue. Use GitHub private
vulnerability reporting when available; otherwise ask for a private channel in a
content-free issue. Rotate exposed credentials first. Deleting a file does not
revoke a credential or erase repository history.
