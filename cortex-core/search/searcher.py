"""
BrainSearcher — semantic + keyword search across all brain files.

Fast mode: keyword/grep-style, no embeddings needed, instant results.
Semantic mode: uses sentence-transformers for meaning-based search (optional dep).
"""

import re
from pathlib import Path
from datetime import date, timedelta
from typing import Optional
from ..brain.schema import BrainConfig


class SearchResult:
    def __init__(self, file: Path, line_no: int, heading: str, snippet: str, score: float = 0.0):
        self.file = file
        self.line_no = line_no
        self.heading = heading
        self.snippet = snippet
        self.score = score

    def __repr__(self):
        return f"[{self.file.name}:{self.line_no}] {self.heading}\n  {self.snippet}"


class BrainSearcher:
    def __init__(self, config: BrainConfig):
        self.config = config

    def _all_brain_files(self, days: Optional[int] = None) -> list[Path]:
        files = []

        # Short-term: optionally filter by date range
        if self.config.short_term_dir.exists():
            short_files = sorted(self.config.short_term_dir.glob("*.md"), reverse=True)
            if days is not None:
                cutoff = date.today() - timedelta(days=days)
                short_files = [
                    f for f in short_files
                    if self._file_date(f) >= cutoff
                ]
            files.extend(short_files)

        # Long-term always included (small, curated)
        if self.config.long_term_dir.exists():
            files.extend(sorted(self.config.long_term_dir.glob("*.md"), reverse=True))

        # Always-on + active context always included
        for f in [self.config.active_context_file, self.config.always_on_file]:
            if f.exists():
                files.append(f)

        return files

    def _file_date(self, path: Path) -> date:
        """Parse date from short-term filename YYYY-MM-DD.md, fallback to today."""
        try:
            return date.fromisoformat(path.stem)
        except ValueError:
            return date.today()

    def search(self, query: str, max_results: int = 10, fast: bool = True, days: Optional[int] = None) -> list[SearchResult]:
        """
        Search brain files for query.
        fast=True: keyword match (default, no deps)
        fast=False: semantic search (requires sentence-transformers)
        """
        if fast:
            return self._keyword_search(query, max_results, days=days)
        else:
            return self._semantic_search(query, max_results, days=days)

    def _keyword_search(self, query: str, max_results: int, days: Optional[int] = None) -> list[SearchResult]:
        terms = query.lower().split()
        results = []

        for path in self._all_brain_files(days=days):
            try:
                lines = path.read_text().splitlines()
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
                    snippet = line.strip()[:120]
                    results.append(SearchResult(
                        file=path,
                        line_no=i,
                        heading=current_heading,
                        snippet=snippet,
                        score=matches / len(terms),
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def _semantic_search(self, query: str, max_results: int, days: Optional[int] = None) -> list[SearchResult]:
        try:
            from sentence_transformers import SentenceTransformer, util
            import torch
        except ImportError:
            raise ImportError(
                "Semantic search requires: pip install sentence-transformers torch\n"
                "Or use fast=True for keyword search."
            )

        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_emb = model.encode(query, convert_to_tensor=True)

        candidates = []
        for path in self._all_brain_files(days=days):
            try:
                lines = path.read_text().splitlines()
            except Exception:
                continue

            current_heading = path.stem
            for i, line in enumerate(lines, 1):
                if line.startswith("#"):
                    current_heading = line.lstrip("#").strip()
                    continue
                if len(line.strip()) < 20:
                    continue
                candidates.append((path, i, current_heading, line.strip()))

        if not candidates:
            return []

        texts = [c[3] for c in candidates]
        text_embs = model.encode(texts, convert_to_tensor=True, batch_size=64)
        scores = util.cos_sim(query_emb, text_embs)[0]

        top_indices = scores.topk(min(max_results, len(candidates))).indices
        results = []
        for idx in top_indices:
            path, line_no, heading, snippet = candidates[idx]
            results.append(SearchResult(
                file=path,
                line_no=line_no,
                heading=heading,
                snippet=snippet[:120],
                score=float(scores[idx]),
            ))

        return results
