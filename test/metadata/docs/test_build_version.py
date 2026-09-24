"""Tests for the site version-box label (issue #3550)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from vultron.metadata.docs.build_version import (
    FALLBACK_VERSION,
    describe_build,
    is_release,
)

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


@pytest.mark.parametrize("version", ["2026.9.0", "2024.4.3"])
def test_tagged_version_is_release(version: str) -> None:
    assert is_release(version)
    assert f"built from release **{version}**" in describe_build(version)


def test_release_candidate_is_labelled_pre_release() -> None:
    # setuptools_scm normalizes a v2026.9.0-rc1 tag to 2026.9.0rc1.
    assert is_release("2026.9.0rc1")
    assert "pre-release **2026.9.0rc1**" in describe_build("2026.9.0rc1")


def test_fallback_matches_pyproject() -> None:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    scm = config["tool"]["setuptools_scm"]
    assert scm["fallback_version"] == FALLBACK_VERSION


@pytest.mark.parametrize(
    "version",
    [
        "2024.4.4.dev7128+g8957cba68",
        "2024.4.4.dev7128+g8957cba68.d20260924",
        "2026.9.0+d20260924",
    ],
)
def test_untagged_version_is_development_build(version: str) -> None:
    assert not is_release(version)
    text = describe_build(version)
    assert "unreleased development build" in text
    assert f"`{version}`" in text
    assert "release **" not in text


@pytest.mark.parametrize("version", [FALLBACK_VERSION, "unknown version"])
def test_fallback_and_unparseable_are_not_releases(version: str) -> None:
    assert not is_release(version)
    assert "unreleased development build" in describe_build(version)


def test_fallback_does_not_print_placeholder_version() -> None:
    assert FALLBACK_VERSION not in describe_build(FALLBACK_VERSION)
