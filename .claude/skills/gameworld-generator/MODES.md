# Mode Authoring Guide

Modes define how a gameworld works — the earn/spend mechanics, craft type, and distribution.

## Mode Config Format

```json
{
  "mode_id": "my-mode",
  "mode_name": "My Gameworld",
  "description": "What agents do in this world",

  "core": {
    "earn": {
      "mechanism": "quest|trade|benchmark|chapter_submission|submission|quest_plus_trade|none",
      "actions": ["quest_accept", "quest_complete", ...],
      "description": "How agents earn rewards"
    },
    "spend": {
      "mechanism": "trade|none",
      "actions": ["trade_post", "trade_buy"],
      "description": "How agents spend rewards"
    },
    "craft_type": "site|story|skill|plugin|recipe",
    "distribution": "individual|team_global|tiered",
    "self_assessment": false
  },

  "execute_includes": ["action1", "action2"],
  "execute_excludes": [],

  "starting_gold": 100,

  "quest_definitions": [
    { "quest_id": "q001", "file": "things/quests/q001.md", "include": true }
  ],

  "achievement_definitions": [
    { "achievement_id": "first", "file": "achievements/first.json", "include": true }
  ],

  "season_config": {
    "reset_trade_board": true,
    "carry_gold": false
  }
}
```

## Core Concepts

### EARN Mechanisms

| Mechanism | Description |
|-----------|-------------|
| `quest` | Agents earn by completing quests (finite bootstrap) |
| `trade` | Agents earn by selling skills (renewable) |
| `benchmark` | Agents earn by passing benchmark tests |
| `chapter_submission` | Agents earn by submitting story chapters |
| `submission` | Generic submission-based earning |
| `quest_plus_trade` | Quest rewards + trade profits |
| `none` | No earning (spend-only world) |

### SPEND Mechanisms

| Mechanism | Description |
|-----------|-------------|
| `trade` | Spend gold at the trade post |
| `none` | No spending (earn-only world) |

### CRAFT Types

| Type | What agents build |
|------|-----------------|
| `skill` | Claude Code skills (.md files) |
| `site` | Cinematic websites |
| `story` | Narrative chapters |
| `plugin` | Claude Code plugins |
| `recipe` | Type-preserving compositions |

### DISTRIBUTION

| Type | Description |
|------|-------------|
| `individual` | Each agent has own gold |
| `team_global` | Rewards go to shared pool, distributed by GM |
| `tiered` | Individual + team bonus |

## Built-in Modes

### cinematic-website
Earn via benchmark scoring. No spending. Craft type: site.
Agents build cinematic websites from URLs, earn by passing 15-item QC gate.

### story-forge
Earn via chapter submission. Team global bonus pool. Craft type: story.
Agents write chapters collaboratively, compete on leaderboard.

### wos (Way of the Craftsperson)
Earn via quest + trade. Spend via trade. Craft type: skill.
Full economic loop — quest rewards bootstrap, trade sustains.

## Creating a Custom Mode

1. Copy `modes/wos.json` as a starting point
2. Modify `core.earn.mechanism` and `core.spend.mechanism`
3. Set `craft_type` to match what agents build
4. Add quest definitions that exist in `modes/base/things/quests/`
5. Run `generate.sh your-mode.json /path/to/output`

## The Reflexive Loop

Extract a mode config from any existing gameworld:

```bash
./generate.sh --extract /path/to/gameworld > my-mode.json
```

Then edit the extracted JSON and use it to generate new gameworlds.
