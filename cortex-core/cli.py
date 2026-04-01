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

    # Onboarding — only if always-on is still the default template
    always_on = manager.read_always_on()
    if "[Your name]" in always_on and not args.skip_onboarding:
        print("\n🧠 Let's set up your brain. (Press Enter to skip any question)\n")

        name = input("Your name: ").strip()
        role = input("Your role / what you do: ").strip()
        focus = input("What are you currently working on? ").strip()
        stack = input("Your main tech stack: ").strip()
        timezone = input("Your timezone (e.g. America/Chicago): ").strip()

        lines = ["# Always-On Context\n"]
        if name:
            lines.append(f"## About Me\n- Name: {name}")
        if role:
            lines.append(f"- Role: {role}")
        if timezone:
            lines.append(f"- Timezone: {timezone}")
        if focus:
            lines.append(f"\n## Current Focus\n- {focus}")
        if stack:
            lines.append(f"\n## My Stack\n- {stack}")

        if any([name, role, focus, stack]):
            config.always_on_file.write_text("\n".join(lines) + "\n")
            print("\n✅ always-on.md created")

        # Seed first project if given
        if focus:
            proj_name = input(f"\nProject name for '{focus[:40]}...' (or Enter to skip): ").strip() if len(focus) > 40 else input(f"\nProject name for '{focus}' (or Enter to skip): ").strip()
            if proj_name:
                manager.update_project(
                    name=proj_name,
                    status="In progress",
                    focus=focus,
                    stack=stack or None,
                )
                print(f"✅ Project '{proj_name}' created")

    print(f"\n🧠 Brain ready at {config.root}")
    print(f"   Run: cortex start")
    print(f"   Dashboard: http://localhost:7700\n")


def cmd_serve(args):
    from .mcp.server import serve
    serve(port=args.port, host=args.host)


def cmd_start(args):
    from .server import serve
    serve(port=args.port, host=args.host, no_agent=args.no_agent)


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

    init_p = sub.add_parser("init", help="Initialize brain directory")
    init_p.add_argument("--skip-onboarding", action="store_true", help="Skip interactive setup")

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

    start_p = sub.add_parser("start", help="Start Cortex (dashboard + MCP + curation agent)")
    start_p.add_argument("--port", type=int, default=7700)
    start_p.add_argument("--host", default="127.0.0.1")
    start_p.add_argument("--no-agent", action="store_true", help="Disable background curation agent")

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
    elif args.command == "start":
        cmd_start(args)
    elif args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
