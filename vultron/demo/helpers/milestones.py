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

"""CVD lifecycle milestone verification helpers.

Each function verifies the observable system state that corresponds to a named
milestone in the VFDPxa lifecycle.  Functions are named after the domain event
they confirm (e.g. ``verify_case_active``, ``verify_fix_ready``) rather than
opaque milestone numbers (m1–m7).

Specs: DEMOMA-06-002, DEMOMA-06-003.
"""

import logging
from collections.abc import Mapping, Sequence
from typing import cast

from vultron.core.predicates.case_closure import (
    CASE_FULLY_CLOSED_EVENT_TYPE,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.em import is_em_embargo_active
from vultron.core.states.rm import RM
from vultron.demo.helpers.polling import (
    find_case_actor_participant_id,
    wait_for_all_participants_rm_closed,
    wait_for_case_actor_ledger_event,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_participant_pxa_state,
)
from vultron.demo.helpers.sync import _extract_ref_id
from vultron.demo.helpers.verification import (
    _assert_participant_pxa_only,
    _assert_participant_vf_pxa,
    _check_participant_d_state_in,
    _check_participant_rm_state_in,
    _check_participant_vf_state_in,
    _fetch_participant,
    _fetch_participant_data,
)
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def verify_case_active(
    receiver_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    receiver_actor_id: str,
    reporter_actor_id: str,
) -> None:
    """Verify that the case is active with required participants and EM.ACTIVE.

    Checks the coordinator DataLayer for the required participants (coordinator
    and reporter) plus at least one Case Actor (≥3 total) with an active
    embargo, then verifies the reporter DataLayer has a matching case replica.

    Spec: DEMOMA-06-002, DEMOMA-06-003.

    Args:
        receiver_client: Client connected to the receiver container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        receiver_actor_id: Full URI of the receiver actor.
        reporter_actor_id: Full URI of the reporter actor.

    Raises:
        AssertionError: If any invariant is violated.
    """
    # Coordinator side
    case_data = receiver_client.get(receiver_client.dl_path(case_id))
    assert case_data, (
        f"verify_case_active: receiver case {case_id!r} not found"
    )
    case = as_VulnerabilityCase.model_validate(case_data)

    required = {receiver_actor_id, reporter_actor_id}
    missing = required - set(case.actor_participant_index.keys())
    if missing:
        raise AssertionError(
            f"verify_case_active: required participants missing from coordinator"
            f" case: {missing}"
        )
    other_actors = set(case.actor_participant_index.keys()) - required
    if not other_actors:
        raise AssertionError(
            "verify_case_active: expected a Case Actor participant in addition"
            " to receiver and reporter"
        )
    if not is_em_embargo_active(case.em_state):
        raise AssertionError(
            f"verify_case_active receiver: expected EM.ACTIVE, found"
            f" {case.em_state}"
        )
    logger.info(
        "✓ case active (receiver): required participants (receiver,"
        " reporter) + case-actor present, EM.ACTIVE, embargo present"
    )

    # Reporter side: replica must exist with matching participant index and
    # embargo.  The replica arrives via the receiver's outbox, which runs as a
    # background task, so poll rather than reading once — the coordinator-side
    # participant count can reach its target a few tens of milliseconds before
    # the reporter's Create(VulnerabilityCase) has been processed.
    wait_for_case_on_container(reporter_client, case_id)
    reporter_case_data = reporter_client.get(reporter_client.dl_path(case_id))
    if not reporter_case_data:
        raise AssertionError(
            f"verify_case_active: reporter does not have case replica for"
            f" {case_id!r} — outbox delivery may not have completed"
        )
    reporter_case = as_VulnerabilityCase.model_validate(reporter_case_data)

    receiver_embargo_id = _extract_ref_id(case.active_embargo)
    reporter_embargo_id = _extract_ref_id(reporter_case.active_embargo)
    if (
        receiver_embargo_id is not None
        and receiver_embargo_id != reporter_embargo_id
    ):
        raise AssertionError(
            f"verify_case_active: reporter active_embargo {reporter_embargo_id!r}"
            f" != coordinator active_embargo {receiver_embargo_id!r}"
        )
    logger.info(
        "✓ case active (reporter): case replica present, active embargo present"
    )


def _assert_vendor_role(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    label: str,
) -> None:
    """Assert that *actor_id* holds ``CVDRole.VENDOR`` in the case.

    Spec: DEMOMA-15-001.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        label: Human-readable label for the ``AssertionError`` message.

    Raises:
        AssertionError: If the participant is not found or does not hold
            ``CVDRole.VENDOR``.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    if participant is None:
        raise AssertionError(
            f"{label}: actor {actor_id!r} not found as a participant in case"
            f" {case_id!r}"
        )
    if CVDRole.VENDOR not in participant.case_roles:
        raise AssertionError(
            f"{label}: actor {actor_id!r} does not hold CVDRole.VENDOR;"
            f" actual roles: {participant.case_roles!r}"
        )


def verify_fix_ready(
    receiver_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    receiver_actor_id: str,
) -> None:
    """Verify that both replicas show CS includes F (fix ready).

    The ``receiver_actor_id`` MUST be the full URI of an actor holding
    ``CVDRole.VENDOR`` in the case.  Passing any other actor (e.g. a
    Coordinator) is a caller error and will raise ``AssertionError`` before
    the state check runs.

    Specs: DEMOMA-06-002, DEMOMA-15-001.

    Args:
        receiver_client: Client connected to the receiver container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        receiver_actor_id: Full URI of the receiver actor whose
            participant vf_state/d_state to check.

    Raises:
        AssertionError: If ``receiver_actor_id`` does not hold
            ``CVDRole.VENDOR``, or if either replica does not reflect
            fix-ready state.
    """
    _assert_vendor_role(
        receiver_client, case_id, receiver_actor_id, "verify_fix_ready"
    )
    fix_ready_state = {CS_vf.VF}
    # CS.F entails RM in {ACCEPTED, DEFERRED, CLOSED}: a participant that has
    # a fix-ready CS state must also have engaged with the report at the RM level.
    rm_engaged_states = {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
    _check_participant_vf_state_in(
        receiver_client,
        case_id,
        receiver_actor_id,
        fix_ready_state,
        "verify_fix_ready coordinator",
    )
    _check_participant_rm_state_in(
        receiver_client,
        case_id,
        receiver_actor_id,
        rm_engaged_states,
        "verify_fix_ready coordinator RM",
    )
    _check_participant_vf_state_in(
        reporter_client,
        case_id,
        receiver_actor_id,
        fix_ready_state,
        "verify_fix_ready reporter replica",
    )
    _check_participant_rm_state_in(
        reporter_client,
        case_id,
        receiver_actor_id,
        rm_engaged_states,
        "verify_fix_ready reporter replica RM",
    )
    logger.info("✓ fix ready: both replicas show CS includes F (fix ready)")


def _assert_deployer_role(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    label: str,
) -> None:
    """Assert that *actor_id* holds ``CVDRole.DEPLOYER`` in the case.

    The d→D (fix-deployed) transition is gated on ``CVDRole.DEPLOYER`` by
    ``CheckDeployerRoleNode`` (CSB-15-002).  A VENDOR-only actor cannot reach
    VFD regardless, so accepting VENDOR here would only produce a confusing
    VFD-state-check failure downstream instead of a clear role-check failure.

    Spec: DEMOMA-15-001.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        label: Human-readable label for the ``AssertionError`` message.

    Raises:
        AssertionError: If the participant is not found or does not hold
            ``CVDRole.DEPLOYER``.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    if participant is None:
        raise AssertionError(
            f"{label}: actor {actor_id!r} not found as a participant in case"
            f" {case_id!r}"
        )
    if CVDRole.DEPLOYER not in (participant.case_roles or []):
        raise AssertionError(
            f"{label}: actor {actor_id!r} does not hold CVDRole.DEPLOYER;"
            f" actual roles: {participant.case_roles!r}"
        )


def verify_fix_deployed(
    receiver_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    receiver_actor_id: str,
) -> None:
    """Verify that both replicas show CS includes D (fix deployed).

    The ``receiver_actor_id`` MUST be the full URI of an actor holding
    ``CVDRole.DEPLOYER`` in the case.  The d→D transition is gated on
    ``CVDRole.DEPLOYER`` by ``CheckDeployerRoleNode`` (CSB-15-002); a
    VENDOR-only actor cannot advance beyond VFd regardless, so passing one
    here is a caller error that will raise ``AssertionError`` immediately.

    Specs: DEMOMA-06-002, DEMOMA-15-001.

    Args:
        receiver_client: Client connected to the receiver container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        receiver_actor_id: Full URI of the receiver actor whose
            participant vf_state/d_state to check.

    Raises:
        AssertionError: If ``receiver_actor_id`` does not hold
            ``CVDRole.DEPLOYER``, or if either replica does not reflect
            fix-deployed state.
    """
    _assert_deployer_role(
        receiver_client, case_id, receiver_actor_id, "verify_fix_deployed"
    )
    deployed_state = {CS_d.D}
    _check_participant_d_state_in(
        receiver_client,
        case_id,
        receiver_actor_id,
        deployed_state,
        "verify_fix_deployed coordinator",
    )
    _check_participant_d_state_in(
        reporter_client,
        case_id,
        receiver_actor_id,
        deployed_state,
        "verify_fix_deployed reporter replica",
    )
    logger.info(
        "✓ fix deployed: both replicas show CS includes D (fix deployed)"
    )


def verify_publicly_disclosed(
    receiver_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    receiver_actor_id: str,
) -> None:
    """Verify that both replicas reflect CS.VFDPxa and EM has terminated.

    Checks:
    - Both DataLayers reflect ``EM.EXITED`` on the case.
    - Coordinator participant's latest status has ``d_state == D`` and
      a public-aware ``pxa_state``.

    Spec: DEMOMA-06-002.

    Args:
        receiver_client: Client connected to the receiver container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        receiver_actor_id: Full URI of the receiver actor.

    Raises:
        AssertionError: If any disclosure invariant is violated.
    """
    # Every replica is gated on each awaited effect before it is asserted.
    # actor_notifies_published returns HTTP 202 before the CaseActor fans the
    # ledger entries out, and that fan-out reaches every replica
    # independently, so an instant read of *either* replica races the async
    # apply (ADR-0058, EDF-06-002, DEMOMA-06-006; #2376 reporter, #3903
    # receiver).
    for label, client in [
        ("receiver", receiver_client),
        ("reporter", reporter_client),
    ]:
        wait_for_case_em_terminated(client=client, case_id=case_id)
        logger.info("✓ publicly disclosed %s: EM.EXITED", label)

    # Verify receiver participant's pxa state (and VFD only for vendor/deployer)
    # on both the coordinator's and reporter's DataLayer replicas.
    vfd_roles = {CVDRole.VENDOR, CVDRole.DEPLOYER}
    for label, c in [
        ("receiver", receiver_client),
        ("reporter", reporter_client),
    ]:
        wait_for_participant_pxa_state(
            client=c,
            case_id=case_id,
            actor_id=receiver_actor_id,
        )
        p = _fetch_participant(c, case_id, receiver_actor_id)
        if p is None:
            raise AssertionError(
                f"verify_publicly_disclosed {label}: receiver participant"
                f" {receiver_actor_id!r} not found"
            )
        receiver_roles = set(p.case_roles or [])
        if receiver_roles & vfd_roles:
            _assert_participant_vf_pxa(p, label, receiver_actor_id)
        else:
            _assert_participant_pxa_only(p, label, receiver_actor_id)
    logger.info("✓ publicly disclosed: both replicas CS.VFDPxa and EM.EXITED")


def verify_case_closed(
    case_manager_client: DataLayerClient,
    case_id: str,
) -> None:
    """Verify that every participant is RM.CLOSED in the CASE_MANAGER's store.

    The CASE_MANAGER's own store, not any participant's replica, is where
    every participant's closure is verified (CM-23-004).  A participant at
    RM ``CLOSED`` is sent nothing after the entries that record its own
    closure, so an earlier leaver's replica never learns of a later
    closure, and the Case Owner's replica never receives the CASE_MANAGER's
    closure steps or ``case_fully_closed``.  Each departing participant's
    replica is checked for its own closure only
    (:func:`~vultron.demo.helpers.closure.close_case_owner_last`).

    The CASE_MANAGER is checked like any other participant.  It used to be
    skipped here as "a coordinator", but it has a full RM lifecycle
    (ADR-0051, CM-23-005) and CM-23-010 defines ``RM.CLOSED`` on its record as
    "the Case Owner has left and the case is fully closed".  Skipping it meant
    this check passed while the authority still read ``RM.ACCEPTED`` — the
    mask over ISSUE-2505.

    Polls through :func:`~vultron.demo.helpers.polling
    .wait_for_all_participants_rm_closed`, then names every participant
    that is not ``RM.CLOSED``.

    Spec: DEMOMA-06-002, CM-23-004.

    Args:
        case_manager_client: Client bound to the CASE_MANAGER's own store
            (see :func:`~vultron.demo.helpers.polling.case_manager_store`).
        case_id: Full URI of the ``as_VulnerabilityCase``.

    Raises:
        AssertionError: If any joined participant is not RM.CLOSED in the
            CASE_MANAGER's store.
    """
    client = case_manager_client
    try:
        wait_for_all_participants_rm_closed(client=client, case_id=case_id)
    except AssertionError:
        pass  # name the participants that are still open, below
    case_data = client.get(client.dl_path(case_id))
    assert case_data, f"verify_case_closed: case {case_id!r} not found"
    case = as_VulnerabilityCase.model_validate(case_data)
    open_actors: list[str] = []
    for a_id, p_id in case.actor_participant_index.items():
        p_data = _fetch_participant_data(client, p_id)
        if p_data is None:
            open_actors.append(f"'{a_id}' (no participant record)")
            continue
        p = as_CaseParticipant(**p_data)
        if not p.joined:
            continue  # unanswered invitee (CM-11-006) — not yet a full
            # participant; excluded from the "all closed" check
            # (parallel to _all_fetchable_participants_rm_closed)
        latest = p.participant_status
        rm = latest.rm.state if latest is not None else None
        if rm != RM.CLOSED:
            open_actors.append(f"'{a_id}' at {rm!r}")
    if open_actors:
        raise AssertionError(
            "verify_case_closed: in the CASE_MANAGER's store, expected"
            " RM.CLOSED for every participant; found " + ", ".join(open_actors)
        )
    logger.info(
        "✓ case closed: all participants RM.CLOSED in the CASE_MANAGER's store"
    )


#: The CASE_MANAGER's owner-close write boundary (ADR-0085, CM-23-002); the
#: same constant the core post-close guard reads (CM-23-013).
CASE_FULLY_CLOSED = CASE_FULLY_CLOSED_EVENT_TYPE

#: The receipt entry of a ``Leave(VulnerabilityCase)`` (ADR-0050, CM-23-001).
_CLOSE_CASE = "close_case"

#: A participant status entry, which carries an explicit RM state.
_PARTICIPANT_STATUS = "add_participant_status_to_participant"


def _ref(value: object) -> str | None:
    """Return the id of a payload reference: a URI string or an ``{"id": …}``."""
    if isinstance(value, Mapping):
        value = value.get("id")
    return value if isinstance(value, str) and value else None


def _rm_on_ledger(entry: Mapping[str, object]) -> tuple[str, str] | None:
    """Return ``(actor_id, rm_state)`` when *entry* records an RM state.

    Only a participant status entry records an RM state: that of the actor its
    status is attributed to.  A ``close_case`` entry records the received
    ``Leave`` and no RM state; the transitions the Leave caused are the status
    entries the CASE_MANAGER commits after it (CM-23-001).
    """
    snapshot = entry.get("payload_snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    if entry.get("event_type") == _PARTICIPANT_STATUS:
        status = snapshot.get("object")
        if not isinstance(status, Mapping):
            return None
        actor_id = _ref(status.get("attributedTo"))
        rm_state = status.get("rmState")
        if actor_id and isinstance(rm_state, str):
            return actor_id, rm_state
    return None


def case_closure_violations(
    entries: Sequence[Mapping[str, object]],
    departed_actor_ids: Sequence[str],
    case_manager_id: str | None,
) -> list[str]:
    """Return every way *entries* fail to record the case's closure.

    *entries* is one case's ledger as the CASE_MANAGER holds it (DataLayer
    shape: ``log_index``, ``event_type``, ``payload_snapshot``).  The ledger
    records a closure when all of these hold:

    - It has exactly one ``case_fully_closed`` entry (CM-23-002).
    - Every actor in *departed_actor_ids* has a ``close_case`` entry before
      ``case_fully_closed``, and the last RM state a status entry records for
      it before that boundary is ``RM.CLOSED`` (CM-23-001, CM-23-015).  The
      ``close_case`` entry itself records no RM state.
    - ``case_fully_closed`` is the last entry that records a participant's
      act: every later entry records the CASE_MANAGER's own act, its
      ``payloadSnapshot.actor`` being *case_manager_id* (CM-23-013).

    Every violation is reported, not only the first (EH-07-001).

    Args:
        entries: The case's ledger entries, in any order.
        departed_actor_ids: Every participant that left the case before it
            closed, the Case Owner included.
        case_manager_id: The CASE_MANAGER's actor id, or ``None`` when it
            could not be found, which is itself a violation.

    Returns:
        One message per violation; empty when the closure is recorded.
    """
    indexed = sorted(
        (
            (index, entry)
            for entry in entries
            if isinstance(index := entry.get("log_index"), int)
        ),
        key=lambda pair: pair[0],
    )
    boundaries = [
        index
        for index, entry in indexed
        if entry.get("event_type") == CASE_FULLY_CLOSED
    ]
    if len(boundaries) != 1:
        return [
            f"expected exactly one {CASE_FULLY_CLOSED!r} entry, found"
            f" {len(boundaries)}"
        ]
    (boundary,) = boundaries
    return _departure_violations(
        [entry for index, entry in indexed if index < boundary],
        departed_actor_ids,
        boundary,
    ) + _post_boundary_violations(
        [(index, entry) for index, entry in indexed if index > boundary],
        case_manager_id,
        boundary,
    )


def _departure_violations(
    before: Sequence[Mapping[str, object]],
    departed_actor_ids: Sequence[str],
    boundary: int,
) -> list[str]:
    """Each departed actor that the ledger before *boundary* leaves open.

    *before* is the ledger before ``case_fully_closed``, in ledger order.
    """
    rm_states: dict[str, str] = {}
    left: set[str] = set()
    for entry in before:
        if entry.get("event_type") == _CLOSE_CASE:
            snapshot = entry.get("payload_snapshot")
            if isinstance(snapshot, Mapping) and (
                leaver := _ref(snapshot.get("actor"))
            ):
                left.add(leaver)
            continue
        recorded = _rm_on_ledger(entry)
        if recorded is not None:
            actor_id, rm_state = recorded
            rm_states[actor_id] = rm_state

    violations: list[str] = []
    for actor_id in departed_actor_ids:
        if actor_id not in left:
            violations.append(
                f"no {_CLOSE_CASE!r} entry for {actor_id!r} before"
                f" {CASE_FULLY_CLOSED!r} (logIndex={boundary})"
            )
        elif rm_states.get(actor_id) != RM.CLOSED:
            violations.append(
                f"{actor_id!r} is at RM {rm_states.get(actor_id)!r} on the"
                f" ledger before {CASE_FULLY_CLOSED!r}, expected"
                f" {RM.CLOSED.value!r}"
            )
    return violations


def _post_boundary_violations(
    after: Sequence[tuple[int, Mapping[str, object]]],
    case_manager_id: str | None,
    boundary: int,
) -> list[str]:
    """Each entry after *boundary* that records a participant's act."""
    if case_manager_id is None:
        return [
            "no CASE_MANAGER in the case's participant index; cannot tell its"
            " own entries from a participant's"
        ]
    violations: list[str] = []
    for index, entry in after:
        snapshot = entry.get("payload_snapshot")
        actor_id = (
            _ref(snapshot.get("actor"))
            if isinstance(snapshot, Mapping)
            else None
        )
        if actor_id != case_manager_id:
            violations.append(
                f"logIndex={index} {entry.get('event_type')!r} records"
                f" {actor_id!r}'s act after {CASE_FULLY_CLOSED!r}"
                f" (logIndex={boundary})"
            )
    return violations


def case_manager_ledger(
    client: DataLayerClient, case_id: str
) -> list[Mapping[str, object]]:
    """Return *case_id*'s ledger entries as the CASE_MANAGER holds them.

    Read through *client* as given: it MUST already be bound to the
    CASE_MANAGER's own store (the closure milestone binds it once, through
    :func:`~vultron.demo.helpers.polling.case_manager_store`), so no second
    store lookup is made here.  DataLayer shape (``log_index``,
    ``event_type``, ``payload_snapshot``), in no particular order.
    """
    raw = client.get(client.dl_path("CaseLedgerEntrys/"))
    if not isinstance(raw, dict):
        return []
    return [
        v
        for v in raw.values()
        if isinstance(v, dict) and v.get("case_id") == case_id
    ]


def own_closure_tail_index(
    entries: Sequence[Mapping[str, object]], actor_id: str
) -> int | None:
    """Return the ``log_index`` of the last entry recording *actor_id*'s closure.

    The entries that record a participant's own closure are its
    ``close_case`` entry and the status entries the CASE_MANAGER commits for
    it (CM-23-001).  They are the last entries a departing participant is
    sent (CM-23-004), so its replica's ledger ends here.  ``None`` when the
    ledger records no ``close_case`` for *actor_id*.
    """
    closed_at: int | None = None
    tail: int | None = None
    for entry in sorted(
        (e for e in entries if isinstance(e.get("log_index"), int)),
        key=lambda e: cast(int, e["log_index"]),
    ):
        index = cast(int, entry["log_index"])
        snapshot = entry.get("payload_snapshot")
        if entry.get("event_type") == _CLOSE_CASE:
            if isinstance(snapshot, Mapping) and (
                _ref(snapshot.get("actor")) == actor_id
            ):
                closed_at = tail = index
            continue
        recorded = _rm_on_ledger(entry)
        if (
            closed_at is not None
            and recorded is not None
            and recorded[0] == actor_id
        ):
            tail = index
    return tail


def verify_case_closure_recorded(
    client: DataLayerClient,
    case_id: str,
    departed_actor_ids: Sequence[str],
) -> None:
    """Verify the CASE_MANAGER's ledger records the case's closure in order.

    The ledger half of the closure milestone; :func:`verify_case_closed` is
    the participant-record half, read in the same store.  Waits for
    ``case_fully_closed`` in the CASE_MANAGER's own store, then checks the
    ledger with :func:`case_closure_violations`: every participant in
    *departed_actor_ids* is ``RM.CLOSED`` on the ledger before
    ``case_fully_closed``, and no later entry records a participant's act.

    Args:
        client: Client bound to the CASE_MANAGER's own store (see
            :func:`~vultron.demo.helpers.polling.case_manager_store`).
        case_id: Full URI of the ``as_VulnerabilityCase``.
        departed_actor_ids: Every participant that left before the case
            closed, the Case Owner included, as
            :func:`~vultron.demo.helpers.closure.close_case_owner_last`
            records them.

    Raises:
        AssertionError: If ``case_fully_closed`` does not appear in time, or
            the ledger fails any check; the message lists every violation.

    Spec: CM-23-015, CM-23-013, CM-23-002, DEMOMA-06-002.
    """
    wait_for_case_actor_ledger_event(
        client=client, case_id=case_id, event_type=CASE_FULLY_CLOSED
    )
    entries = case_manager_ledger(client, case_id)
    violations = case_closure_violations(
        entries,
        departed_actor_ids,
        find_case_actor_participant_id(client, case_id),
    )
    if violations:
        raise AssertionError(
            "verify_case_closure_recorded: " + "; ".join(violations)
        )
    logger.info(
        "✓ case closure recorded: %d departures before %s, no participant"
        " act after it",
        len(departed_actor_ids),
        CASE_FULLY_CLOSED,
    )
