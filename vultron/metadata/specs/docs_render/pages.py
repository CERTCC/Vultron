"""Requirement tables for docs pages: per-kind pages, catalog pages and
callouts.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.docs.exec_page import EXEC_BUILD_ENV
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
from vultron.metadata.specs.coverage import (
    ImplementerCoverageReport,
    compute_implementer_coverage,
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

#: Maps each xfail-only requirement's ID to the issues its holds cite: the
#: rows that carry the "not yet in the reference implementation" marker
#: (DF-12-021). An ID absent from it gets no marker.
NotYetImplemented = Mapping[str, tuple[int, ...]]


def _render_group(
    lines: list[str],
    group: SpecGroup,
    href: RequirementHref,
    not_yet_implemented: NotYetImplemented,
    heading: str = "###",
    specs: list[Spec] | None = None,
    anchor: str | None = None,
) -> None:
    """Render *group* to *lines*, each row defining its requirement's anchor.

    When *specs* is provided only those specs are rendered (used to suppress
    items whose effective kind does not match the page — SR-09-005).
    When *specs* is ``None`` all items in the group are rendered. *anchor*
    overrides the heading's id, which defaults to the group ID's. A row of
    an ID in *not_yet_implemented* carries its marker (DF-12-021).
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
        lines.append(
            render_requirement_row(
                spec,
                href,
                define_anchor=True,
                not_yet_implemented=not_yet_implemented.get(spec.id),
            )
        )
    lines.append("")


def _render_file(
    lines: list[str],
    spec_file: SpecFile,
    href: RequirementHref,
    current_kind: SpecKind,
    not_yet_implemented: NotYetImplemented,
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
            not_yet_implemented,
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

    # Only the two catalog tiers have coverage states (SR-05-017), so no row
    # on a per-kind page carries the marker.
    for sf in regular:
        _render_file(lines, sf, href, target_kind, {}, heading="##")

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
            _render_file(lines, sf, href, target_kind, {}, heading="###")

    return "\n".join(lines)


_TreeKey = tuple[tuple[str, int], ...]

_registry_cache: dict[_TreeKey, SpecRegistry] = {}

_not_yet_implemented_cache: dict[object, NotYetImplemented] = {}


def _specs_key(spec_dir: Path) -> _TreeKey:
    """Each top-level YAML file :func:`load_registry` reads, with its
    modification time."""
    return tuple(
        (path.name, path.stat().st_mtime_ns)
        for path in sorted(spec_dir.glob("*.yaml"))
    )


def _tests_key(test_root: Path) -> _TreeKey:
    """Every ``*.py`` file under *test_root* outside ``__pycache__``, with its
    modification time.

    A file that cannot be stat'ed, such as a dangling symlink an editor left,
    is skipped, as the coverage scan skips a file it cannot read.
    """
    found = []
    for directory, subdirs, files in os.walk(test_root):
        subdirs[:] = [d for d in subdirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            try:
                mtime = os.stat(path).st_mtime_ns
            except OSError:
                continue
            found.append((os.path.relpath(path, test_root), mtime))
    return tuple(sorted(found))


def _docs_registry() -> SpecRegistry:
    """Return the repository's registry, loaded once per state of ``specs/``.

    Each callout on a page would otherwise parse the whole corpus again. The
    key is every YAML file's name and modification time, so ``mkdocs serve``
    sees an edited requirement on its next rebuild.
    """
    spec_dir = repo_root() / "specs"
    key = _specs_key(spec_dir)
    if key not in _registry_cache:
        _registry_cache.clear()
        _registry_cache[key] = load_registry(spec_dir)
    return _registry_cache[key]


def _docs_not_yet_implemented() -> NotYetImplemented:
    """The repository's xfail-only requirements and the issues they cite.

    Computed by ``spec-coverage``'s classifier (SR-05-017) from ``specs/`` and
    ``test/``, which reads every test file, so it is computed once and reused.
    During a docs build the key is the build id the ``exec_page.py`` hook
    records, so a build checks neither tree again and ``mkdocs serve``
    recomputes on each rebuild. Outside a build the key is both trees'
    modification times. Either way an edited test drops a marker on the next
    render (DF-12-021).

    Raises:
        FileNotFoundError: If the checkout has no ``test/`` tree, which would
            otherwise read every requirement as untested and drop every
            marker unseen.
    """
    root = repo_root()
    test_root = root / "test"
    if not test_root.is_dir():
        raise FileNotFoundError(
            f"{test_root} is missing; the not-yet-implemented markers on "
            "requirement rows are read from its tests (DF-12-021)"
        )
    build = os.environ.get(EXEC_BUILD_ENV)
    key: object = (
        ("build", build)
        if build
        else (_specs_key(root / "specs"), _tests_key(test_root))
    )
    if key not in _not_yet_implemented_cache:
        _not_yet_implemented_cache.clear()
        report = compute_implementer_coverage(_docs_registry(), test_root)
        _not_yet_implemented_cache[key] = report.xfail_only_issues()
    return _not_yet_implemented_cache[key]


def _markers(
    registry: SpecRegistry | None, coverage: ImplementerCoverageReport | None
) -> NotYetImplemented:
    """The marked rows for a renderer given *registry* and *coverage*.

    The repository's when both are ``None``, as on every docs page; those of
    *coverage* when it is given; and none for a caller that passes its own
    registry without a coverage report, whose requirements the repository's
    tests do not mark.
    """
    if coverage is not None:
        return coverage.xfail_only_issues()
    if registry is None:
        return _docs_not_yet_implemented()
    return {}


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
    coverage: ImplementerCoverageReport | None = None,
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
        coverage: The coverage states that put the "not yet in the reference
            implementation" marker on each xfail-only row (DF-12-021); see
            :func:`_markers` for the default.

    Raises:
        KeyError: If *pages* has no page *key*.
        ValueError: If the page places a file that does not exist.
    """
    not_yet_implemented = _markers(registry, coverage)
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
            not_yet_implemented,
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
    coverage: ImplementerCoverageReport | None = None,
) -> str:
    """Render an ``info`` admonition showing the requirements *spec_ids*.

    The callout is how the Protocol Specification's narrative presents a
    normative requirement (DF-12-003): a table in the catalog's row format,
    each ID cell linking the requirement's catalog row and defining no anchor
    (DF-12-010). An xfail-only requirement's row carries the same marker as
    its catalog row (DF-12-021). Call it in one line from a ``markdown-exec``
    block.

    Args:
        spec_ids: The requirement IDs, in display order.
        title: The admonition title.
        registry: The registry; the repository's when ``None``.
        page: ``docs/``-relative path of the page the callout is printed on;
            the page being built when ``None``.
        pages: The placement table.
        coverage: The coverage states that mark xfail-only rows (DF-12-021);
            see :func:`_markers` for the default.

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
    not_yet_implemented = _markers(registry, coverage)
    registry = registry if registry is not None else _docs_registry()
    for spec_id in spec_ids:
        catalog_location(spec_id, registry, pages)
    href = requirement_linker(
        registry,
        page if page is not None else current_page(),
        pages=pages,
    )
    rows = [
        render_requirement_row(
            registry.get(i),
            href,
            define_anchor=False,
            not_yet_implemented=not_yet_implemented.get(i),
        )
        for i in spec_ids
    ]
    body = [*_TABLE_HEADER, *rows]
    return f'!!! info "{title}"\n\n' + "".join(f"    {r}\n" for r in body)
