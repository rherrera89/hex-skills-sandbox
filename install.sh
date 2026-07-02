#!/usr/bin/env bash
#
#   hex-skills installer ✨
#   Drop a Hex skill into a Claude Code project's .claude/skills/ directory.
#
#   Usage:
#     ./install.sh                         # list available skills
#     ./install.sh <skill> [project-dir]   # install a skill (default: current dir)
#
#   Or straight from GitHub, no clone needed:
#     curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- <skill> [project-dir]
#
set -euo pipefail

REPO_URL="https://github.com/rherrera89/hex-skills-sandbox.git"
SKILL="${1:-}"
TARGET="${2:-$PWD}"

say() { printf '  %s\n' "$1"; }
die() { printf '\n  ✗ %s\n\n' "$1" >&2; exit 1; }

command -v git   >/dev/null 2>&1 || die "git is required"
command -v rsync >/dev/null 2>&1 || die "rsync is required"

# Source the skills from the local checkout if we're inside it, else clone a shallow copy.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
CLONED=""
if [ -n "${SCRIPT_DIR:-}" ] && [ -d "$SCRIPT_DIR/.git" ]; then
  SRC="$SCRIPT_DIR"
else
  SRC="$(mktemp -d)"; CLONED="$SRC"
  git clone --depth 1 -q "$REPO_URL" "$SRC" || die "couldn't clone $REPO_URL"
fi
cleanup() { [ -n "$CLONED" ] && rm -rf "$CLONED"; }
trap cleanup EXIT

# No skill given → list what's available and bail.
if [ -z "$SKILL" ]; then
  printf '\n  ✨ hex-skills — available skills:\n\n'
  for d in "$SRC"/*/; do [ -f "${d}SKILL.md" ] && say "• $(basename "$d")"; done
  printf '\n  install with:  ./install.sh <skill> [project-dir]\n\n'
  exit 0
fi

[ -f "$SRC/$SKILL/SKILL.md" ] || die "no skill called '$SKILL' (run with no args to list)"

DEST="$TARGET/.claude/skills/$SKILL"
mkdir -p "$DEST"

# Copy the skill — but never someone's secrets or local scratch.
rsync -a --delete \
  --exclude='.git' \
  --exclude='.DS_Store' \
  --exclude='credentials/tableau.env' \
  --exclude='tableau_exports/' \
  --exclude='working/' \
  "$SRC/$SKILL/" "$DEST/"

printf '\n  ✨ installed %s → %s\n\n' "$SKILL" "$DEST"
say "next:"
[ -f "$DEST/credentials/tableau.env.example" ] && \
  say "• cp .claude/skills/$SKILL/credentials/tableau.env.example → tableau.env and fill it in"
say "• open the project in Claude Code and run  /$SKILL"
printf '\n'
