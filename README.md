# Hermes Context

**Keep the current task. Compact old turns. Never split a tool exchange.**

A small, offline-first Python library for agents whose conversation history grows
past a request budget. It preserves system/developer instructions, the first task,
and recent whole turns, then replaces eligible middle history with bounded,
explicitly untrusted notes.

**Status: 0.1.0 alpha.** Text-only, standard-library runtime, Python 3.11+.
The default summarizer is local and extractive: no account, model, API key,
telemetry, environment-variable access, or network call. No PyPI release is claimed;
install from this repository. This is not a drop-in Hermes plugin.

## Try it

```bash
python -m pip install "git+https://github.com/LobsterKingAbsolute/hermes-compression-mechanism.git"
hermes-context demo
```

The demo uses generated synthetic messages and prints only numeric/scalar metrics.
For reproducible installations, pin an audited commit rather than following main.

```python
from hermes_context import Budget, Compactor, TaskState

messages = [
    {"role": "system", "content": "Do not send messages without approval."},
    {"role": "user", "content": "Build a local prototype."},
    {"role": "assistant", "content": "The first tests pass."},
    {"role": "user", "content": "Now review the error handling."},
]
engine = Compactor(Budget(
    context_window=8192,
    reserved_output=1024,
    request_overhead=256,  # Account for tool schemas and other request fields.
    safety_margin=256,
))
result = engine.compact(messages, state=TaskState(
    decisions=("Use SQLite",),
    constraints=("No network calls",),
))
print(result.report())          # No conversation text in this report.
next_messages = result.messages
```

## What it does

| Boundary | Behavior |
| --- | --- |
| Leading system/developer instructions | Preserved verbatim |
| First user turn and latest two turns | Preserved by default; policy is configurable |
| Parallel function calls and their results | Validated and retained/removed as whole turns |
| Protected content is too large | Raises `BudgetExceeded`; never silently truncates it |
| Eligible middle history | Oldest turns removed first; optional bounded summary |
| Summary authority | User-role historical notes, never a system/developer message |
| Decisions and constraints | Explicit `TaskState` notes; no claim of inferred perfect recall |
| Counters | Injectable; default is an approximation, not provider token usage |
| Logging | `result.report()` contains scalar metrics only |
| Local resume | Explicit versioned JSON export/import; no hidden session storage |

The budget is `context_window - reserved_output - request_overhead - safety_margin`.
The returned messages fit **the configured counter**, not necessarily a provider's
true tokenizer. The built-in UTF-8/3 estimate can undercount or overcount. Supply a
provider/model-aware counter and account for schemas, media, framing and reasoning
requirements in your host application. The library does not query model limits.

Compaction is **lossy**. Local excerpts can omit an important older fact. Put critical
state in `TaskState` or protected turns, and evaluate answer quality in your own
workload. Smaller context does not itself prove better answers or lower API bills.

## A real summarizer is opt-in

```python
def my_summarizer(redacted_history, max_tokens):
    # Your application implements this synchronous callback.
    # A provider call here sends conversation content outside your process.
    return "Previously chose SQLite; deployment has not happened."

engine = Compactor(Budget(8192), summarizer=my_summarizer)
```

A callback is invoked at most once per compaction, and only when summary space is
available. Recognizable credentials are masked before and after it. Redaction is
best-effort, not a guarantee: arbitrary private data and structural tool identifiers
may remain. The host must obtain appropriate consent before using an external model.
Errors stop compaction rather than silently retrying or making fallback API calls.

## Local files and privacy

```bash
hermes-context compact history.json --context-window 8192 --reserved-output 1024
# Optional: writes a NEW local file, never overwrites an existing destination.
hermes-context compact history.json --output .hermes-context/continuation.json
```

Create the destination directory yourself. Without `--output`, only metrics reach
stdout. Export is best-effort redacted, not encrypted, and may still contain private
conversation content. POSIX files use mode 0600; Windows access also depends on the
parent directory ACL. Do not commit exports. Interrupted writes may leave an
incomplete file; the loader rejects malformed JSON. Exit codes: 0 success,
2 validation/I/O error, 3 protected-context overflow.

## Supported message boundary

Supported: `role`, text `content`, optional `name`, assistant `tool_calls` with
function `id/name/arguments`, and tool `tool_call_id`. All tool results must be
present before compaction. Controls must form a leading prefix.

Unsupported fields, legacy `function_call`, images/audio, native Responses API
items, and provider-specific reasoning/signature blocks are **rejected**, not
silently dropped. Convert them in a host adapter with suitable accounting before
using this release. Tool calls are data; this package never executes them.

## Test and benchmark

```bash
python -m pip install .
python -m unittest discover -s tests -v
python benchmarks/benchmark.py
python tools/publication_scan.py
```

The suite includes randomized synthetic histories, malformed tool chains, protected
budget overflow, callback privacy, non-overwriting exports and repeat compaction.
The benchmark is offline and prints reproducible counter-based savings, not model
quality scores. See [architecture](docs/architecture.md),
[security](SECURITY.md), and [contributing](CONTRIBUTING.md).

## Relationship to Hermes Agent

The historical `source/` extraction and old analysis documents remain as reference
material. They are not imported or shipped in the wheel. New library code lives in
`src/hermes_context/`. MIT; original Nous Research attribution is preserved.
See [NOTICE.md](NOTICE.md). Independent community project, not an official
Nous Research or OpenAI product.
