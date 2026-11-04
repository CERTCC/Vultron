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

"""Store scans that find a received Invite or Offer and return its id.

Each finder polls the receiver's archive of received activities with
``_poll_datalayer_for`` and a discriminator naming the activity it wants.
"""

import logging

from vultron.demo.helpers.polling._poll import (
    BACKFILL_PROGRESS_CEILING,
    _poll_datalayer_for,
)
from vultron.demo.helpers.polling.ledger import _count_case_ledger_entries
from vultron.demo.helpers.polling.received import (
    _RECEIVED_ACTIVITY_TYPES,
    _received_activity_id,
    _ref_id,
)
from vultron.demo.helpers.verification import (
    recipient_ids,
)
from vultron.demo.utils import (
    DataLayerClient,
    received_activity_in,
)
from vultron.enums.object_types import VultronObjectType

logger = logging.getLogger(__name__)


def _stub_case_id(stub: dict) -> object:
    """The case a received ``VulnerabilityCaseStub`` names (CM-11-013).

    The archive record keeps the Invite as the body that arrived
    (ADR-0149), so the stub is in its wire form.
    """
    return stub.get("caseId")


def _is_case_invite_for(
    obj_data: dict, case_id: str, invitee_id: str, *, full_case: bool = False
) -> bool:
    """Return True if *obj_data* holds a case Invite for *invitee_id*/*case_id*.

    A stub Invite names its case in the stub's ``caseId`` (CM-11-037); the
    stub's own ``id`` is ``<case-id>/stub`` and is never parsed.  A full-case
    Invite names the case by URI (AKM-02-003).  *full_case* selects which of the
    two is wanted: any case Invite by default, only a full-case one when true.
    """
    invite = received_activity_in(obj_data)
    if invite.get("type") != "Invite":
        return False
    target_raw = invite.get("target")
    is_stub = (
        isinstance(target_raw, dict)
        and target_raw.get("type")
        == VultronObjectType.VULNERABILITY_CASE_STUB.value
    )
    if full_case and is_stub:
        return False
    if isinstance(target_raw, dict):
        target_case_id = (
            _stub_case_id(target_raw) if is_stub else target_raw.get("id")
        )
    else:
        target_case_id = target_raw
    if target_case_id != case_id:
        return False
    inner_id = _ref_id(invite.get("object"))
    return inner_id == invitee_id


def find_case_invite_for_actor(
    client: DataLayerClient,
    case_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CaseActor's Invite(Actor)[target=VulnerabilityCaseStub] for
    *invitee_id* arrives.

    The CASE_MANAGER emits every case Invite — after the Case Owner accepts a
    recommendation (ADR-0026) and on the owner's direct invite alike
    (CM-17-007, ADR-0109); the invitee must then send Accept(Invite) to
    trigger the trust-bootstrap Announce(VulnerabilityCase) that seeds its case
    replica (MV-10-003/MV-10-004).  This helper polls the invitee's DataLayer
    for that Invite, archived by intake on arrival (PCR-06-005), so the demo
    can drive the accept step.

    Args:
        client: DataLayerClient connected to the invitee container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        invitee_id: Full URI of the actor being invited.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The invite activity ID string.

    Raises:
        AssertionError: If no matching Invite is found within *timeout_seconds*.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_case_invite_for(
            obj, case_id, invitee_id
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=f"Found Invite for actor {invitee_id} on case {case_id}: %s",
        error_msg=(
            f"Timed out waiting for CaseActor Invite for actor {invitee_id!r}"
            f" on case {case_id!r} to appear in DataLayer at {client.base_url}"
        ),
    )


def find_full_case_invite_for_actor(
    client: DataLayerClient,
    case_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
    progress_ceiling: float = BACKFILL_PROGRESS_CEILING,
) -> str:
    """Poll until the CASE_MANAGER's full-case Invite for *invitee_id* arrives.

    The CASE_MANAGER sends it after the join-time ``Announce(VulnerabilityCase)``
    and ledger replay (CM-11-010); the joined participant answers it with
    ``accept-full-case-invite`` or one of its two siblings (CM-11-011).

    Because the Invite is queued after the replay, the invitee's inbox reaches
    it only once every replayed entry before it has been applied, one at a
    time.  The wait is therefore gated on that backfill (EDF-06, ADR-0058):
    each poll that finds more of the case's ledger entries in the invitee's
    store restarts *timeout_seconds*, so a long backfill under CI load is
    waited for and a stalled one fails (#4424).  The count comes from the
    unrehydrated ledger collection, not a store dump (#4600), which saves
    rehydration but still moves every entry per poll.

    Args:
        client: DataLayerClient connected to the invitee container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        invitee_id: Full URI of the joined participant.
        timeout_seconds: Seconds the invitee's ledger copy of the case may go
            without advancing before the wait gives up.
        poll_interval: Seconds between DataLayer poll attempts.
        progress_ceiling: Seconds after which the wait gives up however far
            the backfill is still advancing.

    Returns:
        The full-case Invite activity ID string.

    Raises:
        AssertionError: If no matching Invite is found before the backfill
            stalls or *progress_ceiling* passes.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_case_invite_for(
            obj, case_id, invitee_id, full_case=True
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        progress_fn=lambda: _count_case_ledger_entries(client, case_id),
        progress_ceiling=progress_ceiling,
        log_msg=(
            f"Found full-case Invite for actor {invitee_id} on case"
            f" {case_id}: %s"
        ),
        error_msg=(
            f"Timed out waiting for the full-case Invite for actor"
            f" {invitee_id!r} on case {case_id!r} to appear in DataLayer at"
            f" {client.base_url}"
        ),
    )


def _is_ownership_transfer_offer_for(
    obj_data: dict, case_id: str, transferee_id: str
) -> bool:
    """True if *obj_data* is the CaseActor's ownership Offer to *transferee_id*.

    The CaseActor makes the one Offer of a transfer from the owner's proposal
    and sends it to the transferee (CM-21-028, ADR-0148).  That Offer has::

        type   = "Offer"
        target = transferee_id      # the actor being offered ownership,
                                    # inline Actor or its id (DL-08-003)
        object = case_id            # the VulnerabilityCase being transferred

    The Vendor's proposal, ``Offer(Offer(VulnerabilityCase))`` addressed to
    the CaseActor, has no ``target`` and an Offer as its object, so it does
    NOT match this discriminator.
    """
    offer = received_activity_in(obj_data)
    if offer.get("type") != "Offer":
        return False
    target_id = _ref_id(offer.get("target"))
    if target_id != transferee_id:
        return False
    inner_id = _ref_id(offer.get("object"))
    return inner_id == case_id


def find_ownership_transfer_offer_for_actor(
    client: DataLayerClient,
    case_id: str,
    transferee_id: str,
    timeout_seconds: float = 90.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CaseActor's Offer(VulnerabilityCase) for *transferee_id* arrives.

    In the ownership-transfer flow (ADR-0053, ADR-0148), Vendor1's proposal,
    ``Offer(Offer(VulnerabilityCase))``, is addressed to the CaseActor
    (``to=[case_actor_id]``).  ``ProposeCaseOwnershipTransferReceivedUseCase``
    then makes the one Offer of the transfer, under an id the CaseActor
    derives, and delivers it to the transferee's inbox.  Polling for the
    proposal's ID with ``wait_for_object_stored`` will never succeed on the
    transferee's container because the proposal is only held by the vendor
    and the CaseActor.

    This helper scans *client*'s DataLayer for any
    ``Offer(VulnerabilityCase)`` whose ``target`` is *transferee_id* (an inline Actor
    or its id) and returns its ID so the
    demo can drive the ``accept-case-ownership-transfer`` trigger with the
    CaseActor's offer ID.

    Args:
        client: DataLayerClient connected to the transferee's container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        transferee_id: Full URI of the actor being offered case ownership.
        timeout_seconds: Maximum time to wait before raising (default: 90 s).
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The CaseActor's offer activity ID string.

    Raises:
        AssertionError: If no matching Offer is found within *timeout_seconds*.

    Spec: CM-21-005.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_ownership_transfer_offer_for(
            obj, case_id, transferee_id
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=(
            f"Found the CaseActor's Offer(VulnerabilityCase) for"
            f" transferee {transferee_id} on case {case_id}: %s"
        ),
        error_msg=(
            f"Timed out waiting for the CaseActor's Offer(VulnerabilityCase) for"
            f" transferee {transferee_id!r} on case {case_id!r} to appear in"
            f" DataLayer at {client.base_url} — CaseActor outbox delivery may"
            " not have completed (CM-21-005)"
        ),
    )


def _is_cp_offer_for_case(obj_data: dict, case_id: str) -> bool:
    """Return True if *obj_data* holds an Offer(CaseParticipant) for *case_id*."""
    offer = received_activity_in(obj_data)
    if offer.get("type") != "Offer":
        return False
    target_id = _ref_id(offer.get("target"))
    if target_id != case_id:
        return False
    inner = offer.get("object")
    if not isinstance(inner, dict):
        return False
    return bool(
        inner.get("type") in ("CaseParticipant", "as_CaseParticipant")
        or inner.get("case_roles")
    )


def find_cp_offer_for_case(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until an Offer(CaseParticipant) for *case_id* appears in DataLayer.

    After a Coordinator sends suggest-actor-to-case, the CaseActor processes the
    Offer(Actor)[target=VulnerabilityCase] and forwards an Offer(CaseParticipant) to the
    Case
    Owner's inbox (ADR-0026).  This helper polls the Case Owner's DataLayer for
    any received Offer whose ``target`` matches *case_id* and whose ``object``
    resembles a CaseParticipant, so the demo can drive the approve step.  It
    reads intake's archive, the only record holding the participant inline.

    Args:
        client: DataLayerClient connected to the Case Owner's container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The offer activity ID string.

    Raises:
        AssertionError: If no such offer is found within *timeout_seconds*.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_cp_offer_for_case(obj, case_id),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=f"Found Offer(CaseParticipant) for case {case_id}: %s",
        error_msg=(
            f"Timed out waiting for Offer(CaseParticipant) for case"
            f" {case_id!r} to appear in DataLayer at {client.base_url}"
        ),
    )


def _is_embargo_invite_for(
    obj_data: dict, embargo_id: str, invitee_id: str
) -> bool:
    """Return True if *obj_data* holds an ``Invite`` of *embargo_id* to *invitee_id*.

    The relayed Invite names its embargo in ``object`` (inline or by id) and its
    invitee as the sole ``to`` recipient (EP-09-010).
    """
    invite = received_activity_in(obj_data)
    if invite.get("type") != "Invite":
        return False
    inner_id = _ref_id(invite.get("object"))
    if inner_id != embargo_id:
        return False
    return invitee_id in recipient_ids(invite.get("to"))


def find_embargo_invite_for_actor(
    client: DataLayerClient,
    embargo_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CASE_MANAGER's relayed ``Invite(EmbargoEvent)`` arrives.

    The CASE_MANAGER relays every embargo proposal, first or revised, to each
    participant but the proposer (EP-09-002).  The invitee answers only an
    Invite addressed to it (EP-09-003), so a demo polls the invitee's own
    DataLayer for it rather than reading another participant's mail.

    Args:
        client: DataLayerClient connected to the invitee's container.
        embargo_id: Full URI of the proposed ``EmbargoEvent``.
        invitee_id: Full URI of the invited actor.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The relayed Invite's activity ID.

    Raises:
        AssertionError: If no matching Invite is found within *timeout_seconds*.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_embargo_invite_for(
            obj, embargo_id, invitee_id
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=f"Found Invite of embargo {embargo_id} for {invitee_id}: %s",
        error_msg=(
            f"Timed out waiting for the relayed Invite of embargo"
            f" {embargo_id!r} to actor {invitee_id!r} to appear in the"
            f" DataLayer at {client.base_url}"
        ),
    )
