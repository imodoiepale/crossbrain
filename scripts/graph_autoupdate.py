"""
Keep a repo's code graph current after small changes - not just on commit.

Claude Code PostToolUse hook (Edit | Write | MultiEdit | NotebookEdit):
    python graph_autoupdate.py            # reads the hook event on stdin, returns immediately

Worker (spawned detached by the hook, never run by hand):
    python graph_autoupdate.py --worker <repo>

Rules:
  - only repos that already have graphify-out/ (building a first graph is `crossbrain graph update` or the
    post-commit hook, not a side effect of one edit)
  - never in a repo that commits graphify-out/: each rebuild would dirty tracked files
  - debounced: one background `graphify update .` at a time per repo, at most one per MIN_INTERVAL; edits that land
    while it runs set a pending flag, and the worker does exactly one more pass for them
  - graphify update is incremental (manifest gate), code only, no LLM

The hook itself does no graph work, so it never slows the agent down. Fails open.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hconfig as hc  # noqa: E402

MIN_INTERVAL = 60                 # seconds between rebuild starts in one repo
STALE_LOCK = 30 * 60              # a lock older than this belongs to a crashed worker
LOCK, PENDING = ".crossbrain-update.lock", ".crossbrain-update.pending"


def repo_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def commits_graph(repo: Path) -> bool:
    r = subprocess.run(["git", "-C", str(repo), "ls-files", "graphify-out"], capture_output=True, text=True)
    return bool(r.stdout.strip())


def plan(event: dict, now: float | None = None) -> tuple[str, Path | None]:
    """('spawn'|'pending'|'skip:<why>', repo). Side effects limited to the pending flag."""
    now = now or time.time()
    tin = event.get("tool_input") or {}
    target = tin.get("file_path") or tin.get("notebook_path") or ""
    cwd = Path(event.get("cwd") or ".")
    path = Path(target) if target and Path(target).is_absolute() else (cwd / target if target else cwd)
    repo = repo_root(path.parent if path.suffix or not path.is_dir() else path)
    if repo is None:
        return "skip:not a git repo", None
    out = repo / "graphify-out"
    if not out.is_dir():
        return "skip:no graph yet", repo
    try:
        rel = path.resolve().relative_to(repo.resolve())
        if rel.parts and rel.parts[0] == "graphify-out":
            return "skip:graph output edited", repo
    except ValueError:
        pass
    if commits_graph(repo):
        return "skip:repo commits its graph", repo
    lock = out / LOCK
    if lock.exists():
        age = now - lock.stat().st_mtime
        if age < STALE_LOCK:
            (out / PENDING).write_text(str(now), encoding="utf-8")
            return "pending", repo
    last = out / ".crossbrain-update.last"
    if last.exists() and now - last.stat().st_mtime < MIN_INTERVAL:
        (out / PENDING).write_text(str(now), encoding="utf-8")
        return "pending", repo
    return "spawn", repo


def spawn(repo: Path) -> None:
    out = repo / "graphify-out"
    (out / LOCK).write_text(str(os.getpid()), encoding="utf-8")
    args = [sys.executable, str(Path(__file__).resolve()), "--worker", str(repo)]
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL, "cwd": str(repo)}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)


def worker(repo: Path, runner=None) -> int:
    out = repo / "graphify-out"
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    if os.name == "nt":
        env.setdefault("GRAPHIFY_MAX_WORKERS", "1")
    passes = 0
    try:
        while True:
            (out / PENDING).unlink(missing_ok=True)
            started = time.time()
            (out / ".crossbrain-update.last").write_text(str(started), encoding="utf-8")
            args = [sys.executable, "-m", "graphify", "update", "."]
            if runner:
                runner(args, repo)
            else:
                with open(hc.state_dir() / "graph-autoupdate.log", "a", encoding="utf-8") as log:
                    log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} update {repo}\n")
                    subprocess.run(args, cwd=str(repo), env=env, stdout=log, stderr=log, timeout=1800)
            passes += 1
            if not (out / PENDING).exists() or passes >= 3:
                return passes
    finally:
        (out / LOCK).unlink(missing_ok=True)


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]))
        return
    try:
        event = json.load(sys.stdin)
        if "graphify" not in hc.load().get("components", []):
            return
        import components
        if not components.graphify_available():
            return
        action, repo = plan(event)
        if action == "spawn" and repo is not None:
            spawn(repo)
    except Exception:
        return


if __name__ == "__main__":
    main()
