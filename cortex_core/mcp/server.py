"""
Cortex MCP Server
-----------------
Exposes brain files as MCP tools for Claude Desktop, Cursor, and any
MCP-compatible AI assistant.

Tools exposed:
  get_context         → returns active-context.md + always-on.md
  search_brain        → keyword/semantic search across all brain files
  get_projects        → returns long-term/projects.md
  get_decisions       → returns long-term/decisions.md
  get_long_term       → returns any long-term topic file
  log_note            → append a note to today's short-term file

Run:
    cortex mcp serve                    # default port 7700
    cortex mcp serve --port 8080
"""

import os
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from ..brain.schema import BrainConfig
from ..brain.manager import BrainManager
from ..search.searcher import BrainSearcher

app = FastAPI(title="Cortex MCP", docs_url=None, redoc_url=None, openapi_url=None)

# Sessions (stateless transport)
_sessions: dict[str, dict] = {}


def get_brain() -> tuple[BrainManager, BrainSearcher]:
    brain_path = os.environ.get("CORTEX_BRAIN_PATH", str(Path.home() / ".cortex" / "brain"))
    config = BrainConfig.from_root(brain_path)
    manager = BrainManager(config)
    searcher = BrainSearcher(config)
    return manager, searcher


TOOLS = [
    {
        "name": "get_context",
        "description": (
            "Get current active context and always-on memory. "
            "ALWAYS call this at the start of every session before anything else."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_brain",
        "description": (
            "Search brain files for relevant entries. Use this when the user references "
            "something specific — a project, decision, or past work. "
            "Use 'days' to scope the search to recent memory (e.g. days=7 for last week). "
            "Never dump full context — always search for what's needed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "days": {"type": "integer", "description": "Limit search to last N days (e.g. 7, 14). Omit to search all time."},
                "max_results": {"type": "integer", "default": 8, "description": "Max results to return"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "log_note",
        "description": (
            "Save a note to today's brain file WITH TIMESTAMP. "
            "IMPORTANT: Call this immediately — do not batch or wait until end of session. "
            "Save as soon as a decision is made, work is completed, or insight is gained. "
            "This ensures nothing is lost if the session ends or context is compacted."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The note to save"},
                "type": {
                    "type": "string",
                    "enum": ["decision", "progress", "insight", "next_steps", "context", "question"],
                    "description": "Type of entry: decision=choice made, progress=work done, insight=lesson learned, next_steps=what's queued, context=background info, question=open question",
                },
                "heading": {"type": "string", "description": "Optional custom heading (overrides type)"},
            },
            "required": ["content", "type"],
        },
    },
    {
        "name": "save_session_summary",
        "description": (
            "IMPORTANT: Call this automatically before any context compaction or session reset, "
            "and when the user says they are done or wrapping up. "
            "Saves a structured summary so the next session picks up exactly where this one left off."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "2-3 sentence summary of what happened this session"},
                "decisions": {"type": "array", "items": {"type": "string"}, "description": "Specific decisions made (list)"},
                "progress": {"type": "array", "items": {"type": "string"}, "description": "Work completed (list)"},
                "next_steps": {"type": "array", "items": {"type": "string"}, "description": "What to pick up next session (list)"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "get_projects",
        "description": "Get the project index — all active projects and their current one-line status. Fast overview only. Use get_project(name) for full details on a specific project.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_project",
        "description": "Get full details for a specific project by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name (e.g. 'cortex', 'lotlytics')"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_project",
        "description": (
            "Create or update a project's current state. "
            "IMPORTANT: Call this during compaction for every project touched this session. "
            "Also call whenever a project's status, focus, or next steps change. "
            "This overwrites the project file with current state only — history stays in short-term."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name"},
                "status": {"type": "string", "description": "Current status (e.g. 'In progress', 'Shipped', 'On hold', 'Idea')"},
                "focus": {"type": "string", "description": "What's actively being worked on right now"},
                "next_steps": {"type": "array", "items": {"type": "string"}, "description": "Prioritized list of what's next"},
                "stack": {"type": "string", "description": "Tech stack (optional, only update if changed)"},
                "url": {"type": "string", "description": "Live URL if applicable"},
                "notes": {"type": "string", "description": "Any other important context"},
            },
            "required": ["name", "status"],
        },
    },
    {
        "name": "log_decision",
        "description": (
            "Save an important decision to long-term memory (decisions.md). "
            "Use for significant choices worth remembering across projects and sessions — "
            "architecture decisions, product direction, vendor choices, etc. "
            "For minor decisions, use log_note(type='decision') instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "description": "What was decided"},
                "rationale": {"type": "string", "description": "Why this decision was made"},
                "project": {"type": "string", "description": "Related project name (optional)"},
            },
            "required": ["decision"],
        },
    },
    {
        "name": "get_decisions",
        "description": "Get long-term decisions log.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_learnings",
        "description": "Get everything learned about the user — preferences, patterns, work style. Call this at session start alongside get_context().",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_learning",
        "description": (
            "Update a learning about the user. Call when you observe a consistent pattern — "
            "NOT for one-time events (use log_note for those). "
            "Also call before compact if this session revealed new patterns. "
            "Learnings overwrite, never grow — file stays small forever."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["work_style", "technical", "communication", "decision_patterns", "goals"],
                    "description": "Category of learning",
                },
                "insight": {"type": "string", "description": "The pattern or preference (be specific, e.g. 'prefers Railway over Heroku for Python backends')"},
                "replaces": {"type": "string", "description": "Existing insight this updates or contradicts (optional)"},
            },
            "required": ["category", "insight"],
        },
    },
    {
        "name": "get_long_term",
        "description": "Get any long-term memory file by topic name (e.g. 'people', 'decisions', or any custom topic).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic name (filename without .md)"},
            },
            "required": ["topic"],
        },
    },
]


def call_tool(name: str, args: dict) -> str:
    manager, searcher = get_brain()

    if name == "get_context":
        from ..brain.soul import read_soul
        soul = read_soul(manager.config)
        always_on = manager.read_always_on()
        active = manager.read_active_context()
        return (
            f"{soul}\n\n"
            f"---\n\n## Always-On Context\n\n{always_on}\n\n"
            f"---\n\n## Active Context\n\n{active}"
        )

    elif name == "search_brain":
        query = args.get("query", "")
        max_results = args.get("max_results", 8)
        days = args.get("days")
        results = searcher.search(query, max_results=max_results, days=days)
        if not results:
            scope = f"last {days} days" if days else "all time"
            return f"No results found for '{query}' ({scope})"
        scope = f"last {days} days" if days else "all time"
        lines = [f"**Search: '{query}'** ({scope}) — {len(results)} results\n"]
        for r in results:
            lines.append(f"📄 `{r.file.name}` — **{r.heading}**\n> {r.snippet}\n")
        return "\n".join(lines)

    elif name == "log_note":
        from datetime import datetime
        import re as _re
        content = args.get("content", "")
        entry_type = args.get("type", "context")

        # Privacy check — warn if content looks like secrets
        secret_patterns = [r"sk-[a-zA-Z0-9]{20,}", r"ghp_[a-zA-Z0-9]{20,}", r"ltk_[a-zA-Z0-9]{20,}", r"Bearer [a-zA-Z0-9]{20,}"]
        for pat in secret_patterns:
            if _re.search(pat, content):
                return "⚠️ Note not saved — content appears to contain a secret/API key. Remove sensitive data before logging."

        heading = args.get("heading") or f"{datetime.now().strftime('%H:%M')} | {entry_type}"
        manager.append_to_today(content, heading)
        return f"✅ Saved [{entry_type}] to {manager.today_file().name}"

    elif name == "save_session_summary":
        from datetime import datetime
        summary = args.get("summary", "")
        decisions = args.get("decisions", [])
        progress = args.get("progress", [])
        next_steps = args.get("next_steps", [])

        lines = [summary]
        if decisions:
            lines.append("\n**Decisions:**")
            lines.extend(f"- {d}" for d in decisions)
        if progress:
            lines.append("\n**Progress:**")
            lines.extend(f"- {p}" for p in progress)
        if next_steps:
            lines.append("\n**Next steps:**")
            lines.extend(f"- {n}" for n in next_steps)

        content = "\n".join(lines)
        heading = f"{datetime.now().strftime('%H:%M')} | session_summary"
        manager.append_to_today(content, heading)
        return f"✅ Session summary saved to {manager.today_file().name}"

    elif name == "get_projects":
        return manager.get_project_index()

    elif name == "get_project":
        return manager.get_project(args.get("name", ""))

    elif name == "update_project":
        path = manager.update_project(
            name=args["name"],
            status=args["status"],
            focus=args.get("focus"),
            next_steps=args.get("next_steps"),
            stack=args.get("stack"),
            url=args.get("url"),
            notes=args.get("notes"),
        )
        return f"✅ Project '{args['name']}' updated — index rebuilt"

    elif name == "log_decision":
        manager.log_decision(
            decision=args["decision"],
            rationale=args.get("rationale"),
            project=args.get("project"),
        )
        return f"✅ Decision saved to decisions.md"

    elif name == "get_learnings":
        return manager.get_learnings_with_stale_check()

    elif name == "update_learning":
        return manager.update_learning(
            category=args["category"],
            insight=args["insight"],
            replaces=args.get("replaces"),
        )

    elif name == "get_decisions":
        return manager.read_long_term("decisions")

    elif name == "get_long_term":
        topic = args.get("topic", "")
        return manager.read_long_term(topic)

    return f"Unknown tool: {name}"


def make_response(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def make_error(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method")
    id_ = body.get("id")
    params = body.get("params", {})

    # Session management
    session_id = request.headers.get("mcp-session-id")
    if not session_id:
        session_id = str(uuid.uuid4())

    if method == "initialize":
        _sessions[session_id] = {}
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "cortex", "version": "0.1.0"},
        }
        response = JSONResponse(make_response(id_, result))
        response.headers["mcp-session-id"] = session_id
        return response

    elif method == "tools/list":
        return JSONResponse(make_response(id_, {"tools": TOOLS}))

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            text = call_tool(tool_name, tool_args)
            result = {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}

        def event_stream():
            data = json.dumps(make_response(id_, result))
            yield f"data: {data}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream",
                                  headers={"mcp-session-id": session_id})

    elif method == "notifications/initialized":
        return Response(status_code=202)

    return JSONResponse(make_error(id_, -32601, f"Method not found: {method}"))


def serve(port: int = 7700, host: str = "127.0.0.1"):
    import uvicorn
    print(f"🧠 Cortex MCP server running at http://{host}:{port}/mcp")
    uvicorn.run(app, host=host, port=port)
