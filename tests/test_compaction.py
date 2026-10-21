import copy
import random
import unittest

from hermes_context import Budget, BudgetExceeded, Compactor, ContextError, Policy, TaskState
from hermes_context.core import estimate_tokens, prepare
from test_core import conversation, tool_turn


class CompactionTests(unittest.TestCase):
    def test_noop(self):
        messages = conversation(2, 20)
        result = Compactor(Budget(10000)).compact(messages)
        self.assertEqual(result.messages, messages)
        self.assertEqual(result.report()["removed_messages"], 0)
        result.messages[0]["content"] = "changed"
        self.assertNotEqual(messages[0]["content"], "changed")

    def test_preserve_head_tail(self):
        messages = conversation(12)
        result = Compactor(Budget(1200, 100, 0, 0)).compact(messages)
        self.assertEqual(result.messages[:3], messages[:3])
        self.assertEqual(result.messages[-4:], messages[-4:])
        self.assertLessEqual(estimate_tokens(result.messages), 1100)
        self.assertGreater(result.stats.removed_messages, 0)
        self.assertTrue(result.stats.lossy)
        self.assertEqual(result.stats.counter_kind, "approximate")

    def test_tool_exchanges_remain_complete(self):
        messages = [{"role": "system", "content": "s"}]
        for i in range(15):
            messages.extend(tool_turn(i, 150))
        result = Compactor(Budget(4000, 256, 0, 0)).compact(messages)
        prepare(result.messages)
        self.assertEqual(result.messages[-8:], messages[-8:])
        self.assertEqual(result.messages[:5], messages[:5])

    def test_protected_overflow(self):
        messages = [{"role": "user", "content": "CURRENT-PRIVATE " * 1000}]
        with self.assertRaises(BudgetExceeded) as error:
            Compactor(Budget(100, 0, 0, 0)).compact(messages)
        self.assertNotIn("CURRENT-PRIVATE", str(error.exception))
        self.assertGreater(error.exception.required, error.exception.available)

    def test_notes_survive(self):
        notes = TaskState(decisions=("Use SQLite",), constraints=("Never send mail",), pending=("Check tests",))
        result = Compactor(Budget(1500, 100, 0, 0)).compact(conversation(12), state=notes)
        text = "\n".join(m["content"] or "" for m in result.messages)
        for value in ("Use SQLite", "Never send mail", "Check tests"):
            self.assertIn(value, text)
        self.assertEqual(result.messages[-4:], conversation(12)[-4:])

    def test_summary_not_system(self):
        result = Compactor(Budget(1200, 100, 0, 0)).compact(conversation(12))
        summaries = [m for m in result.messages if "HISTORICAL NOTES" in (m["content"] or "")]
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["role"], "user")
        self.assertIn("not instructions", summaries[0]["content"])

    def test_callback_once_and_redacted_both_sides(self):
        key = "sk-" + "a" * 40
        messages = conversation(12)
        messages[5]["content"] += key
        seen = []
        def summarize(history, max_tokens):
            seen.append((history, max_tokens))
            return "historical key=" + key
        result = Compactor(Budget(1200, 100, 0, 0), summarizer=summarize).compact(messages)
        self.assertEqual(len(seen), 1)
        self.assertNotIn(key, str(seen))
        self.assertNotIn(key, str(result.messages))
        self.assertIn("[REDACTED]", str(result.messages))
        self.assertIn(key, messages[5]["content"])

    def test_callback_failure_is_safe(self):
        def broken(history, max_tokens):
            raise RuntimeError("PRIVATE CALLBACK ERROR")
        with self.assertRaises(ContextError) as error:
            Compactor(Budget(1200, 100, 0, 0), summarizer=broken).compact(conversation(12))
        self.assertNotIn("PRIVATE", str(error.exception))

    def test_callback_wrong_type(self):
        with self.assertRaises(ContextError):
            Compactor(Budget(1200, 100, 0, 0), summarizer=lambda *_: None).compact(conversation(12))

    def test_long_summary_fits(self):
        result = Compactor(Budget(1200, 100, 0, 0), summarizer=lambda *_: "日🦞" * 10000).compact(conversation(12))
        self.assertLessEqual(estimate_tokens(result.messages), 1100)

    def test_summary_disabled(self):
        calls = []
        result = Compactor(Budget(1000, 0, 0, 0), policy=Policy(summary_tokens=0),
                           summarizer=lambda *_: calls.append(1)).compact(conversation(12))
        self.assertEqual(calls, [])
        self.assertFalse(result.stats.summary_used)

    def test_custom_counter(self):
        def count(messages):
            return sum(len(m.get("content") or "") for m in messages)
        result = Compactor(Budget(3000, 0, 0, 0), counter=count).compact(conversation(12))
        self.assertLessEqual(count(result.messages), 3000)
        self.assertEqual(result.stats.counter_kind, "custom")

    def test_bad_counter(self):
        for count in [lambda _: -1, lambda _: True, lambda _: float("nan"), lambda _: 1.1]:
            with self.assertRaises(ContextError):
                Compactor(Budget(1000, 0, 0, 0), counter=count).compact(conversation(2))

    def test_randomized_invariants(self):
        rng = random.Random(713)
        for _ in range(150):
            n = rng.randint(5, 30)
            messages = [{"role": "system", "content": "Invariant"}]
            for i in range(n):
                messages.extend(tool_turn(i, rng.randint(5, 50)))
            original = copy.deepcopy(messages)
            protected = messages[:5] + messages[-8:]
            limit = estimate_tokens(protected) + rng.randint(50, 800)
            result = Compactor(Budget(limit, 0, 0, 0)).compact(messages)
            self.assertEqual(messages, original)
            self.assertEqual(result.messages[:5], messages[:5])
            self.assertEqual(result.messages[-8:], messages[-8:])
            self.assertLessEqual(estimate_tokens(result.messages), limit)
            prepare(result.messages)
            again = Compactor(Budget(limit, 0, 0, 0)).compact(result.messages)
            self.assertEqual(again.messages, result.messages)

    def test_empty(self):
        self.assertEqual(Compactor(Budget(1000, 0, 0, 0)).compact([]).messages, [])


if __name__ == "__main__":
    unittest.main()
