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

"""Lazy RSVP-deadline enforcement (EMB-17, CM-28): operations with no EM transition.

An invitation's deadline is read when something asks about it, not by a
timer: ``assess_invite_expiry``, ``pending_invitations`` and
``overdue_invitations`` read rows,
and ``detect_and_apply_expiry`` moves an unanswered ``INVITED`` row to
``TIMED_OUT`` (the pocket veto).  The CASE_MANAGER's own expiry and honour of
a late Accept commit the row before writing it, through the one apply function
(``CommitAndApplyInviteExpiryNode``, ``CommitAndApplyHonourLateAcceptNode``,
ADR-0124).
"""

import logging
from datetime import datetime

from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants._lookup import iter_case_participants
from vultron.core.services.embargo_lifecycle.consent import _unchanged
from vultron.core.services.embargo_lifecycle.pec import (
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
)
from vultron.core.states.embargo_register import FINAL_REGISTER_STATUSES
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)

logger = logging.getLogger(__name__)


_ANSWERED_OR_TIMED_OUT = frozenset(
    {EmbargoConsentState.DECLINED, EmbargoConsentState.TIMED_OUT}
)
"""Row states that close an invitation without a deadline left to read.

A ``TIMED_OUT`` row's deadline passed; a ``DECLINED`` row was answered, so
an Accept of it is a later change of answer, which EMB-17-002 honours on the
embargo in force.  Both rows drop their deadline when they leave
``INVITED``, so the state itself is what says the invitation closed.
"""


def _invitation_has_closed(
    participant: CaseParticipant, embargo_id: str, now: datetime
) -> bool:
    """Whether *participant*'s invitation to *embargo_id* has closed by *now*.

    Closed means the row timed out or was declined, or is still ``INVITED``
    with a deadline that has passed (CM-28-001).  An Accept of a closed
    invitation is a late Accept, routed by EMB-17.
    """
    if participant.consent_for(embargo_id) in _ANSWERED_OR_TIMED_OUT:
        return True
    deadline = participant.rsvp_deadline_for(embargo_id)
    return deadline is not None and now >= deadline


class _InviteExpiryOperationsMixin(_PecEffectsMixin):
    """Invite-expiry operations with no EM transition (EMB-17, CM-28)."""

    def assess_invite_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
        now: datetime,
    ) -> tuple[bool, bool]:
        """Read-only check: has the invitation to *embargo_id* timed out?

        Returns a ``(is_expired, needs_apply)`` pair where:

        * ``is_expired`` — ``True`` when the invitation is closed — its
          deadline has passed, its row already ``TIMED_OUT`` or
          ``DECLINED``, or the embargo's register entry is final (the terms
          are stale, EMB-17-003) — **and** the participant is not a
          signatory to the active embargo.  Used by EMB-17 routing.
        * ``needs_apply`` — ``True`` when the row for *embargo_id* is still
          ``INVITED`` **and** its deadline has passed.  When ``True``, the
          caller commits the expiry and its ``TIMED_OUT`` row, then applies
          it (CLP-10-006, ADR-0124).

        Only the row for *embargo_id* is read: an RSVP deadline belongs to
        one invitation (CM-28-001, CM-28-012), and the participant's other
        invitations keep their own.  This method makes **no writes**, so a
        BT node can assess the situation, and only once the entries commit is
        the row written (guard → commit → effect, CLP-10-006, BT-06-006).

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the actor whose participant record to check.
            embargo_id: ID of the ``EmbargoEvent`` the invitation was for.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            ``(is_expired, needs_apply)`` — both ``False`` when the actor has
            no participant record, or the invitation is still open: the row
            is not ``TIMED_OUT`` or ``DECLINED`` and its deadline, if any,
            has not yet passed.
        """
        case = self._read_case(case_id)
        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            return False, False
        _, participant = resolved
        is_expired = not participant.is_signatory(case.active_embargo_id)
        entry = case.embargo_register_entry(embargo_id)
        if entry is not None and entry.status in FINAL_REGISTER_STATUSES:
            # The terms were superseded, rejected, cancelled or terminated:
            # the invitation is closed whatever its deadline, and its row is
            # frozen, so there is nothing to time out (ADR-0122).  The
            # caller's EMB-17 routing answers with the current embargo.
            return is_expired, False
        if not _invitation_has_closed(participant, embargo_id, now):
            return False, False
        # Only an INVITED row carries a deadline (CM-28-013) and the entry is
        # open, so an INVITED row whose deadline passed times out; a row
        # already TIMED_OUT or DECLINED has nothing to apply.
        needs_apply = (
            participant.consent_for(embargo_id) == EmbargoConsentState.INVITED
        )
        return is_expired, needs_apply

    def pending_invitations(
        self, case_id: str
    ) -> list[tuple[CaseParticipant, str]]:
        """Every embargo invitation on *case_id* still awaiting a reply.

        Read-only.  Returns one ``(participant, embargo_id)`` pair per
        consent row that is ``INVITED`` and whose register entry is not final
        — the rows an expiry would move.  A row for a
        final entry is frozen (ADR-0122), so it is not pending: nothing can
        answer or expire it.  The owner-close settle step (CM-23-014) expires
        each pair without waiting for its deadline.

        Every participant record counts, joined or not: a pending invitation
        is a row on a record, not an addressee (CM-10-007 governs who is
        sent to, not whose rows are read).  Ordered by the case's
        participants, then by each record's rows, so the entries a caller
        commits come out in a stable order.

        Args:
            case_id: ID of the ``VulnerabilityCase``.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
        """
        case = self._read_case(case_id)
        pending: list[tuple[CaseParticipant, str]] = []
        for participant in iter_case_participants(case, self._persistence):
            for row in participant.embargo_consents:
                if row.state != EmbargoConsentState.INVITED:
                    continue
                entry = case.embargo_register_entry(row.embargo_id)
                if (
                    entry is not None
                    and entry.status in FINAL_REGISTER_STATUSES
                ):
                    continue
                pending.append((participant, row.embargo_id))
        return pending

    def overdue_invitations(
        self, case_id: str, now: datetime
    ) -> list[tuple[CaseParticipant, str]]:
        """Every pending invitation on *case_id* whose RSVP deadline passed.

        Read-only.  The :meth:`pending_invitations` pairs — ``INVITED`` rows
        on an open proposal or the embargo in force — whose deadline is at or
        before *now* (CM-28-001), in the same order.  A row with no deadline
        never lapses on its own.  The CASE_MANAGER's sweep (CM-28-015)
        expires each pair; a row already ``TIMED_OUT`` is not ``INVITED``, so
        a repeat sweep finds nothing to expire.

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            now: The CASE_MANAGER's clock reading the deadlines are compared
                against.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
        """
        overdue: list[tuple[CaseParticipant, str]] = []
        for participant, embargo_id in self.pending_invitations(case_id):
            deadline = participant.rsvp_deadline_for(embargo_id)
            if deadline is not None and now >= deadline:
                overdue.append((participant, embargo_id))
        return overdue

    def detect_and_apply_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
        now: datetime,
    ) -> EmbargoLifecycleResult:
        """Lazily enforce one invitation's RSVP deadline: apply ``TIME_OUT`` if it passed.

        Reads the row for *embargo_id* on *actor_id*'s participant record.
        If the row is ``INVITED`` and its deadline has passed, applies
        ``PEC_Trigger.TIME_OUT`` (``INVITED → TIMED_OUT``).  A timed-out
        invitation is not a refusal, so ``DECLINE`` is never the timer path
        (ADR-0118, CM-18-002), and the participant's other invitations keep
        their own deadlines (CM-28-001).

        Idempotent: a row already ``TIMED_OUT`` (or in any state other than
        ``INVITED``) is not moved.  The result still carries
        ``is_expired=True`` when the deadline has passed and the participant
        is not a signatory to the active embargo, so the caller can branch on
        whether the invite window closed without re-deriving it.

        Args:
            case_id: ID of the VulnerabilityCase.
            actor_id: ID of the actor whose participant record to check.
            embargo_id: ID of the ``EmbargoEvent`` the invitation was for.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            :class:`EmbargoLifecycleResult` with ``is_expired`` reflecting
            whether the deadline has passed.
        """
        case = self._read_case(case_id)
        em_state = case.em_state

        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            logger.debug(
                "detect_and_apply_expiry: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)
        participant_id, participant = resolved

        deadline = participant.rsvp_deadline_for(embargo_id)
        if not _invitation_has_closed(participant, embargo_id, now):
            return _unchanged(em_state)

        participant_changes = self._apply_where_legal(
            case, participant_id, participant, embargo_id, PEC_Trigger.TIME_OUT
        )
        if participant_changes:
            logger.info(
                "Invite to embargo '%s' timed out for actor '%s' on case '%s'"
                " (deadline=%s, PEC INVITED → TIMED_OUT)",
                embargo_id,
                actor_id,
                case_id,
                deadline,
            )

        # A signatory to the embargo in force has already agreed; a stale
        # deadline is not a real expiry.  Anyone else past the deadline
        # (just timed out, already timed out, or declined) triggers the EMB-17
        # late-Accept routing in the caller.
        return _unchanged(
            em_state,
            participant_changes=participant_changes,
            is_expired=not participant.is_signatory(case.active_embargo_id),
        )
