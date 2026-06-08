#!/usr/bin/env python3
"""
ClaudePMainAgent — a **claude_agent_sdk**-backed main_agent (drop-in for CAVE's tmux CodeAgent).

This is the CEO/`*Gym` chat substrate. It was previously a hand-rolled `claude -p` subprocess
(build argv → pipe stdin → parse NDJSON → scrub env); it is now built on the official Python
**claude_agent_sdk** (`query` + `ClaudeAgentOptions`), which reifies exactly that machinery and —
critically — gives first-class **agent isolation** via `setting_sources`.

It satisfies the SAME method surface the server + PromptGym depend on (CAVE's CodeAgent surface):

    session_exists() -> bool
    create_session() / spawn_agent() -> bool
    send_keys(*sequence) -> bool        # str = prompt chunk; "Enter" = flush => run a turn; float ignored
    capture_pane(history_limit=5000) -> str
    send_and_wait(prompt, timeout=None, on_event=None) -> str   # SYNC, returns final assistant text
    compact() -> bool

Turn semantics (unchanged): `send_keys` ACCUMULATES a pending prompt and `"Enter"` FLUSHES it as ONE
turn. A flush with an empty buffer is a harmless no-op.

ISOLATION (the point of the SDK migration): every agent runs with
    ClaudeAgentOptions(cwd=<dir>, setting_sources=["project"], permission_mode="bypassPermissions",
                       system_prompt={"type":"preset","preset":"claude_code","append":<context>}, ...)
`setting_sources=["project"]` makes Claude Code load ONLY the project layer at `<cwd>` (its
`.claude/{skills,rules,agents}` + `CLAUDE.md`) and EXCLUDE the host user-level `~/.claude` (its
global CLAUDE.md persona + ~150 skills/rules). [VERIFIED 2026-06-08 via the exact `claude
--setting-sources project` subprocess the SDK spawns: skill count 185 → 43, host skills like
`catastrophe-engineering`/`dragonbones-*` ABSENT.] This REPLACES the old CLAUDE_CONFIG_DIR scoping,
which is dropped entirely. (Auth is the MiniMax provider token, NOT a setting source, so it is
unaffected by `setting_sources=["project"]`.)

PROVIDER (IS): the agents run on **MiniMax-M3**, not Anthropic. Every turn's SDK options set
`env={ANTHROPIC_BASE_URL: https://api.minimax.io/anthropic, ANTHROPIC_AUTH_TOKEN: <MiniMax key>}` and
`model="Minimax-M3[1m]"` (the `[1m]` suffix enables 1M-context compaction). [VERIFIED 2026-06-08: a
real turn returns is_error=False with modelUsage=={'Minimax-M3[1m]'} — it executed on MiniMax.] See
the PROVIDER block + `_provider_env()`. ANTHROPIC_API_KEY (x-api-key) is scrubbed so only the Bearer
token authenticates. If no MiniMax token is configured the turn falls back to os.environ (never breaks).

STREAMING (IS): each SDK message (AssistantMessage/UserMessage/ResultMessage/SystemMessage) is mapped
to the SAME `{type, message, ...}` event dict the old `claude -p --output-format stream-json` emitted,
and handed to the live `on_event(ev: dict)` callback — so the server's `broadcast_event(alias, ev)` →
`/ws` gallery streaming is UNCHANGED (the frontend `reduceEvent` consumes assistant/user/result
verbatim). We do NOT enable `include_partial_messages`: the frontend reducer ACCUMULATES text, so
emitting partial deltas AND the final message would double-count — message-granularity matches the
old behavior exactly.

ASYNC→SYNC bridge: the SDK is async (`async for msg in query(...)`); the surface is sync and is called
from FastAPI worker threads (sync routes run in a threadpool, no running loop), so each turn runs via
`asyncio.run` (a fresh loop per turn). The `on_event` callback is sync (it schedules a broadcast onto
the server loop via run_coroutine_threadsafe), so firing it from inside the turn's loop is safe.

Persistence: ConvoRegistry maps alias <-> the SDK-assigned session_id; a turn passes `resume=<id>` so a
FRESH ClaudePMainAgent(alias=...) continues the same conversation. The first turn for an alias runs with
no resume (the SDK mints the id, which we store); a stale/foreign resume id (e.g. a pre-migration `claude
-p` UUID) is handled by a one-shot fresh retry.

HARD CONSTRAINTS honored: runs on the MiniMax provider (ANTHROPIC_API_KEY/x-api-key scrubbed; Bearer
token only); NO tmux; a lean, ISOLATED context (no host `~/.claude`).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Callable, List, Optional

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
)

try:  # package-relative import (when used as application.promptworld.p_main_agent)
    from .convo_registry import ConvoRegistry
except ImportError:  # script / standalone import
    from convo_registry import ConvoRegistry


# Scrub ANTHROPIC_API_KEY (the x-api-key path) once, process-wide: the agent authenticates to the
# MiniMax provider via ANTHROPIC_AUTH_TOKEN (Bearer) — having BOTH a custom base URL and an x-api-key
# set is ambiguous, so we remove x-api-key and use only the Bearer token. (The SDK builds its
# subprocess env as {**os.environ, **options.env}, so an env var can only be REMOVED by popping.)
os.environ.pop("ANTHROPIC_API_KEY", None)

# === PROVIDER: MiniMax-M3 (Anthropic-compatible endpoint) =====================================
# PromptWorld's Claude Code agents run on **MiniMax-M3**, not Anthropic. Claude Code reaches it via
# the standard custom-provider env (the same endpoint heaven/cave-teams use, api.minimax.io):
#   ANTHROPIC_BASE_URL   = https://api.minimax.io/anthropic   (Anthropic-compatible gateway)
#   ANTHROPIC_AUTH_TOKEN = <the MiniMax key>                  (Bearer; = MINIMAX_API_KEY)
#   model = "Minimax-M3[1m]"   (the [1m] suffix turns on 1M-context compaction automatically)
# [VERIFIED 2026-06-08 via the exact `claude --model Minimax-M3[1m]` subprocess the SDK spawns with
# these env vars: the result event reports is_error=False and modelUsage=={'Minimax-M3[1m]'} — i.e.
# the turn actually executed on MiniMax-M3, not Anthropic.]
MINIMAX_ANTHROPIC_BASE_URL = "https://api.minimax.io/anthropic"

# Default model: Isaac's env name is DEFAULT_CLAUDE_CODE_MODEL; fall back to PROMPTWORLD_MODEL, then
# the MiniMax 1M-context model. (Passed as ClaudeAgentOptions.model → `--model` on every turn.)
DEFAULT_MODEL = (
    os.environ.get("DEFAULT_CLAUDE_CODE_MODEL")
    or os.environ.get("PROMPTWORLD_MODEL")
    or "Minimax-M3[1m]"
)


def _provider_env() -> dict:
    """The env that points a claude turn at the MiniMax provider (merged into the SDK subprocess
    env). Token = ANTHROPIC_AUTH_TOKEN (explicit) or MINIMAX_API_KEY; base URL = ANTHROPIC_BASE_URL
    (explicit) or the MiniMax default. Returns {} if NO token is configured — then the turn uses
    whatever os.environ already provides (e.g. an OAuth subscription), so the agent never hard-breaks
    when MiniMax creds are absent."""
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("MINIMAX_API_KEY")
    if not token:
        return {}
    base = os.environ.get("ANTHROPIC_BASE_URL") or MINIMAX_ANTHROPIC_BASE_URL
    return {"ANTHROPIC_BASE_URL": base, "ANTHROPIC_AUTH_TOKEN": token}


def transcript_from_jsonl(path: Path) -> List[dict]:
    """Parse a claude/SDK session .jsonl into assistant-ui ThreadMessageLike messages (for loading a
    PAST conversation into the chat window when the user resumes/browses it).

    Each jsonl line is an event: {type:"user"|"assistant", message:{role, content}, ...}. We build
    one bubble per user text message + one per assistant message, and MERGE a later tool_result (in a
    "user" event) back onto the matching assistant tool-call — the SAME reduction the frontend's
    eventMapping.ts does on the live /ws stream, so resumed history renders identically. Content parts
    use the frontend's AssistantPart shape: {type:"text",text} / {type:"reasoning",text} /
    {type:"tool-call",toolCallId,toolName,args,result?,isError?}."""
    messages: List[dict] = []
    tool_calls_by_id: dict = {}  # toolCallId -> the tool-call part (to merge results onto)

    def _norm_tool_result(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                b.get("text", "") if isinstance(b, dict) and b.get("type") == "text" else json.dumps(b)
                for b in content
            )
        return json.dumps(content) if content is not None else ""

    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        etype = ev.get("type")
        msg = ev.get("message") or {}
        content = msg.get("content")

        if etype == "user":
            # plain text user input -> a user bubble; tool_result-only user events merge onto a call
            if isinstance(content, str):
                if content.strip():
                    messages.append({"role": "user", "content": [{"type": "text", "text": content}]})
            elif isinstance(content, list):
                text_parts = []
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and isinstance(b.get("text"), str):
                        text_parts.append(b["text"])
                    elif b.get("type") == "tool_result":
                        tc = tool_calls_by_id.get(str(b.get("tool_use_id") or ""))
                        if tc is not None:
                            tc["result"] = _norm_tool_result(b.get("content"))
                            if b.get("is_error"):
                                tc["isError"] = True
                joined = "".join(text_parts).strip()
                if joined:
                    messages.append({"role": "user", "content": [{"type": "text", "text": joined}]})

        elif etype == "assistant":
            parts: List[dict] = []
            for b in (content if isinstance(content, list) else []):
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text" and isinstance(b.get("text"), str):
                    parts.append({"type": "text", "text": b["text"]})
                elif bt == "thinking" and isinstance(b.get("thinking"), str):
                    parts.append({"type": "reasoning", "text": b["thinking"]})
                elif bt == "tool_use":
                    part = {
                        "type": "tool-call",
                        "toolCallId": str(b.get("id") or ""),
                        "toolName": str(b.get("name") or ""),
                        "args": b.get("input"),
                    }
                    tool_calls_by_id[part["toolCallId"]] = part
                    parts.append(part)
            if parts:
                messages.append({"role": "assistant", "content": parts})

    return messages


def _doc_mirror_plugin_root() -> Optional[Path]:
    """Locate the doc-mirror plugin root (env-correct).

    Primary: ~/.docmirror_plugin_root, the file install.sh writes with the plugin's path on THIS
    host/container. Fallback: the monorepo source, derived RELATIVE to this file (portable across
    environments — no hard-coded absolute path). Returns None if neither has a skills/ dir. This is
    the canonical discovery; promptgym.py delegates to it (DRY)."""
    marker = Path.home() / ".docmirror_plugin_root"
    try:
        if marker.exists():
            p = Path(marker.read_text().strip())
            if (p / "skills").is_dir():
                return p
    except Exception:
        pass
    # THIS file = <monorepo>/application/promptworld/p_main_agent.py → parents[2] = <monorepo>.
    fallback = Path(__file__).resolve().parents[2] / "doc-mirror-system" / "plugin"
    return fallback if (fallback / "skills").is_dir() else None


# The ONE shared context EVERY PromptWorld agent gets, appended to the claude_code system-prompt
# preset (system_prompt={"type":"preset","preset":"claude_code","append":...}). Per-agent IDENTITY
# (the dir's CLAUDE.md) + CAPABILITIES (the dir's .claude/) load from the project setting source;
# THIS block is the single thing that is universal across the CEO + every specialist.
PROMPTWORLD_CONTEXT_BLOCK = """\
# PromptWorld — shared agent context

You are an agent inside **PromptWorld**. THE DIRECTORY CODES THE AGENT: your identity, skills, and
rules come from the `CLAUDE.md` and `.claude/` of the directory you are running in — and you are
ISOLATED from any host/global configuration (you do NOT have the host machine's persona or skills).

Operate ONLY within your own working directory: every file you read, create, or write stays inside
it. You build real Claude-Code component artifacts (skills, MCPs, prompts, hooks, teams, …) on disk,
and you keep your OWN per-directory doc-mirror (`docs/`, `context/`) as you work. Be concrete and
produce the actual artifact, not chatter.
"""


def _run_coro(coro):
    """Run an async coroutine to completion from a SYNC context.

    Called from FastAPI worker threads (sync routes run in a threadpool with NO running loop), so a
    fresh `asyncio.run` loop per turn is correct and safe.
    """
    return asyncio.run(coro)


class ClaudePMainAgent:
    """A claude_agent_sdk-backed main_agent (drop-in for CAVE's tmux CodeAgent surface)."""

    def __init__(
        self,
        alias: str,
        *,
        registry: Optional[ConvoRegistry] = None,
        registry_path: Optional[str] = None,
        cwd: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        settings_dir: Optional[str] = None,
        max_wait_seconds: float = 300.0,
        on_event: Optional[Callable[[dict], None]] = None,
        append_system_prompt: Optional[str] = None,
        setting_sources: Optional[List[str]] = ("project",),
        plugins: Optional[List[str]] = None,
    ):
        self.alias = alias
        self.registry = registry or ConvoRegistry(registry_path)
        self.cwd = cwd or os.getcwd()
        self.model = model
        # An explicit settings.json file to also load (rarely used). None => none.
        self.settings_dir = settings_dir
        self.max_wait_seconds = max_wait_seconds
        # ISOLATION: which Claude-Code setting layers load. ["project"] = ONLY <cwd>/.claude +
        # <cwd>/CLAUDE.md; the host user-level ~/.claude (its persona + skills/rules) is EXCLUDED.
        # This is the SDK's isolation mechanism and REPLACES the old CLAUDE_CONFIG_DIR scoping.
        # None => SDK default (loads user+project+local = NOT isolated; only for explicit opt-out).
        self.setting_sources = list(setting_sources) if setting_sources else None
        # Optional PERSONA: text appended to the claude_code system-prompt preset on EVERY turn
        # (rides the system prompt, not the message history). The CEO passes its engineer-ceo
        # persona here; specialists pass None (identity comes from their dir's CLAUDE.md). It is
        # always appended AFTER PROMPTWORLD_CONTEXT_BLOCK.
        self.append_system_prompt = append_system_prompt
        # Local plugin DIR paths to load as real Claude Code plugins (SDK --plugin-dir). None =>
        # auto-load the doc-mirror plugin (the base) so its skills/hooks/rules auto-inject; pass an
        # explicit list to override/extend.
        self.plugins = plugins
        # default per-instance live-event callback (a per-call override can be passed to
        # send_and_wait). Invoked once per converted SDK message, in real time.
        self.on_event = on_event

        # pending prompt buffer (accumulated by send_keys, flushed by "Enter")
        self._pending: List[str] = []
        # the rendered transcript of this convo (what capture_pane returns)
        self._transcript: List[str] = []
        # an alias is "created" once create_session() ran OR a session_id exists in the registry —
        # this is what session_exists() reports (so CAVEAgent._ensure_attached passes).
        self._created: bool = False
        # set True by the turn loop whenever a system/compact_boundary event streams by.
        self._compacted_in_last_turn: bool = False

    # ------------------------------------------------------------------ session
    @property
    def session_id(self) -> Optional[str]:
        """The current SDK session_id for this alias (None until the first turn assigns one)."""
        return self.registry.resume(self.alias)

    def session_exists(self) -> bool:
        """True once this alias is created OR already has a session_id in the registry."""
        return self._created or (self.registry.resume(self.alias) is not None)

    def create_session(self) -> bool:
        """Mark this alias active. The SDK assigns the real session_id on the first turn (which we
        store in the registry); create_session does not mint one (no preset-id under the SDK)."""
        self._created = True
        return True

    # alias for CAVE's CodeAgent.spawn_agent()
    def spawn_agent(self) -> bool:
        return self.create_session()

    # --------------------------------------------------------------- key-driving
    def send_keys(self, *sequence) -> bool:
        """Mirror CodeAgent.send_keys.

        - a str that is NOT "Enter": a prompt chunk, appended to the pending buffer.
        - "Enter": flush the pending buffer as ONE turn (empty => no-op).
        - an int/float: a tmux sleep; meaningless headless => ignored.
        """
        for item in sequence:
            if isinstance(item, (int, float)):
                continue  # tmux sleep — no-op headless
            if not isinstance(item, str):
                continue
            if item == "Enter":
                self._flush()
            else:
                self._pending.append(item)
        return True

    def _flush(self, on_event: Optional[Callable[[dict], None]] = None) -> Optional[str]:
        """Run one turn from the accumulated pending buffer (no-op if empty)."""
        prompt = "\n".join(self._pending).strip()
        self._pending.clear()
        if not prompt:
            return None
        return self._run_turn(prompt, on_event=on_event)

    # --------------------------------------------------------------- options
    def _system_append(self) -> str:
        """The text appended to the claude_code system-prompt preset: the shared PromptWorld block,
        then (for the CEO) its persona. Specialists get the block only — their identity is their
        dir's CLAUDE.md loaded via the project setting source."""
        block = PROMPTWORLD_CONTEXT_BLOCK
        if self.append_system_prompt:
            return block + "\n\n---\n\n" + self.append_system_prompt
        return block

    def _build_options(self, resume_id: Optional[str]) -> ClaudeAgentOptions:
        kwargs = dict(
            cwd=self.cwd,
            system_prompt={"type": "preset", "preset": "claude_code", "append": self._system_append()},
            permission_mode="bypassPermissions",
            model=self.model,
            include_partial_messages=False,  # message-granularity (see module docstring)
            # PROVIDER: point the turn at MiniMax-M3 (ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN).
            # The SDK merges this over os.environ for the subprocess; {} if no MiniMax token => the
            # turn falls back to whatever os.environ provides (never hard-breaks). See _provider_env.
            env=_provider_env(),
        )
        if self.setting_sources is not None:
            kwargs["setting_sources"] = self.setting_sources
        if resume_id:
            kwargs["resume"] = resume_id
        if self.settings_dir:
            kwargs["settings"] = self.settings_dir
        # PLUGINS: explicit list if given, else auto-discover the doc-mirror plugin (the base). Each
        # existing dir becomes {"type":"local","path":<dir>} → the SDK launches claude with
        # --plugin-dir <dir>, auto-loading its skills/hooks/rules. Skip non-existent dirs so it never
        # hard-breaks (e.g. the doc-mirror root not found => empty => no plugins key set).
        plugin_dirs = self.plugins if self.plugins is not None else [
            d for d in (_doc_mirror_plugin_root(),) if d
        ]
        plugin_cfgs = [
            {"type": "local", "path": str(p)} for p in plugin_dirs if Path(p).is_dir()
        ]
        if plugin_cfgs:
            kwargs["plugins"] = plugin_cfgs
        return ClaudeAgentOptions(**kwargs)

    # --------------------------------------------- SDK message -> /ws event dict
    @staticmethod
    def _event_from_message(msg) -> tuple[Optional[dict], str]:
        """Map ONE SDK message to the {type, message, ...} dict shape the FRONTEND consumes
        (eventMapping.ts reduceEvent: assistant/user/result), identical to the old `claude -p
        --output-format stream-json` events — so /ws streaming is unchanged. Returns (ev|None, kind).
        """
        if isinstance(msg, AssistantMessage):
            content = []
            for b in (msg.content or []):
                if isinstance(b, TextBlock):
                    content.append({"type": "text", "text": b.text})
                elif isinstance(b, ThinkingBlock):
                    content.append({"type": "thinking", "thinking": b.thinking})
                elif isinstance(b, ToolUseBlock):
                    content.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
            return {"type": "assistant", "message": {"content": content}}, "assistant"
        if isinstance(msg, UserMessage):
            content = []
            for b in (msg.content or []):
                if isinstance(b, ToolResultBlock):
                    item = {"type": "tool_result", "tool_use_id": b.tool_use_id, "content": b.content}
                    if b.is_error:
                        item["is_error"] = True
                    content.append(item)
            return {"type": "user", "message": {"content": content}}, "user"
        if isinstance(msg, ResultMessage):
            return (
                {
                    "type": "result",
                    "subtype": msg.subtype,
                    "result": msg.result,
                    "session_id": msg.session_id,
                    "is_error": msg.is_error,
                },
                "result",
            )
        if isinstance(msg, SystemMessage):
            data = msg.data if isinstance(msg.data, dict) else {}
            return {"type": "system", "subtype": msg.subtype, **data}, "system"
        # StreamEvent (only if include_partial_messages, which we keep off) — not forwarded.
        return None, "other"

    async def _aturn(
        self, prompt: str, resume_id: Optional[str], cb: Optional[Callable[[dict], None]]
    ) -> tuple[str, Optional[str]]:
        """Run ONE SDK turn: stream messages, convert+fire on_event live, return (final_text, sid)."""
        final_text: Optional[str] = None
        last_assistant: Optional[str] = None
        live_sid: Optional[str] = resume_id
        async for msg in query(prompt=prompt, options=self._build_options(resume_id)):
            ev, kind = self._event_from_message(msg)
            if ev is None:
                continue
            if ev.get("session_id"):
                live_sid = ev["session_id"]
            # fire the live callback — guarded so it can never kill the turn
            if cb is not None:
                try:
                    cb(ev)
                except Exception:
                    pass
            if kind == "result":
                final_text = ev.get("result")
            elif kind == "assistant":
                parts = [b.get("text", "") for b in ev["message"]["content"] if b.get("type") == "text"]
                joined = "".join(parts).strip()
                if joined:
                    last_assistant = joined
            elif kind == "system" and ev.get("subtype") == "compact_boundary":
                self._compacted_in_last_turn = True
        text = final_text if final_text is not None else (last_assistant or "")
        if not text:
            text = "[ClaudePMainAgent(SDK): empty output]"
        return text, live_sid

    def _run_turn(self, prompt: str, on_event: Optional[Callable[[dict], None]] = None) -> str:
        """Run ONE SDK turn synchronously (bridges the async SDK), streaming events live via on_event.

        Resume continuity: pass the registry's session_id for this alias (None on the first turn → the
        SDK mints one, which we then store). A stale/foreign resume id (e.g. a pre-migration `claude
        -p` UUID) is recovered by a one-shot fresh retry. The transcript + registry update mirror the
        old contract; the return value is the final assistant text.
        """
        cb = on_event if on_event is not None else self.on_event
        self._compacted_in_last_turn = False
        resume_id = self.registry.resume(self.alias)

        async def _guarded(rid: Optional[str]):
            return await asyncio.wait_for(self._aturn(prompt, rid, cb), self.max_wait_seconds)

        try:
            text, live_sid = _run_coro(_guarded(resume_id))
        except asyncio.TimeoutError:
            text, live_sid = (
                f"[ClaudePMainAgent(SDK): turn exceeded max_wait_seconds={self.max_wait_seconds}, killed]",
                None,
            )
        except Exception as e:  # noqa: BLE001 — surface a diagnostic instead of crashing the route
            if resume_id:
                # the resume id may be stale/foreign (pre-migration) → retry ONCE as a fresh session
                try:
                    text, live_sid = _run_coro(_guarded(None))
                except asyncio.TimeoutError:
                    text, live_sid = (
                        f"[ClaudePMainAgent(SDK): turn exceeded max_wait_seconds={self.max_wait_seconds}, killed]",
                        None,
                    )
                except Exception as e2:  # noqa: BLE001
                    text, live_sid = f"[ClaudePMainAgent(SDK): turn failed: {e2}]", None
            else:
                text, live_sid = f"[ClaudePMainAgent(SDK): turn failed: {e}]", None

        # Update the ACTIVE conversation: store the (possibly new) SDK session id so a fresh
        # instance resumes by alias, bump last_active, and set its title from the first user
        # message. touch_active also auto-opens conversation #1 if the alias is brand new (the
        # rolling default). We touch on every turn so last_active/title stay current.
        self.registry.touch_active(self.alias, session_id=live_sid, title_hint=prompt)
        self._created = True
        # render into the transcript (what capture_pane returns)
        self._transcript.append(f"> {prompt}")
        self._transcript.append(text)
        return text

    # ---------------------------------------------------------------- read pane
    def capture_pane(self, history_limit: int = 5000) -> str:
        """Return the rendered conversation transcript as text (tmux capture-pane parity)."""
        lines = self._transcript[-history_limit:] if history_limit else self._transcript
        return "\n".join(lines)

    # ---------------------------------------------------- session store / transcript
    def _session_store_dir(self) -> Path:
        """Where claude/the SDK keep this cwd's session transcripts.

        Layout: <config_dir>/projects/<cwd-slug>/<session_id>.jsonl, where cwd-slug is the absolute
        cwd with every non-alphanumeric char replaced by '-'. config_dir = CLAUDE_CONFIG_DIR or
        ~/.claude (we do NOT relocate it — isolation is via setting_sources, not config_dir)."""
        config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
        abs_cwd = str(Path(self.cwd).resolve())
        slug = "".join(c if c.isalnum() else "-" for c in abs_cwd)
        return Path(config_dir) / "projects" / slug

    def get_transcript(self, session_id: str) -> List[dict]:
        """Load a past conversation's transcript as assistant-ui ThreadMessageLike messages
        (role + content parts) by parsing the claude/SDK session .jsonl. Empty list if the session
        has no on-disk transcript yet (e.g. a fresh New conversation before its first turn)."""
        if not session_id:
            return []
        path = self._session_store_dir() / f"{session_id}.jsonl"
        if not path.exists():
            return []
        return transcript_from_jsonl(path)

    # -------------------------------------------------------------- convenience
    def send_and_wait(
        self,
        prompt: str,
        timeout: Optional[float] = None,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """Send a prompt, run the turn, return the final assistant text (synchronous).

        `on_event` (optional) overrides `self.on_event` for THIS turn only; events still stream live
        during the turn. The return contract (final assistant text) + timeout-override are unchanged.
        """
        if timeout is not None:
            old = self.max_wait_seconds
            self.max_wait_seconds = timeout
            try:
                self.send_keys(prompt)
                return self._flush(on_event=on_event) or ""
            finally:
                self.max_wait_seconds = old
        self.send_keys(prompt)
        return self._flush(on_event=on_event) or ""

    # ------------------------------------------------------------------- compact
    def compact(self) -> bool:
        """Send the literal turn `/compact` through the normal turn path.

        Returns True iff a system/compact_boundary event was observed streaming by during that turn.
        """
        self._run_turn("/compact")
        return self._compacted_in_last_turn


__all__ = ["ClaudePMainAgent", "ConvoRegistry", "PROMPTWORLD_CONTEXT_BLOCK"]
