"""
Tests for code-graph freshness, graph hooks and the session card's graph line. Real throwaway git repos;
graphify itself is never run (its calls are captured).

    python -m unittest scripts/test_graph.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import components  # noqa: E402

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **IDENTITY}).stdout.strip()


def commit(repo: Path, name: str, body: str = "x\n") -> str:
    (repo / name).write_text(body, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"add {name}")
    return git(repo, "rev-parse", "HEAD")


def report(repo: Path, text: str) -> None:
    (repo / "graphify-out").mkdir(exist_ok=True)
    (repo / "graphify-out" / "GRAPH_REPORT.md").write_text(text, encoding="utf-8")


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "app"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.first = commit(self.repo, "a.py")


class GraphStatusTest(RepoCase):
    def test_missing(self):
        self.assertEqual(components.graph_status(self.repo), {"status": "missing"})

    def test_fresh_when_built_from_head(self):
        report(self.repo, f"# Graph Report - app  (2026-09-14)\n\n- Built from commit: `{self.first[:8]}`\n")
        self.assertEqual(components.graph_status(self.repo)["status"], "fresh")

    def test_stale_counts_commits_behind(self):
        report(self.repo, f"# Graph Report - app  (2026-09-14)\n\n- Built from commit: `{self.first[:8]}`\n")
        commit(self.repo, "b.py")
        commit(self.repo, "c.py")
        st = components.graph_status(self.repo)
        self.assertEqual((st["status"], st["behind"]), ("stale", 2))

    def test_old_report_without_commit_falls_back_to_dates(self):
        report(self.repo, "# Graph Report - .  (2001-01-01)\n")
        self.assertEqual(components.graph_status(self.repo)["status"], "stale")

    def test_graph_line_for_each_state(self):
        self.assertIn("graphify query", components.graph_line({"status": "fresh"}, True))
        self.assertIn("2 commit(s) behind", components.graph_line({"status": "stale", "behind": 2}, True))
        self.assertIn("graphify update .", components.graph_line({"status": "missing"}, True))
        self.assertIn("--with-graphify", components.graph_line({"status": "missing"}, False))


class ExcludeAndHooksTest(RepoCase):
    def test_graph_output_hidden_locally_and_idempotently(self):
        self.assertTrue(components.exclude_graph_output(self.repo))
        self.assertFalse(components.exclude_graph_output(self.repo))
        report(self.repo, "# Graph Report\n")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "", "graphify-out/ must not show in git status")

    def test_not_hidden_when_the_repo_commits_its_graph(self):
        report(self.repo, "# Graph Report\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "commit graph")
        self.assertFalse(components.exclude_graph_output(self.repo))

    def fake_graphify(self, attrs_line: str = "graphify-out/graph.json merge=graphify\n"):
        def runner(args, cwd):
            # what `graphify hook install` does to the repo: hooks + a .gitattributes merge-driver line
            (Path(cwd) / ".gitattributes").open("a", encoding="utf-8").write(attrs_line)
            return CompletedProcess(args, 0, "post-commit: installed", "")
        return runner

    def test_hook_install_restores_a_tracked_gitattributes(self):
        commit(self.repo, ".gitattributes", "* text=auto\n")
        with mock.patch.object(components, "graphify_available", return_value=True):
            status = components.install_graph_hooks(self.repo, runner=self.fake_graphify())
        self.assertEqual(status, "graph hooks installed")
        self.assertEqual((self.repo / ".gitattributes").read_text(encoding="utf-8"), "* text=auto\n")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_hook_install_removes_a_gitattributes_it_created(self):
        with mock.patch.object(components, "graphify_available", return_value=True):
            components.install_graph_hooks(self.repo, runner=self.fake_graphify())
        self.assertFalse((self.repo / ".gitattributes").exists())

    def commit_graph(self):
        report(self.repo, "# Graph Report\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "commit graph")

    def test_repo_that_commits_its_graph_is_skipped_by_default(self):
        # The real rollout: 7 repos committed graphify-out/, and graphify's merge-driver edit was left in each.
        self.commit_graph()
        calls = []
        with mock.patch.object(components, "graphify_available", return_value=True):
            status = components.install_graph_hooks(self.repo, runner=lambda a, c: calls.append(a))
        self.assertTrue(status.startswith("graph hooks skipped"), status)
        self.assertEqual(calls, [], "graphify must not even run")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_tracked_graph_opt_in_installs_but_never_leaves_gitattributes_changed(self):
        self.commit_graph()
        with mock.patch.object(components, "graphify_available", return_value=True):
            status = components.install_graph_hooks(self.repo, runner=self.fake_graphify(), allow_tracked=True)
        self.assertIn("graph hooks installed", status)
        self.assertFalse((self.repo / ".gitattributes").exists())
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_without_graphify_nothing_runs(self):
        calls = []
        with mock.patch.object(components, "graphify_available", return_value=False):
            self.assertEqual(components.install_graph_hooks(self.repo, runner=lambda a, c: calls.append(a)),
                             "graphify not installed")
            self.assertFalse(components.update_graph(self.repo, runner=lambda a, c: calls.append(a))["ok"])
        self.assertEqual(calls, [])


class SessionCardTest(RepoCase):
    def run_hook(self, cwd: Path, cfg: dict, brain: dict):
        import brain_hook
        out = []
        with mock.patch.object(brain_hook.hc, "load", return_value=cfg), \
                mock.patch.object(brain_hook.hc, "brain_dir", return_value=Path(self.tmp.name) / "brain"), \
                mock.patch.object(brain_hook.hc, "projects_root", return_value=Path(self.tmp.name)), \
                mock.patch.object(brain_hook, "refresh_capabilities", return_value=[]), \
                mock.patch.object(components, "graphify_available", return_value=True), \
                mock.patch("sys.stdin", mock.Mock(read=lambda: json.dumps({"cwd": str(cwd)}))), \
                mock.patch("builtins.print", lambda s: out.append(s)):
            (Path(self.tmp.name) / "brain").mkdir(exist_ok=True)
            (Path(self.tmp.name) / "brain" / "brain.json").write_text(json.dumps(brain), encoding="utf-8")
            brain_hook.main()
        return json.loads(out[0])["hookSpecificOutput"]["additionalContext"] if out else None

    def test_unmapped_repo_gets_intake_prompt_and_graph_line(self):
        (self.repo / "src").mkdir()
        ctx = self.run_hook(self.repo / "src", {"components": ["graphify"], "packs": []}, {"repos": []})
        self.assertIn("app has no repo skill yet", ctx)
        self.assertIn("Code graph: none yet", ctx)

    def test_mapped_repo_card_reports_stale_graph(self):
        report(self.repo, f"- Built from commit: `{self.first[:8]}`\n")
        commit(self.repo, "b.py")
        brain = {"repos": [{"repo": "app", "skill": "repo-app", "what": "Demo", "exposure": False,
                            "defect_classes": [], "non_negotiables": [], "verify": []}]}
        ctx = self.run_hook(self.repo, {"components": ["graphify"], "packs": []}, brain)
        self.assertIn("Load skill `repo-app`", ctx)
        self.assertIn("STALE - 1 commit(s) behind", ctx)

    def test_no_graph_line_when_graphify_component_disabled(self):
        ctx = self.run_hook(self.repo, {"components": [], "packs": []}, {"repos": []})
        self.assertNotIn("Code graph", ctx)


if __name__ == "__main__":
    unittest.main()
