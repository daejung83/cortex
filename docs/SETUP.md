# Cortex Setup Guide

Complete setup instructions for all supported AI tools.

---

## Prerequisites

- Python 3.11+

### Install

**macOS / Linux:**
```bash
pip install cortex-brain
# cortex command available immediately in your terminal
```

**Windows:**
```powershell
pip install cortex-brain
# If 'cortex' is not recognized, use this instead for all commands:
python -m cortex_core.cli
```

> **Windows PATH tip:** The installer warns `cortex.exe is installed in ... which is not on PATH`.
> Fix it permanently — run this once in PowerShell then restart:
> ```powershell
> $p = python -m site --user-scripts
> [Environment]::SetEnvironmentVariable("PATH","$env:PATH;$p","User")
> ```
> Or use `python -m cortex_core.cli` as a drop-in for every `cortex` command in this guide.

---

## Step 1 — Initialize Your Brain

**macOS / Linux:**
```bash
cortex init
```

**Windows:**
```powershell
python -m cortex_core.cli init
```

Interactive prompts (3 questions + LLM choice):
- **Name** — how the AI addresses you
- **Role** — what you do (developer, designer, founder, etc.)
- **Current focus** — what you're working on right now
- **LLM curation** — choose Ollama / OpenAI / Anthropic / skip (arrow keys)

> Timezone is auto-detected from your system.
> Tech stack is learned by the AI over time — no need to type it.

What gets created:
```
~/.cortex/
├── .env                   ← secrets file (LLM keys go here)
└── brain/
    ├── SOUL.md            ← AI identity + behavior rules
    ├── always-on.md       ← your name, role, focus
    ├── active-context.md  ← rebuilt every 30min
    ├── short-term/        ← daily timestamped notes
    └── long-term/         ← curated permanent memory
```

Example session:
```
  ╔═══════════════════════════════════════╗
  ║   🧠  Cortex — Brain Setup            ║
  ╚═══════════════════════════════════════╝

? Your name: Derek
? Your role / what you do: Developer / founder
? What are you currently working on?: Building a real estate SaaS

? Choose your curation mode: (Use arrow keys)
 ❯ Ollama — local, free, no API key
   OpenAI — gpt-5.4-nano, ~$0.001/day
   Anthropic — claude-haiku, ~$0.001/day
   Skip — heuristic mode, free, always works

  Brain ready at ~/.cortex/brain
  Run: cortex start
  Dashboard: http://localhost:7700
```

---

## Step 2 — Start the Server

```bash
cortex start
```

Open `http://localhost:7700` to see your dashboard.

### Auto-start on login (recommended)

**macOS:**
```bash
cortex service install
```
Installs `~/Library/LaunchAgents/ai.cortex.brain.plist`. Starts now and on every login. Restarts automatically if it crashes.
```bash
cortex service status      # check if running
cortex service uninstall   # remove
tail -f ~/.cortex/cortex.log  # view logs
```

**Linux:**
```bash
cortex service install
```
Installs `~/.config/systemd/user/cortex.service`. Enabled for your user — no sudo needed.
```bash
cortex service status                    # check
cortex service uninstall                 # remove
journalctl --user -u cortex -f          # view logs
```

**Windows:**
```powershell
python -m cortex_core.cli service install
```
Writes a `.bat` to your Windows Startup folder — runs on login without admin rights.
```powershell
python -m cortex_core.cli service status
python -m cortex_core.cli service uninstall
```

---

## Step 3 — Connect Your AI Tools

### Option A: Global Setup (recommended)

One command, works in every project forever:

**macOS / Linux:**
```bash
cortex init-global
```

**Windows:**
```powershell
python -m cortex_core.cli init-global
```

Creates:
- `~/.claude/.mcp.json` — Claude Code MCP registration
- `~/.claude/CLAUDE.md` — Claude Code memory instructions
- `~/.cursor/rules/cortex.md` — Cursor global rules

Then restart your AI tools.

### Option B: Per-Project Setup

**macOS / Linux:**
```bash
cd /path/to/my-project
cortex init-project
```

**Windows:**
```powershell
cd F:\Projects\my-project
python -m cortex_core.cli init-project
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
- **Linux:** `~/.config/Claude/claude_desktop_config.json` or `~/.claude.json`

> **Note:** Claude Desktop on Linux may not be officially supported. Check your installation for the config file location.

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

### Using the secrets file (recommended — keeps keys out of project dirs)

Edit `~/.cortex/.env` (created automatically on `cortex init`):

```bash
# ~/.cortex/.env — never commit this file

# Option A: Local Ollama (free — recommended for Claude Code/Desktop subscribers)
# Install Ollama: https://ollama.ai → then: ollama pull llama3.2
CORTEX_LLM_PROVIDER=ollama
CORTEX_LLM_MODEL=llama3.2

# Option B: OpenAI gpt-5.4-nano (~pennies/month)
CORTEX_LLM_PROVIDER=openai
CORTEX_LLM_API_KEY=sk-...

# Option C: Anthropic claude-haiku
# Requires a separate Anthropic API account — NOT your Claude subscription
CORTEX_LLM_PROVIDER=anthropic
CORTEX_LLM_API_KEY=sk-ant-...
```

Cortex loads `~/.cortex/.env` automatically on start. Never put API keys in project files.

> **After editing `.env`:** stop Cortex (`Ctrl+C`) and run `cortex start` again — changes are only loaded on startup.

### Using environment variables

```bash
export CORTEX_LLM_PROVIDER=openai
export CORTEX_LLM_API_KEY=sk-...
cortex start
```

> ⚠️ **Claude Code/Desktop subscriptions** use OAuth, not API keys — they can't be used for background curation. Use Ollama (local, free) instead.

---

## How Notes Work

Notes are the core of Cortex memory. When the AI calls `log_note()`, it writes a timestamped entry to today's short-term file:

```markdown
## 14:23 | decision
Decided to use Railway over Heroku — Python backends need long-running processes.
```

Notes flow through the entire memory pipeline:

```
log_note()
    ↓
short-term/YYYY-MM-DD.md     ← raw timestamped entry

Active-context rebuild (every 30min)
    ↓
active-context.md            ← last 48hrs distilled, auto-loaded every session

On-demand search
    ↓
search_brain("query", days=7) ← AI searches when you reference past work

After 30 days (promote-on-prune)
    ↓
long-term/decisions.md       ← decision entries promoted here
long-term/insights.md        ← insight entries promoted here
long-term/summaries/YYYY-MM  ← session summaries promoted here

Forever
    ↓
search_long_term("query")    ← finds promoted entries across all time
```

**Entry types and what they do:**

| Type | When to use | Promoted to |
|------|-------------|-------------|
| `decision` | Any choice made | `long-term/decisions.md` |
| `progress` | Work completed | Project file (via `update_project`) |
| `insight` | Lesson learned | `long-term/insights.md` |
| `next_steps` | What's queued | Discarded at 30 days (stale) |
| `context` | Background info | Discarded at 30 days |
| `session_summary` | End of session | `long-term/summaries/YYYY-MM.md` |

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
