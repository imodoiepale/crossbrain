"""
Work with the vendored ECC library: find anything in it, read it, make it always-loaded, or unload it.

    python scripts/ecc.py search stripe webhook       # rank skills/agents/commands by the words
    python scripts/ecc.py show tdd-workflow           # print the path (and head) of a skill/agent/command
    python scripts/ecc.py use tdd-workflow            # activate a skill (installs on every PC after sync)
    python scripts/ecc.py use --agent planner         # activate an agent
    python scripts/ecc.py drop nextjs-turbopack       # deactivate (stays in the library)
    python scripts/ecc.py list                        # the active set

`use` and `drop` edit vendor/ecc-active.json and regenerate skills/ecc-*, agents/ecc-*, the
capabilities catalogue and the brain. Then commit; sync-knowledge.ps1 spreads it.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import vendor_ecc as v
from build_capabilities import frontmatter

ROOT = v.ROOT


def library():
    for kind, folder, pattern in [("skill", v.VENDOR / "skills", "*/SKILL.md"), ("agent", v.VENDOR / "agents", "*.md"),
                                  ("command", v.VENDOR / "commands", "*.md")]:
        for md in sorted(folder.glob(pattern)) if folder.exists() else []:
            name = md.parent.name if kind == "skill" else md.stem
            yield kind, name, md, frontmatter(md.read_text(encoding="utf-8", errors="replace")).get("description", "")


def rebuild():
    for script in ("build_capabilities.py", "build_brain.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("words", nargs="+")
    s = sub.add_parser("show"); s.add_argument("name")
    for c in ("use", "drop"):
        s = sub.add_parser(c); s.add_argument("name"); s.add_argument("--agent", action="store_true")
    sub.add_parser("list")
    a = ap.parse_args()

    if a.cmd == "search":
        words = [w.lower() for w in a.words]
        scored = []
        for kind, name, md, desc in library():
            hay_name, hay_desc = name.lower(), desc.lower()
            score = sum(3 * (w in hay_name) + (w in hay_desc) for w in words)
            if score:
                scored.append((-score, kind, name, desc))
        for _, kind, name, desc in sorted(scored)[:25]:
            # Normalise outside the f-string: a backslash inside a replacement field needs Python 3.12+.
            summary = re.sub(r"\s+", " ", desc)[:110]
            print(f"{kind:8} {name:40} {summary}")
        if not scored:
            print("no match in the ECC library")
        return

    if a.cmd == "show":
        for kind, name, md, desc in library():
            if name == a.name:
                print(f"{kind}: {md}\n")
                print("\n".join(md.read_text(encoding="utf-8").splitlines()[:40]))
                return
        sys.exit(f"'{a.name}' is not in the ECC library - try: python scripts/ecc.py search {a.name}")

    active = v.load_active()
    if a.cmd == "list":
        print("skills: " + ", ".join(active["skills"]))
        print("agents: " + ", ".join(active["agents"]))
        return

    key = "agents" if a.agent else "skills"
    sha = v.pin()
    if a.cmd == "use":
        (v.activate_agent if a.agent else v.activate_skill)(a.name, sha)
        active[key].append(a.name)
        print(f"activated ECC {key[:-1]} '{a.name}' as ecc-{a.name}")
    else:
        if a.name not in active[key]:
            sys.exit(f"'{a.name}' is not an active ECC {key[:-1]}")
        active[key].remove(a.name)
        target = ROOT / ("agents" if a.agent else "skills") / (f"ecc-{a.name}.md" if a.agent else f"ecc-{a.name}")
        shutil.rmtree(target) if target.is_dir() else target.unlink(missing_ok=True)
        print(f"deactivated ECC {key[:-1]} '{a.name}' (still in the library)")
    v.save_active(active)
    rebuild()
    print("next: commit skills/ agents/ vendor/ecc-active.json skills/capabilities brain/ - sync spreads it to every PC")


if __name__ == "__main__":
    main()
