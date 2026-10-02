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

"""Relay of an adjudicated embargo proposal to the case's participants.

The CASE_MANAGER receives every embargo proposal (PCR-08-001), moves the
canonical case through ``EmbargoLifecycle`` and commits it, then relays one
``Invite(EmbargoEvent)`` per participant except the proposer, as the AS2
``actor`` with the proposer in ``attributedTo`` (EP-09-002, CM-24), committing
each emission in this tree (ADR-0109).  At each commit the invitee's PEC
``INVITE`` trigger is applied where CM-18-003 allows it (EP-09-004).

Two precondition guards and three leaf nodes, in the shape of the ledger
fan-out (``sync/nodes/fanout.py``).  The collect node is a read-only routing
guard the tree places *before* the EM write (BT-19-001), the relay node after
it:

    precondition_guards
    ├─ EmbargoProposalNotYetRecordedNode    # idempotency: same Invite again
    └─ case_manager_admits_proposal_guard   # EM admits PROPOSE (manager only)
    AdjudicateEmbargoProposal (CASE_MANAGER-gated Sequence)
    ├─ CollectEmbargoInviteRecipientsNode   # routing guard; writes recipients
    ├─ ProposeEmbargoLifecycleNode          # EM write (EmbargoLifecycle)
    └─ RelayEmbargoInviteToEachNode         # factory → commit → outbox → PEC

The CM-24-005 delegated-authorship helper (``_prepare_delegated_context``) is
a trigger-side use-case helper a BT node may not import (BTND-04-003), and its
"no CASE_MANAGER, send directly" arm is what ADR-0113 detail 14 retires
(#3964).  The received-side relay satisfies CM-24-001/002 structurally
instead: it runs only under the CASE_MANAGER gate, so ``actor`` is the role
holder by construction, and ``attributed_to`` is the adjudicated proposer.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.rsvp_stamp import (
    stamp_invite_rsvp_deadline,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models._helpers import parse_published
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.em import EM_Trigger
from vultron.errors import (
    BtNodePreconditionError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort

#: Ledger ``event_type`` of a relayed ``Invite(EmbargoEvent)`` emission — the
#: same value the guarded commit derives for the received proposal, so the
#: replica apply node (EP-09-007, #3915) dispatches on one event type.
EMBARGO_INVITE_EVENT_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value

_RECIPIENTS_KEY = "embargo_invite_recipients"


class EmbargoProposalNotYetRecordedNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Idempotency guard: this exact Invite has not been applied here before.

    The latch is ``case.pending_embargo_proposal_index[embargo_id] ==
    invite_id``, which the handler writes only after the whole tree succeeded
    (ID-04-005).  A re-delivered proposal — an outbox retry, a replayed
    inbox — would otherwise re-run the counter-proposal branch and relay a
    second round of Invites.  A precondition guard, so the duplicate commits
    no ledger entry (CLP-13-001); the handler reads its FAILURE as SKIPPED
    (HP-01-003).  A case this store does not hold cannot have recorded
    anything, so that is SUCCESS, not a refusal.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self._resolve_case_replica(self._case_id)
        if case is None:
            return Status.SUCCESS
        recorded = case.pending_embargo_proposal_index.get(self._embargo_id)
        if recorded == self._invite_id:
            self.feedback_message = (
                f"Invite '{self._invite_id}' for embargo '{self._embargo_id}'"
                f" was already applied on case '{self._case_id}'"
            )
            return self._idempotent_failure(
                self.logger,
                "%s: %s — skipping (CLP-13-001)",
                self.name,
                self.feedback_message,
            )
        return Status.SUCCESS


class EmStateAdmitsProposalNode(DataLayerConditionWithPorts):
    """Guard: the case's EM state accepts a PROPOSE trigger.

    A read-only precondition guard (CLP-10-009) for the CASE_MANAGER's
    adjudication of a received proposal: ``NONE``, ``PROPOSED``, ``ACTIVE``
    and ``REVISE`` admit one (EP-09-001), ``EXITED`` does not — the EM
    machine never returns from ``EXITED``.  Placed ahead of the guarded
    commit so a refused proposal leaves no canonical entry behind.  Reads the
    state through :class:`ReadEmStateNode` (AC-1, #1474).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            em_before = read_case_em_state(self.datalayer, self._case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        try:
            EmDimension(state=em_before).transition(EM_Trigger.PROPOSE)
        except VultronInvalidStateTransitionError:
            self.feedback_message = (
                f"Case '{self._case_id}' is at EM {em_before.name}, which"
                " admits no embargo proposal (EP-09-001)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


def invite_rsvp_deadline(invite: dict[str, Any]) -> datetime | None:
    """The RSVP deadline (``endTime``) a relayed Invite's wire body carries.

    The relay and its ledger replay both read it from the same sealed body,
    so the invitee's record takes the same deadline in every store
    (CM-28-013, EP-09-007).
    """
    return parse_published(invite.get(wire_key("end_time")))


def case_manager_admits_proposal_guard(
    case_id: str,
) -> py_trees.composites.Selector:
    """Precondition guard: when this actor is the CASE_MANAGER, EM admits a proposal.

    A read-only composite for a received tree's ``precondition_guards``
    (CLP-10-009): skips as SUCCESS for a participant replica and runs
    :class:`EmStateAdmitsProposalNode` for the manager, so a proposal the
    canonical case cannot take is refused before the guarded commit writes
    an entry for it.
    """
    return create_case_manager_gated_tree(
        name="AdmitsEmbargoProposalIfCaseManager",
        case_id=case_id,
        children=[EmStateAdmitsProposalNode(case_id=case_id)],
    )


class CollectEmbargoInviteRecipientsNode(DataLayerActionWithPorts):
    """Resolve who the CASE_MANAGER relays a proposal to, before anything moves.

    Every participant except the proposer (EP-09-002) and the executing actor
    itself: proposing terms is consenting to them (ADR-0093), and a container
    never addresses mail to an actor it hosts (ADR-0109).  Fails when the
    trigger-activity factory is not injected, so the EM state is not moved
    for a proposal that could not be relayed (BT-19-001, BT-19-003).  Always
    writes the recipients key, so a downstream reader never sees a stale
    value (BT-17-003).
    """

    def __init__(
        self, case_id: str, proposer_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._proposer_id = proposer_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        _RECIPIENTS_KEY: PortInformation(data_type=list, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {_RECIPIENTS_KEY: f"/{_RECIPIENTS_KEY}"}

    def update(self) -> Status:
        self._set_output(_RECIPIENTS_KEY, [])
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        # An Invite asks for consent, so an inert participant — the one that
        # has not consented — is exactly who it must reach; a participant at
        # RM.CLOSED gets none (CM-10-007, EP-09-002).
        recipients = invitation_recipients(
            case,
            self.datalayer,
            excluding={self.actor_id, self._proposer_id},
        )
        self._set_output(_RECIPIENTS_KEY, recipients)
        self.feedback_message = (
            f"{len(recipients)} participant(s) to invite on case"
            f" '{self._case_id}' (proposer '{self._proposer_id}' excluded)"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class RelayEmbargoInviteToEachNode(DataLayerActionWithPorts):
    """Emit, commit and record one relayed ``Invite(EmbargoEvent)`` per recipient.

    For each recipient the collect node named: build the Invite through the
    trigger-activity factory as the executing CASE_MANAGER with the proposer
    in ``attributedTo`` (CM-24-001, CM-24-002) and the manager's RSVP
    deadline as its ``endTime`` (CM-28-012, from ``actor_config``'s windows),
    commit the sealed blob as the canonical entry (VM-08-003) before the
    outbox write (ledger commit precedes outbox write), queue it, then apply
    PEC ``INVITE`` to the invitee where legal, recording the deadline the
    sealed Invite carries (CM-18-003, EP-09-004, CM-28-013).

    A step failing mid-relay is not a protocol refusal — the proposal is
    already committed and the EM state moved — so this node catches nothing:
    the exception escapes to ``BTBridge``, which reports the tree as FAILURE
    with ``internal_error`` set, and the handler raises rather than reporting
    REFUSED (BT-14-001 without the masking the pitfalls table warns of).
    Partial relays are visible in the ledger as the Invites that were
    committed.  The idempotency latch (``pending_embargo_proposal_index``)
    is written by the handler only after the whole tree succeeded
    (ID-04-005), so a redelivery after a mid-relay fault passes the
    :class:`EmbargoProposalNotYetRecordedNode` guard and re-adjudicates: the
    proposal's own commit is deduplicated by the ledger and the EM write is a
    no-op counter-proposal, but this node relays to *every* recipient again —
    a recipient already invited in the failed run receives a second Invite
    (a new activity and a new ledger entry) and its consent state, already
    ``INVITED``, is unchanged.  Per-recipient deduplication is deliberately
    not done here: the same terms re-proposed under a new Invite id are a
    counter-proposal that *is* relayed again, and telling that apart from a
    fault retry is an EP-09 design question, not a node-local check.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        proposer_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._proposer_id = proposer_id
        self._actor_config = actor_config
        self._sync_port: SyncActivityPort | None = None
        self._recipients: list[str] = []

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        _RECIPIENTS_KEY: PortInformation(data_type=list, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            _RECIPIENTS_KEY: f"/{_RECIPIENTS_KEY}",
            "sync_port": "/sync_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self._load_relay_inputs()
        try:
            self._sync_port = cast(
                "SyncActivityPort | None", self.get_input("sync_port")
            )
        except (py_trees.ports.NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def _load_relay_inputs(self) -> None:
        """Read what to relay; the recipients the collect node resolved.

        A subclass that learns its case, embargo and proposer only at tick
        time overrides this rather than the emit path (EP-04-011).
        """
        self._recipients = cast(list[str], self.get_input(_RECIPIENTS_KEY))

    def _activity_id_for(self, recipient_id: str) -> str | None:
        """The id the Invite to *recipient_id* takes; ``None`` mints a fresh one."""
        return None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f
        for recipient_id in self._recipients:
            self._relay_to(recipient_id)
        self.feedback_message = (
            f"Relayed embargo '{self._embargo_id}' on case '{self._case_id}'"
            f" to {len(self._recipients)} participant(s)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _relay_to(self, recipient_id: str) -> None:
        """Factory → commit → outbox → consent, for one invitee; raises on failure."""
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        dl = cast(CaseOutboxPersistence, self.datalayer)
        # The manager stamps the deadline it alone will evaluate (CM-28-012).
        # Regime 1 (ADR-0087): the embargo is one the manager itself holds,
        # so a missing record is its own store's fault, never the sender's —
        # re-raised as internal, as ``_invite_where_legal`` does (ADR-0095).
        try:
            stamp = stamp_invite_rsvp_deadline(
                dl, self._embargo_id, self._actor_config
            )
        except VultronNotFoundError as exc:
            raise RuntimeError(
                f"{self.name}: cannot stamp the RSVP deadline of embargo"
                f" '{self._embargo_id}' on case '{self._case_id}': {exc}"
            ) from exc
        activity_id, blob = self.trigger_activity_factory.propose_embargo(
            embargo_id=self._embargo_id,
            case_id=self._case_id,
            actor=self.actor_id,
            to=[recipient_id],
            attributed_to=self._proposer_id,
            activity_id=self._activity_id_for(recipient_id),
            rsvp_deadline=stamp.rsvp_deadline,
            published=stamp.published,
            min_rsvp_window=stamp.min_rsvp_window,
        )
        self._commit_emission(activity_id, blob)
        dl.outbox_append(activity_id)
        self._invite_where_legal(
            dl, recipient_id, invite_rsvp_deadline(json.loads(blob))
        )
        self.logger.info(
            "CASE_MANAGER '%s' relayed embargo '%s' to '%s' for '%s' (EP-09-002)",
            self.actor_id,
            self._embargo_id,
            recipient_id,
            self._proposer_id,
        )

    def _commit_emission(self, activity_id: str, blob: str) -> None:
        """Commit the emitted Invite as a canonical entry (ADR-0109, VM-08-003)."""
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=cast(str, self.actor_id),
            case_id=self._case_id,
            activity_id=activity_id,
            activity_blob=blob,
            event_type=EMBARGO_INVITE_EVENT_TYPE,
            sync_port=self._sync_port,
        )

    def _invite_where_legal(
        self,
        dl: CaseOutboxPersistence,
        recipient_id: str,
        rsvp_deadline: datetime | None,
    ) -> None:
        """Apply PEC INVITE to *recipient_id* if CM-18-003 allows it (EP-09-004)."""
        # Regime 1 (ADR-0087): the relay follows the manager's own EM write on
        # this case, so a missing case or invitee is an anomaly, not a lenient
        # skip.  ``record_embargo_invite`` raises a ``VultronNotFoundError``,
        # which would read as the sender's fault (REFUSED, ADR-0095), so it is
        # re-raised as the internal error it is in the manager's own store.
        try:
            result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
                case_id=self._case_id,
                invitee_id=recipient_id,
                rsvp_deadline=rsvp_deadline,
            )
        except VultronNotFoundError as exc:
            raise RuntimeError(
                f"{self.name}: the CASE_MANAGER's roster names '{recipient_id}'"
                f" but its store has no record for it: {exc}"
            ) from exc
        if not result.participant_changes:
            self.logger.info(
                "%s: INVITE does not apply to '%s' (EP-09-004)",
                self.name,
                recipient_id,
            )


__all__ = [
    "EMBARGO_INVITE_EVENT_TYPE",
    "CollectEmbargoInviteRecipientsNode",
    "EmStateAdmitsProposalNode",
    "EmbargoProposalNotYetRecordedNode",
    "case_manager_admits_proposal_guard",
    "RelayEmbargoInviteToEachNode",
]
