#!/bin/bash
# extract-mode.sh — Extract mode config from an existing gameworld
# Usage: generate.sh --extract /path/to/gameworld

GAMEWORLD_DIR="${1:-}"

if [[ ! -d "$GAMEWORLD_DIR" ]]; then
  echo "ERROR: Not a directory: $GAMEWORLD_DIR" >&2
  exit 1
fi

GAME_FILE="$GAMEWORLD_DIR/game.json"

if [[ ! -f "$GAME_FILE" ]]; then
  echo "ERROR: No game.json found in $GAMEWORLD_DIR" >&2
  exit 1
fi

GAME_ID=$(jq -r '.game_id' "$GAME_FILE" 2>/dev/null || echo "unknown")
EXEC_FILE="$GAMEWORLD_DIR/execute.sh"

# Detect earn mechanism
HAS_TRADE=$(jq '.trade_board | length' "$GAME_FILE" 2>/dev/null | tr -d '[:space:]' || echo "0")
HAS_BENCHMARKS=$(jq '.benchmarks | length' "$GAME_FILE" 2>/dev/null | tr -d '[:space:]' || echo "0")
HAS_QUEST_LOG=$(jq '.quest_log | length' "$GAME_FILE" 2>/dev/null | tr -d '[:space:]' || echo "0")
HAS_TRADE_HISTORY=$(jq '.trade_history | length' "$GAME_FILE" 2>/dev/null | tr -d '[:space:]' || echo "0")

# Check for story/chapter actions
HAS_CHAPTER=$(grep -E 'chapter_submit|plan_propose' "$EXEC_FILE" 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")

# Check execute.sh for presence of key actions (helps detect even if game state is empty)
HAS_TRADE_IN_EXEC=$(grep -E 'trade_post|trade_buy' "$EXEC_FILE" 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")
HAS_QUEST_IN_EXEC=$(grep -E 'quest_accept|quest_complete' "$EXEC_FILE" 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")

if [[ "$HAS_BENCHMARKS" -gt 0 ]]; then
  EARN_MECH="benchmark"
elif [[ "$HAS_CHAPTER" -gt 0 ]]; then
  EARN_MECH="chapter_submission"
elif [[ ("$HAS_TRADE" -gt 0 || "$HAS_TRADE_IN_EXEC" -gt 0) && ("$HAS_QUEST_LOG" -gt 0 || "$HAS_QUEST_IN_EXEC" -gt 0) ]]; then
  EARN_MECH="quest_plus_trade"
elif [[ "$HAS_QUEST_LOG" -gt 0 || "$HAS_QUEST_IN_EXEC" -gt 0 ]]; then
  EARN_MECH="quest"
elif [[ "$HAS_TRADE" -gt 0 || "$HAS_TRADE_HISTORY" -gt 0 || "$HAS_TRADE_IN_EXEC" -gt 0 ]]; then
  EARN_MECH="trade"
else
  EARN_MECH="submission"
fi

# Detect spend mechanism
if [[ "$HAS_TRADE" -gt 0 || "$HAS_TRADE_HISTORY" -gt 0 || "$HAS_TRADE_IN_EXEC" -gt 0 ]]; then
  SPEND_MECH="trade"
  SPEND_ACTIONS='["trade_post", "trade_buy"]'
else
  SPEND_MECH="none"
  SPEND_ACTIONS='[]'
fi

# Detect craft type from quest files
QUEST_FILES=$(ls "$GAMEWORLD_DIR/things/quests/"*.md 2>/dev/null | grep -v "SKILL.md" | head -5)
if echo "$QUEST_FILES" | grep -qi "cinematic\|website\|site"; then
  CRAFT_TYPE="site"
elif echo "$QUEST_FILES" | grep -qi "chapter\|story"; then
  CRAFT_TYPE="story"
elif echo "$QUEST_FILES" | grep -qi "skill"; then
  CRAFT_TYPE="skill"
else
  CRAFT_TYPE="skill"
fi

# Detect distribution
if [[ "$EARN_MECH" == "chapter_submission" ]]; then
  DISTRIBUTION="team_global"
else
  DISTRIBUTION="individual"
fi

# Extract starting gold from first agent
STARTING_GOLD=$(jq -r '.agents.AGENT_PLACEHOLDER.gold // .agents | values[0].gold // 100' "$GAME_FILE" 2>/dev/null || echo "100")

# Extract actions from execute.sh
ACTIONS=$(grep -E '^\s+[a-z_]+\)' "$EXEC_FILE" 2>/dev/null | sed 's/)//' | sed 's/^[[:space:]]*//' | sort -u | jq -R . | jq -s . 2>/dev/null || echo "[]")

# Extract quest definitions
QUEST_DEFS=$(ls "$GAMEWORLD_DIR/things/quests/"*.md 2>/dev/null | grep -v "SKILL.md" | while read -r f; do
  QUEST_ID=$(basename "$f" .md | sed 's/_/-/g')
  echo "{\"quest_id\": \"$QUEST_ID\", \"file\": \"things/quests/$(basename $f)\", \"include\": true}"
done | jq -s . 2>/dev/null || echo "[]")

# Extract season config
RESET_TRADE=$(jq -r '.season.reset_trade_board // true' "$GAME_FILE" 2>/dev/null || echo "true")
CARRY_GOLD=$(jq -r '.season.carry_gold // false' "$GAME_FILE" 2>/dev/null || echo "false")

jq -n \
  --arg mode_id "$GAME_ID" \
  --arg mode_name "$GAME_ID" \
  --arg earn_mech "$EARN_MECH" \
  --arg spend_mech "$SPEND_MECH" \
  --arg craft_type "$CRAFT_TYPE" \
  --arg distribution "$DISTRIBUTION" \
  --argjson starting_gold "$STARTING_GOLD" \
  --argjson earn_actions "$ACTIONS" \
  --argjson spend_actions "$SPEND_ACTIONS" \
  --argjson quest_defs "$QUEST_DEFS" \
  --argjson reset_trade "$RESET_TRADE" \
  --argjson carry_gold "$CARRY_GOLD" \
  '{
    mode_id: $mode_id,
    mode_name: $mode_name,
    mode_version: "1.0",
    description: "Extracted from existing gameworld",
    core: {
      earn: { mechanism: $earn_mech, actions: $earn_actions, description: "detected" },
      spend: { mechanism: $spend_mech, actions: $spend_actions, description: "detected" },
      craft_type: $craft_type,
      distribution: $distribution,
      self_assessment: false
    },
    execute_includes: $earn_actions,
    execute_excludes: [],
    starting_gold: $starting_gold,
    quest_definitions: $quest_defs,
    season_config: {
      reset_trade_board: $reset_trade,
      carry_gold: $carry_gold
    }
  }'
