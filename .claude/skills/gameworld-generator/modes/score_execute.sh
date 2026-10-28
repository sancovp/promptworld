#!/bin/bash
# execute.sh — Score/Benchmark Mode
# Actions: benchmark_submit, benchmark_claim, learn
# Gold = score. No spending. Max attainable visible for self-assessment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_FILE="$SCRIPT_DIR/game.json"

ACTION_JSON="${1:-}"
if [[ -z "$ACTION_JSON" ]]; then
  echo "Usage: execute.sh '<json action>'" >&2
  exit 1
fi

AGENT_ID=$(basename "$(cd "$SCRIPT_DIR/.." && pwd)")
ACTION_TYPE=$(echo "$ACTION_JSON" | jq -r '.action.type' 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

case "$ACTION_TYPE" in

  benchmark_submit)
    BENCHMARK_ID=$(echo "$ACTION_JSON" | jq -r '.action.benchmark_id // .action.quest_id')
    CRAFT_PATH=$(echo "$ACTION_JSON" | jq -r '.action.craft_path')
    if [[ ! -f "$SCRIPT_DIR/$CRAFT_PATH" ]]; then
      echo "ERROR: Craft file not found at $CRAFT_PATH" >&2; exit 1
    fi
    BENCHMARK_FILE="$SCRIPT_DIR/things/quests/${BENCHMARK_ID}.md"
    if [[ ! -f "$BENCHMARK_FILE" ]]; then
      echo "ERROR: Benchmark $BENCHMARK_ID not found" >&2; exit 1
    fi
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg bid "$BENCHMARK_ID" --arg path "$CRAFT_PATH" \
       --arg ts "$TIMESTAMP" \
      '.benchmark_log[$id] = (.benchmark_log[$id] // []) + [{benchmark_id: $bid, craft_path: $path, submitted_at: $ts, status: "submitted"}]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] submitted $BENCHMARK_ID for scoring"
    ;;

  benchmark_claim)
    BENCHMARK_ID=$(echo "$ACTION_JSON" | jq -r '.action.benchmark_id // .action.quest_id')
    BENCHMARK_ENTRY=$(jq --arg id "$AGENT_ID" --arg bid "$BENCHMARK_ID" \
      '[.benchmark_log[$id] // [][] | select(.benchmark_id == $bid and .status == "submitted")] | first' \
      "$GAME_FILE" 2>/dev/null || echo "null")
    if [[ "$BENCHMARK_ENTRY" == "null" || -z "$BENCHMARK_ENTRY" ]]; then
      echo "ERROR: No submitted benchmark $BENCHMARK_ID found" >&2; exit 1
    fi
    BENCHMARK_FILE="$SCRIPT_DIR/things/quests/${BENCHMARK_ID}.md"
    REWARD=$(grep -A2 '## Reward' "$BENCHMARK_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "50")
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg bid "$BENCHMARK_ID" \
       --argjson reward "$REWARD" --arg ts "$TIMESTAMP" \
      '.agents[$id].gold += $reward |
       .agents[$id].benchmarks_completed += 1 |
       .benchmark_log[$id] = [.benchmark_log[$id][]? | if .benchmark_id == $bid then .status = "claimed" | .claimed_at = $ts else . end]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] claimed benchmark $BENCHMARK_ID — earned $REWARD score"
    ;;

  learn)
    DOMAIN=$(echo "$ACTION_JSON" | jq -r '.action.domain')
    TOPIC=$(echo "$ACTION_JSON" | jq -r '.action.topic')
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg domain "$DOMAIN" --arg topic "$TOPIC" \
       --arg ts "$TIMESTAMP" \
      '.agents[$id].last_action = "learn" |
       .agents[$id].last_action_at = $ts' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] studied $DOMAIN/$TOPIC"
    ;;

  *)
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg atype "$ACTION_TYPE" --arg ts "$TIMESTAMP" \
      '.agents[$id].last_action = $atype | .agents[$id].last_action_at = $ts' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] executed: $ACTION_TYPE"
    ;;
esac
