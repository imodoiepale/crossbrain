"""
Vendor third-party skill packs - pinned to a release tag, scanned, credited.

    python scripts/vendor_skillpacks.py                 # re-vendor every pack at its pinned ref
    python scripts/vendor_skillpacks.py ponytail        # one pack
    python scripts/vendor_skillpacks.py ponytail --ref v4.11.0   # move its pin (review the diff in a PR)

Only SKILL.md folders and licence/rule text are taken. Hooks, plugins, MCP servers and benchmarks are left
upstream on purpose: they are code that would run on your machine, and crossbrain already has its own hooks.

Each pack is staged and scanned first (secret patterns, hidden Unicode, files over 5 MB) and swapped in only if
clean, exactly like the ECC library.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import hconfig as hc
import memory_redact_shim as shim
from vendor_ecc import scan

ROOT = Path(__file__).resolve().parent.parent

PACKS = {
    "ponytail": {
        "url": "https://github.com/DietrichGebert/ponytail",
        "ref": "v4.10.0",
        "skills": "skills",
        "files": ["AGENTS.md", "LICENSE", "README.md"],
        "rules_file": "AGENTS.md",          # always-on ruleset, embedded in the instruction block
        "license": "MIT",
        "why": "lazy-senior-dev ladder: YAGNI, reuse, stdlib, native, one line - with safety carve-outs",
    },
    "engineer-skills": {
        "url": "https://github.com/alonbaron/claude-skills",
        "ref": "v2.1.0",
        "skills": "skills",
        "exclude": ["ponytail"],            # taken from upstream instead
        "files": ["LICENSE", "NOTICE", "README.md"],
        "license": "MIT",
        "why": "architect, review-swarm, ask-the-council, prompt-generator, up-to-date",
    },
}


def vendor(name: str, ref: str | None = None, src: Path | None = None) -> int:
    spec = PACKS[name]
    dest = ROOT / "vendor" / name
    origin = dest / "ORIGIN.json"
    ref = ref or (json.loads(origin.read_text(encoding="utf-8"))["ref"] if origin.exists() else spec["ref"])
    tmp = Path(tempfile.mkdtemp(prefix=f"{name}-"))
    try:
        clone = src or tmp / "clone"
        if src is None:
            subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", ref, spec["url"], str(clone)], check=True)
        commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

        stage = tmp / "stage"
        (stage / "skills").mkdir(parents=True)
        skills = []
        for d in sorted((clone / spec["skills"]).iterdir()):
            if not (d / "SKILL.md").exists() or d.name in spec.get("exclude", []):
                continue
            shutil.copytree(d, stage / "skills" / d.name, ignore=shutil.ignore_patterns("node_modules", ".git"))
            skills.append(d.name)
        if not skills:
            sys.exit(f"{name}: no SKILL.md folders under {spec['skills']}/ at {ref} - upstream layout changed")
        for f in spec["files"]:
            if (clone / f).exists():
                shutil.copy2(clone / f, stage / Path(f).name)

        staged = [p for p in stage.rglob("*") if p.is_file()]
        blocking = scan(staged, shim.load_patterns(), stage)
        if blocking:
            print(f"BLOCKED - {name} {ref} failed the supply-chain scan; nothing was changed:")
            for b in blocking[:30]:
                print("  " + b)
            return 1

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(stage, dest)
        hc.write_text_lf(dest / "ORIGIN.json", json.dumps(
            {"url": spec["url"], "ref": ref, "commit": commit, "license": spec["license"],
             "skills": skills, "rules_file": spec.get("rules_file"), "why": spec["why"]}, indent=2) + "\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"vendored {name} {ref} @ {commit[:7]}: {len(skills)} skills ({', '.join(skills)}), scan clean")
    return 0


def rules_text(pack: str = "ponytail") -> str:
    """The pack's always-on ruleset, for the global instruction block. Empty when not vendored."""
    origin = ROOT / "vendor" / pack / "ORIGIN.json"
    if not origin.exists():
        return ""
    info = json.loads(origin.read_text(encoding="utf-8"))
    f = ROOT / "vendor" / pack / (info.get("rules_file") or "")
    return f.read_text(encoding="utf-8") if f.exists() else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", nargs="?", choices=sorted(PACKS))
    ap.add_argument("--ref")
    ap.add_argument("--src")
    a = ap.parse_args()
    packs = [a.pack] if a.pack else sorted(PACKS)
    return max(vendor(p, a.ref, Path(a.src) if a.src else None) for p in packs)


if __name__ == "__main__":
    sys.exit(main())
