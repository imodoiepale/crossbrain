# Security model

crossbrain puts third-party instructions (skills) in front of agents that can run commands on your machine.
That is a supply chain, and it's treated like one.

## What crossbrain does

| Control | Where | What it stops |
|---|---|---|
| **Commit gate** | `scripts/preflight.py`, and a git pre-commit hook via `crossbrain hooks install` | Secrets, `.env` files, blobs over 5 MB, and commits to protected branches. Findings show `file:line` plus an 8-character prefix, never the value. |
| **One pattern set** | `scripts/secret-patterns.txt` | The gate, the redactor, the audit scanner and the supply-chain scans all use the same list, so they cannot drift apart. The patterns are regression-tested against real leak shapes and against real strings that must not match. |
| **Supply-chain scan on vendoring** | `scripts/vendor_ecc.py` | ECC is copied to a staging folder and scanned for secret patterns, hidden or bidi Unicode (a prompt-injection carrier) and oversized files **before** it touches the repo. Any hit aborts the whole update. |
| **Pinned third-party content** | `vendor/ecc/ORIGIN.json`, `vendor/archify/ORIGIN.json` | Upstream changes are *reported* by `crossbrain drift` and never pulled in automatically. A new pin means reviewing a diff. |
| **Bundled archify** | `scripts/vendor_archify.py` | Only the `archify/` skill folder is taken from a **tagged release**, staged and scanned like ECC (secret patterns, hidden Unicode, files over 5 MB), with the tag and commit recorded. It runs on Node's standard library: no `npm install`, so no dependency tree is fetched at run time. |
| **Graph hooks never touch tracked files** | `scripts/components.py`, `scripts/graph_autoupdate.py` | Repos that commit `graphify-out/` are skipped. graphify's `.gitattributes` edit and its machine-specific project hook files are restored byte for byte. `graphify-out/` is hidden through the local `.git/info/exclude`. The after-edit rebuild runs detached and at most once a minute per repo, and a crashed worker's lock expires after 30 minutes. |
| **Vendored skill packs carry no code** | `scripts/vendor_skillpacks.py` | ponytail and the engineer skills are taken at a pinned release, and only `SKILL.md` folders plus licence and rule text are copied. Their hooks, plugins, MCP servers and benchmarks stay upstream, and a test fails if any `.js`, `.mjs`, `.ps1` or `.sh` file appears under `vendor/ponytail/`. |
| **graphify is opt-in to fetch** | `scripts/components.py` | graphify is not redistributed. crossbrain only drives an installed package's own `graphify install`. It runs `pip install graphifyy` **only** with `crossbrain install --with-graphify`, because that downloads and executes third-party code. A graphify failure never fails an install. |
| **Adoption quarantine** | `scripts/adopt_skills.py` | A skill you add by hand is shared with your other machines only if it passes the same scan. A skill that fails stays local and is reported. Dependency folders are never copied. |
| **Sync refuses broken checkouts** | `scripts/sync.py` | If the engine's own tests fail after a pull, nothing is installed. |
| **Secret redaction for memory services** | `scripts/memory_redact_shim.py` | An optional localhost proxy for agent memory services that capture from the request path. It redacts request bodies before capture, streams responses, and binds only to loopback. |
| **Read-only audit** | `crossbrain intake-scan` | It finds tracked secrets, secrets in git history, client-bundle keys, RLS and `SECURITY DEFINER` gaps and unverified JWTs, without ever printing a value. |

## What crossbrain deliberately does not do

- **Capture transcripts.** Knowledge moves between machines only through git commits you can review. Nothing is
  synced from session transcripts, so a key you pasted into a session doesn't spread.
- **Vendor ECC's hook runtime, installer or continuous-learning observer.** They run code on every tool call. The
  observer stores prompts, and its redaction only matches keyword-shaped secrets (`api_key=…`), so a bare pasted key
  would be stored verbatim.
- **Load all of ECC into context.** Every installed skill description is loaded at the start of every session. The
  full library sits in `vendor/ecc/` and is read on demand through `capabilities`.
- **Auto-run third-party scanners** that fetch and execute packages at scan time.

## Honest limits

- A secret that matches no pattern gets past the gate and the redactor. Patterns are a list, not a proof.
- The audit scanner's SQL checks are regex counts over migration files, not a live schema read. Treat its findings as leads.
- Skills are instructions. A malicious skill that passes the scan can still ask an agent to do harm, so review what
  you adopt.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting on this repository, not a public issue.
