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

"""Tests for the core VulnerabilityCase domain model (step 6 of issue #699)."""

import pytest

from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase, VultronCase
from vultron.core.models.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.errors import VultronValidationError

_ACTOR = "https://example.org/actor"
_CASE_ID = "urn:uuid:case-test"


@pytest.fixture
def case() -> VulnerabilityCase:
    return VulnerabilityCase(
        id_=_CASE_ID,
        attributed_to=_ACTOR,
    )


class TestVulnerabilityCaseBasics:
    """VulnerabilityCase is a CoreObject with the canonical type."""

    def test_inherits_core_object(self):
        assert issubclass(VulnerabilityCase, CoreObject)

    def test_type_literal(self, case: VulnerabilityCase):
        assert case.type_ == "VulnerabilityCase"

    def test_id_preserved(self, case: VulnerabilityCase):
        assert case.id_ == _CASE_ID

    def test_id_auto_generated_when_not_given(self):
        c = VulnerabilityCase()
        assert c.id_.startswith("urn:uuid:")

    def test_attributed_to_stored(self, case: VulnerabilityCase):
        assert case.attributed_to == _ACTOR

    def test_default_fields_empty(self, case: VulnerabilityCase):
        assert case.case_participants == []
        assert case.vulnerability_reports == []
        assert case.notes == []
        assert case.case_activity == []
        assert case.parent_cases == []
        assert case.child_cases == []
        assert case.sibling_cases == []


class TestVulnerabilityCaseInitialStatus:
    """An initial CaseStatus is seeded when attributed_to is set."""

    def test_case_statuses_seeded_with_attributed_to(
        self, case: VulnerabilityCase
    ):
        assert len(case.case_statuses) == 1
        assert isinstance(case.case_statuses[0], CaseStatus)

    def test_initial_status_context_is_case_id(self, case: VulnerabilityCase):
        status = case.case_statuses[0]
        assert isinstance(status, CaseStatus)
        assert status.context == _CASE_ID

    def test_initial_status_attributed_to_is_actor(
        self, case: VulnerabilityCase
    ):
        status = case.case_statuses[0]
        assert isinstance(status, CaseStatus)
        assert status.attributed_to == _ACTOR

    def test_no_seeding_without_attributed_to(self):
        c = VulnerabilityCase(id_=_CASE_ID)
        assert c.case_statuses == []


class TestVulnerabilityCaseRegistration:
    """VulnerabilityCase auto-registers in CORE_VOCABULARY — ADR-0017."""

    def test_registered_in_core_vocabulary(self):
        assert "VulnerabilityCase" in CORE_VOCABULARY
        assert CORE_VOCABULARY["VulnerabilityCase"] is VulnerabilityCase


class TestVulnerabilityCaseBackwardCompatAlias:
    """VultronCase must be an alias for VulnerabilityCase."""

    def test_alias_is_same_class(self):
        assert VultronCase is VulnerabilityCase

    def test_alias_construction_works(self):
        c = VultronCase(attributed_to=_ACTOR)
        assert isinstance(c, VulnerabilityCase)
        assert c.type_ == "VulnerabilityCase"


class TestVulnerabilityCaseCurrentStatus:
    """current_status returns the most recent materialized CaseStatus."""

    def test_current_status_returns_case_status(self, case: VulnerabilityCase):
        assert isinstance(case.current_status, CaseStatus)

    def test_case_status_property_alias(self, case: VulnerabilityCase):
        assert case.case_status is case.current_status

    def test_current_status_raises_when_no_materialized(self):
        c = VulnerabilityCase(id_=_CASE_ID)
        c.case_statuses = ["urn:uuid:some-id"]  # only str refs
        with pytest.raises(ValueError, match="no materialized CaseStatus"):
            _ = c.current_status

    def test_current_status_raises_when_empty(self):
        c = VulnerabilityCase(id_=_CASE_ID)
        with pytest.raises(ValueError):
            _ = c.current_status


class TestVulnerabilityCaseAddReport:
    """add_report appends a report ID to vulnerability_reports."""

    def test_add_report_appends_id(self, case: VulnerabilityCase):
        report_id = "urn:uuid:report-1"
        case.add_report(report_id)
        assert report_id in case.vulnerability_reports

    def test_add_multiple_reports(self, case: VulnerabilityCase):
        case.add_report("urn:uuid:report-1")
        case.add_report("urn:uuid:report-2")
        assert len(case.vulnerability_reports) == 2


class TestVulnerabilityCaseAddParticipant:
    """add_participant updates case_participants and actor_participant_index."""

    def test_add_participant_appends(self, case: VulnerabilityCase):
        p = FinderParticipant(
            id_="urn:uuid:part-1",
            attributed_to="https://example.org/finder",
        )
        case.add_participant(p)
        assert p.id_ in case.case_participants

    def test_add_participant_updates_index(self, case: VulnerabilityCase):
        p = FinderParticipant(
            id_="urn:uuid:part-1",
            attributed_to="https://example.org/finder",
        )
        case.add_participant(p)
        assert (
            case.actor_participant_index.get("https://example.org/finder")
            == "urn:uuid:part-1"
        )

    def test_add_participant_without_attributed_to_no_index(
        self, case: VulnerabilityCase
    ):
        p = FinderParticipant(id_="urn:uuid:part-2")
        case.add_participant(p)
        assert "urn:uuid:part-2" not in case.actor_participant_index

    def test_add_participant_raises_on_actor_index_divergence(
        self, case: VulnerabilityCase
    ):
        actor_id = "https://example.org/finder"
        case.actor_participant_index[actor_id] = "urn:uuid:part-existing"
        participant = FinderParticipant(
            id_="urn:uuid:part-new",
            attributed_to=actor_id,
        )
        with pytest.raises(VultronValidationError, match="divergence"):
            case.add_participant(participant)


class TestVulnerabilityCaseRemoveParticipant:
    """remove_participant removes from list and index."""

    def test_remove_participant_clears_from_list(
        self, case: VulnerabilityCase
    ):
        p = VendorParticipant(
            id_="urn:uuid:part-1",
            attributed_to="https://example.org/vendor",
        )
        case.add_participant(p)
        case.remove_participant("urn:uuid:part-1")
        assert p.id_ not in case.case_participants

    def test_remove_participant_clears_from_index(
        self, case: VulnerabilityCase
    ):
        p = VendorParticipant(
            id_="urn:uuid:part-1",
            attributed_to="https://example.org/vendor",
        )
        case.add_participant(p)
        case.remove_participant("urn:uuid:part-1")
        assert "https://example.org/vendor" not in case.actor_participant_index

    def test_remove_nonexistent_participant_is_noop(
        self, case: VulnerabilityCase
    ):
        case.remove_participant("urn:uuid:no-such")
        assert case.case_participants == []


class TestVulnerabilityCaseSetEmbargo:
    """set_embargo updates active_embargo field."""

    def test_set_embargo_stores_id(self, case: VulnerabilityCase):
        case.set_embargo("urn:uuid:embargo-1")
        assert case.active_embargo == "urn:uuid:embargo-1"

    def test_set_embargo_clears_with_none(self, case: VulnerabilityCase):
        case.set_embargo("urn:uuid:embargo-1")
        case.set_embargo(None)
        assert case.active_embargo is None


class TestVulnerabilityCaseRecordActivity:
    """record_activity appends activity IDs idempotently."""

    def test_record_activity_appends(self, case: VulnerabilityCase):
        case.record_activity("urn:uuid:activity-1")
        assert "urn:uuid:activity-1" in case.case_activity

    def test_record_activity_is_idempotent(self, case: VulnerabilityCase):
        case.record_activity("urn:uuid:activity-1")
        case.record_activity("urn:uuid:activity-1")
        assert case.case_activity.count("urn:uuid:activity-1") == 1

    def test_record_multiple_activities(self, case: VulnerabilityCase):
        case.record_activity("urn:uuid:activity-1")
        case.record_activity("urn:uuid:activity-2")
        assert len(case.case_activity) == 2


class TestVulnerabilityCaseWireRoundTrip:
    """Wire VulnerabilityCase.to_core preserves domain data."""

    def test_to_core_produces_vulnerability_case(self):
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase as WireVC,
        )

        wire_case = WireVC(
            id_="urn:uuid:vc-roundtrip",
            attributed_to="https://example.org/actor",
        )
        core_case = wire_case.to_core()
        assert isinstance(core_case, VulnerabilityCase)
        assert core_case.id_ == "urn:uuid:vc-roundtrip"

    def test_from_core_preserves_id(self):
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase as WireVC,
        )

        core_case = VulnerabilityCase(
            id_="urn:uuid:vc-fromcore",
            attributed_to="https://example.org/actor",
        )
        wire_case = WireVC.from_core(core_case)
        assert wire_case.id_ == "urn:uuid:vc-fromcore"

    def test_round_trip_preserves_active_embargo(self):
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase as WireVC,
        )

        core_case = VulnerabilityCase(
            id_="urn:uuid:vc-rt",
            attributed_to="https://example.org/actor",
        )
        core_case.set_embargo("urn:uuid:embargo-1")
        wire_case = WireVC.from_core(core_case)
        restored = wire_case.to_core()
        assert restored.active_embargo == "urn:uuid:embargo-1"
