"""CI verification test — the shared tag queries (DOCBW-07-006, ADR-0171).

``.github/scripts/release_tags.py`` answers every question the publish gate,
the promote workflow, the release tag check and the staleness alarm ask about
``publish-*`` and ``v*`` tags. The pure queries are pinned here on built
``Tag`` values; the reader runs against a scratch repository, so what git
records is what the queries see.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from test.ci._scratch_git import (
    commit,
    git,
    head,
    isolate_git_config,
    scratch_clone,
    tag_as_bot,
)
from test.ci._scripts import load_script

_tags = load_script("release_tags")
Tag = _tags.Tag
BOT = (_tags.BOT_NAME, _tags.BOT_EMAIL)


def _bot(name: str, commit_id: str = "c1") -> object:
    return Tag(name, True, *BOT, commit_id)


def _hand(name: str, commit_id: str = "c1") -> object:
    return Tag(name, True, "Some Person", "p@example.org", commit_id)


# --- which tags count as a publish ---------------------------------------------


@pytest.mark.spec("DOCBW-06-014", "DOCBW-07-006")
def test_only_a_bot_made_well_named_tag_is_a_publish() -> None:
    own, ignored = _tags.split_publish_tags(
        [
            _bot("publish-2026-11-02.1"),
            _hand("publish-2026-11-02.2"),
            Tag("publish-2026-11-02.3", False),
            # The bot's name with someone else's address is not the bot.
            Tag("publish-2026-11-02.4", True, _tags.BOT_NAME, "p@example.org"),
            _bot("publish-not-a-date"),
        ]
    )
    assert [t.name for t in own] == ["publish-2026-11-02.1"]
    assert len(ignored) == 4


@pytest.mark.spec("DOCBW-07-006")
def test_newest_publish_tag_ignores_a_hand_pushed_tag() -> None:
    tags = [
        _bot("publish-2026-10-30.2"),
        _bot("publish-2026-11-02.1"),
        _bot("publish-2026-10-30.10"),
        # Newer by name, but pushed by hand: it does not name what is live.
        _hand("publish-2026-11-03.1"),
    ]
    newest = _tags.newest_publish_tag(tags)
    assert newest is not None and newest.name == "publish-2026-11-02.1"
    assert _tags.newest_publish_tag([_hand("publish-2026-11-03.1")]) is None
    assert _tags.newest_publish_tag([]) is None


@pytest.mark.spec("DOCBW-07-006")
def test_the_counter_orders_publishes_numerically() -> None:
    tags = [_bot("publish-2026-11-02.9"), _bot("publish-2026-11-02.10")]
    newest = _tags.newest_publish_tag(tags)
    assert newest is not None and newest.name == "publish-2026-11-02.10"


@pytest.mark.spec("DOCBW-07-006")
def test_has_publish_tag_needs_a_bot_tag_on_that_commit() -> None:
    assert _tags.has_publish_tag("c1", [_bot("publish-2026-11-02.1", "c1")])
    assert not _tags.has_publish_tag(
        "c1", [_bot("publish-2026-11-02.1", "c2")]
    )
    assert not _tags.has_publish_tag(
        "c1", [_hand("publish-2026-11-02.1", "c1")]
    )


# --- release names ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "version"),
    [
        ("v2026.10.0", (2026, 10)),
        ("v2026.10.1", (2026, 10, 1)),
        ("v2023.9", (2023, 9)),
        ("v0.7.2", (0, 7, 2)),
        ("vendor-drop", None),
        ("v2026.10.0-rc1", None),
    ],
)
def test_release_version(name: str, version: tuple[int, ...] | None) -> None:
    assert _tags.release_version(name) == version


def test_latest_release_compares_versions_not_names() -> None:
    names = ["v0.7.2", "v2024.4.3", "v2023.10.0", "v2024.10.0", "vendor"]
    assert _tags.latest_release(names) == "v2024.10.0"
    assert _tags.latest_release(["vendor"]) is None


@pytest.mark.spec("DOCBW-07-001", "DOCBW-07-006")
@pytest.mark.parametrize(
    ("today", "existing", "expected"),
    [
        # The first release of a month is .0.
        (date(2026, 11, 2), ["v2026.10.0", "v2026.10.1"], "v2026.11.0"),
        # Then one more than the month's highest.
        (date(2026, 11, 20), ["v2026.11.0", "v2026.11.3"], "v2026.11.4"),
        # Month rollover into a new year.
        (date(2027, 1, 4), ["v2026.12.2"], "v2027.1.0"),
        # The very first release, and old two-component tags.
        (date(2026, 11, 2), [], "v2026.11.0"),
        (date(2026, 11, 2), ["v2023.9", "v0.7.2"], "v2026.11.0"),
    ],
)
def test_next_release_name(
    today: date, existing: list[str], expected: str
) -> None:
    assert _tags.next_release_name(today, existing) == expected


@pytest.mark.spec("DOCBW-07-003")
def test_next_release_name_never_goes_backwards() -> None:
    """A tag from a later month, pushed by hand, stops the promotion."""
    with pytest.raises(_tags.ReleaseOrderError):
        _tags.next_release_name(date(2026, 11, 2), ["v2026.12.0"])
    with pytest.raises(_tags.ReleaseOrderError):
        _tags.next_release_name(date(2026, 11, 2), ["v2027.0.1"])


def test_next_publish_name() -> None:
    existing = ["publish-2026-11-02.1", "publish-2026-11-02.3", "v2026.11.0"]
    assert (
        _tags.next_publish_name("2026-11-02", existing)
        == "publish-2026-11-02.4"
    )
    assert (
        _tags.next_publish_name("2026-11-03", existing)
        == "publish-2026-11-03.1"
    )


# --- reading the clone ------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    isolate_git_config(monkeypatch)
    work = scratch_clone(tmp_path)
    commit(work, "first", when="2026-10-30T12:00:00+00:00")
    monkeypatch.chdir(work)
    return work


@pytest.mark.spec("DOCBW-07-006")
def test_read_tags_records_tagger_commit_and_date(repo: Path) -> None:
    first = head(repo)
    tag_as_bot(repo, "publish-2026-11-02.1", when="2026-11-02T06:30:00+00:00")
    git(repo, "tag", "-a", "publish-2026-11-02.2", "-m", "by hand")
    git(repo, "tag", "publish-2026-11-02.3")
    tag_as_bot(repo, "v2026.11.0")
    second = commit(repo, "second")
    tag_as_bot(repo, "publish-2026-11-03.1")

    on_first = {t.name: t for t in _tags.publish_tags_on(first)}
    assert set(on_first) == {
        "publish-2026-11-02.1",
        "publish-2026-11-02.2",
        "publish-2026-11-02.3",
    }
    bot = on_first["publish-2026-11-02.1"]
    assert bot.is_publish and bot.commit == first
    assert bot.created == datetime(2026, 11, 2, 6, 30, tzinfo=UTC)
    assert not on_first["publish-2026-11-02.2"].is_publish
    lightweight = on_first["publish-2026-11-02.3"]
    assert not lightweight.annotated and lightweight.commit == first

    assert [t.name for t in _tags.workflow_publish_tags_on(first)] == [
        "publish-2026-11-02.1"
    ]
    assert [t.name for t in _tags.release_tags_on(first)] == ["v2026.11.0"]
    assert _tags.release_tags_on(second) == []
    newest = _tags.newest_publish_tag(_tags.publish_tags())
    assert newest is not None and newest.commit == second
    assert _tags.has_publish_tag(first, _tags.publish_tags())


def test_release_tags_skips_a_tag_that_is_no_version(repo: Path) -> None:
    git(repo, "tag", "vendor-drop")
    tag_as_bot(repo, "v2026.11.0")
    assert [t.name for t in _tags.release_tags()] == ["v2026.11.0"]
