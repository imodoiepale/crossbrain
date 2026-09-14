"""
Mine every git repo's history into a per-repo digest, the raw material for per-repo skills.

    python scripts/mine_repo_history.py --root ~/Documents/GitHub --out <dir> [--min-commits 10]

Deterministic, no LLM. For each repo: size and span, conventional-prefix mix, the fix / revert /
rework commits (the lessons), the files that churn most and the files that fixes keep touching
(the defect hotspots), the stack, and any CLAUDE.md / AGENTS.md already written by hand.

Every line of output passes through secret-patterns.txt first: commit messages in real repositories have
carried keys before, and a digest must not become a second copy of them.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
from pathlib import Path

import hconfig as hc
import memory_redact_shim as shim

FIX_RX = re.compile(r"^(fix|hotfix|revert|bug)|\b(fix(e[sd])?|revert|broke|regression|again|actually|real (cause|defect)|rollback|hotfix)\b", re.I)
PREFIX_RX = re.compile(r"^([a-z]+)(\([^)]*\))?!?:", re.I)
DOCS = ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md")


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def stack(repo: Path) -> list[str]:
    out = []
    pj = repo / "package.json"
    if pj.exists():
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
            deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
            out.append("npm: " + ", ".join(sorted(deps)[:60]))
            if d.get("scripts"):
                out.append("scripts: " + ", ".join(f"{k}={v}" for k, v in list(d["scripts"].items())[:15]))
        except ValueError:
            pass
    for f in ("requirements.txt", "pyproject.toml", "go.mod", "Cargo.toml", "pubspec.yaml", "composer.json"):
        p = repo / f
        if p.exists():
            out.append(f"{f}: " + " ".join(p.read_text(encoding="utf-8", errors="replace").split())[:600])
    return out


def digest(repo: Path, patterns) -> str | None:
    log = git(repo, "log", "--all", "--no-merges", "--date=short", "--format=\x1e%h\x1f%ad\x1f%s\x1f%b", "--numstat")
    commits = []
    for block in log.split("\x1e")[1:]:
        head, _, rest = block.partition("\n")
        parts = head.split("\x1f")
        if len(parts) < 4:
            continue
        h, date, subj, body = parts[0], parts[1], parts[2], parts[3]
        files = [ln.split("\t")[2] for ln in rest.splitlines() if ln.count("\t") >= 2]
        commits.append((h, date, subj.strip(), body.strip(), files))
    if not commits:
        return None

    churn, fixchurn, prefixes = collections.Counter(), collections.Counter(), collections.Counter()
    fixes = []
    for h, date, subj, body, files in commits:
        m = PREFIX_RX.match(subj)
        prefixes[m.group(1).lower() if m else "(none)"] += 1
        churn.update(files)
        if FIX_RX.search(subj):
            fixchurn.update(files)
            fixes.append((date, h, subj, body[:400]))

    L = [f"# {repo.name}", "",
         f"commits: {len(commits)}  span: {commits[-1][1]} -> {commits[0][1]}  fix-like: {len(fixes)} ({100*len(fixes)//len(commits)}%)",
         "prefixes: " + ", ".join(f"{k}={v}" for k, v in prefixes.most_common(10)), ""]
    L += ["## stack", *stack(repo), ""]
    L += ["## most-churned files", *[f"{n}\t{f}" for f, n in churn.most_common(25)], ""]
    L += ["## files fixes keep touching (defect hotspots)", *[f"{n}\t{f}" for f, n in fixchurn.most_common(20)], ""]
    L += ["## fix / revert / rework commits (newest first, up to 80)"]
    for date, h, subj, body in fixes[:80]:
        L.append(f"- {date} {h} {subj}")
        if body:
            L.append("  " + " ".join(body.split())[:400])
    L += ["", "## recent subjects (newest 60)", *[f"- {c[1]} {c[2]}" for c in commits[:60]], ""]
    for d in DOCS:
        p = repo / d
        if p.exists():
            L += [f"## existing {d} (first 150 lines)", *p.read_text(encoding="utf-8", errors="replace").splitlines()[:150], ""]
    readme = next((p for p in repo.glob("README*") if p.is_file()), None)
    if readme:
        L += ["## README (first 40 lines)", *readme.read_text(encoding="utf-8", errors="replace").splitlines()[:40]]

    text, _ = shim.redact("\n".join(L).encode("utf-8"), patterns)
    return text.decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(hc.projects_root()))
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-commits", type=int, default=10)
    a = ap.parse_args()
    patterns = shim.load_patterns()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for repo in sorted(Path(a.root).iterdir()):
        if not (repo / ".git").exists() or " - Copy" in repo.name:
            continue
        n = git(repo, "rev-list", "--all", "--count").strip()
        if not n.isdigit() or int(n) < a.min_commits:
            print(f"skip  {repo.name} ({n or 0} commits)")
            continue
        d = digest(repo, patterns)
        if d:
            (out / f"{repo.name.replace(' ', '-')}.md").write_text(d, encoding="utf-8")
            print(f"ok    {repo.name} ({n} commits, {len(d)//1024} KB)")


if __name__ == "__main__":
    main()
