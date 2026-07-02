"""Virtual File System for skills/*.md with versioned evolution history."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def default_skills_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills"


def default_evolution_root() -> Path:
    return default_skills_root() / ".evolution"


@dataclass
class SkillSection:
    heading: str
    level: int
    start_line: int  # 0-based, inclusive
    end_line: int  # 0-based, exclusive
    content: str


def parse_sections(markdown: str) -> List[SkillSection]:
    """Split markdown by ## / ### headings (preserve frontmatter as preamble)."""
    lines = markdown.splitlines(keepends=True)
    sections: List[SkillSection] = []
    current_heading = "__preamble__"
    current_level = 0
    start = 0

    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,4})\s+(.+?)\s*$", line)
        if not m:
            continue
        if i > start or (i == 0 and sections):
            chunk = "".join(lines[start:i])
            sections.append(
                SkillSection(current_heading, current_level, start, i, chunk)
            )
        current_level = len(m.group(1))
        current_heading = m.group(2).strip()
        start = i

    if start < len(lines):
        sections.append(
            SkillSection(
                current_heading,
                current_level,
                start,
                len(lines),
                "".join(lines[start:]),
            )
        )
    return sections


def find_section(sections: List[SkillSection], heading_substr: str) -> Optional[SkillSection]:
    needle = heading_substr.lower()
    for sec in sections:
        if needle in sec.heading.lower():
            return sec
    return None


class SkillVFS:
    """Read/write skill files with immutable version commits."""

    def __init__(
        self,
        skills_root: Optional[Path] = None,
        evolution_root: Optional[Path] = None,
    ):
        self.skills_root = Path(skills_root or default_skills_root())
        self.evolution_root = Path(evolution_root or default_evolution_root())

    def skill_path(self, skill_name: str) -> Path:
        name = skill_name.removesuffix(".md")
        return self.skills_root / f"{name}.md"

    def _version_dir(self, skill_name: str) -> Path:
        name = skill_name.removesuffix(".md")
        return self.evolution_root / name

    def _manifest_path(self, skill_name: str) -> Path:
        return self._version_dir(skill_name) / "manifest.json"

    def read_skill(self, skill_name: str, *, version: Optional[int] = None) -> str:
        if version is None:
            path = self.skill_path(skill_name)
            if not path.exists():
                raise FileNotFoundError(path)
            return path.read_text(encoding="utf-8")

        vpath = self._version_dir(skill_name) / f"v{version}" / "SKILL.md"
        if not vpath.exists():
            raise FileNotFoundError(vpath)
        return vpath.read_text(encoding="utf-8")

    def list_skills(self) -> List[str]:
        return sorted(p.stem for p in self.skills_root.glob("*.md"))

    def current_version(self, skill_name: str) -> int:
        manifest = self._load_manifest(skill_name)
        return int(manifest.get("current_version", 0))

    def _load_manifest(self, skill_name: str) -> Dict:
        path = self._manifest_path(skill_name)
        if not path.exists():
            return {"current_version": 0, "history": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_manifest(self, skill_name: str, manifest: Dict) -> None:
        vdir = self._version_dir(skill_name)
        vdir.mkdir(parents=True, exist_ok=True)
        self._manifest_path(skill_name).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def commit_version(
        self,
        skill_name: str,
        content: str,
        *,
        diagnostic_path: Optional[Path] = None,
        note: str = "",
    ) -> int:
        """Snapshot skill content as next version; optionally copy diagnostic artifact."""
        manifest = self._load_manifest(skill_name)
        next_v = int(manifest.get("current_version", 0)) + 1
        vdir = self._version_dir(skill_name) / f"v{next_v}"
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "SKILL.md").write_text(content, encoding="utf-8")

        entry = {"version": next_v, "note": note}
        if diagnostic_path and diagnostic_path.exists():
            dest = vdir / "diagnostic.json"
            shutil.copy2(diagnostic_path, dest)
            entry["diagnostic"] = str(dest.name)

        history = manifest.get("history", [])
        history.append(entry)
        manifest["current_version"] = next_v
        manifest["history"] = history
        self._save_manifest(skill_name, manifest)
        return next_v

    def write_live_skill(self, skill_name: str, content: str) -> Path:
        path = self.skill_path(skill_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def apply_section_patch(
        self,
        content: str,
        section_heading: str,
        patch_text: str,
        *,
        action: str = "append",
    ) -> Tuple[str, bool]:
        """Apply minimal additive patch to a section. Returns (new_content, changed)."""
        if not patch_text.strip():
            return content, False

        sections = parse_sections(content)
        target = find_section(sections, section_heading)
        if target is None:
            return content, False

        block = target.content
        marker = f"<!-- skillforge-evidence:{section_heading} -->"
        if marker in block and patch_text.strip() in block:
            return content, False

        if action == "append":
            addition = f"\n\n{marker}\n{patch_text.rstrip()}\n"
            new_block = block.rstrip() + addition + "\n"
        elif action == "insert_after":
            lines = block.splitlines(keepends=True)
            insert_at = 1 if lines else 0
            addition = f"{marker}\n{patch_text.rstrip()}\n"
            new_block = "".join(lines[:insert_at]) + addition + "".join(lines[insert_at:])
        else:
            return content, False

        lines = content.splitlines(keepends=True)
        new_lines = (
            lines[: target.start_line]
            + [new_block]
            + lines[target.end_line :]
        )
        return "".join(new_lines), True
