#!/usr/bin/env python
# pyright: reportGeneralTypeIssues=false
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
"""Case participant role delegation: Offer, Accept and Reject (ADR-0039)."""

from typing import ClassVar

from pydantic import Field

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.activities.base import RepliesToObject
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_CarriedActor,
)
from vultron.wire.as2.vocab.objects.case_participant_role import (
    as_CaseParticipantRole,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class _OfferCaseParticipantRoleActivity(as_Offer):
    """Offer a CVDRole to an Actor in a VulnerabilityCase context (ADR-0039).

    Wire format: ``Offer(CaseParticipantRole)[context=VulnerabilityCase]``,
    whose ``target`` is the Actor offered the role.

    Replaces the deprecated ``_OfferCaseManagerRoleActivity`` for role
    delegation.  The ``object_`` carries the specific ``CVDRole`` being
    offered, making the activity self-describing and eliminating the
    target-field ambiguity of the previous format.

    object_: as_CaseParticipantRole (required — carries the CVDRole)
    target: the Actor receiving the role offer (required), as the sender
        holds it or as an actor reference (AKM-05-005, AKM-05-017)
    context: as_VulnerabilityCase or str URI (required)

    Declares **both** ``object_`` and ``target`` in
    :attr:`inline_required_refs`, because neither can be read back from the
    sender's store once collapsed to an id:

    - ``object_`` is minted inline by ``offer_case_participant_role_activity``
      and never persisted as a record of its own, so its id resolves to nothing
      (DL-08-001).  Since ``Offer`` is an initiating type, the outbox gate then
      refuses the whole activity for carrying a bare string (AKM-03-003).
    - ``target`` is the *peer* receiving the role.  Under ADR-0073 a peer's
      record lives in the store of whichever actor knows it, which is not the
      sender's (DL-08-003) — the same reason ``_RmInviteToCaseActivity``
      declares its invitee.

    This ``target`` is typed as an inline actor rather than a ref union, so an id
    there is not merely unresolvable but off-type: read-back yields a plain
    ``as_Offer`` that no longer matches this class, and the receiver cannot
    dispatch it at all.

    See SE-08-003, ADR-0039.
    """

    object_: as_CaseParticipantRole = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_CarriedActor = Field(
        ..., validation_alias="target", serialization_alias="target"
    )
    context: as_VulnerabilityCase | NonEmptyString = Field(
        ..., validation_alias="context", serialization_alias="context"
    )

    inline_required_refs: ClassVar[frozenset[str]] = frozenset(
        {"object_", "target"}
    )


class _AcceptCaseParticipantRoleActivity(RepliesToObject, as_Accept):
    """Target actor accepts the canonical role-delegation offer (ADR-0039).

    - object_: the ``_OfferCaseParticipantRoleActivity`` being accepted
    See SE-08-003, ADR-0039.
    """

    object_: _OfferCaseParticipantRoleActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RejectCaseParticipantRoleActivity(RepliesToObject, as_Reject):
    """Target actor rejects the canonical role-delegation offer (ADR-0039).

    - object_: the ``_OfferCaseParticipantRoleActivity`` being rejected
    See SE-08-003, ADR-0039.
    """

    object_: _OfferCaseParticipantRoleActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
