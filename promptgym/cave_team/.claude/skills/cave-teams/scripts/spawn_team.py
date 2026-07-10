#!/usr/bin/env python3
"""
spawn_team.py — the cave-teams skill entrypoint. Any agent runs this to launch a team.

Usage:
    python3 spawn_team.py '<spec-json>'                 # inline spec
    python3 spawn_team.py /path/to/spec.json            # spec file
    python3 spawn_team.py spec.json --gallery http://localhost:8787
    python3 spawn_team.py spec.json --no-run            # build only, print handle

Gallery URL resolves from --gallery, else $CAVE_TEAMS_GALLERY, else none (headless).
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="Spin up a cave-team from a spec.")
    ap.add_argument("spec", help="inline JSON spec, or a path to a .json file")
    ap.add_argument("--gallery", default=os.environ.get("CAVE_TEAMS_GALLERY"),
                    help="gallery base URL (default: $CAVE_TEAMS_GALLERY)")
    ap.add_argument("--no-run", action="store_true",
                    help="build the team and return a handle instead of running a leader")
    args = ap.parse_args()

    raw = args.spec
    if raw.strip().endswith(".json") and os.path.exists(raw.strip()):
        with open(raw.strip()) as f:
            spec = json.load(f)
    else:
        spec = json.loads(raw)

    from cave_teams.adaptor import spawn_team

    result = spawn_team(spec, gallery_url=args.gallery, run=not args.no_run)
    # drop the live handle before printing (not JSON-serializable)
    out = {k: v for k, v in result.items() if k != "harness"}
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
