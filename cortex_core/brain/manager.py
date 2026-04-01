"""
BrainManager — read/write operations on brain files.
"""

from pathlib import Path
from datetime import date, datetime
from typing import Optional
from .schema import BrainConfig


class BrainManager:
    def __init__(self, config: BrainConfig):
        self.config = config

    def init(self):
        """Initialize brain directory structure."""
        self.config.short_term_dir.mkdir(parents=True, exist_ok=True)
        self.config.long_term_dir.mkdir(parents=True, exist_ok=True)

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

    def recent_short_term(self, days: int = 3) -> list[tuple[str, str]]:
        """Return (date_str, content) for the last N short-term files."""
        if not self.config.short_term_dir.exists():
            return []
        files = sorted(self.config.short_term_dir.glob("*.md"), reverse=True)[:days]
        return [(f.stem, f.read_text()) for f in files]
