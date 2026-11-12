#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.core.models.case_reference import CaseReferenceLink
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    accept_case_participant_role_activity,
    add_case_reference_to_case_activity,
    add_report_to_case_activity,
    add_vulnerability_item_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    offer_case_ownership_transfer_activity,
    offer_case_participant_role_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    reject_case_participant_role_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    undo_case_ownership_transfer_activity,
    update_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Undo,
    as_Update,
)
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    _REPORT,
    _VENDOR,
    EXAMPLE_TIMESTAMP,
    _example_stamp,
    case,
    case_actor,
    gen_report,
    vendor,
)
from vultron.wire.as2.vocab.examples.participant import (
    finder_participant,
    vendor_participant,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_reference import as_CaseReference
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_item import (
    as_VulnerabilityItem,
)


def create_case() -> as_Create:
    """The bootstrap ``Create(VulnerabilityCase)``, every object it introduces inline.

    A receiver seeds its replica from this one activity, so the participant
    travels as an object, not an id (CBT-01-007).  The report travels inline
    too, a choice of this prototype: the receiver offered it, so the protocol
    lets the bootstrap name it by id (AKM-02-004).
    """
    participant = as_CaseParticipant(
        case_roles=[CVDRole.VENDOR],
        attributed_to=_VENDOR.id_,
        name=_VENDOR.name,
        **_example_stamp(),
    )
    _case = case(
        fresh_id=True,
        vulnerability_reports=[_REPORT],
        case_participants=[participant],
    )

    activity = create_case_activity(
        _case,
        actor=_VENDOR.id_,
        content="We've created a case from this report.",
        context=_REPORT.id_,
        at=EXAMPLE_TIMESTAMP,
    )
    return activity


def populated_case() -> as_VulnerabilityCase:
    """A case object carrying its report and its finder and vendor participants.

    Most example functions return an activity. This one returns the case
    *object* itself, so the documentation can show what a case looks like once
    a report has been filed and the finder and vendor have joined.

    It keeps the shared `case()` id rather than minting a fresh one, because the
    participant records are built against `case()` too: a case whose id differed
    from its own participants' ``context`` would be an incoherent example.
    """
    participants = [finder_participant(), vendor_participant()]
    return case(
        vulnerability_reports=[gen_report()],
        case_participants=participants,
        actor_participant_index={p.attributed_to: p.id_ for p in participants},
    )


def add_report_to_case() -> as_Add:
    _vendor = vendor()
    _report = gen_report()
    _case = case()

    activity = add_report_to_case_activity(
        _report,
        actor=_vendor.id_,
        target=_case.id_,
        content="We're adding this report to this case.",
        at=EXAMPLE_TIMESTAMP,
    )
    return activity


def engage_case() -> as_Join:
    _vendor = vendor()
    _case = case()

    activity = rm_engage_case_activity(
        _case,
        actor=_vendor.id_,
        content="We're engaging this case.",
        at=EXAMPLE_TIMESTAMP,
    )
    return activity


def close_case() -> as_Leave:
    _vendor = vendor()
    _case = case()

    activity = rm_close_case_activity(
        _case,
        actor=_vendor.id_,
        content="We're closing this case.",
        at=EXAMPLE_TIMESTAMP,
    )
    return activity


def defer_case() -> as_Ignore:
    _vendor = vendor()
    _case = case()

    activity = rm_defer_case_activity(
        _case,
        actor=_vendor.id_,
        content="We're deferring this case.",
        at=EXAMPLE_TIMESTAMP,
    )
    return activity


def reengage_case() -> as_Join:
    _vendor = vendor()
    _case = case()

    activity = rm_engage_case_activity(
        _case,
        actor=_vendor.id_,
        content="We're reengaging this case.",
        at=EXAMPLE_TIMESTAMP,
    )
    return activity


def propose_case_ownership_transfer() -> as_Offer:
    """The Case Owner's proposal: Offer(Offer(VulnerabilityCase)) (ADR-0148).

    Addressed to the Case Manager, which makes the inner Offer itself, under
    its own id (:func:`offer_case_ownership_transfer`).
    """
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _activity = propose_case_ownership_transfer_activity(
        _case,
        target=_coordinator.id_,
        actor=_vendor.id_,
        to=[case_actor().id_],
        content=f"Please offer ownership of case {_case.name} to the coordinator.",
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def offer_case_ownership_transfer() -> as_Offer:
    """The Case Manager's Offer, made from the owner's proposal (ADR-0148).

    ``actor`` is the Case Manager and ``attributedTo`` the Case Owner whose
    proposal it carries out (CM-24-001, CM-24-002).
    """
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _activity = offer_case_ownership_transfer_activity(
        _case,
        actor=case_actor().id_,
        attributed_to=_vendor.id_,
        target=_coordinator.id_,
        to=[_coordinator.id_],
        content=f"We're offering to transfer ownership of case {_case.name} to you.",
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def accept_case_ownership_transfer() -> as_Accept:
    _case = case()
    _coordinator = _COORDINATOR
    _offer = offer_case_ownership_transfer()
    _activity = accept_case_ownership_transfer_activity(
        _offer,
        actor=_coordinator.id_,
        content=f"We're accepting your offer to transfer ownership of case {_case.name} to us.",
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def reject_case_ownership_transfer() -> as_Reject:
    _case = case()
    _coordinator = _COORDINATOR
    _offer = offer_case_ownership_transfer()
    _activity = reject_case_ownership_transfer_activity(
        _offer,
        actor=_coordinator.id_,
        content=f"We're declining your offer to transfer ownership of case {_case.name} to us.",
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def undo_case_ownership_transfer() -> as_Undo:
    _case = case()
    _vendor = vendor()
    _proposal = propose_case_ownership_transfer()
    _activity = undo_case_ownership_transfer_activity(
        _proposal,
        actor=_vendor.id_,
        to=[case_actor().id_],
        content=f"We're withdrawing our proposal to transfer ownership of case {_case.name}.",
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def update_case() -> as_Update:
    """The CASE_MANAGER's ``Update(VulnerabilityCase)`` naming a new owner.

    On an ownership transfer the CASE_MANAGER commits the case with its new
    ``attributed_to`` as its own ``update_case_owner`` entry (CM-21-024,
    CLP-07-013).  No received use case handles it (ADR-0140 item 5), so the
    example is authored by the case actor and carries no sender-voice
    ``content``.
    """
    _case = case()

    _activity = update_case_activity(
        _case,
        actor=case_actor().id_,
        at=EXAMPLE_TIMESTAMP,
    )
    return _activity


def add_vulnerability_item_to_case() -> as_Add:
    """The CASE_MANAGER's ``Add(VulnerabilityItem)`` of an item to the case.

    A case created from a CSAF report takes an item for each vulnerability
    the report names (CSAF-03-008), and the CASE_MANAGER commits each in full
    as its own ``add_vulnerability_item_to_case`` entry after the genesis
    entry (CLP-07-021).  It is addressed to nobody: each participant takes
    the item from the ledger.
    """
    _case = case()
    item = as_VulnerabilityItem(
        id_=f"{_case.id_}/items/1",
        cve="CVE-2026-0001",
        title="Buffer overflow in the widget parser",
        context=_case.id_,
    )
    return add_vulnerability_item_to_case_activity(
        item,
        target=_case.id_,
        id_=f"{item.id_}/add",
        actor=case_actor().id_,
    )


def add_case_reference_to_case() -> as_Add:
    """The CASE_MANAGER's ``Add(CaseReference)`` of a reference to the case.

    A case created from a CSAF report takes a reference for each of the
    report's document-level references (CSAF-03-009), committed in full as
    its own ``add_case_reference_to_case`` entry (CLP-07-021).
    """
    _case = case()
    reference = as_CaseReference(
        id_=f"{_case.id_}/references/1",
        url=CaseReferenceLink(
            href="https://example.org/advisories/widget-overflow"
        ),
        name="Vendor advisory",
        context=_case.id_,
    )
    return add_case_reference_to_case_activity(
        reference,
        target=_case.id_,
        id_=f"{reference.id_}/add",
        actor=case_actor().id_,
    )


def announce_case() -> as_Announce:
    """Build ``Announce(VulnerabilityCase)`` — sent by the case owner to a new participant.

    The full case object is delivered inline so the recipient can seed their
    local DataLayer immediately after their invite is accepted.
    """
    _case = populated_case()
    return announce_vulnerability_case_activity(
        _case,
        actor=_VENDOR.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def offer_case_participant_role() -> as_Offer:
    """Build ``Offer(CaseParticipantRole)`` — the ADR-0039 role-delegation offer.

    Distinct from ``offer_case_participant``, which is the GI actor-suggestion
    handshake.  The ``as_CaseParticipantRole`` object carries the role, so the
    object type alone tells a receiver this is a role offer and not an
    ownership-transfer offer.  The Case Owner sends it to the case's
    CASE_MANAGER, never to the target (CM-33-001).
    """
    _case = case()
    _vendor = vendor()
    _coordinator = _COORDINATOR
    return offer_case_participant_role_activity(
        role=CVDRole.COORDINATOR,
        target_actor=_coordinator,
        case=_case,
        actor=_vendor.id_,
        to=[case_actor().id_],
        content=(
            f"We're offering the {CVDRole.COORDINATOR.value} role on case "
            f"{_case.name} to {_coordinator.name}."
        ),
        at=EXAMPLE_TIMESTAMP,
    )


def forward_case_participant_role() -> as_Offer:
    """Build the CASE_MANAGER's forward of a recorded role Offer (CM-33-008).

    The CASE_MANAGER is the ``actor`` and the Case Owner that made the Offer
    is ``attributedTo`` (CM-24-005); the forward goes to the target only and
    names the recorded Offer in ``inReplyTo``.
    """
    _offer = offer_case_participant_role()
    _coordinator = _COORDINATOR
    return offer_case_participant_role_activity(
        role=CVDRole.COORDINATOR,
        target_actor=_coordinator,
        case=case(),
        actor=case_actor().id_,
        attributed_to=vendor().id_,
        to=[_coordinator.id_],
        in_reply_to=_offer.id_,
        content=_offer.content,
        at=EXAMPLE_TIMESTAMP,
    )


def accept_case_participant_role() -> as_Accept:
    """Build ``Accept(Offer(CaseParticipantRole))`` — the target takes the role.

    The target answers the CASE_MANAGER's forward, to the CASE_MANAGER
    (CM-33-015).
    """
    _coordinator = _COORDINATOR
    _offer = forward_case_participant_role()
    return accept_case_participant_role_activity(
        _offer,
        actor=_coordinator.id_,
        to=[case_actor().id_],
        content="We're accepting the role you offered.",
        at=EXAMPLE_TIMESTAMP,
    )


def reject_case_participant_role() -> as_Reject:
    """Build ``Reject(Offer(CaseParticipantRole))`` — the target declines the role.

    The target answers the CASE_MANAGER's forward, to the CASE_MANAGER
    (CM-33-015).
    """
    _coordinator = _COORDINATOR
    _offer = forward_case_participant_role()
    return reject_case_participant_role_activity(
        _offer,
        actor=_coordinator.id_,
        to=[case_actor().id_],
        content="We're declining the role you offered.",
        at=EXAMPLE_TIMESTAMP,
    )
