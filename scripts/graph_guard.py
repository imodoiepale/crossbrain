"""
Claude Code PreToolUse hook (Read | Glob | Grep | Bash): nudge the agent to ask the code graph before reading
or searching files. That is where the tokens go: a scoped `graphify query` answer is usually far smaller than the
files it replaces.

Nudge, never block:
  - only in a repo that has graphify-out/graph.json
  - at most ONCE per session per repo (a reminder on every Read would itself waste the tokens it tries to save)
  - skipped once the agent has already run `graphify query|explain|path` in that repo this session

Portable: installed globally per machine by crossbrain, so nothing machine-specific is committed into any repo.
Fails open: any error -> no output, exit 0.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hconfig as hc  # noqa: E402

GRAPH_TOOLS = re.compile(r"\bgraphify\b.*\b(query|explain|path)\b")
SEARCH_BASH = re.compile(r"(^|[\s|;&(])(rg|grep|ag|find|fd|cat|head|tail|less|type|Get-Content|Select-String)(\s|$)")
MAX_AGE = 12 * 3600      # forget session markers after 12h


def repo_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def marker(session: str, repo: Path) -> Path:
    key = hashlib.sha256(f"{session}|{repo}".encode("utf-8")).hexdigest()[:24]
    return hc.state_dir() / "graph-guard" / key


def decide(event: dict) -> str | None:
    """Return the nudge text, or None. Pure except for the per-session marker files."""
    tool = event.get("tool_name", "")
    tin = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or ".")
    session = str(event.get("session_id") or "no-session")
    command = tin.get("command", "") if tool == "Bash" else ""

    target = tin.get("file_path") or tin.get("path") or ""
    base = Path(target) if target and Path(target).is_absolute() else cwd
    repo = repo_root(base if base.is_dir() else base.parent) or repo_root(cwd)
    if repo is None or not (repo / "graphify-out" / "graph.json").exists():
        return None

    mark = marker(session, repo)
    if tool == "Bash" and GRAPH_TOOLS.search(command):
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text("queried", encoding="utf-8")          # the agent is already using the graph
        return None
    if tool == "Bash" and not SEARCH_BASH.search(command):
        return None                                           # builds, tests, git: not a read
    if mark.exists() and time.time() - mark.stat().st_mtime < MAX_AGE:
        return None
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text("nudged", encoding="utf-8")
    return (f"[crossbrain] {repo.name} has a code graph. Before reading or searching files, ask it: "
            "`python -m graphify query \"<question>\"` (or `explain \"<Node>\"`, `path \"<A>\" \"<B>\"`). "
            "It returns a scoped subgraph, far fewer tokens than raw files. Read files directly only for what it does not answer. "
            "(Shown once per session.)")


def main():
    try:
        event = json.load(sys.stdin)
        if "graphify" not in hc.load().get("components", []):
            return
        text = decide(event)
    except Exception:
        return
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}))


if __name__ == "__main__":
    main()
