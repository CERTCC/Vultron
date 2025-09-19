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

from dataclasses import field
from typing import Optional, Sequence

from dataclasses_json import config

from vultron.as_vocab.base.links import as_Link
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
from vultron.as_vocab.base.utils import exclude_if_none
from vultron.as_vocab.objects.embargo_event import EmbargoEvent
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase


class EmProposeEmbargo(as_Invite):
    """The actor is proposing an embargo on the case.
    This corresponds to the Vultron Message Types EP and EV
    as_object: EmbargoEvent
    """

    as_type: str = field(default="Invite", init=False)

    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    context: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None, repr=True
    )


class EmAcceptEmbargo(as_Accept):
    """The actor is accepting an embargo on the case.
    This corresponds to the Vultron Message Types EA and EC
    as_object: the EmbargoEvent being rejected
    context: the VulnerabilityCase for which the EmbargoEvent was proposed
    origin: the EmProposeEmbargo activity that proposed the EmbargoEvent
    """

    as_type: str = field(default="Accept", init=False)

    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    context: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None, repr=True
    )
    in_reply_to: Optional[EmProposeEmbargo | as_Link | str] = field(
        default=None, repr=True
    )


class EmRejectEmbargo(as_Reject):
    """The actor is rejecting an embargo on the case.
    This corresponds to the Vultron Message Types ER and EJ
    as_object: the EmbargoEvent being rejected
    context: the VulnerabilityCase for which the EmbargoEvent was proposed
    in_reply_to: the EmProposeEmbargo activity that proposed the EmbargoEvent
    """

    as_type: str = field(default="Reject", init=False)

    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    context: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None, repr=True
    )
    in_reply_to: Optional[EmProposeEmbargo | as_Link | str] = field(
        default=None, repr=True
    )


class ChoosePreferredEmbargo(as_Question):
    """The case owner is asking the participants to indicate their embargo preferences from among the proposed embargoes.
    Case participants should respond with an EmAcceptEmbargo or EmRejectEmbargo activity for each proposed embargo.
    Either anyOf or oneOf should be specified, but not both.
    The Case owner will then need to decide which embargo to make active on the case.
    """

    # note: not specifying as_object here because Questions are intransitive

    as_type: str = field(default="Question", init=False)
    any_of: Optional[Sequence[EmbargoEvent | as_Link | str]] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    one_of: Optional[Sequence[EmbargoEvent | as_Link | str]] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )


class ActivateEmbargo(as_Add):
    """The case owner is activating an embargo on the case.
    This corresponds to the Vultron Message Types EA and EC at the case level
    as_object: the EmbargoEvent being activated
    target: the VulnerabilityCase for which the EmbargoEvent was proposed
    in_reply_to: the EmProposeEmbargo activity that proposed the EmbargoEvent
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None, repr=True
    )
    in_reply_to: Optional[EmProposeEmbargo | as_Link | str] = field(
        default=None, repr=True
    )


class AddEmbargoToCase(as_Add):
    """Add an EmbargoEvent to a case. This should only be performed by the case owner.
    For use when the case owner is activating an embargo on the case without first proposing it to the participants.
    See ActivateEmbargo for use when the case owner is activating an embargo on the case
    in response to a previous EmProposeEmbargo activity.
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None, repr=True
    )


class AnnounceEmbargo(as_Announce):
    """The case owner is announcing an embargo on the case.
    as_object: the EmbargoEvent being announced
    context: the VulnerabilityCase for which the EmbargoEvent is active
    """

    as_type: str = field(default="Announce", init=False)
    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    context: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None, repr=True
    )


# remove EmbargoEvent from proposedEmbargoes of VulnerabilityCase
# todo: should proposedEmbargoes be its own collection object that can then be used as the origin here?
class RemoveEmbargoFromCase(as_Remove):
    """Remove an EmbargoEvent from the proposedEmbargoes of a VulnerabilityCase.
    This should only be performed by the case owner.
    as_object: EmbargoEvent
    origin: VulnerabilityCase
    """

    as_type: str = field(default="Remove", init=False)
    as_object: Optional[EmbargoEvent | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    origin: Optional[VulnerabilityCase | as_Link | str] = field(default=None)
