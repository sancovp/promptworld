#!/usr/bin/env python3
"""
PromptWorld conversation registry — per-agent MULTI-conversation store with a rolling default.

Each agent is addressed by an ALIAS ("ceo", "skill", "prompt-engineer", ...). An alias now owns a
LIST of conversations plus an ACTIVE pointer (V2 convos-first). The active conversation is the one
/api/chat + /api/gym roll forward (auto-resume) — exactly the old behavior — and the UI can browse
past conversations, start a New one, or resume an old one (set_active).

On-disk shape (a single JSON file; default ~/.promptworld/convos.json, survives restarts)::

    {
      "<alias>": {
        "active": "<conv_id>",            # which conversation rolls forward
        "conversations": [
          {"id": "<conv_id>",             # STABLE handle (minted here, never changes)
           "session_id": "<sdk_sid>"|null,# the claude_agent_sdk session_id (filled on the 1st turn)
           "started_at": "<iso>",
           "last_active": "<iso>",
           "title": "<first-user-msg snippet>"|null}
        ]
      }
    }

A conversation's `session_id` is None until its first turn runs (the SDK ASSIGNS the id; we store it
via touch_active). The STABLE handle is `id` (a uuid) — the UI addresses conversations by `id` OR by
`session_id` (set_active accepts either).

BACKWARD COMPAT: the old flat shape ``{"<alias>": "<session_id>"}`` is migrated on read. The legacy
methods (resume / set / new / get_or_create / list) all operate on the ACTIVE conversation, so
ClaudePMainAgent and the existing /api/convos route keep working unchanged.

NO tmux, NO heaven/sdna. Pure stdlib.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now().isoformat()


def _default_registry_path() -> Path:
    base = os.environ.get("PROMPTWORLD_HOME")
    if base:
        return Path(base) / "convos.json"
    return Path.home() / ".promptworld" / "convos.json"


class ConvoRegistry:
    """Persistent per-alias multi-conversation store (active pointer + conversation list)."""

    def __init__(self, path: Optional[os.PathLike | str] = None):
        self.path = Path(path) if path is not None else _default_registry_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    # ---- low-level persistence -------------------------------------------------
    def _read(self) -> Dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text() or "{}")
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        return self._normalize(raw)

    @staticmethod
    def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce any stored value into the {active, conversations:[...]} shape (migrates the old
        flat ``{alias: session_id}`` form, where the value is a bare string)."""
        out: Dict[str, Any] = {}
        for alias, v in (raw or {}).items():
            if isinstance(v, str):  # legacy flat shape: alias -> session_id
                cid = str(uuid.uuid4())
                out[alias] = {
                    "active": cid,
                    "conversations": [
                        {"id": cid, "session_id": v, "started_at": None, "last_active": None, "title": None}
                    ],
                }
            elif isinstance(v, dict) and isinstance(v.get("conversations"), list):
                out[alias] = v
            else:
                out[alias] = {"active": None, "conversations": []}
        return out

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    # ---- internal record helpers ----------------------------------------------
    @staticmethod
    def _rec(data: Dict[str, Any], alias: str, create: bool = False) -> Optional[Dict[str, Any]]:
        rec = data.get(alias)
        if rec is None and create:
            rec = {"active": None, "conversations": []}
            data[alias] = rec
        return rec

    @staticmethod
    def _active_conv(rec: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rec:
            return None
        aid = rec.get("active")
        for c in rec.get("conversations", []):
            if c.get("id") == aid:
                return c
        return None

    def _ensure_active(self, data: Dict[str, Any], alias: str) -> Dict[str, Any]:
        """Guarantee the alias has an active conversation (create conversation #1 if none). Returns
        the active conversation dict. The rolling default: the first ever turn auto-opens a convo."""
        rec = self._rec(data, alias, create=True)
        conv = self._active_conv(rec)
        if conv is None:
            conv = {
                "id": str(uuid.uuid4()),
                "session_id": None,
                "started_at": _now(),
                "last_active": _now(),
                "title": None,
            }
            rec["conversations"].append(conv)
            rec["active"] = conv["id"]
        return conv

    # ---- legacy API (operate on the ACTIVE conversation) ----------------------
    def resume(self, alias: str) -> Optional[str]:
        """The ACTIVE conversation's session_id (None until its first turn assigns one)."""
        conv = self._active_conv(self._rec(self._read(), alias))
        return conv.get("session_id") if conv else None

    def set(self, alias: str, session_id: str) -> None:
        """Bind the ACTIVE conversation's session_id (used when the SDK assigns/rotates the id)."""
        data = self._read()
        conv = self._ensure_active(data, alias)
        conv["session_id"] = session_id
        conv["last_active"] = _now()
        self._write(data)

    def new(self, alias: str) -> str:
        """Legacy alias for new_conversation; returns the new conversation's STABLE id."""
        return self.new_conversation(alias)["id"]

    def get_or_create(self, alias: str) -> Optional[str]:
        """Return the active conversation's session_id, opening conversation #1 if the alias is new
        (the returned id may be None — a fresh convo has no session_id until its first turn)."""
        existing = self.resume(alias)
        if existing is not None:
            return existing
        data = self._read()
        self._ensure_active(data, alias)
        self._write(data)
        return self.resume(alias)

    def list(self) -> Dict[str, Optional[str]]:
        """Legacy: {alias: active_session_id} (what the /api/convos route + the test expect)."""
        data = self._read()
        return {alias: (self._active_conv(rec) or {}).get("session_id") for alias, rec in data.items()}

    # ---- NEW multi-conversation API -------------------------------------------
    def new_conversation(self, alias: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Open a FRESH conversation for the alias and make it active (the old one stays in the
        list, browsable). Its session_id is None until its first turn runs."""
        data = self._read()
        rec = self._rec(data, alias, create=True)
        conv = {
            "id": str(uuid.uuid4()),
            "session_id": None,
            "started_at": _now(),
            "last_active": _now(),
            "title": title,
        }
        rec["conversations"].append(conv)
        rec["active"] = conv["id"]
        self._write(data)
        return conv

    def list_conversations(self, alias: str) -> List[Dict[str, Any]]:
        """All conversations for the alias, NEWEST first, each tagged ``active: bool``."""
        rec = self._rec(self._read(), alias)
        if not rec:
            return []
        active = rec.get("active")
        convs = sorted(
            rec.get("conversations", []),
            key=lambda c: (c.get("last_active") or c.get("started_at") or ""),
            reverse=True,
        )
        return [{**c, "active": c.get("id") == active} for c in convs]

    def set_active(self, alias: str, conv_or_session_id: str) -> Optional[Dict[str, Any]]:
        """Make a conversation active (resume it). Accepts its STABLE id OR its session_id."""
        data = self._read()
        rec = self._rec(data, alias)
        if not rec:
            return None
        for c in rec.get("conversations", []):
            if c.get("id") == conv_or_session_id or c.get("session_id") == conv_or_session_id:
                rec["active"] = c["id"]
                self._write(data)
                return {**c, "active": True}
        return None

    def active_conversation(self, alias: str) -> Optional[Dict[str, Any]]:
        """The active conversation dict (or None)."""
        return self._active_conv(self._rec(self._read(), alias))

    def touch_active(
        self, alias: str, session_id: Optional[str] = None, title_hint: Optional[str] = None
    ) -> None:
        """Per-turn update (called by ClaudePMainAgent): ensure an active conversation, set its
        session_id (if the SDK assigned one), bump last_active, and set its title from the first
        user message if it has none yet."""
        data = self._read()
        conv = self._ensure_active(data, alias)
        if session_id:
            conv["session_id"] = session_id
        conv["last_active"] = _now()
        if title_hint and not conv.get("title"):
            conv["title"] = title_hint.strip()[:80] or None
        self._write(data)

    def rename(self, old_alias: str, new_alias: str) -> None:
        """Rename a convo alias, preserving its conversations."""
        data = self._read()
        if old_alias not in data:
            raise KeyError(f"no convo with alias {old_alias!r}")
        if new_alias in data:
            raise ValueError(f"alias {new_alias!r} already exists")
        data[new_alias] = data.pop(old_alias)
        self._write(data)

    def delete(self, alias: str) -> None:
        data = self._read()
        data.pop(alias, None)
        self._write(data)


__all__ = ["ConvoRegistry"]
