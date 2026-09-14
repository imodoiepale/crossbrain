#!/usr/bin/env bash
# crossbrain one-line installer (macOS / Linux / WSL / Git Bash)
#
#   curl -fsSL https://raw.githubusercontent.com/imodoiepale/crossbrain/main/install.sh | bash
#
# Clones (or updates) the engine into ~/.crossbrain/engine, puts a `crossbrain` launcher on your PATH,
# and installs skills, agents and instructions into every agent CLI it finds. Re-run to update.
# Read it first if you like - it is short, and it never asks for or stores a credential.
set -euo pipefail

REPO="${CROSSBRAIN_REPO:-https://github.com/imodoiepale/crossbrain.git}"
HOME_DIR="${CROSSBRAIN_HOME:-$HOME/.crossbrain}"
ENGINE="$HOME_DIR/engine"
BIN="${CROSSBRAIN_BIN:-$HOME/.local/bin}"

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required"
# Try each candidate for real: on Windows, `python3` is often a Microsoft Store stub that exists on PATH
# but only prints "Python was not found", so `command -v` alone picks a Python that cannot run.
PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    PY="$(command -v "$candidate")"
    break
  fi
done
[ -n "$PY" ] || die "python 3.9+ is required (tried python3, python, py)"

if [ -d "$ENGINE/.git" ]; then
  say "updating $ENGINE"
  git -C "$ENGINE" pull --ff-only --quiet
else
  say "cloning crossbrain into $ENGINE"
  mkdir -p "$HOME_DIR"
  git clone --depth 1 --quiet "$REPO" "$ENGINE"
fi

mkdir -p "$BIN"
cat > "$BIN/crossbrain" <<EOF
#!/usr/bin/env bash
exec "$PY" "$ENGINE/crossbrain.py" "\$@"
EOF
chmod +x "$BIN/crossbrain"
case ":$PATH:" in *":$BIN:"*) ;; *) say "add $BIN to your PATH to use the 'crossbrain' command";; esac

"$PY" "$ENGINE/crossbrain.py" install "$@"
"$PY" "$ENGINE/crossbrain.py" doctor
