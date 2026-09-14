---
name: brain
description: Entry point for any coding task on a machine running crossbrain. Use at the start of every task, when unsure which skill applies, when starting or inheriting a project, when asked "what do we know about this repo", or before building, debugging, reviewing or shipping. Routes to the matching repo-* skill, capabilities, project-intake, ship and retro, and says where each kind of knowledge lives and where new lessons go.
---

# Brain

The routing table and the operating loop for crossbrain. The knowledge itself lives in skills: generic
ones from the engine, and personal ones in your **brain pack** (`crossbrain config packs`). The generated
map of your repos is `<pack>/brain/BRAIN.md`, with `brain.json` for machines.

## The loop, every task

1. **Locate.** Which repo is this? If a `repo-<name>` skill exists, load it. In Claude Code, a SessionStart
   hook injects that repo's card automatically, including whether its **code graph is fresh, stale or missing**.
   Its defect classes are your first hypotheses. Elsewhere, `crossbrain graph status .` gives the same graph check.
2. **Find the tool.** If no loaded skill fits, open `capabilities`. It indexes everything installed plus the
   full vendored ECC library (hundreds of skills, agents, commands and rule packs). Read the matching file
   and follow it before writing anything from scratch.
3. **Intake.** One paragraph: what, why, and **how we will know it is done**. Ask if that is unclear.
4. **Unfamiliar project?** Run `project-intake` before the first change.
5. **Reuse.** Ask the code graph before writing. If the repo has `graphify-out/`, run
   `python -m graphify query "<what you are about to build>"`, and `python -m graphify explain "<Node>"` for anything you will
   touch. If `GRAPH_REPORT.md` is older than recent structural commits, run `python -m graphify update .` first (no LLM). A stale
   graph is confidently wrong. Repos with `crossbrain hooks install --graph-only` rebuild their graph after every commit and
   branch switch. Without a graph, search the codebase. The second copy of a component is where drift starts.
6. **Verify.** Run the repo's real build and tests. A type-check is not a test. If there are no tests,
   say so. Don't imply coverage.
7. **Ship.** Follow `ship`: branch, preflight gate, a commit that says why, and a PR that says what was
   NOT verified.
8. **Learn.** Follow `retro` to route the lesson (table below).

## Where knowledge lives

| Layer | Holds | Written by |
|---|---|---|
| `repo-*` skills (pack) | One repo's stack, verify commands, defect classes that already shipped (with commit evidence), non-negotiables | `crossbrain mine` + `history-to-skills`, then `retro` |
| Lessons skill (pack) | Defect classes seen in two or more repos | Promoted by `retro` |
| Engine skills | `brain`, `capabilities`, `project-intake`, `ship`, `retro`, `history-to-skills`, active ECC skills | crossbrain |
| Repo `AGENTS.md` / `CLAUDE.md` | Rules that must be enforced inside that repo, for any agent | `retro` |
| Agent memory | Transferable preferences | `retro` |
| Code graph (`graphify-out/`) | Structure: what calls what, and what breaks if this changes | `python -m graphify update .` (graphify, installed by crossbrain) |
| Diagrams (`docs/*.html`) | Validated architecture, sequence, data-flow and state diagrams | the `archify` skill (bundled with crossbrain) |

**Routing a lesson:** is it specific to one repo? Put it in that repo's `AGENTS.md` and its `repo-*` skill. Did it show up in a second repo?
Promote it to the lessons skill. Is it a preference? Save it to memory. Is it a structural change? Refresh the graph.

## Standing rules

- **Never inline or paste a secret.** Commits go through `crossbrain preflight --staged`.
- **Rule of ten.** If a command has run ten times with unchanged output, something is missing (a doc, a
  credential, a spec, an environment). Name it and ask for it.
- **One task per session.** End at the task boundary, not when context runs out.
- **A queued job is not a success. A zero is not an error. A green check that never touched the real path
  proves nothing.**

## Keeping it current, on every machine

`crossbrain sync` (daily with `crossbrain schedule on`) pulls the engine and your packs, runs the engine's
tests, adopts skills you added by hand, reinstalls into every agent CLI, and rebuilds the brain and the
capabilities index.
