"""The spec linter's ``lint()`` driver and command-line entry point
(SR-04-003).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.specs.branch_checks import check_branch
from vultron.metadata.specs.growth_guard import BaseUnavailableError
from vultron.metadata.specs.kind_classification import (
    check_foundation_standard_tags,
    check_implementer_kind_code_references,
    suppression_status_lines,
)
from vultron.metadata.specs.lint.adr_refs import (
    _check_adr_references,
    _check_adr_status,
)
from vultron.metadata.specs.lint.advisories import (
    _check_missing_story_references,
    _check_per_spec_advisory_warnings,
    _check_project_process_story_advisory,
)
from vultron.metadata.specs.lint.phantom_paths import _check_phantom_paths
from vultron.metadata.specs.lint.phantom_symbols import (
    _check_phantom_spec_id_citations,
    _check_phantom_symbols,
    _SourceScan,
)
from vultron.metadata.specs.lint.structure import (
    _check_missing_kind,
    _check_prefix_consistency,
    _check_retirement_rules,
    _check_scenario_start_groups,
    _check_spec_id_prefix_consistency,
)
from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
)
from vultron.metadata.specs.relation_graph import (
    check_both_ends_recorded,
    check_relationship_loops,
)
from vultron.metadata.specs.schema import SpecKind
from vultron.metadata.specs.statement_style import compound_listing
from vultron.metadata.specs.story_links import check_cited_story_pages
from vultron.metadata.specs.verification import (
    VERIFICATION_DEBT_OWNERS,
    check_closing_pr,
    check_verification_coverage,
    closed_debt_owners,
    debt_owner_refs,
)
from vultron.metadata.specs.verification_refs import (
    SuiteIndex,
    check_test_refs,
)


def _report_closed_debt_owners(
    registry: SpecRegistry, debt_owners: Mapping[SpecKind, frozenset[str]]
) -> int:
    """Print each closed or unreadable owner as an error; return the exit code."""
    errors = closed_debt_owners(debt_owner_refs(registry, debt_owners))
    for e in errors:
        print(f"[ERROR] {e}", file=sys.stderr)
    return 1 if errors else 0


def _opt_in_checks(
    registry: SpecRegistry,
    repo_root: Path,
    debt_owners: Mapping[SpecKind, frozenset[str]],
    closing_pr: int | None,
    changed_since: str | None,
    index: SuiteIndex,
) -> tuple[list[str], list[str]]:
    """Hard errors and warnings from the checks a CLI flag turns on."""
    errors: list[str] = []
    warnings: list[str] = []
    if closing_pr is not None:
        errors.extend(check_closing_pr(registry, debt_owners, closing_pr))
    if changed_since is not None:
        branch = check_branch(registry, repo_root, changed_since, index)
        errors.extend(branch.errors)
        warnings.extend(branch.warnings)
    return errors, warnings


def _list_compound(registry: SpecRegistry, spec_dir: Path) -> int:
    """Print every compound requirement by spec file; always exit ``0``."""
    for line in compound_listing(registry, spec_dir):
        print(line)
    return 0


def lint(
    spec_dir: Path,
    adr_dir: Path | None = None,
    registry: SpecRegistry | None = None,
    *,
    list_unverified: bool = False,
    list_no_story_ids: bool = False,
    debt_owners: Mapping[SpecKind, frozenset[str]] | None = None,
    check_debt_owners: bool = False,
    closing_pr: int | None = None,
    changed_since: str | None = None,
    list_compound: bool = False,
) -> int:
    """Validate the spec registry in ``spec_dir``.

    Hard errors cause exit code 1.  Advisory warnings, and the per-kind
    verification-coverage status lines (MS-10-005), are printed but do not
    affect the exit code (SR-04-001, SR-04-002).

    Args:
        spec_dir: Directory containing ``*.yaml`` spec files.
        adr_dir: Directory containing ADR markdown files.  When ``None``
            (the default), falls back to ``spec_dir.parent / "docs" / "adr"``
            so that ``uv run spec-lint`` from the repository root picks up
            ``docs/adr/`` automatically.  To skip the ADR-reference check,
            pass a path that does not exist on disk.
        registry: Pre-loaded :class:`SpecRegistry` instance.  When provided,
            the ``load_registry(spec_dir)`` call is skipped, avoiding
            redundant I/O in callers that already hold a loaded registry.
        list_unverified: Print the ID and marker of every unverified
            MUST-tier requirement under its kind's summary line
            (MS-10-020; ``--list-unverified`` on the CLI).
        list_no_story_ids: Print the IDs of every project/process
            requirement with no ``stories:`` field under its file's
            summary line (SR-11-009; ``--list-no-story-ids`` on the CLI).
        debt_owners: The issues that own each kind's verification backlog.
            Defaults to the live
            :data:`~vultron.metadata.specs.verification.VERIFICATION_DEBT_OWNERS`;
            tests pass a fixture table.
        check_debt_owners: Run only the open-owner check: fail on any
            ``verification_debt`` marker or owner entry naming a closed issue
            (MS-10-024; ``--check-debt-owners`` on the CLI), and on nothing
            else, so an unrelated lint error cannot file the owners-closed
            tracking issue (ARCH-18-008). Needs the ``gh`` CLI and a token, so
            CI runs it and the pre-commit hook does not.
        closing_pr: Also fail when this pull request closes an owner issue
            that a marker or owner entry still names (MS-10-023;
            ``--check-closing-pr N`` on the CLI). Needs ``gh`` and a token.
        changed_since: Also run the branch-scoped checks against the merge
            base with this ref (``--changed-since REF`` on the CLI): the
            MS-10-027 marker check on each requirement the branch changed,
            the PD-10-002 limit on each spec YAML line it added, and the
            MS-03-007 statement check on each requirement whose statement it
            added or changed. See :mod:`vultron.metadata.specs.branch_checks`.
        list_compound: Run only the backlog listing: print every compound
            requirement in the corpus, grouped by spec file, and return ``0``
            (MS-03-001; ``--list-compound`` on the CLI).

    Returns:
        ``0`` if no hard errors, ``1`` if any hard errors found.

    Raises:
        BaseUnavailableError: *changed_since* names a ref that does not
            resolve; :func:`main` reports it with exit code ``2``.
    """
    if debt_owners is None:
        debt_owners = VERIFICATION_DEBT_OWNERS
    if adr_dir is None:
        adr_dir = spec_dir.parent / "docs" / "adr"

    hard_errors: list[str] = []
    warnings: list[str] = []
    status_lines: list[str] = []

    if registry is None:
        try:
            registry = load_registry(spec_dir)
        except (ValidationError, ValueError) as exc:
            print(f"[FATAL] Registry load failed:\n{exc}", file=sys.stderr)
            return 1

    if check_debt_owners:
        return _report_closed_debt_owners(registry, debt_owners)
    if list_compound:
        return _list_compound(registry, spec_dir)

    hard_errors.extend(registry.validate_cross_references())
    hard_errors.extend(check_relationship_loops(registry))
    hard_errors.extend(check_both_ends_recorded(registry))
    hard_errors.extend(_check_prefix_consistency(registry))
    hard_errors.extend(_check_spec_id_prefix_consistency(registry))
    hard_errors.extend(_check_scenario_start_groups(registry))
    hard_errors.extend(_check_retirement_rules(registry, spec_dir.parent))
    hard_errors.extend(_check_phantom_paths(registry, spec_dir.parent))
    suite_index = SuiteIndex.build(spec_dir.parent)
    hard_errors.extend(check_test_refs(registry, spec_dir.parent, suite_index))
    source_scan = _SourceScan(spec_dir.parent)
    hard_errors.extend(_check_phantom_spec_id_citations(registry, source_scan))
    hard_errors.extend(_check_phantom_symbols(registry, source_scan))
    hard_errors.extend(_check_missing_story_references(registry))
    hard_errors.extend(check_cited_story_pages(registry, spec_dir.parent))
    hard_errors.extend(check_implementer_kind_code_references(registry))
    hard_errors.extend(check_foundation_standard_tags(registry))

    warnings.extend(_check_per_spec_advisory_warnings(registry))
    verification_errors, verification_lines = check_verification_coverage(
        registry, debt_owners, list_unverified
    )
    hard_errors.extend(verification_errors)
    status_lines.extend(verification_lines)
    status_lines.extend(suppression_status_lines(registry))
    status_lines.extend(
        _check_project_process_story_advisory(
            registry, list_no_story_ids=list_no_story_ids
        )
    )
    opt_in_errors, opt_in_warnings = _opt_in_checks(
        registry,
        spec_dir.parent,
        debt_owners,
        closing_pr,
        changed_since,
        suite_index,
    )
    hard_errors.extend(opt_in_errors)
    warnings.extend(opt_in_warnings)

    adr_ref_errors, adr_ref_warnings = _check_adr_references(registry, adr_dir)
    hard_errors.extend(adr_ref_errors)
    warnings.extend(adr_ref_warnings)
    hard_errors.extend(_check_missing_kind(registry))
    adr_status_errors, adr_status_warnings = _check_adr_status(
        adr_dir, registry
    )
    hard_errors.extend(adr_status_errors)
    warnings.extend(adr_status_warnings)

    for w in warnings:
        print(w)
    for line in status_lines:
        print(line)
    for e in hard_errors:
        print(f"[ERROR] {e}", file=sys.stderr)

    return 0 if not hard_errors else 1


def main() -> None:
    """CLI entry point: ``uv run spec-lint`` or
    ``python -m vultron.metadata.specs.lint [spec_dir]`` (SR-04-003).

    ``spec_dir`` defaults to ``specs/`` relative to the current working
    directory so that ``uv run spec-lint`` from the repository root
    behaves identically to the pre-commit hook (SR-06-002, SR-04-010).
    """
    parser = argparse.ArgumentParser(
        prog="spec-lint", description="Validate the specs/*.yaml registry."
    )
    parser.add_argument(
        "spec_dir",
        nargs="?",
        default="specs",
        help="Directory containing spec YAML files (default: specs/)",
    )
    parser.add_argument(
        "--list-unverified",
        action="store_true",
        help=(
            "List the ID and verification_debt marker of every MUST or "
            "MUST_NOT requirement with no verification: field under its "
            "kind's summary line (MS-10-020)"
        ),
    )
    parser.add_argument(
        "--list-no-story-ids",
        action="store_true",
        help=(
            "List the IDs of every project/process requirement with no "
            "stories: field under its spec file's summary line (SR-11-009)"
        ),
    )
    parser.add_argument(
        "--check-debt-owners",
        action="store_true",
        help=(
            "Run only the owner check: fail when a verification_debt marker "
            "or owner entry names a closed issue (MS-10-024); needs the gh "
            "CLI and a token"
        ),
    )
    parser.add_argument(
        "--check-closing-pr",
        type=int,
        metavar="N",
        help=(
            "Fail when pull request N closes an owner issue that a "
            "verification_debt marker or owner entry still names "
            "(MS-10-023); needs the gh CLI and a token"
        ),
    )
    parser.add_argument(
        "--changed-since",
        metavar="REF",
        help=(
            "Also check what the branch changed since its merge base with "
            "REF: a protocol or foundation requirement it changed whose "
            "verification names test files carries its marker in one "
            "(MS-10-011), no spec YAML line it added is over 88 "
            "characters (PD-10-002), and each requirement whose statement it "
            "added or changed holds one RFC 2119 keyword, with a warning for "
            "a sentence over 25 words (MS-03-007). Exit 2 when REF does not "
            "resolve"
        ),
    )
    parser.add_argument(
        "--list-compound",
        action="store_true",
        help=(
            "Run only the backlog listing: print every requirement whose "
            "statement holds more than one RFC 2119 keyword, grouped by spec "
            "file (MS-03-001), and exit 0"
        ),
    )
    args = parser.parse_args()
    if args.list_compound and (
        args.changed_since is not None
        or args.check_closing_pr is not None
        or args.check_debt_owners
        or args.list_unverified
        or args.list_no_story_ids
    ):
        # --list-compound runs nothing else, so a combined check would pass
        # without having run.
        parser.error("--list-compound runs alone; drop the other flags")
    spec_dir = Path(args.spec_dir)
    if not spec_dir.is_dir():
        print(
            f"[FATAL] spec_dir '{spec_dir}' not found or not a directory",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        code = lint(
            spec_dir,
            list_unverified=args.list_unverified,
            list_no_story_ids=args.list_no_story_ids,
            check_debt_owners=args.check_debt_owners,
            closing_pr=args.check_closing_pr,
            changed_since=args.changed_since,
            list_compound=args.list_compound,
        )
    except BaseUnavailableError as exc:
        print(f"[FATAL] --changed-since: {exc}", file=sys.stderr)
        sys.exit(2)
    sys.exit(code)
