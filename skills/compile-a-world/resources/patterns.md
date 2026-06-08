# *World patterns — full anatomy

Grounded in a code-read of the four live systems (the differences were verified, not guessed).
Each pattern is `{team-leader, specialists, domain, driver, topology, how a new one is made}`.

---

## JobWorld — the org sim
- **team-leader**: a CEO of departments.
- **specialists**: departments of worker agents.
- **domain**: running an organization (company → dept → project → milestone → goal → task).
- **driver**: heartbeats + events from **automations about the real world** — the CEO dispatches
  tasks and reviews work reported `supposedly_done`.
- **topology**: hierarchy/org (CEO dispatches departments). Team runs over a file-based message bus
  (the cave-teams Harness) or tmux Conversations.
- **how built today**: a CAVE-fork web app — `JobworldAgent(CAVEAgent)` + `JobworldHTTPServer(
  CAVEHTTPServer)` — with the business **domain baked into the Python subclass** (`DOMAIN_ENUM`,
  department specs). A new company is spun by `instantiate.sh` (copy a template, `sed` the port) +
  onboarding config. **Has its own specialized meta-compiler**: JobWorld can make new JobWorlds.
- **signature move**: emits `EVENT:` lines that accumulate into SOP patterns → harvested into reusable
  skills (the company learns its own procedures); a self-grading metacog department.

## GameWorld — the market sim
- **team-leader**: a **Game Master**.
- **specialists**: crafters/traders — **peers in a market**, not a hierarchy.
- **domain**: an economic/trading game around something the agents can **craft**.
- **driver**: the **internal game loop** (craft → trade → score) over shared `game.json` state —
  NOT external real-world events.
- **topology**: **peer market** (the one pattern that is not a CEO+departments hierarchy).
- **how built today**: `gameworld-generator` — the **only real spec→world generator** we have: a
  mode-config JSON → a runnable Claude-Code World dir (GM `CLAUDE.md` + shared `game.json` + an atomic
  `execute.sh` engine + places/quests/achievements + an agent template), with a `--extract` reflexive
  loop that turns an existing world back into a template. **Caveat**: it parameterizes **mechanics,
  not domain** — the actual places/quests/persona are template-copied or hand-built. **Has its own
  specialized meta-compiler**: GameWorld can make new GameWorlds.

## HealthWorld — the body sim ("Osmosis Jones")
- **team-leader**: a CEO/DOCTOR-for-your-body (OSMOSYS).
- **specialists**: body-system agents (≈14 systems as "departments").
- **domain**: your health — agents collaborate to make **holistic analyses from your records + stats**.
- **driver**: your **records + stats** (health imports, webhooks) → analyses.
- **topology**: hierarchy/org — it is **literally a JobWorld fork** (a renamed `(<World>Agent,
  <World>Server)` CAVE-subclass pair; the body is "a company"). Domain hardcoded in the subclass.
- **how built today**: `instantiate.sh` copies the jobworld-style template + `sed`s only the port +
  seeds the system state files. **Probably does NOT have its own meta-compiler** (Isaac: "maybe
  healthworld cant idk") — it's a hand-forked instance.

## PromptWorld — the reactor / meta
- **team-leader**: the **WrightMaster** (currently still named "CEO" — rename pending).
- **specialists**: the seven **\*Wrights** — one per Claude-Code component type (skill, mcp, prompt,
  harness, team, workflow, operating_system), each a `promptgym/<craft>/` **AIOS dir that codes the
  agent** (its own `CLAUDE.md` + `.claude/`).
- **domain**: building Claude-Code components and **nomicons** — and, as the meta, building/composing
  the **other Worlds** as patterns.
- **driver**: **build requests** — the WrightMaster calls the \*Wrights to work a nomicon together.
- **topology**: hierarchy/org, BUT the cleanest substrate: `claude_agent_sdk` per-directory isolated
  AIOS agents + it **carries the nomicon ladder** + a re-skinnable `world-context.md`. Domain is clean
  **config**, not a tangled subclass.
- **the only real difference from the others**: PromptWorld's **team isn't hooked up yet** (the CEO
  doesn't yet *run* the team the way Job/Health/Game leaders do). That is a wiring gap to close, NOT
  an architectural divide. With the meta-compiler, the WrightMaster should run the team.
- **how built**: a CAVE fork (`PromptWorldAgent(CAVEAgent)` + `PromptWorldHTTPServer`), forked from
  HealthWorld, then re-based onto the SDK + nomicon. **Is the meta-compiler**: treats all the above as
  patterns; can build them as AIOS+Teams variants, compose into apps, publish.

---

## What is genuinely SHARED vs per-World (the compiler's variable slots)

**Shared CAVE-core skeleton** (every World has it):
`{ a team-leader persona + a specialist set + a shared state surface + an engine/loop that fires turns
+ injectable .claude/{skills,rules,agents} + a dashboard + a deploy }`.

**Per-World (the slots a World spec fills)**:
- `team-leader role` (CEO | Game Master | WrightMaster | Doctor)
- `topology` (org-hierarchy | peer-market)
- `specialist set` (departments | crafters | \*Wrights | body-systems)
- `domain` (the content + state schema)
- `driver` (real-world automation events | internal game loop | records/stats | build requests)
- `dashboard` + `deploy`

## The honest gaps (state IS vs VISION when you build)
- There is **no general \*World generator** — only per-World ones (`gameworld-generator` real for
  mechanics; Job/Health `instantiate.sh` = copy+sed). Building a real one ("combine the knowledge into
  something new") is the objective, not a thing that exists.
- The nomicon **app-rung** (`ingest-into-nomicon-app`) orchestrates ingest→convert→agentify but its
  **STAGE-3 app-boot is UNPROVEN at scale** (E2E only on a toy single-AIOS). Prove it before relying on it.
- Job/Health bake the domain into a Python subclass (not config); GameWorld parameterizes mechanics
  not domain. A clean compiler should emit **config-driven** Worlds (PromptWorld's shape), not more
  tangled subclasses — but that is a design choice to confirm with Isaac, not a settled fact.
