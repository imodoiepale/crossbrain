"""
Tests for sync's commit rule: sync commits what it owns (generated brain/, adopted skills) and never
commits your own uncommitted work. Runs against real throwaway git repos; no network.

    python -m unittest scripts/test_sync.py -v
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sync  # noqa: E402

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def sh(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CommitOwnedChangesTest(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in IDENTITY}
        os.environ.update(IDENTITY)
        self.tmp = tempfile.TemporaryDirectory()
        self.pack = Path(self.tmp.name) / "pack"
        self.pack.mkdir()
        sh(self.pack, "init", "-q", "-b", "main")
        write(self.pack / "skills" / ".adopt-ignore", "graphify\n")
        write(self.pack / ".gitignore", "digests/\n")
        sh(self.pack, "add", "-A")
        sh(self.pack, "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def adopted_skill(self, name: str):
        write(self.pack / "skills" / name / "SKILL.md", f"---\nname: {name}\ndescription: Test skill.\n---\n")
        write(self.pack / "skills" / name / ".adopted.json", "{}\n")

    def commits(self) -> int:
        return len(sh(self.pack, "log", "--oneline").splitlines())

    def test_generated_brain_alone_is_committed(self):
        write(self.pack / "brain" / "brain.json", "{}\n")
        result = sync.commit_owned_changes(self.pack, [], push=False)
        self.assertIn("committed (not pushed): chore(brain)", result)
        self.assertEqual(self.commits(), 2)
        self.assertEqual(sync.dirty_paths(self.pack), [])

    def test_adopted_skill_and_brain_commit_together_with_skill_subject(self):
        self.adopted_skill("diagrammer")
        write(self.pack / "brain" / "BRAIN.md", "# Brain\n")
        result = sync.commit_owned_changes(self.pack, ["diagrammer"], push=False)
        self.assertIn("feat(skills): adopt diagrammer", result)
        self.assertIn("skills/diagrammer/SKILL.md", sh(self.pack, "show", "--name-only", "HEAD"))

    def test_skill_adopted_on_an_earlier_run_is_still_committed(self):
        self.adopted_skill("scroller")          # adopted before, never committed (the original bug)
        result = sync.commit_owned_changes(self.pack, [], push=False)
        self.assertIn("feat(skills): adopt scroller", result)

    def test_users_own_uncommitted_edit_blocks_the_commit(self):
        self.adopted_skill("diagrammer")
        write(self.pack / "skills" / "my-hand-written" / "SKILL.md", "---\nname: my-hand-written\ndescription: wip\n---\n")
        result = sync.commit_owned_changes(self.pack, ["diagrammer"], push=False)
        self.assertIn("uncommitted changes of yours", result)
        self.assertEqual(self.commits(), 1, "sync must never commit the user's work in progress")

    def test_secret_in_adopted_skill_is_refused_by_preflight(self):
        self.adopted_skill("leaky")
        write(self.pack / "skills" / "leaky" / "notes.md", "token " + "sbp_" + "a86b" + "Q7m2" * 6 + "\n")
        result = sync.commit_owned_changes(self.pack, ["leaky"], push=False)
        self.assertIn("REFUSED by preflight", result)
        self.assertEqual(self.commits(), 1)
        self.assertEqual(sh(self.pack, "diff", "--cached", "--name-only"), "", "refused changes must be unstaged")

    def test_nothing_to_commit(self):
        self.assertEqual(sync.commit_owned_changes(self.pack, [], push=False), "nothing to commit")

    def test_pull_leaves_foreign_changes_alone_but_tolerates_owned_ones(self):
        write(self.pack / "notes.txt", "mine\n")
        self.assertIn("of yours", sync.pull(self.pack, allow_owned=True))
        (self.pack / "notes.txt").unlink()
        write(self.pack / "brain" / "brain.json", "{}\n")
        self.assertIn("pending commit", sync.pull(self.pack, allow_owned=True))


if __name__ == "__main__":
    unittest.main()
