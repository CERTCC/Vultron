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
"""Where each requirement is shown: the Requirements Catalog placement table.

The Protocol Specification renders its normative text from the ``protocol``
and ``foundation`` requirement tiers (ADR-0147). Every requirement of the two
tiers is shown once, in a Requirements Catalog row, and every other page that
shows or links it links that row (DF-12-001, DF-12-010). This module is the
one place that decides where a row lives:

* :data:`CATALOG_PAGES` is the placement table. It maps each catalog page key
  to the requirement files, by file ID, whose items of one tier the page
  holds. Placement is declared here, on the documentation side, and never as
  a field in a requirement file (DF-12-005). :func:`placement_faults` fails a
  file holding either tier that no page of that tier places, or that two
  places of that tier name (DF-12-015).
* :func:`catalog_location` returns the catalog page and anchor of a
  requirement of either tier, and refuses an ID of any other kind.
* :func:`requirement_linker` turns a requirement ID into the link target a
  rendered row shows on a given page. The renderers in
  :mod:`vultron.metadata.specs.docs_render` print their output from a
  ``markdown-exec`` block, where MkDocs neither rewrites nor validates a link,
  so the target is a built-site URL relative to the page, never a ``.md``
  path (``vultron/metadata/AGENTS.md``). On the single-page edition
  (``full.md``) a catalog row is in the page, so the link is a bare
  ``#anchor``: the ``full.md`` link hook skips fenced code and never sees an
  exec block's output (``full_page_links.py``).

* :func:`anchor_homes` maps each requirement, group and file ID to the
  pages whose rendered rows or headings define its anchor, so a tool that
  rewrites links (``scripts/relink_requirement_anchors.py``) and the gate
  that holds ``docs/`` to them agree with the renderers.

The two tiers have no per-kind requirements page: the catalog is where their
rows are (SR-09-004), and the retired ``reference/specs/protocol.md`` and
``foundation.md`` redirect to :data:`CATALOG_LANDING` (#4901).

Submodules, by concern: ``pages`` (the catalog pages and their table),
``placement`` (placing a requirement and checking the table) and ``links``
(link targets and anchor homes).
"""

from vultron.metadata.docs.requirement_catalog.links import (
    AnchorHome,
    anchor_home_of,
    anchor_homes,
    current_page,
    requirement_linker,
    site_href,
    source_href,
)
from vultron.metadata.docs.requirement_catalog.pages import (
    CATALOG_DIR,
    CATALOG_INTRO,
    CATALOG_KINDS,
    CATALOG_LANDING,
    CATALOG_PAGES,
    FULL_PAGE,
    RETIRED_KIND_PAGES,
    CatalogPage,
    kind_page,
)
from vultron.metadata.docs.requirement_catalog.placement import (
    CatalogLocation,
    NotInCatalogError,
    catalog_location,
    placement_faults,
    requirement_anchor,
)

__all__ = [
    "AnchorHome",
    "CATALOG_DIR",
    "CATALOG_INTRO",
    "CATALOG_KINDS",
    "CATALOG_LANDING",
    "CATALOG_PAGES",
    "CatalogLocation",
    "CatalogPage",
    "FULL_PAGE",
    "NotInCatalogError",
    "RETIRED_KIND_PAGES",
    "anchor_home_of",
    "anchor_homes",
    "catalog_location",
    "current_page",
    "kind_page",
    "placement_faults",
    "requirement_anchor",
    "requirement_linker",
    "site_href",
    "source_href",
]
