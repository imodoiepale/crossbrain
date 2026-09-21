"""
Search the on-demand skill libraries registered in config "libraries" (e.g. the cybersecurity library).

    crossbrain library search <words>     # top matches by name, description and subdomain
    crossbrain library list               # registered libraries and their skill counts
"""

from __future__ import annotations

import sys
from pathlib import Path

import hconfig as hc
from build_capabilities import frontmatter


def skills(root: Path):
    for md in sorted((root / "skills").glob("*/SKILL.md")):
        fm = frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        yield md, fm.get("name", md.parent.name), fm.get("description", ""), fm.get("subdomain", "")


def main(argv: list[str]) -> int:
    libs = {k: hc.expand(v) for k, v in hc.load().get("libraries", {}).items()}
    if not argv or argv[0] not in ("search", "list"):
        print(__doc__)
        return 2
    if argv[0] == "list" or not libs:
        for name, root in libs.items():
            print(f"  {name:<12} {root}  ({sum(1 for _ in skills(root))} skills)")
        if not libs:
            print("no libraries registered - crossbrain config libraries '{\"security\": \"<path to clone>\"}'")
        return 0
    words = [w.lower() for w in argv[1:]]
    hits = []
    for lib, root in libs.items():
        for md, name, desc, sub in skills(root):
            score = sum(3 * (w in name) + 2 * (w in sub.lower()) + (w in desc.lower()) for w in words)
            if score:
                hits.append((-score, name, sub, md))
    for _, name, sub, md in sorted(hits)[:15]:
        print(f"  {name:<55} {sub:<24} {md}")
    if not hits:
        print("no match - try broader words")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
