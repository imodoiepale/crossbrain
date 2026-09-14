"""
Bundled tools that make the skills concrete: graphify (code knowledge graph) and archify (diagrams).

  archify   vendored in vendor/archify and installed as an ordinary skill. It needs Node 18+ at run time
            and nothing else (no npm install). Enabled by "archify" in config "components".
  graphify  a Python package (graphifyy, Apache-2.0) with its own installer, so it is NOT vendored.
            On every install/sync crossbrain runs `python -m graphify install --platform <p>` for each
            agent CLI present on this machine, which keeps graphify's skill current everywhere.
            If the package is missing, crossbrain prints the command and moves on. It only pip-installs
            with --with-graphify, because that downloads and runs third-party code.

Neither tool can fail an install: a problem is reported, and everything else proceeds.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import hconfig as hc

GRAPHIFY_PACKAGE = "graphifyy"

# graphify --platform name -> directory whose existence means the agent CLI is present here.
# "agents" is the shared ~/.agents/skills folder (Codex, Cursor, Gemini CLI, OpenCode, Kimi Code).
GRAPHIFY_PLATFORMS = {
    "claude": ["~/.claude"],
    "codex": ["~/.codex"],
    "cursor": ["~/.cursor"],
    "gemini": ["~/.gemini"],
    "opencode": ["~/.config/opencode"],
    "kimi": ["~/.kimi", "~/.kimi-code"],
}


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- graphify

def graphify_available() -> bool:
    return importlib.util.find_spec("graphify") is not None


def graphify_version() -> str | None:
    if not graphify_available():
        return None
    try:
        from importlib.metadata import version
        return version(GRAPHIFY_PACKAGE)
    except Exception:
        return "unknown"


def graphify_platforms(cfg: dict) -> list[str]:
    present = [p for p, dirs in GRAPHIFY_PLATFORMS.items() if any(hc.expand(d).exists() for d in dirs)]
    if "agents" in cfg.get("skill_targets", []):
        present.append("agents")
    return present


def install_graphify(cfg: dict, log=print, allow_pip: bool = False, runner=run) -> dict:
    report = {"available": graphify_available(), "platforms": {}, "pip": None}
    if not report["available"] and allow_pip:
        r = runner([sys.executable, "-m", "pip", "install", "--upgrade", GRAPHIFY_PACKAGE])
        report["pip"] = "installed" if r.returncode == 0 else f"failed: {(r.stderr or r.stdout).strip().splitlines()[-1:]}"
        importlib.invalidate_caches()
        report["available"] = graphify_available() or r.returncode == 0
        log(f"  graphify pip install {GRAPHIFY_PACKAGE}: {report['pip']}")
    if not report["available"]:
        log(f"  graphify not installed - run `{Path(sys.executable).name} -m pip install {GRAPHIFY_PACKAGE}` "
            "or `crossbrain install --with-graphify`")
        return report
    for platform in graphify_platforms(cfg):
        r = runner([sys.executable, "-m", "graphify", "install", "--platform", platform])
        if r.returncode != 0:
            # On Windows, graphify's os.replace() of its references/ folder can hit WinError 5 while an
            # indexer still holds the temp dir, leaving an empty skill folder. Clear it and retry once.
            for base in hc.SKILL_TARGETS.values():
                leftover = hc.expand(base) / "graphify"
                if leftover.exists() and not (leftover / "SKILL.md").exists():
                    shutil.rmtree(leftover, ignore_errors=True)
            time.sleep(0.4)
            r = runner([sys.executable, "-m", "graphify", "install", "--platform", platform])
        report["platforms"][platform] = "ok" if r.returncode == 0 else "failed"
    ok = [p for p, s in report["platforms"].items() if s == "ok"]
    bad = [p for p, s in report["platforms"].items() if s != "ok"]
    log(f"  graphify {graphify_version()} -> {', '.join(ok) or 'no agent CLIs found'}"
        + (f"  (FAILED: {', '.join(bad)} - run `python -m graphify install --platform <p>`)" if bad else ""))
    return report


# ---------------------------------------------------------------- code graphs per repo

GRAPH_DIR = "graphify-out"


def _git(repo: Path, *args: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _run_in(args: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    # PYTHONHASHSEED=0 matches graphify's own hooks: louvain clustering is otherwise non-deterministic run to run.
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, env={**os.environ, "PYTHONHASHSEED": "0"})


def graph_status(repo: Path) -> dict:
    """missing | fresh | stale. Graphs built by recent graphify record `Built from commit: <sha>`, so staleness is an
    exact commit count; older reports only carry a date in their title, compared with the last commit date."""
    report = repo / GRAPH_DIR / "GRAPH_REPORT.md"
    if not report.exists():
        return {"status": "missing"}
    with open(report, encoding="utf-8", errors="replace") as f:
        head = f.read(4000)
    built = re.search(r"Built from commit:\s*`?([0-9a-f]{7,40})`?", head)
    if built:
        sha = built.group(1)
        behind = _git(repo, "rev-list", "--count", f"{sha}..HEAD")
        if behind.isdigit():
            n = int(behind)
            return {"status": "fresh" if n == 0 else "stale", "built_from": sha[:8], "behind": n}
        return {"status": "stale", "built_from": sha[:8], "behind": None}      # commit gone (rebase, shallow clone)
    dated = re.search(r"\((\d{4}-\d{2}-\d{2})\)", head.splitlines()[0] if head else "")
    last = _git(repo, "log", "-1", "--format=%cs")
    if dated and last:
        return {"status": "fresh" if dated.group(1) >= last else "stale", "built_on": dated.group(1), "behind": None}
    return {"status": "stale", "behind": None}


def graph_line(status: dict, available: bool) -> str:
    """One line for session cards and audit reports."""
    if not available:
        return "Code graph: graphify not installed - `crossbrain install --with-graphify`, then `python -m graphify update .`."
    s = status.get("status")
    if s == "fresh":
        return ("Code graph: fresh. Before writing code, ask it: `python -m graphify query \"<question>\"` "
                "(also `explain \"<Node>\"`, `path \"<A>\" \"<B>\"`).")
    if s == "stale":
        lag = f"{status['behind']} commit(s) behind HEAD" if status.get("behind") else \
              f"older than the latest commit (built {status.get('built_from') or status.get('built_on', '?')})"
        return (f"Code graph: STALE - {lag}. Run `python -m graphify update .` (no LLM) before trusting it; "
                "`crossbrain hooks install . --graph-only` keeps it fresh on every commit.")
    return ("Code graph: none yet. Run `python -m graphify update .` (no LLM) to build graphify-out/, then query it "
            "before writing code.")


def exclude_graph_output(repo: Path) -> bool:
    """Keep graphify-out/ out of `git status` without touching any tracked file: .git/info/exclude is local-only.
    Skipped when the repo deliberately commits its graph."""
    if not (repo / ".git").is_dir() or _git(repo, "ls-files", GRAPH_DIR):
        return False
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text(encoding="utf-8", errors="replace") if exclude.exists() else ""
    if any(line.strip().strip("/") == GRAPH_DIR for line in text.splitlines()):
        return False
    with open(exclude, "a", encoding="utf-8", newline="\n") as f:
        f.write(("\n" if text and not text.endswith("\n") else "")
                + f"# crossbrain: local code graph (graphify), rebuilt by git hooks\n{GRAPH_DIR}/\n")
    return True


def update_graph(repo: Path, runner=None, timeout: int = 1800) -> dict:
    if not graphify_available():
        return {"ok": False, "error": "graphify not installed"}
    exclude_graph_output(repo)
    args = [sys.executable, "-m", "graphify", "update", "."]
    try:
        r = runner(args, repo) if runner else _run_in(args, repo, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout}s"}
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["no output"]
        return {"ok": False, "error": tail[0][:200]}
    return {"ok": True, **graph_status(repo)}


def install_graph_hooks(repo: Path, uninstall: bool = False, runner=None) -> str:
    """graphify's own post-commit/post-checkout hooks rebuild the graph in the background (code only, no LLM).

    graphify also registers a graph.json merge driver by writing .gitattributes. That only helps a repo that commits
    its graph; for every other repo it would be a surprise change to a tracked file, so it is put back."""
    if not (repo / ".git").is_dir():
        return "not a git repo"
    if not graphify_available():
        return "graphify not installed"
    attrs = repo / ".gitattributes"
    before = attrs.read_bytes() if attrs.exists() else None
    commits_graph = bool(_git(repo, "ls-files", GRAPH_DIR))
    args = [sys.executable, "-m", "graphify", "hook", "uninstall" if uninstall else "install"]
    r = runner(args, repo) if runner else _run_in(args, repo, timeout=120)
    if not commits_graph:
        after = attrs.read_bytes() if attrs.exists() else None
        if after != before:
            if before is None:
                attrs.unlink()
            else:
                attrs.write_bytes(before)
    if r.returncode != 0:
        return "graph hooks FAILED: " + ((r.stderr or r.stdout).strip().splitlines() or ["no output"])[-1][:120]
    if uninstall:
        return "graph hooks removed"
    exclude_graph_output(repo)
    return "graph hooks installed"


# ---------------------------------------------------------------- archify

def archify_status(cfg: dict) -> dict:
    origin = hc.ENGINE / "vendor" / "archify" / "ORIGIN.json"
    node = shutil.which("node")
    node_version = run([node, "--version"]).stdout.strip() if node else None
    ok_node = bool(node_version) and int(node_version.lstrip("v").split(".")[0]) >= 18
    return {
        "enabled": "archify" in cfg.get("components", []),
        "vendored": origin.exists(),
        "ref": __import__("json").loads(origin.read_text(encoding="utf-8"))["ref"] if origin.exists() else None,
        "node": node_version,
        "node_ok": ok_node,
    }
