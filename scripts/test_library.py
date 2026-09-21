import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


class LibrarySearch(unittest.TestCase):
    def test_ranks_name_match_first(self):
        with tempfile.TemporaryDirectory() as d:
            for name, desc in [("scanning-with-trivy", "container scan"), ("other", "mentions trivy once")]:
                (Path(d) / "lib/skills" / name).mkdir(parents=True)
                (Path(d) / "lib/skills" / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n")
            os.environ["CROSSBRAIN_HOME"] = d
            (Path(d) / "config.json").write_text('{"libraries": {"sec": "%s"}}' % (Path(d) / "lib").as_posix())
            import importlib, hconfig, library
            importlib.reload(hconfig); importlib.reload(library)
            hits = list(library.skills(Path(d) / "lib"))
            self.assertEqual(len(hits), 2)
            from io import StringIO
            from contextlib import redirect_stdout
            out = StringIO()
            with redirect_stdout(out):
                library.main(["search", "trivy"])
            self.assertLess(out.getvalue().index("scanning-with-trivy"), out.getvalue().index("other"))
            del os.environ["CROSSBRAIN_HOME"]


if __name__ == "__main__":
    unittest.main()
