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


"""TriggerLedgerRecordsPort: the ledger part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

The CASE_MANAGER's own case-file changes, recorded in the case ledger.
"""

from typing import Protocol

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.participant_status import ParticipantStatus


class TriggerLedgerRecordsPort(Protocol):
    """The CASE_MANAGER's own case-file changes, recorded in the case ledger.

    Each builds the activity a ledger entry records, as the CASE_MANAGER
    (``actor``), carrying the changed object as the CASE_MANAGER holds it;
    its sealed blob is the entry's ``payloadSnapshot`` (CLP-07-013,
    VM-08-003).  None is queued to the outbox: the ledger fan-out delivers
    it.  Each id is derived from the CASE_MANAGER and what changed, so a
    re-run hands back the body the first run sealed (ID-04-004).  Each
    returns ``(activity_id, activity_blob)``.
    """

    def record_case_created(
        self,
        create_activity_id: str,
    ) -> tuple[str, str]:
        """The genesis ``Create(VulnerabilityCase)`` (``create_case``).

        It is the ``Create`` the CASE_MANAGER built for the case under
        *create_activity_id*, its sealed body verbatim: one activity, both
        delivered and ledgered (CLP-07-011).  Unlike the other ``record_*``
        methods it builds nothing.

        Raises:
            VultronNotFoundError: no body is sealed under *create_activity_id*.
        """
        ...

    def record_embargo_event_created(
        self,
        embargo: EmbargoEvent,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """``Create(EmbargoEvent)`` (``create_embargo_event``), the embargo in full.

        For an embargo the case's creation wrote, such as the default embargo
        (CLP-07-013).  An embargo is created once, so the id is derived from
        its own id.
        """
        ...

    def record_report_added_to_case(
        self,
        report_id: str,
        case_id: str,
        actor: str,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
    ) -> tuple[str, str]:
        """``Add(VulnerabilityReport)[target=VulnerabilityCase]`` (``add_report_to_case``).

        The stored report is carried inline.  ``offer_id`` and
        ``offer_actor_id``, when given, are the report's Offer provenance
        (CP-01-007), carried for participants who were never sent the Offer.
        """
        ...

    def record_participant_status_added(
        self,
        status: ParticipantStatus,
        participant: CaseParticipant,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """``Add(ParticipantStatus)[target=CaseParticipant]`` (``add_participant_status_to_participant``).

        Both are carried inline, as the caller just stored them.
        """
        ...

    def record_case_status_added(
        self,
        status: CaseStatus,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """``Add(CaseStatus)[target=VulnerabilityCase]`` (``add_case_status_to_case``).

        *status* is carried inline; it may be one the caller persists only
        once the entry is committed.
        """
        ...

    def record_case_participant_created(
        self,
        participant: CaseParticipant,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """``Create(CaseParticipant)`` (``create_case_participant``), the record as stored."""
        ...

    def record_case_participant_updated(
        self,
        participant: CaseParticipant,
        case_id: str,
        actor: str,
        cause_id: str,
    ) -> tuple[str, str]:
        """``Update(CaseParticipant)`` (``update_case_participant``), the record as stored.

        *cause_id* names the act the change follows, such as the accepted
        ownership-transfer Offer; the id is derived from it and the record,
        so one act's change to one record is one entry.
        """
        ...

    def record_case_owner_updated(
        self,
        case: VulnerabilityCase,
        actor: str,
        cause_id: str,
    ) -> tuple[str, str]:
        """``Update(VulnerabilityCase)`` (``update_case_owner``), the changed case.

        Records the case's new ``attributed_to`` after an ownership transfer
        (CM-21-024).  *case* is the case as it will be stored: the entry
        commits before the change is saved (CLP-07-013).  *cause_id* names
        the act the change follows, as for
        :meth:`record_case_participant_updated`.
        """
        ...

    def record_embargo_consent_created(
        self,
        row: EmbargoConsent,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """``Create(EmbargoConsent)`` (``create_embargo_consent``), the new row in full.

        *row* names the participant actor whose consent it is.  A row is
        created once, so the id is derived from the row's own id.
        """
        ...

    def record_embargo_consent_updated(
        self,
        row: EmbargoConsent,
        case_id: str,
        actor: str,
        cause_id: str,
    ) -> tuple[str, str]:
        """``Update(EmbargoConsent)`` (``update_embargo_consent``), the changed row in full.

        *row* is the row as it will be stored: the entry commits before the
        change is made (CLP-07-013).  *cause_id* names the act the change
        follows; the id is derived from it and the row, so one act's change
        to one row is one entry.
        """
        ...

    def record_case_announced(
        self,
        case_id: str,
        actor: str,
        object_id: str,
    ) -> tuple[str, str]:
        """``Announce(VulnerabilityCase)`` for the demo ``sync-log-entry`` verb.

        The stored case is carried inline.  The id is derived from the
        CASE_MANAGER, the case and *object_id*, so one request repeated
        commits one entry.
        """
        ...
