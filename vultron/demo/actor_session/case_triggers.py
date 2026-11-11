"""Report, case-lifecycle, membership and ownership-transfer trigger verbs."""

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
    WireTriggerResult,
)
from vultron.enums.roles import CVDRole


class CaseTriggers(SessionBinding):
    """Trigger verbs that open a case and manage who is in it."""

    # -- report triggers --------------------------------------------------

    def submit_report(
        self,
        *,
        report_name: str | None = None,
        report_content: str,
        recipient_id: str,
        proposed_embargo_end_time: datetime | None = None,
        csaf_document: dict[str, Any] | None = None,
        report_summary: str | None = None,
    ) -> WireTriggerResult:
        """Create a report and offer it to *recipient_id* (submit-report).

        *proposed_embargo_end_time* states the Reporter's embargo terms for
        the report; the Offer then carries them as ``proposedEmbargo``
        (EP-04-004).  ``None`` states none — the receiver's default applies
        (EP-04-001).

        *csaf_document* attaches a CSAF 2.1 vulnerability report as a JSON
        object.  *report_summary* is the report's summary.  When
        *csaf_document* is given, *report_name* is optional; the trigger
        fills it from the document's title (CSAF-04-010).
        """
        body: dict[str, Any] = {
            "report_content": report_content,
            "recipient_id": recipient_id,
        }
        if report_name is not None:
            body["report_name"] = report_name
        if proposed_embargo_end_time is not None:
            body["proposed_embargo_end_time"] = (
                proposed_embargo_end_time.isoformat()
            )
        if csaf_document is not None:
            body["csaf_document"] = csaf_document
        if report_summary is not None:
            body["report_summary"] = report_summary
        return self._post("submit-report", body)

    def ack_report(
        self, *, offer_id: str, note: str | None = None
    ) -> WireTriggerResult:
        """Acknowledge the offered report to its reporter (ack-report, RK)."""
        body: dict[str, Any] = {"offer_id": offer_id}
        if note is not None:
            body["note"] = note
        return self._post("ack-report", body)

    def validate_report(
        self, *, offer_id: str, note: str | None = None
    ) -> WireTriggerResult:
        """Advance the offered report to RM.VALID (validate-report)."""
        body: dict[str, Any] = {"offer_id": offer_id}
        if note is not None:
            body["note"] = note
        return self._post("validate-report", body)

    def invalidate_report(
        self, *, offer_id: str, note: str | None = None
    ) -> WireTriggerResult:
        """Mark the offered report RM.INVALID (invalidate-report)."""
        body: dict[str, Any] = {"offer_id": offer_id}
        if note is not None:
            body["note"] = note
        return self._post("invalidate-report", body)

    # -- case lifecycle triggers -----------------------------------------

    def create_case(
        self,
        *,
        name: str,
        content: str,
        report_id: str | None = None,
        to: list[str] | None = None,
    ) -> WireTriggerResult:
        """Create a local case and queue a CreateCaseActivity (create-case)."""
        body: dict[str, Any] = {"name": name, "content": content}
        if report_id is not None:
            body["report_id"] = report_id
        if to is not None:
            body["to"] = to
        return self._post("create-case", body)

    def engage_case(self) -> WireTriggerResult:
        """Engage the bound case, advancing RM to ACCEPTED (engage-case)."""
        return self._post("engage-case", {"case_id": self._require_case_id()})

    def set_stub_summary(self, stub_summary: str) -> WireTriggerResult:
        """Seed stub_summary on this actor's DataLayer copy of the bound case.

        Demo-only scaffold: sets ``stub_summary`` so a subsequent
        :meth:`invite_actor_to_case` call can build the stub Invite
        (CM-17-010, MV-10-001, #4165).
        """
        return self._post(
            "set-stub-summary",
            {"case_id": self._require_case_id(), "stub_summary": stub_summary},
            path_prefix="demo",
        )

    def invite_actor_to_case(
        self, *, invitee_id: str, roles: list[CVDRole] | None = None
    ) -> WireActivityResult:
        """Ask the CASE_MANAGER to invite *invitee_id* (invite-actor-to-case).

        The result is the owner's own Offer to the CASE_MANAGER, not the
        Invite: the CASE_MANAGER emits the Invite (CM-17-007, ADR-0109), so a
        caller finds it on the invitee's side with
        :func:`~vultron.demo.helpers.polling.find_case_invite_for_actor`.
        """
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "invitee_id": invitee_id,
            **self._roles_body(roles),
        }
        return cast(
            WireActivityResult,
            self._post(
                "invite-actor-to-case", body, result_cls=WireActivityResult
            ),
        )

    def suggest_actor_to_case(
        self, *, suggested_actor_id: str, roles: list[CVDRole] | None = None
    ) -> WireTriggerResult:
        """Recommend *suggested_actor_id* to the bound case (suggest-actor-to-case)."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "suggested_actor_id": suggested_actor_id,
            **self._roles_body(roles),
        }
        return self._post("suggest-actor-to-case", body)

    def accept_case_invite(self, *, invite_id: str) -> WireTriggerResult:
        """Accept a case invitation identified by *invite_id* (accept-case-invite)."""
        return self._post("accept-case-invite", {"invite_id": invite_id})

    def reject_case_invite(self, *, invite_id: str) -> WireTriggerResult:
        """Reject a case invitation identified by *invite_id* (reject-case-invite)."""
        return self._post("reject-case-invite", {"invite_id": invite_id})

    def accept_full_case_invite(self, *, invite_id: str) -> WireTriggerResult:
        """Judge the case valid: Accept the full-case Invite (RV, CM-11-011)."""
        return self._post("accept-full-case-invite", {"invite_id": invite_id})

    def accept_actor_recommendation(
        self, *, cp_offer_id: str, case_actor_id: str
    ) -> WireTriggerResult:
        """Accept a forwarded Offer(CaseParticipant) (accept-actor-recommendation)."""
        return self._post(
            "accept-actor-recommendation",
            {"cp_offer_id": cp_offer_id, "case_actor_id": case_actor_id},
        )

    def reject_actor_recommendation(
        self, *, cp_offer_id: str, case_actor_id: str
    ) -> WireTriggerResult:
        """Reject a forwarded Offer(CaseParticipant) (reject-actor-recommendation)."""
        return self._post(
            "reject-actor-recommendation",
            {"cp_offer_id": cp_offer_id, "case_actor_id": case_actor_id},
        )

    def offer_case_ownership_transfer(
        self,
        *,
        transferee_id: str,
        content: str | None = None,
        end_time: datetime | None = None,
    ) -> WireActivityResult:
        """Offer ownership of the bound case to *transferee_id* (offer-case-ownership-transfer).

        *end_time*, when given, is the deadline to answer (TRIG-11-007).
        """
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "transferee_id": transferee_id,
        }
        if content is not None:
            body["content"] = content
        if end_time is not None:
            body["end_time"] = end_time.isoformat()
        return cast(
            WireActivityResult,
            self._post(
                "offer-case-ownership-transfer",
                body,
                result_cls=WireActivityResult,
            ),
        )

    def accept_case_ownership_transfer(
        self, *, offer_id: str
    ) -> WireActivityResult:
        """Accept a case-ownership-transfer offer (accept-case-ownership-transfer)."""
        return cast(
            WireActivityResult,
            self._post(
                "accept-case-ownership-transfer",
                {"offer_id": offer_id},
                result_cls=WireActivityResult,
            ),
        )

    def reject_case_ownership_transfer(
        self, *, offer_id: str
    ) -> WireActivityResult:
        """Decline a case-ownership-transfer offer (reject-case-ownership-transfer)."""
        return cast(
            WireActivityResult,
            self._post(
                "reject-case-ownership-transfer",
                {"offer_id": offer_id},
                result_cls=WireActivityResult,
            ),
        )

    def withdraw_case_ownership_transfer(
        self, *, offer_id: str
    ) -> WireActivityResult:
        """Withdraw an open case-ownership-transfer offer (withdraw-case-ownership-transfer)."""
        return cast(
            WireActivityResult,
            self._post(
                "withdraw-case-ownership-transfer",
                {"offer_id": offer_id},
                result_cls=WireActivityResult,
            ),
        )
