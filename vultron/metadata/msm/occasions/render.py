"""Render the occasion fragments: tables, sections, shorthands and embeds."""

from __future__ import annotations

import textwrap

from vultron.metadata.msm._mapping import (
    MappingStatus,
    OccasionGroup,
    OccasionRow,
    OccasionTable,
    PageLink,
)
from vultron.metadata.msm.occasions.table import DETAILS_TAB, EXAMPLE_TAB
from vultron.semantic_registry._occasion import (
    MessagePage,
    ProtocolShorthand,
)

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
#: of that definition (MSM-06-010).
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
    details = ["\n".join(facts)]
    if row.notes is not None:
        details.append(row.notes)
    tabs = [
        _tab(DETAILS_TAB, "\n\n".join(details)),
        _tab(EXAMPLE_TAB, _example_block(row)),
    ]
    return "\n\n".join(
        [
            f"## {row.heading} {{ #{row.anchor} }}",
            row.description,
            *tabs,
        ]
    )


def _indent(text: str) -> str:
    """Indent *text* one block level; blank lines stay empty."""
    return textwrap.indent(text, "    ")


def _tab(label: str, body: str) -> str:
    """Render *body* as one content tab labelled *label*.

    Adjacent tabs form one tab set.  The heading and description stay outside
    the set, so the occasion's anchor and its table-of-contents entry do not
    depend on which tab is open (MSM-08-004).
    """
    return f'=== "{label}"\n\n' + _indent(body)


def render_embed(group: OccasionGroup, row: OccasionRow) -> str:
    """Render *row*'s embed, linking from :data:`EMBED_DIR`.

    The embed is what a page outside the reference shows where one of its
    steps sends the occasion: a box set apart from the host's own prose,
    holding the facts a sender acts on, a link to the canonical section, and
    the example JSON collapsed.  It carries no heading, so it adds no anchor
    and no table-of-contents entry to its host, and leaves out the reference
    facts (formal definition, mapping status, notes and "Seen in") that the
    linked section holds (DF-01-007).
    """
    to_pages = "../../"
    facts = _send_facts(row)
    facts.append(f"- **Reference:** {details_link(group, row, to_pages)}")
    example = f'??? example "{EXAMPLE_TAB}"\n\n' + _indent(_example_block(row))
    body = "\n\n".join([row.description, "\n".join(facts), example])
    return f'!!! info "{row.heading}"\n\n' + _indent(body)
