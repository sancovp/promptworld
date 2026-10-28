---
name: gameworld-generator
description: Given a domain, generate a complete Claude Code game-world directory — GM prompt, economy engine, places, quests, achievements, and agent template. One-shot instantiation.
---

# Gameworld Generator

Given a domain (e.g., "code review", "meditation teaching", "startup ideation"), produce a complete, runnable Claude Code game-world. The output is a directory that, when entered, turns Claude Code into the GM of that domain.

## What You Produce

### THE GAMEWORLD (complete plugin project with agents inside)

```
{gameworld}/
├── CLAUDE.md                    ← GM prompt (this IS the game)
├── game.json                    ← world state (gold, XP, board)
├── execute.sh                   ← economy engine (bash + jq)
├── skills/                      ← PLUGIN LEVEL skills (injected to users who load plugin)
├── agents/                      ← PLUGIN LEVEL agent definitions (optional)
├── rules/                       ← PLUGIN LEVEL rules
├── agents/template/            ← player agent template (COPIED to spawn agents)
│   ├── CLAUDE.md               ← agent prompt ({{AGENT_ID}} replaced on spawn)
│   └── .claude/skills/           ← skills COPIED to each new agent
│       ├── execute_in_game/     ← how to commit actions
│       │   ├── SKILL.md
│       │   └── execute.sh
│       ├── places/             ← how to navigate places
│       │   └── SKILL.md
│       ├── things/             ← how to do quests
│       │   └── SKILL.md
│       └── remember/           ← zettelkasten
│           └── SKILL.md
├── places/                     ← knowledge content (study here)
│   └── {domain}/
│       ├── SKILL.md
│       └── {topics}.md
├── things/
│   └── quests/
│       ├── SKILL.md
│       ├── quest_001.md
│       └── quest_002.md
├── achievements/
│   ├── SKILL.md
│   ├── first_quest.json
│   └── ten_crafts.json
└── .claude/
    └── rules/                  ← game rules (injected on achievements)
```

**Include ALL canonical plugin directories at root level: `skills/`, `agents/`, `rules/`, even if empty — this makes the plugin structure complete.**

## Generate with Modes

The faster path: use `generate.sh` to produce gameworlds from mode configs.

```bash
# List available modes
./generate.sh --list

# Generate a gameworld from a built-in mode
./generate.sh wos /path/to/project/gameworlds/

# Generate from a custom mode config
./generate.sh /path/to/my-mode.json /path/to/output/

# Extract a mode config from an existing gameworld (reflexive loop)
./generate.sh --extract /path/to/existing/gameworld > my-mode.json
```

Built-in modes:
- **wos** — earn via quest+trade, spend via trade, craft type: skill

See `MODES.md` for full mode authoring guide.

## The Core Insight

A game-world is a **domain-specific simulation with economic pressure**. Agents study places, craft capabilities as `.md` skill files, trade them for gold, and earn XP for achievements that modify their rules. The GM CLAUDE.md IS the game — it tells Claude Code how to act as the GM, what actions to accept, and how to respond.

The GM runs a loop:
1. Agent does something → `execute.sh` records it in `game.json`
2. GM notices (from game.json reads or direct observation) → responds
3. Achievement detector runs → finds evidence → awards XP + injects rules
4. Agent reads their modified rules → behaves differently next turn

## Step-by-Step Generation

### Step 1: Define the Domain

Pick a domain. Name it. Write a one-line purpose.

Example: **Code Review Agent Guild** — "Agents learn to review code by studying review patterns, crafting review skills, and trading them on a market."

The domain defines:
- **Places** — what knowledge agents study
- **Quests** — what capabilities they must demonstrate
- **Skill types** — what categories of crafted skills exist
- **Achievements** — what evidence earns XP and modifies rules
- **Economy** — what actions cost/gain gold and XP

### Step 2: Write the GM CLAUDE.md

This is the most important file. It makes Claude Code the GM.

```bash
cat > {gameworld}/CLAUDE.md << 'CLAUDE_EOF'
# GM — {Domain Name}

You are the Game Master for {domain}. You run the world, respond to agents,
adjudicate actions, and evolve the game based on what happens.

## Your Role

- Observe agent actions from game.json
- Respond to agent requests (accept/reject with narrative)
- Create new quests when old ones complete
- Inject achievements when agents demonstrate growth
- Keep the world consistent and interesting
- Narrate outcomes — don't just report stats

## Game State

Read `game.json` to see:
- Agent gold and XP
- Trade board listings
- Active quests
- Season number

```bash
jq '.agents' game.json       # all agent stats
jq '.trade_board' game.json   # current listings
jq '.season' game.json        # season info
```

## Action Types You Accept

When an agent calls execute.sh, you receive actions. Handle each:

| Action | What It Means | Your Response |
|--------|--------------|---------------|
| move/navigate | Agent goes somewhere | Describe where they went |
| learn | Agent studies a place | Confirm what they learned |
| quest_accept | Agent takes a quest | Confirm, add to log |
| quest_complete | Agent submits a skill | Evaluate quality, award gold |
| trade_post | Agent lists a skill | Confirm listing, describe the skill |
| trade_buy | Agent buys a skill | Describe what they received |
| achievement_claim | Agent claims an achievement | Verify evidence, inject rules |

## Economy

- Starting gold: 100
- Quest rewards: 25–100g depending on difficulty
- Trade prices: 10–200g based on rarity and quality
- XP earned: 10–100 per achievement

## The GM Loop

1. Agent reads game.json → decides action
2. Agent calls execute.sh → game.json updates
3. You (GM) read the updated state
4. You respond narratively and/or trigger events
5. Achievement detector runs → awards XP if earned
6. Repeat

## Season Management

Seasons are cycles. At season end:
- Gold resets to 100 + bounty earnings
- Crafted skills and zettels persist
- Trade board clears
- XP carries over

Use `deity-season.sh` commands when running seasons manually.

## GM Commands

When *USER* says "GM", "deity", or "run the game", read this file and execute.

Keep the world narratively consistent. Agents remember what happened.
CLAUDE_EOF
```

### Step 3: Write execute.sh

The economy engine. 300 lines of bash that validates and mutates game.json atomically.

```bash
cat > {gameworld}/execute.sh << 'EXEC_EOF'
#!/bin/bash
# execute.sh — economy engine
# ALL game logic lives here. Agent ID from directory name only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GAME_FILE="$AGENT_DIR/game.json"

ACTION_JSON="${1:-}"
if [[ -z "$ACTION_JSON" ]]; then
  echo "Usage: execute.sh '<json action>'" >&2
  exit 1
fi

AGENT_ID=$(basename "$AGENT_DIR")
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
    SKILL_PATH=$(echo "$ACTION_JSON" | jq -r '.action.skill_path')
    QUEST_FILE="$AGENT_DIR/things/quests/${QUEST_ID}.md"
    if [[ ! -f "$QUEST_FILE" ]]; then
      echo "ERROR: Quest $QUEST_ID not found" >&2; exit 1
    fi
    REWARD=$(grep -A2 '## Reward' "$QUEST_FILE" | grep -oE '[0-9]+' | head -1 || echo "50")
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
    if [[ ! -f "$AGENT_DIR/$SKILL_PATH" ]]; then
      echo "ERROR: Skill file not found at $SKILL_PATH" >&2; exit 1
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
    if [[ -z "$LISTING" ]]; then
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
       .agents[$id].last_action_at = $ts |
       .agents[$id].xp = (.agents[$id].xp // 0) + 5' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] learned about $DOMAIN/$TOPIC (+5 XP)"
    ;;

  achievement_claim)
    ACHIEVEMENT_ID=$(echo "$ACTION_JSON" | jq -r '.action.achievement_id')
    CLAIMED=$(jq --arg id "$AGENT_ID" --arg ach "$ACHIEVEMENT_ID" \
      '[.achievements[$id] // []] | if .[] == $ach then true else false end' \
      "$GAME_FILE" 2>/dev/null || echo "false")
    if [[ "$CLAIMED" == "true" ]]; then
      echo "ERROR: Achievement $ACHIEVEMENT_ID already claimed" >&2; exit 1
    fi
    ACHIEVEMENT_FILE="$AGENT_DIR/achievements/${ACHIEVEMENT_ID}.json"
    if [[ ! -f "$ACHIEVEMENT_FILE" ]]; then
      echo "ERROR: Achievement $ACHIEVEMENT_ID not found" >&2; exit 1
    fi
    XP=$(jq -r '.xp // 50' "$ACHIEVEMENT_FILE")
    GOLD=$(jq -r '.gold // 0' "$ACHIEVEMENT_FILE")
    BONUS_FILE=$(jq -r '.bonus_file // ""' "$ACHIEVEMENT_FILE")
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg ach "$ACHIEVEMENT_ID" \
       --argjson xp "$XP" --argjson gold "$GOLD" \
      '.agents[$id].xp = (.agents[$id].xp // 0) + $xp |
       .agents[$id].gold += $gold |
       .achievements[$id] = (.achievements[$id] // []) + [$ach]' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] earned achievement: $ACHIEVEMENT_ID (+${XP}XP, +${GOLD}g)"
    ;;

  *)
    TEMP=$(mktemp)
    jq --arg id "$AGENT_ID" --arg atype "$ACTION_TYPE" --arg ts "$TIMESTAMP" \
      '.agents[$id].last_action = $atype | .agents[$id].last_action_at = $ts' \
      "$GAME_FILE" > "$TEMP" && mv "$TEMP" "$GAME_FILE"
    echo "[$AGENT_ID] executed: $ACTION_TYPE"
    ;;
esac
EXEC_EOF
chmod +x {gameworld}/execute.sh
```

### Step 4: Write game.json

```bash
cat > {gameworld}/game.json << 'GAME_EOF'
{
  "game_id": "{gameworld}",
  "tick": 0,
  "season": {
    "number": 1,
    "title": "Season of First Steps",
    "started_at": null,
    "previous_season": null,
    "rarity_consensus": {
      "common": "Basic capability, works as described",
      "uncommon": "Demonstrates technique, not just output",
      "rare": "Shows genuine novelty or sophistication",
      "epic": "Stacked composition with emergent properties"
    }
  },
  "agents": {},
  "trade_board": [],
  "trade_history": [],
  "quest_log": {},
  "achievements": {},
  "deity_bulletin": []
}
GAME_EOF
```

### Step 5: Write Places (Domain Knowledge)

```bash
mkdir -p {gameworld}/places/{domain}
cat > {gameworld}/places/{domain}/SKILL.md << 'EOF'
# {Domain Name}

Places are where agents LEARN. Each place is a knowledge domain with content to study.

## Structure

```
places/{domain}/
├── SKILL.md           ← what this domain teaches
└── {topic}.md         ← specific knowledge files
```

## How to Use

1. Read this SKILL.md to understand what the domain covers
2. Read topic files to learn specifics
3. Record key insights in your zettelkasten (remember/)
4. Use what you learned when crafting skills

## Topics

- `fundamentals.md` — core concepts
- `techniques.md` — common techniques
- `examples.md` — worked examples

## The Learning Loop

Study places → Craft skills → Test → Trade → Complete quests
EOF

cat > {gameworld}/places/{domain}/fundamentals.md << 'EOF'
# {Domain} Fundamentals

## Core Concept

{1-2 sentences on what this domain IS.}

## Key Principles

1. **{principle 1}** — {explanation}
2. **{principle 2}** — {explanation}
3. **{principle 3}** — {explanation}

## Common Mistakes

- **{mistake 1}** — {why it's wrong}
- **{mistake 2}** — {why it's wrong}

## Further Study

See also: techniques.md, examples.md
EOF
```

### Step 6: Write Quest Files

```bash
mkdir -p {gameworld}/things/quests

cat > {gameworld}/things/quests/SKILL.md << 'EOF'
---
name: quests
description: The quest board — accept quests, craft domain skills, earn gold rewards.
---

# Quests

Accept quests from this board. Complete them by crafting skills that demonstrate the required capability.

## How to Accept

```bash
./execute.sh '{"action":{"type":"quest_accept","quest_id":"quest_001"}}'
```

## How to Complete

```bash
./execute.sh '{"action":{"type":"quest_complete","quest_id":"quest_001","skill_path":"crafted/my_skill.md"}}'
```

## Quest Format

Each quest file contains:
- **Objective** — what skill to build
- **Requirements** — what makes it count
- **Reward** — gold earned on completion
- **Difficulty** — solo or party
- **Knowledge hints** — where to study first
EOF

cat > {gameworld}/things/quests/quest_001.md << 'EOF'
# Quest: quest_001 — The First Skill

## Objective

Craft a skill that demonstrates a basic {domain} capability.

## Requirements

- Must be a valid `.md` skill file
- Must include clear instructions another agent could follow
- Must include at least one worked example
- Must actually work when tested

## Reward

25 gold

## Difficulty

Solo — entry level

## Knowledge Hints

- Visit `places/{domain}/fundamentals.md` for core concepts
- Study `places/{domain}/techniques.md` for common approaches
EOF
```

### Step 7: Create Agent Template (INSIDE the gameworld)

```bash
# Create agents/template/ INSIDE the gameworld
mkdir -p {gameworld}/agents/template/.claude/skills/{execute_in_game,places,things,remember}

# Execute in Game skill
cat > {gameworld}/agents/template/.claude/skills/execute_in_game/SKILL.md << 'EOF'
---
name: execute-in-game
description: Commit actions to the game world — movement, quests, trading, learning.
---

# Execute In Game

Your callback to the GM layer. Call this to commit any action.

```bash
./execute.sh '{"action":{"type":"quest_accept","quest_id":"quest_001"}}'
./execute.sh '{"action":{"type":"learn","domain":"{domain}","topic":"fundamentals"}}'
./execute.sh '{"action":{"type":"trade_post","skill_path":"crafted/my.md","price":30,"rarity":"common","description":"..."}}'
```

## Action Types

| Action | Fields |
|--------|--------|
| quest_accept | quest_id |
| quest_complete | quest_id, skill_path |
| trade_post | skill_path, price, rarity, description |
| trade_buy | listing_id |
| learn | domain, topic |
| achievement_claim | achievement_id |
EOF

cp {gameworld}/agents/template/.claude/skills/execute_in_game/SKILL.md {gameworld}/agents/template/.claude/skills/execute_in_game/execute.sh

# Places skill
cat > {gameworld}/agents/template/.claude/skills/places/SKILL.md << 'EOF'
---
name: places
description: Knowledge domains to study. Read before crafting skills.
---

# Places

Visit knowledge places to learn before crafting. Each domain has content to study.

```bash
# Read the domain overview
cat places/{domain}/SKILL.md

# Study a specific topic
cat places/{domain}/fundamentals.md
cat places/{domain}/techniques.md
```

Record what you learn in your zettelkasten.
EOF

# Things skill
cat > {gameworld}/agents/template/.claude/skills/things/SKILL.md << 'EOF'
---
name: things
description: Quest board and artifacts. Accept quests, craft deliverables, earn gold.
---

# Things

Quests and the quest board. Browse `things/quests/` to find objectives.
EOF

# Remember skill
cat > {gameworld}/agents/template/.claude/skills/remember/SKILL.md << 'EOF'
---
name: remember
description: Persistent memory across sessions. Record observations, strategies, craft insights.
---

# Remember

Your zettelkasten. Write observations after every significant action.

```bash
# Add a zettel
echo "[$(date -u +%Y-%m-%d)] $title: $content" >> .memory/zettels.txt
```
EOF
```

### Step 8: Write Agent CLAUDE.md Template

```bash
cat > {gameworld}/agents/template/CLAUDE.md << 'EOF'
# Agent {{AGENT_ID}}

You are agent `{{AGENT_ID}}` in {domain}. You explore knowledge, craft skills, trade them for gold, and complete quests.

## Your ID
`{{AGENT_ID}}`

## Game State
Read `game.json` to see the world: your gold, the trade board, quest log.

```bash
jq '.agents.{{AGENT_ID}}' game.json
jq '.trade_board' game.json
jq '.quest_log.{{AGENT_ID}}' game.json
```

## The Game Loop
1. EXPLORE → Visit places to learn
2. QUEST → Accept quests from things/quests/
3. CRAFT → Use knowledge to build skills
4. TRADE → Post skills to trade board, buy from others

## Your Skills

- **execute_in_game/** — commit actions to game
- **places/** — study knowledge domains
- **things/** — browse quests
- **remember/** — your zettelkasten

## How to Play
1. Read places/{domain}/ to learn
2. Accept a quest: execute_in_game with quest_accept
3. Craft the skill
4. Complete: execute_in_game with quest_complete
5. Trade: execute_in_game with trade_post
EOF
```

### Step 9: Write Achievement Files

```bash
mkdir -p {gameworld}/achievements

cat > {gameworld}/achievements/SKILL.md << 'EOF'
---
name: achievements
description: Achievements are earned by demonstrating growth. Each awards XP, gold, and bonus rules.
---

# Achievements

Earn achievements by demonstrating you know how to do things. Each achievement awards XP and may inject bonus rules into your `.claude/rules/`.

## How to Claim

```bash
./execute.sh '{"action":{"type":"achievement_claim","achievement_id":"first_quest"}}'
```

## Available Achievements

| ID | Name | XP | Gold | Trigger |
|----|------|-----|------|---------|
| first_quest | First Steps | 10 | 25 | Complete 1 quest |
| ten_crafts | Craft Apprentice | 50 | 100 | Craft 10 skills |

Achievements are defined as JSON files in this directory.
EOF

cat > {gameworld}/achievements/first_quest.json << 'EOF'
{
  "achievement_id": "first_quest",
  "name": "First Steps",
  "description": "Complete your first quest",
  "xp": 10,
  "gold": 25,
  "trigger": "quests_completed >= 1"
}
EOF
```

## How to Run the Gameworld

```bash
cd {gameworld}

# Spawn agents as teammates in a team
# Each agent gets a copy of agents/template/ into their working directory

# Agent reads CLAUDE.md first
# Then reads game.json to see state
# Then explores places, accepts quests, crafts skills
# Calls execute.sh to commit actions
# GM reads game.json, responds, awards achievements
```

## How to Spawn Agents

```bash
# Copy template to new agent directory
cp -r agents/template agents/agent_001
sed -i '' 's/{{AGENT_ID}}/agent_001/g' agents/agent_001/CLAUDE.md

# Add to game.json
jq '.agents.agent_001 = {gold: 100, xp: 0, quests_completed: 0}' game.json > tmp && mv tmp game.json

# Spawn as teammate in a Claude Code team
```

## Key Files Summary

| File | Purpose |
|------|---------|
| CLAUDE.md | GM prompt |
| execute.sh | Economy engine |
| game.json | World state |
| agents/template/ | Base agent template (inside gameworld) |
| places/{domain}/ | Knowledge content |
| things/quests/*.md | Quest definitions |
| achievements/*.json | XP/rule rewards |

## Pattern: What Makes a Good Gameworld

1. **Domain is specific** — "code review" not "programming"
2. **Places have real content** — agents actually learn something useful
3. **Quests require crafting** — not just reading, must produce an artifact
4. **Trade board has value** — skills other agents want to buy
5. **Achievements change behavior** — bonus rules modify how agents operate
6. **GM has personality** — responses are narrative, not just stats

Follow this pattern and you get a domain-specific simulation where agents develop real capabilities that compound across seasons.
