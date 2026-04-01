# Cortex 🧠

**Persistent memory for AI — across every tool, every session.**

Your AI forgets everything between sessions. Cortex fixes that.

One install. One brain. Works with Claude Code, Claude Desktop, Cursor, Windsurf, and any MCP-compatible tool.

---

## The Problem

Every AI session starts from zero. You re-explain your stack, your project names, what you decided last week — over and over. Claude Projects and ChatGPT Memory help within one tool, but switch tools and you're back to square one.

## What Cortex Does

- **Persistent brain files** — plain markdown you own and can read/edit
- **Auto-curation** — distills sessions into long-term memory automatically
- **MCP server** — plugs into any AI tool via the Model Context Protocol
- **SOUL.md** — define who your AI is and what it must always do
- **Learnings** — AI builds a profile of your preferences over time
- **One command setup** — `cortex init-global` connects every tool at once

---

## Installation

```bash
pip install cortex-brain
```

> **Windows users:** `cortex` may not be on PATH after install. Use `python -m cortex_core.cli` instead of `cortex` in all commands below.

---

## First-Time Setup

### Step 1 — Initialize your brain

```bash
cortex init
```

This creates your brain directory at `~/.cortex/brain/` and runs an interactive setup:
- Your name, role, timezone
- Current focus / active project
- Your tech stack

You can edit these anytime in `~/.cortex/brain/always-on.md`.

### Step 2 — Start the server

```bash
cortex start
```

This starts:
- **Dashboard** at `http://localhost:7700` — view/search your brain, edit SOUL.md
- **MCP server** at `http://localhost:7700/mcp` — connects to AI tools
- **Curation agent** — rebuilds active-context every 30min in the background

Keep this running while you work. Add it to your startup if you want it always available.

### Step 3 — Connect your AI tools

```bash
# One-time global setup — works in every project forever
cortex init-global

# Or per-project (run in your project folder)
cortex init-project
```

Then restart your AI tool and you're done.

---

## Connecting AI Tools

### Claude Code (CLI)

Claude Code reads MCP config from `~/.claude/.mcp.json` (global) or `.mcp.json` in your project root.

**Recommended: Use the command**
```bash
cortex init-global
```

This creates:
- `~/.claude/.mcp.json` — registers Cortex as an MCP server
- `~/.claude/CLAUDE.md` — instructs Claude to load your memory every session

> ⚠️ **Common mistake:** Do NOT add `mcpServers` to `settings.json` — Claude Code silently ignores it there. Always use `.mcp.json`.

**Manual setup** — create `~/.claude/.mcp.json`:
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

And create `~/.claude/CLAUDE.md`:
```markdown
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

**Restart Claude Code** after saving the config.

---

### Claude Desktop

Add to your config file:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`

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

Restart Claude Desktop. Cortex will appear in your tools list.

To auto-load memory each session, start your conversation with:
> "Load my cortex context"

---

### Cursor

**Global rules (recommended — works in every project):**

`cortex init-global` creates `~/.cursor/rules/cortex.md` automatically.

Or manually create `~/.cursor/rules/cortex.md` with the memory instructions (see Claude Code section above).

**Project-scoped:**

Run `cortex init-project` in your project folder. This creates `.cursor/rules/cortex.md` for that project.

Or manually create `.cursorrules` in your project root with the memory instructions.

**Add MCP server in Cursor:**

Go to Cursor Settings → MCP → Add server:
```json
{
  "cortex": {
    "type": "streamable-http",
    "url": "http://127.0.0.1:7700/mcp"
  }
}
```

Restart Cursor after saving.

---

### Windsurf

**Project rules:**

Run `cortex init-project` in your project folder. This creates `.windsurfrules` automatically.

Or manually create `.windsurfrules` in your project root with the memory instructions.

**Global rules (Windsurf — manual only):**

Windsurf global rules are configured in the UI, not via a file. To set them:

1. Open Windsurf
2. Go to **Settings** (gear icon) → **AI** → **Global Rules**
3. Paste the memory instructions:

```
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
```

**Add MCP server in Windsurf:**

Go to Windsurf Settings → MCP Servers → Add:
```json
{
  "cortex": {
    "type": "streamable-http",
    "url": "http://127.0.0.1:7700/mcp"
  }
}
```

---

## LLM Curation (Optional)

By default Cortex uses smart heuristic curation — free, no API key, works well for most users.

To enable AI-powered distillation (smarter active-context rebuilds):

```bash
# Option A: Local Ollama — free, no API key (best for Claude Code/Desktop subscribers)
# 1. Install Ollama: https://ollama.ai
# 2. Run: ollama pull llama3.2
export CORTEX_LLM_PROVIDER=ollama

# Option B: OpenAI gpt-5.4-nano — $0.20/1M tokens, ~pennies/month
export CORTEX_LLM_PROVIDER=openai
export CORTEX_LLM_API_KEY=sk-...

# Option C: Anthropic claude-haiku (requires separate Anthropic API account)
export CORTEX_LLM_PROVIDER=anthropic
export CORTEX_LLM_API_KEY=sk-ant-...

# Override default model
export CORTEX_LLM_MODEL=llama3.1  # or any model name
```

Then start Cortex normally:
```bash
cortex start
```

> ⚠️ **Claude Code/Desktop subscriptions** use OAuth auth, not API keys. They **cannot** be used for background curation. Use Ollama (local, free) instead.

---

## How It Works

```
Session start
    AI calls get_context()         loads SOUL.md + always-on + active-context (~1,500 tokens)
    AI calls get_learnings()       loads your AI profile

During session
    AI calls log_note()            saves decisions/progress/insights immediately with timestamp
    AI calls update_project()      keeps project state current

Before compact / session end
    AI calls save_session_summary() structured summary saved to short-term
    AI calls update_project()       for every project touched

Next session
    get_context() loads fresh active-context
    AI picks up exactly where you left off

After 30 days
    Curation agent promotes decisions + insights to long-term/
    Short-term file deleted — nothing important lost
    search_long_term() finds old promoted content forever
```

---

## Brain Structure

```
~/.cortex/brain/
├── SOUL.md                        ← AI identity + mandatory tool call rules (editable)
├── always-on.md                   ← permanent context: name, stack, focus
├── active-context.md              ← last 48hrs distilled (auto-rebuilt every 30min)
├── short-term/
│   ├── 2026-04-01.md              ← today's timestamped notes
│   ├── 2026-03-31.md              ← yesterday
│   └── ...                        ← pruned after 30 days (important stuff promoted first)
└── long-term/
    ├── projects/
    │   ├── _index.md              ← one-line status per project (fast overview)
    │   ├── cortex.md              ← current state only, ~15 lines max
    │   └── my-saas.md
    ├── decisions.md               ← major decisions log (last 90 days by default)
    ├── insights.md                ← lessons learned (promoted from short-term)
    ├── learnings.md               ← AI-maintained user profile
    └── summaries/
        ├── 2026-04.md             ← monthly session summaries
        └── 2026-03.md
```

---

## Available MCP Tools

| Tool | When AI calls it | What it does |
|------|-----------------|--------------|
| `get_context()` | Start of every session | Loads SOUL.md + always-on + active-context |
| `get_learnings()` | Start of session | Loads AI-maintained user profile |
| `search_brain(query, days?)` | User references past work | Keyword search, optionally scoped to N days |
| `search_long_term(query)` | Finding old content (>30 days) | Searches only long-term promoted files |
| `log_note(content, type)` | Immediately on decision/progress/insight | Timestamped entry in today's short-term |
| `save_session_summary(...)` | Before compact or session end | Structured summary with decisions + next steps |
| `update_project(name, status, ...)` | When project state changes | Overwrites project file with current state (merge-safe) |
| `log_decision(decision, rationale)` | Major architectural decisions | Appends to long-term/decisions.md |
| `update_learning(category, insight)` | New user patterns observed | Updates learnings.md, never grows |
| `get_projects()` | User asks about projects | Returns _index.md — fast one-line overview |
| `get_project(name)` | User asks about specific project | Returns full project file |
| `get_decisions(days?)` | User asks what was decided | Last 90 days by default, days=0 for all |
| `get_summary(month)` | User asks about a past month | Returns YYYY-MM monthly summary |
| `get_long_term(topic)` | Any other long-term topic | Returns that topic file |

---

## Token Usage

| Scenario | No Brain | Cortex |
|----------|---------|--------|
| Session start | Re-explain ~500 tokens every time | ~1,500 tokens loaded automatically |
| After compaction | Starts from zero | Picks up from active-context |
| Past decisions | Gone | Searchable in long-term |
| Cross-tool memory | ❌ | ✅ Same brain everywhere |
| Cost over 30 days | ~40k tokens wasted on re-explanation | ~42k tokens (all useful) |

---

## CLI Reference

```bash
cortex init                  # Initialize brain (interactive setup)
cortex start                 # Start server + dashboard + curation agent
cortex init-global           # Connect all AI tools globally (one-time)
cortex init-project          # Connect AI tools to current project folder
cortex search <query>        # Search brain from terminal
cortex note "text"           # Add note to today's brain file
cortex context               # Print active context
cortex distill --days 3      # Distill recent sessions (with LLM if configured)
cortex build-context         # Rebuild active-context.md manually
cortex mcp serve             # MCP server only (no dashboard)
```

---

## Status

🚧 **Early development** — not ready for public use yet.

---

Built with ❤️ by [@daejung83](https://github.com/daejung83)
