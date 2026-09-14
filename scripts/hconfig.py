"""
crossbrain configuration: where the engine lives, where your brain packs are, which agent CLIs to feed.

    ~/.crossbrain/config.json      (override the directory with CROSSBRAIN_HOME)

{
  "projects_root": "~/Documents/GitHub",   # where your repos are checked out (brain hook, audit, mining)
  "packs": ["~/code/my-brain"],            # brain packs: YOUR skills, lessons, brain map. Usually private.
  "skill_targets": ["claude", "agents"],   # where skills are installed (see SKILL_TARGETS)
  "instruction_targets": ["claude", "codex", "gemini"]
}

Engine vs pack: the engine (this repo) is generic and public. A pack is a separate git repo holding
what is specific to you: repo-* skills mined from your history, adopted skills, your lessons, the
generated brain. Engine updates never conflict with your knowledge, and nothing personal can end up
in the public engine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("CROSSBRAIN_HOME", Path.home() / ".crossbrain")).expanduser()
CONFIG = HOME / "config.json"

# Global skill folders each agent CLI reads (verified against each tool's docs, 2026-09 - see docs/HARNESSES.md).
# "claude" and "agents" together reach all of them:
#   ~/.claude/skills  -> Claude Code, OpenCode, Kimi Code
#   ~/.agents/skills  -> Codex, Cursor, Gemini CLI, OpenCode, Kimi Code
SKILL_TARGETS = {
    "claude": "~/.claude/skills",
    "agents": "~/.agents/skills",
    "codex": "~/.codex/skills",
    "cursor": "~/.cursor/skills",
    "gemini": "~/.gemini/skills",
    "opencode": "~/.config/opencode/skills",
    "kimi": "~/.kimi/skills",
}

# Global instruction files. crossbrain writes a marked block and never touches the rest of the file.
# opencode is deliberately NOT a default: OpenCode only falls back to ~/.claude/CLAUDE.md when its own
# AGENTS.md is absent, so creating one would silently drop your Claude rules from OpenCode.
INSTRUCTION_TARGETS = {
    "claude": "~/.claude/CLAUDE.md",
    "codex": "~/.codex/AGENTS.md",
    "gemini": "~/.gemini/GEMINI.md",
    "opencode": "~/.config/opencode/AGENTS.md",
}

DEFAULTS = {
    "projects_root": "~/Documents/GitHub" if (Path.home() / "Documents" / "GitHub").exists() else "~/code",
    "packs": [],
    "skill_targets": ["claude", "agents"],
    "instruction_targets": ["claude", "codex", "gemini"],
}


def expand(p: str | Path) -> Path:
    return Path(os.path.expandvars(str(p))).expanduser()


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    return cfg


def save(cfg: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8", newline="\n")


def packs(cfg: dict | None = None) -> list[Path]:
    return [expand(p) for p in (cfg or load())["packs"]]


def primary_pack(cfg: dict | None = None) -> Path | None:
    ps = packs(cfg)
    return ps[0] if ps else None


def skill_roots(cfg: dict | None = None) -> list[Path]:
    """Engine first, then packs. When two roots hold the same skill name, the later root wins,
    so a pack can override an engine skill with its own version."""
    return [ENGINE / "skills"] + [p / "skills" for p in packs(cfg) if (p / "skills").exists()]


def agent_roots(cfg: dict | None = None) -> list[Path]:
    return [ENGINE / "agents"] + [p / "agents" for p in packs(cfg) if (p / "agents").exists()]


def projects_root(cfg: dict | None = None) -> Path:
    return expand(os.environ.get("CROSSBRAIN_PROJECTS") or (cfg or load())["projects_root"])


def brain_dir(cfg: dict | None = None) -> Path:
    pack = primary_pack(cfg)
    return (pack / "brain") if pack else (HOME / "state" / "brain")


def state_dir() -> Path:
    d = HOME / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def skill_target_dirs(cfg: dict | None = None) -> list[Path]:
    return [expand(SKILL_TARGETS[t]) for t in (cfg or load())["skill_targets"] if t in SKILL_TARGETS]
