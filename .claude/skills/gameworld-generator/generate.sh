#!/bin/bash
# generate.sh — Generate a gameworld from a mode config
#
# Usage:
#   ./generate.sh <mode> [output_dir]
#   ./generate.sh /path/to/custom-mode.json [output_dir]
#   ./generate.sh --list
#   ./generate.sh --extract /path/to/existing/gameworld

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODES_DIR="$SCRIPT_DIR/modes"
LIB_DIR="$SCRIPT_DIR/lib"

# --list: show available modes
if [[ "${1:-}" == "--list" ]]; then
  echo "Available modes:"
  for f in "$MODES_DIR"/*.json; do
    if [[ -f "$f" ]]; then
      name=$(jq -r '.mode_name // .mode_id' "$f" 2>/dev/null)
      desc=$(jq -r '.description // ""' "$f" 2>/dev/null)
      echo "  - $(basename "$f" .json): $desc"
    fi
  done
  exit 0
fi

# --extract: reflexive loop — extract mode config from existing gameworld
if [[ "${1:-}" == "--extract" ]]; then
  if [[ -z "${2:-}" ]]; then
    echo "ERROR: --extract requires a gameworld path" >&2
    exit 1
  fi
  exec "$LIB_DIR/extract-mode.sh" "${2}"
fi

MODE_ARG="${1:-}"
OUTPUT_DIR="${2:-$(pwd)/gameworlds}"

if [[ -z "$MODE_ARG" ]]; then
  echo "Usage: generate.sh <mode> [output_dir]" >&2
  echo "       generate.sh --list" >&2
  echo "       generate.sh --extract /path/to/gameworld" >&2
  exit 1
fi

# Resolve mode: built-in or custom path
if [[ -f "$MODE_ARG" ]]; then
  MODE_FILE="$MODE_ARG"
else
  MODE_FILE="$MODES_DIR/${MODE_ARG}.json"
fi

if [[ ! -f "$MODE_FILE" ]]; then
  echo "ERROR: Mode '$MODE_ARG' not found" >&2
  echo "Run --list to see available modes, or pass a path to a .json file" >&2
  exit 1
fi

# Validate mode config
"$LIB_DIR/validate-mode.sh" "$MODE_FILE"

# Create output directory
GAMEWORLD_NAME=$(jq -r '.mode_id' "$MODE_FILE")
GAMEWORLD_OUTPUT="$OUTPUT_DIR/$GAMEWORLD_NAME"

if [[ -d "$GAMEWORLD_OUTPUT" ]]; then
  echo "WARNING: Output directory $GAMEWORLD_OUTPUT already exists. Overwriting." >&2
fi
mkdir -p "$GAMEWORLD_OUTPUT"

# Copy base template
cp -r "$MODES_DIR/base/"* "$GAMEWORLD_OUTPUT/"

# Apply mode config
MODES_DIR="$MODES_DIR" "$LIB_DIR/render-template.sh" "$MODE_FILE" "$GAMEWORLD_OUTPUT"

echo "Generated: $GAMEWORLD_OUTPUT"
echo "  mode: $(jq -r '.mode_name' "$MODE_FILE")"
echo "  craft_type: $(jq -r '.core.craft_type' "$MODE_FILE")"
echo "  earn: $(jq -r '.core.earn.mechanism' "$MODE_FILE")"
echo "  spend: $(jq -r '.core.spend.mechanism' "$MODE_FILE")"
