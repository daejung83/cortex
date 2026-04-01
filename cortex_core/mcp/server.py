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
            "Get your current active context and always-on memory. "
            "Call this at the start of any session to orient the AI on your current projects and focus."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_brain",
        "description": "Search across all your brain files (short-term notes, long-term memory, projects, decisions).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "max_results": {"type": "integer", "default": 8, "description": "Max results to return"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_projects",
        "description": "Get the full projects file — active projects, their current state, and what's in progress.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_decisions",
        "description": "Get key decisions and their rationale.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_long_term",
        "description": "Get any long-term memory file by topic name (e.g. 'people', 'projects', 'decisions', or any custom topic).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic name (filename without .md)"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "log_note",
        "description": "Save a note, decision, or insight to today's brain file. Use this to capture anything worth remembering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The note to save"},
                "heading": {"type": "string", "description": "Optional section heading"},
            },
            "required": ["content"],
        },
    },
]


def call_tool(name: str, args: dict) -> str:
    manager, searcher = get_brain()

    if name == "get_context":
        always_on = manager.read_always_on()
        active = manager.read_active_context()
        return f"## Always-On Context\n\n{always_on}\n\n---\n\n## Active Context\n\n{active}"

    elif name == "search_brain":
        query = args.get("query", "")
        max_results = args.get("max_results", 8)
        results = searcher.search(query, max_results=max_results)
        if not results:
            return f"No results found for: {query}"
        lines = [f"**Search: {query}** — {len(results)} results\n"]
        for r in results:
            lines.append(f"📄 `{r.file.name}` (line {r.line_no}) — **{r.heading}**\n> {r.snippet}\n")
        return "\n".join(lines)

    elif name == "get_projects":
        return manager.read_long_term("projects")

    elif name == "get_decisions":
        return manager.read_long_term("decisions")

    elif name == "get_long_term":
        topic = args.get("topic", "")
        return manager.read_long_term(topic)

    elif name == "log_note":
        content = args.get("content", "")
        heading = args.get("heading")
        manager.append_to_today(content, heading)
        return f"✅ Note saved to {manager.today_file().name}"

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
