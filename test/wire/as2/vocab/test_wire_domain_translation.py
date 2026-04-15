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

from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.case_status import VultronCaseStatus
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.objects.case_actor import CaseActor
from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


def test_vulnerability_report_round_trips_between_core_and_wire():
    core = VultronReport(
        id_="https://example.org/reports/1",
        attributed_to="https://example.org/actors/finder",
        context="https://example.org/cases/1",
        name="VU-1",
        content="report body",
    )

    wire = VulnerabilityReport.from_core(core)

    assert isinstance(wire, VulnerabilityReport)
    assert wire.id_ == core.id_
    assert wire.to_core() == core


def test_case_status_round_trips_between_core_and_wire():
    core = VultronCaseStatus(
        id_="https://example.org/cases/1/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        em_state=EM.PROPOSED,
    )

    wire = CaseStatus.from_core(core)

    assert isinstance(wire, CaseStatus)
    assert wire.em_state == EM.PROPOSED
    round_tripped = wire.to_core()
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context
    assert round_tripped.em_state == core.em_state
    assert round_tripped.pxa_state == core.pxa_state


def test_participant_status_from_core_materializes_case_status_reference():
    core = VultronParticipantStatus(
        id_="https://example.org/cases/1/participants/1/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        rm_state=RM.ACCEPTED,
        case_status="https://example.org/cases/1/status/1",
    )

    wire = ParticipantStatus.from_core(core)

    assert isinstance(wire.case_status, CaseStatus)
    assert wire.case_status.id_ == "https://example.org/cases/1/status/1"
    round_tripped = wire.to_core()
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context
    assert round_tripped.rm_state == core.rm_state
    assert round_tripped.vfd_state == core.vfd_state
    assert round_tripped.case_status == core.case_status


def test_case_participant_round_trips_between_core_and_wire():
    core = VultronParticipant(
        id_="https://example.org/cases/1/participants/vendor",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        case_roles=[],
        participant_statuses=[
            VultronParticipantStatus(
                id_="https://example.org/cases/1/participants/vendor/status/1",
                attributed_to="https://example.org/actors/vendor",
                context="https://example.org/cases/1",
                rm_state=RM.ACCEPTED,
            )
        ],
        accepted_embargo_ids=["https://example.org/embargoes/1"],
        participant_case_name="Vendor Case Name",
    )

    wire = CaseParticipant.from_core(core)

    assert isinstance(wire, CaseParticipant)
    assert wire.id_ == core.id_
    round_tripped = wire.to_core()
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context
    assert round_tripped.accepted_embargo_ids == core.accepted_embargo_ids
    assert round_tripped.participant_statuses[0].rm_state == RM.ACCEPTED


def test_vulnerability_case_round_trips_between_core_and_wire():
    case_status = VultronCaseStatus(
        id_="https://example.org/cases/1/status/1",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
        em_state=EM.PROPOSED,
    )
    participant = VultronParticipant(
        id_="https://example.org/cases/1/participants/vendor",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
    )
    core = VultronCase(
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

    wire = VulnerabilityCase.from_core(core)

    assert isinstance(wire, VulnerabilityCase)
    assert wire.id_ == core.id_
    round_tripped = wire.to_core()
    assert round_tripped.id_ == core.id_
    assert round_tripped.vulnerability_reports == core.vulnerability_reports
    assert round_tripped.notes == core.notes
    assert round_tripped.active_embargo == core.active_embargo
    assert round_tripped.proposed_embargoes == core.proposed_embargoes
    assert round_tripped.case_activity == core.case_activity
    assert round_tripped.parent_cases == core.parent_cases
    assert round_tripped.child_cases == core.child_cases
    assert round_tripped.sibling_cases == core.sibling_cases
    assert isinstance(round_tripped.case_statuses[0], VultronCaseStatus)
    assert round_tripped.case_statuses[0].id_ == case_status.id_


def test_case_log_entry_to_core_returns_domain_model():
    wire = CaseLogEntry(
        case_id="https://example.org/cases/1",
        log_index=1,
        log_object_id="https://example.org/activities/1",
        event_type="case_created",
        payload_snapshot={"id": "https://example.org/activities/1"},
    )

    core = wire.to_core()

    assert isinstance(core, VultronCaseLogEntry)
    assert core.case_id == wire.case_id
    assert core.entry_hash == wire.entry_hash


def test_case_actor_round_trips_between_core_and_wire():
    core = VultronCaseActor(
        id_="https://example.org/actors/case-actor",
        name="Case Actor",
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/1",
    )

    wire = CaseActor.from_core(core)

    assert isinstance(wire, CaseActor)
    assert wire.id_ == core.id_
    round_tripped = wire.to_core()
    assert round_tripped.id_ == core.id_
    assert round_tripped.attributed_to == core.attributed_to
    assert round_tripped.context == core.context


# ============================================================================
# WIRE-TRANS-04: VultronAS2Activity.from_core()
# ============================================================================


def test_vultron_as2_activity_from_core_with_string_fields():
    """VultronAS2Activity.from_core() round-trips a simple activity."""
    from vultron.core.models.activity import VultronActivity
    from vultron.wire.as2.vocab.activities.base import VultronAS2Activity

    core = VultronActivity(
        id_="https://example.org/activities/1",
        type_="Offer",
        actor="https://example.org/actors/alice",
        object_="https://example.org/reports/1",
    )

    wire = VultronAS2Activity.from_core(core)

    assert isinstance(wire, VultronAS2Activity)
    assert wire.id_ == core.id_
    assert wire.actor == core.actor
    assert wire.object_ == core.object_


def test_vultron_as2_activity_from_core_with_no_object():
    """from_core() handles an activity whose object_ is None."""
    from vultron.core.models.activity import VultronActivity
    from vultron.wire.as2.vocab.activities.base import VultronAS2Activity

    core = VultronActivity(
        id_="https://example.org/activities/2",
        type_="Read",
        actor="https://example.org/actors/bob",
    )

    wire = VultronAS2Activity.from_core(core)

    assert isinstance(wire, VultronAS2Activity)
    assert wire.id_ == core.id_
    assert wire.actor == core.actor
    assert wire.object_ is None


def test_vultron_as2_activity_subclass_field_map_renames():
    """A subclass _field_map renames domain fields before validation."""
    from typing import ClassVar

    from vultron.core.models.activity import VultronActivity
    from vultron.wire.as2.vocab.activities.base import VultronAS2Activity

    class _AliasMappedActivity(VultronAS2Activity):
        _field_map: ClassVar[dict[str, str]] = {"origin": "target"}

    core = VultronActivity(
        id_="https://example.org/activities/3",
        type_="Move",
        actor="https://example.org/actors/alice",
        origin="https://example.org/cases/old",
    )

    wire = _AliasMappedActivity.from_core(core)

    assert isinstance(wire, _AliasMappedActivity)
    assert wire.target == "https://example.org/cases/old"


def test_vultron_as2_activity_from_core_accept_subtype():
    """from_core() works for a VultronAccept domain sub-type."""
    from vultron.core.models.activity import VultronAccept
    from vultron.wire.as2.vocab.activities.base import VultronAS2Activity

    core = VultronAccept(
        id_="https://example.org/activities/4",
        actor="https://example.org/actors/vendor",
        object_="https://example.org/activities/offer-1",
    )

    wire = VultronAS2Activity.from_core(core)

    assert isinstance(wire, VultronAS2Activity)
    assert wire.id_ == core.id_
    assert wire.actor == core.actor
    assert wire.object_ == core.object_
