"""Render the ``stakeholder_type`` × ``level`` coverage matrix (DF-11-008).

Design rationale: ``notes/site-information-architecture.md`` § "The coverage
matrix is generated too" (ADR-0102).

The matrix makes "we do not serve audience X at depth Y" a fact in a file. It
is written to ``notes/``, never ``docs/``, because it prints levels and a level
is never shown to readers (DF-11-004).

Its check enforces **currency, not fullness**: the committed file must match
the tree, and an empty cell is a recorded gap for planning, never a failure. A
rule demanding every type at every level would contradict the expected shape,
in which audiences share level 100 and diverge above it.

``ALL`` is counted as its own row rather than spread across every type's row,
so that shape — ``ALL`` heavy at 100 and thinning as the level climbs — stays
legible instead of being smeared across the table. A page listing two types is
counted once in each of their rows.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.docs.page_frontmatter import (
    DECLARATION_KEYS,
    classify_docs_tree,
)
from vultron.metadata.docs.page_schema import (
    ALL_STAKEHOLDERS,
    LEVELS,
    PageFrontmatter,
    StakeholderType,
    is_working_record,
)
from vultron.metadata.file_loading import (
    MetadataLoadError,
    load_frontmatter,
    validate,
)

#: Repository-relative path of the committed matrix.
MATRIX_PATH = "notes/site-coverage-matrix.md"

#: Row keys in display order: every member, then ``ALL`` as its own row.
ROWS: tuple[str, ...] = (
    *(member.value for member in StakeholderType),
    ALL_STAKEHOLDERS,
)


@dataclass
class Coverage:
    """Counts behind the matrix.

    Attributes:
        cells: ``(row, level) -> pages``, for rows in :data:`ROWS`.
        declared: Reader-facing pages that declare both keys.
        undeclared: Reader-facing pages that declare neither yet.
        working_record: Working-record pages, which carry no level.
    """

    cells: Counter[tuple[str, int]] = field(default_factory=Counter)
    declared: int = 0
    undeclared: int = 0
    working_record: int = 0


def measure_coverage(root: Path) -> Coverage:
    """Count every reader-facing page into its type × level cells.

    Raises:
        MetadataLoadError: If the tree resolves no pages (DF-09-009), or a
            page's declarations do not validate — a matrix built by skipping
            a malformed page would under-count the cell it belongs to.
    """
    tree = classify_docs_tree(root)
    if not tree.pages:
        raise MetadataLoadError(
            "resolved no pages to count; an empty target set is a failure, "
            "not a pass (DF-09-009)",
            path="docs",
        )
    coverage = Coverage()
    for rel in tree.pages:
        if is_working_record(rel):
            coverage.working_record += 1
            continue
        path = root / "docs" / rel
        metadata = load_frontmatter(path, root=root).metadata
        declared = {k: metadata[k] for k in DECLARATION_KEYS if k in metadata}
        if not declared:
            coverage.undeclared += 1
            continue
        fm = validate(PageFrontmatter, declared, path=path, root=root)
        types = (
            [member.value for member in fm.stakeholder_type]
            if isinstance(fm.stakeholder_type, list)
            else [ALL_STAKEHOLDERS]
        )
        for row in types:
            coverage.cells[(row, fm.level)] += 1
        coverage.declared += 1
    return coverage


_FRONTMATTER = """\
---
title: Site Coverage Matrix — Stakeholder Type × Level
status: active
description: >
  Generated count of reader-facing docs/ pages per stakeholder_type and level
  (DF-11-008). A gap here is planning input, never a merge blocker.
related_notes:
  - notes/site-information-architecture.md
related_specs:
  - specs/diataxis-requirements.yaml
---
"""


def render_matrix(coverage: Coverage) -> str:
    """Render the full contents of :data:`MATRIX_PATH`."""
    header = "| Stakeholder type | " + " | ".join(map(str, LEVELS)) + " |"
    delimiter = "|---|" + "---:|" * len(LEVELS)
    rows = [
        f"| `{row}` | "
        + " | ".join(str(coverage.cells[(row, lvl)]) for lvl in LEVELS)
        + " |"
        for row in ROWS
    ]
    return (
        f"{_FRONTMATTER}\n"
        "<!-- GENERATED from docs/ page frontmatter by "
        "`uv run docs-site --write` — do not edit (DF-11-008) -->\n\n"
        "# Site Coverage Matrix — Stakeholder Type × Level\n\n"
        "How many reader-facing `docs/` pages declare each `stakeholder_type`\n"
        "at each `level`. Read it against the expected shape described in\n"
        "[site-information-architecture.md](site-information-architecture.md):"
        "\n`ALL` heavy at 100 and thinning as the level climbs, the named types"
        "\ndiverging above it. An empty cell is a gap someone has to decide "
        "about;\nnothing fails because of one.\n\n"
        "`ALL` is its own row, not spread across the others. A page listing "
        "two\ntypes is counted in both of their rows.\n\n"
        f"{header}\n{delimiter}\n" + "\n".join(rows) + "\n\n"
        "## Not in the table\n\n"
        f"- Reader-facing pages counted above: {coverage.declared}\n"
        "- Reader-facing pages that declare neither key yet (baselined in\n"
        "  `vultron/metadata/docs/page_frontmatter_baseline.txt`): "
        f"{coverage.undeclared}\n"
        "- Working-record pages, which carry no level (DF-11-012): "
        f"{coverage.working_record}\n"
    )
