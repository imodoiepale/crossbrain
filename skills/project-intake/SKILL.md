---
name: project-intake
description: The fixed procedure for taking on ANY project - a new client repo, an inherited codebase, a repo untouched for months, or "audit this / review this / is this safe / what's the architecture / what breaks in prod". Runs identify, evidence scan, architecture map, security audit, defect-class sweep, production readiness, report, then routes the lessons, using `crossbrain intake-scan` for evidence and the vendored ECC security, architecture, database and production-audit skills and agents for judgement. Use before the first change to any unfamiliar project, and before launch or handover of a familiar one.
---

# Project intake

One sequence for every project. Automate what can be proven, and use judgement only on what a script
cannot see. The output is a report file in the repo, not a chat message, so the next session starts
from it.

`R` is the project repo.

## Phase 0 — Identify

1. If a `repo-*` skill exists for R, read it **first**. Its shipped defect classes are your first hypotheses.
2. If none exists, you will write one in Phase 6.
3. Pin down the acceptance question: what does *done* mean for this intake? An audit report, a fix list,
   a launch go or no-go, or a first feature.

## Phase 1 — Evidence scan (automated, read-only)

```bash
crossbrain intake-scan R > R/docs/intake/AUDIT.md
```

The scan never prints secret values. It checks:
- **Architecture:** stack, layout, API routes, migrations, edge functions, workers, tests, CI, agent docs, code graph.
- **Secrets:** secret files tracked in git; secret patterns at HEAD and in history; secret-named `NEXT_PUBLIC_`/`VITE_` variables; hardcoded env fallbacks.
- **Access:** RLS coverage; `SECURITY DEFINER` functions without a `REVOKE`; views without `security_invoker`; JWTs decoded but never verified.
- **Agent config:** hidden Unicode in agent instructions.
- **Hygiene:** personal-data files, files over 5 MB, `node_modules` in git, copy files, lockfile ambiguity, no tests, no CI, no pre-commit gate.

**Stop rule:** a `critical` finding (a live secret, or a secret in a client bundle) goes to the top of the
report with rotation steps, and to the user **before** you continue.

## Phase 2 — Architecture map

1. **Code graph (graphify).** Build or refresh the graph, which needs no LLM:
   ```bash
   python -m graphify update R            # writes R/graphify-out/ (graph.json, GRAPH_REPORT.md)
   ```
   Read `R/graphify-out/GRAPH_REPORT.md` for god nodes, communities and cycles. Answer structural questions from the graph
   before grepping: `python -m graphify query "where is auth enforced"`, `python -m graphify explain "<Node>"`,
   `python -m graphify path "<A>" "<B>"`. If graphify is missing, note it under *Not verified* and suggest
   `crossbrain install --with-graphify`.
2. Follow **`ecc-codebase-onboarding`**: entry points, request lifecycle, data flow and directory map, taken from the code (and the graph), not the README.
3. Brief the **`ecc-architect`** agent with the map and `GRAPH_REPORT.md`. Ask for boundary violations, duplicated responsibilities and scaling limits.
4. Record each load-bearing decision (auth model, tenancy, sync strategy) as an ADR with **`ecc-architecture-decision-records`**.
5. **Architecture diagram (archify).** Use the **`archify`** skill to render the runtime as a validated architecture diagram:
   clients, API, database, workers and third parties, with every node taken from the evidence above. Save it as
   `R/docs/intake/architecture.html`. Add a sequence diagram for the most critical request path if it clarifies auth or payments.
   If Node 18+ is unavailable, fall back to one Mermaid diagram in the report and note that archify could not run.

## Phase 3 — Security audit (in order)

1. **Secrets.** Confirm each Phase 1 hit by hand: its provider, that it must be rotated, and how to remove it (`git rm --cached`; a history rewrite if the repo is public).
2. **Access control.** Views run as their owner. `SECURITY DEFINER` needs explicit revokes. RLS blocks without an error, so every write
   path must check affected rows. Use **`ecc-database-reviewer`** and **`ecc-postgres-patterns`**.
3. **Auth.** Is authorisation enforced server-side on every route? Are tokens verified, not just decoded? Are role checks the same in middleware and handlers?
4. **Input, injection, XSS, CSRF, rate limits, uploads.** Use the **`ecc-security-review`** checklist, and **`ecc-security-reviewer`** on routes and actions.
5. **Payments and webhooks.** Signature verified before parsing; handlers idempotent; net vs gross named; money math in one module.
6. **Silent failure.** Run **`ecc-silent-failure-hunter`**: swallowed errors, `{ data }` without `error`, errors shown as zeros.
7. **Agent surface.** Check `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.mcp.json` and hooks for auto-run instructions, over-broad permissions and hidden payloads. Treat them as supply chain.
8. **Personal data** in the repo, the logs and client bundles.

## Phase 4 — Defect-class sweep

Take every class in your lessons skill, or these defaults. Answer each one **yes (with evidence) / no / unknown**:
- schema drift between code and the live database
- errors reported as zeros
- money math in more than one place
- copy-files drifting apart
- deploy config fix streaks
- background jobs that nothing runs
- checks that never touch the real path
- protocols guessed instead of captured

Unknowns become questions in the report.

## Phase 5 — Production readiness

Follow **`ecc-production-audit`** (security, data integrity, payments, operations and UX lenses, then a band). Use
**`ecc-deployment-patterns`** for deploy and rollback, **`ecc-database-migrations`** for migration safety, and
**`ecc-verification-loop`** before claiming anything passes. Run R's real build and tests. Anything not run goes under *Not verified*.

## Phase 6 — Report and learn

Write `R/docs/intake/YYYY-MM-DD-INTAKE.md`:

```markdown
# <Repo> intake — <date>
## Verdict        band + score, the answer to the acceptance question
## Stop-the-line  critical findings with rotation/removal steps (or "none")
## Architecture   map, graph findings (GRAPH_REPORT.md), archify diagram link, ADRs written
## Security       findings by severity: evidence (file:line / commit), impact, fix
## Defect classes each as yes / no / unknown
## Production     lens scores, launch blockers
## Fix plan       ordered, sized, one branch per item
## Not verified   every check that could not be run, and why
```

Then route what you learned, with `retro`:
- **New repo:** write `<pack>/skills/repo-<name>/SKILL.md`, then run `crossbrain brain`.
- **A class now seen in a second repo:** promote it to your lessons skill.
- **Something the scanner could have proven but missed:** add a check and a fixture to `scripts/test_project_audit.py`, and contribute it upstream.

## Guardrails

- Read-only until the user accepts the fix plan. No rotation, history rewrite or push on their behalf.
- Never put a secret value in the report, a commit or chat. Use file:line and pattern id only.
- Rule of ten: if a check can't run, record it under *Not verified* and move on.
