"""
Tests for project_audit.py against a throwaway git repo seeded with real-world defect
shapes. All key material is FAKE and assembled at runtime so the commit gate has nothing to flag.

    python -m unittest scripts/test_project_audit.py -v

Also guards the vendored ECC content: no hidden Unicode may enter skills/ or agents/.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory_redact_shim as shim  # noqa: E402
import project_audit as pa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAKE_SBP = "sbp_" + "a86bFAKEFAKEFAKEFAKEFAKEfake123"
FAKE_JWT = "eyJ" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJ" + "yb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIn0"


def sh(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class AuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        r = Path(cls.tmp.name) / "fixture-app"
        r.mkdir()
        sh(r, "init", "-q")
        sh(r, "config", "user.email", "t@t")
        sh(r, "config", "user.name", "t")
        files = {
            "package.json": '{"dependencies":{"next":"16","@supabase/supabase-js":"2"},"scripts":{"build":"next build"}}',
            ".env": f"SUPABASE_ACCESS={FAKE_SBP}\n",
            "lib/client.ts": f'export const key = process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY || "{FAKE_JWT}";\n',
            "proxy.ts": "const claims = jwtDecode(token); if (claims.exp > now) next();\n",
            "supabase/migrations/001.sql": "create table a (id int);\ncreate table b (id int);\nalter table a enable row level security;\n"
                                           "create function f() returns int language sql security definer as $$ select 1 $$;\n"
                                           "create view v as select * from a;\n",
            "app/page copy.tsx": "export default function P() {}\n",
            "public/national-id-front.jpg": "not really a jpeg",
            # False-positive fixtures from the first real-world run - each must stay quiet.
            "scripts/test-keys.ps1": f"$fixture = '{FAKE_SBP}'\n",
            "src/i18n/locales/ar/settings.json": '{"title": "‏الإعدادات"}',
            "docs/setup.md": "Set NEXT_PUBLIC_MAPS_API_KEY in Vercel.\n",
            "lib/maps.ts": "export const mapsKey = process.env.NEXT_PUBLIC_MAPS_API_KEY;\n",
        }
        for name, body in files.items():
            (r / name).parent.mkdir(parents=True, exist_ok=True)
            (r / name).write_text(body, encoding="utf-8")
        sh(r, "add", "-A")
        sh(r, "commit", "-qm", "init")
        (r / ".env").unlink()
        sh(r, "rm", "-q", "--cached", ".env")
        sh(r, "commit", "-qm", "fix: remove env")
        cls.rep = pa.audit(r, shim.load_patterns())
        cls.ids = {f.id for f in cls.rep.findings}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_catches_every_seeded_defect(self):
        for expected in ["secret-in-client-bundle", "hardcoded-env-fallback", "jwt-decoded-not-verified",
                         "rls-coverage-gap", "definer-without-revoke", "views-run-as-owner", "env-not-ignored",
                         "secrets-in-history", "personal-data-files", "copy-files", "secret-patterns-at-head"]:
            with self.subTest(expected):
                self.assertIn(expected, self.ids)

    def test_removed_env_is_not_reported_as_tracked_but_history_still_is(self):
        self.assertNotIn("tracked-secret-files", self.ids)
        hist = next(f for f in self.rep.findings if f.id == "secrets-in-history")
        self.assertTrue(any("[supabase-mgmt]" in e for e in hist.evidence))

    def test_report_never_contains_a_secret_value(self):
        out = pa.render([self.rep])
        self.assertNotIn(FAKE_SBP, out)
        self.assertNotIn(FAKE_JWT, out)

    def test_architecture_map(self):
        a = self.rep.architecture
        self.assertIn("Next.js", a["stack"])
        self.assertIn("Supabase", a["stack"])
        self.assertEqual(a["sql_migrations"], 1)

    def test_fixture_keys_are_counted_not_reported(self):
        at_head = next(f for f in self.rep.findings if f.id == "secret-patterns-at-head")
        self.assertFalse(any("test-keys.ps1" in e for e in at_head.evidence))
        self.assertGreaterEqual(self.rep.facts.get("secret_shaped_strings_in_test_fixtures", 0), 1)
        hist = next(f for f in self.rep.findings if f.id == "secrets-in-history")
        self.assertEqual(len(hist.evidence), 1, "only the .env commit, not the fixture file")

    def test_rtl_marks_in_a_locale_file_are_not_agent_injection(self):
        self.assertNotIn("hidden-unicode-agent-config", self.ids)

    def test_browser_api_key_is_high_not_critical_and_doc_mentions_ignored(self):
        crit = next(f for f in self.rep.findings if f.id == "secret-in-client-bundle")
        self.assertTrue(all("SERVICE_ROLE" in e for e in crit.evidence))
        api = next(f for f in self.rep.findings if f.id == "api-key-in-client-bundle")
        self.assertEqual(api.severity, "high")
        self.assertTrue(any("lib/maps.ts" in e for e in api.evidence))
        self.assertFalse(any("docs/setup.md" in e for e in api.evidence + crit.evidence))

    def test_summary_mode_has_no_file_line_evidence(self):
        out = pa.render([self.rep], summary=True)
        self.assertNotIn("lib/client.ts", out)
        self.assertNotIn("supabase-mgmt", out)

    def test_small_repos_are_not_nagged_about_tests_or_ci(self):
        # Under 10 commits is a spike or a demo; demanding a test suite there is noise.
        self.assertNotIn("no-tests", self.ids)
        self.assertNotIn("no-ci", self.ids)

    def test_score_is_bounded_and_banded(self):
        self.assertGreaterEqual(self.rep.score, 0)
        self.assertEqual(self.rep.band, "Blocked")


class VendoredContentTest(unittest.TestCase):
    def test_no_hidden_unicode_in_skills_or_agents(self):
        hidden = re.compile("[​-‏‪-‮⁠-⁤﻿]")
        bad = [str(p.relative_to(ROOT)) for d in ("skills", "agents", "vendor") if (ROOT / d).exists()
               for p in (ROOT / d).rglob("*") if p.is_file() and p.suffix in (".md", ".json", ".txt", ".yaml", ".yml")
               and hidden.search(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
