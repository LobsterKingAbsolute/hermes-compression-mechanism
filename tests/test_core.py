import copy
import unittest

from hermes_context import Budget, Compactor, ContextError, Policy, TaskState
from hermes_context.core import estimate_tokens, prepare


def conversation(n=8, size=300):
    messages = [{"role": "system", "content": "Do not disclose private data."}]
    for i in range(n):
        messages.extend([
            {"role": "user", "content": f"Task {i}: " + "synthetic " * (size // 10)},
            {"role": "assistant", "content": f"Result {i}: " + "example " * (size // 10)},
        ])
    return messages


def tool_turn(i, size=500):
    return [
        {"role": "user", "content": f"Inspect synthetic item {i}."},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"call_{i}", "type": "function", "function": {
                "name": "inspect", "arguments": '{"sample":true}'}}]},
        {"role": "tool", "tool_call_id": f"call_{i}", "content": "sample " * size},
        {"role": "assistant", "content": f"Inspected item {i}."},
    ]


class BudgetTests(unittest.TestCase):
    def test_reservations(self):
        self.assertEqual(Budget(4096, 512, 128, 64).input_limit, 3392)

    def test_invalid_values(self):
        for args in [(0,), (-1,), (100, 100, 0, 0), (True,), (1000, -1), (1000.5,)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Budget(*args)

    def test_policy_invalid(self):
        for kwargs in [{"keep_last_turns": 0}, {"keep_first_turns": -1},
                       {"summary_tokens": -1}, {"keep_last_turns": True}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Policy(**kwargs)

    def test_counter_unicode(self):
        self.assertGreater(estimate_tokens([{"role": "user", "content": "日本語🦞"}]), 0)

    def test_notes_type_validation(self):
        with self.assertRaises(ValueError):
            TaskState(decisions="not a tuple")


class ValidationTests(unittest.TestCase):
    def test_valid_parallel_tools(self):
        messages = tool_turn(0, 1)
        second = {"id": "other", "type": "function", "function": {"name": "read", "arguments": "{}"}}
        messages[1]["tool_calls"].append(second)
        messages.insert(2, {"role": "tool", "tool_call_id": "other", "content": "ok"})
        _, turns = prepare(messages)
        self.assertEqual(len(turns), 1)
        self.assertEqual(len(turns[0]), 5)

    def test_bad_histories(self):
        valid = tool_turn(0, 1)
        cases = [
            [{"role": "alien", "content": "x"}],
            [{"role": "user", "content": [{"type": "text", "text": "x"}]}],
            [{"role": "user", "content": "x", "hidden": "do not drop me"}],
            [{"role": "tool", "tool_call_id": "missing", "content": "x"}],
            valid[:-2],
            valid[:2] + [{"role": "user", "content": "interruption"}],
            valid[:2] + [{"role": "tool", "tool_call_id": "wrong", "content": "x"}],
            valid[:3] + [valid[2]],
            valid + valid,
            [{"role": "user", "content": "x"}, {"role": "system", "content": "late"}],
            [{"role": "assistant", "content": None}],
            [{"role": "user", "content": "x", "name": 1}],
            [{"role": "user", "content": "x", "tool_call_id": "extra"}],
            [{"role": "assistant", "content": "x", "tool_calls": []}],
        ]
        for case in cases:
            with self.subTest(case_number=cases.index(case)), self.assertRaises(ContextError):
                prepare(case)

    def test_safe_errors(self):
        marker = "PRIVATE-INPUT-MARKER"
        with self.assertRaises(ContextError) as error:
            prepare([{"role": marker, "content": marker}])
        self.assertNotIn(marker, str(error.exception))

    def test_control_prefix(self):
        messages = [{"role": "system", "content": "s"}, {"role": "developer", "content": "d"}]
        prefix, turns = prepare(messages + tool_turn(0, 1))
        self.assertEqual(prefix, messages)
        self.assertEqual(len(turns), 1)

    def test_input_is_not_mutated(self):
        messages = conversation()
        original = copy.deepcopy(messages)
        Compactor(Budget(10000)).compact(messages)
        self.assertEqual(messages, original)

    def test_oversized_and_non_list(self):
        for value in [None, "text", {}, [None], [{"role": "user", "content": 5}]]:
            with self.assertRaises(ContextError):
                prepare(value)
        with self.assertRaises(ContextError):
            prepare([{"role": "user", "content": "x" * 100}], max_bytes=20)


if __name__ == "__main__":
    unittest.main()
