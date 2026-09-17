"""
Tests for vendored skill packs (ponytail, engineer-skills): they are pinned, installable as skills, and
ponytail's ruleset is embedded verbatim in the instruction block every agent reads.

    python -m unittest scripts/test_packs.py -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hconfig as hc  # noqa: E402
import install as inst  # noqa: E402
import vendor_skillpacks as vp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALL_ON = {"components": ["archify", "graphify", "ponytail", "engineer-skills"], "packs": []}


class VendoredPacksTest(unittest.TestCase):
    def origin(self, pack: str) -> dict:
        f = ROOT / "vendor" / pack / "ORIGIN.json"
        if not f.exists():
            self.skipTest(f"{pack} not vendored in this checkout")
        return json.loads(f.read_text(encoding="utf-8"))

    def test_each_pack_is_pinned_to_a_release_with_a_licence(self):
        for pack in vp.PACKS:
            with self.subTest(pack):
                info = self.origin(pack)
                self.assertEqual(info["license"], "MIT")
                self.assertRegex(info["ref"], r"^v\d+\.\d+")
                self.assertRegex(info["commit"], r"^[0-9a-f]{40}$")
                self.assertTrue((ROOT / "vendor" / pack / "LICENSE").exists())

    def test_ponytail_skills_are_installable_and_engineer_skills_exclude_the_duplicate(self):
        self.origin("ponytail")
        skills = inst.collect(hc.skill_roots(ALL_ON), "*")
        for name in ("ponytail", "ponytail-review", "ponytail-audit"):
            self.assertIn(name, skills)
        self.assertEqual(skills["ponytail"], ROOT / "vendor" / "ponytail" / "skills" / "ponytail")
        for name in ("architect", "review-swarm", "ask-the-council", "prompt-generator", "up-to-date"):
            self.assertIn(name, skills)
        # the engineer pack ships its own copy of ponytail; upstream's must win
        self.assertNotIn("engineer-skills", skills)

    def test_no_executable_pack_machinery_is_vendored(self):
        self.origin("ponytail")
        bad = [str(p.relative_to(ROOT)) for p in (ROOT / "vendor" / "ponytail").rglob("*")
               if p.suffix in (".js", ".mjs", ".cjs", ".ps1", ".sh")]
        self.assertEqual(bad, [], "hooks/plugins are code that would run on a user's machine")

    def test_components_toggle_the_skill_roots(self):
        off = {"components": [], "packs": []}
        self.assertNotIn(ROOT / "vendor" / "ponytail" / "skills", hc.skill_roots(off))
        self.assertIn(ROOT / "vendor" / "ponytail" / "skills", hc.skill_roots(ALL_ON))


class AlwaysOnRulesTest(unittest.TestCase):
    def setUp(self):
        if not (ROOT / "vendor" / "ponytail" / "ORIGIN.json").exists():
            self.skipTest("ponytail not vendored in this checkout")

    def test_rules_are_embedded_verbatim_with_attribution(self):
        rules = inst.always_on_rules(ALL_ON)
        upstream = vp.rules_text("ponytail").strip()
        self.assertIn(upstream, rules, "the ruleset must be embedded verbatim, not paraphrased")
        self.assertIn("DietrichGebert/ponytail", rules)
        self.assertIn("MIT", rules)

    def test_the_instruction_block_carries_them(self):
        block = inst.INSTRUCTIONS.format(begin=inst.BLOCK_BEGIN, end=inst.BLOCK_END, rules=inst.always_on_rules(ALL_ON))
        self.assertIn("lazy senior developer", block)
        self.assertIn("YAGNI", block)
        self.assertTrue(block.strip().endswith(inst.BLOCK_END))

    def test_opting_out_removes_them(self):
        self.assertEqual(inst.always_on_rules({"components": ["graphify"]}), "")
        block = inst.INSTRUCTIONS.format(begin=inst.BLOCK_BEGIN, end=inst.BLOCK_END, rules="")
        self.assertNotIn("YAGNI", block)


if __name__ == "__main__":
    unittest.main()
