"""
Vendor ALL of ECC (github.com/affaan-m/ecc, MIT), pinned and scanned. A chosen subset is made active.

    python scripts/vendor_ecc.py                  # re-vendor at the pin in vendor/ecc/ORIGIN.json
    python scripts/vendor_ecc.py --ref <sha>      # move the pin (review the diff in a PR)
    python scripts/vendor_ecc.py --latest         # move the pin to upstream HEAD
    python scripts/vendor_ecc.py --src <clone>    # use an existing checkout (must be at the ref)

Two tiers, because having everything and loading everything are different things:

  vendor/ecc/**         EVERY skill, agent, command, rule pack, context, workflow, and MCP config.
                        Costs nothing per session. Catalogued by the `capabilities` skill, so an
                        agent can find any of it and read it on demand.
  skills/ecc-*          The ACTIVE set: installed into ~/.claude, so its descriptions load into
  agents/ecc-*.md       every session. Listed in vendor/ecc-active.json; change it with
                        `python scripts/ecc.py use|drop <name>`.

Why not activate all ~290 skills: every installed skill's description is loaded at session start,
in every repo. All of ECC is roughly 15-20k tokens before the first message, and several ECC
descriptions claim universal triggers ("MUST BE USED for all code changes") that collide with the
harness's own skills. Details: docs/SECURITY.md.

Supply chain (ECC's own security guide: scan skills, hooks and agent descriptors like any other
dependency): everything is copied to a staging directory and scanned BEFORE it touches the repo.
Secret patterns, hidden Unicode, or a file over 5 MB aborts the whole vendoring.

Not vendored, by design: ECC's hook runtime and installer (they execute), its continuous-learning
observer (it captures prompts; its redaction misses bare key pastes), translations, and assets.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import memory_redact_shim as shim

URL = "https://github.com/affaan-m/ecc"
ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "ecc"
ORIGIN = VENDOR / "ORIGIN.json"
ACTIVE_FILE = ROOT / "vendor" / "ecc-active.json"
DEFAULT_PIN = "8321021c54d670126ce3b2969d5deb880b4b0c2a"
SURFACES = ["skills", "agents", "commands", "rules", "contexts", "workflows", "mcp-configs"]
DEFAULT_ACTIVE = {
    "skills": ["security-review", "production-audit", "codebase-onboarding", "architecture-decision-records",
               "database-migrations", "postgres-patterns", "deployment-patterns", "verification-loop",
               "nextjs-turbopack", "hexagonal-architecture"],
    "agents": ["security-reviewer", "silent-failure-hunter", "architect", "database-reviewer", "code-reviewer"],
}
HIDDEN = re.compile("[​-‏‪-‮⁠-⁤﻿]")
TEXT = {".md", ".json", ".txt", ".yaml", ".yml", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".py", ".sh", ".ps1",
        ".toml", ".lua", ".setting", ".html", ".css"}
MAX_BYTES = 5_000_000
NOTE = ("> Vendored from [ECC]({url}) @ `{sha}` (MIT). Your crossbrain and brain-pack skills take "
        "precedence where they conflict. Catalogue: `capabilities`. Refresh: `python scripts/vendor_ecc.py`.\n\n")


# ---------------------------------------------------------------- shared helpers (ecc.py imports these)

def pin() -> str:
    if ORIGIN.exists():
        return json.loads(ORIGIN.read_text(encoding="utf-8"))["commit"]
    return DEFAULT_PIN


def load_active() -> dict:
    if ACTIVE_FILE.exists():
        return json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
    return {k: list(v) for k, v in DEFAULT_ACTIVE.items()}


def save_active(active: dict) -> None:
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {k: sorted(set(v)) for k, v in active.items()}
    ACTIVE_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def rename(text: str, new: str) -> str:
    if re.search(r"^name:\s*.+$", text, flags=re.M):
        return re.sub(r"^name:\s*.+$", f"name: {new}", text, count=1, flags=re.M)
    # ECC commands and some agents have no name: - add one so the loader and CI can key on it.
    return re.sub(r"^---\s*\n", f"---\nname: {new}\n", text, count=1)


def with_note(text: str, sha: str) -> str:
    note = NOTE.format(url=URL, sha=sha[:7])
    m = re.match(r"(---\s*\n.*?\n---\s*\n)", text, re.S)
    return m.group(1) + "\n" + note + text[m.end():] if m else note + text


def defuse_dead_links(text: str, base: Path) -> str:
    """Links into ECC files we did not vendor (docs/, translations) would fail this repo's CI link
    check. Keep the words, drop the link: [x](gone.md) -> x (`gone.md`)."""
    def sub(m):
        return m.group(0) if (base / m.group(2)).exists() else f"{m.group(1)} (`{m.group(2)}`)"
    return re.sub(r"\[([^\]]+)\]\(([^)#:]+\.md)[^)]*\)", sub, text)


def activate_skill(name: str, sha: str, vendor: Path = VENDOR, root: Path = ROOT) -> Path:
    src = vendor / "skills" / name
    if not (src / "SKILL.md").exists():
        raise SystemExit(f"no ECC skill named '{name}' in {vendor / 'skills'}")
    dest = root / "skills" / f"ecc-{name}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    md = dest / "SKILL.md"
    md.write_text(with_note(rename(md.read_text(encoding="utf-8"), f"ecc-{name}"), sha), encoding="utf-8", newline="\n")
    for doc in dest.rglob("*.md"):
        doc.write_text(defuse_dead_links(doc.read_text(encoding="utf-8"), doc.parent), encoding="utf-8", newline="\n")
    return dest


def activate_agent(name: str, sha: str, vendor: Path = VENDOR, root: Path = ROOT) -> Path:
    src = vendor / "agents" / f"{name}.md"
    if not src.exists():
        raise SystemExit(f"no ECC agent named '{name}' in {vendor / 'agents'}")
    dest = root / "agents" / f"ecc-{name}.md"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(with_note(rename(src.read_text(encoding="utf-8"), f"ecc-{name}"), sha), encoding="utf-8", newline="\n")
    return dest


def scan(paths: list[Path], patterns, base: Path) -> list[str]:
    blocking = []
    for p in paths:
        rel = p.relative_to(base)
        if p.stat().st_size > MAX_BYTES:
            blocking.append(f"{rel} [over 5 MB]")
            continue
        if p.suffix.lower() not in TEXT and p.suffix:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        for pid, rx in patterns:
            m = rx.search(t)
            if m:
                blocking.append(f"{rel}:{t.count(chr(10), 0, m.start()) + 1} [{pid}]")
        if HIDDEN.search(t):
            blocking.append(f"{rel} [hidden-unicode]")
    return blocking


# ---------------------------------------------------------------- vendoring

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--ref")
    ap.add_argument("--latest", action="store_true")
    a = ap.parse_args()

    ref = a.ref or pin()
    if a.latest:
        ref = subprocess.run(["git", "ls-remote", URL, "HEAD"], capture_output=True, text=True, check=True).stdout.split()[0]

    tmp = Path(tempfile.mkdtemp(prefix="ecc-"))
    try:
        if a.src:
            src = Path(a.src)
        else:
            src = tmp / "clone"
            subprocess.run(["git", "clone", "--quiet", URL, str(src)], check=True)
            subprocess.run(["git", "-C", str(src), "-c", "advice.detachedHead=false", "checkout", "--quiet", ref], check=True)
        head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head != ref:
            sys.exit(f"ECC checkout is at {head[:7]}, expected {ref[:7]} - refusing to vendor unpinned content")

        # 1. Stage the full surface and scan it before anything touches the repo.
        stage = tmp / "stage"
        for s in SURFACES:
            if (src / s).exists():
                shutil.copytree(src / s, stage / s, ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".DS_Store"))
        shutil.copy2(src / "LICENSE", stage / "LICENSE")
        for doc in stage.rglob("*.md"):
            doc.write_text(defuse_dead_links(doc.read_text(encoding="utf-8", errors="replace"), doc.parent),
                           encoding="utf-8", newline="\n")
        staged = [p for p in stage.rglob("*") if p.is_file()]
        blocking = scan(staged, shim.load_patterns(), stage)
        if blocking:
            print(f"BLOCKED - ECC @ {ref[:7]} failed the supply-chain scan; nothing was changed:")
            for b in blocking[:50]:
                print("  " + b)
            sys.exit(1)

        # 2. Swap it in.
        if VENDOR.exists():
            shutil.rmtree(VENDOR)
        shutil.copytree(stage, VENDOR)
        counts = {s: len([d for d in (VENDOR / s).iterdir()]) if (VENDOR / s).exists() else 0 for s in SURFACES}
        ORIGIN.write_text(json.dumps({"url": URL, "commit": ref, "license": "MIT", "surfaces": counts}, indent=2) + "\n",
                          encoding="utf-8", newline="\n")

        # 3. Rebuild the active tier from the list.
        for old in (ROOT / "skills").glob("ecc-*"):
            shutil.rmtree(old)
        for old in (ROOT / "agents").glob("ecc-*.md"):
            old.unlink()
        active, missing = load_active(), []
        for name in active["skills"]:
            if (VENDOR / "skills" / name / "SKILL.md").exists():
                activate_skill(name, ref)
            else:
                missing.append(f"skill {name}")
        for name in active["agents"]:
            if (VENDOR / "agents" / f"{name}.md").exists():
                activate_agent(name, ref)
            else:
                missing.append(f"agent {name}")
        save_active(active)
        (ROOT / "agents" / "ECC-LICENSE").write_text((VENDOR / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"vendored ECC @ {ref[:7]}: " + ", ".join(f"{n} {s}" for s, n in counts.items()) + f" ({len(staged)} files, scan clean)")
    print(f"active: {len(active['skills'])} skills, {len(active['agents'])} agents")
    if missing:
        print("  WARN active entries no longer upstream: " + ", ".join(missing))


if __name__ == "__main__":
    main()
