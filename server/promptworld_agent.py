"""PromptWorldAgent — CAVEAgent subclass for PromptWorld v1.

Forked from twi-healthworld's HealthworldAgent, with the health domain STRIPPED:
no DEPARTMENT_SPECS, no _ensure_body_departments, no body-system enum. v1 has NO
departments — it is just the engineer-CEO + chat.

THE CRUX — the main_agent injection:
    super().__init__(config) builds CAVEAgent, whose _attach_to_session() sets
    self.main_agent to a tmux ClaudeCodeAgent (or None if no tmux session). We then
    OVERRIDE self.main_agent with a ClaudePMainAgent — a `claude -p --resume`-backed
    drop-in that exposes the SAME method surface (session_exists/send_keys/capture_pane/
    create_session) but drives the subscription `claude` CLI headless, NO tmux.

    We call create_session() on the injected agent so CAVEAgent._ensure_attached()
    (which returns True iff self.main_agent.session_exists()) passes — otherwise it
    would fall back to _attach_to_session() and clobber our injected agent.

Usage:
    agent = PromptWorldAgent(promptworld_dir="/path/to/instance", port=3858)
"""
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from cave.core.cave_agent import CAVEAgent
from cave.core.config import CAVEConfig
from cave.core.models import MainAgentConfig

# p_main_agent.py + convo_registry.py live at the promptworld root (a sibling of this
# package). `python -m server` is run from that root, so the root is on sys.path and
# these import as top-level modules. (This keeps the proven, already-verified -p
# main_agent untouched — we use it, we do not rewrite it.)
from p_main_agent import ClaudePMainAgent
from promptgym import PromptGym, COMPONENT_TYPES

logger = logging.getLogger(__name__)


class PromptWorldAgent(CAVEAgent):
    """PromptWorld v1: an engineer-CEO agent driven by `claude -p` (subscription, no tmux).

    v2 adds the first DEPARTMENT — PROMPTS. A department = a claude-code COMPONENT TYPE,
    and its agent is a component-engineer that COMPILES that type into a real artifact on
    disk. The Prompt department's engineer is just a SECOND named ClaudePMainAgent convo
    (alias "prompt-engineer", same convos.json registry) — NOT a new backend.
    """

    # The canonical claude-code component types = PromptWorld's departments. A department
    # is "implemented" iff PromptWorld can actually compile that type to disk. In v2 only
    # the Prompt department (the atomic component everything else composes from) is built.
    DEPARTMENT_TYPES = [
        "prompt",
        "skill",
        "mcp",
        "harness",
        "operating_system",
        "team",
        "workflow",
    ]
    IMPLEMENTED_DEPARTMENTS = {"prompt"}

    def departments(self) -> Dict[str, Any]:
        """Return the department registry: every component type + whether it's implemented."""
        return {
            "departments": [
                {"type": t, "implemented": t in self.IMPLEMENTED_DEPARTMENTS}
                for t in self.DEPARTMENT_TYPES
            ]
        }

    def __init__(
        self,
        promptworld_dir: str,
        port: int = 3858,
        tmux_session: str = "cave",  # inert — PromptWorld has NO tmux; kept for arg parity
    ):
        self.promptworld_dir = Path(promptworld_dir).resolve()
        self.promptworld_dir.mkdir(parents=True, exist_ok=True)

        # Minimal store — v1 has NO departments/company/tasks. Kept tiny so the
        # dashboard + chat surface work without the health/jobworld domain.
        self.store: Dict[str, Any] = {
            "day": 1,
            "day_started_at": datetime.now().isoformat(),
        }

        self._ws_clients: set = set()
        # The server's asyncio event loop, captured lazily by the /ws endpoint (which
        # runs ON that loop). Needed so broadcasts SCHEDULED from a worker thread (the
        # sync /api/chat route + the ClaudePMainAgent on_event callback, both off-loop)
        # reach the WebSocket clients thread-safely via run_coroutine_threadsafe.
        self._loop = None
        self.last_input_at: float = 0

        config = CAVEConfig(
            port=port,
            main_agent_config=MainAgentConfig(
                agent_id="ceo",
                tmux_session=tmux_session,
                working_dir=str(self.promptworld_dir),
                command="claude",
            ),
        )

        # Build the CAVEAgent god object. This sets self.main_agent via
        # _attach_to_session() (tmux ClaudeCodeAgent or None).
        super().__init__(config=config)

        # === THE CRUX: inject the -p main_agent, replacing the tmux ClaudeCodeAgent ===
        self._convos_path = self.promptworld_dir / ".promptworld" / "convos.json"
        # v2.1: inject the engineer-CEO PERSONA so /api/chat talks AS the CEO (not bare
        # claude). The persona rides the system prompt via --append-system-prompt every
        # turn (ClaudePMainAgent.append_system_prompt) — no conversation-token cost, and
        # the persona persists across --resume. Falls back to bare claude if absent.
        ceo_persona_path = self.promptworld_dir / "agents" / "engineer-ceo.md"
        ceo_persona = ceo_persona_path.read_text() if ceo_persona_path.exists() else ""

        # The PromptGym (the gym OF AGENTS) — one AIOS-directory agent per component type.
        # The CEO does NOT dispatch the gym via an MCP tool: that mechanism (a gym_mcp.py
        # stdio server + a .promptgym_mcp.json given to the CEO via --mcp-config) was the
        # WRONG mechanism and was removed. In MVP1 the CEO controls specialists via
        # claude-code-native teams (invisible); MVP2 uses CAVE injection. The gym is still
        # used by the STANDALONE per-specialist chat path (POST /api/gym/{type} -> run_gym),
        # which the gallery's per-window composer posts to.
        self.gym = PromptGym()

        # SDK-backed + ISOLATED: ClaudePMainAgent defaults to setting_sources=["project"], so the
        # CEO loads ONLY <promptworld_dir>/.claude + the engineer-ceo persona (append_system_prompt)
        # and does NOT inherit the host user-level ~/.claude (its global persona + ~150 skills).
        self.main_agent = ClaudePMainAgent(
            alias="ceo",
            cwd=str(self.promptworld_dir),
            registry_path=str(self._convos_path),
            append_system_prompt=ceo_persona,
        )
        # Ensure a session exists so CAVEAgent._ensure_attached() returns True
        # (it checks self.main_agent.session_exists()) instead of re-attaching to tmux.
        self.main_agent.create_session()

        # === V1 two-halves model (HALF 1): make the CEO able to do everything + reach the
        # specialists by NATIVE claude-code subagent calling (no bridge, no MCP). ===
        self._provision_ceo_aios()

        logger.info(
            "PromptWorldAgent initialized: dir=%s port=%d main_agent=ClaudePMainAgent(alias=ceo) "
            "convos=%s",
            self.promptworld_dir, port, self._convos_path,
        )

    def _provision_ceo_aios(self) -> None:
        """Provision the CEO's PROJECT-level .claude (HALF 1 of Isaac's V1 two-halves model).

        The CEO is ISOLATED from the host (the SDK-backed ClaudePMainAgent defaults to
        setting_sources=["project"]), so it does NOT inherit the host user-level ~/.claude (its
        global persona + ~150 skills). Its build capability + specialists therefore come ENTIRELY
        from what we provision here at PROJECT level (<promptworld_dir>/.claude — loaded because the
        CEO's cwd IS promptworld_dir and the project setting source includes it):

          (1) a NATIVE subagent definition per component type in
              .claude/agents/<type>-specialist.md. Each body = that specialist's identity
              (DERIVED from the committed promptgym/<type>/CLAUDE.md — single source of truth)
              + a HARD constraint to work ONLY in promptgym/<type>/. The CEO reaches a
              specialist by plain native claude-code subagent calling (the Task tool) — NO
              bridge, NO MCP, NO config_dir gymnastics; the dir constraint is JUST A SENTENCE
              in the subagent prompt (per the 2026-06-07T20:43:05 V1 decision).

        The doc-mirror plugin's skills, hooks, and rules are loaded via the SDK `plugins=` option
        in p_main_agent.py's `_build_options` — NOT symlinked here. Symlinking them was redundant
        double-loading; that block was removed when doc-mirror was wired as a real plugin.

        Runtime, idempotent, best-effort (never raises). The whole <promptworld_dir>/.claude is
        gitignored (root .gitignore), so the subagent defs (DERIVED from the CLAUDE.mds) are
        regenerated per environment = the dev-time equivalent of "the promptworld container ships
        the CEO that can do everything".
        """
        claude_dir = self.promptworld_dir / ".claude"
        model = self.main_agent.model if self.main_agent else "sonnet"
        # (1) native specialist subagents, derived from each scoped specialist's CLAUDE.md
        try:
            agents_dst = claude_dir / "agents"
            agents_dst.mkdir(parents=True, exist_ok=True)
            for t in COMPONENT_TYPES:
                src = self.gym.agent_dir(t) / "CLAUDE.md"
                if not src.exists():
                    continue
                identity = src.read_text()
                subagent = (
                    f"---\n"
                    f"name: {t}-specialist\n"
                    f"description: Builds and critiques {t} components for Claude Code. Delegate "
                    f"{t}-component work to it; it works ONLY in promptgym/{t}/.\n"
                    f"tools: Bash, Read, Write, Edit, Glob, Grep\n"
                    f"model: {model}\n"
                    f"---\n"
                    f"(You are the {t}-specialist subagent. Below, \"this directory\" means "
                    f"`promptgym/{t}/` — your ONLY workspace, relative to your working directory.)\n\n"
                    f"{identity}\n\n"
                    f"## DIRECTORY CONSTRAINT (hard)\n"
                    f"You MUST work ONLY inside `promptgym/{t}/`. Never read, write, create, or "
                    f"reference anything outside `promptgym/{t}/`. Every artifact you produce goes there.\n"
                )
                (agents_dst / f"{t}-specialist.md").write_text(subagent)
        except Exception:
            logger.exception("CEO subagent provisioning failed (non-fatal)")

        # (2) PromptWorld-LOCAL skills: symlink each subdir of <promptworld_dir>/skills/ into the
        # CEO's project-level .claude/skills/ so the Archwizard discovers them (e.g. compile-a-world
        # = the *World meta-compiler, wield-the-tome = the SkillTome ops, ingest-into-tome-app =
        # the app-rung). doc-mirror skills come from the plugin (plugins=); THESE are the app's own
        # skills. Idempotent, best-effort.
        try:
            skills_src = self.promptworld_dir / "skills"
            if skills_src.is_dir():
                skills_dst = claude_dir / "skills"
                skills_dst.mkdir(parents=True, exist_ok=True)
                for skill_dir in skills_src.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    link = skills_dst / skill_dir.name
                    if not link.exists() and not link.is_symlink():
                        link.symlink_to(skill_dir.resolve())
        except Exception:
            logger.exception("CEO local-skill provisioning failed (non-fatal)")

    # ========================================
    # BROADCAST (WebSocket for dashboard)
    # ========================================

    def broadcast(self, message: dict):
        """Push a JSON message to all connected /ws clients, from ANY thread.

        Sync routes (/api/chat) and the ClaudePMainAgent on_event callback run in a
        worker thread with NO running event loop, so we schedule the actual sends onto
        the captured server loop via run_coroutine_threadsafe (a bare asyncio.create_task
        here would raise 'no running event loop'). Per-client send is guarded; dead
        sockets are dropped.
        """
        self._broadcast_threadsafe(message)

    def broadcast_event(self, alias: str, ev: dict):
        """Broadcast ONE live agent stream event, tagged with the convo alias so a UI
        client can filter: {"alias": <alias>, "event": <ev>}. Used as the
        ClaudePMainAgent on_event callback during a turn (assistant text, tool_use,
        tool_result, result, compact_boundary stream through here in real time)."""
        self._broadcast_threadsafe({"alias": alias, "event": ev})

    def _broadcast_threadsafe(self, payload: dict):
        import asyncio
        import json

        if not self._ws_clients:
            return
        data = json.dumps(payload, default=str)

        async def _send_all():
            dead = set()
            for ws in list(self._ws_clients):
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.add(ws)
            self._ws_clients -= dead

        loop = self._loop
        if loop is not None and loop.is_running():
            # off-loop (worker thread) → schedule onto the server loop, thread-safely
            try:
                asyncio.run_coroutine_threadsafe(_send_all(), loop)
                return
            except Exception:
                pass
        # fallback: we may already be ON the loop thread
        try:
            asyncio.get_running_loop().create_task(_send_all())
        except RuntimeError:
            pass  # no loop available anywhere — drop (no clients can be reached)

    # ========================================
    # CHAT — one round-trip with the engineer-CEO via claude -p
    # ========================================

    def chat(self, message: str, history_limit: int = 5) -> str:
        """Send one message to the engineer-CEO and return its reply.

        Runs ONE `claude -p --resume` turn via the injected ClaudePMainAgent and returns
        the final assistant text. The turn's LIVE event stream (assistant text, tool_use,
        tool_result, result, compact_boundary) is broadcast to all connected /ws clients
        in real time via on_event=broadcast_event (tagged with alias "ceo") — so a UI can
        watch the CEO think/act. The POST /api/chat contract is unchanged: it still gets
        the final reply string back. (history_limit kept for signature parity; the reply
        is now the turn's final text directly, not a transcript-tail scrape.)
        """
        self.last_input_at = time.time()
        if not self._ensure_attached():
            return "[PromptWorld: main_agent not attached]"
        return self.main_agent.send_and_wait(
            message,
            on_event=lambda ev: self.broadcast_event("ceo", ev),
        )

    # ========================================
    # PROMPT DEPARTMENT — compile a real prompt artifact to disk
    # ========================================

    def _prompt_engineer(self) -> "ClaudePMainAgent":
        """The Prompt department's component-engineer: a SECOND named ClaudePMainAgent
        convo (alias "prompt-engineer") on the SAME convos.json registry as the CEO.

        It is the same backend as the CEO (claude -p, subscription, ANTHROPIC_API_KEY
        scrubbed, no tmux) — just a different named conversation. Cached on first use.
        """
        if getattr(self, "_pe_agent", None) is None:
            self._pe_agent = ClaudePMainAgent(
                alias="prompt-engineer",
                cwd=str(self.promptworld_dir),
                registry_path=str(self._convos_path),
            )
            self._pe_agent.create_session()
        return self._pe_agent

    def compile_prompt(self, request: str, name: str) -> Dict[str, Any]:
        """Compile a real prompt artifact to compiled/prompts/<name>.md.

        Drives the prompt-engineer convo (the PROMPTS department's component-engineer):
        seeds the turn with the prompt-engineer persona, the natural-language request, and
        the EXACT output path, then runs ONE claude -p turn. The engineer authors the
        artifact AND writes the file itself (its claude -p turn has Write/Bash tools under
        bypassPermissions, cwd = the instance dir). Returns {path, reply, ok}.

        ok = the file actually exists on disk after the turn (the real success signal —
        not the engineer's say-so).
        """
        # Resolve the output path (absolute, under the instance dir) and ensure its dir.
        out_dir = self.promptworld_dir / "compiled" / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}.md"

        # Read the prompt-engineer persona and prepend it as the turn's context.
        persona_path = self.promptworld_dir / "agents" / "prompt-engineer.md"
        persona = persona_path.read_text() if persona_path.exists() else ""

        instruction = (
            f"{persona}\n\n"
            "---\n\n"
            "You are now compiling a prompt. Here is the request and the exact output path.\n\n"
            f"REQUEST: {request}\n\n"
            f"OUTPUT PATH (write the compiled prompt artifact here, this exact absolute path): "
            f"{out_path}\n\n"
            "Author the full, self-contained prompt artifact per your COMPILE-PROMPT-TURN CoR, "
            "then WRITE it to that exact path with your Write tool (the file contents must be the "
            "prompt artifact alone — clean Markdown, no preamble, no fence wrapping the whole doc). "
            "After writing, confirm with the path and a one-line summary."
        )

        pe = self._prompt_engineer()
        self.last_input_at = time.time()
        pe.send_keys(instruction)
        pe.send_keys("Enter")  # flush -> runs ONE claude -p turn (engineer writes the file)
        transcript = pe.capture_pane()
        lines = transcript.split("\n")
        reply = lines[-1] if lines else ""

        ok = out_path.exists()
        result = {"path": str(out_path), "reply": reply, "ok": ok}
        self.broadcast({"type": "compile_prompt", "data": {"request": request, "name": name, **result}})
        return result

    # ========================================
    # PROMPTGYM DISPATCH — CEO controls the AIOS-directory specialist agents
    # ========================================

    def run_gym(self, component_type: str, request: str) -> Dict[str, Any]:
        """Dispatch a PromptGym specialist (scoped AIOS agent) and return its reply.

        Runs IN this server process so the specialist's live event stream broadcasts to all
        /ws clients TAGGED by component_type (the gallery — each agent in its own window),
        via on_event=broadcast_event. The reply is returned to the caller (the standalone
        POST /api/gym/{type} route, which the gallery's per-specialist composer posts to).
        gym.run scopes the agent to its AIOS dir.
        """
        self.last_input_at = time.time()
        return self.gym.run(
            component_type,
            request,
            on_event=lambda ev: self.broadcast_event(component_type, ev),
        )
