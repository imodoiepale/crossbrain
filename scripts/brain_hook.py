"""
Claude Code SessionStart hook: tell a new session which repo it is in, what that repo already broke, and
whether its code graph can be trusted.

Claude Code sends {"cwd": ...} on stdin. This prints a short card as additionalContext. Skills load only when
the model opens them; this puts the one card that matters in front of it from the first turn.

  - a repo with a repo-* skill      -> its card: defect classes, non-negotiables, verify commands, graph status
  - any other git repo              -> a short card: no skill yet (run project-intake), graph status
  - the projects root               -> how many repos are mapped
  - anything else                   -> nothing

It also keeps this machine's `capabilities` index current, and names skills added by hand that
`crossbrain sync` has not shared yet.

Fails open: missing brain, bad JSON, unknown directory, git or graphify errors -> no output or a shorter card,
exit 0. A hook that breaks session start gets switched off, and then it protects nothing.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hconfig as hc  # noqa: E402


def match(cwd: str, repos: list[dict], root: Path) -> dict | None:
    c = str(Path(cwd)).lower().rstrip("\\/")
    best, best_len = None, -1
    for r in repos:
        p = str(root / r["repo"]).lower().rstrip("\\/")
        if (c == p or c.startswith(p + "\\") or c.startswith(p + "/")) and len(p) > best_len:
            best, best_len = r, len(p)
    return best


def repo_root(cwd: str) -> Path | None:
    p = Path(cwd)
    for candidate in (p, *p.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def graph_hint(repo: Path | None, cfg: dict) -> str | None:
    if repo is None or "graphify" not in cfg.get("components", []):
        return None
    try:
        import components
        return components.graph_line(components.graph_status(repo), components.graphify_available())
    except Exception:
        return None


def card(r: dict, brain: dict) -> str:
    lessons = brain.get("lessons_skill")
    L = [f"[crossbrain] You are in {r['repo']} - {r['what']}",
         f"Load skill `{r['skill']}` before editing" + (f", and `{lessons}` for cross-repo rules." if lessons else ".")]
    if r["exposure"]:
        L.append("WARNING: this repo has committed secrets on record. Never inline keys; read the skill before touching env or config.")
    if r["defect_classes"]:
        L.append("Already shipped here: " + " | ".join(r["defect_classes"][:4]))
    if r["non_negotiables"]:
        L += ["Non-negotiables:"] + [f"- {n}" for n in r["non_negotiables"][:5]]
    if r["verify"]:
        L.append("Verify with: " + " ; ".join(r["verify"][:3]))
    L.append("Ship via `ship` (branch, preflight, PR). Close with `retro`.")
    return "\n".join(L)


def refresh_capabilities(cfg: dict) -> list[str]:
    """Regenerate the local capabilities index only when installed skills or plugins changed."""
    try:
        import adopt_skills
        import build_capabilities as bc
        targets = hc.skill_target_dirs(cfg)
        names = sorted(d.name for t in targets if t.exists() for d in t.iterdir() if d.is_dir())
        plugin_md = sorted(str(p) for p in bc.PLUGINS.rglob("SKILL.md")) if bc.PLUGINS.exists() else []
        roots = [str(r) for r in hc.skill_roots(cfg)]
        # hashlib, not hash(): str hashing is salted per process and would regenerate on every start.
        fp = hashlib.sha256(json.dumps([names, plugin_md, roots]).encode("utf-8")).hexdigest()
        state = hc.state_dir() / "capabilities.fp"
        if not state.exists() or state.read_text(encoding="utf-8") != fp:
            text = bc.build(local=True, extra_roots=tuple(r for r in hc.skill_roots(cfg)[1:]))
            for t in targets:
                (t / "capabilities").mkdir(parents=True, exist_ok=True)
                hc.write_text_lf(t / "capabilities" / "SKILL.md", text)
            state.write_text(fp, encoding="utf-8")
        pack = hc.primary_pack(cfg)
        if not pack:
            return []
        return sorted({c.name for t in targets if t.exists()
                       for c in adopt_skills.candidates(t, pack / "skills", t / adopt_skills.MANIFEST_NAME)})
    except Exception:
        return []


def main():
    try:
        event = json.load(sys.stdin)
        cfg = hc.load()
    except (OSError, ValueError):
        return
    try:
        brain = json.loads((hc.brain_dir(cfg) / "brain.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        brain = {"repos": []}
    pending = refresh_capabilities(cfg)
    root = hc.projects_root(cfg)
    cwd = event.get("cwd", "")
    r = match(cwd, brain.get("repos", []), root) if cwd else None
    git_root = repo_root(cwd) if cwd else None

    if r:
        text = card(r, brain)
        hint = graph_hint(root / r["repo"], cfg)
    elif git_root is not None:
        text = (f"[crossbrain] {git_root.name} has no repo skill yet. If it is unfamiliar, run `project-intake` before the "
                "first change; `capabilities` indexes every tool available.")
        hint = graph_hint(git_root, cfg)
    elif cwd and Path(cwd).resolve() == root.resolve():
        text = (f"[crossbrain] Projects root: {len(brain['repos'])} repos mapped. Load `brain` to route to the right "
                "repo skill, and `capabilities` for everything else.")
        hint = None
    elif pending:
        text, hint = "[crossbrain]", None
    else:
        return
    if hint:
        text += "\n" + hint
    if pending:
        text += (f"\nSkills added by hand on this machine, not yet shared: {', '.join(pending)}. "
                 "`crossbrain sync` adopts them (scanned) into your brain pack.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    main()
