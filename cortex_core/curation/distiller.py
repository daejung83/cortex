"""
Distiller — turns raw short-term notes into structured long-term memory.

Two modes:
  Heuristic (default): fast, no API cost, grabs recent lines
  LLM mode: uses Claude/GPT/Ollama to produce a clean distilled summary

Configure LLM via env vars:
  CORTEX_LLM_PROVIDER = anthropic | openai | ollama
  CORTEX_LLM_API_KEY  = your API key (not needed for ollama)
  CORTEX_LLM_MODEL    = override default model (optional)

Runs automatically via curation agent, or on-demand:
  cortex distill --days 3
  cortex build-context --days 2
"""

import os
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

ACTIVE_CONTEXT_PROMPT = """You are a memory curator. Below are raw session notes from the last {days} days.

Write a clean, dense active-context summary in markdown. Max {max_lines} lines.

Rules:
- Lead with session summaries if present
- Include decisions and progress
- Skip noise (next_steps fillers, duplicate lines, one-word entries)
- Preserve specific details: names, numbers, URLs, tech choices
- Use bullet points, not paragraphs

---
SESSION NOTES:
{notes}
---

Output clean markdown only. Start with: # Active Context
"""


class Distiller:
    def __init__(self, config: BrainConfig, llm_fn=None):
        """
        config: BrainConfig
        llm_fn: callable(prompt: str) -> str
                If None, uses heuristic mode (no API cost).
                Auto-detected from env vars if not passed.
        """
        self.config = config
        self.manager = BrainManager(config)
        self.llm_fn = llm_fn or self._detect_llm()

    def _detect_llm(self):
        """Auto-detect LLM from environment variables."""
        from ..agent.curator import get_llm_fn
        return get_llm_fn()

    def distill(self, days: int = 3) -> str:
        """Distill recent short-term notes into structured long-term memory."""
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
        """Simple extraction without LLM — grabs headings and content."""
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
        """
        Build active-context.md from recent short-term files.

        LLM mode: sends notes to LLM for intelligent distillation
        Heuristic mode: prioritizes session_summary > decision/insight > other
        """
        recent = self.manager.recent_short_term(days=days)
        if not recent:
            return "No recent context available."

        if self.llm_fn:
            result = self._llm_build_context(recent, days, max_lines)
        else:
            result = self._heuristic_build_context(recent, max_lines)

        # Atomic write
        tmp = self.config.active_context_file.with_suffix(".tmp")
        tmp.write_text(result, encoding="utf-8")
        import os
        os.replace(tmp, self.config.active_context_file)
        return result

    def _llm_build_context(self, recent: list[tuple[str, str]], days: int, max_lines: int) -> str:
        """Use LLM to produce a clean active context summary."""
        combined = "\n\n---\n\n".join(
            f"## {date_str}\n\n{content}" for date_str, content in recent
        )
        prompt = ACTIVE_CONTEXT_PROMPT.format(days=days, notes=combined, max_lines=max_lines)
        try:
            result = self.llm_fn(prompt)
            # Ensure it starts with the right header
            if not result.strip().startswith("# Active Context"):
                result = f"# Active Context\n_Last updated: {date.today().isoformat()}_\n\n{result}"
            return result
        except Exception as e:
            # Fallback to heuristic if LLM fails
            return self._heuristic_build_context(recent, max_lines)

    def _heuristic_build_context(self, recent: list[tuple[str, str]], max_lines: int) -> str:
        """
        Heuristic build — prioritizes by entry type:
          1. session_summary (most distilled)
          2. decision / insight (high value)
          3. progress (useful)
          4. everything else
        """
        PRIORITY = {"session_summary": 0, "decision": 1, "insight": 1, "progress": 2}

        # Parse entries with their types
        entries = []  # (priority, date_str, heading, lines)
        for date_str, content in recent:
            current_heading = ""
            current_type = "other"
            current_lines = []

            for line in content.splitlines():
                if line.startswith("## "):
                    if current_lines:
                        p = PRIORITY.get(current_type, 3)
                        entries.append((p, date_str, current_heading, list(current_lines)))
                    current_heading = line[3:].strip()
                    current_type = "other"
                    if " | " in current_heading:
                        parts = current_heading.split(" | ", 1)
                        if len(parts) == 2:
                            current_type = parts[1].strip().lower()
                    current_lines = []
                elif line.strip():
                    current_lines.append(line)

            if current_lines:
                p = PRIORITY.get(current_type, 3)
                entries.append((p, date_str, current_heading, list(current_lines)))

        # Sort by priority then date (newest first)
        entries.sort(key=lambda e: (e[0], e[1]), reverse=False)
        # Re-sort by priority asc, date desc
        entries.sort(key=lambda e: (e[0], [-ord(c) for c in e[1]]))

        lines_out = [
            "# Active Context\n",
            f"_Last updated: {date.today().isoformat()}_\n",
        ]
        total = 2

        for priority, date_str, heading, entry_lines in entries:
            if total >= max_lines:
                break
            lines_out.append(f"## {date_str} — {heading}")
            total += 1
            for line in entry_lines:
                if total >= max_lines:
                    break
                lines_out.append(line)
                total += 1

        return "\n".join(lines_out)
