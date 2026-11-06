"""The push gates call the CI mirror before they push.

PAD-18-021: `create-pr` runs `prepush-ci-mirror` before its first push, and
`pr-execute` before each push. A skill is prose, so these tests pin where the
command sits relative to the push step.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[2] / ".agents" / "skills"


def _text(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


@pytest.mark.spec("PAD-18-021")
def test_create_pr_runs_the_mirror_before_its_push():
    text = _text("create-pr")
    mirror = _section(text, "### 3c — CI mirror", "## Phase 4")

    assert "uv run prepush-ci-mirror" in mirror
    assert 'echo "exit: $rc"' in mirror
    assert text.index("### 3c — CI mirror") < text.index(
        "git push -u origin HEAD"
    )
    assert "Never push past a failing Phase 3c mirror" in text


@pytest.mark.spec("PAD-18-021")
def test_pr_execute_runs_the_mirror_before_each_push():
    text = _text("pr-execute")
    gate = _section(
        text, "#### Step 3 — Run the local gate", "#### Step 4 — Push"
    )

    assert "uv run prepush-ci-mirror --base <base_ref> --pr <number>" in gate
    assert 'echo "exit: $rc"' in gate


@pytest.mark.spec("PAD-18-021")
@pytest.mark.parametrize("skill", ["create-pr", "pr-execute"])
def test_the_type_checkers_share_the_mirrors_memo(skill: str):
    # The mirror runs mypy and pyright through run-if-changed.sh; a bare run
    # just before it would leave no record and type-check the tree twice.
    text = _text(skill)

    assert "uv run ruff check && uv run mypy" not in text
    assert '"$G" pyright vultron/ test/ pyrightconfig.json uv.lock' in text
