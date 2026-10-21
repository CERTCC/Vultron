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
"""MkDocs hook: show each reading-path thread on the pages it passes through.

Requirements: DF-11-015 (a member page shows the pages before and after it
and a link to its thread's start page, the same for every reader), DF-11-017
(no nav-order footer on a member page), DF-11-009 (titled by situation).
Design: ``notes/site-information-architecture.md`` § "Threads: staged data,
rendered at both ends" (ADR-0150).

``on_files`` reads every start page's thread once per build, before any page
renders, so ``mkdocs serve`` picks up an edited thread on its next rebuild.
``on_page_markdown`` then appends one box per thread the page is on, as
Markdown, so MkDocs rewrites and validates its links like any other, and adds
``footer`` to the page's ``hide`` list: the theme's previous/next footer
follows nav order, and two "next" links that disagree would mislead
(DF-11-017). Pages on no thread are returned unchanged.

The thread model, the before/after rule and the box itself live in
:mod:`vultron.metadata.docs.threads`, which the thread check shares, so the
build and the check cannot read a thread two ways. Unlike the other hooks,
this one therefore imports from ``vultron``; MkDocs runs in the project's
environment, where the package is installed.

Registered under ``hooks:`` in ``mkdocs.yml``.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from vultron.metadata.docs.threads import (
    StartThread,
    load_threads,
    member_boxes,
    page_titles,
)

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
    from mkdocs.structure.pages import Page

#: The ``hide`` entry Material reads to suppress its nav-order footer.
FOOTER = "footer"


@dataclass
class _Build:
    """The threads of the current build, refreshed by :func:`on_files`."""

    threads: tuple[StartThread, ...] = ()
    titles: dict[str, str] = field(default_factory=dict)


_BUILD = _Build()


def load_build(root: Path) -> None:
    """Read every thread under *root* into the current build's state."""
    threads = load_threads(root)
    _BUILD.threads = threads
    _BUILD.titles = page_titles(root, threads)


def on_files(files: Files, *, config: MkDocsConfig) -> Files:
    """Load the threads for this build; the file list is returned unchanged."""
    load_build(Path(config.docs_dir).parent)
    return files


def hide_footer(meta: MutableMapping[str, object]) -> None:
    """Add :data:`FOOTER` to *meta*'s ``hide`` list, keeping what is there."""
    hidden = meta.get("hide")
    if isinstance(hidden, list):
        entries = list(hidden)
    else:
        entries = [hidden] if isinstance(hidden, str) else []
    if FOOTER not in entries:
        entries.append(FOOTER)
    meta["hide"] = entries


def on_page_markdown(
    markdown: str, *, page: Page, config: MkDocsConfig, files: Files
) -> str:
    """Append a box per thread *page* is on, and hide its nav-order footer."""
    boxes = member_boxes(_BUILD.threads, page.file.src_uri, _BUILD.titles)
    if not boxes:
        return markdown
    hide_footer(page.meta)
    return "\n\n".join([markdown.rstrip("\n"), *boxes]) + "\n"


__all__ = [
    "FOOTER",
    "hide_footer",
    "load_build",
    "on_files",
    "on_page_markdown",
]
