"""
BrainSearcher — semantic + keyword search across all brain files.

Fast mode: keyword/grep-style, no embeddings needed, instant results.
Semantic mode: uses sentence-transformers for meaning-based search (optional dep).
"""

import re
from pathlib import Path
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

    def _all_brain_files(self) -> list[Path]:
        files = []
        for d in [self.config.short_term_dir, self.config.long_term_dir]:
            if d.exists():
                files.extend(sorted(d.glob("*.md"), reverse=True))
        for f in [self.config.active_context_file, self.config.always_on_file]:
            if f.exists():
                files.append(f)
        return files

    def search(self, query: str, max_results: int = 10, fast: bool = True) -> list[SearchResult]:
        """
        Search brain files for query.
        fast=True: keyword match (default, no deps)
        fast=False: semantic search (requires sentence-transformers)
        """
        if fast:
            return self._keyword_search(query, max_results)
        else:
            return self._semantic_search(query, max_results)

    def _keyword_search(self, query: str, max_results: int) -> list[SearchResult]:
        terms = query.lower().split()
        results = []

        for path in self._all_brain_files():
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

    def _semantic_search(self, query: str, max_results: int) -> list[SearchResult]:
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
        for path in self._all_brain_files():
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
