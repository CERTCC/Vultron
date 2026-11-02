"""The tag queries shared by every workflow that reads ``publish-*`` or ``v*`` tags.

Two kinds of tag name what the project shipped:

- ``publish-YYYY-MM-DD.N`` names a commit the publish workflow
  (``deploy_site.yml``, ADR-0171) deployed to the site. Only an annotated tag
  whose tagger is ``github-actions[bot]`` counts as a publish: tag creation is
  unrestricted (#5545), so a tag pushed by hand must not pass as one
  (DOCBW-06-014).
- ``vYYYY.M.P`` names a release (ADR-0006). The promote workflow makes one on
  the commit of a ``publish-*`` tag (DOCBW-07).

The publish gate's skip rule, the promote workflow, the release tag check and
the staleness alarm all ask their questions here, so each one honours the same
tagger check. The answers are pure functions over ``Tag`` values; the only
I/O is ``read_tags``, a ``git for-each-ref`` over the local clone, and the
``*_on``/``*_tags`` readers built on it. A caller that needs to know, at build
time, which ``publish-*`` and ``v*`` tags a commit carries reads them through
``workflow_publish_tags_on`` and ``release_tags_on``.

Nothing here creates, moves or deletes a tag.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gh_cli import run  # see gh_cli

PUBLISH_PREFIX = "publish-"
RELEASE_PREFIX = "v"
# The identity the workflows tag as. git records it as the tagger of every
# annotated tag a workflow creates; a tag query recognises a workflow's tag by
# it (ADR-0171).
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
# The ``git`` options that make a tag as the bot: ``git *BOT_GIT_IDENTITY tag``.
BOT_GIT_IDENTITY = (
    "-c",
    f"user.name={BOT_NAME}",
    "-c",
    f"user.email={BOT_EMAIL}",
)

PUBLISH_TAG_RE = re.compile(r"^publish-(\d{4}-\d{2}-\d{2})\.(\d+)$")
# A release name ADR-0006 allows: three components, always.
RELEASE_TAG_RE = re.compile(r"^v(\d{4})\.(1[0-2]|[1-9])\.(\d+)$")
# Any version-shaped ``v*`` tag, the older two-component and SemVer ones
# included: a new release must compare greater than every one of them.
_VERSION_TAG_RE = re.compile(r"^v(\d+(?:\.\d+)*)$")

# One line per tag: name, object type, tagger name, tagger e-mail, the commit
# it names (peeled for an annotated tag) and its creation date.
_FORMAT = "\t".join(
    [
        "%(refname:strip=2)",
        "%(objecttype)",
        "%(taggername)",
        "%(taggeremail:trim)",
        "%(if)%(*objectname)%(then)%(*objectname)%(else)%(objectname)%(end)",
        "%(creatordate:iso-strict)",
    ]
)


class ReleaseOrderError(ValueError):
    """The next release name would not compare greater than the latest one."""


@dataclass(frozen=True)
class Tag:
    """A tag as git records it.

    ``commit`` is the commit the tag names and ``created`` its tagger date
    (an annotated tag) or its commit's date (a lightweight one). Both are
    empty for a tag built without reading git.
    """

    name: str
    annotated: bool
    tagger_name: str = ""
    tagger_email: str = ""
    commit: str = ""
    created: datetime | None = None

    @property
    def made_by_workflow(self) -> bool:
        return (
            self.annotated
            and self.tagger_name == BOT_NAME
            and self.tagger_email == BOT_EMAIL
        )

    @property
    def is_publish(self) -> bool:
        """A ``publish-*`` tag a workflow made: the only kind that counts."""
        return self.made_by_workflow and bool(PUBLISH_TAG_RE.match(self.name))


# --- pure queries -------------------------------------------------------------


def split_publish_tags(tags: Iterable[Tag]) -> tuple[list[Tag], list[Tag]]:
    """Split tags into publishes and the tags a publish query ignores.

    Only an annotated, well-named ``publish-*`` tag whose tagger is
    ``github-actions[bot]`` is a publish (DOCBW-06-014).
    """
    own: list[Tag] = []
    ignored: list[Tag] = []
    for tag in tags:
        (own if tag.is_publish else ignored).append(tag)
    return own, ignored


def _publish_order(tag: Tag) -> tuple[str, int]:
    match = PUBLISH_TAG_RE.match(tag.name)
    assert match is not None  # callers pass publishes only
    return match.group(1), int(match.group(2))


def newest_publish_tag(tags: Iterable[Tag]) -> Tag | None:
    """The publish that names what is live, or ``None`` if there is none.

    Publishes are numbered by UTC date and a counter inside one concurrency
    group (DOCBW-06-016, DOCBW-06-021), so the highest name is the newest.
    """
    own, _ = split_publish_tags(tags)
    return max(own, key=_publish_order, default=None)


def has_publish_tag(commit: str, tags: Iterable[Tag]) -> bool:
    """Whether *commit* carries a publish."""
    own, _ = split_publish_tags(tags)
    return any(tag.commit == commit for tag in own)


def next_publish_name(day: str, existing: Iterable[str]) -> str:
    """``publish-<day>.N`` with N one more than the highest for *day*, from 1."""
    taken = [
        int(m.group(2))
        for name in existing
        if (m := PUBLISH_TAG_RE.match(name)) and m.group(1) == day
    ]
    return f"{PUBLISH_PREFIX}{day}.{max(taken, default=0) + 1}"


def release_version(name: str) -> tuple[int, ...] | None:
    """The version a ``v*`` tag names, as integers, or ``None``.

    Trailing zeros are dropped, so ``v2023.9`` and ``v2023.9.0`` compare
    equal, as version comparators read them.
    """
    match = _VERSION_TAG_RE.match(name)
    if match is None:
        return None
    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def latest_release(names: Iterable[str]) -> str | None:
    """The ``v*`` tag with the highest version, or ``None``."""
    versioned = [
        (version, name)
        for name in names
        if (version := release_version(name)) is not None
    ]
    return max(versioned, default=(None, None))[1]


def next_release_name(today: date, existing: Iterable[str]) -> str:
    """The next ``vYYYY.M.P`` for *today*'s month (ADR-0006).

    ``P`` is 0 for the month's first release and one more than the month's
    highest otherwise. The month is the day of promotion, not the day of the
    publish being promoted. Raises ``ReleaseOrderError`` when the name would
    not compare strictly greater than every existing ``v*`` tag, as when a
    tag from a later month was pushed by hand.
    """
    names = list(existing)
    patches = [
        int(m.group(3))
        for name in names
        if (m := RELEASE_TAG_RE.match(name))
        and (int(m.group(1)), int(m.group(2))) == (today.year, today.month)
    ]
    patch = max(patches) + 1 if patches else 0
    name = f"{RELEASE_PREFIX}{today.year}.{today.month}.{patch}"
    latest = latest_release(names)
    if latest is not None:
        new, old = release_version(name), release_version(latest)
        assert new is not None and old is not None
        if new <= old:
            raise ReleaseOrderError(
                f"{name} would not be greater than the latest release {latest}"
            )
    return name


# --- reading the clone --------------------------------------------------------


def _parse_date(text: str) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def read_tags(pattern: str, *, points_at: str = "") -> list[Tag]:
    """Every tag matching the ``for-each-ref`` *pattern* in the local clone.

    With *points_at*, only the tags that name that commit.
    """
    argv = ["git", "for-each-ref", f"--format={_FORMAT}"]
    if points_at:
        argv.append(f"--points-at={points_at}")
    tags: list[Tag] = []
    for line in run(*argv, f"refs/tags/{pattern}").splitlines():
        name, kind, tagger, email, commit, created = [
            *line.split("\t"),
            *[""] * 6,
        ][:6]
        tags.append(
            Tag(
                name,
                kind == "tag",
                tagger,
                email,
                commit,
                _parse_date(created),
            )
        )
    return tags


def tag_commit(tag: str) -> str | None:
    """The commit *tag* names in this clone, or ``None`` if there is no such tag."""
    try:
        return run(
            "git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"
        ).strip()
    except subprocess.CalledProcessError:
        return None


def publish_tags(*, points_at: str = "") -> list[Tag]:
    """Every ``publish-*`` tag, publishes and ignored ones alike."""
    return read_tags(f"{PUBLISH_PREFIX}*", points_at=points_at)


def publish_tags_on(sha: str) -> list[Tag]:
    """Every ``publish-*`` tag that points at *sha*, ignored ones included."""
    return publish_tags(points_at=sha)


def workflow_publish_tags_on(sha: str) -> list[Tag]:
    """The publishes on *sha*: what the skip rule and the release check read."""
    return split_publish_tags(publish_tags_on(sha))[0]


def release_tags(*, points_at: str = "") -> list[Tag]:
    """Every version-shaped ``v*`` tag."""
    return [
        tag
        for tag in read_tags(f"{RELEASE_PREFIX}*", points_at=points_at)
        if release_version(tag.name) is not None
    ]


def release_tags_on(sha: str) -> list[Tag]:
    """The version-shaped ``v*`` tags that point at *sha*."""
    return release_tags(points_at=sha)
