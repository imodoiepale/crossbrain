"""
Adopt skills added by hand on this PC into the harness, so every PC gets them.

    python scripts/adopt_skills.py            # adopt everything eligible
    python scripts/adopt_skills.py --dry-run  # show what would happen
    python scripts/adopt_skills.py --json     # machine-readable result (used by sync-knowledge.ps1)

A skill is eligible when it sits in ~/.claude/skills, has a SKILL.md whose `name:` matches its
directory, is not already in the harness, was not installed BY the harness (manifest), and is not
listed in skills/.adopt-ignore (tool-managed skills such as graphify, which its own installer owns).

What is copied: the skill's own files. Never copied: node_modules, .git, virtualenvs, build output,
caches. Each PC restores dependencies from the lockfile (install-skills.ps1).

Quarantine instead of adoption, when any file: matches a secret pattern, contains hidden/bidi
Unicode (a prompt-injection carrier in agent instructions), or is over 5 MB. Quarantined skills
stay local and are reported. Nothing is ever deleted from ~/.claude/skills.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

import hconfig as hc
import memory_redact_shim as shim
from build_capabilities import frontmatter

ROOT = hc.ENGINE
# Where people drop skills by hand. Both are scanned; each carries the installer manifest.
USER_SKILL_DIRS = [hc.expand(hc.SKILL_TARGETS["claude"]), hc.expand(hc.SKILL_TARGETS["agents"])]
USER_SKILLS = USER_SKILL_DIRS[0]
MANIFEST_NAME = ".harnessd-manifest.json"
MANIFEST = USER_SKILLS / MANIFEST_NAME
# Dependency and cache folders only. NOT dist/ or build/: a skill may ship built files it runs from,
# and a copy missing them would install broken on every other PC.
EXCLUDE_PARTS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".cache", ".pytest_cache"}
TEXT = {".md", ".json", ".txt", ".yaml", ".yml", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".py", ".sh", ".ps1", ".toml",
        ".html", ".css", ".svg", ".env", ".ini", ".cfg"}
HIDDEN = re.compile("[​-‏‪-‮⁠-⁤﻿]")
MAX_BYTES = 5_000_000


def own_files(skill: Path) -> list[Path]:
    return sorted(p for p in skill.rglob("*") if p.is_file() and not (set(p.relative_to(skill).parts) & EXCLUDE_PARTS))


def scan(skill: Path, files: list[Path], patterns) -> list[str]:
    problems = []
    for p in files:
        rel = p.relative_to(skill).as_posix()
        if p.stat().st_size > MAX_BYTES:
            problems.append(f"{rel} is over 5 MB")
            continue
        if p.suffix.lower() in TEXT or p.name.startswith(".env"):
            t = p.read_text(encoding="utf-8", errors="replace")
            for pid, rx in patterns:
                if rx.search(t):
                    problems.append(f"{rel} matches secret pattern [{pid}]")
            if HIDDEN.search(t):
                problems.append(f"{rel} contains hidden/bidi Unicode")
    return problems


def ignored(repo_skills: Path) -> set[str]:
    f = repo_skills / ".adopt-ignore"
    if not f.exists():
        return set()
    return {l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}


def candidates(user_skills: Path, repo_skills: Path, manifest: Path) -> list[Path]:
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    managed = set(data.get("items", data.get("skills", [])))
    have = {p.name for p in repo_skills.iterdir() if p.is_dir()} if repo_skills.exists() else set()
    have |= {p.name for root in hc.skill_roots() if root.exists() for p in root.iterdir() if p.is_dir()}
    skip = ignored(repo_skills) | managed | have | {"capabilities"}
    return sorted(d for d in user_skills.iterdir() if d.is_dir() and d.name not in skip and (d / "SKILL.md").exists()) \
        if user_skills.exists() else []


def adopt(user_skills: Path | None = None, repo_skills: Path | None = None, manifest: Path = MANIFEST,
          dry_run: bool = False, today: str | None = None) -> dict:
    patterns = shim.load_patterns()
    result = {"adopted": [], "quarantined": {}, "skipped": {}}
    if repo_skills is None:
        pack = hc.primary_pack()
        if pack is None:
            result["error"] = "no brain pack configured - run: harnessd pack init <dir>"
            return result
        repo_skills = pack / "skills"
        repo_skills.mkdir(parents=True, exist_ok=True)
    sources = [(user_skills, manifest)] if user_skills is not None else [(d, d / MANIFEST_NAME) for d in USER_SKILL_DIRS]
    todo, seen = [], set()
    for src, man in sources:
        for c in candidates(src, repo_skills, man):
            if c.name not in seen:
                seen.add(c.name)
                todo.append(c)
    for skill in todo:
        fm = frontmatter((skill / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        if fm.get("name") != skill.name:
            result["skipped"][skill.name] = f"SKILL.md name '{fm.get('name')}' does not match the directory"
            continue
        if not fm.get("description"):
            result["skipped"][skill.name] = "SKILL.md has no description"
            continue
        files = own_files(skill)
        problems = scan(skill, files, patterns)
        if problems:
            result["quarantined"][skill.name] = problems[:10]
            continue
        if not dry_run:
            dest = repo_skills / skill.name
            for p in files:
                target = dest / p.relative_to(skill)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
            # First excluded folder on each path only - a `dist` nested inside node_modules is not a skill folder.
            excluded = sorted({next(part for part in p.relative_to(skill).parts if part in EXCLUDE_PARTS)
                               for p in skill.rglob("*") if set(p.relative_to(skill).parts) & EXCLUDE_PARTS})
            (dest / ".adopted.json").write_text(json.dumps({
                "source": f"~/{skill.parent.parent.name}/{skill.parent.name}/{skill.name}",
                "adopted": today or datetime.date.today().isoformat(),
                "files": len(files),
                "excluded": excluded,
                "license": fm.get("license", "unspecified"),
                "restore_dependencies": (skill / "package-lock.json").exists() or (skill / "requirements.txt").exists(),
            }, indent=2) + "\n", encoding="utf-8", newline="\n")
        result["adopted"].append(skill.name)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = adopt(dry_run=a.dry_run)
    if r.get("error"):
        print(json.dumps(r) if a.json else r["error"])
        return
    if a.json:
        print(json.dumps(r))
        return
    verb = "would adopt" if a.dry_run else "adopted"
    print(f"{verb}: {', '.join(r['adopted']) or 'nothing new'}")
    for name, why in r["quarantined"].items():
        print(f"QUARANTINED {name} (stays local):")
        for w in why:
            print(f"  {w}")
    for name, why in r["skipped"].items():
        print(f"skipped {name}: {why}")
    sys.exit(0)


if __name__ == "__main__":
    main()
