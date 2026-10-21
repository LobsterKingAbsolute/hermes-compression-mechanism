import copy
import importlib.util
import inspect
import json
import threading
import unittest
from unittest.mock import patch

from hermes_context import ContextError
from test_core import conversation, tool_turn


def adapter(**kwargs):
    spec = importlib.util.find_spec("hermes_context.hermes")
    if spec is None:
        raise AssertionError("The Hermes context-engine adapter has not been implemented")
    from hermes_context.hermes import HermesContextAdapter
    return HermesContextAdapter(**kwargs)


def history():
    messages = [{"role": "system", "content": "Synthetic instructions"}]
    for _ in range(20):
        messages.extend(tool_turn(0, 60))  # Identical text/IDs but DIFFERENT durable message identities.
    for i, message in enumerate(messages):
        message["message_uid"] = f"{i:032x}"
        message["_row_id"] = i
        message["timestamp"] = i
        message["display_metadata"] = {"local": "never sent to a summarizer"}
    return messages


class AdapterTests(unittest.TestCase):
    def test_current_signature_and_unconfigured_passthrough(self):
        engine = adapter()
        params = inspect.signature(engine.compress).parameters
        for name in ("messages", "current_tokens", "focus_topic", "force", "memory_context"):
            self.assertIn(name, params)
        messages = conversation(12)
        self.assertEqual(engine.compress(messages), messages)
        self.assertEqual(engine.get_status()["last_outcome"], "unconfigured")

    def test_preserves_exact_metadata_and_input(self):
        engine = adapter(context_length=4096)
        messages = history()
        original = copy.deepcopy(messages)
        result = engine.compress(messages)
        self.assertLess(len(result), len(messages))
        self.assertEqual(result[:5], messages[:5])
        self.assertEqual(result[-8:], messages[-8:])
        self.assertEqual(messages, original)
        self.assertEqual(engine.compression_count, 1)
        self.assertEqual(engine.get_status()["last_outcome"], "compressed")
        self.assertNotIn("local", json.dumps(engine.get_status()))
        self.assertNotIn("Synthetic", json.dumps(engine.get_status()))
        self.assertTrue(any(m.get("_compressed_summary") for m in result))

    def test_safe_passthrough_unknown_reasoning_media_and_restrictions(self):
        for addition in ({"reasoning_opaque": "PRIVATE"}, {"_unknown": "PRIVATE"},
                         {"content": [{"type": "image_url", "image_url": {"url": "PRIVATE"}}]},
                         {"data_use": ["no_training"]},
                         {"display_metadata": {"data_use": ["no_training"]}}):
            engine = adapter(context_length=4096)
            messages = history()
            messages[10].update(addition)
            with self.subTest(addition=next(iter(addition))):
                self.assertEqual(engine.compress(messages), messages)
                self.assertEqual(engine.get_status()["last_outcome"], "unsupported_input")
                self.assertNotIn("PRIVATE", str(engine.get_status()))

    def test_memory_context_is_not_silently_ignored(self):
        engine = adapter(context_length=4096)
        messages = history()
        self.assertEqual(engine.compress(messages, memory_context="provider memory"), messages)
        self.assertEqual(engine.get_status()["last_outcome"], "unsupported_memory_context")

    def test_usage_model_switch_and_clone_isolation(self):
        engine = adapter(context_length=10000, threshold_percent=0.75)
        engine.update_from_response({"input_tokens": 8000, "output_tokens": 100})
        self.assertTrue(engine.should_compress())
        self.assertEqual(engine.last_total_tokens, 8100)
        child = engine.clone_for_agent()
        self.assertEqual(type(child), type(engine))
        self.assertIsNot(child._lock, engine._lock)
        self.assertEqual(child.last_prompt_tokens, 0)
        child.update_model("synthetic-small", 4096, api_key="PRIVATE-SHOULD-NOT-BE-STORED")
        self.assertEqual(engine.context_length, 10000)
        self.assertEqual(child.context_length, 4096)
        self.assertNotIn("PRIVATE", str(vars(child)))
        engine.update_model("synthetic-small", 4096)
        self.assertEqual(engine.last_prompt_tokens, 0)
        self.assertEqual(engine.compression_count, 0)

    def test_reset_clears_usage_and_status(self):
        engine = adapter(context_length=4096)
        engine.compress(history())
        engine.on_session_reset()
        self.assertEqual(engine.compression_count, 0)
        self.assertEqual(engine.get_status()["last_outcome"], "idle")

    def test_usage_legacy_and_sentinel(self):
        engine = adapter(context_length=4096)
        engine.update_from_response({"prompt_tokens": 4000, "completion_tokens": 10, "total_tokens": 4010})
        self.assertEqual(engine.last_prompt_tokens, 4000)
        self.assertTrue(engine.should_compress())
        engine.last_prompt_tokens = -1
        self.assertFalse(engine.should_compress())
        self.assertEqual(engine.get_status()["usage_percent"], 0)
        for usage in ({"prompt_tokens": True}, {"prompt_tokens": -3}, {"prompt_tokens": "private"}):
            with self.assertRaises(ContextError):
                engine.update_from_response(usage)

    def test_protected_overflow_preserves_input_and_blocks_retries(self):
        engine = adapter(context_length=2048)
        messages = [{"role": "user", "content": "synthetic " * 2000}]
        self.assertEqual(engine.compress(messages), messages)
        self.assertEqual(engine.get_status()["last_outcome"], "protected_overflow")
        self.assertFalse(engine.should_compress_preflight(messages))
        self.assertEqual(engine.compress(messages), messages)
        self.assertEqual(engine.get_status()["last_outcome"], "unchanged_context")
        self.assertEqual(engine.compress(messages, force=True), messages)
        self.assertEqual(engine.get_status()["last_outcome"], "protected_overflow")

    def test_stale_pass_does_not_commit_after_reset(self):
        engine = adapter(context_length=4096)
        messages = history()
        from hermes_context import Compactor
        real = Compactor.compact
        entered, release = threading.Event(), threading.Event()
        def slow(compactor, msgs, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test synchronization failed")
            return real(compactor, msgs, **kwargs)
        result = []
        with patch.object(Compactor, "compact", slow):
            worker = threading.Thread(target=lambda: result.append(engine.compress(messages)))
            worker.start()
            self.assertTrue(entered.wait(5))
            engine.on_session_reset()
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [messages])
        self.assertEqual(engine.compression_count, 0)
        self.assertEqual(engine.get_status()["last_outcome"], "idle")

    def test_metadata_not_counted_as_model_content(self):
        engine = adapter(context_length=4096)
        messages = conversation(2, 20)
        for m in messages:
            m["display_metadata"] = {"render": "x" * 10000}
        self.assertFalse(engine.should_compress_preflight(messages))
        self.assertEqual(engine.compress(messages), messages)

    def test_manual_focus_is_explicitly_reported(self):
        engine = adapter(context_length=4096)
        engine.compress(history(), focus_topic="historical task")
        self.assertFalse(engine.get_status()["focus_supported"])

    def test_preflight_respects_output_reservation_before_threshold(self):
        from hermes_context.core import estimate_tokens
        engine = adapter(context_length=4096, reserved_output=2500)
        messages = conversation(10, 200)
        self.assertLess(estimate_tokens(messages), engine.threshold_tokens)
        self.assertGreater(estimate_tokens(messages), 4096 - 2500 - 128)
        self.assertTrue(engine.should_compress_preflight(messages))
        self.assertTrue(engine.should_compress(estimate_tokens(messages)))

    def test_invalid_threshold_metadata_usage_and_small_budget(self):
        for kwargs in ({"threshold_percent": True}, {"threshold_percent": float("nan")},
                       {"threshold_percent": 0}, {"metadata_fields": frozenset({"content"})}):
            with self.assertRaises(ContextError):
                adapter(**kwargs)
        engine = adapter(context_length=10)
        self.assertEqual(engine.compress(conversation(2)), conversation(2))
        self.assertEqual(engine.get_status()["last_outcome"], "invalid_budget")
        with self.assertRaises(ContextError):
            engine.update_from_response(None)

    def test_lifecycle_and_availability_hooks(self):
        engine = adapter(context_length=4096)
        self.assertTrue(engine.has_content_to_compress(history()))
        self.assertFalse(engine.has_content_to_compress(conversation(2)))
        self.assertFalse(engine.has_content_to_compress([None]))
        self.assertFalse(engine.should_defer_preflight_to_real_usage(10000))
        engine.update_from_response({"prompt_tokens": 4000})
        self.assertEqual(engine.should_compress_info(), (True, None))
        engine.on_session_start("private-session-name")
        self.assertEqual(engine.last_prompt_tokens, 0)
        engine.on_session_end("private-session-name", [])
        self.assertNotIn("private-session-name", str(vars(engine)))

    def test_concurrent_pass_is_not_started_twice(self):
        engine = adapter(context_length=4096)
        from hermes_context import Compactor
        real = Compactor.compact
        entered, release = threading.Event(), threading.Event()
        def slow(compactor, messages, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("synchronization failed")
            return real(compactor, messages, **kwargs)
        messages = history()
        with patch.object(Compactor, "compact", slow):
            worker = threading.Thread(target=lambda: engine.compress(messages))
            worker.start()
            self.assertTrue(entered.wait(5))
            self.assertEqual(engine.compress(messages), messages)
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(engine.compression_count, 1)


if __name__ == "__main__":
    unittest.main()
