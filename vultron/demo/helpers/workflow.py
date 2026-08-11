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

"""Workflow step helpers shared across demo scenarios.

Provides generic CVD workflow actions — report submission, report validation,
and case lookup — that can be reused across FV, three-actor, and
multi-vendor demo scenarios.  Each function is named after the CVD role that
performs the action (reporter, coordinator) rather than any scenario-specific
persona (finder, vendor).
"""

import logging
from typing import Optional, Tuple

from vultron.adapters.utils import parse_id
from vultron.core.states.rm import RM
from vultron.demo.helpers.polling import (
    wait_for_event_type_in_ledger,
    wait_for_participant_rm_state,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    post_to_inbox_and_wait,
    post_to_trigger,
    ref_id,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    add_report_to_case_activity,
    create_case_activity,
    parse_submit_report_offer,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def reporter_submits_report(
    receiver_client: DataLayerClient,
    reporter: as_Actor,
    receiver: as_Actor,
    reporter_client: Optional[DataLayerClient] = None,
) -> Tuple[as_VulnerabilityReport, as_Offer]:
    """Reporter creates a vulnerability report and submits it to the receiver.

    When ``reporter_client`` is provided (e.g. in a multi-container Docker
    demo), the report and offer are created via the reporter container's
    ``submit-report`` trigger endpoint so that the reporter container logs tell
    the full process-flow story (D5-6a).  The resulting offer is then delivered
    to the receiver container's inbox.

    When ``reporter_client`` is ``None`` (e.g. single-container integration
    tests), the report and offer are constructed in memory and posted directly
    to the receiver container (backward-compatible path).

    **Default embargo — no explicit negotiation required.**
    When the receiver processes the submitted report,
    ``InitializeDefaultEmbargoNode`` automatically initializes the embargo
    using the receiver's published default policy.  Because the reporter
    submits without a counter-proposal, this constitutes *tacit acceptance*
    of the receiver's default (EP-04-001), and the case reaches ``EM.ACTIVE``
    immediately — no ``ProposeEmbargo`` / ``AcceptEmbargo`` message exchange
    occurs.  This is intentional protocol behavior, not a missing step.  All
    demo scenarios that call this function exercise this default path.  A
    demo that includes an explicit embargo-negotiation round-trip is
    implementing the *negotiated path* (EP-04-003), which is distinct.
    See ``notes/embargo-default-semantics.md`` for the full model.

    Args:
        receiver_client: Client connected to the receiver's container.
        reporter: Reporter ``as_Actor``.
        receiver: Receiver ``as_Actor``.
        reporter_client: Optional client connected to the reporter container.
            When provided, the submit-report trigger is called on the reporter
            container; when absent the legacy in-memory path is used.

    Returns:
        Tuple of ``(report, offer)``.
    """
    if reporter_client is not None:
        report_name = "Remote Code Execution in Network Stack"
        report_content = (
            "A critical remote code execution vulnerability was discovered "
            "in the network stack component. An attacker can exploit this "
            "issue to execute arbitrary code with elevated privileges."
        )
        with demo_step(
            "Reporter submits vulnerability report to receiver's inbox"
        ):
            result = post_to_trigger(
                client=reporter_client,
                actor_id=reporter.id_,
                behavior="submit-report",
                body={
                    "report_name": report_name,
                    "report_content": report_content,
                    "recipient_id": receiver.id_,
                },
            )
        offer_dict = result.get("offer", {})
        report, offer = parse_submit_report_offer(offer_dict)
        # Deliver the offer from the reporter to the receiver's inbox.
        # Per ADR-0012 (per-actor DataLayer isolation) the trigger stores the
        # offer only in the reporter's namespace; the receiver must receive
        # it explicitly via inbox delivery so SubmitReportReceivedUseCase runs
        # and creates the case at RM.RECEIVED (ADR-0015).
        with demo_step("Deliver reporter's offer to receiver's inbox"):
            post_to_inbox_and_wait(receiver_client, receiver.id_, offer)
    else:
        report = as_VulnerabilityReport(
            attributed_to=reporter.id_,
            name="Remote Code Execution in Network Stack",
            content=(
                "A critical remote code execution vulnerability was discovered "
                "in the network stack component. An attacker can exploit this "
                "issue to execute arbitrary code with elevated privileges."
            ),
        )
        offer = rm_submit_report_activity(
            report,
            actor=reporter.id_,
            target=receiver.id_,
            to=receiver.id_,
        )
        with demo_step(
            "Reporter submits vulnerability report to receiver's inbox"
        ):
            post_to_inbox_and_wait(receiver_client, receiver.id_, offer)
    with demo_check("Report stored in receiver's DataLayer"):
        verify_object_stored(receiver_client, report.id_)
    with demo_check("Offer stored in receiver's DataLayer"):
        verify_object_stored(receiver_client, offer.id_)
    logger.info("Report submitted: %s", ref_id(report))
    return report, offer


def receiver_validates_report(
    receiver_client: DataLayerClient,
    receiver: as_Actor,
    offer_id: str,
) -> dict:
    """Receiver validates the submitted report via the trigger endpoint.

    Advances RM state to VALID only.  To transition RM to ACCEPTED the
    receiver must subsequently call ``receiver_engages_case``.

    Args:
        receiver_client: Client connected to the receiver's container.
        receiver: Receiver ``as_Actor``.
        offer_id: Full URI of the submit-report ``as_Offer`` to validate.

    Returns:
        Response dict from the trigger endpoint (contains the validate
        activity).
    """
    receiver_obj_id = parse_id(receiver.id_)["object_id"]
    with demo_step("Receiver validates the vulnerability report"):
        result = post_to_trigger(
            client=receiver_client,
            actor_id=receiver.id_,
            behavior="validate-report",
            body={"offer_id": offer_id},
        )
    logger.info("Validate-report trigger result for actor %s", receiver_obj_id)
    return result


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
    with demo_step("Receiver engages the vulnerability case"):
        result = post_to_trigger(
            client=receiver_client,
            actor_id=receiver.id_,
            behavior="engage-case",
            body={"case_id": case_id},
        )
    logger.info("Engage-case trigger result for actor %s", receiver_obj_id)
    return result


def seed_offer_record_for_actor(
    client: DataLayerClient,
    actor: as_Actor,
    offer_id: str,
    report_id: str,
    offer_actor_id: str,
) -> dict:
    """Seed a VultronOfferRecord on an invited actor's DataLayer (CM-11-002).

    Invited actors (e.g. Vendor2) join a case via invite-accept and do not
    receive an Offer(Report) directly, so their DataLayer has no
    VultronOfferRecord.  This endpoint seeds the record so they can call
    ``validate-report`` to run the standard RM triage cycle.

    Only valid in ``RunMode.PROTOTYPE``.

    Args:
        client: Client connected to the actor's container.
        actor: The actor whose DataLayer will be seeded.
        offer_id: Full URI of the original submit-report Offer activity.
        report_id: Full URI of the VulnerabilityReport in the case.
        offer_actor_id: Full URI of the actor that originally submitted the
            Offer (the reporter/finder).

    Returns:
        Response dict from the seed endpoint.
    """
    actor_obj_id = parse_id(actor.id_)["object_id"]
    with demo_step(
        "Seeding offer record for invited actor (CM-11-002 triage)"
    ):
        result = post_to_trigger(
            client=client,
            actor_id=actor.id_,
            behavior="seed-offer-record",
            path_prefix="demo",
            body={
                "offer_id": offer_id,
                "report_id": report_id,
                "offer_actor_id": offer_actor_id,
            },
        )
    logger.info(
        "Offer record seeded for actor %s: offer=%s", actor_obj_id, offer_id
    )
    return result


def run_invite_path_rm_triage(
    invited_client: DataLayerClient,
    invited_actor: as_Actor,
    offer: object,
    report: as_VulnerabilityReport,
    finder: as_Actor,
    auth_client: DataLayerClient,
    case: as_VulnerabilityCase,
    invited_obj: as_Actor,
    timeout_seconds: float = 20.0,
) -> None:
    """Run the full RM triage cycle for an invite-path participant (CM-11-002).

    Invited actors join via Accept(Invite) and receive the case via
    Announce(VulnerabilityCase) with embedded reports + the canonical
    Offer(VulnerabilityReport) ledger backfill.  The VultronOfferRecord is
    created from the ledger entry by ApplyOfferReportFromLedgerNode — no
    spoofing via seed-offer-record is needed or permitted.

    Steps:
    1. Wait for submit_report ledger entry to be backfilled and processed
       (ensures VultronOfferRecord exists before validate-report fires).
    2. Trigger validate-report (RM → VALID).
    3. Poll until CaseActor reflects RM.VALID or RM.ACCEPTED.
    4. Trigger engage-case (RM → ACCEPTED).
    5. Poll until CaseActor reflects RM.ACCEPTED.

    Args:
        invited_client: Client for the invited actor's container.
        invited_actor: The invited actor's local replica (e.g. vendor2_in_vendor2).
        offer: The original submit-report Offer activity.
        report: The VulnerabilityReport in the case.
        finder: The actor that originally submitted the Offer (unused; kept for
            call-site compatibility).
        auth_client: Client for an actor that can see the CaseActor state
            (e.g. the coordinating actor or vendor1_client).
        case: The VulnerabilityCase.
        invited_obj: The invited actor's top-level object (used for actor_id lookup).
        timeout_seconds: Polling timeout per wait call (default 20s).
    """
    offer_id = getattr(offer, "id_", str(offer))

    # Wait for the submit_report ledger entry to be backfilled and processed
    # by ApplyOfferReportFromLedgerNode before triggering validate-report.
    # Without this wait, validate-report fires before VultronOfferRecord exists
    # and the trigger returns 404 (Offer not found).
    with demo_check("submit_report ledger entry backfilled to invited actor"):
        wait_for_event_type_in_ledger(
            client=invited_client,
            case_id=case.id_,
            event_type="submit_report",
            timeout_seconds=timeout_seconds,
        )

    receiver_validates_report(
        receiver_client=invited_client,
        receiver=invited_actor,
        offer_id=offer_id,
    )

    with demo_check(f"CaseActor reflects {invited_obj.id_} at RM.VALID"):
        wait_for_participant_rm_state(
            client=auth_client,
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

    with demo_check(f"CaseActor reflects {invited_obj.id_} at RM.ACCEPTED"):
        wait_for_participant_rm_state(
            client=auth_client,
            case_id=case.id_,
            actor_id=invited_obj.id_,
            expected_states={RM.ACCEPTED},
            timeout_seconds=timeout_seconds,
        )
    logger.info("✓ %s RM state reached ACCEPTED", invited_obj.id_)


def _report_id_from_offer_data(
    offer_data: dict[str, object],
    offer_id: str,
) -> str | None:
    """Extract the report ID referenced by an offer.

    Args:
        offer_data: Raw dict representation of the offer from the DataLayer.
        offer_id: Full URI of the offer (used in warning log only).

    Returns:
        The report ID string, or ``None`` if the offer does not reference a
        report object.
    """
    offer_object = offer_data.get("object")
    if isinstance(offer_object, str):
        return offer_object
    if isinstance(offer_object, dict):
        return offer_object.get("id")

    report_id = ref_id(offer_object)
    if report_id:
        return report_id

    logger.warning("Offer %s does not reference a report object", offer_id)
    return None


def _load_case_from_datalayer(
    client: DataLayerClient,
    item: str | dict[str, object],
) -> as_VulnerabilityCase | None:
    """Load a as_VulnerabilityCase from the DataLayer, handling both IDs and dicts.

    Args:
        client: DataLayerClient for the container to query.
        item: Either a full case URI string or a raw dict to validate.

    Returns:
        The ``as_VulnerabilityCase``, or ``None`` if the fetch fails.
    """
    if not isinstance(item, str):
        return as_VulnerabilityCase.model_validate(item)

    try:
        return as_VulnerabilityCase.model_validate(
            client.get(f"/datalayer/{item}")
        )
    except Exception as exc:
        logger.warning("Could not fetch case %s: %s", item, exc)
        return None


def find_case_by_report_id(
    client: DataLayerClient,
    report_id: str,
) -> Optional[as_VulnerabilityCase]:
    """Find the first ``as_VulnerabilityCase`` referencing *report_id*.

    Args:
        client: DataLayerClient connected to the container holding the case.
        report_id: Full URI of the ``as_VulnerabilityReport``.

    Returns:
        The matching ``as_VulnerabilityCase``, or ``None`` if not found.
    """
    cases_data = client.get("/datalayer/VulnerabilityCases/")
    if not cases_data:
        return None

    for item in cases_data:
        case = _load_case_from_datalayer(client, item)
        if case is None:
            continue

        report_ids = [
            (
                report
                if isinstance(report, str)
                else getattr(report, "id_", str(report))
            )
            for report in (case.vulnerability_reports or [])
        ]
        if report_id in report_ids:
            return case
    return None


def find_case_for_offer(
    client: DataLayerClient,
    offer_id: str,
) -> Optional[as_VulnerabilityCase]:
    """Find the as_VulnerabilityCase associated with a report offer.

    Args:
        client: DataLayerClient connected to the container holding the case.
        offer_id: Full URI of the ``VultronActivity`` offer.

    Returns:
        The matching ``as_VulnerabilityCase``, or ``None`` if not found.
    """
    offer_data = client.get(f"/datalayer/{offer_id}")
    if not offer_data:
        return None

    report_id = _report_id_from_offer_data(offer_data, offer_id)
    if not report_id:
        return None

    return find_case_by_report_id(client, report_id)


def setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> as_VulnerabilityCase:
    """Create a fully initialised case ready for invitation/suggestion workflows.

    Performs the standard 7-step setup shared by ``invite_actor_demo``,
    ``suggest_actor_demo``, and ``transfer_ownership_demo``:

    1. Finder submits report → vendor inbox
    2. Vendor validates the report
    3. Vendor creates the case
    4. Vendor adds the report to the case
    5. Vendor creates the finder participant record
    6. Vendor adds the finder participant to the case
    7. Logs final case state

    Args:
        client: DataLayerClient for the shared (or single) container.
        finder: The finder/reporter ``as_Actor``.
        vendor: The receiving vendor ``as_Actor`` who creates the case.

    Returns:
        The newly created ``as_VulnerabilityCase``.
    """
    report = as_VulnerabilityReport(
        attributed_to=finder.id_,
        content="A remote code execution vulnerability in the web framework.",
        name="Remote Code Execution Vulnerability",
    )
    report_offer = rm_submit_report_activity(
        report, actor=finder.id_, to=vendor.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = rm_validate_report_activity(
        offer,
        actor=vendor.id_,
        content="Confirmed — remote code execution via unsanitized input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = as_VulnerabilityCase(
        attributed_to=vendor.id_,
        name="RCE Case — Web Framework",
        content="Tracking the RCE vulnerability in the web framework.",
    )
    create_case_act = create_case_activity(case, actor=vendor.id_)
    post_to_inbox_and_wait(client, vendor.id_, create_case_act)
    verify_object_stored(client, case.id_)

    add_report_activity = add_report_to_case_activity(
        report, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    participant = as_CaseParticipant(
        case_roles=[CVDRole.FINDER, CVDRole.REPORTER],
        attributed_to=finder.id_,
        context=case.id_,
    )
    create_participant_activity = as_Create(
        actor=vendor.id_,
        object_=participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_participant_activity)
    verify_object_stored(client, participant.id_)

    add_participant_activity = add_participant_to_case_activity(
        participant, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)

    log_case_state(client, case.id_, "after setup")
    logger.info("✓ Setup: Case initialized with report and finder participant")
    return case


def setup_two_participant_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> as_VulnerabilityCase:
    """Create a case with two participants (vendor + coordinator) as a precondition.

    Performs the 6-step shared setup used by ``establish_embargo_demo`` and
    ``manage_embargo_demo``:

    1. Finder submits report → vendor inbox
    2. Vendor validates the report
    3. Vendor creates the case
    4. Vendor adds the report to the case
    5. Vendor creates and adds the finder participant
    6. Vendor invites coordinator; coordinator accepts → coordinator added

    Args:
        client: DataLayerClient for the shared (or single) container.
        finder: The finder/reporter ``as_Actor``.
        vendor: The receiving vendor ``as_Actor`` who creates the case.
        coordinator: The coordinator ``as_Actor`` to invite.

    Returns:
        The newly created ``as_VulnerabilityCase`` with vendor and coordinator
        as participants.
    """
    report = as_VulnerabilityReport(
        attributed_to=finder.id_,
        content="A use-after-free vulnerability in the network stack.",
        name="Use-After-Free in Network Stack",
    )
    report_offer = rm_submit_report_activity(
        report, actor=finder.id_, to=vendor.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = rm_validate_report_activity(
        offer,
        actor=vendor.id_,
        content="Confirmed — use-after-free via unsanitized network input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = as_VulnerabilityCase(
        attributed_to=vendor.id_,
        name="UAF Case — Network Stack",
        content="Tracking the use-after-free vulnerability in the network stack.",
    )
    create_case_act = create_case_activity(case, actor=vendor.id_)
    post_to_inbox_and_wait(client, vendor.id_, create_case_act)
    verify_object_stored(client, case.id_)

    add_report_activity = add_report_to_case_activity(
        report, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    participant = as_CaseParticipant(
        case_roles=[CVDRole.FINDER, CVDRole.REPORTER],
        attributed_to=finder.id_,
        context=case.id_,
    )
    create_participant_activity = as_Create(
        actor=vendor.id_,
        object_=participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_participant_activity)
    verify_object_stored(client, participant.id_)

    add_participant_activity = add_participant_to_case_activity(
        participant, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)

    invite = rm_invite_to_case_activity(
        coordinator,
        actor=vendor.id_,
        target=case.id_,
        to=[coordinator.id_],
        content=f"Inviting you to participate in {case.name}.",
    )
    post_to_inbox_and_wait(client, coordinator.id_, invite)

    accept = rm_accept_invite_to_case_activity(
        invite,
        actor=coordinator.id_,
        to=[vendor.id_],
        content=f"Accepting invitation to {case.name}.",
    )
    post_to_inbox_and_wait(client, vendor.id_, accept)

    log_case_state(client, case.id_, "after setup (two participants)")
    logger.info(
        "✓ Setup: Case initialized with vendor and coordinator participants"
    )
    return case
