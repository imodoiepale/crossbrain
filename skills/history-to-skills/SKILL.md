---
name: history-to-skills
description: Turn the git history of every repository you own into one repo-* skill per repo - stack, real verify commands, defect classes that already shipped (with commit hashes and root causes read from the diffs), hotspot files and non-negotiables - plus a lessons skill for classes that recur across repos. Use when setting up crossbrain for the first time, when adding a repo, when `crossbrain drift` shows fixes newer than a skill, or when asked to "learn from my repos / commits / past mistakes".
---

# History to skills

Your commit history already records every defect you shipped and how you fixed it. This skill distils it into
skills that every future agent session loads.

## 1. Mine (deterministic, no LLM)

```bash
crossbrain mine --out ~/crossbrain-digests --min-commits 10     # reads crossbrain config projects_root
```

This writes one digest per repo, **with secrets redacted before writing**. Each digest has:
- size and time span, and the mix of conventional prefixes
- fix, revert and rework commits, with their bodies
- the most-churned files, and the files that fixes keep touching
- the stack, and any `CLAUDE.md` / `AGENTS.md` already in the repo

Keep digests outside any public repository. They map every defect you have ever shipped.

## 2. Distil: one repo at a time, or several subagents in parallel

For each digest, write `<pack>/skills/repo-<slug>/SKILL.md` (`slug` is lowercase with hyphens; `name:` must equal the folder):

```markdown
---
name: repo-<slug>
description: <what the repo is>. Use whenever working in the <Repo> repo (path <projects_root>/<Repo>) - before editing, debugging, or shipping. Carries its stack, conventions, and the defect classes its commit history shows already shipped.
---
## What it is             2–4 lines + stack
## How to verify here     the real commands from package.json/Makefile/CI - say plainly if there are no tests
## Conventions            only what the evidence shows
## Defect classes that already shipped
**A. <class>.** Rule: <the guard>.
- <hash> <subject> — <root cause, read from `git show <hash>`>
## Hotspot files          files fixes keep touching, and what to watch in each
## Non-negotiables        3–7 imperative rules
```

Rules for distilling:
- **Read the diffs** of the most instructive fixes (`git -C <repo> show <hash>`). Commit subjects like `fix` or `update` hide the real lesson.
- **Never copy a credential**, token or personal data. If you find a tracked `.env` or a hardcoded key, write *"a secret was committed here — rotate, never inline"* without the value, and tell the user.
- **Don't invent anything.** If history is thin, keep the skill short and say so.
- Keep the repos read-only: no installs, builds or commits in them.

With several repos, give each subagent 2–4 digests at once. Group repos by size, so small histories share one agent.

## 3. Synthesise the cross-repo lessons

Read all the `repo-*` skills. Any class that shipped in **two or more repos** becomes an entry in `<pack>/skills/lessons/SKILL.md`,
naming the repos, the rule and the guard (for example "RLS fails silently in both directions", "an error is not a zero", or
"money math lives in more than one place").

## 4. Build and install

```bash
crossbrain brain          # the repo map + SessionStart cards
crossbrain sync           # commit your pack, install into every agent CLI
```

## Keep it current

`crossbrain drift` (run by every sync) lists repos with fix commits newer than their skill. Fold those in with `retro`,
or re-mine that one repo.
