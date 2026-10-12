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
- ``docs/reference/messages/_occasions/sections/<anchor>.md`` — one section
  per occasion, anchored by the occasion's ID.

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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from vultron.metadata.base import repo_root
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
    HowToLink,
    MappingStatus,
    OccasionGroup,
    OccasionRow,
    OccasionTable,
    distinguished_by,
    load_occasion_table,
    mapping_status,
    section_heading,
    sent_by,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    ProtocolShorthand,
)
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


def format_pattern(pattern: ActivityPattern) -> str:
    """Render *pattern* as a compact wire-form string.

    Examples::

        Offer(VulnerabilityReport)
        Accept(Invite(Event)[context=VulnerabilityCase])
        Add(CaseStatus)[target=VulnerabilityCase]
    """
    parts: list[str] = []
    if pattern.object_ is not None:
        if isinstance(pattern.object_, ActivityPattern):
            parts.append(f"({format_pattern(pattern.object_)})")
        else:
            parts.append(f"({pattern.object_})")

    qualifiers: list[str] = []
    if pattern.target_ is not None:
        if isinstance(pattern.target_, ActivityPattern):
            qualifiers.append(f"target={format_pattern(pattern.target_)}")
        else:
            qualifiers.append(f"target={pattern.target_}")
    if pattern.context_ is not None:
        if isinstance(pattern.context_, ActivityPattern):
            qualifiers.append(f"context={format_pattern(pattern.context_)}")
        elif isinstance(pattern.context_, tuple):
            # A tuple admits any of several subjects (VAM-05-001); render the
            # alternatives, not the enum reprs.
            alternatives = "|".join(str(t) for t in pattern.context_)
            qualifiers.append(f"context={alternatives}")
        else:
            qualifiers.append(f"context={pattern.context_}")

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


def howto_title(guide: HowToGuide, root: Path) -> str:
    """Return the H1 of *guide*'s page, the text a link to it carries.

    Raises:
        ValueError: When the page has no H1.
    """
    path = root / "docs" / guide.value
    for section in iter_sections(path.read_text(encoding="utf-8")):
        if section.level == 1:
            return section.heading.strip()
    raise ValueError(f"docs/{guide.value} has no H1 to title a link with")


def derive_table(
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
    root: Path | None = None,
) -> OccasionTable:
    """Project *registry*'s occasions into an :class:`OccasionTable`.

    Rows follow registry order within a group, which is dispatch order.

    Raises:
        ValueError: When a page carrying occasions is in no table group, or a
            derivation fails (a missing heading, an undeclared sender rule).
    """
    base = root or repo_root()
    entries = [e for e in registry if e.semantics not in EXEMPTED_SEMANTICS]
    grouped = {group.page for group in TABLE_GROUPS}
    ungrouped = {e.page for e in entries if e.page not in grouped}
    if ungrouped:
        names = ", ".join(sorted(str(p) for p in ungrouped))
        raise ValueError(f"pages in no TABLE_GROUPS entry: {names}")

    groups: list[OccasionGroup] = []
    for group in TABLE_GROUPS:
        rows = [
            OccasionRow(
                anchor=occasion.anchor,
                heading=section_heading(occasion, registry),
                when=occasion.when,
                send=wire_summary(entry),
                sent_by=sent_by(entry, occasion),
                distinguished_by=distinguished_by(occasion),
                semantics=entry.semantics,
                shorthand=occasion.shorthand,
                status=mapping_status(entry, registry),
                description=occasion.description,
                notes=occasion.notes,
                howto=(
                    None
                    if occasion.howto is None
                    else HowToLink(
                        path=occasion.howto,
                        title=howto_title(occasion.howto, base),
                    )
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
        "| When… | Send | Sent by | Distinguished by | Details |",
        "|---|---|---|---|---|",
    ]
    for row in group.occasions:
        cells = (
            row.when,
            _code_cell(row.send),
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


def render_section(row: OccasionRow) -> str:
    """Render *row*'s section, linking from ``FRAGMENT_DIR/sections``."""
    to_pages = "../../"
    to_reference = "../" + to_pages
    facts = [
        f"- **When…** {row.when}",
        f"- **Send:** `{row.send}`",
        f"- **Sent by:** {row.sent_by}",
    ]
    if row.distinguished_by is not None:
        facts.append(f"- **Distinguished by:** {row.distinguished_by}")
    if row.howto is not None:
        facts.append(
            f"- **How-to:** [{row.howto.title}]"
            f"(../{to_reference}{row.howto.path.value})"
        )
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
    blocks.append(
        '```python exec="true" idprefix=""\n'
        "from vultron.wire.as2.vocab.examples.vocab_examples import (\n"
        f"    {row.example},\n"
        "    json2md,\n"
        ")\n"
        "\n"
        f"print(json2md({row.example}()))\n"
        "```"
    )
    return "\n\n".join(blocks)


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
    for group in table.groups:
        contents[f"{FRAGMENT_DIR}/lookup-{group.page.value}.md"] = _fragment(
            render_slice(group)
        )
        for row in group.occasions:
            contents[f"{FRAGMENT_DIR}/sections/{row.anchor}.md"] = _fragment(
                render_section(row)
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
    "FRAGMENT_DIR",
    "FRAGMENT_MARKER",
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
    "format_pattern",
    "formal_link",
    "howto_title",
    "main",
    "render_section",
    "render_slice",
    "render_whole",
    "status_link",
    "wire_summary",
    "write_artifacts",
]
