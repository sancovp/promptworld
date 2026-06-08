# PROMPT: Build PromptWorld v1 — fork the CAVE-core *World, inject the -p main_agent, boot, chat to the engineer-CEO

You are forking the proven twi-healthworld CAVE-*World into PromptWorld v1: a standalone server you boot
and chat with an "engineer-CEO" agent through a web UI — backed by the already-built `claude -p` main_agent
(subscription auth), NOT tmux. **Departments are DEFERRED** — v1 is just the engineer-CEO + chat. Do not
wire PromptWorld to jobworld/healthworld/starsystem (it stays standalone).

## CONTEXT YOU MUST READ FIRST (full files, no skimming)
- Template (the proven working *World): `/home/GOD/twi-healthworld/server/{__main__.py, healthworld_agent.py, healthworld_server.py, __init__.py}` and its `index.html` / dashboard + the CEO-chat endpoint (find how the dashboard chat posts to the server and how the server calls `self.cave.main_agent.send_keys/capture_pane`). 
- The CAVE base: `/home/GOD/gnosys-plugin-v2/application/cave/cave/core/cave_agent.py` (how `__init__` builds `self.main_agent` ≈ lines 109, 285-293) and `cave/core/agent.py` `CodeAgent` (the `send_keys`/`capture_pane`/`session_exists` surface).
- The ALREADY-BUILT, VERIFIED `-p` main_agent you will inject: `/home/GOD/gnosys-plugin-v2/application/promptworld/p_main_agent.py` (`ClaudePMainAgent`) + `convo_registry.py`. It already scrubs `ANTHROPIC_API_KEY` so claude -p uses the subscription. Do NOT rewrite it; use it.

## WHAT TO BUILD (all under `/home/GOD/gnosys-plugin-v2/application/promptworld/`)

Create a `server/` package mirroring healthworld's:
1. `server/__init__.py`, `server/__main__.py` — entry point `python -m server --dir . --port 3858` (drop the `--tmux` arg or keep it inert; PromptWorld has NO tmux). Builds `PromptWorldAgent` + `PromptWorldHTTPServer(cave=agent)`, `server.run()`. Port default **3858**.
2. `server/promptworld_agent.py` — `class PromptWorldAgent(CAVEAgent)`:
   - fork `HealthworldAgent` but **STRIP the health domain**: no `DEPARTMENT_SPECS`, no `_ensure_body_departments`, no body-system enum. v1 has NO departments.
   - **Inject the -p main_agent (the crux):** in `__init__`, call `super().__init__(config)` then **override** `self.main_agent = ClaudePMainAgent(alias="ceo", cwd=<instance dir>, registry_path=<instance>/.promptworld/convos.json)` — replacing whatever tmux `ClaudeCodeAgent` CAVEAgent built. Import it: `from ..p_main_agent import ClaudePMainAgent` (or move `p_main_agent.py`/`convo_registry.py` into the package and import locally — your call, keep it clean and importable under `python -m server`).
   - Keep the CAVEConfig/MainAgentConfig wiring healthworld uses (working_dir = the instance dir).
3. `server/promptworld_server.py` — `class PromptWorldHTTPServer(CAVEHTTPServer)`: fork `HealthworldHTTPServer`, rename, **keep the CEO-chat endpoint + dashboard serving**, drop health-specific routes (department-status, health-import). The chat endpoint must call `self.cave.main_agent.send_keys(...)` / `send_keys("Enter")` / `capture_pane(...)` exactly as healthworld does — which now drives `ClaudePMainAgent` (claude -p) transparently.
4. `index.html` (or wherever healthworld serves the dashboard) — fork it, rebrand to "PromptWorld", keep the chat panel. Minimal is fine; it must let you type a message and see the engineer-CEO's reply.
5. `agents/engineer-ceo.md` — a STUB persona for the engineer-CEO: an agent whose job is compiling claude-code components and making agents (departments — MCPs/Skills/Harnesses/Operating-Systems/Prompts/Teams/Workflows — are deferred; for v1 it just converses competently as "the engineer"). Keep it short.
6. **Delete the dead skeleton:** `run_agent.py`, `entrypoint_agent.sh`, `_probe_sysprompt.py`, `_probe_entrypoint.sh`, and the old bare-FastAPI `server.py` at the promptworld root (it's superseded by `server/`). (Use `git rm` if tracked, else `rm`.) Do NOT delete `p_main_agent.py`/`convo_registry.py`/`test_p_main_agent.py`/`prompts/`/`docs/`.

## CONSTRAINTS
- Pure Claude on the subscription: the engineer-CEO runs via `ClaudePMainAgent` (claude -p, ANTHROPIC_API_KEY scrubbed). NO tmux, NO anthropic base SDK, NO claude_agent_sdk, NO SDNA.
- Standalone: no imports from jobworld/healthworld/starsystem; only `cave.*` + the local `p_main_agent`.
- Don't try to use `CAVEHTTPServer` raw — fork the WORKING `HealthworldHTTPServer` extension (CAVE is mid-refactor; the healthworld extension is the proven-bootable path).

## ACCEPTANCE TEST — you must actually boot it and chat (paste literal output)
1. Boot: `cd /home/GOD/gnosys-plugin-v2/application/promptworld && python3 -m server --dir . --port 3858` (run in background, capture logs). Confirm it starts without traceback.
2. `curl -s localhost:3858/health` (or whatever the health route is) → 200 / healthy JSON. Paste it.
3. The real chat round-trip through the SAME surface the UI uses: POST a message to the chat endpoint (find the exact route + payload in promptworld_server.py — mirror how the dashboard posts), e.g. "You are the PromptWorld engineer. Reply in one sentence: what do you build?" → capture the engineer-CEO's actual reply (it must be a real claude -p response on the subscription, not an error). Paste the literal request + response.
4. Confirm the conversation is registered/resumable (the convo registry has a "ceo" alias with a session_id after the turn).
5. Shut the server down cleanly.

## REPORT BACK
- The files you created/deleted (paths) and the public shape of `PromptWorldAgent` / `PromptWorldHTTPServer`.
- The exact main_agent-injection code (the `super().__init__` + `self.main_agent = ClaudePMainAgent(...)` override).
- The literal boot log, the `/health` output, and the literal chat request+response showing the engineer-CEO replying via claude -p.
- The chat endpoint route + payload shape (so it can be verified independently).
- Anything that differed from healthworld's structure or any CAVE wart you worked around.
- Anything deferred.

A green claim without the literal boot + /health + chat-response output is a FAIL.
