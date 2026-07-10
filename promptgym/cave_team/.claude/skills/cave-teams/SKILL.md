---
name: cave-teams
description: "WHAT: Spin up a programmatic agent TEAM on the fly from a spec — mixed Claude-Code (claude -p, subscription) leaders + cheap MiniMax workers — with a LIVE WEB GALLERY that shows each agent in its own window as it works. cave-teams is a STANDALONE library (claude -p + MiniMax + files; no running CAVE required); it optionally streams its event seam to a gallery, a CAVE Channel, or Discord. WHEN: when you need to launch a sub-team to do parallel/heterogeneous work and watch it live — equip when spawning a team, unequip when done. Triggers: spawn a team, run a team, cave-teams, agent squadron, watch the agents, team gallery."
---

# cave-teams — programmatic teams, watched live

You PROGRAM a team (you do not have Claude Code improvise deletable JSONs). One call
spins it up, runs it, and streams every boundary (agent dispatched / responded / message
/ done / blocked) out the **event seam** to any frontend. The default frontend is a live
web **gallery**: each team a column, each agent its own card, appearing on the fly.

## 1. Start the gallery once (long-running)

```bash
python3 -m cave_teams.frontend --port 8787   # open http://localhost:8787
```

## 2. Spin up a team (this is the whole API)

```bash
python3 scripts/spawn_team.py '<spec-json>'           # or a path to a .json file
# gallery auto-detected from $CAVE_TEAMS_GALLERY, or pass --gallery http://localhost:8787
```

…or from Python (e.g. inside another agent / a CAVE server):

```python
from cave_teams.adaptor import spawn_team
spawn_team(spec, gallery_url="http://localhost:8787")          # runs an autonomous leader
# or, to drive it yourself (programmatic flow, no leader):
from cave_teams.adaptor import build_team
h = build_team(spec, gallery_url="http://localhost:8787")
h.send_message("leader", "writer", "draft the email")          # control IN
h.deliver("leader", "writer", "draft the email")               # run one turn (streams out)
```

## 3. The spec

```json
{
  "name": "outreach",
  "task": "find 3 leads in Kennesaw GA and draft a cold email for each",
  "agents": [
    {"name": "leader",  "backend": "claude-p", "model": "claude-sonnet-4-6",
     "system_prompt": "You are the team leader. Dispatch workers, review, finish."},
    {"name": "research","backend": "claude-p", "model": "claude-sonnet-4-6",
     "system_prompt": "You research leads with WebSearch."},
    {"name": "writer",  "backend": "minimax",
     "system_prompt": "You write CAN-SPAM-compliant cold emails."}
  ],
  "leader": {"model": "claude-sonnet-4-6", "max_turns": 40}
}
```

- `backend`: `"claude-p"` (real Claude Code with tools, runs on your subscription) or
  `"minimax"` (cheap, text-only worker).
- Omit `task` (or pass `run=False`) to get a ready team handle you drive yourself.
- Omit `gallery_url` to run **headless** — it still works; events go to
  `/tmp/cave-teams/<name>/events.jsonl`.

## Architecture (one seam, swappable frontends)

```
spawn_team(spec, gallery_url)
  → Harness.bus  (the EVENT SEAM: emits at every boundary)
       ├─ FileListener            → /tmp/cave-teams/<name>/events.jsonl   (always)
       ├─ HttpFrontendListener    → POST gallery /emit → /ws → browser gallery
       └─ your on_event           → a CAVE Channel → Discord, a web dashboard, anything
  control IN: harness.send_message(to, content)   (already there)
```

cave-teams stays standalone; "using CAVE" just means pointing the seam at a CAVE
surface. See `reference.md` for the full spec schema, the event kinds, and how to
project to a CAVE Channel / Discord.
