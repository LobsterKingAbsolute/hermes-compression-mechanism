"""Isolated loader tests. Real upstream ABC verification runs separately in CI."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from abc import ABC, abstractmethod
from pathlib import Path
from unittest.mock import patch

from hermes_context import ContextError
from hermes_context.hermes import PERSISTENCE_FIELDS
from hermes_context.installation import create_engine, doctor, install_plugin, read_options


class ContractStub(ABC):
    @property
    @abstractmethod
    def name(self):
        pass
    @abstractmethod
    def compress(self, messages, current_tokens=None, focus_topic=None, force=False, memory_context=""):
        pass
    @abstractmethod
    def should_compress(self, prompt_tokens=None):
        pass
    @abstractmethod
    def update_from_response(self, usage):
        pass


def host_modules():
    parent = types.ModuleType("agent")
    parent.__path__ = []
    context = types.ModuleType("agent.context_engine")
    context.ContextEngine = ContractStub
    metadata = types.ModuleType("agent.message_metadata")
    metadata.PERSISTENCE_ONLY_MESSAGE_FIELDS = PERSISTENCE_FIELDS | {"_host_future_metadata"}
    return {"agent": parent, "agent.context_engine": context, "agent.message_metadata": metadata}


class PluginContractTests(unittest.TestCase):
    def test_factory_uses_real_supplied_base_and_metadata_contract(self):
        with patch.dict(sys.modules, host_modules()):
            engine = create_engine({"reserved_output": 256})
            self.assertIsInstance(engine, ContractStub)
            self.assertEqual(engine.reserved_output, 256)
            self.assertIn("_host_future_metadata", engine.metadata_fields)
            clone = engine.clone_for_agent()
            self.assertIsInstance(clone, ContractStub)
            self.assertIsNot(clone._lock, engine._lock)
            self.assertEqual(doctor(check_hermes=True)["hermes_contract"], "compatible")

    def test_installed_entry_registers_exactly_one_engine(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, host_modules()):
            destination = Path(root) / "hermes_context"
            install_plugin(destination, apply=True, options={"reserved_output": 512})
            spec = importlib.util.spec_from_file_location("test_plugin", destination / "__init__.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            engines = []
            ctx = types.SimpleNamespace(register_context_engine=engines.append)
            module.register(ctx)
            self.assertEqual(len(engines), 1)
            self.assertIsInstance(engines[0], ContractStub)
            self.assertEqual(engines[0].reserved_output, 512)

    def test_options_read_errors_are_content_free(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "options.json"
            for text in ('PRIVATE-invalid', '{"secret":"PRIVATE"}', '{"threshold_percent":NaN}',
                         '{"reserved_output":1,"reserved_output":2}', '"PRIVATE"', 'x' * 17000):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ContextError) as error:
                    read_options(path)
                self.assertNotIn("PRIVATE", str(error.exception))
            path.unlink()
            with self.assertRaises(ContextError):
                read_options(path)

    def test_missing_host_is_reported_without_paths(self):
        with patch.dict(sys.modules, {"agent": None, "agent.context_engine": None}):
            report = doctor(check_hermes=True)
            self.assertEqual(report["hermes_contract"], "unavailable_or_incompatible")
            self.assertNotIn("path", report)


if __name__ == "__main__":
    unittest.main()
