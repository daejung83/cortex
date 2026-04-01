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

from typing import Optional
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
      <button class="nav-item" onclick="showTab('learnings')" id="nav-learnings">
        <span class="icon">🧬</span> Learnings
      </button>
      <button class="nav-item" onclick="showTab('soul')" id="nav-soul">
        <span class="icon">💫</span> SOUL.md
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
          <div class="stat-card"><div class="stat-value" id="stat-projects">—</div><div class="stat-label">Active projects</div></div>
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
          <select id="search-days" style="background:var(--bg2);border:1px solid var(--border);color:var(--text);padding:8px 10px;border-radius:6px;font-size:13px;outline:none;">
            <option value="">All time</option>
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
          </select>
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

      <!-- Learnings Tab -->
      <div class="tab-content" id="tab-learnings">
        <div class="card">
          <div class="card-header">
            <span class="card-title">What AI Has Learned About You</span>
            <span class="badge">AI-maintained · max 35 lines</span>
          </div>
          <div class="card-body"><pre id="learnings-content">Loading...</pre></div>
        </div>
      </div>

      <!-- SOUL Tab -->
      <div class="tab-content" id="tab-soul">
        <div class="card">
          <div class="card-header">
            <span class="card-title">SOUL.md — AI Identity & Memory Contract</span>
            <button class="copy-btn" onclick="saveSoul()">Save</button>
          </div>
          <div class="card-body">
            <p style="font-size:12px;color:var(--muted);margin-bottom:10px">Edit who your AI is and what it MUST do. Loaded on every session.</p>
            <textarea id="soul-content" rows="24" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:12px;border-radius:6px;font-family:monospace;font-size:12px;line-height:1.6;outline:none;resize:vertical"></textarea>
            <div id="soul-status" style="margin-top:8px;font-size:12px"></div>
          </div>
        </div>
      </div>

      <!-- Connect Tab -->
      <div class="tab-content" id="tab-connect">

        <div class="card">
          <div class="card-header"><span class="card-title">LLM Curation</span></div>
          <div class="card-body">
            <div id="llm-status" class="loading">Checking...</div>
            <p style="font-size:12px;color:var(--muted);margin-top:10px">
              Enable AI curation by setting env vars before <code>cortex start</code>:
            </p>
            <div class="code-block" id="env-template"></div>
            <p style="font-size:11px;color:var(--muted);margin-top:8px">
              Only the <strong>active provider's key</strong> is used — store multiple keys, switch by changing <code>CORTEX_LLM_PROVIDER</code>.<br>
              ⚠️ Claude Code/Desktop <strong>subscriptions</strong> can't be used for curation (OAuth, not API key). Use <strong>Ollama</strong> instead.
            </p>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">MCP Server Status</span>
            <span class="badge green" id="mcp-status-badge">Checking...</span>
          </div>
          <div class="card-body">
            <div id="mcp-status" class="loading">Checking...</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">Claude Desktop</span></div>
          <div class="card-body">
            <p style="font-size:12px;color:var(--muted);margin-bottom:10px">
              Add to <code>%APPDATA%/Claude/claude_desktop_config.json</code> (Windows) or<br>
              <code>~/Library/Application Support/Claude/claude_desktop_config.json</code> (Mac)
            </p>
            <div class="code-block" id="claude-config"></div>
            <button class="copy-btn" style="margin-top:8px" onclick="copyConfig('claude-config')">Copy</button>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">Quick Setup Commands</span></div>
          <div class="card-body">
            <p style="font-size:13px;font-weight:600;margin-bottom:6px">Global <span style="font-size:11px;color:var(--green);font-weight:400">(one-time — works in every project)</span></p>
            <div class="code-block" id="cmd-global"></div>
            <button class="copy-btn" style="margin-top:6px" onclick="copyConfig('cmd-global')">Copy</button>

            <div style="border-top:1px solid var(--border);margin:14px 0"></div>

            <p style="font-size:13px;font-weight:600;margin-bottom:6px">Per-project <span style="font-size:11px;color:var(--muted);font-weight:400">(run in each project folder)</span></p>
            <div class="code-block" id="cmd-project"></div>
            <button class="copy-btn" style="margin-top:6px" onclick="copyConfig('cmd-project')">Copy</button>
            <p style="font-size:11px;color:var(--muted);margin-top:8px">Creates CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules, and .mcp.json in the current directory.</p>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">Claude Code (CLI)</span></div>
          <div class="card-body">

            <p style="font-size:13px;font-weight:600;margin-bottom:6px">Option 1 — Global <span style="font-size:11px;color:var(--green);font-weight:400">(recommended — works in every project)</span></p>
            <p style="font-size:12px;color:var(--muted);margin-bottom:8px">Manually create <code>~/.claude/.mcp.json</code>:</p>
            <div class="code-block" id="claudecode-config"></div>
            <button class="copy-btn" style="margin-top:8px" onclick="copyConfig('claudecode-config')">Copy</button>

            <div style="border-top:1px solid var(--border);margin:16px 0"></div>

            <p style="font-size:13px;font-weight:600;margin-bottom:6px">Option 2 — Project-scoped <span style="font-size:11px;color:var(--muted);font-weight:400">(only active in current project folder)</span></p>
            <p style="font-size:12px;color:var(--muted);margin-bottom:8px">Run in your project directory — creates a local <code>.mcp.json</code>:</p>
            <div class="code-block" id="claudecode-cmd"></div>
            <button class="copy-btn" style="margin-top:8px" onclick="copyConfig('claudecode-cmd')">Copy</button>

            <p style="font-size:11px;color:var(--red);margin-top:10px">⚠️ Do NOT put mcpServers in settings.json — Claude Code silently ignores it there.</p>

            <div style="border-top:1px solid var(--border);margin:16px 0"></div>

            <p style="font-size:13px;font-weight:600;margin-bottom:6px">Auto-load context every session</p>
            <p style="font-size:12px;color:var(--muted);margin-bottom:8px">
              Cortex won't call <code>get_context()</code> automatically — you need to tell Claude to do it.<br>
              Add a <code>CLAUDE.md</code> file to your project root (or <code>~/.claude/CLAUDE.md</code> for global):
            </p>
            <div class="code-block"># Memory Instructions
At the start of every session, call cortex:get_context() and cortex:get_learnings()
before responding to anything. This loads your persistent memory and who you are.</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">Cursor / Windsurf</span></div>
          <div class="card-body">
            <p style="font-size:12px;color:var(--muted);margin-bottom:10px">Settings → MCP → Add server:</p>
            <div class="code-block" id="cursor-config"></div>
            <button class="copy-btn" style="margin-top:8px" onclick="copyConfig('cursor-config')">Copy</button>

            <div style="border-top:1px solid var(--border);margin:16px 0"></div>

            <p style="font-size:13px;font-weight:600;margin-bottom:6px">Auto-load context every session</p>
            <p style="font-size:12px;color:var(--muted);margin-bottom:8px">
              Cursor/Windsurf don't auto-call <code>get_context()</code> either.<br>
              Add a <code>.cursorrules</code> file (Cursor) or <code>.windsurfrules</code> (Windsurf) to your project root:
            </p>
            <div class="code-block"># Memory Instructions
At the start of every session, call cortex:get_context() and cortex:get_learnings()
before responding to anything. This loads your persistent memory and who you are.</div>
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
  const titles = {context:'Active Context', search:'Search', longterm:'Long-Term Memory', notes:'Add Note', files:'Brain Files', learnings:'Learnings', soul:'SOUL.md', connect:'Connect AI'};
  document.getElementById('page-title').textContent = titles[tab];
  loadTab(tab);
}

function refreshCurrent() { loadTab(currentTab); }

async function loadTab(tab) {
  if (tab === 'context') await loadContext();
  else if (tab === 'longterm') await loadLongTerm();
  else if (tab === 'files') await loadFiles();
  else if (tab === 'learnings') await loadLearnings();
  else if (tab === 'soul') await loadSoul();
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
    document.getElementById('stat-projects').textContent = s.projects || s.long_term_topics;
  } catch(e) { console.error(e); }
}

async function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  const days = document.getElementById('search-days').value;
  const params = new URLSearchParams({q});
  if (days) params.set('days', days);
  document.getElementById('search-results').innerHTML = '<div class="loading">Searching...</div>';
  try {
    const d = await api('/api/search?' + params.toString());
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
    const url = `http://127.0.0.1:${port}/mcp`;

    document.getElementById('mcp-status').innerHTML = `<span style="color:var(--green)">✅ Running on port ${port} · ${url}</span>`;
    document.getElementById('mcp-status-badge').textContent = '● Connected';
    document.getElementById('mcp-status-badge').style.color = 'var(--green)';

    // LLM status
    if (d.llm) {
      document.getElementById('llm-status').innerHTML = `<span style="color:var(--green)">✅ ${d.llm.provider} / ${d.llm.model} — AI curation active</span>`;
    } else {
      document.getElementById('llm-status').innerHTML = `<span style="color:var(--yellow)">⚡ Heuristic mode — works great for most users. Want smarter curation? Set CORTEX_LLM_PROVIDER=ollama (free, local) or use an OpenAI/Anthropic API key.</span>`;
    }

    // LLM env template
    const envPath = '~/.cortex/.env';
    document.getElementById('env-template').textContent =
`# ${envPath} — never commit this file
# Only the active provider's key is used. Store all keys here,
# switch providers by changing CORTEX_LLM_PROVIDER.

# ── Active provider (uncomment one) ──────────────
# CORTEX_LLM_PROVIDER=ollama        # local, free
# CORTEX_LLM_PROVIDER=openai        # ~$0.001/day
# CORTEX_LLM_PROVIDER=anthropic     # ~$0.001/day

# ── Keys ──────────────────────────────────────────
# CORTEX_LLM_API_KEY=sk-...         # OpenAI or Anthropic key

# ── Model override (optional) ─────────────────────
# CORTEX_LLM_MODEL=llama3.2`;

    document.getElementById('cmd-global').textContent = `python -m cortex_core.cli init-global --port ${port}`;
    document.getElementById('cmd-project').textContent = `python -m cortex_core.cli init-project --port ${port}`;
    document.getElementById('claude-config').textContent = JSON.stringify({mcpServers:{cortex:{type:"streamable-http",url}}},null,2);
    document.getElementById('claudecode-cmd').textContent = `claude mcp add cortex --transport http ${url}`;
    document.getElementById('claudecode-config').textContent = JSON.stringify({mcpServers:{cortex:{type:"streamable-http",url}}},null,2);
    document.getElementById('cursor-config').textContent = JSON.stringify({cortex:{type:"streamable-http",url}},null,2);
  } catch(e) {
    document.getElementById('mcp-status').innerHTML = '<span style="color:var(--red)">❌ Server not reachable</span>';
  }
}

function copyConfig(id) {
  navigator.clipboard.writeText(document.getElementById(id).textContent);
}

async function loadLearnings() {
  try {
    const d = await api('/api/learnings');
    document.getElementById('learnings-content').textContent = d.content || '(no learnings yet)';
  } catch(e) { document.getElementById('learnings-content').textContent = 'Error loading.'; }
}

async function loadSoul() {
  try {
    const d = await api('/api/soul');
    document.getElementById('soul-content').value = d.content;
  } catch(e) {}
}

async function saveSoul() {
  const content = document.getElementById('soul-content').value;
  try {
    await api('/api/soul', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({content})
    });
    document.getElementById('soul-status').innerHTML = '<span style="color:var(--green)">✅ Saved</span>';
    setTimeout(() => document.getElementById('soul-status').innerHTML = '', 3000);
  } catch(e) { document.getElementById('soul-status').innerHTML = '<span style="color:var(--red)">Failed to save</span>'; }
}

function copyClaudeConfig() { copyConfig('claude-config'); }

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
async def api_search(q: str = Query(...), days: Optional[int] = Query(None)):
    config = get_config()
    searcher = BrainSearcher(config)
    results = searcher.search(q, max_results=10, days=days)
    return {
        "query": q,
        "days": days,
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


@app.get("/api/learnings")
async def api_learnings():
    config = get_config()
    manager = BrainManager(config)
    return {"content": manager.get_learnings_with_stale_check()}


@app.get("/api/soul")
async def api_get_soul():
    from .brain.soul import read_soul
    config = get_config()
    return {"content": read_soul(config)}


@app.post("/api/soul")
async def api_save_soul(request: Request):
    from .brain.soul import get_soul_path
    config = get_config()
    body = await request.json()
    content = body.get("content", "")
    path = get_soul_path(config)
    path.write_text(content)
    return {"ok": True}


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
        lf = list(config.long_term_dir.rglob("*.md"))
        total += len(lf)
    if config.active_context_file.exists():
        total += 1
    if config.always_on_file.exists():
        total += 1
    projects = manager.list_projects()
    return {
        "total_files": total,
        "days_of_memory": days,
        "long_term_topics": len(topics),
        "projects": len(projects),
    }


@app.get("/api/status")
async def api_status():
    port = int(os.environ.get("CORTEX_PORT", "7700"))
    brain_path = os.environ.get("CORTEX_BRAIN_PATH", str(Path.home() / ".cortex" / "brain"))
    llm_provider = os.environ.get("CORTEX_LLM_PROVIDER", "")
    llm_model = os.environ.get("CORTEX_LLM_MODEL", "")
    defaults = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-nano", "ollama": "llama3.2"}
    llm_info = None
    if llm_provider:
        llm_info = {"provider": llm_provider, "model": llm_model or defaults.get(llm_provider, "default")}
    return {"status": "ok", "port": port, "brain_path": brain_path, "llm": llm_info}


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

def _load_secrets():
    """Load ~/.cortex/.env if it exists — keeps API keys out of project dirs."""
    secrets_file = Path.home() / ".cortex" / ".env"
    if secrets_file.exists():
        for line in secrets_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val and key not in os.environ:
                    os.environ[key] = val


def serve(port: int = 7700, host: str = "127.0.0.1", no_agent: bool = False):
    import uvicorn

    _load_secrets()
    os.environ["CORTEX_PORT"] = str(port)

    # Show LLM status so user knows what mode is active
    provider = os.environ.get("CORTEX_LLM_PROVIDER", "")
    model = os.environ.get("CORTEX_LLM_MODEL", "")
    if provider:
        defaults = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-nano", "ollama": "llama3.2"}
        active_model = model or defaults.get(provider, "default")
        print(f"  LLM curation: {provider} / {active_model}")
    else:
        print(f"  LLM curation: heuristic mode (set CORTEX_LLM_PROVIDER in ~/.cortex/.env to enable)")

    print(f"  To apply .env changes: stop Cortex (Ctrl+C) then run cortex start again\n")

    async def run_with_agent():
        config = get_config()
        agent = CurationAgent(config)
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None  # let asyncio handle signals
        print(f"\n🧠 Cortex running at http://{host}:{port}")
        print(f"   Dashboard  → http://{host}:{port}")
        print(f"   MCP server → http://{host}:{port}/mcp")
        print(f"   Brain path → {config.root}\n")
        if not no_agent:
            await asyncio.gather(server.serve(), agent.run())
        else:
            await server.serve()

    try:
        asyncio.run(run_with_agent())
    except KeyboardInterrupt:
        print("\n  Cortex stopped. Goodbye!\n")
