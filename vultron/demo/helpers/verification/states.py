#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Participant and case state assertions (RM, VF, D, PXA, EM, notes)."""

from vultron.core.models.dimensions import dimension_state
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_d_state,
    participant_status_vf_state,
)
from vultron.core.predicates.participants import all_participants_rm_closed
from vultron.core.states.cs import (
    CS_d,
    CS_pxa,
    CS_vf,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.states.em import is_em_embargo_active
from vultron.core.states.rm import RM
from vultron.demo.helpers.seeding.actors import dl_key
from vultron.demo.helpers.verification.participants import (
    _fetch_participant,
    _fetch_participant_data,
)
from vultron.demo.utils import (
    DataLayerClient,
    ref_id,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _assert_vendor_participant_state(
    vendor_client: DataLayerClient,
    participant_id: str,
) -> None:
    """Assert that the vendor participant has reached ``RM.ACCEPTED``.

    Args:
        vendor_client: DataLayerClient connected to the Vendor container.
        participant_id: Full URI / DataLayer key of the participant record.

    Raises:
        AssertionError: If the participant has no statuses or the latest
            RM state is not ``RM.ACCEPTED``.
    """
    participant = as_CaseParticipant(
        **vendor_client.get(vendor_client.dl_path(dl_key(participant_id)))
    )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError("Vendor participant has no participant statuses")
    if latest.rm.state != RM.ACCEPTED:
        raise AssertionError(
            "Vendor participant RM state did not transition to ACCEPTED"
        )


def _assert_vendor_case_status(case: as_VulnerabilityCase) -> None:
    """Assert that *case* has ``EM.ACTIVE`` and ``pxa == CS_pxa.pxa``.

    Raises:
        AssertionError: If either invariant is violated.
    """
    if not is_em_embargo_active(case.em_state):
        raise AssertionError(
            f"Expected ACTIVE final EM state (default embargo activated at"
            f" case creation per EP-04-001), found {case.em_state}"
        )
    pxa = case.current_status.pxa.state
    if (
        is_pxa_public_aware(pxa)
        or is_pxa_exploit_public(pxa)
        or is_pxa_attacks_observed(pxa)
    ):
        raise AssertionError(f"Expected pxa final case state, found {pxa}")


def _require_note_thread_pair(
    question_note_id: str | None,
    reply_note_id: str | None,
) -> None:
    """Refuse a note-thread assertion that names one half of the thread.

    A note thread has two halves, so a caller asserts both or neither: the
    IDs are both given or both ``None``.  Naming one alone used to leave the
    other half unchecked with no signal (#5643).

    Raises:
        AssertionError: If exactly one ID is ``None``, naming that ID.
    """
    if (question_note_id is None) == (reply_note_id is None):
        return
    missing = (
        "question_note_id" if question_note_id is None else "reply_note_id"
    )
    raise AssertionError(
        f"{missing} is None: a note thread assertion needs both"
        " question_note_id and reply_note_id, or neither"
    )


def _assert_case_notes(
    case: as_VulnerabilityCase,
    question_note_id: str | None,
    reply_note_id: str | None,
) -> None:
    """Assert that *question_note_id* and *reply_note_id* are in *case.notes*.

    A note thread has two halves, so the IDs are both given or both ``None``.
    The check is skipped only when both are ``None``.

    Raises:
        AssertionError: If exactly one ID is ``None``, or a provided note ID
            is missing from the case.
    """
    _require_note_thread_pair(question_note_id, reply_note_id)
    if question_note_id is None or reply_note_id is None:
        # The pair check admitted the call, so both IDs are ``None``: a
        # scenario that asserts no thread names neither half.
        return

    note_ids = [ref_id(note) or str(note) for note in case.notes]
    if question_note_id not in note_ids:
        raise AssertionError(
            f"Question note {question_note_id!r} not found in case notes"
        )
    if reply_note_id not in note_ids:
        raise AssertionError(
            f"Reply note {reply_note_id!r} not found in case notes"
        )


def _latest_status_of(
    participant: as_CaseParticipant | None, actor_id: str, label: str
) -> ParticipantStatus:
    """Return *participant*'s latest status, or raise naming *actor_id*.

    Raises:
        AssertionError: When *participant* is ``None`` or has no statuses.
    """
    if participant is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' not found"
        )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' has no participant"
            " statuses"
        )
    return latest


def _check_participant_rm_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[RM]",
    label: str,
    dl_actor_id: str | None = None,
) -> None:
    """Assert actor's latest participant RM state is in *expected_states*.

    Used to enforce cross-state protocol invariants such as
    "CS.F entails RM in {ACCEPTED, DEFERRED, CLOSED}" — i.e. a participant
    that has a fix-ready or fix-deployed CS state must also have engaged with
    the case at the RM level.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``RM`` values.
        label: Human-readable label for ``AssertionError`` messages.
        dl_actor_id: When provided, read from this actor's store on *client*
            instead of the client's own default store.  Needed when the
            authoritative record is held by a co-hosted CaseActor rather
            than the container's primary actor (ADR-0073).
    """
    participant = _fetch_participant(
        client, case_id, actor_id, dl_actor_id=dl_actor_id
    )
    latest = _latest_status_of(participant, actor_id, label)
    latest_rm = latest.rm.state
    if latest_rm not in expected_states:
        raise AssertionError(
            f"{label}: expected RM state in {expected_states!r}, "
            f"found {latest_rm!r}"
        )


def _check_participant_vf_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[CS_vf]",
    label: str,
) -> None:
    """Assert actor's latest participant VF state is in *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``CS_vf`` values.
        label: Human-readable label for ``AssertionError`` messages.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    latest = _latest_status_of(participant, actor_id, label)
    latest_vf = participant_status_vf_state(latest)
    if latest_vf not in expected_states:
        raise AssertionError(
            f"{label}: expected VF state in {expected_states!r}, "
            f"found {latest_vf!r}"
        )


def _check_participant_d_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[CS_d]",
    label: str,
) -> None:
    """Assert actor's latest participant D state is in *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``CS_d`` values.
        label: Human-readable label for ``AssertionError`` messages.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    latest = _latest_status_of(participant, actor_id, label)
    latest_d = participant_status_d_state(latest)
    if latest_d not in expected_states:
        raise AssertionError(
            f"{label}: expected D state in {expected_states!r}, "
            f"found {latest_d!r}"
        )


def _check_participant_not_fix_deployed(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    label: str,
) -> None:
    """Assert actor's latest participant status records no d→D transition.

    Not ``_check_participant_d_state_in(…, {CS_d.d}, …)``: a participant that
    holds no DEPLOYER role carries no ``d`` dimension at all, so its D state
    reads ``None`` rather than ``CS_d.d``
    (:func:`~vultron.core.models.participant_status\
    .participant_status_d_state`).  Both answers say the fix was not
    deployed and only ``CS_d.D`` says it was, so pinning the set to
    ``{CS_d.d}`` would fail on the very shape the claim is about (#5602).

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        label: Human-readable label for ``AssertionError`` messages.

    Raises:
        AssertionError: If the participant is missing, has no statuses, or its
            latest status records ``CS_d.D``.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    latest = _latest_status_of(participant, actor_id, label)
    latest_d = participant_status_d_state(latest)
    if latest_d is CS_d.D:
        raise AssertionError(
            f"{label}: expected no fix-deployed (D) state, found {latest_d!r}"
        )


def _assert_participant_pxa_only(
    participant: as_CaseParticipant,
    label: str,
    actor_id: str,
) -> None:
    """Assert *participant* has a public-aware pxa_state (no VFD check).

    Used for non-vendor/non-deployer receivers (e.g. coordinators) whose
    vf/d state never advances (non-vendor/deployer) — only pxa is meaningful for them
    after a public-disclosure event (CSB-15-003).

    Raises:
        AssertionError: If pxa_state is not public-aware.
    """
    public_aware = {CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA}
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"M6 {label}: participant {actor_id!r} has no statuses"
        )
    cs = getattr(latest, "case_status", None)
    pxa = dimension_state(cs, "pxa")
    if pxa not in public_aware:
        raise AssertionError(
            f"M6 {label}: pxa_state is not public-aware, found {pxa!r}"
        )


def _assert_participant_vf_pxa(
    participant: as_CaseParticipant,
    label: str,
    vendor_actor_id: str,
) -> None:
    """Assert *participant* has fix-ready (VF=VF) and a public-aware pxa_state.

    Both fix-ready-only and fix-deployed actors have vf.state == CS_vf.VF.

    Args:
        participant: The ``as_CaseParticipant`` to check.
        label: Human-readable label for ``AssertionError`` messages.
        vendor_actor_id: Full URI of the vendor actor (used in error messages).

    Raises:
        AssertionError: If the participant's vf.state is not CS_vf.VF or
            its pxa_state is not public-aware.
    """
    public_aware = {CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA}
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"M6 {label}: participant {vendor_actor_id!r} has no statuses"
        )
    latest_vf = participant_status_vf_state(latest)
    if latest_vf != CS_vf.VF:
        raise AssertionError(
            f"M6 {label}: vfState is not VF (fix ready), found {latest_vf!r}"
        )
    cs = getattr(latest, "case_status", None)
    pxa = dimension_state(cs, "pxa")
    if pxa not in public_aware:
        raise AssertionError(
            f"M6 {label}: pxa_state is not public-aware, found {pxa!r}"
        )


def _all_fetchable_participants_rm_closed(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
) -> bool:
    """Return ``True`` when every fetchable participant is ``RM.CLOSED``.

    Participants on remote containers (fetch returns ``None``) are skipped
    since their state is not locally observable.  Convergence logic is
    delegated to
    :func:`~vultron.core.predicates.participants.all_participants_rm_closed`,
    which includes the CASE_MANAGER (ADR-0051, CM-23-005/CM-23-010) — this
    helper used to describe it as exempt, which is what let ISSUE-2505 stay
    invisible to every scenario's M7 check.

    Args:
        client: DataLayerClient for the container to query.
        case: The ``as_VulnerabilityCase`` whose participant index to walk.

    Returns:
        ``True`` if all locally-fetchable participants are ``RM.CLOSED``;
        ``False`` otherwise.
    """
    core_participants = []
    for p_id in case.actor_participant_index.values():
        p_data = _fetch_participant_data(client, p_id)
        if p_data is None:
            continue  # remote container — not fetchable here
        if not p_data:
            return False
        # No projection step: as_CaseParticipant *is* CaseParticipant
        # (ARCH-25-003, ADR-0099), so validating the fetched payload already yields the
        # core object ``all_participants_rm_closed`` expects.
        participant = as_CaseParticipant(**p_data)
        if not participant.joined:
            # Inert (never-joined) participants are excluded from the active-closure
            # check.  A rejected invitee's RM.CLOSED state is confirmed at the
            # point of rejection (M2 check); replica sync for inert records is
            # not guaranteed across containers (ADR-0114, CM-11-007).
            continue
        core_participants.append(participant)
    if not core_participants:
        # No locally-fetchable participants — cannot confirm closure.
        return False
    return all_participants_rm_closed(core_participants)
