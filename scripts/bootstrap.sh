#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${GIS_CONVERT_REPO:-https://github.com/tyrrs/gis-convert.git}"
INSTALL_DIR="${GIS_CONVERT_HOME:-$HOME/.gis-convert}"

usage() {
  cat <<'USAGE'
gis-convert bootstrap installer

Usage:
  bootstrap.sh [install.py options]

Examples:
  bootstrap.sh
  bootstrap.sh --install claude-code
  bootstrap.sh --install claude-code --with-deps
  bootstrap.sh --install claude-code --dry-run --skip-deps-check --no-interactive

Environment:
  GIS_CONVERT_HOME  Checkout directory. Default: ~/.gis-convert
  GIS_CONVERT_REPO  Git repository URL. Default: https://github.com/tyrrs/gis-convert.git
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v git >/dev/null 2>&1; then
  echo "bootstrap.sh: git is required but was not found in PATH." >&2
  exit 1
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating existing gis-convert checkout: $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only
elif [[ -e "$INSTALL_DIR" ]]; then
  echo "bootstrap.sh: $INSTALL_DIR exists but is not a git checkout." >&2
  echo "Set GIS_CONVERT_HOME to another directory or move the existing path." >&2
  exit 1
else
  echo "Cloning gis-convert into: $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
exec ./scripts/install.sh "$@"
