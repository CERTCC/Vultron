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
"""Protocol-tier @pytest.mark.spec coverage reporter.

Scans the test suite for ``@pytest.mark.spec("ID")`` markers and reports, for
the requirements every implementation must obey — ``protocol`` and
``foundation`` kind (:data:`~vultron.metadata.specs.schema.IMPLEMENTER_KINDS`)
— which of three states each one is in (SR-05-017):

* **verified** — at least one marked test runs to pass or fail;
* **xfail-only** — it has marked tests, and each one is held: a strict
  ``xfail`` (conditional or not) is on it, or it cannot run (an unconditional
  ``skip``, an empty parameter list), so no passing test shows that ``main``
  meets it;
* **untested** — no marker names it.

The coverage figure is verified over total. ``--json PATH`` writes each
requirement's state, statement and xfail reasons (SR-05-018).

Runnable locally::

    spec-coverage
    spec-coverage specs/ test/
    spec-coverage --json /tmp/spec-coverage.json

Coverage reporter requirements: specs/spec-registry.yaml SR-05-004,
SR-05-005, SR-05-017, SR-05-018.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field

from vultron.metadata.specs.marked_tests import (
    MarkedCase,
    issue_refs,
    marked_spec_ids,
    read_marked_file,
)
from vultron.metadata.specs.registry import (
    SpecRegistry,
    find_repo_root,
    load_registry,
)
from vultron.metadata.specs.schema import IMPLEMENTER_KINDS, Spec, SpecKind


class CoverageState(StrEnum):
    """What the test suite shows about one implementer-kind requirement."""

    VERIFIED = "verified"
    """A marked test runs to pass or fail."""
    XFAIL_ONLY = "xfail_only"
    """Every marked test is held by a strict ``xfail`` or cannot run."""
    UNTESTED = "untested"
    """No marker names the requirement."""


class XfailTest(BaseModel):
    """One strict ``xfail``, or skip, that holds a test marked for a requirement.

    A skip's reason starts with ``skip:``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    test: str
    """``path::Class::function``, followed by ``[ids]`` when every parameter
    set of the case has a literal ``id=``."""
    reason: str | None
    """The marker's ``reason``; ``None`` when it is not a resolvable string."""
    issues: tuple[int, ...]
    """The issue numbers *reason* cites as ``#N``."""


class RequirementCoverage(BaseModel):
    """One implementer-kind requirement and its coverage state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: SpecKind
    statement: str
    state: CoverageState
    xfail_tests: tuple[XfailTest, ...] = ()
    """Each strict ``xfail`` or skip on a test marked for this requirement, in
    any state: a verified requirement can also have an xfail-marked test."""


class CoverageSummary(BaseModel):
    """The counts of each coverage state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int
    verified: int
    xfail_only: int
    untested: int
    verified_pct: float
    """Verified over total, as a percentage (0–100); 0.0 when total is 0."""


class ImplementerCoverageReport(BaseModel):
    """Coverage of ``protocol`` and ``foundation`` requirements by state.

    Serialized by ``spec-coverage --json``: ``requirements`` lists every
    implementer-kind requirement sorted by ID, and ``summary`` gives the
    counts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirements: tuple[RequirementCoverage, ...]

    def _ids(self, state: CoverageState) -> list[str]:
        return [r.id for r in self.requirements if r.state is state]

    @property
    def total(self) -> int:
        """Number of implementer-kind requirements."""
        return len(self.requirements)

    @property
    def verified(self) -> list[str]:
        """Marked IDs that are not xfail-only, sorted."""
        return self._ids(CoverageState.VERIFIED)

    @property
    def xfail_only(self) -> list[str]:
        """IDs whose every marked test is held, sorted."""
        return self._ids(CoverageState.XFAIL_ONLY)

    @property
    def untested(self) -> list[str]:
        """IDs no marker names, sorted."""
        return self._ids(CoverageState.UNTESTED)

    @property
    def verified_pct(self) -> float:
        """Percentage of implementer-kind requirements verified (0–100)."""
        if self.total == 0:
            return 0.0
        return 100.0 * len(self.verified) / self.total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> CoverageSummary:
        """The counts of each state, written with the requirements."""
        return CoverageSummary(
            total=self.total,
            verified=len(self.verified),
            xfail_only=len(self.xfail_only),
            untested=len(self.untested),
            verified_pct=self.verified_pct,
        )


def marked_ids_in(sources: Iterable[str]) -> frozenset[str]:
    """Spec IDs referenced by ``@pytest.mark.spec`` markers in *sources*.

    Each item of *sources* is one file's text, read by
    :func:`~vultron.metadata.specs.marked_tests.marked_spec_ids`: every
    ``mark.spec`` call counts, wherever it is, and marker text inside a string
    literal does not. A marker naming several IDs,
    ``@pytest.mark.spec("A", "B")``, covers each of them; a keyword argument
    is not an ID.

    This set alone decides *untested*, so the SR-05-005 growth guard and the
    report agree on it; :mod:`~vultron.metadata.specs.marked_tests` only
    splits the marked IDs into verified and xfail-only.
    """
    return frozenset().union(*(marked_spec_ids(source) for source in sources))


def _read_files(test_root: Path) -> Iterator[tuple[Path, str]]:
    for py_file in sorted(test_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        try:
            yield py_file, py_file.read_text(encoding="utf-8")
        except OSError:
            continue


def _read_sources(test_root: Path) -> Iterator[str]:
    return (source for _, source in _read_files(test_root))


def collect_marked_ids(test_root: Path) -> frozenset[str]:
    """Scan ``*.py`` files under *test_root* and return referenced spec IDs.

    Reads each file as :func:`marked_ids_in` does.

    Args:
        test_root: Directory to scan recursively for ``*.py`` files.

    Returns:
        Frozen set of all spec ID strings referenced by ``@pytest.mark.spec``
        markers found under *test_root*.
    """
    return marked_ids_in(_read_sources(test_root))


def _implementer_specs(registry: SpecRegistry) -> dict[str, Spec]:
    return {
        spec_id: spec
        for spec_id, spec in registry.all_specs.items()
        if spec.kind in IMPLEMENTER_KINDS
    }


def _state(
    spec_id: str, marked_ids: frozenset[str], cases: list[MarkedCase]
) -> CoverageState:
    if spec_id not in marked_ids:
        return CoverageState.UNTESTED
    if cases and all(case.is_xfail for case in cases):
        return CoverageState.XFAIL_ONLY
    return CoverageState.VERIFIED


def _xfail_tests(cases: Iterable[MarkedCase]) -> tuple[XfailTest, ...]:
    found = {
        (case.test, reason) for case in cases for reason in case.xfail_reasons
    }
    return tuple(
        XfailTest(test=test, reason=reason, issues=issue_refs(reason))
        for test, reason in sorted(
            found, key=lambda t: (t[0], t[1] is not None, t[1] or "")
        )
    )


def classify_requirements(
    registry: SpecRegistry,
    marked_ids: frozenset[str],
    cases: Iterable[MarkedCase],
) -> ImplementerCoverageReport:
    """Put each implementer-kind requirement in its coverage state.

    Args:
        registry: The requirements to classify.
        marked_ids: IDs any marker names (:func:`marked_ids_in`); an ID
            outside it is untested.
        cases: The marked test cases
            (:func:`~vultron.metadata.specs.marked_tests.marked_cases_in`).
            A marked ID is xfail-only when it has cases and each one is
            held; otherwise it is verified. A marked ID with no case (its
            call sits where the case reader does not look) counts as
            verified.
    """
    by_id: dict[str, list[MarkedCase]] = {}
    for case in cases:
        for spec_id in case.spec_ids:
            by_id.setdefault(spec_id, []).append(case)
    return ImplementerCoverageReport(
        requirements=tuple(
            RequirementCoverage(
                id=spec_id,
                kind=spec.kind,
                statement=spec.statement,
                state=_state(spec_id, marked_ids, by_id.get(spec_id, [])),
                xfail_tests=_xfail_tests(by_id.get(spec_id, [])),
            )
            for spec_id, spec in sorted(_implementer_specs(registry).items())
        )
    )


def compute_implementer_coverage(
    registry: SpecRegistry,
    test_root: Path,
) -> ImplementerCoverageReport:
    """Compute @pytest.mark.spec coverage for implementer-kind requirements.

    Args:
        registry: Loaded :class:`~vultron.metadata.specs.registry.SpecRegistry`.
        test_root: Directory to scan for test files. Tests are named by their
            path relative to its parent, so ``test/`` gives ``test/...``.

    Returns:
        :class:`ImplementerCoverageReport` with every ``protocol`` and
        ``foundation`` requirement in its :class:`CoverageState`.
    """
    base = test_root.resolve().parent
    marked = [
        read_marked_file(path.resolve().relative_to(base).as_posix(), source)
        for path, source in _read_files(test_root)
    ]
    return classify_requirements(
        registry,
        frozenset().union(*(file.spec_ids for file in marked)),
        [case for file in marked for case in file.cases],
    )


def uncovered_implementer_ids(
    repo_root: Path, *, test_sources: Iterable[str] | None = None
) -> frozenset[str]:
    """``protocol`` and ``foundation`` IDs under *repo_root* no marker covers.

    The untested set of :class:`ImplementerCoverageReport`, and the per-item
    extractor behind the SR-05-005 growth guard
    (:func:`vultron.metadata.specs.growth_guard.added_since_base`): it reads
    ``specs/`` and ``test/`` under *repo_root*, so the same function runs on
    the working tree and on a materialized base tree. An xfail-only
    requirement has a marker, so it is not in this set.

    Args:
        repo_root: Tree holding ``specs/`` (and ``test/`` unless
            *test_sources* is given).
        test_sources: Test file texts already in memory, used instead of
            reading ``test/`` — the architecture suite passes its shared
            ``test/architecture/_corpus.py`` sources here.
    """
    if test_sources is None:
        test_sources = _read_sources(repo_root / "test")
    implementer = _implementer_specs(load_registry(repo_root / "specs"))
    return frozenset(implementer) - marked_ids_in(test_sources)


@dataclass(frozen=True)
class KindAndMarker:
    """One spec ID's kind, and whether any test marker covers it."""

    kind: SpecKind
    marked: bool


def kinds_and_markers(
    repo_root: Path, *, test_sources: Iterable[str] | None = None
) -> dict[str, KindAndMarker]:
    """Every spec ID under *repo_root* with its kind and marker state.

    The reader behind the MS-12-011 kind-change guard, run on the working tree
    and on a materialized base tree by
    :func:`vultron.metadata.specs.growth_guard.compare_with_base`. Arguments
    are as :func:`uncovered_implementer_ids` documents.
    """
    if test_sources is None:
        test_sources = _read_sources(repo_root / "test")
    marked = marked_ids_in(test_sources)
    registry = load_registry(repo_root / "specs")
    return {
        spec_id: KindAndMarker(spec.kind, spec_id in marked)
        for spec_id, spec in registry.all_specs.items()
    }


def markers_dropped_by_kind_change(
    base: Mapping[str, KindAndMarker], head: Mapping[str, KindAndMarker]
) -> frozenset[str]:
    """IDs that changed kind and lost the marker they had at *base* (MS-12-011).

    Whatever the destination kind, a kind change keeps the tests that already
    verify the spec. An ID retired at *head* is not reported: retirement is not
    a kind change.
    """
    return frozenset(
        spec_id
        for spec_id, was in base.items()
        if was.marked
        and (now := head.get(spec_id)) is not None
        and now.kind != was.kind
        and not now.marked
    )


def format_report(report: ImplementerCoverageReport) -> str:
    """The text ``spec-coverage`` prints: the three counts, then the IDs.

    Each xfail-only ID is followed by the reasons of the xfails that hold it,
    and each untested ID is listed alone.
    """
    summary = report.summary
    lines = [
        f"Protocol and foundation spec coverage: "
        f"{summary.verified}/{summary.total} verified ({summary.verified_pct:.1f}%)",
        f"  verified:   {summary.verified}",
        f"  xfail-only: {summary.xfail_only}",
        f"  untested:   {summary.untested}",
    ]
    xfail_only = [
        r for r in report.requirements if r.state is CoverageState.XFAIL_ONLY
    ]
    if xfail_only:
        lines += [
            "",
            "xfail-only protocol and foundation requirements "
            f"({len(xfail_only)}):",
        ]
        for requirement in xfail_only:
            lines.append(f"  {requirement.id}")
            reasons = dict.fromkeys(
                t.reason or "(no reason)" for t in requirement.xfail_tests
            )
            lines += [f"      {reason}" for reason in reasons]
    if report.untested:
        lines += [
            "",
            "Untested protocol and foundation requirements "
            f"({len(report.untested)}):",
            *(f"  {spec_id}" for spec_id in report.untested),
        ]
    return "\n".join(lines)


def write_json(report: ImplementerCoverageReport, path: Path) -> None:
    """Write *report* to *path* as indented JSON (SR-05-018).

    The output holds no clock or path outside the test tree, so the same
    tree always writes the same bytes.
    """
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """CLI entry point: print each implementer-kind requirement's state."""
    parser = argparse.ArgumentParser(
        description=(
            "Report which protocol- and foundation-kind requirements a passing "
            "@pytest.mark.spec test verifies, which only a strict xfail "
            "checks, and which no marker names."
        )
    )
    parser.add_argument(
        "spec_dir",
        nargs="?",
        default=None,
        help="Directory containing spec YAML files (default: auto-detect specs/)",
    )
    parser.add_argument(
        "test_dir",
        nargs="?",
        default=None,
        help="Directory containing test files (default: test/ at repo root)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        metavar="PATH",
        help="Also write each requirement's state and xfail reasons to PATH",
    )
    args = parser.parse_args()

    spec_dir = Path(args.spec_dir) if args.spec_dir else None
    registry = load_registry(spec_dir)

    if args.test_dir:
        test_root = Path(args.test_dir)
    else:
        test_root = find_repo_root() / "test"

    report = compute_implementer_coverage(registry, test_root)
    print(format_report(report))
    if args.json is not None:
        write_json(report, args.json)


if __name__ == "__main__":  # pragma: no cover
    main()
