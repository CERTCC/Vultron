#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The CASE_MANAGER's stub Invite for the Case Owner's decision (CM-17-007).

Split from :mod:`~vultron.core.behaviors.case.nodes.owner_invite`, which
re-exports every name here and holds the guards the CASE_MANAGER runs first:

- :class:`InviteeAwaitsReplyNode` picks a first Invite or a replacement.
- :class:`EmitOwnerDecidedStubInviteNode` sends the stub Invite.
- :class:`SeatOwnerInvitedInviteeNode` seats the inert participant.
- :func:`owner_decided_stub_invite` composes them for both paths that reach
  the CASE_MANAGER with the Owner's decision.

Every node reads the case, the invitee and the sender from the per-act keys
``/case_id``, ``/invitee_id`` and ``/sender_id`` (BTND-01-008, BTND-01-009),
through :class:`_InviteKeysMixin`.
"""

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
)
from vultron.core.behaviors.act_keys import CASE_ID, INVITEE_ID, SENDER_ID
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    _StubInviteEmitBase,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    _SeatInertInviteeBase,
    validated_invitee_roles,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    awaiting_stub_reply,
    invitee_record,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.received_request import ReceivedRequestInputMixin
from vultron.enums.roles import CVDRole
from vultron.primitives import normalise_actor_id

#: The per-act keys every node here reads.
_INVITE_KEYS = (CASE_ID, INVITEE_ID, SENDER_ID)


class _InviteKeysMixin:
    """Read ``/case_id``, ``/invitee_id`` and ``/sender_id`` (BTND-01-008).

    Mix it in before the node's ports base.  It adds one optional port per
    key, bound to the key's path, to whatever ``INPUT_PORTS`` the class ends
    up with.  A read of a key nothing seeded is a wiring error (BT-25-008).
    """

    # Annotation only, as in ``ReceivedRequestInputMixin``.
    INPUT_PORTS: dict[str, Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.INPUT_PORTS = {**cls.INPUT_PORTS, **act_key_ports(*_INVITE_KEYS)}
        super().__init_subclass__(**kwargs)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        remappings = dict(super()._domain_port_remappings())  # type: ignore[misc]
        remappings.update(act_key_remappings(*_INVITE_KEYS))
        return remappings

    def _act_case(self) -> str:
        """The case the act is about."""
        return act_value(self, CASE_ID, str)  # type: ignore[arg-type]

    def _act_invitee(self) -> str:
        """The invitee, in its canonical spelling (OID-01-006)."""
        return normalise_actor_id(act_value(self, INVITEE_ID, str))  # type: ignore[arg-type]

    def _act_sender(self) -> str:
        """The sender of the received activity."""
        return act_value(self, SENDER_ID, str)  # type: ignore[arg-type]


class InviteeAwaitsReplyNode(_InviteKeysMixin, DataLayerConditionWithPorts):
    """Condition: the invitee has an inert record that has not answered.

    SUCCESS when a re-invite is due: a fresh stub Invite goes out on that
    record (CM-11-015).  FAILURE leaves the first-invite path.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._act_case())
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        record = invitee_record(self.datalayer, case, self._act_invitee())
        return (
            Status.SUCCESS if awaiting_stub_reply(record) else Status.FAILURE
        )


class EmitOwnerDecidedStubInviteNode(
    _InviteKeysMixin, ReceivedRequestInputMixin, _StubInviteEmitBase
):
    """Send the invitee the CASE_MANAGER's stub Invite for the Owner's decision.

    The case and the invitee are the act's keys; the roles are the ones the
    Owner named.  With *credits_sender*, the Invite carries out the Owner's
    received Invite: ``attributedTo`` is its sender and ``inReplyTo`` its id
    (CM-24-002, CM-24-020), and the stub's id derives from it, so a retry
    rebuilds the same stub (OX-06-002).  Without, the Owner is the
    CASE_MANAGER and the Invite is its own, with a minted id (CM-24-021).
    A replacement names the stub it supersedes in ``inReplyTo`` instead
    (CM-11-044).
    """

    def __init__(
        self,
        offered_roles: list[str],
        *,
        credits_sender: bool,
        replaces_previous_stub: bool = False,
        actor_config: ActorConfig | None = None,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        # The case is the act's, read in ``initialise()`` (BTND-01-008).
        super().__init__(
            case_id="",
            captured=captured,
            name=name,
            replaces_previous_stub=replaces_previous_stub,
            actor_config=actor_config,
        )
        self._roles = list(offered_roles)
        self._credits_sender = credits_sender

    def initialise(self) -> None:
        super().initialise()
        self.case_id = self._act_case()

    def _invitee(self) -> str:
        return self._act_invitee()

    def _read_suggested_roles(self) -> list[str] | None:
        return self._roles

    def _requester(self) -> str | None:
        return self._act_sender() if self._credits_sender else None

    def _answered_request(self) -> str | None:
        return self._received_request_id() if self._credits_sender else None


class SeatOwnerInvitedInviteeNode(_InviteKeysMixin, _SeatInertInviteeBase):
    """Seat the inert record of the invitee the Case Owner invited (CM-11-006).

    The invitee and the case are the act's keys; the roles are the Owner's.
    See :class:`~vultron.core.behaviors.case.nodes.invite_inert_participant._SeatInertInviteeBase`.
    """

    def __init__(
        self, offered_roles: list[str], name: str | None = None
    ) -> None:
        # The case is the act's, read in ``initialise()`` (BTND-01-008).
        super().__init__(case_id="", name=name)
        self._roles = list(offered_roles)

    def initialise(self) -> None:
        super().initialise()
        self.case_id = self._act_case()

    def _invitee(self) -> str:
        return self._act_invitee()

    def _resolve_roles(self) -> list[CVDRole]:
        return validated_invitee_roles(self._roles)


def owner_decided_stub_invite(
    offered_roles: list[str],
    *,
    credits_sender: bool,
    actor_config: ActorConfig | None = None,
    captured: dict | None = None,
) -> py_trees.composites.Selector:
    """Send the invitee the CASE_MANAGER's stub Invite, first or replacement.

    One subtree, composed by both places the Owner's decision reaches the
    CASE_MANAGER: the received tree of the Owner's own Invite (CM-17-007),
    and the direct-invite trigger of an Owner that holds the CASE_MANAGER
    role itself (CM-24-021).  ``Selector(Reinvite, FirstInvite)``:

    - **Reinvite** — the invitee has an inert record that has not answered:
      a fresh stub Invite goes out on that record, with a new deadline,
      naming the stub it supersedes (CM-11-015, CM-11-044).
    - **FirstInvite** — no such record: the stub Invite goes out, then the
      inert participant is seated and added to the case in the same act
      (CM-11-006, CM-11-023).

    The second arm is guarded by the inverse of the first's check, so a
    failed re-invite surfaces rather than falling through to seating a
    second record.  Each emit commits its Invite once it is in the outbox
    (CM-17-006).

    Args:
        offered_roles: The roles the Owner named; never empty (CM-11-019): the
            caller has refused an Invite without one.
        credits_sender: The stub carries out the received Owner's Invite
            (``attributedTo``, ``inReplyTo``); ``False`` when the Owner is
            the CASE_MANAGER and the stub is its own.
        actor_config: The CASE_MANAGER's configuration, for the RSVP window
            (CM-11-014, CM-28-012).
        captured: Optional dict; ``captured["activity"]`` is set to the stub
            Invite sent.
    """

    def _emit(
        *, replaces_previous_stub: bool
    ) -> EmitOwnerDecidedStubInviteNode:
        return EmitOwnerDecidedStubInviteNode(
            offered_roles,
            credits_sender=credits_sender,
            replaces_previous_stub=replaces_previous_stub,
            actor_config=actor_config,
            captured=captured,
            name=(
                "EmitReplacementStubInvite"
                if replaces_previous_stub
                else "EmitStubInvite"
            ),
        )

    reinvite = py_trees.composites.Sequence(
        name="Reinvite",
        memory=False,
        children=[
            InviteeAwaitsReplyNode(name="InviteeAwaitsReply"),
            # The record is already on the roster: only the Invite goes out.
            _emit(replaces_previous_stub=True),
        ],
    )
    first_invite = py_trees.composites.Sequence(
        name="FirstInvite",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="InviteeHasNoAwaitingRecord",
                child=InviteeAwaitsReplyNode(name="InviteeAwaitsReplyCheck"),
            ),
            _emit(replaces_previous_stub=False),
            SeatOwnerInvitedInviteeNode(offered_roles),
        ],
    )
    return py_trees.composites.Selector(
        name="OwnerDecidedStubInvite",
        memory=False,
        children=[reinvite, first_invite],
    )


__all__ = [
    "EmitOwnerDecidedStubInviteNode",
    "InviteeAwaitsReplyNode",
    "SeatOwnerInvitedInviteeNode",
    "owner_decided_stub_invite",
]
