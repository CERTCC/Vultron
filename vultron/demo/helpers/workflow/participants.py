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

"""The CASE_MANAGER, ownership-transfer Offers and two-participant setup."""

import logging

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    find_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
)
from vultron.demo.helpers.seeding import get_actor_by_id
from vultron.demo.helpers.workflow.case_setup import (
    seat_participant_through_stub_invite,
    setup_initialized_case,
)
from vultron.demo.utils import (
    DataLayerClient,
    log_case_state,
    ref_id,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def await_ownership_transfer_offer(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    transferee: as_Actor,
    timeout_seconds: float = 90.0,
) -> str:
    """Gate on the CaseActor's ownership-transfer Offer; return its id.

    The owner addresses its proposal, ``Offer(Offer(VulnerabilityCase))``, to
    the CaseActor, which makes the one ``Offer(VulnerabilityCase)`` of the
    transfer under an id of its own and sends it to the transferee (CM-21-028,
    ADR-0148).  The consequent therefore has a new identity: polling the
    transferee's store for the proposal's id never matches (EDF-06-004, issue
    #2178).  This helper discovers the CaseActor's Offer by its properties
    instead.  The transferee answers it through its accept or reject trigger,
    which takes that Offer's id (TRIG-11-002, TRIG-11-005).

    Args:
        client: DataLayerClient for the container hosting the actors.
        case: The case whose ownership is being transferred.
        transferee: The actor being offered ownership.
        timeout_seconds: Maximum time to wait for the CaseActor's Offer.

    Returns:
        The CaseActor's Offer's activity id, as the transferee holds it.

    Raises:
        AssertionError: If no such Offer arrives within *timeout_seconds*.
    """
    transferee_client = client.model_copy(update={"actor_id": transferee.id_})
    return find_ownership_transfer_offer_for_actor(
        client=transferee_client,
        case_id=case.id_,
        transferee_id=transferee.id_,
        timeout_seconds=timeout_seconds,
    )


def find_case_manager_actor_id(
    client: DataLayerClient, vendor_id: str, case_id: str
) -> str | None:
    """Return the CASE_MANAGER actor ID by reading the case participant roster (ADR-0088).

    Authority is the ``CVDRole.CASE_MANAGER`` role — hosting location is not
    consulted (ARCH-24-004, CM-02-013).
    """
    try:
        case_data = client.get(client.dl_path(case_id, actor_id=vendor_id))
        case_obj = as_VulnerabilityCase(**case_data)
    except Exception:  # noqa: BLE001  # ruff-baseline #3326
        return None

    for p_ref in case_obj.case_participants:
        pid = ref_id(p_ref) or str(p_ref)
        if not pid:
            continue
        try:
            p_data = client.get(client.dl_path(pid, actor_id=vendor_id))
            p = as_CaseParticipant(**p_data)
            if CVDRole.CASE_MANAGER in p.case_roles:
                attr = p.attributed_to
                return (
                    attr
                    if isinstance(attr, str)
                    else getattr(attr, "id_", None)
                )
        except Exception:  # noqa: BLE001, S112  # ruff-baseline #3326
            continue
    return None


def case_manager_invites_actor(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    vendor: as_Actor,
    coordinator: as_Actor,
    invite_actor_id: str,
) -> str:
    """Have *vendor* trigger the stub Invite of *coordinator*; return its id.

    The CASE_MANAGER sends and records the Invite (CM-17-007, ADR-0109), so
    the coordinator answers that Invite and not one the demo builds: a reply
    to an Invite the CASE_MANAGER has no record of is refused (CM-11-017).
    The trigger also records the inert participant at invite-send time
    (ADR-0114, CM-11-006).
    """
    # Seed stub_summary on the CASE_MANAGER's DataLayer copy: the invite BT
    # reads the case from the CASE_MANAGER's store and the BT-created case
    # has none (CM-17-010, MV-10-001, #4165).
    ActorSession(
        client=client, actor=get_actor_by_id(client, invite_actor_id)
    ).with_case(case).quiet().set_stub_summary(
        "Vulnerability report — details shared after acceptance."
    )
    ActorSession(client=client, actor=vendor).with_case(
        case
    ).quiet().invite_actor_to_case(
        invitee_id=str(coordinator.id_), roles=[CVDRole.COORDINATOR]
    )
    invite_id = find_case_invite_for_actor(
        client=client.model_copy(update={"actor_id": coordinator.id_}),
        case_id=case.id_,
        invitee_id=str(coordinator.id_),
    )
    logger.info("CASE_MANAGER Invite for coordinator: %s", invite_id)
    return invite_id


def setup_two_participant_case(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> as_VulnerabilityCase:
    """Create a case with two participants (vendor + coordinator) as a precondition.

    Builds on :func:`setup_initialized_case`, so the vendor mints the case
    through the ``trigger/create-case`` endpoint and holds
    ``CASE_OWNER`` and ``CASE_MANAGER`` on it, then invites the coordinator.
    Used by ``establish_embargo_demo`` and ``manage_embargo_demo``, whose
    embargo messages are accepted only from a sender with standing on a case
    that names a CASE_MANAGER (ADR-0115, EP-09).

    1. The initialised case (:func:`setup_initialized_case`)
    2. The coordinator is seated through its stub Invite
       (:func:`seat_participant_through_stub_invite`), which raises when it
       is not seated

    Args:
        client: DataLayerClient for the shared (or single) container.
        reporter: The reporter ``as_Actor``.
        vendor: The receiving vendor ``as_Actor`` who creates the case.
        coordinator: The coordinator ``as_Actor`` to invite.

    Returns:
        The newly created ``as_VulnerabilityCase`` with vendor and coordinator
        as participants.
    """
    case = setup_initialized_case(client, reporter, vendor)
    seat_participant_through_stub_invite(
        client,
        case,
        owner=vendor,
        invitee=coordinator,
        role=CVDRole.COORDINATOR,
    )

    log_case_state(client, case.id_, "after setup (two participants)")
    logger.info(
        "✓ Setup: Case initialized with vendor and coordinator participants"
    )
    return case
