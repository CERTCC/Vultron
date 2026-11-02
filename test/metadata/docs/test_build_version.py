"""Tests for the footer line naming each page's publish and build (#3550, #5544)."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from vultron.metadata.docs import build_version
from vultron.metadata.docs.build_version import (
    FALLBACK_VERSION,
    FOOTER_KEY,
    PUBLISH_DATE_ENV,
    PUBLISH_TAG_ENV,
    RELEASE_TAG_ENV,
    Publish,
    PublishLabelError,
    describe_build,
    is_release,
    on_config,
    publish_from_env,
)

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"
REPO = "https://github.com/CERTCC/Vultron"
DEV = "2026.10.1.dev570+gabc123"
TAG = "publish-2026-10-30.1"
PUBLISH = Publish(TAG, date(2026, 10, 30))


def _link(tag: str) -> str:
    return f'<a href="{REPO}/tree/{tag}">{tag}</a>'


# --- the build version (#3550) -------------------------------------------------


@pytest.mark.parametrize("version", ["2026.9.0", "2024.4.3"])
def test_tagged_version_is_release(version: str) -> None:
    assert is_release(version)
    assert f"release {version}" in describe_build(version, None, REPO)


def test_no_build_is_described_as_a_pre_release() -> None:
    # ADR-0006 rejects alpha/beta/rc tags and tag_regex admits none, so the
    # renderer has no pre-release wording to fall into for any input.
    for version in ("2026.9.0", "2026.9.0rc1", FALLBACK_VERSION, "junk"):
        for publish in (None, PUBLISH):
            assert "pre-release" not in describe_build(version, publish, REPO)


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
    text = describe_build(version, None, REPO)
    assert version in text
    assert "release" not in text


@pytest.mark.parametrize("version", [FALLBACK_VERSION, "unknown version"])
def test_fallback_and_unparseable_are_not_releases(version: str) -> None:
    assert not is_release(version)
    assert f"release {version}" not in describe_build(version, None, REPO)


def test_fallback_does_not_print_placeholder_version() -> None:
    text = describe_build(FALLBACK_VERSION, None, REPO)
    assert FALLBACK_VERSION not in text
    assert "no release tag in its history" in text


# --- the publish (#5544) -------------------------------------------------------


def test_unpublished_build_says_so() -> None:
    assert describe_build(DEV, None, REPO) == f"Unpublished build · {DEV}"


def test_publish_names_its_date_tag_and_build() -> None:
    assert describe_build(DEV, PUBLISH, REPO) == (
        f"Published 2026-10-30 · {_link(TAG)} · {DEV}"
    )


def test_a_released_commit_names_its_release() -> None:
    publish = Publish(TAG, date(2026, 10, 30), "v2026.11.0")
    text = describe_build("2026.11.0", publish, REPO)
    assert text == (
        f"Published 2026-10-30 · {_link(TAG)} · release {_link('v2026.11.0')}"
    )


def test_tag_links_ignore_a_trailing_slash_on_the_repo_url() -> None:
    assert _link(TAG) in describe_build(DEV, PUBLISH, f"{REPO}/")


def test_values_are_escaped_into_the_html() -> None:
    publish = Publish('publish-<b>"x"', date(2026, 10, 30))
    text = describe_build("<script>", publish, REPO)
    assert "<b>" not in text and "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "/tree/publish-%3Cb%3E%22x%22" in text


# --- reading the environment ---------------------------------------------------


def test_no_variables_is_an_unpublished_build() -> None:
    assert publish_from_env({}) is None


def test_empty_variables_are_unset() -> None:
    # The workflow passes "" for an output it has no value for.
    env = {PUBLISH_TAG_ENV: "", PUBLISH_DATE_ENV: " ", RELEASE_TAG_ENV: ""}
    assert publish_from_env(env) is None


def test_the_publish_variables_are_read() -> None:
    env = {
        PUBLISH_TAG_ENV: TAG,
        PUBLISH_DATE_ENV: "2026-10-30",
        RELEASE_TAG_ENV: "v2026.11.0",
    }
    assert publish_from_env(env) == Publish(
        TAG, date(2026, 10, 30), "v2026.11.0"
    )
    del env[RELEASE_TAG_ENV]
    assert publish_from_env(env) == PUBLISH


@pytest.mark.parametrize(
    "env",
    [
        {PUBLISH_TAG_ENV: TAG},
        {PUBLISH_DATE_ENV: "2026-10-30"},
        {PUBLISH_TAG_ENV: TAG, PUBLISH_DATE_ENV: "30 Oct 2026"},
        # date.fromisoformat would take both of these.
        {PUBLISH_TAG_ENV: TAG, PUBLISH_DATE_ENV: "20261030"},
        {PUBLISH_TAG_ENV: TAG, PUBLISH_DATE_ENV: "2026-W44-5"},
        # The tag names another day than the date.
        {PUBLISH_TAG_ENV: TAG, PUBLISH_DATE_ENV: "2026-10-31"},
        {RELEASE_TAG_ENV: "v2026.11.0"},
    ],
    ids=[
        "tag-only",
        "date-only",
        "bad-date",
        "basic-format-date",
        "week-date",
        "date-mismatch",
        "release-only",
    ],
)
def test_half_a_publish_is_refused(env: dict[str, str]) -> None:
    with pytest.raises(PublishLabelError):
        publish_from_env(env)


# --- the MkDocs hook -----------------------------------------------------------


def _config(repo_url: str | None = REPO) -> SimpleNamespace:
    return SimpleNamespace(repo_url=repo_url, extra={})


def test_hook_renders_an_unpublished_footer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (PUBLISH_TAG_ENV, PUBLISH_DATE_ENV, RELEASE_TAG_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(build_version, "__version__", DEV)
    config = _config()
    assert on_config(config) is config  # type: ignore[arg-type]
    assert config.extra[FOOTER_KEY] == f"Unpublished build · {DEV}"


def test_hook_renders_the_publish_jobs_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PUBLISH_TAG_ENV, TAG)
    monkeypatch.setenv(PUBLISH_DATE_ENV, "2026-10-30")
    monkeypatch.delenv(RELEASE_TAG_ENV, raising=False)
    monkeypatch.setattr(build_version, "__version__", DEV)
    config = _config()
    on_config(config)  # type: ignore[arg-type]
    assert config.extra[FOOTER_KEY] == (
        f"Published 2026-10-30 · {_link(TAG)} · {DEV}"
    )


def test_hook_is_registered_and_the_footer_partial_reads_its_key() -> None:
    """Jinja prints an undefined value as nothing, so drift blanks every footer."""
    root = Path(__file__).resolve().parents[3]
    mkdocs_yml = (root / "mkdocs.yml").read_text(encoding="utf-8")
    assert "  - vultron/metadata/docs/build_version.py\n" in mkdocs_yml
    partial = root / "overrides" / "partials" / "copyright.html"
    assert f"{{{{ config.extra.{FOOTER_KEY} }}}}" in partial.read_text(
        encoding="utf-8"
    )


def test_hook_needs_a_repo_url_to_link_tags() -> None:
    with pytest.raises(PublishLabelError, match="repo_url"):
        on_config(_config(None))  # type: ignore[arg-type]
