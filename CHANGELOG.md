# Changelog

## [0.1.0b2] — 2026-04-02

### Bug fixes
- **WSL fix:** `cortex init-global` now correctly writes Claude Code config to the Windows user home (`C:\Users\<name>\.claude\`) when running from WSL, instead of the Linux home. Claude Code is a Windows app and was silently ignoring the config written to the wrong path.
- **MCP transport:** Ensured `.mcp.json` always includes `"type": "streamable-http"` — without it Claude Code skips the server silently.
- **searcher.py:** `read_text()` now uses `encoding="utf-8", errors="replace"` to prevent cp1252 crashes on Windows.
- **manager.py:** `always-on.md` and `active-context.md` seed files now write with `encoding="utf-8"`.
- **cli.py:** Fixed partial key match bug in `_write_secret()` — keys like `CORTEX_LLM_PROVIDER_EXTRA` no longer clobber `CORTEX_LLM_PROVIDER`.
- **pyproject.toml:** License changed to SPDX string format (`"MIT"`) — removes deprecation warnings during build.

## [0.1.0b1] — 2026-04-01

### First public release

**Core features:**
- Brain file format: `SOUL.md`, `always-on.md`, `active-context.md`, `short-term/`, `long-term/`
- MCP server with 14 tools: `get_context`, `search_brain`, `log_note`, `update_project`, `save_session_summary`, `log_decision`, `update_learning`, and more
- Unified server: dashboard + MCP + REST API in a single `cortex start` command
- Background curation agent: rebuilds `active-context.md` every 30min, daily distillation, promote-on-prune at 30 days

**LLM curation:**
- Heuristic mode (default): free, no API key, priority-sorted rebuilds
- Ollama support: local, free, recommended for Claude subscribers
- OpenAI support: gpt-5.4-nano default (~$0.001/day)
- Anthropic support: claude-haiku-4-5

**CLI:**
- `cortex init` — interactive TUI with arrow key navigation (questionary)
- `cortex start` — unified server with version check
- `cortex service install/uninstall/status` — macOS launchd, Linux systemd, Windows startup
- `cortex init-global` — connects Claude Code, Cursor globally
- `cortex init-project` — connects all AI tools to current project
- `cortex update` — check PyPI and upgrade

**Platform support:**
- Windows: UTF-8 file handling, PATH detection and fix instructions
- macOS: launchd service, `~/.cursor/rules/` global rules
- Linux: systemd user service

**Known issues / beta caveats:**
- `cortex service install` tested on Windows only; macOS/Linux paths written but not verified
- `questionary` arrow keys may not work in all Windows terminals (falls back to plain input)
- Semantic search (sentence-transformers) is optional — keyword search is default
