#!/bin/bash
# validate-mode.sh — Validate mode config structure

MODE_FILE="${1:-}"

if [[ -z "$MODE_FILE" || ! -f "$MODE_FILE" ]]; then
  echo "ERROR: Mode file not found: $MODE_FILE" >&2
  exit 1
fi

VALID_EARN=("quest" "trade" "benchmark" "chapter_submission" "submission" "quest_plus_trade" "none")
VALID_SPEND=("trade" "none")
VALID_CRAFT=("site" "story" "skill" "plugin" "recipe")
VALID_DIST=("individual" "team_global" "tiered")

# Check required fields
mode_id=$(jq -r '.mode_id // "MISSING"' "$MODE_FILE")
if [[ "$mode_id" == "MISSING" || -z "$mode_id" ]]; then
  echo "ERROR: Missing required field: mode_id" >&2
  exit 1
fi

mode_name=$(jq -r '.mode_name // "MISSING"' "$MODE_FILE")
if [[ "$mode_name" == "MISSING" || -z "$mode_name" ]]; then
  echo "ERROR: Missing required field: mode_name" >&2
  exit 1
fi

earn_mech=$(jq -r '.core.earn.mechanism // "MISSING"' "$MODE_FILE")
if [[ "$earn_mech" == "MISSING" ]]; then
  echo "ERROR: Missing required field: core.earn.mechanism" >&2
  exit 1
fi

spend_mech=$(jq -r '.core.spend.mechanism // "MISSING"' "$MODE_FILE")
if [[ "$spend_mech" == "MISSING" ]]; then
  echo "ERROR: Missing required field: core.spend.mechanism" >&2
  exit 1
fi

craft_type=$(jq -r '.core.craft_type // "MISSING"' "$MODE_FILE")
if [[ "$craft_type" == "MISSING" ]]; then
  echo "ERROR: Missing required field: core.craft_type" >&2
  exit 1
fi

# Validate enums
is_valid=0
for v in "${VALID_EARN[@]}"; do [[ "$v" == "$earn_mech" ]] && is_valid=1 && break; done
if [[ $is_valid -eq 0 ]]; then
  echo "ERROR: Invalid earn.mechanism: '$earn_mech'. Valid: ${VALID_EARN[*]}" >&2
  exit 1
fi

is_valid=0
for v in "${VALID_SPEND[@]}"; do [[ "$v" == "$spend_mech" ]] && is_valid=1 && break; done
if [[ $is_valid -eq 0 ]]; then
  echo "ERROR: Invalid spend.mechanism: '$spend_mech'. Valid: ${VALID_SPEND[*]}" >&2
  exit 1
fi

is_valid=0
for v in "${VALID_CRAFT[@]}"; do [[ "$v" == "$craft_type" ]] && is_valid=1 && break; done
if [[ $is_valid -eq 0 ]]; then
  echo "ERROR: Invalid craft_type: '$craft_type'. Valid: ${VALID_CRAFT[*]}" >&2
  exit 1
fi

distribution=$(jq -r '.core.distribution // "individual"' "$MODE_FILE")
is_valid=0
for v in "${VALID_DIST[@]}"; do [[ "$v" == "$distribution" ]] && is_valid=1 && break; done
if [[ $is_valid -eq 0 ]]; then
  echo "ERROR: Invalid distribution: '$distribution'. Valid: ${VALID_DIST[*]}" >&2
  exit 1
fi

echo "Mode config valid: $mode_id"
