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
``_base._seal_record``).  Each id is derived from the CASE_MANAGER and what
changed, so a re-run builds nothing new and hands back the body the first run
sealed (ID-04-004), which is what lets the commit boundary recognise the retry
as the entry it already holds.

Each object is carried as the CASE_MANAGER holds it: the participant or status
the caller has just written, or the case as stored.  A replica stores what the
entry carries (ADR-0124).  The demo verb's ``Announce`` is the exception: an
announced case carries its participants and reports inline (AKM-02-004).
"""

import logging

from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import (
    add_report_to_case_activity,
    add_status_to_case_activity,
    add_status_to_participant_activity,
    create_case_activity,
    create_participant_activity,
)
from vultron.wire.as2.factories.case import (
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._base import _case_for_wire, _seal_record, _to_wire

logger = logging.getLogger(__name__)


def _stored_case(dl: CaseOutboxPersistence, case_id: str) -> VulnerabilityCase:
    """The case as *dl* holds it; raises when it holds none."""
    case = dl.read_case(case_id)
    if case is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    return case


class _LedgerRecordsMixin:
    """CASE_MANAGER-authored activities recorded in the case ledger."""

    _dl: CaseOutboxPersistence

    def record_case_created(
        self,
        case_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Build and seal the genesis ``Create(VulnerabilityCase)``."""
        # The case as stored, its participants and reports by id: each of
        # them is carried in full by an entry of its own (``create_case_participant``,
        # ``add_report_to_case``), so a replica copying this entry stores the
        # case exactly as the CASE_MANAGER holds it (ADR-0124).
        activity = create_case_activity(
            case=_stored_case(self._dl, case_id),
            actor=actor,
            context=case_id,
            id_=derived_activity_id("case-created", actor, case_id),
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

    def record_case_announced(
        self,
        case_id: str,
        actor: str,
        event_type: str,
        object_id: str,
    ) -> tuple[str, str]:
        """Build and seal the demo sync verb's ``Announce(VulnerabilityCase)``."""
        activity = announce_vulnerability_case_activity(
            case=_case_for_wire(self._dl, case_id),
            actor=actor,
            context=case_id,
            id_=derived_activity_id(
                "demo-sync-log-entry", actor, case_id, event_type, object_id
            ),
        )
        return _seal_record(self._dl, activity)


__all__ = ["_LedgerRecordsMixin"]
