"""
Keep this machine identical to every other machine, and let the knowledge grow.

    python harnessd.py sync             # once
    python harnessd.py sync --no-push   # commit adoptions locally but do not push
    python harnessd.py schedule on      # daily + at logon (Windows Task Scheduler / cron)

Git is the sync channel. Every machine runs the same loop:

  1. pull the engine and every brain pack (fast-forward only; trees with your own uncommitted edits are left alone)
  2. run the engine's own tests; if any fail, STOP - never install from a broken checkout
  3. adopt skills you added by hand (~/.claude/skills, ~/.agents/skills): scan -> copy into your primary pack
  4. install skills, agents and instructions into every agent CLI; rebuild brain and capabilities
  5. commit what sync itself owns in the pack (generated brain/, adopted skills) -> preflight -> push
  6. write the drift report: repos whose fixes landed after their skill, and ECC upstream moves

Ownership, not cleanliness, decides what sync may commit. brain/ is generated and skills carrying an
.adopted.json were adopted by sync; those are sync's to commit. Anything else uncommitted in the pack is
your work in progress, and its presence blocks the automatic commit - sync never commits your edits.

Knowledge enters only through git. Nothing is synced from session transcripts, so nothing a session
saw (keys included) spreads by itself.
"""

from __future__ import annotations

import datetime
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import hconfig as hc

TASK = "harnessd-sync"


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(repo), *args])


def dirty_paths(repo: Path) -> list[str]:
    out = git(repo, "status", "--porcelain", "--untracked-files=all").stdout
    return [l[3:].strip().strip('"').replace("\\", "/") for l in out.splitlines() if l.strip()]


def owned_by_sync(pack: Path, path: str) -> bool:
    """brain/ is generated output; skills/<name>/ with .adopted.json was put there by adoption."""
    if path.startswith("brain/"):
        return True
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "skills" and (pack / "skills" / parts[1] / ".adopted.json").exists()


def foreign_changes(pack: Path) -> list[str]:
    return [p for p in dirty_paths(pack) if not owned_by_sync(pack, p)]


def pull(repo: Path, allow_owned: bool = False) -> str:
    if not (repo / ".git").exists():
        return "not a git repo"
    dirty = dirty_paths(repo)
    if dirty and not (allow_owned and not foreign_changes(repo)):
        return "has uncommitted changes of yours - pull skipped"
    if dirty:
        return "sync-owned changes pending commit - pull after commit"
    if not git(repo, "remote").stdout.strip():
        return "no remote"
    r = git(repo, "pull", "--ff-only", "--quiet")
    return f"@ {git(repo, 'rev-parse', '--short', 'HEAD').stdout.strip()}" if r.returncode == 0 else "pull failed (diverged?)"


def commit_owned_changes(pack: Path, adopted: list[str], push: bool = True) -> str:
    """Commit generated brain/ and adopted skills. Refuses if the pack holds changes sync does not own."""
    if not (pack / ".git").exists():
        return "pack is not a git repo - nothing committed"
    pending = dirty_paths(pack)
    if not pending:
        return "nothing to commit"
    foreign = foreign_changes(pack)
    if foreign:
        return f"not committed: the pack has uncommitted changes of yours ({', '.join(foreign[:3])}{'…' if len(foreign) > 3 else ''})"
    git(pack, "add", "-A", "--", *sorted({p.split("/")[0] + ("/" + p.split("/")[1] if p.startswith("skills/") else "") for p in pending}))
    gate = run([sys.executable, str(hc.ENGINE / "scripts" / "preflight.py"), "--staged", "--allow-protected-branch", str(pack)])
    if gate.returncode != 0:
        git(pack, "reset", "--quiet")
        return "commit REFUSED by preflight - changes left unstaged for review:\n" + gate.stdout.strip()
    skills = sorted({p.split("/")[1] for p in pending if p.startswith("skills/")})
    subject = f"feat(skills): adopt {', '.join(skills)}" if skills else "chore(brain): rebuild brain map"
    body = (f"Committed by harnessd sync on {platform.node()} after the supply-chain scan and preflight passed.\n"
            "Dependency folders are never adopted; see each skill's .adopted.json.")
    c = git(pack, "commit", "--quiet", "-m", subject + "\n\n" + body)
    if c.returncode != 0:
        return f"commit failed: {(c.stderr or c.stdout).strip().splitlines()[-1] if (c.stderr or c.stdout).strip() else 'unknown error'}"
    if not push:
        return f"committed (not pushed): {subject}"
    if not git(pack, "remote").stdout.strip():
        return f"committed (no remote to push to): {subject}"
    p = git(pack, "push", "--quiet")
    if p.returncode != 0:                       # remote moved: replay our commit on top once, then retry
        if git(pack, "pull", "--rebase", "--quiet").returncode == 0:
            p = git(pack, "push", "--quiet")
    return f"committed + {'pushed' if p.returncode == 0 else 'push failed, retries next sync'}: {subject}"


def sync(push: bool = True, quiet: bool = False) -> int:
    cfg = hc.load()
    log_file = hc.state_dir() / "sync.log"

    def say(msg: str) -> None:
        if not msg:
            return
        line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        if not quiet:
            print("  " + msg)

    say(f"sync start on {platform.node()}")
    say(f"engine {pull(hc.ENGINE)}")
    for pack in hc.packs(cfg):
        say(f"pack {pack.name} {pull(pack, allow_owned=True)}")

    tests = run([sys.executable, "-m", "unittest", "discover", "-s", str(hc.ENGINE / "scripts"), "-p", "test_*.py"])
    if tests.returncode != 0:
        say("ABORT engine tests failed - refusing to install from a broken checkout")
        say(tests.stderr.strip().splitlines()[-1] if tests.stderr.strip() else "")
        return 1
    say("gates pass")

    pack = hc.primary_pack(cfg)
    adopted: list[str] = []
    if pack:
        r = run([sys.executable, str(hc.ENGINE / "scripts" / "adopt_skills.py"), "--json"])
        try:
            res = json.loads(r.stdout)
        except ValueError:
            res = {"adopted": [], "quarantined": {}, "skipped": {}}
            say("adopt: unreadable output, skipped")
        for name, why in res.get("quarantined", {}).items():
            say(f"QUARANTINED {name} (stays local): {'; '.join(why)}")
        adopted = res.get("adopted", [])
        if adopted:
            say(f"adopted into {pack.name}: {', '.join(adopted)}")
    else:
        say("no brain pack configured - hand-added skills are not shared (harnessd pack init <dir>)")

    import install as inst
    inst.install(cfg, log=lambda m: say(m.strip()))

    if pack:
        say(f"pack {pack.name}: {commit_owned_changes(pack, adopted, push=push)}")
        if not dirty_paths(pack):
            say(f"pack {pack.name} {pull(pack)}")
    say(run([sys.executable, str(hc.ENGINE / "scripts" / "knowledge_drift.py")]).stdout.strip())
    say("sync done")
    return 0


def schedule(on: bool) -> int:
    cmd = f'"{sys.executable}" "{hc.ENGINE / "harnessd.py"}" sync --quiet'
    if platform.system() == "Windows":
        if not on:
            for name in (TASK, f"{TASK}-logon"):
                run(["schtasks", "/Delete", "/TN", name, "/F"])
            print("scheduled sync removed")
            return 0
        a = run(["schtasks", "/Create", "/TN", TASK, "/TR", cmd, "/SC", "DAILY", "/ST", "09:00", "/F"])
        b = run(["schtasks", "/Create", "/TN", f"{TASK}-logon", "/TR", cmd, "/SC", "ONLOGON", "/F"])
        print("daily 09:00 sync registered" if a.returncode == 0 else f"could not register: {a.stderr.strip()}")
        print("logon sync registered" if b.returncode == 0 else "logon trigger needs an elevated shell - skipped")
        return a.returncode
    if not shutil.which("crontab"):
        print("crontab not found - run `harnessd sync` from your own scheduler")
        return 1
    current = run(["crontab", "-l"]).stdout
    lines = [l for l in current.splitlines() if "harnessd.py\" sync" not in l]
    if on:
        lines += [f"0 9 * * * {cmd} >/dev/null 2>&1", f"@reboot {cmd} >/dev/null 2>&1"]
    r = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    print(("cron sync registered (daily 09:00 + reboot)" if on else "cron sync removed") if r.returncode == 0 else "crontab update failed")
    return r.returncode
