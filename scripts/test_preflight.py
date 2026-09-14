"""
Regression tests for the secret patterns and the commit gate.

A gate is only worth having if it catches real leaks AND stays quiet on real non-leaks; a gate that
cries wolf gets bypassed with --no-verify and then protects nothing. Both halves are tested.
All key material is FAKE. This file is exempt from the gate's own scan (preflight.FIXTURE_FILES).

    python -m unittest scripts/test_preflight.py -v
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory_redact_shim as shim  # noqa: E402
import preflight  # noqa: E402

PATTERNS = dict(shim.load_patterns())

MUST_CATCH = [
    ("supabase-mgmt", "sbp_a86bFAKEFAKEFAKEFAKEFAKEfake123"),
    ("runpod", "rpa_FAKEFAKEFAKEFAKEFAKEFAKE0123456"),
    ("google-api", 'const k = "AIzaSyCduWFAKEFAKEFAKEFAKEFAKEFAKE01234"'),
    ("openai-like", "sk-fish-FAKEFAKEFAKEFAKEFAKEfake0123"),
    ("openai-like", "sk-FAKEFAKEFAKEFAKEFAKEfake01234567"),
    ("github-token", "gho_FAKEFAKEFAKEFAKEFAKEFAKEFAKEfake12"),
    ("jwt", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIn0"),
    ("aws-akid", "AKIAFAKEFAKEFAKE1234"),
    ("private-key", "-----BEGIN RSA PRIVATE KEY-----"),
    ("supabase-svc", 'SUPABASE_SERVICE_ROLE_KEY="FAKEFAKEFAKEFAKEFAKEfake"'),
]

# Real-world strings that naive patterns flag. The first one broke the original gate:
# "task-manager" contains "sk-".
MUST_IGNORE = [
    'const REMEMBERED_LOGIN_KEY = "task-manager-login-identifier";',
    'import { task } from "./task-manager-utils";',
    'const id = "disk-management-service";',
    "sk-short",
    "https://abcdefexample.supabase.co",
    "NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co",
    "process.env.SUPABASE_SERVICE_ROLE_KEY",
    "# see docs: AIza keys are rotated quarterly",
    'const brand = "#ffd000";',
    "SUPABASE_SERVICE_ROLE_KEY=",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY=",
]

# Assembled at runtime and free of placeholder words, so the gate treats it as live.
LIVE_LOOKING = "sbp_" + "a86b" + "Q7m2" * 6


class PatternTest(unittest.TestCase):
    def test_every_pattern_catches_its_fixture(self):
        for pid, text in MUST_CATCH:
            with self.subTest(pid):
                self.assertIn(pid, PATTERNS)
                self.assertRegex(text, PATTERNS[pid])

    def test_real_non_secrets_stay_quiet(self):
        for text in MUST_IGNORE:
            with self.subTest(text):
                self.assertEqual([pid for pid, rx in PATTERNS.items() if rx.search(text)], [])


def repo_with(files: dict, branch: str = "feature/x", stage: bool = True) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    r = Path(tmp.name)
    for args in (["init", "-q", "-b", branch], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(r), *args], check=True, capture_output=True)
    (r / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    for name, body in files.items():
        (r / name).parent.mkdir(parents=True, exist_ok=True)
        (r / name).write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
    if stage:
        subprocess.run(["git", "-C", str(r), "add", "-A"], check=True, capture_output=True)
    return tmp


class GateTest(unittest.TestCase):
    def run_gate(self, files, **kw):
        tmp = repo_with(files, **{k: kw.pop(k) for k in ("branch",) if k in kw})
        self.addCleanup(tmp.cleanup)
        return preflight.check(Path(tmp.name), staged=True, **kw)

    def test_clean_change_passes(self):
        self.assertEqual(self.run_gate({"app.ts": "export const x = 1;\n"})[0], [])

    def test_live_looking_secret_blocks_and_is_redacted(self):
        fails, _ = self.run_gate({"lib/client.ts": f'const token = "{LIVE_LOOKING}";\n'})
        self.assertTrue(any("[supabase-mgmt]" in f and "lib/client.ts:1" in f for f in fails))
        self.assertFalse(any(LIVE_LOOKING in f for f in fails), "the report must never print the secret")

    def test_placeholder_values_do_not_block(self):
        self.assertEqual(self.run_gate({"README.md": "token: sbp_FAKEFAKEFAKEFAKEFAKEFAKEFAKE00\n"})[0], [])

    def test_env_file_blocks_example_does_not(self):
        fails, _ = self.run_gate({".env": "A=1\n", ".env.example": "A=\n"})
        self.assertTrue(any(".env is a .env file" in f for f in fails))
        self.assertFalse(any(".env.example" in f for f in fails))

    def test_large_file_blocks(self):
        fails, _ = self.run_gate({"dump.bin": b"\0" * 5_100_000})
        self.assertTrue(any("[size] dump.bin" in f for f in fails))

    def test_protected_branch_blocks_unless_allowed(self):
        fails, _ = self.run_gate({"a.txt": "x\n"}, branch="main")
        self.assertTrue(any("[branch]" in f for f in fails))
        fails, _ = self.run_gate({"a.txt": "x\n"}, branch="main", allow_protected=True)
        self.assertEqual(fails, [])


if __name__ == "__main__":
    unittest.main()
