"""agent_profiles — server-side persistence for per-agent PROFILE (display name + avatar).

PromptWorld V2 (a)(b): every agent (CEO + the 7 PromptGym specialists, addressed by ALIAS)
gets a customizable DISPLAY NAME and an AVATAR image (shown as a circle in every chat-window
header + the specialist selector). This module persists those per-alias, so they survive a
server restart (within the same writable volume).

The prompt itself is NOT here (V2 (c) DROPPED prompt-blocks): an agent's prompt is its
CLAUDE.md edited directly in the Monaco workbench (+ @ file-refs). This store holds ONLY
{display_name, avatar}.

Storage (mirrors group_templates):
  - a single JSON file ``agent_profiles.json`` (a dict keyed by alias) holding the display name
    and the avatar's file extension; default $PROMPTWORLD_DATA, else ~/.promptworld.
  - the avatar IMAGE bytes are saved as a real file ``avatars/<alias>.<ext>`` next to it, and
    served by the GET /api/agents/{alias}/avatar route — so the JSON stays small and the image
    is a normal cacheable file. The browser UPLOADS the image as a base64 data URL in the PUT
    body (no python-multipart dependency); the server decodes it once and writes the file.

Pure-ish: every storage path is passed in, so the persistence is unit-testable in isolation and
the SAME functions are reused by the render-verification harness.

One profile record (normalized on save)::

    {"alias": "<str>", "display_name": "<str>"|null, "avatar_ext": "<png|jpg|...>"|null}

The HTTP layer turns ``avatar_ext`` into a served URL ``/api/agents/<alias>/avatar?v=<mtime>``
(cache-buster) when the file exists, else ``avatar: null``.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# image mime -> file extension we accept for an uploaded avatar
_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}
_EXTENSIONS = set(_MIME_EXT.values()) | {"jpeg"}
MAX_AVATAR_BYTES = 2_000_000  # ~2MB decoded cap (avatars are small; reject anything larger)
_ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # the alias is also a filename component → jail it


# --------------------------------------------------------------------------- paths
def data_root() -> Path:
    """The writable root for profile JSON + avatar files. $PROMPTWORLD_DATA wins; else
    ~/.promptworld. Created if missing (same convention as group_templates)."""
    base = os.environ.get("PROMPTWORLD_DATA")
    root = Path(base) if base else (Path.home() / ".promptworld")
    root.mkdir(parents=True, exist_ok=True)
    return root


def profiles_path() -> Path:
    """The JSON file holding all agent profiles (keyed by alias)."""
    return data_root() / "agent_profiles.json"


def avatars_dir() -> Path:
    """The directory holding avatar image files (one per alias)."""
    d = data_root() / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_alias(alias: str) -> str:
    alias = (alias or "").strip()
    if not _ALIAS_RE.match(alias):
        raise ValueError(f"invalid alias: {alias!r}")
    return alias


# --------------------------------------------------------------------------- json store
def _load_raw(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text() or "{}")
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_raw(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def get_profile(path: Path, alias: str) -> Dict[str, Any]:
    """The stored profile for an alias (display_name + avatar_ext, both possibly None). Never
    raises for a missing alias — returns the empty default."""
    alias = _safe_alias(alias)
    rec = _load_raw(path).get(alias) or {}
    return {
        "alias": alias,
        "display_name": rec.get("display_name") or None,
        "avatar_ext": rec.get("avatar_ext") or None,
    }


def set_profile(
    path: Path,
    alias: str,
    display_name: Any = ...,  # sentinel: only update if provided
    avatar_ext: Any = ...,
) -> Dict[str, Any]:
    """Merge-update a profile. Pass ``display_name``/``avatar_ext`` to change them (None clears);
    omit a field to leave it unchanged. Returns the fresh stored profile."""
    alias = _safe_alias(alias)
    data = _load_raw(path)
    rec = dict(data.get(alias) or {})
    if display_name is not ...:
        dn = (display_name or "").strip() if isinstance(display_name, str) else None
        rec["display_name"] = dn or None
    if avatar_ext is not ...:
        rec["avatar_ext"] = (avatar_ext or None)
    data[alias] = rec
    _write_raw(path, data)
    return get_profile(path, alias)


# --------------------------------------------------------------------------- avatar files
def _decode_data_url(data_url: str) -> Tuple[bytes, str]:
    """Decode a ``data:image/<t>;base64,<...>`` URL → (bytes, ext). Raises ValueError on a
    non-image / malformed / oversized payload."""
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise ValueError("avatar must be a data: URL (data:image/<type>;base64,<...>)")
    try:
        header, b64 = data_url.split(",", 1)
    except ValueError:
        raise ValueError("malformed data URL")
    mime = header[5:].split(";", 1)[0].strip().lower()  # strip 'data:' .. ';base64'
    ext = _MIME_EXT.get(mime)
    if ext is None:
        raise ValueError(f"unsupported image type: {mime!r}")
    # cheap size guard BEFORE decoding the whole thing
    if len(b64) > (MAX_AVATAR_BYTES * 4) // 3 + 1024:
        raise ValueError("avatar too large")
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        raise ValueError("avatar is not valid base64")
    if len(raw) > MAX_AVATAR_BYTES:
        raise ValueError(f"avatar too large ({len(raw)} bytes; max {MAX_AVATAR_BYTES})")
    if not raw:
        raise ValueError("empty avatar")
    return raw, ext


def _existing_avatar(adir: Path, alias: str) -> Optional[Path]:
    for ext in sorted(_EXTENSIONS):
        p = adir / f"{alias}.{ext}"
        if p.exists():
            return p
    return None


def avatar_file(adir: Path, alias: str) -> Optional[Path]:
    """The avatar image file for an alias (any supported extension), or None."""
    return _existing_avatar(adir, _safe_alias(alias))


def save_avatar(adir: Path, profiles: Path, alias: str, data_url: str) -> Dict[str, Any]:
    """Decode a data-URL avatar, write ``avatars/<alias>.<ext>`` (removing any prior one of a
    different extension), record the ext in the profile, and return the fresh profile."""
    alias = _safe_alias(alias)
    raw, ext = _decode_data_url(data_url)
    adir.mkdir(parents=True, exist_ok=True)
    # drop any prior avatar of a different ext so only ONE file per alias exists
    prior = _existing_avatar(adir, alias)
    if prior is not None and prior.name != f"{alias}.{ext}":
        try:
            prior.unlink()
        except OSError:
            pass
    (adir / f"{alias}.{ext}").write_bytes(raw)
    return set_profile(profiles, alias, avatar_ext=ext)


def clear_avatar(adir: Path, profiles: Path, alias: str) -> Dict[str, Any]:
    """Delete the avatar file (if any) and clear its profile record."""
    alias = _safe_alias(alias)
    prior = _existing_avatar(adir, alias)
    if prior is not None:
        try:
            prior.unlink()
        except OSError:
            pass
    return set_profile(profiles, alias, avatar_ext=None)


def load_personas(personas_json: Path) -> Dict[str, Dict[str, str]]:
    """Read the per-agent persona config (display name + avatar filename) from a JSON file, LIVE
    (read on each call → hot-reloadable, never baked into code). Shape:
    ``{"<alias>": {"name": "<str>", "avatar": "<file under promptgym/avatars/>"}, ...}``. Returns
    {} on missing/invalid file. Keys starting with '_' (e.g. '_comment') are ignored. The HTTP layer
    uses this as the DEFAULT name+avatar for an alias that has no user-set profile (a user override
    via the profile editor always wins)."""
    try:
        raw = json.loads(Path(personas_json).read_text() or "{}")
    except (OSError, ValueError):
        return {}
    out: Dict[str, Dict[str, str]] = {}
    if isinstance(raw, dict):
        for alias, rec in raw.items():
            if alias.startswith("_") or not isinstance(rec, dict):
                continue
            out[alias] = {"name": str(rec.get("name") or ""), "avatar": str(rec.get("avatar") or "")}
    return out


__all__ = [
    "data_root",
    "profiles_path",
    "avatars_dir",
    "get_profile",
    "set_profile",
    "save_avatar",
    "clear_avatar",
    "avatar_file",
    "load_personas",
    "MAX_AVATAR_BYTES",
]
