import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from hermes_context import Budget, Compactor, ContextError, redact_messages, redact_text


class PrivacyTests(unittest.TestCase):
    def test_known_patterns(self):
        values = [
            "sk-" + "a" * 40,
            "ghp_" + "z" * 36,
            "github_pat_" + "x" * 40,
            "AKIA" + "A" * 16,
            "Bearer " + "a" * 32,
            "password=" + "synthetic-value",
            "https://user:synthetic-value@example.invalid/path",
            "https://example.invalid/?token=synthetic-value",
            "https://example.invalid/?X-Amz-Signature=synthetic-value",
            "person" + "@" + "example.invalid",
        ]
        for text in values:
            with self.subTest(kind=text[:5]):
                self.assertNotEqual(redact_text(text), text)
                self.assertIn("[REDACTED]", redact_text(text))

    def test_idempotent(self):
        text = 'api_key="synthetic-value" password=synthetic-value'
        once = redact_text(text)
        self.assertEqual(redact_text(once), once)

    def test_private_key(self):
        text = "-----BEGIN " + "PRIVATE KEY-----\nsynthetic\n-----END " + "PRIVATE KEY-----"
        self.assertEqual(redact_text(text), "[REDACTED]")

    def test_safe_text(self):
        text = "Keep SQLite and run tests. No networking."
        self.assertEqual(redact_text(text), text)

    def test_copy(self):
        messages = [{"role": "user", "content": "password=synthetic-value"}]
        clean = redact_messages(messages)
        self.assertNotEqual(clean, messages)
        self.assertEqual(messages[0]["content"], "password=synthetic-value")

    def test_falsey_callbacks_rejected(self):
        for value in (False, 0, [], ""):
            for key in ("counter", "summarizer"):
                with self.subTest(key=key), self.assertRaises(ContextError):
                    Compactor(Budget(1000, 0, 0, 0), **{key: value})


class CliTests(unittest.TestCase):
    def call(self, args):
        from hermes_context.cli import main
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_demo(self):
        code, out, err = self.call(["demo"])
        self.assertEqual((code, err), (0, ""))
        report = json.loads(out)
        self.assertGreater(report["before"], report["after"])
        self.assertNotIn("messages", report)

    def test_safe_output_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "input.json", Path(directory) / "output.json"
            key = "sk-" + "b" * 40
            source.write_text(json.dumps([{"role": "user", "content": "PRIVATE-PAYLOAD " + key}]), encoding="utf-8")
            args = ["compact", str(source), "--context-window", "4096", "--output", str(target)]
            code, out, err = self.call(args)
            self.assertEqual((code, err), (0, ""))
            self.assertNotIn("PRIVATE-PAYLOAD", out)
            exported = target.read_text(encoding="utf-8")
            self.assertNotIn(key, exported)
            self.assertIn("[REDACTED]", exported)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            code, out, err = self.call(args)
            self.assertEqual(code, 2)
            self.assertIn("exists", err)
            self.assertEqual(target.read_text(encoding="utf-8"), exported)
            code, _, err = self.call(["compact", str(target), "--context-window", "4096"])
            self.assertEqual((code, err), (0, ""))

    def test_error_does_not_echo_content(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            for content in ["PRIVATE-INVALID-JSON", '[{"role":"PRIVATE-ROLE","content":"x"}]']:
                source.write_text(content, encoding="utf-8")
                code, out, err = self.call(["compact", str(source)])
                self.assertEqual(code, 2)
                self.assertNotIn("PRIVATE", out + err)

    def test_missing_input(self):
        code, out, err = self.call(["compact", "/nonexistent/synthetic.json"])
        self.assertEqual(code, 2)
        self.assertNotIn("/nonexistent", out + err)

    def test_reject_envelope_version(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            for version in [True, 2, "1"]:
                source.write_text(json.dumps({"schema_version": version, "messages": []}), encoding="utf-8")
                code, _, _ = self.call(["compact", str(source)])
                self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
