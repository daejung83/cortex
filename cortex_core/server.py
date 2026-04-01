"""
Cortex Unified Server
---------------------
Single FastAPI app serving:
  GET  /              → dashboard (HTML)
  GET  /api/*         → REST API for dashboard JS
  POST /mcp           → MCP server for Claude/Cursor/etc
  
Start with: cortex start
"""

import os
import uuid
import json
import asyncio
import logging
from pathlib import Path
from datetime import date

from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .brain.schema import BrainConfig
from .brain.manager import BrainManager
from .search.searcher import BrainSearcher
from .curation.distiller import Distiller
from .agent.curator import CurationAgent

logger = logging.getLogger("cortex")

app = FastAPI(title="Cortex", docs_url=None, redoc_url=None, openapi_url=None)

_sessions: dict[str, dict] = {}


def get_config() -> BrainConfig:
    brain_path = os.environ.get("CORTEX_BRAIN_PATH", str(Path.home() / ".cortex" / "brain"))
    return BrainConfig.from_root(brain_path)


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cortex — Your AI Brain</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
      --border: #30363d; --text: #e6edf3; --muted: #8b949e;
      --accent: #58a6ff; --green: #3fb950; --yellow: #d29922;
      --red: #f85149; --purple: #bc8cff;
    }
    body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; min-height: 100vh; }
    
    /* Layout */
    .shell { display: grid; grid-template-columns: 220px 1fr; height: 100vh; }
    .sidebar { background: var(--bg2); border-right: 1px solid var(--border); padding: 0; display: flex; flex-direction: column; }
    .main { overflow-y: auto; }

    /* Sidebar */
    .logo { padding: 20px 16px 16px; border-bottom: 1px solid var(--border); }
    .logo h1 { font-size: 18px; font-weight: 700; color: var(--text); }
    .logo span { font-size: 11px; color: var(--muted); }
    .nav { padding: 12px 8px; flex: 1; }
    .nav-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; color: var(--muted); transition: all 0.1s; border: none; background: none; width: 100%; text-align: left; }
    .nav-item:hover { background: var(--bg3); color: var(--text); }
    .nav-item.active { background: var(--bg3); color: var(--accent); }
    .nav-item .icon { width: 16px; text-align: center; }
    .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); margin-left: auto; animation: pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    .sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--border); font-size: 11px; color: var(--muted); }

    /* Header */
    .page-header { padding: 20px 28px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
    .page-title { font-size: 16px; font-weight: 600; }
    .badge { font-size: 11px; padding: 2px 8px; border-radius: 12px; background: var(--bg3); color: var(--muted); border: 1px solid var(--border); }
    .badge.green { color: var(--green); border-color: var(--green); }

    /* Content */
    .content { padding: 24px 28px; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    
    /* Cards */
    .card { background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
    .card-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
    .card-title { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .card-body { padding: 16px; }
    .card-body pre { font-size: 12px; line-height: 1.7; color: var(--text); white-space: pre-wrap; word-break: break-word; }

    /* Search */
    .search-bar { display: flex; gap: 8px; margin-bottom: 20px; }
    .search-bar input { flex: 1; background: var(--bg2); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: 13px; outline: none; }
    .search-bar input:focus { border-color: var(--accent); }
    .search-bar button { background: var(--accent); color: #000; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }

    /* Search results */
    .result-item { background: var(--bg2); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; margin-bottom: 8px; }
    .result-file { font-size: 11px; color: var(--accent); font-family: monospace; margin-bottom: 4px; }
    .result-heading { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
    .result-snippet { font-size: 12px; color: var(--muted); }

    /* Note form */
    .note-form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
    .note-form input, .note-form textarea { background: var(--bg2); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: 13px; outline: none; font-family: inherit; resize: vertical; }
    .note-form input:focus, .note-form textarea:focus { border-color: var(--accent); }
    .note-form button { align-self: flex-end; background: var(--green); color: #000; border: none; padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }
    .success-msg { color: var(--green); font-size: 12px; }

    /* Files list */
    .file-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border); }
    .file-item:last-child { border-bottom: none; }
    .file-name { font-family: monospace; font-size: 13px; flex: 1; }
    .file-size { font-size: 11px; color: var(--muted); }
    .file-date { font-size: 11px; color: var(--muted); }

    /* Stats */
    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }
    .stat-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
    .stat-value { font-size: 28px; font-weight: 700; color: var(--accent); }
    .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }

    /* MCP config */
    .code-block { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 14px; font-family: monospace; font-size: 12px; line-height: 1.6; color: var(--text); overflow-x: auto; }
    .copy-btn { background: var(--bg3); border: 1px solid var(--border); color: var(--text); padding: 4px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; }
    .copy-btn:hover { border-color: var(--accent); color: var(--accent); }

    /* Loading */
    .loading { color: var(--muted); font-size: 13px; padding: 20px 0; }
    .error { color: var(--red); font-size: 13px; padding: 8px 0; }
  </style>
</head>
<body>
<div class="shell">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="logo">
      <h1>🧠 Cortex</h1>
      <span>Your AI Brain</span>
    </div>
    <nav class="nav">
      <button class="nav-item active" onclick="showTab('context')" id="nav-context">
        <span class="icon">⚡</span> Active Context
        <span class="status-dot"></span>
      </button>
      <button class="nav-item" onclick="showTab('search')" id="nav-search">
        <span class="icon">🔍</span> Search
      </button>
      <button class="nav-item" onclick="showTab('longterm')" id="nav-longterm">
        <span class="icon">📚</span> Long-Term Memory
      </button>
      <button class="nav-item" onclick="showTab('notes')" id="nav-notes">
        <span class="icon">✏️</span> Add Note
      </button>
      <button class="nav-item" onclick="showTab('files')" id="nav-files">
        <span class="icon">📁</span> Brain Files
      </button>
      <button class="nav-item" onclick="showTab('connect')" id="nav-connect">
        <span class="icon">🔌</span> Connect AI
      </button>
    </nav>
    <div class="sidebar-footer">
      Brain: <span id="brain-path-short">~/.cortex/brain</span>
    </div>
  </div>

  <!-- Main -->
  <div class="main">
    <div class="page-header">
      <span class="page-title" id="page-title">Active Context</span>
      <div style="display:flex;gap:8px;align-items:center">
        <span class="badge green" id="agent-status">● Agent running</span>
        <button class="copy-btn" onclick="refreshCurrent()">↻ Refresh</button>
      </div>
    </div>

    <div class="content">

      <!-- Context Tab -->
      <div class="tab-content active" id="tab-context">
        <div class="stats-grid" id="stats">
          <div class="stat-card"><div class="stat-value" id="stat-files">—</div><div class="stat-label">Brain files</div></div>
          <div class="stat-card"><div class="stat-value" id="stat-days">—</div><div class="stat-label">Days of memory</div></div>
          <div class="stat-card"><div class="stat-value" id="stat-topics">—</div><div class="stat-label">Long-term topics</div></div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Always-On Context</span>
            <span class="badge">always loaded</span>
          </div>
          <div class="card-body"><pre id="always-on-content">Loading...</pre></div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Active Context</span>
            <span class="badge">last 48hrs distilled</span>
          </div>
          <div class="card-body"><pre id="active-context-content">Loading...</pre></div>
        </div>
      </div>

      <!-- Search Tab -->
      <div class="tab-content" id="tab-search">
        <div class="search-bar">
          <input type="text" id="search-input" placeholder="Search your brain..." onkeydown="if(event.key==='Enter')doSearch()">
          <button onclick="doSearch()">Search</button>
        </div>
        <div id="search-results"></div>
      </div>

      <!-- Long-Term Tab -->
      <div class="tab-content" id="tab-longterm">
        <div id="longterm-nav" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px"></div>
        <div class="card">
          <div class="card-header">
            <span class="card-title" id="longterm-title">Select a topic</span>
          </div>
          <div class="card-body"><pre id="longterm-content">Select a topic from above.</pre></div>
        </div>
      </div>

      <!-- Notes Tab -->
      <div class="tab-content" id="tab-notes">
        <div class="card">
          <div class="card-header"><span class="card-title">Add Note to Today's Brain</span></div>
          <div class="card-body">
            <div class="note-form">
              <input type="text" id="note-heading" placeholder="Heading (optional)">
              <textarea id="note-content" rows="5" placeholder="What do you want to remember?"></textarea>
              <button onclick="saveNote()">Save Note</button>
            </div>
            <div id="note-status"></div>
          </div>
        </div>
      </div>

      <!-- Files Tab -->
      <div class="tab-content" id="tab-files">
        <div class="card">
          <div class="card-header"><span class="card-title">Short-Term Files</span></div>
          <div class="card-body"><div id="shortterm-files">Loading...</div></div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Long-Term Files</span></div>
          <div class="card-body"><div id="longterm-files">Loading...</div></div>
        </div>
      </div>

      <!-- Connect Tab -->
      <div class="tab-content" id="tab-connect">
        <div class="card">
          <div class="card-header"><span class="card-title">Connect to Claude Desktop</span></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--muted);margin-bottom:12px">Add this to your <code>claude_desktop_config.json</code>:</p>
            <div class="code-block" id="claude-config"></div>
            <button class="copy-btn" style="margin-top:10px" onclick="copyClaudeConfig()">Copy</button>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Connect to Cursor / Windsurf</span></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--muted);margin-bottom:12px">Add to your MCP settings:</p>
            <div class="code-block">{
  "cortex": {
    "url": "http://127.0.0.1:<span id="mcp-port-2">7700</span>/mcp"
  }
}</div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Test Connection</span></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--muted);margin-bottom:12px">MCP server status:</p>
            <div id="mcp-status" class="loading">Checking...</div>
          </div>
        </div>
      </div>

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /shell -->

<script>
const API = '';
let currentTab = 'context';
let port = 7700;

async function api(path, opts={}) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function showTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  document.getElementById('nav-' + tab).classList.add('active');
  currentTab = tab;
  const titles = {context:'Active Context', search:'Search', longterm:'Long-Term Memory', notes:'Add Note', files:'Brain Files', connect:'Connect AI'};
  document.getElementById('page-title').textContent = titles[tab];
  loadTab(tab);
}

function refreshCurrent() { loadTab(currentTab); }

async function loadTab(tab) {
  if (tab === 'context') await loadContext();
  else if (tab === 'longterm') await loadLongTerm();
  else if (tab === 'files') await loadFiles();
  else if (tab === 'connect') await loadConnect();
}

async function loadContext() {
  try {
    const d = await api('/api/context');
    document.getElementById('always-on-content').textContent = d.always_on || '(empty)';
    document.getElementById('active-context-content').textContent = d.active_context || '(empty)';
    
    const s = await api('/api/stats');
    document.getElementById('stat-files').textContent = s.total_files;
    document.getElementById('stat-days').textContent = s.days_of_memory;
    document.getElementById('stat-topics').textContent = s.long_term_topics;
  } catch(e) { console.error(e); }
}

async function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  document.getElementById('search-results').innerHTML = '<div class="loading">Searching...</div>';
  try {
    const d = await api('/api/search?q=' + encodeURIComponent(q));
    if (!d.results.length) {
      document.getElementById('search-results').innerHTML = '<div class="error">No results found.</div>';
      return;
    }
    document.getElementById('search-results').innerHTML = d.results.map(r => `
      <div class="result-item">
        <div class="result-file">📄 ${r.file}:${r.line}</div>
        <div class="result-heading">${r.heading}</div>
        <div class="result-snippet">${r.snippet}</div>
      </div>
    `).join('');
  } catch(e) { document.getElementById('search-results').innerHTML = '<div class="error">Search failed.</div>'; }
}

async function loadLongTerm(topic=null) {
  try {
    const d = await api('/api/long-term');
    const nav = document.getElementById('longterm-nav');
    nav.innerHTML = d.topics.map(t => 
      `<button class="copy-btn" onclick="loadLongTermTopic('${t}')" style="padding:6px 12px">${t}</button>`
    ).join('');
    if (!topic && d.topics.length) topic = d.topics[0];
    if (topic) loadLongTermTopic(topic);
  } catch(e) {}
}

async function loadLongTermTopic(topic) {
  document.getElementById('longterm-title').textContent = topic;
  document.getElementById('longterm-content').textContent = 'Loading...';
  try {
    const d = await api('/api/long-term/' + topic);
    document.getElementById('longterm-content').textContent = d.content;
  } catch(e) { document.getElementById('longterm-content').textContent = 'Error loading topic.'; }
}

async function saveNote() {
  const content = document.getElementById('note-content').value.trim();
  const heading = document.getElementById('note-heading').value.trim();
  if (!content) return;
  try {
    await api('/api/notes', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({content, heading: heading || null})
    });
    document.getElementById('note-status').innerHTML = '<div class="success-msg">✅ Note saved!</div>';
    document.getElementById('note-content').value = '';
    document.getElementById('note-heading').value = '';
    setTimeout(() => document.getElementById('note-status').innerHTML = '', 3000);
  } catch(e) { document.getElementById('note-status').innerHTML = '<div class="error">Failed to save.</div>'; }
}

async function loadFiles() {
  try {
    const d = await api('/api/files');
    const render = (files) => files.map(f => `
      <div class="file-item">
        <span class="file-name">📄 ${f.name}</span>
        <span class="file-size">${f.size}</span>
        <span class="file-date">${f.modified}</span>
      </div>
    `).join('') || '<div class="loading">No files yet.</div>';
    document.getElementById('shortterm-files').innerHTML = render(d.short_term);
    document.getElementById('longterm-files').innerHTML = render(d.long_term);
  } catch(e) {}
}

async function loadConnect() {
  try {
    const d = await api('/api/status');
    port = d.port;
    const config = `{
  "mcpServers": {
    "cortex": {
      "url": "http://127.0.0.1:${port}/mcp"
    }
  }
}`;
    document.getElementById('claude-config').textContent = config;
    document.getElementById('mcp-port-2').textContent = port;
    document.getElementById('mcp-status').innerHTML = `<span style="color:var(--green)">✅ MCP server running on port ${port}</span>`;
  } catch(e) {}
}

function copyClaudeConfig() {
  navigator.clipboard.writeText(document.getElementById('claude-config').textContent);
}

// Init
loadContext();
loadConnect();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


# ─────────────────────────────────────────────
# REST API for dashboard
# ─────────────────────────────────────────────

@app.get("/api/context")
async def api_context():
    config = get_config()
    manager = BrainManager(config)
    return {
        "always_on": manager.read_always_on(),
        "active_context": manager.read_active_context(),
    }


@app.get("/api/search")
async def api_search(q: str = Query(...)):
    config = get_config()
    searcher = BrainSearcher(config)
    results = searcher.search(q, max_results=10)
    return {
        "query": q,
        "results": [
            {
                "file": r.file.name,
                "line": r.line_no,
                "heading": r.heading,
                "snippet": r.snippet,
                "score": round(r.score, 3),
            }
            for r in results
        ],
    }


@app.get("/api/long-term")
async def api_long_term_list():
    config = get_config()
    manager = BrainManager(config)
    return {"topics": manager.list_long_term_topics()}


@app.get("/api/long-term/{topic}")
async def api_long_term_topic(topic: str):
    config = get_config()
    manager = BrainManager(config)
    return {"topic": topic, "content": manager.read_long_term(topic)}


@app.post("/api/notes")
async def api_save_note(request: Request):
    body = await request.json()
    config = get_config()
    manager = BrainManager(config)
    manager.append_to_today(body["content"], heading=body.get("heading"))
    return {"ok": True, "file": str(manager.today_file().name)}


@app.get("/api/files")
async def api_files():
    config = get_config()

    def file_info(p: Path) -> dict:
        stat = p.stat()
        size = f"{stat.st_size / 1024:.1f}KB"
        import datetime
        modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%b %d %H:%M")
        return {"name": p.name, "size": size, "modified": modified}

    short = []
    if config.short_term_dir.exists():
        short = [file_info(f) for f in sorted(config.short_term_dir.glob("*.md"), reverse=True)[:20]]

    long_ = []
    if config.long_term_dir.exists():
        long_ = [file_info(f) for f in sorted(config.long_term_dir.glob("*.md"))]

    return {"short_term": short, "long_term": long_}


@app.get("/api/stats")
async def api_stats():
    config = get_config()
    manager = BrainManager(config)
    topics = manager.list_long_term_topics()
    days = 0
    total = 0
    if config.short_term_dir.exists():
        files = list(config.short_term_dir.glob("*.md"))
        days = len(files)
        total += len(files)
    if config.long_term_dir.exists():
        lf = list(config.long_term_dir.glob("*.md"))
        total += len(lf)
    if config.active_context_file.exists():
        total += 1
    if config.always_on_file.exists():
        total += 1
    return {"total_files": total, "days_of_memory": days, "long_term_topics": len(topics)}


@app.get("/api/status")
async def api_status():
    port = int(os.environ.get("CORTEX_PORT", "7700"))
    brain_path = os.environ.get("CORTEX_BRAIN_PATH", str(Path.home() / ".cortex" / "brain"))
    return {"status": "ok", "port": port, "brain_path": brain_path}


# ─────────────────────────────────────────────
# MCP server (copy from mcp/server.py, inlined)
# ─────────────────────────────────────────────

from .mcp.server import TOOLS, call_tool

def make_mcp_response(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}

def make_mcp_error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method")
    id_ = body.get("id")
    params = body.get("params", {})

    session_id = request.headers.get("mcp-session-id", str(uuid.uuid4()))

    if method == "initialize":
        _sessions[session_id] = {}
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "cortex", "version": "0.1.0"},
        }
        resp = JSONResponse(make_mcp_response(id_, result))
        resp.headers["mcp-session-id"] = session_id
        return resp

    elif method == "tools/list":
        return JSONResponse(make_mcp_response(id_, {"tools": TOOLS}))

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            text = call_tool(tool_name, tool_args)
            result = {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}

        def stream():
            yield f"data: {json.dumps(make_mcp_response(id_, result))}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                  headers={"mcp-session-id": session_id})

    elif method == "notifications/initialized":
        return Response(status_code=202)

    return JSONResponse(make_mcp_error(id_, -32601, f"Method not found: {method}"))


# ─────────────────────────────────────────────
# Server entrypoint
# ─────────────────────────────────────────────

def serve(port: int = 7700, host: str = "127.0.0.1", no_agent: bool = False):
    import uvicorn

    os.environ["CORTEX_PORT"] = str(port)

    async def run_with_agent():
        config = get_config()
        agent = CurationAgent(config)
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
        print(f"\n🧠 Cortex running at http://{host}:{port}")
        print(f"   Dashboard  → http://{host}:{port}")
        print(f"   MCP server → http://{host}:{port}/mcp")
        print(f"   Brain path → {config.root}\n")
        if not no_agent:
            await asyncio.gather(server.serve(), agent.run())
        else:
            await server.serve()

    asyncio.run(run_with_agent())
