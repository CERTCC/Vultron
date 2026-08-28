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
    _poll_until,
    resolve_case_actor_store_id,
    wait_for_event_type_in_ledger,
    wait_for_participant_rm_state,
)
from vultron.demo.utils import (
    seed_case_actor_for_report,
    DataLayerClient,
    demo_check,
    demo_gate,
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


def _provision_case_actor(receiver_client, report) -> None:
    """Provision the CaseActor this report's proposal will be addressed to.

    ``ProposeReportCaseToActorNode`` derives the CaseActor's URI from the report
    and delivery is an ordinary HTTP POST to that actor's inbox (ADR-0042). The
    inbox route resolves the actor from the store its URI names (ADR-0073), so
    the CaseActor has to be a hosted actor *before* the proposal is delivered —
    otherwise the POST answers 404 and the round-trip never starts.

    Called from both arms of :func:`reporter_submits_report`. It used to sit only
    in the ``reporter_client is None`` arm, so every scenario that passes a
    reporter client — the FV demo among them — delivered the proposal to an actor
    that did not exist. The visible symptom was two phases later and nowhere near
    the cause: "Expected as_VulnerabilityCase to be created after
    validate-report", then ``'NoneType' object has no attribute 'id_'``. Only the
    router's own delivery warning named the 404, and it is a WARNING in a passing
    step.

    Both arms need it and neither can do it earlier: the report id is not known
    until the offer exists.
    """
    report_id = getattr(report, "id_", None)
    if not isinstance(report_id, str) or not report_id:
        logger.warning(
            "_provision_case_actor: report has no id; cannot derive the"
            " CaseActor to provision, so its proposal will 404 on delivery"
        )
        return
    seed_case_actor_for_report(receiver_client, report_id)


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
        result = None
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
        offer_dict = result.get("offer", {}) if result is not None else {}
        report, offer = parse_submit_report_offer(offer_dict)
        # Deliver the offer from the reporter to the receiver's inbox.
        # Per ADR-0012 (per-actor DataLayer isolation) the trigger stores the
        # offer only in the reporter's namespace; the receiver must receive
        # it explicitly via inbox delivery so SubmitReportReceivedUseCase runs
        # and creates the case at RM.RECEIVED (ADR-0015).
        with demo_step("Deliver reporter's offer to receiver's inbox"):
            _provision_case_actor(receiver_client, report)
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
            _provision_case_actor(receiver_client, report)
            post_to_inbox_and_wait(receiver_client, receiver.id_, offer)
    # These checks name the receiver explicitly rather than relying on
    # `receiver_client`'s binding. The check text says whose replica it is about,
    # so the read should say so too — and not every caller binds its client, in
    # which case `dl_path` refuses to guess (ADR-0073).
    with demo_check("Report stored in receiver's DataLayer"):
        verify_object_stored(
            receiver_client, report.id_, actor_id=receiver.id_
        )
    with demo_check("Offer stored in receiver's DataLayer"):
        verify_object_stored(receiver_client, offer.id_, actor_id=receiver.id_)
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
    result: dict = {}
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
    result: dict = {}
    with demo_step("Receiver engages the vulnerability case"):
        result = post_to_trigger(
            client=receiver_client,
            actor_id=receiver.id_,
            behavior="engage-case",
            body={"case_id": case_id},
        )
    logger.info("Engage-case trigger result for actor %s", receiver_obj_id)
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
    created from the ledger entry by ApplyOfferReportFromLedgerNode.

    Steps:
    1. Wait for add_report_to_case ledger entry in invited actor's ledger;
       SYNC processing of this entry creates the VultronOfferRecord.
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
        auth_client: Client for the container that hosts the CaseActor (e.g.
            the coordinating actor's or vendor1_client).  The CaseActor's own
            store is what gets read through it when the case has one — see
            :func:`resolve_case_actor_store_id`; the host actor's replica is
            read only when the case has no CaseActor participant.
        case: The VulnerabilityCase.
        invited_obj: The invited actor's top-level object (used for actor_id lookup).
        timeout_seconds: Polling timeout per wait call (default 20s).
    """
    offer_id = getattr(offer, "id_", str(offer))

    # Wait for the add_report_to_case ledger entry to appear in the invited
    # actor's ledger before triggering validate-report.  This entry's SYNC
    # processing runs ApplyOfferReportFromLedgerNode, which creates the
    # VultronOfferRecord — the prerequisite for validate-report to succeed.
    with demo_check(
        "add_report_to_case ledger entry backfilled before validate-report"
    ):
        wait_for_event_type_in_ledger(
            client=invited_client,
            case_id=case.id_,
            event_type="add_report_to_case",
            timeout_seconds=timeout_seconds,
        )

    receiver_validates_report(
        receiver_client=invited_client,
        receiver=invited_actor,
        offer_id=offer_id,
    )

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
    # validate-report returns HTTP 202 before its ParticipantStatus write
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
    actor_id: str | None = None,
) -> as_VulnerabilityCase | None:
    """Load a as_VulnerabilityCase from the DataLayer, handling both IDs and dicts.

    Args:
        client: DataLayerClient for the container to query.
        item: Either a full case URI string or a raw dict to validate.
        actor_id: Whose replica to read.  Defaults to *client*'s own actor; must
            match the store the enclosing listing came from, or the id fetched
            here will be looked for in a different replica than it was found in.

    Returns:
        The ``as_VulnerabilityCase``, or ``None`` if the fetch fails.
    """
    if not isinstance(item, str):
        return as_VulnerabilityCase.model_validate(item)

    try:
        return as_VulnerabilityCase.model_validate(
            client.get(client.dl_path(item, actor_id=actor_id))
        )
    except Exception as exc:
        logger.warning("Could not fetch case %s: %s", item, exc)
        return None


def find_case_by_report_id(
    client: DataLayerClient,
    report_id: str,
    actor_id: str | None = None,
) -> Optional[as_VulnerabilityCase]:
    """Find the first ``as_VulnerabilityCase`` referencing *report_id*.

    Args:
        client: DataLayerClient connected to the container holding the case.
        report_id: Full URI of the ``as_VulnerabilityReport``.
        actor_id: Whose replica to search.  Defaults to *client*'s own actor.
            Note that under ADR-0041 the **CaseActor** authors the canonical case,
            so a caller looking for the case a report produced — rather than for
            its own replica of one — should pass the CaseActor
            (:func:`~vultron.demo.utils.case_actor_id_for_report`).  Searching the
            reporter's or vendor's store instead finds nothing until the
            CaseActor's ``Create(VulnerabilityCase)`` has been delivered and
            processed.

    Returns:
        The matching ``as_VulnerabilityCase``, or ``None`` if not found.
    """
    cases_data = client.get(
        client.dl_path("VulnerabilityCases/", actor_id=actor_id)
    )
    if not cases_data:
        return None

    for item in cases_data:
        case = _load_case_from_datalayer(client, item, actor_id=actor_id)
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
    offer_data = client.get(client.dl_path(offer_id))
    if not offer_data:
        return None

    report_id = _report_id_from_offer_data(offer_data, offer_id)
    if not report_id:
        return None

    return find_case_by_report_id(client, report_id)


def wait_for_case_for_offer(
    client: DataLayerClient,
    offer_id: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
) -> as_VulnerabilityCase:
    """Poll *client*'s own store until the case for *offer_id* is replicated.

    This is the causal precondition for ``validate-report`` (ADR-0058).  Under
    ADR-0041 the receiver does not create the case: it proposes one to the
    CaseActor, which creates the case in *its own* store (ADR-0073) and
    replicates it back as ``Create(VulnerabilityCase)``.  PCR-01-003 makes that
    the *only* route — co-locating the CaseActor on the same host grants no
    visibility into its store — so the receiver genuinely has no case until the
    replica lands, and ``RM.VALID`` is a case-scoped transition.

    Unlike the case object as observed *after* validate-report (which used to
    look synchronously available and was therefore an invalid gate, #2134), the
    replica's arrival is a real asynchronous event driven by another actor's
    outbox: exactly the kind of causal arrow ADR-0058 wants gated.

    Lives next to :func:`find_case_for_offer` rather than in ``polling.py``
    because it is that finder's polling wrapper; putting it here keeps the
    offer→report→case resolution chain in one module (ARCH-15-004).

    Args:
        client: DataLayerClient connected to the receiving actor's container.
        offer_id: Full URI of the submit-report ``as_Offer`` activity.
        timeout_seconds: Maximum time to wait for the replica.
        poll_interval: Seconds between polls.

    Returns:
        The replicated ``as_VulnerabilityCase`` from *client*'s own store.

    Raises:
        AssertionError: If the replica does not appear within *timeout_seconds*.
    """
    found: dict[str, as_VulnerabilityCase] = {}

    def _check() -> bool:
        case = find_case_for_offer(client, offer_id)
        if case is None:
            return False
        found["case"] = case
        return True

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for the VulnerabilityCase replica for offer"
        f" {offer_id!r} to arrive in the store at {client.base_url} — the"
        " CaseActor's Create(VulnerabilityCase) may not have been delivered"
        " (ADR-0041, PCR-01-003)",
        swallow_exceptions=True,
    )
    return found["case"]


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
