"""Entry point for PromptWorld v1 CAVE server.

Usage:
    python -m server --dir /path/to/instance [--port 3858]

    PROMPTWORLD_DIR=/path/to/instance python -m server

PromptWorld has NO tmux: the engineer-CEO runs via ClaudePMainAgent (claude -p,
subscription auth). The --tmux arg is accepted but inert (kept for arg parity with
the healthworld template).
"""
import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


def main():
    parser = argparse.ArgumentParser(description="PromptWorld v1 CAVE Server")
    parser.add_argument("--dir", type=str, default=os.environ.get("PROMPTWORLD_DIR", "."),
                        help="PromptWorld instance directory")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "3858")),
                        help="Server port")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Server host")
    parser.add_argument("--tmux", type=str, default=os.environ.get("PROMPTWORLD_TMUX", "cave"),
                        help="(inert — PromptWorld has no tmux) kept for arg parity")
    args = parser.parse_args()

    from .promptworld_agent import PromptWorldAgent
    from .promptworld_server import PromptWorldHTTPServer

    agent = PromptWorldAgent(
        promptworld_dir=args.dir,
        port=args.port,
        tmux_session=args.tmux,
    )

    server = PromptWorldHTTPServer(
        cave=agent,
        port=args.port,
        host=args.host,
    )

    print(f"[PromptWorld] Starting at http://{args.host}:{args.port}")
    print(f"[PromptWorld] Instance: {args.dir}")
    print(f"[PromptWorld] Engineer-CEO via claude -p (subscription, no tmux)")
    server.run()


if __name__ == "__main__":
    main()
