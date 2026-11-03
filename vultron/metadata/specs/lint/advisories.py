"""Story traceability gate (SR-11-003), per-spec advisory warnings
(SR-04-002) and the per-file project/process story advisory (SR-11-009).
"""

from __future__ import annotations

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    LintWarningCode,
    RFC2119Priority,
    SpecKind,
)

_RATIONALE_WARN_CHARS = 500


def sr_11_003_gate_applies(kind: SpecKind, priority: RFC2119Priority) -> bool:
    """Whether SR-11-003's story gate covers a requirement of this kind and priority.

    SR-11-003 is the one recorded exception to MS-02-003: it is deliberately
    ``MUST``-only, not MUST-tier, because the protocol ``MUST_NOT``s with no
    ``stories:`` still await their stories (#3601 adjudicated them; #2717
    holds the list) and the gate extends to them as #2717's closing step once
    their stories exist — see the spec's
    ``note:``. This is the only place that decision is written down, so the
    exception cannot drift into a second hand-written copy. When it is
    retired, replace the member comparison with ``priority.is_must_tier`` and
    drop the matching allowlist entry in
    ``test/metadata/specs/test_priority_tier_gate.py``.
    """
    return (
        kind == SpecKind.PROTOCOL
        and priority
        == RFC2119Priority.MUST  # SR-11-003: MUST-only, see docstring
    )


def _check_missing_story_references(registry: SpecRegistry) -> list[str]:
    """Hard error when a ``kind: protocol`` MUST spec has no ``stories:`` (SR-11-003).

    Protocol MUST specs define wire-level compliance invariants.  A MUST with no
    user-story back-reference breaks the bidirectional traceability graph and is
    treated as a hard gate (exit 1).  Suppressible via
    ``lint_suppress: [missing_story_reference]`` for specs that are genuinely
    not traceable to any story. The gate's scope is
    :func:`sr_11_003_gate_applies`.
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if not sr_11_003_gate_applies(spec.kind, spec.priority):
            continue
        if spec.stories:
            continue
        suppressed = set(spec.lint_suppress or [])
        if LintWarningCode.MISSING_STORY_REFERENCE in suppressed:
            continue
        errors.append(
            f"{spec_id}: kind=protocol, priority=MUST but has no stories: "
            f"field (SR-11-003); add user-story back-references, or suppress "
            f"with lint_suppress: [missing_story_reference]"
        )
    return errors


def _check_per_spec_advisory_warnings(registry: SpecRegistry) -> list[str]:
    """Collect per-spec advisory warnings (SR-04-002).

    Covers: testable_without_steps, rationale_too_long, missing_tags, and
    missing_story_reference for every ``kind: protocol`` requirement below the
    MUST tier (SR-11-004 — SHOULD, SHOULD_NOT and MAY). All are suppressible
    via ``lint_suppress``. Unverified MUST-tier requirements are checked per
    item, against their ``verification_debt`` markers, by
    :func:`~vultron.metadata.specs.verification.check_verification_coverage`
    (MS-10-006, MS-10-022).
    """
    warnings: list[str] = []
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
            len(spec.rationale) > _RATIONALE_WARN_CHARS
            and LintWarningCode.RATIONALE_TOO_LONG not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: rationale exceeds "
                f"{_RATIONALE_WARN_CHARS} characters"
            )

        tags = registry.get_effective_tags(spec_id)
        if not tags and LintWarningCode.MISSING_TAGS not in suppressed:
            warnings.append(f"[WARN] {spec_id}: no tags defined")

        if (
            spec.kind == SpecKind.PROTOCOL
            and not spec.priority.is_must_tier
            and not spec.stories
            and LintWarningCode.MISSING_STORY_REFERENCE not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: kind=protocol, priority={spec.priority} "
                f"but has no stories: field (SR-11-004); consider adding "
                f"user-story back-references, or suppress with "
                f"lint_suppress: [missing_story_reference]"
            )

    return warnings


_PROJECT_PROCESS_KINDS = frozenset({SpecKind.PROJECT, SpecKind.PROCESS})


def _check_project_process_story_advisory(
    registry: SpecRegistry,
    *,
    list_no_story_ids: bool = False,
) -> list[str]:
    """One summary ``[INFO]`` line per spec file for project/process
    requirements with no ``stories:`` field (SR-11-009).

    The count is computed from the loaded registry on every run. ``kind:
    protocol`` and ``kind: architecture`` requirements are excluded: SR-11-003
    and SR-11-004 cover protocol, and architecture is not this advisory's
    business. The advisory never affects the exit code. The IDs appear under
    each file's summary line only when *list_no_story_ids* is ``True``
    (``--list-no-story-ids`` on the CLI).
    """
    lines: list[str] = []
    for file in registry.files:
        no_story_ids = sorted(
            spec.id
            for group in file.groups
            for spec in group.specs
            if spec.kind in _PROJECT_PROCESS_KINDS and not spec.stories
        )
        if not no_story_ids:
            continue
        lines.append(
            f"[INFO] {LintWarningCode.NO_PROJECT_PROCESS_STORY}: {file.id} "
            f"({file.title}): {len(no_story_ids)} project/process "
            f"requirement(s) with no stories: field (SR-11-009)"
        )
        if list_no_story_ids:
            lines.extend(f"    {spec_id}" for spec_id in no_story_ids)
    return lines
