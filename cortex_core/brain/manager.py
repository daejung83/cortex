"""
BrainManager — read/write operations on brain files.
"""

from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional
import re
from .schema import BrainConfig


class BrainManager:
    def __init__(self, config: BrainConfig):
        self.config = config

    @property
    def projects_dir(self) -> Path:
        return self.config.long_term_dir / "projects"

    def init(self):
        """Initialize brain directory structure."""
        self.config.short_term_dir.mkdir(parents=True, exist_ok=True)
        self.config.long_term_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        # Seed SOUL.md if missing
        from .soul import init_soul
        init_soul(self.config)

        # Seed always-on.md if missing
        if not self.config.always_on_file.exists():
            self.config.always_on_file.write_text(
                "# Always-On Context\n\n"
                "_Permanent context always loaded. Edit this file to add things "
                "your AI should always know about you._\n\n"
                "## About Me\n\n"
                "## Current Focus\n\n"
                "## My Stack\n"
            )

        # Seed active-context.md if missing
        if not self.config.active_context_file.exists():
            self.config.active_context_file.write_text(
                "# Active Context\n\n"
                "_Auto-rebuilt from recent sessions. Do not edit manually._\n\n"
                "No context yet — run `cortex build-context` after your first session.\n"
            )

        # Seed default long-term files
        for fname in ["projects.md", "decisions.md", "people.md"]:
            f = self.config.long_term_dir / fname
            if not f.exists():
                title = fname.replace(".md", "").capitalize()
                f.write_text(f"# {title}\n\n_Add entries here._\n", encoding="utf-8")

        # Seed ~/.cortex/.env secrets template
        secrets_file = self.config.root.parent / ".env"
        if not secrets_file.exists():
            secrets_file.write_text(
                "# Cortex secrets — never commit this file\n"
                "#\n"
                "# Set CORTEX_LLM_PROVIDER to activate AI curation.\n"
                "# Only the active provider's key is used — others are ignored.\n"
                "# Store multiple keys here and switch by changing CORTEX_LLM_PROVIDER.\n"
                "#\n"
                "# !! After editing this file: stop Cortex (Ctrl+C) and run 'cortex start' again.\n"
                "# Changes are only loaded on startup.\n"
                "#\n"
                "# ── Active provider (uncomment one) ──────────────────\n"
                "# CORTEX_LLM_PROVIDER=ollama          # local, free\n"
                "# CORTEX_LLM_PROVIDER=openai          # ~$0.001/day\n"
                "# CORTEX_LLM_PROVIDER=anthropic       # ~$0.001/day\n"
                "#\n"
                "# ── Keys (store all, only active provider's key is used) ─\n"
                "# CORTEX_LLM_API_KEY=sk-...           # OpenAI or Anthropic key\n"
                "#\n"
                "# ── Model override (optional) ──────────────────────────\n"
                "# CORTEX_LLM_MODEL=llama3.2           # default per provider\n",
                encoding="utf-8"
            )

        print(f"✅ Brain initialized at {self.config.root}")

    def today_file(self) -> Path:
        """Return path to today's short-term file (creates if missing)."""
        today = date.today().isoformat()
        path = self.config.short_term_dir / f"{today}.md"
        if not path.exists():
            path.write_text(f"# Brain — {today}\n\n", encoding="utf-8")
        return path

    def append_to_today(self, content: str, heading: Optional[str] = None):
        """Append a note to today's short-term file."""
        f = self.today_file()
        ts = datetime.now().strftime("%H:%M")
        entry = f"\n## {heading or ts}\n\n{content.strip()}\n"
        with f.open("a", encoding="utf-8") as fp:
            fp.write(entry)

    def read_active_context(self) -> str:
        if self.config.active_context_file.exists():
            return self.config.active_context_file.read_text(encoding="utf-8", errors="replace")
        return ""

    def read_always_on(self) -> str:
        if self.config.always_on_file.exists():
            return self.config.always_on_file.read_text(encoding="utf-8", errors="replace")
        return ""

    def read_long_term(self, topic: str) -> str:
        """Read a long-term file by topic name (e.g. 'projects', 'decisions')."""
        path = self.config.long_term_dir / f"{topic}.md"
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        return f"No long-term file for topic: {topic}"

    def list_long_term_topics(self) -> list[str]:
        if not self.config.long_term_dir.exists():
            return []
        return [f.stem for f in self.config.long_term_dir.glob("*.md")]

    # ── Project methods ──────────────────────────────────────────────

    def _project_file(self, name: str) -> Path:
        slug = re.sub(r"[^\w-]", "-", name.lower().strip()).strip("-")
        return self.projects_dir / f"{slug}.md"

    def _index_file(self) -> Path:
        return self.projects_dir / "_index.md"

    def update_project(
        self,
        name: str,
        status: str,
        focus: Optional[str] = None,
        next_steps: Optional[list[str]] = None,
        stack: Optional[str] = None,
        notes: Optional[str] = None,
        url: Optional[str] = None,
    ) -> str:
        """
        Create or update a project file — MERGES with existing data.
        Only updates fields explicitly passed. Preserves everything else.
        Max ~15 lines — current state only, not history.
        """
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        path = self._project_file(name)

        # Load existing fields if file exists
        existing = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                for field in ["Status", "URL", "Stack", "Current focus", "Notes"]:
                    if f"**{field}:**" in line:
                        existing[field.lower().replace(" ", "_")] = line.split(f"**{field}:**")[-1].strip()

        # Merge — only override if explicitly passed
        merged = {
            "status": status,
            "url": url or existing.get("url"),
            "stack": stack or existing.get("stack"),
            "focus": focus or existing.get("current_focus"),
            "notes": notes or existing.get("notes"),
        }

        lines = [f"# {name}\n"]
        lines.append(f"- **Status:** {merged['status']}")
        if merged["url"]:
            lines.append(f"- **URL:** {merged['url']}")
        if merged["stack"]:
            lines.append(f"- **Stack:** {merged['stack']}")
        if merged["focus"]:
            lines.append(f"- **Current focus:** {merged['focus']}")
        if next_steps:
            lines.append("- **Next steps:**")
            for s in next_steps:
                lines.append(f"  - {s}")
        if merged["notes"]:
            lines.append(f"- **Notes:** {merged['notes']}")
        lines.append(f"- **Last updated:** {today}")

        content = "\n".join(lines) + "\n"

        # Atomic write — prevents race condition with concurrent sessions
        import tempfile, os
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

        self._rebuild_project_index()
        return str(path)

    def get_project(self, name: str) -> str:
        path = self._project_file(name)
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        return f"No project found: {name}"

    def list_projects(self) -> list[str]:
        if not self.projects_dir.exists():
            return []
        return [f.stem for f in sorted(self.projects_dir.glob("*.md"))
                if f.stem != "_index"]

    def get_project_index(self) -> str:
        idx = self._index_file()
        if idx.exists():
            return idx.read_text(encoding="utf-8", errors="replace")
        return self._rebuild_project_index()

    def _rebuild_project_index(self) -> str:
        """Rebuild _index.md from all project files — one line per project."""
        projects = []
        for f in sorted(self.projects_dir.glob("*.md")):
            if f.stem == "_index":
                continue
            content = f.read_text(encoding="utf-8", errors="replace")
            # Extract name (first # heading) and status
            name = f.stem
            status = "unknown"
            for line in content.splitlines():
                if line.startswith("# "):
                    name = line[2:].strip()
                if "**Status:**" in line:
                    status = line.split("**Status:**")[-1].strip()
                    break
            projects.append(f"- **{name}:** {status}")

        today = date.today().isoformat()
        index_content = f"# Projects\n_Updated: {today}_\n\n" + "\n".join(projects) + "\n"
        self._index_file().write_text(index_content, encoding="utf-8")
        return index_content

    # ── Learnings methods ────────────────────────────────────────────

    LEARNING_CATEGORIES = ["work_style", "technical", "communication", "decision_patterns", "goals"]
    MAX_LEARNINGS_LINES = 35
    STALE_LEARNING_DAYS = 90

    @property
    def _learnings_file(self) -> Path:
        return self.config.long_term_dir / "learnings.md"

    def read_learnings(self) -> str:
        if not self._learnings_file.exists():
            return "_No learnings yet. AI will update this as patterns are observed._"
        return self._learnings_file.read_text(encoding="utf-8", errors="replace")

    def update_learning(self, category: str, insight: str, replaces: Optional[str] = None) -> str:
        """
        Add or update a learning about the user.
        Merges into existing category section.
        Enforces max line limit — AI must consolidate if too big.
        """
        today = date.today().isoformat()
        existing = self._learnings_file.read_text(encoding="utf-8", errors="replace") if self._learnings_file.exists() else ""

        # Parse existing into sections
        sections: dict[str, list[str]] = {}
        current_section = None
        header_line = None

        for line in existing.splitlines():
            if line.startswith("# "):
                header_line = line
            elif line.startswith("## "):
                current_section = line[3:].strip().lower().replace(" ", "_")
                sections[current_section] = []
            elif current_section and line.strip().startswith("- "):
                sections[current_section].append(line.strip())

        # Remove replaced insight
        if replaces and category in sections:
            sections[category] = [
                l for l in sections[category]
                if replaces.lower() not in l.lower()
            ]

        # Add new insight with date tag
        if category not in sections:
            sections[category] = []
        tagged = f"- {insight} _(confirmed {today})_"
        # Don't duplicate
        if not any(insight.lower() in l.lower() for l in sections[category]):
            sections[category].append(tagged)

        # Rebuild file
        lines = ["# Learnings", f"_Last updated: {today}_", ""]
        category_titles = {
            "work_style": "Work Style",
            "technical": "Technical Preferences",
            "communication": "Communication",
            "decision_patterns": "Decision Patterns",
            "goals": "Goals",
        }
        for cat in self.LEARNING_CATEGORIES:
            if cat in sections and sections[cat]:
                lines.append(f"## {category_titles.get(cat, cat)}")
                lines.extend(sections[cat])
                lines.append("")

        content = "\n".join(lines)

        # Enforce max lines
        actual_lines = [l for l in content.splitlines() if l.strip()]
        if len(actual_lines) > self.MAX_LEARNINGS_LINES:
            content += f"\n\n⚠️ CONSOLIDATION NEEDED: {len(actual_lines)} lines (max {self.MAX_LEARNINGS_LINES}). Call update_learning with replaces= to consolidate."

        # Atomic write
        import tempfile, os
        tmp = self._learnings_file.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, self._learnings_file)
        return f"✅ Learning updated in category: {category}"

    def get_learnings_with_stale_check(self) -> str:
        """Read learnings, flagging entries older than STALE_LEARNING_DAYS."""
        content = self.read_learnings()
        if "_No learnings yet" in content:
            return content

        today = date.today()
        lines_out = []
        for line in content.splitlines():
            # Check for date tags like _(confirmed 2026-01-01)_
            match = re.search(r"_\(confirmed (\d{4}-\d{2}-\d{2})\)_", line)
            if match:
                confirmed = date.fromisoformat(match.group(1))
                age = (today - confirmed).days
                if age > self.STALE_LEARNING_DAYS:
                    line = f"⚠️ [STALE — {age}d ago, confirm still true] {line}"
            lines_out.append(line)
        return "\n".join(lines_out)

    def log_decision(self, decision: str, rationale: Optional[str] = None, project: Optional[str] = None) -> str:
        """Append a decision to long-term/decisions.md."""
        decisions_file = self.config.long_term_dir / "decisions.md"
        today = date.today().isoformat()
        now = datetime.now().strftime("%H:%M")

        lines = [f"\n## {today} {now}"]
        if project:
            lines.append(f"**Project:** {project}")
        lines.append(f"**Decision:** {decision}")
        if rationale:
            lines.append(f"**Why:** {rationale}")

        entry = "\n".join(lines) + "\n"
        with decisions_file.open("a", encoding="utf-8") as f:
            f.write(entry)
        return str(decisions_file)

    def read_decisions(self, days: int = 90) -> str:
        """Read decisions.md filtered to last N days. Use days=0 for all."""
        path = self.config.long_term_dir / "decisions.md"
        if not path.exists():
            return "_No decisions logged yet._"
        if days == 0:
            return path.read_text(encoding="utf-8", errors="replace")

        cutoff = date.today() - timedelta(days=days)
        lines_out = []
        include = True
        header_added = False

        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            # Section headers like "## 2026-04-01 14:23"
            if line.startswith("## "):
                date_match = re.match(r"## (\d{4}-\d{2}-\d{2})", line)
                if date_match:
                    entry_date = date.fromisoformat(date_match.group(1))
                    include = entry_date >= cutoff
                else:
                    include = True
            if include:
                if not header_added:
                    lines_out.append(f"# Decisions (last {days} days)\n")
                    header_added = True
                lines_out.append(line)

        return "\n".join(lines_out) if lines_out else f"_No decisions in the last {days} days._"

    def search_long_term(self, query: str, max_results: int = 8) -> list:
        """Search only long-term files — decisions, insights, summaries, projects."""
        from ..search.searcher import BrainSearcher, SearchResult
        import copy

        # Temporarily override to search only long-term
        long_term_files = []
        if self.config.long_term_dir.exists():
            long_term_files.extend(self.config.long_term_dir.rglob("*.md"))

        terms = query.lower().split()
        results = []

        for path in long_term_files:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            current_heading = path.stem
            for i, line in enumerate(lines, 1):
                if line.startswith("#"):
                    current_heading = line.lstrip("#").strip()
                    continue
                line_lower = line.lower()
                matches = sum(1 for t in terms if t in line_lower)
                if matches > 0:
                    from ..search.searcher import SearchResult
                    results.append(SearchResult(
                        file=path,
                        line_no=i,
                        heading=current_heading,
                        snippet=line.strip()[:120],
                        score=matches / len(terms),
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def list_monthly_summaries(self) -> list[str]:
        summaries_dir = self.config.long_term_dir / "summaries"
        if not summaries_dir.exists():
            return []
        return [f.stem for f in sorted(summaries_dir.glob("*.md"), reverse=True)]

    def get_monthly_summary(self, month: str) -> str:
        """Get summary for a specific month (YYYY-MM)."""
        path = self.config.long_term_dir / "summaries" / f"{month}.md"
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        return f"No summary for {month}"

    def recent_short_term(self, days: int = 3) -> list[tuple[str, str]]:
        """Return (date_str, content) for the last N short-term files."""
        if not self.config.short_term_dir.exists():
            return []
        files = sorted(self.config.short_term_dir.glob("*.md"), reverse=True)[:days]
        return [(f.stem, f.read_text(encoding="utf-8", errors="replace")) for f in files]
