#!/usr/bin/env bash
# harnessd one-line installer (macOS / Linux / WSL / Git Bash)
#
#   curl -fsSL https://raw.githubusercontent.com/imodoiepale/harnessd/main/install.sh | bash
#
# Clones (or updates) the engine into ~/.harnessd/engine, puts a `harnessd` launcher on your PATH,
# and installs skills, agents and instructions into every agent CLI it finds. Re-run to update.
# Read it first if you like - it is short, and it never asks for or stores a credential.
set -euo pipefail

REPO="${HARNESSD_REPO:-https://github.com/imodoiepale/harnessd.git}"
HOME_DIR="${HARNESSD_HOME:-$HOME/.harnessd}"
ENGINE="$HOME_DIR/engine"
BIN="${HARNESSD_BIN:-$HOME/.local/bin}"

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required"
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || die "python 3.9+ is required"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || die "python 3.9+ is required"

if [ -d "$ENGINE/.git" ]; then
  say "updating $ENGINE"
  git -C "$ENGINE" pull --ff-only --quiet
else
  say "cloning harnessd into $ENGINE"
  mkdir -p "$HOME_DIR"
  git clone --depth 1 --quiet "$REPO" "$ENGINE"
fi

mkdir -p "$BIN"
cat > "$BIN/harnessd" <<EOF
#!/usr/bin/env bash
exec "$PY" "$ENGINE/harnessd.py" "\$@"
EOF
chmod +x "$BIN/harnessd"
case ":$PATH:" in *":$BIN:"*) ;; *) say "add $BIN to your PATH to use the 'harnessd' command";; esac

"$PY" "$ENGINE/harnessd.py" install "$@"
"$PY" "$ENGINE/harnessd.py" doctor
