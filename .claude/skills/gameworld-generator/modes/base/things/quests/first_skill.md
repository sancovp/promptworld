# Quest: first_skill — Craft Your First Skill

## Objective

Craft a skill that demonstrates a useful capability. A skill is a `.md` file that teaches another agent how to do something.

## Requirements

- Create a file at `crafted/first_skill.md`
- Must have clear instructions another agent can follow
- Must include at least one worked example
- Must actually work when tested

## Reward

50 gold

## Difficulty

Solo — entry level

## Knowledge Hints

- Study `places/skillcraft/` for skill writing patterns
- A skill has: name, description, instructions, examples
- Keep it focused — one skill, one purpose

## Quest Steps

1. **Accept** this quest: `./execute.sh '{"action":{"type":"quest_accept","quest_id":"first_skill"}}'`
2. **Craft** your skill at `crafted/first_skill.md`
3. **Complete** the quest: `./execute.sh '{"action":{"type":"quest_complete","quest_id":"first_skill","skill_path":"crafted/first_skill.md"}}'`
