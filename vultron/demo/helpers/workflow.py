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
and case lookup — that can be reused across rv, three-actor, and
multi-vendor demo scenarios.  Each function is named after the CVD role that
performs the action (reporter, coordinator) rather than after a scenario that
uses it.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from vultron.adapters.utils import parse_id
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession, WireTriggerResult
from vultron.demo.helpers.invite_chain import (
    DEMO_STUB_SUMMARY,
    CaseInviter,
    run_case_invite_chain,
)
from vultron.demo.helpers.polling import (
    _poll_until,
    case_actor_participant_id_in,
    find_case_actor_participant_id,
    find_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
    resolve_case_actor_store_id,
    wait_for_initialized_case,
    wait_for_participant_rm_state,
    wait_for_report_submission_stored,
    wait_for_reporter_introduction,
)
from vultron.demo.helpers.seeding import get_actor_by_id
from vultron.demo.helpers.verification import _fetch_participant
from vultron.demo.utils import (
    DataLayerClient,
    case_references_report,
    demo_check,
    demo_gate,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    read_received_activity,
    ref_id,
    seed_case_actor,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    add_report_to_case_activity,
    parse_submit_report_offer,
    reject_embargo_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)

#: The one report every scenario submits, stated once for both arms of
#: :func:`reporter_submits_report`.
_DEMO_REPORT_NAME = "Remote Code Execution in Network Stack"
_DEMO_REPORT_CONTENT = (
    "A critical remote code execution vulnerability was discovered "
    "in the network stack component. An attacker can exploit this "
    "issue to execute arbitrary code with elevated privileges."
)


def _provision_case_actor(receiver_client) -> None:
    """Provision the CaseActor the receiver's report proposal is addressed to.

    ``ProposeReportCaseToActorNode`` sends its proposal to the container's
    CaseActor, and delivery is an ordinary HTTP POST to that actor's inbox
    (ADR-0042).  The inbox route resolves the actor from the store its URI names
    (ADR-0073), so the CaseActor has to be a hosted actor *before* the Offer
    reaches the receiver -- otherwise the POST answers 404 and the round-trip
    never starts.

    The CaseActor's identity is stable: one per container, independent of the
    report (#1872, closed).  So provisioning needs no report id and runs *before*
    the ``submit-report`` trigger in both arms of :func:`reporter_submits_report`.
    It used to run after the trigger because the id was per-report; by then the
    trigger's outbox had already delivered the Offer.
    """
    seed_case_actor(receiver_client)


def reporter_submits_report(
    receiver_client: DataLayerClient,
    reporter: as_Actor,
    receiver: as_Actor,
    reporter_client: DataLayerClient,
    proposed_embargo_end_time: datetime | None = None,
    report_name: str = _DEMO_REPORT_NAME,
    report_content: str = _DEMO_REPORT_CONTENT,
) -> tuple[as_VulnerabilityReport, as_Offer]:
    """Reporter creates a vulnerability report and submits it to the receiver.

    The report and offer are created via the reporter's own ``submit-report``
    trigger, never built here and posted into the receiver's inbox
    (DEMOMA-05-001).  The trigger is where the reporter writes its trust
    anchor, the pending ``ReportCaseLink`` naming *receiver* (CBT-01-005);
    without it the reporter refuses the receiver's case introduction, because
    no trust anchor names the receiver (CBT-01-011, #4675).  It also makes the
    reporter's logs tell the full process-flow story (D5-6a).  The trigger's
    own outbox is the sole delivery of the offer to the receiver's inbox; this
    function never re-posts it.  The receiver's CaseActor has a stable
    identity (#1872), so it is provisioned before the trigger, and the
    function then waits for the report and offer to land in the receiver's
    own store (EDF-06-002, EDF-06-003).

    In a single-container exchange demo, pass the one client as both
    *receiver_client* and *reporter_client*.

    **Default embargo — no explicit negotiation required.**
    When the receiver processes the submitted report,
    ``InitializeDefaultEmbargoNode`` automatically initializes the embargo
    using the receiver's published default policy, or the configured
    protocol default when none is published (EP-04-005).  Because the reporter
    submits without a counter-proposal, this constitutes *tacit acceptance*
    of the receiver's default (EP-04-001), and the case reaches ``EM.ACTIVE``
    immediately — no ``ProposeEmbargo`` / ``AcceptEmbargo`` message exchange
    occurs.  This is intentional protocol behavior, not a missing step.  Every
    call that leaves ``proposed_embargo_end_time`` unset exercises this
    default path.

    **Negotiated path (EP-04-003).**  When ``proposed_embargo_end_time`` is
    given, the Reporter states embargo terms *with* the submission: the Offer
    carries an ``EmbargoEvent`` ending then as ``proposedEmbargo``
    (EP-04-004), and at case creation the CASE_MANAGER activates the shorter
    of those terms and the receiver's actor default, registering the longer
    as a pending revision (``EM.REVISE``).  Still no ``ProposeEmbargo`` /
    ``AcceptEmbargo`` exchange is visible — the negotiation is settled at
    creation — so a reader distinguishes the two paths by whether terms were
    stated on the Offer, not by the messages on the wire.  The
    ``report-with-embargo`` exchange demo is the negotiated path's
    demonstration.  See ``notes/embargo-default-semantics.md`` for the full
    model.

    Args:
        receiver_client: Client connected to the receiver's container.
        reporter: Reporter ``as_Actor``.
        receiver: Receiver ``as_Actor``.
        reporter_client: Client connected to the reporter's container, where
            the ``submit-report`` trigger is called.
        proposed_embargo_end_time: The Reporter's proposed embargo end for this
            report, timezone-aware and in the future; ``None`` proposes
            nothing.
        report_name: ``name`` of the submitted report.
        report_content: ``content`` of the submitted report.

    Returns:
        Tuple of ``(report, offer)``.
    """
    with demo_step("Provision the receiver's CaseActor"):
        _provision_case_actor(receiver_client)
    result = None
    with demo_step(
        "Reporter submits vulnerability report to receiver's inbox"
    ):
        result = ActorSession(
            client=reporter_client, actor=reporter
        ).submit_report(
            report_name=report_name,
            report_content=report_content,
            recipient_id=receiver.id_,
            proposed_embargo_end_time=proposed_embargo_end_time,
        )
    offer_dict = (result.offer or {}) if result is not None else {}
    report, offer = parse_submit_report_offer(offer_dict)
    # No hand delivery: the trigger's outbox already delivered the offer
    # (ADR-0012 isolation means it is stored only in the reporter's
    # namespace until that delivery lands). Gate on the effect in the
    # receiver's own store instead, naming the receiver rather than relying
    # on `receiver_client`'s binding (ADR-0073).
    with demo_check("Report and offer stored in receiver's DataLayer"):
        wait_for_report_submission_stored(
            receiver_client, receiver.id_, report.id_, offer.id_
        )
    logger.info("Report submitted: %s", ref_id(report))
    return report, offer


def verify_reporter_trusts_introduction(
    reporter_client: DataLayerClient,
    reporter: as_Actor,
    receiver: as_Actor,
    report: as_VulnerabilityReport,
    case_id: str | None = None,
) -> str | None:
    """Check the reporter took the receiver's case introduction on the trusted route.

    The receiver of a report introduces the case to the reporter with its own
    ``Create(VulnerabilityCase)`` (CBT-01-001, ADR-0132).  The reporter
    accepts it only against the anchor its ``submit-report`` trigger wrote
    (CBT-01-005), and then binds that link to the case, naming the receiver
    as ``case_creator_id``.  Every demo that submits through
    :func:`reporter_submits_report` calls this once the case exists, so the
    trusted bootstrap is shown, not assumed (#4675).

    A ``demo_check``: nothing in the exchange demos reads the result, so a
    timeout is recorded and the run goes on (EDF-06-005).

    Args:
        reporter_client: Client connected to the reporter's container.
        reporter: The report submitter.
        receiver: The actor the report was submitted to.
        report: The submitted report.
        case_id: The case the receiver opened for the report, when the demo
            knows it; the link must then be bound to that case.  ``None``
            checks only that the link is bound to some case, which is all a
            demo that also mints a second case through ``create-case`` can
            say: the introduction is of the case opened on receipt.

    Returns:
        The id of the case the reporter's link is bound to, or ``None`` when
        the check failed and was recorded.
    """
    bound_case_id = None
    with demo_check(
        "Reporter accepted the receiver's case introduction on the trusted"
        " route (CBT-01-005)"
    ):
        bound_case_id = wait_for_reporter_introduction(
            reporter_client,
            reporter.id_,
            receiver.id_,
            report.id_,
            case_id=case_id,
        )
    return bound_case_id


def receiver_validates_report(
    receiver_client: DataLayerClient,
    receiver: as_Actor,
    offer_id: str,
    note: str | None = None,
) -> dict:
    """Receiver validates the submitted report via the trigger endpoint.

    Advances RM state to VALID only.  To transition RM to ACCEPTED the
    receiver must subsequently call ``receiver_engages_case``.  The
    ``validate-report`` trigger sends the Report Valid (RV) to the
    CASE_MANAGER of the case opened on receipt; a demo never posts the RV
    into the receiver's own inbox, which refuses it (#5438).

    Args:
        receiver_client: Client connected to the receiver's container.
        receiver: Receiver ``as_Actor``.
        offer_id: Full URI of the submit-report ``as_Offer`` to validate.
        note: The Report Valid's ``content``; ``None`` sends none.

    Returns:
        Response dict from the trigger endpoint (contains the validate
        activity).
    """
    return _receiver_answers_report(
        receiver_client,
        receiver,
        "validates",
        lambda session: session.validate_report(offer_id=offer_id, note=note),
    )


def receiver_invalidates_report(
    receiver_client: DataLayerClient,
    receiver: as_Actor,
    offer_id: str,
    note: str | None = None,
) -> dict:
    """Receiver invalidates the submitted report via the trigger endpoint.

    The ``invalidate-report`` trigger sends the Report Invalid (RI),
    ``TentativeReject(Offer(VulnerabilityReport))``, to the CASE_MANAGER of
    the case opened on receipt, which records the receiver at RM.INVALID and
    replicates that to the other participants.  A demo never posts the RI
    into an inbox by hand: the receiver's own inbox refuses it, as it is not
    the CASE_MANAGER (#5438, vultron/demo/AGENTS.md).

    Args:
        receiver_client: Client connected to the receiver's container.
        receiver: Receiver ``as_Actor``.
        offer_id: Full URI of the submit-report ``as_Offer`` to invalidate.
        note: The Report Invalid's ``content``; ``None`` sends none.

    Returns:
        Response dict from the trigger endpoint (contains the invalidate
        activity).
    """
    return _receiver_answers_report(
        receiver_client,
        receiver,
        "invalidates",
        lambda session: session.invalidate_report(
            offer_id=offer_id, note=note
        ),
    )


def check_report_answer_recorded(
    client: DataLayerClient,
    reporter: as_Actor,
    receiver: as_Actor,
    offer_id: str,
    expected_states: set[RM],
) -> None:
    """Check the reporter learned *receiver*'s answer to its report Offer.

    A ``demo_check`` on the effect of a report-answer trigger (ADR-0058):
    the CASE_MANAGER of the case opened on receipt records the answer, and
    the ledger carries it to the reporter's replica.  This replaces posting
    a copy of the answer into the reporter's inbox, which refused it (#5438).

    Args:
        client: DataLayerClient for the container hosting both actors.
        reporter: The actor that submitted the report.
        receiver: The actor that answered it.
        offer_id: Full URI of the submit-report ``as_Offer``.
        expected_states: RM states that count as the answer recorded.
    """
    with demo_check(
        f"Reporter's replica records {receiver.id_} at"
        f" {sorted(str(state) for state in expected_states)}"
    ):
        wait_for_report_answer_recorded(
            client,
            receiver,
            offer_id,
            expected_states,
            store_actor_id=reporter.id_,
        )


def _receiver_answers_report(
    receiver_client: DataLayerClient,
    receiver: as_Actor,
    verb: str,
    answer: Callable[[ActorSession], WireTriggerResult],
) -> dict:
    """Run one report-answer trigger for *receiver* inside a demo step."""
    result: dict = {}
    with demo_step(f"Receiver {verb} the vulnerability report"):
        result = answer(
            ActorSession(client=receiver_client, actor=receiver).quiet()
        ).model_dump(exclude_none=True)
    logger.info(
        "Receiver %s report: trigger result for actor %s",
        verb,
        parse_id(receiver.id_)["object_id"],
    )
    return result


def wait_for_report_answer_recorded(
    client: DataLayerClient,
    receiver: as_Actor,
    offer_id: str,
    expected_states: set[RM],
    *,
    store_actor_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> as_VulnerabilityCase:
    """Wait until a store shows *receiver*'s answer to the report Offer.

    The effect a demo gates a report-answer trigger on (ADR-0058): the case
    opened on receipt records *receiver* in one of *expected_states*.  The
    CASE_MANAGER records the answer and the ledger carries it to every
    participant's replica, so reading the reporter's store shows the
    reporter learned it.

    Args:
        client: DataLayerClient for the container holding the store.
        receiver: The actor that answered the report.
        offer_id: Full URI of the submit-report ``as_Offer``.
        expected_states: RM states that count as the answer recorded.
        store_actor_id: The actor whose store to read; ``None`` reads
            *client*'s own actor's store.
        timeout_seconds: Polling timeout per wait (default 20s).

    Returns:
        The case opened on receipt, as *client*'s actor holds it.

    Raises:
        AssertionError: If the case or the answer does not appear in time.
    """
    case = wait_for_case_for_offer(
        client, offer_id, timeout_seconds=timeout_seconds
    )
    wait_for_participant_rm_state(
        client=client,
        case_id=case.id_,
        actor_id=receiver.id_,
        expected_states=expected_states,
        timeout_seconds=timeout_seconds,
        dl_actor_id=store_actor_id,
    )
    return case


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

    An invited actor joins via ``Accept(Invite(Actor, VulnerabilityCaseStub))``
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
    except Exception as exc:  # noqa: BLE001  # ruff-baseline #3326
        logger.warning("Could not fetch case %s: %s", item, exc)
        return None


def find_case_by_report_id(
    client: DataLayerClient,
    report_id: str,
    actor_id: str | None = None,
) -> as_VulnerabilityCase | None:
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

        if case_references_report(case, report_id):
            return case
    return None


def find_case_for_offer(
    client: DataLayerClient,
    offer_id: str,
) -> as_VulnerabilityCase | None:
    """Find the as_VulnerabilityCase associated with a report offer.

    The Offer is the one *client*'s actor received, read from its archive
    record (DL-06-006).

    Args:
        client: DataLayerClient connected to the container holding the case.
        offer_id: Full URI of the ``VultronActivity`` offer.

    Returns:
        The matching ``as_VulnerabilityCase``, or ``None`` if not found.
    """
    offer_data = read_received_activity(client, offer_id)
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
    because it is that lookup's polling wrapper; putting it here keeps the
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


def wait_for_case_by_report(
    client: DataLayerClient,
    report_id: str,
    actor_id: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
) -> as_VulnerabilityCase:
    """Poll *actor_id*'s store on *client* until the case for *report_id* exists.

    The canonical case is created by the CaseActor in *its own* store when it
    accepts the vendor's ``Create(CaseProposal)`` (ADR-0041, ADR-0073), some
    time after the report Offer was delivered — a background task on the
    receiver, then another on the CaseActor.  Pass the CaseActor's id to read
    the canonical case, or a participant's id to wait for that participant's
    replica of it.  This is :func:`find_case_by_report_id`'s polling wrapper
    and lives beside it for the reason :func:`wait_for_case_for_offer` gives.

    Args:
        client: DataLayerClient connected to the container hosting *actor_id*.
        report_id: Full URI of the ``as_VulnerabilityReport``.
        actor_id: Whose store to read — the CaseActor's for the canonical case.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between polls.

    Returns:
        The ``as_VulnerabilityCase`` referencing *report_id* in that store.

    Raises:
        AssertionError: If no such case appears within *timeout_seconds*.
    """
    found: dict[str, as_VulnerabilityCase] = {}

    def _check() -> bool:
        case = find_case_by_report_id(client, report_id, actor_id=actor_id)
        if case is None:
            return False
        found["case"] = case
        return True

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for a VulnerabilityCase referencing report"
        f" {report_id!r} in the store of {actor_id!r} at {client.base_url}"
        " — the CaseActor's Create(CaseProposal) handling may not have"
        " completed (ADR-0041)",
        swallow_exceptions=True,
    )
    return found["case"]


def create_case_via_trigger(
    client: DataLayerClient,
    vendor: as_Actor,
    name: str,
    content: str,
    stub_summary: str | None = None,
) -> as_VulnerabilityCase:
    """Mint a case through the ``trigger/create-case`` endpoint.

    The trigger registers *vendor* as CASE_OWNER and CASE_MANAGER
    (CM-02-014, CM-02-015).
    A case injected as ``Create(VulnerabilityCase)`` has no CASE_MANAGER, so
    the CASE_MANAGER-gated received handlers (``Add(Report, Case)``) refuse
    it.

    Returns:
        A stub ``as_VulnerabilityCase`` carrying the new case's id.
    """
    trigger_result = ActorSession(client=client, actor=vendor).create_case(
        name=name, content=content
    )
    case_id = trigger_result.case_id
    if not case_id:
        raise ValueError("create-case trigger did not return a case_id")
    verify_object_stored(client, case_id)
    return as_VulnerabilityCase.model_validate(
        {
            "id": case_id,
            "attributed_to": vendor.id_,
            "name": name,
            "content": content,
            **({"stub_summary": stub_summary} if stub_summary else {}),
        }
    )


def seat_participant_through_stub_invite(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    owner: as_Actor,
    invitee: as_Actor,
    role: CVDRole,
) -> as_CaseParticipant:
    """Seat *invitee* on *case* the one way a member joins: the stub Invite.

    *owner*, the Case Owner, asks the CASE_MANAGER to invite *invitee*
    (``Offer(Actor)``, CM-17-007); the CASE_MANAGER sends the stub Invite,
    creates the inert record, and seats *invitee* when its ``Accept``
    arrives (ADR-0114, CM-17-004).  The chain is
    :func:`~vultron.demo.helpers.invite_chain.run_case_invite_chain`, driven
    through the triggers in one container.  ``Add(CaseParticipant)`` never
    seats a member: it is the Case Owner's request to reinstate a removed
    one (CM-31-011, ADR-0116).

    Args:
        client: DataLayerClient for the container hosting every actor.
        case: The case to seat *invitee* on.
        owner: The Case Owner, who asks for the invitation.
        invitee: The actor joining the case.
        role: The CVD role the Invite names for the new member.

    Returns:
        The participant record the CASE_MANAGER created, as its store holds it.

    Raises:
        ValueError: The CASE_MANAGER's case does not seat *invitee*.
    """
    case_manager_id = _run_stub_invite_chain(
        client, case, owner, invitee, role, respond="accept"
    )
    participant = _fetch_participant(
        client, case.id_, invitee.id_, dl_actor_id=case_manager_id
    )
    if participant is None:
        raise ValueError(
            f"'{invitee.id_}' is not seated on case '{case.id_}' after"
            " accepting its stub Invite"
        )
    log_case_state(
        client, case.id_, f"after {invitee.name or invitee.id_} joined"
    )
    return participant


def invitee_declines_stub_invite(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    owner: as_Actor,
    invitee: as_Actor,
    role: CVDRole,
) -> None:
    """*owner* has *invitee* invited to *case*, and *invitee* declines.

    The reject counterpart of :func:`seat_participant_through_stub_invite`:
    the CASE_MANAGER sends the stub Invite, and *invitee* answers it with
    its own ``reject-case-invite`` trigger.  The Invite is one the
    CASE_MANAGER recorded, so the ``Reject`` is admitted from its invitee
    (EP-09-010); a hand-built Invite posted into the invitee's inbox is not,
    and its ``Reject`` is refused (#5438).

    Args:
        client: DataLayerClient for the container hosting every actor.
        case: The case *invitee* is invited to.
        owner: The Case Owner, who asks for the invitation.
        invitee: The actor that declines.
        role: The CVD role the Invite names.
    """
    _run_stub_invite_chain(
        client, case, owner, invitee, role, respond="reject"
    )


def _run_stub_invite_chain(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    owner: as_Actor,
    invitee: as_Actor,
    role: CVDRole,
    *,
    respond: Literal["accept", "reject"],
) -> str:
    """Drive the stub-Invite chain in one container; return the manager's id.

    Returns:
        The id of the actor holding CASE_MANAGER on *case*: its CaseActor,
        or *owner* when the owner is its own CASE_MANAGER.
    """
    # The CASE_MANAGER builds the stub Invite from its own copy of the case,
    # which needs a summary (CM-17-010).  A separate CaseActor is seeded by
    # the chain; an owner that is its own CASE_MANAGER is seeded here, with
    # the summary the caller gave the case when it has one.
    case_actor_id = find_case_actor_participant_id(client, case.id_)
    if case_actor_id is None:
        ActorSession(client=client, actor=owner).with_case(
            case
        ).quiet().set_stub_summary(case.stub_summary or DEMO_STUB_SUMMARY)
    run_case_invite_chain(
        case=case,
        invitee_name=invitee.name or invitee.id_,
        # The invitee's own store, where the Invite and its replica land.
        invitee_client=client.model_copy(update={"actor_id": invitee.id_}),
        invitee=invitee,
        invitee_in_own_container=invitee,
        inviter=CaseInviter(
            name=owner.name or owner.id_,
            client=client,
            actor=owner,
            role=role,
        ),
        case_manager_client=client if case_actor_id is not None else None,
        respond=respond,
    )
    return case_actor_id or owner.id_


def submit_validate_and_create_case(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    *,
    report_name: str,
    report_content: str,
    validation_note: str,
    case_name: str,
    case_content: str,
    stub_summary: str | None = None,
) -> tuple[as_VulnerabilityReport, as_VulnerabilityCase]:
    """Take a report from submission to a vendor-minted case holding it.

    The shared opening of the single-container exchange demos whose vendor
    mints its case through ``create-case`` (DEMOMA-17-001, #4770):

    1. The reporter submits the report through its own ``submit-report``
       trigger (:func:`reporter_submits_report`).
    2. The vendor validates it through its ``validate-report`` trigger
       (:func:`receiver_validates_report`), which sends the Report Valid (RV)
       to the CASE_MANAGER of the case opened on receipt (#5438).
    3. The vendor mints the case through the ``create-case`` trigger
       (:func:`create_case_via_trigger`), which seats it as CASE_OWNER and
       CASE_MANAGER.
    4. The vendor adds the report to that case.
    5. The reporter is checked to have taken the vendor's introduction of the
       case opened on receipt on the trusted route
       (:func:`verify_reporter_trusts_introduction`).

    Args:
        client: DataLayerClient for the shared container.
        reporter: The reporting ``as_Actor``.
        vendor: The receiving vendor ``as_Actor``.
        report_name: ``name`` of the submitted report.
        report_content: ``content`` of the submitted report.
        validation_note: ``content`` of the vendor's Report Valid.
        case_name: ``name`` of the minted case.
        case_content: ``content`` of the minted case.
        stub_summary: The minted case's ``stub_summary``, for a demo that
            later invites to it (CM-17-010); ``None`` sets none.

    Returns:
        Tuple of ``(report, case)``, the case being the trigger-minted one.
    """
    report, report_offer = reporter_submits_report(
        client,
        reporter,
        vendor,
        reporter_client=client,
        report_name=report_name,
        report_content=report_content,
    )

    receiver_validates_report(
        client, vendor, report_offer.id_, note=validation_note
    )

    case = create_case_via_trigger(
        client,
        vendor,
        name=case_name,
        content=case_content,
        stub_summary=stub_summary,
    )

    add_report_activity = add_report_to_case_activity(
        report, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)
    verify_reporter_trusts_introduction(client, reporter, vendor, report)
    return report, case


def setup_initialized_case(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
) -> as_VulnerabilityCase:
    """Create a fully initialised case ready for invitation/suggestion workflows.

    The vendor mints the case via the ``trigger/create-case`` endpoint, which
    registers the vendor as a participant with
    ``[CVDRole.CASE_OWNER, CVDRole.CASE_MANAGER]`` (CM-02-014, CM-02-015).
    Use :func:`setup_canonical_case` for any exchange that requires a separate
    CaseActor service identity — ownership transfer among them — or the routing
    silently degrades to the direct peer-to-peer path (a failure under CM-24-006).

    Performs the standard setup shared by ``invite_actor_demo``,
    ``suggest_actor_demo``, and ``status_updates_demo``:

    1. :func:`submit_validate_and_create_case`: the reporter submits the
       report through its own ``submit-report`` trigger, which writes the
       anchor it checks the vendor's case introduction against (CBT-01-005);
       the vendor validates it, creates the case through the trigger endpoint
       (registering CASE_OWNER+CASE_MANAGER) and adds the report to it; and
       the reporter is checked to have taken the vendor's introduction of the
       case it created on receipt on the trusted route
    2. Vendor asks the CASE_MANAGER (itself) to invite the reporter, which
       sends the stub Invite
    3. Reporter accepts, which seats it as REPORTER (ADR-0114, ADR-0078;
       ``Add(CaseParticipant)`` only reinstates, CM-31-011)
    4. Logs final case state

    Args:
        client: DataLayerClient for the shared (or single) container.
        reporter: The reporter ``as_Actor``.
        vendor: The receiving vendor ``as_Actor`` who creates the case.

    Returns:
        The newly created ``as_VulnerabilityCase``.
    """
    _report, case = submit_validate_and_create_case(
        client,
        reporter,
        vendor,
        report_name="Remote Code Execution Vulnerability",
        report_content=(
            "A remote code execution vulnerability in the web framework."
        ),
        validation_note=(
            "Confirmed — remote code execution via unsanitized input."
        ),
        case_name="RCE Case — Web Framework",
        case_content="Tracking the RCE vulnerability in the web framework.",
        stub_summary=(
            "Remote code execution in web framework"
            " — details shared after acceptance."
        ),
    )

    seat_participant_through_stub_invite(
        client, case, owner=vendor, invitee=reporter, role=CVDRole.REPORTER
    )

    log_case_state(client, case.id_, "after setup")
    logger.info(
        "✓ Setup: Case initialized with report and reporter participant"
    )
    return case


def setup_canonical_case(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    report_name: str,
    report_content: str,
    validation_content: str,
) -> tuple[as_VulnerabilityCase, str]:
    """Create a **CaseActor-owned** case and return it with the CaseActor's URI.

    Unlike :func:`setup_initialized_case`, which has the vendor mint the case
    itself, this drives the canonical path: the reporter submits a report
    through its own ``submit-report`` trigger, the vendor validates it,
    ``ProposeReportCaseToActorNode`` sends a ``Create(CaseProposal)`` to the
    CaseActor, and the CaseActor creates the ``VulnerabilityCase``,
    registering vendor (``CASE_OWNER``), reporter, and itself
    (``CASE_MANAGER``) as the initial participants (ADR-0041, CP-01-004).
    The vendor then introduces the case to the reporter, which accepts it on
    the trusted route (CBT-01-001, CBT-01-005).

    Any exchange that must route through the CaseActor — the ownership-transfer
    handshake (ADR-0053, CM-21-005/006) among them — needs this setup rather
    than :func:`setup_initialized_case`: a vendor-minted case has **no**
    ``CASE_MANAGER`` participant, so there is no CaseActor to address and the
    routing silently degrades to the direct peer-to-peer path it is meant to
    replace (a failure under CM-24-006).

    Args:
        client: DataLayerClient for the container hosting all three actors.
        reporter: The reporter ``as_Actor`` who submits the report.
        vendor: The receiving vendor ``as_Actor`` who validates it.
        report_name: ``name`` for the submitted ``as_VulnerabilityReport``.
        report_content: ``content`` for the submitted report.
        validation_content: ``content`` for the vendor's validation activity.

    Returns:
        ``(case, case_actor_id)`` — the canonical case as the CaseActor holds
        it, and the URI of the actor that actually holds ``CASE_MANAGER`` on it.

    Raises:
        AssertionError: If the created case has no resolvable CaseActor
            participant.  Returning the config-derived URI instead would let a
            caller address an actor that is not this case's manager, and the
            symptom lands far away: the CM-gated forward skips silently, and the
            dependent gate times out reporting a delivery problem.
    """
    report, report_offer = reporter_submits_report(
        client,
        reporter,
        vendor,
        reporter_client=client,
        report_name=report_name,
        report_content=report_content,
    )

    receiver_validates_report(
        client, vendor, report_offer.id_, note=validation_content
    )

    case = wait_for_initialized_case(client, report.id_)
    verify_reporter_trusts_introduction(
        client, reporter, vendor, report, case_id=case.id_
    )
    # Attach a stub_summary so demo Invites carry the required non-empty
    # summary (CM-17-010, MV-10-001, #4165).  The BT-created case never has
    # this field; set it on the local object before any Invite factory call.
    case = case.model_copy(
        update={
            "stub_summary": (
                f"{report_name} — details shared after acceptance."
            )
        }
    )
    # Resolve the CaseActor from the case's own participant index, not from
    # config: `case_actor_id_for_report` answers "which CaseActor would *this
    # node* address", which is a different question and returns `""` when no
    # CaseActor service is configured.  What callers need is the actor that holds
    # CASE_MANAGER on this case.
    case_actor_id = case_actor_participant_id_in(case)
    assert case_actor_id, (
        f"canonical case {case.id_!r} has no CaseActor participant —"
        " ProposeReportCaseToActorNode did not complete, or the CaseActor"
        " registered itself under an unexpected identity"
    )
    logger.info(
        "✓ Setup: canonical case %s created by CaseActor %s",
        case.id_,
        case_actor_id,
    )
    return case, case_actor_id


def await_ownership_transfer_offer(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    transferee: as_Actor,
    timeout_seconds: float = 90.0,
) -> str:
    """Gate on the CaseActor's ownership-transfer Offer; return its id.

    The owner addresses its proposal, ``Offer(Offer(VulnerabilityCase))``, to
    the CaseActor, which makes the one ``Offer(VulnerabilityCase)`` of the
    transfer under an id of its own and sends it to the transferee (CM-21-005,
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


def _send_owner_embargo_decision(
    client: DataLayerClient,
    owner: as_Actor,
    case_manager_id: str,
    case: as_VulnerabilityCase,
    embargo: as_EmbargoEvent,
    *,
    accept: bool,
    summary: str,
) -> None:
    """Send the case owner's decision on a proposal to the CASE_MANAGER.

    The owner decides for the case with ``Accept`` or ``Reject`` of the
    ``EmbargoEvent`` itself, the case as ``target`` (ADR-0122) — never of
    the Invite that proposed it, which is only the owner's own consent.
    """
    build = (
        activate_embargo_activity
        if accept
        else reject_embargo_proposal_activity
    )
    decision = build(
        embargo,
        actor=owner.id_,
        target=case.id_,
        context=case.id_,
        to=[case_manager_id],
        summary=summary,
    )
    logger.info(
        "Sending the owner's %s: %s",
        "activation" if accept else "rejection",
        logfmt(decision),
    )
    post_to_inbox_and_wait(client, case_manager_id, decision)


def owner_activates_embargo(
    client: DataLayerClient,
    owner: as_Actor,
    case_manager_id: str,
    case: as_VulnerabilityCase,
    embargo: as_EmbargoEvent,
) -> None:
    """The case owner activates a proposed embargo (EA / EC, ADR-0122)."""
    _send_owner_embargo_decision(
        client,
        owner,
        case_manager_id,
        case,
        embargo,
        accept=True,
        summary=f"Activating the proposed embargo for {case.name}.",
    )


def owner_rejects_embargo_proposal(
    client: DataLayerClient,
    owner: as_Actor,
    case_manager_id: str,
    case: as_VulnerabilityCase,
    embargo: as_EmbargoEvent,
) -> None:
    """The case owner rejects a proposed embargo (ER / EJ, ADR-0122)."""
    _send_owner_embargo_decision(
        client,
        owner,
        case_manager_id,
        case,
        embargo,
        accept=False,
        summary=f"Rejecting the proposed embargo for {case.name}.",
    )
