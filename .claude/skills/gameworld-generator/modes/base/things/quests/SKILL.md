---
name: quests
description: The quest board — accept quests, craft domain skills, earn gold rewards.
---

# Quests

Accept quests from this board. Complete them by crafting skills that demonstrate the required capability.

## How to Accept

```bash
cd /path/to/gameworld
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
