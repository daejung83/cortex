"""
BrainManager — read/write operations on brain files.
"""

from pathlib import Path
from datetime import date, datetime
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
                f.write_text(f"# {title}\n\n_Add entries here._\n")

        print(f"✅ Brain initialized at {self.config.root}")

    def today_file(self) -> Path:
        """Return path to today's short-term file (creates if missing)."""
        today = date.today().isoformat()
        path = self.config.short_term_dir / f"{today}.md"
        if not path.exists():
            path.write_text(f"# Brain — {today}\n\n")
        return path

    def append_to_today(self, content: str, heading: Optional[str] = None):
        """Append a note to today's short-term file."""
        f = self.today_file()
        ts = datetime.now().strftime("%H:%M")
        entry = f"\n## {heading or ts}\n\n{content.strip()}\n"
        with f.open("a") as fp:
            fp.write(entry)

    def read_active_context(self) -> str:
        if self.config.active_context_file.exists():
            return self.config.active_context_file.read_text()
        return ""

    def read_always_on(self) -> str:
        if self.config.always_on_file.exists():
            return self.config.always_on_file.read_text()
        return ""

    def read_long_term(self, topic: str) -> str:
        """Read a long-term file by topic name (e.g. 'projects', 'decisions')."""
        path = self.config.long_term_dir / f"{topic}.md"
        if path.exists():
            return path.read_text()
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
        Create or overwrite a project file with current state.
        Max ~15 lines — current state only, not history.
        History lives in short-term files.
        """
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()

        lines = [f"# {name}\n"]
        lines.append(f"- **Status:** {status}")
        if url:
            lines.append(f"- **URL:** {url}")
        if stack:
            lines.append(f"- **Stack:** {stack}")
        if focus:
            lines.append(f"- **Current focus:** {focus}")
        if next_steps:
            lines.append(f"- **Next steps:**")
            for s in next_steps:
                lines.append(f"  - {s}")
        if notes:
            lines.append(f"- **Notes:** {notes}")
        lines.append(f"- **Last updated:** {today}")

        content = "\n".join(lines) + "\n"
        path = self._project_file(name)
        path.write_text(content)

        # Rebuild index
        self._rebuild_project_index()
        return str(path)

    def get_project(self, name: str) -> str:
        path = self._project_file(name)
        if path.exists():
            return path.read_text()
        return f"No project found: {name}"

    def list_projects(self) -> list[str]:
        if not self.projects_dir.exists():
            return []
        return [f.stem for f in sorted(self.projects_dir.glob("*.md"))
                if f.stem != "_index"]

    def get_project_index(self) -> str:
        idx = self._index_file()
        if idx.exists():
            return idx.read_text()
        return self._rebuild_project_index()

    def _rebuild_project_index(self) -> str:
        """Rebuild _index.md from all project files — one line per project."""
        projects = []
        for f in sorted(self.projects_dir.glob("*.md")):
            if f.stem == "_index":
                continue
            content = f.read_text()
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
        self._index_file().write_text(index_content)
        return index_content

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
        with decisions_file.open("a") as f:
            f.write(entry)
        return str(decisions_file)

    def recent_short_term(self, days: int = 3) -> list[tuple[str, str]]:
        """Return (date_str, content) for the last N short-term files."""
        if not self.config.short_term_dir.exists():
            return []
        files = sorted(self.config.short_term_dir.glob("*.md"), reverse=True)[:days]
        return [(f.stem, f.read_text()) for f in files]
