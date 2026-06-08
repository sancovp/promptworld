#!/usr/bin/env bash
# PromptWorld container entrypoint. Runs as root FIRST (to take ownership of the files brought in
# at boot), then DROPS to the non-root `ceo` user to run the server — the Claude CLI refuses
# --dangerously-skip-permissions (bypassPermissions) as root.
set -e

# Make the Claude subscription creds available to `ceo` regardless of HOW they arrive — and for
# ANY host uid:
#   - HOST volume-mount: the host file is bind-mounted read-only at /creds/.credentials.json. It
#     keeps the HOST uid + mode 600 and a :ro mount CANNOT be chowned, so `ceo` (uid 1000) could
#     only read it if the host user were also uid 1000. Instead, root (this phase) — which can
#     always read a :ro mount — COPIES it into ceo's config and chowns the COPY. Works for any uid.
#   - create -> docker cp -> start (mind_of_god): creds are cp'd straight to
#     /home/ceo/.claude/.credentials.json (root-owned); the chown below hands the file to ceo.
mkdir -p /home/ceo/.claude
if [ -f /creds/.credentials.json ]; then
  cp -f /creds/.credentials.json /home/ceo/.claude/.credentials.json
fi
chown -R ceo:ceo /home/ceo/.claude 2>/dev/null || true
chown -R ceo:ceo /workspace 2>/dev/null || true

PORT="${PORT:-3858}"

exec su -s /bin/bash ceo -c "
  export HOME=/home/ceo
  export PATH=/home/ceo/.local/bin:\$PATH
  export DOCMIRROR_CARTON=${DOCMIRROR_CARTON:-0}
  export PROMPTWORLD_WORKSPACE=${PROMPTWORLD_WORKSPACE:-/app/promptworld}
  # PROVIDER: run the Claude Code agents on MiniMax-M3 (Anthropic-compatible gateway). The
  # MiniMax secret arrives at deploy as MINIMAX_API_KEY (or ANTHROPIC_AUTH_TOKEN) via docker -e;
  # p_main_agent._provider_env reads these. If absent, the agents fall back (no hard break).
  export DEFAULT_CLAUDE_CODE_MODEL=${DEFAULT_CLAUDE_CODE_MODEL:-Minimax-M3[1m]}
  export ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.minimax.io/anthropic}
  export ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-${MINIMAX_API_KEY:-}}
  cd /app/promptworld
  exec python3 -m server --dir /app/promptworld --port ${PORT} --host 0.0.0.0
"
