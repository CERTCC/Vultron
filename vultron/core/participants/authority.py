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
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.participants._lookup import iter_case_participants
from vultron.core.ports.case_persistence import CasePersistence
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


def established_link_case_manager_id(
    dl: CasePersistence, case_id: str
) -> str | None:
    """Return the ``case_manager_id`` recorded for *case_id*, if any.

    A completed ``VultronReportCaseLink`` records the address the authority was
    reached at during bootstrap (CBT-01-006).  That recorded address answers
    before the local replica has a participant roster to read, which is the one
    window :func:`resolve_case_manager_id` cannot cover.
    """
    for link in dl.list_objects("ReportCaseLink"):
        if not isinstance(link, VultronReportCaseLink):
            continue
        if link.case_id == case_id and link.case_manager_id:
            return str(link.case_manager_id)
    return None


def case_manager_address(dl: CasePersistence, case_id: str) -> str | None:
    """Return the delivery address of *case_id*'s authority, if resolvable.

    **This is address resolution, not authority determination.**  The two are
    different questions and ADR-0088 keeps them apart: "am I the authority?" is
    answered by the role, via
    :func:`~vultron.core.participants.authority.resolve_case_manager_id`, and
    this function only answers "what address do I route to?".  Because
    authority *is* the ``CVDRole.CASE_MANAGER`` role, the authority's address is
    simply the role-holder's address (ARCH-24-005, CM-02-011).

    Resolution order:

    1. The ``case_manager_id`` recorded on a completed
       ``VultronReportCaseLink`` (CBT-01-006).
    2. The actor enacting ``CVDRole.CASE_MANAGER`` on the case replica.

    Path 1 comes first because it is the only answer available before the local
    replica has a roster to read: the link records the address the authority was
    reached at during bootstrap, whereas path 2 needs
    ``Create(VulnerabilityCase)`` to have seeded a replica.  Path 2 then covers
    everything afterwards, and covers it without a window — the replica embeds
    the CASE_MANAGER participant from the moment it is seeded (CP-09-004).

    Neither path consults a URL shape or a ``Service`` object's hosting
    location.  Both were removed by ADR-0088: they are not evidence of anything
    protocol-salient (ARCH-24-004, CM-02-013), and the ``Service``-``context``
    scan they relied on had a bootstrap window in which the real authority
    failed its own hosting test (CM-02-012).

    Returns ``None`` when the case has no resolvable authority address — a case
    with no CASE_MANAGER participant and no recorded link.  Every caller
    handles ``None``.  Note that an ordinary participant enacting CASE_MANAGER
    *is* the authority and *does* resolve here: under ADR-0088 there is no
    separate "CaseActor entity" that could be absent while the role is held.
    This is the authoritative address lookup for PCR-08-007 (invite sender) and
    PCR-08-008 (accept recipient).
    """
    established = established_link_case_manager_id(dl, case_id)
    if established is not None:
        return established

    case = dl.read_case(case_id)
    if case is None:
        return None
    return resolve_case_manager_id(case, dl)
