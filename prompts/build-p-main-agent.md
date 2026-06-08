# PROMPT: Build the `claude -p`-backed main_agent for PromptWorld (standalone, verified)

You are building ONE focused module for PromptWorld and proving it works in isolation. Do exactly this
deliverable; do not fork CAVE or touch healthworld/jobworld — that is a later step.

## GOAL

Build a drop-in replacement for CAVE's tmux `main_agent` that is backed by **`claude -p --resume`**
instead of a tmux TUI, plus an **alias↔session_id registry** that gives named, save/resumable
conversations. It must satisfy the SAME method surface CAVE's `CodeAgent` exposes, so a later step can
inject it into `CAVEAgent` with zero other changes. Then PROVE it in a standalone test (no CAVE, no tmux).

## HARD CONSTRAINTS (do not violate — these are the whole point)

- **Pure Claude Code, headless.** Use the `claude` CLI in `-p` (print/headless) mode via `subprocess`.
- **NO tmux.** No `send-keys` to a terminal, no `capture-pane`, no TUI puppeting.
- **NO SDNA, NO claude_agent_sdk / ClaudeSDKClient, NO heaven/sdna imports.** Plain `subprocess` + `claude -p` only. (The existing `cave/core/remote_agent.py` uses SDNA — do NOT copy it.)
- **NO host-settings bloat.** The `claude -p` agent must run with a SCOPED/LEAN settings dir (only the paia hooks + `--permission-mode bypassPermissions`), NOT the full `~/.claude`. Pass settings explicitly.
- Python 3.11, stdlib + whatever PromptWorld already uses. New files go under `application/promptworld/`.

## STEP 1 — Confirm the exact `claude -p` resume mechanism EMPIRICALLY (do this first, report it)

Do NOT assume flags. Run and read:
```
claude --help 2>&1 | grep -iE 'resume|session|output-format|permission|print' -A1
```
Then prove a real two-turn resume from the shell (the container is already `claude login`'d):
```
# turn 1 — start a session, capture its id from --output-format json
claude -p --output-format json --permission-mode bypassPermissions "Remember the number 42. Reply OK." 
# note the session_id field in the JSON
# turn 2 — resume that session id, confirm it remembers
claude -p --resume <session_id> --output-format json --permission-mode bypassPermissions "What number did I ask you to remember?"
```
Confirm the response to turn 2 contains "42". Record in your report the EXACT flags that work (the
session_id field name, whether `--session-id <uuid>` to preset it exists, how `stream-json` differs from
`json`). If a flag differs from the above, use what actually works and say so.

## STEP 2 — The interface to satisfy (mirror CAVE's CodeAgent surface)

Read `application/cave/cave/core/agent.py` — the `CodeAgent` class (≈ lines 903-997) and how
`twi-healthworld/server/healthworld_agent.py` (≈ lines 254-271) calls `self.main_agent.send_keys(prompt)`,
`send_keys("Enter")`, `capture_pane(...)`, `session_exists()`. Your class MUST expose at least:
- `session_exists() -> bool`
- `create_session() / spawn_agent() -> bool`   (init/ensure a conversation exists)
- `send_keys(*sequence) -> bool`                (a str is a prompt chunk; `"Enter"` = end-of-prompt → run a turn; a float = ignore/no sleep needed)
- `capture_pane(history_limit: int = 5000) -> str`  (return the conversation transcript as text)
- `send_and_wait(prompt: str, timeout=None) -> str`  (send a prompt, run the turn, return the response text)

Semantics (per the settled design): `send_keys` accumulates a pending prompt; `"Enter"` flushes it as ONE
`claude -p --resume` turn (turn-loop / message-queue — async events delivered at the next turn boundary);
`capture_pane` returns the rendered transcript of the resumed session. No mid-turn injection needed.

## STEP 3 — The alias↔session_id registry (the convo management tmux lacks)

A small persistent registry (JSON file, e.g. `~/.promptworld/convos.json` or a configurable path):
- `new(alias) -> session_id` (start a fresh convo, store alias→session_id)
- `resume(alias) -> session_id` (look up an existing convo by its human alias)
- `rename(old_alias, new_alias)`, `list() -> {alias: session_id}`
- The main_agent is constructed with an `alias` (which convo it is driving); its turns use that alias's
  session_id and update it if `claude` rotates the id per turn.

## DELIVERABLES (under `application/promptworld/`)

1. `p_main_agent.py` — the class (suggest `ClaudePMainAgent`) implementing the Step-2 surface over `claude -p`.
2. the alias registry (in `p_main_agent.py` or a sibling `convo_registry.py`).
3. `test_p_main_agent.py` — a standalone pytest/script (NO CAVE import) that proves:
   - (a) `new("t1")` then `send_and_wait("Remember the number 42, reply OK")` returns a reply;
   - (b) a FRESH `ClaudePMainAgent(alias="t1")` (simulating restart) `send_and_wait("What number?")` → response contains **"42"** (proves persistence via the registry + `--resume`);
   - (c) `registry.list()` shows `t1`.
4. a lean settings dir / file used for the `-p` invocation (paia hooks + bypassPermissions only) — if the
   paia hooks aren't trivially locatable, stub the settings to just `--permission-mode bypassPermissions`
   and NOTE in your report that paia-hook wiring is deferred.

## VERIFY (you must actually run it — report literal output)

Run `python test_p_main_agent.py` (or `pytest`) and paste the REAL output showing (a)/(b)/(c) pass,
especially the turn-2 response containing "42". A green claim without the literal transcript is a FAIL.

## REPORT BACK (exactly this)

- The exact working `claude -p` resume flags (from Step 1), with the 2-turn proof output.
- The files you wrote (paths) and the public surface of `ClaudePMainAgent`.
- The literal test output proving persistence across a fresh instance.
- Anything deferred (e.g. paia-hook settings) and why.
- Any place the real `claude` behavior differed from this spec and what you did about it.
