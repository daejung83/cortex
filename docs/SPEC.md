# Cortex Brain Format Spec v0.2

## Overview

The Cortex Brain Format is an open specification for persistent AI memory. Plain markdown files, human-readable, version-controllable, tool-agnostic.

Goals:
- Human-readable and human-editable at all times
- Version-controllable (git-friendly)
- Tool-agnostic — works with any AI via MCP
- Hierarchical context: hot / warm / cold
- Never grows unbounded — enforced size limits, promote-on-prune

---

## Directory Structure

```
<brain-root>/
├── SOUL.md                        ← AI identity + mandatory behavior (user-editable)
├── always-on.md                   ← permanent context (user-maintained, ~25 lines max)
├── active-context.md              ← hot context, auto-rebuilt every 30min (~40 lines)
├── short-term/
│   ├── YYYY-MM-DD.md              ← daily timestamped notes
│   └── ...                        ← retained 30 days, then promoted + deleted
└── long-term/
    ├── projects/
    │   ├── _index.md              ← one-line status per project
    │   └── <slug>.md              ← per-project current state (~15 lines max)
    ├── decisions.md               ← major decisions log
    ├── insights.md                ← lessons learned (promoted from short-term)
    ├── learnings.md               ← AI-maintained user profile (~35 lines max)
    └── summaries/
        └── YYYY-MM.md             ← monthly session summaries (promoted from short-term)
```

---

## File Types

### `SOUL.md`
**Purpose:** AI identity and mandatory behavior contract.
**Who writes it:** User (seeded with defaults on `cortex init`, editable in dashboard).
**Loaded:** Always — first thing in every `get_context()` response.
**Format:** Free-form markdown. Typically includes:
- Who the AI is
- MUST USE section: which tools to call at which moments
- Tone and communication preferences

### `always-on.md`
**Purpose:** Permanent context about the user — name, role, stack, current focus.
**Who writes it:** User.
**Max size:** 25 lines enforced.
**Loaded:** Always — part of every `get_context()` response.

### `active-context.md`
**Purpose:** Hot summary of the last 48 hours. Auto-rebuilt by curation agent.
**Who writes it:** Curation agent (do not edit manually — will be overwritten).
**Max size:** 40 lines enforced.
**Loaded:** Always — part of every `get_context()` response.
**Rebuild trigger:** Every 30 minutes by curation agent, or `cortex build-context`.

### `short-term/YYYY-MM-DD.md`
**Purpose:** Raw daily notes with timestamps. One file per day.
**Who writes it:** AI (via `log_note()`, `save_session_summary()`) + user (via `cortex note`).
**Retention:** 30 days. Before deletion, important entries are promoted to long-term.
**Entry format:**
```markdown
## HH:MM | type
Content here.
```
Valid types: `decision`, `progress`, `insight`, `next_steps`, `context`, `question`, `session_summary`

### `long-term/projects/_index.md`
**Purpose:** One-line status overview of all projects. Auto-rebuilt on every `update_project()` call.
**Who writes it:** Auto-rebuilt only — do not edit manually.
**Format:**
```markdown
# Projects
_Updated: YYYY-MM-DD_

- **ProjectName:** current status
- **AnotherProject:** current status
```

### `long-term/projects/<slug>.md`
**Purpose:** Current state of a single project. Overwritten on every `update_project()`.
**Max size:** ~15 lines. Current state only — history stays in short-term.
**Fields:** Status, URL, Stack, Current focus, Next steps, Notes, Last updated.

### `long-term/decisions.md`
**Purpose:** Major decisions log with rationale.
**Who writes it:** AI (via `log_decision()`). Append-only.
**Query:** `get_decisions(days=90)` returns last 90 days by default.

### `long-term/insights.md`
**Purpose:** Lessons learned. Promoted from `insight`-tagged short-term entries at 30 days.

### `long-term/learnings.md`
**Purpose:** AI-maintained profile of user preferences, patterns, and habits.
**Who writes it:** AI (via `update_learning()`). Overwrites, never appends.
**Max size:** 35 lines enforced.
**Sections:** work_style, technical, communication, decision_patterns, goals.
**Stale detection:** Entries older than 90 days flagged with ⚠️ in `get_learnings()`.

### `long-term/summaries/YYYY-MM.md`
**Purpose:** Monthly session summaries. Promoted from `session_summary` entries at 30 days.

---

## Context Hierarchy

| Layer | File | Tokens | Loaded | Written by |
|-------|------|--------|--------|-----------|
| Identity | `SOUL.md` | ~300 | Always | User |
| Permanent | `always-on.md` | ~400 | Always | User |
| Hot | `active-context.md` | ~800 | Always | Agent (auto) |
| Learning | `learnings.md` | ~300 | On `get_learnings()` | AI (auto) |
| Projects | `_index.md` | ~100 | On `get_projects()` | Auto |
| On-demand | `long-term/*.md` | varies | When searched | Mixed |
| Archive | `short-term/*.md` | varies | On search hit | AI + User |

**Baseline per session:** ~1,500 tokens (SOUL + always-on + active-context)

---

## Promote-on-Prune

Before any short-term file is deleted (at 30 days), entries are extracted by type:

| Entry type | Promoted to | Discarded |
|-----------|-------------|-----------|
| `decision` | `long-term/decisions.md` | Never |
| `insight` | `long-term/insights.md` | Never |
| `session_summary` | `long-term/summaries/YYYY-MM.md` | Never |
| `progress` | Already in project file via `update_project()` | Raw entry discarded |
| `next_steps` | Not promoted | Discarded (stale if old) |
| `context` | Not promoted | Discarded |
| `question` | Not promoted | Discarded |

---

## MCP Tools Reference

### Read tools

| Tool | Description | Returns |
|------|-------------|---------|
| `get_context()` | Load session context | SOUL.md + always-on + active-context |
| `get_learnings()` | Load user profile | learnings.md with stale flags |
| `get_projects()` | Project overview | _index.md (one line per project) |
| `get_project(name)` | Single project detail | Full project file |
| `get_decisions(days?)` | Decisions log | Last N days (default 90), days=0 for all |
| `get_summary(month)` | Monthly summary | summaries/YYYY-MM.md |
| `get_long_term(topic)` | Any long-term file | That file's content |
| `search_brain(query, days?)` | Scoped search | Snippets from short-term + long-term |
| `search_long_term(query)` | Old content search | Snippets from long-term only |

### Write tools

| Tool | Description | Writes to |
|------|-------------|-----------|
| `log_note(content, type)` | Timestamped note | short-term/YYYY-MM-DD.md |
| `save_session_summary(...)` | Session wrap-up | short-term/YYYY-MM-DD.md |
| `update_project(name, status, ...)` | Project state | long-term/projects/<slug>.md (merge-safe) |
| `log_decision(decision, rationale)` | Important decision | long-term/decisions.md |
| `update_learning(category, insight)` | User profile | long-term/learnings.md (overwrite) |

---

## Versioning

This is spec v0.2. Breaking changes increment major version.
Backward-compatible additions increment minor version.

Changes from v0.1:
- Added `SOUL.md`
- Per-project files under `long-term/projects/` (replaces single `projects.md`)
- `learnings.md` with stale detection
- Promote-on-prune pipeline
- `summaries/` directory for monthly history
- Timestamped entry format with type tags
