"""Unit tests for core CaseParticipant and role subclasses (issue #728)."""

import pytest

from vultron.core.models.case_participant import (
    CaseActorParticipant,
    CaseParticipant,
    CoordinatorParticipant,
    DeployerParticipant,
    FinderParticipant,
    FinderReporterParticipant,
    OtherParticipant,
    ReporterParticipant,
    VendorParticipant,
    VultronParticipant,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole

_ACTOR = "https://example.org/actors/alice"
_CONTEXT = "https://example.org/cases/case-001"


def _make(attributed_to=_ACTOR, context=_CONTEXT, **kw) -> CaseParticipant:
    return CaseParticipant(attributed_to=attributed_to, context=context, **kw)


# ---------------------------------------------------------------------------
# Construction & vocabulary registration
# ---------------------------------------------------------------------------


class TestCaseParticipantConstruction:
    """Basic construction and CORE_VOCABULARY registration."""

    def test_type_literal(self):
        """type_ must equal the Literal value 'CaseParticipant'."""
        p = _make()
        assert p.type_ == "CaseParticipant"

    def test_registered_in_core_vocabulary(self):
        """CaseParticipant must be registered in CORE_VOCABULARY."""
        from vultron.core.models import CORE_VOCABULARY

        assert "CaseParticipant" in CORE_VOCABULARY

    def test_vultron_participant_alias(self):
        """VultronParticipant is an alias for CaseParticipant."""
        assert VultronParticipant is CaseParticipant

    def test_default_case_roles_empty(self):
        """Fresh participant has no roles."""
        p = _make()
        assert p.case_roles == []

    def test_default_embargo_consent_state(self):
        """Default embargo_consent_state is PEC.NO_EMBARGO."""
        from vultron.core.states.participant_embargo_consent import PEC

        p = _make()
        assert p.embargo_consent_state == PEC.NO_EMBARGO

    def test_participant_case_name_default_none(self):
        """participant_case_name defaults to None."""
        p = _make()
        assert p.participant_case_name is None

    def test_participant_case_name_accepts_non_empty(self):
        """participant_case_name accepts a non-empty string."""
        p = _make(participant_case_name="My alias")
        assert p.participant_case_name == "My alias"

    def test_participant_case_name_rejects_empty_string(self):
        """participant_case_name must not be an empty string (CS-08-002)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _make(participant_case_name="")


# ---------------------------------------------------------------------------
# _set_name_if_empty validator
# ---------------------------------------------------------------------------


class TestSetNameIfEmpty:
    """_set_name_if_empty sets name from attributed_to when unset."""

    def test_name_derived_from_attributed_to_string(self):
        """When name is None and attributed_to is a string, name = attributed_to."""
        p = CaseParticipant(attributed_to=_ACTOR, context=_CONTEXT)
        assert p.name == _ACTOR

    def test_explicit_name_preserved(self):
        """When name is provided it is not overwritten."""
        p = CaseParticipant(
            attributed_to=_ACTOR, context=_CONTEXT, name="Explicit"
        )
        assert p.name == "Explicit"

    def test_name_none_when_attributed_to_none(self):
        """When both name and attributed_to are None, name stays None."""
        p = CaseParticipant()
        assert p.name is None


# ---------------------------------------------------------------------------
# _init_participant_status_if_empty validator
# ---------------------------------------------------------------------------


class TestInitParticipantStatusIfEmpty:
    """_init_participant_status_if_empty seeds a default status when the list is empty."""

    def test_seeds_one_status_by_default(self):
        """A freshly-constructed participant starts with exactly one status."""
        p = _make()
        assert len(p.participant_statuses) == 1

    def test_seeded_status_is_participant_status_instance(self):
        """The seeded status is a ParticipantStatus instance."""
        p = _make()
        assert isinstance(p.participant_statuses[0], ParticipantStatus)

    def test_seeded_status_rm_start(self):
        """The seeded status starts at RM.START."""
        p = _make()
        assert p.participant_statuses[0].rm_state == RM.START

    def test_pre_populated_list_preserved(self):
        """When participant_statuses is non-empty the validator does not replace it."""
        existing = ParticipantStatus(
            context=_CONTEXT,
            attributed_to=_ACTOR,
            rm_state=RM.ACCEPTED,
        )
        p = _make(participant_statuses=[existing])
        assert len(p.participant_statuses) == 1
        assert p.participant_statuses[0].rm_state == RM.ACCEPTED


# ---------------------------------------------------------------------------
# participant_status property
# ---------------------------------------------------------------------------


class TestParticipantStatusProperty:
    """participant_status returns the last-appended status (append-order semantics)."""

    def test_returns_last_element(self):
        """participant_status returns participant_statuses[-1]."""
        p = _make()
        second = ParticipantStatus(
            context=_CONTEXT,
            attributed_to=_ACTOR,
            rm_state=RM.ACCEPTED,
        )
        p.participant_statuses.append(second)
        assert p.participant_status is second

    def test_returns_none_when_list_cleared(self):
        """participant_status returns None when participant_statuses is empty."""
        p = _make()
        p.participant_statuses = []
        assert p.participant_status is None

    def test_returns_single_status(self):
        """participant_status returns the only status when exactly one is present."""
        p = _make()
        assert p.participant_status is p.participant_statuses[0]


# ---------------------------------------------------------------------------
# append_rm_state
# ---------------------------------------------------------------------------


class TestAppendRmState:
    """append_rm_state validates the RM transition before appending."""

    def test_valid_transition_appended(self):
        """A valid START → RECEIVED transition appends a new status."""
        p = _make()
        assert p.append_rm_state(RM.RECEIVED, _ACTOR, _CONTEXT) is True
        assert len(p.participant_statuses) == 2
        assert p.participant_status is not None
        assert p.participant_status.rm_state == RM.RECEIVED

    def test_invalid_transition_blocked(self):
        """An invalid RM transition (START → ACCEPTED) is rejected and returns False."""
        p = _make()
        initial_len = len(p.participant_statuses)
        result = p.append_rm_state(RM.ACCEPTED, _ACTOR, _CONTEXT)
        assert result is False
        assert len(p.participant_statuses) == initial_len

    def test_invalid_transition_logs_warning(self, caplog):
        """An invalid RM transition logs a WARNING."""
        import logging

        p = _make()
        with caplog.at_level(logging.WARNING):
            p.append_rm_state(RM.ACCEPTED, _ACTOR, _CONTEXT)
        assert "Invalid RM transition" in caplog.text


# ---------------------------------------------------------------------------
# Role subclasses
# ---------------------------------------------------------------------------


_ROLE_SUBCLASS_CASES = [
    (FinderParticipant, [CVDRole.FINDER]),
    (VendorParticipant, [CVDRole.VENDOR]),
    (DeployerParticipant, [CVDRole.DEPLOYER]),
    (CoordinatorParticipant, [CVDRole.COORDINATOR]),
    (OtherParticipant, [CVDRole.OTHER]),
    (ReporterParticipant, [CVDRole.REPORTER]),
    (FinderReporterParticipant, [CVDRole.FINDER, CVDRole.REPORTER]),
    (CaseActorParticipant, [CVDRole.COORDINATOR, CVDRole.CASE_MANAGER]),
]


class TestRoleSubclasses:
    """Role subclasses auto-set case_roles via model validators."""

    @pytest.mark.parametrize("cls,expected_roles", _ROLE_SUBCLASS_CASES)
    def test_case_roles_set_by_validator(self, cls, expected_roles):
        """Role subclass sets exactly the expected roles."""
        p = cls(attributed_to=_ACTOR, context=_CONTEXT)
        assert set(p.case_roles) == set(expected_roles), (
            f"{cls.__name__} should have roles {expected_roles}, "
            f"got {p.case_roles}"
        )

    @pytest.mark.parametrize("cls,expected_roles", _ROLE_SUBCLASS_CASES)
    def test_is_case_participant_subclass(self, cls, expected_roles):
        """All role subclasses are subclasses of CaseParticipant."""
        assert issubclass(cls, CaseParticipant)

    @pytest.mark.parametrize("cls,expected_roles", _ROLE_SUBCLASS_CASES)
    def test_type_still_case_participant(self, cls, expected_roles):
        """All role subclasses retain type_ == 'CaseParticipant'."""
        p = cls(attributed_to=_ACTOR, context=_CONTEXT)
        assert p.type_ == "CaseParticipant"


# ---------------------------------------------------------------------------
# ACCEPTED status for Reporter and FinderReporter
# ---------------------------------------------------------------------------


class TestAcceptedStatusOnReporterSubclasses:
    """ReporterParticipant and FinderReporterParticipant start at RM.ACCEPTED."""

    @pytest.mark.parametrize(
        "cls", [ReporterParticipant, FinderReporterParticipant]
    )
    def test_participant_status_accepted(self, cls):
        """Subclass starts with RM.ACCEPTED participant status."""
        p = cls(attributed_to=_ACTOR, context=_CONTEXT)
        assert p.participant_status is not None
        assert p.participant_status.rm_state == RM.ACCEPTED

    @pytest.mark.parametrize(
        "cls", [FinderParticipant, VendorParticipant, CoordinatorParticipant]
    )
    def test_non_reporter_status_rm_start(self, cls):
        """Non-reporter subclasses start at RM.START."""
        p = cls(attributed_to=_ACTOR, context=_CONTEXT)
        assert p.participant_status is not None
        assert p.participant_status.rm_state == RM.START
