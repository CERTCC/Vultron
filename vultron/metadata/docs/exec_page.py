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
"""MkDocs hook: tell a ``markdown-exec`` block which page it is rendering for.

A requirement callout or catalog page printed from an exec block links other
pages by built-site URL, and on the specification's single-page edition
(``full.md``) it links in-page instead (DF-12-002). Both need the page being
rendered, and ``markdown-exec`` gives a block no page: a fragment included by
several pages runs the same code on each.

This ``on_pre_page`` hook records the page's ``docs/``-relative source path in
the :data:`EXEC_PAGE_ENV` environment variable before the page is read.
MkDocs reads, converts and post-processes one page before it starts the next
(``mkdocs.commands.build._populate_page``), and exec blocks run during the
conversion, so the variable names the page whose blocks are running. The
renderers read it through
:func:`vultron.metadata.docs.requirement_catalog.current_page`. An environment
variable rather than a module global, because the per-kind requirement pages'
exec blocks purge ``vultron`` modules from ``sys.modules`` before they import;
``markdown-exec`` passes ``MKDOCS_CONFIG_DIR`` to its blocks the same way.

Registered under ``hooks:`` in ``mkdocs.yml``. MkDocs loads a hook by file
path, so this module imports only the standard library and MkDocs itself.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
    from mkdocs.structure.pages import Page

EXEC_PAGE_ENV = "VULTRON_DOCS_PAGE"
"""Holds the ``docs/``-relative source path of the page being rendered."""


def on_pre_page(page: Page, *, config: MkDocsConfig, files: Files) -> Page:
    """Record *page* as the page whose exec blocks run next."""
    os.environ[EXEC_PAGE_ENV] = page.file.src_uri
    return page


def on_post_build(*, config: MkDocsConfig) -> None:
    """Forget the last page, so nothing outside the build reads it."""
    os.environ.pop(EXEC_PAGE_ENV, None)


__all__ = ["EXEC_PAGE_ENV", "on_post_build", "on_pre_page"]
