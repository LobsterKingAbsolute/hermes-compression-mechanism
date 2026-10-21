import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hermes_context import ContextError
from hermes_context.cli import main, _load


def installation():
    if importlib.util.find_spec("hermes_context.installation") is None:
        raise AssertionError("Explicit plugin installer has not been implemented")
    from hermes_context import installation as module
    return module


class InstallationTests(unittest.TestCase):
    def test_dry_run_does_not_write(self):
        module = installation()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "plugins" / "hermes_context"
            report = module.install_plugin(target)
            self.assertFalse(target.parent.exists())
            self.assertFalse(report["installed"])
            self.assertEqual(report["files"], 3)

    def test_install_is_explicit_exclusive_and_config_untouched(self):
        module = installation()
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "config.yaml"
            config.write_text("context:\n  engine: compressor\n", encoding="utf-8")
            target = Path(root) / "plugins" / "hermes_context"
            report = module.install_plugin(target, apply=True, options={"reserved_output": 512})
            self.assertTrue(report["installed"])
            self.assertEqual(set(p.name for p in target.iterdir()), {"__init__.py", "plugin.yaml", "options.json"})
            self.assertIn("ContextEngine", (target / "__init__.py").read_text())
            self.assertEqual(json.loads((target / "options.json").read_text())["reserved_output"], 512)
            self.assertEqual(config.read_text(), "context:\n  engine: compressor\n")
            original = (target / "options.json").read_bytes()
            with self.assertRaises(ContextError):
                module.install_plugin(target, apply=True)
            self.assertEqual((target / "options.json").read_bytes(), original)

    def test_invalid_options_and_directory_name(self):
        module = installation()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "hermes_context"
            for options in ({"api_key": "PRIVATE"}, {"threshold_percent": float("nan")},
                            {"keep_last_turns": 0}, {"metadata_fields": []}):
                with self.assertRaises(ContextError):
                    module.install_plugin(target, apply=True, options=options)
            self.assertFalse(target.exists())
            with self.assertRaises(ContextError):
                module.install_plugin(Path(root) / "wrong_name", apply=True)

    @unittest.skipUnless(os.name == "posix", "symlink safety on POSIX")
    def test_symlink_parent_refused(self):
        module = installation()
        with tempfile.TemporaryDirectory() as root:
            real = Path(root) / "real"
            real.mkdir()
            link = Path(root) / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ContextError):
                module.install_plugin(link / "hermes_context", apply=True)
            self.assertEqual(list(real.iterdir()), [])

    def test_partial_failure_removes_only_created_files(self):
        module = installation()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "hermes_context"
            with patch.object(module, "_write_new", side_effect=OSError("PRIVATE")):
                with self.assertRaises(ContextError) as error:
                    module.install_plugin(target, apply=True)
            self.assertNotIn("PRIVATE", str(error.exception))
            self.assertFalse(target.exists())

    def test_doctor_offline(self):
        module = installation()
        report = module.doctor()
        self.assertEqual(report["self_test"], "passed")
        self.assertEqual(report["hermes_contract"], "not_checked")
        self.assertNotIn("path", report)

    def test_duplicate_json_keys_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "input.json"
            path.write_text('[{"role":"system","role":"user","content":"PRIVATE"}]')
            with self.assertRaises(ContextError):
                _load(path)

    def test_cli_doctor_and_install_preview(self):
        installation()  # Clear missing-feature failure before argparse is exercised.
        for args in (["doctor"], ["install-hermes", "--destination", "./synthetic/hermes_context"]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(args)
            self.assertEqual(code, 0, err.getvalue())
            json.loads(out.getvalue())


if __name__ == "__main__":
    unittest.main()
