"""
Distiller — turns raw short-term notes into structured long-term memory.

Uses an LLM to extract:
- Project updates
- Decisions made
- Things learned
- Next steps

Runs automatically after sessions (via cortex agent) or on-demand:
    cortex distill --days 3
"""

from pathlib import Path
from datetime import date, timedelta
from typing import Optional
from ..brain.schema import BrainConfig
from ..brain.manager import BrainManager


DISTILL_PROMPT = """You are a memory curator. Below are raw session notes from the last {days} days.

Extract and structure the following into clean markdown:

1. **Project Updates** — what changed in each active project
2. **Decisions Made** — any choices made with brief rationale
3. **Lessons Learned** — insights, mistakes, things to remember
4. **Next Steps** — what's in progress or planned

Be concise. Skip filler. Each entry should be a single line if possible.
Preserve specific numbers, names, and technical details exactly.

---
SESSION NOTES:
{notes}
---

Output clean markdown only. No preamble.
"""


class Distiller:
    def __init__(self, config: BrainConfig, llm_fn=None):
        """
        config: BrainConfig
        llm_fn: callable(prompt: str) -> str
                If None, uses a simple heuristic extractor (no LLM needed).
        """
        self.config = config
        self.manager = BrainManager(config)
        self.llm_fn = llm_fn

    def distill(self, days: int = 3) -> str:
        """Distill recent short-term notes. Returns distilled markdown."""
        recent = self.manager.recent_short_term(days=days)
        if not recent:
            return "No recent notes to distill."

        combined = "\n\n---\n\n".join(
            f"## {date_str}\n\n{content}" for date_str, content in recent
        )

        if self.llm_fn:
            prompt = DISTILL_PROMPT.format(days=days, notes=combined)
            return self.llm_fn(prompt)
        else:
            return self._heuristic_distill(recent)

    def _heuristic_distill(self, recent: list[tuple[str, str]]) -> str:
        """Simple extraction without LLM — grabs ## headings and their content."""
        lines_out = ["# Distilled Memory\n"]
        for date_str, content in recent:
            lines_out.append(f"## From {date_str}\n")
            in_section = False
            for line in content.splitlines():
                if line.startswith("## "):
                    in_section = True
                    lines_out.append(f"### {line[3:]}")
                elif in_section and line.strip():
                    lines_out.append(line)
            lines_out.append("")
        return "\n".join(lines_out)

    def build_active_context(self, days: int = 2, max_lines: int = 40) -> str:
        """Build active-context.md from recent short-term files."""
        recent = self.manager.recent_short_term(days=days)
        if not recent:
            return "No recent context available."

        lines = ["# Active Context\n", f"_Last updated: {date.today().isoformat()}_\n"]
        total_lines = 2

        for date_str, content in recent:
            for line in content.splitlines():
                if total_lines >= max_lines:
                    break
                if line.strip():
                    lines.append(line)
                    total_lines += 1

        result = "\n".join(lines)

        # Atomic write — prevents half-written file if AI reads during rebuild
        import os
        tmp = self.config.active_context_file.with_suffix(".tmp")
        tmp.write_text(result)
        os.replace(tmp, self.config.active_context_file)
        return result
