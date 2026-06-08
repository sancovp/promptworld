"""promptworld_automations — the THIN PromptWorld layer over CAVE's REAL automation engine.

PromptWorld does NOT have its own cron/heartbeat engine. Its agent is a CAVEAgent subclass, so
`pw.automation_registry` (an `AutomationRegistry`) is already loaded at boot and CAVEAgent's Heart
already runs a 60s `cron_scheduler` tick → `fire_due_automations()` (cave/core/cave_agent.py). This
module is ONLY:

  1. a CODE-POINTER bridge (`fire_agent_turn`) that a CronAutomation fires to RUN AN AGENT TURN — it
     POSTs to PromptWorld's own loopback `/api/chat` (CEO) or `/api/gym/{alias}` (a specialist). It
     dispatches on a daemon thread so the Heart tick NEVER blocks on a multi-second model turn (the
     conductor heartbeat avoids blocking by writing to a file inbox; we avoid it by fire-and-forget).
     This mirrors `cave/core/mixins/heartbeat_cron.conductor_heartbeat_fire` — same idea, PromptWorld
     delivery surface.

  2. small helpers to BUILD / LIST / TOGGLE / REMOVE automations through CAVE's real
     `AutomationRegistry` + `Automation.create()` factory (the exact path `Calendar` uses) — WITHOUT
     going through `Calendar.schedule`, because that validates the schedule with `croniter` (absent in
     the image) and only accepts 5-field cron expressions. PromptWorld defaults to INTERVAL schedules
     (`"every:<seconds>"`), which CAVE's SDNA `CronJob.is_due()` handles with NO extra dependency.

Schedule format reused from CAVE/SDNA:
  - interval: ``"every:300"`` (fires every 300s) — the default, no croniter needed.
  - cron expr: ``"0 3 * * *"`` — ONLY fires if `croniter` is installed (else `is_due()` returns False).
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- code-pointer bridge
def fire_agent_turn(
    url: Optional[str] = None,
    prompt: str = "",
    alias: str = "ceo",
    name: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """CronAutomation code-pointer: run ONE real agent turn by POSTing to PromptWorld's own HTTP
    surface (loopback). Dispatched on a daemon thread so the Heart tick returns immediately and is
    never blocked by a multi-second MiniMax turn. Returns a 'dispatched' marker synchronously.

    code_args supply: url (the loopback endpoint, e.g. http://127.0.0.1:3858/api/chat), prompt,
    alias, name. The route bakes `url` in at create time so this pointer needs no global state.
    """
    if not url or not prompt:
        return {"status": "error", "error": "fire_agent_turn requires url + prompt in code_args"}

    def _post() -> None:
        try:
            # send BOTH keys so one pointer serves CEO /api/chat ("message") AND
            # gym /api/gym/{alias} ("request") uniformly
            body = json.dumps({"message": prompt, "request": prompt}).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 (loopback only)
                resp.read()
            logger.info("PromptWorld automation '%s' fired a turn for '%s' via %s", name, alias, url)
        except Exception as e:  # noqa: BLE001
            logger.error("PromptWorld automation '%s' turn failed (%s): %s", name, alias, e)

    threading.Thread(target=_post, daemon=True).start()
    return {"status": "dispatched", "name": name, "alias": alias, "url": url}


# --------------------------------------------------------------------------- registry helpers
def _normalize_schedule(schedule: Optional[str], interval_seconds: Optional[int]) -> str:
    """Produce a CAVE/SDNA schedule string. Prefer an explicit `schedule`; else build an interval
    `"every:<seconds>"` (the no-croniter-needed default). Falls back to every:900."""
    if schedule and str(schedule).strip():
        return str(schedule).strip()
    try:
        secs = int(interval_seconds) if interval_seconds is not None else 900
    except (TypeError, ValueError):
        secs = 900
    secs = max(10, secs)
    return f"every:{secs}"


def schema_dict(
    name: str,
    *,
    prompt: str,
    alias: str,
    loopback_url: str,
    schedule: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    description: str = "",
    enabled: bool = True,
) -> Dict[str, Any]:
    """Build the AutomationSchema dict for a PromptWorld agent-turn cron (fires `prompt` at the
    target agent on the schedule, via the loopback bridge code-pointer)."""
    sched = _normalize_schedule(schedule, interval_seconds)
    return {
        "name": name,
        "description": description or f"Run a turn for '{alias}' on {sched}",
        "schedule": sched,
        "code_pointer": "server.promptworld_automations.fire_agent_turn",
        "code_args": {"url": loopback_url, "prompt": prompt, "alias": alias, "name": name},
        "enabled": enabled,
        "tags": ["promptworld", f"agent:{alias}"],
    }


def register_automation(registry: Any, schema_dict_: Dict[str, Any]) -> Dict[str, Any]:
    """Create a live CronAutomation from a schema dict via CAVE's `Automation.create()` factory and
    register + persist it in the REAL registry (the same path Calendar uses, minus croniter)."""
    from cave.core.automation import Automation, AutomationSchema

    schema = AutomationSchema.from_dict(schema_dict_)
    auto = Automation.create(schema=schema)  # interval → CronAutomation; no croniter needed
    registry.register(auto)
    registry.save_schema(schema)
    return _describe(auto)


def _describe(auto: Any) -> Dict[str, Any]:
    s = auto.schema
    return {
        "name": s.name,
        "description": s.description,
        "schedule": s.schedule,
        "enabled": bool(s.enabled),
        "alias": (s.code_args or {}).get("alias"),
        "prompt": (s.code_args or {}).get("prompt"),
        "type": type(auto).__name__,
        "run_count": getattr(auto, "run_count", 0),
        "last_run": auto.last_run.isoformat() if getattr(auto, "last_run", None) else None,
    }


def list_automations(registry: Any) -> List[Dict[str, Any]]:
    """All registered automations, newest-schedule-agnostic, described for the UI."""
    return [_describe(a) for a in registry.automations.values()]


def get_automation(registry: Any, name: str) -> Optional[Dict[str, Any]]:
    auto = registry.get(name)
    return _describe(auto) if auto else None


def set_enabled(registry: Any, name: str, enabled: bool) -> Optional[Dict[str, Any]]:
    """Enable/disable an automation. Flips schema.enabled, persists, and REBUILDS the live instance
    (the SDNA CronJob copies `enabled` at build time, so a rebuild is needed for is_due() to see it).
    """
    auto = registry.get(name)
    if not auto:
        return None
    auto.schema.enabled = bool(enabled)
    registry.save_schema(auto.schema)
    # rebuild the live instance so its CronJob picks up the new enabled flag
    from cave.core.automation import Automation
    fresh = Automation.create(schema=auto.schema)
    registry.register(fresh)
    return _describe(fresh)


def remove_automation(registry: Any, name: str) -> bool:
    """Unregister + delete the persisted schema JSON."""
    removed = registry.unregister(name)
    try:
        json_path = registry._dir / f"{name}.json"
        if json_path.exists():
            json_path.unlink()
    except Exception:  # noqa: BLE001
        pass
    return bool(removed)


def view(registry: Any, days: int = 7, now: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Upcoming fire times over the next `days`, across ALL enabled automations — handling BOTH
    interval ("every:N", computed from last_run/now) AND 5-field cron expressions (via croniter, if
    installed; else cron-expr automations are skipped). Returns [{time, name, schedule}] sorted by time.
    (Calendar.view only covers cron-exprs; this also covers PromptWorld's interval default.)"""
    from datetime import datetime, timedelta

    base = now or datetime.now()
    end = base + timedelta(days=max(1, int(days)))
    events: List[Dict[str, Any]] = []
    try:
        from croniter import croniter as _croniter
    except ImportError:
        _croniter = None

    for auto in registry.automations.values():
        s = auto.schema
        if not s.enabled or not s.schedule:
            continue
        sched = s.schedule
        if sched.startswith("every:"):
            try:
                secs = int(sched.split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            t = (auto.last_run or base) + timedelta(seconds=secs)
            while t <= end:
                if t >= base:
                    events.append({"time": t.isoformat(), "name": s.name, "schedule": sched})
                t = t + timedelta(seconds=secs)
        elif _croniter is not None:
            try:
                it = _croniter(sched, base)
                while True:
                    nxt = it.get_next(datetime)
                    if nxt > end:
                        break
                    events.append({"time": nxt.isoformat(), "name": s.name, "schedule": sched})
            except Exception:  # noqa: BLE001
                continue
    events.sort(key=lambda e: e["time"])
    return events[:200]


def fire_now(registry: Any, name: str) -> Optional[Dict[str, Any]]:
    """Fire an automation immediately (the deterministic 'it actually fires' surface for the UI/E2E),
    bypassing the schedule. Returns the fire result dict."""
    auto = registry.get(name)
    if not auto:
        return None
    return auto.fire()


__all__ = [
    "fire_agent_turn",
    "schema_dict",
    "register_automation",
    "list_automations",
    "get_automation",
    "set_enabled",
    "remove_automation",
    "fire_now",
    "view",
]
