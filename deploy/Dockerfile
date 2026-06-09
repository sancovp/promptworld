# PromptWorld V1 image.
# Base = ghcr.io/sancovp/cave-harness-base (the NEUTRAL CAVE-server runtime: claude CLI + node20 +
# python3.11 + the cave/sdna/cave-teams/llegos/heaven stack that boots a CAVE HTTP server, with NO
# jobworld entrypoint/branding). PromptWorld and jobworld are SIBLING x-CAVE products on this shared
# base — neither builds on the other's product image. PromptWorld forks CAVEHTTPServer/CAVEAgent, so
# we refresh the CURRENT cave + sdna over the base, add the promptworld app, build the SPA in-layer,
# and install doc-mirror by default.
#
# Build context is STAGED by deploy/build.sh: the context root holds
#   promptworld/  doc-mirror-plugin/  cave/  sdna/ .
FROM ghcr.io/sancovp/cave-harness-base:v1.0.0

USER root

# --- refresh CURRENT cave + sdna so the promptworld fork matches (our packages -> --no-deps) ---
COPY cave/ /tmp/cave/
COPY sdna/ /tmp/sdna/
RUN pip install --no-cache-dir --no-deps /tmp/cave/ /tmp/sdna/ \
    && rm -rf /tmp/cave /tmp/sdna
# server runtime deps the FastAPI /ws path needs (idempotent if already present)
RUN pip install --no-cache-dir --no-deps websockets requests 2>/dev/null || true
# claude_agent_sdk: the Python SDK p_main_agent.py drives the agent turns with (#41 migration).
# THIRD-PARTY. It needs `mcp` (NOT in the base — the base has fastmcp, a different package). We MUST
# pin mcp==1.12.4 (the host-proven version): a bare `pip install claude-agent-sdk` pulls the LATEST
# mcp (1.27.2) which forces pydantic 2.13.4, but heaven/cave/sdna/llegos pin pydantic==2.10.6 — that
# upgrade would break the CAVE server PromptWorld extends. mcp 1.12.4 needs pydantic>=2.8,<3, which
# 2.10.6 satisfies, so pip leaves pydantic untouched. [VERIFIED in jobworld-cave:latest: SDK imports,
# pydantic stays 2.10.6, `import cave.server.cave_http_server` still works.]
RUN pip install --no-cache-dir 'mcp==1.12.4' 'claude-agent-sdk==0.1.19'
# croniter: lets the Crons page (#46) honor 5-field CRON EXPRESSIONS (e.g. "0 3 * * *"). Without it,
# CAVE's SDNA CronJob.is_due() returns False for any cron expr (it `except ImportError: return False`),
# so cron-expr automations silently never fire; INTERVAL schedules ("every:N") work regardless. Pure-
# python (deps: python-dateutil — already present). Pinned. [VERIFIED in jobworld-cave:latest: `import
# croniter` works, pydantic STAYS 2.10.6, `import cave.server.cave_http_server` still works — no cascade.]
RUN pip install --no-cache-dir 'croniter==2.0.7'

# --- the promptworld app ---
# /creds = the staging mountpoint for host creds (entrypoint copies them to ceo's config + chowns,
# so a host volume-mount works for ANY host uid; pre-creating it also lets `docker cp` target it).
RUN mkdir -p /app /workspace /creds
COPY promptworld/ /app/promptworld/

# --- build the assistant-ui SPA IN-LAYER (node is in the base) — no committed dist dependency ---
WORKDIR /app/promptworld/frontend
RUN npm ci && npm run build
WORKDIR /app/promptworld

# --- doc-mirror installed BY DEFAULT (bins on PATH + ~/.docmirror_plugin_root for `ceo`, so the
#     per-dir _provision_aios / _provision_ceo_aios resolve the plugin inside the container) ---
COPY doc-mirror-plugin/ /opt/doc-mirror-plugin/
RUN mkdir -p /home/ceo/.claude \
    && chown -R ceo:ceo /opt/doc-mirror-plugin /app /workspace /home/ceo/.claude

# doc-mirror registered as a Claude Code PLUGIN in the container's Claude Code config so the
# INTERACTIVE terminal `claude` also loads it (the SDK agents already get it via plugins=/--plugin-dir;
# this is the canonical "load the plugin into the Claude Code application directories" path). A
# directory-source marketplace -> /opt/doc-mirror-plugin (where the plugin tree is COPY'd above);
# enabledPlugins turns it on. Mirrors how the host registers the same plugin.
COPY promptworld/deploy/claude-settings.json /home/ceo/.claude/settings.json
RUN chown ceo:ceo /home/ceo/.claude/settings.json

# NO creds are baked into the image — it ships UNAUTHENTICATED. Auth arrives at boot, two ways:
#   1. the DEPLOYING AGENT does create -> `docker cp <creds> :/creds/.credentials.json` -> start;
#      the entrypoint (root) copies /creds -> /home/ceo/.claude/.credentials.json + chowns ceo.
#   2. OR the user signs in LIVE in the embedded terminal (`claude auth login`).
# (/creds was created above as the docker-cp / mount staging point.)

USER ceo
# Host-level bins/config (install.sh), THEN register + install the plugin into the container's
# Claude Code config so the INTERACTIVE terminal `claude` loads it (directory-source marketplace =
# local read, no auth/network). Belt-and-suspenders with the baked settings.json above; this is the
# canonical `marketplace add` -> `plugin install` flow (per ship-a-plugin). SDK agents are unaffected
# (they load doc-mirror via plugins=/--plugin-dir). HOME=/home/ceo, claude on PATH at /usr/bin/claude.
RUN bash /opt/doc-mirror-plugin/install.sh \
 && claude plugin marketplace add /opt/doc-mirror-plugin \
 && claude plugin install doc-mirror@doc-mirror-marketplace \
 && claude plugin list
USER root

# --- entrypoint + env ---
COPY promptworld/deploy/entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh
# PROMPTWORLD_WORKSPACE = the file-explorer root. Point it at the app itself so the editor shows the
# REAL agent dirs (promptgym/{type}/ + agents/ + server/) — editing an agent's dir IS editing that
# agent. file_api stays path-jailed to this root.
ENV PROMPTWORLD_DIR=/app/promptworld \
    PROMPTWORLD_WORKSPACE=/app/promptworld \
    PORT=3858 \
    DOCMIRROR_CARTON=0 \
    HOME=/home/ceo \
    PATH=/home/ceo/.local/bin:/usr/local/bin:/usr/bin:/bin
EXPOSE 3858
ENTRYPOINT ["/opt/entrypoint.sh"]
