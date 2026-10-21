"""Synthetic, offline counter benchmark. No provider calls or quality claims."""
import json

from hermes_context import Budget, Compactor
from hermes_context.cli import demo_messages

for turns in (10, 30, 100):
    result = Compactor(Budget(4096, 512)).compact(demo_messages(turns))
    print(json.dumps({"scenario": "synthetic_tool_history", "turns": turns, **result.report()}, sort_keys=True))
