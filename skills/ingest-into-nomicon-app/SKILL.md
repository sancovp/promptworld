---
name: ingest-into-nomicon-app
description: "WHAT: the PromptWorld app-rung — a single flow that ingests an existing Claude-Code system directory (a dir of AIOSes / skills / rules / CLAUDE.mds), converts it into its own {name}-nomicon (the author's framework-of-frameworks holder/search/router), and agentifies that nomicon into a standalone sidecar PromptWorld app (a CEO that carries the nomicon as its world-model, with the ingested AIOS dirs as its specialist agents). It WIRES the already-existing pieces (ingest = copy into the workspace; convert = the skill2framework→fold-into-nomicon pipeline; agentify = PromptWorld scoped to the nomicon) into one drop-dir→get-app flow. WHEN: when the user says 'ingest this claude-code dir', 'turn this system into an app / a webapp', 'make a {name}-nomicon from this', 'convert this dir into its own app', 'app-rung', or wants a Claude-Code directory packaged as a runnable sidecar PromptWorld with an AIOS (any of)."
---
# ingest-into-nomicon-app — drop a Claude-Code dir → get a sidecar PromptWorld app

This is the **top rung of the nomicon ladder** (`info → prompt → skill → rules → AIOS → framework →
fold-into-nomicon → APP`). Everything below this rung already exists and is dogfooded E2E; this skill is the
**orchestration** that composes them into one flow. You run THREE stages in order. Each stage's heavy lifting
is a canonical piece you DISPATCH — you are the orchestrator, not the hands.

## Inputs (filled at invocation)
- `SOURCE_DIR` — the Claude-Code system directory to ingest (holds AIOSes: CLAUDE.md(s) + `.claude/skills` +
  `.claude/rules`, or a doc-mirror repo).
- `NAME` — the new app/nomicon name (e.g. `acme`). Produces `{NAME}-nomicon`.
- `AUTHOR` — the author token for the nomicon (the `{user}` in `fold-into-nomicon`).
- `WORKSPACE` — the PromptWorld workspace root the app runs over (defaults to the new app's dir).

## STAGE 1 — INGEST (copy the dir into the workspace; trivial)
Copy `SOURCE_DIR` into the app workspace as the new app's source tree. This is a plain filesystem copy into
the path-jailed PromptWorld workspace (`server/file_api.py` jails every op to the workspace root) — never a
mount of an outside path. The ingested dir's AIOS subdirectories (each a `CLAUDE.md` + `.claude/`) become the
candidate specialist-agent dirs for STAGE 3. (Mechanism mirrors `_ingest.md`: "ingest = copy a dir into the
bind-mounted workspace volume".)

## STAGE 2 — CONVERT (the dir → a {NAME}-nomicon; run the existing UP pipeline)

### Pinned names + paths (NON-NEGOTIABLE — these prevent a real name-collision + an atomize footgun; learned from the E2E)
Use EXACTLY these, do not improvise (the underlying prompts disagree on names; pin them here):
- **Holder (the app's nomicon)** → `{NAME}-nomicon` at `<app>/nomicon/{NAME}-nomicon/SKILL.md` — its OWN
  dir, NOT inside the deploy `skills/`.
- **Framework skill (per AIOS)** → `{AUTHOR}-framework-{aios}` (e.g. `sancovp-framework-acme`) — this is the
  PROVEN dogfood convention; do NOT use `{aios}-nomicon` (the `generate-framework-skill` prompt's default),
  because when the app has ONE AIOS named like the app it COLLIDES with the holder `{NAME}-nomicon`.
- **Atomize target (the deploy dir)** → `<app>/skills/` — a DISTINCT dir that does NOT contain the holder.
  NEVER atomize into the dir that contains the holder: `nomicon-atomize` will `rmtree` + self-symlink the
  holder and DELETE it (the bin's self-symlink guard only covers the inverse nesting — see the footgun note).

For EACH AIOS discovered in the ingested dir, run the **already-dogfooded** `skill2framework` pipeline by
searching the prompt-store and dispatching each prompt-skill with its specifics:
`docmirror search "<step>" --corpus prompts` → dispatch (the doc-mirror-prompts one-line form), in ORDER:
1. `skill2framework/blog-organ/narrative-blog-from-aios` — Blog1 (narrative) from the AIOS.
2. `skill2framework/deep-dive/deepdive-blog-from-impl-docs` — Blog2 (deep-dive) from its impl docs.
3. `skill2framework/chapter/assemble-chapter` — combine Blog1+Blog2 + CTAs + cross-links.
4. `skill2framework/framework-skill/generate-framework-skill` — the framework index/decision-tree/router skill.
   OVERRIDE its output name to `{AUTHOR}-framework-{aios}` (per the pinned names above), NOT `{aios}-nomicon`.
5. `skill2framework/plugin/package-framework-plugin` — the self-contained framework plugin (its skill dir =
   the framework skill's real frontmatter name `{AUTHOR}-framework-{aios}`, not the prompt's hardcoded default).
6. `skill2framework/nomicon/fold-into-nomicon` — fold the framework into the holder (create it if absent;
   idempotent one row per framework). Pass `{user}=AUTHOR`, `{nomicon_dir}=<app>/nomicon/{NAME}-nomicon`.

Then project the held frameworks flat so agents auto-discover them — into the DISTINCT deploy dir:
`nomicon-atomize <app>/nomicon/{NAME}-nomicon/SKILL.md  <app>/skills` (canon stays the source of truth;
the deploy dir is relative symlinks to the holder + each framework skill — see the `nomicon-atomize` docstring).

> **Atomize footgun (verified):** `nomicon-atomize <holder> <target>` self-symlinks the holder into `<target>`;
> if `<target>` is the dir CONTAINING the holder, `author_dest` == the holder dir and the bin `rmtree`s it →
> the holder is destroyed. ALWAYS atomize into a separate dir (the pinned `<app>/skills/`). (Bin guard gap
> tracked as a doc-mirror-system finding.)

VERIFY each hop's artifact yourself (the dispatched agent's report is a claim) — per prompt-skill discipline,
these are GOLDEN/1.00 so a SANITY check of each produced file suffices; drop to FULL_E2E on any miss. After
atomize, CONFIRM the holder SKILL.md still exists and the deploy symlinks resolve.

## STAGE 3 — AGENTIFY (the {NAME}-nomicon → a runnable sidecar PromptWorld app)
Stand up a PromptWorld instance whose:
- **CEO carries `{NAME}-nomicon`** as its world-model — make the holder discoverable in the CEO's config by
  atomizing it into the CEO's skills dir: `nomicon-atomize <app>/nomicon/{NAME}-nomicon/SKILL.md  <ceo_config>/skills`
  (a DISTINCT dir from the holder — safe). The CEO then meshes with the framework set and routes tasks into the
  right framework (`_nomicon.md` v2: "the agent has the -nomicon which lets them mesh with the user way of thinking").
- **Specialist agents = the ingested AIOS dirs** — each ingested AIOS subdir is already a scoped AIOS
  directory (the directory-codes-the-agent model, VERIFIED: `p_main_agent.py` `config_dir`→`CLAUDE_CONFIG_DIR`),
  registered with `PromptGym` so it runs scoped to its dir and streams to the gallery.
- runs over `WORKSPACE` and serves the SPA + file-explorer + gallery (the existing PromptWorld server).

The container/packaging half (Dockerfile, docker-compose with neo4j, the install wizard, `--strict-mcp-config`,
clean container `~/.claude`) is the **deployment boundary (packaging #1)** — hand off to it; do not inline it
here. This skill's terminal artifact = a runnable app DIRECTORY (nomicon + agent dirs + server config) that a
local `python -m server --dir <app>` boots.

## VERIFY (the whole flow, E2E — the only proof)
Run the flow on a SMALL real Claude-Code dir and confirm, by your own checks: (1) `<app>/nomicon/{NAME}-nomicon/SKILL.md`
exists with a `## Frameworks` table holding one row per ingested AIOS, each row's links resolving, and it
SURVIVED atomize (was not self-clobbered); (2) the deploy `<app>/skills/` dir's symlinks resolve (the holder +
each `{AUTHOR}-framework-{aios}`) and auto-discover; (3) the PromptWorld app boots over the new dir and its CEO,
asked "which of your frameworks fits <task>?", routes via the nomicon. Capture the literal output. Mark
IS / UNKNOWN honestly.

## Canonical references (resolve by design, not by accident)
- The UP pipeline: `doc-mirror-prompts` → `resources/prompts/skill2framework/*` (provisioned with doc-mirror).
- `nomicon-atomize` (doc-mirror `plugin/bin/`) — flat projection of a nomicon.
- The PromptWorld app: `application/promptworld/` (server, `PromptGym`, `p_main_agent.py` scoping, file_api jail).
- Design: `docs/vision/_ingest.md`, `_nomicon.md`; doc-mirror-system `docs/vision/_framework-to-nomicon.md`.
