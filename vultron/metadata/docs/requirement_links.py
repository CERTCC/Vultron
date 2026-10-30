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
"""Point every ``docs/`` link to a requirement at the page that defines it.

A requirement, group or file anchor is defined only where its items render:
a ``protocol`` or ``foundation`` item on its Requirements Catalog page, any
other kind on its per-kind requirements page (SR-09-001, SR-09-002,
SR-09-004, DF-12-002). A ``kind:`` relabel or a catalog placement change moves the
anchor, and every prose link to the old page then dangles. This module finds
each Markdown link whose target is a requirements page and rewrites it to the
page and fragment :func:`~vultron.metadata.docs.requirement_catalog.anchor_homes`
gives:

1. **A requirement cited by its group anchor.** A link whose text is one
   requirement ID, or a comma-separated list of them, all of the anchored
   group, is repointed at each requirement's own row, one link per ID. A
   relabel can move one ID off a page while the group anchor still resolves
   there, so neither the build nor the next pass would catch it (#4894).
2. **Any link whose anchor is not defined on the page it names.** The link
   moves to a page that defines it. For a group or file shown on several
   pages, that is the page of the tier the link named (``protocol.md`` or a
   ``protocol-`` fragment means the ``protocol`` tier), else the page showing
   the most of its items, with :class:`SpecKind` order as the tie-break.

Links to the retired per-kind pages of the two catalog tiers
(``reference/specs/protocol.md`` and ``foundation.md``) are rewritten the
same way, since their anchors now live in the catalog (#4901).

Links are resolved against the file that holds them, so a fragment's links
stay relative to the fragment, as ``include-markdown`` expects. Lines inside
fenced code are left alone. An anchor the registry does not know is reported
and left unchanged.

:func:`anchor_definition_faults` is the other half of DF-12-002: no page but
a catalog page and ``full.md`` defines a catalog anchor.

The CLI is ``scripts/relink_requirement_anchors.py``; the gate that holds
``docs/`` to both rules is ``test/metadata/docs/test_requirement_links.py``.
"""

from __future__ import annotations

import ast
import posixpath
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.docs.level_order import fragment_hosts
from vultron.metadata.docs.page_frontmatter import classify_docs_tree
from vultron.metadata.docs.requirement_catalog import (
    CATALOG_KINDS,
    CATALOG_PAGES,
    FULL_PAGE,
    RETIRED_KIND_PAGES,
    AnchorHome,
    CatalogPage,
    anchor_homes,
    kind_page,
)
from vultron.metadata.markdown_tables import (
    ExecBlock,
    exec_blocks,
    fenced_lines,
)
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    SPEC_GROUP_PATTERN,
    SPEC_ID_PATTERN,
    SpecKind,
)

_ID_LIST_RE = re.compile(rf"{SPEC_ID_PATTERN}(?:,\s*{SPEC_ID_PATTERN})*")
# A group anchor is the lowercased group ID (``#df-12``).
_GROUP_RE = re.compile(SPEC_GROUP_PATTERN, re.IGNORECASE)
_LINK_RE = re.compile(
    r"\[(?P<text>[^\]\n]*)\]"
    r"\((?P<page>[^)#\s]+)#(?P<fragment>[^)\s]+)\)"
)


def requirement_pages(
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> dict[str, SpecKind]:
    """Map each page a requirement link may name to the tier it shows.

    The per-kind pages of every kind (the retired two included, so links to
    them are found and moved) and the Requirements Catalog pages.
    """
    named = {
        kind_page(kind): kind for kind in SpecKind if kind not in CATALOG_KINDS
    }
    named.update(RETIRED_KIND_PAGES)
    named.update({page.path: page.tier for page in pages})
    return named


@dataclass
class RelinkStats:
    """Tallies for one or more files.

    Attributes:
        repointed: Links split or repointed from a group to a requirement.
        moved: Links moved to another page or fragment.
        unknown_ids: Requirement IDs in link text the registry does not know.
        unknown_anchors: Fragments, with their ``#``, the registry does not
            know.
    """

    repointed: int = 0
    moved: int = 0
    unknown_ids: Counter[str] = field(default_factory=Counter)
    unknown_anchors: Counter[str] = field(default_factory=Counter)

    def add(self, other: RelinkStats) -> None:
        """Fold *other*'s tallies into this one."""
        self.repointed += other.repointed
        self.moved += other.moved
        self.unknown_ids.update(other.unknown_ids)
        self.unknown_anchors.update(other.unknown_anchors)


def _href(home: AnchorHome, path: str) -> str:
    start = posixpath.dirname(path) or "."
    return f"{posixpath.relpath(home.page, start)}#{home.fragment}"


def _bare(fragment: str) -> tuple[str, SpecKind | None]:
    """The ID a fragment names and the tier its prefix names, if any."""
    for kind in CATALOG_KINDS:
        prefix = f"{kind.value}-"
        if fragment.startswith(prefix):
            return fragment.removeprefix(prefix), kind
    return fragment, None


def _best(homes: tuple[AnchorHome, ...], tier: SpecKind) -> AnchorHome:
    """The home of *tier* if there is one, else the one with the most items.

    *homes* is in :class:`SpecKind` order, so ``max`` keeps the first of a
    tie.
    """
    same_tier = [home for home in homes if home.tier is tier]
    return max(same_tier or homes, key=lambda home: home.items)


class RequirementLinker:
    """Rewrite requirement links in ``docs/`` files against one registry."""

    def __init__(
        self,
        registry: SpecRegistry,
        pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
    ) -> None:
        self._homes: Mapping[str, tuple[AnchorHome, ...]] = anchor_homes(
            registry, pages
        )
        self._pages = requirement_pages(pages)

    def _split(
        self, text: str, group: str, path: str, stats: RelinkStats
    ) -> str | None:
        """Pass 1: one link per requirement ID, or ``None`` to leave it."""
        if not _GROUP_RE.fullmatch(group) or not _ID_LIST_RE.fullmatch(text):
            return None
        spec_ids = re.split(r",\s*", text)
        if any(i.lower().rsplit("-", 1)[0] != group for i in spec_ids):
            return None  # names another group's ID: not these requirements
        unknown = [i for i in spec_ids if i.lower() not in self._homes]
        if unknown:
            stats.unknown_ids.update(
                unknown
            )  # report every one, not the first
            return None
        stats.repointed += len(spec_ids)
        return ", ".join(
            f"[{i}]({_href(self._homes[i.lower()][0], path)})"
            for i in spec_ids
        )

    def relink(self, text: str, path: str) -> tuple[str, RelinkStats]:
        """Return *text*, held at ``docs/``-relative *path*, relinked.

        Returns:
            The rewritten text, unchanged when every link is already right,
            and the tallies of what changed.
        """
        stats = RelinkStats()
        fenced = fenced_lines(text)
        directory = posixpath.dirname(path)

        def rewrite(match: re.Match[str]) -> str:
            target = posixpath.normpath(
                posixpath.join(directory, match["page"])
            )
            named_tier = self._pages.get(target)
            if named_tier is None:
                return match[0]
            bare, prefixed_tier = _bare(match["fragment"])
            homes = self._homes.get(bare)
            if homes is None:
                stats.unknown_anchors[f"#{match['fragment']}"] += 1
                return match[0]
            split = self._split(match["text"], bare, path, stats)
            if split is not None:
                return split
            if any(
                (h.page, h.fragment) == (target, match["fragment"])
                for h in homes
            ):
                return match[0]
            stats.moved += 1
            home = _best(homes, prefixed_tier or named_tier)
            return f"[{match['text']}]({_href(home, path)})"

        lines = text.splitlines(keepends=True)
        out = [
            line if number in fenced else _LINK_RE.sub(rewrite, line)
            for number, line in enumerate(lines, 1)
        ]
        return "".join(out), stats


def retired_page_links(text: str, path: str) -> list[str]:
    """Return each link target in *text* that names a retired tier page."""
    directory = posixpath.dirname(path)
    fenced = fenced_lines(text)
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if number in fenced:
            continue
        for match in re.finditer(r"\]\((?P<target>[^)\s]+)\)", line):
            page = match["target"].split("#", 1)[0]
            if not page or "://" in page:
                continue
            resolved = posixpath.normpath(posixpath.join(directory, page))
            if resolved in RETIRED_KIND_PAGES:
                found.append(f"docs/{path}:{number}: {match['target']}")
    return found


# The renderers whose output defines requirement anchors, with the keyword
# name of the argument that picks what they render.
_RENDERERS = {"render_catalog_page": "key", "render_for_kind": "kind"}
# An ``id=`` attribute, an ``<a name=>``, or an attribute-list id in any of
# its forms: ``{#id}``, ``{: #id }``, ``{.cls #id}``.
_ANCHOR_DEF_RE = re.compile(
    r"""\bid=["'](?P<id>[^"']+)["']"""
    r"""|<a\s[^>]*\bname=["'](?P<name>[^"']+)["']"""
    r"|\{:?(?:[^}#]*\s)?#(?P<attr>[\w-]+)[^}]*\}"
)


def anchor_definition_faults(
    root: Path,
    registry: SpecRegistry,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> list[str]:
    """Return every way ``docs/`` defines a catalog anchor outside its row.

    The anchor of a ``protocol`` or ``foundation`` requirement, and the
    tier-prefixed anchors of its group and file headings, are defined only by
    the Requirements Catalog and its copy on ``full.md`` (DF-12-002). They are
    printed by :func:`~vultron.metadata.specs.docs_render.render_catalog_page`,
    so a fault is (renderer calls count only inside ``markdown-exec``
    blocks, the code the build runs):

    * a ``render_catalog_page`` call anywhere but the key's own catalog
      fragment, :attr:`CatalogPage.fragment`;
    * a ``render_for_kind`` call for a catalog tier (which also raises);
    * a renderer call whose argument is not a string literal, so it cannot
      be placed, or a ``markdown-exec`` block that does not parse;
    * a catalog fragment that is missing, or that renders on a page other
      than its catalog page and ``full.md``, or not on both;
    * a hand-written ``id=``, ``<a name=>`` or ``{#…}`` naming a catalog
      anchor, in any file.

    Args:
        root: The repository root, holding ``docs/`` and ``mkdocs.yml``,
            which decide what is a page and what is an include fragment.
        registry: The loaded requirement registry.
        pages: The placement table.
    """
    docs_dir = root / "docs"
    catalog_paths = {page.path for page in pages}
    anchors = frozenset(
        home.fragment
        for homes in anchor_homes(registry, pages).values()
        for home in homes
        if home.page in catalog_paths
    )
    fragment_of = {page.key: page.fragment for page in pages}
    faults: list[str] = []
    for source in sorted(docs_dir.rglob("*.md")):
        rel = source.relative_to(docs_dir).as_posix()
        faults += _file_faults(
            rel, source.read_text(encoding="utf-8"), anchors, fragment_of
        )
    return faults + _fragment_host_faults(root, pages)


def _renderer_calls(code: str) -> list[tuple[int, str, str | None]]:
    """``(lineno, renderer, argument)`` for each renderer call in *code*.

    The argument is the literal that picks what the call renders, positional
    or by keyword, or ``None`` when it is not a string literal and so cannot
    be placed.

    Raises:
        SyntaxError: If *code* does not parse.
    """
    calls: list[tuple[int, str, str | None]] = []
    for node in ast.walk(ast.parse(code)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        if name not in _RENDERERS:
            continue
        picked = node.args[:1] or [
            k.value for k in node.keywords if k.arg == _RENDERERS[name]
        ]
        arg = (
            picked[0].value
            if picked
            and isinstance(picked[0], ast.Constant)
            and isinstance(picked[0].value, str)
            else None
        )
        calls.append((node.lineno, name, arg))
    return calls


def _exec_call_fault(
    where: str,
    fn: str,
    arg: str | None,
    rel: str,
    fragment_of: Mapping[str, str],
) -> str | None:
    """The fault in one renderer call inside an exec block, if any."""
    if arg is None:
        return f"{where}: {fn}() without a literal argument cannot be placed"
    if fn == "render_for_kind":
        if arg in {kind.value for kind in CATALOG_KINDS}:
            return (
                f"{where}: render_for_kind({arg!r}) — the tier renders only "
                "in the Requirements Catalog"
            )
        return None
    if fragment_of.get(arg) != rel:
        home = fragment_of.get(arg, "no fragment: no such key")
        return f"{where}: render_catalog_page({arg!r}) belongs only in {home}"
    return None


def _exec_faults(
    rel: str, block: ExecBlock, fragment_of: Mapping[str, str]
) -> list[str]:
    """The renderer-call faults in one ``markdown-exec`` block."""
    try:
        calls = _renderer_calls(block.code)
    except SyntaxError as error:
        line = block.line + (error.lineno or 0)
        return [f"docs/{rel}:{line}: exec block does not parse: {error.msg}"]
    return [
        fault
        for lineno, fn, arg in calls
        if (
            fault := _exec_call_fault(
                f"docs/{rel}:{block.line + lineno}", fn, arg, rel, fragment_of
            )
        )
    ]


def _file_faults(
    rel: str,
    text: str,
    anchors: frozenset[str],
    fragment_of: Mapping[str, str],
) -> list[str]:
    """The anchor-definition faults in one ``docs/`` file.

    A renderer call counts only inside a ``markdown-exec`` block, the one
    place the build runs it, and is read by parsing the block, so a call over
    several lines or by keyword is still seen. An anchor counts only outside
    fenced code, where it would render.
    """
    faults: list[str] = []
    for block in exec_blocks(text):
        faults.extend(_exec_faults(rel, block, fragment_of))
    fenced = fenced_lines(text)
    for number, line in enumerate(text.splitlines(), 1):
        if number in fenced:
            continue
        for match in _ANCHOR_DEF_RE.finditer(line):
            anchor = match["id"] or match["name"] or match["attr"]
            if anchor in anchors:
                faults.append(
                    f"docs/{rel}:{number}: defines #{anchor}, a Requirements "
                    "Catalog anchor (DF-12-002)"
                )
    return faults


def _fragment_host_faults(
    root: Path, pages: tuple[CatalogPage, ...]
) -> list[str]:
    """Each catalog fragment that is missing or renders on the wrong pages."""
    tree = classify_docs_tree(root)
    built = frozenset(tree.pages)
    faults: list[str] = []
    for page in pages:
        if not (root / "docs" / page.fragment).is_file():
            faults.append(f"docs/{page.fragment}: missing catalog fragment")
            continue
        rendered_on = set(
            fragment_hosts(page.fragment, tree, built, frozenset())
        )
        expected = {page.path, FULL_PAGE}
        if rendered_on != expected:
            faults.append(
                f"docs/{page.fragment}: renders on "
                f"{sorted(rendered_on) or 'no page'}; expected exactly "
                f"{sorted(expected)}"
            )
    return faults


__all__ = [
    "RelinkStats",
    "anchor_definition_faults",
    "RequirementLinker",
    "requirement_pages",
    "retired_page_links",
]
