"""Derive the occasion table from ``SEMANTIC_REGISTRY`` and the docs pages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from vultron.enums.object_types import VultronObjectType as VOtype
from vultron.metadata.base import (
    markdown_files,
    mkdocs_config,
    repo_root,
    unbuilt_docs_spec,
)
from vultron.metadata.docs.page_frontmatter import include_directives
from vultron.metadata.markdown_tables import iter_sections
from vultron.metadata.msm._mapping import (
    EXEMPTED_SEMANTICS,
    OCCASION_TABLE_FORMAT_VERSION,
    OCCASION_TABLE_PATH,
    OccasionGroup,
    OccasionRow,
    OccasionTable,
    PageLink,
    distinguished_by,
    mapping_status,
    section_heading,
    send_to,
    sent_by,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    MessagePage,
)
from vultron.wire.as2.enums import as_ObjectType as AOtype
from vultron.wire.as2.extractor._pattern import ActivityPattern

#: Command that regenerates every artifact, quoted in every failure message.
WRITE_COMMAND = "uv run msm-occasions --write"


#: Repository-relative path of the occasion table, derived from
#: :data:`~vultron.metadata.msm._mapping.OCCASION_TABLE_PATH` so the two
#: cannot name different files.
YAML_PATH = OCCASION_TABLE_PATH.relative_to(
    Path(__file__).resolve().parents[4]
).as_posix()


#: Repository-relative directory holding every generated fragment.
FRAGMENT_DIR = "docs/reference/messages/_occasions"


#: Repository-relative directory holding each occasion's embed, the variant
#: a page outside the reference includes where it sends the occasion.
EMBED_DIR = f"{FRAGMENT_DIR}/embeds"


# Labels of the two content tabs every section renders.  Every section on a
# page uses the same two, so the theme's linked tabs (``content.tabs.link``)
# switch them together; the embed reuses the example label for its collapsed
# box.
DETAILS_TAB = "Details"


EXAMPLE_TAB = "Example activity"


#: The first line of every fragment.  An HTML comment, so it renders nowhere.
FRAGMENT_MARKER = (
    "<!-- Generated from SEMANTIC_REGISTRY — do not edit; "
    f"edit the occasions and run `{WRITE_COMMAND}` -->"
)


@dataclass(frozen=True)
class TableGroup:
    """One group of the whole table: a message page and its title.

    Attributes:
        page: The message page.
        title: The group's heading in the whole table, in sentence case.
        mechanics: ``True`` for protocol mechanics, which follow the case
            lifecycle.
    """

    page: MessagePage
    title: str
    mechanics: bool = False


#: The whole table's groups in reading order (ADR-0128): the case lifecycle,
#: then protocol mechanics.  This is not ``MessagePage`` order, which is the
#: nav order.
TABLE_GROUPS: tuple[TableGroup, ...] = (
    TableGroup(MessagePage.RM, "Report"),
    TableGroup(MessagePage.CASE_PROPOSAL, "Case proposal"),
    TableGroup(MessagePage.CASE_MANAGEMENT, "Case and participants"),
    TableGroup(MessagePage.EM, "Embargo"),
    TableGroup(MessagePage.CS, "Case status"),
    TableGroup(MessagePage.GENERAL, "General"),
    TableGroup(
        MessagePage.FAULTS_AND_ACKNOWLEDGEMENTS,
        "Faults and acknowledgments",
        mechanics=True,
    ),
    TableGroup(
        MessagePage.LEDGER_REPLICATION, "Ledger replication", mechanics=True
    ),
)


# ---------------------------------------------------------------------------
# Wire summary.
# ---------------------------------------------------------------------------


#: Object types a pattern matches on that the sender emits under another
#: ``type``.  The embargo patterns match AS2 ``Event``, and the matcher accepts
#: a plain ``as:Event`` as an embargo, which is a defect: the sender always
#: emits ``EmbargoEvent``, receivers must accept only that, and Wire Activity
#: notation writes the type the sender puts on the wire (Annex C).  This is a
#: rendering override only.  #5155 owns fixing the patterns and the matcher,
#: after which this table should become empty.
_EMITTED_TYPE: Mapping[str, str] = {
    str(AOtype.EVENT): str(VOtype.EMBARGO_EVENT),
}


def emitted_type(type_name: object) -> str:
    """Return the ``type`` a sender emits for the pattern type *type_name*."""
    name = str(type_name)
    return _EMITTED_TYPE.get(name, name)


def format_pattern(pattern: ActivityPattern) -> str:
    """Render *pattern* as a compact wire-form string.

    Object types are rendered as the sender emits them (:data:`_EMITTED_TYPE`).

    Examples::

        Offer(VulnerabilityReport)
        Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])
        Add(CaseStatus)[target=VulnerabilityCase]
    """
    parts: list[str] = []
    if pattern.object_ is not None:
        if isinstance(pattern.object_, ActivityPattern):
            parts.append(f"({format_pattern(pattern.object_)})")
        else:
            parts.append(f"({emitted_type(pattern.object_)})")

    qualifiers: list[str] = []
    if pattern.target_ is not None:
        if isinstance(pattern.target_, ActivityPattern):
            qualifiers.append(f"target={format_pattern(pattern.target_)}")
        else:
            qualifiers.append(f"target={emitted_type(pattern.target_)}")
    if pattern.context_ is not None:
        if isinstance(pattern.context_, ActivityPattern):
            qualifiers.append(f"context={format_pattern(pattern.context_)}")
        else:
            qualifiers.append(f"context={emitted_type(pattern.context_)}")

    qualifier_str = "[" + ", ".join(qualifiers) + "]" if qualifiers else ""
    return f"{pattern.activity_}" + "".join(parts) + qualifier_str


def wire_summary(entry: SemanticEntry) -> str:
    """Return *entry*'s wire summary, without markup.

    Raises:
        ValueError: When the entry has no pattern; only the dispatcher
            fallbacks lack one, and they have no occasions.
    """
    if entry.pattern is None:
        raise ValueError(f"{entry.semantics.name} has no ActivityPattern")
    return format_pattern(entry.pattern)


# ---------------------------------------------------------------------------
# Derivation: registry -> OccasionTable.
# ---------------------------------------------------------------------------


def page_title(docs_path: str, root: Path) -> str:
    """Return the H1 of the ``docs/``-relative page *docs_path*.

    Raises:
        ValueError: When the page has no H1.
    """
    path = root / "docs" / docs_path
    for section in iter_sections(path.read_text(encoding="utf-8")):
        if section.level == 1:
            return section.heading.strip()
    raise ValueError(f"docs/{docs_path} has no H1 to title a link with")


def _page_includes(
    docs: Path, fragments: Path
) -> tuple[dict[str, list[str]], set[str]]:
    """Return each page's include targets, and the targets included whole.

    Pages are the ``docs/``-relative ``*.md`` files outside *fragments*, in
    path order; a target counts whether or not it exists yet.
    """
    directives: dict[str, list[str]] = {}
    included: set[str] = set()
    skipped = docs / fragments
    for host in markdown_files(docs, lambda directory: directory == skipped):
        page = host.relative_to(docs)
        found = list(include_directives(host, docs, existing=False))
        included.update(target for _, target, whole in found if whole)
        directives[page.as_posix()] = [target for _, target, _ in found]
    return directives, included


def embedding_pages(
    owners: Mapping[str, MessagePage], root: Path
) -> dict[str, tuple[str, ...]]:
    """Return ``{anchor: docs/-relative pages}`` for every embedded occasion.

    Reads the include directives of every page under ``docs/`` outside
    :data:`FRAGMENT_DIR`, whose fragments include nothing, so the result never
    depends on a file this generator writes.  A directive counts whether or
    not the embed exists yet, so one ``--write`` settles a new include.  A
    page that ``mkdocs.yml``'s ``draft_docs`` or ``exclude_docs`` keeps out
    of the production build is skipped: a "Seen in" link to it would point
    at a page the published site withholds.

    Args:
        owners: Each occasion anchor, mapped to the message page that holds
            its canonical section.
        root: The repository root, holding ``mkdocs.yml`` and ``docs/``.

    Raises:
        ValueError: When a page includes the embed of an anchor no occasion
            declares, a message page includes an embed (it carries sections),
            or a file another page includes whole holds an embed, which would
            list the fragment rather than the page a reader sees.
    """
    docs = root / "docs"
    fragments = Path(FRAGMENT_DIR).relative_to("docs")
    embeds = Path(EMBED_DIR).relative_to("docs")
    message_pages = fragments.parent
    unbuilt = unbuilt_docs_spec(mkdocs_config(root))
    directives, included = _page_includes(docs, fragments)
    found: dict[str, list[str]] = {}
    problems: list[str] = []
    for docs_path, targets in directives.items():
        for target in targets:
            path = Path(target)
            if path.parent != embeds:
                continue
            anchor = path.stem
            if anchor not in owners:
                problems.append(
                    f"docs/{docs_path} includes {target}, "
                    "which no occasion declares"
                )
            elif Path(docs_path).is_relative_to(message_pages):
                problems.append(
                    f"docs/{docs_path} includes {target}; "
                    "a message page includes sections, not embeds"
                )
            elif docs_path in included:
                problems.append(
                    f"docs/{docs_path} includes {target} but is itself "
                    "included whole by another page; embed the occasion on the "
                    "page that includes it"
                )
            elif unbuilt.match_file(docs_path):
                continue
            elif docs_path not in found.setdefault(anchor, []):
                found[anchor].append(docs_path)
    if problems:
        raise ValueError("; ".join(problems))
    return {anchor: tuple(pages) for anchor, pages in found.items()}


def derive_table(
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
    root: Path | None = None,
) -> OccasionTable:
    """Project *registry*'s occasions into an :class:`OccasionTable`.

    Rows follow registry order within a group, which is dispatch order.

    Raises:
        ValueError: When a page carrying occasions is in no table group, a
            derivation fails (a missing heading, an undeclared sender rule),
            or an occasion's declared how-to guide does not embed it.
    """
    base = root or repo_root()
    entries = [e for e in registry if e.semantics not in EXEMPTED_SEMANTICS]
    grouped = {group.page for group in TABLE_GROUPS}
    ungrouped = {e.page for e in entries if e.page not in grouped}
    if ungrouped:
        names = ", ".join(sorted(str(p) for p in ungrouped))
        raise ValueError(f"pages in no TABLE_GROUPS entry: {names}")

    owners = {
        o.anchor: e.page
        for e in entries
        if e.page is not None
        for o in e.occasions
    }
    embedded = embedding_pages(owners, base)
    unembedded = sorted(
        f"{occasion.anchor} (docs/{occasion.howto.value})"
        for entry in entries
        for occasion in entry.occasions
        if occasion.howto is not None
        and occasion.howto.value not in embedded.get(occasion.anchor, ())
    )
    if unembedded:
        raise ValueError(
            "how-to guides that do not embed the occasion they declare: "
            + ", ".join(unembedded)
        )

    groups: list[OccasionGroup] = []
    for group in TABLE_GROUPS:
        rows = [
            OccasionRow(
                anchor=occasion.anchor,
                heading=section_heading(occasion, registry),
                when=occasion.when,
                send=wire_summary(entry),
                send_to=send_to(occasion),
                sent_by=sent_by(entry, occasion),
                distinguished_by=distinguished_by(entry, occasion),
                semantics=entry.semantics,
                shorthand=occasion.shorthand,
                status=mapping_status(entry, registry),
                description=occasion.description,
                notes=occasion.notes,
                seen_in=tuple(
                    PageLink(path=page, title=page_title(page, base))
                    for page in embedded.get(occasion.anchor, ())
                ),
                example=occasion.example,
            )
            for entry in entries
            if entry.page is group.page
            for occasion in entry.occasions
        ]
        if rows:
            groups.append(
                OccasionGroup(
                    page=group.page,
                    title=group.title,
                    mechanics=group.mechanics,
                    occasions=tuple(rows),
                )
            )
    return OccasionTable(
        format_version=OCCASION_TABLE_FORMAT_VERSION, groups=tuple(groups)
    )


_YAML_HEADER = (
    "# The occasion table, generated from SEMANTIC_REGISTRY (ADR-0128).\n"
    f"# Do not edit: edit the occasions and run `{WRITE_COMMAND}`.\n"
    "# Internal; not a published interface (#2959).\n"
)


def dump_table(table: OccasionTable) -> str:
    """Serialize *table* as the committed YAML text."""
    data = table.model_dump(mode="json", exclude_none=True)
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)
    return _YAML_HEADER + body
