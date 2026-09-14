"""
Vendor archify (github.com/tt-a1i/archify, MIT) - pinned, scanned - into vendor/archify.

    python scripts/vendor_archify.py                  # re-vendor at the pin in vendor/archify/ORIGIN.json
    python scripts/vendor_archify.py --ref v2.17.0    # move the pin (review the diff in a PR)
    python scripts/vendor_archify.py --src <clone>    # use an existing checkout (must be at the ref)

archify turns a small typed JSON spec (or pasted Mermaid) into a validated, explorable architecture /
workflow / sequence / data-flow / lifecycle diagram as standalone HTML. project-intake uses it for the
architecture map. It runs on Node's standard library alone - no npm install - which is why it can
ship as a plain skill folder.

Only the skill folder (archify/ in the upstream repo) is taken. Like ECC, it is staged and scanned
first (secret patterns, hidden Unicode, files over 5 MB) and swapped in only if clean.
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

URL = "https://github.com/tt-a1i/archify"
ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "archify"
DEFAULT_REF = "v2.16.0"


def pinned_ref() -> str:
    origin = DEST / "ORIGIN.json"
    return json.loads(origin.read_text(encoding="utf-8"))["ref"] if origin.exists() else DEFAULT_REF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--ref")
    a = ap.parse_args()
    ref = a.ref or pinned_ref()

    tmp = Path(tempfile.mkdtemp(prefix="archify-"))
    try:
        src = Path(a.src) if a.src else tmp / "clone"
        if not a.src:
            subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", ref, URL, str(src)], check=True)
        commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if not (src / "archify" / "SKILL.md").exists():
            sys.exit(f"{src} has no archify/SKILL.md - upstream layout changed; refusing to vendor")

        stage = tmp / "stage" / "archify"
        shutil.copytree(src / "archify", stage, ignore=shutil.ignore_patterns("node_modules", ".git", "__pycache__"))
        staged = [p for p in stage.rglob("*") if p.is_file()]
        blocking = scan(staged, shim.load_patterns(), stage)
        if blocking:
            print(f"BLOCKED - archify {ref} failed the supply-chain scan; nothing was changed:")
            for b in blocking[:30]:
                print("  " + b)
            sys.exit(1)

        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.copytree(stage, DEST)
        hc.write_text_lf(DEST / "ORIGIN.json", json.dumps(
            {"url": URL, "ref": ref, "commit": commit, "license": "MIT", "path": "archify/", "files": len(staged)},
            indent=2) + "\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"vendored archify {ref} @ {commit[:7]}: {len(staged)} files, scan clean -> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
