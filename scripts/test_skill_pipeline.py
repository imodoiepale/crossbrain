"""
Tests for the self-updating skill pipeline: adoption of hand-added skills, and the generated
capabilities catalogue. No network, no real ~/.claude.

    python -m unittest scripts/test_skill_pipeline.py -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import adopt_skills as ad  # noqa: E402
import build_capabilities as bc  # noqa: E402
import hconfig as hc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAKE_SBP = "sbp_" + "a86bFAKEFAKEFAKEFAKEFAKEfake123"


def skill(root: Path, name: str, desc: str = "Does a thing. Use when testing.", body: str = "# x\n", fm_name: str | None = None):
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {fm_name or name}\ndescription: {desc}\n---\n\n{body}", encoding="utf-8")
    return d


class FrontmatterTest(unittest.TestCase):
    def test_scalar_quoted_and_block(self):
        fm = bc.frontmatter('---\nname: a\ndescription: >\n  folded line one\n  line two\nlicense: "MIT"\n---\nbody')
        self.assertEqual(fm["name"], "a")
        self.assertEqual(fm["description"], "folded line one line two")
        self.assertEqual(fm["license"], "MIT")

    def test_no_frontmatter(self):
        self.assertEqual(bc.frontmatter("# just markdown"), {})


class AdoptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        # Never read this machine's real ~/.harnessd/config.json. A real brain pack that happens to hold a
        # skill named like a fixture ("diagrammer") made adoption skip it, the tests failed, and sync then
        # refused to install - on exactly the machines that use harnessd the most.
        patcher = mock.patch.object(hc, "CONFIG", t / "no-config.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user, self.repo, self.manifest = t / "user", t / "repo", t / "user" / ".harness-manifest.json"
        self.user.mkdir(); self.repo.mkdir()
        good = skill(self.user, "diagrammer", body="Run node bin/x.js\n")
        (good / "node_modules" / "dep").mkdir(parents=True)
        (good / "node_modules" / "dep" / "index.js").write_text("module.exports = 1", encoding="utf-8")
        (good / "package-lock.json").write_text("{}", encoding="utf-8")
        skill(self.user, "leaky", body=f"Use token {FAKE_SBP}\n")
        skill(self.user, "renamed", fm_name="other-name")
        skill(self.user, "tool-managed")
        skill(self.user, "from-harness")
        skill(self.repo, "already-here")
        skill(self.user, "already-here")
        (self.repo / ".adopt-ignore").write_text("# owned by their installers\ntool-managed\n", encoding="utf-8")
        self.manifest.write_text(json.dumps({"skills": ["from-harness"]}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_adopt(self, dry=False):
        return ad.adopt(self.user, self.repo, self.manifest, dry_run=dry, today="2026-09-13")

    def test_adopts_clean_skill_without_node_modules(self):
        r = self.run_adopt()
        self.assertEqual(r["adopted"], ["diagrammer"])
        dest = self.repo / "diagrammer"
        self.assertTrue((dest / "SKILL.md").exists())
        self.assertFalse((dest / "node_modules").exists())
        meta = json.loads((dest / ".adopted.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["excluded"], ["node_modules"])
        self.assertTrue(meta["restore_dependencies"])

    def test_secret_bearing_skill_is_quarantined_and_not_copied(self):
        r = self.run_adopt()
        self.assertIn("leaky", r["quarantined"])
        self.assertTrue(any("supabase-mgmt" in p for p in r["quarantined"]["leaky"]))
        self.assertFalse((self.repo / "leaky").exists())
        self.assertNotIn(FAKE_SBP, json.dumps(r), "the report must not carry the secret")

    def test_ignore_manifest_existing_and_name_mismatch_are_respected(self):
        r = self.run_adopt()
        self.assertNotIn("tool-managed", r["adopted"] + list(r["quarantined"]))
        self.assertNotIn("from-harness", r["adopted"])
        self.assertNotIn("already-here", r["adopted"])
        self.assertIn("renamed", r["skipped"])

    def test_dry_run_writes_nothing(self):
        r = self.run_adopt(dry=True)
        self.assertEqual(r["adopted"], ["diagrammer"])
        self.assertFalse((self.repo / "diagrammer").exists())

    def test_idempotent(self):
        self.run_adopt()
        self.assertEqual(self.run_adopt()["adopted"], [])


class CapabilitiesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.root = Path(self.tmp.name)
        skill(r / "skills", "brain", "Master brain.")
        skill(r / "skills", "repo-demo", "Demo repo.")
        skill(r / "skills", "ecc-security-review", "Security checklist.")
        a = skill(r / "skills", "diagrammer", "Draws diagrams.")
        (a / ".adopted.json").write_text("{}", encoding="utf-8")
        (r / "agents").mkdir()
        (r / "agents" / "ecc-architect.md").write_text("---\nname: ecc-architect\ndescription: Designs.\n---\n", encoding="utf-8")
        v = r / "vendor" / "ecc"
        skill(v / "skills", "security-review", "Security checklist.")
        skill(v / "skills", "django-tdd", "Django TDD.")
        skill(v / "skills", "tdd-workflow", "desc placeholder")
        (v / "skills" / "tdd-workflow" / "SKILL.md").write_text(
            "---\nname: tdd-workflow\ndescription: >\n  Red green refactor\n  for everything.\n---\n", encoding="utf-8")
        (v / "agents").mkdir(); (v / "agents" / "planner.md").write_text("---\nname: planner\ndescription: Plans.\n---\n", encoding="utf-8")
        (v / "commands").mkdir(); (v / "commands" / "code-review.md").write_text("---\ndescription: Review | code.\n---\n", encoding="utf-8")
        (v / "rules" / "typescript").mkdir(parents=True)
        (v / "ORIGIN.json").write_text(json.dumps({"commit": "8321021c54d6"}), encoding="utf-8")
        (r / "vendor" / "ecc-active.json").write_text(json.dumps({"skills": ["security-review"], "agents": ["architect"]}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_indexes_every_tier(self):
        out = bc.build(self.root)
        for needle in ["`brain`", "`repo-demo`", "`ecc-security-review`", "`diagrammer`", "`ecc-architect`",
                       "`django-tdd`", "`planner`", "`code-review`", "`typescript`", "security-review ✅"]:
            with self.subTest(needle):
                self.assertIn(needle, out)
        self.assertIn("Red green refactor for everything.", out)
        self.assertIn("Review / code.", out, "pipes in descriptions must not break the table")

    def test_categorises_framework_skills_by_prefix(self):
        out = bc.build(self.root)
        lang = out.split("### Skills: Languages & frameworks")[1].split("###")[0]
        self.assertIn("django-tdd", lang)

    def test_deterministic_and_machine_independent(self):
        a, b = bc.build(self.root), bc.build(self.root)
        self.assertEqual(a, b)
        self.assertNotIn(str(Path.home()), a)
        self.assertIn(bc.HARNESS_TOKEN, a)

    def test_local_build_adds_plugins_and_pending_local_skills(self):
        user = self.root / "userskills"; skill(user, "scroll-thing", "Scroll.")
        plugins = self.root / "plugins"
        skill(plugins / "cache" / "official" / "superpowers" / "5.0" / "skills", "brainstorming", "Brainstorm first.")
        out = bc.build(self.root, local=True, user_skills=user, plugins=plugins)
        self.assertIn("scroll-thing ⏳", out)
        self.assertIn("### superpowers", out)
        self.assertIn("`brainstorming`", out)

    def test_committed_catalogue_is_current(self):
        if not (ROOT / "vendor" / "ecc" / "ORIGIN.json").exists():
            self.skipTest("ECC not vendored in this checkout")
        committed = (ROOT / "skills" / "capabilities" / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(committed, bc.build(ROOT), "run python scripts/build_capabilities.py")


if __name__ == "__main__":
    unittest.main()
