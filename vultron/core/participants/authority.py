"""Single neutral role-authority resolver for CASE_MANAGER (ARCH-24-001/002).

This module is the one canonical answer to "which actor enacts
``CVDRole.CASE_MANAGER`` on this case?".  It lives below both
``vultron.core.behaviors`` and ``vultron.core.use_cases`` and depends only on
``models``, ``ports``, and ``enums`` — no ``behaviors → use_cases`` import is
needed or permitted here.

Both former twins (``_resolve_case_manager_id`` in ``use_cases/_helpers.py``
and ``resolve_case_manager_id`` in
``behaviors/case/nodes/participant/roles.py``) were deleted and replaced by
this single implementation (ADR-0088, ARCH-24-001, ARCH-24-002).
"""

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole


def resolve_case_manager_id(
    case: VulnerabilityCase, dl: CasePersistence
) -> str | None:
    """Return the actor ID of the CASE_MANAGER participant, or ``None``.

    Authority is the ``CVDRole.CASE_MANAGER`` role — the sole correct signal
    per ADR-0088.  Neither hosting location nor URL shape is consulted.

    Checks two participant sources in order:

    1. ``actor_participant_index`` — fast lookup used after bootstrap (primary
       path for trigger and received use cases).
    2. ``case_participants`` — canonical list used during bootstrap, where
       inline participant objects may not yet be indexed; also handles ID-only
       references absent from the index.

    Returns the ``attributed_to`` actor ID of the first participant holding
    ``CVDRole.CASE_MANAGER``, or ``None`` when none is found.

    This is the correct recipient for all participant-originated outbound
    activities after case creation (PCR-08-001, PCR-08-002).
    """
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if not isinstance(p, CaseParticipant):
            continue
        if CVDRole.CASE_MANAGER in p.roles:
            return _as_id(getattr(p, "attributed_to", None))

    indexed_ids = set(case.actor_participant_index.values())
    for participant_ref in case.case_participants:
        if not isinstance(participant_ref, str):
            if isinstance(participant_ref, CaseParticipant) and (
                CVDRole.CASE_MANAGER in participant_ref.roles
            ):
                return _as_id(getattr(participant_ref, "attributed_to", None))
            continue
        if participant_ref in indexed_ids:
            continue
        p = dl.read(participant_ref)
        if not isinstance(p, CaseParticipant):
            continue
        if CVDRole.CASE_MANAGER in p.roles:
            return _as_id(getattr(p, "attributed_to", None))

    return None
