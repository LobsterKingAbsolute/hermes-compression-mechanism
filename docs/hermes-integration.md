# Hermes integration

## What is actually integrated

The opt-in plugin implements `ContextEngine.name`, usage updates, compression,
preflight checks, model updates, status, session reset, and per-agent cloning.
Its signature includes `current_tokens`, `focus_topic`, `force`, and
`memory_context`. It inherits the host's optional no-op selection/tool hooks.

Reference examined on 2026-10-21:
[NousResearch/hermes-agent at 4d04303818b61bf3aa09278af48356315515965b](https://github.com/NousResearch/hermes-agent/tree/4d04303818b61bf3aa09278af48356315515965b).
The CI contract check validates the actual `agent/context_engine.py` blob
`eec8ac0efcda5363ba8cc971c32e1562988e3b02` and constructs a subclass of its ABC.
It extracts that class to avoid importing the entire runtime and its providers.
This is an interface/behavior check, **not** an end-to-end live-agent test.

## Install without changing a working setup

1. Choose the Python executable used by Hermes. Install this project into that
   environment using `python -m pip install` with a reviewed repository commit.
   The package is not published to PyPI. Do not accidentally install into a second
   interpreter; `doctor --hermes` checks whether the current interpreter can bind
   the engine to the installed Hermes interface.
2. Run `python -m hermes_context doctor`, then `python -m hermes_context doctor --hermes`.
   The optional host check imports the installed host interface, but does not run
   an agent or make a model request. Import failures are reported without raw paths
   or provider exception text.
3. Preview the plugin files:

   ```bash
   python -m hermes_context install-hermes --destination "<HERMES_HOME>/plugins/hermes_context"
   ```

4. Set budget options to match your host and repeat with `--apply`. The installer
   creates `__init__.py`, `plugin.yaml`, and `options.json`. It refuses to overwrite
   an existing plugin and does not edit your Hermes configuration, credentials,
   runtime databases, or production checkout.
5. Set `context.engine: hermes_context` in your own Hermes config and restart the
   agent/session. In the current host, this context-engine selection is the opt-in;
   no general `plugins.enabled` entry is required for a directory engine.
6. Test with synthetic tasks before real work. `get_status()` exposes
   `last_outcome`, estimated before/after counts and successful compression count.

`<HERMES_HOME>` is a placeholder for your actual Hermes home. Paths with spaces
must be quoted. The installer does not guess custom Hermes locations. Its parent
folder must be trusted; portable symlink checks do not defeat a malicious local
process racing filesystem operations.

## Options

| Option / installer flag | Default | Meaning |
| --- | ---: | --- |
| `threshold_percent` / `--threshold-percent` | 0.75 | Context-window fraction at which to target compaction |
| `reserved_output` / `--reserved-output` | 1024 | Space reserved for the host's model output |
| `request_overhead` / `--request-overhead` | 0 | System/schema/other request tokens not represented in input |
| `safety_margin` / `--safety-margin` | 128 | Additional buffer |
| `keep_first_turns` / `--keep-first-turns` | 1 | Protected first complete turns |
| `keep_last_turns` / `--keep-last-turns` | 2 | Protected recent complete turns |
| `summary_tokens` / `--summary-tokens` | 384 | Maximum wrapped summary size under the approximate counter |

The effective target is the smaller of the threshold and the remaining input
budget after reservations. A large output reserve therefore triggers compaction
before the fractional threshold when necessary. The model window comes from the
host's `update_model()` call; no changing vendor model limits are hard-coded.

Use the **actual** output limit, not an assumed universal value. The adapter uses
the documented approximate counter. Real provider usage triggers checks but does
not magically make byte estimates exact. The standalone library supports custom
counters; this first adapter intentionally uses the offline default.

The plugin owns its policy: Hermes' built-in `compression.*` settings, including
model-specific threshold maps, are not applied. Configure this plugin through its
non-secret `options.json`; unknown options are rejected. Restart after changes.

## Retention and safe fallback

`message_uid`, tool occurrence IDs and other host persistence fields are excluded
from model-size estimation, then restored from the exact retained input positions.
Equal message text is not treated as identity. The current host's explicit
`PERSISTENCE_ONLY_MESSAGE_FIELDS` set is used at binding time; arbitrary underscore
keys are not silently assumed to be harmless metadata.

New summaries are marked `_compressed_summary`; Hermes can mint their durable UID
when persisting them. The plugin never opens the session database itself.

| Outcome | Behavior |
| --- | --- |
| `compressed` | Older complete turns removed; bounded historical notes may be inserted |
| `no_change` | Context already fits the configured target |
| `protected_overflow` | Original history returned; current instructions are not truncated |
| `unsupported_input` | Original history returned; unknown fields/media/reasoning/data-use restrictions kept intact |
| `unsupported_memory_context` | Original history returned; nonempty provider memory needs a future dedicated integration |
| `invalid_budget` | Reservations exceed capacity; original history returned |
| `unconfigured` | Host has not supplied a context window; original history returned |
| `unchanged_context` | An identical unsuccessful input was not retried; `force` can bypass this guard |

Manual focus text is accepted for signature compatibility but not used by the
extractive summarizer; status reports `focus_supported: false`. `force` bypasses
no-op suppression, never safety validation or protected-context limits.

Fail-open does **not** guarantee an unsupported request fits a provider. Inspect
the status; use the built-in compressor until your workload fits this adapter's
text-only boundary. The plugin is not a replacement for data-use enforcement.

## Threads, sessions and rollback

Each agent clone receives separate counters, reservations and lock state. A model
switch or session reset invalidates an in-flight result. Concurrent passes on one
instance do not mutate a shared conversation. There are no external writes or
model calls inside the adapter, so a host timeout cannot leave background durable
side effects from this plugin.

To roll back, select `context.engine: compressor` and restart. The plugin directory
can remain installed but inactive. Future upgrades should be reviewed and applied
with the agent stopped; the installer intentionally does not auto-overwrite an
existing plugin or change its selected engine.
