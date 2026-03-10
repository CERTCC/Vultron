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

from vultron.wire.as2.vocab.activities.case import (
    AcceptCaseOwnershipTransfer,
    AddReportToCase,
    CreateCase,
    OfferCaseOwnershipTransfer,
    RejectCaseOwnershipTransfer,
    RmCloseCase,
    RmDeferCase,
    RmEngageCase,
    UpdateCase,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Undo
from vultron.wire.as2.vocab.examples._base import (
    _CASE,
    _COORDINATOR,
    _REPORT,
    _VENDOR,
    case,
    gen_report,
    vendor,
)
from vultron.wire.as2.vocab.objects.case_participant import VendorParticipant


def create_case() -> CreateCase:
    _case = case()
    _case.add_report(_REPORT.as_id)
    participant = VendorParticipant(
        attributed_to=_VENDOR.as_id, name=_VENDOR.name, context=_case.as_id
    )
    _case.add_participant(participant)

    activity = CreateCase(
        actor=_VENDOR.as_id,
        object=_case,
        content="We've created a case from this report.",
        context=_REPORT.as_id,
    )
    return activity


def add_report_to_case() -> AddReportToCase:
    _vendor = vendor()
    _report = gen_report()
    _case = case()

    activity = AddReportToCase(
        actor=_vendor.as_id,
        object=_report.as_id,
        target=_case.as_id,
        content="We're adding this report to this case.",
    )
    return activity


def engage_case() -> RmEngageCase:
    _vendor = vendor()
    _case = case()

    activity = RmEngageCase(
        actor=_vendor.as_id,
        object=_case.as_id,
        content="We're engaging this case.",
    )
    return activity


def close_case() -> RmCloseCase:
    _vendor = vendor()
    _case = case()

    activity = RmCloseCase(
        actor=_vendor.as_id,
        object=_case.as_id,
        content="We're closing this case.",
    )
    return activity


def defer_case() -> RmDeferCase:
    _vendor = vendor()
    _case = case()

    activity = RmDeferCase(
        actor=_vendor.as_id,
        object=_case.as_id,
        content="We're deferring this case.",
    )
    return activity


def reengage_case() -> as_Undo:
    _vendor = vendor()
    _case = case()
    _deferral = defer_case()

    activity = as_Undo(
        actor=_vendor.as_id,
        object=_deferral,
        content="We're reengaging this case.",
        context=_case.as_id,
    )
    return activity


def offer_case_ownership_transfer() -> OfferCaseOwnershipTransfer:
    _vendor = vendor()
    _case = case()
    _coordinator = _COORDINATOR
    _activity = OfferCaseOwnershipTransfer(
        actor=_vendor.as_id,
        object=_case,
        target=_coordinator.as_id,
        content=f"We're offering to transfer ownership of case {_case.name} to you.",
    )
    return _activity


def accept_case_ownership_transfer() -> AcceptCaseOwnershipTransfer:
    _case = case()
    _coordinator = _COORDINATOR
    _offer = offer_case_ownership_transfer()
    _activity = AcceptCaseOwnershipTransfer(
        actor=_coordinator.as_id,
        object=_offer,
        content=f"We're accepting your offer to transfer ownership of case {_case.name} to us.",
    )
    return _activity


def reject_case_ownership_transfer() -> RejectCaseOwnershipTransfer:
    _case = case()
    _coordinator = _COORDINATOR
    _offer = offer_case_ownership_transfer()
    _activity = RejectCaseOwnershipTransfer(
        actor=_coordinator.as_id,
        object=_offer,
        content=f"We're declining your offer to transfer ownership of case {_case.name} to us.",
    )
    return _activity


def update_case() -> UpdateCase:
    _case = case()
    _vendor = vendor()

    _activity = UpdateCase(
        actor=_vendor.as_id,
        object=_case.as_id,
        content="We're updating the case to reflect a transfer of ownership.",
    )
    return _activity
