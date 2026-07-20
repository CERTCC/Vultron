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

import collections

from vultron.metadata.specs.registry import (
    SpecRegistry,
    effective_kind,
    load_registry,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    LintWarningCode,
    SpecKind,
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


def _majority_kind(kinds: list[SpecKind]) -> SpecKind | None:
    """Return the most common kind in *kinds*, or ``None`` if empty."""
    if not kinds:
        return None
    counter: collections.Counter[SpecKind] = collections.Counter(kinds)
    return counter.most_common(1)[0][0]


def _check_kind_drift(registry: SpecRegistry) -> list[str]:
    """Emit advisory warnings when declared kind diverges from majority kind
    of children (SR-09-003, SR-09-004).

    - Group-level ``kind`` SHOULD match the majority effective kind of its
      items.
    - File-level ``kind`` SHOULD match the majority effective group kind.

    The check is suppressible via ``lint_suppress: [kind_drift]`` on any
    spec item inside the affected group or file — because neither groups nor
    files have a ``lint_suppress`` field, suppression is evaluated per-spec
    to allow targeted opt-outs.
    """
    warnings: list[str] = []
    for spec_file in registry.files:
        group_majority_kinds: list[SpecKind] = []
        for group in spec_file.groups:
            item_kinds = [
                effective_kind(spec, group, spec_file) for spec in group.specs
            ]
            majority = _majority_kind(item_kinds)
            if majority is None:
                continue
            group_majority_kinds.append(majority)
            # Check group-level kind against majority of its items.
            group_effective = (
                group.kind if group.kind is not None else spec_file.kind
            )
            if group_effective != majority:
                # Suppress if any spec in the group has kind_drift suppressed.
                suppressed = any(
                    LintWarningCode.KIND_DRIFT in (spec.lint_suppress or [])
                    for spec in group.specs
                )
                if not suppressed:
                    warnings.append(
                        f"[WARN] {group.id}: group kind={group_effective.value!r} "
                        f"does not match majority item kind={majority.value!r} "
                        f"(suppress with lint_suppress: [kind_drift])"
                    )
        # Check file-level kind against majority of group majority kinds.
        file_majority = _majority_kind(group_majority_kinds)
        if file_majority is not None and spec_file.kind != file_majority:
            suppressed = any(
                LintWarningCode.KIND_DRIFT in (spec.lint_suppress or [])
                for group in spec_file.groups
                for spec in group.specs
            )
            if not suppressed:
                warnings.append(
                    f"[WARN] {spec_file.id}: file kind={spec_file.kind.value!r} "
                    f"does not match majority group kind={file_majority.value!r} "
                    f"(suppress with lint_suppress: [kind_drift])"
                )
    return warnings


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
    warnings.extend(_check_kind_drift(registry))

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
