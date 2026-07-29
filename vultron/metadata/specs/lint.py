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
    TriggerType,
)

_RATIONALE_WARN_CHARS = 500
_ADR_REF_RE = re.compile(r"\bADR-(\d{4})\b")

# MS-14: valid ADR status values (ADR-0043). A retired ADR uses bare
# ``superseded`` with a separate ``superseded_by:`` frontmatter field (the
# project convention, see notes/notes-frontmatter.md); the inline MADR form
# ``superseded by <link>`` is also tolerated and matched by prefix below.
_ADR_VALID_STATUSES = frozenset(
    {
        "proposed",
        "accepted",
        "accepted-provisional",
        "deprecated",
        "rejected",
        "superseded",
    }
)
# MS-14-002: prose markers that mean the design is not yet validated. An ADR
# whose body contains any of these MUST NOT declare status: accepted.
_ADR_PROVISIONAL_MARKERS = (
    "formed in sand",
    "not concrete",
    "provisional",
    "forward-looking",
    "will converge",
    "expected to converge",
    "should refine this adr",
    "status will advance",
)
_ADR_STATUS_RE = re.compile(r"^status:\s*(.*?)\s*$", re.MULTILINE)


def _adr_status(text: str) -> str | None:
    """Extract the ``status:`` value from an ADR's YAML frontmatter.

    Returns the raw value (lower-cased, stripped) or ``None`` when there is no
    frontmatter status line at all.
    """
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    frontmatter = text[3:end]
    match = _ADR_STATUS_RE.search(frontmatter)
    if match is None:
        return None
    return match.group(1).strip().strip("{}").lower()


def _check_adr_status(
    adr_dir: Path | None,
) -> tuple[list[str], list[str]]:
    """Validate ADR status frontmatter (MS-14-001 hard, MS-14-002 advisory).

    Returns ``(hard_errors, warnings)``:

    - **Hard (MS-14-001)**: every ADR (excluding template, index, and
      ``archived/``) MUST declare a non-empty status whose value is one of the
      known values (a retired ADR uses ``superseded`` with a separate
      ``superseded_by:`` field, or the inline ``superseded by <link>`` form).
      This is mechanical and has no false positives.
    - **Advisory (MS-14-002)**: an ADR whose prose carries a provisional marker
      SHOULD NOT be ``status: accepted``. This is a heuristic substring scan and
      can false-positive (e.g. an ADR that *discusses* provisional-ness), so it
      surfaces candidates for the ``decision-audit`` skill to adjudicate rather
      than blocking CI.

    Degrades to empty lists when ``adr_dir`` is missing so the check is a no-op
    in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return [], []

    errors: list[str] = []
    warnings: list[str] = []
    for adr_path in sorted(adr_dir.glob("*.md")):
        name = adr_path.name
        if name == "index.md" or name.startswith("_"):
            continue

        text = adr_path.read_text(encoding="utf-8")
        status = _adr_status(text)

        if not status:
            errors.append(
                f"{name}: missing or empty 'status' frontmatter field "
                f"(MS-14-001; see ADR-0043)"
            )
            continue

        is_superseded_inline = status.startswith("superseded by")
        if status not in _ADR_VALID_STATUSES and not is_superseded_inline:
            errors.append(
                f"{name}: invalid status '{status}' (MS-14-001); expected one "
                f"of {sorted(_ADR_VALID_STATUSES)} (a retired ADR uses "
                f"'superseded' with a separate superseded_by: field, or the "
                f"inline 'superseded by <link>' form)"
            )
            continue

        if status == "accepted":
            body = text.lower()
            hit = next(
                (m for m in _ADR_PROVISIONAL_MARKERS if m in body), None
            )
            if hit is not None:
                warnings.append(
                    f"[WARN] {name}: status is 'accepted' but prose contains "
                    f"provisional marker '{hit}' (MS-14-002); if the design is "
                    f"genuinely unvalidated use 'accepted-provisional' — else "
                    f"this is a decision-audit candidate (see ADR-0043)"
                )
    return errors, warnings


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
) -> tuple[list[str], list[str]]:
    """Validate spec → ADR references (MS-11-004, SR-03-004).

    Returns ``(hard_errors, warnings)``:

    - **Hard**: a structured ``adr:`` field target with no matching ADR file
      (in ``adr_dir`` or ``adr_dir/archived``). The structured field is part of
      the traceability edges graph, so a dangling target silently breaks
      "dependents of ADR-NNNN" queries.
    - **Advisory**: a free-text ``rationale`` citation of an ADR that does not
      exist (legacy prose form; suppressible via ``lint_suppress``).

    Returns two empty lists when ``adr_dir`` is None or does not exist so the
    check degrades gracefully in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return [], []

    warnings: list[str] = []
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        # Structured adr: references are validated as HARD errors — the field is
        # part of the traceability graph, so a dangling target breaks
        # "dependents of ADR-NNNN" queries (MS-11-004, SR-03-004). Also search
        # both docs/adr/ and docs/adr/archived/ so pointing at a retired ADR is
        # still valid.
        for adr_id in spec.adr or []:
            adr_number = adr_id.split("-", 1)[1]
            if not _adr_exists(adr_dir, adr_number) and not _adr_exists(
                adr_dir / "archived", adr_number
            ):
                errors.append(
                    f"{spec_id}: adr reference '{adr_id}' has no matching "
                    f"ADR file in '{adr_dir}' or '{adr_dir / 'archived'}'"
                )

        # Free-text rationale ADR citations remain advisory (legacy prose form).
        suppressed = set(spec.lint_suppress or [])
        if LintWarningCode.DANGLING_ADR_REF in suppressed:
            continue
        seen = set(_ADR_REF_RE.findall(spec.rationale or ""))
        for adr_number in seen:
            if not _adr_exists(adr_dir, adr_number) and not _adr_exists(
                adr_dir / "archived", adr_number
            ):
                warnings.append(
                    f"[WARN] {spec_id}: rationale references "
                    f"ADR-{adr_number} but no matching file found in "
                    f"'{adr_dir}' "
                    f"(suppress with lint_suppress: [dangling_adr_ref])"
                )
    return errors, warnings


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


def _check_scenario_start_groups(registry: SpecRegistry) -> list[str]:
    """Hard error when a scenario_start group has no BehavioralSpec with steps.

    Enforces MS-13-004: mixed groups are permitted, but at least one item must
    be a BehavioralSpec with a non-empty steps list.
    """
    errors: list[str] = []
    for spec_file in registry.files:
        for group in spec_file.groups:
            if (
                group.trigger is None
                or group.trigger.type != TriggerType.SCENARIO_START
            ):
                continue
            has_eca = any(
                isinstance(spec, BehavioralSpec) and bool(spec.steps)
                for spec in group.specs
            )
            if not has_eca:
                errors.append(
                    f"Group '{group.id}' has trigger type scenario_start but "
                    f"contains no BehavioralSpec item with steps (MS-13-004)"
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
    hard_errors.extend(_check_scenario_start_groups(registry))

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

    adr_ref_errors, adr_ref_warnings = _check_adr_references(registry, adr_dir)
    hard_errors.extend(adr_ref_errors)
    warnings.extend(adr_ref_warnings)
    hard_errors.extend(_check_missing_kind(registry))
    adr_status_errors, adr_status_warnings = _check_adr_status(adr_dir)
    hard_errors.extend(adr_status_errors)
    warnings.extend(adr_status_warnings)

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
