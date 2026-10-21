# Hermes Context

Offline context compaction for text agents, with an opt-in Hermes context-engine plugin.

**0.2.0 alpha · Python 3.11+ · MIT · No runtime dependencies**

Keep the leading instructions and recent complete turns. Replace eligible older
history with bounded, explicitly untrusted notes. Never split a tool call from its
results, silently truncate the current task, or invoke an external model by default.

## Run it without a model or API key

```bash
python -m pip install "git+https://github.com/LobsterKingAbsolute/hermes-compression-mechanism.git"
hermes-context doctor
hermes-context demo
```

Pin a reviewed commit for reproducible installations. No PyPI release is claimed.
The demo uses only generated synthetic data. Default CLI output contains metrics,
not conversations. The library does not execute tools or make provider calls.

## New in 0.2

- **Hermes adapter:** implements the current context-engine interface, clones state
  per agent, resets usage on model switches, and discards stale compression results
  after a reset. Activation is explicit; installation never edits Hermes config.
- **Correct message identity:** retained rows recover their exact original metadata
  by input position, even when messages have identical text or reused tool IDs.
- **Faster long histories:** the default counter no longer repeatedly recounts every
  remaining suffix. Custom counters retain an independently checked path.
- **Better redaction:** quoted secrets with spaces are fully masked; structured
  tool arguments retain valid JSON while secret-valued fields are replaced.
- **Diagnostics and installation:** `doctor`, `doctor --hermes`, `--version`, and
  `install-hermes` with a preview default and no overwriting existing installs.

## Use the library

```python
from hermes_context import Budget, Compactor, TaskState

messages = [
    {"role": "system", "content": "Do not perform external actions without approval."},
    {"role": "user", "content": "Build a local prototype."},
    {"role": "assistant", "content": "The first tests pass."},
    {"role": "user", "content": "Review error handling next."},
]
engine = Compactor(Budget(
    context_window=8192,
    reserved_output=1024,
    request_overhead=256,
    safety_margin=256,
))
result = engine.compact(messages, state=TaskState(
    decisions=("Use SQLite",),
    constraints=("No network calls",),
))
next_messages = result.messages
print(result.report())  # Scalar metrics, no transcript.
```

`result.source_indices` maps each retained output row to its exact input index;
`None` marks a generated note. It is not part of the metrics report or CLI export.
A protected context that cannot fit raises `BudgetExceeded`, leaving input untouched.

The budget is `context_window - reserved_output - request_overhead - safety_margin`.
The built-in byte-based counter is **approximate**, not a provider tokenizer or a
universal upper bound. Include tool schemas and all other request overhead. Supply
an appropriate custom counter for stricter model-specific accounting.

Compaction is **lossy**. Local excerpts may omit an older fact. `TaskState` holds
caller-authored notes, not automatically inferred permanent memory. Do not assume
that a lower token estimate implies better answers or lower real API bills.

## Enable it in Hermes

Use **the same Python environment that runs Hermes**, not an unrelated global pip:

```bash
python -m hermes_context doctor --hermes
python -m hermes_context install-hermes --destination "<HERMES_HOME>/plugins/hermes_context"
# Review the preview; create the plugin only when ready:
python -m hermes_context install-hermes --destination "<HERMES_HOME>/plugins/hermes_context" --apply
```

Replace `<HERMES_HOME>` with your actual Hermes home directory. Then select it:

```yaml
context:
  engine: hermes_context
```

Restart the agent/session. To roll back, change the engine to `compressor` and
restart. Set the plugin's output reservation to the host's real output limit and
account for external prompt/schema overhead; the defaults are not model-specific.
[Full installation, options, rollback, and compatibility notes](docs/hermes-integration.md).

### Compatibility boundary

The adapter is tested against the context-engine ABC from the pinned upstream
revision documented in the integration guide. This is **not** a certification of
all live providers, the complete Hermes runtime, or your local installation.

Recognized persistence metadata is preserved on retained rows. Unknown fields,
multimodal content, opaque reasoning blocks, incomplete tool chains, duplicate IDs
within one call batch, and data-use constrained histories **pass through intact**.
A nonempty provider `memory_context` also passes through rather than being ignored.
An unsupported request may still be too large for its provider. Check `get_status()`
for the content-free outcome instead of assuming compression happened.

The standalone core deliberately remains stricter and raises on unsupported
schemas. Reused call IDs are allowed across completed exchanges, not within a batch.

## CLI and privacy

```bash
hermes-context --version
hermes-context compact history.json --context-window 8192 --reserved-output 1024
hermes-context compact history.json --output .hermes-context/continuation.json
```

Create the destination directory first. No `--output` means no transcript file.
Export is explicit, best-effort redacted, unencrypted, and never overwrites an
existing file. It may still contain private text or structural IDs. Do not publish
exports. POSIX files use 0600; Windows privacy also depends on the parent ACL.
Malformed JSON and duplicate keys are rejected. Exit codes: 0 success, 2 validation
or setup error, 3 protected-context overflow.

A custom standalone `summarizer(redacted_history, max_tokens) -> str` callback is
called at most once. Using a network provider inside it is the host application's
explicit choice and requires appropriate consent. Redaction is not guaranteed
anonymization, and labeling a summary is not a prompt-injection sandbox.

## Development

```bash
python -m pip install .
python -m unittest discover -s tests -v
python benchmarks/benchmark.py
python tools/publication_scan.py
```

Tests include repeated compaction, randomized tool histories, cross-agent state,
concurrent reset, exact metadata recovery, secret masking and installation safety.
CI also checks a pinned upstream ABC and scans tracked content and Git history.
See [security](SECURITY.md), [contributing](CONTRIBUTING.md), and
[0.2 verification](docs/verification-0.2.0.md).

## Attribution

Independent community project, not an official Nous Research or OpenAI product.
The historical Hermes extraction under `source/` remains reference material,
unchanged and excluded from the wheel. New implementation: `src/hermes_context/`.
Original MIT attribution is preserved; see [NOTICE.md](NOTICE.md).
