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
each emission in this tree once it is queued (ADR-0109, ADR-0119).  After
each commit the invitee's PEC ``INVITE`` on its row for the embargo, where
CM-18-003 allows it (EP-09-004), is committed as the CASE_MANAGER's own
``Update(EmbargoConsent)`` entry and written by copying it (ADR-0124).

Two precondition guards (``relay_guards.py``, re-exported here) and three
leaf nodes, in the shape of the ledger fan-out (``sync/nodes/fanout.py``).  The collect node is a read-only routing
guard the tree places *before* the EM write (BT-19-001), the relay node after
it:

    precondition_guards
    ├─ EmbargoProposalNotYetRecordedNode    # idempotency: same Invite again
    └─ case_manager_admits_proposal_guard   # EM admits PROPOSE (manager only)
    AdjudicateEmbargoProposal (CASE_MANAGER-gated Sequence)
    ├─ CollectEmbargoInviteRecipientsNode   # routing guard; writes recipients
    ├─ ProposeEmbargoLifecycleNode          # EM write (EmbargoLifecycle)
    └─ RelayEmbargoInviteToEachNode         # factory → outbox → commit → row

``actor`` and ``attributed_to`` come from the shared CM-24-005 helper
(``delegated_authorship``): the relay runs only under the CASE_MANAGER gate, so
the doing actor is the role holder, and the asking actor is the adjudicated
proposer.
"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.embargo.decided_entries import (
    decide_commit_and_apply,
)
from vultron.core.behaviors.embargo.nodes.relay_guards import (
    EmbargoProposalNotYetRecordedNode,
    EmStateAdmitsProposalNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.embargo.rsvp_stamp import (
    invite_rsvp_deadline,
    stamp_invite_rsvp_deadline,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.events.base import MessageSemantics
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import (
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


class RelayEmbargoInviteToEachNode(
    DataLayerActionWithPorts, EmitCapable, StateWriteCapable
):
    """Emit, commit and record one relayed ``Invite(EmbargoEvent)`` per recipient.

    For each recipient the collect node named: build the Invite through the
    trigger-activity factory as the executing CASE_MANAGER with the proposer
    in ``attributedTo`` (CM-24-001, CM-24-002) and the manager's RSVP
    deadline as its ``endTime`` (CM-28-012, from ``actor_config``'s windows),
    queue it, commit the sealed blob as the canonical entry (VM-08-003) once
    it is queued (ADR-0119), then commit PEC ``INVITE`` on the invitee's row
    for the embargo, where legal and with the deadline the sealed Invite
    carries (CM-18-003, EP-09-004, CM-28-013), as the CASE_MANAGER's own
    ``Update(EmbargoConsent)`` entry, and only then write the row by copying
    it (ADR-0124, CLP-07-013).  The row change is decided before the Invite
    is sent, so a missing invitee record fails with nothing sent.

    *answers* names the request the relay answers — the proposer's Invite on
    the received path, the manager's own proposal on the trigger path.
    Given, each Invite's id is derived from it, the embargo and the
    recipient, so a retry of the tree for the same request rebuilds the
    Invites the failed attempt queued, under the same ids: the outbox does
    not queue one twice (OX-06-002) and the commit records each once.

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
    each recipient is relayed to again.  With *answers* given, the retry
    rebuilds each Invite under its first id, so a recipient the failed run
    already invited is not sent a second one and its entry is not committed
    twice; its consent row, already ``INVITED``, is unchanged.  The key is
    the request, not the terms: the same terms re-proposed under a new
    Invite id are a counter-proposal that *is* relayed again.

    *withdraw_unrecorded* is for a relay no retry rebuilds: the manager's own
    proposal, which a repeated trigger answers with a new embargo.  An Invite
    whose commit fails is then taken back out of the outbox before the
    failure is raised, so no participant is sent an Invite the ledger does
    not record (CLP-07-013).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        proposer_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
        *,
        answers: str | None = None,
        withdraw_unrecorded: bool = False,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._proposer_id = proposer_id
        self._actor_config = actor_config
        self._answers = answers
        self._withdraw_unrecorded = withdraw_unrecorded
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
        """The id the Invite to *recipient_id* takes; ``None`` mints a fresh one.

        Derived from the request the relay answers, the embargo and the
        recipient when *answers* was given (ID-04-004, OX-06-002).
        """
        if self._answers is None:
            return None
        assert self.actor_id is not None
        return derived_activity_id(
            self._EVENT_TYPE,
            self.actor_id,
            self._case_id,
            self._answers,
            self._embargo_id,
            recipient_id,
        )

    #: Ledger ``event_type`` the emission is committed under.
    _EVENT_TYPE = EMBARGO_INVITE_EVENT_TYPE

    def _attributed_to(self) -> str | None:
        """Whose terms the Invite carries; ``None`` when it is the manager's own ask."""
        return self._proposer_id

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
        """Factory → outbox → commit → consent, for one invitee; raises on failure."""
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
        proposer_id = self._attributed_to()
        authorship = (
            delegated_authorship(
                doing_actor_id=self.actor_id, requesting_actor_id=proposer_id
            )
            if proposer_id
            else None
        )
        activity_id, blob = self.trigger_activity_factory.propose_embargo(
            embargo_id=self._embargo_id,
            case_id=self._case_id,
            actor=authorship.actor if authorship else self.actor_id,
            to=[recipient_id],
            attributed_to=authorship.attributed_to if authorship else None,
            activity_id=self._activity_id_for(recipient_id),
            rsvp_deadline=stamp.rsvp_deadline,
            published=stamp.published,
            min_rsvp_window=stamp.min_rsvp_window,
        )
        rsvp_deadline = invite_rsvp_deadline(json.loads(blob))

        def _send_and_commit() -> None:
            # Sent, then recorded: the entry records a completed act
            # (ADR-0119).
            self._queue(activity_id)
            committed = False
            try:
                self._commit_emission(activity_id, blob)
                committed = True
            finally:
                # The failure itself propagates (BT-14-001); an Invite no
                # retry rebuilds is first taken back out of the outbox.
                if not committed and self._withdraw_unrecorded:
                    self._withdraw(activity_id)

        self._invite_where_legal(
            dl,
            recipient_id,
            rsvp_deadline,
            cause_id=activity_id,
            send_and_commit=_send_and_commit,
        )
        self.logger.info(
            "CASE_MANAGER '%s' relayed embargo '%s' to '%s' for '%s' (EP-09-002)",
            self.actor_id,
            self._embargo_id,
            recipient_id,
            self._attributed_to() or self.actor_id,
        )

    def _queue(self, activity_id: str) -> None:
        """Queue *activity_id* in the outbox, then note that it was queued.

        An id already pending is an earlier attempt's send and is not queued
        again (OX-06-002).
        """
        if not cast(CaseOutboxPersistence, self.datalayer).outbox_append(
            activity_id
        ):
            self.logger.info(
                "%s: Invite '%s' is already pending — not queued again"
                " (OX-06-002)",
                self.name,
                activity_id,
            )
        self._record_queued(activity_id)

    def _withdraw(self, activity_id: str) -> None:
        """Take an Invite whose commit failed back out of the outbox.

        One delivery already took cannot be withdrawn, and is reported.
        """
        if cast(CaseOutboxPersistence, self.datalayer).outbox_withdraw(
            activity_id
        ):
            self.logger.warning(
                "%s: withdrew Invite '%s' from the outbox: its entry did not"
                " commit",
                self.name,
                activity_id,
            )
            return
        self.logger.error(
            "%s: Invite '%s' was already taken for delivery, but its entry did"
            " not commit",
            self.name,
            activity_id,
        )

    def _record_queued(self, activity_id: str) -> None:
        """Note that *activity_id* reached the outbox; the base records nothing.

        A subclass whose retry must tell a queued Invite from a lost one
        overrides this to write a durable receipt (EP-04-011), since delivery
        empties the outbox and leaves nothing there to read.
        """

    def _commit_emission(self, activity_id: str, blob: str) -> None:
        """Commit the emitted Invite as a canonical entry (ADR-0109, VM-08-003)."""
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=cast(str, self.actor_id),
            case_id=self._case_id,
            activity_id=activity_id,
            activity_blob=blob,
            event_type=self._EVENT_TYPE,
            sync_port=self._sync_port,
        )

    def _invite_where_legal(
        self,
        dl: CaseOutboxPersistence,
        recipient_id: str,
        rsvp_deadline: datetime | None,
        *,
        cause_id: str,
        send_and_commit: Callable[[], None] | None = None,
    ) -> None:
        """Commit the Invite, then the invitee's row; apply it by copying.

        The decision is PEC ``INVITE`` on *recipient_id*'s row for this
        embargo where legal, with the Invite's deadline (CM-18-003,
        CM-28-013), taken on a staged store.  The Invite's entry is
        committed first (*send_and_commit*; ``None`` when the Invite
        *cause_id* is already committed), then the row as the CASE_MANAGER's
        own ``Update(EmbargoConsent)`` entry, and only then is the row
        written, by copying (ADR-0124, CLP-07-013).  Where INVITE does not
        apply the Invite is still committed, and no row entry follows.
        """
        # Regime 1 (ADR-0087): the relay follows the manager's own EM write on
        # this case, so a missing case or invitee is an anomaly, not a lenient
        # skip.  ``record_embargo_invite`` raises a ``VultronNotFoundError``,
        # which would read as the sender's fault (REFUSED, ADR-0095), so it is
        # re-raised as the internal error it is in the manager's own store.
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        try:
            decision = decide_commit_and_apply(
                datalayer=dl,
                case_id=self._case_id,
                decide=lambda staged: EmbargoLifecycle(
                    persistence=staged
                ).record_embargo_invite(
                    case_id=self._case_id,
                    invitee_id=recipient_id,
                    embargo_id=self._embargo_id,
                    rsvp_deadline=rsvp_deadline,
                ),
                trigger_activity=self.trigger_activity_factory,
                actor_id=self.actor_id,
                cause_id=cause_id,
                act_commit=send_and_commit,
            )
        except VultronNotFoundError as exc:
            raise RuntimeError(
                f"{self.name}: the CASE_MANAGER's roster names '{recipient_id}'"
                f" but its store has no record for it: {exc}"
            ) from exc
        if not decision.rows:
            self.logger.info(
                "%s: INVITE does not apply to '%s' (EP-09-004)",
                self.name,
                recipient_id,
            )


__all__ = [
    "EMBARGO_INVITE_EVENT_TYPE",
    "invite_rsvp_deadline",
    "CollectEmbargoInviteRecipientsNode",
    "EmStateAdmitsProposalNode",
    "EmbargoProposalNotYetRecordedNode",
    "case_manager_admits_proposal_guard",
    "RelayEmbargoInviteToEachNode",
]
