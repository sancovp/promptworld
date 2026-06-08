# vision: PromptWorld — product loop & distribution (aggregated from the journal, 2026-05-31)

Cross-cutting vision. IDEA/DECISION, not yet built. Source: the 2026-05-31 journal design arc.

## The product loop (the flywheel)
```
ASSEMBLE   build your whole Claude setup piece-by-piece in the app (an agent drives paia-builder —
           the *Gym "spec studio": add skills/agents/personas/mcps/plugins, materialize)
   ↓
PROJECT    project the assembled setup as a deployable IMAGE
   ↓
PUBLISH    wrap it in the plugin-distribution pattern: a TOP-LEVEL SKILL that, when someone loads the
           plugin into Claude, LEADS them through installing + building the whole remote system
   ↓
INSTALL    installing someone's plugin = their entire mental model made legible — a FREE COURSE inside
           the app — and it BUILDS YOUR thing, SCORES it (GEAR, later), lets you PUBLISH → un-putdownable
   ↓ (→ they ASSEMBLE → … the network grows)
```
Each published plugin is simultaneously product + demo + content + course ("building IS content IS
product", made literal).

## Dumb-versions-first (the build strategy)
Ship each rung as a standalone "dumb" version BEFORE unifying (unification cascades; can't ship unless
each piece works standalone first). The dumb versions are also the CONTENT/positioning engine. Ladder:
prompt-engineering (the 3 resources — DONE) → agent/skill/mcp/plugin engineering (the "better Claude
Code stuff") → harnesses (CAVE / \*World) → SOMA (admissibility) → STARSYSTEM (unify) → SANCREV.
PromptWorld is the harness/\*World rung and the demo of the whole thing.

## Build approach (decided)

<!-- ===VISION DELTA: id-tagged appends below = the gap (`vision diff <m>`); `doc-mirror-commit --realizes <ids>` drops them on build === -->
- [v1]  **Fork the cave-teams JobWorld/HealthWorld pattern** for the \*World runtime — do not reinvent.
- [v2]  The reusable agent primitive is a persona-scoped `ClaudeSDKClient` (persona = system prompt, own dir,
  own doc-mirror). Copy it per compiler-agent (skill-/mcp-/hook-/persona-/agent-engineer).
- [v3]  The interface = the cave-teams dashboard (FastAPI+WS) wrapping the running team.
- [v4]  Generalize back later: retrofit JobWorld/HealthWorld to the same standalone-agents + CEO-team shape;
  a fork-a-\*World skill.

## Naming
PromptWorld (the \*World) / \*Gym = the compiler-modules (paia-builder). "Guys" = personas. Umbrella name
still open (PromptWorld vs AgentWorld); not load-bearing yet.

## The prompt-system pieces that ARE built (graduated to impl elsewhere)
The doc-mirror-prompts skill + 3 resources (`how-to-write-a-prompt`, `how-to-make-a-persona-prompt`,
`how-to-make-a-harness`) + the CoR-first-complexify authoring loop are DONE in doc-mirror-system/plugin
and propagated live. They are the KNOW-HOW the *Gym agents use. (Those are impl, not vision.)

## Ordered next (pointers — graduate to doc(m) as built)
1. Build PromptWorld as a fork of the cave-teams \*World (JobworldTeam → PromptWorldTeam; departments =
   compiler-agents).
2. The dashboard interface (FastAPI+WS) wrapping the team = the live interface in the container.
3. Container (the \*World image); the start-promptworld skill that boots it; user does `claude
   setup-token` + everything via the interface; talk remotely.
4. paia-builder wired as the *Gym (the assemble flow).
5. publish/port (marketplace + guided-install); GEAR on compiler-output reps; retrofit Job/Health.

## Open mechanism fix (why this doc had to be written by hand)
The journal→vision auto-projection only targets EXISTING module doc(m)s via `--tags`, so vision about a
NOT-YET-BUILT thing (the normal case) silently projects nowhere. FIX: a vision-type journal observation
must auto-create/append a cross-cutting `docs/vision/_<topic>.md` for the thing it's about, even with no
doc(m) yet. Until that's built, aggregate by hand (this doc) — but it should be automatic.
- [v5]  2026-06-01T12:07:53  VISION: CONVERGED PRODUCT/FUNNEL: product loop unchanged (ASSEMBLE via paia-builder -> PROJECT a deployable image -> PUBLISH a self-installing plugin (top-level skill leads the install) -> INSTALL = a free course that BUILDS+SCORES the installer's own thing; 'building IS content IS product'). FUNNEL IS ALREADY PARTLY BUILT on the aisaac site: each *World = a set of domain entry-pages -> the CLINIC funnel (apply/join). HealthWorld = 14 body-system pages BUILT; Dharma = dharma-concierge/ (23 pages) BUILT; JobWorld = jobworld-premium.html is a PLACEHOLDER. The HealthWorld index says 'Same engine. Different world.' = the holographic-work convergence already live in the funnel. PromptWorld gets its own component-page entry set (skill/mcp/hook/persona/plugin -> 'build one' -> apply/join).  tags:[product-and-distribution]
