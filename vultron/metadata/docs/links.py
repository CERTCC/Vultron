#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Enforce the reference axis: every internal reference in ``site/`` resolves.

:mod:`vultron.metadata.docs.withheld` checks the *publication* axis — a withheld
artifact produced no files. That left the other half of withholding unchecked:
nothing verified that the site stopped *linking to* a path the build did not
produce. When ``docs/ns/`` moved to ``draft_docs`` (#3549), the What's New page
kept advertising ``../../ns/``, a well-formed path with no target, and every gate
passed (#3574). This module is the missing check (DOCBW-03-007).

Three properties make it a gate rather than a sample:

* **Resolution, not link form.** ``../../ns/`` is exactly what a correctly
  rewritten link to a published page looks like, so no pattern over the href
  can tell a dead one from a live one. Each reference is resolved against the
  files the build produced. That subsumes form checks such as a ``.md`` suffix,
  which resolves to no built file.
* **Every built HTML file, not a crawl.** Many built pages have no inbound link
  from the nav — every ``not_in_nav`` page, ``404.html`` — so a crawl from
  ``index.html`` never reads their links and reports success over only what it
  reached. :func:`scan_site` walks the whole tree.
* **Nothing resolved is a failure.** An absent or empty ``site/``, one with no
  HTML in it, or pages yielding no internal reference fail rather than pass
  (DF-09-009).

``mkdocs build --strict`` is not a substitute. markdown-exec renders a block's
output on a child ``Markdown`` instance that lacks MkDocs' relative-link
treeprocessor, so links an exec block prints are never validated by the build.
Checking the bytes the build emitted covers them.

Anchor validity is out of scope: a fragment is stripped before resolution, and
dead in-page anchors are ``validation.links.anchors``' job under ``--strict``
(DOCBW-03-011). External URLs are out of scope too.

CLI (``uv run docs-links``)::

    uv run mkdocs build
    uv run docs-links             # exit 1 if any internal reference is dead
"""

from __future__ import annotations

import argparse
import html
import posixpath
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from vultron.metadata.base import mkdocs_config, repo_root
from vultron.metadata.docs.built_site import require_built_site, site_dir

# Bytes-mode so pages are never decoded whole; only matched values are. Both
# quote styles and the unquoted form, and the leading whitespace keeps
# ``data-href=`` from matching. Escaped text such as ``href=&quot;x&quot;`` in
# a code block cannot match the quoted forms.
_REFERENCE = re.compile(
    rb"""\s(href|src|srcset)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""",
    re.IGNORECASE,
)
# One ``srcset`` candidate: separators, the URL (a non-whitespace run whose
# trailing commas end the candidate), then descriptors up to the next comma.
_SRCSET_CANDIDATE = re.compile(r"[\s,]*(\S*[^\s,])(?:,+|[^,]*,?)")
# RFC 3986 scheme: ``https:``, ``mailto:``, ``data:``, ``javascript:``, …
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class DeadReference:
    """An internal reference on a built page that resolves to no built file.

    Attributes:
        page: The page carrying the reference, relative to ``site/``.
        reference: The reference as it appears in the page's HTML.
    """

    page: str
    reference: str


@dataclass(frozen=True)
class SiteScan:
    """What one pass over ``site/`` checked and found.

    The counts are reported beside the verdict so a pass says how much it
    covered: a scan that checked nothing must be visible as such (DF-09-009).
    """

    pages: int
    references: int
    dead: list[DeadReference] = field(default_factory=list)


def site_base_path(root: Path | None = None) -> str:
    """Return the URL path the site is served under, with a trailing slash.

    ``site_url: https://certcc.github.io/Vultron/`` gives ``/Vultron/``. Material
    writes ``404.html``'s references root-absolute under this path, because a
    404 is served at whatever URL was missed and a relative reference from it
    would resolve against that URL rather than the page's own location.
    """
    site_url = mkdocs_config(root).get("site_url")
    path = urlsplit(site_url).path if isinstance(site_url, str) else ""
    return path.rstrip("/") + "/"


def _target(page: str, reference: str, base_path: str) -> str | None:
    """Return the ``site/``-relative path a reference points at.

    Returns ``None`` for a reference this check does not own: an external URL
    (any scheme, or protocol-relative ``//host``), and a fragment-only or empty
    reference, which names the page it is on. A reference that climbs out of
    the site, or is root-absolute outside ``base_path``, returns a path that
    starts with ``..``, which no built file matches.
    """
    # Material obfuscates ``mailto:`` as character references, so the scheme is
    # only visible after unescaping.
    value = html.unescape(reference).strip()
    if not value or _SCHEME.match(value) or value.startswith("//"):
        return None
    value = unquote(value.split("#", 1)[0].split("?", 1)[0])
    if not value:
        return None
    if value.startswith("/"):
        # ``/Vultron`` is the site root too: a static host redirects it there.
        if f"{value}/" == base_path:
            return "."
        if not value.startswith(base_path):
            return posixpath.join("..", value.lstrip("/"))
        return posixpath.normpath(value[len(base_path) :] or ".")
    return posixpath.normpath(posixpath.join(posixpath.dirname(page), value))


def _resolves(target: str, built_files: frozenset[str]) -> bool:
    """Return whether a target names a built file or a directory's index page.

    A directory reference is live only if the directory has an ``index.html``:
    that is what a static host serves for it, and under ``use_directory_urls``
    it is what every page link is.
    """
    if target == ".":
        return "index.html" in built_files
    return target in built_files or f"{target}/index.html" in built_files


def _values(match: re.Match[bytes]) -> list[str]:
    """Return the references one attribute match carries.

    ``href`` and ``src`` carry one. ``srcset`` carries a comma-separated list
    of candidates, each a URL optionally followed by a width or density
    descriptor (``logo.png 2x``); every candidate URL is a reference.
    """
    value = (match.group(2) or match.group(3) or match.group(4) or b"").decode(
        "utf-8", errors="replace"
    )
    if match.group(1).lower() != b"srcset":
        return [value]
    return _srcset_urls(value)


def _srcset_urls(value: str) -> list[str]:
    """Return the candidate URLs of a ``srcset``, per the HTML parsing rules.

    A candidate's URL is its first run of non-whitespace, so a comma *inside*
    a URL (``data:image/png;base64,…``) does not split it; trailing commas end
    the candidate, and otherwise its descriptors run to the next comma.
    """
    urls: list[str] = []
    pos = 0
    while candidate := _SRCSET_CANDIDATE.match(value, pos):
        urls.append(candidate.group(1))
        pos = candidate.end()
    return urls


def scan_site(root: Path | None = None) -> SiteScan:
    """Resolve every internal reference on every built HTML page.

    Args:
        root: Repository root holding ``mkdocs.yml`` and the built ``site/``.
            Defaults to the enclosing checkout.

    Returns:
        The pages and references checked, and every dead reference, sorted by
        page then reference so output is stable.

    Raises:
        FileNotFoundError: If ``site/`` is absent, empty, or holds no HTML. The
            caller must build the site first; an unbuilt site resolves no
            references, so it is a failure rather than a pass (DF-09-009).
    """
    base = root or repo_root()
    built = require_built_site(base, "its references resolve")
    # One walk builds the index, so resolution is a set lookup per reference
    # rather than a ``stat`` call: ~65k references, and the difference is ~2x.
    built_files = frozenset(
        path.relative_to(built).as_posix()
        for path in built.rglob("*")
        if path.is_file()
    )
    pages = sorted(p for p in built_files if p.endswith(".html"))
    if not pages:
        raise FileNotFoundError(
            f"{built} holds no HTML pages, so there are no references to check."
        )

    base_path = site_base_path(base)
    references = 0
    dead: list[DeadReference] = []
    for page in pages:
        for match in _REFERENCE.finditer((built / page).read_bytes()):
            for raw in _values(match):
                target = _target(page, raw, base_path)
                if target is None:
                    continue
                references += 1
                if not _resolves(target, built_files):
                    dead.append(DeadReference(page=page, reference=raw))
    return SiteScan(
        pages=len(pages),
        references=references,
        dead=sorted(dead, key=lambda d: (d.page, d.reference)),
    )


def _report(dead: list[DeadReference]) -> None:
    """Print each dead reference to stderr as ``<page>: <reference>``."""
    for ref in dead:
        print(f"{ref.page}: {ref.reference}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run docs-links``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root holding the built site/ (default: this checkout).",
    )
    args = parser.parse_args(argv)
    base = args.root or repo_root()

    try:
        scan = scan_site(base)
    except FileNotFoundError as exc:
        # The audience is whoever just ran the tool without building first, so
        # a missing site/ owes them an instruction rather than a traceback.
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    if not scan.references:
        # Pages with no internal reference at all mean the extraction broke, not
        # that the site is clean; passing here would check nothing (DF-09-009).
        print(
            f"[ERROR] {scan.pages} pages in {site_dir(base).name}/ yielded no "
            "internal references, so nothing was checked.",
            file=sys.stderr,
        )
        sys.exit(1)

    if scan.dead:
        _report(scan.dead)
        print(
            f"\n✗ {len(scan.dead)} of {scan.references} internal reference(s) "
            f"across {scan.pages} pages resolve to no built file.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"✓ All {scan.references} internal references across {scan.pages} "
        f"pages in {site_dir(base).name}/ resolve."
    )


if __name__ == "__main__":
    main()
