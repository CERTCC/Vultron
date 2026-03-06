#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""
Provides Vultron Activity Streams Vocabulary classes for Embargo activities
"""

from typing import Sequence, TypeAlias

from pydantic import Field

from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Invite,
    as_Reject,
    as_Remove,
)
from vultron.as_vocab.objects.embargo_event import (
    EmbargoEventRef,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCaseRef


class EmProposeEmbargo(as_Invite):
    """The actor is proposing an embargo on the case.
    This corresponds to the Vultron Message Types EP and EV
    as_object: EmbargoEvent
    """

    as_object: EmbargoEventRef = Field(default=None, alias="object")
    context: VulnerabilityCaseRef = None


EmProposeEmbargoRef: TypeAlias = ActivityStreamRef[EmProposeEmbargo]


class EmAcceptEmbargo(as_Accept):
    """The actor is accepting an embargo proposal.
    This corresponds to the Vultron Message Types EA and EC.
    Per ActivityStreams convention: Accept(object=<Invite>) — the actor accepts
    the proposal activity itself, not the EmbargoEvent being proposed.
    as_object: the EmProposeEmbargo activity being accepted
    context: the VulnerabilityCase for which the embargo was proposed
    """

    as_object: EmProposeEmbargoRef = Field(default=None, alias="object")
    context: VulnerabilityCaseRef = None


class EmRejectEmbargo(as_Reject):
    """The actor is rejecting an embargo proposal.
    This corresponds to the Vultron Message Types ER and EJ.
    Per ActivityStreams convention: Reject(object=<Invite>) — the actor rejects
    the proposal activity itself, not the EmbargoEvent being proposed.
    as_object: the EmProposeEmbargo activity being rejected
    context: the VulnerabilityCase for which the embargo was proposed
    """

    as_object: EmProposeEmbargoRef = Field(default=None, alias="object")
    context: VulnerabilityCaseRef = None


class ChoosePreferredEmbargo(as_Question):
    """The case owner is asking the participants to indicate their embargo preferences from among the proposed embargoes.
    Case participants should respond with an EmAcceptEmbargo or EmRejectEmbargo activity for each proposed embargo.
    Either anyOf or oneOf should be specified, but not both.
    The Case owner will then need to decide which embargo to make active on the case.
    """

    # note: not specifying as_object here because Questions are intransitive

    any_of: Sequence[EmbargoEventRef] | None = None
    one_of: Sequence[EmbargoEventRef] | None = None


class ActivateEmbargo(as_Add):
    """The case owner is activating an embargo on the case.
    This corresponds to the Vultron Message Types EA and EC at the case level
    as_object: the EmbargoEvent being activated
    target: the VulnerabilityCase for which the EmbargoEvent was proposed
    in_reply_to: the EmProposeEmbargo activity that proposed the EmbargoEvent
    """

    as_object: EmbargoEventRef = Field(default=None, alias="object")
    target: VulnerabilityCaseRef = None
    in_reply_to: EmProposeEmbargoRef = None


class AddEmbargoToCase(as_Add):
    """Add an EmbargoEvent to a case. This should only be performed by the case owner.
    For use when the case owner is activating an embargo on the case without first proposing it to the participants.
    See ActivateEmbargo for use when the case owner is activating an embargo on the case
    in response to a previous EmProposeEmbargo activity.
    """

    as_object: EmbargoEventRef = Field(default=None, alias="object")
    target: VulnerabilityCaseRef = None


class AnnounceEmbargo(as_Announce):
    """The case owner is announcing an embargo on the case.
    as_object: the EmbargoEvent being announced
    context: the VulnerabilityCase for which the EmbargoEvent is active
    """

    as_object: EmbargoEventRef = Field(default=None, alias="object")
    context: VulnerabilityCaseRef = None


# remove EmbargoEvent from proposedEmbargoes of VulnerabilityCase
# todo: should proposedEmbargoes be its own collection object that can then be used as the origin here?
class RemoveEmbargoFromCase(as_Remove):
    """Remove an EmbargoEvent from the proposedEmbargoes of a VulnerabilityCase.
    This should only be performed by the case owner.
    as_object: EmbargoEvent
    origin: VulnerabilityCase
    """

    as_object: EmbargoEventRef = Field(default=None, alias="object")
    origin: VulnerabilityCaseRef = None
