from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@dataclass(frozen=True)
class ResearchSkill:
    name: str
    path: Path
    text: str


class ResearchSkillRegistry:
    """Loads markdown skills used by the fixed research workflow."""

    def __init__(self, mode: str = "academic", skills_dir: Path | None = None):
        base = skills_dir or SKILLS_DIR
        if mode == "visual":
            self.skills_dir = base / "visual"
        else:
            self.skills_dir = base

    def load(self, name: str) -> ResearchSkill:
        path = self.skills_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Research skill not found: {path}")
        return ResearchSkill(name=name, path=path, text=path.read_text(encoding="utf-8"))

    def load_text(self, name: str) -> str:
        return self.load(name).text
