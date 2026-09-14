"""
Register brain_hook.py as a Claude Code SessionStart hook in ~/.claude/settings.json.

    python scripts/install_brain_hook.py              # install (idempotent)
    python scripts/install_brain_hook.py --uninstall

Backs settings.json up first and leaves every other hook untouched - clobbering someone's existing
hooks would silently switch them off.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"
HOOK = Path(__file__).resolve().parent / "brain_hook.py"
MARK = "brain_hook.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()

    data = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    groups = data.setdefault("hooks", {}).setdefault("SessionStart", [])
    kept = [g for g in groups if not any(MARK in h.get("command", "") for h in g.get("hooks", []))]
    removed = len(groups) - len(kept)

    if a.uninstall:
        if not removed:
            print("brain hook not installed - nothing to do")
            return 0
        data["hooks"]["SessionStart"] = kept
    else:
        if removed:
            print("brain hook already installed")
            return 0
        # The interpreter that ran the installer: `python` is not on PATH everywhere (macOS ships python3).
        kept.append({"hooks": [{"type": "command", "command": f'"{sys.executable}" "{HOOK}"', "timeout": 10}]})
        data["hooks"]["SessionStart"] = kept

    if not data["hooks"]["SessionStart"]:
        del data["hooks"]["SessionStart"]
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_suffix(".json.bak-crossbrain"))
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(("uninstalled" if a.uninstall else "installed") + f" brain hook in {SETTINGS} (backup: settings.json.bak-crossbrain)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
