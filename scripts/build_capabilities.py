"""
Generate the `capabilities` master skill: one index of everything an agent here can do.

    python scripts/build_capabilities.py            # skills/capabilities/SKILL.md (committed, deterministic)
    python scripts/build_capabilities.py --check    # CI: exit 1 if the committed catalogue is stale
    python scripts/build_capabilities.py --local    # ~/.claude/skills/capabilities/SKILL.md, plus this PC's
                                                    # plugin skills and not-yet-adopted local skills

It regenerates itself: sync-knowledge.ps1 runs it on every sync, the SessionStart hook runs --local
whenever the set of installed skills changes, and CI fails if the committed copy drifts from the
skills it describes. Nothing in the catalogue is written by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import hconfig as hc

ROOT = Path(__file__).resolve().parent.parent
USER_SKILLS = Path.home() / ".claude" / "skills"
PLUGINS = Path.home() / ".claude" / "plugins"
OUT = ROOT / "skills" / "capabilities" / "SKILL.md"
HARNESS_TOKEN = "<HARNESS>"

# First match wins. Language/framework prefixes go first so `django-security` files under Django.
CATEGORIES = [
    ("Languages & frameworks", r"^(django|laravel|kotlin|swift|rust|golang|java|jpa|cpp|csharp|fsharp|dotnet|perl|dart|flutter|"
                               r"quarkus|springboot|nestjs|nuxt|vue|angular|react|rails|python|pytorch|fastapi|bun|"
                               r"compose|android|swiftui|nextjs|vite|prisma|redis|clickhouse|mysql|kubernetes|docker|"
                               r"tinystruct|ui-to-vue|harmonyos|arkts|php|ruby|typescript)"),
    ("Security & compliance", r"secur|hipaa|phi|threat|audit|safety|guard|compliance|vulnerab|owasp|pentest|bounty"),
    ("Architecture & design", r"architect|hexagonal|adr|decision|design|blueprint|contract-first|pattern|system|plan"),
    ("Testing & verification", r"test|tdd|verif|eval|e2e|qa|benchmark|regression|comply|check|gate"),
    ("Data & databases", r"postgres|database|sql|migration|data|etl|pipeline|recsys|scraper|clickhouse|vector|rag"),
    ("Deploy & operations", r"deploy|ci|devops|canary|infra|homelab|network|ops|monitor|incident|cost|uncloud|flox"),
    ("Agents & harness", r"agent|harness|loop|orch|council|workflow|skill|hook|context|token|prompt|memory|learning|"
                         r"instinct|compact|ecc|claude|codex|mcp|devfleet|ralph|santa|gan"),
    ("Frontend, UI & media", r"frontend|ui|ux|a11y|access|motion|video|design-system|slides|icon|glass|interface|taste|"
                             r"remotion|manim|blender|brand|seo"),
    ("Research & knowledge", r"research|search|docs|knowledge|literature|scholar|scientific|lookup|onboarding|tour"),
    ("Business & content", r"invest|market|content|social|email|billing|finance|customer|lead|growth|sales|article|"
                           r"logistics|procurement|trade|carrier|inventory|jira|product|messages|notifications"),
]


def frontmatter(text: str) -> dict:
    """Minimal YAML frontmatter: scalars, quoted scalars, and >/| block scalars. Enough for SKILL.md."""
    m = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out, lines, i = {}, m.group(1).splitlines(), 0
    while i < len(lines):
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", lines[i])
        i += 1
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if val in (">", "|", ">-", "|-", ">+", "|+"):
            block = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            val = (" " if val.startswith(">") else "\n").join(b for b in block if b)
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def short(s: str, n: int = 150) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def category(name: str, desc: str) -> str:
    for label, rx in CATEGORIES:
        if re.search(rx, name) or (label != "Languages & frameworks" and re.search(rx, name + " " + desc[:120].lower())):
            return label
    return "Other"


def read_items(folder: Path, pattern: str) -> list[tuple[str, str]]:
    items = []
    if not folder.exists():
        return items
    for p in sorted(folder.glob(pattern)):
        md = p / "SKILL.md" if p.is_dir() else p
        if not md.exists():
            continue
        fm = frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        items.append((p.name if p.is_dir() else p.stem, fm.get("description", "")))
    return items


def build(root: Path = ROOT, local: bool = False, user_skills: Path = USER_SKILLS, plugins: Path = PLUGINS,
          extra_roots: tuple = ()) -> str:
    skills_dir, vendor = root / "skills", root / "vendor" / "ecc"
    origin = json.loads((vendor / "ORIGIN.json").read_text(encoding="utf-8")) if (vendor / "ORIGIN.json").exists() else {}
    active = json.loads((root / "vendor" / "ecc-active.json").read_text(encoding="utf-8")) \
        if (root / "vendor" / "ecc-active.json").exists() else {"skills": [], "agents": []}

    merged: dict[str, tuple[str, Path]] = {}
    for folder in (skills_dir, *extra_roots):          # later roots (brain packs) override the engine
        for n, d in read_items(folder, "*"):
            merged[n] = (d, folder)
    own = [(n, v[0]) for n, v in sorted(merged.items()) if n != "capabilities"]
    repo_skills = [n for n, _ in own if n.startswith("repo-")]
    ecc_active = [(n, d) for n, d in own if n.startswith("ecc-")]
    adopted = [(n, d) for n, d in own if (merged[n][1] / n / ".adopted.json").exists()]
    core = [(n, d) for n, d in own if not n.startswith(("repo-", "ecc-")) and (n, d) not in adopted]
    agents = read_items(root / "agents", "*.md")

    v_skills = read_items(vendor / "skills", "*")
    v_agents = read_items(vendor / "agents", "*.md")
    v_commands = read_items(vendor / "commands", "*.md")
    rule_packs = sorted(d.name for d in (vendor / "rules").iterdir() if d.is_dir()) if (vendor / "rules").exists() else []
    contexts = [p.stem for p in sorted((vendor / "contexts").glob("*.md"))] if (vendor / "contexts").exists() else []
    workflows = [p.name for p in sorted((vendor / "workflows").glob("*")) if p.name != "README.md"] if (vendor / "workflows").exists() else []
    mcp = []
    if (vendor / "mcp-configs" / "mcp-servers.json").exists():
        try:
            mcp = sorted(json.loads((vendor / "mcp-configs" / "mcp-servers.json").read_text(encoding="utf-8")).get("mcpServers", {}))
        except ValueError:
            pass

    total = len(own) + len(agents) + len(v_skills) + len(v_agents) + len(v_commands)
    H = str(root) if local else HARNESS_TOKEN
    L = ["---", "name: capabilities",
         "description: Master index of EVERYTHING the agent can do here - crossbrain skills, your repo skills, the full ECC "
         "library (every skill, agent, command, rule pack), adopted and plugin skills - with how to use or activate "
         "each. Use when asked what can you do / is there a skill for X / which tool fits this task, before writing "
         "something that may already exist as a skill, or when a task needs a capability no loaded skill covers. "
         "Regenerated automatically; never edit by hand.",
         "---", "",
         "# Capabilities", "",
         f"Generated by `scripts/build_capabilities.py`{' for this PC' if local else ''}. {total} capabilities indexed. "
         f"`{HARNESS_TOKEN}` = the crossbrain engine directory (`crossbrain doctor` prints it)." if not local else
         f"Generated by `scripts/build_capabilities.py --local` for this PC. {total} capabilities indexed.",
         "",
         "## How to use this index", "",
         "1. **Loaded now:** the core, repo, active ECC and adopted skills below are installed. Invoke them by name.",
         f"2. **Available on demand:** for any ECC item in the library, **read the file and follow it**. You don't need to install it: `{H}/vendor/ecc/skills/<name>/SKILL.md`, "
         f"`{H}/vendor/ecc/agents/<name>.md` (as a subagent brief), `{H}/vendor/ecc/commands/<name>.md`, "
         f"`{H}/vendor/ecc/rules/<lang>/*.md`.",
         f"3. **Make one always-loaded:** `python {H}/scripts/ecc.py use <name>` (or `--agent <name>`). That adds it to the active "
         "set on every PC after merge and sync. Keep the active set small, because every loaded description costs context in every session.",
         f"4. **Find one:** `python {H}/scripts/ecc.py search <words>`.",
         "5. **Your rules win:** where an ECC skill conflicts with `brain`, `ship`, `retro` or a skill from your brain pack, follow yours.",
         ""]

    def table(rows, head=("Name", "What it does")):
        return [f"| {head[0]} | {head[1]} |", "|---|---|", *[f"| `{n}` | {short(d).replace('|', '/')} |" for n, d in rows]]

    L += ["## Loaded: crossbrain core", "", *table(core), ""]
    L += [f"## Loaded: repo skills ({len(repo_skills)})", "",
          "One per repo, from your brain pack. The SessionStart hook names the right one, and `<pack>/brain/BRAIN.md` maps them.", "",
          ", ".join(f"`{n}`" for n in repo_skills), ""]
    if adopted:
        L += ["## Loaded: adopted (added on a PC, shared by sync)", "", *table(adopted), ""]
    L += [f"## Loaded: active ECC ({len(ecc_active)} skills, {len([a for a in agents if a[0].startswith('ecc-')])} agents)", "",
          *table(ecc_active), "", *table([a for a in agents if a[0].startswith("ecc-")], ("Agent", "Use for")), ""]

    L += [f"## ECC library @ `{origin.get('commit', '?')[:7]}`: {len(v_skills)} skills, {len(v_agents)} agents, "
          f"{len(v_commands)} commands, {len(rule_packs)} rule packs", "",
          "Available on demand (read the file). ✅ marks items already active.", ""]
    by_cat: dict[str, list] = {}
    for n, d in v_skills:
        by_cat.setdefault(category(n, d.lower()), []).append((n + (" ✅" if n in active.get("skills", []) else ""), d))
    for label in [c for c, _ in CATEGORIES] + ["Other"]:
        if by_cat.get(label):
            L += [f"### Skills: {label} ({len(by_cat[label])})", "", *table(by_cat[label], ("Skill", "What it does")), ""]
    L += [f"### Agents ({len(v_agents)})", "", *table([(n + (" ✅" if n in active.get("agents", []) else ""), d) for n, d in v_agents],
                                                    ("Agent", "Use for")), ""]
    L += [f"### Commands ({len(v_commands)})", "",
          "Slash-command workflows. Read the file and follow its steps; `$ARGUMENTS` means the user's arguments.", "",
          *table(v_commands, ("Command", "What it does")), ""]
    L += [f"### Rule packs ({len(rule_packs)})", "",
          "Coding standards per language: `coding-style`, `patterns`, `security`, `testing`, `hooks`. Read the matching pack "
          "when working in that language; `common/` applies to all.", "", ", ".join(f"`{r}`" for r in rule_packs), ""]
    if contexts or workflows or mcp:
        L += ["### Other ECC material", "",
              f"- Contexts (mode briefs): {', '.join(f'`{c}`' for c in contexts) or 'none'}",
              f"- Workflows: {', '.join(f'`{w}`' for w in workflows) or 'none'}",
              f"- MCP server catalogue ({len(mcp)}): {', '.join(f'`{m}`' for m in mcp) or 'none'}. These are reference configs only. Adding one is a "
              "settings change, so ask the user first.", ""]
    L += ["### Deliberately not vendored", "",
          "ECC's hook runtime and installer (they run code on every tool call), its continuous-learning observer "
          "(it captures prompts, and its redaction misses bare key pastes), translations and assets. See docs/SECURITY.md.", ""]

    if local:
        installed = {n for n, _ in own}
        ignore = set()
        if (skills_dir / ".adopt-ignore").exists():
            ignore = {l.strip() for l in (skills_dir / ".adopt-ignore").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
        pending = [(n, d) for n, d in read_items(user_skills, "*") if n not in installed and n != "capabilities"]
        if pending:
            L += ["## This PC: local skills", "",
                  "Installed here but not in the harness. Items marked ⏳ get adopted, and shared with every PC, on the next sync.", "",
                  *table([(n + ("" if n in ignore else " ⏳"), d) for n, d in pending]), ""]
        plug = {}
        if plugins.exists():
            for md in sorted(plugins.rglob("SKILL.md")):
                parts = md.relative_to(plugins).parts
                if "marketplaces" in parts or "example-plugin" in parts:
                    continue
                name = md.parent.name
                plugin = parts[2] if parts[0] == "cache" and len(parts) > 3 else parts[0]
                plug.setdefault(plugin, {})[name] = frontmatter(md.read_text(encoding="utf-8", errors="replace")).get("description", "")
        if plug:
            L += [f"## This PC: plugin skills ({sum(len(v) for v in plug.values())})", "",
                  "Managed by Claude Code's plugin system, per PC. Invoke them as `plugin:skill`.", ""]
            for plugin in sorted(plug):
                L += [f"### {plugin}", "", *table(sorted(plug[plugin].items())), ""]
    return "\n".join(L).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.local:
        text = build(local=True, extra_roots=tuple(hc.skill_roots()[1:]))
        for target in hc.skill_target_dirs():
            dest = target / "capabilities" / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            hc.write_text_lf(dest, text)
            print(f"capabilities (local) -> {dest}")
        return
    text = build()
    if a.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current.replace("\r\n", "\n") != text:
            print("skills/capabilities/SKILL.md is stale - run python scripts/build_capabilities.py and commit")
            sys.exit(1)
        print("capabilities catalogue is current")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    hc.write_text_lf(OUT, text)
    print(f"capabilities: {text.count(chr(10))} lines -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
