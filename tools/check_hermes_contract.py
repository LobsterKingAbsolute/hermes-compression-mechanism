"""Verify the pinned upstream ABC, without importing its full agent runtime.

Run only on the pinned public source retrieved by CI. This tests the actual ABC
class plus our adapter; it does not certify providers, loader isolation, or a
live Hermes session.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_context.cli import demo_messages
from hermes_context.hermes import HermesContextAdapter

COMMIT = "4d04303818b61bf3aa09278af48356315515965b"
BLOB = "eec8ac0efcda5363ba8cc971c32e1562988e3b02"


def main(path: Path) -> None:
    raw = path.read_bytes()
    digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if digest != BLOB:
        raise SystemExit("Upstream ABC differs from the reviewed pin; review before updating.")
    tree = ast.parse(raw.decode("utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ContextEngine")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, cls], type_ignores=[]))
    namespace = {"ABC": ABC, "abstractmethod": abstractmethod, "copy": copy, "json": json,
                 "Any": Any, "Dict": Dict, "List": List, "Optional": Optional}
    exec(compile(module, "<pinned-upstream-ABC>", "exec"), namespace)
    base = namespace["ContextEngine"]
    bound = type("BoundHermesContext", (HermesContextAdapter, base), {})
    assert not inspect.isabstract(bound)
    engine = bound()
    engine.update_model("synthetic-contract-model", 4096)
    messages = demo_messages(30)
    result = engine.compress(messages, current_tokens=17000, focus_topic=None, force=True, memory_context="")
    assert len(result) < len(messages)
    assert result[-8:] == messages[-8:]
    assert engine.select_context(messages, budget_tokens=4096) is None
    assert engine.get_tool_schemas() == []
    assert engine.prune_tool_results_only(messages) == (messages, 0)
    engine.on_turn_complete(messages, usage=None)
    clone = engine.clone_for_agent()
    clone.update_model("synthetic-child", 2048)
    assert isinstance(clone, base) and engine.context_length == 4096
    assert clone._lock is not engine._lock
    print(json.dumps({"upstream_commit": COMMIT, "upstream_blob": BLOB,
                      "check": "extracted upstream ABC contract", "passed": True}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tools/check_hermes_contract.py <pinned-context_engine.py>")
    main(Path(sys.argv[1]))
