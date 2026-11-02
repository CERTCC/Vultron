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
"""Every cited user story has a page (TRACE-03-001).

SR-11-002 checks the *shape* of a ``stories:`` entry, so ``story_2022_999``
passes while naming nothing. The edge is then silently broken: the generated
traceability matrix cannot show it, and nobody reading the requirement can
reach the need it claims to serve. This module is the hard error that closes
that gap, and it is deliberately not suppressible — a citation that resolves to
no page is a typo or a deleted page, never a judgment call. Compare SR-11-003,
whose gate *is* suppressible because "this requirement has no story" can be
true.

The rule is split in two so the gate is testable without a documentation tree:
:func:`cited_story_page_errors` is pure over a catalog, and
:func:`check_cited_story_pages` resolves the live catalog for the linter.

The other half of keeping the edges sound is that a page, once committed, is
never removed (TRACE-03-002): a removed page is both a dangling citation in
every past revision of its citers and a freed ID a later story could reuse,
silently repointing them. :func:`removed_story_pages` is that PR-only guard.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.docs.story_pages import (
    STORY_DIR,
    STORY_ROOT,
    story_catalog,
    story_ids,
)
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.specs.growth_guard import compare_with_base
from vultron.metadata.specs.registry import SpecRegistry


def cited_story_page_errors(
    registry: SpecRegistry, catalog: Collection[str]
) -> list[str]:
    """Return one error per requirement citing a story absent from *catalog*.

    Every absent ID on a requirement is named in its one error rather than one
    error per ID, so the message says what to fix about that requirement
    (EH-07-001).
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        missing = [
            story for story in spec.stories or [] if story not in catalog
        ]
        if missing:
            errors.append(
                f"{spec_id}: stories: names {', '.join(missing)}, which have "
                f"no page under docs/{STORY_DIR}/ (TRACE-03-001). Add the "
                "page, or correct the citation; this check is not "
                "suppressible."
            )
    return errors


def check_cited_story_pages(
    registry: SpecRegistry, repo_root: Path
) -> list[str]:
    """Return the TRACE-03-001 errors for the catalog under *repo_root*.

    Returns an empty list when that repository has no story catalog, so the
    check degrades gracefully in an environment without a ``docs/`` tree, as
    the ADR-reference check does. The catalog's own absence is not excused by
    this: ``uv run docs-site --check`` fails on it, because the generated table
    and matrix enumerate the catalog and cannot be rendered from nothing.
    """
    try:
        catalog = story_ids(repo_root)
    except MetadataLoadError:
        return []
    return cited_story_page_errors(registry, catalog)


@dataclass(frozen=True)
class CatalogRemovals:
    """What one :func:`removed_story_pages` evaluation found.

    Attributes:
        base: The merge-base commit compared against, or ``None`` if skipped.
        removed: Story IDs with a page at the base and none at the head.
        skipped: Why the comparison did not run, or ``None`` if it did.
    """

    base: str | None
    removed: frozenset[str]
    skipped: str | None = None

    def failure_message(self) -> str:
        """Name every removed page, one per line, with the remedy."""
        listing = "\n".join(f"  {story}" for story in sorted(self.removed))
        base = self.base[:12] if self.base else "?"
        return (
            f"{len(self.removed)} story page(s) removed since the merge base "
            f"{base}:\n{listing}\n"
            "Restore each page and mark it superseded, naming the story IDs "
            "that replace it (TRACE-03-002). A `stories:` entry must resolve "
            "for as long as any revision of the citing spec exists, and a "
            "freed ID can be reused, silently repointing every citation of "
            "the old story."
        )


def removed_story_pages(
    repo_root: Path,
    *,
    base_ref: str | None = None,
    require_base: bool | None = None,
) -> CatalogRemovals:
    """The TRACE-03-002 guard: story pages this branch removed.

    Arguments, skipping and errors are as
    :func:`~vultron.metadata.specs.growth_guard.added_since_base` documents.
    Only removals fail: a page the branch adds, and one the base already
    lacked, are not this branch's doing.
    """
    seen = compare_with_base(
        story_catalog,
        repo_root=repo_root,
        paths=(STORY_ROOT,),
        base_ref=base_ref,
        require_base=require_base,
    )
    if seen.base_value is None:
        return CatalogRemovals(None, frozenset(), skipped=seen.skipped)
    return CatalogRemovals(seen.base, seen.base_value - seen.head_value)


__all__ = [
    "CatalogRemovals",
    "check_cited_story_pages",
    "cited_story_page_errors",
    "removed_story_pages",
]
