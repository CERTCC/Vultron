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
    as_Update,
)
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    _REPORT,
    _VENDOR,
    case,
    gen_report,
    vendor,
)
from vultron.wire.as2.vocab.examples.participant import (
    finder_participant,
    vendor_participant,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    accept_case_participant_role_activity,
    add_report_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    offer_case_ownership_transfer_activity,
    offer_case_participant_role_activity,
    reject_case_ownership_transfer_activity,
    reject_case_participant_role_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    update_case_activity,
)


def create_case() -> as_Create:
    participant = as_CaseParticipant(
        case_roles=[CVDRole.VENDOR],
        attributed_to=_VENDOR.id_,
        name=_VENDOR.name,
    )
    _case = case(
        random_id=True,
        vulnerability_reports=[_REPORT.id_],
        case_participants=[participant.id_],
    )

    activity = create_case_activity(
        _case,
        actor=_VENDOR.id_,
        content="We've created a case from this report.",
        context=_REPORT.id_,
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
        vulnerability_reports=[gen_report().id_],
        case_participants=[p.id_ for p in participants],
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
    )
    return activity


def engage_case() -> as_Join:
    _vendor = vendor()
    _case = case()

    activity = rm_engage_case_activity(
        _case, actor=_vendor.id_, content="We're engaging this case."
    )
    return activity


def close_case() -> as_Leave:
    _vendor = vendor()
    _case = case()

    activity = rm_close_case_activity(
        _case, actor=_vendor.id_, content="We're closing this case."
    )
    return activity


def defer_case() -> as_Ignore:
    _vendor = vendor()
    _case = case()

    activity = rm_defer_case_activity(
        _case, actor=_vendor.id_, content="We're deferring this case."
    )
    return activity


def reengage_case() -> as_Join:
    _vendor = vendor()
    _case = case()

    activity = rm_engage_case_activity(
        _case, actor=_vendor.id_, content="We're reengaging this case."
    )
    return activity


def offer_case_ownership_transfer() -> as_Offer:
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _activity = offer_case_ownership_transfer_activity(
        _case,
        actor=_vendor.id_,
        target=_coordinator.id_,
        content=f"We're offering to transfer ownership of case {_case.name} to you.",
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
    )
    return _activity


def update_case() -> as_Update:
    _case = case()
    _vendor = vendor()

    _activity = update_case_activity(
        _case,
        actor=_vendor.id_,
        content="We're updating the case to reflect a transfer of ownership.",
    )
    return _activity


def announce_case() -> as_Announce:
    """Build ``Announce(VulnerabilityCase)`` — sent by the case owner to a new participant.

    The full case object is delivered inline so the recipient can seed their
    local DataLayer immediately after their invite is accepted.
    """
    _case = populated_case()
    return announce_vulnerability_case_activity(
        _case,
        actor=_VENDOR.id_,
    )


def offer_case_participant_role() -> as_Offer:
    """Build ``Offer(CaseParticipantRole)`` — the ADR-0039 role-delegation offer.

    Distinct from ``offer_case_participant``, which is the GI actor-suggestion
    handshake.  The ``as_CaseParticipantRole`` object carries the role, so the
    object type alone tells a receiver this is a role offer and not an
    ownership-transfer offer.
    """
    _case = case()
    _vendor = vendor()
    _coordinator = _COORDINATOR
    return offer_case_participant_role_activity(
        role=CVDRole.COORDINATOR,
        target_actor=_coordinator,
        case=_case,
        actor=_vendor.id_,
        to=[_coordinator.id_],
        content=(
            f"We're offering the {CVDRole.COORDINATOR.value} role on case "
            f"{_case.name} to {_coordinator.name}."
        ),
    )


def accept_case_participant_role() -> as_Accept:
    """Build ``Accept(Offer(CaseParticipantRole))`` — the target takes the role."""
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _offer = offer_case_participant_role()
    return accept_case_participant_role_activity(
        _offer,
        actor=_coordinator.id_,
        to=[_vendor.id_],
        content="We're accepting the role you offered.",
    )


def reject_case_participant_role() -> as_Reject:
    """Build ``Reject(Offer(CaseParticipantRole))`` — the target declines the role."""
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _offer = offer_case_participant_role()
    return reject_case_participant_role_activity(
        _offer,
        actor=_coordinator.id_,
        to=[_vendor.id_],
        content="We're declining the role you offered.",
    )
