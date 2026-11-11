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

"""Milestones from case activation through public disclosure.

Specs: DEMOMA-06-002, DEMOMA-06-003.
"""

import logging

from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.em import is_em_embargo_active
from vultron.core.states.rm import RM
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_participant_pxa_state,
)
from vultron.demo.helpers.sync.ledger import (
    _extract_ref_id,
)
from vultron.demo.helpers.verification.participants import (
    _fetch_participant,
)
from vultron.demo.helpers.verification.states import (
    _assert_participant_pxa_only,
    _assert_participant_vf_pxa,
    _check_participant_d_state_in,
    _check_participant_not_fix_deployed,
    _check_participant_rm_state_in,
    _check_participant_vf_state_in,
)
from vultron.demo.utils import DataLayerClient
from vultron.demo.utils.served import from_server
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
    case = from_server(as_VulnerabilityCase, case_data)

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
    reporter_case = from_server(as_VulnerabilityCase, reporter_case_data)

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

    The guard a caller wants when it needs the role and not the record; see
    :func:`_fetch_vendor_participant` for the arguments and the raise.

    Spec: DEMOMA-15-001.
    """
    _fetch_vendor_participant(client, case_id, actor_id, label)


def _fetch_vendor_participant(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    label: str,
) -> as_CaseParticipant:
    """Return *actor_id*'s participant record, or raise naming the shortfall.

    One fetch serves both role guards, so a check that needs the roles again
    does not read the store a second time.

    Spec: DEMOMA-15-001.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        label: Human-readable label for the ``AssertionError`` message.

    Returns:
        The participant record, which holds ``CVDRole.VENDOR``.

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
    return participant


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


def _assert_vendor_only_role(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    label: str,
) -> None:
    """Assert *actor_id* holds ``CVDRole.VENDOR`` and not ``CVDRole.DEPLOYER``.

    The claim ``verify_stops_at_fix_ready`` makes is the CSB-15-002 ceiling —
    this participant cannot advance past VFd — not "it has not deployed yet".
    A participant that also holds ``CVDRole.DEPLOYER`` has a deploy path, so
    reading its ``d_state`` as ``d`` says only that the deploy has not landed
    yet and a later one falsifies the milestone's label.  Refusing it here
    makes a mis-cast call a clear role failure instead of a check that passes
    until the scenario grows a deploy step (DEMOMA-15-004).

    Spec: DEMOMA-15-004.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        label: Human-readable label for the ``AssertionError`` message.

    Raises:
        AssertionError: If the participant is not found, does not hold
            ``CVDRole.VENDOR``, or also holds ``CVDRole.DEPLOYER``.
    """
    participant = _fetch_vendor_participant(client, case_id, actor_id, label)
    if CVDRole.DEPLOYER in participant.case_roles:
        raise AssertionError(
            f"{label}: actor {actor_id!r} holds CVDRole.DEPLOYER, so it has a"
            f" deploy path and does not stop at VFd; actual roles:"
            f" {participant.case_roles!r}"
        )


def verify_stops_at_fix_ready(
    receiver_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    receiver_actor_id: str,
) -> None:
    """Verify that both replicas show the participant stopped at VFd.

    The other half of :func:`verify_fix_ready`: that one reads the f→F
    transition the vendor made, this one reads the d→D transition it did not.
    A milestone labelled "stops at VFd" asserts something ``verify_fix_ready``
    does not say, so the two together are a pair rather than one claim told
    twice (#5602).

    The ``receiver_actor_id`` MUST be the full URI of an actor holding
    ``CVDRole.VENDOR`` and not ``CVDRole.DEPLOYER``: the d→D transition is
    gated on DEPLOYER by ``CheckDeployerRoleNode`` (CSB-15-002), which is what
    makes reading ``d_state`` as ``d`` a statement about the ceiling rather
    than about the moment it is read.  Passing a DEPLOYER is a caller error
    and raises ``AssertionError`` before the state check runs.

    No poll precedes the reads: DEMOMA-06-006 requires one before each
    positive state a helper asserts, and there is no waiting for a transition
    that must never happen — the role guard, not a timeout, is what holds it.

    Specs: DEMOMA-06-002, DEMOMA-15-004.

    Args:
        receiver_client: Client connected to the receiver container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        receiver_actor_id: Full URI of the receiver actor whose participant
            fix-deployed state to check.

    Raises:
        AssertionError: If ``receiver_actor_id`` does not hold
            ``CVDRole.VENDOR``, holds ``CVDRole.DEPLOYER``, or either replica
            records a fix-deployed transition for it.
    """
    _assert_vendor_only_role(
        receiver_client,
        case_id,
        receiver_actor_id,
        "verify_stops_at_fix_ready",
    )
    for label, client in (
        ("receiver", receiver_client),
        ("reporter replica", reporter_client),
    ):
        _check_participant_not_fix_deployed(
            client,
            case_id,
            receiver_actor_id,
            f"verify_stops_at_fix_ready {label}",
        )
    logger.info(
        "✓ stops at fix ready: both replicas show CS still excludes D (no fix"
        " deployed)"
    )


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
    - Coordinator participant's latest status has ``d.state == D`` and
      a public-aware ``pxa`` state.

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
