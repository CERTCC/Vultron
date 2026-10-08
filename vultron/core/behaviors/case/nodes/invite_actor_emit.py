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

"""The CASE_MANAGER's ``Invite(Actor, CaseStub)`` emit node.

Split out of ``actor.py`` (BTND-07-004).  Every stub Invite it emits carries a
reply deadline (CM-11-014); a replacement issued after an embargo change names
the Invite it supersedes in ``inReplyTo`` (CM-11-016).
"""

from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.participant.roles import (
    suggested_roles_key,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    RecordedStubInvite,
    current_stub_embargo_end,
    outstanding_stale_stubs,
    recorded_stub_invites,
)
from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.embargo.rsvp_stamp import stamp_rsvp_deadline
from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models._helpers import now_utc
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.enums.roles import serialize_roles


def emit_stub_invite(
    *,
    datalayer: CaseOutboxPersistence,
    factory: TriggerActivityPort,
    actor_id: str,
    case_id: str,
    invitee_id: str,
    roles: list[str] | None,
    attributed_to: str | None = None,
    in_reply_to: str | None = None,
    actor_config: ActorConfig | None = None,
) -> tuple[str, str]:
    """Build a stub Invite carrying a reply deadline, and commit it.

    The one emission every stub Invite takes, first or replacement: the
    CASE_MANAGER stamps the deadline (CM-11-014, CM-28-012), the stub carries
    the terms of the embargo active now (CM-17-002), and the sealed blob is
    committed as the canonical entry before the caller queues it (CM-17-006).
    Returns ``(activity_id, activity_blob)``.
    """
    # CM-17-002: pass the full case object so the adapter+factory can
    # project it to an enriched stub (with end_time) when em_state==ACTIVE.
    # Regime 3 (ADR-0087): the case is *optional enrichment* here, not
    # coordination state — the Invite is fully specified by invitee/case_id/
    # actor/roles, and the factory tolerates target=None (CM-17-002 only
    # enriches the stub when the case is present and em_state==ACTIVE). A
    # missing local case therefore emits a bare stub rather than failing;
    # this read is deliberately unguarded (conformance allowlist).
    case = datalayer.read_case(case_id)
    # The CASE_MANAGER states the reply deadline once, the way it does on an
    # embargo Invite (CM-11-014, CM-28-012, ASK-03-004); the cap is the end of
    # the embargo the stub carries, when it carries one.
    stamp = stamp_rsvp_deadline(
        current_stub_embargo_end(datalayer, case)
        if case is not None
        else None,
        actor_config,
    )
    # ``None`` is the manager's own invitation; otherwise the participant who
    # asked for it is the attributed author (PCR-08-007, CM-24-005).
    authorship = (
        delegated_authorship(
            doing_actor_id=actor_id, requesting_actor_id=attributed_to
        )
        if attributed_to is not None
        else None
    )
    activity_id, activity_blob = factory.invite_actor_to_case(
        invitee_id=invitee_id,
        case_id=case_id,
        actor=authorship.actor if authorship else actor_id,
        to=[invitee_id],
        attributed_to=authorship.attributed_to if authorship else None,
        roles=roles,
        target=case,
        rsvp_deadline=stamp.rsvp_deadline,
        published=stamp.published,
        in_reply_to=in_reply_to,
    )
    # The recorded snapshot is the exact blob the port returned: the factory
    # owns its completeness (``context``, inline objects), and this same text
    # is what the outbox delivers (VM-08-003).
    commit_emitted_activity(
        datalayer=datalayer,
        actor_id=actor_id,
        case_id=case_id,
        activity_id=activity_id,
        activity_blob=activity_blob,
        event_type="invite_actor_to_case",
    )
    return activity_id, activity_blob


class EmitInviteActorToCaseNode(_EmitSingleActivityBase):
    """Create Invite(Actor, CaseStub), commit it, and queue it in this actor's outbox.

    Runs only in a CASE_MANAGER-gated received tree, so ``self.actor_id`` is
    the CASE_MANAGER and the store is its own (BT-05-006, CM-24-004).  The
    Invite is addressed ``to=[invitee_id]`` and to no one else: the
    CASE_MANAGER never addresses a copy to itself (CLP-10-001, ADR-0109).
    Build → commit → outbox append is the order, so the in-tree commit is the
    only ledger entry the Invite ever gets and a failed commit cannot orphan
    an outbox item (CM-17-006).  An optional ``attributed_to`` carries the
    participant who asked for the invitation (PCR-08-007).

    Roles are resolved via ``_read_suggested_roles()``, which uses two paths:

    1. **Injected roles** (``roles`` constructor parameter): used when the
       node is instantiated from a stored ``Offer(CaseParticipant)`` in the
       DataLayer (ISSUE-1745, CM-16-018).  The stored Offer is the trusted
       source because the received ``Accept`` is untrusted.
    2. **Evaluator output** (``recommendation_id`` constructor parameter):
       the roles :class:`EvaluateDefaultRolesNode` wrote earlier in the same
       tree under its namespaced key ``suggested_roles_{id_segment}``
       (BTND-03-004, CM-16-003, CM-17-007).

    Reads the ``VulnerabilityCase`` from the DataLayer and passes it as
    ``target`` to ``TriggerActivityPort.invite_actor_to_case()``.  The adapter
    and factory project it to an enriched ``as_VulnerabilityCaseStub`` — including
    ``end_time`` when ``em_state == EM.ACTIVE`` — without violating the
    core→wire import boundary (ARCH-01-001, CM-17-002).
    """

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        attributed_to: str | None = None,
        captured: dict | None = None,
        roles: list[str] | None = None,
        recommendation_id: str | None = None,
        name: str | None = None,
        *,
        in_reply_to: str | None = None,
        replaces_previous_stub: bool = False,
        actor_config: ActorConfig | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.attributed_to = attributed_to
        self._in_reply_to = in_reply_to
        self._replaces_previous_stub = replaces_previous_stub
        self._actor_config = actor_config
        self._injected_roles = roles
        self._roles_key = (
            f"/{suggested_roles_key(recommendation_id)}"
            if recommendation_id is not None
            else None
        )
        self._suggested_roles_bb = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **_EmitSingleActivityBase.INPUT_PORTS,
        "suggested_roles": PortInformation(data_type=list, required=False),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        if self._roles_key is None:
            return {}
        return {"suggested_roles": self._roles_key}

    def initialise(self) -> None:
        super().initialise()
        self._suggested_roles_bb = None
        if self._roles_key is None:
            return
        try:
            self._suggested_roles_bb = self.get_input("suggested_roles")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _read_suggested_roles(self) -> list[str] | None:
        # Use injected roles (from stored Offer via DataLayer) when available
        # (ISSUE-1745: blackboard is empty in a separate BT execution).
        if self._injected_roles is not None:
            return self._injected_roles if self._injected_roles else None
        roles = self._suggested_roles_bb
        if isinstance(roles, list):
            return serialize_roles(roles)
        return None

    def _in_reply_to_id(self) -> str | None:
        """The earlier stub Invite this one replaces, if it replaces one.

        A re-invite replaces the invitee's newest earlier stub, so the invitee
        has one live stub at a time (CM-11-015); a first Invite replaces none.
        """
        if self._in_reply_to is not None or not self._replaces_previous_stub:
            return self._in_reply_to
        assert self.datalayer is not None and self.actor_id is not None
        earlier = recorded_stub_invites(
            self.datalayer, self.case_id, self.actor_id, self.invitee_id
        )
        return earlier[-1].invite_id if earlier else None

    def _call_factory(self) -> tuple[str, str]:
        """Build Invite(Actor, CaseStub) activity and commit the ledger correlation marker."""
        roles = self._read_suggested_roles()
        if roles is not None and not roles:
            raise ValueError(
                f"suggested_roles for actor '{self.invitee_id}' is empty"
                " — cannot emit Invite(Actor, CaseStub) without at least one role"
            )
        assert self.datalayer is not None and self.actor_id is not None
        assert self.trigger_activity_factory is not None
        return emit_stub_invite(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            factory=self.trigger_activity_factory,
            actor_id=self.actor_id,
            case_id=self.case_id,
            invitee_id=self.invitee_id,
            roles=roles,
            attributed_to=self.attributed_to,
            in_reply_to=self._in_reply_to_id(),
            actor_config=self._actor_config,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' emitted Invite(Actor, CaseStub) to '%s' for case '%s'",
            self.actor_id,
            self.invitee_id,
            self.case_id,
        )


class ReissueStubInvitesNode(_EmitSingleActivityBase):
    """Re-issue every outstanding stub Invite the active embargo's change staled.

    Accepting a stub consents to the terms it carried, so when the active
    embargo is activated, revised or terminated while a stub is outstanding
    the CASE_MANAGER sends the invitee a replacement carrying the current terms
    and a new deadline, on the same participant record, naming in
    ``inReplyTo`` the Invite it supersedes (CM-11-016).  No ``Undo`` retracts the old one: an ``Accept`` of
    it is refused, naming the replacement, and a ``Reject`` of it is honoured.

    *Outstanding* means the invitee has not replied and its newest Invite has
    not expired; an expired stub is not re-issued (CM-11-015).  The node is
    level-triggered, comparing each stub's carried embargo with the one a stub
    sent now would carry, so it is safe after any step that may have changed the
    embargo and is a no-op after one that did not (a revision *proposal* changes
    no active embargo).  CASE_MANAGER only: place it inside the role gate.

    Succeeds with nothing emitted when no stub is stale.
    """

    def __init__(
        self,
        case_id: str,
        actor_config: ActorConfig | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.case_id = case_id
        self._actor_config = actor_config

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        dl = cast(CaseOutboxPersistence, self.datalayer)
        stale_stubs = outstanding_stale_stubs(
            dl, case, self.actor_id, now_utc()
        )
        if not stale_stubs:
            return Status.SUCCESS
        # Only a re-issue needs the emit port: a change that leaves no stub
        # stale must not fail a tree that was composed without one.
        if (f := self._require_factory()) is not None:
            self.logger.error("%s", self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None
        for stale in stale_stubs:
            self._reissue(stale)
        return Status.SUCCESS

    def _reissue(self, stale: RecordedStubInvite) -> None:
        """Send the replacement for *stale*, naming it, and queue it."""
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None
        activity_id, activity_blob = emit_stub_invite(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            factory=self.trigger_activity_factory,
            actor_id=self.actor_id,
            case_id=self.case_id,
            invitee_id=stale.invitee_id,
            roles=list(stale.roles) or None,
            attributed_to=stale.attributed_to,
            in_reply_to=stale.invite_id,
            actor_config=self._actor_config,
        )
        self._emit_through_seam(activity_id, activity_blob)
        self.logger.info(
            "Actor '%s' re-issued stub Invite '%s' to '%s' as '%s' after"
            " an embargo change on case '%s' (CM-11-016)",
            self.actor_id,
            stale.invite_id,
            stale.invitee_id,
            activity_id,
            self.case_id,
        )


__all__ = [
    "EmitInviteActorToCaseNode",
    "ReissueStubInvitesNode",
    "emit_stub_invite",
]
