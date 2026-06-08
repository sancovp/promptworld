#!/usr/bin/env python3
"""PromptGym — the gym OF AGENTS: one AIOS-directory-coded agent per component type.

THE DIRECTORY CODES THE AGENT. Each PromptGym agent is a directory under promptgym/<type>/
holding its OWN CLAUDE.md (memory) + .claude/{skills,rules,agents} + its own doc-mirror
(docs/mirror, docs/vision, context/journal). It runs as a claude_agent_sdk agent (the SDK-backed
ClaudePMainAgent) scoped to that dir and ISOLATED from the host, EXACTLY how the CEO is scoped
(server/promptworld_agent.py):
  - `cwd=<dir>`  → the project IS that directory.
  - `setting_sources=["project"]`  → Claude Code loads ONLY the project layer at <dir>
    (`<dir>/CLAUDE.md` as memory + `<dir>/.claude/{skills,rules,agents}`) and EXCLUDES the host
    user-level ~/.claude (its global CLAUDE.md persona + ~150 skills/rules). This is the SDK
    default for every ClaudePMainAgent, so PromptGym does not pass it explicitly.
So the agent IS that AIOS — its character comes from the directory's CLAUDE.md + .claude/, NOT from
any Python persona string and NOT from the host machine's config. [Isolation VERIFIED 2026-06-08:
the same `claude --setting-sources project` subprocess the SDK spawns reports 43 skills (the dir's
doc-mirror set + claude built-ins) vs 185 with the host loaded, and host skills like
`catastrophe-engineering`/`dragonbones-*` are ABSENT.]

OAuth subscription creds (~/.claude/.credentials.json) are AUTH, not a setting source, so they keep
working under setting_sources=["project"] — the same creds the CEO uses.

(WHY NOT CLAUDE_CONFIG_DIR: that env var merely relocates the USER-level ~/.claude wholesale; it is
NOT per-directory isolation and is dropped entirely. The SDK's setting_sources is the real isolator.)

This module is the registry + runner only: it maps a component type to its AIOS dir and runs a
ClaudePMainAgent scoped to it. It does NOT define the agents' behavior (the directories do).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:  # package-relative (application.promptworld.promptgym)
    from .p_main_agent import ClaudePMainAgent
except ImportError:  # script / standalone (run from the promptworld root)
    from p_main_agent import ClaudePMainAgent

# The 7 claude-code component types. Each has an AIOS directory promptgym/<type>/.
COMPONENT_TYPES: List[str] = [
    "skill", "mcp", "harness", "operating_system", "prompt", "team", "workflow",
]

# promptgym/ lives next to this file (application/promptworld/promptgym/).
PROMPTGYM_ROOT = Path(__file__).resolve().parent / "promptgym"

# The shared universal-worker subagent: a generic specialized build hand EVERY gym agent can
# call (a CEO-mirror WITHOUT the CEO's omniscient prompt — option B). ONE canonical definition,
# provisioned (symlinked) into each scoped agent's <config>/agents/ at agent init.
UNIVERSAL_WORKER_SRC = PROMPTGYM_ROOT / "universal-worker.md"



class PromptGym:
    """Registry + runner for the per-type AIOS-directory agents.

    Each agent is lazily built and cached: a ClaudePMainAgent with cwd = promptgym/<type>/
    (and NO CLAUDE_CONFIG_DIR), so claude auto-injects that dir's CLAUDE.md (project memory)
    and its .claude/{skills,rules,agents} — the dir IS the AIOS, exactly like the CEO.
    """

    def __init__(self, root: Optional[os.PathLike | str] = None):
        self.root = Path(root).resolve() if root is not None else PROMPTGYM_ROOT
        self._agents: Dict[str, ClaudePMainAgent] = {}

    # ---- directory mapping -----------------------------------------------------
    def agent_dir(self, ctype: str) -> Path:
        """The AIOS directory for a component type (promptgym/<type>/)."""
        return self.root / ctype

    def types(self) -> List[str]:
        """The component types that actually have an AIOS dir with a CLAUDE.md on disk."""
        return [t for t in COMPONENT_TYPES if (self.agent_dir(t) / "CLAUDE.md").exists()]

    # ---- provisioning ----------------------------------------------------------
    def _provision_aios(self, agent_dir: str) -> None:
        """Provision the universal-worker subagent INTO an AIOS dir's `.claude/agents/`.

        doc-mirror skills, hooks, and rules are now provided by the doc-mirror PLUGIN, loaded via
        the SDK `plugins=` option in `p_main_agent.py` `_build_options`. They arrive namespaced as
        `doc-mirror:<skill>` and do NOT need symlinks here — symlinking them was redundant and
        caused double-loading (bare `doc-mirror-boot` + namespaced `doc-mirror:doc-mirror-boot`).

        This method now ONLY symlinks the shared universal-worker subagent into
        `<dir>/.claude/agents/` so the scoped agent can delegate build work to it (uniform
        capability, no CEO-prompt inheritance — option B).

        Best-effort + idempotent (symlink-if-absent, never raises). The symlink points at THIS
        environment's canonical source, so it is runtime, env-specific setup (gitignored —
        the monorepo root ignores every `.claude/`), regenerated per environment.
        """
        cfg = Path(agent_dir) / ".claude"
        # (2) universal-worker subagent -> <dir>/.claude/agents/universal-worker.md
        try:
            if UNIVERSAL_WORKER_SRC.exists():
                agents_dst = cfg / "agents"
                agents_dst.mkdir(parents=True, exist_ok=True)
                link = agents_dst / "universal-worker.md"
                if not link.exists():
                    try:
                        link.symlink_to(UNIVERSAL_WORKER_SRC)
                    except OSError:
                        import shutil
                        shutil.copy2(UNIVERSAL_WORKER_SRC, link)
        except Exception:
            pass

    # ---- the agents ------------------------------------------------------------
    def agent(self, ctype: str) -> ClaudePMainAgent:
        """Lazily build (and cache) the AIOS agent for a type, scoped + ISOLATED to its directory.

        cwd = the AIOS dir; the SDK-backed ClaudePMainAgent defaults to setting_sources=["project"],
        so claude loads ONLY that dir's CLAUDE.md (project memory) + .claude/{skills,rules,agents}
        (the agent's identity + capabilities) and EXCLUDES the host user-level ~/.claude. (Mirrors
        the CEO; CLAUDE_CONFIG_DIR is gone.) OAuth creds still come from ~/.claude (auth, not a
        setting source). The convo registry is shared (one convos.json under the gym root) keyed by
        the type alias. doc-mirror + the universal-worker subagent are provisioned into the dir's
        .claude/ before first use.
        """
        if ctype not in COMPONENT_TYPES:
            raise ValueError(f"unknown component type: {ctype!r}")
        if ctype not in self._agents:
            d = str(self.agent_dir(ctype))
            self._provision_aios(d)  # universal-worker into <dir>/.claude/agents/ (doc-mirror comes from the plugin)
            self._agents[ctype] = ClaudePMainAgent(
                alias=ctype,
                cwd=d,  # cwd-only scoping: <dir>/CLAUDE.md + <dir>/.claude/ auto-inject (no config_dir)
                registry_path=str(self.root / ".promptgym" / "convos.json"),
            )
            self._agents[ctype].create_session()
        return self._agents[ctype]

    def run(
        self,
        ctype: str,
        request: str,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> Dict[str, object]:
        """Run ONE turn on the type's AIOS agent (scoped to its dir) and return its reply.

        on_event (optional) streams the turn's live events — the server passes
        broadcast_event(ctype, ev) so the gym agent's stream is gallery-ready on /ws,
        tagged with the component type. Returns {reply, type, dir}.
        """
        agent = self.agent(ctype)
        reply = agent.send_and_wait(request, on_event=on_event)
        return {"reply": reply, "type": ctype, "dir": str(self.agent_dir(ctype))}


__all__ = ["PromptGym", "COMPONENT_TYPES", "PROMPTGYM_ROOT"]
