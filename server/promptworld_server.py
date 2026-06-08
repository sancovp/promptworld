"""PromptWorldHTTPServer — CAVEHTTPServer with PromptWorld v1 routes.

Forked from twi-healthworld's HealthworldHTTPServer (the proven-bootable CAVEHTTPServer
extension — CAVE is mid-refactor, so we extend the working subclass, not raw
CAVEHTTPServer). The health/jobworld domain routes are DROPPED (departments, company,
tasks, SOPs, health-import, department-status — v1 has none of that, and those routes
referenced jobworld-only attributes anyway).

What's kept:
  - the dashboard at `/` (serves index.html, the chat panel)
  - a CEO-chat endpoint that drives self.cave.main_agent (the injected ClaudePMainAgent)
    via send_keys/capture_pane — the SAME surface healthworld used for its tmux agent.
  - CORS + the WebSocket keep-alive.

Inherited from CAVEHTTPServer (the base): /health, /exec, /output, /input, /state, etc.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import Body, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from cave.server.cave_http_server import CAVEHTTPServer

from .promptworld_agent import PromptWorldAgent
from . import file_api
from . import group_templates
from . import gym_specs
from . import agent_profiles
from . import promptworld_automations

logger = logging.getLogger(__name__)

# The research instruction the assigned specialist receives on each gym-research turn (the spec's
# title + body are appended). It directs the agent to EMPIRICALLY test the spec via a review subagent,
# determine what is proven or not, and return a markdown research paper.
GYM_RESEARCH_COR = (
    "You are running a GYM RESEARCH turn on a spec. The spec describes something the user wants to "
    "exist, or to know why it can't yet. Your job:\n"
    "(1) make and fire a REVIEW SUBAGENT (use your Task tool / your universal-worker subagent) that "
    "EMPIRICALLY TESTS whether the approach actually works — do not just reason about it, run it;\n"
    "(2) from what the subagent finds, determine what was empirically PROVEN or NOT, and WHY;\n"
    "(3) write your findings as a concise RESEARCH PAPER in markdown — a title line, then findings, "
    "evidence, what's proven/disproven, and the next step.\n"
    "Return ONLY the markdown paper as your reply."
)


class PromptWorldHTTPServer(CAVEHTTPServer):
    """PromptWorld v1 CAVE server — engineer-CEO chat over claude -p."""

    def __init__(self, cave: PromptWorldAgent, port: int = 3858, host: str = "0.0.0.0"):
        super().__init__(cave=cave, port=port, host=host)
        self.pw = cave  # typed reference

        # CORS for dashboard
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._register_promptworld_routes()
        self._register_file_routes()
        self._register_group_template_routes()
        self._register_gym_routes()
        self._register_agent_profile_routes()
        self._register_automation_routes()
        self._register_conversation_routes()
        self._register_websocket()
        self._register_terminal_ws()
        self._mount_frontend()

    def _agent_for_alias(self, alias: str):
        """Resolve the ClaudePMainAgent backing a chat alias, for its registry (conversations) + cwd
        (transcript). 'ceo' -> the injected main_agent; a gym component type -> the scoped gym agent
        (built+cached on demand). Returns None for an unknown alias."""
        pw = self.pw
        if alias == "ceo":
            return pw.main_agent
        try:
            if alias in pw.gym.types():
                return pw.gym.agent(alias)
        except Exception:
            return None
        return None

    def _register_conversation_routes(self):
        """Per-agent MULTI-conversation management (V2 convos-first). Each alias owns a list of
        conversations + an active pointer; the active one is what /api/chat + /api/gym roll forward.
        These routes let the UI browse past conversations, start a New one, resume an old one, and
        load a conversation's transcript. The rolling-default chat behavior is unchanged."""
        pw = self.pw  # noqa: F841 (kept for parity/readability)

        @self.app.get("/api/conversations/{alias}")
        def conversations_list(alias: str):
            ag = self._agent_for_alias(alias)
            if ag is None:
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            return {"alias": alias, "conversations": ag.registry.list_conversations(alias)}

        @self.app.post("/api/conversations/{alias}/new")
        def conversations_new(alias: str):
            ag = self._agent_for_alias(alias)
            if ag is None:
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            conv = ag.registry.new_conversation(alias)
            return {"alias": alias, "conversation": {**conv, "active": True}}

        @self.app.post("/api/conversations/{alias}/active")
        def conversations_set_active(alias: str, data: Dict[str, Any]):
            handle = data.get("session_id") or data.get("id")
            if not handle:
                raise HTTPException(status_code=400, detail="'session_id' (or 'id') is required")
            ag = self._agent_for_alias(alias)
            if ag is None:
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            conv = ag.registry.set_active(alias, handle)
            if conv is None:
                raise HTTPException(status_code=404, detail=f"no conversation {handle!r} for {alias}")
            return {"alias": alias, "active": conv}

        @self.app.get("/api/conversations/{alias}/{session_id}")
        def conversations_transcript(alias: str, session_id: str):
            ag = self._agent_for_alias(alias)
            if ag is None:
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            return {"alias": alias, "session_id": session_id, "messages": ag.get_transcript(session_id)}

    def _register_file_routes(self):
        """Workspace file API for the Monaco explorer — every op PATH-JAILED to the
        workspace root (file_api.jail_resolve). PROMPTWORLD_WORKSPACE > ceo agent cwd >
        instance dir. A successful write broadcasts {"type":"file_changed","path"} on /ws.
        """
        pw = self.pw
        root = file_api.resolve_workspace_root(pw)
        self._workspace_root = root
        logger.info("PromptWorld workspace root (file API jail): %s", root)

        @self.app.get("/api/files/tree")
        def files_tree():
            return file_api.build_tree(self._workspace_root)

        @self.app.get("/api/files/read")
        def files_read(path: str = Query(...)):
            try:
                return file_api.read_file(self._workspace_root, path)
            except file_api.PathJailError as e:
                raise HTTPException(status_code=403, detail=str(e))
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"not found: {path}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.put("/api/files/write")
        def files_write(data: Dict[str, Any]):
            path = data.get("path")
            content = data.get("content", "")
            if not path:
                raise HTTPException(status_code=400, detail="'path' is required")
            try:
                result = file_api.write_file(self._workspace_root, path, content)
            except file_api.PathJailError as e:
                raise HTTPException(status_code=403, detail=str(e))
            except (OSError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e))
            # notify all /ws clients so the explorer (and any UI) refreshes
            pw.broadcast({"type": "file_changed", "path": result["path"]})
            return result

        @self.app.post("/api/files/mkdir")
        def files_mkdir(data: Dict[str, Any]):
            path = data.get("path")
            if not path:
                raise HTTPException(status_code=400, detail="'path' is required")
            try:
                result = file_api.make_dir(self._workspace_root, path)
            except file_api.PathJailError as e:
                raise HTTPException(status_code=403, detail=str(e))
            except OSError as e:
                raise HTTPException(status_code=400, detail=str(e))
            pw.broadcast({"type": "file_changed", "path": result["path"]})
            return result

        @self.app.post("/api/files/rename")
        def files_rename(data: Dict[str, Any]):
            src = data.get("from")
            dst = data.get("to")
            if not src or not dst:
                raise HTTPException(status_code=400, detail="'from' and 'to' are required")
            try:
                result = file_api.rename_path(self._workspace_root, src, dst)
            except file_api.PathJailError as e:
                raise HTTPException(status_code=403, detail=str(e))
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"not found: {src}")
            except FileExistsError:
                raise HTTPException(status_code=409, detail=f"already exists: {dst}")
            except OSError as e:
                raise HTTPException(status_code=400, detail=str(e))
            pw.broadcast({"type": "file_changed", "path": result["to"]})
            return result

        @self.app.delete("/api/files/delete")
        def files_delete(path: str = Query(...)):
            try:
                result = file_api.delete_path(self._workspace_root, path)
            except file_api.PathJailError as e:
                raise HTTPException(status_code=403, detail=str(e))
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"not found: {path}")
            except OSError as e:
                raise HTTPException(status_code=400, detail=str(e))
            pw.broadcast({"type": "file_changed", "path": result["path"]})
            return result

    def _register_group_template_routes(self):
        """GROUP-page named templates (order/color/label of a side-by-side agent set),
        persisted server-side as JSON via group_templates (writable: $PROMPTWORLD_DATA or
        ~/.promptworld). This is the MAXIMUM persistence option (survives restart), vs the
        localStorage minimum."""

        @self.app.get("/api/group-templates")
        def group_templates_list():
            return {"templates": group_templates.list_templates(group_templates.templates_path())}

        @self.app.put("/api/group-templates")
        def group_templates_save(data: Dict[str, Any]):
            name = (data.get("name") or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="'name' is required")
            try:
                return group_templates.save_template(
                    group_templates.templates_path(), name, data.get("agents", [])
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/api/group-templates")
        def group_templates_delete(name: str = Query(...)):
            ok = group_templates.delete_template(group_templates.templates_path(), name)
            return {"deleted": ok, "name": name}

    def _register_gym_routes(self):
        """GYM MODULE specs (the new additive layer): write SPECS, track each spec's STATUS,
        record OBSERVATIONS/measurements, and launch RESEARCH-RUNS (dispatch a specialist via the
        existing pw.run_gym / pw.chat and RECORD the run + a reply excerpt onto the spec). Persisted
        server-side as JSON via gym_specs (writable: $PROMPTWORLD_DATA or ~/.promptworld), exactly
        like the group-template / profile stores. DISTINCT from the PromptGym agent registry."""

        @self.app.get("/api/gym-specs")
        def gym_specs_list(status: str = Query(None), owner: str = Query(None)):
            return {"specs": gym_specs.list_specs(gym_specs.specs_path(), status=status, owner=owner)}

        @self.app.post("/api/gym-specs")
        def gym_specs_create(data: Dict[str, Any]):
            owner_alias = (data.get("owner_alias") or "").strip()
            if owner_alias not in self._known_aliases():
                raise HTTPException(status_code=400, detail=f"unknown owner alias: {owner_alias}")
            assigned_agent = (data.get("assigned_agent") or "").strip() or None
            if assigned_agent is not None and assigned_agent not in self._known_aliases():
                raise HTTPException(status_code=400, detail=f"unknown assigned agent: {assigned_agent}")
            try:
                return gym_specs.create_spec(
                    gym_specs.specs_path(),
                    data.get("title", ""),
                    data.get("body", ""),
                    owner_alias,
                    assigned_agent=assigned_agent,
                    schedule=data.get("schedule"),
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/api/gym-specs/{spec_id}")
        def gym_specs_get(spec_id: str):
            spec = gym_specs.get_spec(gym_specs.specs_path(), spec_id)
            if spec is None:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            return spec

        @self.app.put("/api/gym-specs/{spec_id}")
        def gym_specs_update(spec_id: str, data: Dict[str, Any]):
            assigned_agent = data.get("assigned_agent")
            if assigned_agent is not None:
                assigned_agent = assigned_agent.strip()
                if assigned_agent not in self._known_aliases():
                    raise HTTPException(status_code=400, detail=f"unknown assigned agent: {assigned_agent}")
            try:
                return gym_specs.update_spec(
                    gym_specs.specs_path(),
                    spec_id,
                    status=data.get("status"),
                    body=data.get("body"),
                    title=data.get("title"),
                    assigned_agent=assigned_agent,
                    schedule=data.get("schedule"),
                )
            except KeyError:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/api/gym-specs/{spec_id}/observe")
        def gym_specs_observe(spec_id: str, data: Dict[str, Any]):
            try:
                return gym_specs.add_observation(
                    gym_specs.specs_path(), spec_id, data.get("text", ""), metric=data.get("metric")
                )
            except KeyError:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/api/gym-specs/{spec_id}/run")
        def gym_specs_run(spec_id: str, data: Dict[str, Any]):
            spec = gym_specs.get_spec(gym_specs.specs_path(), spec_id)
            if spec is None:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            alias = (data.get("alias") or "").strip()
            if alias not in self._known_aliases():
                raise HTTPException(status_code=400, detail=f"unknown agent alias: {alias}")
            request = (data.get("request") or "").strip()
            if not request:
                raise HTTPException(status_code=400, detail="'request' is required")
            # dispatch the specialist: CEO -> pw.chat (returns the reply string); a gym type ->
            # pw.run_gym (returns {"reply","type","dir"}). The Gym just RECORDS the run + excerpt.
            if alias == "ceo":
                reply = self.pw.chat(request)
            else:
                result = self.pw.run_gym(alias, request)
                reply = result.get("reply")
            excerpt = (reply or "")[:500]
            updated = gym_specs.add_run_record(
                gym_specs.specs_path(), spec_id, alias, request, excerpt
            )
            return {"spec": updated, "reply": reply}

        @self.app.post("/api/gym-specs/{spec_id}/research")
        def gym_specs_research(spec_id: str, data: Dict[str, Any] = Body(default={})):
            """Run ONE research turn on a spec (this is what the cron fires; also callable directly).
            Dispatches the spec's assigned agent against GYM_RESEARCH_COR + the stored spec, records
            the reply as a research PAPER + an observation, and returns the updated spec. The request
            body is accepted but ignored — the prompt is built from the stored spec, so the cron's
            POST body is harmless. The 'team' craft cannot be auto-researched (a team must be run by
            the researcher, not fired as a subagent), so a team-assigned spec is skipped."""
            path = gym_specs.specs_path()
            spec = gym_specs.get_spec(path, spec_id)
            if spec is None:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            agent = spec.get("assigned_agent") or spec.get("owner_alias")
            if agent == "team":
                spec = gym_specs.add_observation(
                    path, spec_id,
                    text="research skipped: team craft cannot be auto-researched "
                         "(a team must be run by the researcher)",
                )
                return {
                    "spec": spec,
                    "skipped": "team craft cannot be auto-researched (a team must be run by the researcher)",
                }
            prompt = GYM_RESEARCH_COR + "\n\n## SPEC: " + spec["title"] + "\n\n" + spec.get("body", "")
            if agent == "ceo":
                reply = self.pw.chat(prompt)
            else:
                reply = self.pw.run_gym(agent, prompt).get("reply")
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            gym_specs.add_paper(
                path, spec_id, title=f"{spec['title']} — research {stamp}", body=reply or ""
            )
            updated = gym_specs.add_observation(
                path, spec_id, text=f"research run by {agent} (paper added)"
            )
            return {"spec": updated, "paper_added": True}

        @self.app.post("/api/gym-specs/{spec_id}/schedule")
        def gym_specs_schedule(spec_id: str, data: Dict[str, Any] = Body(default={})):
            """Start the research loop: persist a CAVE schedule onto the spec, mark it active, and
            register a CronAutomation that fires .../research at the spec's assigned agent on that
            schedule. A team-assigned spec cannot be scheduled (a team must be run by the researcher)."""
            path = gym_specs.specs_path()
            spec = gym_specs.get_spec(path, spec_id)
            if spec is None:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            agent = spec.get("assigned_agent") or spec.get("owner_alias")
            if agent == "team":
                raise HTTPException(
                    status_code=400,
                    detail="team-assigned specs cannot be scheduled (a team must be run by the researcher)",
                )
            schedule = (data.get("schedule") or "every:3600").strip() or "every:3600"
            spec = gym_specs.update_spec(path, spec_id, status="active", schedule=schedule)
            url = f"http://127.0.0.1:{self.port}/api/gym-specs/{spec_id}/research"
            sd = promptworld_automations.schema_dict(
                name=f"gym-{spec_id}",
                prompt=spec["title"],
                alias=agent,
                loopback_url=url,
                schedule=schedule,
                description=f"Gym research loop for {spec['title']}",
            )
            automation = promptworld_automations.register_automation(self.pw.automation_registry, sd)
            return {"spec": spec, "automation": automation}

        @self.app.post("/api/gym-specs/{spec_id}/schedule/stop")
        def gym_specs_schedule_stop(spec_id: str):
            """Stop the research loop: remove the spec's CronAutomation and clear its schedule."""
            path = gym_specs.specs_path()
            if gym_specs.get_spec(path, spec_id) is None:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            promptworld_automations.remove_automation(self.pw.automation_registry, f"gym-{spec_id}")
            spec = gym_specs.update_spec(path, spec_id, schedule="")
            return {"spec": spec, "stopped": True}

        @self.app.post("/api/gym-specs/{spec_id}/papers")
        def gym_specs_add_paper(spec_id: str, data: Dict[str, Any]):
            try:
                return gym_specs.add_paper(
                    gym_specs.specs_path(), spec_id, data.get("title", ""), data.get("body", "")
                )
            except KeyError:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.put("/api/gym-specs/{spec_id}/papers/{paper_id}")
        def gym_specs_update_paper(spec_id: str, paper_id: str, data: Dict[str, Any]):
            try:
                return gym_specs.update_paper(
                    gym_specs.specs_path(),
                    spec_id,
                    paper_id,
                    title=data.get("title"),
                    body=data.get("body"),
                    published=data.get("published"),
                )
            except KeyError:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}' or paper '{paper_id}'")

        @self.app.post("/api/gym-specs/{spec_id}/publish")
        def gym_specs_publish(spec_id: str, data: Dict[str, Any] = Body(default={})):
            try:
                return gym_specs.set_published(
                    gym_specs.specs_path(), spec_id, bool(data.get("published", True))
                )
            except KeyError:
                raise HTTPException(status_code=404, detail=f"no spec '{spec_id}'")

    def _loopback_url(self, alias: str) -> str:
        """The PromptWorld HTTP endpoint a cron fires a turn at (loopback). CEO → /api/chat,
        a gym specialist → /api/gym/{alias}."""
        base = f"http://127.0.0.1:{self.port}"
        return f"{base}/api/chat" if alias == "ceo" else f"{base}/api/gym/{alias}"

    def _register_automation_routes(self):
        """CRONS + CEO-HEARTBEAT (V2 (f)) — a THIN layer over CAVE's REAL automation engine. PromptWorld
        is a CAVEAgent, so `pw.automation_registry` is already loaded and CAVEAgent's Heart already runs
        a 60s tick firing due CronAutomations. These routes only manage that registry (list/create/toggle/
        fire/delete) + the per-agent heartbeat (a CronAutomation that fires a turn at the agent on an
        interval). NOTHING here re-implements scheduling. Default schedule = interval ("every:N"), which
        needs no croniter; a raw cron expression works only if croniter is installed in the image."""
        pw = self.pw
        registry = getattr(pw, "automation_registry", None)

        def _reg():
            if registry is None:
                raise HTTPException(status_code=503, detail="automation engine not available")
            return registry

        @self.app.get("/api/automations")
        def automations_list():
            return {"automations": promptworld_automations.list_automations(_reg())}

        @self.app.get("/api/automations/view")
        def automations_view(days: int = 7):
            return {"days": days, "events": promptworld_automations.view(_reg(), days)}

        @self.app.post("/api/automations")
        def automations_create(data: Dict[str, Any]):
            name = (data.get("name") or "").strip()
            if not name or not name.replace("_", "").replace("-", "").isalnum():
                raise HTTPException(status_code=400, detail="'name' required (alnum/_/- only)")
            alias = (data.get("alias") or "ceo").strip()
            if alias not in self._known_aliases():
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            prompt = (data.get("prompt") or "").strip()
            if not prompt:
                raise HTTPException(status_code=400, detail="'prompt' required")
            sd = promptworld_automations.schema_dict(
                name,
                prompt=prompt,
                alias=alias,
                loopback_url=self._loopback_url(alias),
                schedule=data.get("schedule"),
                interval_seconds=data.get("interval_seconds"),
                description=data.get("description", ""),
                enabled=bool(data.get("enabled", True)),
            )
            return {"automation": promptworld_automations.register_automation(_reg(), sd)}

        @self.app.post("/api/automations/{name}/enable")
        def automations_enable(name: str):
            r = promptworld_automations.set_enabled(_reg(), name, True)
            if r is None:
                raise HTTPException(status_code=404, detail=f"no automation '{name}'")
            return {"automation": r}

        @self.app.post("/api/automations/{name}/disable")
        def automations_disable(name: str):
            r = promptworld_automations.set_enabled(_reg(), name, False)
            if r is None:
                raise HTTPException(status_code=404, detail=f"no automation '{name}'")
            return {"automation": r}

        @self.app.post("/api/automations/{name}/fire")
        def automations_fire(name: str):
            r = promptworld_automations.fire_now(_reg(), name)
            if r is None:
                raise HTTPException(status_code=404, detail=f"no automation '{name}'")
            return {"fired": r}

        @self.app.delete("/api/automations/{name}")
        def automations_delete(name: str):
            ok = promptworld_automations.remove_automation(_reg(), name)
            return {"deleted": ok, "name": name}

        # --- CEO (per-agent) HEARTBEAT = a CronAutomation named heartbeat_{alias} ---
        def _hb_name(alias: str) -> str:
            return f"heartbeat_{alias}"

        @self.app.get("/api/heartbeat/{alias}")
        def heartbeat_get(alias: str):
            if alias not in self._known_aliases():
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            auto = promptworld_automations.get_automation(_reg(), _hb_name(alias))
            if auto is None:
                return {"alias": alias, "enabled": False, "interval_seconds": 300,
                        "prompt": "Heartbeat: review your workspace and report status."}
            sched = auto.get("schedule") or "every:300"
            interval = int(sched.split(":", 1)[1]) if sched.startswith("every:") else 300
            return {"alias": alias, "enabled": auto["enabled"], "interval_seconds": interval,
                    "prompt": auto.get("prompt") or ""}

        @self.app.put("/api/heartbeat/{alias}")
        def heartbeat_put(alias: str, data: Dict[str, Any]):
            if alias not in self._known_aliases():
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            enabled = bool(data.get("enabled", False))
            interval = data.get("interval_seconds", 300)
            prompt = (data.get("prompt") or "Heartbeat: review your workspace and report status.").strip()
            sd = promptworld_automations.schema_dict(
                _hb_name(alias),
                prompt=prompt,
                alias=alias,
                loopback_url=self._loopback_url(alias),
                interval_seconds=interval,
                description=f"CEO/agent heartbeat for '{alias}'",
                enabled=enabled,
            )
            promptworld_automations.register_automation(_reg(), sd)
            return heartbeat_get(alias)

    def _known_aliases(self) -> set:
        """The valid agent aliases (CEO + the gym component types) — used to jail profile writes
        so an arbitrary alias can't create a stray avatar file."""
        aliases = {"ceo"}
        try:
            aliases |= set(self.pw.gym.types())
        except Exception:
            pass
        return aliases

    def _register_agent_profile_routes(self):
        """Per-agent PROFILE (V2 (a)(b)): customizable display name + avatar image, keyed by
        alias, persisted via agent_profiles ($PROMPTWORLD_DATA / ~/.promptworld). The avatar is
        uploaded as a base64 data URL in the PUT body (no multipart dep), saved as a real file,
        and served by GET .../avatar. The prompt is NOT here (V2 (c): edit CLAUDE.md in Monaco)."""
        ppath = agent_profiles.profiles_path()
        adir = agent_profiles.avatars_dir()
        # #48 specialization: persona NAME + AVATAR defaults live in a HOT-RELOADING JSON config
        # (promptgym/agent_personas.json) + bundled emblems (promptgym/avatars/), NOT baked into code.
        # The config is read LIVE on each request, so editing it takes effect with no restart; a user's
        # own profile (set via the editor) always overrides it.
        personas_json = self.pw.promptworld_dir / "promptgym" / "agent_personas.json"
        bundled_avatars = self.pw.promptworld_dir / "promptgym" / "avatars"

        def _persona(alias: str) -> Dict[str, str]:
            return agent_profiles.load_personas(personas_json).get(alias, {})

        def _bundled_avatar(alias: str):
            """The bundled persona emblem file for an alias (from the live config), or None."""
            fname = _persona(alias).get("avatar")
            if not fname:
                return None
            # jail to the bundled dir (filename only — no path escape)
            p = (bundled_avatars / Path(fname).name)
            return p if p.exists() else None

        def _public(alias: str) -> Dict[str, Any]:
            """Stored profile -> client shape. Display name + avatar fall back to the live persona
            config when the user hasn't set their own (user override always wins)."""
            prof = agent_profiles.get_profile(ppath, alias)
            name = prof["display_name"] or (_persona(alias).get("name") or None)
            af = agent_profiles.avatar_file(adir, alias)          # user-uploaded avatar (wins)
            avatar = None
            if af is not None:
                try:
                    mtime = int(af.stat().st_mtime)
                except OSError:
                    mtime = 0
                avatar = f"/api/agents/{alias}/avatar?v={mtime}"
            elif _bundled_avatar(alias) is not None:               # else the live persona emblem
                avatar = f"/api/agents/{alias}/avatar"
            return {"alias": alias, "display_name": name, "avatar": avatar}

        @self.app.get("/api/agents/{alias}/profile")
        def agent_profile_get(alias: str):
            if alias not in self._known_aliases():
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            return _public(alias)

        @self.app.put("/api/agents/{alias}/profile")
        def agent_profile_put(alias: str, data: Dict[str, Any]):
            if alias not in self._known_aliases():
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            try:
                if "display_name" in data:
                    agent_profiles.set_profile(ppath, alias, display_name=data.get("display_name"))
                if "avatar" in data:
                    av = data.get("avatar")
                    if av:  # a data: URL -> decode + save the image file
                        agent_profiles.save_avatar(adir, ppath, alias, av)
                    else:  # null / "" -> clear the avatar
                        agent_profiles.clear_avatar(adir, ppath, alias)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            return _public(alias)

        @self.app.get("/api/agents/{alias}/avatar")
        def agent_avatar_get(alias: str):
            if alias not in self._known_aliases():
                raise HTTPException(status_code=404, detail=f"unknown agent alias: {alias}")
            af = agent_profiles.avatar_file(adir, alias)   # user-uploaded avatar wins
            if af is None:
                af = _bundled_avatar(alias)                # else the live persona emblem (config)
            if af is None:
                raise HTTPException(status_code=404, detail="no avatar")
            return FileResponse(str(af))

    def _mount_frontend(self):
        """Serve the built assistant-ui frontend (frontend/dist) if present.

        The built SPA is served at "/" (replacing the legacy single-box index.html);
        its hashed JS/CSS live under dist/assets and are mounted at "/assets" (vite
        base="./" → the index references ./assets/* which resolves to /assets/* when
        served at root). /api/* and /ws are explicit routes and are unaffected. If the
        frontend hasn't been built, "/" falls back to the legacy index.html (handled in
        serve_dashboard), so the server still boots without a build step.
        """
        dist = self.pw.promptworld_dir / "frontend" / "dist"
        assets = dist / "assets"
        if assets.is_dir():
            self.app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
            logger.info("PromptWorld frontend mounted: /assets -> %s", assets)
        else:
            logger.info("PromptWorld frontend not built (no %s); serving legacy index.html", assets)
        # Self-hosted Monaco editor (min/vs copied into dist/monaco by `npm run build`). Serving it
        # same-origin at /monaco/vs means the editor loads with NO CDN dependency — so it renders
        # even when the browser/container cannot reach jsdelivr. monacoSetup.ts points the loader here.
        monaco = dist / "monaco"
        if monaco.is_dir():
            self.app.mount("/monaco", StaticFiles(directory=str(monaco)), name="monaco")
            logger.info("PromptWorld Monaco self-hosted: /monaco -> %s", monaco)
        else:
            logger.info("PromptWorld Monaco dir not built (no %s); editor will 404 its loader", monaco)

    def _register_websocket(self):
        pw = self.pw

        @self.app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            # Capture the running server event loop so broadcasts scheduled from worker
            # threads (the sync /api/chat route + the agent on_event callback) can reach
            # ws clients via run_coroutine_threadsafe. This endpoint runs ON that loop.
            import asyncio
            try:
                pw._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            pw._ws_clients.add(ws)
            try:
                while True:
                    await ws.receive_text()  # keep alive
            except WebSocketDisconnect:
                pw._ws_clients.discard(ws)
            except Exception:
                pw._ws_clients.discard(ws)

    def _register_terminal_ws(self):
        """A REAL terminal over WebSocket — the universal LOGIN surface.

        /ws/terminal spawns a PTY running interactive `bash` as THIS process's user (the server
        runs as the non-root `ceo` user in the container), so a user can open the terminal in the
        SPA and run `claude auth login` — the OAuth flow stores creds in /home/ceo/.claude where
        `claude -p` (the CEO + specialists) read them. No creds copying; works on every machine.

        Bytes flow both ways: PTY master is registered non-blocking on the event loop
        (loop.add_reader) → an asyncio.Queue → ws.send_text (ordered); browser keystrokes →
        os.write(master). A JSON control frame {"type":"resize","cols","rows"} resizes the PTY.
        """
        import asyncio
        import fcntl
        import json as _json
        import os
        import pty
        import struct
        import subprocess
        import termios

        @self.app.websocket("/ws/terminal")
        async def terminal_ws(ws: WebSocket):
            await ws.accept()
            master_fd, slave_fd = pty.openpty()
            env = dict(os.environ)
            env["TERM"] = "xterm-256color"
            env.setdefault("HOME", "/home/ceo")
            home = env.get("HOME", "/")
            try:
                proc = subprocess.Popen(
                    ["/bin/bash", "-il"],
                    stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                    preexec_fn=os.setsid, env=env, cwd=home, close_fds=True,
                )
            except Exception as e:  # noqa: BLE001
                try:
                    await ws.send_text(f"[terminal: failed to start shell: {e}]\r\n")
                    await ws.close()
                finally:
                    os.close(master_fd)
                    os.close(slave_fd)
                return
            os.close(slave_fd)

            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            loop = asyncio.get_running_loop()
            out_q: asyncio.Queue = asyncio.Queue()

            def _on_readable():
                try:
                    data = os.read(master_fd, 65536)
                except (BlockingIOError, InterruptedError):
                    return
                except OSError:
                    data = b""
                out_q.put_nowait(data if data else None)  # b"" / EOF -> None sentinel

            loop.add_reader(master_fd, _on_readable)

            async def _sender():
                while True:
                    data = await out_q.get()
                    if data is None:
                        break
                    try:
                        await ws.send_text(data.decode("utf-8", "replace"))
                    except Exception:  # noqa: BLE001
                        break

            send_task = asyncio.create_task(_sender())
            try:
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        break
                    if msg.get("type") != "websocket.receive":
                        continue
                    txt = msg.get("text")
                    if txt is not None:
                        # control frame: {"type":"resize","cols":N,"rows":M}
                        if txt.startswith("{") and '"type"' in txt:
                            try:
                                obj = _json.loads(txt)
                                if obj.get("type") == "resize":
                                    winsz = struct.pack(
                                        "HHHH", int(obj.get("rows", 24)), int(obj.get("cols", 80)), 0, 0
                                    )
                                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsz)
                                    continue
                            except Exception:  # noqa: BLE001
                                pass
                        os.write(master_fd, txt.encode("utf-8"))
                    elif msg.get("bytes") is not None:
                        os.write(master_fd, msg["bytes"])
            except WebSocketDisconnect:
                pass
            except Exception:  # noqa: BLE001
                pass
            finally:
                try:
                    loop.remove_reader(master_fd)
                except Exception:  # noqa: BLE001
                    pass
                out_q.put_nowait(None)
                send_task.cancel()
                try:
                    proc.terminate()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    os.close(master_fd)
                except Exception:  # noqa: BLE001
                    pass

    def _register_promptworld_routes(self):
        pw = self.pw

        # === Dashboard === prefer the built assistant-ui SPA; fall back to legacy box.
        @self.app.get("/")
        def serve_dashboard():
            built = pw.promptworld_dir / "frontend" / "dist" / "index.html"
            if built.exists():
                return FileResponse(str(built))
            index = pw.promptworld_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"error": "No index.html found", "dir": str(pw.promptworld_dir)}

        # === PromptWorld health (richer than base /health) ===
        @self.app.get("/api/health")
        def api_health():
            return {
                "status": "ok",
                "type": "promptworld",
                "dir": str(pw.promptworld_dir),
                "main_agent": pw.main_agent.__class__.__name__ if pw.main_agent else None,
                "ceo_session": pw.main_agent.session_id if pw.main_agent else None,
            }

        # === Config ===
        @self.app.get("/api/config")
        def api_config():
            return {"promptworldDir": str(pw.promptworld_dir), "serverPort": self.port}

        # === CEO CHAT — the round-trip the dashboard posts to ===
        # POST /api/chat  {"message": "..."}  ->  {"reply": "<engineer-CEO reply>"}
        # Drives the injected ClaudePMainAgent (claude -p) via send_keys/capture_pane,
        # exactly as healthworld drove its tmux main_agent.
        @self.app.post("/api/chat")
        def ceo_chat(data: Dict[str, Any]):
            message = data.get("message", "")
            if not message:
                return {"error": "message required"}
            reply = pw.chat(message)
            pw.broadcast({"type": "chat", "data": {"message": message, "reply": reply}})
            return {
                "reply": reply,
                "alias": "ceo",
                "session_id": pw.main_agent.session_id if pw.main_agent else None,
            }

        # === Convo registry inspection ===
        @self.app.get("/api/convos")
        def list_convos():
            return pw.main_agent.registry.list() if pw.main_agent else {}

        # === Department registry ===
        # GET /api/departments -> {"departments": [{"type": ..., "implemented": bool}, ...]}
        @self.app.get("/api/departments")
        def list_departments():
            return pw.departments()

        # === PROMPT department — compile a real prompt artifact to disk ===
        # POST /api/department/prompt  {"request": "...", "name": "..."}
        #   -> {"path": "<abs compiled/prompts/<name>.md>", "reply": "<engineer reply>", "ok": <file exists>}
        # Drives the prompt-engineer convo (a second ClaudePMainAgent alias); the engineer
        # authors AND writes the artifact itself via its claude -p Write tool.
        @self.app.post("/api/department/prompt")
        def compile_prompt(data: Dict[str, Any]):
            request = data.get("request", "")
            name = data.get("name", "")
            if not request or not name:
                return {"error": "both 'request' and 'name' are required", "ok": False}
            return pw.compile_prompt(request, name)

        # === PROMPTGYM STANDALONE DISPATCH — the gallery's per-specialist composer POSTs here ===
        # POST /api/gym/{ctype}  {"request": "..."}  ->  {"reply","type","dir"}
        # Runs the scoped AIOS specialist IN-PROCESS so its live event stream broadcasts to
        # /ws TAGGED by component type (the gallery window for that type). Returns its reply.
        # (Standalone chat with one specialist; the CEO does NOT call this via an MCP tool —
        # CEO-controls-gym is claude-code-native teams in MVP1 / CAVE injection in MVP2.)
        @self.app.post("/api/gym/{ctype}")
        def run_gym(ctype: str, data: Dict[str, Any]):
            request = data.get("request", "")
            if not request:
                raise HTTPException(status_code=400, detail="'request' is required")
            if ctype not in pw.gym.types():
                raise HTTPException(status_code=404, detail=f"unknown gym component type: {ctype}")
            return pw.run_gym(ctype, request)
