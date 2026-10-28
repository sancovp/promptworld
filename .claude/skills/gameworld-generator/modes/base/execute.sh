#!/bin/bash
# execute.sh — WoS BASE economy engine
# Core actions: quest_accept, quest_complete, trade_post, trade_buy, learn
# ALL game logic lives here. Agent ID from directory name only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_FILE="$SCRIPT_DIR/game.json"

ACTION_JSON="${1:-}"
if [[ -z "$ACTION_JSON" ]]; then
  echo "Usage: execute.sh '<json action>'" >&2
  exit 1
fi

# Agent ID: prefer explicit agent_id in JSON, else derive from directory structure
EXPLICIT_ID=$(echo "$ACTION_JSON" | jq -r '.agent_id // .action.agent_id // empty' 2>/dev/null)
if [[ -n "$EXPLICIT_ID" ]]; then
  AGENT_ID="$EXPLICIT_ID"
else
  AGENT_ID=$(basename "$(cd "$SCRIPT_DIR/.." && pwd)")
fi
ACTION_TYPE=$(echo "$ACTION_JSON" | jq -r '.action.type' 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

case "$ACTION_TYPE" in

  quest_accept)
    QUEST_ID=$(echo "$ACTION_JSON" | jq -r '.action.quest_id')
    ALREADY=$(jq --arg id "$AGENT_ID" --arg qid "$QUEST_ID" \
      '[(.quest_log[$id] // [])[] | select(.quest_id == $qid)] | length' \
      "$GAME_FILE" 2>/dev/null || echo "0")
    if [[ "$ALREADY" != "0" ]]; then
      echo "ERROR: Quest $QUEST_ID already accepted" >&2; exit 1
    fi
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg qid "$QUEST_ID" --arg ts "$TIMESTAMP" \
      '.quest_log[$id] = (.quest_log[$id] // []) + [{quest_id: $qid, accepted_at: $ts, status: "active"}]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] accepted quest: $QUEST_ID"
    ;;

  quest_complete)
    QUEST_ID=$(echo "$ACTION_JSON" | jq -r '.action.quest_id')
    SKILL_PATH=$(echo "$ACTION_JSON" | jq -r '.action.skill_path // empty')
    QUEST_FILE="$SCRIPT_DIR/things/quests/${QUEST_ID}.md"
    if [[ ! -f "$QUEST_FILE" ]]; then
      echo "ERROR: Quest $QUEST_ID not found at $QUEST_FILE" >&2; exit 1
    fi
    REWARD=$(grep -A2 '## Reward' "$QUEST_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "50")
    QUEST_STATUS=$(jq --arg id "$AGENT_ID" --arg qid "$QUEST_ID" \
      '(.quest_log[$id] // [])[] | select(.quest_id == $qid and .status == "active") | .status' \
      "$GAME_FILE" 2>/dev/null || echo "")
    if [[ -z "$QUEST_STATUS" ]]; then
      echo "ERROR: Quest $QUEST_ID not active" >&2; exit 1
    fi
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg qid "$QUEST_ID" --arg sp "$SKILL_PATH" \
       --argjson reward "$REWARD" --arg ts "$TIMESTAMP" \
      '.agents[$id].gold += $reward |
       .agents[$id].quests_completed += 1 |
       .quest_log[$id] = [.quest_log[$id][]? | if .quest_id == $qid then .status = "completed" | .completed_at = $ts | .skill_path = $sp else . end]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] completed quest $QUEST_ID — earned $REWARD gold"
    ;;

  trade_post)
    SKILL_PATH=$(echo "$ACTION_JSON" | jq -r '.action.skill_path')
    PRICE=$(echo "$ACTION_JSON" | jq -r '.action.price')
    DESCRIPTION=$(echo "$ACTION_JSON" | jq -r '.action.description // "No description"')
    RARITY=$(echo "$ACTION_JSON" | jq -r '.action.rarity // "common"')
    if (( PRICE <= 0 )); then
      echo "ERROR: Price must be positive" >&2; exit 1
    fi
    LISTING_ID="listing_$(date +%s)_${RANDOM}_${AGENT_ID}"
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg lid "$LISTING_ID" --arg sp "$SKILL_PATH" \
       --arg desc "$DESCRIPTION" --arg rarity "$RARITY" --argjson price "$PRICE" \
       --arg ts "$TIMESTAMP" \
      '.trade_board += [{listing_id: $lid, seller: $id, skill_path: $sp, price: $price, rarity: $rarity, description: $desc, posted_at: $ts}]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] posted [$RARITY] $SKILL_PATH for $PRICE gold"
    ;;

  trade_buy)
    LISTING_ID=$(echo "$ACTION_JSON" | jq -r '.action.listing_id')
    LISTING=$(jq --arg lid "$LISTING_ID" '.trade_board[] | select(.listing_id == $lid)' "$GAME_FILE")
    if [[ -z "$LISTING" || "$LISTING" == "null" ]]; then
      echo "ERROR: Listing $LISTING_ID not found" >&2; exit 1
    fi
    SELLER=$(echo "$LISTING" | jq -r '.seller')
    PRICE=$(echo "$LISTING" | jq -r '.price')
    BUYER_GOLD=$(jq --arg id "$AGENT_ID" '.agents[$id].gold' "$GAME_FILE")
    if [[ "$AGENT_ID" == "$SELLER" ]]; then
      echo "ERROR: Cannot buy your own listing" >&2; exit 1
    fi
    if (( BUYER_GOLD < PRICE )); then
      echo "ERROR: Not enough gold. Have $BUYER_GOLD, need $PRICE" >&2; exit 1
    fi
    TEMP=$(mktemp)
    jq --arg buyer "$AGENT_ID" --arg seller "$SELLER" --arg lid "$LISTING_ID" \
       --argjson price "$PRICE" --arg ts "$TIMESTAMP" \
      '.agents[$buyer].gold -= $price |
       .agents[$seller].gold += $price |
       .agents[$buyer].trades_completed += 1 |
       .agents[$seller].trades_completed += 1 |
       .trade_board = [.trade_board[] | select(.listing_id != $lid)] |
       .trade_history += [{listing_id: $lid, seller: $seller, buyer: $buyer, price: $price, at: $ts}]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] bought listing $LISTING_ID from $SELLER for $PRICE gold"
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
