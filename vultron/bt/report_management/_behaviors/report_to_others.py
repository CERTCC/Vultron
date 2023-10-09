#!/usr/bin/env python
"""file: report_to_others
author: adh
created_at: 6/23/22 2:26 PM
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
import random

from vultron.bt.base.bt_node import ActionNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.decorators import Invert
from vultron.bt.base.fuzzer import AlmostAlwaysFail, UsuallyFail
from vultron.bt.embargo_management.conditions import (
    EMinStateActiveOrRevise,
    EMinStateNoneOrProposeOrRevise,
)
from vultron.bt.report_management.fuzzer.report_to_others import (
    AllPartiesKnown,
    FindContact,
    NotificationsComplete,
    PolicyCompatible,
    RcptNotInQrmS,
    RecipientEffortExceeded,
)
from vultron.bt.states import CapabilityFlag
from vultron.case_states.states import CS

# from vultron.sim.communications import Message

logger = logging.getLogger(__name__)


class HaveReportToOthersCapability(ConditionCheck):
    """Succeeds when ReportToOthers capability is present"""

    def func(self):
        return self.bb.capabilities & CapabilityFlag.ReportToOthers


class ReportingEffortAvailable(ConditionCheck):
    """Succeeds when reporting effort budget remains"""

    def func(self):
        return self.bb.reporting_effort_budget > 0


# FIXED TotalEffortLimit starts at some value, Returns SUCCESS when 0?
class TotalEffortLimitMet(Invert):
    """Succeeds when reporting effort budget is empty"""

    _children = (ReportingEffortAvailable,)


class InjectParticipant(ActionNode):
    participant_type = "Participant"

    def func(self):
        p_class = self.bb.participant_types[self.participant_type]
        p = p_class()
        self.bb.case.potential_participants.append(p)
        return True


# todo move to fuzzers
class MoreVendors(UsuallyFail):
    pass


# todo move to fuzzers
class MoreCoordinators(AlmostAlwaysFail):
    pass


# todo move to fuzzers
class MoreOthers(AlmostAlwaysFail):
    pass


class InjectVendor(InjectParticipant):
    participant_type = "Vendor"


class InjectCoordinator(InjectParticipant):
    participant_type = "Coordinator"


class InjectOther(InjectParticipant):
    participant_type = "Participant"


class IdentifyVendors(SequenceNode):
    _children = (MoreVendors, InjectVendor)


class IdentifyCoordinators(SequenceNode):
    _children = (MoreCoordinators, InjectCoordinator)


class IdentifyOthers(SequenceNode):
    _children = (MoreOthers, InjectOther)


# FIXED Identify* should add participants to a "to notify" list
class IdentifyPotentialCaseParticipants(SequenceNode):
    _children = (IdentifyVendors, IdentifyCoordinators, IdentifyOthers)


# TODO AllPartiesKnown should be a simulated annealing where p rises with tick count
#  thereby forcing notification to happen toward the outset of a case
#  but for now we'll just leave it as a dumb fuzzer
class IdentifyParticipants(FallbackNode):
    _children = (AllPartiesKnown, IdentifyPotentialCaseParticipants)


class DecideWhetherToPruneRecipient(FallbackNode):
    _children = (RcptNotInQrmS, RecipientEffortExceeded)


class RemoveRecipient(ActionNode):
    def func(self):
        current = self.bb.currently_notifying
        if current is None:
            return True

        logger.debug(f"Removing {current} from potential participants list")
        try:
            self.bb.case.potential_participants.remove(current)
        except ValueError:
            logger.warning(
                f"Unable to remove {current}, not in potential participants list"
            )
        self.bb.currently_notifying = None
        return True


class PruneRecipients(SequenceNode):
    _children = (DecideWhetherToPruneRecipient, RemoveRecipient)


class EnsureRcptPolicyCompatibleWithExistingEmbargo(SequenceNode):
    _children = (EMinStateActiveOrRevise, PolicyCompatible)


class EnsureOkToNotify(FallbackNode):
    _children = (
        EMinStateNoneOrProposeOrRevise,
        EnsureRcptPolicyCompatibleWithExistingEmbargo,
    )


class NewParticipantHandler(ActionNode):
    def func(self):
        if self.bb.currently_notifying is None:
            logger.warning(f"Node blackboard currently_notifying is not set.")
            return False

        return self._func()


# class ReportToNewParticipant(NewParticipantHandler):
#     """Direct messages an initial report to a new participant in their inbox"""
#
#     def _func(self):
#         # inject an RS message from us into their inbox
#         report = Message(sender="", body="Initial report", type=MT.RS)
#
#         dm = self.bb.dm_func
#         dm(message=report, recipient=self.bb.currently_notifying)
#
#         return True


class ConnectNewParticipantToCase(NewParticipantHandler):
    """Wires up a new participant's inbox to the case"""

    def _func(self):
        # wire up their inbox to the case
        add_func = self.bb.add_participant_func
        if add_func is None:
            logger.warning(f"Node blackboard add_participant_func is not set.")
            return False

        add_func(self.bb.currently_notifying)
        return True


class BringNewParticipantUpToSpeed(NewParticipantHandler):
    """Sets a new participant's global state to match the current participant's global state"""

    def _func(self):
        # EM state is global to the case
        self.bb.currently_notifying.bt.bb.q_em = self.bb.q_em

        # CS.PXA is 000111, so only the P, X, and A states carry over
        self.bb.currently_notifying.bt.bb.q_cs = CS.PXA & self.bb.q_cs

        return True


class EngageParticipant(SequenceNode):
    _children = (
        ReportToNewParticipant,
        ConnectNewParticipantToCase,
        BringNewParticipantUpToSpeed,
    )


# FIXED Replace EmitRS with inject RS into new participant then add participant to case
#  will also need to sync case pxa and embargo status with new participant
class NotifyRecipient(SequenceNode):
    _children = (EnsureOkToNotify, FindContact, EngageParticipant)


class PruneOrNotifyRecipient(FallbackNode):
    _children = (PruneRecipients, NotifyRecipient)


class ChooseRecipient(ActionNode):
    def func(self):
        if not self.bb.case.potential_participants:
            logger.debug("Potential Participants is empty")
            return False

        # return True on success
        next_recipient = random.choice(self.bb.case.potential_participants)
        self.bb.currently_notifying = next_recipient
        return True


class SelectAndProcessRecipient(SequenceNode):
    _children = (ChooseRecipient, PruneOrNotifyRecipient)


class NotifyOthers(FallbackNode):
    _children = (NotificationsComplete, SelectAndProcessRecipient)


class IdentifyAndNotifyParticipants(SequenceNode):
    _children = (IdentifyParticipants, NotifyOthers)


class ReportToOthers(FallbackNode):
    _children = (TotalEffortLimitMet, IdentifyAndNotifyParticipants)


class MaybeReportToOthers(SequenceNode):
    _children = (HaveReportToOthersCapability, ReportToOthers)


def main():
    pass


if __name__ == "__main__":
    main()
