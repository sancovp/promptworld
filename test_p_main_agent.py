#!/usr/bin/env python3
"""
Standalone acceptance test for ClaudePMainAgent + ConvoRegistry.

NO CAVE import, NO tmux. Proves the whole point: persistence across a FRESH instance
via the alias<->session_id registry + the SDK's `resume`.

Run:  python3 test_p_main_agent.py
(the container is already `claude login`'d, so the SDK turn authenticates via OAuth)

(a) new("t1") + send_and_wait("Remember 42, reply OK") -> a reply
(b) a FRESH ClaudePMainAgent(alias="t1") (simulating restart) send_and_wait("What number?")
    -> response contains "42"  (PROVES persistence)
(c) registry.list() shows t1
"""
import sys
import tempfile
from pathlib import Path

# import the module under test (standalone — sibling files, no package)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p_main_agent import ClaudePMainAgent, ConvoRegistry  # noqa: E402


def main() -> int:
    # isolated registry file so the test never touches the real ~/.promptworld
    tmp = tempfile.mkdtemp(prefix="pw_test_")
    reg_path = str(Path(tmp) / "convos.json")
    print(f"[test] registry path: {reg_path}")

    failures = []

    # ---- (a) start a fresh convo "t1", remember 42 -------------------------------
    # Under the SDK, the FIRST turn assigns the session_id (no preset/mint) — so we do NOT
    # reg.new() here; create the agent and let the turn mint+store the id.
    print("\n=== (a) new convo t1: remember 42 ===")
    reg_a = ConvoRegistry(reg_path)
    agent_a = ClaudePMainAgent(alias="t1", registry=reg_a)
    agent_a.create_session()
    reply_a = agent_a.send_and_wait("Remember the number 42. Reply with just OK.")
    print(f"[test] turn-1 reply: {reply_a!r}")
    if not reply_a.strip():
        failures.append("(a) turn-1 returned an empty reply")
    sid_after_a = reg_a.resume("t1")
    print(f"[test] session_id after turn 1: {sid_after_a}")

    # ---- (b) FRESH instance (simulating a restart): does it recall 42? -----------
    print("\n=== (b) FRESH ClaudePMainAgent(alias='t1') — does it recall 42? ===")
    # brand-new registry object reading the SAME file (no shared in-memory state)
    reg_b = ConvoRegistry(reg_path)
    agent_b = ClaudePMainAgent(alias="t1", registry=reg_b)
    print(f"[test] fresh agent resolved t1 -> session_id {agent_b.session_id}")
    assert agent_b.session_exists(), "fresh agent should see the saved convo"
    reply_b = agent_b.send_and_wait("What number did I ask you to remember? Reply with just the number.")
    print(f"[test] turn-2 reply (fresh instance): {reply_b!r}")
    if "42" not in reply_b:
        failures.append(f"(b) fresh instance did NOT recall 42 (got {reply_b!r})")
    else:
        print("[test] PERSISTENCE PROVEN: fresh instance recalled 42 via --resume")

    # ---- (c) registry.list() shows t1 -------------------------------------------
    print("\n=== (c) registry.list() ===")
    listing = ConvoRegistry(reg_path).list()
    print(f"[test] registry.list() = {listing}")
    if "t1" not in listing:
        failures.append("(c) registry.list() does not contain t1")

    # ---- summary -----------------------------------------------------------------
    print("\n=== SUMMARY ===")
    print(f"(a) reply non-empty : {'PASS' if not any(f.startswith('(a)') for f in failures) else 'FAIL'}")
    print(f"(b) recall 42       : {'PASS' if not any(f.startswith('(b)') for f in failures) else 'FAIL'}")
    print(f"(c) list shows t1   : {'PASS' if not any(f.startswith('(c)') for f in failures) else 'FAIL'}")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL PASS — persistence proven across a fresh instance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
