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


def _q():
    """Import questionary, fallback to plain input if unavailable."""
    try:
        import questionary
        return questionary
    except ImportError:
        return None


def cmd_init(args):
    config = get_config()
    manager = BrainManager(config)
    manager.init()

    flag_file = config.root / ".initialized"
    if not flag_file.exists() and not args.skip_onboarding:
        q = _q()
        _run_onboarding(config, manager, flag_file, q)

    print(f"\n  Brain ready at {config.root}")
    print(f"  Run: cortex start")
    print(f"  Dashboard: http://localhost:7700\n")


def _run_onboarding(config, manager, flag_file, q):
    """Interactive onboarding — uses questionary if available, falls back to input()."""

    _print_banner()

    if q:
        name     = q.text("Your name:").ask() or ""
        role     = q.text("Your role / what you do:").ask() or ""
        focus    = q.text("What are you currently working on? (Enter to skip)").ask() or ""
        stack    = q.text("Your main tech stack: (e.g. Python, Next.js)").ask() or ""
        timezone = q.text("Your timezone:").ask() or ""
    else:
        print("(Press Enter to skip any question)\n")
        name     = input("Your name: ").strip()
        role     = input("Your role / what you do: ").strip()
        focus    = input("What are you currently working on? ").strip()
        stack    = input("Your main tech stack: ").strip()
        timezone = input("Your timezone (e.g. America/Chicago): ").strip()

    # Write always-on.md
    lines = ["# Always-On Context\n"]
    if name:     lines.append(f"## About Me\n- Name: {name}")
    if role:     lines.append(f"- Role: {role}")
    if timezone: lines.append(f"- Timezone: {timezone}")
    if focus:    lines.append(f"\n## Current Focus\n- {focus}")
    if stack:    lines.append(f"\n## My Stack\n- {stack}")

    if any([name, role, focus, stack]):
        config.always_on_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n  always-on.md saved")

    flag_file.write_text("initialized", encoding="utf-8")

    # Seed a welcome note so first get_context() has something useful
    from datetime import datetime
    welcome = f"Cortex initialized. User: {name or 'unknown'}. Focus: {focus or 'not set'}. Stack: {stack or 'not set'}."
    manager.append_to_today(welcome, heading=f"{datetime.now().strftime('%H:%M')} | context")
    print("  Brain seeded with your setup")

    # LLM setup
    _setup_llm(config, q)


def _print_banner():
    print("""
  ╔═══════════════════════════════════════╗
  ║   🧠  Cortex — Brain Setup            ║
  ║   Persistent memory for your AI       ║
  ╚═══════════════════════════════════════╝
""")


def _setup_llm(config, q=None):
    """Interactive LLM setup — arrow key selection if questionary available."""
    secrets_file = config.root.parent / ".env"

    print("""
  ─────────────────────────────────────────
  AI Curation (optional but recommended)
  ─────────────────────────────────────────
  Without LLM: Cortex uses heuristic mode — free,
  instant, no setup. Good enough for most users.

  With LLM: Cortex reads your session notes and
  writes intelligent summaries — understanding what
  actually mattered, not just copying recent lines.
  Active context is sharper, more useful, less noise.

  Estimated cost: ~$0.001/day with OpenAI or Anthropic.
  Ollama is 100% free and runs locally.
  ─────────────────────────────────────────
""")

    choices = [
        "Ollama — local, free, no API key (best for Claude subscribers)",
        "OpenAI — gpt-5.4-nano, ~$0.001/day",
        "Anthropic — claude-haiku, ~$0.001/day (separate API account needed)",
        "Skip — heuristic mode, free, always works",
    ]

    if q:
        choice = q.select(
            "Choose your curation mode:",
            choices=choices,
            use_arrow_keys=True,
        ).ask()
        if choice is None:
            choice = choices[3]
    else:
        for i, c in enumerate(choices, 1):
            print(f"  {i}) {c}")
        raw = input("\n  Choose [1-4] (default: 4): ").strip() or "4"
        idx = int(raw) - 1 if raw in ("1","2","3","4") else 3
        choice = choices[idx]

    if "Ollama" in choice:
        if q:
            model = q.text("Ollama model:", default="llama3.2").ask() or "llama3.2"
        else:
            model = input("  Ollama model (default: llama3.2): ").strip() or "llama3.2"
        _write_secret(secrets_file, "CORTEX_LLM_PROVIDER", "ollama")
        _write_secret(secrets_file, "CORTEX_LLM_MODEL", model)
        print(f"\n  Ollama configured ({model})")
        print(f"  Install: https://ollama.ai")
        print(f"  Then run: ollama pull {model}")

    elif "OpenAI" in choice:
        if q:
            api_key = q.password("OpenAI API key (sk-...):").ask() or ""
        else:
            api_key = input("  OpenAI API key (sk-...): ").strip()
        if api_key:
            _write_secret(secrets_file, "CORTEX_LLM_PROVIDER", "openai")
            _write_secret(secrets_file, "CORTEX_LLM_API_KEY", api_key)
            _write_secret(secrets_file, "CORTEX_LLM_MODEL", "gpt-5.4-nano")
            print(f"\n  OpenAI configured (gpt-5.4-nano)")
            print(f"  Key saved to {secrets_file}")
        else:
            print("\n  No key entered — using heuristic mode.")

    elif "Anthropic" in choice:
        print("\n  Note: Claude Code/Desktop subscription != API key.")
        print("  You need a separate account at console.anthropic.com\n")
        if q:
            api_key = q.password("Anthropic API key (sk-ant-...):").ask() or ""
        else:
            api_key = input("  Anthropic API key (sk-ant-...): ").strip()
        if api_key:
            _write_secret(secrets_file, "CORTEX_LLM_PROVIDER", "anthropic")
            _write_secret(secrets_file, "CORTEX_LLM_API_KEY", api_key)
            _write_secret(secrets_file, "CORTEX_LLM_MODEL", "claude-haiku-4-5")
            print(f"\n  Anthropic configured (claude-haiku-4-5)")
            print(f"  Key saved to {secrets_file}")
        else:
            print("\n  No key entered — using heuristic mode.")

    else:
        print("\n  Heuristic mode — fast, free, no setup needed.")
        print(f"  Enable LLM anytime: edit {secrets_file}")

    print()


def _write_secret(secrets_file, key: str, value: str):
    """Write or update a key in the secrets file."""
    content = secrets_file.read_text(encoding="utf-8") if secrets_file.exists() else ""
    lines = content.splitlines()
    new_lines = []
    updated = False
    for line in lines:
        stripped = line.lstrip("# ").split("=")[0].strip()
        if stripped == key:
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    secrets_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def cmd_serve(args):
    from .mcp.server import serve
    serve(port=args.port, host=args.host)


def cmd_start(args):
    from .server import serve
    serve(port=args.port, host=args.host, no_agent=args.no_agent)


MEMORY_INSTRUCTIONS = """# Memory Instructions (Cortex)
At the start of every session, call cortex:get_context() and cortex:get_learnings()
before responding to anything. This loads persistent memory and user profile.

During the session:
- Call cortex:log_note(content, type="decision") immediately when any decision is made
- Call cortex:log_note(content, type="progress") when work is completed
- Call cortex:log_note(content, type="insight") when something important is learned

Before any compaction or session end:
- Call cortex:save_session_summary() with a distilled summary
- Call cortex:update_project() for every project touched this session

When user references past work:
- Call cortex:search_brain(query, days=7) for last week
- Call cortex:search_brain(query) for all time
- Never guess — always search first
"""

MCP_JSON = lambda port: f"""\
{{
  "mcpServers": {{
    "cortex": {{
      "type": "streamable-http",
      "url": "http://127.0.0.1:{port}/mcp"
    }}
  }}
}}
"""


def cmd_init_project(args):
    """Set up Cortex in the current project directory."""
    import json
    from pathlib import Path

    port = args.port
    cwd = Path.cwd()
    created = []

    # .mcp.json — Claude Code project-scoped
    mcp_file = cwd / ".mcp.json"
    if not mcp_file.exists() or args.force:
        mcp_file.write_text(MCP_JSON(port), encoding="utf-8")
        created.append(".mcp.json (Claude Code — project-scoped MCP)")

    # CLAUDE.md — Claude Code instructions
    claude_md = cwd / "CLAUDE.md"
    if not claude_md.exists() or args.force:
        claude_md.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append("CLAUDE.md (Claude Code auto-load instructions)")

    # AGENTS.md — cross-tool standard (Cursor, Codex, Gemini, etc.)
    agents_md = cwd / "AGENTS.md"
    if not agents_md.exists() or args.force:
        agents_md.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append("AGENTS.md (cross-tool: Cursor, Codex, Gemini, Copilot)")

    # .cursorrules — Cursor legacy format
    cursorrules = cwd / ".cursorrules"
    if not cursorrules.exists() or args.force:
        cursorrules.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append(".cursorrules (Cursor)")

    # .windsurfrules — Windsurf
    windsurfrules = cwd / ".windsurfrules"
    if not windsurfrules.exists() or args.force:
        windsurfrules.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append(".windsurfrules (Windsurf)")

    print(f"\n🧠 Cortex connected to: {cwd.name}/\n")
    for f in created:
        print(f"  ✅ {f}")

    if not created:
        print("  ℹ️  All files already exist. Use --force to overwrite.")

    print(f"\n  Restart Claude Code / Cursor / Windsurf to activate.\n")


def cmd_init_global(args):
    """Set up Cortex globally — works in every project without per-project setup."""
    import json
    from pathlib import Path

    port = args.port
    created = []

    # Claude Code global: ~/.claude/.mcp.json
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(exist_ok=True)

    mcp_file = claude_dir / ".mcp.json"
    if not mcp_file.exists() or args.force:
        mcp_file.write_text(MCP_JSON(port), encoding="utf-8")
        created.append(f"{mcp_file} (Claude Code — global MCP)")

    # Claude Code global instructions: ~/.claude/CLAUDE.md
    claude_md = claude_dir / "CLAUDE.md"
    if not claude_md.exists() or args.force:
        claude_md.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append(f"{claude_md} (Claude Code — global instructions)")

    # Cursor global rules: ~/.cursor/rules/cortex.md
    cursor_rules_dir = Path.home() / ".cursor" / "rules"
    cursor_rules_dir.mkdir(parents=True, exist_ok=True)
    cursor_rule = cursor_rules_dir / "cortex.md"
    if not cursor_rule.exists() or args.force:
        cursor_rule.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append(f"{cursor_rule} (Cursor — global rules)")

    print(f"\n🧠 Cortex configured globally\n")
    for f in created:
        print(f"  ✅ {f}")

    if not created:
        print("  ℹ️  All files already exist. Use --force to overwrite.")

    print("""
  Next steps:
  • Restart Claude Code and Cursor to activate
  • Windsurf: set global rules manually in Settings → AI → Global Rules
    (paste the memory instructions from the Connect tab in the dashboard)
  • Run 'cortex start' to keep the MCP server running
""")


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

    ip = sub.add_parser("init-project", help="Connect Cortex to current project (creates CLAUDE.md, .cursorrules, etc.)")
    ip.add_argument("--port", type=int, default=7700)
    ip.add_argument("--force", action="store_true", help="Overwrite existing files")

    ig = sub.add_parser("init-global", help="Connect Cortex globally — works in every project")
    ig.add_argument("--port", type=int, default=7700)
    ig.add_argument("--force", action="store_true", help="Overwrite existing files")

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
    elif args.command == "init-project":
        cmd_init_project(args)
    elif args.command == "init-global":
        cmd_init_global(args)
    elif args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
