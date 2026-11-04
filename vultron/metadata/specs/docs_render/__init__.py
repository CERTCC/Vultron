"""MkDocs Material markdown renderer for requirement pages and callouts.

Renders the loaded :class:`SpecRegistry` for human readers of the published
documentation site, unlike ``render.py`` (agent/LLM export). One row renderer,
:func:`render_requirement_row`, produces every requirement table row the site
shows, in three places:

* the per-kind requirement pages under ``docs/reference/specs/``, for the
  ``architecture``, ``project`` and ``process`` kinds (:func:`render_for_kind`);
* the Protocol Specification's Requirements Catalog pages
  (:func:`render_catalog_page`, DF-12-001);
* the requirement callouts in the specification's narrative
  (:func:`requirement_callout`, DF-12-003).

A catalog row and a per-kind row define the requirement's anchor; a callout
row links it instead (DF-12-010). Where each requirement's row is, and the
link a row shows to it, come from
:mod:`vultron.metadata.docs.requirement_catalog`.

Usage (in a markdown-exec Python block)::

    from vultron.metadata.specs import load_registry
    from vultron.metadata.specs.docs_render import render_for_kind

    registry = load_registry()
    print(render_for_kind("architecture", registry))

A callout is one line::

    from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VM-10-001"))

Submodules, by concern: ``rows`` (one requirement's table row and its cells)
and ``pages`` (per-kind pages, catalog pages and callouts, and the cached
repository registry they default to).
"""

from vultron.metadata.docs.requirement_catalog import (
    CATALOG_KINDS,
    NotInCatalogError,
)
from vultron.metadata.specs.docs_render.pages import (
    render_catalog_page,
    render_for_kind,
    requirement_callout,
)
from vultron.metadata.specs.docs_render.rows import (
    RequirementHref,
    render_requirement_row,
)
from vultron.metadata.specs.registry import load_registry

__all__ = [
    "CATALOG_KINDS",
    "NotInCatalogError",
    "RequirementHref",
    "load_registry",
    "render_catalog_page",
    "render_for_kind",
    "render_requirement_row",
    "requirement_callout",
]
