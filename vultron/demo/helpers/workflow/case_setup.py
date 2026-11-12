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

"""Case creation and the stub-Invite chain that seats a participant."""

import logging
from typing import Literal

from vultron.demo import wall_clock
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.invite_chain import (
    DEMO_STUB_SUMMARY,
    CaseInviter,
    run_case_invite_chain,
)
from vultron.demo.helpers.polling import (
    case_actor_participant_id_in,
    find_case_actor_participant_id,
    wait_for_initialized_case,
)
from vultron.demo.helpers.verification.participants import (
    _fetch_participant,
)
from vultron.demo.helpers.workflow.report import (
    receiver_validates_report,
    reporter_submits_report,
    verify_reporter_trusts_introduction,
)
from vultron.demo.utils import (
    DataLayerClient,
    log_case_state,
    post_to_inbox_and_wait,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_report_to_case_activity,
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
    the CASE_MANAGER-gated received handlers
    (``Add(VulnerabilityReport)[target=VulnerabilityCase]``) refuse it.

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
) -> str:
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

    Returns:
        The id of the actor holding CASE_MANAGER on *case*, whose store
        holds *invitee*'s closed inert record (CM-11-007).
    """
    return _run_stub_invite_chain(
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
        report, actor=vendor.id_, target=case.id_, at=wall_clock.now()
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
    silently degrades to the direct peer-to-peer path (a failure under CM-24-014).

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
    replace (a failure under CM-24-014).

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
    # node* address", which is a different question and raises when no
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
