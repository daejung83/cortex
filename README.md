# Cortex 🧠

**Persistent memory for AI — across every tool, every session.**

Your AI forgets everything between sessions. Cortex fixes that.

Connect Cortex to Claude, Cursor, ChatGPT, or any MCP-compatible tool. Your AI instantly knows your projects, decisions, and context — without you re-explaining anything.

---

## The Problem

Every AI session starts from zero. You explain your stack, your project names, your decisions — over and over. Claude Projects, ChatGPT Memory, and similar tools help within one product, but the moment you switch tools, you're starting over.

## What Cortex Does

- **Persistent brain files** — structured, human-readable markdown you own
- **Auto-curation** — an agent distills sessions into long-term memory automatically
- **MCP server** — plugs into Claude Desktop, Claude Code, Cursor, Windsurf, and anything MCP-compatible
- **Cross-tool** — one memory layer for all your AI tools
- **SOUL.md** — define who your AI is and what it must always do

## Quick Start

```bash
pip install cortex-brain
cortex init        # interactive setup — name, projects, stack
cortex start       # dashboard + MCP server at http://localhost:7700
```

---

## Connect to Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

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

---

## Connect to Claude Code (CLI)

Claude Code reads MCP config from `~/.claude/.mcp.json` (global) or `.mcp.json` in your project root (project-scoped).

**Option 1 — CLI command (recommended):**
```bash
claude mcp add cortex --transport http http://127.0.0.1:7700/mcp
```

**Option 2 — Manual:** Create `~/.claude/.mcp.json`:
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

> ⚠️ **Do not put `mcpServers` in `settings.json`** — Claude Code silently ignores it there.

**Auto-load context on every session:** Create a `CLAUDE.md` in your project root:
```markdown
# MCP Instructions
At the start of every session, call cortex:get_context() and cortex:get_learnings()
before responding to anything. This loads your persistent memory.
```

---

## Connect to Cursor / Windsurf

In Cursor settings → MCP → Add server:
```json
{
  "cortex": {
    "type": "streamable-http",
    "url": "http://127.0.0.1:7700/mcp"
  }
}
```

---

## How It Works

```
You talk to Claude/Cursor/etc
        ↓
AI calls get_context() — loads your brain (~1,500 tokens)
        ↓
AI responds with full project awareness
        ↓
AI calls log_note() for decisions/progress during session
        ↓
Before compact/end: save_session_summary() + update_project()
        ↓
Next session picks up exactly where you left off
```

## The Brain Format

```
brain/
├── SOUL.md                    ← AI identity + mandatory tool call rules
├── always-on.md               ← permanent context (your name, stack, focus)
├── active-context.md          ← last 48hrs distilled (auto-rebuilt)
├── short-term/
│   └── YYYY-MM-DD.md          ← timestamped daily notes
└── long-term/
    ├── projects/
    │   ├── _index.md          ← one-line status per project
    │   └── <project>.md       ← current state, ~15 lines max
    ├── decisions.md           ← major decisions log
    ├── insights.md            ← lessons learned (promoted from short-term)
    ├── learnings.md           ← AI-maintained user profile
    └── summaries/
        └── YYYY-MM.md         ← monthly session summaries
```

## Available MCP Tools

| Tool | When AI calls it |
|------|-----------------|
| `get_context()` | Start of every session |
| `get_learnings()` | Start of session — loads your AI profile |
| `search_brain(query, days?)` | User references past work |
| `search_long_term(query)` | Finding old decisions/insights (>30 days) |
| `log_note(content, type)` | Immediately on any decision/progress/insight |
| `save_session_summary()` | Before compact or session end |
| `update_project(name, status)` | When project state changes |
| `log_decision(decision)` | Major architectural/strategic decisions |
| `update_learning(category, insight)` | When new user patterns observed |
| `get_projects()` | Project index overview |
| `get_decisions(days?)` | Decisions log (default: last 90 days) |
| `get_summary(month)` | Monthly history (YYYY-MM) |

## Token Usage

| | No Brain | Cortex |
|--|---------|--------|
| Session baseline | 0 (re-explain ~500 tokens each time) | ~1,500 tokens loaded automatically |
| Cross-tool memory | ❌ | ✅ |
| Survives compaction | ❌ | ✅ |
| Old decisions findable | ❌ | ✅ (promoted to long-term) |

## Status

🚧 **Early development** — not ready for public use yet.

---

Built with ❤️ by [@daejung83](https://github.com/daejung83)
