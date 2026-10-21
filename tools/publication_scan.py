"""Offline tracked-file hygiene scan; complementary to Gitleaks, not full DLP."""
from pathlib import Path
import subprocess
import sys

from hermes_context.privacy import SECRET_PATTERNS

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {"auth.json", "config.yaml", "state.db", "kanban.db"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx"}
FORBIDDEN_DIRS = {".hermes-context", "context-exports", "logs", "runs", "node_modules", ".venv"}


def main() -> int:
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    paths = [Path(name.decode("utf-8")) for name in tracked.split(b"\0") if name]
    if not paths:
        print("publication scan: no tracked files; refusing an empty audit", file=sys.stderr)
        return 2
    findings = []
    checked = 0
    for relative in paths:
        path = ROOT / relative
        if (relative.name.startswith(".env") or relative.name in FORBIDDEN_NAMES
                or relative.suffix in FORBIDDEN_SUFFIXES or FORBIDDEN_DIRS.intersection(relative.parts)):
            findings.append((relative.as_posix(), "forbidden runtime/credential file"))
            continue
        if path.is_symlink():
            findings.append((relative.as_posix(), "symlink requires manual review"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append((relative.as_posix(), "unreadable/non-text tracked file"))
            continue
        checked += 1
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            findings.append((relative.as_posix(), "credential-shaped content; values suppressed"))
    for path, reason in findings:
        print(f"{path}: {reason}", file=sys.stderr)
    print(f"publication scan: {checked} text files checked; {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
