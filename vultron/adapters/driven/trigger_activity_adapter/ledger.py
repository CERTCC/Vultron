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

"""The CASE_MANAGER's own case-file changes, as activities for the ledger.

Every change the CASE_MANAGER makes to the case file is committed as its own
entry, and the entry's ``payloadSnapshot`` is the activity built here and
sealed, verbatim (CLP-07-013, VM-08-003).  None is queued to the outbox, or
stored as an activity: the ledger fan-out is its delivery (see
``_base._seal_record``).  The genesis entry is the exception: it is the
``Create(VulnerabilityCase)`` the creation already built and queued, so the
case's creation is one activity, delivered and ledgered (CLP-07-011).  Each
id is derived from the CASE_MANAGER and what changed, so a re-run builds
nothing new and hands back the body the first run sealed (ID-04-004), which
is what lets the commit boundary recognise the retry as the entry it already
holds.

Each object is carried as the CASE_MANAGER holds it: the participant or status
the caller has just written.  A replica stores what the entry carries
(ADR-0124).  Two snapshots carry a case with its participants and reports
inline: the genesis ``Create``, built for its first participant (and also
carrying its active embargo), and the demo verb's ``Announce`` (AKM-02-004).
"""

import logging

from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import (
    add_report_to_case_activity,
    add_status_to_case_activity,
    add_status_to_participant_activity,
    create_embargo_consent_activity,
    create_embargo_event_activity,
    create_participant_activity,
    update_case_activity,
    update_embargo_consent_activity,
    update_participant_activity,
)
from vultron.wire.as2.factories.case import (
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._base import _case_for_wire, _seal_record, _to_wire

logger = logging.getLogger(__name__)


class _LedgerRecordsMixin:
    """CASE_MANAGER-authored activities recorded in the case ledger."""

    _dl: CaseOutboxPersistence

    def record_case_created(
        self,
        create_activity_id: str,
    ) -> tuple[str, str]:
        """Hand back the built ``Create(VulnerabilityCase)`` for the genesis entry.

        The case's creation is one activity, delivered and ledgered
        (CLP-07-011): the ``Create`` the creation sealed for the outbox,
        carrying its participants, reports and active embargo inline.  Each
        of them is also carried in full by an entry of its own
        (``create_embargo_event``, ``add_report_to_case``,
        ``create_case_participant``), so a replica that builds its case from
        the ledger copies each record from its own entry (ADR-0124).
        """
        sealed = read_sealed_body(self._dl, create_activity_id)
        if sealed is None:
            raise VultronNotFoundError(
                "Create(VulnerabilityCase)", create_activity_id
            )
        return create_activity_id, sealed.body

    def record_embargo_event_created(
        self,
        embargo: EmbargoEvent,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Build and seal ``Create(EmbargoEvent)``, the embargo in full."""
        activity = create_embargo_event_activity(
            embargo=embargo,
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "embargo-event-created", actor, embargo.id_
            ),
        )
        return _seal_record(self._dl, activity)

    def record_report_added_to_case(
        self,
        report_id: str,
        case_id: str,
        actor: str,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
    ) -> tuple[str, str]:
        """Build and seal ``Add(VulnerabilityReport, target=case)``."""
        report = _to_wire(self._dl.read(report_id), as_VulnerabilityReport)
        activity = add_report_to_case_activity(
            report=report,
            target=case_id,
            actor=actor,
            context=case_id,
            offer_id=offer_id or None,
            offer_actor_id=offer_actor_id or None,
            id_=derived_activity_id(
                "report-added-to-case", actor, case_id, report_id
            ),
        )
        return _seal_record(self._dl, activity)

    def record_participant_status_added(
        self,
        status: ParticipantStatus,
        participant: CaseParticipant,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Build and seal ``Add(ParticipantStatus, target=participant)``."""
        activity = add_status_to_participant_activity(
            status=status,
            target=participant,
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "participant-status-added", actor, status.id_
            ),
        )
        return _seal_record(self._dl, activity)

    def record_case_status_added(
        self,
        status: CaseStatus,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Build and seal ``Add(CaseStatus, target=case)``."""
        activity = add_status_to_case_activity(
            status=status,
            target=case_id,
            actor=actor,
            context=case_id,
            id_=derived_activity_id("case-status-added", actor, status.id_),
        )
        return _seal_record(self._dl, activity)

    def record_case_participant_created(
        self,
        participant: CaseParticipant,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Build and seal ``Create(CaseParticipant)``."""
        activity = create_participant_activity(
            participant=participant,
            target=case_id,
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "case-participant-created", actor, participant.id_
            ),
        )
        return _seal_record(self._dl, activity)

    def record_case_participant_updated(
        self,
        participant: CaseParticipant,
        case_id: str,
        actor: str,
        cause_id: str,
    ) -> tuple[str, str]:
        """Build and seal ``Update(CaseParticipant)``, the record in full."""
        activity = update_participant_activity(
            participant=participant,
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "case-participant-updated", actor, cause_id, participant.id_
            ),
        )
        return _seal_record(self._dl, activity)

    def record_case_owner_updated(
        self,
        case: VulnerabilityCase,
        actor: str,
        cause_id: str,
    ) -> tuple[str, str]:
        """Build and seal ``Update(VulnerabilityCase)`` naming the new owner."""
        # The case as it will be stored, its participants by id: each changed
        # record is carried in full by its own ``update_case_participant``
        # entry (ADR-0124), as for the genesis ``Create``.  The caller passes
        # the changed case because the entry commits before the change is
        # saved (CLP-07-013).
        activity = update_case_activity(
            case=case,
            actor=actor,
            context=case.id_,
            id_=derived_activity_id(
                "case-owner-updated", actor, cause_id, case.id_
            ),
        )
        return _seal_record(self._dl, activity)

    def record_embargo_consent_created(
        self,
        row: EmbargoConsent,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Build and seal ``Create(EmbargoConsent)``, the new row in full."""
        activity = create_embargo_consent_activity(
            row=row,
            actor=actor,
            context=case_id,
            id_=derived_activity_id("embargo-consent-created", actor, row.id_),
        )
        return _seal_record(self._dl, activity)

    def record_embargo_consent_updated(
        self,
        row: EmbargoConsent,
        case_id: str,
        actor: str,
        cause_id: str,
    ) -> tuple[str, str]:
        """Build and seal ``Update(EmbargoConsent)``, the changed row in full."""
        activity = update_embargo_consent_activity(
            row=row,
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "embargo-consent-updated", actor, cause_id, row.id_
            ),
        )
        return _seal_record(self._dl, activity)

    def record_case_announced(
        self,
        case_id: str,
        actor: str,
        object_id: str,
    ) -> tuple[str, str]:
        """Build and seal the demo sync verb's ``Announce(VulnerabilityCase)``."""
        activity = announce_vulnerability_case_activity(
            case=_case_for_wire(self._dl, case_id),
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "demo-sync-log-entry", actor, case_id, object_id
            ),
        )
        return _seal_record(self._dl, activity)


__all__ = ["_LedgerRecordsMixin"]
