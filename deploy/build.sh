#!/usr/bin/env bash
# PromptWorld V1 — build / boot / e2e / stop.
#
#   build.sh build           Stage a build context (promptworld + doc-mirror plugin + cave + sdna)
#                            and build the promptworld:latest image.
#   build.sh boot [hostport] Boot a container (mind_of_god-safe: create -> docker cp creds +
#                            workspace -> start; NO -v of mind_of_god paths).
#   build.sh e2e  [hostport] Verify the running container from INSIDE it (docker exec curl):
#                            SPA, /api/health, /api/files/tree, a real CEO /api/chat reply, and a
#                            CEO->skill-specialist native subagent that writes a file in its dir.
#   build.sh stop            Remove the container.
#
# On a NORMAL host (not mind_of_god) prefer: build.sh build  then  docker compose -f
# deploy/docker-compose.yml up  (compose bind-mounts ./workspace + your ~/.claude creds).
set -euo pipefail

MONO="/home/GOD/gnosys-plugin-v2"
PW="$MONO/application/promptworld"
IMAGE="promptworld:latest"
NAME="promptworld-v1"
PORT="3858"                       # in-container server port (fixed)
HOSTPORT="${2:-38588}"            # host-published port (E2E uses exec, so this is cosmetic here)
CTX="/tmp/pw-build-ctx"
WS="/tmp/promptworld-workspace"   # a sample workspace docker-cp'd in at boot (no host bind mount)

# stage_dep <ctx_subdir> <mono_path> <tier2_url>
# DUAL-MODE dependency staging. If the monorepo path exists (our dev box), cp it (fast, the CURRENT
# source). Otherwise (an EXTERNAL clone of the promptworld plugin, no private monorepo present),
# git clone --depth 1 the published tier-2 public repo into the context. Either way the dep lands
# at $CTX/<ctx_subdir> so the Dockerfile's COPY paths are identical for both modes.
stage_dep() {
  local sub="$1" mono="$2" url="$3"
  if [ -d "$mono" ]; then
    echo "[build]   $sub: cp from monorepo ($mono)"
    cp -r "$mono" "$CTX/$sub"
  else
    echo "[build]   $sub: git clone --depth 1 $url (monorepo absent)"
    git clone --depth 1 "$url" "$CTX/$sub"
    rm -rf "$CTX/$sub/.git"
  fi
}

stage_context() {
  echo "[build] staging context at $CTX ..."
  rm -rf "$CTX"; mkdir -p "$CTX"
  # promptworld app (prune node_modules/dist/runtime/__pycache__/scoped-runtime cruft)
  if command -v rsync >/dev/null 2>&1; then
    # STAGE the per-dir AIOS source: promptgym/<type>/{CLAUDE.md, .claude/{rules,agents}, docs/,
    # context/}. EXCLUDE only the CEO root .claude (regenerated at runtime: '/.claude' is anchored
    # to $PW) and the RUNTIME symlinks provisioned into promptgym/<type>/.claude/{skills,agents}/
    # (doc-mirror skill links + the universal-worker subagent — regenerated at agent init).
    rsync -a \
      --exclude 'frontend/node_modules' --exclude 'frontend/dist' \
      --exclude '/.claude' --exclude '__pycache__' --exclude '*.pyc' \
      --exclude '.promptworld' --exclude 'promptgym/.promptgym' \
      --exclude 'promptgym/*/.claude/skills/*' \
      --exclude 'promptgym/*/.claude/agents/universal-worker.md' \
      --exclude 'promptgym/*/projects' --exclude 'promptgym/*/backups' \
      --exclude 'promptgym/*/sessions' --exclude 'promptgym/*/session-env' \
      --exclude 'promptgym/*/shell-snapshots' --exclude 'promptgym/*/telemetry' \
      --exclude 'promptgym/*/statsig' --exclude 'promptgym/*/todos' \
      --exclude 'promptgym/*/.claude.json' \
      --exclude 'promptgym/*/.credentials.json' --exclude 'promptgym/*/.last-cleanup' \
      --exclude 'promptgym/*/mcp-needs-auth-cache.json' \
      --exclude 'compiled' \
      "$PW/" "$CTX/promptworld/"
  else
    cp -r "$PW" "$CTX/promptworld"
    # drop the CEO root .claude only (regenerated at runtime); KEEP promptgym/<type>/.claude
    # authored content (rules/agents) + docs/ + context/.
    rm -rf "$CTX/promptworld/frontend/node_modules" "$CTX/promptworld/frontend/dist" \
           "$CTX/promptworld/.claude" "$CTX/promptworld/.promptworld" "$CTX/promptworld/compiled"
    find "$CTX/promptworld" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
    # scoped-runtime cruft under promptgym/<type>/ (legacy CLAUDE_CONFIG_DIR model)
    find "$CTX/promptworld/promptgym" -maxdepth 2 \
      \( -name projects -o -name backups -o -name sessions -o -name session-env \
         -o -name shell-snapshots -o -name telemetry -o -name statsig -o -name todos \
         -o -name '.claude.json' -o -name '.credentials.json' \
         -o -name '.last-cleanup' -o -name 'mcp-needs-auth-cache.json' \) \
      -exec rm -rf {} + 2>/dev/null || true
    rm -rf "$CTX/promptworld/promptgym/.promptgym" 2>/dev/null || true
    # drop ALL provisioned runtime symlinks under promptgym/<type>/.claude/ (doc-mirror skill
    # links + the universal-worker subagent) — regenerated at agent init. Authored .gitkeep/files
    # are real files, kept.
    find "$CTX/promptworld/promptgym" -type l -delete 2>/dev/null || true
  fi
  # DUAL-MODE deps: cp from the monorepo when present (our dev path), else clone the tier-2 repo.
  stage_dep doc-mirror-plugin "$MONO/doc-mirror-system/plugin" "https://github.com/sancovp/doc-mirror.git"
  stage_dep cave              "$MONO/application/cave"         "https://github.com/sancovp/cave.git"
  stage_dep sdna              "$MONO/base/sdna"                "https://github.com/sancovp/sdna.git"
  find "$CTX/cave" "$CTX/sdna" "$CTX/doc-mirror-plugin" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$CTX/doc-mirror-plugin" -name '*.bak_*' -delete 2>/dev/null || true
  # NO creds are staged or baked — the image ships UNAUTHENTICATED. Auth arrives at boot via
  # `docker cp <creds> :/creds` (the AGENT deploy path, see boot()) or the embedded terminal login.
}

build() {
  stage_context
  echo "[build] docker build $IMAGE ..."
  docker build -t "$IMAGE" -f "$PW/deploy/Dockerfile" "$CTX"
  rm -rf "$CTX"
  echo "[build] done: $IMAGE"
}

boot() {
  echo "[boot] (re)creating $NAME on host port $HOSTPORT -> container $PORT (agent create->cp->start) ..."
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  # AGENT DEPLOY PATH: create -> docker cp creds to the /creds STAGING path -> start. No -v bind
  # mount (works from mind_of_god / host docker socket). The entrypoint (root) copies /creds into
  # ceo's config + chowns, so it authenticates for ANY host uid. Creds are read from this machine
  # (${HOME}/.claude/.credentials.json). If absent, the container still boots — the user logs in
  # live in the embedded terminal (`claude auth login`).
  # PROVIDER ENV (load-bearing): the agents run on MiniMax-M3, so the container MUST get the
  # MiniMax key + provider config. Omitting -e MINIMAX_API_KEY leaves ANTHROPIC_AUTH_TOKEN empty
  # in the entrypoint -> every agent turn POSTs to MiniMax with no auth -> hangs -> /api/chat
  # times out. Pass it through from this host (where it is set) at create time.
  docker create --name "$NAME" -p "${HOSTPORT}:${PORT}" \
    -e MINIMAX_API_KEY="${MINIMAX_API_KEY:-}" \
    -e DEFAULT_CLAUDE_CODE_MODEL="${DEFAULT_CLAUDE_CODE_MODEL:-Minimax-M3[1m]}" \
    -e ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.minimax.io/anthropic}" \
    "$IMAGE" >/dev/null
  if [ -z "${MINIMAX_API_KEY:-}" ]; then
    echo "[boot] WARNING: MINIMAX_API_KEY is empty on this host — agent turns will hang (no provider auth). Export it before boot."
  fi
  if [ -f "${HOME}/.claude/.credentials.json" ]; then
    docker cp "${HOME}/.claude/.credentials.json" "$NAME:/creds/.credentials.json"
    echo "[boot] cp'd creds from ${HOME}/.claude/.credentials.json -> :/creds (authenticated)"
  else
    echo "[boot] no creds at ${HOME}/.claude/.credentials.json — boots UNAUTHENTICATED (terminal login)"
  fi
  # a sample workspace (the Monaco file explorer / file API jail operates on /workspace)
  mkdir -p "$WS"; echo "hello from the promptworld workspace" > "$WS/README.md"
  docker cp "$WS/." "$NAME:/workspace/"
  docker start "$NAME" >/dev/null
  echo "[boot] started $NAME (logs: docker logs -f $NAME)"
}

wait_up() {
  echo "[e2e] waiting for the server inside $NAME ..."
  for _ in $(seq 1 90); do
    if docker exec "$NAME" sh -c "curl -sf localhost:${PORT}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "[e2e] server did not come up; recent logs:"; docker logs --tail 60 "$NAME" 2>&1 || true
  return 1
}

e2e() {
  wait_up || return 1
  echo "=== /api/health ==="; docker exec "$NAME" sh -c "curl -s localhost:${PORT}/api/health"; echo
  echo "=== GET / (SPA, first 240 chars) ==="; docker exec "$NAME" sh -c "curl -s localhost:${PORT}/ | head -c 240"; echo
  echo "=== /api/files/tree (operates on /workspace, first 240) ==="; docker exec "$NAME" sh -c "curl -s localhost:${PORT}/api/files/tree | head -c 240"; echo
  echo "=== POST /api/chat (real CEO reply IN-CONTAINER) ==="
  docker exec "$NAME" sh -c "curl -s -X POST localhost:${PORT}/api/chat -H 'content-type: application/json' -d '{\"message\":\"Reply with exactly the token DOCKERPONG and nothing else.\"}'"; echo
  echo "=== POST /api/chat (CEO -> skill-specialist NATIVE subagent writes a file in its dir) ==="
  docker exec "$NAME" sh -c "curl -s -X POST localhost:${PORT}/api/chat -H 'content-type: application/json' -d '{\"message\":\"Use your Task tool to delegate to your skill-specialist subagent. Instruct it EXACTLY: work ONLY in your promptgym/skill/ directory; create a file PROBE_DOCKER.txt there containing exactly DOCKER-SUB-OK. Then report what it did.\"}'"; echo
  echo "=== verify the subagent's artifact exists IN-CONTAINER ==="
  docker exec "$NAME" sh -c "cat /app/promptworld/promptgym/skill/PROBE_DOCKER.txt 2>/dev/null && echo ' <- PROBE present' || echo 'PROBE MISSING'"
}

stop() { docker rm -f "$NAME" >/dev/null 2>&1 && echo "[stop] removed $NAME" || echo "[stop] $NAME not running"; }

case "${1:-}" in
  build) build ;;
  boot)  boot ;;
  e2e)   e2e ;;
  stop)  stop ;;
  all)   build; boot; e2e ;;
  *) echo "usage: $0 {build|boot|e2e|stop|all} [hostport]"; exit 1 ;;
esac
