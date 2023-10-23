#!/usr/bin/env python
"""
Provides behaviors for handling embargo messages.
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


from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.case_state.conditions import (
    CSinStateNotPublicNoExploitNoAttacks,
    CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
)
from vultron.bt.common import show_graph
from vultron.bt.embargo_management.behaviors import TerminateEmbargoBt
from vultron.bt.embargo_management.conditions import (
    EMinStateActive,
    EMinStateActiveOrRevise,
    EMinStateExited,
    EMinStateNone,
    EMinStateProposed,
    EMinStateRevise,
)
from vultron.bt.embargo_management.transitions import (
    q_em_R_to_A,
    q_em_to_A,
    q_em_to_N,
    q_em_to_P,
    q_em_to_R,
    q_em_to_X,
)
from vultron.bt.messaging.conditions import (
    IsEMMessage,
    IsMsgTypeEA,
    IsMsgTypeEC,
    IsMsgTypeEE,
    IsMsgTypeEJ,
    IsMsgTypeEK,
    IsMsgTypeEP,
    IsMsgTypeER,
    IsMsgTypeET,
    IsMsgTypeEV,
)
from vultron.bt.messaging.inbound._behaviors.fuzzer import (
    FollowUpOnErrorMessage,
)
from vultron.bt.messaging.outbound.behaviors import EmitEE, EmitEK


class _HandleEe(SequenceNode):
    """Handle embargo error (EE) messages."""

    _children = (IsMsgTypeEE, FollowUpOnErrorMessage)


class _RecognizeEmbargoExit(SequenceNode):
    """Recognize an embargo exit."""

    _children = (EMinStateActiveOrRevise, q_em_to_X)


class _EnsureEmbargoExited(FallbackNode):
    """Ensure that the embargo is exited."""

    _children = (EMinStateExited, _RecognizeEmbargoExit)


class _HandleEt(SequenceNode):
    """Handle embargo termination (ET) messages."""

    _children = (IsMsgTypeET, _EnsureEmbargoExited)


class _RecognizeRejection(SequenceNode):
    """Recognize a rejected embargo proposal, retuning to the EM.None state."""

    _children = (EMinStateProposed, q_em_to_N)


class _EnsureRejectionRecognized(FallbackNode):
    """Ensure that the rejection is recognized and that the embargo is in the EM.None state."""

    _children = (EMinStateNone, _RecognizeRejection)


class _HandleEr(SequenceNode):
    """Handle embargo rejection (ER) messages."""

    _children = (IsMsgTypeER, _EnsureRejectionRecognized)


class _RecognizeProposal(SequenceNode):
    """Recognize an embargo proposal, transitioning to the EM.Proposed state."""

    _children = (EMinStateNone, q_em_to_P)


class _EnsureProposalRecognized(FallbackNode):
    """Ensure that the proposal is recognized and that the embargo is in the EM.Proposed state."""

    _children = (EMinStateProposed, _RecognizeProposal)


class _HandleEp(SequenceNode):
    """Handle embargo proposal (EP) messages."""

    _children = (IsMsgTypeEP, _EnsureProposalRecognized)


class _RecognizeActivation(SequenceNode):
    """Recognize an embargo activation, transitioning to the EM.Active state."""

    _children = (EMinStateProposed, q_em_to_A)


class _EnsureEmbargoActivated(FallbackNode):
    """Ensure that the embargo is activated and that the embargo is in the EM.Active state."""

    _children = (EMinStateActive, _RecognizeActivation)


class _HandleEa(SequenceNode):
    """Handle embargo activation (EA) messages."""

    _children = (IsMsgTypeEA, _EnsureEmbargoActivated)


class _RecognizeRevision(SequenceNode):
    """Recognize an embargo revision, transitioning to the EM.Revise state."""

    _children = (EMinStateActive, q_em_to_R)


class _EnsureEmbargoRevisionRecognized(FallbackNode):
    """Ensure that the embargo is in the EM.Revise state."""

    _children = (EMinStateRevise, _RecognizeRevision)


class _HandleEv(SequenceNode):
    """Handle embargo revision (EV) messages."""

    _children = (IsMsgTypeEV, _EnsureEmbargoRevisionRecognized)


class _HandleEj(SequenceNode):
    """Handle embargo revision rejection (EJ) messages."""

    _children = (IsMsgTypeEJ, q_em_R_to_A)


class _HandleEc(SequenceNode):
    """Handle embargo revision acceptance (EC) messages."""

    _children = (IsMsgTypeEC, q_em_to_A)


class _SelectEjOrEcResponse(FallbackNode):
    """Select the appropriate response to an EJ or EC message."""

    _children = (_HandleEj, _HandleEc)


class _HandleEjOrEcMsg(SequenceNode):
    """Handle an EJ or EC message."""

    _children = (EMinStateRevise, _SelectEjOrEcResponse)


class _EnsureEmActive(FallbackNode):
    """Ensure that the embargo is in the EM.Active state."""

    _children = (EMinStateActive, _HandleEjOrEcMsg)


class _CheckEjOrEcMsg(FallbackNode):
    """Check if the message is an EJ or EC message."""

    _children = (IsMsgTypeEJ, IsMsgTypeEC)


class _HandleRevisionResponse(SequenceNode):
    """Handle a revision response. Always returns to the EM.Active state."""

    _children = (_CheckEjOrEcMsg, _EnsureEmActive)


class _HandleMessagesInpxa(FallbackNode):
    """Handle embargo messages when the case state is compatible with an embargo."""

    _children = (_HandleEp, _HandleEa, _HandleEv, _HandleRevisionResponse)


class _HandleCSpxa(SequenceNode):
    """Check if the case state is compatible with an embargo then handle embargo messages."""

    _children = (CSinStateNotPublicNoExploitNoAttacks, _HandleMessagesInpxa)


class _AvoidNonViableEmbargo(SequenceNode):
    """Avoid non-viable embargo states.
    If the case state is not compatible with an embargo, then the embargo is terminated.
    """

    _children = (
        CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
        TerminateEmbargoBt,
    )


class _HandleAckable(FallbackNode):
    """Handle ackable messages."""

    _children = (
        _HandleEe,
        _HandleEt,
        _HandleEr,
        _HandleCSpxa,
        _AvoidNonViableEmbargo,
    )


class _HandleAndAckEmMsg(SequenceNode):
    """Handle an EM message and acknowledge it."""

    _children = (_HandleAckable, EmitEK)


class _HandleEmMessage(FallbackNode):
    """Handle an EM message. Emit an error (EE) message if there is an error."""

    _children = (IsMsgTypeEK, _HandleAndAckEmMsg, EmitEE)


class ProcessEMMessagesBt(SequenceNode):
    """The bt tree for processing incoming EM messages."""

    _children = (IsEMMessage, _HandleEmMessage)


def main():
    show_graph(ProcessEMMessagesBt)


if __name__ == "__main__":
    main()
