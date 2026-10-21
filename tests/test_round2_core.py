import copy
import json
import unittest
from unittest.mock import patch

from hermes_context import Budget, Compactor, ContextError, Policy, TaskState, redact_text, redact_messages
from hermes_context.core import estimate_tokens, prepare
from test_core import conversation, tool_turn


class RoundTwoCoreTests(unittest.TestCase):
    def test_repeated_ids_after_completed_exchange(self):
        messages = tool_turn(0, 1) + tool_turn(0, 2)
        try:
            _, turns = prepare(messages)
        except ContextError:
            self.fail("Completed exchanges must be allowed to reuse a provider call ID")
        self.assertEqual(len(turns), 2)

    def test_duplicate_ids_in_same_batch_still_rejected(self):
        messages = tool_turn(0, 1)
        messages[1]["tool_calls"].append(copy.deepcopy(messages[1]["tool_calls"][0]))
        with self.assertRaises(ContextError):
            prepare(messages)

    def test_origin_indices_with_identical_messages(self):
        messages = [{"role": "system", "content": "Control"}]
        for _ in range(20):
            messages.extend(conversation(1, 100)[1:])
        result = Compactor(Budget(600, 0, 0, 0), policy=Policy(summary_tokens=0)).compact(messages)
        self.assertTrue(hasattr(result, "source_indices"), "Need exact origin indices to restore host identity")
        self.assertEqual(len(result.messages), len(result.source_indices))
        self.assertEqual(result.source_indices[-4:], tuple(range(len(messages) - 4, len(messages))))
        for message, index in zip(result.messages, result.source_indices):
            if index is not None:
                self.assertEqual(message, messages[index])
        self.assertNotIn("source_indices", result.report())

    def test_origin_indices_for_notes_and_summary(self):
        messages = conversation(12)
        result = Compactor(Budget(1500, 100, 0, 0)).compact(messages, state=TaskState(decisions=("SQLite",)))
        self.assertTrue(hasattr(result, "source_indices"))
        self.assertEqual(result.source_indices.count(None), 2)
        for message, index in zip(result.messages, result.source_indices):
            if index is not None:
                self.assertEqual(message, messages[index])

    def test_default_counting_does_not_rescan_every_remaining_suffix(self):
        messages = conversation(400, 100)
        engine = Compactor(Budget(1000, 0, 0, 0))
        with patch.object(engine, "_count", wraps=engine._count) as counted:
            result = engine.compact(messages)
        self.assertLess(counted.call_count, 40)
        self.assertLessEqual(estimate_tokens(result.messages), 1000)

    def test_default_and_explicit_same_counter_give_same_result(self):
        for size in (20, 80, 150):
            for budget in (1000, 1500, 3000):
                messages = conversation(30, size)
                a = Compactor(Budget(budget, 0, 0, 0)).compact(messages)
                b = Compactor(Budget(budget, 0, 0, 0), counter=estimate_tokens).compact(messages)
                self.assertEqual(a.messages, b.messages)
                self.assertEqual(a.stats.after, b.stats.after)

    def test_quote_delimited_secret_is_fully_masked(self):
        for text in ['password="alpha beta gamma"', "secret='alpha beta gamma'", 'token="alpha beta gamma"']:
            result = redact_text(text)
            self.assertNotIn("alpha", result)
            self.assertNotIn("beta", result)
            self.assertNotIn("gamma", result)
            self.assertEqual(redact_text(result), result)

    def test_json_arguments_redaction_stays_valid(self):
        args = {"nested": {"client_secret": "alpha beta", "password": ["first", "second"]},
                "keep": 12, "authorization": "Basic " + "X" * 32}
        messages = tool_turn(0, 1)
        messages[1]["tool_calls"][0]["function"]["arguments"] = json.dumps(args)
        result = redact_messages(messages)
        clean = json.loads(result[1]["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(clean["nested"]["password"], "[REDACTED]")
        self.assertEqual(clean["nested"]["client_secret"], "[REDACTED]")
        self.assertEqual(clean["keep"], 12)
        self.assertNotIn("X" * 32, clean["authorization"])
        self.assertEqual(json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]), args)

    def test_repeated_compactions_preserve_latest_task(self):
        messages = [{"role": "system", "content": "Never execute external actions."}]
        engine = Compactor(Budget(1200, 0, 0, 0))
        for i in range(60):
            messages.extend(tool_turn(i, 30))
            result = engine.compact(messages)
            self.assertEqual(result.messages[-4:], messages[-4:])
            self.assertLessEqual(estimate_tokens(result.messages), 1200)
            messages = result.messages


if __name__ == "__main__":
    unittest.main()
