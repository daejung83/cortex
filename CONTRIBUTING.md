# Contributing to Cortex

Thanks for trying Cortex! Here's how to report issues and contribute.

## Reporting Bugs

[Open an issue on GitHub](https://github.com/daejung83/cortex/issues)

Please include:
- **OS:** Windows / macOS / Linux (+ version)
- **Python version:** `python --version`
- **Cortex version:** `cortex --version` or check `cortex_core/__init__.py`
- **What you did:** step-by-step
- **What happened:** exact error message or output
- **What you expected:** what should have happened

## Common Issues

**`cortex` not found on Windows**
```powershell
$p = python -m site --user-scripts
[Environment]::SetEnvironmentVariable("PATH","$env:PATH;$p","User")
# Restart PowerShell
```

**Port 7700 already in use**
```bash
cortex start --port 7800
```

**Brain path issues**
```bash
export CORTEX_BRAIN_PATH=/path/to/your/brain
cortex start
```

**Arrow keys not working in cortex init**
Questionary requires a real TTY. If running in a non-interactive terminal, it falls back to plain text input automatically.

## Feature Requests

[Open a discussion](https://github.com/daejung83/cortex/discussions) — describe the use case and what you'd expect it to do.

## Development Setup

```bash
git clone https://github.com/daejung83/cortex.git
cd cortex
pip install -e ".[dev]"
```

The package is in `cortex_core/`. Key files:
- `cortex_core/mcp/server.py` — MCP tools
- `cortex_core/brain/manager.py` — brain file read/write
- `cortex_core/server.py` — unified server + dashboard
- `cortex_core/cli.py` — all CLI commands
- `cortex_core/agent/curator.py` — background curation agent

Run locally:
```bash
cortex init
cortex start
```
