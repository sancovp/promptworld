---
name: achievements
description: Achievements are earned by demonstrating growth. Each awards gold and bonus rules.
---

# Achievements

Earn achievements by demonstrating you know how to do things. Each achievement awards gold and may inject bonus rules into your `.claude/rules/`.

## How to Claim

```bash
./execute.sh '{"action":{"type":"achievement_claim","achievement_id":"first_quest"}}'
```

## Achievement Evidence

You must demonstrate actual evidence before claiming:
- Quest completion → show the skill you made
- Trade success → show what you bought/sold and why
- Learning → show what you recorded in zettels

## Available Achievements

| ID | Name | Gold | Trigger |
|----|------|------|---------|
| first_quest | First Steps | 25 | Complete 1 quest |
| ten_crafts | Craft Apprentice | 100 | Complete 10 quests |
| first_trade | Merchant | 50 | Complete 1 trade |
