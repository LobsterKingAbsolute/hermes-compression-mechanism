# Architecture and integration contract

`core.prepare` validates and copies bounded text messages into complete user turns.
Tool IDs may repeat in later completed exchanges; duplicate IDs inside a single
assistant batch, orphan results and unfinished batches are rejected. The core
never repairs malformed input by silently throwing content away.

`Budget` reserves output, request overhead and a safety margin. `Compactor` protects
the control prefix and configured first/recent turns, removes eligible oldest turns,
then optionally inserts an explicitly untrusted user-role summary. Failure to fit
the protected skeleton raises `BudgetExceeded`. A callback is invoked at most once.

For the default byte estimator, exact serialized-message lengths allow the
remaining candidate size to be updated without repeatedly copying and recounting
every suffix. Custom counters retain the direct, separately verified counting path.
Every output is validated and checked against its final budget.

`Result.source_indices` identifies retained **occurrences**, not text hashes or
provider call IDs. A generated note has index `None`. The Hermes adapter uses this
mapping to recover the correct durable metadata even for identical messages.
It is deliberately absent from `report()`, which contains only scalar metrics.

## Counter and summary contracts

`counter(messages) -> int` must be deterministic, nonnegative, side-effect-free
and account for all relevant message fields. Default UTF-8/3 plus framing is an
approximation, not a provider tokenizer or universal bound. Extra request fields
belong in `request_overhead`. The optimization is used only by the default path.

`summarizer(redacted_messages, max_tokens) -> str` is synchronous and explicit.
Recognizable secrets are masked before and after it. Tool argument JSON is redacted
structurally when valid; malformed input receives best-effort text masking. Network
calls inside a custom callback are the host application's responsibility.

`TaskState` holds explicit caller notes. It is not a durable state database or an
automatic semantic-memory system. Protected in-memory messages remain unchanged,
including private values; compaction is not a general data-loss-prevention service.

## Hermes boundary

`hermes.HermesContextAdapter` is a dependency-free mixin. The optional plugin binds
it to the installed host's actual `ContextEngine` ABC and persistence metadata set.
No Hermes imports occur on normal package import. Recognized retained metadata is
restored exactly; unsupported schemas and restricted content pass through intact.
See [integration](hermes-integration.md) for supported/unsupported cases.

The adapter has per-agent mutable state protected by a lock and reset generation.
It stores counters, configuration and a no-op fingerprint, not conversation text.
Model changes invalidate old usage and in-flight results. Installation is explicit,
preview-first and does not edit host config. It does not access a provider, execute
tools, or modify the upstream Hermes checkout.

## Local export

Version-1 files use `{"schema_version": 1, "messages": [...]}`. They are plain JSON,
not encrypted/signed/transactional multi-writer checkpoints. Duplicate JSON keys
and nonstandard numeric constants are rejected. Export is explicit, best-effort
redacted and exclusive-create. Interrupted writes may be incomplete; malformed
files will not load. Treat all exports as private.

No live-provider or semantic-recall evaluation is claimed. The original `source/`
subtree is historical material, not the installed runtime or a hardened agent.
