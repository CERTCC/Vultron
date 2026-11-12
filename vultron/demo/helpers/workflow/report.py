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

"""Report submission and the receiver's answer to the report Offer."""

import logging
from collections.abc import Callable
from datetime import datetime

from pydantic import JsonValue

from vultron.adapters.utils import parse_id
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession, WireTriggerResult
from vultron.demo.helpers.polling import (
    wait_for_participant_rm_state,
    wait_for_report_submission_stored,
    wait_for_reporter_introduction,
)
from vultron.demo.helpers.verification import (
    verify_receiver_verified_sender_key,
)
from vultron.demo.helpers.workflow.case_lookup import (
    wait_for_case_for_offer,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
    seed_case_actor,
)
from vultron.wire.as2.factories import (
    parse_submit_report_offer,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
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
    report_name: str | None = None,
    report_content: str | None = None,
    *,
    csaf_document: dict[str, JsonValue] | None = None,
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
        report_name: ``name`` of the submitted report.  ``None`` submits the
            family's report name, or, with *csaf_document*, states none, so
            the trigger names the report from the document (CSAF-04-010).
        report_content: ``content`` of the submitted report.  ``None``
            submits the family's report content.
        csaf_document: A CSAF 2.1 vulnerability report to attach, as a JSON
            object; the trigger checks it against the schema and fills the
            report's name, summary and proposed embargo end from it where the
            call states none (CSAF-04-009, CSAF-04-010).  ``None`` attaches
            nothing.

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
            report_name=(
                _DEMO_REPORT_NAME
                if report_name is None and csaf_document is None
                else report_name
            ),
            report_content=(
                _DEMO_REPORT_CONTENT
                if report_content is None
                else report_content
            ),
            recipient_id=receiver.id_,
            proposed_embargo_end_time=proposed_embargo_end_time,
            csaf_document=csaf_document,
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
    # The receiver fetched the reporter's profile, from the reporter's own
    # container, for the key that verified the Offer's proof, and recorded
    # it on the Offer's archived record (SIG-02-001, SIG-03-004).
    with demo_check(
        "Receiver verified the Offer by the key the reporter's profile"
        " publishes"
    ):
        verify_receiver_verified_sender_key(
            receiver_client,
            receiver.id_,
            offer.id_,
            reporter_client,
            reporter.id_,
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
        offer_id,
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
        offer_id,
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
    offer_id: str,
    verb: str,
    answer: Callable[[ActorSession], WireTriggerResult],
) -> dict:
    """Run one report-answer trigger for *receiver*, gated on its cause.

    The answer goes to the CASE_MANAGER of the case opened on receipt, which
    the receiver knows only once the CaseActor's ``Create(VulnerabilityCase)``
    replica reaches its own store (ADR-0041, PCR-01-007).  That replica lands
    after the report, on another actor's outbox delivery, so the trigger
    waits for it inside a ``demo_gate`` (ADR-0058, DEMOCI-01-007).  Answering
    first is refused: ``validate-report`` with HTTP 422, while
    ``invalidate-report`` addresses the reporter, whose inbox has no case to
    record it against (#5464).

    Args:
        receiver_client: Client connected to the receiver's container, bound
            to the receiver's store.
        receiver: Receiver ``as_Actor``.
        offer_id: Full URI of the submit-report ``as_Offer`` being answered.
        verb: The answer's verb, for the step label.
        answer: Posts the trigger through the receiver's session.

    Returns:
        The trigger response dict, or ``{}`` when the gate or step failed
        and was recorded.
    """
    result: dict = {}
    with demo_gate(
        f"case replica present in {receiver.id_}'s own store before it"
        f" {verb} the report"
    ):
        wait_for_case_for_offer(receiver_client, offer_id)
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
