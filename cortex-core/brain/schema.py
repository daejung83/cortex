"""
Cortex Brain Schema
-------------------
Defines the brain directory structure and file conventions.

Brain Layout:
    brain/
    ├── short-term/
    │   └── YYYY-MM-DD.md       # Daily session notes (raw, auto-generated)
    ├── long-term/
    │   ├── projects.md         # Active projects + current state
    │   ├── decisions.md        # Key decisions with rationale
    │   ├── people.md           # People, orgs, relationships
    │   └── <topic>.md          # Any other long-term topic file
    ├── active-context.md       # Hot context rebuilt periodically (last 48hrs distilled)
    └── always-on.md            # Permanent context always loaded into AI

File Conventions:
    - All files are UTF-8 markdown
    - Entries are prefixed with ## headings
    - Timestamps use ISO 8601 (YYYY-MM-DD or YYYY-MM-DD HH:MM)
    - Files are human-readable and human-editable
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


BRAIN_STRUCTURE = {
    "short_term_dir": "short-term",
    "long_term_dir": "long-term",
    "active_context_file": "active-context.md",
    "always_on_file": "always-on.md",
}

LONG_TERM_DEFAULT_FILES = [
    "projects.md",
    "decisions.md",
    "people.md",
]


@dataclass
class BrainConfig:
    root: Path
    short_term_dir: Path
    long_term_dir: Path
    active_context_file: Path
    always_on_file: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "BrainConfig":
        root = Path(root)
        return cls(
            root=root,
            short_term_dir=root / BRAIN_STRUCTURE["short_term_dir"],
            long_term_dir=root / BRAIN_STRUCTURE["long_term_dir"],
            active_context_file=root / BRAIN_STRUCTURE["active_context_file"],
            always_on_file=root / BRAIN_STRUCTURE["always_on_file"],
        )

    def validate(self) -> list[str]:
        """Return list of warnings about missing expected files/dirs."""
        warnings = []
        if not self.short_term_dir.exists():
            warnings.append(f"short-term dir missing: {self.short_term_dir}")
        if not self.long_term_dir.exists():
            warnings.append(f"long-term dir missing: {self.long_term_dir}")
        if not self.active_context_file.exists():
            warnings.append(f"active-context.md missing — run: cortex build-context")
        if not self.always_on_file.exists():
            warnings.append(f"always-on.md missing — run: cortex build-always-on")
        return warnings
