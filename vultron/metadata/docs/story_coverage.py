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
"""Generate the user-story index table and traceability matrix (TRACE-03-003).

ADR-0072 made a requirement's ``stories:`` field the authoritative side of the
story graph, so the two artifacts that display that graph are rendered from it
rather than kept by hand:

* ``docs/reference/user_stories/table.md`` — the index table the stories'
  reader-facing ``index.md`` includes. One row per story page, with the number
  of requirements that cite it. Before #4506 its third column held a support
  level assigned once against v0.4.0, which no check could keep true.
* ``docs/reference/user_stories/traceability.md`` — the matrix TRACE-01-001
  requires. One section per story page, with its citing requirements grouped by
  spec file and each linked to the row that defines its anchor.

Both are whole-file artifacts in the ``docs-site`` flow, so ``uv run docs-site
--check`` fails a hand edit (DF-11-005's shape, applied here by TRACE-03-003).
Hand editing is how the old matrix came to link 161 of the 801 requirements
that carried a story (measured 2026-10-12, #4487).

Three design points worth not re-deriving:

* **The story text is included, never copied.** Each entry pulls the text from
  the story page's ``story-start``/``story-end`` markers with
  ``include-markdown``, so one source feeds both artifacts (DF-10-002).
* **Links are source-relative ``.md`` paths**, from
  :func:`~vultron.metadata.docs.requirement_catalog.source_href` over
  :func:`~vultron.metadata.docs.requirement_catalog.anchor_homes` — the same
  pair the relinker uses, so a generated link already satisfies the gate that
  holds ``docs/`` to the anchor homes, and a ``kind:`` relabel moves it on the
  next regeneration.
* **A cited story with no page raises.** The linter is the gate for that
  (TRACE-03-001), but dropping the citation here would let the generator
  disagree with the linter about what the corpus says.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.docs.landing_pages import WRITE_COMMAND
from vultron.metadata.docs.requirement_catalog import (
    anchor_home_of,
    anchor_homes,
    source_href,
)
from vultron.metadata.docs.story_pages import (
    STORY_DIR,
    STORY_END,
    STORY_START,
    story_ids,
    story_page,
)
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.specs.registry import SpecRegistry

#: Repository-relative path of the generated index table.
TABLE_PATH = f"docs/{STORY_DIR}/table.md"

#: Repository-relative path of the generated traceability matrix.
MATRIX_PATH = f"docs/{STORY_DIR}/traceability.md"

#: ``docs/``-relative path of the matrix, for links that resolve against it.
_MATRIX_PAGE = f"{STORY_DIR}/traceability.md"

#: ``docs/``-relative path of the table, for links that resolve against it.
_TABLE_PAGE = f"{STORY_DIR}/table.md"

#: What TRACE-01-002 requires a story no requirement cites to be marked with.
UNCITED_NOTE = "No mapped requirements"

_INCLUDE = (
    f'{{{{% include-markdown "./{{page}}" start="{STORY_START}" '
    f'end="{STORY_END}" trailing-newlines=false %}}}}'
)


@dataclass(frozen=True)
class Citation:
    """One requirement that cites a story.

    Attributes:
        spec_id: The citing requirement's ID.
        file_id: The ID of the spec file it is declared in.
        file_title: That file's title.
        href: Source-relative link to the row defining the requirement's
            anchor, resolved against the matrix page.
    """

    spec_id: str
    file_id: str
    file_title: str
    href: str


@dataclass(frozen=True)
class StoryCoverage:
    """Every story page with the requirements citing it.

    Attributes:
        by_story: ``story ID -> citations``, one key per story page in the
            catalog, in ID order, and the citations in spec-file then
            requirement-ID order. A story no requirement cites maps to an
            empty tuple, which is what TRACE-01-002 marks.
    """

    by_story: Mapping[str, tuple[Citation, ...]]

    @property
    def uncited(self) -> tuple[str, ...]:
        """The story IDs no requirement cites, in ID order."""
        return tuple(
            story for story, cites in self.by_story.items() if not cites
        )


def measure_story_coverage(
    root: Path, registry: SpecRegistry
) -> StoryCoverage:
    """Map every story page in the catalog to the requirements citing it.

    A requirement naming the same story twice is counted once: ``stories:``
    constrains each entry's shape but not the list's uniqueness, and a repeat
    would otherwise inflate the coverage count and print the same link twice.

    Raises:
        MetadataLoadError: If the story catalog resolves no pages, or a
            ``stories:`` entry names a story with no page (TRACE-03-001).
            Every such entry is named in one error (EH-07-001), since a run
            that reported the first would hide the rest.
    """
    catalog = story_ids(root)
    homes = anchor_homes(registry)
    cited: dict[str, list[Citation]] = {story: [] for story in catalog}
    dangling: Counter[str] = Counter()
    for spec_file in registry.files:
        for group in spec_file.groups:
            for spec in group.specs:
                home = anchor_home_of(homes, spec.id)
                for story in dict.fromkeys(spec.stories or []):
                    if story not in cited:
                        dangling[story] += 1
                        continue
                    cited[story].append(
                        Citation(
                            spec_id=spec.id,
                            file_id=spec_file.id,
                            file_title=spec_file.title,
                            href=(
                                source_href(
                                    home.page,
                                    home.fragment,
                                    from_page=_MATRIX_PAGE,
                                )
                                if home
                                else ""
                            ),
                        )
                    )
    if dangling:
        named = ", ".join(
            f"{story} ({count} citation(s))"
            for story, count in sorted(dangling.items())
        )
        raise MetadataLoadError(
            f"{len(dangling)} cited story ID(s) have no page under "
            f"docs/{STORY_DIR}/: {named}. Add the page, or correct the "
            "citing requirements' stories: fields (TRACE-03-001)",
            path=f"docs/{STORY_DIR}",
        )
    return StoryCoverage(
        {
            story: tuple(sorted(cites, key=lambda c: (c.file_id, c.spec_id)))
            for story, cites in cited.items()
        }
    )


def _generated_banner(requirement: str) -> str:
    return (
        "<!-- GENERATED from the specs' `stories:` fields by "
        f"`{WRITE_COMMAND}` — do not edit ({requirement}) -->"
    )


def _coverage_cell(story: str, cites: tuple[Citation, ...]) -> str:
    """The table's coverage cell: a count linking the matrix, or the note."""
    if not cites:
        return f"*{UNCITED_NOTE}*"
    href = source_href(_MATRIX_PAGE, story, from_page=_TABLE_PAGE)
    return f"[{len(cites)}]({href})"


def render_table(coverage: StoryCoverage) -> str:
    """Render the full contents of :data:`TABLE_PATH`."""
    rows = [
        f"| [{story.removeprefix('story_')}]({story_page(story)}) "
        f"| {_INCLUDE.format(page=story_page(story))} "
        f"| {_coverage_cell(story, cites)} |"
        for story, cites in coverage.by_story.items()
    ]
    return (
        f"{_generated_banner('TRACE-03-003')}\n\n"
        '!!! note "Legend"\n\n'
        "    - **Coverage** counts the requirements in `specs/` that cite the "
        "story in their `stories:` field. It links the story's section of the "
        "[traceability matrix](traceability.md).\n"
        f"    - *{UNCITED_NOTE}* means no requirement cites the story yet.\n\n"
        "| ID | Title | Coverage |\n"
        "|---|---|---:|\n" + "\n".join(rows) + "\n"
    )


def _matrix_entry(story: str, cites: tuple[Citation, ...]) -> str:
    """One story's section of the matrix.

    The heading links the story's page, which is what routes it: a story page
    is working record kept out of the navigation, reachable only through this
    matrix (DF-11-003, DF-11-006). The link does not change the heading's
    anchor, so the index table's link to this section still resolves.
    """
    head = (
        f"## [{story}]({story_page(story)})\n\n"
        f"{_INCLUDE.format(page=story_page(story))}\n"
    )
    if not cites:
        return f"{head}\n*{UNCITED_NOTE}* (TRACE-01-002).\n"
    rows = []
    for file_id in dict.fromkeys(c.file_id for c in cites):
        in_file = [c for c in cites if c.file_id == file_id]
        links = ", ".join(
            f"[{c.spec_id}]({c.href})" if c.href else c.spec_id
            for c in in_file
        )
        rows.append(f"| {file_id} — {in_file[0].file_title} | {links} |")
    return (
        f"{head}\n| Spec file | Citing requirements |\n"
        "|---|---|\n" + "\n".join(rows) + "\n"
    )


def render_matrix(coverage: StoryCoverage) -> str:
    """Render the full contents of :data:`MATRIX_PATH`."""
    entries = [
        _matrix_entry(story, cites)
        for story, cites in coverage.by_story.items()
    ]
    return (
        "---\nstakeholder_type: [project-contributor]\n---\n\n"
        f"{_generated_banner('TRACE-01-001')}\n\n"
        "# User Story Traceability Matrix\n\n"
        "This page maps each user story under "
        f"`docs/{STORY_DIR}/` to the requirements that cite it in their "
        "`stories:` field.\n"
        "The spec files are the authoritative side of the story graph "
        "(ADR-0072), so this page is generated from them and a hand edit "
        f"fails `{WRITE_COMMAND.replace('--write', '--check')}`.\n"
        "To change an entry, change the citing requirement's `stories:` "
        "field in `specs/` and regenerate.\n\n"
        f"A story that no requirement cites is marked *{UNCITED_NOTE}* "
        "(TRACE-01-002).\n"
        "Each requirement links the row that defines its anchor: the "
        "Requirements Catalog for a `protocol` or `foundation` requirement, "
        "its tier page for any other kind.\n\n" + "\n".join(entries)
    )


__all__ = [
    "MATRIX_PATH",
    "TABLE_PATH",
    "UNCITED_NOTE",
    "Citation",
    "StoryCoverage",
    "measure_story_coverage",
    "render_matrix",
    "render_table",
]
