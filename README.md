# PromptWorld

<!-- SCALABLE-PUBLISHING:AUTOGEN START (managed block — do not edit between these markers) -->

![Stars](https://img.shields.io/github/stars/sancovp/promptworld.svg?style=social) ![Updated](https://img.shields.io/badge/updated-2026_07_03-lightgrey.svg)

⭐ 0 stars • 🕑 Updated 2026-07-03

📦 Auto-published from the monorepo • [CHANGELOG](./CHANGELOG.md) • [sancovp/promptworld](https://github.com/sancovp/promptworld)

<!-- SCALABLE-PUBLISHING:AUTOGEN END -->

**PromptWorld is a Claude-Code-native app for building Claude-Code-native software.**

You chat with one agent — the **Engineer-CEO** — and it builds the seven primitive component types that
make up any Claude Code system (skills, MCP servers, prompts, harnesses, teams, workflows, operating
systems), itself or by delegating to a specialist builder for each type. It runs as a single web app: a
chat + a live file workbench + dashboards, served from one container.

PromptWorld is also a **worked example of an app built over a "nomicon"** — the doc-mirror documentation /
development operating system. Every agent in PromptWorld loads the **doc-mirror plugin**, so the whole app
carries the ladder for turning a component into an AIOS into a framework and folding it back into the
system. PromptWorld can **inspect its own structure** and explain, as a living example, how an app like it
is built. It is also the **meta-compiler of patterns** (the `compile-a-world` skill): it treats every
`*World` — JobWorld, GameWorld, HealthWorld, PromptWorld — as a named architecture pattern (a *World = a
sim: a team-leader + specialists + a domain + a driver), so an agent can reuse a pattern or combine them
into a new World/app and fold it up the nomicon ladder. (`*World` is a CAVE-fork *resemblance*, a way of
doing this — not a rigid type; there is no push-button general generator yet, by design.)

---

## Quickstart

PromptWorld ships as a Docker image built from the monorepo. From the app directory:

```bash
cd application/promptworld

# 1. Build the image (stages promptworld + the doc-mirror plugin + cave + sdna, builds the SPA in-layer)
bash deploy/build.sh build

# 2. Boot a container on host port 3858 (mind_of_god-safe: create -> docker cp creds -> start)
#    REQUIRES the provider key in your env so the agents can run:
export MINIMAX_API_KEY=...          # the MiniMax-M3 key the agents authenticate with
bash deploy/build.sh boot 3858

# 3. Smoke-test it end-to-end from inside the container (health, SPA, a real CEO reply, a subagent build)
bash deploy/build.sh e2e

# stop
bash deploy/build.sh stop
```

Then open `http://localhost:3858`.

**Auth model.** The agents run on **MiniMax-M3** (`Minimax-M3[1m]`, base URL `https://api.minimax.io/anthropic`).
The key is passed into the container at boot as `MINIMAX_API_KEY` and exported as `ANTHROPIC_AUTH_TOKEN`.
A Claude subscription credential is *also* copied in (for the embedded terminal), but the agent turns use
the MiniMax provider token, not OAuth.

---

## What's inside (the architecture)

### The World module — the CEO + seven specialist builders

PromptWorld's **World module** is the guild that builds things:

- the **Engineer-CEO** (`agents/engineer-ceo.md`) — the single agent you chat with. It has every skill and
  one native subagent per component type, so it can build anything itself or delegate.
- seven **specialist AIOS dirs** under `promptgym/<craft>/`, one per component type. Each is a directory
  that *codes an agent* (its own `CLAUDE.md` + `.claude/rules` + `.claude/agents`), and each specialist
  works ONLY in its own directory.

| craft | builds | master |
|---|---|---|
| `skill` | a SKILL (lean `SKILL.md` + `resources/`) | Skillwright |
| `mcp` | an MCP server (FastMCP tools) | Toolwright |
| `prompt` | a prompt / persona (a "guy" in a role) | Promptwright |
| `harness` | a harness (sequenced typed outputs across a turn) | Harnesswright |
| `team` | a team / subagent set on a shared task list | Teamwright |
| `workflow` | a deterministic fan-out script (the Workflow tool) | Flowwright |
| `operating_system` | an AI OS (a directory + core loop that governs) | Systemwright |

The shared, re-skinnable world description lives in `promptgym/world-context.md`; the shared global agent
context in `promptgym/global-context.md`.

### The nomicon ladder (what makes PromptWorld an app-over-a-nomicon)

Every PromptWorld agent loads the **doc-mirror plugin**, which carries the rungs:

```
component  ->  AIOS  ->  framework  ->  fold-into-nomicon  ->  app
```

as real skills/CLIs (`make-ai-operating-system`, the `skill2framework` prompt-tree, `nomicon-atomize`,
`ship-a-plugin`, and the app-rung skill). Ask the CEO *"how is PromptWorld built / what is the nomicon"*
and it inspects its own dirs and explains itself as the example.

### The web app (the SPA)

Five pages, selected from the left panel:

- **Main** — chat with the CEO + a Monaco file workbench over the app's own dirs + an embedded terminal.
- **Specialist** — pick one specialist and chat with it in its own window + workbench.
- **Group** — N specialists side-by-side, colored/relabeled/reordered, with saveable layout templates.
- **Crons** — scheduled automations (CAVE SDNA cron/interval jobs).
- **Gym** — the research-layer page (see *Gym module*, below).

### The HTTP API (FastAPI, served with the SPA on `:3858`)

`/api/chat` · `/api/conversations/{alias}[/new|/active|/{session}]` · `/api/files/{tree,read,write,mkdir,rename,delete}`
· `/api/group-templates` · `/api/automations[...]` · `/api/agents/{alias}/{profile,avatar}` · `/api/departments`
· `/api/gym-specs[...]` · `/api/config` · `/api/health` · a `/ws` stream + an embedded-terminal websocket.

---

## The doc-mirror plugin (loaded in every agent)

doc-mirror is installed as a first-class Claude Code plugin in the container, two ways at once:

- **SDK agents** (the CEO + specialists, driven by `claude_agent_sdk`) load it via the SDK `plugins=` option
  → `--plugin-dir /opt/doc-mirror-plugin`.
- **The interactive terminal** loads it from the container's Claude Code config: the image bakes
  `/home/ceo/.claude/settings.json` (a directory-source marketplace → `/opt/doc-mirror-plugin` +
  `enabledPlugins`) and runs `claude plugin marketplace add` + `claude plugin install` at build, so a fresh
  container shows `doc-mirror ✔ enabled` in `claude plugin list` out of the box.

This gives every agent the doc-mirror state machine, the journal/vision/tracker/cursor CLIs, and the
build-and-ship skills.

---

## Customizing PromptWorld

Everything an agent *is* lives in editable files in this app — editing an agent's dir IS editing that agent:

- **The CEO's voice/role** → `agents/engineer-ceo.md`.
- **A specialist's behavior** → `promptgym/<craft>/CLAUDE.md` + `promptgym/<craft>/.claude/rules/*.md`.
- **The shared world** (re-theme the whole guild — Smiths, a crew, etc.) → `promptgym/world-context.md`
  (one neutral file every agent @-references) + each persona's voice file.
- **The shared global context** → `promptgym/global-context.md`.

The Monaco workbench on the **Main** page is pointed at the app itself, so you can edit these dirs live.

---

## Gym module

The **Gym module** is the research layer: a place where the building agents do **research on the things they
make**, and where you **talk to those agents** in that research context, with dashboards wired up.

You write a **spec** ("I want X to exist, or know why it can't yet"), assign it to a specialist, and give it
a **cron** schedule. On each fire the specialist **researches the spec in a loop** by dispatching a review
subagent that **empirically tests** whether the thing works, and writes the result as a **research paper**
on the spec. You CRUD specs, schedule/stop the research loop, run it on demand, and publish the papers — the
Gym page (`/api/gym-specs`) is the dashboard. (Teams are the one caveat: a team must be run by the
researcher, so auto-research is disabled for team specs — see the in-app note.)

---

## Layout

```
application/promptworld/
  agents/engineer-ceo.md         the CEO persona
  promptgym/<craft>/             the seven specialist AIOS dirs (skill, mcp, prompt, harness, team, workflow, operating_system)
  promptgym/world-context.md     the shared, re-skinnable world
  promptgym/global-context.md    the shared global agent context
  server/                        FastAPI server, file API, conversation/group/gym/automation registries
  frontend/                      the assistant-ui SPA (Main / Specialist / Group / Crons / Gym)
  p_main_agent.py                ClaudePMainAgent — drives agent turns via claude_agent_sdk (loads doc-mirror)
  deploy/                        Dockerfile, build.sh (build|boot|e2e|stop), entrypoint.sh, claude-settings.json
  docs/ context/                 the doc-mirror documentation + journal layer for this app
```
