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
"""Case invitations: the stub Invite, the full-case Invite and their replies."""

from typing import Any, ClassVar

from pydantic import Field, model_validator

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_CarriedActor,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)


class _RmInviteToCaseActivity(as_Invite):
    """The actor is inviting another actor to a case.
    This corresponds to the Vultron Message Type RS when a case already exists.
    See also _RmSubmitReportActivity for the scenario when a case does not exist yet.
    object_: the Actor being invited
    target: the ``as_VulnerabilityCaseStub`` naming the case (CM-11-013);
        required, so an Invite whose target is a URI or a full case is not
        this class
    roles: inherited from as_Invite (CM-17-003)

    Declares ``object_`` in :attr:`inline_required_refs` (DL-08-003). The
    invitee is by definition a *peer* — under ADR-0073 its record lives in the
    store of whichever actor knows it, and the sender here is the Case Actor,
    which does not. Dehydrating the invitee to its id therefore had nothing to
    read it back from, so the stored Invite came back carrying a bare string and
    outbox delivery refused it (AKM-03-003) after exhausting its retries. The
    invitation never arrived, and the invitee's ``reject-case-invite`` then
    answered 404 for an invite it had never been told about (#2548, rcv-reject).
    """

    object_: as_CarriedActor = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseStub = Field(...)

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})


class _RmAcceptInviteToCaseActivity(as_Accept):
    """The actor is accepting an invitation to a case.
    This corresponds to the Vultron Message Type RV when the case already exists.
    See also _RmValidateReportActivity for the scenario when the case does not exist yet.

    object_: the _RmInviteToCaseActivity being accepted (inline typed object
        required — bare string IDs are rejected at construction time)
    """

    object_: _RmInviteToCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def set_in_reply_to_from_invite(self):
        if self.in_reply_to is None:
            object.__setattr__(self, "in_reply_to", self.object_.id_)
        return self


class _RmRejectInviteToCaseActivity(as_Reject):
    """The actor is rejecting an invitation to a case.
    This corresponds to the Vultron Message Type RI when the case already exists.
    See also _RmInvalidateReportActivity for the scenario when the case does not exist yet.

    `object_`: the `_RmInviteToCaseActivity` being rejected (inline typed
        object required — bare string IDs are rejected at construction time)
    """

    object_: _RmInviteToCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def set_in_reply_to_from_invite(self):
        if self.in_reply_to is None:
            object.__setattr__(self, "in_reply_to", self.object_.id_)
        return self


def _check_ledger_position(activity: Any, what: str) -> None:
    """Require *activity* to state its sender's ledger position.

    The full-case Invite and its replies carry it in ``ledgerPosition``, the
    property every case activity states (SYNC-18-001, VAM-04-011, ADR-0156);
    the field itself validates its shape, so only its absence is checked.
    """
    if activity.ledger_position is None:
        raise ValueError(f"{what} must carry its `ledgerPosition`")


class _RmInviteToFullCaseActivity(as_Invite):
    """The CASE_MANAGER asks a joined participant to judge the case.

    ``Invite(Actor)[target=VulnerabilityCase]`` — the full-case Invite
    (VAM-04-011, CM-11-010, ADR-0121).  The ``target`` is the plain case URI:
    the invitee already holds the case from the Announce (AKM-02-003).  The
    CASE_MANAGER's ledger position when it issued the Invite, the floor the
    participant's reply must reach, is its ``ledgerPosition`` (SYNC-18-001).

    Declares ``object_`` in :attr:`inline_required_refs`: the invitee is a
    peer the sender holds no record of (see :class:`_RmInviteToCaseActivity`).
    """

    object_: as_CarriedActor = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: NonEmptyString = Field(...)

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})

    @model_validator(mode="after")
    def _states_a_ledger_position(self):
        _check_ledger_position(self, "the full-case Invite")
        return self


def _check_full_case_reply(reply: Any) -> None:
    """Shared rules of the three replies to the full-case Invite.

    A reply carries the replier's ledger position in ``ledgerPosition``
    (CM-11-011, SYNC-18-001) and answers the Invite it embeds.
    """
    _check_ledger_position(reply, "a reply to the full-case Invite")
    if reply.in_reply_to is None:
        object.__setattr__(reply, "in_reply_to", reply.object_.id_)


class _RmAcceptFullCaseInviteActivity(as_Accept):
    """The participant judges the case valid: RV, ``RECEIVED → VALID``.

    `object_`: the `_RmInviteToFullCaseActivity` being accepted.  Carries the
    replier's ledger position (VAM-04-012, CM-11-034).
    """

    object_: _RmInviteToFullCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def _validate_reply(self):
        _check_full_case_reply(self)
        return self


class _RmTentativeRejectFullCaseInviteActivity(as_TentativeReject):
    """The participant judges the case invalid: RI, ``RECEIVED → INVALID``.

    Carries the replier's ledger position (VAM-04-013, CM-11-034).
    """

    object_: _RmInviteToFullCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def _validate_reply(self):
        _check_full_case_reply(self)
        return self


class _RmRejectFullCaseInviteActivity(as_Reject):
    """The participant closes the case: RC, ``RECEIVED → CLOSED``.

    Carries the replier's ledger position (VAM-04-014, CM-11-034).
    """

    object_: _RmInviteToFullCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def _validate_reply(self):
        _check_full_case_reply(self)
        return self
