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
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.participants._lookup import iter_case_participants
from vultron.enums.roles import CVDRole


def resolve_case_manager_id(
    case: VulnerabilityCase, dl: CasePersistence
) -> str | None:
    """Return the actor ID of the CASE_MANAGER participant, or ``None``.

    Authority is the ``CVDRole.CASE_MANAGER`` role — the sole correct signal
    per ADR-0088.  Neither hosting location nor URL shape is consulted.

    Delegates to :func:`~vultron.core.participants._lookup.iter_case_participants`
    for the two-phase participant scan (fast path via ``actor_participant_index``,
    bootstrap fallback via ``case_participants``), then returns the
    ``attributed_to`` actor ID of the first participant holding
    ``CVDRole.CASE_MANAGER``, or ``None`` when none is found.

    This is the correct recipient for all participant-originated outbound
    activities after case creation (PCR-08-001, PCR-08-002).
    """
    for p in iter_case_participants(case, dl):
        if CVDRole.CASE_MANAGER in p.roles:
            return _as_id(getattr(p, "attributed_to", None))
    return None


def has_local_participant_roster(
    case: VulnerabilityCase, dl: CasePersistence
) -> bool:
    """True when *case*'s roster resolves to at least one local participant record.

    Distinguishes a **locally-derived replica** from a case object that is merely
    *present* in the store.  The two are not the same, and the difference matters
    wherever the local roster is used as evidence about a sender: the FastAPI
    ingress adapter pre-stores an inbound activity's nested objects before
    dispatch, so ``dl.read_case()`` can answer with the *sender's own announced
    payload* echoed straight back.  Reading that as local evidence is circular.

    A genuine replica has participant *records* — ``SeedAnnouncedCaseNode``
    writes them, and the ingress pre-store does not — so a resolvable roster is
    the signal that the receiver has an opinion of its own.  A payload echoed in
    by ingress carries ``case_participants`` as bare ID strings that resolve to
    nothing locally, and answers ``False`` here.

    Deliberately *not* "does the roster name a CASE_MANAGER": a seeded replica
    whose roster names only a bystander, or whose CASE_MANAGER carries no
    ``attributed_to``, still has a local opinion and must still fail closed
    (PCR-07-003, #3273 AC-4).  Use :func:`resolve_case_manager_id` for the
    separate question of *who* the authority is.
    """
    return any(True for _ in iter_case_participants(case, dl))
