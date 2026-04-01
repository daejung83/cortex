"""
Cortex CLI

Usage:
    cortex init                          # Initialize brain directory
    cortex mcp serve [--port 7700]       # Start MCP server
    cortex search <query>                # Search brain files
    cortex note <text>                   # Append note to today
    cortex context                       # Print active context
    cortex distill [--days 3]            # Distill recent sessions
    cortex build-context [--days 2]      # Rebuild active-context.md
"""

import argparse
import os
import sys
from pathlib import Path

from .brain.schema import BrainConfig
from .brain.manager import BrainManager
from .search.searcher import BrainSearcher
from .curation.distiller import Distiller


def get_config() -> BrainConfig:
    brain_path = os.environ.get("CORTEX_BRAIN_PATH", str(Path.home() / ".cortex" / "brain"))
    return BrainConfig.from_root(brain_path)


def cmd_init(args):
    config = get_config()
    manager = BrainManager(config)
    manager.init()


def cmd_serve(args):
    from .mcp.server import serve
    serve(port=args.port, host=args.host)


def cmd_search(args):
    config = get_config()
    searcher = BrainSearcher(config)
    results = searcher.search(" ".join(args.query), max_results=args.limit)
    if not results:
        print("No results found.")
        return
    for r in results:
        print(f"\n📄 {r.file.name}:{r.line_no} [{r.heading}]")
        print(f"   {r.snippet}")


def cmd_note(args):
    config = get_config()
    manager = BrainManager(config)
    manager.append_to_today(" ".join(args.text), heading=args.heading)
    print(f"✅ Note saved to {manager.today_file().name}")


def cmd_context(args):
    config = get_config()
    manager = BrainManager(config)
    print(manager.read_active_context())


def cmd_distill(args):
    config = get_config()
    distiller = Distiller(config)
    result = distiller.distill(days=args.days)
    print(result)


def cmd_build_context(args):
    config = get_config()
    distiller = Distiller(config)
    result = distiller.build_active_context(days=args.days)
    print(f"✅ active-context.md rebuilt ({len(result.splitlines())} lines)")


def main():
    parser = argparse.ArgumentParser(prog="cortex", description="Cortex — persistent AI memory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize brain directory")

    serve_p = sub.add_parser("mcp", help="MCP server commands")
    serve_sub = serve_p.add_subparsers(dest="mcp_command")
    serve_cmd = serve_sub.add_parser("serve", help="Start MCP server")
    serve_cmd.add_argument("--port", type=int, default=7700)
    serve_cmd.add_argument("--host", default="127.0.0.1")

    search_p = sub.add_parser("search", help="Search brain files")
    search_p.add_argument("query", nargs="+")
    search_p.add_argument("--limit", type=int, default=10)

    note_p = sub.add_parser("note", help="Add note to today's brain file")
    note_p.add_argument("text", nargs="+")
    note_p.add_argument("--heading", default=None)

    sub.add_parser("context", help="Print active context")

    distill_p = sub.add_parser("distill", help="Distill recent sessions")
    distill_p.add_argument("--days", type=int, default=3)

    build_p = sub.add_parser("build-context", help="Rebuild active-context.md")
    build_p.add_argument("--days", type=int, default=2)

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "search": cmd_search,
        "note": cmd_note,
        "context": cmd_context,
        "distill": cmd_distill,
        "build-context": cmd_build_context,
    }

    if args.command == "mcp" and args.mcp_command == "serve":
        cmd_serve(args)
    elif args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
