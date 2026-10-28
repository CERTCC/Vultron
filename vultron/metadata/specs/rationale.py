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
"""Rationale coverage: the growth guard's extractor and two backfill worklists.

Requirements: specs/meta-specifications.yaml MS-10-012 through MS-10-015.

Every requirement carries a ``rationale:`` that gives its reason (MS-10-012),
not its history (MS-10-013). Until the backfill brings the corpus to zero, the
schema still admits a missing rationale, so three pieces hold the line:

- :func:`missing_rationale_ids` — the per-item extractor behind the PR-only
  growth guard (MS-10-014) in
  ``test/architecture/test_spec_rationale_guard.py``. It runs through
  :func:`vultron.metadata.specs.growth_guard.added_since_base`, so no count is
  committed.
- :func:`adr_link_candidates` — requirements a live decision record names in
  its body that do not cite that record in ``adr:`` (MS-10-015). Reading
  record bodies here is tooling, not agent context (ADR-0127): a person or
  agent working the list reads the requirement, and opens a record only to
  decide whether it is really a reason the requirement exists.
- :func:`history_narration_hits` — rationales that match
  :data:`HISTORY_PATTERNS` (MS-10-015). The patterns have false positives, so
  this is a worklist and never a gate.

CLI: ``uv run spec-rationale {missing,adr-links,history} [--file PATH ...]``
prints one line per item and exits 0 whatever it finds (2 on a usage error,
such as a ``--file`` that names no spec file); ``--file`` narrows the report to
the spec files a backfill task owns.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.adr.back_edges import live_records
from vultron.metadata.adr.loader import load_adr_post, load_adr_registry
from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
    load_spec_files,
)
from vultron.metadata.specs.schema import cited_spec_ids

#: Rationale text that usually narrates how a requirement came about
#: (MS-10-013).
#:
#: Each entry is a short label and the pattern it names. Issue, PR and planning
#: references are the most common narration, but a rationale may cite an issue
#: as a pointer to evidence, so a hit is a candidate to read, not a defect.
HISTORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("issue reference", re.compile(r"#\d+")),
    (
        "pull request",
        re.compile(
            r"\bPRs? #?\d+\b|\b(?:a|the|this|that|earlier|previous|later"
            r"|reverted) (?:PR|pull request)\b(?!-)",
            re.IGNORECASE,
        ),
    ),
    (
        "planning item",
        re.compile(r"\b(?:BUG|CONCERN|IDEA|ISSUE|TASK)-\d+\b"),
    ),
    (
        "prior state",
        re.compile(
            r"\b(?:previously|originally|formerly|historically|no longer"
            r"|the original|at the time|prior to)\b"
            # "used to" as a past habit, not the passive "is (only) used to",
            # "it's used to" or "commonly used to".
            r"|(?<!\bis )(?<!\bare )(?<!\bbe )(?<!\bbeen )(?<!\bwas )"
            r"(?<!\bwere )(?<!\bbeing )(?<!'s )(?<!n't )(?<!ly )"
            r"(?<!\bonly )(?<!\balso )(?<!\bnot )\bused to\b",
            re.IGNORECASE,
        ),
    ),
    (
        "edit event",
        re.compile(
            r"\b(?:was|were) (?:added|removed|renamed|introduced|changed"
            r"|split|merged|replaced|reverted|upgraded|downgraded)\b"
            r"|\breverted\b|\b(?:upgraded|downgraded) from\b",
            re.IGNORECASE,
        ),
    ),
    (
        "until a decision",
        re.compile(r"\buntil ADR-\d{4}\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True)
class HistoryHit:
    """A rationale that matches one or more :data:`HISTORY_PATTERNS`."""

    spec_id: str
    spec_file: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class AdrLinkCandidate:
    """A requirement a live decision record names but ``adr:`` does not cite."""

    spec_id: str
    spec_file: str
    adr_id: str


def missing_rationale(registry: SpecRegistry) -> frozenset[str]:
    """IDs of the requirements in *registry* with no ``rationale:``."""
    return frozenset(
        spec_id
        for spec_id, spec in registry.all_specs.items()
        if spec.rationale is None
    )


def missing_rationale_ids(repo_root: Path) -> frozenset[str]:
    """Requirements with no ``rationale:`` in ``specs/`` under *repo_root*.

    The per-item extractor behind the MS-10-014 growth guard
    (:func:`vultron.metadata.specs.growth_guard.added_since_base`).
    """
    return missing_rationale(load_registry(repo_root / "specs"))


def load_with_files(spec_dir: Path) -> tuple[SpecRegistry, dict[str, str]]:
    """The registry under *spec_dir*, and each requirement's file.

    Each file is named relative to the parent of *spec_dir*
    (``specs/<name>.yaml``), from the same load the registry is built from.
    """
    loaded = load_spec_files(spec_dir)
    owner = {
        spec.id: str(path.relative_to(spec_dir.parent))
        for path, spec_file in loaded
        for group in spec_file.groups
        for spec in group.specs
    }
    return SpecRegistry(files=[f for _, f in loaded]), owner


def history_labels(text: str) -> tuple[str, ...]:
    """The :data:`HISTORY_PATTERNS` labels whose pattern *text* matches.

    Whitespace runs collapse to one space first, so a line break inside a
    literal block reads like the space the patterns expect.
    """
    flat = " ".join(text.split())
    return tuple(
        label for label, pattern in HISTORY_PATTERNS if pattern.search(flat)
    )


def history_narration_hits(
    registry: SpecRegistry, spec_file: Mapping[str, str]
) -> list[HistoryHit]:
    """Rationales in *registry* that look like history, sorted by ID.

    Args:
        registry: The loaded requirements.
        spec_file: Each requirement's file, from :func:`load_with_files`.
    """
    hits: list[HistoryHit] = []
    for spec_id, spec in sorted(registry.all_specs.items()):
        labels = history_labels(spec.rationale or "")
        if labels:
            hits.append(HistoryHit(spec_id, spec_file[spec_id], labels))
    return hits


def adr_link_candidates(
    registry: SpecRegistry,
    spec_file: Mapping[str, str],
    adr_bodies: Mapping[str, str],
) -> list[AdrLinkCandidate]:
    """Requirements a record body names whose ``adr:`` omits that record.

    Args:
        registry: The loaded requirements.
        spec_file: Each requirement's file, from :func:`load_with_files`.
        adr_bodies: Each live record's body, keyed by ``ADR-NNNN``.

    Returns:
        One candidate per (requirement, record) pair, sorted by requirement
        then record. A body names an ID literally, inside a range, or in a
        slash list (:func:`~vultron.metadata.specs.schema.cited_spec_ids`);
        an ID that names no requirement is ignored.
    """
    specs = registry.all_specs
    found: set[tuple[str, str]] = set()
    for adr_id, body in adr_bodies.items():
        for spec_id in cited_spec_ids(body, specs):
            spec = specs.get(spec_id)
            if spec is not None and adr_id not in (spec.adr or []):
                found.add((spec_id, adr_id))
    return [
        AdrLinkCandidate(spec_id, spec_file[spec_id], adr_id)
        for spec_id, adr_id in sorted(found)
    ]


def live_adr_bodies(root: Path) -> dict[str, str]:
    """The body of every live decision record under *root*, by ``ADR-NNNN``.

    Live is as :func:`vultron.metadata.adr.back_edges.live_records` defines
    it: outside ``docs/adr/archived/`` and not superseded, deprecated or
    rejected.
    """
    adr_dir = root / "docs" / "adr"
    return {
        record.adr_id: load_adr_post(adr_dir / record.file_name, root).content
        for record in live_records(load_adr_registry(root))
    }


def _in_files(spec_file: str, files: Sequence[str]) -> bool:
    return not files or spec_file in files


def _normalize_files(files: Iterable[str]) -> list[str]:
    """``--file`` values as ``specs/<name>.yaml``; a bare name gains the dir."""
    return [f if "/" in f else f"specs/{f}" for f in files]


def report_lines(
    report: str, root: Path, files: Sequence[str] = ()
) -> list[str]:
    """The lines ``spec-rationale <report>`` prints for the repo at *root*.

    Args:
        report: ``missing``, ``adr-links`` or ``history``.
        root: Repository root.
        files: Spec files to keep (``specs/<name>.yaml``); empty keeps all.

    Raises:
        ValueError: *report* is not one of the three names, or a name in
            *files* is not a spec file.
    """
    spec_dir = root / "specs"
    registry, owner = load_with_files(spec_dir)
    unknown = sorted(set(files) - set(owner.values()))
    if unknown:
        raise ValueError(f"not a spec file under {spec_dir}: {unknown}")
    if report == "missing":
        return [
            f"{owner[spec_id]}: {spec_id}: no rationale"
            for spec_id in sorted(missing_rationale(registry))
            if _in_files(owner[spec_id], files)
        ]
    if report == "history":
        return [
            f"{hit.spec_file}: {hit.spec_id}: rationale may narrate history "
            f"({', '.join(hit.labels)})"
            for hit in history_narration_hits(registry, owner)
            if _in_files(hit.spec_file, files)
        ]
    if report == "adr-links":
        return [
            f"{c.spec_file}: {c.spec_id}: {c.adr_id} names it, but its adr: "
            f"does not cite {c.adr_id}"
            for c in adr_link_candidates(
                registry, owner, live_adr_bodies(root)
            )
            if _in_files(c.spec_file, files)
        ]
    raise ValueError(f"unknown report {report!r}")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run spec-rationale``; exits 0, or 2 on misuse."""
    parser = argparse.ArgumentParser(
        prog="spec-rationale",
        description=(
            "Rationale backfill worklists (MS-10-012, MS-10-013, MS-10-015): "
            "requirements with no rationale, rationales that may narrate "
            "history, and candidate adr: links. Advisory: exits 0 whatever it "
            "finds, 2 on a usage error."
        ),
    )
    parser.add_argument(
        "report",
        choices=("missing", "adr-links", "history"),
        help="which worklist to print",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "keep only this spec file (specs/<name>.yaml or <name>.yaml); "
            "repeat for several"
        ),
    )
    args = parser.parse_args(argv)
    root = _find_repo_root()
    try:
        lines = report_lines(args.report, root, _normalize_files(args.file))
    except ValueError as exc:
        parser.error(str(exc))
    for line in lines:
        print(line)
    print(f"[INFO] {len(lines)} item(s) in the {args.report} report")


if __name__ == "__main__":
    main()


__all__ = [
    "AdrLinkCandidate",
    "HISTORY_PATTERNS",
    "HistoryHit",
    "adr_link_candidates",
    "history_labels",
    "history_narration_hits",
    "live_adr_bodies",
    "load_with_files",
    "main",
    "missing_rationale",
    "missing_rationale_ids",
    "report_lines",
]
