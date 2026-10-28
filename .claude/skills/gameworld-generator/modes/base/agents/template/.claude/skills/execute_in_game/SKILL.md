---
name: execute-in-game
description: Commit actions to the game world — movement, quests, trading, learning.
---

# Execute In Game

Your callback to the GM layer. Call this to commit any action. ALWAYS include your agent_id.

```bash
cd /path/to/gameworld
./execute.sh '{"agent_id":"YOUR_AGENT_ID","action":{"type":"quest_accept","quest_id":"quest_001"}}'
./execute.sh '{"agent_id":"YOUR_AGENT_ID","action":{"type":"learn","domain":"places","topic":"fundamentals"}}'
./execute.sh '{"agent_id":"YOUR_AGENT_ID","action":{"type":"trade_post","skill_path":"crafted/my.md","price":30,"rarity":"common","description":"..."}}'
./execute.sh '{"agent_id":"YOUR_AGENT_ID","action":{"type":"trade_buy","listing_id":"listing_123"}}'
```

## Action Types

| Action | Fields |
|--------|--------|
| quest_accept | quest_id |
| quest_complete | quest_id, skill_path |
| trade_post | skill_path, price, rarity, description |
| trade_buy | listing_id |
| learn | domain, topic |
