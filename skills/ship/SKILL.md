---
name: ship
description: Branch, verify, commit, PR, tag and merge discipline. Use whenever work is about to be committed, pushed, merged or released - including bare requests like "push to main", "commit this", "ship it", "deploy", "make a PR", or "is it pushed". Enforces short-lived branch lanes, the crossbrain preflight secret/size/branch gate, commit messages that say why, PRs that state what was NOT verified, tagging, and routing the lesson through retro.
---

# Ship

Most expensive failures happen at the end of the pipeline: a key committed "just for a minute", a
change that skipped review on `main`, a release nobody can identify. This skill is that missing gate.

## If asked to "push to main"

Unless the user has explicitly set a repo up for direct commits, don't. Say so briefly, then:

1. Cut a lane branch.
2. Run the gates.
3. Commit.
4. Open a PR.

A genuine production-down `hotfix/` still goes through a PR; it just merges straight after CI.

## Branch lanes

| Lane | For | Extra gate |
|---|---|---|
| `feat/` | a new capability | full check + PR |
| `fix/` | a defect in shipped behaviour | **add or point to a regression test** |
| `ui/` | presentation only, with no schema and no logic | a viewport check |
| `data/` | migrations, RLS, SQL functions | migration check + "anonymous user gets zero rows" check |
| `agent/` | a long autonomous run | **squash before PR** |
| `chore/` | deps, config, tooling | — |
| `spike/` | throwaway exploration | **never merges**; delete within 14 days |
| `hotfix/` | production is broken now | from `main`, back to `main` (and `develop`), tag |

Name branches `<lane>/<outcome>`: `fix/rls-view-security-invoker`, `ui/calendar-fits-viewport`.

## Verify

Run the repo's real `check`, build and tests. **A type-check is not a test suite.** It can't see a layout, an
access policy or a timezone. If the repo has no tests, say so in the PR.

## Preflight

```bash
crossbrain preflight --staged        # or install it once: crossbrain hooks install --all
```

It refuses a commit for any of three reasons:
- **Secret:** a live key in the change. Once pushed, **the key is burned**. Rotate it, because removing the line doesn't remove it from history.
- **Size:** a file over 5 MB. Git keeps it in every clone forever.
- **Branch:** a protected branch, unless explicitly allowed.

**Never bypass it with `--no-verify`.** The patterns are regression-tested against real leaks and real false
positives, so if it fires, the finding is real.

## Commit

Use a conventional prefix. **The subject says why, not what:**

```
fix(pregen): the retry was spending a budget it had already spent
fix(onboarding): the first ritual has returned 500 for every user since 5 Aug
perf(db): hoist auth.uid() out of 62 row-level security policies
```

Never write `changes`, `fix`, `update`, `wip` or `....`. The body carries the incident, the root cause, and **what was verified,
including what wasn't**. One coherent slice per commit.

## Pull request

The body answers three questions. The third matters most:

1. **What changed**, and why.
2. **What was verified**: the actual commands and their results.
3. **What was NOT verified**: the honest gap.

## Merge, tag, learn

Squash-merge and delete the branch. Tag `v0.<minor>.<patch>`: minor for `feat`/`data`, patch for the rest. Then run
`retro` so the lesson lands where the next session will read it.

## Two session rules

- **One task per session.** Long sessions compact, lose the contract, and re-earn the same corrections.
- **The rule of ten.** If a command has run ten times with unchanged output, stop. Name the missing document,
  credential, spec or environment, and go get it.
