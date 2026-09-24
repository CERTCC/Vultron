"""Tests for the site version-box label (issue #3550)."""

from __future__ import annotations

import pytest

from vultron.metadata.docs.build_version import (
    FALLBACK_VERSION,
    describe_build,
    is_release,
)


@pytest.mark.parametrize("version", ["2026.9.0", "2024.4.3", "2026.9.0rc1"])
def test_tagged_version_is_release(version: str) -> None:
    assert is_release(version)
    assert f"release **{version}**" in describe_build(version)


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
