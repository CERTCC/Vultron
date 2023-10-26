#!/usr/bin/env python
"""
This module contains the behaviors that are used by the inbound message handler to process CS messages.
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


from vultron.bt.base.factory import fallback_node, sequence_node
from vultron.bt.case_state.conditions import (
    CSinStateAttacksObserved,
    CSinStateExploitPublic,
    CSinStatePublicAware,
    CSinStatePublicAwareAndExploitPublic,
)
from vultron.bt.case_state.transitions import q_cs_to_A, q_cs_to_P, q_cs_to_X
from vultron.bt.common import show_graph
from vultron.bt.embargo_management.behaviors import TerminateEmbargoBt
from vultron.bt.messaging.conditions import (
    IsCSMessage,
    IsMsgTypeCA,
    IsMsgTypeCD,
    IsMsgTypeCE,
    IsMsgTypeCF,
    IsMsgTypeCK,
    IsMsgTypeCP,
    IsMsgTypeCV,
    IsMsgTypeCX,
)
from vultron.bt.messaging.inbound._behaviors.fuzzer import (
    FollowUpOnErrorMessage,
)
from vultron.bt.messaging.outbound.behaviors import EmitCE, EmitCK, EmitCP


# CS messages


_HandleCe = sequence_node("_HandleCe", """Handle CE messages.""", IsMsgTypeCE, FollowUpOnErrorMessage)


_EnsureCsInP = fallback_node("_EnsureCsInP", """Ensure that the case state is in the public aware state.""",
                             CSinStatePublicAware, q_cs_to_P)


_HandleCp = sequence_node("_HandleCp", """Handle CP messages.
    If the case state is not in the public aware state, transition to it.
    """, IsMsgTypeCP, _EnsureCsInP)


_EnsureCsInX = fallback_node("_EnsureCsInX", """Ensure that the case state is in the exploit public state.""",
                             CSinStateExploitPublic, q_cs_to_X)


_CsToXThenP = sequence_node("_CsToXThenP", """Transition to the exploit public state, then to the public aware state.
    Emit a CP message to indicate that the case state has changed.
    """, _EnsureCsInX, _EnsureCsInP, EmitCP)


_EnsureCsInPX = fallback_node("_EnsureCsInPX",
                              """Ensure that the case state is in the PUBLIC_AWARE and EXPLOIT_PUBLIC states.""",
                              CSinStatePublicAwareAndExploitPublic, _CsToXThenP)


_HandleCx = sequence_node("_HandleCx", """Handle CX messages.
    If the case state is not in the PUBLIC_AWARE and EXPLOIT_PUBLIC states, transition to them.
    """, IsMsgTypeCX, _EnsureCsInPX)


_EnsureCsInA = fallback_node("_EnsureCsInA", """Ensure that the case state is in the ATTACKS_OBSERVED state.""",
                             CSinStateAttacksObserved, q_cs_to_A)


_HandleCa = sequence_node("_HandleCa", """Handle CA messages.
    If the case state is not in the ATTACKS_OBSERVED state, transition to it.
    """, IsMsgTypeCA, _EnsureCsInA)


_CpCxCa = fallback_node("_CpCxCa", """Handle CP, CX, and CA messages.""", _HandleCp, _HandleCx, _HandleCa)


_HandleCpCxCa = sequence_node("_HandleCpCxCa",
                              """Handle CP, CX, and CA messages, and terminate any embargo that may be in effect.""",
                              _CpCxCa, TerminateEmbargoBt)


# The status of some other vendor doesn't really affect us, so we don't do anything fancy here.
_HandleCv = IsMsgTypeCV
_HandleCf = IsMsgTypeCF
_HandleCd = IsMsgTypeCD


_HandleAckableCsMessages = fallback_node("_HandleAckableCsMessages", """
    Handle CP, CX, CA, CV, CF, and CD messages.
    """, _HandleCpCxCa, _HandleCv, _HandleCf, _HandleCd, _HandleCe)


_HandleAndAckNormalCsMessages = sequence_node("_HandleAndAckNormalCsMessages",
                                              """Handle CP, CX, CA, CV, CF, and CD messages, and emit a CK message to acknowledge receipt.""",
                                              _HandleAckableCsMessages, EmitCK)


_HandleCsMessageTypes = fallback_node("_HandleCsMessageTypes", """Handle CP, CX, CA, CV, CF, CD, and CE messages.
    Emit a CE message if there is an error.
    """, IsMsgTypeCK, _HandleAndAckNormalCsMessages, EmitCE)


ProcessCSMessagesBt = sequence_node("ProcessCSMessagesBt", """Behavior tree for processing CS messages.""", IsCSMessage,
                                    _HandleCsMessageTypes)


def main():
    show_graph(ProcessCSMessagesBt)


if __name__ == "__main__":
    main()
