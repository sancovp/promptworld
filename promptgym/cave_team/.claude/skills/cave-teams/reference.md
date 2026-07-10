# cave-teams — reference

## Topologies & control flow — WRITE YOUR PYTHON HERE

The control flow is **plain Python and Turing-complete** — there is no DSL. You wire *any* agent
topology with four Harness verbs, then either pick a named pattern from `cave_teams.topologies`
or write a new one in ~5 lines. **This is the part you (the coding agent) author for the user.**

```python
from cave_teams import build_team, topologies as T
from cave_teams import when_flag, after, when, all_of, any_of

h = build_team(spec)                 # spec with concurrent agents (see below)

# THE FOUR VERBS (everything composes from these):
h.add_condition(agent, pred)         # NODE gate — may this agent fire?   pred(h, agent) -> bool
h.add_route(src, dst, when=, transform=)   # EDGE — src's output → dst (optional guard / reshape)
h.add_watch(agent, fn)               # OUTPUT→STATE — fn(h, agent, text); set flags from a reply
h.set_flag(name) / h.set_drain(agent)      # STATE / gather-all-pending-inputs

# AND / OR / NOT / arbitrary checks are just Python:
h.add_condition("publish", all_of(when_flag("approved"), when(lambda h,a: h.get_flag("budget") > 0)))
h.add_condition("merge",   after("frontend", "backend", "tests"))   # join/barrier
```

**Named topologies (the AutoGen-class menu — `cave_teams.topologies`):**

| fn | shape |
|---|---|
| `pipeline(h, [a,b,c], task)` | sequential A→B→C |
| `fan_out(h, workers, task)` / `broadcast` | scatter / parallel-map (concurrent) |
| `synthesis_gate(h, synth, sources)` | join: synth fires after ALL sources, drains every output |
| `map_reduce(h, workers, synth, task)` | scatter-gather (the most common shape) |
| `supervisor(h, boss, workers, task)` | hierarchical (compose deeper for sub-teams) |
| `router(h, r, {dst: guard})` | conditional branch (edge guards) |
| `loop_refine(h, worker, critic, task, approved=…)` | reflection loop until the critic approves |
| `round_robin(h, agents, rounds, topic)` | debate / turn-taking |

Each is a worked example — open `topologies.py` and copy the 5-line shape to build your own
(e.g. a "synthesis gate that waits for 3 agents then fans to 2 reviewers"). Firing model:
**an agent fires when it has a pending message AND all its conditions pass; eligible agents run
concurrently.** Set `spec["concurrent"] = False` for deterministic single-threaded runs.

## The spec (full)

| field | type | meaning |
|---|---|---|
| `name` | str (req) | team id; team dir = `/tmp/cave-teams/<name>` |
| `task` | str | what the team should accomplish; drives the autonomous leader. Omit → ready handle |
| `agents` | list (req) | the workers (and usually a leader); see below |
| `agents[].name` | str | alias (the inbox is `messages/<name>.jsonl`) |
| `agents[].backend` | str | `"claude-p"` (real Claude Code w/ tools, subscription auth) or `"minimax"` (cheap text worker) |
| `agents[].model` | str | model id (e.g. `claude-sonnet-4-6`, `MiniMax-M2.7-highspeed`) |
| `agents[].system_prompt` | str | the agent's role |
| `agents[].cwd` | str | working dir for a claude-p agent (default `/tmp`) |
| `agents[].mcp_config` | str | optional MCP config path for a claude-p agent |
| `leader` | obj | `{backend, model, max_turns, cwd}` for the autonomous TeamLeader |
| `team_dir` | str | override the team dir |

## Event kinds (what streams out the seam)

`team_spawned` · `agent_added` · `dispatched` · `response` · `message` · `task` · `done` · `blocked` · `error`

Each event: `{team, kind, agent, data, ts}`. Frontends switch on `kind`.

## Architecture

- **Library (standalone):** `claude -p` (subscription) + MiniMax API + the filesystem. No running CAVE needed.
- **The seam:** `Harness.bus` (an `EventBus`) emits a `TeamEvent` at every boundary. Control IN = `Harness.send_message(to, content)`.
- **Listeners (interchangeable frontends):**
  - `FileListener` → `<team_dir>/events.jsonl` (auto, always on)
  - `HttpFrontendListener(gallery_url)` → POST `/emit` → gallery `/ws` → browser
  - `FrontendListener(server)` → in-process gallery
  - any `on_event(dict)` callback you pass → e.g. a CAVE Channel / Discord

## Frontend (the gallery)

```bash
python3 -m cave_teams.frontend --port 8787     # GET / = gallery, /ws = browsers, POST /emit = spawners
```
The gallery is central + long-running. Every team that POSTs to `/emit` (via the adaptor's
`gallery_url`) appears live — one column per team, one card per agent, busy/idle dot, event log.

## Project to a CAVE Channel / Discord (instead of, or alongside, the gallery)

The seam is generic — pass your own sink as `on_event`:

```python
def to_channel(ev: dict):
    # ev = {team, kind, agent, data, ts}
    cave_channel.post(f"[{ev['team']}/{ev['agent']}] {ev['kind']}: {ev['data']}")

from cave_teams.adaptor import spawn_team
spawn_team(spec, on_event=to_channel)            # → Discord/Channel
# or both at once:
spawn_team(spec, gallery_url="http://localhost:8787", on_event=to_channel)
```

This is how cave-harness becomes ONE frontend (its bidirectional Channels can also feed
replies back via `harness.send_message`) — not a dependency.

## Headless

Omit `gallery_url` and `on_event`: the team runs anyway; the full event stream is in
`/tmp/cave-teams/<name>/events.jsonl`.

## Live token streaming

Watching is **two levels**, both built:
- **event-level** — `dispatched / response / message / done / …` (the coarse log).
- **token-level** — each agent's turn streams token deltas as `stream` events; the gallery
  renders them live (the agent "types") in a dedicated live line per card. `claude -p` uses
  `Popen` + `--include-partial-messages`; MiniMax uses `client.messages.stream`. Token deltas
  are ephemeral: the gallery shows them but they are NOT persisted to `events.jsonl` (the final
  `response` event carries the full text). The HTTP listener is non-blocking (queue + daemon
  thread), so per-token emits never stall the team.

## What this build added (vs the 2026-05-18 proof)

The original build proved the mechanism but hardcoded the frontend as files (poll to watch).
This adds the missing **events-OUT seam** (`EventBus` + emits), a **decoupled gallery** with
**live token streaming**, and the **adaptor** that wires a team to a frontend on the fly — so
any agent (with this skill) can spawn a team and watch it work in real time. The autonomous-leader
path runs on `claude -p` (subscription); MiniMax workers run on `$MINIMAX_API_KEY`.
