"""Requirement tables for docs pages: per-kind pages, catalog pages and
callouts.
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.docs.requirement_catalog import (
    CATALOG_KINDS,
    CATALOG_PAGES,
    FULL_PAGE,
    CatalogPage,
    catalog_location,
    current_page,
    kind_page,
    requirement_anchor,
    requirement_linker,
)
from vultron.metadata.specs.docs_render.rows import (
    _EMPTY_KIND_NOTICE,
    _TABLE_HEADER,
    RequirementHref,
    render_requirement_row,
)
from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Spec,
    SpecFile,
    SpecGroup,
    SpecKind,
    SpecTag,
)


def _render_group(
    lines: list[str],
    group: SpecGroup,
    href: RequirementHref,
    heading: str = "###",
    specs: list[Spec] | None = None,
    anchor: str | None = None,
) -> None:
    """Render *group* to *lines*, each row defining its requirement's anchor.

    When *specs* is provided only those specs are rendered (used to suppress
    items whose effective kind does not match the page — SR-09-005).
    When *specs* is ``None`` all items in the group are rendered. *anchor*
    overrides the heading's id, which defaults to the group ID's.
    """
    visible = specs if specs is not None else group.specs
    group_anchor = anchor or requirement_anchor(group.id)
    lines.append(f"{heading} {group.title} {{#{group_anchor}}}")
    lines.append("")
    if group.description:
        lines.append(group.description)
        lines.append("")
    if group.trigger:
        trigger_type = group.trigger.type.value.replace("_", " ").title()
        lines.append(f"*Trigger*: {trigger_type} — `{group.trigger.value}`")
        lines.append("")
    lines.extend(_TABLE_HEADER)
    for spec in visible:
        lines.append(render_requirement_row(spec, href, define_anchor=True))
    lines.append("")


def _render_file(
    lines: list[str],
    spec_file: SpecFile,
    href: RequirementHref,
    current_kind: SpecKind,
    *,
    heading: str,
    anchor_prefix: str = "",
    show_file_id: bool = True,
) -> None:
    """Render *spec_file* groups that have at least one item matching
    *current_kind* (SR-09-001, SR-09-002, SR-09-005).

    Groups appear here only when they contain at least one item whose
    ``kind`` matches *current_kind*; non-matching items are suppressed.
    *heading* is the file's heading level, and a group's is one below it.
    *anchor_prefix* goes before each heading id, so a page that renders the
    same file for two kinds (``full.md`` holds both catalog tiers) defines no
    id twice.
    """
    anchor = anchor_prefix + requirement_anchor(spec_file.id)
    lines.append(f"{heading} {spec_file.title} {{#{anchor}}}")
    lines.append("")
    lines.append(spec_file.description)
    lines.append("")
    if show_file_id:
        lines.append(f"*File ID*: `{spec_file.id}`")
        lines.append("")
    for group in spec_file.groups:
        # Collect items whose effective kind matches current_kind.
        matching_specs = [
            spec for spec in group.specs if spec.kind == current_kind
        ]
        if not matching_specs:
            continue
        _render_group(
            lines,
            group,
            href,
            heading=heading + "#",
            specs=matching_specs,
            anchor=anchor_prefix + requirement_anchor(group.id),
        )


def _is_behavioral_file(spec_file: SpecFile) -> bool:
    return any(
        isinstance(spec, BehavioralSpec)
        for group in spec_file.groups
        for spec in group.specs
    )


def _has_behavioral_tag(spec_file: SpecFile) -> bool:
    return SpecTag.BEHAVIORAL in (spec_file.tags or [])


def render_for_kind(kind: str, registry: SpecRegistry) -> str:
    """Render all spec files matching *kind* as rich MkDocs Material markdown.

    Args:
        kind: A :class:`SpecKind` string value (e.g. ``"architecture"``).
        registry: A loaded :class:`SpecRegistry`.

    Returns:
        A markdown string ready for embedding via markdown-exec.

    Raises:
        ValueError: If *kind* is not a :class:`SpecKind` value, or is
            ``protocol`` or ``foundation``, whose rows only the Requirements
            Catalog defines (:func:`render_catalog_page`, DF-12-002). A valid
            kind that no spec carries renders a notice saying so.
    """
    try:
        target_kind = SpecKind(kind)
    except ValueError:
        valid = [k.value for k in SpecKind]
        raise ValueError(f"Unknown SpecKind: {kind!r}. Valid values: {valid}")  # noqa: B904  # ruff-baseline #3353
    if target_kind in CATALOG_KINDS:
        raise ValueError(
            f"{target_kind.value} requirements render in the Requirements "
            "Catalog, not on a per-kind page; use render_catalog_page "
            "(SR-09-004, DF-12-002)"
        )

    # Route by effective kind: a file contributes to this page when it has at
    # least one item whose effective kind matches target_kind (SR-09-001).
    matching = [
        f
        for f in registry.files
        if any(
            spec.kind == target_kind
            for group in f.groups
            for spec in group.specs
        )
    ]
    if not matching:
        # A valid kind no spec carries yet still has its page (every SpecKind
        # has one, test_kind_page_coverage.py), so the build must not fail on
        # it; the page says so instead of rendering nothing.
        return _EMPTY_KIND_NOTICE.format(kind=target_kind.value)

    lines: list[str] = []
    href = requirement_linker(registry, kind_page(target_kind))

    # Separate behavioral files (tagged or containing BehavioralSpec items)
    regular: list[SpecFile] = []
    behavioral: list[SpecFile] = []
    for sf in matching:
        if _has_behavioral_tag(sf) or _is_behavioral_file(sf):
            behavioral.append(sf)
        else:
            regular.append(sf)

    for sf in regular:
        _render_file(lines, sf, href, target_kind, heading="##")

    if behavioral:
        lines.append("## Behavioral Specifications")
        lines.append("")
        lines.append(
            "The following specifications define Event-Condition-Action (ECA) "
            "behavioral requirements with typed preconditions, ordered steps, "
            "and postconditions."
        )
        lines.append("")
        for sf in behavioral:
            _render_file(lines, sf, href, target_kind, heading="###")

    return "\n".join(lines)


_registry_cache: dict[tuple[tuple[str, int], ...], SpecRegistry] = {}


def _docs_registry() -> SpecRegistry:
    """Return the repository's registry, loaded once per state of ``specs/``.

    Each callout on a page would otherwise parse the whole corpus again. The
    key is every YAML file's name and modification time, so ``mkdocs serve``
    sees an edited requirement on its next rebuild.
    """
    spec_dir = repo_root() / "specs"
    key = tuple(
        (path.name, path.stat().st_mtime_ns)
        for path in sorted(Path(spec_dir).glob("*.yaml"))
    )
    if key not in _registry_cache:
        _registry_cache.clear()
        _registry_cache[key] = load_registry(spec_dir)
    return _registry_cache[key]


def _catalog_page(key: str, pages: tuple[CatalogPage, ...]) -> CatalogPage:
    for page in pages:
        if page.key == key:
            return page
    known = ", ".join(p.key for p in pages)
    raise KeyError(f"no catalog page {key!r}; the pages are: {known}")


def render_catalog_page(
    key: str,
    registry: SpecRegistry | None = None,
    *,
    page: str | None = None,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
    heading: str | None = None,
) -> str:
    """Render the Requirements Catalog page *key* (DF-12-001).

    One subsection per requirement file the placement table gives the page,
    in table order, holding the file's items of the page's tier, group by
    group. Each row defines its requirement's anchor (DF-12-002). Headings
    carry the tier in their id, so a file whose items span both tiers has
    distinct headings on the two pages and on ``full.md``, which includes
    both.

    Args:
        key: The catalog page key.
        registry: The registry; the repository's when ``None``.
        page: ``docs/``-relative path of the page the output is printed on;
            the page being built when ``None``.
        pages: The placement table.
        heading: The Markdown heading of a file subsection; a group heading
            is one level below it. By default ``###`` under the page's
            ``## 14.N`` heading, and ``####`` on ``full.md``, where the
            subsection sits one level deeper, under ``## 14.``.

    Raises:
        KeyError: If *pages* has no page *key*.
        ValueError: If the page places a file that does not exist.
    """
    registry = registry if registry is not None else _docs_registry()
    catalog = _catalog_page(key, pages)
    on_page = page if page is not None else current_page()
    if heading is None:
        heading = "####" if on_page == FULL_PAGE else "###"
    href = requirement_linker(registry, on_page, pages=pages)
    files = {spec_file.id: spec_file for spec_file in registry.files}
    lines: list[str] = []
    for file_id in catalog.files:
        if file_id not in files:
            raise ValueError(
                f"catalog page {key!r} places {file_id}, which names no "
                "requirement file"
            )
        _render_file(
            lines,
            files[file_id],
            href,
            catalog.tier,
            heading=heading,
            anchor_prefix=f"{catalog.tier.value}-",
            show_file_id=False,
        )
    return "\n".join(lines)


def requirement_callout(
    *spec_ids: str,
    title: str = "Requirements",
    registry: SpecRegistry | None = None,
    page: str | None = None,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> str:
    """Render an ``info`` admonition showing the requirements *spec_ids*.

    The callout is how the Protocol Specification's narrative presents a
    normative requirement (DF-12-003): a table in the catalog's row format,
    each ID cell linking the requirement's catalog row and defining no anchor
    (DF-12-010). Call it in one line from a ``markdown-exec`` block.

    Args:
        spec_ids: The requirement IDs, in display order.
        title: The admonition title.
        registry: The registry; the repository's when ``None``.
        page: ``docs/``-relative path of the page the callout is printed on;
            the page being built when ``None``.
        pages: The placement table.

    Raises:
        ValueError: If no ID is given, an ID is given twice, or an ID names no
            requirement of kind ``protocol`` or ``foundation``
            (:class:`NotInCatalogError`), which fails the documentation
            build (DF-12-012).
    """
    if not spec_ids:
        raise ValueError("a requirement callout needs at least one ID")
    repeated = sorted({i for i in spec_ids if spec_ids.count(i) > 1})
    if repeated:
        raise ValueError(f"requirement callout repeats {', '.join(repeated)}")
    registry = registry if registry is not None else _docs_registry()
    for spec_id in spec_ids:
        catalog_location(spec_id, registry, pages)
    href = requirement_linker(
        registry,
        page if page is not None else current_page(),
        pages=pages,
    )
    rows = [
        render_requirement_row(registry.get(i), href, define_anchor=False)
        for i in spec_ids
    ]
    body = [*_TABLE_HEADER, *rows]
    return f'!!! info "{title}"\n\n' + "".join(f"    {r}\n" for r in body)
