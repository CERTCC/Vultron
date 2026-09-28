"""Hold ``pyproject.toml``'s ``tag_regex`` to the release-tag policy.

ADR-0006 names a release with a three-component CalVer tag, ``vYYYY.M.P``,
and rejects alpha/beta/rc labels outright. ``setuptools_scm`` derives
``vultron.__version__`` from the first reachable tag its ``tag_regex``
accepts, so the regex is where that policy is enforced: a pattern that
admitted an ``rc`` suffix would let a tag the ADR forbids become the
published version, and one that admitted two components would let
``v2026.9`` masquerade as a release instead of falling back to
``0.0.0+dev`` (issue #3772).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def _tag_regex() -> re.Pattern[str]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return re.compile(config["tool"]["setuptools_scm"]["tag_regex"])


@pytest.mark.parametrize(
    ("tag", "version"),
    [
        ("v2026.9.0", "2026.9.0"),
        ("2026.10.0", "2026.10.0"),
        ("v2024.4.3", "2024.4.3"),
    ],
)
def test_three_component_release_tag_is_accepted(
    tag: str, version: str
) -> None:
    match = _tag_regex().match(tag)
    assert match is not None
    assert match.group("version") == version


@pytest.mark.parametrize(
    "tag",
    [
        "v2026.9",  # two components: ADR-0006 requires the patch component
        "v2026.9.0-rc1",  # pre-release labels are rejected
        "v2026.9.0.rc1",
        "v2026.9.0rc1",
        "v2026.9.0a1",
        "v2026.9.0b1",
        "snapshot-2026Q3",  # quarterly checkpoints are not releases
        "last-green-CI",
    ],
)
def test_non_release_tag_is_rejected(tag: str) -> None:
    assert _tag_regex().match(tag) is None
