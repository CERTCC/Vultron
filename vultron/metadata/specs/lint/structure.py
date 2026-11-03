"""Structural spec-registry checks: id prefixes, lifecycle fields, ``kind`` and
scenario-start groups (SR-04).
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.retire import retired_spec_ids
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    TriggerType,
)


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


_LIFECYCLE_KEYS = ("deprecated", "superseded_by")


def _check_retirement_rules(
    registry: SpecRegistry, repo_root: Path
) -> list[str]:
    """Enforce the retirement rules (MS-09-001, MS-09-004).

    A requirement that is no longer current is removed and archived in
    ``plan/retired-specs/``, never marked ``deprecated:`` or
    ``superseded_by:`` in place, and an ID in the archive is never declared
    again.
    """
    errors: list[str] = []
    retired = retired_spec_ids(repo_root)
    for spec_id, spec in registry.all_specs.items():
        for key in _LIFECYCLE_KEYS:
            if key in spec.model_fields_set:
                errors.append(
                    f"Spec '{spec_id}' carries '{key}:'; remove the "
                    f"requirement and archive it with `uv run spec-retire "
                    f"{spec_id}` instead (MS-09-001)"
                )
        if spec_id in retired:
            errors.append(
                f"Spec '{spec_id}' is declared in specs/ but is in the "
                f"retired archive plan/retired-specs/; a requirement ID is "
                f"never reused, so give the new rule a new ID (MS-09-004)"
            )
    return errors


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
