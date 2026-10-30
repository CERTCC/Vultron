"""Tests that skill and notes guidance uses ``append-history`` as specified.

Covers: HM-05-004 (``learn`` reads no legacy history file), HM-07-008 (no
frontmatter-in-stdin example for ``append-history``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / ".agents" / "skills"
_HISTORY_NOTE = _REPO_ROOT / "notes" / "history-management.md"

_FENCE = re.compile(r"^\s*(```|~~~)")
_FRONTMATTER_KEY = re.compile(r"^\s*(title|type|source|timestamp):")


def _fenced_blocks(text: str) -> list[list[str]]:
    """Return the lines of each fenced code block in *text*."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if _FENCE.match(line):
            if current is None:
                current = []
            else:
                blocks.append(current)
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def _frontmatter_examples(text: str) -> list[str]:
    """Return each ``append-history`` block that writes a frontmatter key."""
    return [
        "\n".join(block)
        for block in _fenced_blocks(text)
        if any("append-history" in line for line in block)
        and any(_FRONTMATTER_KEY.match(line) for line in block)
    ]


@pytest.mark.spec("HM-05-004")
def test_learn_skill_reads_no_legacy_history_file() -> None:
    """The ``learn`` skill names no ``plan/*HISTORY.md`` file to read."""
    text = (_SKILLS_DIR / "learn" / "SKILL.md").read_text()
    assert "HISTORY.md" not in text


@pytest.mark.spec("HM-07-008")
def test_guidance_shows_no_frontmatter_in_stdin() -> None:
    """No skill or the history note pipes frontmatter into append-history."""
    sources = [*sorted(_SKILLS_DIR.glob("*/SKILL.md")), _HISTORY_NOTE]
    offenders = {
        str(path.relative_to(_REPO_ROOT)): examples
        for path in sources
        if (examples := _frontmatter_examples(path.read_text()))
    }
    assert not offenders, offenders


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        (
            "```bash\ncat <<'B' | uv run append-history idea\n---\ntitle: T\n---\nB\n```",
            1,
        ),
        (
            "```bash\ncat <<'B' | uv run append-history note \\\n  --title T\n---\nbody\nB\n```",
            0,
        ),
        ("```yaml\ntitle: T\n```", 0),
    ],
)
def test_frontmatter_detector(block: str, expected: int) -> None:
    """The detector flags frontmatter keys, not a horizontal rule or flags."""
    assert len(_frontmatter_examples(block)) == expected
