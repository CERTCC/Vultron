"""Spec registry linter.

Linter requirements: specs/spec-registry.yaml SR-04.

Usage::

    python -m vultron.metadata.specs.lint specs/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    LintWarningCode,
)

_RATIONALE_WARN_CHARS = 500
_ADR_REF_RE = re.compile(r"\bADR-(\d{4})\b")


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


def _check_spec_id_prefix_consistency(registry: SpecRegistry) -> list[str]:
    """Verify each spec ID prefix matches the group it lives in (MS-04-004).

    A spec with ID ``HP-07-002`` MUST reside in group ``HP-07``.
    """
    errors: list[str] = []
    for spec_file in registry.files:
        for group in spec_file.groups:
            expected_prefix = group.id + "-"
            for spec in group.specs:
                if not spec.id.startswith(expected_prefix):
                    errors.append(
                        f"Spec '{spec.id}' does not belong in group "
                        f"'{group.id}' (expected prefix '{expected_prefix}')"
                    )
    return errors


def _adr_exists(adr_dir: Path, adr_number: str) -> bool:
    """Return True if an ADR file for ``adr_number`` exists in ``adr_dir``.

    ADR files follow the naming convention ``NNNN-<slug>.md``, so
    ``ADR-0009`` resolves to any file matching ``0009-*.md``.
    """
    return any(adr_dir.glob(f"{adr_number}-*.md"))


def _check_adr_references(
    registry: SpecRegistry, adr_dir: Path | None
) -> list[str]:
    """Emit advisory warnings for spec rationale fields that cite an ADR that
    does not exist in ``adr_dir`` (MS-11-004).

    Returns an empty list when ``adr_dir`` is None or does not exist so that
    the check degrades gracefully in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return []

    warnings: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        suppressed = set(spec.lint_suppress or [])
        if LintWarningCode.DANGLING_ADR_REF in suppressed:
            continue
        seen = set(_ADR_REF_RE.findall(spec.rationale or ""))
        for adr_number in seen:
            if not _adr_exists(adr_dir, adr_number):
                warnings.append(
                    f"[WARN] {spec_id}: rationale references "
                    f"ADR-{adr_number} but no matching file found in "
                    f"'{adr_dir}' "
                    f"(suppress with lint_suppress: [dangling_adr_ref])"
                )
    return warnings


def _check_missing_kind(registry: SpecRegistry) -> list[str]:
    """Return hard errors for any spec item missing a ``kind:`` field (SR-09-003).

    Pydantic already rejects ``kind: null`` at load time via the required
    ``SpecKind`` field type, so this check is belt-and-suspenders for future
    schema relaxations or registry manipulation outside the Pydantic validator.
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if spec.kind is None:
            errors.append(
                f"{spec_id}: missing required 'kind' field on spec item"
            )
    return errors


def lint(spec_dir: Path, adr_dir: Path | None = None) -> int:
    """Validate the spec registry in ``spec_dir``.

    Hard errors cause exit code 1.  Advisory warnings are printed but do not
    affect the exit code (SR-04-001, SR-04-002).

    Args:
        spec_dir: Directory containing ``*.yaml`` spec files.
        adr_dir: Directory containing ADR markdown files.  When ``None``
            (the default), falls back to ``spec_dir.parent / "docs" / "adr"``
            so that ``uv run spec-lint`` from the repository root picks up
            ``docs/adr/`` automatically.  To skip the ADR-reference check,
            pass a path that does not exist on disk.

    Returns:
        ``0`` if no hard errors, ``1`` if any hard errors found.
    """
    if adr_dir is None:
        adr_dir = spec_dir.parent / "docs" / "adr"

    hard_errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = load_registry(spec_dir)
    except (ValidationError, ValueError) as exc:
        print(f"[FATAL] Registry load failed:\n{exc}", file=sys.stderr)
        return 1

    hard_errors.extend(registry.validate_cross_references())
    hard_errors.extend(_check_prefix_consistency(registry))
    hard_errors.extend(_check_spec_id_prefix_consistency(registry))

    for spec_id, spec in registry.all_specs.items():
        suppressed = set(spec.lint_suppress or [])

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
            spec.rationale
            and len(spec.rationale) > _RATIONALE_WARN_CHARS
            and LintWarningCode.RATIONALE_TOO_LONG not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: rationale exceeds "
                f"{_RATIONALE_WARN_CHARS} characters"
            )

        tags = registry.get_effective_tags(spec_id)
        if not tags and LintWarningCode.MISSING_TAGS not in suppressed:
            warnings.append(f"[WARN] {spec_id}: no tags defined")

    warnings.extend(_check_adr_references(registry, adr_dir))
    hard_errors.extend(_check_missing_kind(registry))

    for w in warnings:
        print(w)
    for e in hard_errors:
        print(f"[ERROR] {e}", file=sys.stderr)

    return 0 if not hard_errors else 1


def main() -> None:
    """CLI entry point: ``uv run spec-lint`` or
    ``python -m vultron.metadata.specs.lint [spec_dir]`` (SR-04-003).

    ``spec_dir`` defaults to ``specs/`` relative to the current working
    directory so that ``uv run spec-lint`` from the repository root
    behaves identically to the pre-commit hook.
    """
    spec_dir = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path("specs")
    if not spec_dir.is_dir():
        print(
            f"[FATAL] spec_dir '{spec_dir}' not found or not a directory",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(lint(spec_dir))


if __name__ == "__main__":
    main()
