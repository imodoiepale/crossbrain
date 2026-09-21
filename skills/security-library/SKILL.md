---
name: security-library
description: Router to the cybersecurity skills library (800+ skills - vulnerability scanning, cloud and container security, incident response, forensics, threat modeling, detection engineering, compliance, secure code review). Use for any security task: auditing an app or repo, hardening, triaging a vulnerability or incident, forensics, detection rules, compliance checks, or authorised security testing. Finds the one matching skill, confirms scope, then follows it.
---

# Security library

A large on-demand library of security skills lives outside this engine (path: `crossbrain config libraries`).
It is not loaded into context. Find the one skill that fits, read it, follow it.

## How to use it

1. **Find:** `crossbrain library search <words>`, e.g. `crossbrain library search trivy container`.
   It ranks skills by name, description and subdomain and prints their paths.
2. **Read** the matching `SKILL.md` fully, and any file it points to under `references/` or `scripts/`.
3. **Follow it**, and report findings with evidence (file:line, command output), severity and the fix.
4. For estate repos, prefer `project-intake` first; use this library for the depth it links to.

## Ground rules (always)

- **Scope first.** Defensive work, analysis and review of code or data you were given are fine. Before any *active*
  test against a live system (scanning, probing, fuzzing, exploitation checks), confirm with the user that they own
  it or have written authorisation, and what is in scope. No authorisation, no active testing.
- **Read scripts before running them.** Never run a library script you have not read. Run nothing destructive.
- **Never touch third-party targets** that were not explicitly put in scope by the user.
- **Secrets stay secret.** Report where a credential is, never its value.
- Prefer the least invasive method that answers the question (read-only config review over live scanning).
