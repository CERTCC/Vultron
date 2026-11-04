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


def _check_retirement_rules(
    registry: SpecRegistry, repo_root: Path
) -> list[str]:
    """Refuse a re-declared retired requirement ID (MS-09-004).

    An ID in ``plan/retired-specs/`` is never declared again. The other
    retirement rule, no ``deprecated:`` or ``superseded_by:`` key in place
    (MS-09-001), is enforced at load time by the ``SpecGroup.specs``
    validator, so a registry that reaches this check cannot carry either key.
    """
    retired = retired_spec_ids(repo_root)
    return [
        f"Spec '{spec_id}' is declared in specs/ but is in the "
        f"retired archive plan/retired-specs/; a requirement ID is "
        f"never reused, so give the new rule a new ID (MS-09-004)"
        for spec_id in registry.all_specs
        if spec_id in retired
    ]


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
