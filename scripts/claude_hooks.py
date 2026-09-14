"""
Register crossbrain's Claude Code hooks in ~/.claude/settings.json - idempotent, backed up, other hooks untouched.

    python scripts/claude_hooks.py                # install all hooks crossbrain owns
    python scripts/claude_hooks.py --uninstall

  SessionStart                               brain_hook.py        repo card + graph status
  PreToolUse  Read|Glob|Grep|Bash            graph_guard.py       ask the code graph before reading (once/session)
  PostToolUse Edit|Write|MultiEdit|NotebookEdit  graph_autoupdate.py  background incremental graph rebuild

The graph hooks are registered only when "graphify" is in config components. Each hook is recognised by its
script name, so re-running replaces nothing it does not own and never duplicates.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hconfig as hc  # noqa: E402

SETTINGS = Path.home() / ".claude" / "settings.json"
SCRIPTS = Path(__file__).resolve().parent

HOOKS = [
    # (event, matcher or None, script, timeout seconds, needs graphify component)
    ("SessionStart", None, "brain_hook.py", 10, False),
    ("PreToolUse", "Read|Glob|Grep|Bash", "graph_guard.py", 5, True),
    ("PostToolUse", "Edit|Write|MultiEdit|NotebookEdit", "graph_autoupdate.py", 5, True),
]


def ours(group: dict, script: str) -> bool:
    return any(script in h.get("command", "") for h in group.get("hooks", []))


def apply(data: dict, cfg: dict, uninstall: bool = False) -> list[str]:
    changes = []
    hooks = data.setdefault("hooks", {})
    for event, matcher, script, timeout, needs_graph in HOOKS:
        groups = hooks.setdefault(event, [])
        kept = [g for g in groups if not ours(g, script)]
        present = len(kept) != len(groups)
        wanted = not uninstall and (not needs_graph or "graphify" in cfg.get("components", []))
        if wanted:
            entry = {"hooks": [{"type": "command", "command": f'"{sys.executable}" "{SCRIPTS / script}"', "timeout": timeout}]}
            if matcher:
                entry = {"matcher": matcher, **entry}
            if present and [g for g in groups if ours(g, script)] == [entry]:
                continue
            kept.append(entry)
            changes.append(f"{'updated' if present else 'added'} {event} {script}")
        elif present:
            changes.append(f"removed {event} {script}")
        hooks[event] = kept
        if not kept:
            del hooks[event]
    return changes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args(argv)
    data = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    changes = apply(data, hc.load(), uninstall=a.uninstall)
    if not changes:
        print("claude hooks already current")
        return 0
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_suffix(".json.bak-crossbrain"))
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("claude hooks: " + "; ".join(changes) + f" (backup: {SETTINGS.name}.bak-crossbrain)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
