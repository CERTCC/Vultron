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

"""The CASE_MANAGER's re-issue of a stub Invite the embargo change staled.

When the active embargo is activated, revised or terminated while a stub
Invite is outstanding, the CASE_MANAGER sends a replacement on the same
participant record, naming the Invite it supersedes in ``inReplyTo``
(CM-11-016).  Split out of ``invite_actor_emit.py`` (BTND-07-004), whose
``build_stub_invite`` and ``commit_stub_invite`` every stub Invite shares.
"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import cast

from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    build_stub_invite,
    commit_stub_invite,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    RecordedStubInvite,
    awaiting_stub_reply,
    current_stub_embargo_id,
    invitee_record,
    outstanding_stale_stubs,
    recorded_stub_invites,
    stub_invite_expired,
)
from vultron.core.behaviors.embargo.decided_entries import (
    decide_commit_and_apply,
)
from vultron.core.behaviors.embargo.rsvp_stamp import invite_rsvp_deadline
from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.models._helpers import now_utc
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_event_types import CONSENT_ROW_VERBS
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.sync_helpers import recorded_entries_for_case

#: Kind label of a replacement stub Invite's id, derived from the Invite it
#: replaces (CM-11-016).
REISSUED_INVITE_ID_KIND = "reissue-invite-actor-to-case"


class ReissueStubInvitesNode(_EmitSingleActivityBase, StateWriteCapable):
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

    A replacement is an invitation to the embargo in force, as the first
    stub is: after its entry, the inert invitee's row for that embargo moves
    by PEC ``INVITE`` with the replacement's RSVP deadline, committed as the
    CASE_MANAGER's own ``Update(EmbargoConsent)`` entry and written by
    copying it (ADR-0124); with no embargo in force no row changes.

    Each replacement is queued, then committed (ADR-0119), under an id
    derived from the stub it replaces.  A replacement that committed while
    its invitee's row did not is completed by the next run, which commits
    the row it owes (:meth:`_rows_owed`).  A replacement whose commit failed is
    stored and sent but not yet in the ledger, and it is the invitee's newest
    stub, so nothing is stale for that invitee any more: the next run of the
    node finds it and records it, rebuilding it under the same id so the
    outbox does not queue it twice (OX-06-002).

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
        now = now_utc()
        stale_stubs = outstanding_stale_stubs(dl, case, self.actor_id, now)
        unrecorded = self._unrecorded_replacements()
        # A re-issued stub invites to the embargo it carries, the one in
        # force (CM-11-016); with none in force it invites to nothing.
        in_force = current_stub_embargo_id(case)
        owed = self._rows_owed(case, in_force, now)
        if not stale_stubs and not unrecorded and not owed:
            return Status.SUCCESS
        # Only a re-issue needs the emit port: a change that leaves no stub
        # stale must not fail a tree that was composed without one.
        if (f := self._require_factory()) is not None:
            self.logger.error("%s", self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None
        for replacement in owed:
            # The replacement committed and its row did not: commit the row.
            self._commit_with_invitee_row(
                dl,
                replacement.invitee_id,
                in_force,
                replacement.invite_id,
                replacement.end_time,
            )
        for replaced in unrecorded:
            self._reissue(replaced, in_force)
        for stale in stale_stubs:
            self._reissue(stale, in_force)
        return Status.SUCCESS

    def _rows_owed(
        self,
        case: VulnerabilityCase,
        in_force: str | None,
        now: datetime,
    ) -> list[RecordedStubInvite]:
        """Recorded replacements whose invitee's row was never invited.

        A replacement commits before its invitee's row (CLP-07-013), so a run
        whose row commit failed leaves the replacement recorded and the row
        as it was.  It is owed when the replacement is the invitee's newest
        stub and still outstanding, carries the embargo in force, the row
        has not moved to the replacement's invitation (``UNINVITED``, or
        ``INVITED`` under another deadline), and no row entry for it follows
        the replacement's in the ledger.  An answered or expired invitation
        owes nothing.
        """
        if in_force is None:
            return []
        assert self.datalayer is not None and self.actor_id is not None
        dl = self.datalayer
        entries = recorded_entries_for_case(case_id=self.case_id, dl=dl)
        position = {e.log_object_id: e.log_index for e in entries}
        by_invitee: dict[str, list[RecordedStubInvite]] = {}
        for stub in recorded_stub_invites(dl, self.case_id, self.actor_id):
            by_invitee.setdefault(stub.invitee_id, []).append(stub)
        owed: list[RecordedStubInvite] = []
        for invitee_id, stubs in by_invitee.items():
            newest = stubs[-1]
            replaced = next(
                (s for s in stubs if s.invite_id == newest.in_reply_to), None
            )
            record = invitee_record(dl, case, invitee_id)
            if (
                replaced is None
                or newest.invite_id != self._replacement_id(replaced)
                or newest.invite_id not in position
                or newest.embargo_id != in_force
                or stub_invite_expired(newest, now)
                or not awaiting_stub_reply(record)
            ):
                continue
            assert record is not None
            row = record.held_row(in_force)
            if row is None or not (
                row.state is EmbargoConsentState.UNINVITED
                or (
                    row.state is EmbargoConsentState.INVITED
                    and row.rsvp_deadline != newest.end_time
                )
            ):
                continue
            row_id = EmbargoConsent.build_id(in_force, invitee_id)
            after = position[newest.invite_id]
            if not any(
                e.log_index > after
                and e.event_type in CONSENT_ROW_VERBS
                and _extract_id_from_field(e.payload_snapshot.get("object"))
                == row_id
                for e in entries
            ):
                owed.append(newest)
        return owed

    def _unrecorded_replacements(self) -> list[RecordedStubInvite]:
        """The stubs whose replacement this node sent but did not commit.

        A replacement is told apart from any other stub by its id, which only
        this node derives from the stub replaced; one with no ledger entry was
        queued by a run whose commit failed.
        """
        assert self.datalayer is not None and self.actor_id is not None
        stubs = recorded_stub_invites(
            self.datalayer, self.case_id, self.actor_id
        )
        by_id = {stub.invite_id: stub for stub in stubs}
        recorded = {
            entry.log_object_id
            for entry in recorded_entries_for_case(
                case_id=self.case_id, dl=self.datalayer
            )
        }
        found: list[RecordedStubInvite] = []
        for stub in stubs:
            replaced = by_id.get(stub.in_reply_to or "")
            if (
                replaced is not None
                and stub.invite_id not in recorded
                and stub.invite_id == self._replacement_id(replaced)
            ):
                found.append(replaced)
        return found

    def _replacement_id(self, stale: RecordedStubInvite) -> str:
        """The id of the replacement for *stale*, derived from it."""
        assert self.actor_id is not None
        return derived_activity_id(
            REISSUED_INVITE_ID_KIND,
            self.actor_id,
            self.case_id,
            stale.invite_id,
        )

    def _reissue(
        self, stale: RecordedStubInvite, embargo_in_force: str | None
    ) -> None:
        """Send the replacement for *stale*, naming it: queue, then commit.

        The replacement's id is derived from the Invite it replaces, so a
        retry after a queued replacement whose commit failed — *stale* is
        still the invitee's newest recorded stub — rebuilds the same
        replacement, and the outbox does not queue it twice (OX-06-002,
        ADR-0119).
        """
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None
        dl = cast(CaseOutboxPersistence, self.datalayer)
        activity_id, activity_blob = build_stub_invite(
            datalayer=dl,
            factory=self.trigger_activity_factory,
            actor_id=self.actor_id,
            case_id=self.case_id,
            invitee_id=stale.invitee_id,
            roles=list(stale.roles) or None,
            attributed_to=stale.attributed_to,
            in_reply_to=stale.invite_id,
            actor_config=self._actor_config,
            activity_id=self._replacement_id(stale),
        )

        def _send_and_commit() -> None:
            self._emit_through_seam(activity_id, activity_blob)
            commit_stub_invite(
                datalayer=dl,
                actor_id=cast(str, self.actor_id),
                case_id=self.case_id,
                activity_id=activity_id,
                activity_blob=activity_blob,
            )

        self._commit_with_invitee_row(
            dl,
            stale.invitee_id,
            embargo_in_force,
            activity_id,
            invite_rsvp_deadline(json.loads(activity_blob)),
            _send_and_commit,
        )
        self.logger.info(
            "Actor '%s' re-issued stub Invite '%s' to '%s' as '%s' after"
            " an embargo change on case '%s' (CM-11-016)",
            self.actor_id,
            stale.invite_id,
            stale.invitee_id,
            activity_id,
            self.case_id,
        )

    def _commit_with_invitee_row(
        self,
        dl: CaseOutboxPersistence,
        invitee_id: str,
        embargo_id: str | None,
        activity_id: str,
        rsvp_deadline: datetime | None,
        send_and_commit: Callable[[], None] | None = None,
    ) -> None:
        """Commit the replacement, then the invitee's row for the embargo in force.

        A re-issued stub is an invitation to the embargo in force, as the
        first stub is: PEC ``INVITE`` on the inert invitee's row for that
        embargo, with the replacement's RSVP deadline (CM-11-016,
        CM-28-013).  An ``UNINVITED`` row (the invitee joined after the
        embargo was proposed) becomes ``INVITED``; an ``INVITED`` row keeps
        its state and takes the new deadline.  The row change is decided on
        a staged store, committed as the CASE_MANAGER's own
        ``Update(EmbargoConsent)`` entry after the replacement's, and written
        by copying (ADR-0124, CLP-07-013).  With no embargo in force
        (*embargo_id* ``None``, the re-issue after a termination) no row
        changes and none is committed.  *send_and_commit* is ``None`` when
        the replacement *activity_id* is already committed.
        """
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None
        case_id = self.case_id

        def _decide(staged: CasePersistence) -> None:
            if embargo_id is None:
                return
            EmbargoLifecycle(persistence=staged).record_embargo_invite(
                case_id=case_id,
                invitee_id=invitee_id,
                embargo_id=embargo_id,
                rsvp_deadline=rsvp_deadline,
            )

        decide_commit_and_apply(
            datalayer=dl,
            case_id=case_id,
            decide=_decide,
            trigger_activity=self.trigger_activity_factory,
            actor_id=self.actor_id,
            cause_id=activity_id,
            act_commit=send_and_commit,
        )


__all__ = ["REISSUED_INVITE_ID_KIND", "ReissueStubInvitesNode"]
