"""group_templates — server-side persistence for the GROUP page's named templates.

The frontend GROUP page lets a user select any subset of the 8 agents (CEO + 7
PromptGym specialists), arrange them side-by-side, and customize each window's
ORDER + COLOR + LABEL. A "group template" captures that arrangement under a name so it
can be reloaded. This module persists templates as a single JSON file (a dict keyed by
template name), so it survives server restarts (within the same writable volume).

Pure-ish: the storage path is passed in, so the persistence is unit-testable in isolation
and the SAME functions are reused by the render-verification harness. The path helper
picks a WRITABLE location: $PROMPTWORLD_DATA, else ~/.promptworld (created if missing).

Schema of one template (validated/normalized on save):
    {"name": "<str>", "agents": [{"alias": "<str>", "label": "<str>", "color": "<str>"}, ...]}
The `agents` list order IS the window order.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List


def templates_path() -> Path:
    """The writable JSON file holding all group templates. $PROMPTWORLD_DATA wins; else
    ~/.promptworld/group_templates.json. The parent dir is created if missing."""
    base = os.environ.get("PROMPTWORLD_DATA")
    root = Path(base) if base else (Path.home() / ".promptworld")
    root.mkdir(parents=True, exist_ok=True)
    return root / "group_templates.json"


def _load_raw(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text() or "{}")
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _normalize_agents(agents: Any) -> List[Dict[str, str]]:
    """Coerce the incoming agents list into [{alias,label,color}] of strings, dropping
    anything without an alias. Order is preserved (= window order)."""
    out: List[Dict[str, str]] = []
    for a in agents if isinstance(agents, list) else []:
        if not isinstance(a, dict):
            continue
        alias = str(a.get("alias", "")).strip()
        if not alias:
            continue
        out.append(
            {
                "alias": alias,
                "label": str(a.get("label", "") or alias),
                "color": str(a.get("color", "") or ""),
            }
        )
    return out


def list_templates(path: Path) -> List[Dict[str, Any]]:
    """All saved templates as a list (insertion order of the underlying dict)."""
    return list(_load_raw(path).values())


def save_template(path: Path, name: str, agents: Any) -> Dict[str, Any]:
    """Create/overwrite the named template; returns the stored template."""
    name = (name or "").strip()
    if not name:
        raise ValueError("template name is required")
    data = _load_raw(path)
    tmpl = {"name": name, "agents": _normalize_agents(agents)}
    data[name] = tmpl
    path.write_text(json.dumps(data, indent=2))
    return tmpl


def delete_template(path: Path, name: str) -> bool:
    """Delete the named template; True if it existed."""
    data = _load_raw(path)
    if name in data:
        del data[name]
        path.write_text(json.dumps(data, indent=2))
        return True
    return False
