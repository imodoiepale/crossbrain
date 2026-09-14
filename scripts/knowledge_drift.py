"""
Which repo skills has reality moved past? Lists repos with fix-like commits newer than their skill.

    crossbrain drift [--out FILE]        (sync runs it; default ~/.crossbrain/state/drift.md)

A skill is written once; the repo keeps shipping. Fixes that land after a skill was last committed may
hold a defect class the skill does not know. This names them so `retro` or a re-mine can fold them in.
It also reports how far upstream ECC has moved past the vendored pin - it never auto-bumps, because a
new pin is new third-party instructions for every agent and deserves a reviewed diff.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import hconfig as hc

FIX_RX = re.compile(r"^(fix|hotfix|revert)|\b(fix(e[sd])?|revert|broke|regression|hotfix)\b", re.I)


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def skill_home(skill: str, cfg: dict) -> Path | None:
    for root in reversed(hc.skill_roots(cfg)):
        if (root / skill / "SKILL.md").exists():
            return root.parent
    return None


def main():
    cfg = hc.load()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(hc.state_dir() / "drift.md"))
    a = ap.parse_args()
    brain_file = hc.brain_dir(cfg) / "brain.json"
    brain = json.loads(brain_file.read_text(encoding="utf-8")) if brain_file.exists() else {"repos": []}
    root = hc.projects_root(cfg)
    rows, missing = [], []
    for r in brain["repos"]:
        repo = root / r["repo"]
        if not (repo / ".git").exists():
            missing.append(r["repo"])
            continue
        home = skill_home(r["skill"], cfg)
        since = git(home, "log", "-1", "--format=%cI", "--", f"skills/{r['skill']}").strip() if home else ""
        since = since or "1970-01-01"
        new = [l for l in git(repo, "log", "--all", "--no-merges", f"--since={since}", "--format=%h %cs %s").splitlines()
               if FIX_RX.search(l.split(" ", 2)[-1])]
        if new:
            rows.append((r["repo"], r["skill"], since[:10], new))

    L = ["# Knowledge drift", "", "Repos with fix-like commits newer than their skill. Fold these in with `retro`, "
         "or re-mine the repo with `crossbrain mine`.", ""]
    if not brain["repos"]:
        L.append("No repo skills yet - see the `history-to-skills` skill.")
    elif not rows:
        L.append("No drift: every repo skill is newer than the repo's latest fix.")
    for repo, skill, since, new in sorted(rows, key=lambda x: -len(x[3])):
        L += [f"## {repo} — {len(new)} new fix-like commit(s) since `{skill}` ({since})", *[f"- {c}" for c in new[:15]], ""]
    if missing:
        L += ["", f"Not checked out under {root}: {', '.join(missing)}"]

    origin = hc.ENGINE / "vendor" / "ecc" / "ORIGIN.json"
    if origin.exists():
        info = json.loads(origin.read_text(encoding="utf-8"))
        try:
            head = subprocess.run(["git", "ls-remote", info["url"], "HEAD"], capture_output=True, text=True,
                                  timeout=20).stdout.split()[0]
            status = ("up to date" if head == info["commit"] else
                      f"upstream moved to {head[:7]} (pinned {info['commit'][:7]}) - review with "
                      "`python scripts/vendor_ecc.py --latest` on a branch")
        except (subprocess.SubprocessError, IndexError, OSError):
            status = "upstream unreachable"
        L += ["", f"## ECC library: {status}"]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"drift: {len(rows)} repo(s) with new fixes since their skill; {len(missing)} not checked out -> {out}")


if __name__ == "__main__":
    main()
