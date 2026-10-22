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

from pydantic import Field, model_validator

from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    termination_reason_from_content,
)
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Announce,
    as_Create,
    as_Invite,
    as_Leave,
    as_Reject,
    as_Remove,
    as_Update,
)
from vultron.wire.as2.vocab.objects.embargo_consent import (
    as_EmbargoConsent,
)
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)


class _EmProposeEmbargoActivity(as_Invite):
    """The actor is proposing an embargo on the case.
    This corresponds to the Vultron Message Types EP and EV
    object_: as_EmbargoEvent, or its URI when the sender named the terms by
        reference.  An Invite received that way is still answered: the ER
        names the Invite by id and needs no terms (ADR-0123).
    """

    object_: as_EmbargoEvent | NonEmptyString = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    context: as_VulnerabilityCaseRef = None


class _EmAcceptEmbargoActivity(as_Accept):
    """The actor is accepting an embargo proposal.
    This corresponds to the Vultron Message Types EA and EC.
    Per ActivityStreams convention: Accept(object=<Invite>) — the actor accepts
    the proposal activity itself, not the as_EmbargoEvent being proposed.

    object_: the _EmProposeEmbargoActivity activity being accepted (inline typed
        object required — bare string IDs are rejected at construction time)
    context: the VulnerabilityCase for which the embargo was proposed
    """

    object_: _EmProposeEmbargoActivity = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    context: as_VulnerabilityCaseRef = None


class _EmRejectEmbargoActivity(as_Reject):
    """The actor is rejecting an embargo proposal.
    This corresponds to the Vultron Message Types ER and EJ.
    Per ActivityStreams convention: Reject(object=<Invite>) — the actor rejects
    the proposal activity itself, not the as_EmbargoEvent being proposed.

    object_: the _EmProposeEmbargoActivity activity being rejected (inline typed
        object required — bare string IDs are rejected at construction time)
    context: the VulnerabilityCase for which the embargo was proposed
    """

    object_: _EmProposeEmbargoActivity = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    context: as_VulnerabilityCaseRef = None


class _ActivateEmbargoActivity(as_Accept):
    """The case owner activates a proposed embargo on the case (ADR-0122).

    ``Accept(EmbargoEvent, target=VulnerabilityCase)``: the owner's decision
    for the case, distinct from ``Accept(Invite(EmbargoEvent))``, which is
    always the sender's own consent.  Only the case owner sends it.
    object_: the as_EmbargoEvent being activated (inline, so a recipient
        reads the terms without a dereference, VAM-05-010)
    target: the VulnerabilityCase the embargo was proposed for
    """

    object_: as_EmbargoEvent = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


class _RejectEmbargoProposalActivity(as_Reject):
    """The case owner rejects a proposed embargo on the case (ADR-0122).

    ``Reject(EmbargoEvent, target=VulnerabilityCase)``: the owner's decision
    for the case, distinct from ``Reject(Invite(EmbargoEvent))``, which is
    always the sender's own consent.  Only the case owner sends it.
    object_: the as_EmbargoEvent being rejected (inline, VAM-05-010)
    target: the VulnerabilityCase the embargo was proposed for
    """

    object_: as_EmbargoEvent = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


class _WithdrawFromEmbargoActivity(as_Leave):
    """A signatory withdraws from the embargo in force (MSM-07-010).

    ``Leave(EmbargoEvent)[context=VulnerabilityCase]``: the sender ends its
    own consent to the case's active embargo, which stays in force for
    everyone else (ADR-0122).  It answers no Invite, so it covers every
    signatory, including one made by seeding or by joining.  The case owner
    does not send it: it ends an embargo by terminating it.
    object_: the as_EmbargoEvent in force (inline, VAM-05-012)
    context: the VulnerabilityCase the embargo is on
    """

    object_: as_EmbargoEvent = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    context: as_VulnerabilityCaseRef = None


class _AnnounceEmbargoActivity(as_Announce):
    """The case owner is announcing an embargo on the case.
    object_: the as_EmbargoEvent being announced
    context: the VulnerabilityCase for which the as_EmbargoEvent is active
    """

    object_: as_EmbargoEvent = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    context: as_VulnerabilityCaseRef = None


class _RemoveEmbargoFromCaseActivity(as_Remove):
    """Remove the embargo in force from a VulnerabilityCase (ET).

    The receiver terminates the case's ``ACTIVE`` embargo register entry and
    cancels every open proposal in the same step, so EM derives ``EXITED``
    (MSM-07-006, ADR-0122).  A Remove naming an embargo that is only
    proposed changes nothing.  This should only be performed by the case
    owner, or by the CASE_MANAGER.
    object_: as_EmbargoEvent
    origin: VulnerabilityCase
    content: the termination's what — exactly ``END_TIME_REACHED`` or
        ``EARLY`` (ADR-0122); anything else is refused.  ``summary`` is a
        human-readable account the protocol does not read.
    termination_cause: the termination's why, when its sender names one,
        as ``terminationCause`` (EMB-13-004, EMB-13-005); an
        ``END_TIME_REACHED`` termination has none.
    """

    object_: as_EmbargoEvent = Field(
        default=..., validation_alias="object", serialization_alias="object"
    )
    origin: as_VulnerabilityCaseRef = None

    @model_validator(mode="after")
    def _content_is_a_termination_reason(self):
        EmbargoTermination.from_reason(
            termination_reason_from_content(self.content),
            self.termination_cause,
        )
        return self


class _CreateEmbargoConsentActivity(as_Create):
    """The CASE_MANAGER brought a consent row into existence (ADR-0122).

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    row in full, such as the ``UNINVITED`` row a proposal writes for a
    participant (CLP-07-013).  It is not a message any actor sends: it has no
    ``ActivityPattern`` and no ``MessageSemantics``.  Do not add a received
    route.

    object_: as_EmbargoConsent
    """

    object_: as_EmbargoConsent = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _UpdateEmbargoConsentActivity(as_Update):
    """The CASE_MANAGER changed a consent row (ADR-0122).

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    changed row in full, such as a ``CARRY_OVER`` at activation or the
    CASE_MANAGER's own policy consent (CLP-07-013).  Not a message any actor
    sends; do not add a received route.

    object_: as_EmbargoConsent
    """

    object_: as_EmbargoConsent = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
