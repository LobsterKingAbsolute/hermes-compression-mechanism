import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from hermes_context import Budget, Compactor, ContextError, Policy, TaskState
from hermes_context.cli import _load, main
from hermes_context.core import MAX_BYTES, prepare
from test_core import conversation


class BoundaryTests(unittest.TestCase):
    def test_wrong_configuration_types(self):
        for kwargs in [{"budget": 1}, {"budget": Budget(4096), "policy": {}}]:
            with self.assertRaises(ContextError):
                Compactor(**kwargs)
        with self.assertRaises(ContextError):
            Compactor(Budget(4096)).compact([], state={})

    def test_notes_with_overlapping_protection(self):
        messages = conversation(2, 20)
        result = Compactor(Budget(4096), policy=Policy(keep_first_turns=5)).compact(
            messages, state=TaskState(decisions=("Keep state",)))
        self.assertEqual(result.messages[:3], messages[:3])
        self.assertEqual(result.messages[-2:], messages[-2:])
        self.assertEqual(len(result.messages), len(messages) + 1)

    def test_empty_notes_are_noop(self):
        messages = conversation(2, 20)
        self.assertEqual(Compactor(Budget(4096)).compact(messages, state=TaskState()).messages, messages)

    def test_counter_error_is_suppressed(self):
        def counter(messages):
            raise RuntimeError("PRIVATE VALUE")
        with self.assertRaises(ContextError) as error:
            Compactor(Budget(4096), counter=counter).compact(conversation(2))
        self.assertNotIn("PRIVATE", str(error.exception))

    def test_invalid_unicode(self):
        with self.assertRaises(ContextError):
            prepare([{"role": "user", "content": "\ud800"}])
        with self.assertRaises(ContextError):
            TaskState(decisions=("\ud800",))
        with self.assertRaises(ContextError):
            Compactor(Budget(1200, 100, 0, 0), summarizer=lambda *_: "\ud800").compact(conversation(12))

    def test_oversized_summary(self):
        with self.assertRaises(ContextError):
            Compactor(Budget(1200, 100, 0, 0), summarizer=lambda *_: "x" * (MAX_BYTES + 1)).compact(conversation(12))

    def test_oversized_notes(self):
        with self.assertRaises(ContextError):
            TaskState(decisions=("x" * (MAX_BYTES + 1),))

    def test_summary_callback_cannot_mutate_input(self):
        messages = conversation(12)
        original = json.dumps(messages)
        def summarize(history, max_tokens):
            history.clear()
            return "Older work was summarized."
        Compactor(Budget(1200, 100, 0, 0), summarizer=summarize).compact(messages)
        self.assertEqual(json.dumps(messages), original)

    def test_empty_summary(self):
        result = Compactor(Budget(1200, 100, 0, 0), summarizer=lambda *_: "").compact(conversation(12))
        self.assertFalse(result.stats.summary_used)
        self.assertTrue(result.stats.lossy)

    def test_no_protected_head(self):
        messages = conversation(12)
        result = Compactor(Budget(1000, 0, 0, 0), policy=Policy(keep_first_turns=0)).compact(messages)
        self.assertEqual(result.messages[0], messages[0])
        self.assertEqual(result.messages[-4:], messages[-4:])

    def test_invalid_tool_shape(self):
        with self.assertRaises(ContextError):
            prepare([{"role": "assistant", "content": None, "tool_calls": [{"id": "a"}]}])

    def test_cli_large_and_non_list_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for content in ['"text"', " " * (MAX_BYTES + 1)]:
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ContextError):
                    _load(path)

    def test_cli_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps([{"role": "user", "content": "PRIVATE " * 1000}]))
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(["compact", str(path), "--context-window", "1000", "--reserved-output", "0"])
            self.assertEqual(code, 3)
            self.assertNotIn("PRIVATE", out.getvalue() + err.getvalue())

    @unittest.skipUnless(os.name == "posix", "POSIX symlink case")
    def test_export_refuses_symlink(self):
        from hermes_context.cli import _export
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.json"
            target.write_text("untouched")
            link = Path(directory) / "link.json"
            link.symlink_to(target)
            with self.assertRaises(ContextError):
                _export(link, [{"role": "user", "content": "x"}])
            self.assertEqual(target.read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()
