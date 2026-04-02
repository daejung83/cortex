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
    import platform
    config = get_config()
    manager = BrainManager(config)
    manager.init()

    flag_file = config.root / ".initialized"
    if not flag_file.exists() and not args.skip_onboarding:
        q = _q()
        _run_onboarding(config, manager, flag_file, q)

    print(f"\n  Brain ready at {config.root}")

    if platform.system() == "Windows":
        # Check if cortex is on PATH
        import shutil
        if not shutil.which("cortex"):
            print("""
  ⚠️  'cortex' is not on your PATH yet.
  Fix it permanently by running this in PowerShell:

    $p = python -m site --user-scripts
    [Environment]::SetEnvironmentVariable("PATH","$env:PATH;$p","User")

  Then restart PowerShell and use 'cortex start' directly.
  Until then, use: python -m cortex_core.cli start
""")
        else:
            print(f"  Run: cortex start")
    else:
        print(f"  Run: cortex start")

    print(f"  Dashboard: http://localhost:7700\n")


def _run_onboarding(config, manager, flag_file, q):
    """Interactive onboarding — uses questionary if available, falls back to input()."""

    _print_banner()

    if q:
        name  = q.text("Your name:").ask() or ""
        role  = q.text("Your role / what you do:").ask() or ""
        focus = q.text("What are you currently working on? (Enter to skip):").ask() or ""
    else:
        print("(Press Enter to skip any question)\n")
        name  = input("Your name: ").strip()
        role  = input("Your role / what you do: ").strip()
        focus = input("What are you currently working on? ").strip()

    # Auto-detect timezone
    try:
        import datetime
        timezone = str(datetime.datetime.now().astimezone().tzinfo)
    except Exception:
        timezone = ""

    # Write always-on.md
    lines = ["# Always-On Context\n"]
    if name: lines.append(f"## About Me\n- Name: {name}")
    if role: lines.append(f"- Role: {role}")
    if timezone: lines.append(f"- Timezone: {timezone}")
    if focus: lines.append(f"\n## Current Focus\n- {focus}")

    if any([name, role, focus]):
        config.always_on_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n  always-on.md saved")

    flag_file.write_text("initialized", encoding="utf-8")

    # Seed a welcome note so first get_context() has something useful
    from datetime import datetime
    welcome = f"Cortex initialized. User: {name or 'unknown'}. Focus: {focus or 'not set'}."
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
        print("\n  Heuristic mode selected — no setup needed, works immediately.")
        print("""
  You can enable LLM curation anytime later:

  Option 1 — Edit the secrets file directly:
""")
        print(f"    {secrets_file}")
        print("""
  Option 2 — Re-run setup:

    cortex init --skip-onboarding  (then change LLM in secrets file)

  Option 3 — From the dashboard:

    cortex start → open http://localhost:7700 → Connect tab → LLM Curation
""")

    print()


def cmd_update(args):
    """Check PyPI for a newer version and upgrade if available."""
    import subprocess, sys, urllib.request, json
    from importlib.metadata import version as pkg_version

    current = pkg_version("cortex-brain")
    print(f"\n  Current version: {current}")
    print(f"  Checking PyPI...")

    try:
        with urllib.request.urlopen("https://pypi.org/pypi/cortex-brain/json", timeout=5) as r:
            data = json.loads(r.read())
        latest = data["info"]["version"]
    except Exception:
        print("  Could not reach PyPI. Check your connection.")
        return

    if latest == current:
        print(f"  Already up to date ({current})\n")
        return

    print(f"  New version available: {latest}")
    q = _q()
    if q:
        do_update = q.confirm(f"  Upgrade from {current} to {latest}?", default=True).ask()
    else:
        do_update = input(f"  Upgrade from {current} to {latest}? [Y/n]: ").strip().lower() != "n"

    if do_update:
        import platform
        if platform.system() == "Windows":
            # Windows locks cortex.exe while running — pip can't overwrite it
            print(f"\n  ⚠️  Windows: stop Cortex first, then run:")
            print(f"       pip install --upgrade cortex-brain")
            print(f"  Then restart with: cortex start\n")
            return
        print(f"  Upgrading...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "cortex-brain", "-q"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✅ Upgraded to {latest}")
            print(f"  Restart Cortex to apply: stop (Ctrl+C) then cortex start\n")
        else:
            if "WinError 32" in result.stderr or "being used by another process" in result.stderr:
                print(f"\n  ⚠️  cortex.exe is locked. Stop Cortex first, then run:")
                print(f"       pip install --upgrade cortex-brain\n")
            else:
                print(f"  Upgrade failed: {result.stderr.strip()}")
    else:
        print("  Skipped.\n")


def _print_service_status(config_file=None, config_label="Config"):
    """Check if Cortex is running by hitting the API — works on all platforms."""
    import urllib.request, json
    try:
        with urllib.request.urlopen("http://127.0.0.1:7700/api/status", timeout=2) as r:
            data = json.loads(r.read())
            print(f"  Cortex: running ✅")
            print(f"  Dashboard: http://127.0.0.1:{data.get('port', 7700)}")
            print(f"  Brain: {data.get('brain_path', '~/.cortex/brain')}")
            llm = data.get('llm')
            print(f"  LLM: {llm['provider']} / {llm['model']}" if llm else "  LLM: heuristic mode")
    except Exception:
        print("  Cortex: not running ❌")
        print("  Run: cortex start")
    if config_file:
        from pathlib import Path
        p = Path(str(config_file))
        print(f"  {config_label}: {p} ({'exists' if p.exists() else 'missing'})")


def cmd_service(args):
    import platform
    system = platform.system()

    if not hasattr(args, 'service_command') or not args.service_command:
        print("Usage: cortex service [install|uninstall|status]")
        return

    if system == "Darwin":
        _service_macos(args)
    elif system == "Linux":
        _service_linux(args)
    elif system == "Windows":
        _service_windows(args)
    else:
        print(f"  Unsupported OS: {system}")
        print("  Run 'cortex start' manually to keep Cortex running.")


def _cortex_executable():
    """Find the cortex executable path."""
    import shutil, sys
    exe = shutil.which("cortex")
    if exe:
        return exe
    # Fallback: python -m cortex_core.cli
    return f"{sys.executable} -m cortex_core.cli"


def _service_macos(args):
    """macOS launchd plist — auto-starts on login."""
    import subprocess
    from pathlib import Path

    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "ai.cortex.brain.plist"
    cortex_exe = _cortex_executable()
    brain_path = Path.home() / ".cortex" / "brain"
    log_path = Path.home() / ".cortex" / "cortex.log"

    if args.service_command == "install":
        port = args.port
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.cortex.brain</string>
    <key>ProgramArguments</key>
    <array>
        <string>{cortex_exe.split()[0]}</string>
        {"".join(f"<string>{a}</string>" for a in cortex_exe.split()[1:])}
        <string>start</string>
        <string>--port</string>
        <string>{port}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>CORTEX_BRAIN_PATH</key>
        <string>{brain_path}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""
        plist_path.write_text(plist_content, encoding="utf-8")
        result = subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"\n  Cortex service installed and started!")
            print(f"  Auto-starts on login.")
            print(f"  Dashboard: http://localhost:{port}")
            print(f"  Logs: {log_path}")
            print(f"\n  To stop:      cortex service uninstall")
            print(f"  To check:     cortex service status\n")
        else:
            print(f"  Install failed: {result.stderr}")
            print(f"  Plist written to: {plist_path}")
            print(f"  Try manually: launchctl load {plist_path}")

    elif args.service_command == "uninstall":
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            print("  Cortex service removed.")
        else:
            print("  No service found.")

    elif args.service_command == "status":
        _print_service_status(plist_path, "Plist")


def _service_linux(args):
    """Linux systemd user service — auto-starts on login."""
    import subprocess
    from pathlib import Path

    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / "cortex.service"
    cortex_exe = _cortex_executable()
    brain_path = Path.home() / ".cortex" / "brain"

    if args.service_command == "install":
        port = args.port
        service_content = f"""[Unit]
Description=Cortex AI Brain Server
After=network.target

[Service]
Type=simple
ExecStart={cortex_exe} start --port {port}
Environment=CORTEX_BRAIN_PATH={brain_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
        service_path.write_text(service_content, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        result = subprocess.run(["systemctl", "--user", "enable", "--now", "cortex"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"\n  Cortex service installed and started!")
            print(f"  Auto-starts on login.")
            print(f"  Dashboard: http://localhost:{port}")
            print(f"\n  Logs:         journalctl --user -u cortex -f")
            print(f"  Stop:         cortex service uninstall")
            print(f"  Status:       cortex service status\n")
        else:
            print(f"  systemctl enable failed: {result.stderr.strip()}")
            print(f"  Service file written to: {service_path}")
            print(f"  Try manually:")
            print(f"    systemctl --user daemon-reload")
            print(f"    systemctl --user enable --now cortex")

    elif args.service_command == "uninstall":
        subprocess.run(["systemctl", "--user", "disable", "--now", "cortex"], capture_output=True)
        if service_path.exists():
            service_path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        print("  Cortex service removed.")

    elif args.service_command == "status":
        _print_service_status(service_path, "Service file")


def _service_windows(args):
    """Windows — no native service support without admin. Guide user to Task Scheduler."""
    from pathlib import Path
    import sys

    cortex_exe = _cortex_executable()
    port = getattr(args, 'port', 7700)
    brain_path = Path.home() / ".cortex" / "brain"
    bat_path = Path.home() / ".cortex" / "start-cortex.bat"

    if args.service_command == "install":
        # Write a .bat file and add to Windows startup folder
        startup_dir = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        shortcut_bat = startup_dir / "cortex.bat"

        bat_content = f"""@echo off
set CORTEX_BRAIN_PATH={brain_path}
start /B {cortex_exe} start --port {port}
"""
        bat_path.write_text(bat_content, encoding="utf-8")

        # Copy to startup folder
        try:
            import shutil
            shutil.copy(bat_path, shortcut_bat)
            print(f"\n  Cortex startup script installed!")
            print(f"  Auto-starts on Windows login.")
            print(f"  Dashboard: http://localhost:{port}")
            print(f"\n  Script: {bat_path}")
            print(f"  Startup: {shortcut_bat}")
            print(f"\n  To remove: cortex service uninstall\n")
        except PermissionError:
            print(f"\n  Could not write to startup folder (permission denied).")
            print(f"  Manual option: add this to your Windows startup folder:")
            print(f"  {bat_path} -> {startup_dir}")

    elif args.service_command == "uninstall":
        startup_dir = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        shortcut_bat = startup_dir / "cortex.bat"
        removed = []
        for p in [bat_path, shortcut_bat]:
            if p.exists():
                p.unlink()
                removed.append(str(p))
        if removed:
            print(f"  Removed: {', '.join(removed)}")
        else:
            print("  No startup files found.")

    elif args.service_command == "status":
        startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "cortex.bat"
        _print_service_status(startup, "Startup script")


def _write_secret(secrets_file, key: str, value: str):
    """Write or update a key in the secrets file. Exact key match only."""
    content = secrets_file.read_text(encoding="utf-8") if secrets_file.exists() else ""
    lines = content.splitlines()
    new_lines = []
    updated = False
    for line in lines:
        # Parse the key from the line, handling commented-out lines like "# KEY=val"
        stripped = line.lstrip("#").lstrip()
        if "=" in stripped:
            line_key = stripped.split("=", 1)[0].strip()
            if line_key == key:
                new_lines.append(f"{key}={value}")
                updated = True
                continue
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

    # Claude Code global MCP — use `claude mcp add -s user` (user-scoped, works everywhere)
    # This writes to ~/.claude/settings.json which Claude Code reads for user-level MCP servers.
    # Writing .mcp.json directly is unreliable across platforms (scope is project-local).
    import os, platform, subprocess as sp
    claude_cli = "claude"
    mcp_url = f"http://127.0.0.1:{port}/mcp"
    claude_result = sp.run(
        [claude_cli, "mcp", "add", "-s", "user", "--transport", "http", "cortex", mcp_url],
        capture_output=True, text=True
    )
    if claude_result.returncode == 0:
        created.append("Claude Code user-scoped MCP server (via claude mcp add -s user)")
    else:
        # claude CLI not found or failed — fall back to manual instructions
        print(f"\n  ⚠️  Could not run 'claude mcp add' automatically.")
        print(f"  Run this manually to register Cortex with Claude Code:")
        print(f"    claude mcp add -s user --transport http cortex {mcp_url}\n")

    # Claude Code global instructions: ~/.claude/CLAUDE.md
    # Resolve to Windows home if running in WSL
    if platform.system() == "Linux" and "microsoft" in platform.uname().release.lower():
        win_home = os.environ.get("USERPROFILE") or os.environ.get("HOMEDRIVE", "C:") + os.environ.get("HOMEPATH", "\\Users\\User")
        claude_dir = Path(win_home) / ".claude"
    else:
        claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(exist_ok=True)

    claude_md = claude_dir / "CLAUDE.md"
    if not claude_md.exists() or args.force:
        claude_md.write_text(MEMORY_INSTRUCTIONS, encoding="utf-8")
        created.append(f"{claude_md} (Claude Code — global memory instructions)")

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
    from . import __version__
    parser = argparse.ArgumentParser(prog="cortex", description="Cortex — persistent AI memory")
    parser.add_argument("--version", action="version", version=f"cortex-brain {__version__}")
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

    sub.add_parser("update", help="Check for updates and upgrade cortex-brain")

    svc_p = sub.add_parser("service", help="Manage Cortex as a background service")
    svc_sub = svc_p.add_subparsers(dest="service_command")
    svc_install = svc_sub.add_parser("install", help="Install Cortex as a system service (auto-start on login)")
    svc_install.add_argument("--port", type=int, default=7700)
    svc_sub.add_parser("uninstall", help="Remove the Cortex system service")
    svc_sub.add_parser("status", help="Show service status")

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "search": cmd_search,
        "note": cmd_note,
        "context": cmd_context,
        "distill": cmd_distill,
        "build-context": cmd_build_context,
    }

    if args.command == "update":
        cmd_update(args)
    elif args.command == "mcp" and args.mcp_command == "serve":
        cmd_serve(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "init-project":
        cmd_init_project(args)
    elif args.command == "init-global":
        cmd_init_global(args)
    elif args.command == "service":
        cmd_service(args)
    elif args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
