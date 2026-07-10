"""cave_teams_bridge — render a spawned cave-team's live event stream INSIDE PromptWorld's gallery.

A cave-team (spawned by the Cave Teamwizard via the cave-teams skill) streams its TeamEvents
(`{team, kind, agent, data, ts}`) to `$CAVE_TEAMS_GALLERY/emit`. PromptWorld points that env at its
own bridge route, which calls map_event() here to translate each cave-event into the SAME
claude -p stream-json shape the React gallery already consumes (`eventMapping.reduceEvent`:
`{type:"assistant", message:{content:[{type:"text",text}]}}` and `{type:"result"}`), then broadcasts
it on /ws to the Cave Teamwizard's window (alias `cave_team`). So the whole team's life — spawn,
each agent's dispatch + live token stream + response, done/blocked — unfolds in ONE gallery window,
no separate frontend.

map_event is PURE (no server/DOM) → unit-testable headlessly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# the alias of the Cave Teamwizard window in the gallery (matches agents.ts + COMPONENT_TYPES)
ALIAS = "cave_team"


def _text(s: str) -> Dict[str, Any]:
    """A stream-json assistant-text event (reduceEvent accumulates these into the live bubble)."""
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": s}]}}


def _result(subtype: str = "success") -> Dict[str, Any]:
    """A stream-json result event — ends the current turn so the next one starts a fresh bubble."""
    return {"type": "result", "subtype": subtype, "result": ""}


def map_event(ce: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Map ONE cave-teams TeamEvent → a list of (alias, stream-json-event) to broadcast.

    Returns [] for unknown kinds (silently ignored). All output targets the `cave_team` window so
    the team reads as one coherent live transcript, each line labeled by agent.
    """
    kind = ce.get("kind", "")
    team = ce.get("team", "")
    agent = ce.get("agent", "")
    d = ce.get("data") or {}
    out: List[Tuple[str, Dict[str, Any]]] = []

    if kind == "team_spawned":
        agents = ", ".join(d.get("agents", []) or [])
        out.append((ALIAS, _text(f"\n▣ {team} — spawned [{agents}]\n   task: {d.get('task', '')}\n")))
    elif kind == "agent_added":
        model = d.get("model") or ""
        out.append((ALIAS, _text(f"  + {agent} ({d.get('backend', '')} {model})\n")))
    elif kind == "dispatched":
        out.append((ALIAS, _text(f"\n▶ {agent} ◄ {d.get('frm', '')}: {str(d.get('content', ''))[:200]}\n")))
    elif kind == "stream":
        out.append((ALIAS, _text(str(d.get("delta", "")))))         # live token typing
    elif kind == "response":
        out.append((ALIAS, _text("\n")))                            # turn already streamed; just separate
    elif kind == "message":
        out.append((ALIAS, _text(f"✉ {agent} ◄ {d.get('frm', '')}: {str(d.get('content', ''))[:200]}\n")))
    elif kind == "done":
        out.append((ALIAS, _text(f"\n✅ {team} done: {str(d.get('summary', ''))[:300]}\n")))
        out.append((ALIAS, _result("success")))
    elif kind == "blocked":
        out.append((ALIAS, _text(f"\n⛔ {team} blocked: {d.get('reason', '')}\n")))
        out.append((ALIAS, _result("blocked")))
    elif kind == "error":
        out.append((ALIAS, _text(f"\n❌ {agent or team} error: {d.get('error', '')}\n")))

    return out
