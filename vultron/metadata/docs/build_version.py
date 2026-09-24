"""Label for the version box on ``docs/includes/curr_ver.md``.

The box states which build of the Vultron project the site was generated from.
The site and the ``vultron`` package share one version (ADR-0006), derived by
``setuptools_scm`` from the most recent release tag. Only a build made exactly
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
    and neither is the no-tag fallback or an unparseable string.
    """
    if version == FALLBACK_VERSION:
        return False
    try:
        parsed = Version(version)
    except InvalidVersion:
        return False
    return not (parsed.is_devrelease or parsed.local)


def describe_build(version: str) -> str:
    """Return a Markdown sentence naming the build *version* describes."""
    if is_release(version):
        return (
            "This site and the `vultron` package were built from "
            f"release **{version}**."
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
