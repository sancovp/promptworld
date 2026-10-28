#!/bin/bash
# deity-season.sh — season management for World of Skillcraft
# Usage: deity-season.sh <command> [args...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_FILE="$SCRIPT_DIR/game.json"
BUG_FILE="$SCRIPT_DIR/bug_reports.json"

if [[ ! -f "$GAME_FILE" ]]; then
  echo "ERROR: game.json not found at $GAME_FILE" >&2
  exit 1
fi

COMMAND="${1:-}"

case "$COMMAND" in

  show)
    echo "=== CURRENT SEASON ==="
    jq '.season' "$GAME_FILE"
    echo ""
    echo "=== AGENTS ==="
    jq '.agents' "$GAME_FILE"
    echo ""
    echo "Trade board: $(jq '.trade_board | length' "$GAME_FILE") listings"
    echo "Trade history: $(jq '.trade_history | length' "$GAME_FILE") trades"
    RACE_COUNT=$(jq '.races // {} | length' "$GAME_FILE")
    if [[ "$RACE_COUNT" -gt 0 ]]; then
      echo "Races: $RACE_COUNT crystallized"
    fi
    if [[ -f "$BUG_FILE" ]]; then
      OPEN=$(jq '[.[] | select(.status == "open")] | length' "$BUG_FILE")
      VALID=$(jq '[.[] | select(.status == "valid" and .reward_paid == false)] | length' "$BUG_FILE")
      echo "Bug reports: $OPEN open, $VALID validated (unpaid)"
    fi
    ;;

  advance)
    CURRENT_NUM=$(jq '.season.number' "$GAME_FILE")
    NEXT_NUM=$((CURRENT_NUM + 1))

    # Pay bug bounties before resetting gold
    BOUNTY_LOG=""
    if [[ -f "$BUG_FILE" ]]; then
      # Find valid, unpaid bugs and pay 100g each
      VALID_BUGS=$(jq -r '[.[] | select(.status == "valid" and .reward_paid == false)] | length' "$BUG_FILE")
      if [[ "$VALID_BUGS" -gt 0 ]]; then
        # Get list of reporters and their bug counts
        REPORTERS=$(jq -r '[.[] | select(.status == "valid" and .reward_paid == false)] | group_by(.reporter) | .[] | "\(.[0].reporter) \(length)"' "$BUG_FILE")
        while IFS=' ' read -r REPORTER COUNT; do
          REWARD=$((COUNT * 100))
          BOUNTY_LOG="$BOUNTY_LOG  $REPORTER: $COUNT bug(s) = ${REWARD}g bounty\n"
        done <<< "$REPORTERS"

        # Mark all valid bugs as paid
        TEMP=$(mktemp)
        jq '[.[] | if .status == "valid" and .reward_paid == false then .reward_paid = true else . end]' "$BUG_FILE" > "$TEMP" && mv "$TEMP" "$BUG_FILE"
      fi
    fi

    TEMP=$(mktemp)
    # Collect completed quests from quest_log before clearing it
    TEMP_QC=$(mktemp)
    jq '
      .quest_log as $ql |
      .agents = (.agents | to_entries | map(
        .key as $id |
        .value.completed_quests = ((.value.completed_quests // []) + [($ql[$id] // [])[] | select(.status == "completed") | .quest_id] | unique)
      ) | from_entries)
    ' "$GAME_FILE" > "$TEMP_QC" && mv "$TEMP_QC" "$GAME_FILE"

    jq --argjson next "$NEXT_NUM" '
      .season as $current |
      .season = {
        "number": $next,
        "title": null,
        "started_at": null,
        "previous_season": {
          "number": $current.number,
          "title": ($current.title // "Untitled"),
          "rarity_consensus": $current.rarity_consensus,
          "top_performer": ($current.top_performer // null),
          "notable_events": ($current.notable_events // [])
        },
        "rarity_consensus": $current.rarity_consensus
      } |
      .agents = (.agents | to_entries | map(
        .value.lifetime_skills = ((.value.lifetime_skills // 0) + (.value.skills_crafted // 0)) |
        .value.lifetime_trades = ((.value.lifetime_trades // 0) + (.value.trades_completed // 0)) |
        .value.lifetime_quests = ((.value.lifetime_quests // 0) + (.value.quests_completed // 0)) |
        .value.last_action = null |
        .value.last_action_at = null |
        .value.skills_crafted = 0 |
        .value.trades_completed = 0 |
        .value.quests_completed = 0
      ) | from_entries) |
      .trade_board = [] |
      .trade_history = [] |
      .lfg_board = [] |
      .quest_log = {}
    ' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"

    # Now add bounty gold on top of the 100g reset
    # Use the BOUNTY_LOG from the first pass (lines 46-51) which only counted JUST-paid bugs
    if [[ -n "$BOUNTY_LOG" ]]; then
      # Re-parse the bounty log we built during the first pass
      echo -e "$BOUNTY_LOG" | while IFS=': ' read -r REPORTER REST; do
        REPORTER=$(echo "$REPORTER" | tr -d ' ')
        COUNT=$(echo "$REST" | grep -oE '^[0-9]+' || echo "0")
        if [[ -n "$REPORTER" && "$COUNT" -gt 0 ]]; then
          REWARD=$((COUNT * 100))
          TEMP2=$(mktemp)
          jq --arg id "$REPORTER" --argjson reward "$REWARD" '.agents[$id].gold += $reward' "$GAME_FILE" > "$TEMP2" && mv "$TEMP2" "$GAME_FILE"
        fi
      done
    fi

    echo "Advanced to Season $NEXT_NUM. Season $CURRENT_NUM archived as previous_season."
    echo "Boards cleared. Gold preserved. Completed quests locked. Rarity consensus ratcheted."
    if [[ -n "$BOUNTY_LOG" ]]; then
      echo ""
      echo "=== BUG BOUNTIES PAID ==="
      echo -e "$BOUNTY_LOG"
    fi
    ;;

  reset)
    # Collect completed quests before clearing quest_log
    TEMP_QC=$(mktemp)
    jq '
      .quest_log as $ql |
      .agents = (.agents | to_entries | map(
        .key as $id |
        .value.completed_quests = ((.value.completed_quests // []) + [($ql[$id] // [])[] | select(.status == "completed") | .quest_id] | unique)
      ) | from_entries)
    ' "$GAME_FILE" > "$TEMP_QC" && mv "$TEMP_QC" "$GAME_FILE"

    TEMP=$(mktemp)
    jq '
      .agents = (.agents | to_entries | map(
        .value.lifetime_skills = ((.value.lifetime_skills // 0) + (.value.skills_crafted // 0)) |
        .value.lifetime_trades = ((.value.lifetime_trades // 0) + (.value.trades_completed // 0)) |
        .value.lifetime_quests = ((.value.lifetime_quests // 0) + (.value.quests_completed // 0)) |
        .value.last_action = null |
        .value.last_action_at = null |
        .value.skills_crafted = 0 |
        .value.trades_completed = 0 |
        .value.quests_completed = 0
      ) | from_entries) |
      .trade_board = [] |
      .trade_history = [] |
      .lfg_board = [] |
      .quest_log = {}
    ' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"

    echo "Season $(jq '.season.number' "$GAME_FILE") reset. Boards cleared. Gold preserved."
    ;;

  rollback)
    HAS_PREV=$(jq '.season.previous_season // null' "$GAME_FILE")
    if [[ "$HAS_PREV" == "null" ]]; then
      echo "ERROR: No previous season to rollback to." >&2
      exit 1
    fi

    TEMP=$(mktemp)
    jq '
      .season.previous_season as $prev |
      .season = {
        "number": $prev.number,
        "title": $prev.title,
        "started_at": null,
        "rarity_consensus": $prev.rarity_consensus,
        "top_performer": ($prev.top_performer // null),
        "notable_events": ($prev.notable_events // [])
      } |
      .agents = (.agents | to_entries | map(.value.gold = 100 | .value.last_action = null | .value.last_action_at = null | .value.skills_crafted = 0 | .value.trades_completed = 0 | .value.quests_completed = 0) | from_entries) |
      .trade_board = [] |
      .trade_history = [] |
      .lfg_board = [] |
      .quest_log = {}
    ' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"

    ROLLED=$(jq '.season.number' "$GAME_FILE")
    echo "Rolled back to Season $ROLLED. Boards cleared, gold reset."
    ;;

  title)
    TITLE="${2:-}"
    if [[ -z "$TITLE" ]]; then
      echo "Usage: deity-season.sh title \"Season Name\"" >&2
      exit 1
    fi
    TEMP=$(mktemp)
    jq --arg t "$TITLE" '.season.title = $t' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "Season titled: $TITLE"
    ;;

  event)
    EVENT="${2:-}"
    if [[ -z "$EVENT" ]]; then
      echo "Usage: deity-season.sh event \"What happened\"" >&2
      exit 1
    fi
    TEMP=$(mktemp)
    jq --arg e "$EVENT" '.season.notable_events = (.season.notable_events // []) + [$e]' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "Recorded: $EVENT"
    ;;

  winner)
    WINNER="${2:-}"
    if [[ -z "$WINNER" ]]; then
      echo "Usage: deity-season.sh winner \"agent_001 (400g, 3 sales)\"" >&2
      exit 1
    fi
    TEMP=$(mktemp)
    jq --arg w "$WINNER" '.season.top_performer = $w' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "Top performer: $WINNER"
    ;;

  bugs)
    if [[ ! -f "$BUG_FILE" ]]; then
      echo "No bug reports filed yet."
      exit 0
    fi

    echo "=== BUG REPORTS ==="
    echo ""
    TOTAL=$(jq '. | length' "$BUG_FILE")
    OPEN=$(jq '[.[] | select(.status == "open")] | length' "$BUG_FILE")
    VALID=$(jq '[.[] | select(.status == "valid")] | length' "$BUG_FILE")
    INVALID=$(jq '[.[] | select(.status == "invalid")] | length' "$BUG_FILE")
    UNPAID=$(jq '[.[] | select(.status == "valid" and .reward_paid == false)] | length' "$BUG_FILE")

    echo "Total: $TOTAL | Open: $OPEN | Valid: $VALID | Invalid: $INVALID | Unpaid: $UNPAID"
    echo ""

    if [[ "$OPEN" -gt 0 ]]; then
      echo "--- OPEN (needs review) ---"
      jq -r '.[] | select(.status == "open") | "[\(.id)] [\(.severity | ascii_upcase)] \(.title) (by \(.reporter))\n  \(.description)\n  Repro: \(.reproduction)\n"' "$BUG_FILE"
    fi

    if [[ "$UNPAID" -gt 0 ]]; then
      echo "--- VALID (unpaid — will pay on advance) ---"
      jq -r '.[] | select(.status == "valid" and .reward_paid == false) | "[\(.id)] \(.title) (by \(.reporter)) — 100g pending"' "$BUG_FILE"
    fi
    ;;

  bugs-validate)
    BUG_ID="${2:-}"
    STATUS="${3:-valid}"

    if [[ -z "$BUG_ID" ]]; then
      echo "Usage: deity-season.sh bugs-validate <bug_id> [valid|invalid]" >&2
      exit 1
    fi

    if [[ "$STATUS" != "valid" && "$STATUS" != "invalid" ]]; then
      echo "ERROR: Status must be 'valid' or 'invalid'" >&2
      exit 1
    fi

    if [[ ! -f "$BUG_FILE" ]]; then
      echo "ERROR: No bug reports file found" >&2
      exit 1
    fi

    TEMP=$(mktemp)
    jq --arg id "$BUG_ID" --arg s "$STATUS" \
      '[.[] | if .id == $id then .status = $s else . end]' \
      "$BUG_FILE" > "$TEMP" && mv "$TEMP" "$BUG_FILE"

    if [[ "$STATUS" == "valid" ]]; then
      echo "Bug $BUG_ID marked VALID — 100g bounty will be paid on next season advance."
    else
      echo "Bug $BUG_ID marked INVALID — no bounty."
    fi
    ;;

  bulletin)
    MSG="${2:-}"
    if [[ -z "$MSG" ]]; then
      echo "Usage: deity-season.sh bulletin \"What changed this season\"" >&2
      echo ""
      echo "Current bulletin:"
      jq -r '.deity_bulletin[] | "  [\(.season)] \(.message)"' "$GAME_FILE"
      exit 0
    fi
    SEASON_NUM=$(jq '.season.number' "$GAME_FILE")
    TEMP=$(mktemp)
    jq --arg m "$MSG" --argjson s "$SEASON_NUM" --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
      .deity_bulletin = (.deity_bulletin // []) + [{
        "season": $s,
        "message": $m,
        "posted_at": $t
      }]
    ' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "Bulletin posted (Season $SEASON_NUM): $MSG"
    ;;

  bulletin-clear)
    TEMP=$(mktemp)
    jq '.deity_bulletin = []' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "Bulletin cleared."
    ;;

  crystallize)
    echo "=== RACE CRYSTALLIZATION ANALYSIS ==="
    echo ""
    SEASON_NUM=$(jq '.season.number' "$GAME_FILE")
    echo "Season $SEASON_NUM — Analyzing domain specialization patterns..."
    echo ""

    # For each agent, show domain reputation weighted scores and suggest race
    jq -r '
      .agents | to_entries[] | .key as $id | .value |
      "\n--- \($id) (Level \(.level // 1)) ---",
      "Race: \(.race // "none")",
      "Gold: \(.gold)",
      "Lifetime: \((.lifetime_skills // 0) + (.skills_crafted // 0)) skills, \((.lifetime_trades // 0) + (.trades_completed // 0)) trades, \((.lifetime_quests // 0) + (.quests_completed // 0)) quests",
      "",
      "Domain Reputation:",
      (if .domain_reputation and (.domain_reputation | length) > 0 then
        (.domain_reputation | to_entries | sort_by(-.value.weighted_score) | .[] | "  \(.key): \(.value.weighted_score) pts (\(.value.sales) sales)")
      else
        "  (no domain reputation yet)"
      end),
      "",
      (if .domain_reputation and (.domain_reputation | length) > 0 then
        (.domain_reputation | to_entries | sort_by(-.value.weighted_score) |
          if length > 0 then
            "  >> Strongest domain: \(.[0].key) (score: \(.[0].value.weighted_score), sales: \(.[0].value.sales))"
          else
            "  >> No clear specialization"
          end)
      else
        "  >> No trades yet — cannot crystallize"
      end)
    ' "$GAME_FILE"

    echo ""
    echo "=== EXISTING RACES ==="
    HAS_RACES=$(jq '.races // {} | length' "$GAME_FILE")
    if [[ "$HAS_RACES" -gt 0 ]]; then
      jq -r '.races | to_entries[] | "  \(.key): \(.value.description) (crystallized S\(.value.crystallized_season), members: \(.value.members | join(", ")))"' "$GAME_FILE"
    else
      echo "  No races crystallized yet."
    fi

    echo ""
    echo "To crystallize a race:"
    echo "  deity-season.sh crystallize-confirm <agent_id> <race_name> \"Description of the race\""
    echo ""
    echo "Race names should be fantastic archetypes (Runewright, Merchant-Bard, Loreweaver, etc.)"
    echo "Races emerge from BEHAVIOR — what the agent actually did, not what you want them to be."
    ;;

  crystallize-confirm)
    AGENT_ID="${2:-}"
    RACE_NAME="${3:-}"
    RACE_DESC="${4:-}"

    if [[ -z "$AGENT_ID" || -z "$RACE_NAME" || -z "$RACE_DESC" ]]; then
      echo "Usage: deity-season.sh crystallize-confirm <agent_id> <race_name> \"Race description\"" >&2
      echo "" >&2
      echo "Example: deity-season.sh crystallize-confirm agent_001 runewright \"Masters of instruction architecture who see skills as rune-patterns to be composed\"" >&2
      exit 1
    fi

    # Verify agent exists
    AGENT_EXISTS=$(jq --arg id "$AGENT_ID" '.agents[$id] // null' "$GAME_FILE")
    if [[ "$AGENT_EXISTS" == "null" ]]; then
      echo "ERROR: Agent $AGENT_ID not found in game.json" >&2
      exit 1
    fi

    # Normalize race name (lowercase, hyphens)
    RACE_KEY=$(echo "$RACE_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
    SEASON_NUM=$(jq '.season.number' "$GAME_FILE")

    # Get agent's dominant domain for affinity
    DOMAIN_AFFINITY=$(jq -r --arg id "$AGENT_ID" '
      .agents[$id].domain_reputation // {} | to_entries | sort_by(-.value.weighted_score) |
      if length > 0 then .[0].key else "general" end
    ' "$GAME_FILE")

    TEMP=$(mktemp)
    jq --arg agent "$AGENT_ID" --arg race "$RACE_KEY" --arg desc "$RACE_DESC" \
       --argjson season "$SEASON_NUM" --arg domain "$DOMAIN_AFFINITY" '
      # Initialize races object if needed
      .races = (.races // {}) |

      # Create or update the race
      .races[$race] = (
        (.races[$race] // {
          "crystallized_season": $season,
          "domain_affinity": $domain,
          "description": $desc,
          "myth_origin": null,
          "powers": [],
          "members": []
        }) |
        .description = $desc |
        .members = (.members + [$agent] | unique)
      ) |

      # Assign race to agent
      .agents[$agent].race = $race |
      .agents[$agent].race_crystallized_at = $season
    ' "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"

    echo "Race crystallized!"
    echo "  Agent: $AGENT_ID"
    echo "  Race: $RACE_KEY"
    echo "  Description: $RACE_DESC"
    echo "  Domain affinity: $DOMAIN_AFFINITY"
    echo "  Crystallized: Season $SEASON_NUM"
    echo ""
    echo "The race persists across seasons. Other agents with similar specialization"
    echo "can be added to this race with crystallize-confirm."
    ;;

  races)
    echo "=== RACES OF WORLD OF SKILLCRAFT ==="
    echo ""
    HAS_RACES=$(jq '.races // {} | length' "$GAME_FILE")
    if [[ "$HAS_RACES" -eq 0 ]]; then
      echo "No races have crystallized yet."
      echo "Races emerge from agent behavior — run 'deity-season.sh crystallize' to analyze."
      exit 0
    fi

    jq -r '
      .races | to_entries[] |
      "=== \(.key | ascii_upcase) ===",
      "  \(.value.description)",
      "  Domain affinity: \(.value.domain_affinity)",
      "  Crystallized: Season \(.value.crystallized_season)",
      "  Members: \(.value.members | join(", "))",
      (if .value.myth_origin then "  Myth: \(.value.myth_origin)" else "" end),
      (if (.value.powers | length) > 0 then "  Powers: \(.value.powers | join(", "))" else "" end),
      ""
    ' "$GAME_FILE"
    ;;

  *)
    echo "deity-season.sh — Season management for World of Skillcraft"
    echo ""
    echo "Commands:"
    echo "  show                                — display current season state"
    echo "  advance                             — end current season, start next (pays bounties)"
    echo "  reset                               — reset current season (keep number + consensus)"
    echo "  rollback                            — restore previous season"
    echo "  title \"Season Name\"                 — name the current season"
    echo "  event \"What happened\"               — record a notable event"
    echo "  winner \"agent_001 (stats)\"          — record top performer"
    echo "  bulletin \"What changed\"              — post deity announcement"
    echo "  bulletin                              — show current bulletin"
    echo "  bulletin-clear                        — clear all bulletins"
    echo "  bugs                                  — review all bug reports"
    echo "  bugs-validate <bug_id> [valid|invalid] — validate or reject a bug report"
    echo "  crystallize                            — analyze domain specialization for race naming"
    echo "  crystallize-confirm <id> <race> <desc> — assign a race to an agent"
    echo "  races                                  — show all crystallized races"
    ;;

esac
