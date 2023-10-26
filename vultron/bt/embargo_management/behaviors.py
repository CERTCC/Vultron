#!/usr/bin/env python
"""
Provides behavior tree nodes for the Embargo Management process.
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
    CSinStateFixDeployed,
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

_MaybeExitWhenDeployed = sequence_node("MaybeExitWhenDeployed",
                                       "Sequence node for transitioning from R to X when the case state is in Fix Deployed.",
                                       CSinStateFixDeployed, ExitEmbargoWhenDeployed)

_MaybeExitWhenFixReady = sequence_node("MaybeExitWhenFixReady",
                                       "Sequence node for transitioning from R to X when the case state is in Fix Ready.",
                                       CSinStateFixReady, RoleIsNotDeployer, ExitEmbargoWhenFixReady)

_OtherReasonToExitEmbargo = fallback_node("OtherReasonToExitEmbargo",
                                          "Fallback node for transitioning from R to X. Allows for various other reasons to exit an embargo.",
                                          _MaybeExitWhenDeployed, _MaybeExitWhenFixReady, ExitEmbargoForOtherReason)

_AvoidNewEmbargoesInCsDeployedUnlessReason = fallback_node("AvoidNewEmbargoesInCsDeployedUnlessReason",
                                                           "Fallback node for avoiding new embargoes when the case state is in Fix Deployed unless there is a reason to do so.",
                                                           CSinStateFixDeployed, ReasonToProposeEmbargoWhenDeployed)

_AvoidCounterProposal = sequence_node("AvoidCounterProposal",
                                      "Sequence node for avoiding counter-proposing an embargo when the current embargo is acceptable.",
                                      EMinStateProposeOrRevise, AvoidEmbargoCounterProposal)

_ProposeNewEmbargo = sequence_node("ProposeNewEmbargo",
                                   "Sequence node for proposing a new embargo. Steps: 1. Check if the EM state is in None or Proposed. 2. Transition "
                                   "to Proposed. 3. Emit an EP message indicating a new embargo is being proposed.",
                                   EMinStateNoneOrPropose, q_em_to_P, EmitEP)

_ProposeEmbargoRevision = sequence_node("ProposeEmbargoRevision",
                                        "Sequence node for proposing a revision to the current embargo. Steps: 1. Check if the EM state is in Active or "
                                        "Revise. 2. Transition to Revise. 3. Emit an EV message indicating the current embargo is being revised.",
                                        EMinStateActiveOrRevise, q_em_to_R, EmitEV)

_ConsiderProposingEmbargo = fallback_node("ConsiderProposingEmbargo",
                                          "Fallback node for considering proposing an embargo. Steps: 1. Generally avoid counter-proposing an embargo in "
                                          "favor of accepting the existing proposal and proposing a revision. 2. Propose a new embargo. 3. Propose a "
                                          "revision to the current embargo.", _AvoidCounterProposal, _ProposeNewEmbargo,
                                          _ProposeEmbargoRevision)

_ProposeEmbargoBt = sequence_node("ProposeEmbargoBt", """Propose an embargo.
    Steps:
    1. Check if the EM state is in None or Proposed.
    2. Check if the case state is in Fix Not Deployed.
    3. Check if there is a reason to propose an embargo.
    4. Choose the terms of the potential embargo offer.
    5. Decide on whether to propose an embargo.
    """, EMinStateNoneOrPropose, CSinStateNotPublicNoExploitNoAttacks, _AvoidNewEmbargoesInCsDeployedUnlessReason,
                                  SelectEmbargoOfferTerms, _ConsiderProposingEmbargo)

_SufficientCauseToAbandonProposedEmbargo = fallback_node("SufficientCauseToAbandonProposedEmbargo", """Determine if there is sufficient cause to abandon the proposed embargo.
    Reasons to abandon:
    1. The public is already aware of the vulnerability
    2. An exploit is already public
    3. Attacks have already been observed
    4. Another reason not covered by the above
    """, CSinStatePublicAwareOrExploitPublicOrAttacksObserved, _OtherReasonToExitEmbargo)


_ConsiderAbandoningProposedEmbargo = sequence_node("ConsiderAbandoningProposedEmbargo", """Consider abandoning the proposed embargo.
    Steps:
    1. Check if the EM state is in Proposed.
    2. Check if there is sufficient cause to abandon the proposed embargo.
    3. Transition to None.
    4. Emit an ER message indicating the proposed embargo was rejected.
    """, EMinStateProposed, _SufficientCauseToAbandonProposedEmbargo, q_em_to_N, EmitER)

_SufficientCauseToTerminateActiveEmbargo = fallback_node("SufficientCauseToTerminateActiveEmbargo", """Determine if there is sufficient cause to terminate the active embargo.
    Reasons to terminate:
    1. The public is already aware of the vulnerability
    2. An exploit is already public
    3. Attacks have already been observed
    4. The embargo timer has expired
    5. Another reason not covered by the above
    """, CSinStatePublicAwareOrExploitPublicOrAttacksObserved, EmbargoTimerExpired, _OtherReasonToExitEmbargo)

_ConsiderTerminatingActiveEmbargo = sequence_node("ConsiderTerminatingActiveEmbargo", """Consider terminating the active embargo.
    Steps:
    1. Check if the EM state is in Active or Revise.
    2. Check if there is sufficient cause to terminate the active embargo.
    3. Transition to Exited.
    4. Emit an ET message.
    """, EMinStateActiveOrRevise, _SufficientCauseToTerminateActiveEmbargo, OnEmbargoExit, q_em_to_X, EmitET)

TerminateEmbargoBt = fallback_node("TerminateEmbargoBt",
                                   """Terminate the embargo if the case state is in a state where the embargo should be terminated.""",
                                   EMinStateNoneOrExited, _ConsiderAbandoningProposedEmbargo,
                                   _ConsiderTerminatingActiveEmbargo)

_EnsureSufficientEffortToAchieveEmbargo = fallback_node("EnsureSufficientEffortToAchieveEmbargo",
                                                        """Continue to propose embargoes until sufficient effort has been made.""",
                                                        StopProposingEmbargo, _ProposeEmbargoBt)

_EmNone = sequence_node("EmNone", """Check if the EM state is None.
    If so, continue to propose embargoes until sufficient effort has been made.
    """, EMinStateNone, _EnsureSufficientEffortToAchieveEmbargo)


# noinspection PyPep8Naming
_AvoidNewEmbargoWhenNotInCs_pxa = sequence_node("AvoidNewEmbargoWhenNotInCs_pxa", """Avoid proposing new embargoes when
    the public is aware of the vulnerability or
    an exploit is already public or
    attacks have been observed.
    """, CSinStatePublicAwareOrExploitPublicOrAttacksObserved, EMinStateNone)

_EvaluateAndAcceptProposedEmbargo = sequence_node("EvaluateAndAcceptProposedEmbargo", """If the proposed embargo is acceptable, it will be accepted and
    the EM state will transition to the Active state.
    An EA message will be emitted.
    """, EvaluateEmbargoProposal, OnEmbargoAccept, q_em_to_A, EmitEA)

_CounterEmbargoProposal = sequence_node("CounterEmbargoProposal", """If there is willingness to counter a proposed embargo,
    an embargo counter-proposal will be made.
    """, WillingToCounterEmbargoProposal, _ProposeEmbargoBt)

_RejectProposedEmbargo = sequence_node("RejectProposedEmbargo", """Rejects a proposed embargo.
    The EM state returns to None.
    An ER message is emitted.
    """, OnEmbargoReject, q_em_to_N, EmitER)

_ChooseEmProposedResponse = fallback_node("ChooseEmProposedResponse", """Chooses a response to a proposed embargo.
    Options are:
    - Terminate the embargo
    - Accept the proposed embargo and transition to the Active state
    - Counter the proposed embargo and stay in the Proposed state
    - Reject the proposed embargo, returning to the None state
    """, TerminateEmbargoBt, _EvaluateAndAcceptProposedEmbargo, _CounterEmbargoProposal, _RejectProposedEmbargo)


_EmProposed = sequence_node("EmProposed", """Embargo management bt tree for the Proposed state.
    Checks the EM state and chooses a response.
    """, EMinStateProposed, _ChooseEmProposedResponse)

_ChooseEmActiveResponse = fallback_node("ChooseEmActiveResponse", """Chooses a response to an active embargo.
    Options are:
    - Terminate the embargo
    - Keep the current embargo
    - Propose a new embargo
    """, TerminateEmbargoBt, CurrentEmbargoAcceptable, _ProposeEmbargoBt)


_EmActive = sequence_node("EmActive", """Embargo management bt tree for the Active state.
    Checks the EM state and chooses a response.
    """, EMinStateActive, _ChooseEmActiveResponse)


_RejectRevision = sequence_node("RejectRevision", """Rejects a proposed embargo revision.
    The EM state returns to Active and the current embargo is retained.
    An EJ message is emitted.
    """, OnEmbargoReject, q_em_R_to_A, EmitEJ)

_ChooseEmReviseResponse = fallback_node("ChooseEmReviseResponse", """Chooses a response to a proposed embargo revision.
    Options are:
    - Terminate the embargo
    - Evaluate and accept the proposed embargo
    - Counter the proposed embargo
    - Reject the proposed embargo and return to the Active state with the current embargo
    """, TerminateEmbargoBt, _EvaluateAndAcceptProposedEmbargo, _CounterEmbargoProposal, _RejectRevision)


_EmRevise = sequence_node("EmRevise", """Embargo management bt tree for the Revise state.
    Checks the EM state and chooses the appropriate response.
    """, EMinStateRevise, _ChooseEmReviseResponse)

EmbargoManagementBt = fallback_node("EmbargoManagementBt", """This is the top-level node for the embargo management bt tree.
    It is responsible for choosing the appropriate embargo management bt tree for the current state.
    """, RMinStateStartOrClosed, EMinStateExited, _AvoidNewEmbargoWhenNotInCs_pxa, _EmNone, _EmProposed, _EmActive,
                                    _EmRevise)
