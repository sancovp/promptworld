---
name: install-promptworld
description: "WHAT: the deploy WIZARD for PromptWorld — YOU (the agent) build the docker image and boot a container running the whole system (the Engineer-CEO that has every skill + a native subagent per component type, the 7 PromptGym specialist agents, the assistant-ui chat + Monaco file explorer + an embedded terminal), find the Claude credentials on THIS machine, copy them into the container at boot, and then just hand the user a URL. WHEN: when the user wants to install / run / launch / boot / spin up / deploy PromptWorld, or says 'set up promptworld', 'start promptworld', 'boot the promptworld container' (any of)."
---

# install-promptworld — the agent's deploy how-to

YOU (the agent reading this) do the ENTIRE deploy. The user fills in NOTHING and runs NOTHING — when
you finish, you hand them ONE URL to open. There are no placeholders, no bind mounts, no `-e` flags,
no human-typed docker commands. You build the image, find the Claude creds on THIS machine, and boot
via `create → docker cp creds → start` (which works even when docker is the host daemon via a mounted
socket, because it needs no `-v` bind mount of a local path).

## What gets deployed
A single `promptworld:latest` container, on port 3858, serving:
- the **Engineer-CEO** (claude -p) — has every skill + a native subagent per component type
  (skill / mcp / harness / operating_system / prompt / team / workflow);
- the **7 PromptGym specialist** AIOS agents (each scoped to its own `promptgym/<type>/` directory);
- the **assistant-ui** chat SPA + the **Monaco** file explorer over `/workspace` + an embedded
  **xterm terminal** (`/ws/terminal` → a PTY shell as `ceo`);
- **doc-mirror** installed for every agent. Journal is file-only (`DOCMIRROR_CARTON=0`) — no DB.

The image ships **UNAUTHENTICATED** (no creds baked). Auth arrives at boot, two ways — you handle #1,
the user can do #2 if you have no creds:
1. **You cp the creds in** (the normal path): you find the Claude OAuth creds on this machine and
   `docker cp` them into the container.
2. **The user logs in live** in the embedded terminal (`claude auth login`) — the fallback when this
   machine has no creds file (e.g. macOS, where creds live in Keychain).

## Do this (you, the agent)

1. **Locate the deploy dir**: `<plugin-or-repo>/application/promptworld/deploy/`. Confirm
   `deploy/build.sh` + `deploy/Dockerfile` exist.

2. **Build the image** (stages promptworld + the doc-mirror plugin + cave + sdna, then `docker build`;
   a few minutes the first time). NO creds go into the image:
   ```bash
   bash <...>/application/promptworld/deploy/build.sh build
   ```

3. **Find the Claude creds on THIS machine.** The OAuth credentials file is at
   `${HOME}/.claude/.credentials.json` (on this dev box that resolves to
   `/home/GOD/.claude/.credentials.json`). Check it exists:
   ```bash
   ls -l "${HOME}/.claude/.credentials.json"
   ```
   - If it exists → you'll cp it in (step 4 does this automatically).
   - If it does NOT exist (e.g. macOS Keychain) → the container still boots; tell the user to sign in
     via the embedded terminal (`claude auth login`).

4. **Boot it — `create → docker cp creds → start`** (this is exactly what `build.sh boot` does: it
   `docker create`s with `-p 3858:3858` and NO bind mount, `docker cp`s `${HOME}/.claude/.credentials.json`
   to the container's `/creds/.credentials.json`, then `docker start`s; the entrypoint copies `/creds`
   into the `ceo` user's config + chowns it, so it authenticates for any uid):
   ```bash
   bash <...>/application/promptworld/deploy/build.sh boot
   ```

5. **Verify through the real surface** (don't trust "it started"):
   ```bash
   bash <...>/application/promptworld/deploy/build.sh e2e
   ```
   It must show a real CEO `/api/chat` reply AND the `skill-specialist` subagent writing a file inside
   `promptgym/skill/`. (`e2e` uses `docker exec`, so it works regardless of host networking.)

6. **Hand the user the URL.** Tell them: open **http://localhost:3858** — chat with the Engineer-CEO,
   watch it dispatch specialists, edit files in the Monaco panel. If step 3 found no creds, add: "open
   the Terminal panel at the bottom and run `claude auth login` to sign in on your own subscription."

## Done when
`build.sh e2e` shows a real CEO `/api/chat` reply AND the specialist-subagent artifact in-container.
The build/boot are idempotent (safe to re-run). On failure, read `docker logs promptworld-v1`, fix,
re-run.
