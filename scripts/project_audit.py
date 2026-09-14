"""
Deterministic project audit: architecture map, security, and hygiene, for one repo or all of them.

    python scripts/project_audit.py <repo>                  # one repo -> stdout (markdown)
    python scripts/project_audit.py --all --out report.md   # every repo under ~/Documents/GitHub
    python scripts/project_audit.py <repo> --json

This is the evidence half of the `project-intake` skill: things a script can prove without an
LLM, run first so the model spends its judgement on what the script cannot see. Every check maps
to a defect class that has already shipped in real repositories (numbering follows the lessons skill).

Read-only. Git and file reads only. Never prints a secret value, only file:line and pattern id.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import hconfig as hc
import memory_redact_shim as shim

GITHUB = hc.projects_root()
SEV_COST = {"critical": 25, "high": 10, "medium": 4, "low": 1}
TEXT_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".java", ".kt", ".sql", ".json", ".yaml",
            ".yml", ".toml", ".env", ".md", ".sh", ".ps1", ".rb", ".php", ".cs", ".dart", ".swift", ".vue", ".html",
            ".txt", ".ini", ".cfg", ".properties", ".xml", ".gradle"}
SKIP_DIRS = re.compile(r"(^|/)(node_modules|\.next|dist|build|vendor|\.git|graphify-out|coverage|\.venv|venv)/")
FIX_RX = re.compile(r"^(fix|hotfix|revert)|\b(fix(e[sd])?|revert|broke|regression|hotfix)\b", re.I)
HIDDEN = re.compile("[​-‏‪-‮⁠-⁤﻿]")
# Test fixtures hold realistic fake keys on purpose (this repo's own test-preflight.ps1 does).
# Flagging them as live secrets taught the first real-world run to cry wolf, so they are counted apart.
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|fixtures?|spec|testdata)/|\.(test|spec)\.[a-z]+$|(^|/)test[-_][\w-]*\.[a-z0-9]+$|_test\.[a-z]+$", re.I)
AGENT_CONFIG = re.compile(r"(^|/)(CLAUDE|AGENTS)\.md$|^\.mcp\.json$|^\.claude/|^\.cursor/rules/")


@dataclass
class Finding:
    id: str
    severity: str
    lesson: str          # defect class, e.g. "1 secrets"
    title: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Report:
    repo: str
    path: str
    facts: dict = field(default_factory=dict)
    architecture: dict = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def score(self) -> int:
        return max(0, 100 - sum(SEV_COST[f.severity] for f in self.findings))

    @property
    def band(self) -> str:
        s = self.score
        return "Blocked" if s < 50 else "Risky" if s < 70 else "Launchable with caveats" if s < 85 else "Strong"


def git(repo: Path, *args: str, timeout: int = 120) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except subprocess.TimeoutExpired:
        return ""


def read(p: Path, limit: int = 1_000_000) -> str:
    try:
        return p.read_bytes()[:limit].decode("utf-8", errors="replace") if p.stat().st_size <= limit else ""
    except OSError:
        return ""


def audit(repo: Path, patterns, history: bool = True) -> Report:
    rep = Report(repo=repo.name, path=str(repo))
    add = rep.findings.append
    files = [f for f in git(repo, "ls-files").splitlines() if f]
    text_files = [f for f in files if not SKIP_DIRS.search(f) and
                  (Path(f).suffix.lower() in TEXT_EXT or Path(f).name.startswith(".env"))]

    # ---------------------------------------------------------------- facts
    log = git(repo, "log", "--all", "--no-merges", "--format=%cs\x1f%s").splitlines()
    fixes = sum(1 for l in log if FIX_RX.search(l.partition("\x1f")[2]))
    head_ref = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    rep.facts = {
        "commits": len(log), "fix_like": fixes, "rework_pct": round(100 * fixes / len(log)) if log else 0,
        "span": f"{log[-1].split(chr(31))[0]} -> {log[0].split(chr(31))[0]}" if log else "",
        "tracked_files": len(files), "origin_head": head_ref or "(none)",
        "branch": git(repo, "branch", "--show-current").strip(),
    }
    if head_ref.endswith("/master") and "main" in git(repo, "branch", "-r"):
        main_d, master_d = git(repo, "log", "-1", "--format=%cs", "origin/main").strip(), git(repo, "log", "-1", "--format=%cs", "origin/master").strip()
        if main_d > master_d:
            add(Finding("default-branch-stale", "medium", "9 hollow checks",
                        "origin/HEAD points at master but main is newer - fresh clones land on stale code",
                        [f"origin/master {master_d}, origin/main {main_d}"]))

    # ---------------------------------------------------------------- architecture map
    pkg = {}
    if (repo / "package.json").exists():
        try:
            pkg = json.loads(read(repo / "package.json"))
        except ValueError:
            pass
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    stack = [n for k, n in [("next", "Next.js"), ("react", "React"), ("vite", "Vite"), ("vue", "Vue"),
                            ("@supabase/supabase-js", "Supabase"), ("prisma", "Prisma"), ("drizzle-orm", "Drizzle"),
                            ("@capacitor/core", "Capacitor"), ("expo", "Expo"), ("electron", "Electron"),
                            ("express", "Express"), ("fastify", "Fastify"), ("playwright", "Playwright"),
                            ("@playwright/test", "Playwright tests"), ("vitest", "Vitest"), ("jest", "Jest"),
                            ("stripe", "Stripe")] if k in deps]
    for marker, name in [("requirements.txt", "Python"), ("pyproject.toml", "Python"), ("go.mod", "Go"),
                         ("pom.xml", "Java"), ("build.gradle", "Gradle/JVM"), ("build.gradle.kts", "Kotlin"),
                         ("pubspec.yaml", "Flutter"), ("Dockerfile", "Docker"), ("vercel.json", "Vercel"),
                         ("nixpacks.toml", "Nixpacks"), ("render.yaml", "Render"), ("railway.json", "Railway")]:
        if any(f == marker or f.endswith("/" + marker) for f in files if not SKIP_DIRS.search(f)):
            stack.append(name)
    top = sorted({f.split("/")[0] for f in files if "/" in f and not SKIP_DIRS.search(f)})
    routes = [f for f in files if re.search(r"(^|/)app/.*route\.(t|j)sx?$|(^|/)pages/api/|(^|/)api/.*\.(t|j)s$", f)]
    migrations = [f for f in files if f.endswith(".sql") and re.search(r"migration|supabase/", f, re.I)]
    edge = sorted({f.split("/")[2] for f in files if f.startswith("supabase/functions/") and f.count("/") >= 3})
    workers = [f for f in files if re.search(r"(cron|worker|queue|job)s?[/.]", f, re.I) and not SKIP_DIRS.search(f)]
    tests = [f for f in files if re.search(r"(\.|_)(test|spec)\.|(^|/)tests?/", f) and not SKIP_DIRS.search(f)]
    ci = [f for f in files if f.startswith(".github/workflows/")]
    rep.architecture = {
        "stack": sorted(set(stack)), "top_level_dirs": top[:25], "api_routes": len(routes),
        "sql_migrations": len(migrations), "edge_functions": edge, "worker_like_files": len(workers),
        "test_files": len(tests), "ci_workflows": [Path(c).name for c in ci],
        "scripts": list(pkg.get("scripts", {}).keys())[:20],
        "agent_docs": [f for f in files if Path(f).name in ("CLAUDE.md", "AGENTS.md")][:5],
        "code_graph": (repo / "graphify-out" / "GRAPH_REPORT.md").exists(),
    }

    # ---------------------------------------------------------------- security
    secret_files = [f for f in files if re.search(
        r"(^|/)\.env(\.[\w-]+)?$|\.pem$|\.p12$|\.pfx$|\.key$|id_rsa|service[-_]?account.*\.json$|client_secret.*\.json$|credentials?\.json$", f, re.I)
        and not re.search(r"\.(example|sample|template|dist)$|example", f, re.I)]
    if secret_files:
        add(Finding("tracked-secret-files", "critical", "1 secrets",
                    "Secret-bearing files are tracked in git - rotate every value, then git rm --cached", secret_files[:15]))

    hits, fixture_hits, client, client_hard, fallback, jwt_noverify, hidden = [], 0, [], [], [], [], []
    rls_create, rls_enable, definer, revoke, views, invoker = 0, 0, 0, 0, 0, 0
    for f in text_files:
        t = read(repo / f)
        if not t:
            continue
        is_test = bool(TEST_PATH.search(f))
        for pid, rx in patterns:
            for m in rx.finditer(t):
                if is_test:
                    fixture_hits += 1
                else:
                    hits.append(f"{f}:{t.count(chr(10), 0, m.start()) + 1} [{pid}]")
        # Only code and env files ship to a bundle; a variable NAME in a doc or a test is not exposure.
        if not is_test and not f.lower().endswith((".md", ".txt")):
            for m in re.finditer(r"\b(NEXT_PUBLIC|VITE|EXPO_PUBLIC|REACT_APP)_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|PASSWORD|API_KEY)[A-Z0-9_]*", t):
                name = m.group(0)
                if re.search(r"ANON|PUBLISHABLE|PUBLIC_KEY|SITE_KEY", name):
                    continue
                loc = f"{f}:{t.count(chr(10), 0, m.start()) + 1} {name}"
                # A password, service role or secret is never meant for a browser. An API key sometimes is
                # (maps, analytics) - but only if the provider restricts it by referrer.
                (client_hard if re.search(r"SECRET|SERVICE_ROLE|PRIVATE|PASSWORD", name) else client).append(loc)
        for m in re.finditer(r"process\.env\.\w+\s*(\|\||\?\?)\s*['\"`][A-Za-z0-9_\-.]{24,}['\"`]|import\.meta\.env\.\w+\s*(\|\||\?\?)\s*['\"`][A-Za-z0-9_\-.]{24,}['\"`]", t):
            fallback.append(f"{f}:{t.count(chr(10), 0, m.start()) + 1}")
        if re.search(r"(middleware|proxy|auth)", f, re.I) and re.search(r"jwt\.decode\(|jwtDecode\(|atob\(\s*\w+\.split\(['\"]\.['\"]\)", t) \
                and not re.search(r"jwt\.verify\(|jwtVerify\(|getUser\(|getClaims\(", t):
            jwt_noverify.append(f)
        if AGENT_CONFIG.search(f):
            if HIDDEN.search(t):
                hidden.append(f)
        if f.endswith(".sql"):
            rls_create += len(re.findall(r"\bcreate\s+table\s+(?!if\s+not\s+exists\s+\w+\s+partition)", t, re.I))
            rls_enable += len(re.findall(r"enable\s+row\s+level\s+security", t, re.I))
            definer += len(re.findall(r"security\s+definer", t, re.I))
            revoke += len(re.findall(r"revoke\s+(all|execute)[^;]*from\s+(public|anon)", t, re.I))
            views += len(re.findall(r"\bcreate\s+(or\s+replace\s+)?view\b", t, re.I))
            invoker += len(re.findall(r"security_invoker", t, re.I))

    if hits:
        add(Finding("secret-patterns-at-head", "critical", "1 secrets",
                    f"{len(hits)} secret-shaped string(s) in tracked files at HEAD (values not shown)", hits[:15]))
    if fixture_hits:
        rep.facts["secret_shaped_strings_in_test_fixtures"] = fixture_hits
    if client_hard:
        add(Finding("secret-in-client-bundle", "critical", "1 secrets",
                    "A password / secret / service-role variable uses a browser-exposed prefix - it ships to every visitor",
                    client_hard[:10]))
    if client:
        add(Finding("api-key-in-client-bundle", "high", "1 secrets",
                    "API key uses a browser-exposed prefix - acceptable only if the provider restricts it by referrer/domain; otherwise proxy it server-side",
                    client[:10]))
    if fallback:
        add(Finding("hardcoded-env-fallback", "high", "1 secrets",
                    "Env var falls back to a hardcoded literal - a missing var silently uses a committed key", fallback[:10]))
    if jwt_noverify:
        add(Finding("jwt-decoded-not-verified", "high", "2 access",
                    "Auth/middleware decodes a JWT without verifying its signature - forged tokens pass", jwt_noverify[:10]))
    if hidden:
        add(Finding("hidden-unicode-agent-config", "high", "supply chain",
                    "Hidden/bidi Unicode in agent instructions - a prompt-injection carrier", hidden))
    if rls_create and rls_enable < rls_create:
        add(Finding("rls-coverage-gap", "high", "2 access",
                    f"SQL creates {rls_create} table(s) but enables RLS {rls_enable} time(s) - check every table",
                    [f"create table x{rls_create}, enable row level security x{rls_enable}"]))
    if definer and revoke == 0:
        add(Finding("definer-without-revoke", "high", "2 access",
                    f"{definer} SECURITY DEFINER function(s) and no REVOKE from public/anon - Postgres grants EXECUTE to PUBLIC by default",
                    [f"security definer x{definer}, revoke x0"]))
    if views and invoker < views:
        add(Finding("views-run-as-owner", "medium", "2 access",
                    f"{views} view(s), {invoker} with security_invoker - a view runs as its owner, so RLS does not apply",
                    [f"create view x{views}, security_invoker x{invoker}"]))
    env_ignored = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", ".env"]).returncode == 0
    if not env_ignored:
        add(Finding("env-not-ignored", "medium", "1 secrets", ".env is not covered by .gitignore", []))

    if history and rep.facts["commits"]:
        hist = history_secrets(repo, patterns)
        if hist:
            add(Finding("secrets-in-history", "high", "1 secrets",
                        f"Secret-shaped strings were added in {len(hist)} commit(s) - still fetchable from history; rotate",
                        hist[:12]))

    # ---------------------------------------------------------------- personal data & hygiene
    pii = [f for f in files if re.search(r"(passport|national[-_ ]?id|\bid[-_ ]?(card|front|back)|kra[-_ ]?pin|payslip|invoice).*\.(png|jpe?g|pdf|docx?)$", f, re.I)
           or re.search(r"\.(log)$|(^|/)(whatsapp chat|chat export)", f, re.I)]
    if pii:
        add(Finding("personal-data-files", "high", "personal data",
                    "Files that look like personal or client documents or logs are tracked - removal needs a history rewrite", pii[:10]))
    big = []
    for f in files:
        try:
            if (repo / f).stat().st_size > 5_000_000:
                big.append(f"{f} ({(repo / f).stat().st_size // 1_000_000} MB)")
        except OSError:
            pass
    if big:
        add(Finding("large-files", "medium", "7 deploy/hygiene", "Tracked files over 5 MB", big[:10]))
    if any(f.startswith("node_modules/") or "/node_modules/" in f for f in files):
        add(Finding("node-modules-tracked", "medium", "7 deploy/hygiene", "node_modules is tracked", []))
    copies = [f for f in files if re.search(r"( copy| - copy|copy\d*|_old|\.bak|draft\d)\.[a-z]+$", f, re.I)]
    if copies:
        add(Finding("copy-files", "medium", "6 copy drift", f"{len(copies)} copy/backup file(s) tracked - fixes land in one copy only", copies[:10]))
    if any(f.endswith("tsconfig.tsbuildinfo") for f in files):
        add(Finding("tsbuildinfo-tracked", "low", "7 deploy/hygiene", "tsconfig.tsbuildinfo is tracked (has broken builds here before)", []))
    locks = [f for f in files if Path(f).name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb") and "/" not in f]
    if len(locks) > 1:
        add(Finding("multiple-lockfiles", "low", "7 deploy/hygiene", "More than one root lockfile - package manager ambiguity", locks))
    if not tests and rep.facts["commits"] >= 10:
        add(Finding("no-tests", "medium", "9 hollow checks", "No test files - verification is manual only", []))
    if not ci and rep.facts["commits"] >= 10:
        add(Finding("no-ci", "low", "9 hollow checks", "No GitHub Actions workflow", []))
    if not (repo / ".git" / "hooks" / "pre-commit").exists():
        add(Finding("no-precommit-gate", "low", "1 secrets", "No pre-commit hook - run `harnessd hooks install`", []))
    return rep


def history_secrets(repo: Path, patterns, max_bytes: int = 150_000_000, max_seconds: int = 90) -> list[str]:
    """Commits whose ADDED lines match a secret pattern. Bounded, so a vendored-node_modules repo cannot hang it."""
    proc = subprocess.Popen(["git", "-C", str(repo), "log", "--all", "-p", "--no-color", "-U0",
                             "--format=\x1e%h %cs", "--", ".", ":(exclude)*.lock", ":(exclude)*lock.json",
                             ":(exclude)node_modules", ":(exclude)*.min.js"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    found, commit, path, seen, t0, read_bytes = [], "", "", set(), time.monotonic(), 0
    assert proc.stdout
    for raw in proc.stdout:
        read_bytes += len(raw)
        if read_bytes > max_bytes or time.monotonic() - t0 > max_seconds:
            found.append("(history scan truncated - repo too large)")
            break
        line = raw.decode("utf-8", errors="replace")
        if line.startswith("\x1e"):
            commit = line[1:].strip()
            continue
        if line.startswith("+++ "):
            path = line[4:].strip().removeprefix("b/")
            continue
        if line.startswith("+") and commit not in seen and not TEST_PATH.search(path):
            for pid, rx in patterns:
                if rx.search(line):
                    found.append(f"{commit} [{pid}]")
                    seen.add(commit)
                    break
    proc.kill()
    proc.stdout.close()
    proc.wait()
    return found


def render(reps: list[Report], summary: bool = False) -> str:
    """summary=True: scores and finding counts only, no file:line evidence. That is the form safe to
    commit - a full evidence table is a map of where every credential lives (see .gitignore creds.csv)."""
    L = []
    if summary:
        ids = sorted({f.id for r in reps for f in r.findings})
        L += ["| Repo | Score | Band | Critical | High | Medium | Findings |", "|---|---|---|---|---|---|---|"]
        for r in sorted(reps, key=lambda r: r.score):
            n = {s: sum(f.severity == s for f in r.findings) for s in SEV_COST}
            L.append(f"| {r.repo} | {r.score} | {r.band} | {n['critical']} | {n['high']} | {n['medium']} | "
                     f"{', '.join(sorted(f.id for f in r.findings if f.severity in ('critical', 'high')))} |")
        L += ["", "| Finding | Repos |", "|---|---|"]
        for i in ids:
            L.append(f"| `{i}` | {sum(any(f.id == i for f in r.findings) for r in reps)} |")
        return "\n".join(L)
    if len(reps) > 1:
        L += ["| Repo | Score | Band | Critical | High | Rework % | Stack |", "|---|---|---|---|---|---|---|"]
        for r in sorted(reps, key=lambda r: r.score):
            c = sum(f.severity == "critical" for f in r.findings)
            h = sum(f.severity == "high" for f in r.findings)
            L.append(f"| {r.repo} | {r.score} | {r.band} | {c} | {h} | {r.facts.get('rework_pct', 0)} | {', '.join(r.architecture.get('stack', [])[:5])} |")
        L.append("")
    for r in reps:
        a, fa = r.architecture, r.facts
        L += [f"## {r.repo} — {r.score}/100 ({r.band})", "",
              f"{fa['commits']} commits ({fa['span']}), {fa['rework_pct']}% fix-like · branch `{fa['branch']}` · origin/HEAD `{fa['origin_head']}`", "",
              "**Architecture.** " + "; ".join([
                  f"stack: {', '.join(a['stack']) or 'unknown'}",
                  f"top-level: {', '.join(a['top_level_dirs'][:12])}",
                  f"{a['api_routes']} API routes", f"{a['sql_migrations']} SQL migrations",
                  f"{len(a['edge_functions'])} edge functions", f"{a['test_files']} test files",
                  f"CI: {', '.join(a['ci_workflows']) or 'none'}",
                  f"agent docs: {', '.join(a['agent_docs']) or 'none'}",
                  f"code graph: {'yes' if a['code_graph'] else 'no'}"]), ""]
        if r.findings:
            L += ["| Sev | Finding | Lesson | Evidence |", "|---|---|---|---|"]
            order = ["critical", "high", "medium", "low"]
            for f in sorted(r.findings, key=lambda f: order.index(f.severity)):
                ev = "<br>".join(e.replace("|", "/") for e in f.evidence[:6]) + (f"<br>…+{len(f.evidence) - 6}" if len(f.evidence) > 6 else "")
                L.append(f"| {f.severity} | {f.title} | {f.lesson} | {ev} |")
        else:
            L.append("No findings from the automated checks.")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--root", default=str(GITHUB))
    ap.add_argument("--min-commits", type=int, default=10)
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--summary", action="store_true", help="scores and counts only - safe to commit")
    ap.add_argument("--out")
    a = ap.parse_args()
    patterns = shim.load_patterns()
    if a.all:
        repos = [p for p in sorted(Path(a.root).iterdir()) if (p / ".git").exists() and " - Copy" not in p.name]
        repos = [p for p in repos if (git(p, "rev-list", "--all", "--count").strip() or "0").isdigit()
                 and int(git(p, "rev-list", "--all", "--count").strip() or 0) >= a.min_commits]
    elif a.repo:
        repos = [Path(a.repo).resolve()]
    else:
        ap.error("give a repo path or --all")
    reps = []
    for p in repos:
        reps.append(audit(p, patterns, history=not a.no_history))
        print(f"audited {p.name}: {reps[-1].score}/100", flush=True) if a.out else None
    out = json.dumps([{**asdict(r), "score": r.score, "band": r.band} for r in reps], indent=2) if a.json else render(reps, summary=a.summary)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    main()
