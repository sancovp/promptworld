# PROMPT: PromptWorld v2 — the first department (PROMPTS) = a prompt-engineer that compiles real prompt artifacts

PromptWorld v1 is done and verified: `PromptWorldAgent(CAVEAgent)` + `PromptWorldHTTPServer(CAVEHTTPServer)`
boot on port 3858, and you chat the engineer-CEO through `POST /api/chat` over the built `ClaudePMainAgent`
(`claude -p --resume`, subscription, ANTHROPIC_API_KEY scrubbed). Now add the FIRST department: **PROMPTS**.

A "department" in PromptWorld = a claude-code COMPONENT TYPE, and its agent = a **component-engineer** that
COMPILES that type into a real artifact on disk. The Prompt department's engineer compiles **prompts** (the
atomic component — everything else composes from prompts). Build ONLY the Prompt department in v2; register
the others as known-but-unimplemented. Standalone — no jobworld/healthworld/starsystem wiring.

## CONTEXT TO READ FIRST (full)
- The v1 you're extending: `application/promptworld/server/{promptworld_agent.py, promptworld_server.py, __main__.py}`, `p_main_agent.py` (`ClaudePMainAgent` — reuse it for the engineer convo), `convo_registry.py`.
- How v1 drives a convo: `PromptWorldAgent.chat()` → `main_agent.send_keys(msg)` + `send_keys("Enter")` + `capture_pane()`. You'll do the same to drive a SECOND convo (the prompt-engineer) on its own alias.
- Quality bar for what a "good prompt" is: the doc-mirror-prompts skill style (CoR-first prompt-files) — look at the existing prompt-files in `application/promptworld/prompts/*.md` (incl. this one) as the SHAPE a compiled prompt should resemble: a self-contained instruction with role/goal/constraints/acceptance. Keep it general (the engineer compiles ANY requested prompt, not just agent-dispatch prompts).

## WHAT TO BUILD (under `application/promptworld/`)

1. **Department registry on `PromptWorldAgent`** — a simple structure listing the canonical component types:
   `["prompt", "skill", "mcp", "harness", "operating_system", "team", "workflow"]`, each marked
   `implemented: bool` (only `prompt` = True in v2). Expose it (used by the route + a `/api/departments` GET).
2. **`agents/prompt-engineer.md`** — the prompt-engineer persona: an agent whose job is to COMPILE a prompt —
   take a natural-language request for "a prompt that does X" and author a clean, self-contained prompt
   artifact (role/goal/constraints/acceptance, CoR-first where it fits the doc-mirror-prompts style), then
   WRITE it to the output path it's told. It must actually create the file (it runs via `claude -p` with
   tools + bypassPermissions, cwd = instance dir, so Write/Bash are available).
3. **The Prompt department wiring** — the prompt-engineer is its OWN `ClaudePMainAgent` convo:
   `ClaudePMainAgent(alias="prompt-engineer", cwd=<instance dir>, registry_path=<same convos.json>)`. Add a
   method on `PromptWorldAgent` like `compile_prompt(request: str, name: str) -> dict` that: ensures the
   prompt-engineer convo exists, sends it a compile instruction (the persona context + the request + the
   exact output path `compiled/prompts/<name>.md`), runs the turn, and returns `{path, reply, ok: <file exists>}`.
   Seed the engineer's turn with the persona from `agents/prompt-engineer.md` (read it and prepend, or pass it
   as the first message of that convo).
4. **Server route** `POST /api/department/prompt` — body `{"request": "...", "name": "..."}` → calls
   `pw.compile_prompt(request, name)` → returns `{path, reply, ok}`. Also `GET /api/departments` → the registry.
5. Output dir: `application/promptworld/compiled/prompts/` (create on demand). Add `compiled/` to the
   promptworld `.gitignore` is NOT wanted — compiled artifacts ARE the product; leave them trackable, but you
   don't need to commit them in this task.

## CONSTRAINTS
- Reuse `ClaudePMainAgent` (claude -p, subscription, no tmux, no SDK). The prompt-engineer is just a second
  named convo — do NOT build a new agent backend.
- Standalone; only `cave.*` + local `p_main_agent`/`convo_registry`.
- Don't break v1: `/api/chat` (the CEO) must still work.

## ACCEPTANCE TEST — actually run it, paste literal output
1. Boot `python3 -m server --dir . --port 3858` (background, no traceback).
2. `GET /api/departments` → shows the 7 types, `prompt` implemented:true. Paste it.
3. `POST /api/department/prompt` with a REAL request, e.g. `{"request":"a prompt that instructs an agent to review a Python file for security issues and report findings as a numbered list","name":"security-review"}`.
4. Show `ok:true` AND **cat the actual file** `compiled/prompts/security-review.md` — it must be a real,
   coherent prompt artifact authored by the prompt-engineer (not a stub, not an error).
5. Confirm `GET /api/convos` now shows BOTH `ceo` and `prompt-engineer` aliases.
6. Confirm `/api/chat` (the CEO) still replies (v1 not broken). Shut down cleanly.

## REPORT BACK
- Files created/changed + the `compile_prompt` method code + the route.
- Literal: boot log, `/api/departments`, the `POST /api/department/prompt` response, the **full cat of the
  compiled prompt file**, `/api/convos` showing both aliases, and a v1 `/api/chat` still-works check.
- The exact route + payload shapes (for independent verification).
- Anything deferred (e.g. CEO auto-dispatch to the department).

A green claim without the literal compiled-prompt-file contents is a FAIL.
