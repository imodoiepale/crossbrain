#!/usr/bin/env python3
"""
crossbrain - one brain for every coding agent.

  install                 install skills, agents and instructions into every agent CLI on this machine
  sync [--no-push]        pull, test, adopt hand-added skills, install, rebuild, report drift
  schedule on|off         run sync daily and at logon
  doctor                  show detected agent CLIs, targets, packs and health
  pack init|add <dir>     create or attach a brain pack (your private skills and lessons)
  config [key [value]]    read or change ~/.crossbrain/config.json

  intake-scan <repo>      deterministic architecture + security + hygiene audit (alias: audit)
  mine [--out DIR]        turn every repo's git history into redacted digests
  brain                   rebuild the brain map from repo-* skills
  capabilities [--check|--local]   rebuild the master capabilities index
  adopt [--dry-run]       adopt hand-added skills into your primary pack
  ecc search|show|use|drop|list    work with the vendored ECC library
  preflight [--staged] [path]      the commit gate
  hooks install|uninstall [path|--all]   the gate as a git pre-commit hook
  shim [--port N]         the secret-redacting proxy for agent memory services
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE / "scripts"))

import hconfig as hc  # noqa: E402

PASSTHROUGH = {
    "intake-scan": "project_audit.py", "audit": "project_audit.py", "mine": "mine_repo_history.py",
    "brain": "build_brain.py", "capabilities": "build_capabilities.py", "adopt": "adopt_skills.py",
    "ecc": "ecc.py", "preflight": "preflight.py", "shim": "memory_redact_shim.py", "drift": "knowledge_drift.py",
}
CLIS = {"claude": "Claude Code", "codex": "Codex", "cursor": "Cursor", "gemini": "Gemini CLI",
        "opencode": "OpenCode", "kimi": "Kimi Code"}


def doctor() -> int:
    cfg = hc.load()
    print(f"crossbrain engine   {hc.ENGINE}")
    print(f"config            {hc.CONFIG} ({'present' if hc.CONFIG.exists() else 'defaults'})")
    print(f"python            {platform.python_version()}  git {'yes' if shutil.which('git') else 'MISSING'}")
    print(f"projects_root     {hc.projects_root(cfg)}")
    print("\nagent CLIs")
    for exe, name in CLIS.items():
        found = shutil.which(exe)
        mark = "+" if found else "-"   # ASCII: Windows consoles default to cp1252
        print(f"  {mark} {name:<12} {found or 'not on PATH'}")
    print("\nskill targets")
    for t in cfg["skill_targets"]:
        d = hc.expand(hc.SKILL_TARGETS[t])
        n = len([p for p in d.iterdir() if (p / "SKILL.md").exists()]) if d.exists() else 0
        print(f"  {t:<9} {d}  ({n} skills)")
    print("\nbrain packs")
    for p in hc.packs(cfg) or []:
        mark = "+" if p.exists() else "MISSING"
        print(f"  {mark} {p}")
    if not cfg["packs"]:
        print("  none - run `crossbrain pack init ~/my-brain` to keep your own skills and lessons")
    hook = hc.expand("~/.claude/settings.json")
    hooked = hook.exists() and "brain_hook.py" in hook.read_text(encoding="utf-8", errors="replace")
    print(f"\nClaude SessionStart brain hook: {'installed' if hooked else 'not installed'}")
    return 0


def pack_cmd(args: list[str]) -> int:
    if len(args) != 2 or args[0] not in ("init", "add"):
        print("usage: crossbrain pack init|add <dir>")
        return 2
    d = hc.expand(args[1]).resolve()
    cfg = hc.load()
    if args[0] == "init":
        for sub in ("skills", "agents", "brain", "memory"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        (d / ".gitignore").write_text("digests/\nnode_modules/\n.env\n.env.*\n!.env.example\n", encoding="utf-8")
        (d / "README.md").write_text(
            "# My crossbrain brain pack\n\nPrivate knowledge for [crossbrain](https://github.com/imodoiepale/crossbrain):\n\n"
            "- `skills/repo-*`: one skill per repo, distilled from its history (`crossbrain mine`, then the `history-to-skills` skill)\n"
            "- `skills/<name>`: skills adopted from any of your machines by `crossbrain sync`\n"
            "- `brain/`: generated map (`crossbrain brain`)\n\nKeep this repository **private**.\n", encoding="utf-8")
        (d / "skills" / ".adopt-ignore").write_text("# skills owned by their own installers\ngraphify\n", encoding="utf-8")
        if not (d / ".git").exists():
            subprocess.run(["git", "init", "-q", str(d)], check=False)
            # Start clean: sync only commits adoptions into a pack with no uncommitted changes.
            subprocess.run(["git", "-C", str(d), "add", "-A"], check=False)
            first = subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", "chore: initialise crossbrain brain pack"],
                                   capture_output=True, text=True)
            if first.returncode != 0:
                # Usually no git identity. Left uncommitted, sync would treat the pack as dirty and never commit adoptions.
                print("  warn: could not make the pack's first commit - set git user.name and user.email, then run:\n"
                      f"        git -C \"{d}\" commit -m \"chore: initialise crossbrain brain pack\"")
    elif not d.exists():
        print(f"{d} does not exist")
        return 1
    if str(d) not in [str(p) for p in hc.packs(cfg)]:
        cfg["packs"] = cfg["packs"] + [str(d)]
        hc.save(cfg)
    print(f"pack {args[0]}: {d}  (primary pack: {hc.primary_pack(cfg)})")
    return 0


def config_cmd(args: list[str]) -> int:
    cfg = hc.load()
    if not args:
        print(json.dumps(cfg, indent=2))
    elif len(args) == 1:
        print(json.dumps(cfg.get(args[0]), indent=2))
    else:
        key, value = args[0], " ".join(args[1:])
        try:
            cfg[key] = json.loads(value)
        except ValueError:
            cfg[key] = value
        hc.save(cfg)
        print(f"{key} = {json.dumps(cfg[key])}")
    return 0


def hooks_cmd(args: list[str]) -> int:
    import install as inst
    if not args or args[0] not in ("install", "uninstall"):
        print("usage: crossbrain hooks install|uninstall [path|--all]")
        return 2
    uninstall = args[0] == "uninstall"
    if "--all" in args:
        root = hc.projects_root()
        repos = [p for p in sorted(root.iterdir()) if (p / ".git").is_dir()] if root.exists() else []
    else:
        repos = [Path(args[1] if len(args) > 1 else ".").resolve()]
    for r in repos:
        print(f"  {inst.install_git_hook(r, uninstall):<22} {r}")
    return 0


def main(argv: list[str]) -> int:
    # Skill descriptions and repo names can hold any Unicode; never crash a cp1252 console over one.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in PASSTHROUGH:
        return subprocess.call([sys.executable, str(ENGINE / "scripts" / PASSTHROUGH[cmd]), *rest])
    if cmd == "install":
        import install as inst
        cfg = hc.load()
        if "--targets" in rest:
            cfg["skill_targets"] = rest[rest.index("--targets") + 1].split(",")
        print("crossbrain install")
        inst.install(cfg, dry_run="--dry-run" in rest)
        print("\nDone. Start a new agent session to load the skills. Next: `crossbrain doctor`, `crossbrain schedule on`.")
        return 0
    if cmd == "sync":
        import sync
        return sync.sync(push="--no-push" not in rest, quiet="--quiet" in rest)
    if cmd == "schedule":
        import sync
        return sync.schedule(on=(rest[:1] == ["on"]))
    if cmd == "doctor":
        return doctor()
    if cmd == "pack":
        return pack_cmd(rest)
    if cmd == "config":
        return config_cmd(rest)
    if cmd == "hooks":
        return hooks_cmd(rest)
    print(f"unknown command '{cmd}'\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
