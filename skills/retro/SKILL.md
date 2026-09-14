---
name: retro
description: Close out a task by routing what was learned to the one durable place a future session will actually read - a defect class into the repo's AGENTS.md/CLAUDE.md and its repo-* skill, a cross-repo class into the lessons skill, a preference into memory, a structural change into the code graph. Use at the end of a task, after a merge, when a bug's root cause has just been found, when a session is ending, or when the same correction has come up more than once.
---

# Retro

Agents repeat mistakes that were never written down anywhere the next session would read. The most
valuable file in a repository is often a hand-written list of *bug classes that have already shipped
here*. This skill makes writing that list a step of every task.

## Run it

1. **What broke, and what was the root cause?** Record the cause, not the symptom: *"the calendar scrolled"* is a symptom, *"`aspect-square` on calendar cells"* is a cause.
2. **Could a check have caught it?** If so, the check is part of the lesson.
3. **Route it to exactly one destination** below, and say which in one line.

## Destination 1 — the repo (`AGENTS.md` / `CLAUDE.md`) and its `repo-*` skill

For a **defect class specific to this codebase**: a version trap, a schema quirk, a platform behaviour.

Append to a numbered *"bug classes that have already shipped here"* section, and give each entry a symptom, a cause, a guard and **what it cost**:

> **A view runs as its OWNER, so row-level security does not apply to it.** The public anon key returned every
> customer's name, phone and address through `v_deliveries`. **Any new view over user data sets
> `security_invoker = on` or is revoked from `anon` in the same migration.**

`AGENTS.md` is read by Codex, Cursor, OpenCode, Gemini CLI and others. `CLAUDE.md` is read by Claude Code, so keep both
if both exist. Mirror the class into `<pack>/skills/repo-<name>/SKILL.md`.

**If the lesson has a mechanical guard, write the guard too** (a lint, a regression test or a CI step) and reference it from the entry.

## Destination 2 — the lessons skill (in your pack)

When the same class has now shipped in **a second repo**, promote it to the cross-repo lessons skill,
with evidence from both repos. Then run `harnessd brain`.

## Destination 3 — memory

For a **preference that transfers** (density, navigation pattern, branch naming), write one fact per memory entry,
with *why* and *how to apply*. Don't store what the repo already records: code structure, past fixes and history are
already durable.

## Destination 4 — the code graph

For a **structural change** (a new module, a deleted abstraction, a moved boundary), refresh the graph. A stale graph is
worse than none, because it is confidently wrong.

## When a correction recurs

If the user has corrected the same thing twice, **that is the signal**. The rule is missing from the written record,
not from the agent's judgement. Write it down before continuing, and say that you have.

## Don't

- Write one lesson to every destination. Pick one.
- Record a symptom without its cause, or "be more careful". That is not a guard.
- Skip this because the task went well. A confirmed rule is worth recording too.
