---
name: compile-a-world
description: "WHAT: PromptWorld's meta-compiler skill — the architecture patterns + worked examples for building a *World (a sim app = a team-leader + a specialist set + a domain + a driver) such as JobWorld, GameWorld, HealthWorld, or PromptWorld itself, plus how to reuse one pattern, combine them into a new World/app, and compose+publish it over the nomicon. WHEN: when the user (or the Archwizard) says 'compile/build/make a World', 'make a new jobworld/gameworld/healthworld', 'what World patterns are there / how is a World built', 'turn this into an app / a sim', 'meta-compiler', 'world compiler', or wants to scaffold a CAVE-fork sim app or fold one into the nomicon (any of)."
---

# compile-a-world — the *World meta-compiler

PromptWorld is the **meta-compiler of patterns**: it treats every "*World" we have built as a
**named architecture pattern**, so you can *reuse* a pattern, *combine* patterns into a new World,
or *compose* Worlds into an app and *publish* it — all over the nomicon ladder. This skill carries
the pattern knowledge you need to do that. (You do NOT need any host file to use it — the patterns
are stated here in full.)

## The one model: a *World is a SIM = {team-leader, specialists, domain, driver}

Every "*World" is the **same shape** — a simulation run by a team:

- **team-leader** — the one agent that orchestrates (a CEO / Game Master / Archwizard).
- **specialists** — the worker agents it coordinates (departments / crafters / Wizards).
- **domain** — what the sim is *about* (an org, a game economy, a body, claude-code components).
- **driver** — what makes a turn happen (real-world events, an internal game loop, your records,
  build requests).

A "*World" is **NOT a reified type or a single compiler** — it is a **CAVE-fork resemblance**, a *way*
of doing this. The patterns below are the vocabulary; the objective (bottom) is to reuse one or
**combine them into something new**.

## The patterns (the vocabulary — anatomy + worked examples in `resources/patterns.md`)

| pattern | team-leader | specialists | domain | driver |
|---|---|---|---|---|
| **JobWorld** | CEO of departments | departments | running an org | heartbeats/events from automations about the **real world** |
| **GameWorld** | **Game Master** | crafters/traders (peers in a market) | an economic/trading game around craftable things | the **internal game loop** (craft → trade → score) |
| **HealthWorld** | a CEO-for-your-body (Osmosis-Jones) | body-system agents | your health | your **records + stats** → holistic analyses |
| **PromptWorld** | the **Archwizard** | the **Wizards** (skill/mcp/prompt/harness/team/cave_team/workflow/operating_system) | building Claude-Code components & tomes | **build requests** → the Wizards work the tome together |

Two structural axes distinguish them:
- **topology**: a hierarchy/org (a leader dispatches specialists — Job/Health/Prompt) vs a **peer
  market** (a GM referees crafting+trading peers — Game).
- **what drives a turn**: external input (real-world events, your records, build requests) vs an
  **internal loop** (the game economy).

**PromptWorld is special only in its job**: its domain is *making the others*. It is the **reactor /
meta** — it can build any of these Worlds as AIOS+Teams variants, **compose** them into apps, and
**publish** them. Some Worlds carry their **own** specialized meta-compiler (JobWorld can make new
JobWorlds; GameWorld can make new GameWorlds); PromptWorld is the one that treats them **all** as
patterns.

## How to compile a World (the procedure)

1. **Pick or combine a pattern.** State the target as `{name, team-leader role, specialists,
   domain, driver, topology}`. If it matches a pattern above, **reuse** it. If it's genuinely new,
   **combine** the closest patterns and say exactly what is new and why.
2. **Scaffold the World module** = the team-leader (a persona/CLAUDE.md) + the specialist set (each
   an AIOS dir that codes an agent: its own `CLAUDE.md` + `.claude/`) + the domain config + the
   driver (which CAVE automation/heartbeat or game loop fires turns). PromptWorld's own
   `agents/` + `promptgym/<craft>/` dirs are the live worked example of this module — read them.
3. **Add Gym module(s) if research is needed** — the spec / status / observation / research-run
   layer (`/api/gym-specs`) where specialists research what they build by dispatching subagents.
4. **Fold it up the nomicon ladder** so it becomes a real, installable app:
   `component → AIOS → framework → fold-into-nomicon → app`. Use the ladder skills you carry:
   `make-ai-operating-system` (AIOS rung), the `skill2framework` prompt-tree (framework rung),
   `fold-into-nomicon` + `nomicon-atomize` (the nomicon), `ingest-into-nomicon-app` (the app rung),
   `ship-a-plugin` (publish). `ingest-into-nomicon-app` is the one-shot "drop a Claude-Code dir →
   get a sidecar PromptWorld app" flow.
5. **Verify by the user surface**, never by assertion: the World **boots**, the team-leader actually
   **dispatches** a specialist, an artifact lands. Mark IS vs VISION honestly.

## The objective (Isaac's framing)

> "give those as examples — they use those skills, learn them, but know that the real objective is
> to combine all the knowledge and come up with something new."

So: this skill is **patterns + examples**, not a black-box generator. Reuse a pattern when one fits;
otherwise combine the knowledge into a new World. PromptWorld is the meta that holds them all — the
place we can also fold in **courses** and anything else, give people **one** thing, and have it
install from Claude Code and run remotely inside their own Claude Code.

## Depth + references (resolve by design)
- `resources/patterns.md` — the full anatomy of each pattern (driver mechanics, topology, the real
  generators each one has, and what's genuinely shared vs per-World).
- The nomicon ladder rungs you carry as skills: `make-ai-operating-system`, `doc-mirror-prompts`
  (the `skill2framework` tree), `ship-a-plugin`, and the PromptWorld-local `ingest-into-nomicon-app`.
- The live worked example = **PromptWorld itself**: `agents/engineer-ceo.md` (the team-leader),
  `promptgym/<craft>/` (the specialist AIOS dirs), `server/` (the World+Gym modules), the nomicon
  self-inspection in `promptgym/world-context.md`.
