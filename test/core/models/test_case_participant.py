"""Unit tests for core CaseParticipant and role subclasses (issue #728)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vultron.core.models.case_participant import (
    CaseActorParticipant,
    CaseParticipant,
    CoordinatorParticipant,
    DeployerParticipant,
    FinderParticipant,
    FinderReporterParticipant,
    ObserverParticipant,
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.embargo_register import (
    FINAL_REGISTER_STATUSES,
    EmbargoRegisterStatus,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole, validate_roles
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)

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

    def test_default_case_roles_empty(self):
        """Fresh participant has no roles."""
        p = _make()
        assert p.case_roles == []

    def test_default_embargo_consents_empty(self):
        """A fresh record holds no rows until it joins a case's roster."""
        p = _make()
        assert p.embargo_consents == []

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
        assert p.participant_statuses[0].rm.state == RM.START

    def test_pre_populated_list_preserved(self):
        """When participant_statuses is non-empty the validator does not replace it."""
        existing = ParticipantStatus(
            context=_CONTEXT,
            attributed_to=_ACTOR,
            rm=RmDimension(state=RM.ACCEPTED),
        )
        p = _make(participant_statuses=[existing])
        assert len(p.participant_statuses) == 1
        assert p.participant_statuses[0].rm.state == RM.ACCEPTED


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
            rm=RmDimension(state=RM.ACCEPTED),
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
# add_participant_status
# ---------------------------------------------------------------------------


class TestAddParticipantStatus:
    """add_participant_status validates shape and appends (PRM-03-003)."""

    def test_valid_status_appended(self):
        p = _make()
        initial_len = len(p.participant_statuses)
        status = ParticipantStatus(context=_CONTEXT, attributed_to=_ACTOR)
        p.add_participant_status(status)
        assert len(p.participant_statuses) == initial_len + 1
        assert p.participant_statuses[-1] is status

    def test_rejects_wire_shaped_status(self):
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        # ``as_ParticipantStatus`` *is* ``ParticipantStatus`` (ADR-0099 detail 3),
        # so the status is accepted rather than refused.  ``test_rejects_non_status_object``
        # below still covers a genuinely wrong type.
        p = _make()
        wire_status = as_ParticipantStatus(context=_CONTEXT)
        p.add_participant_status(wire_status)
        assert p.participant_statuses[-1] is wire_status

    def test_rejects_non_status_object(self):
        p = _make()
        with pytest.raises(VultronValidationError):
            p.add_participant_status("not-a-status")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Role subclasses
# ---------------------------------------------------------------------------


_ROLE_SUBCLASS_CASES = [
    (FinderParticipant, [CVDRole.FINDER]),
    (VendorParticipant, [CVDRole.VENDOR]),
    (DeployerParticipant, [CVDRole.DEPLOYER]),
    (CoordinatorParticipant, [CVDRole.COORDINATOR]),
    (ObserverParticipant, [CVDRole.OBSERVER]),
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
        assert p.participant_status.rm.state == RM.ACCEPTED

    @pytest.mark.parametrize(
        "cls", [FinderParticipant, VendorParticipant, CoordinatorParticipant]
    )
    def test_non_reporter_status_rm_start(self, cls):
        """Non-reporter subclasses start at RM.START."""
        p = cls(attributed_to=_ACTOR, context=_CONTEXT)
        assert p.participant_status is not None
        assert p.participant_status.rm.state == RM.START


# ---------------------------------------------------------------------------
# CVE_NUMBERING_AUTHORITY role on participants
# ---------------------------------------------------------------------------


class TestCNARoleOnParticipant:
    """CVE_NUMBERING_AUTHORITY is recognised in participant role lookups."""

    def test_cna_role_recognized_via_add_role(self):
        """add_role(CVE_NUMBERING_AUTHORITY) stores the role correctly."""
        p = _make()
        p.add_role(CVDRole.CVE_NUMBERING_AUTHORITY)
        assert CVDRole.CVE_NUMBERING_AUTHORITY in p.case_roles

    def test_has_role_returns_true_for_cna(self):
        """has_role() returns True when CVE_NUMBERING_AUTHORITY is held."""
        p = _make(case_roles=[CVDRole.CVE_NUMBERING_AUTHORITY])
        assert p.has_role(CVDRole.CVE_NUMBERING_AUTHORITY)

    def test_has_role_returns_false_without_cna(self):
        """has_role() returns False when CVE_NUMBERING_AUTHORITY is not held."""
        p = _make(case_roles=[CVDRole.VENDOR])
        assert not p.has_role(CVDRole.CVE_NUMBERING_AUTHORITY)

    def test_cna_role_orthogonal_to_vendor(self):
        """A participant may hold both CVE_NUMBERING_AUTHORITY and VENDOR."""
        p = _make(case_roles=[CVDRole.VENDOR, CVDRole.CVE_NUMBERING_AUTHORITY])
        assert p.has_role(CVDRole.VENDOR)
        assert p.has_role(CVDRole.CVE_NUMBERING_AUTHORITY)

    def test_cna_role_orthogonal_to_coordinator(self):
        """A participant may hold both CVE_NUMBERING_AUTHORITY and COORDINATOR."""
        p = _make(
            case_roles=[CVDRole.COORDINATOR, CVDRole.CVE_NUMBERING_AUTHORITY]
        )
        assert p.has_role(CVDRole.COORDINATOR)
        assert p.has_role(CVDRole.CVE_NUMBERING_AUTHORITY)

    def test_cna_role_roundtrips_via_serialization(self):
        """CVE_NUMBERING_AUTHORITY survives a serialize_roles → validate_roles roundtrip."""
        from vultron.enums.roles import serialize_roles

        roles = [CVDRole.VENDOR, CVDRole.CVE_NUMBERING_AUTHORITY]
        serialized = serialize_roles(roles)
        assert "cve_numbering_authority" in serialized
        restored = validate_roles(serialized)
        assert CVDRole.CVE_NUMBERING_AUTHORITY in restored

    def test_cna_role_persists_in_participant_status(self):
        """CVE_NUMBERING_AUTHORITY assigned to participant is stored in its status.cvd_role."""
        p = _make(case_roles=[CVDRole.CVE_NUMBERING_AUTHORITY])
        p.participant_statuses[0].cvd_role = p.case_roles
        status = p.participant_status
        assert status is not None
        assert CVDRole.CVE_NUMBERING_AUTHORITY in status.cvd_role


# ---------------------------------------------------------------------------
# Per-embargo consent rows (ADR-0122, CM-10-001, CM-18-001, CM-18-005)
# ---------------------------------------------------------------------------

_EMBARGO = "https://example.org/embargoes/em-001"
_OTHER = "https://example.org/embargoes/em-002"
_DEADLINE = datetime(2030, 1, 1, tzinfo=UTC)

S = EmbargoConsentState
T = PEC_Trigger
R = EmbargoRegisterStatus
_ACTIVE = R.ACTIVE


def _with_rows(**rows: EmbargoConsentState) -> CaseParticipant:
    """A participant holding one row per ``{embargo_id: state}`` pair."""
    return _make(
        embargo_consents=[
            EmbargoConsent(embargo_id=eid, state=state)
            for eid, state in rows.items()
        ]
    )


def _entry(
    embargo_id: str, status: EmbargoRegisterStatus, replaces: str | None = None
) -> EmbargoRegisterEntry:
    return EmbargoRegisterEntry(
        embargo=embargo_id, status=status, replaces=replaces
    )


class TestConsentFor:
    @pytest.mark.spec("CM-18-001")
    def test_missing_row_raises(self):
        """A missing row is a defect, never "not asked" (ADR-0122)."""
        with pytest.raises(VultronNotFoundError):
            _make().consent_for(_EMBARGO)

    def test_reads_the_row_for_that_embargo_only(self):
        p = _with_rows(**{_EMBARGO: S.AGREED, _OTHER: S.DECLINED})
        assert p.consent_for(_EMBARGO) is S.AGREED
        assert p.consent_for(_OTHER) is S.DECLINED
        with pytest.raises(VultronNotFoundError):
            p.consent_for("urn:unknown")

    def test_rows_round_trip_serialization(self):
        p = _with_rows(**{_EMBARGO: S.AGREED, _OTHER: S.UNINVITED})
        restored = CaseParticipant.model_validate(p.model_dump(by_alias=True))
        assert restored.consent_for(_EMBARGO) is S.AGREED
        assert restored.consent_for(_OTHER) is S.UNINVITED

    def test_retired_scalar_fields_are_refused(self):
        for key, value in (
            ("embargo_consent_state", "SIGNATORY"),
            ("accepted_embargo_ids", [_EMBARGO]),
            ("invite_rsvp_deadline", _DEADLINE.isoformat()),
        ):
            with pytest.raises(ValidationError):
                CaseParticipant.model_validate(
                    {"attributed_to": _ACTOR, "context": _CONTEXT, key: value}
                )

    def test_status_no_longer_carries_consent(self):
        p = _make()
        status = p.participant_status
        assert status is not None
        assert not hasattr(status, "consent")
        assert not hasattr(status, "embargo_adherence")


class TestWriteUninvitedRows:
    """The creation write of the consent table (ADR-0122)."""

    @pytest.mark.spec("CM-18-001")
    def test_writes_one_uninvited_row_per_embargo(self):
        p = _make()
        assert p.write_uninvited_rows([_EMBARGO, _OTHER]) is True
        assert [(r.embargo_id, r.state) for r in p.embargo_consents] == [
            (_EMBARGO, S.UNINVITED),
            (_OTHER, S.UNINVITED),
        ]

    def test_keeps_rows_already_held(self):
        p = _with_rows(**{_EMBARGO: S.AGREED})
        assert p.write_uninvited_rows([_EMBARGO, _OTHER, _OTHER]) is True
        assert p.consent_for(_EMBARGO) is S.AGREED
        assert p.consent_for(_OTHER) is S.UNINVITED
        assert len(p.embargo_consents) == 2

    def test_idempotent(self):
        p = _with_rows(**{_EMBARGO: S.UNINVITED})
        assert p.write_uninvited_rows([_EMBARGO]) is False


class TestRsvpDeadlineOnTheRow:
    """An RSVP deadline belongs to one invitation (CM-28-001, CM-28-013)."""

    @pytest.mark.spec("CM-28-013")
    def test_only_an_invited_row_carries_a_deadline(self):
        EmbargoConsent(
            embargo_id=_EMBARGO, state=S.INVITED, rsvp_deadline=_DEADLINE
        )
        for state in (S.UNINVITED, S.AGREED, S.DECLINED, S.TIMED_OUT):
            with pytest.raises(ValidationError):
                EmbargoConsent(
                    embargo_id=_EMBARGO, state=state, rsvp_deadline=_DEADLINE
                )

    @pytest.mark.spec("CM-28-006")
    def test_naive_deadline_is_read_as_utc(self):
        row = EmbargoConsent(
            embargo_id=_EMBARGO,
            state=S.INVITED,
            rsvp_deadline=datetime(2030, 1, 1),  # noqa: DTZ001 — naive on purpose
        )
        assert row.rsvp_deadline == _DEADLINE

    @pytest.mark.spec("CM-28-013")
    def test_invite_sets_the_deadline_and_leaving_invited_clears_it(self):
        p = _with_rows(**{_EMBARGO: S.UNINVITED})
        p.apply_pec_transition(
            _EMBARGO, T.INVITE, entry_status=_ACTIVE, rsvp_deadline=_DEADLINE
        )
        assert p.rsvp_deadline_for(_EMBARGO) == _DEADLINE
        p.apply_pec_transition(_EMBARGO, T.TIME_OUT, entry_status=_ACTIVE)
        assert p.consent_for(_EMBARGO) is S.TIMED_OUT
        assert p.rsvp_deadline_for(_EMBARGO) is None

    @pytest.mark.spec("CM-28-013")
    def test_a_deadline_rides_only_on_invite(self):
        p = _with_rows(**{_EMBARGO: S.INVITED})
        with pytest.raises(VultronValidationError):
            p.apply_pec_transition(
                _EMBARGO,
                T.AGREE,
                entry_status=_ACTIVE,
                rsvp_deadline=_DEADLINE,
            )
        assert p.consent_for(_EMBARGO) is S.INVITED

    @pytest.mark.spec("CM-28-001")
    def test_concurrent_invitations_keep_their_own_deadlines(self):
        later = _DEADLINE.replace(year=2031)
        p = _with_rows(**{_EMBARGO: S.UNINVITED, _OTHER: S.UNINVITED})
        p.apply_pec_transition(
            _EMBARGO, T.INVITE, entry_status=_ACTIVE, rsvp_deadline=_DEADLINE
        )
        p.apply_pec_transition(
            _OTHER, T.INVITE, entry_status=R.PROPOSED, rsvp_deadline=later
        )
        assert p.rsvp_deadline_for(_EMBARGO) == _DEADLINE
        assert p.rsvp_deadline_for(_OTHER) == later

    def test_restamp_replaces_an_invited_rows_deadline_only(self):
        later = _DEADLINE.replace(year=2031)
        p = _make(
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=_EMBARGO,
                    state=S.INVITED,
                    rsvp_deadline=_DEADLINE,
                ),
                EmbargoConsent(embargo_id=_OTHER, state=S.AGREED),
            ]
        )
        assert p.restamp_rsvp_deadline(_EMBARGO, later, entry_status=_ACTIVE)
        assert p.rsvp_deadline_for(_EMBARGO) == later
        assert not p.restamp_rsvp_deadline(
            _EMBARGO, later, entry_status=_ACTIVE
        )
        assert not p.restamp_rsvp_deadline(_OTHER, later, entry_status=_ACTIVE)
        assert not p.restamp_rsvp_deadline(
            _EMBARGO, _DEADLINE, entry_status=R.SUPERSEDED
        )
        assert p.rsvp_deadline_for(_EMBARGO) == later


class TestApplyPecTransition:
    """apply_pec_transition() is the single authoritative consent-write path."""

    @pytest.mark.spec("CM-18-005")
    def test_missing_row_raises_and_writes_nothing(self):
        p = _make()
        with pytest.raises(VultronNotFoundError):
            p.apply_pec_transition(_EMBARGO, T.INVITE, entry_status=_ACTIVE)
        assert p.embargo_consents == []

    @pytest.mark.spec("CM-18-005", "CM-18-003")
    def test_transition_replaces_the_row_without_duplicating(self):
        p = _with_rows(**{_OTHER: S.UNINVITED, _EMBARGO: S.UNINVITED})
        p.apply_pec_transition(_EMBARGO, T.INVITE, entry_status=_ACTIVE)
        p.apply_pec_transition(_EMBARGO, T.AGREE, entry_status=_ACTIVE)
        assert p.consent_for(_EMBARGO) is S.AGREED
        assert [r.embargo_id for r in p.embargo_consents] == [_OTHER, _EMBARGO]

    @pytest.mark.spec("CM-18-005")
    def test_one_embargo_does_not_touch_another(self):
        p = _with_rows(**{_EMBARGO: S.AGREED, _OTHER: S.UNINVITED})
        p.apply_pec_transition(_OTHER, T.INVITE, entry_status=R.PROPOSED)
        assert p.consent_for(_EMBARGO) is S.AGREED
        assert p.consent_for(_OTHER) is S.INVITED

    @pytest.mark.spec("CM-18-003")
    def test_illegal_trigger_raises_and_leaves_rows_unchanged(self):
        p = _with_rows(**{_EMBARGO: S.AGREED})
        with pytest.raises(VultronInvalidStateTransitionError):
            p.apply_pec_transition(_EMBARGO, T.AGREE, entry_status=_ACTIVE)
        assert p.consent_for(_EMBARGO) is S.AGREED
        assert len(p.embargo_consents) == 1

    def test_if_legal_reports_whether_the_row_moved(self):
        p = _with_rows(**{_EMBARGO: S.AGREED})
        assert not p.apply_pec_transition_if_legal(
            _EMBARGO, T.AGREE, entry_status=_ACTIVE
        )
        assert p.apply_pec_transition_if_legal(
            _EMBARGO, T.DECLINE, entry_status=_ACTIVE
        )
        assert p.consent_for(_EMBARGO) is S.DECLINED
        assert not p.apply_pec_transition_if_legal(
            _EMBARGO, T.TIME_OUT, entry_status=_ACTIVE
        )
        assert p.consent_for(_EMBARGO) is S.DECLINED


class TestFinalEntriesAreFrozen:
    """A row whose register entry is final accepts no trigger (ADR-0122)."""

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("status", sorted(FINAL_REGISTER_STATUSES))
    @pytest.mark.parametrize("trigger", list(T))
    def test_no_trigger_moves_a_row_for_a_final_entry(self, status, trigger):
        for state in S:
            p = _with_rows(**{_EMBARGO: state})
            assert not p.accepts_pec_trigger(
                _EMBARGO, trigger, entry_status=status
            )
            assert not p.apply_pec_transition_if_legal(
                _EMBARGO, trigger, entry_status=status
            )
            with pytest.raises(VultronInvalidStateTransitionError):
                p.apply_pec_transition(_EMBARGO, trigger, entry_status=status)
            assert p.consent_for(_EMBARGO) is state

    @pytest.mark.parametrize("status", [R.PROPOSED, R.ACTIVE])
    def test_rows_for_open_entries_follow_the_table(self, status):
        p = _with_rows(**{_EMBARGO: S.UNINVITED})
        assert p.accepts_pec_trigger(_EMBARGO, T.INVITE, entry_status=status)


class TestAcceptsPecTrigger:
    """``accepts_pec_trigger`` is the read-only twin of the write path."""

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize(
        ("state", "accepts"),
        [
            (S.UNINVITED, True),
            (S.DECLINED, True),
            (S.TIMED_OUT, True),
            (S.INVITED, False),
            (S.AGREED, False),
        ],
    )
    def test_invite_legality_by_row(self, state, accepts):
        p = _with_rows(**{_EMBARGO: state})
        assert (
            p.accepts_pec_trigger(_EMBARGO, T.INVITE, entry_status=_ACTIVE)
            is accepts
        )

    def test_asking_changes_nothing(self):
        p = _with_rows(**{_EMBARGO: S.AGREED})
        p.accepts_pec_trigger(_EMBARGO, T.INVITE, entry_status=_ACTIVE)
        p.accepts_pec_trigger(_EMBARGO, T.DECLINE, entry_status=_ACTIVE)
        assert p.consent_for(_EMBARGO) is S.AGREED


class TestIsSignatory:
    """Signatory is a lookup on the embargo in force (CM-18-001)."""

    @pytest.mark.spec("CM-18-001")
    def test_no_embargo_in_force_nobody_is_signatory(self):
        p = _with_rows(**{_EMBARGO: S.AGREED})
        assert p.is_signatory(None) is False

    @pytest.mark.spec("CM-18-001")
    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (S.UNINVITED, False),
            (S.INVITED, False),
            (S.AGREED, True),
            (S.DECLINED, False),
            (S.TIMED_OUT, False),
        ],
    )
    def test_signatory_iff_active_row_is_agreed(self, state, expected):
        p = _with_rows(**{_EMBARGO: state})
        assert p.is_signatory(_EMBARGO) is expected

    @pytest.mark.spec("CM-18-001")
    def test_agreement_to_another_embargo_does_not_make_a_signatory(self):
        p = _with_rows(**{_OTHER: S.AGREED, _EMBARGO: S.UNINVITED})
        assert p.is_signatory(_EMBARGO) is False

    def test_missing_row_for_the_active_embargo_raises(self):
        with pytest.raises(VultronNotFoundError):
            _make().is_signatory(_EMBARGO)


_D0 = "https://example.org/embargoes/d0"
_D1 = "https://example.org/embargoes/d1"
_D2 = "https://example.org/embargoes/d2"


class TestHasLapsed:
    """Lapsed is read from the rows and the register (ADR-0122, CM-18-001)."""

    @pytest.mark.spec("CM-18-001")
    def test_no_embargo_in_force_nobody_has_lapsed(self):
        p = _with_rows(**{_D0: S.AGREED})
        assert p.has_lapsed([]) is False
        assert p.has_lapsed([_entry(_D0, R.TERMINATED)]) is False

    @pytest.mark.spec("CM-18-001")
    @pytest.mark.parametrize(
        "active_row", [S.UNINVITED, S.INVITED, S.TIMED_OUT]
    )
    def test_agreed_to_the_replaced_embargo_but_not_the_active_one(
        self, active_row
    ):
        register = [_entry(_D0, R.SUPERSEDED), _entry(_D1, _ACTIVE, _D0)]
        p = _with_rows(**{_D0: S.AGREED, _D1: active_row})
        assert p.has_lapsed(register) is True

    @pytest.mark.spec("CM-18-001")
    @pytest.mark.parametrize("active_row", [S.AGREED, S.DECLINED])
    def test_an_answer_to_the_active_embargo_is_not_a_lapse(self, active_row):
        register = [_entry(_D0, R.SUPERSEDED), _entry(_D1, _ACTIVE, _D0)]
        p = _with_rows(**{_D0: S.AGREED, _D1: active_row})
        assert p.has_lapsed(register) is False

    @pytest.mark.spec("CM-18-001")
    def test_never_bound_participant_has_not_lapsed(self):
        register = [_entry(_D0, R.SUPERSEDED), _entry(_D1, _ACTIVE, _D0)]
        p = _with_rows(**{_D0: S.TIMED_OUT, _D1: S.INVITED})
        assert p.has_lapsed(register) is False

    @pytest.mark.spec("CM-18-001")
    def test_three_step_chain_stays_lapsed(self):
        """Agree D0; longer D1 activates; shorter D2 activates: still lapsed.

        D2 carries over only those who agreed to D1, so the participant has no
        agreement to D2; following ``replaces`` from D2 passes D1 (never
        answered) and reaches its agreement to D0.
        """
        register = [
            _entry(_D0, R.SUPERSEDED),
            _entry(_D1, R.SUPERSEDED, _D0),
            _entry(_D2, _ACTIVE, _D1),
        ]
        p = _with_rows(**{_D0: S.AGREED, _D1: S.INVITED, _D2: S.UNINVITED})
        assert p.has_lapsed(register) is True

    @pytest.mark.spec("CM-18-001")
    def test_agreeing_to_a_proposal_that_never_took_effect_binds_nothing(self):
        """Only embargoes once in force are on the ``replaces`` chain."""
        register = [_entry(_D0, R.REJECTED), _entry(_D1, _ACTIVE)]
        p = _with_rows(**{_D0: S.AGREED, _D1: S.UNINVITED})
        assert p.has_lapsed(register) is False
        open_revision = [_entry(_D1, _ACTIVE), _entry(_D2, R.PROPOSED)]
        q = _with_rows(**{_D1: S.UNINVITED, _D2: S.AGREED})
        assert q.has_lapsed(open_revision) is False

    @pytest.mark.spec("CM-18-001")
    def test_withdrawal_from_a_later_embargo_is_not_a_lapse(self):
        """Agree D0; shorter D1 carried over; withdraw from D1; longer D2."""
        register = [
            _entry(_D0, R.SUPERSEDED),
            _entry(_D1, R.SUPERSEDED, _D0),
            _entry(_D2, _ACTIVE, _D1),
        ]
        p = _with_rows(**{_D0: S.AGREED, _D1: S.DECLINED, _D2: S.UNINVITED})
        assert p.has_lapsed(register) is False

    @pytest.mark.spec("CM-18-001")
    def test_lapse_is_read_not_written(self):
        register = [_entry(_D0, R.SUPERSEDED), _entry(_D1, _ACTIVE, _D0)]
        p = _with_rows(**{_D0: S.AGREED, _D1: S.UNINVITED})
        before = list(p.embargo_consents)
        assert p.has_lapsed(register) is True
        assert p.embargo_consents == before


class TestSignEmbargo:
    """``sign_embargo`` seeding (CM-14-005, CM-10-001, ADR-0122)."""

    @pytest.mark.parametrize(
        "start", [S.UNINVITED, S.INVITED, S.TIMED_OUT, S.AGREED]
    )
    def test_signs_where_agree_is_legal(self, start):
        p = _with_rows(**{_EMBARGO: start})

        assert p.sign_embargo(_EMBARGO) is True

        assert p.consent_for(_EMBARGO) is S.AGREED
        assert p.is_signatory(_EMBARGO)
        assert len(p.embargo_consents) == 1

    def test_a_declined_participant_is_left_unsigned(self):
        p = _with_rows(**{_EMBARGO: S.DECLINED})

        assert p.sign_embargo(_EMBARGO) is False

        assert p.consent_for(_EMBARGO) is S.DECLINED
        assert not p.is_signatory(_EMBARGO)

    def test_signing_leaves_other_embargo_rows_alone(self):
        p = _with_rows(**{_OTHER: S.DECLINED, _EMBARGO: S.UNINVITED})
        p.sign_embargo(_EMBARGO)
        assert p.consent_for(_OTHER) is S.DECLINED


# ---------------------------------------------------------------------------
# The removal fact: record_removal and clear_removal (CM-31-001, CM-31-011)
# ---------------------------------------------------------------------------

_REMOVAL_ID = "https://example.org/activities/remove-1"


def _participant_for_removal() -> CaseParticipant:
    return CaseParticipant(
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/case-1",
    )


@pytest.mark.spec("CM-31-011")
def test_clear_removal_reinstates_a_removed_participant() -> None:
    participant = _participant_for_removal()
    assert participant.record_removal(_REMOVAL_ID)

    assert participant.clear_removal() is True

    assert not participant.removed
    assert participant.removal_activity is None


@pytest.mark.spec("CM-31-011")
def test_clear_removal_of_a_participant_that_is_not_removed_is_a_no_op() -> (
    None
):
    participant = _participant_for_removal()

    assert participant.clear_removal() is False

    assert not participant.removed


@pytest.mark.spec("CM-31-011")
def test_a_reinstated_participant_can_be_removed_again() -> None:
    participant = _participant_for_removal()
    participant.record_removal(_REMOVAL_ID)
    participant.clear_removal()

    assert participant.record_removal("https://example.org/activities/r2")

    assert participant.removal_activity == "https://example.org/activities/r2"


@pytest.mark.spec("CM-18-001")
def test_has_lapsed_refuses_a_replaces_the_register_does_not_hold():
    """A dangling ``replaces`` is a broken register, never "not lapsed"."""
    register = [_entry(_D1, _ACTIVE, _D0)]
    p = _with_rows(**{_D0: S.AGREED, _D1: S.UNINVITED})
    with pytest.raises(VultronValidationError):
        p.has_lapsed(register)


@pytest.mark.spec("CM-18-001")
def test_has_lapsed_refuses_a_replaces_chain_that_loops():
    """A looping ``replaces`` chain is a broken register: it raises, never hangs."""
    register = [
        _entry(_D2, _ACTIVE, _D1),
        _entry(_D1, EmbargoRegisterStatus.SUPERSEDED, _D0),
        _entry(_D0, EmbargoRegisterStatus.SUPERSEDED, _D1),
    ]
    p = _with_rows(**{_D0: S.UNINVITED, _D1: S.UNINVITED, _D2: S.UNINVITED})
    with pytest.raises(VultronValidationError):
        p.has_lapsed(register)
