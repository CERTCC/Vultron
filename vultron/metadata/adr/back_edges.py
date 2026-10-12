"""Report live decision records that nothing in ``specs/`` or ``notes/`` points back to.

Requirements: specs/meta-specifications.yaml MS-11-004, MS-11-006, MS-16-002;
specs/architecture.yaml ARCH-18-005 (the exemption set). Decision: ADR-0127.

Under ADR-0127 a decision record is history, and specs and notes are the only
documents that describe the current state. A decision is therefore reachable
from current-state documents only through a **back-edge**:

- a structured ``adr:`` edge on some requirement in ``specs/``, or
- a prose citation in a ``specs/`` or ``notes/`` file, either the record's
  ``ADR-NNNN`` identifier or its file name.

A live record (not archived, and not ``superseded``, ``deprecated`` or
``rejected``) with no back-edge is **homeless** unless it is legitimately
record-only. Record-only records are the one-time process choices MS-11-006
says need no spec entry; they are listed in :data:`RECORD_ONLY_EXEMPTIONS`, a
pinned exemption set rather than a ratchet or a backlog: it has no terminal
value, and its entries are exempt by that recorded decision.

The report is computed from the corpus on every run, never read from a
committed count (MS-16-002).

CLI: ``uv run adr-back-edges`` — prints each homeless record and each stale
exemption, and exits 1 when there is either.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.adr.loader import adr_number, load_adr_registry
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import AdrStatus

#: Records that are legitimately record-only, so need no back-edge.
#:
#: A pinned exemption set (ARCH-18-005), not a ratchet and not a backlog: it has
#: no terminal value, because these records are exempt by a recorded decision
#: rather than awaiting a home. Both are meta-process choices about how this
#: project records decisions — keep decision records at all (ADR-0000), and write
#: them in MADR form (ADR-0001). Neither imposes a per-change requirement an
#: agent could check, which is the MS-11-006 test for an ADR that needs no spec
#: entry. The set is kept equal to reality in both directions: an entry that
#: gains a back-edge, or stops being a live record, is reported as stale.
#:
#: permanent: MS-11-006
RECORD_ONLY_EXEMPTIONS: frozenset[str] = frozenset({"ADR-0000", "ADR-0001"})

#: Statuses whose records have left the live set.
_RETIRED_STATUSES = frozenset(
    {AdrStatus.SUPERSEDED, AdrStatus.DEPRECATED, AdrStatus.REJECTED}
)

#: File types under ``specs/`` and ``notes/`` that can carry a citation.
_TEXT_SUFFIXES = frozenset({".md", ".yaml", ".yml"})

_ADR_ID_RE = re.compile(r"\bADR-(\d{4})\b")


@dataclass(frozen=True)
class LiveRecord:
    """A live decision record: its ``ADR-NNNN`` id and its file name."""

    adr_id: str
    file_name: str


@dataclass(frozen=True)
class BackEdgeReport:
    """The result of one back-edge audit.

    Attributes:
        homeless: Live records with no back-edge and no exemption, sorted.
        stale_exemptions: Exemption entries that are not live records or that
            have a back-edge, sorted.
    """

    homeless: tuple[str, ...]
    stale_exemptions: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """True when nothing is homeless and every exemption is still needed."""
        return not self.homeless and not self.stale_exemptions


def cited_records(
    texts: Iterable[str], records: Iterable[LiveRecord]
) -> set[str]:
    """Return the ids of *records* that some text in *texts* cites in prose.

    A citation is the record's ``ADR-NNNN`` id as a whole token, or its file
    name.
    """
    by_name = {r.file_name: r.adr_id for r in records}
    cited: set[str] = set()
    for text in texts:
        cited.update(f"ADR-{num}" for num in _ADR_ID_RE.findall(text))
        cited.update(
            adr_id for name, adr_id in by_name.items() if name in text
        )
    return cited


def audit_back_edges(
    records: Iterable[LiveRecord],
    structured_edges: Iterable[str],
    texts: Iterable[str],
    exemptions: Iterable[str] = RECORD_ONLY_EXEMPTIONS,
) -> BackEdgeReport:
    """Classify live records by whether anything points back to them.

    Args:
        records: The live decision records.
        structured_edges: Every ``ADR-NNNN`` value of every requirement's
            ``adr:`` field.
        texts: The contents of every ``specs/`` and ``notes/`` file.
        exemptions: Record-only ids that need no back-edge.

    Returns:
        The homeless records and the stale exemptions.
    """
    live = list(records)
    live_ids = {r.adr_id for r in live}
    reached = set(structured_edges) | cited_records(texts, live)
    exempt = set(exemptions)
    homeless = sorted(live_ids - reached - exempt)
    stale = sorted(e for e in exempt if e not in live_ids or e in reached)
    return BackEdgeReport(
        homeless=tuple(homeless), stale_exemptions=tuple(stale)
    )


def live_records(
    adr_registry: Mapping[str, AdrFrontmatter],
) -> list[LiveRecord]:
    """Return the live records of an ADR registry keyed by relative path.

    A record is live when it is outside ``docs/adr/archived/`` and its status is
    not ``superseded``, ``deprecated`` or ``rejected``.

    Raises:
        ValueError: If a record's file name carries no ``NNNN-`` number.
    """
    live: list[LiveRecord] = []
    for rel_path, fm in adr_registry.items():
        path = Path(rel_path)
        if "archived" in path.parts:
            continue
        if fm.status in _RETIRED_STATUSES:
            continue
        number = adr_number(path)
        if number is None:
            raise ValueError(f"{rel_path}: decision record name has no number")
        live.append(LiveRecord(adr_id=f"ADR-{number}", file_name=path.name))
    return live


def _corpus_texts(root: Path) -> list[str]:
    texts: list[str] = []
    for tree in ("specs", "notes"):
        for path in sorted((root / tree).rglob("*")):
            if path.is_file() and path.suffix in _TEXT_SUFFIXES:
                texts.append(path.read_text(encoding="utf-8"))
    return texts


def audit_corpus(
    root: Path | None = None, registry: SpecRegistry | None = None
) -> BackEdgeReport:
    """Run :func:`audit_back_edges` over the repository at *root*.

    Args:
        root: Repository root; resolved from ``pyproject.toml`` when ``None``.
        registry: An already-loaded ``specs/`` registry, to skip reloading it.
    """
    root = root or _find_repo_root()
    registry = registry or load_registry(root / "specs")
    edges = [
        adr for spec in registry.all_specs.values() for adr in spec.adr or []
    ]
    return audit_back_edges(
        records=live_records(load_adr_registry(root)),
        structured_edges=edges,
        texts=_corpus_texts(root),
    )


def main() -> None:
    """CLI entry point: ``uv run adr-back-edges``."""
    report = audit_corpus()
    for adr_id in report.homeless:
        print(
            f"{adr_id}: live record with no back-edge from specs/ or notes/ "
            "and no record-only exemption"
        )
    for adr_id in report.stale_exemptions:
        print(
            f"{adr_id}: stale record-only exemption (not a live record, or "
            "now has a back-edge); remove it from RECORD_ONLY_EXEMPTIONS"
        )
    if report.clean:
        print("Every live decision record has a back-edge or an exemption.")
    sys.exit(0 if report.clean else 1)


if __name__ == "__main__":
    main()
