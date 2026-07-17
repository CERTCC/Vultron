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

"""Tests for the lifecycle-staged VulnerabilityCase types.

Covers AC-1 through AC-6 from issue #1452 and spec requirements
LST-02-001 through LST-05-003.
"""

import pytest

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    CaseParticipant,
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.core.models.staged_case import Case, EmbargoedCase, IncomingReport
from vultron.core.states.em import EM
from vultron.errors import VultronValidationError

_ACTOR = "https://example.org/actor"
_REPORT_ID = "urn:uuid:report-1"
_EMBARGO_ID = "urn:uuid:embargo-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_case_participants() -> list[str | CaseParticipant]:
    """Return two participant IDs representing reporter + receiver."""
    reporter = ReporterParticipant(
        id_="urn:uuid:participant-reporter",
        attributed_to="https://example.org/reporter",
    )
    receiver = VendorParticipant(
        id_="urn:uuid:participant-receiver",
        attributed_to="https://example.org/receiver",
    )
    return [reporter.id_, receiver.id_]


def _minimal_case() -> VulnerabilityCase:
    """Minimal VulnerabilityCase that satisfies Case invariants."""
    vc = VulnerabilityCase(attributed_to=_ACTOR)
    vc.vulnerability_reports.append(_REPORT_ID)
    vc.case_participants = _minimal_case_participants()
    # case_statuses is seeded by _init_case_statuses when attributed_to is set
    return vc


def _embargoed_case_data() -> VulnerabilityCase:
    """VulnerabilityCase that satisfies EmbargoedCase invariants."""
    vc = _minimal_case()
    vc.active_embargo = _EMBARGO_ID
    # Seed a status with em_state=ACTIVE
    vc.case_statuses = [
        CaseStatus(
            context=vc.id_,
            attributed_to=_ACTOR,
            em_state=EM.ACTIVE,
        )
    ]
    return vc


# ---------------------------------------------------------------------------
# IncomingReport
# ---------------------------------------------------------------------------


class TestIncomingReport:
    """Tests for IncomingReport staged type (LST-02-001)."""

    def test_is_subclass_of_vulnerability_case(self):
        assert issubclass(IncomingReport, VulnerabilityCase)

    def test_type_literal_unchanged(self):
        """IncomingReport shares type_='VulnerabilityCase' (LST-05-003)."""
        ir = IncomingReport(vulnerability_reports=[_REPORT_ID])
        assert ir.type_ == "VulnerabilityCase"

    def test_not_registered_separately_in_core_vocabulary(self):
        """Staged subtypes must not add extra CORE_VOCABULARY entries."""
        assert "IncomingReport" not in CORE_VOCABULARY

    def test_valid_with_one_report_no_participants(self):
        ir = IncomingReport(vulnerability_reports=[_REPORT_ID])
        assert ir.vulnerability_reports == [_REPORT_ID]
        assert ir.case_participants == []

    def test_raises_when_no_reports(self):
        with pytest.raises(VultronValidationError, match="IncomingReport"):
            IncomingReport()

    def test_raises_when_participants_present(self):
        p = CaseParticipant(id_="urn:uuid:p1")
        with pytest.raises(VultronValidationError, match="participants"):
            IncomingReport(
                vulnerability_reports=[_REPORT_ID],
                case_participants=[p.id_],
            )

    def test_model_validate_from_vulnerability_case(self):
        """model_validate promotes a plain VulnerabilityCase (LST-05-001)."""
        vc = VulnerabilityCase()
        vc.vulnerability_reports.append(_REPORT_ID)
        # No participants yet: satisfies IncomingReport constraint
        ir = IncomingReport.model_validate(vc)
        assert isinstance(ir, IncomingReport)

    def test_model_validate_raises_on_missing_report(self):
        vc = VulnerabilityCase()
        with pytest.raises(VultronValidationError):
            IncomingReport.model_validate(vc)

    def test_model_validate_raises_when_participants_present(self):
        vc = VulnerabilityCase()
        vc.vulnerability_reports.append(_REPORT_ID)
        vc.case_participants = _minimal_case_participants()
        with pytest.raises(VultronValidationError):
            IncomingReport.model_validate(vc)


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------


class TestCase:
    """Tests for Case staged type (LST-02-001, LST-02-002)."""

    def test_is_subclass_of_vulnerability_case(self):
        assert issubclass(Case, VulnerabilityCase)

    def test_type_literal_unchanged(self):
        """Case shares type_='VulnerabilityCase' (LST-05-003)."""
        c = Case.model_validate(_minimal_case())
        assert c.type_ == "VulnerabilityCase"

    def test_not_registered_separately_in_core_vocabulary(self):
        assert "Case" not in CORE_VOCABULARY

    def test_valid_with_minimum_participants(self):
        c = Case.model_validate(_minimal_case())
        assert len(c.case_participants) >= 2
        assert c.vulnerability_reports
        assert c.case_statuses

    def test_raises_when_no_reports(self):
        vc = VulnerabilityCase(attributed_to=_ACTOR)
        vc.case_participants = _minimal_case_participants()
        with pytest.raises(VultronValidationError, match="report"):
            Case.model_validate(vc)

    def test_raises_when_fewer_than_two_participants(self):
        vc = VulnerabilityCase(attributed_to=_ACTOR)
        vc.vulnerability_reports.append(_REPORT_ID)
        one: list[str | CaseParticipant] = ["urn:uuid:p1"]
        vc.case_participants = one
        with pytest.raises(
            VultronValidationError, match="reporter and receiver"
        ):
            Case.model_validate(vc)

    def test_raises_when_no_participants(self):
        vc = VulnerabilityCase(attributed_to=_ACTOR)
        vc.vulnerability_reports.append(_REPORT_ID)
        none: list[str | CaseParticipant] = []
        vc.case_participants = none
        with pytest.raises(VultronValidationError):
            Case.model_validate(vc)

    def test_raises_when_no_case_statuses(self):
        # Construct with no attributed_to so _init_case_statuses does not seed.
        vc = VulnerabilityCase()
        vc.vulnerability_reports.append(_REPORT_ID)
        vc.case_participants = _minimal_case_participants()
        # case_statuses is empty (no attributed_to to trigger auto-seed)
        assert vc.case_statuses == []
        with pytest.raises(
            VultronValidationError, match="materialized CaseStatus"
        ):
            Case.model_validate(vc)

    def test_raises_when_case_statuses_contains_only_string_ids(self):
        """String-only case_statuses must not pass the Case invariant (LST-02-002)."""
        vc = VulnerabilityCase()
        vc.vulnerability_reports.append(_REPORT_ID)
        vc.case_participants = _minimal_case_participants()
        vc.case_statuses = ["urn:uuid:status-string-id"]
        with pytest.raises(
            VultronValidationError, match="materialized CaseStatus"
        ):
            Case.model_validate(vc)

    def test_model_validate_promotes_vulnerability_case(self):
        """model_validate promotes a qualifying VulnerabilityCase (LST-05-001)."""
        vc = _minimal_case()
        c = Case.model_validate(vc)
        assert isinstance(c, Case)

    def test_pre_embargo_case_is_valid_case(self):
        """A Case without an active embargo is still a valid Case."""
        vc = _minimal_case()
        assert vc.active_embargo is None
        c = Case.model_validate(vc)
        assert c.active_embargo is None


# ---------------------------------------------------------------------------
# EmbargoedCase
# ---------------------------------------------------------------------------


class TestEmbargoedCase:
    """Tests for EmbargoedCase staged type (LST-02-001, LST-02-003)."""

    def test_is_subclass_of_case(self):
        assert issubclass(EmbargoedCase, Case)

    def test_is_subclass_of_vulnerability_case(self):
        assert issubclass(EmbargoedCase, VulnerabilityCase)

    def test_type_literal_unchanged(self):
        """EmbargoedCase shares type_='VulnerabilityCase' (LST-05-003)."""
        ec = EmbargoedCase.model_validate(_embargoed_case_data())
        assert ec.type_ == "VulnerabilityCase"

    def test_not_registered_separately_in_core_vocabulary(self):
        assert "EmbargoedCase" not in CORE_VOCABULARY

    def test_valid_with_active_embargo_and_active_em_state(self):
        ec = EmbargoedCase.model_validate(_embargoed_case_data())
        assert ec.active_embargo == _EMBARGO_ID
        assert ec.current_status.em_state == EM.ACTIVE

    def test_valid_with_revise_em_state(self):
        vc = _embargoed_case_data()
        vc.case_statuses = [
            CaseStatus(
                context=vc.id_,
                attributed_to=_ACTOR,
                em_state=EM.REVISE,
            )
        ]
        ec = EmbargoedCase.model_validate(vc)
        assert ec.current_status.em_state == EM.REVISE

    def test_raises_when_active_embargo_is_none(self):
        vc = _minimal_case()
        assert vc.active_embargo is None
        with pytest.raises(VultronValidationError, match="active_embargo"):
            EmbargoedCase.model_validate(vc)

    def test_raises_when_em_state_is_no_embargo(self):
        vc = _embargoed_case_data()
        vc.case_statuses = [
            CaseStatus(
                context=vc.id_,
                attributed_to=_ACTOR,
                em_state=EM.NO_EMBARGO,
            )
        ]
        with pytest.raises(VultronValidationError, match="em_state"):
            EmbargoedCase.model_validate(vc)

    def test_raises_when_em_state_is_proposed(self):
        vc = _embargoed_case_data()
        vc.case_statuses = [
            CaseStatus(
                context=vc.id_,
                attributed_to=_ACTOR,
                em_state=EM.PROPOSED,
            )
        ]
        with pytest.raises(VultronValidationError, match="em_state"):
            EmbargoedCase.model_validate(vc)

    def test_raises_when_em_state_is_exited(self):
        vc = _embargoed_case_data()
        vc.case_statuses = [
            CaseStatus(
                context=vc.id_,
                attributed_to=_ACTOR,
                em_state=EM.EXITED,
            )
        ]
        with pytest.raises(VultronValidationError, match="em_state"):
            EmbargoedCase.model_validate(vc)

    def test_inherits_case_invariants(self):
        """EmbargoedCase is a Case: it also enforces Case invariants."""
        vc = VulnerabilityCase(attributed_to=_ACTOR)
        vc.active_embargo = _EMBARGO_ID
        # No reports: should fail the Case check first
        with pytest.raises(VultronValidationError):
            EmbargoedCase.model_validate(vc)

    def test_model_validate_promotes_qualified_vulnerability_case(self):
        """model_validate promotes a qualifying VulnerabilityCase (LST-05-001)."""
        vc = _embargoed_case_data()
        ec = EmbargoedCase.model_validate(vc)
        assert isinstance(ec, EmbargoedCase)

    def test_pre_embargo_case_fails_embargoed_validate(self):
        """A pre-embargo Case fails EmbargoedCase.model_validate (LST-05-003)."""
        vc = _minimal_case()
        with pytest.raises(VultronValidationError):
            EmbargoedCase.model_validate(vc)


# ---------------------------------------------------------------------------
# DataLayer round-trip (AC-4, LST-05-003)
# ---------------------------------------------------------------------------


class TestDataLayerRoundTrip:
    """Persisted staged objects rehydrate to base type and re-validate."""

    def test_embargoed_case_round_trips_via_model_dump(self):
        """Dump EmbargoedCase → reload as VulnerabilityCase → re-validate (LST-05-003)."""
        ec = EmbargoedCase.model_validate(_embargoed_case_data())
        dumped = ec.model_dump(by_alias=True)

        # Rehydration always yields the base type
        vc = VulnerabilityCase.model_validate(dumped)
        assert isinstance(vc, VulnerabilityCase)
        assert vc.type_ == "VulnerabilityCase"
        assert vc.active_embargo == _EMBARGO_ID

        # Re-narrowing succeeds
        ec2 = EmbargoedCase.model_validate(vc)
        assert isinstance(ec2, EmbargoedCase)

    def test_case_round_trips_via_model_dump(self):
        """Dump Case → reload as VulnerabilityCase → re-validate (LST-05-003)."""
        c = Case.model_validate(_minimal_case())
        dumped = c.model_dump(by_alias=True)

        vc = VulnerabilityCase.model_validate(dumped)
        assert isinstance(vc, VulnerabilityCase)

        c2 = Case.model_validate(vc)
        assert isinstance(c2, Case)

    def test_pre_embargo_case_fails_embargoed_revalidation(self):
        """A persisted pre-embargo Case fails EmbargoedCase re-validation (AC-4)."""
        c = Case.model_validate(_minimal_case())
        dumped = c.model_dump(by_alias=True)
        vc = VulnerabilityCase.model_validate(dumped)
        with pytest.raises(VultronValidationError):
            EmbargoedCase.model_validate(vc)


# ---------------------------------------------------------------------------
# Spec compliance: no RM staged type (AC-5, LST-02-004)
# ---------------------------------------------------------------------------


class TestNoRMStagedTypes:
    """Per-participant RM state MUST NOT be a VulnerabilityCase staged type (AC-5)."""

    def test_no_valid_case_type_exists(self):
        """There must be no 'ValidCase' or 'TriagedCase' in staged_case __all__."""
        from vultron.core.models.staged_case import __all__ as exports

        for name in exports:
            assert (
                "Valid" not in name
            ), f"Found unexpected RM-typed class {name!r} in staged_case.__all__"
            assert (
                "Triage" not in name
            ), f"Found unexpected RM-typed class {name!r} in staged_case.__all__"

    def test_staged_case_exports(self):
        from vultron.core.models.staged_case import __all__

        assert set(__all__) == {"IncomingReport", "Case", "EmbargoedCase"}
