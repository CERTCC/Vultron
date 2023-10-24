#!/usr/bin/env python
"""file: embargo_management
author: adh
created_at: 4/5/22 12:29 PM

This module contains the bt tree nodes for the Embargo Management activity.

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
    CSinStateFixDeployed,
    CSinStateFixNotDeployed,
    CSinStateFixReady,
    CSinStateNotPublicNoExploitNoAttacks,
    CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
)
from vultron.bt.embargo_management.conditions import (
    EMinStateActive,
    EMinStateActiveOrRevise,
    EMinStateExited,
    EMinStateNone,
    EMinStateNoneOrExited,
    EMinStateNoneOrPropose,
    EMinStateProposeOrRevise,
    EMinStateProposed,
    EMinStateRevise,
)
from vultron.bt.embargo_management.fuzzer import (
    AvoidEmbargoCounterProposal,
    CurrentEmbargoAcceptable,
    EmbargoTimerExpired,
    EvaluateEmbargoProposal,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoAccept,
    OnEmbargoExit,
    OnEmbargoReject,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WillingToCounterEmbargoProposal,
)
from vultron.bt.embargo_management.transitions import (
    q_em_R_to_A,
    q_em_to_A,
    q_em_to_N,
    q_em_to_P,
    q_em_to_R,
    q_em_to_X,
)
from vultron.bt.messaging.outbound.behaviors import (
    EmitEA,
    EmitEJ,
    EmitEP,
    EmitER,
    EmitET,
    EmitEV,
)
from vultron.bt.report_management.conditions import (
    RMinStateStartOrClosed,
)
from vultron.bt.roles.conditions import RoleIsNotDeployer


class _MaybeExitWhenDeployed(SequenceNode):
    """Sequence node for transitioning from R to X when the case state is in Fix Deployed."""

    _children = (CSinStateFixDeployed, ExitEmbargoWhenDeployed)


class _MaybeExitWhenFixReady(SequenceNode):
    """Sequence node for transitioning from R to X when the case state is in Fix Ready."""

    _children = (CSinStateFixReady, RoleIsNotDeployer, ExitEmbargoWhenFixReady)


class _OtherReasonToExitEmbargo(FallbackNode):
    """Fallback node for transitioning from R to X. Allows for various other reasons to exit an embargo."""

    _children = (
        _MaybeExitWhenDeployed,
        _MaybeExitWhenFixReady,
        ExitEmbargoForOtherReason,
    )


class _AvoidNewEmbargoesInCsDeployedUnlessReason(FallbackNode):
    """Avoid proposing new embargoes when the case state is in Fix Deployed unless there is a reason to do so."""

    _children = (CSinStateFixNotDeployed, ReasonToProposeEmbargoWhenDeployed)


class _AvoidCounterProposal(SequenceNode):
    """Avoid counter-proposing an embargo when the current embargo is acceptable."""

    _children = (EMinStateProposeOrRevise, AvoidEmbargoCounterProposal)


class _ProposeNewEmbargo(SequenceNode):
    """Propose a new embargo.
    Steps:
    1. Check if the EM state is in None or Proposed.
    2. Transition to Proposed.
    3. Emit an EP message indicating a new embargo is being proposed.
    """

    _children = (EMinStateNoneOrPropose, q_em_to_P, EmitEP)


class _ProposeEmbargoRevision(SequenceNode):
    """Propose a revision to the current embargo.
    Steps:
    1. Check if the EM state is in Active or Revise.
    2. Transition to Revise.
    3. Emit an EV message indicating the current embargo is being revised.
    """

    _children = (EMinStateActiveOrRevise, q_em_to_R, EmitEV)


class _ConsiderProposingEmbargo(FallbackNode):
    """Consider proposing an embargo.
    Steps:
    1. Generally avoid counter-proposing an embargo in favor of
    accepting the existing proposal and proposing a revision.
    2. Propose a new embargo.
    3. Propose a revision to the current embargo.
    """

    _children = (
        _AvoidCounterProposal,
        _ProposeNewEmbargo,
        _ProposeEmbargoRevision,
    )


class _ProposeEmbargoBt(SequenceNode):
    """Propose an embargo.
    Steps:
    1. Check if the EM state is in None or Proposed.
    2. Check if the case state is in Fix Not Deployed.
    3. Check if there is a reason to propose an embargo.
    4. Choose the terms of the potential embargo offer.
    5. Decide on whether to propose an embargo.
    """

    _children = (
        CSinStateNotPublicNoExploitNoAttacks,
        _AvoidNewEmbargoesInCsDeployedUnlessReason,
        SelectEmbargoOfferTerms,
        _ConsiderProposingEmbargo,
    )


class _SufficientCauseToAbandonProposedEmbargo(FallbackNode):
    """Determine if there is sufficient cause to abandon the proposed embargo.
    Reasons to abandon:
    1. The public is already aware of the vulnerability
    2. An exploit is already public
    3. Attacks have already been observed
    4. Another reason not covered by the above
    """

    _children = (
        CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
        _OtherReasonToExitEmbargo,
    )


class _ConsiderAbandoningProposedEmbargo(SequenceNode):
    """Consider abandoning the proposed embargo.
    Steps:
    1. Check if the EM state is in Proposed.
    2. Check if there is sufficient cause to abandon the proposed embargo.
    3. Transition to None.
    4. Emit an ER message indicating the proposed embargo was rejected.
    """

    _children = (
        EMinStateProposed,
        _SufficientCauseToAbandonProposedEmbargo,
        q_em_to_N,
        EmitER,
    )


class _SufficientCauseToTerminateActiveEmbargo(FallbackNode):
    """Determine if there is sufficient cause to terminate the active embargo.
    Reasons to terminate:
    1. The public is already aware of the vulnerability
    2. An exploit is already public
    3. Attacks have already been observed
    4. The embargo timer has expired
    5. Another reason not covered by the above
    """

    _children = (
        CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
        EmbargoTimerExpired,
        _OtherReasonToExitEmbargo,
    )


class _ConsiderTerminatingActiveEmbargo(SequenceNode):
    """Consider terminating the active embargo.
    Steps:
    1. Check if the EM state is in Active or Revise.
    2. Check if there is sufficient cause to terminate the active embargo.
    3. Transition to Exited.
    4. Emit an ET message.
    """

    _children = (
        EMinStateActiveOrRevise,
        _SufficientCauseToTerminateActiveEmbargo,
        OnEmbargoExit,
        q_em_to_X,
        EmitET,
    )


class TerminateEmbargoBt(FallbackNode):
    """Terminate the embargo if the case state is in a state where the embargo should be terminated."""

    _children = (
        EMinStateNoneOrExited,
        _ConsiderAbandoningProposedEmbargo,
        _ConsiderTerminatingActiveEmbargo,
    )


class _EnsureSufficientEffortToAchieveEmbargo(FallbackNode):
    """Continue to propose embargoes until sufficient effort has been made."""

    _children = (StopProposingEmbargo, _ProposeEmbargoBt)


class _EmNone(SequenceNode):
    """Check if the EM state is None.
    If so, continue to propose embargoes until sufficient effort has been made.
    """

    _children = (EMinStateNone, _EnsureSufficientEffortToAchieveEmbargo)


# noinspection PyPep8Naming
class _AvoidNewEmbargoWhenNotInCs_pxa(SequenceNode):
    """Avoid proposing new embargoes when
    the public is aware of the vulnerability or
    an exploit is already public or
    attacks have been observed.
    """

    _children = (
        CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
        EMinStateNone,
    )


class _EvaluateAndAcceptProposedEmbargo(SequenceNode):
    """If the proposed embargo is acceptable, it will be accepted and
    the EM state will transition to the Active state.
    An EA message will be emitted.
    """

    _children = (EvaluateEmbargoProposal, OnEmbargoAccept, q_em_to_A, EmitEA)


class _CounterEmbargoProposal(SequenceNode):
    """If there is willingness to counter a proposed embargo,
    an embargo counter-proposal will be made.
    """

    _children = (WillingToCounterEmbargoProposal, _ProposeEmbargoBt)


class _RejectProposedEmbargo(SequenceNode):
    """Rejects a proposed embargo.
    The EM state returns to the None.
    An ER message is emitted.
    """

    _children = (OnEmbargoReject, q_em_to_N, EmitER)


class _ChooseEmProposedResponse(FallbackNode):
    """Chooses a response to a proposed embargo.
    Options are:
    - Terminate the embargo
    - Accept the proposed embargo and transition to the Active state
    - Counter the proposed embargo and stay in the Proposed state
    - Reject the proposed embargo, returning to the None state
    """

    _children = (
        TerminateEmbargoBt,
        _EvaluateAndAcceptProposedEmbargo,
        _CounterEmbargoProposal,
        _RejectProposedEmbargo,
    )


class _EmProposed(SequenceNode):
    """Embargo management bt tree for the Proposed state.
    Checks the EM state and chooses a response.
    """

    _children = (EMinStateProposed, _ChooseEmProposedResponse)


class _ChooseEmActiveResponse(FallbackNode):
    """Chooses a response to an active embargo.
    Options are:
    - Terminate the embargo
    - Keep the current embargo
    - Propose a new embargo
    """

    _children = (
        TerminateEmbargoBt,
        CurrentEmbargoAcceptable,
        _ProposeEmbargoBt,
    )


class _EmActive(SequenceNode):
    """Embargo management bt tree for the Active state.
    Checks the EM state and chooses a response.
    """

    _children = (EMinStateActive, _ChooseEmActiveResponse)


class _RejectRevision(SequenceNode):
    """Rejects a proposed embargo revision.
    The EM state returns to Active and the current embargo is retained.
    An EJ message is emitted.
    """

    _children = (OnEmbargoReject, q_em_R_to_A, EmitEJ)


class _ChooseEmReviseResponse(FallbackNode):
    """Chooses a response to a proposed embargo revision.
    Options are:
    - Terminate the embargo
    - Evaluate and accept the proposed embargo
    - Counter the proposed embargo
    - Reject the proposed embargo and return to the Active state with the current embargo
    """

    _children = (
        TerminateEmbargoBt,
        _EvaluateAndAcceptProposedEmbargo,
        _CounterEmbargoProposal,
        _RejectRevision,
    )


class _EmRevise(SequenceNode):
    """Embargo management bt tree for the Revise state.
    Checks the EM state and chooses the appropriate response.
    """

    _children = (EMinStateRevise, _ChooseEmReviseResponse)


class EmbargoManagementBt(FallbackNode):
    """This is the top-level node for the embargo management bt tree.
    It is responsible for choosing the appropriate embargo management bt tree for the current state.
    """

    _children = (
        RMinStateStartOrClosed,
        EMinStateExited,
        _AvoidNewEmbargoWhenNotInCs_pxa,
        _EmNone,
        _EmProposed,
        _EmActive,
        _EmRevise,
    )
