"""Label for the version box on ``docs/includes/curr_ver.md``.

The box states which build of the Vultron repository the site was generated
from. The site and the ``vultron`` package are built from the same commit, so
the box reports the package version ``setuptools_scm`` derives from the most
recent release tag. That is a build version, not a protocol version: the
protocol's CalVer scheme (ADR-0006) numbers the protocol alone. Only a build made exactly
at a tag is a release: any commit after the tag, and any uncommitted change,
yields a development or local version, and a checkout with no tag history falls
back to ``0.0.0+dev``. Printing such a string bare, as if it were the current
release, is what issue #3550 fixed.

Usage (in a markdown-exec Python block)::

    from vultron import __version__
    from vultron.metadata.docs.build_version import describe_build

    print(describe_build(__version__))
"""

from __future__ import annotations

from packaging.version import InvalidVersion, Version

#: ``fallback_version`` in ``pyproject.toml``, used when no tag is reachable.
FALLBACK_VERSION = "0.0.0+dev"


def is_release(version: str) -> bool:
    """Return True when *version* names a tagged release build.

    Development (``.devN``) and local (``+...``) versions are not releases,
    and neither is the no-tag fallback (itself a local version) or an
    unparseable string. A release candidate is a release build.
    """
    try:
        parsed = Version(version)
    except InvalidVersion:
        return False
    return not (parsed.is_devrelease or parsed.local)


def describe_build(version: str) -> str:
    """Return a Markdown sentence naming the build *version* describes."""
    if is_release(version):
        kind = "pre-release" if Version(version).is_prerelease else "release"
        return (
            "This site and the `vultron` package were built from "
            f"{kind} **{version}**."
        )
    if version == FALLBACK_VERSION:
        return (
            "This site was built from an **unreleased development build** "
            "with no release tag in its history."
        )
    return (
        "This site was built from an **unreleased development build** "
        f"(`{version}`), not from a release."
    )
