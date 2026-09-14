"""
Tests for the bundled tools: archify as a vendored skill root, graphify driven through its own installer.
No network and no real graphify: subprocess calls are captured.

    python -m unittest scripts/test_components.py -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import components  # noqa: E402
import hconfig as hc  # noqa: E402
import install as inst  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Recorder:
    def __init__(self, fail_first: set[str] = frozenset()):
        self.calls: list[list[str]] = []
        self.fail_first = set(fail_first)

    def __call__(self, args):
        self.calls.append(list(args))
        platform = args[-1]
        if platform in self.fail_first:
            self.fail_first.discard(platform)
            return CompletedProcess(args, 1, "", "WinError 5")
        return CompletedProcess(args, 0, "", "")


class GraphifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        patch = mock.patch.object(hc, "expand", lambda p: Path(str(p).replace("~", str(self.home), 1)))
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.cfg = {"skill_targets": ["claude", "agents"], "components": ["archify", "graphify"]}

    def test_installs_only_for_agent_clis_present_plus_shared_agents_folder(self):
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir()
        rec = Recorder()
        with mock.patch.object(components, "graphify_available", return_value=True), \
                mock.patch.object(components, "graphify_version", return_value="0.9.30"):
            report = components.install_graphify(self.cfg, log=lambda m: None, runner=rec)
        self.assertEqual(sorted(report["platforms"]), ["agents", "claude", "codex"])
        self.assertTrue(all(c[1:4] == ["-m", "graphify", "install"] for c in rec.calls))

    def test_failed_platform_is_retried_once_then_reported_not_raised(self):
        (self.home / ".claude").mkdir()
        rec = Recorder(fail_first={"claude"})
        with mock.patch.object(components, "graphify_available", return_value=True), \
                mock.patch.object(components, "graphify_version", return_value="0.9.30"):
            report = components.install_graphify({"skill_targets": ["claude"]}, log=lambda m: None, runner=rec)
        self.assertEqual(report["platforms"], {"claude": "ok"})
        self.assertEqual(len(rec.calls), 2)

    def test_missing_package_prints_command_and_never_pip_installs_by_default(self):
        rec, lines = Recorder(), []
        with mock.patch.object(components, "graphify_available", return_value=False):
            report = components.install_graphify(self.cfg, log=lines.append, runner=rec)
        self.assertFalse(report["available"])
        self.assertEqual(rec.calls, [], "no pip install and no graphify call without --with-graphify")
        self.assertTrue(any("pip install graphifyy" in l for l in lines))

    def test_with_graphify_runs_pip_first(self):
        (self.home / ".claude").mkdir()
        rec = Recorder()
        with mock.patch.object(components, "graphify_available", side_effect=[False, True]), \
                mock.patch.object(components, "graphify_version", return_value="0.9.30"):
            report = components.install_graphify({"skill_targets": ["claude"]}, log=lambda m: None, allow_pip=True, runner=rec)
        self.assertEqual(rec.calls[0][1:5], ["-m", "pip", "install", "--upgrade"])
        self.assertEqual(report["platforms"], {"claude": "ok"})


class ArchifyTest(unittest.TestCase):
    def test_vendored_archify_is_a_skill_root_when_enabled(self):
        on = {"packs": [], "components": ["archify"]}
        off = {"packs": [], "components": []}
        self.assertIn(hc.ENGINE / "vendor", hc.skill_roots(on))
        self.assertNotIn(hc.ENGINE / "vendor", hc.skill_roots(off))

    def test_install_collects_archify_but_never_the_ecc_library_wholesale(self):
        if not (ROOT / "vendor" / "archify" / "SKILL.md").exists():
            self.skipTest("archify not vendored in this checkout")
        skills = inst.collect(hc.skill_roots({"packs": [], "components": ["archify"]}), "*")
        self.assertIn("archify", skills)
        self.assertNotIn("ecc", skills)
        self.assertEqual(skills["archify"], ROOT / "vendor" / "archify")

    def test_vendored_archify_is_pinned(self):
        origin = ROOT / "vendor" / "archify" / "ORIGIN.json"
        if not origin.exists():
            self.skipTest("archify not vendored in this checkout")
        import json
        info = json.loads(origin.read_text(encoding="utf-8"))
        self.assertEqual(info["license"], "MIT")
        self.assertRegex(info["commit"], r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
