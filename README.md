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
- **MCP server** — plugs into Claude Desktop, Cursor, Windsurf, and anything MCP-compatible
- **Cross-tool** — one memory layer for all your AI tools

## How It Works

```
You talk to Claude/Cursor/ChatGPT
        ↓
AI queries Cortex MCP for context
        ↓
AI responds with full project awareness
        ↓
Session distilled → brain files updated
        ↓
Next session picks up exactly where you left off
```

## The Brain Format

Cortex uses plain markdown files — readable, editable, version-controllable:

```
brain/
├── short-term/
│   └── 2026-04-01.md      # Today's raw session notes
├── long-term/
│   ├── projects.md        # Active projects + status
│   ├── decisions.md       # Key decisions + rationale
│   └── people.md          # People + relationships
├── active-context.md      # Hot context (rebuilt every 6hrs)
└── always-on.md           # Permanent always-loaded context
```

## Quick Start

```bash
pip install cortex-brain

cortex init
cortex mcp serve          # Start MCP server on localhost:7700
```

Then add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cortex": {
      "url": "http://localhost:7700/mcp"
    }
  }
}
```

Ask Claude: *"What am I currently working on?"* — it will know.

## Repo Structure

```
cortex-core/     # Open source: brain format, search, MCP server
cortex-cloud/    # Hosted service: API, dashboard, curation agent
docs/            # Spec, guides, examples
examples/        # Sample brain files, integrations
```

## Status

🚧 **Early development** — not ready for public use yet.

---

Built with ❤️ by [@daejung83](https://github.com/daejung83)
