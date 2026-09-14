"""
Keep this machine identical to every other machine, and let the knowledge grow.

    python harnessd.py sync             # once
    python harnessd.py sync --no-push   # adopt skills locally but do not push
    python harnessd.py schedule on      # daily + at logon (Windows Task Scheduler / cron)

Git is the sync channel. Every machine runs the same loop:

  1. pull the engine and every brain pack (fast-forward only; dirty or diverged trees are left alone)
  2. run the engine's own tests; if any fail, STOP - never install from a broken checkout
  3. adopt skills you added by hand (~/.claude/skills, ~/.agents/skills): scan -> copy into your
     primary pack -> preflight -> commit -> push. Other machines install them on their next sync.
  4. install skills, agents and instructions into every agent CLI; rebuild brain and capabilities
  5. write the drift report: repos whose fixes landed after their skill, and ECC upstream moves

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


def pull(repo: Path) -> str:
    if not (repo / ".git").exists():
        return "not a git repo"
    if git(repo, "status", "--porcelain").stdout.strip():
        return "dirty - pull skipped"
    if not git(repo, "remote").stdout.strip():
        return "no remote"
    r = git(repo, "pull", "--ff-only", "--quiet")
    return f"@ {git(repo, 'rev-parse', '--short', 'HEAD').stdout.strip()}" if r.returncode == 0 else "pull failed (diverged?)"


def sync(push: bool = True, quiet: bool = False) -> int:
    cfg = hc.load()
    log_file = hc.state_dir() / "sync.log"

    def say(msg: str) -> None:
        line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        if not quiet:
            print("  " + msg)

    say(f"sync start on {platform.node()}")
    say(f"engine {pull(hc.ENGINE)}")
    pack_state = {}
    for pack in hc.packs(cfg):
        pack_state[pack] = git(pack, "status", "--porcelain").stdout.strip() == ""
        say(f"pack {pack.name} {pull(pack)}")

    tests = run([sys.executable, "-m", "unittest", "discover", "-s", str(hc.ENGINE / "scripts"), "-p", "test_*.py"])
    if tests.returncode != 0:
        say("ABORT engine tests failed - refusing to install from a broken checkout")
        say(tests.stderr.strip().splitlines()[-1] if tests.stderr.strip() else "")
        return 1
    say("gates pass")

    pack = hc.primary_pack(cfg)
    if pack:
        r = run([sys.executable, str(hc.ENGINE / "scripts" / "adopt_skills.py"), "--json"])
        try:
            res = json.loads(r.stdout)
        except ValueError:
            res = {"adopted": [], "quarantined": {}, "skipped": {}}
            say("adopt: unreadable output, skipped")
        for name, why in res["quarantined"].items():
            say(f"QUARANTINED {name} (stays local): {'; '.join(why)}")
        if res["adopted"]:
            names = ", ".join(res["adopted"])
            if (pack / ".git").exists() and pack_state.get(pack) and push:
                run([sys.executable, str(hc.ENGINE / "scripts" / "build_capabilities.py"), "--local"])
                run([sys.executable, str(hc.ENGINE / "scripts" / "build_brain.py")])
                git(pack, "add", "--", "skills", "brain")
                gate = run([sys.executable, str(hc.ENGINE / "scripts" / "preflight.py"), "--staged",
                            "--allow-protected-branch", str(pack)])
                if gate.returncode != 0:
                    git(pack, "reset", "--quiet")
                    say(f"adoption commit REFUSED by preflight - left unstaged in {pack}: {names}")
                else:
                    git(pack, "commit", "--quiet", "-m",
                        f"feat(skills): adopt {names} (added on {platform.node()})\n\nAdopted by harnessd sync after the "
                        "supply-chain scan and preflight passed. Dependency folders excluded; see .adopted.json.")
                    pushed = git(pack, "push", "--quiet")
                    say(f"adopted + {'pushed' if pushed.returncode == 0 else 'committed (push failed, retries next sync)'}: {names}")
            else:
                say(f"adopted into {pack} but not committed (dirty pack, no git, or --no-push): {names}")
    else:
        say("no brain pack configured - hand-added skills are not shared (harnessd pack init <dir>)")

    import install as inst
    inst.install(cfg, log=lambda m: say(m.strip()))
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
