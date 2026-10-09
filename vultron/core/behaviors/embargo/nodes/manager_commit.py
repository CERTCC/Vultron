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

"""The CASE_MANAGER's own embargo decision, committed as a canonical entry.

A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).  When
the role holder is the actor deciding — proposing terms, accepting or
rejecting them, or ending the embargo — its EM write is canonical, and a
replica can only learn it from a ledger entry the announce slots replay
(EP-09-007, RSH-08-004).  The ``Add(CaseStatus)`` the trigger tree also
emits is not replayed for EM, so without this commit every replica kept the
state it had before the manager decided (#4085).

The nodes here build the decision activity through the trigger-activity
factory as the executing actor, commit the sealed blob as the canonical
entry (VM-08-003) and only then queue it (ledger commit precedes outbox
write).  The activity is addressed to the participants it has to *reach*,
never to the manager itself (CLP-10-001, ADR-0109): an embargo teardown goes
to every other participant (EMB-19-001), and an empty audience commits the
entry and queues nothing (EMB-19-002).  A decision every replica learns from
the entry alone (an Accept or Reject the manager makes) is addressed to
nobody and only committed.

Like the relay node, these catch nothing: a failed factory call or commit
after the manager's EM write is not a protocol refusal, so the exception
escapes to ``BTBridge`` and the trigger raises (BT-14-001).
"""

from collections.abc import Callable
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.events.base import MessageSemantics
from vultron.core.participants.recipients import case_content_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence

#: Build the decision activity addressed to *to* (``None``: nobody) and
#: return ``(activity_id, sealed_blob)`` — the shape every embargo factory
#: method returns.
EmbargoActivityBuilder = Callable[[list[str] | None], tuple[str, str]]

#: Ledger ``event_type`` of a committed embargo teardown — the value the
#: ``EmbargoTeardown`` announce slot replays.
EMBARGO_TEARDOWN_EVENT_TYPE = (
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE.value
)

#: ``result_out`` key :class:`CommitEmbargoDecisionNode` writes the id of the
#: activity it committed to, for :class:`IndexOwnEmbargoProposalNode`.
COMMITTED_ACTIVITY_KEY = "committed_activity_id"


class _CommitEmbargoDecisionBase(_EmitSingleActivityBase):
    """Build → commit → (queue) one embargo decision activity.

    Subclasses supply :meth:`_build`.  With ``notify_participants`` the
    activity is addressed to every case-content recipient except the
    executing actor, and queued when that audience is not empty; otherwise it
    is addressed to nobody and only committed.

    The queue write goes through the shared emit seam
    (:meth:`_EmitSingleActivityBase._emit_through_seam`, OX-14-001); unlike
    that base's ``update()``, this one catches nothing (see the module
    docstring).
    """

    def __init__(
        self,
        case_id: str,
        event_type: str,
        notify_participants: bool = False,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._event_type = event_type
        self._notify_participants = notify_participants

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        """Return ``(activity_id, sealed_blob)`` for an activity sent *to*."""
        raise NotImplementedError

    def _build_all(self, to: list[str] | None) -> list[tuple[str, str]]:
        """Return every ``(activity_id, sealed_blob)`` this decision commits.

        One decision is one activity, except an abandonment, which answers
        every open proposal at once (EMB-16-001) and overrides this.
        """
        return [self._build(to)]

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        actor_id = cast(str, self.actor_id)
        dl = cast(CaseOutboxPersistence, self.datalayer)

        to = (
            case_content_recipients(case, dl, excluding={actor_id})
            if self._notify_participants
            else []
        )
        committed = []
        for activity_id, blob in self._build_all(to or None):
            # A nested commit inherits the outer execution's ``/sync_port``,
            # so the entry is announced to every participant replica
            # (SYNC-02-002).
            commit_emitted_activity(
                datalayer=dl,
                actor_id=actor_id,
                case_id=self._case_id,
                activity_id=activity_id,
                activity_blob=blob,
                event_type=self._event_type,
            )
            if to:
                self._emit_through_seam(activity_id, blob)
            committed.append(activity_id)
        self.feedback_message = (
            f"CASE_MANAGER committed '{self._event_type}' entry for"
            f" {', '.join(repr(i) for i in committed)} on case"
            f" '{self._case_id}' ({len(to)} participant(s) addressed)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CommitEmbargoDecisionNode(_CommitEmbargoDecisionBase):
    """Commit the decision a trigger use case builds (EP-09-008, #4085).

    *builder* is the use case's factory closure, so the use case captures the
    activity it reports in its result.  With *result_out* the built
    activity's id is also written to ``result_out[COMMITTED_ACTIVITY_KEY]``.
    """

    def __init__(
        self,
        case_id: str,
        event_type: str,
        builder: EmbargoActivityBuilder,
        notify_participants: bool = False,
        result_out: dict[str, object] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            event_type=event_type,
            notify_participants=notify_participants,
            name=name,
        )
        self._builder = builder
        self._result_out = result_out

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        activity_id, blob = self._builder(to)
        if self._result_out is not None:
            self._result_out[COMMITTED_ACTIVITY_KEY] = activity_id
        return activity_id, blob


class IndexOwnEmbargoProposalNode(DataLayerActionWithPorts):
    """Index the CASE_MANAGER's own proposal (EP-09-001, EP-08-002).

    The manager answers its own terms through
    ``pending_embargo_proposal_index``, as it answers a proposal it received.
    It runs last in the manager's propose arm, so the correlation is written
    only once every other half of the proposal — EM write, commit, relay —
    has succeeded (ID-04-005).  Reads the proposal id
    :class:`CommitEmbargoDecisionNode` wrote to ``result_out``; a missing id
    is a fault in the tree, not a refusal, so it raises (BT-14-001).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._result_out = result_out

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        proposal_id = self._result_out.get(COMMITTED_ACTIVITY_KEY)
        if not isinstance(proposal_id, str) or not proposal_id:
            raise RuntimeError(
                f"{self.name}: no committed proposal id for embargo"
                f" '{self._embargo_id}' on case '{self._case_id}'"
            )
        record_embargo_proposal_index(
            self.datalayer, self._case_id, self._embargo_id, proposal_id
        )
        self.feedback_message = (
            f"Indexed own proposal '{proposal_id}' for embargo"
            f" '{self._embargo_id}' on case '{self._case_id}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CommitEmbargoTeardownNode(_CommitEmbargoDecisionBase):
    """Commit the CASE_MANAGER's ``Remove(EmbargoEvent)`` and tell the others.

    The cascade form of the terminate decision: it has no use case to build
    the activity, so it reads ``/embargo_id`` (written by
    ``ReadEmbargoIdNode``) and calls the factory itself.  Addressed to every
    other participant (EMB-19-001), never to the manager (#4112).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            case_id=case_id,
            event_type=EMBARGO_TEARDOWN_EVENT_TYPE,
            notify_participants=True,
            name=name,
        )

    def initialise(self) -> None:
        super().initialise()
        self._embargo_id: str = self.get_input("embargo_id")

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.terminate_embargo(
            embargo_id=self._embargo_id,
            case_id=self._case_id,
            actor=cast(str, self.actor_id),
            to=to,
        )


__all__ = [
    "COMMITTED_ACTIVITY_KEY",
    "EMBARGO_TEARDOWN_EVENT_TYPE",
    "EmbargoActivityBuilder",
    "CommitEmbargoDecisionNode",
    "CommitEmbargoTeardownNode",
    "IndexOwnEmbargoProposalNode",
]
