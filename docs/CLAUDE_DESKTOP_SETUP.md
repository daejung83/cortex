# Connect Cortex to Claude Desktop

## 1. Install Cortex

```bash
pip install cortex-brain
```

## 2. Initialize your brain

```bash
cortex init
```

This creates `~/.cortex/brain/` with the default structure.

## 3. Start the MCP server

```bash
cortex mcp serve
# 🧠 Cortex MCP server running at http://127.0.0.1:7700/mcp
```

## 4. Add to Claude Desktop config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "cortex": {
      "url": "http://127.0.0.1:7700/mcp"
    }
  }
}
```

## 5. Restart Claude Desktop

Claude will now have access to your brain. Try asking:

> "What am I currently working on?"
> "What decisions have I made recently?"
> "Search my notes for anything about [project name]"

## Custom brain path

```bash
export CORTEX_BRAIN_PATH=/path/to/your/brain
cortex mcp serve
```
