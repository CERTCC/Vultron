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
"""Generate and check the occasion table and its fragments (ADR-0128).

One generator projects the occasions on ``SEMANTIC_REGISTRY`` into committed
artifacts, and ``--check`` fails on any difference (MSM-06-001):

- ``vultron/metadata/msm/occasions.yaml`` — the occasion table, with a
  ``format_version``.  Internal; publication belongs to #2959.
  :func:`~vultron.metadata.msm._mapping.load_occasion_table` loads and
  validates it.
- ``docs/reference/messages/_occasions/lookup.md`` — the whole table, one
  ``##`` group per message page: the case lifecycle first, then protocol
  mechanics.
- ``docs/reference/messages/_occasions/lookup-<page>.md`` — one page's slice.
- ``docs/reference/messages/_occasions/shorthands.md`` — the formal message
  set, each shorthand with the wire activities that carry it, for the
  Protocol Quick Reference (MSM-06-004).
- ``docs/reference/messages/_occasions/sections/<anchor>.md`` — one section
  per occasion, anchored by the occasion's ID.
- ``docs/reference/messages/_occasions/embeds/<anchor>.md`` — one embed per
  occasion: what a page outside the reference includes at the step that sends
  the occasion.  It is a box with no heading, holding the facts a sender acts
  on, a link to the canonical section and the example JSON collapsed, so one
  source renders in two places, separated and linked (DF-01-003, ADR-0128).

Each section's "Seen in" lists the pages that include its embed.  It is read
from the include directives of every page under ``docs/`` outside the
fragment directory, never typed by hand, and the fragments themselves include
nothing, so the pages that are read are never pages this generator writes:
one ``--write`` settles a new include, and ``--check`` cannot loop.  The
occasion's own message page carries the section, not the embed, so it never
lists itself; no message page may include an embed.  A page the production
build withholds (``draft_docs``, ``exclude_docs``) is not listed, and an embed
must sit on the page a reader sees, not in a fragment another page includes
whole.  An occasion that declares a how-to guide must be embedded there,
which is how the guides are held to show what their steps send.

The table fragments are not named ``*table*.md``: ``lint-docs`` exempts that
name as a generated content class, and these carry occasion prose it must
check (DF-09-007).  Only ``*.md`` files under the fragment directory count as
committed fragments, so ``--write`` never deletes anything else there.

The fragments are rendered from the YAML text, re-parsed, not from the
registry, so the YAML carries every fact a fragment shows.  Every fragment
heading starts at ``##``; a host shifts it with ``heading-offset``.

Links are ordinary relative ``.md`` links, written from the fragment's own
directory.  ``include-markdown`` rewrites them for the host page and MkDocs
then rewrites and checks them as it does any hand-written link.  That is why
these are fragments and not ``markdown_exec`` output, whose links MkDocs never
sees (``vultron/metadata/AGENTS.md`` § Generate vs. Check).  The JSON example
is the exception: it carries no link and its IDs are minted per run, so a
section renders it with an exec block at build time.

The fragments are in ``exclude_docs``: they are not pages of their own.  The
message pages include them, and their links are checked there, against the
host page that carries the sections they point to.  Built alone, a table's
links would be checked against the wrong page, and every fragment would
publish a URL the project then has to keep.

Each section states its entry's mapping status, linked to the definition of
the status values on ``docs/reference/messages/index.md`` (MSM-06-003).  The
table does not carry it: its columns serve a sender choosing what to send, and
the status describes the formal protocol's relation to the wire form.

CLI (``uv run msm-occasions``):
    --check   exit 1 if the YAML or any fragment is stale or unexpected
    --write   rewrite every artifact and delete stale fragments
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from vultron.enums.object_types import VultronObjectType as VOtype
from vultron.metadata.base import mkdocs_config, repo_root, unbuilt_docs_spec
from vultron.metadata.docs.page_frontmatter import include_directives
from vultron.metadata.file_loading import (
    MetadataLoadError,
    loads_yaml,
    validate,
)
from vultron.metadata.generated_files import stale_paths, write_generated
from vultron.metadata.markdown_tables import iter_sections
from vultron.metadata.msm._mapping import (
    EXEMPTED_SEMANTICS,
    OCCASION_TABLE_FORMAT_VERSION,
    OCCASION_TABLE_PATH,
    MappingStatus,
    OccasionGroup,
    OccasionRow,
    OccasionTable,
    PageLink,
    distinguished_by,
    load_occasion_table,
    mapping_status,
    section_heading,
    send_to,
    sent_by,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    MessagePage,
    ProtocolShorthand,
)
from vultron.wire.as2.enums import as_ObjectType as AOtype
from vultron.wire.as2.extractor._pattern import ActivityPattern

#: Command that regenerates every artifact, quoted in every failure message.
WRITE_COMMAND = "uv run msm-occasions --write"

#: Repository-relative path of the occasion table, derived from
#: :data:`~vultron.metadata.msm._mapping.OCCASION_TABLE_PATH` so the two
#: cannot name different files.
YAML_PATH = OCCASION_TABLE_PATH.relative_to(
    Path(__file__).resolve().parents[3]
).as_posix()

#: Repository-relative directory holding every generated fragment.
FRAGMENT_DIR = "docs/reference/messages/_occasions"

#: Repository-relative directory holding each occasion's embed, the variant
#: a page outside the reference includes where it sends the occasion.
EMBED_DIR = f"{FRAGMENT_DIR}/embeds"

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
    for host in sorted(docs.rglob("*.md")):
        page = host.relative_to(docs)
        if page.is_relative_to(fragments):
            continue
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


# ---------------------------------------------------------------------------
# Rendering: OccasionTable -> markdown fragments.
# ---------------------------------------------------------------------------


#: Characters a ``<code>`` table cell spells as entities: the pipe, which
#: would end the cell, and the brackets, which a markdown linter reads as a
#: reversed link in ``(Event)[context=…]`` once no code span protects them.
_CODE_CELL_ENTITIES = str.maketrans(
    {"|": "&#124;", "[": "&#91;", "]": "&#93;"}
)


def _code_cell(text: str) -> str:
    """Render *text* as code in a table cell.

    A pipe cannot be escaped inside a backtick code span in a way both
    readers accept: Python-Markdown keeps a code span whole and would show
    ``\\|`` literally, while GFM (and so ``markdownlint``) splits the cell at
    a bare ``|``.  A ``<code>`` element with entities satisfies both.
    """
    if "|" in text:
        return f"<code>{text.translate(_CODE_CELL_ENTITIES)}</code>"
    return f"`{text}`"


def details_link(group: OccasionGroup, row: OccasionRow, prefix: str) -> str:
    """Link *row*'s section, from a fragment *prefix* away from the pages."""
    return f"[{row.heading}]({prefix}{group.page.value}.md#{row.anchor})"


def render_slice(group: OccasionGroup) -> str:
    """Render one group's table, linking from :data:`FRAGMENT_DIR`."""
    lines = [
        "| When… | Send | Send to | Sent by | Distinguished by | Details |",
        "|---|---|---|---|---|---|",
    ]
    for row in group.occasions:
        cells = (
            row.when,
            _code_cell(row.send),
            row.send_to,
            row.sent_by,
            row.distinguished_by or "—",
            details_link(group, row, "../"),
        )
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_whole(table: OccasionTable) -> str:
    """Render the whole table: each group under its own ``##`` heading."""
    blocks = [
        f"## {group.title}\n\n{render_slice(group)}" for group in table.groups
    ]
    return "\n\n".join(blocks)


#: The formal-model message page and state machine of each shorthand family,
#: keyed by the shorthand's first letter.
SHORTHAND_FAMILIES: dict[str, tuple[MessagePage, str]] = {
    "R": (MessagePage.RM, "RM"),
    "E": (MessagePage.EM, "EM"),
    "C": (MessagePage.CS, "CS"),
    "G": (MessagePage.GENERAL, "General"),
}

#: The anchor of the section each formal-model message page ends with, which
#: covers the shorthands that have no dedicated wire activity.
NO_WIRE_ANCHOR = "formal-messages-with-no-dedicated-wire-activity"


def _shorthand_carriers(
    table: OccasionTable,
) -> dict[ProtocolShorthand, list[str]]:
    """Link each shorthand's wire activities to their sections, once each."""
    carriers: dict[ProtocolShorthand, dict[str, str]] = {
        shorthand: {} for shorthand in ProtocolShorthand
    }
    for group in table.groups:
        for row in group.occasions:
            if row.shorthand is None:
                continue
            carriers[row.shorthand].setdefault(
                row.send,
                f"[{_code_cell(row.send)}](../{group.page.value}.md"
                f"#{row.anchor})",
            )
    return {s: list(links.values()) for s, links in carriers.items()}


def render_shorthands(table: OccasionTable) -> str:
    """Render the formal message set, linking from :data:`FRAGMENT_DIR`.

    One row per shorthand, in formal order, naming the wire activities whose
    occasions carry it.  A shorthand no occasion carries links its family
    page's section on shorthands with no dedicated wire activity.
    """
    carriers = _shorthand_carriers(table)
    lines = [
        "| Type | Name | Model | Wire activity |",
        "| :---: | --- | :---: | --- |",
    ]
    for shorthand in ProtocolShorthand:
        page, model = SHORTHAND_FAMILIES[shorthand.value[0]]
        wire = ", ".join(carriers[shorthand]) or (
            f"[none](../{page.value}.md#{NO_WIRE_ANCHOR})"
        )
        cells = (f"`{shorthand.value}`", shorthand.formal_name, model, wire)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def formal_link(shorthand: ProtocolShorthand, prefix: str) -> str:
    """Link *shorthand*'s definition in the formal message set."""
    label = f"{shorthand.formal_name} ({shorthand.value})"
    target = f"formal_protocol/messages.md#{shorthand.formal_section}"
    return f"[{label}]({prefix}{target})"


#: The message page that defines each mapping status value, and the anchor
#: of that definition (MSM-06-003).
STATUS_PAGE = "index.md"
STATUS_ANCHOR = "mapping-status"


def status_link(status: MappingStatus, prefix: str) -> str:
    """Link *status* to its definition, from *prefix* away from the pages."""
    return f"[{status.value}]({prefix}{STATUS_PAGE}#{STATUS_ANCHOR})"


def _send_facts(row: OccasionRow) -> list[str]:
    """The facts a sender acts on, shared by a section and its embed."""
    facts = [
        f"- **When…** {row.when}",
        f"- **Send:** `{row.send}`",
        f"- **Send to:** {row.send_to}",
        f"- **Sent by:** {row.sent_by}",
    ]
    if row.distinguished_by is not None:
        facts.append(f"- **Distinguished by:** {row.distinguished_by}")
    return facts


def seen_in_link(page: PageLink, prefix: str) -> str:
    """Link *page*, from a fragment *prefix* away from ``docs/``."""
    return f"[{page.title}]({prefix}{page.path})"


def _example_block(row: OccasionRow) -> str:
    """The exec block that renders *row*'s example JSON at build time."""
    return (
        '```python exec="true" idprefix=""\n'
        "from vultron.wire.as2.vocab.examples.vocab_examples import (\n"
        f"    {row.example},\n"
        "    json2md,\n"
        ")\n"
        "\n"
        f"print(json2md({row.example}()))\n"
        "```"
    )


def render_section(row: OccasionRow) -> str:
    """Render *row*'s section, linking from ``FRAGMENT_DIR/sections``."""
    to_pages = "../../"
    to_reference = "../" + to_pages
    to_docs = "../" + to_reference
    facts = _send_facts(row)
    if row.seen_in:
        pages = ", ".join(seen_in_link(page, to_docs) for page in row.seen_in)
        facts.append(f"- **Seen in:** {pages}")
    if row.shorthand is not None:
        facts.append(
            f"- **Formal definition:** {formal_link(row.shorthand, to_reference)}"
        )
    facts.append(f"- **Mapping status:** {status_link(row.status, to_pages)}")
    blocks = [
        f"## {row.heading} {{ #{row.anchor} }}",
        row.description,
        "\n".join(facts),
    ]
    if row.notes is not None:
        blocks.append(row.notes)
    blocks.append(_example_block(row))
    return "\n\n".join(blocks)


def _indent(text: str) -> str:
    """Indent *text* one admonition level; blank lines stay empty."""
    return textwrap.indent(text, "    ")


def render_embed(group: OccasionGroup, row: OccasionRow) -> str:
    """Render *row*'s embed, linking from :data:`EMBED_DIR`.

    The embed is what a page outside the reference shows where one of its
    steps sends the occasion: a box set apart from the host's own prose,
    holding the facts a sender acts on, a link to the canonical section, and
    the example JSON collapsed.  It carries no heading, so it adds no anchor
    and no table-of-contents entry to its host, and leaves out the reference
    facts (formal definition, mapping status, notes and "Seen in") that the
    linked section holds (DF-01-003).
    """
    to_pages = "../../"
    facts = _send_facts(row)
    facts.append(f"- **Reference:** {details_link(group, row, to_pages)}")
    example = '??? example "Example activity"\n\n' + _indent(
        _example_block(row)
    )
    body = "\n\n".join([row.description, "\n".join(facts), example])
    return f'!!! info "{row.heading}"\n\n' + _indent(body)


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------


def _fragment(body: str) -> str:
    return f"{FRAGMENT_MARKER}\n\n{body}\n"


def desired_contents(
    root: Path | None = None,
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
) -> dict[str, str]:
    """Return ``{repo-relative path: contents}`` for every artifact.

    The fragments are rendered from the YAML text, re-parsed, so a fact the
    YAML does not carry cannot reach a fragment.
    """
    base = root or repo_root()
    text = dump_table(derive_table(registry, base))
    shown = Path(YAML_PATH)
    table = validate(OccasionTable, loads_yaml(text, shown), path=shown)
    contents = {YAML_PATH: text}
    contents[f"{FRAGMENT_DIR}/lookup.md"] = _fragment(render_whole(table))
    contents[f"{FRAGMENT_DIR}/shorthands.md"] = _fragment(
        render_shorthands(table)
    )
    for group in table.groups:
        contents[f"{FRAGMENT_DIR}/lookup-{group.page.value}.md"] = _fragment(
            render_slice(group)
        )
        for row in group.occasions:
            contents[f"{FRAGMENT_DIR}/sections/{row.anchor}.md"] = _fragment(
                render_section(row)
            )
            contents[f"{EMBED_DIR}/{row.anchor}.md"] = _fragment(
                render_embed(group, row)
            )
    return contents


def _committed_fragments(base: Path) -> set[str]:
    directory = base / FRAGMENT_DIR
    if not directory.is_dir():
        return set()
    return {
        path.relative_to(base).as_posix()
        for path in directory.rglob("*.md")
        if path.is_file()
    }


@dataclass(frozen=True)
class Drift:
    """How the committed artifacts differ from a fresh generation.

    Attributes:
        stale: Paths whose contents differ or that are missing.
        unexpected: Files under :data:`FRAGMENT_DIR` that nothing generates.
    """

    stale: tuple[str, ...]
    unexpected: tuple[str, ...]


def _compare(
    base: Path, registry: Sequence[SemanticEntry]
) -> tuple[dict[str, str], Drift]:
    """Generate once and compare; the single comparison point for
    ``--check`` and ``--write``, so the two cannot disagree about "stale"."""
    desired = desired_contents(base, registry)
    stale = tuple(stale_paths(base, desired))
    unexpected = sorted(_committed_fragments(base) - set(desired))
    return desired, Drift(stale=stale, unexpected=tuple(unexpected))


def drift(
    root: Path | None = None,
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
) -> Drift:
    """Compare the committed artifacts with a fresh generation."""
    return _compare(root or repo_root(), registry)[1]


def write_artifacts(
    root: Path | None = None,
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
) -> list[str]:
    """Rewrite stale artifacts, delete unexpected fragments; return paths."""
    base = root or repo_root()
    desired, found = _compare(base, registry)
    for path in found.stale:
        write_generated(base / path, desired[path])
    for path in found.unexpected:
        (base / path).unlink()
    return [*found.stale, *found.unexpected]


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run msm-occasions [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the occasion table or any fragment is stale.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite the occasion table and every fragment.",
    )
    args = parser.parse_args(argv)
    root = repo_root()

    if args.write:
        written = write_artifacts(root)
        if not written:
            print("Occasion artifacts already in sync.")
        for path in written:
            print(f"Wrote {path}")
        return

    problems: list[str] = []
    try:
        load_occasion_table(root / YAML_PATH, root=root)
    except FileNotFoundError:
        pass  # reported as stale below
    except MetadataLoadError as exc:
        problems.append(str(exc))
    found = drift(root)
    problems.extend(
        f"{path} is stale — run '{WRITE_COMMAND}' (MSM-06-001)."
        for path in found.stale
    )
    problems.extend(
        f"{path} is not generated from any occasion — run "
        f"'{WRITE_COMMAND}' to delete it (MSM-06-001)."
        for path in found.unexpected
    )
    if problems:
        for problem in problems:
            print(f"[ERROR] {problem}", file=sys.stderr)
        sys.exit(1)
    print("Occasion artifacts are in sync.")


if __name__ == "__main__":
    main()


__all__ = [
    "EMBED_DIR",
    "FRAGMENT_DIR",
    "FRAGMENT_MARKER",
    "NO_WIRE_ANCHOR",
    "SHORTHAND_FAMILIES",
    "STATUS_ANCHOR",
    "STATUS_PAGE",
    "TABLE_GROUPS",
    "WRITE_COMMAND",
    "YAML_PATH",
    "Drift",
    "TableGroup",
    "derive_table",
    "desired_contents",
    "details_link",
    "drift",
    "dump_table",
    "embedding_pages",
    "emitted_type",
    "format_pattern",
    "formal_link",
    "main",
    "page_title",
    "render_embed",
    "render_section",
    "render_shorthands",
    "render_slice",
    "render_whole",
    "seen_in_link",
    "status_link",
    "wire_summary",
    "write_artifacts",
]
