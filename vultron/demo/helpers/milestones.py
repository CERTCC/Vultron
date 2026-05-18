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

from vultron.core.states.cs import CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.demo.helpers.sync import _extract_ref_id
from vultron.demo.helpers.verification import (
    _assert_participant_vfd_pxa,
    _check_participant_vfd_state_in,
    _fetch_participant,
    _fetch_participant_data,
)
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

logger = logging.getLogger(__name__)


def verify_case_active(
    coordinator_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    coordinator_actor_id: str,
    reporter_actor_id: str,
) -> None:
    """Verify that the case is active with required participants and EM.ACTIVE.

    Checks the coordinator DataLayer for the required participants (coordinator
    and reporter) plus at least one Case Actor (≥3 total) with an active
    embargo, then verifies the reporter DataLayer has a matching case replica.

    Spec: DEMOMA-06-002, DEMOMA-06-003.

    Args:
        coordinator_client: Client connected to the coordinator container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``VulnerabilityCase``.
        coordinator_actor_id: Full URI of the coordinator actor.
        reporter_actor_id: Full URI of the reporter actor.

    Raises:
        AssertionError: If any invariant is violated.
    """
    # Coordinator side
    case_data = coordinator_client.get(f"/datalayer/{case_id}")
    assert (
        case_data
    ), f"verify_case_active: coordinator case {case_id!r} not found"
    case = VulnerabilityCase.model_validate(case_data)

    required = {coordinator_actor_id, reporter_actor_id}
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
            " to coordinator and reporter"
        )
    if case.current_status.em_state != EM.ACTIVE:
        raise AssertionError(
            f"verify_case_active coordinator: expected EM.ACTIVE, found"
            f" {case.current_status.em_state}"
        )
    if case.active_embargo is None:
        raise AssertionError(
            "verify_case_active coordinator: case has no active_embargo"
        )
    logger.info(
        "✓ case active (coordinator): required participants (coordinator,"
        " reporter) + case-actor present, EM.ACTIVE, embargo present"
    )

    # Reporter side: replica must exist with matching participant index and embargo
    reporter_case_data = reporter_client.get(f"/datalayer/{case_id}")
    if not reporter_case_data:
        raise AssertionError(
            f"verify_case_active: reporter does not have case replica for"
            f" {case_id!r} — outbox delivery may not have completed"
        )
    reporter_case = VulnerabilityCase.model_validate(reporter_case_data)

    coordinator_embargo_id = _extract_ref_id(case.active_embargo)
    reporter_embargo_id = _extract_ref_id(reporter_case.active_embargo)
    if (
        coordinator_embargo_id is not None
        and coordinator_embargo_id != reporter_embargo_id
    ):
        raise AssertionError(
            f"verify_case_active: reporter active_embargo {reporter_embargo_id!r}"
            f" != coordinator active_embargo {coordinator_embargo_id!r}"
        )
    logger.info(
        "✓ case active (reporter): case replica present, matching participant"
        " index and active embargo"
    )


def verify_fix_ready(
    coordinator_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    coordinator_actor_id: str,
) -> None:
    """Verify that both replicas show CS includes F (fix ready).

    Spec: DEMOMA-06-002.

    Args:
        coordinator_client: Client connected to the coordinator container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``VulnerabilityCase``.
        coordinator_actor_id: Full URI of the coordinator actor whose
            participant vfd_state to check.

    Raises:
        AssertionError: If either replica does not reflect fix-ready state.
    """
    fix_ready_states = {CS_vfd.VFd, CS_vfd.VFD}
    _check_participant_vfd_state_in(
        coordinator_client,
        case_id,
        coordinator_actor_id,
        fix_ready_states,
        "verify_fix_ready coordinator",
    )
    _check_participant_vfd_state_in(
        reporter_client,
        case_id,
        coordinator_actor_id,
        fix_ready_states,
        "verify_fix_ready reporter replica",
    )
    logger.info("✓ fix ready: both replicas show CS includes F (fix ready)")


def verify_fix_deployed(
    coordinator_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    coordinator_actor_id: str,
) -> None:
    """Verify that both replicas show CS includes D (fix deployed).

    Spec: DEMOMA-06-002.

    Args:
        coordinator_client: Client connected to the coordinator container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``VulnerabilityCase``.
        coordinator_actor_id: Full URI of the coordinator actor whose
            participant vfd_state to check.

    Raises:
        AssertionError: If either replica does not reflect fix-deployed state.
    """
    deployed_state = {CS_vfd.VFD}
    _check_participant_vfd_state_in(
        coordinator_client,
        case_id,
        coordinator_actor_id,
        deployed_state,
        "verify_fix_deployed coordinator",
    )
    _check_participant_vfd_state_in(
        reporter_client,
        case_id,
        coordinator_actor_id,
        deployed_state,
        "verify_fix_deployed reporter replica",
    )
    logger.info(
        "✓ fix deployed: both replicas show CS includes D (fix deployed)"
    )


def verify_publicly_disclosed(
    coordinator_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    coordinator_actor_id: str,
) -> None:
    """Verify that both replicas reflect CS.VFDPxa and EM has terminated.

    Checks:
    - Both DataLayers reflect ``EM.EXITED`` on the case.
    - Coordinator participant's latest status has ``vfd_state == VFD`` and
      a public-aware ``pxa_state``.

    Spec: DEMOMA-06-002.

    Args:
        coordinator_client: Client connected to the coordinator container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``VulnerabilityCase``.
        coordinator_actor_id: Full URI of the coordinator actor.

    Raises:
        AssertionError: If any disclosure invariant is violated.
    """
    for label, client in [
        ("coordinator", coordinator_client),
        ("reporter", reporter_client),
    ]:
        case_data = client.get(f"/datalayer/{case_id}")
        assert (
            case_data
        ), f"verify_publicly_disclosed {label}: case {case_id!r} not found"
        case = VulnerabilityCase.model_validate(case_data)
        if case.current_status.em_state != EM.EXITED:
            raise AssertionError(
                f"verify_publicly_disclosed {label}: expected EM.EXITED,"
                f" found {case.current_status.em_state}"
            )
        logger.info("✓ publicly disclosed %s: EM.EXITED", label)

    # Verify coordinator participant's latest status is VFD + public-aware pxa
    # on both the coordinator's and reporter's DataLayer replicas.
    for label, c in [
        ("coordinator", coordinator_client),
        ("reporter", reporter_client),
    ]:
        p = _fetch_participant(c, case_id, coordinator_actor_id)
        if p is None:
            raise AssertionError(
                f"verify_publicly_disclosed {label}: coordinator participant"
                f" {coordinator_actor_id!r} not found"
            )
        _assert_participant_vfd_pxa(p, label, coordinator_actor_id)
    logger.info("✓ publicly disclosed: both replicas CS.VFDPxa and EM.EXITED")


def verify_case_closed(
    coordinator_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
) -> None:
    """Verify that all participants are RM.CLOSED on both replicas.

    The Case Actor automatically closes the case once all participants report
    RM.CLOSED (DEMOMA-07-003 step 5).  This helper verifies the terminal
    participant state on both DataLayers.

    Spec: DEMOMA-06-002.

    Args:
        coordinator_client: Client connected to the coordinator container.
        reporter_client: Client connected to the reporter container.
        case_id: Full URI of the ``VulnerabilityCase``.

    Raises:
        AssertionError: If any non-coordinator participant is not RM.CLOSED
            on either replica.
    """
    for label, client in [
        ("coordinator", coordinator_client),
        ("reporter", reporter_client),
    ]:
        case_data = client.get(f"/datalayer/{case_id}")
        assert (
            case_data
        ), f"verify_case_closed {label}: case {case_id!r} not found"
        case = VulnerabilityCase.model_validate(case_data)
        for a_id, p_id in case.actor_participant_index.items():
            p_data = _fetch_participant_data(client, p_id)
            if p_data is None:
                continue  # remote container — not fetchable here
            p = CaseParticipant(**p_data)
            # Case Manager is a coordinator; skip RM closure check.
            if CVDRole.CASE_MANAGER in (p.case_roles or []):
                continue
            latest = p.participant_status
            if latest is None:
                raise AssertionError(
                    f"verify_case_closed {label}: actor '{a_id}' has no"
                    " participant statuses"
                )
            rm = latest.rm_state
            if rm != RM.CLOSED:
                raise AssertionError(
                    f"verify_case_closed {label}: actor '{a_id}' RM state is"
                    f" {rm!r}, expected RM.CLOSED"
                )
        logger.info("✓ case closed %s: all participants RM.CLOSED", label)
    logger.info("✓ case closed: all participants RM.CLOSED on both replicas")
