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

from py_trees.ports import NoDataAvailable, PortInformation

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.participant.roles import (
    suggested_roles_key,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    current_stub_embargo_end,
    recorded_stub_invites,
)
from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.embargo.rsvp_stamp import (
    stamp_rsvp_deadline,
)
from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.enums.roles import serialize_roles

#: Kind label of a stub Invite's derived id (see ``derived_activity_id``).
INVITE_ID_KIND = "invite-actor-to-case"

#: Ledger ``event_type`` of a stub Invite's entry.
INVITE_EVENT_TYPE = "invite_actor_to_case"


def build_stub_invite(
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
    activity_id: str | None = None,
) -> tuple[str, str]:
    """Build a stub Invite carrying a reply deadline.

    The one build every stub Invite takes, first or replacement: the
    CASE_MANAGER stamps the deadline (CM-11-014, CM-28-012) and the stub
    carries the terms of the embargo active now (CM-17-002).  The caller
    queues it and then commits it with :func:`commit_stub_invite` (CM-17-006,
    ADR-0119).  *activity_id*, when given, is the Invite's id; absent, the
    factory mints one.  An Invite built under an id the store already holds
    is the earlier attempt's Invite: the factory hands back the body sealed
    then, and the outbox and the commit each record it once (OX-06-002).
    Returns ``(activity_id, activity_blob)``.
    """
    # CM-17-002: pass the full case object so the adapter+factory can
    # project it to an enriched stub (embedding the full active embargo,
    # CM-17-011) when em_state==ACTIVE.
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
        id_=activity_id,
        attributed_to=authorship.attributed_to if authorship else None,
        roles=roles,
        target=case,
        rsvp_deadline=stamp.rsvp_deadline,
        published=stamp.published,
        in_reply_to=in_reply_to,
    )
    return activity_id, activity_blob


def commit_stub_invite(
    *,
    datalayer: CaseOutboxPersistence,
    actor_id: str,
    case_id: str,
    activity_id: str,
    activity_blob: str,
) -> None:
    """Commit the stub Invite just queued as its one canonical entry.

    The recorded snapshot is the exact blob the port returned: the factory
    owns its completeness (``context``, inline objects), and this same text
    is what the outbox delivers (VM-08-003).  Raises ``RuntimeError`` when
    the commit does not succeed.
    """
    commit_emitted_activity(
        datalayer=datalayer,
        actor_id=actor_id,
        case_id=case_id,
        activity_id=activity_id,
        activity_blob=activity_blob,
        event_type=INVITE_EVENT_TYPE,
    )


class _StubInviteEmitBase(_EmitSingleActivityBase):
    """Create Invite(Actor, CaseStub), queue it in this actor's outbox, and commit it.

    The shared build of :class:`EmitInviteActorToCaseNode`.  A subclass names
    the invitee (:meth:`_invitee`), the roles the Invite offers
    (:meth:`_read_suggested_roles`) and the request it answers
    (:meth:`_answered_request`): fixed at construction, or read from the
    recorded Offer the Case Owner accepted.
    """

    def __init__(
        self,
        case_id: str,
        attributed_to: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
        *,
        in_reply_to: str | None = None,
        replaces_previous_stub: bool = False,
        actor_config: ActorConfig | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.attributed_to = attributed_to
        self._in_reply_to = in_reply_to
        self._replaces_previous_stub = replaces_previous_stub
        self._actor_config = actor_config

    def _invitee(self) -> str:
        """The actor the Invite is addressed to."""
        raise NotImplementedError

    def _read_suggested_roles(self) -> list[str] | None:
        """The roles the Invite offers; ``None`` offers none."""
        raise NotImplementedError

    def _answered_request(self) -> str | None:
        """The request the Invite answers, which its id derives from."""
        raise NotImplementedError

    def _in_reply_to_id(self) -> str | None:
        """The earlier stub Invite this one replaces, if it replaces one.

        A re-invite replaces the invitee's newest earlier stub, so the invitee
        has one live stub at a time (CM-11-015); a first Invite replaces none.
        """
        if self._in_reply_to is not None or not self._replaces_previous_stub:
            return self._in_reply_to
        assert self.datalayer is not None and self.actor_id is not None
        earlier = recorded_stub_invites(
            self.datalayer, self.case_id, self.actor_id, self._invitee()
        )
        return earlier[-1].invite_id if earlier else None

    def _call_factory(self) -> tuple[str, str]:
        """Build the Invite(Actor, CaseStub) activity."""
        roles = self._read_suggested_roles()
        if roles is not None and not roles:
            raise ValueError(
                f"suggested_roles for actor '{self._invitee()}' is empty"
                " — cannot emit Invite(Actor, CaseStub) without at least one role"
            )
        assert self.datalayer is not None and self.actor_id is not None
        assert self.trigger_activity_factory is not None
        return build_stub_invite(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            factory=self.trigger_activity_factory,
            actor_id=self.actor_id,
            case_id=self.case_id,
            invitee_id=self._invitee(),
            roles=roles,
            attributed_to=self.attributed_to,
            in_reply_to=self._in_reply_to_id(),
            actor_config=self._actor_config,
            activity_id=self._invite_id(),
        )

    def _record_sent(self, activity_id: str, activity_blob: str) -> None:
        assert self.datalayer is not None and self.actor_id is not None
        commit_stub_invite(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=self.actor_id,
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=activity_blob,
        )

    def _invite_id(self) -> str | None:
        """The Invite's id, derived from the request it answers, if one is named."""
        answers = self._answered_request()
        if answers is None:
            return None
        assert self.actor_id is not None
        return derived_activity_id(
            INVITE_ID_KIND, self.actor_id, self.case_id, answers
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' emitted Invite(Actor, CaseStub) to '%s' for case '%s'",
            self.actor_id,
            self._invitee(),
            self.case_id,
        )


class EmitInviteActorToCaseNode(_StubInviteEmitBase):
    """Create Invite(Actor, CaseStub), queue it in this actor's outbox, and commit it.

    Runs only in a CASE_MANAGER-gated received tree, so ``self.actor_id`` is
    the CASE_MANAGER and the store is its own (BT-05-006, CM-24-004).  The
    Invite is addressed ``to=[invitee_id]`` and to no one else: the
    CASE_MANAGER never addresses a copy to itself (CLP-10-001, ADR-0109).
    Build → outbox append → commit is the order: the entry records an Invite
    already sent (ADR-0119), and the in-tree commit is the only ledger entry
    the Invite ever gets (CM-17-006).  An optional ``attributed_to`` carries
    the participant who asked for the invitation (PCR-08-007).

    ``answers`` names the request this Invite answers — the ``Offer(Actor,
    Case)`` that asked for it.  Given, the Invite's id is derived from the
    CASE_MANAGER and that request, so a retry of the tree for the same request
    rebuilds the same Invite, and the outbox, finding it already pending,
    does not queue it twice (OX-06-002, ID-04-004, ADR-0119).  Absent, the
    factory mints a fresh id.

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
    and factory project it to an enriched ``as_VulnerabilityCaseStub`` — embedding
    the full active embargo when ``em_state == EM.ACTIVE`` (CM-17-011) — without
    violating the core→wire import boundary (ARCH-01-001, CM-17-002).
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
        answers: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            attributed_to=attributed_to,
            captured=captured,
            name=name,
            in_reply_to=in_reply_to,
            replaces_previous_stub=replaces_previous_stub,
            actor_config=actor_config,
        )
        self.invitee_id = invitee_id
        self._answers = answers
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

    def _invitee(self) -> str:
        return self.invitee_id

    def _answered_request(self) -> str | None:
        return self._answers

    def _read_suggested_roles(self) -> list[str] | None:
        # Use injected roles (from stored Offer via DataLayer) when available
        # (ISSUE-1745: blackboard is empty in a separate BT execution).
        if self._injected_roles is not None:
            return self._injected_roles if self._injected_roles else None
        roles = self._suggested_roles_bb
        if isinstance(roles, list):
            return serialize_roles(roles)
        return None


__all__ = [
    "EmitInviteActorToCaseNode",
    "INVITE_EVENT_TYPE",
    "build_stub_invite",
    "commit_stub_invite",
]
