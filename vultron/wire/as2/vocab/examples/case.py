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

from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Undo
from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    _REPORT,
    _VENDOR,
    case,
    gen_report,
    vendor,
)
from vultron.wire.as2.vocab.objects.case_participant import VendorParticipant
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    add_report_to_case_activity,
    create_case_activity,
    offer_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    update_case_activity,
)
from vultron.core.models.vultron_types import VultronActivity


def create_case() -> VultronActivity:
    _case = case()
    _case.add_report(_REPORT.id_)
    participant = VendorParticipant(
        attributed_to=_VENDOR.id_, name=_VENDOR.name, context=_case.id_
    )
    _case.add_participant(participant)

    activity = create_case_activity(
        _case,
        actor=_VENDOR.id_,
        content="We've created a case from this report.",
        context=_REPORT.id_,
    )
    return activity


def add_report_to_case() -> VultronActivity:
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


def engage_case() -> VultronActivity:
    _vendor = vendor()
    _case = case()

    activity = rm_engage_case_activity(
        _case, actor=_vendor.id_, content="We're engaging this case."
    )
    return activity


def close_case() -> VultronActivity:
    _vendor = vendor()
    _case = case()

    activity = rm_close_case_activity(
        _case, actor=_vendor.id_, content="We're closing this case."
    )
    return activity


def defer_case() -> VultronActivity:
    _vendor = vendor()
    _case = case()

    activity = rm_defer_case_activity(
        _case, actor=_vendor.id_, content="We're deferring this case."
    )
    return activity


def reengage_case() -> as_Undo:
    _vendor = vendor()
    _case = case()
    _deferral = defer_case()

    activity = as_Undo(
        actor=_vendor.id_,
        object_=_deferral,
        content="We're reengaging this case.",
        context=_case.id_,
    )
    return activity


def offer_case_ownership_transfer() -> VultronActivity:
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


def accept_case_ownership_transfer() -> VultronActivity:
    _case = case()
    _coordinator = _COORDINATOR
    _offer = offer_case_ownership_transfer()
    _activity = accept_case_ownership_transfer_activity(
        _offer,
        actor=_coordinator.id_,
        content=f"We're accepting your offer to transfer ownership of case {_case.name} to us.",
    )
    return _activity


def reject_case_ownership_transfer() -> VultronActivity:
    _case = case()
    _coordinator = _COORDINATOR
    _offer = offer_case_ownership_transfer()
    _activity = reject_case_ownership_transfer_activity(
        _offer,
        actor=_coordinator.id_,
        content=f"We're declining your offer to transfer ownership of case {_case.name} to us.",
    )
    return _activity


def update_case() -> VultronActivity:
    _case = case()
    _vendor = vendor()

    _activity = update_case_activity(
        _case,
        actor=_vendor.id_,
        content="We're updating the case to reflect a transfer of ownership.",
    )
    return _activity
