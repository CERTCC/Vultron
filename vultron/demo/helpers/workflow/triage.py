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

"""The receiver's RM triage on the direct and invite paths."""

import logging

from vultron.adapters.utils import parse_id
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    resolve_case_actor_store_id,
    wait_for_participant_rm_state,
)
from vultron.demo.helpers.workflow.case_lookup import (
    wait_for_case_for_offer,
)
from vultron.demo.helpers.workflow.report import (
    receiver_validates_report,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def receiver_engages_case(
    receiver_client: DataLayerClient,
    receiver: as_Actor,
    case_id: str,
) -> dict:
    """Receiver engages the case via the trigger endpoint (RM → ACCEPTED).

    This is a separate, explicit step from ``receiver_validates_report``.
    Validation advances RM to VALID; engagement advances RM to ACCEPTED.
    A receiver may validly stop at VALID and defer further work.

    Args:
        receiver_client: Client connected to the receiver's container.
        receiver: Receiver ``as_Actor``.
        case_id: Full URI of the ``as_VulnerabilityCase`` to engage.

    Returns:
        Response dict from the trigger endpoint (contains the engage
        activity).
    """
    receiver_obj_id = parse_id(receiver.id_)["object_id"]
    result: dict = {}
    with demo_step("Receiver engages the vulnerability case"):
        result = (
            ActorSession(client=receiver_client, actor=receiver)
            .with_case(case_id)
            .quiet()
            .engage_case()
            .model_dump(exclude_none=True)
        )
    logger.info("Engage-case trigger result for actor %s", receiver_obj_id)
    return result


def run_invite_path_rm_triage(
    invited_client: DataLayerClient,
    invited_actor: as_Actor,
    offer: object,
    report: as_VulnerabilityReport,
    reporter: as_Actor,
    auth_client: DataLayerClient,
    case: as_VulnerabilityCase,
    invited_obj: as_Actor,
    timeout_seconds: float = 20.0,
) -> None:
    """Run the RM triage cycle for an invite-path participant (CM-11-011).

    An invited actor joins via ``Accept(Invite(Actor)[target=VulnerabilityCaseStub])``
    and receives the case, then the ledger replay, then the CASE_MANAGER's
    full-case Invite.  It never answers the reporter's
    ``Offer(VulnerabilityReport)``: it was not sent that Offer (CM-11-020,
    ADR-0121).  It judges the case by replying to the full-case Invite, and
    :func:`~vultron.demo.helpers.invite_chain.run_case_invite_chain` sends that
    reply for every invitee before this runs.

    Steps:
    1. Poll until CaseActor reflects RM.VALID or RM.ACCEPTED.
    2. Trigger engage-case (RM → ACCEPTED).
    3. Poll until CaseActor reflects RM.ACCEPTED.

    Args:
        invited_client: Client for the invited actor's container.
        invited_actor: The invited actor's local replica (e.g. vendor2_in_vendor2).
        offer: Unused; kept for call-site compatibility.
        report: Unused; kept for call-site compatibility.
        reporter: Unused; kept for call-site compatibility.
        auth_client: Client for the container that hosts the CaseActor (e.g.
            the coordinating actor's or vendor1_client).  The CaseActor's own
            store is what gets read through it when the case has one — see
            :func:`resolve_case_actor_store_id`; the host actor's replica is
            read only when the case has no CaseActor participant.
        case: The VulnerabilityCase.
        invited_obj: The invited actor's top-level object (used for actor_id lookup).
        timeout_seconds: Polling timeout per wait call (default 20s).
    """
    # Read the CaseActor's own store, not the store of the actor that hosts it:
    # the CaseActor applies the participant RM transition to its own replica and
    # emits no add_participant_status_to_participant ledger entry for it, so the
    # host's replica of the participant stays at RM.START forever (ADR-0073
    # decision 5).  None means "the case has no CaseActor" and preserves the
    # previous read.
    case_actor_store_id = resolve_case_actor_store_id(auth_client, case.id_)

    with demo_check(f"CaseActor reflects {invited_obj.id_} at RM.VALID"):
        wait_for_participant_rm_state(
            client=auth_client,
            case_id=case.id_,
            actor_id=invited_obj.id_,
            expected_states={RM.VALID, RM.ACCEPTED},
            timeout_seconds=timeout_seconds,
            dl_actor_id=case_actor_store_id,
        )

    # Gate engage-case on the invited actor's OWN RM.VALID commit.
    # The reply trigger returns HTTP 202 before its ParticipantStatus write
    # lands, so engaging without the gate races the async commit and yields
    # TransitionParticipantRMtoAccepted (HTTP 422).  Mirrors the direct-path
    # causal gate in run_direct_path_rm_triage (ADR-0058).
    with demo_gate(f"{invited_obj.id_} reached RM.VALID before engage-case"):
        wait_for_participant_rm_state(
            client=invited_client,
            case_id=case.id_,
            actor_id=invited_obj.id_,
            expected_states={RM.VALID, RM.ACCEPTED},
            timeout_seconds=timeout_seconds,
        )
        logger.info("✓ %s RM state reached VALID", invited_obj.id_)

        receiver_engages_case(
            receiver_client=invited_client,
            receiver=invited_actor,
            case_id=case.id_,
        )

        with demo_check(
            f"CaseActor reflects {invited_obj.id_} at RM.ACCEPTED"
        ):
            wait_for_participant_rm_state(
                client=auth_client,
                case_id=case.id_,
                actor_id=invited_obj.id_,
                expected_states={RM.ACCEPTED},
                timeout_seconds=timeout_seconds,
                dl_actor_id=case_actor_store_id,
            )
        with demo_check(f"{invited_obj.id_} own container at RM.ACCEPTED"):
            wait_for_participant_rm_state(
                client=invited_client,
                case_id=case.id_,
                actor_id=invited_obj.id_,
                expected_states={RM.ACCEPTED},
                timeout_seconds=timeout_seconds,
            )
        logger.info("✓ %s RM state reached ACCEPTED", invited_obj.id_)


def run_direct_path_rm_triage(
    receiver_client: DataLayerClient,
    receiver: as_Actor,
    offer: object,
    timeout_seconds: float = 20.0,
) -> as_VulnerabilityCase:
    """Run the RM triage cycle for a direct (report-submission) receiver.

    The submitted-to actor (a Coordinator or Vendor that received an
    Offer(VulnerabilityReport) directly) validates the report and then engages
    the case, holding CASE_OWNER on its own container.

    Steps, each gated on the receiver's *own* store so the demo follows causal
    arrows rather than mere sequence:

    1. Wait for the CaseActor's ``Create(VulnerabilityCase)`` replica to land in
       the receiver's own store.  Under ADR-0041 the receiver never creates the
       case itself, and under PCR-01-003 co-location grants it no peek into the
       CaseActor's store — so until the replica arrives there is no case to
       validate against, and ``RM.VALID`` is a case-scoped transition.
    2. Trigger validate-report (RM → VALID).
    3. Poll until the receiver's own participant status reaches RM.VALID —
       validate-report is dispatched asynchronously (HTTP 202), so the
       ParticipantStatus commit lands *after* the trigger returns.  engage-case
       transitions RM.VALID → RM.ACCEPTED and is rejected (HTTP 422,
       TransitionParticipantRMtoAccepted) if it fires before that commit.
    4. Trigger engage-case (RM → ACCEPTED).
    5. Poll until the receiver's own participant status reaches RM.ACCEPTED.

    The invite-path counterpart is :func:`run_invite_path_rm_triage`; both gate
    engagement on a committed RM.VALID rather than the mere presence of the
    case object (which appears synchronously during validate and is therefore
    not a valid causal precondition for engagement).

    Step 1 replaced a post-hoc ``demo_check`` that asserted the case existed
    *after* validate-report.  That check passed by accident: validate-report used
    to write its report-phase RM.VALID latch whether or not the case was there,
    so the run limped on with the two halves of RM state split, and the case
    usually showed up a moment later (ISSUE-2548).

    Args:
        receiver_client: Client connected to the receiver's container.
        receiver: The receiver's local ``as_Actor`` replica.
        offer: The submit-report ``as_Offer`` activity (or its id).
        timeout_seconds: Polling timeout per wait call (default 20s).

    Returns:
        The ``as_VulnerabilityCase`` replica in the receiver's own store.
    """
    offer_id = getattr(offer, "id_", str(offer))
    case: as_VulnerabilityCase | None = None

    # Gate everything on the case replica reaching this receiver's own store.
    # Dependent steps are nested inside the gate per demo_gate's scoping model,
    # so a missing replica records one clear GATE FAILED rather than a cascade of
    # 422s from work that had no case to act on.
    with demo_gate(
        f"case replica present in {receiver.id_}'s own store before"
        " validate-report"
    ):
        case = wait_for_case_for_offer(
            client=receiver_client,
            offer_id=offer_id,
            timeout_seconds=timeout_seconds,
        )
        logger.info("✓ Case replica available locally: %s", case.id_)

        receiver_validates_report(
            receiver_client=receiver_client,
            receiver=receiver,
            offer_id=offer_id,
        )

        # Gate engage-case on the receiver's OWN RM.VALID commit.
        # validate-report returns HTTP 202 before its ParticipantStatus write
        # lands, so engaging on case-object-presence alone races the async commit
        # (TransitionParticipantRMtoAccepted 422).  RM.ACCEPTED is accepted too
        # in case the state has already advanced by the time we poll.
        with demo_gate(f"{receiver.id_} reached RM.VALID before engage-case"):
            wait_for_participant_rm_state(
                client=receiver_client,
                case_id=case.id_,
                actor_id=receiver.id_,
                expected_states={RM.VALID, RM.ACCEPTED},
                timeout_seconds=timeout_seconds,
            )
            logger.info("✓ %s RM state reached VALID", receiver.id_)

            receiver_engages_case(
                receiver_client=receiver_client,
                receiver=receiver,
                case_id=case.id_,
            )

            with demo_check(f"{receiver.id_} reached RM.ACCEPTED"):
                wait_for_participant_rm_state(
                    client=receiver_client,
                    case_id=case.id_,
                    actor_id=receiver.id_,
                    expected_states={RM.ACCEPTED},
                    timeout_seconds=timeout_seconds,
                )
            logger.info("✓ %s RM state reached ACCEPTED", receiver.id_)

    if case is None:
        # demo_gate suppresses its failure so the accumulator can report it, but
        # every caller dereferences the returned case.  Fail loudly here rather
        # than letting an AttributeError surface hundreds of lines downstream.
        raise AssertionError(
            "run_direct_path_rm_triage: no VulnerabilityCase replica for offer"
            f" {offer_id!r} in {receiver.id_}'s store — the CaseActor's"
            " Create(VulnerabilityCase) never arrived (ADR-0041, PCR-01-003)"
        )
    return case
