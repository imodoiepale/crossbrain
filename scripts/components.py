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
