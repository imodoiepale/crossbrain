"""
Tests for the graph-first nudge, graph auto-update after edits, per-repo instructions, and hook registration.
Real throwaway git repos; graphify is never run and no process is spawned.

    python -m unittest scripts/test_hooks.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import claude_hooks  # noqa: E402
import components  # noqa: E402
import graph_autoupdate as au  # noqa: E402
import graph_guard as gg  # noqa: E402
import hconfig as hc  # noqa: E402

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **IDENTITY}).stdout.strip()


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "app"
        (self.repo / "src").mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        state = mock.patch.object(hc, "state_dir", lambda: (base / "state").mkdir(exist_ok=True) or base / "state")
        state.start()
        self.addCleanup(state.stop)

    def with_graph(self):
        (self.repo / "graphify-out").mkdir(exist_ok=True)
        (self.repo / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")


class GraphGuardTest(RepoCase):
    def event(self, tool, session="s1", **tin):
        return {"tool_name": tool, "tool_input": tin, "cwd": str(self.repo), "session_id": session}

    def test_no_graph_no_nudge(self):
        self.assertIsNone(gg.decide(self.event("Read", file_path=str(self.repo / "src" / "a.py"))))

    def test_nudges_once_per_session_then_stays_quiet(self):
        self.with_graph()
        first = gg.decide(self.event("Read", file_path=str(self.repo / "src" / "a.py")))
        self.assertIn("graphify query", first)
        self.assertIsNone(gg.decide(self.event("Grep", pattern="x")))
        self.assertIsNotNone(gg.decide(self.event("Glob", session="s2", pattern="*.py")), "a new session is nudged again")

    def test_agent_already_querying_the_graph_is_not_nudged(self):
        self.with_graph()
        self.assertIsNone(gg.decide(self.event("Bash", command='python -m graphify query "where is x"')))
        self.assertIsNone(gg.decide(self.event("Read", file_path=str(self.repo / "src" / "a.py"))))

    def test_non_search_bash_is_ignored(self):
        self.with_graph()
        self.assertIsNone(gg.decide(self.event("Bash", command="npm test")))
        self.assertIsNotNone(gg.decide(self.event("Bash", command="rg handler src")))


class AutoUpdateTest(RepoCase):
    def edit(self, rel="src/a.py"):
        return {"tool_name": "Edit", "tool_input": {"file_path": str(self.repo / rel)}, "cwd": str(self.repo)}

    def test_skips_repo_without_a_graph(self):
        self.assertEqual(au.plan(self.edit())[0], "skip:no graph yet")

    def test_spawns_then_debounces_into_a_pending_pass(self):
        self.with_graph()
        self.assertEqual(au.plan(self.edit())[0], "spawn")
        (self.repo / "graphify-out" / au.LOCK).write_text("1", encoding="utf-8")        # a worker is running
        self.assertEqual(au.plan(self.edit())[0], "pending")
        self.assertTrue((self.repo / "graphify-out" / au.PENDING).exists())

    def test_min_interval_between_rebuilds(self):
        self.with_graph()
        (self.repo / "graphify-out" / ".crossbrain-update.last").write_text("x", encoding="utf-8")
        self.assertEqual(au.plan(self.edit())[0], "pending")
        self.assertEqual(au.plan(self.edit(), now=time.time() + au.MIN_INTERVAL + 5)[0], "spawn")

    def test_crashed_worker_lock_expires(self):
        self.with_graph()
        lock = self.repo / "graphify-out" / au.LOCK
        lock.write_text("1", encoding="utf-8")
        old = time.time() - au.STALE_LOCK - 10
        os.utime(lock, (old, old))
        self.assertEqual(au.plan(self.edit())[0], "spawn")

    def test_never_in_a_repo_that_commits_its_graph_or_for_graph_output_edits(self):
        self.with_graph()
        self.assertEqual(au.plan(self.edit("graphify-out/graph.json"))[0], "skip:graph output edited")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "commit graph")
        self.assertEqual(au.plan(self.edit())[0], "skip:repo commits its graph")

    def test_worker_runs_one_extra_pass_for_edits_during_a_run_and_releases_the_lock(self):
        self.with_graph()
        out = self.repo / "graphify-out"
        calls = []

        def runner(args, cwd):
            calls.append(args)
            if len(calls) == 1:
                (out / au.PENDING).write_text("edit during run", encoding="utf-8")

        (out / au.LOCK).write_text("1", encoding="utf-8")
        self.assertEqual(au.worker(self.repo, runner=runner), 2)
        self.assertFalse((out / au.LOCK).exists())


class InstructRepoTest(RepoCase):
    def fake_graphify(self, args, cwd):
        platform, action = args[-2], args[-1]
        cwd = Path(cwd)
        doc, hook_files = components.INSTRUCTION_PLATFORMS[platform]
        if action == "install":
            (cwd / doc).write_text("## graphify\n\nRules: query first.\n", encoding="utf-8")
            for rel in hook_files:
                (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
                (cwd / rel).write_text('{"hooks": {"PreToolUse": [{"command": "C:/abs/graphify.EXE hook-guard read"}]}}',
                                       encoding="utf-8")
        return CompletedProcess(args, 0, "", "")

    def test_writes_sections_and_removes_machine_specific_hook_configs(self):
        with mock.patch.object(components, "graphify_available", return_value=True):
            res = components.instruct_repo(self.repo, runner=self.fake_graphify)
        self.assertEqual(res, "CLAUDE.md ok, AGENTS.md ok")
        self.assertIn("## graphify", (self.repo / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertFalse((self.repo / ".claude").exists(), "the abs-path hook config must not be left for commit")
        self.assertFalse((self.repo / ".codex").exists())

    def test_an_existing_project_settings_file_is_restored_byte_for_byte(self):
        (self.repo / ".claude").mkdir()
        original = b'{"permissions": {"allow": ["Bash(npm test)"]}}\n'
        (self.repo / ".claude" / "settings.json").write_bytes(original)
        with mock.patch.object(components, "graphify_available", return_value=True):
            components.instruct_repo(self.repo, runner=self.fake_graphify)
        self.assertEqual((self.repo / ".claude" / "settings.json").read_bytes(), original)


class ClaudeHooksTest(unittest.TestCase):
    def test_registers_all_three_idempotently_and_keeps_foreign_hooks(self):
        data = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]}}
        cfg = {"components": ["graphify"]}
        changes = claude_hooks.apply(data, cfg)
        self.assertEqual(len(changes), 3)
        self.assertEqual(claude_hooks.apply(data, cfg), [], "second run changes nothing")
        pre = data["hooks"]["PreToolUse"]
        self.assertTrue(any("rtk hook claude" in h["command"] for g in pre for h in g["hooks"]))
        self.assertTrue(any(g.get("matcher") == "Read|Glob|Grep|Bash" for g in pre))
        self.assertIn("PostToolUse", data["hooks"])

    def test_graph_hooks_removed_when_graphify_component_disabled(self):
        data = {}
        claude_hooks.apply(data, {"components": ["graphify"]})
        claude_hooks.apply(data, {"components": []})
        self.assertNotIn("PostToolUse", data["hooks"])
        self.assertFalse(any("graph_guard.py" in h["command"] for g in data["hooks"].get("PreToolUse", []) for h in g["hooks"]))
        self.assertIn("SessionStart", data["hooks"])

    def test_uninstall_removes_only_ours(self):
        data = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]}}
        claude_hooks.apply(data, {"components": ["graphify"]})
        claude_hooks.apply(data, {"components": ["graphify"]}, uninstall=True)
        self.assertEqual(json.dumps(data["hooks"]["PreToolUse"]), json.dumps(
            [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]))


if __name__ == "__main__":
    unittest.main()
