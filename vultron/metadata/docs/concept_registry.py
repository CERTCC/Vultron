"""The concepts ``docs/`` pages introduce, read for the level check.

Support for :mod:`vultron.metadata.docs.level_order` (DF-11-002). The glossary
is the concept registry (SG-11): a concept is a glossary term, and the page
that is its canonical introduction lists it under :data:`INTRODUCES_KEY` in
its frontmatter. This module reads the registry and validates those
declarations; the level check orders pages by them.
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.docs.concept_scan import term_forms
from vultron.metadata.docs.glossary_index import GLOSSARY_PATH, strip_bold
from vultron.metadata.docs.page_frontmatter import frontmatter_key_lines
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.markdown_tables import iter_tables

#: The frontmatter key naming the glossary terms a page introduces.
INTRODUCES_KEY = "introduces"

#: The glossary defines every term it lists, so it cannot depend on a page for
#: one; it is the registry the scan reads, never a page the scan reads.
REGISTRY = GLOSSARY_PATH.relative_to("docs").as_posix()


def glossary_terms(root: Path) -> dict[str, tuple[str, ...]]:
    """Map every glossary term to the spellings that count as a use of it.

    Raises:
        MetadataLoadError: If the glossary is missing or lists no term, since
            an empty registry would make every ``introduces`` entry unknown
            and every page vacuously compliant (DF-09-009).
    """
    path = root / "docs" / REGISTRY
    if not path.is_file():
        raise MetadataLoadError(
            "the glossary, the concept registry (SG-11), is missing",
            path=GLOSSARY_PATH.as_posix(),
        )
    terms: dict[str, tuple[str, ...]] = {}
    for table in iter_tables(path.read_text(encoding="utf-8")):
        if "Term" not in table.columns:
            continue
        for cell in table.column("Term"):
            term = strip_bold(cell).replace("`", "")
            if term:
                terms[term] = term_forms(term)
    if not terms:
        raise MetadataLoadError(
            "the glossary lists no terms; an empty concept registry is a "
            "failure, not a pass (DF-09-009)",
            path=GLOSSARY_PATH.as_posix(),
        )
    return terms


def introductions(
    rel: str,
    metadata: dict[str, object],
    *,
    path: Path,
    terms: dict[str, tuple[str, ...]],
    introducers: dict[str, str],
    can_introduce: str | None,
) -> list[MetadataLoadError]:
    """Record *rel*'s ``introduces`` entries and return every fault in them.

    Args:
        can_introduce: ``None`` when *rel* may introduce terms, else why not.
    """
    if INTRODUCES_KEY not in metadata:
        return []
    line = frontmatter_key_lines(path).get(INTRODUCES_KEY)

    def fault(detail: str) -> MetadataLoadError:
        return MetadataLoadError(
            f"{INTRODUCES_KEY}: {detail}", path=f"docs/{rel}", line=line
        )

    if can_introduce is not None:
        return [fault(can_introduce)]
    value = metadata[INTRODUCES_KEY]
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        return [fault("must be a non-empty list of glossary terms")]
    faults = []
    if len(set(value)) != len(value):
        faults.append(fault("lists a term more than once"))
    unknown = [v for v in value if v not in terms]
    if unknown:
        faults.append(
            fault(
                f"{', '.join(unknown)} is not a term in {GLOSSARY_PATH}; the "
                f"glossary is the concept registry (SG-11)"
            )
        )
    unmatchable = [v for v in value if v in terms and not terms[v]]
    if unmatchable:
        faults.append(
            fault(
                f"{', '.join(unmatchable)} has no spelling the scan can match "
                f"(single letters and slashed forms are dropped)"
            )
        )
    for term in dict.fromkeys(v for v in value if terms.get(v)):
        other = introducers.setdefault(term, rel)
        if other != rel:
            faults.append(
                fault(
                    f"{term} is already introduced by docs/{other}; a concept "
                    f"has one canonical introduction (SG-11)"
                )
            )
    return faults
