#!/usr/bin/env python3
"""
generate_unit_readme.py — per-repo README badge-block + CHANGELOG auto-generator.

The PER-REPO extension of heaven-bml's ecosystem-README generator
(github_workflows/generate_ecosystem_readme.py): same pattern (requests -> GitHub API ->
badges, with graceful try/except when offline), but instead of building ONE multi-repo index
README it maintains a SINGLE tier-2 unit's README + CHANGELOG.

Two things it does to a target working tree (the rsync'd clone, or any dir):

  1. README.md — injects a MANAGED block (badges + latest-release + last-updated + a link to
     the CHANGELOG) between sentinel markers, WITHOUT clobbering the unit's hand-written README.
       - markers present  -> replace only the text between them (idempotent)
       - markers absent    -> insert the block right after the first '# H1' (or prepend)
       - no README at all  -> create a minimal one (# name + description + block)
  2. CHANGELOG.md — PREPENDS one entry per publish ref ('## <ref> — <date>'), idempotent:
     if an entry for <ref> already exists it is left untouched (re-runs add nothing).

It does NOT commit/push — the caller (publish_unit.sh) does git add + commit-if-changed, so the
no-drift property is the caller's `git diff --cached --quiet`. This script only edits files.

Offline / no token: badge fetching degrades gracefully (no network -> no badges, README/CHANGELOG
structure still written) — same try/except discipline as the heaven-bml generator.

Usage:
  generate_unit_readme.py --repo <owner/name> --dir <tree> [--ref <label>] [--meta <json>]
                          [--token-env GITHUB_TOKEN] [--no-changelog]
    --repo   public repo (owner/name) — used for badges + the GitHub API lookup.
    --dir    working tree to edit (default '.') — where README.md / CHANGELOG.md live.
    --ref    publish ref/tag for the CHANGELOG entry (default 'manual'); no entry written if 'manual'.
    --meta   optional JSON string OR @path: {name, description, install, links{}, badges{}}.
    --token-env  env var holding a GitHub token (default GITHUB_TOKEN); absent -> offline mode.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

try:
    import requests  # the ONE dependency (matches heaven-bml: `pip install requests`)
except Exception:  # pragma: no cover - offline import guard
    requests = None

AUTOGEN_START = "<!-- SCALABLE-PUBLISHING:AUTOGEN START (managed block — do not edit between these markers) -->"
AUTOGEN_END = "<!-- SCALABLE-PUBLISHING:AUTOGEN END -->"

DEFAULT_BADGES = {"license": True, "version": True, "stars": True, "last_updated": True, "issue_count": False}


def get_repo_data(repo_name, github_token):
    """Fetch repository data from the GitHub API. Mirrors heaven-bml's get_repo_data:
    returns a best-effort dict; on ANY failure returns a safe offline stub (no raise)."""
    if not (requests and github_token):
        return None
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(f"https://api.github.com/repos/{repo_name}", headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        try:
            rel = requests.get(
                f"https://api.github.com/repos/{repo_name}/releases/latest", headers=headers, timeout=20
            )
            data["latest_release"] = rel.json() if rel.status_code == 200 else None
        except Exception:
            data["latest_release"] = None
        return data
    except Exception as e:
        print(f"[generate_unit_readme] repo data unavailable for {repo_name}: {e}", file=sys.stderr)
        return None


def generate_badges(repo_data, repo_name, badge_cfg):
    """Badge markdown for ONE repo. Same shields.io vocabulary as the heaven-bml generator."""
    badges = []
    if not repo_data:
        return ""
    if badge_cfg.get("license") and repo_data.get("license"):
        lic = repo_data["license"]["name"].replace(" ", "_").replace("-", "--")
        badges.append(f"![License](https://img.shields.io/badge/license-{lic}-blue.svg)")
    if badge_cfg.get("version") and repo_data.get("latest_release"):
        ver = repo_data["latest_release"]["tag_name"].replace("-", "--")
        badges.append(f"![Version](https://img.shields.io/badge/version-{ver}-green.svg)")
    if badge_cfg.get("stars"):
        badges.append(f"![Stars](https://img.shields.io/github/stars/{repo_name}.svg?style=social)")
    if badge_cfg.get("last_updated") and repo_data.get("updated_at"):
        upd = repo_data["updated_at"][:10].replace("-", "_")
        badges.append(f"![Updated](https://img.shields.io/badge/updated-{upd}-lightgrey.svg)")
    if badge_cfg.get("issue_count") and "open_issues_count" in repo_data:
        n = repo_data["open_issues_count"]
        color = "red" if n > 10 else "yellow" if n > 5 else "green"
        badges.append(f"![Issues](https://img.shields.io/badge/issues-{n}-{color}.svg)")
    return " ".join(badges)


def build_managed_block(repo_name, repo_data, meta):
    """The text that lives between the sentinels. Badges + a stats line + links + CHANGELOG pointer."""
    badge_cfg = {**DEFAULT_BADGES, **(meta.get("badges") or {})}
    lines = [AUTOGEN_START, ""]

    badges = generate_badges(repo_data, repo_name, badge_cfg)
    if badges:
        lines += [badges, ""]

    if repo_data:
        stats = f"⭐ {repo_data.get('stargazers_count', 0)} stars"
        if repo_data.get("latest_release"):
            stats += f" • 📦 Latest: {repo_data['latest_release']['tag_name']}"
        if repo_data.get("updated_at"):
            stats += f" • 🕑 Updated {repo_data['updated_at'][:10]}"
        lines += [stats, ""]

    links = meta.get("links") or {}
    if links:
        lines.append(" • ".join(f"[{k}]({v})" for k, v in links.items()))
        lines.append("")

    lines += [
        f"📦 Auto-published from the monorepo • [CHANGELOG](./CHANGELOG.md) • [{repo_name}](https://github.com/{repo_name})",
        "",
        AUTOGEN_END,
    ]
    return "\n".join(lines)


def inject_block(readme_text, block, name, description):
    """Insert/replace the managed block in README text, preserving hand-written content."""
    if AUTOGEN_START in readme_text and AUTOGEN_END in readme_text:
        # Replace only the managed region (idempotent).
        pattern = re.compile(re.escape(AUTOGEN_START) + r".*?" + re.escape(AUTOGEN_END), re.DOTALL)
        return pattern.sub(block, readme_text, count=1)

    if not readme_text.strip():
        # No README at all -> minimal scaffold.
        head = f"# {name}\n\n"
        if description:
            head += f"{description}\n\n"
        return head + block + "\n"

    # README exists but has no markers -> insert after the first H1 (or prepend).
    lines = readme_text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            insert_at = i + 1
            out = "\n".join(lines[:insert_at] + ["", block, ""] + lines[insert_at:])
            return _collapse_blanks(out.rstrip("\n") + "\n")
    # No H1 found -> prepend.
    return _collapse_blanks((block + "\n\n" + readme_text).rstrip("\n") + "\n")


def _collapse_blanks(text):
    """Collapse runs of 3+ newlines down to a single blank line (cosmetic; block uses \\n\\n)."""
    return re.sub(r"\n{3,}", "\n\n", text)


def prepend_changelog(changelog_text, ref, date_str, note):
    """Prepend a '## <ref> — <date>' entry (newest-first) unless one for <ref> already exists."""
    header = "# Changelog\n\nAll notable publishes of this repo. Auto-maintained on publish.\n\n"
    if not changelog_text.strip():
        changelog_text = header
    # Idempotency: bail if an entry header for this exact ref already exists.
    if re.search(r"^##\s+" + re.escape(ref) + r"\b", changelog_text, re.MULTILINE):
        return changelog_text, False

    entry = f"## {ref} — {date_str}\n\n- {note}\n\n"
    # Insert before the FIRST existing entry ('## ' line) so newest is on top, below the header.
    m = re.search(r"^## ", changelog_text, re.MULTILINE)
    if m:
        idx = m.start()
        return changelog_text[:idx] + entry + changelog_text[idx:], True
    # No existing entry yet -> append the entry after the header block.
    if not changelog_text.endswith("\n\n"):
        changelog_text = changelog_text.rstrip("\n") + "\n\n"
    return changelog_text + entry, True


def load_meta(meta_arg):
    if not meta_arg:
        return {}
    if meta_arg.startswith("@"):
        with open(meta_arg[1:], "r") as f:
            return json.load(f)
    return json.loads(meta_arg)


def main():
    ap = argparse.ArgumentParser(description="Per-repo README badge-block + CHANGELOG generator.")
    ap.add_argument("--repo", required=True, help="public repo owner/name (badges + API)")
    ap.add_argument("--dir", default=".", help="working tree to edit (default '.')")
    ap.add_argument("--ref", default="manual", help="publish ref/tag for the CHANGELOG entry")
    ap.add_argument("--meta", default="", help="JSON string or @path: {name,description,install,links,badges}")
    ap.add_argument("--note", default="Published from monorepo.", help="CHANGELOG entry note")
    ap.add_argument("--token-env", default="GITHUB_TOKEN", help="env var holding a GitHub token")
    ap.add_argument("--no-changelog", action="store_true", help="skip CHANGELOG maintenance")
    args = ap.parse_args()

    tree = args.dir
    meta = load_meta(args.meta)
    name = meta.get("name") or args.repo.split("/")[-1]
    description = meta.get("description", "")
    token = os.environ.get(args.token_env, "")

    repo_data = get_repo_data(args.repo, token)
    if repo_data is None:
        print("[generate_unit_readme] offline/no-token mode — writing structure without live badges.")

    # ---- README ----
    readme_path = os.path.join(tree, "README.md")
    readme_text = ""
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            readme_text = f.read()
    block = build_managed_block(args.repo, repo_data, meta)
    new_readme = inject_block(readme_text, block, name, description)
    if new_readme != readme_text:
        with open(readme_path, "w") as f:
            f.write(new_readme)
        print(f"[generate_unit_readme] README.md updated ({readme_path})")
    else:
        print("[generate_unit_readme] README.md unchanged")

    # ---- CHANGELOG ----
    if not args.no_changelog and args.ref and args.ref != "manual":
        cl_path = os.path.join(tree, "CHANGELOG.md")
        cl_text = ""
        if os.path.exists(cl_path):
            with open(cl_path, "r") as f:
                cl_text = f.read()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_cl, changed = prepend_changelog(cl_text, args.ref, date_str, args.note)
        if changed:
            with open(cl_path, "w") as f:
                f.write(new_cl)
            print(f"[generate_unit_readme] CHANGELOG.md entry added for {args.ref}")
        else:
            print(f"[generate_unit_readme] CHANGELOG.md already has an entry for {args.ref}")


if __name__ == "__main__":
    main()
