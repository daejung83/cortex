"""
Cortex Curation Agent
---------------------
Runs in the background and maintains your brain automatically.

Tasks:
  - Rebuild active-context.md every N minutes from recent short-term notes
  - Distill yesterday's short-term notes into long-term memory (runs once/day)
  - Prune short-term files older than retention_days

Uses an LLM if configured (CORTEX_LLM_PROVIDER + CORTEX_LLM_API_KEY).
Falls back to heuristic extraction if no LLM configured.

Supported LLM providers:
  - anthropic (claude-haiku-3-5 by default — cheap and fast)
  - openai (gpt-4o-mini by default)
  - ollama (local, free)
"""

import os
import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from ..brain.schema import BrainConfig
from ..brain.manager import BrainManager
from ..curation.distiller import Distiller

logger = logging.getLogger("cortex.agent")


def get_llm_fn():
    """Return an LLM callable based on env config, or None for heuristic mode."""
    provider = os.environ.get("CORTEX_LLM_PROVIDER", "").lower()
    api_key = os.environ.get("CORTEX_LLM_API_KEY", "")
    model = os.environ.get("CORTEX_LLM_MODEL", "")

    if provider == "anthropic" and api_key:
        return _make_anthropic_fn(api_key, model or "claude-haiku-4-5")
    elif provider == "openai" and api_key:
        return _make_openai_fn(api_key, model or "gpt-4o-mini")
    elif provider == "ollama":
        return _make_ollama_fn(model or "llama3.2")
    else:
        logger.info("No LLM configured — using heuristic curation (set CORTEX_LLM_PROVIDER to enable AI curation)")
        return None


def _make_anthropic_fn(api_key: str, model: str):
    def call(prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    return call


def _make_openai_fn(api_key: str, model: str):
    def call(prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return resp.choices[0].message.content
    return call


def _make_ollama_fn(model: str):
    def call(prompt: str) -> str:
        import urllib.request, json
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["response"]
    return call


class CurationAgent:
    def __init__(
        self,
        config: BrainConfig,
        context_interval_minutes: int = 30,
        distill_hour: int = 3,          # 3am daily distillation
        retention_days: int = 30,
    ):
        self.config = config
        self.manager = BrainManager(config)
        self.context_interval = context_interval_minutes * 60
        self.distill_hour = distill_hour
        self.retention_days = retention_days
        self._last_distill_date: date | None = None

    def _get_distiller(self) -> Distiller:
        return Distiller(self.config, llm_fn=get_llm_fn())

    async def rebuild_context(self):
        """Rebuild active-context.md from recent short-term files."""
        try:
            distiller = self._get_distiller()
            distiller.build_active_context(days=2, max_lines=40)
            logger.info("active-context.md rebuilt")
        except Exception as e:
            logger.error(f"Context rebuild failed: {e}")

    async def distill_yesterday(self):
        """Distill yesterday's notes into long-term memory."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        yesterday_file = self.config.short_term_dir / f"{yesterday}.md"

        if not yesterday_file.exists():
            return

        try:
            distiller = self._get_distiller()
            distilled = distiller.distill(days=1)

            # Append to long-term projects file with date header
            projects_file = self.config.long_term_dir / "projects.md"
            if projects_file.exists():
                existing = projects_file.read_text(encoding="utf-8")
                entry = f"\n\n## Update — {yesterday}\n\n{distilled}"
                # Only append if not already there
                if yesterday not in existing:
                    with projects_file.open("a", encoding="utf-8") as f:
                        f.write(entry)
                    logger.info(f"Distilled {yesterday} into long-term memory")

        except Exception as e:
            logger.error(f"Distillation failed: {e}")

    async def prune_old_files(self):
        """
        Promote important entries then remove short-term files older than retention_days.
        Decisions + insights get promoted to long-term before deletion — nothing important is lost.
        """
        if not self.config.short_term_dir.exists():
            return

        from ..brain.manager import BrainManager
        manager = BrainManager(self.config)
        cutoff = date.today() - timedelta(days=self.retention_days)
        pruned = 0

        for f in self.config.short_term_dir.glob("*.md"):
            try:
                file_date = date.fromisoformat(f.stem)
                if file_date < cutoff:
                    await self._promote_entries(f, manager)
                    f.unlink()
                    pruned += 1
            except ValueError:
                pass

        if pruned:
            logger.info(f"Pruned {pruned} old short-term files (important entries promoted)")

    async def _promote_entries(self, file: Path, manager):
        """
        Extract tagged entries from a short-term file before deletion.
        - decision entries → long-term/decisions.md
        - insight entries → long-term/insights.md
        - session_summary → long-term/summaries/YYYY-MM.md
        """
        from pathlib import Path as P
        content = file.read_text(encoding="utf-8")
        file_date = file.stem  # YYYY-MM-DD

        current_heading = ""
        current_type = None
        current_lines = []

        def flush():
            if not current_lines or not current_type:
                return
            text = "\n".join(current_lines).strip()
            if not text:
                return

            if current_type == "decision":
                self._append_to_longterm("decisions.md", file_date, current_heading, text)
            elif current_type == "insight":
                self._append_to_longterm("insights.md", file_date, current_heading, text)
            elif current_type == "session_summary":
                self._append_to_monthly_summary(file_date, text)

        for line in content.splitlines():
            if line.startswith("## "):
                flush()
                current_heading = line[3:].strip()
                # Detect type from heading format: "HH:MM | decision"
                current_type = None
                current_lines = []
                if " | " in current_heading:
                    parts = current_heading.split(" | ", 1)
                    if len(parts) == 2:
                        current_type = parts[1].strip().lower().replace(" ", "_")
            else:
                if line.strip():
                    current_lines.append(line)

        flush()

    def _append_to_longterm(self, filename: str, date_str: str, heading: str, text: str):
        target = self.config.long_term_dir / filename
        entry = f"\n## {date_str} — {heading}\n{text}\n"
        with target.open("a", encoding="utf-8") as f:
            f.write(entry)

    def _append_to_monthly_summary(self, date_str: str, text: str):
        """Append session summary to long-term/summaries/YYYY-MM.md"""
        try:
            month = date_str[:7]  # YYYY-MM
        except Exception:
            return
        summaries_dir = self.config.long_term_dir / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        target = summaries_dir / f"{month}.md"
        if not target.exists():
            target.write_text(f"# Session Summaries — {month}\n\n", encoding="utf-8")
        with target.open("a", encoding="utf-8") as f:
            f.write(f"\n## {date_str}\n{text}\n")

    async def run(self):
        """Main agent loop."""
        logger.info(f"Curation agent started — context rebuild every {self.context_interval // 60}min")

        # Rebuild immediately on start
        await self.rebuild_context()

        while True:
            await asyncio.sleep(self.context_interval)
            await self.rebuild_context()

            # Daily distillation
            today = date.today()
            now = datetime.now()
            if (
                now.hour >= self.distill_hour
                and self._last_distill_date != today
            ):
                await self.distill_yesterday()
                await self.prune_old_files()
                self._last_distill_date = today
