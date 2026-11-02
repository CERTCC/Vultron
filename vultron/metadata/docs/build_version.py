"""The footer line that names the publish and build every site page came from.

Every page's footer states which publish of the site it belongs to and which
build of the Vultron repository generated it (#5544). The line is rendered once
per build by this module's ``on_config`` MkDocs hook, stored in
``config.extra[FOOTER_KEY]``, and printed by ``overrides/partials/copyright.html``.
Nothing else writes it, so no two places on the site can disagree about it.

A publish is named by the ``publish-YYYY-MM-DD.N`` tag the publish workflow
creates on the deployed commit (``deploy_site.yml``, ADR-0171, DOCBW-06-016).
The workflow's gate decides that name before the build runs and passes it, with
the publish date and any ``v*`` release tag on the commit, through the
environment variables ``PUBLISH_TAG_ENV``, ``PUBLISH_DATE_ENV`` and
``RELEASE_TAG_ENV`` (DOCBW-06-031). A build without them, such as
``mkdocs serve`` or a pull request's review build, is an unpublished build and
says so.

The build version is the package version ``setuptools_scm`` derives from the
most recent release tag: the site and the ``vultron`` package are built from
the same commit. It is a build version, not a protocol version: the protocol's
CalVer scheme (ADR-0006) numbers the protocol alone. Only a build made exactly
at a tag is a release: any commit after the tag, and any uncommitted change,
yields a development or local version, and a checkout with no tag history falls
back to ``0.0.0+dev``. Printing such a string as if it were the current
release is what issue #3550 fixed.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html import escape
from typing import TYPE_CHECKING
from urllib.parse import quote

from packaging.version import InvalidVersion, Version

from vultron import __version__

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

#: ``fallback_version`` in ``pyproject.toml``, used when no tag is reachable.
FALLBACK_VERSION = "0.0.0+dev"

#: The publish tag the publish workflow will create for this build.
PUBLISH_TAG_ENV = "VULTRON_PUBLISH_TAG"
#: The publish's UTC date, ``YYYY-MM-DD``, the date in the tag's name.
PUBLISH_DATE_ENV = "VULTRON_PUBLISH_DATE"
#: The newest ``v*`` release tag on the built commit, if it has one.
RELEASE_TAG_ENV = "VULTRON_RELEASE_TAG"

#: The ``config.extra`` key the footer partial reads.
FOOTER_KEY = "build_footer"

#: The date shape the gate writes, zero-padded; ``strptime`` alone also
#: takes ``2026-1-5``.
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

SEPARATOR = " · "
UNPUBLISHED = "Unpublished build"


class PublishLabelError(ValueError):
    """The publish environment variables do not describe one publish."""


@dataclass(frozen=True)
class Publish:
    """The publish a build belongs to.

    ``tag`` is the ``publish-*`` tag that names it, ``published`` its UTC
    date, and ``release_tag`` the ``v*`` tag on the built commit, if any.
    """

    tag: str
    published: date
    release_tag: str | None = None


def is_release(version: str) -> bool:
    """Return True when *version* names a tagged release build.

    Development (``.devN``) and local (``+...``) versions are not releases,
    and neither is the no-tag fallback (itself a local version) or an
    unparseable string. ``tag_regex`` in ``pyproject.toml`` admits no
    pre-release suffix (ADR-0006), so every release build is a final release.
    """
    try:
        parsed = Version(version)
    except InvalidVersion:
        return False
    return not (parsed.is_devrelease or parsed.local)


def _publish_date(day: str) -> date:
    """*day* as a date, if it is exactly ``YYYY-MM-DD``.

    Raises:
        PublishLabelError: If *day* is any other shape or no real date.
    """
    # Not date.fromisoformat, which also takes 20261030 and 2026-W44-1; the
    # fullmatch refuses the unpadded 2026-1-5 that strptime alone takes.
    bad = PublishLabelError(
        f"{PUBLISH_DATE_ENV} {day!r} is not a YYYY-MM-DD date."
    )
    if not _DATE_RE.fullmatch(day):
        raise bad
    try:
        return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError as error:
        raise bad from error


def publish_from_env(env: Mapping[str, str]) -> Publish | None:
    """The publish *env* describes, or ``None`` for an unpublished build.

    The publish workflow passes an empty string for a value it does not
    have, so an empty variable counts as unset. A publish tag needs its date
    and a date needs its tag, and a release tag is only read for a publish:
    anything else is a wiring fault, so it raises rather than print a footer
    that names half a publish.

    Raises:
        PublishLabelError: If the variables are set inconsistently, the
            date is not ``YYYY-MM-DD``, or the tag is not
            ``publish-<date>.N``.
    """
    tag = env.get(PUBLISH_TAG_ENV, "").strip()
    day = env.get(PUBLISH_DATE_ENV, "").strip()
    release = env.get(RELEASE_TAG_ENV, "").strip()
    if not tag and not day:
        if release:
            raise PublishLabelError(
                f"{RELEASE_TAG_ENV} is set to {release!r} but "
                f"{PUBLISH_TAG_ENV} is not; only a publish names its release."
            )
        return None
    if not tag or not day:
        raise PublishLabelError(
            f"{PUBLISH_TAG_ENV} and {PUBLISH_DATE_ENV} must be set together; "
            f"got tag {tag!r} and date {day!r}."
        )
    published = _publish_date(day)
    prefix = f"publish-{day}."
    serial = tag.removeprefix(prefix)
    if not (tag.startswith(prefix) and serial.isascii() and serial.isdigit()):
        raise PublishLabelError(
            f"{PUBLISH_TAG_ENV} {tag!r} is not publish-{day}.N, the publish "
            f"tag of the publish date {day}."
        )
    return Publish(tag, published, release or None)


def version_label(version: str) -> str:
    """The plain-text name of the build *version* describes."""
    if is_release(version):
        return f"release {version}"
    if version == FALLBACK_VERSION:
        return "development build with no release tag in its history"
    return version


def _tag_link(repo_url: str, tag: str) -> str:
    href = f"{repo_url.rstrip('/')}/tree/{quote(tag, safe='')}"
    return f'<a href="{escape(href)}">{escape(tag)}</a>'


def describe_build(
    version: str, publish: Publish | None, repo_url: str
) -> str:
    """Return the footer line, as HTML, for a build of *version*.

    A publish names its date and its tag, linked to the tag on GitHub at
    *repo_url*, and then the release tag on the commit when there is one,
    or the build version otherwise. An unpublished build says so and names
    its build version.
    """
    if publish is None:
        return SEPARATOR.join([UNPUBLISHED, escape(version_label(version))])
    built = (
        f"release {_tag_link(repo_url, publish.release_tag)}"
        if publish.release_tag
        else escape(version_label(version))
    )
    return SEPARATOR.join(
        [
            f"Published {publish.published.isoformat()}",
            _tag_link(repo_url, publish.tag),
            built,
        ]
    )


def on_config(config: MkDocsConfig) -> MkDocsConfig:
    """MkDocs hook: render the footer line into ``config.extra``.

    Raises:
        PublishLabelError: If the publish environment is inconsistent, or
            ``repo_url`` is unset, so a tag cannot be linked.
    """
    repo_url = config.repo_url
    if not repo_url:
        raise PublishLabelError("mkdocs.yml sets no repo_url to link tags to.")
    config.extra[FOOTER_KEY] = describe_build(
        __version__, publish_from_env(os.environ), repo_url
    )
    return config
