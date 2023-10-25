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


from vultron.bt.base.factory import fallback, sequence
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


_HandleEe = sequence(
    "_HandleEe",
    """Handle embargo error (EE) messages.""",
    IsMsgTypeEE,
    FollowUpOnErrorMessage,
)


_RecognizeEmbargoExit = sequence(
    "_RecognizeEmbargoExit",
    """Recognize an embargo exit.""",
    EMinStateActiveOrRevise,
    q_em_to_X,
)


_EnsureEmbargoExited = fallback(
    "_EnsureEmbargoExited",
    """Ensure that the embargo is exited.""",
    EMinStateExited,
    _RecognizeEmbargoExit,
)


_HandleEt = sequence(
    "_HandleEt",
    """Handle embargo termination (ET) messages.""",
    IsMsgTypeET,
    _EnsureEmbargoExited,
)


_RecognizeRejection = sequence(
    "_RecognizeRejection",
    """Recognize a rejected embargo proposal, retuning to the EM.None state.""",
    EMinStateProposed,
    q_em_to_N,
)


_EnsureRejectionRecognized = fallback(
    "_EnsureRejectionRecognized",
    """Ensure that the rejection is recognized and that the embargo is in the EM.None state.""",
    EMinStateNone,
    _RecognizeRejection,
)


_HandleEr = sequence(
    "_HandleEr",
    """Handle embargo rejection (ER) messages.""",
    IsMsgTypeER,
    _EnsureRejectionRecognized,
)


_RecognizeProposal = sequence(
    "_RecognizeProposal",
    """Recognize an embargo proposal, transitioning to the EM.Proposed state.""",
    EMinStateNone,
    q_em_to_P,
)


_EnsureProposalRecognized = fallback(
    "_EnsureProposalRecognized",
    """Ensure that the proposal is recognized and that the embargo is in the EM.Proposed state.""",
    EMinStateProposed,
    _RecognizeProposal,
)


_HandleEp = sequence(
    "_HandleEp",
    """Handle embargo proposal (EP) messages.""",
    IsMsgTypeEP,
    _EnsureProposalRecognized,
)


_RecognizeActivation = sequence(
    "_RecognizeActivation",
    """Recognize an embargo activation, transitioning to the EM.Active state.""",
    EMinStateProposed,
    q_em_to_A,
)


_EnsureEmbargoActivated = fallback(
    "_EnsureEmbargoActivated",
    """Ensure that the embargo is activated and that the embargo is in the EM.Active state.""",
    EMinStateActive,
    _RecognizeActivation,
)


_HandleEa = sequence(
    "_HandleEa",
    """Handle embargo activation (EA) messages.""",
    IsMsgTypeEA,
    _EnsureEmbargoActivated,
)


_RecognizeRevision = sequence(
    "_RecognizeRevision",
    """Recognize an embargo revision, transitioning to the EM.Revise state.""",
    EMinStateActive,
    q_em_to_R,
)


_EnsureEmbargoRevisionRecognized = fallback(
    "_EnsureEmbargoRevisionRecognized",
    """Ensure that the embargo is in the EM.Revise state.""",
    EMinStateRevise,
    _RecognizeRevision,
)


_HandleEv = sequence(
    "_HandleEv",
    """Handle embargo revision (EV) messages.""",
    IsMsgTypeEV,
    _EnsureEmbargoRevisionRecognized,
)


_HandleEj = sequence(
    "_HandleEj",
    """Handle embargo revision rejection (EJ) messages.""",
    IsMsgTypeEJ,
    q_em_R_to_A,
)


_HandleEc = sequence(
    "_HandleEc",
    """Handle embargo revision acceptance (EC) messages.""",
    IsMsgTypeEC,
    q_em_to_A,
)


_SelectEjOrEcResponse = fallback(
    "_SelectEjOrEcResponse",
    """Select the appropriate response to an EJ or EC message.""",
    _HandleEj,
    _HandleEc,
)


_HandleEjOrEcMsg = sequence(
    "_HandleEjOrEcMsg",
    """Handle an EJ or EC message.""",
    EMinStateRevise,
    _SelectEjOrEcResponse,
)


_EnsureEmActive = fallback(
    "_EnsureEmActive",
    """Ensure that the embargo is in the EM.Active state.""",
    EMinStateActive,
    _HandleEjOrEcMsg,
)


_CheckEjOrEcMsg = fallback(
    "_CheckEjOrEcMsg",
    """Check if the message is an EJ or EC message.""",
    IsMsgTypeEJ,
    IsMsgTypeEC,
)


_HandleRevisionResponse = sequence(
    "_HandleRevisionResponse",
    """Handle a revision response. Always returns to the EM.Active state.""",
    _CheckEjOrEcMsg,
    _EnsureEmActive,
)


_HandleMessagesInpxa = fallback(
    "_HandleMessagesInpxa",
    """Handle embargo messages when the case state is compatible with an embargo.""",
    _HandleEp,
    _HandleEa,
    _HandleEv,
    _HandleRevisionResponse,
)


_HandleCSpxa = sequence(
    "_HandleCSpxa",
    """Check if the case state is compatible with an embargo then handle embargo messages.""",
    CSinStateNotPublicNoExploitNoAttacks,
    _HandleMessagesInpxa,
)


_AvoidNonViableEmbargo = sequence(
    "_AvoidNonViableEmbargo",
    """Avoid non-viable embargo states.
    If the case state is not compatible with an embargo, then the embargo is terminated.
    """,
    CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
    TerminateEmbargoBt,
)


_HandleAckable = fallback(
    "_HandleAckable",
    """Handle ackable messages.""",
    _HandleEe,
    _HandleEt,
    _HandleEr,
    _HandleCSpxa,
    _AvoidNonViableEmbargo,
)


_HandleAndAckEmMsg = sequence(
    "_HandleAndAckEmMsg",
    """Handle an EM message and acknowledge it.""",
    _HandleAckable,
    EmitEK,
)


_HandleEmMessage = fallback(
    "_HandleEmMessage",
    """Handle an EM message. Emit an error (EE) message if there is an error.""",
    IsMsgTypeEK,
    _HandleAndAckEmMsg,
    EmitEE,
)


ProcessEMMessagesBt = sequence(
    "ProcessEMMessagesBt",
    """The bt tree for processing incoming EM messages.""",
    IsEMMessage,
    _HandleEmMessage,
)


def main():
    show_graph(ProcessEMMessagesBt)


if __name__ == "__main__":
    main()
