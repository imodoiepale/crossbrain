"""
End-to-end tests of the command-line entry points, run as real subprocesses.

Unit tests call functions directly, so a crash in an entry point (a missing import used only by main())
passed the whole suite once and was caught only by an end-to-end run. These run `crossbrain.py` the way a
user or an agent does. graphify rebuilds are disabled (--no-graph) so no third-party tool is needed.

    python -m unittest scripts/test_cli.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
CLI = str(ENGINE / "crossbrain.py")
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.repo = base / "app"
        cls.repo.mkdir()
        # an isolated crossbrain home, so the tests never read this machine's real config
        cls.env = {**os.environ, **IDENTITY, "CROSSBRAIN_HOME": str(base / "cbhome"), "PYTHONIOENCODING": "utf-8"}
        for args in (["init", "-q", "-b", "main"],):
            subprocess.run(["git", "-C", str(cls.repo), *args], check=True, capture_output=True, env=cls.env)
        (cls.repo / "app.py").write_text("def handler(event):\n    return event\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(cls.repo), "add", "-A"], check=True, capture_output=True, env=cls.env)
        subprocess.run(["git", "-C", str(cls.repo), "commit", "-qm", "init"], check=True, capture_output=True, env=cls.env)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, CLI, *args], cwd=str(cwd or self.repo), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=self.env, timeout=300)

    def test_intake_scan_runs_and_writes_a_clean_report_to_stdout(self):
        r = self.cli("intake-scan", ".", "--no-graph", "--no-history")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## app", r.stdout)
        self.assertIn("code graph: missing", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_graph_status_runs(self):
        r = self.cli("graph", "status", ".")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"missing\s+app")

    def test_help_and_doctor_run(self):
        self.assertEqual(self.cli("--help").returncode, 0)
        d = self.cli("doctor")
        self.assertEqual(d.returncode, 0, d.stderr)
        self.assertIn("bundled tools", d.stdout)

    def test_unknown_command_is_an_error_not_a_crash(self):
        r = self.cli("no-such-command")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
