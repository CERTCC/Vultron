#!/usr/bin/env python
"""file: em_messages
author: adh
created_at: 6/27/22 2:44 PM
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


class HandleEe(SequenceNode):
    """Handle embargo error (EE) messages."""

    _children = (IsMsgTypeEE, FollowUpOnErrorMessage)


class RecognizeEmbargoExit(SequenceNode):
    """Recognize an embargo exit."""

    _children = (EMinStateActiveOrRevise, q_em_to_X)


class EnsureEmbargoExited(FallbackNode):
    """Ensure that the embargo is exited."""

    _children = (EMinStateExited, RecognizeEmbargoExit)


class HandleEt(SequenceNode):
    """Handle embargo termination (ET) messages."""

    _children = (IsMsgTypeET, EnsureEmbargoExited)


class RecognizeRejection(SequenceNode):
    """Recognize a rejected embargo proposal, retuning to the EM.None state."""

    _children = (EMinStateProposed, q_em_to_N)


class EnsureRejectionRecognized(FallbackNode):
    """Ensure that the rejection is recognized and that the embargo is in the EM.None state."""

    _children = (EMinStateNone, RecognizeRejection)


class HandleEr(SequenceNode):
    """Handle embargo rejection (ER) messages."""

    _children = (IsMsgTypeER, EnsureRejectionRecognized)


class RecognizeProposal(SequenceNode):
    """Recognize an embargo proposal, transitioning to the EM.Proposed state."""

    _children = (EMinStateNone, q_em_to_P)


class EnsureProposalRecognized(FallbackNode):
    """Ensure that the proposal is recognized and that the embargo is in the EM.Proposed state."""

    _children = (EMinStateProposed, RecognizeProposal)


class HandleEp(SequenceNode):
    """Handle embargo proposal (EP) messages."""

    _children = (IsMsgTypeEP, EnsureProposalRecognized)


class RecognizeActivation(SequenceNode):
    """Recognize an embargo activation, transitioning to the EM.Active state."""

    _children = (EMinStateProposed, q_em_to_A)


class EnsureEmbargoActivated(FallbackNode):
    """Ensure that the embargo is activated and that the embargo is in the EM.Active state."""

    _children = (EMinStateActive, RecognizeActivation)


class HandleEa(SequenceNode):
    """Handle embargo activation (EA) messages."""

    _children = (IsMsgTypeEA, EnsureEmbargoActivated)


class RecognizeRevision(SequenceNode):
    """Recognize an embargo revision, transitioning to the EM.Revise state."""

    _children = (EMinStateActive, q_em_to_R)


class EnsureEmbargoRevisionRecognized(FallbackNode):
    """Ensure that the embargo is in the EM.Revise state."""

    _children = (EMinStateRevise, RecognizeRevision)


class HandleEv(SequenceNode):
    """Handle embargo revision (EV) messages."""

    _children = (IsMsgTypeEV, EnsureEmbargoRevisionRecognized)


class HandleEj(SequenceNode):
    """Handle embargo revision rejection (EJ) messages."""

    _children = (IsMsgTypeEJ, q_em_R_to_A)


class HandleEc(SequenceNode):
    """Handle embargo revision acceptance (EC) messages."""

    _children = (IsMsgTypeEC, q_em_to_A)


class SelectEjOrEcResponse(FallbackNode):
    """Select the appropriate response to an EJ or EC message."""

    _children = (HandleEj, HandleEc)


class HandleEjOrEcMsg(SequenceNode):
    """Handle an EJ or EC message."""

    _children = (EMinStateRevise, SelectEjOrEcResponse)


class EnsureEmActive(FallbackNode):
    """Ensure that the embargo is in the EM.Active state."""

    _children = (EMinStateActive, HandleEjOrEcMsg)


class CheckEjOrEcMsg(FallbackNode):
    """Check if the message is an EJ or EC message."""

    _children = (IsMsgTypeEJ, IsMsgTypeEC)


class HandleRevisionResponse(SequenceNode):
    """Handle a revision response. Always returns to the EM.Active state."""

    _children = (CheckEjOrEcMsg, EnsureEmActive)


class HandleMessagesInpxa(FallbackNode):
    """Handle embargo messages when the case state is compatible with an embargo."""

    _children = (HandleEp, HandleEa, HandleEv, HandleRevisionResponse)


class HandleCSpxa(SequenceNode):
    """Check if the case state is compatible with an embargo then handle embargo messages."""

    _children = (CSinStateNotPublicNoExploitNoAttacks, HandleMessagesInpxa)


class AvoidNonViableEmbargo(SequenceNode):
    """Avoid non-viable embargo states.
    If the case state is not compatible with an embargo, then the embargo is terminated.
    """

    _children = (
        CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
        TerminateEmbargoBt,
    )


class HandleAckable(FallbackNode):
    """Handle ackable messages."""

    _children = (
        HandleEe,
        HandleEt,
        HandleEr,
        HandleCSpxa,
        AvoidNonViableEmbargo,
    )


class HandleAndAckEmMsg(SequenceNode):
    """Handle an EM message and acknowledge it."""

    _children = (HandleAckable, EmitEK)


class HandleEmMessage(FallbackNode):
    """Handle an EM message. Emit an error (EE) message if there is an error."""

    _children = (IsMsgTypeEK, HandleAndAckEmMsg, EmitEE)


class ProcessEMMessagesBt(SequenceNode):
    """The bt tree for processing incoming EM messages."""

    _children = (IsEMMessage, HandleEmMessage)
