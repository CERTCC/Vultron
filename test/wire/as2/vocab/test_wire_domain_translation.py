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
#  Carnegie Mellon(R), CERT(R) and CERT Coordination Center(R) are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Wire/core translation tests for WIRE-TRANS-03 and WIRE-TRANS-04."""

import pytest
from pydantic import ValidationError

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_status import CaseStatus as CoreCaseStatus
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import (
    ParticipantStatus as CoreParticipantStatus,
)
from vultron.core.models.report import VultronReport
from vultron.core.models.dimensions import (
    EmDimension,
    PecDimension,
    RmDimension,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.objects.case_actor import as_CaseActor
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


def test_vulnerability_report_round_trips_between_core_and_wire():
    """ADR-0099 detail 3: as_VulnerabilityReport is VulnerabilityReport (identity)."""
    assert as_VulnerabilityReport is VultronReport

    core = VultronReport(
        id_="https://example.org/reports/1",
        attributed_to="https://example.org/actors/finder",
        context="https://example.org/cases/1",
        name="VU-1",
        content="report body",
    )

    assert isinstance(core, as_VulnerabilityReport)
    data = core.model_dump(by_alias=True, exclude_none=True, mode="json")
    # The wire shape uses the AS2 spellings, not the Python field names.
    assert data["attributedTo"] == core.attributed_to
    assert "attributed_to" not in data and "id_" not in data
    restored = as_VulnerabilityReport.model_validate(data)
    assert restored.id_ == core.id_


def test_case_status_round_trips_between_core_and_wire():
    core = CoreCaseStatus(
        id_="https://example.org/cases/1/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        em=EmDimension(state=EM.PROPOSED),
    )

    wire = as_CaseStatus.model_validate(
        core.model_dump(by_alias=True, mode="json")
    )

    assert isinstance(wire, as_CaseStatus)
    assert wire.em_state == EM.PROPOSED
    round_tripped = wire
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context
    assert round_tripped.em.state == core.em.state
    assert round_tripped.pxa.state == core.pxa.state


def test_participant_status_from_core_materializes_case_status_reference():
    core_case_status = CoreCaseStatus(
        id_="https://example.org/cases/1/status/1",
        context="https://example.org/cases/1",
        attributed_to="https://example.org/actors/vendor",
        em=EmDimension(state=EM.NONE),
    )
    core = CoreParticipantStatus(
        id_="https://example.org/cases/1/participants/1/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        rm=RmDimension(state=RM.ACCEPTED),
        case_status=core_case_status,
    )

    wire = as_ParticipantStatus.model_validate(
        core.model_dump(by_alias=True, mode="json")
    )

    assert isinstance(wire.case_status, as_CaseStatus)
    assert wire.case_status.id_ == "https://example.org/cases/1/status/1"
    round_tripped = wire
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context
    assert round_tripped.rm.state == core.rm.state
    assert round_tripped.vf == core.vf
    assert isinstance(round_tripped.case_status, CoreCaseStatus)
    assert round_tripped.case_status.id_ == core_case_status.id_
    assert round_tripped.case_status.em.state == core_case_status.em.state


def test_participant_status_embargo_adherence_survives_wire_round_trip():
    """embargo_adherence is correctly projected through from_core() and round-tripped via to_core() (ADR-0056)."""
    core_signatory = CoreParticipantStatus(
        id_="https://example.org/cases/1/participants/vendor/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        consent=PecDimension(state=PEC.SIGNATORY),
    )
    wire = as_ParticipantStatus.model_validate(
        core_signatory.model_dump(by_alias=True, mode="json")
    )
    assert wire.embargo_adherence is True

    round_tripped = wire
    assert round_tripped.embargo_adherence is True

    core_no_consent = CoreParticipantStatus(
        id_="https://example.org/cases/1/participants/vendor/status/2",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        consent=None,
    )
    wire_no_consent = as_ParticipantStatus.model_validate(
        core_no_consent.model_dump(by_alias=True, mode="json")
    )
    assert wire_no_consent.embargo_adherence is False
    assert wire_no_consent.embargo_adherence is False


def test_case_participant_round_trips_between_core_and_wire():
    core = VultronParticipant(
        id_="https://example.org/cases/1/participants/vendor",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        case_roles=[],
        participant_statuses=[
            CoreParticipantStatus(
                id_="https://example.org/cases/1/participants/vendor/status/1",
                attributed_to="https://example.org/actors/vendor",
                context="https://example.org/cases/1",
                rm=RmDimension(state=RM.ACCEPTED),
            )
        ],
        accepted_embargo_ids=["https://example.org/embargoes/1"],
        participant_case_name="Vendor Case Name",
    )

    wire = as_CaseParticipant.model_validate(
        core.model_dump(by_alias=True, mode="json")
    )

    assert isinstance(wire, as_CaseParticipant)
    assert wire.id_ == core.id_
    round_tripped = wire
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context
    assert round_tripped.accepted_embargo_ids == core.accepted_embargo_ids
    assert round_tripped.participant_statuses[0].rm.state == RM.ACCEPTED


def test_vulnerability_case_round_trips_between_core_and_wire():
    """ADR-0099 detail 3: as_VulnerabilityCase is VulnerabilityCase (identity)."""
    assert as_VulnerabilityCase is VulnerabilityCase

    case_status = CoreCaseStatus(
        id_="https://example.org/cases/1/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        em=EmDimension(state=EM.PROPOSED),
    )
    participant = VultronParticipant(
        id_="https://example.org/cases/1/participants/vendor",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
    )
    core = VulnerabilityCase(
        id_="https://example.org/cases/1",
        attributed_to="https://example.org/actors/vendor",
        case_participants=[participant],
        actor_participant_index={
            "https://example.org/actors/vendor": participant.id_
        },
        vulnerability_reports=["https://example.org/reports/1"],
        case_statuses=[case_status],
        notes=["https://example.org/notes/1"],
        active_embargo="https://example.org/embargoes/1",
        proposed_embargoes=["https://example.org/embargoes/1"],
        case_activity=["https://example.org/activities/1"],
        parent_cases=["https://example.org/cases/parent"],
        child_cases=["https://example.org/cases/child"],
        sibling_cases=["https://example.org/cases/sibling"],
    )

    assert isinstance(core, as_VulnerabilityCase)
    data = core.model_dump(by_alias=True, exclude_none=True, mode="json")
    for key in (
        "caseParticipants",
        "vulnerabilityReports",
        "caseStatuses",
        "activeEmbargo",
        "proposedEmbargoes",
        "caseActivity",
        "parentCases",
        "childCases",
        "siblingCases",
    ):
        assert key in data, f"wire dump is missing AS2 key {key!r}"
    assert "case_statuses" not in data and "active_embargo" not in data
    restored = as_VulnerabilityCase.model_validate(data)
    assert restored.id_ == core.id_
    assert restored.vulnerability_reports == core.vulnerability_reports
    assert restored.notes == core.notes
    assert restored.active_embargo == core.active_embargo
    assert restored.proposed_embargoes == core.proposed_embargoes
    assert restored.case_activity == core.case_activity
    assert restored.parent_cases == core.parent_cases
    assert restored.child_cases == core.child_cases
    assert restored.sibling_cases == core.sibling_cases
    assert isinstance(restored.case_statuses[0], CoreCaseStatus)
    assert restored.case_statuses[0].id_ == case_status.id_


def test_case_ledger_entry_to_core_returns_domain_model():
    """ADR-0099 detail 3: as_CaseLedgerEntry is CaseLedgerEntry (identity)."""
    assert as_CaseLedgerEntry is CaseLedgerEntry

    entry = as_CaseLedgerEntry(
        case_id="https://example.org/cases/1",
        log_index=1,
        log_object_id="https://example.org/activities/1",
        event_type="case_created",
        payload_snapshot={"id": "https://example.org/activities/1"},
    )

    assert isinstance(entry, CaseLedgerEntry)
    assert entry.case_id == "https://example.org/cases/1"
    assert entry.entry_hash is not None


def test_case_actor_round_trips_between_core_and_wire():
    """ADR-0099 detail 3: as_CaseActor is CaseActor (identity)."""
    assert as_CaseActor is VultronCaseActor

    core = VultronCaseActor(
        id_="https://example.org/actors/case-actor",
        name="Case Actor",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
    )

    assert isinstance(core, as_CaseActor)
    data = core.model_dump(by_alias=True, exclude_none=True, mode="json")
    restored = as_CaseActor.model_validate(data)
    assert restored.id_ == core.id_
    assert restored.attributed_to == core.attributed_to
    assert restored.context == core.context


# ============================================================================
# WIRE-TRANS-04: as_VultronActivity.from_core()
# ============================================================================


def test_vultron_as2_activity_from_core_with_string_fields():
    """as_VultronActivity.from_core() round-trips a simple activity."""
    from vultron.core.models.activity import VultronActivity
    from vultron.wire.as2.vocab.activities.base import as_VultronActivity

    core = VultronActivity(
        id_="https://example.org/activities/1",
        type_="Offer",
        actor="https://example.org/actors/alice",
        object_="https://example.org/reports/1",
    )

    wire = as_VultronActivity.model_validate(
        core.model_dump(by_alias=True, mode="json")
    )

    assert isinstance(wire, as_VultronActivity)
    assert wire.id_ == core.id_
    assert wire.actor == core.actor
    assert wire.object_ == core.object_


def test_vultron_as2_activity_from_core_with_no_object():
    """from_core() rejects objectless transitive activities."""
    from vultron.core.models.activity import VultronActivity
    from vultron.wire.as2.vocab.activities.base import as_VultronActivity

    core = VultronActivity(
        id_="https://example.org/activities/2",
        type_="Read",
        actor="https://example.org/actors/bob",
    )

    with pytest.raises(ValidationError):
        as_VultronActivity.from_core(core)


def test_vultron_as2_activity_subclass_field_map_renames():
    """A subclass _field_map renames domain fields before validation."""
    from typing import ClassVar

    from vultron.core.models.activity import VultronActivity
    from vultron.wire.as2.vocab.activities.base import as_VultronActivity

    class _AliasMappedActivity(as_VultronActivity):
        _field_map: ClassVar[dict[str, str]] = {"origin": "target"}

    core = VultronActivity(
        id_="https://example.org/activities/3",
        type_="Move",
        actor="https://example.org/actors/alice",
        object_="https://example.org/reports/1",
        origin="https://example.org/cases/old",
    )

    wire = _AliasMappedActivity.from_core(core)

    assert isinstance(wire, _AliasMappedActivity)
    assert wire.target == "https://example.org/cases/old"


def test_vultron_as2_activity_from_core_accept_subtype():
    """from_core() works for a VultronAccept domain sub-type."""
    from vultron.core.models.activity import VultronAccept
    from vultron.wire.as2.vocab.activities.base import as_VultronActivity

    core = VultronAccept(
        id_="https://example.org/activities/4",
        actor="https://example.org/actors/vendor",
        object_="https://example.org/activities/offer-1",
    )

    wire = as_VultronActivity.model_validate(
        core.model_dump(by_alias=True, mode="json")
    )

    assert isinstance(wire, as_VultronActivity)
    assert wire.id_ == core.id_
    assert wire.actor == core.actor
    assert wire.object_ == core.object_
