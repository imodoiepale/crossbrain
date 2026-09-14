"""
The commit gate. Refuses a commit that leaks a secret, ships a huge blob, or lands on a protected branch.

    python scripts/preflight.py                 # whole working tree of the current repo
    python scripts/preflight.py --staged        # staged files only (pre-commit hook mode)
    python scripts/preflight.py path/to/repo --allow-protected-branch

Exit 0 = clean, 1 = blocked. Findings show file:line, pattern id and an 8-character prefix, never a
full secret. Patterns live in secret-patterns.txt, shared with the memory redaction shim, so the gate
and the redactor cannot drift apart.

Each check exists because its absence has already cost someone:
  secret  - a key pasted "just for a minute" is burned forever once pushed; history keeps it
  size    - one committed zip or sqlite makes every clone of the repo huge, permanently
  branch  - work that skips review on main is how untested changes reach production
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import memory_redact_shim as shim

PLACEHOLDER = re.compile(r"FAKE|EXAMPLE|PLACEHOLDER|XXXX|your[_-]?key|<[a-z]", re.I)
SKIP_CONTENT = re.compile(r"\.(png|jpe?g|gif|webp|ico|pdf|zip|gz|tgz|7z|mp3|mp4|wav|woff2?|ttf|otf|eot|sqlite3?|db|exe|dll|"
                          r"nupkg|blob|lock)$|(^|/)(node_modules|\.next|dist|build|graphify-out|\.git)/", re.I)
# Files that exist to hold realistic-looking fake keys. Scanning them makes the gate fail its own CI.
FIXTURE_FILES = re.compile(r"(^|/)(test_preflight\.py|test-preflight\.ps1)$")
ENV_FILE = re.compile(r"(^|/)\.env(\.[\w-]+)?$")


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def check(repo: Path, staged: bool = False, max_mb: float = 5.0, protected=("main", "master", "develop"),
          allow_protected: bool = False) -> tuple[list[str], list[str]]:
    failures, warnings = [], []
    if git(repo, "rev-parse", "--is-inside-work-tree").strip() != "true":
        return [f"{repo} is not a git repository"], []

    # symbolic-ref, not rev-parse --abbrev-ref: on a repo with no commits yet rev-parse answers "HEAD",
    # which would let the very first commit onto main slip past the branch check.
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").strip() or git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in protected and not allow_protected:
        failures.append(f"[branch] you are on '{branch}'. Cut a branch and open a PR, or pass --allow-protected-branch "
                        "for a deliberate direct commit.")

    listing = git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACM") if staged else \
        git(repo, "ls-files", "--cached", "--others", "--exclude-standard")
    files = [f for f in listing.splitlines() if f and (repo / f).is_file()]
    patterns = shim.load_patterns()

    for f in files:
        p = repo / f
        size = p.stat().st_size
        if size > max_mb * 1_000_000:
            failures.append(f"[size] {f} is {size / 1_000_000:.1f} MB (limit {max_mb:g} MB). Git keeps it forever, in "
                            "every clone. Use Git LFS, ignore it, or host it elsewhere.")
        if ENV_FILE.search(f) and not f.endswith((".example", ".sample", ".template")):
            failures.append(f"[secret] {f} is a .env file about to be committed. Env files must never be tracked.")
        if SKIP_CONTENT.search(f) or FIXTURE_FILES.search(f) or size > 2_000_000:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for pid, rx in patterns:
            hits = [m for m in rx.finditer(text) if not PLACEHOLDER.search(m.group(0))]
            if hits:
                line = text.count("\n", 0, hits[0].start()) + 1
                sample = hits[0].group(0)
                shown = sample[:8] + "...<REDACTED>" if len(sample) > 8 else "<REDACTED>"
                more = f" ({len(hits)} matches)" if len(hits) > 1 else ""
                failures.append(f"[secret] {f}:{line} [{pid}] {shown}{more}")

    if not (repo / ".gitignore").exists():
        warnings.append("[hygiene] no .gitignore - that is how build output and .env files get committed")
    return failures, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="harnessd commit gate")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--max-mb", type=float, default=5.0)
    ap.add_argument("--allow-protected-branch", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.path).resolve()
    failures, warnings = check(repo, a.staged, a.max_mb, allow_protected=a.allow_protected_branch)
    print(f"preflight: {repo}")
    for w in warnings:
        print("  warn " + w)
    if failures:
        for f in failures:
            print("  FAIL " + f)
        print(f"\npreflight FAILED - {len(failures)} blocking issue(s). If a secret was already pushed anywhere, rotate it.")
        return 1
    print("preflight CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
