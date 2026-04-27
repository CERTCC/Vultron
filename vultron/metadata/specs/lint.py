"""Spec registry linter.

Linter requirements: specs/spec-registry.md SR-04.

Usage::

    python -m vultron.metadata.specs.lint specs/
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import BehavioralSpec, LintWarningCode

_RATIONALE_WARN_CHARS = 500


def _check_prefix_consistency(registry: SpecRegistry) -> list[str]:
    """Verify each group ID prefix matches its containing file prefix
    (SR-01-007)."""
    errors: list[str] = []
    for spec_file in registry.files:
        file_prefix = spec_file.id
        for group in spec_file.groups:
            group_prefix = group.id.split("-")[0]
            if group_prefix != file_prefix:
                errors.append(
                    f"Group '{group.id}' prefix '{group_prefix}' does not "
                    f"match file prefix '{file_prefix}'"
                )
    return errors


def lint(spec_dir: Path) -> int:
    """Validate the spec registry in ``spec_dir``.

    Hard errors cause exit code 1.  Advisory warnings are printed but do not
    affect the exit code (SR-04-001, SR-04-002).

    Args:
        spec_dir: Directory containing ``*.yaml`` spec files.

    Returns:
        ``0`` if no hard errors, ``1`` if any hard errors found.
    """
    hard_errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = load_registry(spec_dir)
    except (ValidationError, ValueError) as exc:
        print(f"[FATAL] Registry load failed:\n{exc}", file=sys.stderr)
        return 1

    hard_errors.extend(registry.validate_cross_references())
    hard_errors.extend(_check_prefix_consistency(registry))

    for spec_id, spec in registry.all_specs.items():
        suppressed = set(spec.lint_suppress)

        is_behavioral = isinstance(spec, BehavioralSpec) and bool(spec.steps)

        if (
            not spec.testable
            and not is_behavioral
            and LintWarningCode.TESTABLE_WITHOUT_STEPS not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: testable=false but no behavioral steps "
                f"(suppress with lint_suppress: [testable_without_steps])"
            )

        if (
            len(spec.rationale) > _RATIONALE_WARN_CHARS
            and LintWarningCode.RATIONALE_TOO_LONG not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: rationale exceeds "
                f"{_RATIONALE_WARN_CHARS} characters"
            )

        if not spec.tags and LintWarningCode.MISSING_TAGS not in suppressed:
            warnings.append(f"[WARN] {spec_id}: no tags defined")

    for w in warnings:
        print(w)
    for e in hard_errors:
        print(f"[ERROR] {e}", file=sys.stderr)

    return 0 if not hard_errors else 1


def main() -> None:
    """CLI entry point: ``python -m vultron.metadata.specs.lint specs/``
    (SR-04-003)."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <spec_dir>", file=sys.stderr)
        sys.exit(2)
    spec_dir = Path(sys.argv[1])
    sys.exit(lint(spec_dir))


if __name__ == "__main__":
    main()
