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

from vultron.bt.base.bt_node import ActionNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.decorators import Invert
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


class _ReportingEffortAvailable(ConditionCheck):
    """Succeeds when reporting effort budget remains"""

    def func(self):
        return self.bb.reporting_effort_budget > 0


class _TotalEffortLimitMet(Invert):
    """Succeeds when reporting effort budget is empty"""

    _children = (_ReportingEffortAvailable,)


class _IdentifyVendors(SequenceNode):
    _children = (MoreVendors, InjectVendor)


class _IdentifyCoordinators(SequenceNode):
    _children = (MoreCoordinators, InjectCoordinator)


class _IdentifyOthers(SequenceNode):
    _children = (MoreOthers, InjectOther)


class _IdentifyPotentialCaseParticipants(SequenceNode):
    _children = (_IdentifyVendors, _IdentifyCoordinators, _IdentifyOthers)


# TODO AllPartiesKnown should be a simulated annealing where p rises with tick count
#  thereby forcing notification to happen toward the outset of a case
#  but for now we'll just leave it as a dumb fuzzer
class _IdentifyParticipants(FallbackNode):
    _children = (AllPartiesKnown, _IdentifyPotentialCaseParticipants)


class _DecideWhetherToPruneRecipient(FallbackNode):
    _children = (RcptNotInQrmS, RecipientEffortExceeded)


class _RemoveRecipient(ActionNode):
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


class _PruneRecipients(SequenceNode):
    _children = (_DecideWhetherToPruneRecipient, _RemoveRecipient)


class _EnsureRcptPolicyCompatibleWithExistingEmbargo(SequenceNode):
    _children = (EMinStateActiveOrRevise, PolicyCompatible)


class _EnsureOkToNotify(FallbackNode):
    _children = (
        EMinStateNoneOrProposeOrRevise,
        _EnsureRcptPolicyCompatibleWithExistingEmbargo,
    )


class _NewParticipantHandler(ActionNode):
    def func(self):
        if self.bb.currently_notifying is None:
            logger.warning(f"Node blackboard currently_notifying is not set.")
            return False

        return self._func()


class _ReportToNewParticipant(_NewParticipantHandler):
    """Direct messages an initial report to a new participant in their inbox"""

    def _func(self):
        # inject an RS message from us into their inbox
        report = Message(
            sender="", body="Initial report", msg_type=MessageTypes.RS
        )

        dm = self.bb.dm_func
        dm(message=report, recipient=self.bb.currently_notifying)

        return True


class _ConnectNewParticipantToCase(_NewParticipantHandler):
    """Wires up a new participant's inbox to the case"""

    def _func(self):
        # wire up their inbox to the case
        add_func = self.bb.add_participant_func
        if add_func is None:
            logger.warning(f"Node blackboard add_participant_func is not set.")
            return False

        add_func(self.bb.currently_notifying)
        return True


class _BringNewParticipantUpToSpeed(_NewParticipantHandler):
    """Sets a new participant's global state to match the current participant's global state"""

    def _func(self):
        # EM state is global to the case
        self.bb.currently_notifying.bt.bb.q_em = self.bb.q_em

        # CS.PXA is 000111, so only the P, X, and A states carry over
        self.bb.currently_notifying.bt.bb.q_cs = CS.PXA & self.bb.q_cs

        return True


class _EngageParticipant(SequenceNode):
    _children = (
        _ReportToNewParticipant,
        _ConnectNewParticipantToCase,
        _BringNewParticipantUpToSpeed,
    )


# FIXED Replace EmitRS with inject RS into new participant then add participant to case
#  will also need to sync case pxa and embargo status with new participant
class _NotifyRecipient(SequenceNode):
    _children = (_EnsureOkToNotify, FindContact, _EngageParticipant)


class _PruneOrNotifyRecipient(FallbackNode):
    _children = (_PruneRecipients, _NotifyRecipient)


class _SelectAndProcessRecipient(SequenceNode):
    _children = (ChooseRecipient, _PruneOrNotifyRecipient)


class _NotifyOthers(FallbackNode):
    _children = (NotificationsComplete, _SelectAndProcessRecipient)


class _IdentifyAndNotifyParticipants(SequenceNode):
    _children = (_IdentifyParticipants, _NotifyOthers)


class _ReportToOthers(FallbackNode):
    _children = (_TotalEffortLimitMet, _IdentifyAndNotifyParticipants)


class MaybeReportToOthers(SequenceNode):
    _children = (HaveReportToOthersCapability, _ReportToOthers)


def main():
    pass


if __name__ == "__main__":
    main()
