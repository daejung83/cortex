# Cortex Setup Guide

Complete setup instructions for all supported AI tools.

---

## Prerequisites

- Python 3.11+
- `pip install cortex-brain`
- Cortex server running: `cortex start`

> **Windows users:** If `cortex` isn't on PATH, use `python -m cortex_core.cli` instead.

---

## Step 1 — Initialize Your Brain

```bash
cortex init
```

Interactive prompts:
- **Name** — how the AI addresses you
- **Role** — what you do (developer, designer, founder, etc.)
- **Current focus** — what you're working on right now
- **Tech stack** — your main tools/languages
- **Timezone** — for time-aware context

Creates `~/.cortex/brain/` with:
- `SOUL.md` — AI identity and mandatory behavior rules
- `always-on.md` — your permanent context
- `active-context.md` — rebuilt automatically
- `short-term/`, `long-term/` directories

---

## Step 2 — Start the Server

```bash
cortex start
```

Output:
```
🧠 Cortex running at http://127.0.0.1:7700
   Dashboard  → http://127.0.0.1:7700
   MCP server → http://127.0.0.1:7700/mcp
   Brain path → ~/.cortex/brain
```

Open `http://localhost:7700` to see your dashboard.

Keep the server running while using AI tools. To auto-start on login, add it to your shell profile or use a process manager.

---

## Step 3 — Connect Your AI Tools

### Option A: Global Setup (recommended)

One command, works in every project forever:

```bash
cortex init-global
```

Creates:
- `~/.claude/.mcp.json` — Claude Code MCP registration
- `~/.claude/CLAUDE.md` — Claude Code memory instructions
- `~/.cursor/rules/cortex.md` — Cursor global rules

Then restart your AI tools.

### Option B: Per-Project Setup

Run inside any project folder:

```bash
cd /path/to/my-project
cortex init-project
```

Creates in the project root:
- `.mcp.json` — Claude Code project MCP
- `CLAUDE.md` — Claude Code instructions
- `AGENTS.md` — cross-tool standard (works with Cursor, Codex, Gemini, Copilot)
- `.cursorrules` — Cursor legacy format
- `.windsurfrules` — Windsurf project rules

---

## Claude Code (CLI) — Detailed Setup

### Global (recommended)

```bash
cortex init-global
```

Or manually create `~/.claude/.mcp.json`:
```json
{
  "mcpServers": {
    "cortex": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:7700/mcp"
    }
  }
}
```

And `~/.claude/CLAUDE.md` with the memory instructions (see below).

### Project-scoped

```bash
cd my-project
cortex init-project
```

Or manually create `.mcp.json` in your project root with the same JSON above.

### ⚠️ Common Mistake

Do NOT put `mcpServers` in `settings.json`. Claude Code silently ignores it there.
Always use `.mcp.json` (either global `~/.claude/.mcp.json` or project-root `.mcp.json`).

### Verify it works

In Claude Code:
```
/mcp
```
You should see `cortex` listed. If not, restart Claude Code.

---

## Claude Desktop — Detailed Setup

Edit your config file:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cortex": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:7700/mcp"
    }
  }
}
```

Restart Claude Desktop.

To auto-load memory, start each session with:
> "Load my cortex context"

---

## Cursor — Detailed Setup

### Global rules

`cortex init-global` creates `~/.cursor/rules/cortex.md` automatically.

Or manually create `~/.cursor/rules/cortex.md` with the memory instructions below.

### Project rules

`cortex init-project` creates `.cursor/rules/cortex.md` (and `.cursorrules` for legacy support).

### Add MCP server

1. Open Cursor Settings (`Ctrl+,`)
2. Search for "MCP"
3. Add server:
```json
{
  "cortex": {
    "type": "streamable-http",
    "url": "http://127.0.0.1:7700/mcp"
  }
}
```
4. Restart Cursor

---

## Windsurf — Detailed Setup

### Project rules

`cortex init-project` creates `.windsurfrules` in your project root automatically.

Windsurf reads `.windsurfrules` at the start of every session — no further setup needed.

### Global rules (manual — UI only)

Windsurf global rules cannot be set via a file. Set them in the UI:

1. Open Windsurf
2. Click the **gear icon** (Settings)
3. Go to **AI** → **Global Rules** (or **Cascade** → **Rules**)
4. Paste the memory instructions below
5. Save

### Add MCP server in Windsurf

1. Open Windsurf Settings
2. Go to **MCP Servers** (or search "MCP")
3. Add server:
```json
{
  "cortex": {
    "type": "streamable-http",
    "url": "http://127.0.0.1:7700/mcp"
  }
}
```
4. Restart Windsurf

---

## Memory Instructions (copy-paste)

Use this text for CLAUDE.md, .cursorrules, .windsurfrules, AGENTS.md, or any rules file:

```
# Memory Instructions (Cortex)
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
```

---

## LLM Curation Setup

By default Cortex uses heuristic curation (free, no API key). To enable AI curation:

```bash
# Local Ollama (free — recommended for Claude subscribers)
# Install: https://ollama.ai → ollama pull llama3.2
export CORTEX_LLM_PROVIDER=ollama

# OpenAI gpt-5.4-nano (~pennies/month)
export CORTEX_LLM_PROVIDER=openai
export CORTEX_LLM_API_KEY=sk-...

# Anthropic claude-haiku (requires separate API account, not Claude subscription)
export CORTEX_LLM_PROVIDER=anthropic
export CORTEX_LLM_API_KEY=sk-ant-...
```

Then `cortex start` as normal. The dashboard will show LLM curation as active.

---

## Troubleshooting

**Cortex not showing in /mcp (Claude Code)**
- Check `.mcp.json` exists at `~/.claude/.mcp.json` or project root
- Confirm it has `"type": "streamable-http"` — older format without `type` may not work
- Restart Claude Code fully (not just reload)

**Server not reachable**
- Make sure `cortex start` is running
- Test: `curl http://127.0.0.1:7700/api/status`
- If port 7700 is taken: `cortex start --port 7800`

**get_context() not called automatically**
- Expected — MCP tools are passive, AI decides when to call them
- Fix: ensure your CLAUDE.md / .cursorrules / .windsurfrules has the memory instructions
- The instructions tell the AI to call get_context() at session start

**Brain path**
- Default: `~/.cortex/brain/`
- Override: `export CORTEX_BRAIN_PATH=/path/to/brain`
- Dashboard shows current brain path in the sidebar footer
