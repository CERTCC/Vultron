"""Note, embargo, publication-milestone, leave and sync trigger verbs."""

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

from datetime import datetime
from typing import Any, cast

from vultron.demo.actor_session.binding import SessionBinding
from vultron.demo.actor_session.results import (
    WireActivityResult,
    WireNoteResult,
    WireSyncLogEntryResult,
    WireTriggerResult,
)


class ProgressTriggers(SessionBinding):
    """Trigger verbs that move a bound case's work forward."""

    # -- demo-only triggers (path_prefix="demo") -------------------------

    def add_note_to_case(
        self,
        *,
        note_name: str,
        note_content: str,
        in_reply_to: str | None = None,
    ) -> WireNoteResult:
        """Attach a note to the bound case (add-note-to-case)."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "note_name": note_name,
            "note_content": note_content,
        }
        if in_reply_to is not None:
            body["in_reply_to"] = in_reply_to
        return cast(
            WireNoteResult,
            self._post(
                "add-note-to-case",
                body,
                path_prefix="demo",
                result_cls=WireNoteResult,
            ),
        )

    # -- embargo triggers ------------------------------------------------

    def propose_embargo(
        self, *, end_time: datetime, note: str | None = None
    ) -> WireActivityResult:
        """Propose an embargo ending at *end_time* (propose-embargo).

        The result is the proposer's own ``Invite(EmbargoEvent)`` to the
        CASE_MANAGER, which relays it to the other participants (EP-09-002);
        the embargo's id is the Invite's ``object``.
        """
        return self._embargo_proposal("propose-embargo", end_time, note)

    def propose_embargo_revision(
        self, *, end_time: datetime, note: str | None = None
    ) -> WireActivityResult:
        """Propose revised terms ending at *end_time* (propose-embargo-revision).

        Valid only while an embargo is in force (``EM.ACTIVE`` or
        ``EM.REVISE``); the result is shaped as :meth:`propose_embargo`'s.
        """
        return self._embargo_proposal(
            "propose-embargo-revision", end_time, note
        )

    def _embargo_proposal(
        self, behavior: str, end_time: datetime, note: str | None
    ) -> WireActivityResult:
        """Post an embargo proposal *behavior* and type the emitted Invite."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "end_time": end_time.isoformat(),
        }
        if note is not None:
            body["note"] = note
        return cast(
            WireActivityResult,
            self._post(behavior, body, result_cls=WireActivityResult),
        )

    def accept_embargo(
        self, *, proposal_id: str | None = None
    ) -> WireTriggerResult:
        """Accept an open embargo proposal on the bound case (accept-embargo).

        *proposal_id* names the proposal; omitted, the earliest-expiring open
        proposal is answered (EP-08-002).
        """
        body: dict[str, Any] = {"case_id": self._require_case_id()}
        if proposal_id is not None:
            body["proposal_id"] = proposal_id
        return self._post("accept-embargo", body)

    def terminate_embargo(self) -> WireTriggerResult:
        """Announce the end of the bound case's active embargo (terminate-embargo)."""
        return self._post(
            "terminate-embargo", {"case_id": self._require_case_id()}
        )

    def notify_fix_ready(self) -> WireTriggerResult:
        """Self-report fix ready (CS.VFd) for the bound case (notify-fix-ready)."""
        return self._post(
            "notify-fix-ready",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def notify_fix_deployed(self) -> WireTriggerResult:
        """Self-report fix deployed (CS.VFD) for the bound case (notify-fix-deployed)."""
        return self._post(
            "notify-fix-deployed",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def notify_published(self) -> WireTriggerResult:
        """Self-report public disclosure for the bound case (notify-published)."""
        return self._post(
            "notify-published",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def leave_case(self) -> WireTriggerResult:
        """Send Leave(VulnerabilityCase) for the bound case (leave-case, TRIG-13-001)."""
        return self._post("leave-case", {"case_id": self._require_case_id()})

    def sync_log_entry(self, *, object_id: str) -> WireSyncLogEntryResult:
        """Commit and fan out a canonical ledger entry (sync-log-entry).

        The entry's semantic type is the registry's label for its
        ``Announce(VulnerabilityCase)`` payload (ADR-0140), never the
        caller's.
        """
        return cast(
            WireSyncLogEntryResult,
            self._post(
                "sync-log-entry",
                {
                    "case_id": self._require_case_id(),
                    "object_id": object_id,
                },
                path_prefix="demo",
                result_cls=WireSyncLogEntryResult,
            ),
        )
