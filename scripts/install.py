"""
Install harnessd into every agent CLI on this machine.

    python harnessd.py install                    # skills + agents + instruction blocks + Claude hook
    python harnessd.py install --dry-run
    python harnessd.py hooks install [--all]      # the preflight gate as a git pre-commit hook

What goes where (targets come from ~/.harnessd/config.json - see hconfig.py):
  skills        engine skills + every pack's skills -> each skill target (~/.claude/skills, ~/.agents/skills, ...)
  agents        engine + pack agents/*.md           -> ~/.claude/agents (Claude Code subagents)
  instructions  a marked block in ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md, ...
  hook          SessionStart brain card for Claude Code

Only things harnessd installed are ever replaced or removed (per-target manifest). A skill's own
node_modules survives reinstalls, because adopted skills are stored without dependencies.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import hconfig as hc

MANIFEST = ".harnessd-manifest.json"
BLOCK_BEGIN, BLOCK_END = "<!-- harnessd:begin -->", "<!-- harnessd:end -->"
IGNORE = shutil.ignore_patterns("node_modules", ".git", "__pycache__", ".venv")

INSTRUCTIONS = """{begin}
## harnessd

Skills from harnessd are installed. Before any coding task:

1. `brain`: identify the project and load its `repo-*` skill if one exists.
2. `capabilities`: the index of everything available (skills, the full ECC library, commands, rule packs). Read a matching skill before writing something from scratch.
3. `project-intake`: for any unfamiliar, inherited or client project, or any "audit / is this safe / what's the architecture" request.
4. Never paste or echo a secret. Commit through the preflight gate (`harnessd preflight --staged`).
{end}
"""


def collect(roots: list[Path], pattern: str) -> dict[str, Path]:
    """name -> source. Later roots win, so a pack can override an engine item."""
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.glob(pattern)):
            if pattern == "*" and p.is_dir() and (p / "SKILL.md").exists():
                found[p.name] = p
            elif pattern != "*" and p.is_file():
                found[p.name] = p
    return found


def copy_skill(src: Path, dest: Path) -> None:
    parked = None
    if (dest / "node_modules").exists():
        parked = dest.parent / f".harnessd-nm-{dest.name}"
        if parked.exists():
            shutil.rmtree(parked)
        (dest / "node_modules").rename(parked)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=IGNORE)
    if parked:
        parked.rename(dest / "node_modules")


def read_manifest(folder: Path) -> list[str]:
    f = folder / MANIFEST
    return json.loads(f.read_text(encoding="utf-8")).get("items", []) if f.exists() else []


def write_manifest(folder: Path, items: list[str]) -> None:
    (folder / MANIFEST).write_text(json.dumps({"items": sorted(items)}, indent=2) + "\n", encoding="utf-8")


def upsert_block(path: Path, block: str) -> str:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if BLOCK_BEGIN in text and BLOCK_END in text:
        start, end = text.index(BLOCK_BEGIN), text.index(BLOCK_END) + len(BLOCK_END)
        new = text[:start] + block.strip() + text[end:]
    else:
        new = (text.rstrip() + "\n\n" if text.strip() else "") + block.strip() + "\n"
    if new == text:
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8", newline="\n")
    return "updated" if text else "created"


def install(cfg: dict | None = None, dry_run: bool = False, log=print) -> dict:
    cfg = cfg or hc.load()
    skills = collect(hc.skill_roots(cfg), "*")
    report = {"skills": len(skills), "targets": [], "agents": 0, "instructions": {}}

    for target in hc.skill_target_dirs(cfg):
        previous = set(read_manifest(target))
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            for name, src in skills.items():
                copy_skill(src, target / name)
            for gone in previous - set(skills):          # removed from engine/packs since last install
                if (target / gone).exists():
                    shutil.rmtree(target / gone)
            write_manifest(target, list(skills))
        report["targets"].append(str(target))
        log(f"  skills  {len(skills):>3} -> {target}")

    if "claude" in cfg["skill_targets"]:
        agents = collect(hc.agent_roots(cfg), "*.md")
        dest = hc.expand("~/.claude/agents")
        if not dry_run and agents:
            dest.mkdir(parents=True, exist_ok=True)
            for gone in set(read_manifest(dest)) - set(agents):
                (dest / gone).unlink(missing_ok=True)
            for name, src in agents.items():
                shutil.copy2(src, dest / name)
            write_manifest(dest, list(agents))
        report["agents"] = len(agents)
        log(f"  agents  {len(agents):>3} -> {dest}")

    block = INSTRUCTIONS.format(begin=BLOCK_BEGIN, end=BLOCK_END)
    for name in cfg["instruction_targets"]:
        if name not in hc.INSTRUCTION_TARGETS:
            continue
        path = hc.expand(hc.INSTRUCTION_TARGETS[name])
        # Only write where the tool is actually present, so we never create config for a CLI you don't use.
        if not path.parent.exists():
            report["instructions"][name] = "skipped (tool not found)"
            continue
        report["instructions"][name] = "dry-run" if dry_run else upsert_block(path, block)
        log(f"  rules   {name:<8} {report['instructions'][name]} ({path})")

    if not dry_run:
        for script, args in (("build_capabilities.py", ["--local"]), ("build_brain.py", [])):
            subprocess.run([sys.executable, str(hc.ENGINE / "scripts" / script), *args], check=False)
        if "claude" in cfg["skill_targets"] and hc.expand("~/.claude").exists():
            subprocess.run([sys.executable, str(hc.ENGINE / "scripts" / "install_brain_hook.py")], check=False)
    return report


# ---------------------------------------------------------------- git pre-commit hooks

HOOK = """#!/bin/sh
# harnessd preflight gate (installed by `harnessd hooks install`)
PY=$(command -v python3 || command -v python)
"$PY" "{script}" --staged . || exit 1
"""


def install_git_hook(repo: Path, uninstall: bool = False) -> str:
    hooks = repo / ".git" / "hooks"
    if not hooks.exists():
        return "not a git repo"
    hook, backup = hooks / "pre-commit", hooks / "pre-commit.harnessd-backup"
    ours = hook.exists() and "harnessd preflight gate" in hook.read_text(encoding="utf-8", errors="replace")
    if uninstall:
        if not ours:
            return "not installed"
        hook.unlink()
        if backup.exists():
            backup.rename(hook)
        return "removed"
    if ours:
        return "already installed"
    if hook.exists():
        hook.rename(backup)
    hook.write_text(HOOK.format(script=(hc.ENGINE / "scripts" / "preflight.py").as_posix()), encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return "installed" + (" (previous hook kept as pre-commit.harnessd-backup)" if backup.exists() else "")
