#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${GIS_CONVERT_REPO:-https://github.com/tyrrs/gis-convert.git}"

usage() {
  cat <<'USAGE'
gis-convert bootstrap installer

Usage:
  bootstrap.sh [install.py options]

Examples:
  bootstrap.sh
  bootstrap.sh --install claude-code
  bootstrap.sh --uninstall claude-code
  bootstrap.sh --uninstall all
  bootstrap.sh --install claude-code --with-deps
  bootstrap.sh --install claude-code --dry-run --skip-deps-check --no-interactive

Environment:
  GIS_CONVERT_HOME           Use a persistent checkout directory instead of a temporary checkout.
  GIS_CONVERT_KEEP_CHECKOUT  Set to 1 to keep the temporary checkout after the run.
  GIS_CONVERT_REPO           Git repository URL. Default: https://github.com/tyrrs/gis-convert.git
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

if [[ -n "${GIS_CONVERT_HOME:-}" ]]; then
  INSTALL_DIR="$GIS_CONVERT_HOME"
  CLEANUP_CHECKOUT=0
else
  TMP_BASE="${TMPDIR:-/tmp}"
  TMP_BASE="${TMP_BASE%/}"
  INSTALL_DIR="$(mktemp -d "$TMP_BASE/gis-convert.XXXXXX")"
  CLEANUP_CHECKOUT=1
fi

if [[ "${GIS_CONVERT_KEEP_CHECKOUT:-}" == "1" ]]; then
  CLEANUP_CHECKOUT=0
fi

cleanup() {
  if [[ "$CLEANUP_CHECKOUT" -eq 1 && -n "${INSTALL_DIR:-}" && -d "$INSTALL_DIR" ]]; then
    echo "Cleaning up temporary checkout: $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
  fi
}

trap cleanup EXIT

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating existing gis-convert checkout: $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only
elif [[ -e "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR")" ]]; then
  echo "bootstrap.sh: $INSTALL_DIR exists but is not a git checkout." >&2
  echo "Set GIS_CONVERT_HOME to another directory or move the existing path." >&2
  exit 1
else
  echo "Cloning gis-convert into: $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

no_interactive=0
for arg in "$@"; do
  if [[ "$arg" == "--no-interactive" ]]; then
    no_interactive=1
    break
  fi
done

if [[ "$no_interactive" -eq 0 && -r /dev/tty && -t 1 ]]; then
  if ./install/install.sh "$@" < /dev/tty; then
    exit 0
  else
    exit $?
  fi
fi

if ./install/install.sh "$@"; then
  exit 0
else
  exit $?
fi
