#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Tests for bootstrap helpers and protocol-error enforcement.

Covers:
  CBT-05-007  Bootstrap Create stores the reporter participant at RM.ACCEPTED
              when a fully inline participant object is provided (CBT-01-008).
  CBT-05-008  Bootstrap Create is refused with a protocol-error reason when
              a participant arrives as a bare URI string (#2736, #2808).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_participant import (
    CaseParticipant,
    CaseParticipant as CoreCaseParticipant,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import create_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# CBT-05-007: Reporter participant stored at RM.ACCEPTED when inline (#589)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CBT-05-007")
def test_reporter_participant_stored_at_accepted_when_inline(make_payload):
    """Reporter participant at RM.ACCEPTED in inline payload is preserved (#589).

    CBT-01-008 requires the sender to include the reporter's participant inline
    at RM.ACCEPTED.  CBT-05-008 requires the receiver to reject bare-string
    participants.  This test confirms that when the sender complies (fully
    inline participant at RM.ACCEPTED), the receiver stores it correctly via
    store_embedded_participants so subsequent Add(ParticipantStatus) calls can
    read it at RM.ACCEPTED.
    """
    from vultron.core.models.participant_status import ParticipantStatus as PS

    _VENDOR_ID = "https://vendor.example.org/actors/vendor-cbt05007"
    _FINDER_ID = "https://finder.example.org/actors/finder-cbt05007"
    _CASE_ID = "https://example.org/cases/case-cbt05007"
    _REPORT_ID = "https://example.org/reports/report-cbt05007"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-cbt05007"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-cbt05007"

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_FINDER_ID)
    report = VulnerabilityReport(id_=_REPORT_ID, attributed_to=_FINDER_ID)
    dl.create(report)
    link = VultronReportCaseLink(
        report_id=_REPORT_ID,
        case_creator_id=_VENDOR_ID,
    )
    dl.save(link)
    vendor_participant = CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ID,
        context=_CASE_ID,
    )
    finder_participant = CaseParticipant(
        id_=_FINDER_PARTICIPANT_ID,
        attributed_to=_FINDER_ID,
        context=_CASE_ID,
        participant_statuses=[
            PS(
                context=_CASE_ID,
                attributed_to=_FINDER_ID,
                rm_state=RM.ACCEPTED,  # type: ignore[call-arg]
            )
        ],
    )
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="CBT-05-007 inline participant test",
        case_participants=[vendor_participant, finder_participant],
    )
    case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
    case.actor_participant_index[_FINDER_ID] = _FINDER_PARTICIPANT_ID
    activity = create_case_activity(case, actor=_VENDOR_ID)
    event = make_payload(activity, receiving_actor_id=_FINDER_ID)

    CreateCaseReceivedUseCase(dl, event).execute()

    stored = dl.read(_FINDER_PARTICIPANT_ID)
    assert stored is not None, (
        "Reporter participant must exist after bootstrap"
    )
    statuses = getattr(stored, "participant_statuses", [])
    assert statuses, "Reporter participant must have at least one status"
    assert statuses[-1].rm.state == RM.ACCEPTED, (
        f"Reporter participant must be at RM.ACCEPTED after bootstrap;"
        f" got {statuses[-1].rm.state!r}"
    )


# ---------------------------------------------------------------------------
# CBT-05-008: Bare-URI participant MUST raise a protocol error, not silently
# fall back to domain-knowledge inference.  Tracked by #2736.
# ---------------------------------------------------------------------------


@pytest.mark.spec("CBT-05-008")
def test_bootstrap_bare_uri_participant_is_refused(make_payload):
    """Bootstrap with a bare-URI participant is refused (CBT-05-008)."""
    _VENDOR_ID = "https://vendor.example.org/actors/vendor-cbt05008"
    _FINDER_ID = "https://finder.example.org/actors/finder-cbt05008"
    _CASE_ID = "https://example.org/cases/case-cbt05008"
    _REPORT_ID = "https://example.org/reports/report-cbt05008"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-cbt05008"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-cbt05008"

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_FINDER_ID)
    report = VulnerabilityReport(id_=_REPORT_ID, attributed_to=_FINDER_ID)
    dl.create(report)
    link = VultronReportCaseLink(
        report_id=_REPORT_ID,
        case_creator_id=_VENDOR_ID,
    )
    dl.save(link)
    case_actor_participant = CoreCaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ID,
        context=_CASE_ID,
    )
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="CBT-05-008 bare URI test",
        case_participants=[
            case_actor_participant,
            _FINDER_PARTICIPANT_ID,  # bare string — protocol violation
        ],
    )
    case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
    case.actor_participant_index[_FINDER_ID] = _FINDER_PARTICIPANT_ID
    activity = create_case_activity(case, actor=_VENDOR_ID)
    event = make_payload(activity, receiving_actor_id=_FINDER_ID)
    result = CreateCaseReceivedUseCase(dl, event).execute()

    # Rejected before any write, as a refusal the inbox reports (#2255).
    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason is not None and "CBT-05-008" in result.reason
    assert dl.read(_CASE_ID) is None
