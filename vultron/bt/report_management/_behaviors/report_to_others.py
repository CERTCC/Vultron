#!/usr/bin/env python
"""
Provides report_to_others behavior tree nodes.
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
import logging

from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import (
    action_node,
    condition_check,
    fallback_node,
    invert,
    sequence_node,
)
from vultron.bt.common import show_graph
from vultron.bt.embargo_management.conditions import (
    EMinStateActiveOrRevise,
    EMinStateNoneOrProposeOrRevise,
)
from vultron.bt.messaging.states import MessageTypes
from vultron.bt.report_management.fuzzer.report_to_others import (
    AllPartiesKnown,
    ChooseRecipient,
    FindContact,
    HaveReportToOthersCapability,
    InjectCoordinator,
    InjectOther,
    InjectVendor,
    MoreCoordinators,
    MoreOthers,
    MoreVendors,
    NotificationsComplete,
    PolicyCompatible,
    RcptNotInQrmS,
    RecipientEffortExceeded,
)
from vultron.case_states.states import CS
from vultron.sim.messages import Message

# from vultron.sim.communications import Message

logger = logging.getLogger(__name__)


def reporting_effort_available(obj: BtNode) -> bool:
    """True if reporting effort budget remains"""
    return obj.bb.reporting_effort_budget > 0


_ReportingEffortAvailable = condition_check(
    "ReportingEffortAvailable", reporting_effort_available
)

_TotalEffortLimitMet = invert(
    "_TotalEffortLimitMet",
    "Checks whether the effort limit has been met",
    _ReportingEffortAvailable,
)

_IdentifyVendors = sequence_node("_IdentifyVendors", """XXX""", MoreVendors, InjectVendor)


_IdentifyCoordinators = sequence_node("_IdentifyCoordinators", """XXX""", MoreCoordinators, InjectCoordinator)


_IdentifyOthers = sequence_node("_IdentifyOthers", """XXX""", MoreOthers, InjectOther)


_IdentifyPotentialCaseParticipants = sequence_node("_IdentifyPotentialCaseParticipants",
                                                   "Identifies potential case participants: vendors, coordinators, and others",
                                                   _IdentifyVendors, _IdentifyCoordinators, _IdentifyOthers)


# TODO AllPartiesKnown should be a simulated annealing where p rises with tick count
#  thereby forcing notification to happen toward the outset of a case
#  but for now we'll just leave it as a dumb fuzzer
_IdentifyParticipants = fallback_node("_IdentifyParticipants",
                                      "Checks whether all parties are known, otherwise identifies potential case",
                                      AllPartiesKnown, _IdentifyPotentialCaseParticipants)


_DecideWhetherToPruneRecipient = fallback_node("_DecideWhetherToPruneRecipient",
                                               "Checks whether a recipient is already aware (RM != START) or effort budget exceeded",
                                               RcptNotInQrmS, RecipientEffortExceeded)


def remove_recipient(obj: BtNode) -> bool:
    """Removes the current recipient from the list of potential participants"""
    current = obj.bb.currently_notifying
    if current is None:
        return True

    logger.debug(f"Removing {current} from potential participants list")
    try:
        obj.bb.case.potential_participants.remove(current)
    except ValueError:
        logger.warning(
            f"Unable to remove {current}, not in potential participants list"
        )
    obj.bb.currently_notifying = None
    return True


_RemoveRecipient = action_node("RemoveRecipient", remove_recipient)


_PruneRecipients = sequence_node("_PruneRecipients", """XXX""", _DecideWhetherToPruneRecipient, _RemoveRecipient)


_EnsureRcptPolicyCompatibleWithExistingEmbargo = sequence_node("_EnsureRcptPolicyCompatibleWithExistingEmbargo",
                                                               "If there is an active embargo, then the recipient's policy must be compatible with the embargo policy",
                                                               EMinStateActiveOrRevise, PolicyCompatible)


_EnsureOkToNotify = fallback_node("_EnsureOkToNotify", "Verify that it is ok to notify a recipient",
                                  EMinStateNoneOrProposeOrRevise, _EnsureRcptPolicyCompatibleWithExistingEmbargo)


def report_to_new_participant(obj: BtNode) -> bool:
    """Direct messages an initial report to a new participant in their inbox"""
    # inject an RS message from us into their inbox
    report = Message(
        sender="", body="Initial report", msg_type=MessageTypes.RS
    )

    dm = obj.bb.dm_func
    dm(message=report, recipient=obj.bb.currently_notifying)

    return True


_ReportToNewParticipant = action_node(
    "ReportToNewParticipant", report_to_new_participant
)


def connect_new_participant_to_case(obj: BtNode) -> bool:
    """Wires up a new participant's inbox to the case"""
    # wire up their inbox to the case
    add_func = obj.bb.add_participant_func
    if add_func is None:
        logger.warning(f"Node blackboard add_participant_func is not set.")
        return False

    add_func(obj.bb.currently_notifying)
    return True


_ConnectNewParticipantToCase = action_node(
    "ConnectNewParticipantToCase", connect_new_participant_to_case
)


def bring_new_participant_up_to_speed(obj: BtNode) -> bool:
    """Sets a new participant's global state to match the current participant's global state"""
    # EM state is global to the case
    obj.bb.currently_notifying.bt.bb.q_em = obj.bb.q_em

    # FIXME this doesn't work with the new CS enumerations
    # CS.PXA is 000111, so only the P, X, and A states carry over
    obj.bb.currently_notifying.bt.bb.q_cs = CS.PXA & obj.bb.q_cs

    return True


_BringNewParticipantUpToSpeed = action_node(
    "BringNewParticipantUpToSpeed", bring_new_participant_up_to_speed
)


_EngageParticipant = sequence_node("_EngageParticipant",
                                   "Reports to a new participant, connects them to the case, and brings them up to speed",
                                   _ReportToNewParticipant, _ConnectNewParticipantToCase, _BringNewParticipantUpToSpeed)


# FIXED Replace EmitRS with inject RS into new participant then add participant to case
#  will also need to sync case pxa and embargo status with new participant
_NotifyRecipient = sequence_node("_NotifyRecipient",
                                 "Checks if it is ok to notify a recipient, finds their contact info, then notifies them",
                                 _EnsureOkToNotify, FindContact, _EngageParticipant)


_PruneOrNotifyRecipient = fallback_node("_PruneOrNotifyRecipient",
                                        "Prunes a recipient if necessary, otherwise notifies them", _PruneRecipients,
                                        _NotifyRecipient)


_SelectAndProcessRecipient = sequence_node("_SelectAndProcessRecipient",
                                           "Chooses a recipient, then prunes or notifies them", ChooseRecipient,
                                           _PruneOrNotifyRecipient)


_NotifyOthers = fallback_node("_NotifyOthers",
                              "Checks if there are more recipients to notify, then selects and processes a recipient",
                              NotificationsComplete, _SelectAndProcessRecipient)


_IdentifyAndNotifyParticipants = sequence_node("_IdentifyAndNotifyParticipants",
                                               "Identify participants and notify them", _IdentifyParticipants,
                                               _NotifyOthers)


_ReportToOthers = fallback_node("_ReportToOthers",
                                "Checks an effort budget remains, then identifies and notifies participants",
                                _TotalEffortLimitMet, _IdentifyAndNotifyParticipants)


MaybeReportToOthers = sequence_node("MaybeReportToOthers",
                                    "Checks for reporting capability, then reports to others if possible",
                                    HaveReportToOthersCapability, _ReportToOthers)


def main():
    show_graph(MaybeReportToOthers)


if __name__ == "__main__":
    main()
