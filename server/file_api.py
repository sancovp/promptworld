"""file_api — workspace file operations for the PromptWorld Monaco explorer.

SECURITY-CRITICAL: every operation is PATH-JAILED to the workspace root. The jail
resolves the requested path under the root and rejects anything whose REAL (symlink-
resolved) path is not inside the root — blocking ../ traversal, absolute paths, and
symlink escapes. Plain Python I/O (no docker exec, no base64).

Pure functions (root passed in) so the jail can be unit-tested in isolation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

# directories never walked / returned in the tree
SKIP_DIRS = {
    "node_modules", ".git", "dist", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".vite", ".idea", ".cache",
}
MAX_FILE_BYTES = 1_000_000  # ~1MB: skip bigger files in the tree, reject on read
MAX_DEPTH = 12


class PathJailError(Exception):
    """Raised when a requested path resolves outside the workspace root."""


def resolve_workspace_root(pw: Any) -> Path:
    """Workspace root: env PROMPTWORLD_WORKSPACE, else the ceo agent's cwd, else the
    instance dir. Resolved to a real absolute path (symlinks collapsed)."""
    env = os.environ.get("PROMPTWORLD_WORKSPACE")
    if env:
        return Path(env).resolve()
    ma = getattr(pw, "main_agent", None)
    cwd = getattr(ma, "cwd", None) if ma is not None else None
    if cwd:
        return Path(cwd).resolve()
    return Path(getattr(pw, "promptworld_dir", ".")).resolve()


def jail_resolve(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root` and PROVE the real path stays inside `root`.

    Raises PathJailError on: None/empty-with-no-root-meaning, NUL bytes, absolute
    paths (Path('/x') division resets to absolute → resolves outside), ../ traversal,
    and symlink escapes (resolve() follows symlinks, so an escaping link resolves out).
    strict=False so a not-yet-existing WRITE target still resolves (its parents are
    still jailed). Returns the resolved absolute Path on success.
    """
    root = root.resolve()
    if rel is None:
        raise PathJailError("path required")
    if "\x00" in rel:
        raise PathJailError("invalid path")
    rel_clean = rel.strip()
    # "" / "." / "./" mean the root itself
    candidate = root if rel_clean in ("", ".", "./") else (root / rel_clean)
    real = candidate.resolve()
    if real != root and root not in real.parents:
        raise PathJailError(f"path escapes workspace: {rel!r}")
    return real


def build_tree(root: Path) -> Dict[str, Any]:
    """Recursive tree of the workspace (relative paths, dirs+files). Skips SKIP_DIRS,
    files > MAX_FILE_BYTES, symlinks (avoid loops/escapes), and caps depth."""
    root = root.resolve()

    def walk(d: Path, depth: int):
        out = []
        try:
            children = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except (PermissionError, OSError):
            return out
        for child in children:
            if child.is_symlink():
                continue  # never follow/list symlinks (loop + escape safety)
            name = child.name
            try:
                rel = str(child.relative_to(root))
            except ValueError:
                continue
            if child.is_dir():
                if name in SKIP_DIRS:
                    continue
                node: Dict[str, Any] = {"name": name, "path": rel, "type": "dir"}
                node["children"] = [] if depth >= MAX_DEPTH else walk(child, depth + 1)
                out.append(node)
            elif child.is_file():
                try:
                    size = child.stat().st_size
                except OSError:
                    continue
                if size > MAX_FILE_BYTES:
                    continue
                out.append({"name": name, "path": rel, "type": "file", "size": size})
        return out

    return {"root": str(root), "tree": walk(root, 0)}


def read_file(root: Path, rel: str) -> Dict[str, Any]:
    """Read a text file (path-jailed). Raises PathJailError / FileNotFoundError /
    ValueError(binary|too large)."""
    real = jail_resolve(root, rel)
    if not real.exists() or not real.is_file():
        raise FileNotFoundError(rel)
    size = real.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file too large ({size} bytes)")
    data = real.read_bytes()
    if b"\x00" in data[:4096]:
        raise ValueError("binary file")
    return {"path": rel, "content": data.decode("utf-8", errors="replace"), "size": size}


def write_file(root: Path, rel: str, content: str) -> Dict[str, Any]:
    """Write a text file (path-jailed). Creates parent dirs (which are themselves inside
    the jail, since `real` is proven inside root). Raises PathJailError on escape."""
    real = jail_resolve(root, rel)
    if real == root.resolve():
        raise PathJailError("cannot write the workspace root itself")
    real.parent.mkdir(parents=True, exist_ok=True)
    text = content if isinstance(content, str) else str(content)
    real.write_text(text, encoding="utf-8")
    return {"ok": True, "path": rel, "bytes": len(text.encode("utf-8"))}


def make_dir(root: Path, rel: str) -> Dict[str, Any]:
    """Create a directory (path-jailed). Idempotent (exist_ok). Raises PathJailError on
    escape. Used by the editor's 'new folder' action."""
    real = jail_resolve(root, rel)
    if real == root.resolve():
        raise PathJailError("cannot create the workspace root itself")
    real.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": rel, "type": "dir"}


def rename_path(root: Path, src: str, dst: str) -> Dict[str, Any]:
    """Rename/move a file or dir from `src` to `dst` (BOTH path-jailed). Creates dst parent dirs.
    Raises PathJailError on escape, FileNotFoundError if src missing, FileExistsError if dst exists."""
    real_src = jail_resolve(root, src)
    real_dst = jail_resolve(root, dst)
    if real_src == root.resolve() or real_dst == root.resolve():
        raise PathJailError("cannot rename the workspace root itself")
    if not real_src.exists():
        raise FileNotFoundError(src)
    if real_dst.exists():
        raise FileExistsError(dst)
    real_dst.parent.mkdir(parents=True, exist_ok=True)
    real_src.rename(real_dst)
    return {"ok": True, "from": src, "to": dst}


def delete_path(root: Path, rel: str) -> Dict[str, Any]:
    """Delete a file or directory (path-jailed, recursive for dirs). Raises PathJailError
    on escape, FileNotFoundError if missing. Used by the editor's delete action."""
    import shutil

    real = jail_resolve(root, rel)
    if real == root.resolve():
        raise PathJailError("cannot delete the workspace root itself")
    if not real.exists():
        raise FileNotFoundError(rel)
    if real.is_dir():
        shutil.rmtree(real)
        kind = "dir"
    else:
        real.unlink()
        kind = "file"
    return {"ok": True, "path": rel, "type": kind}
