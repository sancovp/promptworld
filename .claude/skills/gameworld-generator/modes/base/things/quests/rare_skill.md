# Quest: rare_skill — Craft a Rare Skill

## Objective

Craft a skill that demonstrates genuine sophistication. Aim for "rare" rarity by showing real depth.

## Requirements

- Create a file at `crafted/rare_skill.md`
- Must demonstrate technique, not just output
- Must have multiple worked examples
- Must teach a non-obvious approach

## Reward

100 gold

## Difficulty

Solo — requires genuine skill

## Rarity Guidelines

| Rarity | Criteria |
|--------|----------|
| Common | Basic capability, works as described |
| Uncommon | Demonstrates technique, not just output |
| Rare | Shows genuine novelty or sophistication |
| Epic | Stacked composition with emergent properties |

## Quest Steps

1. **Accept**: `./execute.sh '{"action":{"type":"quest_accept","quest_id":"rare_skill"}}'`
2. **Craft** your skill at `crafted/rare_skill.md`
3. **Complete**: `./execute.sh '{"action":{"type":"quest_complete","quest_id":"rare_skill","skill_path":"crafted/rare_skill.md"}}'`
