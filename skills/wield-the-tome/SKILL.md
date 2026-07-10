---
name: wield-the-tome
description: "WHAT: how a PromptWorld wizard WIELDS the SkillTome — consult the author's tome (which framework fits this task?), route through a framework's volume row, run the skill2framework chapter chain on something you built, and FOLD the finished framework into a tome (a code op, skilltree fold). WHEN: when a task smells like an existing framework might cover it; when a build is finished and should become a chapter; when the user mentions the tome, the nomicon, folding, a volume, or 'which of my frameworks fits this' (any of)."
---

# wield-the-tome — the SkillWizard's core move

PromptWorld is **the first SkillWizard**: an app whose agents wield the **SkillTome** — the
author's overall corpus, a SkillTree whose **volume** nodes hold **frameworks** (chapters) as
rows in a generated `## Frameworks` table. ("nomicon" is the legacy name for volume/tome.)

## Where the tome is (in this container)

- **`/opt/tome/`** — the author tome (dev builds ship the real one; an external build has a
  pointer README instead). Read `/opt/tome/.claude/skills/*/SKILL.md` (the root) and each
  volume node's SKILL.md — the `## Frameworks` tables ARE the index: framework name +
  what-it's-for + where its skill lives. NOTE: row paths point into the dev monorepo; inside
  this container treat them as the *index/pointers* (the names + what-for are the searchable
  knowledge; the chapter/plugin URLs are the resolvable form once chapters publish).
- **`/opt/skill2framework/`** — the chapter chain: six stage skills (`narrative-blog`,
  `deepdive-blog`, `assemble-chapter`, `framework-skill`, `package-plugin`, `fold-into-tome`)
  plus the compiled rollup (`skill2framework/SKILL.md`). Read the rollup, follow the stages.

## The ops (installed in this image)

- **`skilltree`** CLI (`agent-skilltree ≥ 0.3.0`): `skilltree validate <tree>` (breadcrumbs +
  tome-table round-trip) · `skilltree emit <tree>` (re-localize after a move/checkout) ·
  `skilltree fold <framework_dir> --into <volume> --tree <tome_root> --relative` (bind a
  framework as a row — idempotent, one row per framework) · `skilltree project <tree> <target>
  --policy flat|progressive` (deploy: flat = every held framework auto-discovers as a
  top-level skill; progressive = root + branches behind Read-breadcrumbs).
- **`framework`** (python): `JourneyCore` + `render_blog1` (fill the model, never hand-write
  the narrative) · `assemble_chapter` · `package_plugin` · `fold_into_tome` (delegates to
  `skilltree.tome.fold`).

## The moves

1. **Consult** — task in hand? Scan the volume tables first: does a framework already fit?
   Prefer routing through an existing framework over building from scratch.
2. **Chapter** — something you built deserves to transfer? Run the `/opt/skill2framework`
   chain on it: blogs → chapter → `{aios}-volume` index skill → plugin.
3. **Fold** — register the finished framework: `fold_into_tome(framework_skill_dir,
   volume=..., tome_root=...)` (or the `skilltree fold` CLI). NEVER hand-edit a `## Frameworks`
   table — it is generated from the tree manifest; the fold op is the only writer.
4. **Grow a local tome** — a World you emit can carry its OWN tome (materialize a SkillTree
   with volume nodes, fold its frameworks in). An app that wields its tome is a SkillWizard;
   that is what you are, and what your outputs can become.

## Verify (always)

After any fold/emit: `skilltree validate <tome_root>` must be green. After moving/copying a
tome: `skilltree emit <tome_root>` first (re-localizes the breadcrumbs from the manifest — the
relative rows need no rewrite), then validate.
