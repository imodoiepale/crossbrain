<p align="center">
  <img src="assets/banner.svg" alt="crossbrain — one brain for every coding agent" width="100%">
</p>

<p align="center">
  <a href="https://github.com/imodoiepale/crossbrain/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/imodoiepale/crossbrain/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-22c55e.svg"></a>
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="Platforms" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-64748b">
  <img alt="Dependencies" src="https://img.shields.io/badge/runtime%20deps-0-0ea5e9">
  <img alt="No telemetry" src="https://img.shields.io/badge/telemetry-none-16a34a">
</p>

<p align="center">
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude%20Code-supported-D97757?logo=anthropic&logoColor=white">
  <img alt="Codex" src="https://img.shields.io/badge/Codex-supported-10a37f?logo=openai&logoColor=white">
  <img alt="Cursor" src="https://img.shields.io/badge/Cursor-supported-000000?logo=cursor&logoColor=white">
  <img alt="Gemini CLI" src="https://img.shields.io/badge/Gemini%20CLI-supported-4285F4?logo=googlegemini&logoColor=white">
  <img alt="OpenCode" src="https://img.shields.io/badge/OpenCode-supported-7c3aed">
  <img alt="Kimi Code" src="https://img.shields.io/badge/Kimi%20Code-supported-111827">
</p>

<p align="center">
  <img alt="ECC skills" src="https://img.shields.io/badge/ECC%20library-292%20skills%20%C2%B7%2068%20agents%20%C2%B7%2094%20commands-f472b6">
  <img alt="Rule packs" src="https://img.shields.io/badge/rule%20packs-22%20languages-818cf8">
  <a href="https://github.com/Graphify-Labs/graphify"><img alt="graphify" src="https://img.shields.io/badge/bundled-graphify%20code%20graph-0f766e"></a>
  <a href="https://github.com/tt-a1i/archify"><img alt="archify" src="https://img.shields.io/badge/bundled-archify%20diagrams-9333ea"></a>
</p>

<p align="center">
  <b>Your coding agents forget everything between sessions. crossbrain gives them one shared, growing brain</b><br>
  skills learned from your own git history · security gates at the end of the pipeline · a fixed procedure for any project ·<br>
  a code knowledge graph (<a href="https://github.com/Graphify-Labs/graphify">graphify</a>) and validated diagrams (<a href="https://github.com/tt-a1i/archify">archify</a>) ·
  the entire <a href="https://github.com/affaan-m/ecc">ECC</a> library on demand · identical on every machine, in every agent CLI.
</p>

---

## ⚡ One-line install

**macOS · Linux · WSL**

```bash
curl -fsSL https://raw.githubusercontent.com/imodoiepale/crossbrain/main/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/imodoiepale/crossbrain/main/install.ps1 | iex
```

It clones the engine to `~/.crossbrain/engine`, adds a `crossbrain` command, installs skills (including archify) into every agent CLI it
finds, installs graphify into those CLIs if the package is present, and runs `crossbrain doctor`. Re-run it to update. It needs `git` and
Python 3.9+, and it never asks for or stores a credential. For graphify too, add `--with-graphify` (Python 3.10+):
`curl -fsSL …/install.sh | bash -s -- --with-graphify`.
[Read install.sh](install.sh) before piping it to a shell, since it's short.

---

## Table of contents

- [Why](#-why)
- [What you get](#-what-you-get)
- [How it works](#-how-it-works)
- [Works with every agent CLI](#-works-with-every-agent-cli)
- [Bundled tools: graphify + archify](#-bundled-tools-graphify--archify)
- [Quick start](#-quick-start)
- [The skills](#-the-skills)
- [Project intake](#-project-intake-any-project-same-procedure)
- [Knowledge that grows across machines](#-knowledge-that-grows-across-machines)
- [Security model](#-security-model)
- [CLI reference](#-cli-reference)
- [FAQ](#-faq)
- [Contributing](#-contributing) · [License](#-license)

---

## 🧭 Why

Throughput is rarely the problem with AI coding agents. **Memory and the end of the pipeline are.**

- **Corrections repeat.** A preference restated in five repos over two weeks was never written anywhere the next session reads.
- **Bugs repeat.** Your history already records every defect class you shipped, but no agent ever reads it.
- **Leaks happen late.** Secrets get committed "for a minute", blobs bloat history, and changes skip review, all at commit time.
- **Every tool has its own silo.** Claude Code, Codex, Cursor, Gemini CLI, OpenCode and Kimi Code each keep separate rules and skills.
- **Every machine drifts.** Your laptop's agent knows things your desktop's doesn't.

crossbrain fixes this with plain files and git. There's no server, database, or cloud account, and nothing captures your transcripts.

---

## ✨ What you get

| | Capability | What it means for you |
|---|---|---|
| 🧠 | **Brain** | Opening an agent in a repo automatically surfaces that repo's stack, verify commands, and *the bugs it already shipped*. |
| 📚 | **History → skills** | `crossbrain mine` turns every repo's git history into redacted digests, and `history-to-skills` distils one skill per repo with commit-cited defect classes. |
| 🗂️ | **Capabilities** | One generated, self-updating index of *everything* an agent can use: your skills, plugin skills, and the full ECC library. |
| 🛡️ | **Preflight gate** | Blocks secrets, `.env` files, blobs over 5 MB, and protected-branch commits. It runs as a pre-commit hook in every repo, and it's regression-tested against real leaks *and* real false positives. |
| 🔍 | **Project intake** | A fixed sequence for any unfamiliar project: evidence scan, architecture map, security audit, defect-class sweep, production readiness, and a report. |
| 🕸️ | **Code graph (graphify)** | Installed into every agent CLI. Agents ask the graph where things are, and what breaks if they change, *before* writing code. Project intake builds one for every new repo. |
| 📐 | **Diagrams (archify)** | Bundled as a skill. Agents render validated architecture, sequence, data-flow and state diagrams as interactive HTML, drawn from the real code. |
| 📦 | **Full ECC library** | 292 skills, 68 agents, 94 commands, and 22 language rule packs, vendored, pinned, and scanned. Any of it can be read on demand or promoted to always-loaded. |
| 🔄 | **Sync & adoption** | Drop a skill into `~/.claude/skills` on any machine, and the next sync scans it, commits it to your private brain pack, and installs it on every other machine. |
| 🧩 | **Every agent CLI** | One install feeds Claude Code, Codex, Cursor, Gemini CLI, OpenCode and Kimi Code. |
| 🔒 | **Memory redaction shim** | A localhost proxy that strips secrets from requests before a memory service stores them. |

---

## 🏗️ How it works

```mermaid
flowchart LR
  subgraph ENGINE["crossbrain engine · public"]
    direction TB
    S1["core skills<br/>brain · capabilities · project-intake<br/>ship · retro · history-to-skills"]
    S2["ECC library<br/>292 skills · 68 agents<br/>94 commands · 22 rule packs"]
    S3["bundled tools<br/>archify diagrams · graphify code graph"]
    T["tools<br/>preflight · intake-scan · mine<br/>adopt · sync · shim"]
  end

  subgraph PACK["your brain pack · private git repo"]
    direction TB
    P1["repo-* skills<br/>mined from your history"]
    P2["lessons<br/>defect classes seen in 2+ repos"]
    P3["adopted skills<br/>added by hand on any machine"]
    P4["brain map"]
  end

  ENGINE --> I{{"crossbrain install / sync"}}
  PACK --> I

  I --> C1["~/.claude/skills"]
  I --> C2["~/.agents/skills"]
  I --> C3["instruction blocks<br/>CLAUDE.md · AGENTS.md · GEMINI.md"]
  I --> C4["Claude SessionStart<br/>brain hook"]

  C1 --> A1([Claude Code]) & A5([OpenCode]) & A6([Kimi Code])
  C2 --> A2([Codex]) & A3([Cursor]) & A4([Gemini CLI]) & A5 & A6
  C3 --> A1 & A2 & A4
  C4 --> A1
```

**Engine vs pack.** The engine is generic and public. Your knowledge (skills distilled from *your* repos, your lessons, the skills
you adopt) lives in a separate **brain pack**, which is usually a private git repo. Updating the engine never conflicts with your
knowledge, and nothing personal can end up in the public repo.

### A session, start to finish

```mermaid
sequenceDiagram
  autonumber
  actor You
  participant Agent as Agent CLI
  participant Hook as brain hook
  participant Skills as Skills
  participant Gate as preflight
  participant Pack as brain pack

  You->>Agent: open a session in ~/code/shop-api
  Agent->>Hook: SessionStart {cwd}
  Hook-->>Agent: "You are in shop-api · RLS dropped writes silently before · verify with npm test"
  You->>Agent: "add refunds"
  Agent->>Skills: brain → repo-shop-api → capabilities (ecc-security-review)
  Agent->>Agent: graphify query "where are payments captured" (reuse before writing)
  Agent->>Agent: build · run the repo's real tests
  Agent->>Gate: git commit
  alt secret, .env, blob or protected branch
    Gate-->>Agent: BLOCKED file:line [pattern] (value never shown)
  else clean
    Gate-->>Agent: preflight CLEAN
  end
  Agent->>Skills: retro: route the lesson
  Skills->>Pack: new defect class → repo-shop-api / lessons
```

### Capabilities: have everything, load only what you need

```mermaid
flowchart TB
  subgraph LOADED["Loaded every session · costs context"]
    L1[core skills]
    L2[your repo-* skills]
    L3[active ECC skills + agents]
    L4[adopted skills]
  end
  subgraph LIBRARY["Library · zero context cost"]
    V1[292 ECC skills]
    V2[68 agents]
    V3[94 commands]
    V4[22 rule packs]
  end
  CAP[["capabilities<br/>generated index"]] --> LOADED
  CAP --> LIBRARY
  LIBRARY -- "agent reads the file on demand" --> AG((agent))
  LIBRARY -- "crossbrain ecc use NAME" --> L3
```

Every installed skill's description is loaded at the start of **every** session. Loading all of ECC would add 15–20k tokens
before you type anything, and some of its skills claim universal triggers. So all of it is *available* through the `capabilities` index,
and only a curated set is *loaded*.

---

## 🧩 Works with every agent CLI

| Agent CLI | Skills | Instructions | Session brain card |
|---|:---:|:---:|:---:|
| **Claude Code** | ✅ `~/.claude/skills` | ✅ `CLAUDE.md` | ✅ |
| **Codex** | ✅ `~/.agents/skills` | ✅ `~/.codex/AGENTS.md` | via `brain` skill |
| **Cursor** | ✅ `~/.agents/skills` | Settings → Rules | via `brain` skill |
| **Gemini CLI** | ✅ `~/.agents/skills` | ✅ `~/.gemini/GEMINI.md` | via `brain` skill |
| **OpenCode** | ✅ `~/.claude/skills` + `~/.agents/skills` | opt-in `AGENTS.md` | via `brain` skill |
| **Kimi Code** | ✅ `~/.claude/skills` + `~/.agents/skills` | — | via `brain` skill |
| **Anything that reads Agent Skills** | ✅ add a target | — | — |

The paths, sources and caveats are in **[docs/HARNESSES.md](docs/HARNESSES.md)**. For example, OpenCode's instruction file is opt-in, because creating
it would hide your `CLAUDE.md` from OpenCode.

---

## 🧰 Bundled tools: graphify + archify

Two tools make the skills concrete instead of aspirational. crossbrain installs both and tells every agent exactly when to use them.

```mermaid
flowchart LR
  subgraph G["graphify · code knowledge graph"]
    G1["python -m graphify update .<br/>(no LLM)"] --> G2[("graphify-out/<br/>graph.json · GRAPH_REPORT.md")]
    G2 --> G3["query · explain · path"]
  end
  subgraph A["archify · validated diagrams"]
    A1["typed JSON spec<br/>or pasted Mermaid"] --> A2["validate"] --> A3["interactive HTML<br/>PNG · SVG · WebM export"]
  end
  BR["brain · step 5 Reuse"] --> G3
  PI["project-intake · phase 2"] --> G1
  PI --> A1
  G2 -. "real nodes and edges" .-> A1
```

| | graphify | archify |
|---|---|---|
| **What** | Turns a codebase into a queryable knowledge graph: god nodes, communities, shortest paths | Renders architecture, workflow, sequence, data-flow and lifecycle diagrams as standalone HTML |
| **How crossbrain ships it** | Python package [`graphifyy`](https://github.com/Graphify-Labs/graphify) (Apache-2.0). On every install and sync, crossbrain runs `graphify install` for each agent CLI present, so its skill stays current everywhere | Vendored from [tt-a1i/archify](https://github.com/tt-a1i/archify) (MIT) at a **pinned release**, scanned like ECC, installed as a skill in every agent CLI |
| **Requirements** | Python 3.10+ | Node 18+ (no `npm install`) |
| **Used by** | `brain` (query before writing), `project-intake` phase 2, the instruction blocks | `project-intake` phase 2 (`docs/intake/architecture.html`), any "draw the architecture" request |
| **Opt out** | remove `"graphify"` from `components` | remove `"archify"` from `components` |

```bash
crossbrain install --with-graphify     # also pip-installs graphify if it is missing (runs third-party code - opt-in)
python -m graphify update .            # build the graph for the current repo
python -m graphify query "where is auth enforced"
crossbrain doctor                      # shows archify version + Node, graphify version + platforms
```

`crossbrain doctor` reports both. If graphify isn't installed, crossbrain prints the exact command and carries on. It never pip-installs
unless you pass `--with-graphify`.

### Who runs them, and with which model

Agents run them, following the skills. crossbrain makes that hard to skip:

| Trigger | What happens | Model involved |
|---|---|---|
| **Session start** (Claude Code) | The card says whether this repo's graph is **fresh, stale (N commits behind) or missing**, with the exact command to run | none |
| **Every commit / branch switch** | `crossbrain hooks install --graph-only` installs graphify's post-commit/post-checkout hooks, which rebuild the graph in the background | none: code is parsed with tree-sitter |
| **`crossbrain intake-scan R`** | Rebuilds R's graph before auditing, and reports its freshness | none |
| **`brain`**, step 5 | The agent runs `graphify query` / `explain` / `path` before writing code | your session's model reads the answers |
| **`project-intake`**, phase 2 | The agent reads `GRAPH_REPORT.md`, writes an archify spec from the graph and code, then renders `architecture.html` | your session's model writes the spec; archify renders it deterministically |

graphify only uses a model to extract **docs, PDFs and images**, never code. It uses Gemini if `GEMINI_API_KEY` is set, and otherwise your agent
session itself. archify never uses a model: the agent authors a JSON spec, and archify validates and draws it.

```bash
crossbrain graph status --all                  # fresh / stale / missing for every repo
crossbrain graph update .                      # rebuild one repo's graph now
crossbrain hooks install --all --graph-only    # keep every repo's graph fresh (does not add the commit gate)
```

Graph hooks never modify tracked files. graphify's merge-driver line in `.gitattributes` is put back unless the repo commits its graph, and
`graphify-out/` is hidden from `git status` through the local `.git/info/exclude`.

---

## 🚀 Quick start

```mermaid
flowchart LR
  A["1 · install<br/>one-line installer"] --> B["2 · brain pack<br/>crossbrain pack init"]
  B --> C["3 · learn<br/>crossbrain mine<br/>+ history-to-skills"]
  C --> D["4 · sync everywhere<br/>crossbrain schedule on"]
  D --> E["5 · use it<br/>open any agent in any repo"]
```

```bash
# 1. install (see above), then check what was detected
crossbrain doctor

# 2. create your private brain pack and push it to a PRIVATE remote
crossbrain pack init ~/my-brain
cd ~/my-brain && git remote add origin git@github.com:you/my-brain.git

# 3. teach it your history (point projects_root at the folder holding your repos)
crossbrain config projects_root ~/code
crossbrain mine --out ~/crossbrain-digests
#    then in your agent: "use the history-to-skills skill on ~/crossbrain-digests"
crossbrain brain

# 4. install everywhere, now and every day
crossbrain sync
crossbrain schedule on

# 5. gate every repo
crossbrain hooks install --all
```

On a second machine, install crossbrain, then run `crossbrain pack add ~/my-brain` after cloning your pack, and `crossbrain sync`. That's it.

---

## 🧠 The skills

| Skill | Use it when |
|---|---|
| **`brain`** | Starting any task. It routes to the repo skill, capabilities, intake, ship and retro. |
| **`capabilities`** | "Is there a skill for X?" It covers everything available, including the full ECC library. It's generated and never hand-edited. |
| **`project-intake`** | Taking on any unfamiliar, inherited or client project, or "is this safe / what's the architecture". |
| **`history-to-skills`** | Setting up, adding a repo, or when `crossbrain drift` shows fixes newer than a skill. |
| **`ship`** | Committing, pushing, PRs, releases. It covers branch lanes, preflight, why-not-what commits and honest PRs. |
| **`retro`** | Ending a task. It routes the lesson to the one place the next session will read. |
| **`archify`** (bundled) | Drawing architecture, workflow, sequence, data-flow or state diagrams from real code. |
| **`graphify`** (bundled) | Answering "where is X / what calls Y / what breaks if I change Z" from the code graph before writing code. |
| **`ecc-*`** (active set) | Security review, production audit, codebase onboarding, ADRs, migrations, Postgres, deployment, verification, Next.js, hexagonal architecture. |

Five ECC reviewer agents install as Claude Code subagents: `ecc-security-reviewer`, `ecc-silent-failure-hunter`,
`ecc-architect`, `ecc-database-reviewer` and `ecc-code-reviewer`.

```bash
crossbrain ecc search stripe webhook     # find anything in the library
crossbrain ecc show tdd-workflow         # read it
crossbrain ecc use tdd-workflow          # make it always-loaded (on every machine after sync)
crossbrain ecc drop nextjs-turbopack
```

---

## 🔍 Project intake: any project, same procedure

```mermaid
flowchart TD
  P0["0 · Identify<br/>load repo-* skill · define done"] --> P1["1 · Evidence scan<br/>crossbrain intake-scan"]
  P1 --> STOP{"critical finding?<br/>live secret · key in client bundle"}
  STOP -- yes --> U["⛔ tell the user first<br/>rotation steps on top"]
  STOP -- no --> P2
  U --> P2["2 · Architecture map<br/>graphify graph · onboarding · architect agent · ADRs · archify diagram"]
  P2 --> P3["3 · Security audit<br/>secrets → access → auth → input → payments → silent failure → agent surface → PII"]
  P3 --> P4["4 · Defect-class sweep<br/>yes / no / unknown for each"]
  P4 --> P5["5 · Production readiness<br/>lenses · score band · real build + tests"]
  P5 --> P6["6 · Report + learn<br/>docs/intake/DATE-INTAKE.md · new repo skill · lessons"]
```

The scanner is deterministic and read-only, and it never prints a secret value:

| Area | Checks |
|---|---|
| **Architecture** | stack, layout, API routes, migrations, edge functions, workers, tests, CI, agent docs, and a **freshly rebuilt code graph** (`--no-graph` to skip) |
| **Secrets** | tracked secret files · secret patterns at HEAD **and in git history** · secret-named `NEXT_PUBLIC_`/`VITE_` vars · hardcoded env fallbacks · `.env` not ignored |
| **Access** | tables vs `ENABLE ROW LEVEL SECURITY` · `SECURITY DEFINER` without `REVOKE` · views without `security_invoker` · JWT decoded but not verified |
| **Supply chain** | hidden or bidi Unicode in `CLAUDE.md`, `AGENTS.md`, `.mcp.json`, `.claude/`, `.cursor/rules/` |
| **Hygiene** | personal-data files · files over 5 MB · tracked `node_modules` · copy files · multiple lockfiles · no tests / CI / pre-commit gate |

```bash
crossbrain intake-scan ~/code/shop-api          # one repo → markdown
crossbrain intake-scan --all --summary          # every repo: scores and counts only
```

---

## 🔄 Knowledge that grows across machines

```mermaid
flowchart LR
  subgraph M1["Laptop"]
    A1["you add a skill<br/>or retro writes a lesson"] --> S1["crossbrain sync"]
  end
  subgraph GIT["git remote · private"]
    R[("brain pack")]
  end
  subgraph M2["Desktop · daily / at logon"]
    S2["crossbrain sync"] --> I2["pull → tests → install<br/>→ brain → capabilities → drift"]
  end
  S1 -- "scan → preflight → commit → push" --> R
  R -- pull --> S2
  I2 --> D["drift report<br/>repos whose fixes outran their skill<br/>ECC upstream vs pin"]
  D -. "retro" .-> A1
```

- **Adoption:** a skill dropped into `~/.claude/skills` or `~/.agents/skills` is scanned for secrets, hidden Unicode and files over 5 MB,
  then copied **without** `node_modules`, committed and pushed. A skill that fails the scan is quarantined: it stays local and is reported.
- **Drift:** each sync lists repos with fix commits newer than their skill, so lessons don't go stale.
- **Safety:** sync refuses to install from a checkout whose tests fail. Nothing is synced from transcripts.

---

## 🛡️ Security model

```mermaid
flowchart LR
  K["🔑 secret"] --> G1{"preflight<br/>commit gate"}
  G1 -- blocked --> X1["never committed"]
  K --> G2{"redaction shim"}
  G2 -- "[REDACTED:id]" --> MEM[("memory service")]
  TP["third-party skills<br/>ECC · adopted"] --> G3{"supply-chain scan<br/>secrets · hidden unicode · size"}
  G3 -- fail --> X3["quarantined / aborted"]
  G3 -- pass --> PIN["pinned + reviewed diff"]
```

- **One pattern set** (`scripts/secret-patterns.txt`) is shared by the gate, the redactor, the scanner and the supply-chain scans.
- **Third-party content is pinned.** Upstream moves are *reported*, never auto-applied.
- **Deliberately not included:** transcript capture, ECC's hook runtime and installer, and its prompt-capturing observer.
- **Honest limits:** a secret that matches no pattern still gets through, and the SQL checks are leads, not a live schema read.

Full threat model: **[docs/SECURITY.md](docs/SECURITY.md)**.

---

## 📟 CLI reference

| Command | Does |
|---|---|
| `crossbrain install [--with-graphify] [--targets claude,agents] [--dry-run]` | Install skills, agents, instruction blocks, archify, graphify and the Claude hook |
| `crossbrain sync [--no-push] [--quiet]` | Pull → tests → adopt → install → brain → capabilities → drift |
| `crossbrain schedule on\|off` | Daily and at-logon sync (Task Scheduler / cron) |
| `crossbrain doctor` | Detected agent CLIs, targets, packs, archify/Node, graphify version and platforms, hook status |
| `crossbrain pack init\|add <dir>` | Create or attach a brain pack |
| `crossbrain config [key [value]]` | Read or change `~/.crossbrain/config.json` |
| `crossbrain mine [--out DIR]` | Git history → redacted per-repo digests |
| `crossbrain brain` | Rebuild the brain map from `repo-*` skills |
| `crossbrain capabilities [--check\|--local]` | Rebuild the capabilities index |
| `crossbrain adopt [--dry-run]` | Adopt hand-added skills into your pack |
| `crossbrain ecc search\|show\|use\|drop\|list` | Work with the ECC library |
| `crossbrain intake-scan <repo> \| --all [--summary]` | The deterministic project audit |
| `crossbrain preflight [--staged] [path]` | The commit gate |
| `crossbrain hooks install\|uninstall [path\|--all] [--graph-only\|--no-graph]` | The gate as a pre-commit hook, plus graphify hooks that rebuild the code graph on commit and checkout |
| `crossbrain graph status\|update [path\|--all]` | Code-graph freshness per repo (fresh, stale by N commits, or missing); rebuild with no LLM |
| `crossbrain drift` | Repos whose fixes outran their skill, plus ECC upstream status |
| `crossbrain shim [--port N]` | Localhost secret-redacting proxy for memory services |

<details>
<summary><b>Configuration</b>: <code>~/.crossbrain/config.json</code></summary>

```json
{
  "projects_root": "~/code",
  "packs": ["~/my-brain"],
  "skill_targets": ["claude", "agents"],
  "instruction_targets": ["claude", "codex", "gemini"],
  "components": ["archify", "graphify"]
}
```

Available skill targets are `claude`, `agents`, `codex`, `cursor`, `gemini`, `opencode` and `kimi`. Instruction targets are `claude`,
`codex`, `gemini` and `opencode`. Set `CROSSBRAIN_HOME` to move the config and state directory.
</details>

<details>
<summary><b>Repository layout</b></summary>

```
crossbrain/
├── crossbrain.py              CLI
├── install.sh / install.ps1 one-line installers
├── skills/                  core skills + active ECC skills + generated capabilities
├── agents/                  active ECC subagents
├── vendor/ecc/              the full ECC library (pinned, scanned)
├── vendor/archify/          archify diagram skill (pinned release, scanned)
├── scripts/                 preflight · project_audit · mine · adopt · sync · install · shim · tests
└── docs/                    HARNESSES.md · SECURITY.md
```
</details>

---

## ❓ FAQ

<details>
<summary><b>Does it send my code or prompts anywhere?</b></summary>

No. crossbrain is local files plus git. It has no telemetry and no server. The only network calls are `git` operations on remotes you
configure, and an optional `git ls-remote` to check whether ECC has moved upstream.
</details>

<details>
<summary><b>Do I need a brain pack?</b></summary>

No. Install alone gives every agent the core skills, the capabilities index, the ECC library and the preflight gate. A pack is what
lets your *own* lessons and hand-added skills follow you across machines.
</details>

<details>
<summary><b>Why not install all 292 ECC skills?</b></summary>

Every installed skill's description loads into every session. All of ECC costs roughly 15–20k tokens before you type, and several
skills claim universal triggers that collide with each other. The library tier keeps all of it one file-read away.
`crossbrain ecc use <name>` loads anything you use often.
</details>

<details>
<summary><b>Does it install graphify and archify?</b></summary>

Yes. **archify** ships inside crossbrain at a pinned release and installs as a skill in every agent CLI. It needs Node 18+ to run.
**graphify** is a separate Python package (Python 3.10+). If it's installed, crossbrain runs `graphify install` for every agent CLI on
each install and sync. If it isn't, `crossbrain install --with-graphify` installs it. Both are wired into `brain` and `project-intake`,
and into the instruction block every agent reads.
</details>

<details>
<summary><b>Will it overwrite my existing CLAUDE.md / AGENTS.md?</b></summary>

No. It writes a single block between `<!-- crossbrain:begin -->` and `<!-- crossbrain:end -->`, and it only touches tools whose config folder
already exists. Skills and agents that crossbrain did not install are never replaced or removed.
</details>

<details>
<summary><b>How do I uninstall?</b></summary>

```bash
crossbrain schedule off
crossbrain hooks uninstall --all
python ~/.crossbrain/engine/scripts/install_brain_hook.py --uninstall
```

Then delete the skill folders listed in `~/.claude/skills/.crossbrain-manifest.json` and `~/.agents/skills/.crossbrain-manifest.json`, the
crossbrain blocks in your instruction files, and `~/.crossbrain`.
</details>

---

## 🤝 Contributing

Issues and PRs are welcome. Read **[CONTRIBUTING.md](CONTRIBUTING.md)**. The short version: run the tests, ship fixtures for any new check
(a catch *and* a real-world string that must stay quiet), keep everything generic, and cite docs for any harness path.

## 🙏 Credits

- **[ECC](https://github.com/affaan-m/ecc)** by Affaan Mustafa (MIT): the skills, agents, commands and rule packs in `vendor/ecc/`.
- **[archify](https://github.com/tt-a1i/archify)** by tt-a1i (MIT): the diagram skill in `vendor/archify/`.
- **[graphify](https://github.com/Graphify-Labs/graphify)** by Graphify Labs (Apache-2.0): the code knowledge graph, installed from its own package.
- The [Agent Skills](https://agentskills.io) format, which lets one skill folder work across agent CLIs.

## 📄 License

[MIT](LICENSE). Vendored ECC and archify content remain under their own MIT licenses ([vendor/ecc/LICENSE](vendor/ecc/LICENSE),
[vendor/archify/LICENSE](vendor/archify/LICENSE)). graphify is not redistributed; it is installed from its own package.
