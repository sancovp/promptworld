"""gym_specs — server-side persistence for the GYM MODULE's SPECS (the new additive layer).

The Gym module lets a user write SPECS (what to build/measure), track each spec's STATUS,
record OBSERVATIONS/measurements against a spec, and launch RESEARCH-RUNS (a specialist agent
dispatched against a spec, whose run + reply-excerpt is recorded back onto the spec). This is
DISTINCT from the PromptGym class (the agent registry) — this module only persists spec records.

This module persists specs as a single JSON file (a dict keyed by spec id), so they survive a
server restart (within the same writable volume). Same storage convention as group_templates /
agent_profiles: the path helper picks a WRITABLE location — $PROMPTWORLD_DATA, else ~/.promptworld
(created if missing).

Pure-ish: the storage path is passed in, so the persistence is unit-testable in isolation and the
SAME functions are reused by any harness.

Schema of one spec::

    {
      "id": "<slug-stamp>", "title": "<str>", "body": "<str>",
      "status": "<draft|active|measuring|done|abandoned>",
      "owner_alias": "<str>", "assigned_agent": "<str>", "created_at": "<iso datetime>",
      "schedule": "<str|null>",  # a CAVE schedule string (e.g. "every:3600"); null = not scheduled
      "published": false,
      "observations": [{"ts": "<iso>", "text": "<str>", "metric": "<str>|null"}, ...],
      "runs": [{"ts": "<iso>", "alias": "<str>", "request": "<str>", "reply_excerpt": "<str>"}, ...],
      "papers": [{"id": "<slug-stamp>", "ts": "<iso>", "title": "<str>", "body": "<str>",
                  "published": false}, ...]
    }
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# the allowed spec statuses (the Gym ontology lifecycle)
ALLOWED_STATUSES = {"draft", "active", "measuring", "done", "abandoned"}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def specs_path() -> Path:
    """The writable JSON file holding all gym specs. $PROMPTWORLD_DATA wins; else
    ~/.promptworld/gym_specs.json. The parent dir is created if missing. (Same convention as
    templates_path()/data_root().)"""
    base = os.environ.get("PROMPTWORLD_DATA")
    root = Path(base) if base else (Path.home() / ".promptworld")
    root.mkdir(parents=True, exist_ok=True)
    return root / "gym_specs.json"


def _load_raw(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text() or "{}")
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _slug(title: str) -> str:
    """A short lowercase slug of the title (alnum words joined by '-', max ~40 chars)."""
    s = _SLUG_RE.sub("-", (title or "").lower()).strip("-")
    return s[:40] or "spec"


def list_specs(path: Path, status: Optional[str] = None, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    """All specs as a list (insertion order of the underlying dict), optionally filtered by
    status and/or owner_alias."""
    specs = list(_load_raw(path).values())
    if status is not None:
        specs = [s for s in specs if s.get("status") == status]
    if owner is not None:
        specs = [s for s in specs if s.get("owner_alias") == owner]
    return specs


def get_spec(path: Path, spec_id: str) -> Optional[Dict[str, Any]]:
    """The stored spec for an id, or None if missing."""
    return _load_raw(path).get(spec_id)


def create_spec(
    path: Path,
    title: str,
    body: str,
    owner_alias: str,
    assigned_agent: Optional[str] = None,
    schedule: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new spec (status 'draft') and persist it; returns the stored spec. The id is a
    short slug of the title plus a datetime.now() stamp, made unique against existing ids.

    `assigned_agent` is the specialist alias that researches the spec (defaults to owner_alias when
    not given). `schedule` is a CAVE schedule string (e.g. "every:3600"); null when not scheduled.
    A spec starts unpublished with no papers. Raises ValueError if title is empty."""
    title = (title or "").strip()
    if not title:
        raise ValueError("spec title is required")
    data = _load_raw(path)
    base_id = f"{_slug(title)}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    spec_id = base_id
    n = 1
    while spec_id in data:  # ensure unique even within the same second
        n += 1
        spec_id = f"{base_id}-{n}"
    spec = {
        "id": spec_id,
        "title": title,
        "body": body or "",
        "status": "draft",
        "owner_alias": owner_alias,
        "assigned_agent": assigned_agent or owner_alias,
        "created_at": datetime.now().isoformat(),
        "schedule": schedule or None,
        "published": False,
        "observations": [],
        "runs": [],
        "papers": [],
    }
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


def update_spec(
    path: Path,
    spec_id: str,
    *,
    status: Optional[str] = None,
    body: Optional[str] = None,
    title: Optional[str] = None,
    assigned_agent: Optional[str] = None,
    schedule: Optional[str] = None,
) -> Dict[str, Any]:
    """Patch the allowed fields of a spec; persist; return the updated spec. Validates status
    against ALLOWED_STATUSES. `assigned_agent`, when provided, sets the researching specialist.
    `schedule`, when provided, sets the CAVE schedule string; the empty string clears it (stored as
    null). Raises KeyError if the spec is missing, ValueError on a bad status."""
    data = _load_raw(path)
    if spec_id not in data:
        raise KeyError(spec_id)
    spec = data[spec_id]
    if status is not None:
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {status!r} (allowed: {sorted(ALLOWED_STATUSES)})")
        spec["status"] = status
    if body is not None:
        spec["body"] = body
    if title is not None:
        title = title.strip()
        if not title:
            raise ValueError("spec title cannot be empty")
        spec["title"] = title
    if assigned_agent is not None:
        spec["assigned_agent"] = assigned_agent
    if schedule is not None:
        # "" clears the schedule -> null; any other value is stored verbatim
        spec["schedule"] = schedule.strip() or None
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


def add_observation(path: Path, spec_id: str, text: str, metric: Optional[str] = None) -> Dict[str, Any]:
    """Append an observation {ts, text, metric} to a spec's observations; persist; return the
    updated spec. Raises KeyError if the spec is missing, ValueError if text is empty."""
    text = (text or "").strip()
    if not text:
        raise ValueError("observation text is required")
    data = _load_raw(path)
    if spec_id not in data:
        raise KeyError(spec_id)
    spec = data[spec_id]
    spec.setdefault("observations", []).append(
        {"ts": datetime.now().isoformat(), "text": text, "metric": metric}
    )
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


def add_run_record(path: Path, spec_id: str, alias: str, request: str, reply_excerpt: str) -> Dict[str, Any]:
    """Append a research-run record {ts, alias, request, reply_excerpt} to a spec's runs; persist;
    return the updated spec. Raises KeyError if the spec is missing."""
    data = _load_raw(path)
    if spec_id not in data:
        raise KeyError(spec_id)
    spec = data[spec_id]
    spec.setdefault("runs", []).append(
        {
            "ts": datetime.now().isoformat(),
            "alias": alias,
            "request": request,
            "reply_excerpt": reply_excerpt,
        }
    )
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


def add_paper(path: Path, spec_id: str, title: str, body: str) -> Dict[str, Any]:
    """Append a RESEARCH PAPER {id, ts, title, body, published} to a spec's papers; persist; return
    the updated spec. The id is a short slug of the title plus a datetime.now() stamp, made unique
    against the spec's existing paper ids. Raises KeyError if the spec is missing, ValueError if both
    title and body are empty."""
    title = (title or "").strip()
    body = body or ""
    if not title and not body.strip():
        raise ValueError("paper requires a title or a body")
    data = _load_raw(path)
    if spec_id not in data:
        raise KeyError(spec_id)
    spec = data[spec_id]
    papers = spec.setdefault("papers", [])
    base_id = f"{_slug(title or 'paper')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    paper_id = base_id
    n = 1
    existing = {p.get("id") for p in papers}
    while paper_id in existing:  # ensure unique even within the same second
        n += 1
        paper_id = f"{base_id}-{n}"
    papers.append(
        {
            "id": paper_id,
            "ts": datetime.now().isoformat(),
            "title": title,
            "body": body,
            "published": False,
        }
    )
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


def update_paper(
    path: Path,
    spec_id: str,
    paper_id: str,
    *,
    title: Optional[str] = None,
    body: Optional[str] = None,
    published: Optional[bool] = None,
) -> Dict[str, Any]:
    """Patch a research paper's title/body/published flag; persist; return the updated spec. Raises
    KeyError if the spec or the paper is missing."""
    data = _load_raw(path)
    if spec_id not in data:
        raise KeyError(spec_id)
    spec = data[spec_id]
    paper = next((p for p in spec.get("papers", []) if p.get("id") == paper_id), None)
    if paper is None:
        raise KeyError(paper_id)
    if title is not None:
        paper["title"] = title
    if body is not None:
        paper["body"] = body
    if published is not None:
        paper["published"] = bool(published)
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


def set_published(path: Path, spec_id: str, published: bool) -> Dict[str, Any]:
    """Set a spec's published flag; persist; return the updated spec. Raises KeyError if missing."""
    data = _load_raw(path)
    if spec_id not in data:
        raise KeyError(spec_id)
    spec = data[spec_id]
    spec["published"] = bool(published)
    data[spec_id] = spec
    path.write_text(json.dumps(data, indent=2))
    return spec


__all__ = [
    "ALLOWED_STATUSES",
    "specs_path",
    "list_specs",
    "get_spec",
    "create_spec",
    "update_spec",
    "add_observation",
    "add_run_record",
    "add_paper",
    "update_paper",
    "set_published",
]
