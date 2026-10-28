#!/bin/bash
# render-template.sh — Apply mode config to base template

MODE_FILE="$1"
GAMEWORLD_DIR="$2"

MODE_ID=$(jq -r '.mode_id' "$MODE_FILE")
STARTING_GOLD=$(jq -r '.starting_gold // 100' "$MODE_FILE")

# Update game.json with mode_id, starting gold, and max_attainable if set
MAX_ATTAINABLE=$(jq -r '.season_config.max_attainable // null' "$MODE_FILE")
TEMP=$(mktemp)
if [[ "$MAX_ATTAINABLE" != "null" ]]; then
  jq --arg gid "$MODE_ID" --argjson gold "$STARTING_GOLD" \
     --argjson max "$MAX_ATTAINABLE" \
    '.game_id = $gid | .agents."AGENT_PLACEHOLDER".gold = $gold | .season.max_attainable = $max' \
    "$GAMEWORLD_DIR/game.json" > "$TEMP" && mv "$TEMP" "$GAMEWORLD_DIR/game.json"
else
  jq --arg gid "$MODE_ID" --argjson gold "$STARTING_GOLD" \
    '.game_id = $gid | .agents."AGENT_PLACEHOLDER".gold = $gold' \
    "$GAMEWORLD_DIR/game.json" > "$TEMP" && mv "$TEMP" "$GAMEWORLD_DIR/game.json"
fi

# Copy mode-specific execute.sh if it exists (overrides base)
MODE_EXEC="$MODES_DIR/${MODE_ID}_execute.sh"
if [[ -f "$MODE_EXEC" ]]; then
  cp "$MODE_EXEC" "$GAMEWORLD_DIR/execute.sh"
  chmod +x "$GAMEWORLD_DIR/execute.sh"
fi

# Copy .claude/ directory from base (cp -r base/* skips dotfiles, so copy explicitly)
if [[ -d "$MODES_DIR/base/.claude" ]]; then
  cp -r "$MODES_DIR/base/.claude" "$GAMEWORLD_DIR/.claude"
fi

# Create skills/ symlink at root → .claude/skills/ (plugin structure)
if [[ ! -L "$GAMEWORLD_DIR/skills" && ! -e "$GAMEWORLD_DIR/skills" ]]; then
  ln -s .claude/skills "$GAMEWORLD_DIR/skills"
fi

# Create rules/ symlink at root → .claude/rules/ (plugin structure)
if [[ ! -L "$GAMEWORLD_DIR/rules" && ! -e "$GAMEWORLD_DIR/rules" ]]; then
  ln -s .claude/rules "$GAMEWORLD_DIR/rules"
fi

# Ensure agents/ directory exists at root (for spawning agent projects)
mkdir -p "$GAMEWORLD_DIR/agents"

# Copy quest files specified in mode config
jq -r '.quest_definitions[] | select(.include == true) | .file' "$MODE_FILE" 2>/dev/null | while read -r quest_file; do
  if [[ -n "$quest_file" && -f "$MODES_DIR/base/$quest_file" ]]; then
    mkdir -p "$GAMEWORLD_DIR/$(dirname "$quest_file")"
    cp "$MODES_DIR/base/$quest_file" "$GAMEWORLD_DIR/$quest_file"
  fi
done

# Copy achievement files specified in mode config
jq -r '.achievement_definitions[] | select(.include == true) | .file' "$MODE_FILE" 2>/dev/null | while read -r ach_file; do
  if [[ -n "$ach_file" && -f "$MODES_DIR/base/$ach_file" ]]; then
    mkdir -p "$GAMEWORLD_DIR/$(dirname "$ach_file")"
    cp "$MODES_DIR/base/$ach_file" "$GAMEWORLD_DIR/$ach_file"
  fi
done

# Copy place directories specified in mode config
jq -r '.place_definitions[] | select(.include == true) | .path' "$MODE_FILE" 2>/dev/null | while read -r place_path; do
  if [[ -n "$place_path" && -d "$MODES_DIR/base/$place_path" ]]; then
    mkdir -p "$GAMEWORLD_DIR/$place_path"
    cp -r "$MODES_DIR/base/$place_path/"* "$GAMEWORLD_DIR/$place_path/"
  fi
done

# Write mode config into gameworld for reference
cp "$MODE_FILE" "$GAMEWORLD_DIR/.mode_config.json"

echo "Mode config applied to $GAMEWORLD_DIR"
