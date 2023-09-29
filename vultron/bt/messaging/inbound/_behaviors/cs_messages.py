#!/usr/bin/env python
"""file: cs_messages
author: adh
created_at: 6/27/22 1:27 PM

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


from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.case_state.conditions import (
    CSinStateAttacksObserved,
    CSinStateExploitPublic,
    CSinStatePublicAware,
    CSinStatePublicAwareAndExploitPublic,
)
from vultron.bt.case_state.transitions import q_cs_to_A, q_cs_to_P, q_cs_to_X
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


class HandleCe(SequenceNode):
    """Handle CE messages."""

    _children = (IsMsgTypeCE, FollowUpOnErrorMessage)


class EnsureCsInP(FallbackNode):
    """Ensure that the case state is in the public aware state."""

    _children = (CSinStatePublicAware, q_cs_to_P)


class HandleCp(SequenceNode):
    """Handle CP messages.
    If the case state is not in the public aware state, transition to it.
    """

    _children = (IsMsgTypeCP, EnsureCsInP)


class EnsureCsInX(FallbackNode):
    """Ensure that the case state is in the exploit public state."""

    _children = (CSinStateExploitPublic, q_cs_to_X)


class CsToXThenP(SequenceNode):
    """Transition to the exploit public state, then to the public aware state.
    Emit a CP message to indicate that the case state has changed.
    """

    _children = (EnsureCsInX, EnsureCsInP, EmitCP)


class EnsureCsInPX(FallbackNode):
    """Ensure that the case state is in the PUBLIC_AWARE and EXPLOIT_PUBLIC states."""

    _children = (CSinStatePublicAwareAndExploitPublic, CsToXThenP)


class HandleCx(SequenceNode):
    """Handle CX messages.
    If the case state is not in the PUBLIC_AWARE and EXPLOIT_PUBLIC states, transition to them.
    """

    _children = (IsMsgTypeCX, EnsureCsInPX)


class EnsureCsInA(FallbackNode):
    """Ensure that the case state is in the ATTACKS_OBSERVED state."""

    _children = (CSinStateAttacksObserved, q_cs_to_A)


class HandleCa(SequenceNode):
    """Handle CA messages.
    If the case state is not in the ATTACKS_OBSERVED state, transition to it.
    """

    _children = (IsMsgTypeCA, EnsureCsInA)


class CpCxCa(FallbackNode):
    """Handle CP, CX, and CA messages."""

    _children = (HandleCp, HandleCx, HandleCa)


class HandleCpCxCa(SequenceNode):
    """Handle CP, CX, and CA messages, and terminate any embargo that may be in effect."""

    _children = (CpCxCa, TerminateEmbargoBt)


# The status of some other vendor doesn't really affect us, so we don't do anything fancy here.
HandleCv = IsMsgTypeCV
HandleCf = IsMsgTypeCF
HandleCd = IsMsgTypeCD


class HandleAckableCsMessages(FallbackNode):
    """
    Handle CP, CX, CA, CV, CF, and CD messages.
    """

    _children = (HandleCpCxCa, HandleCv, HandleCf, HandleCd, HandleCe)


class HandleAndAckNormalCsMessages(SequenceNode):
    """Handle CP, CX, CA, CV, CF, and CD messages, and emit a CK message to acknowledge receipt."""

    _children = (HandleAckableCsMessages, EmitCK)


class HandleCsMessageTypes(FallbackNode):
    """Handle CP, CX, CA, CV, CF, CD, and CE messages.
    Emit a CE message if there is an error.
    """

    _children = (IsMsgTypeCK, HandleAndAckNormalCsMessages, EmitCE)


class ProcessCSMessagesBt(SequenceNode):
    """Behavior tree for processing CS messages."""

    _children = (IsCSMessage, HandleCsMessageTypes)
