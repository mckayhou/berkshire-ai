#!/usr/bin/env python3
"""SkillForge CLI — evolve berkshire-ai skills from bad-case evidence.

Subcommands:
  list | judge | analyze | evolve | status | create

Examples:
  python3 tools/skill_evolve.py list
  python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/tasks_unlabeled.jsonl --judge-mode auto
  python3 tools/skill_evolve.py analyze tests/fixtures/skill_forge/bad_cases.jsonl --judge-mode rule
  python3 tools/skill_evolve.py evolve investment-research --rounds 1 --dry-run --judge-mode auto
  python3 tools/skill_evolve.py status investment-research

Docs: docs/SKILL_EVOLUTION.md
Tests: pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from skill_forge.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
