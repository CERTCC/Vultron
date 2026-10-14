#!/usr/bin/env python
"""Unit tests for vultron/core/models/dimensions.py."""

import pytest
from pydantic import ValidationError

from test.support.embargo_register import activate
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
    RmDimension,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM, RM_Trigger
from vultron.errors import VultronInvalidStateTransitionError


class TestEmDimension:
    def test_default_state(self):
        d = EmDimension()
        assert d.state == EM.NONE

    def test_construct_from_enum(self):
        d = EmDimension(state=EM.ACTIVE)
        assert d.state == EM.ACTIVE

    def test_construct_from_string(self):
        d = EmDimension.model_validate({"state": "ACTIVE"})
        assert d.state == EM.ACTIVE

    def test_is_active_true(self):
        assert EmDimension(state=EM.ACTIVE).is_active()

    def test_is_active_revise(self):
        assert EmDimension(state=EM.REVISE).is_active()

    def test_is_active_false(self):
        assert not EmDimension(state=EM.NONE).is_active()

    def test_is_proposed(self):
        assert EmDimension(state=EM.PROPOSED).is_proposed()
        assert not EmDimension(state=EM.ACTIVE).is_proposed()

    def test_is_exited(self):
        assert EmDimension(state=EM.EXITED).is_exited()
        assert not EmDimension(state=EM.ACTIVE).is_exited()

    def test_is_none(self):
        assert EmDimension(state=EM.NONE).is_none()
        assert not EmDimension(state=EM.ACTIVE).is_none()

    def test_serialization_roundtrip(self):
        d = EmDimension(state=EM.ACTIVE)
        json_str = d.model_dump_json()
        d2 = EmDimension.model_validate_json(json_str)
        assert d2.state == EM.ACTIVE

    def test_state_mutation_raises(self):
        """``EmDimension`` is frozen: assigning to .state raises (SDO-03-006)."""
        d = EmDimension(state=EM.NONE)
        with pytest.raises(ValidationError):
            d.state = EM.ACTIVE  # type: ignore[misc]

    def test_status_em_assignment_raises(self):
        """``CaseStatus.em`` is a frozen field: reassignment raises (SDO-03-006)."""
        status = CaseStatus(context="urn:case:1")
        with pytest.raises(ValidationError):
            status.em = EmDimension(state=EM.ACTIVE)  # type: ignore[misc]

    def test_status_em_state_assignment_raises(self):
        """Writing to ``status.em.state`` raises because EmDimension is frozen."""
        status = CaseStatus(context="urn:case:1")
        with pytest.raises(ValidationError):
            status.em.state = EM.ACTIVE  # type: ignore[misc]

    @pytest.mark.parametrize("flat", ["em_state", "pxa_state"])
    def test_flat_assignment_raises(self, flat):
        """The flat spelling ``status.em_state = X`` raises (SDO-03-006)."""
        status = CaseStatus(context="urn:case:1")
        with pytest.raises(ValidationError, match="no attribute"):
            setattr(status, flat, EM.ACTIVE)
        assert status.em.state == EM.NONE
        assert status.pxa.state == CS_pxa.pxa

    def test_case_register_step_still_stamps_frozen_status(self):
        """A register step re-stamps EM onto the frozen status (AC-3, ADR-0122)."""
        case = VulnerabilityCase(
            id_="urn:uuid:case-4375",
            case_statuses=[CaseStatus(context="urn:uuid:case-4375")],
        )
        before = case.current_status
        activate(case, "urn:uuid:embargo-4375")
        assert case.em_state == EM.ACTIVE
        assert case.current_status.em.state == EM.ACTIVE
        # the stamp replaced the status by copy; the old one is untouched
        assert before.em.state == EM.NONE

    def test_model_copy_with_em_update_works(self):
        """``model_copy(update={"em": ...})`` is the legitimate write path (ADR-0122)."""
        status = CaseStatus(context="urn:case:1")
        stamped = status.model_copy(
            update={"em": EmDimension(state=EM.ACTIVE)}
        )
        assert stamped.em.state == EM.ACTIVE
        # original is unchanged
        assert status.em.state == EM.NONE


class TestPxaDimension:
    def test_default_state(self):
        d = PxaDimension()
        assert d.state == CS_pxa.pxa

    def test_construct_from_enum(self):
        d = PxaDimension(state=CS_pxa.Pxa)
        assert d.state == CS_pxa.Pxa

    def test_construct_from_string(self):
        d = PxaDimension.model_validate({"state": "pxa"})
        assert d.state == CS_pxa.pxa

    def test_is_embargo_eligible(self):
        assert PxaDimension(state=CS_pxa.pxa).is_embargo_eligible()
        assert not PxaDimension(state=CS_pxa.Pxa).is_embargo_eligible()

    def test_is_public_aware(self):
        assert PxaDimension(state=CS_pxa.Pxa).is_public_aware()
        assert not PxaDimension(state=CS_pxa.pxa).is_public_aware()


class TestRmDimension:
    def test_default_state(self):
        d = RmDimension()
        assert d.state == RM.START

    def test_construct_from_enum(self):
        d = RmDimension(state=RM.RECEIVED)
        assert d.state == RM.RECEIVED

    def test_construct_from_string(self):
        d = RmDimension.model_validate({"state": "RECEIVED"})
        assert d.state == RM.RECEIVED

    def test_transition_returns_new_object(self):
        d = RmDimension(state=RM.START)
        d2 = d.transition(RM_Trigger.RECEIVE)
        assert d2 is not d
        assert d.state == RM.START
        assert d2.state == RM.RECEIVED

    def test_transition_invalid_raises(self):
        d = RmDimension(state=RM.CLOSED)
        with pytest.raises(VultronInvalidStateTransitionError):
            d.transition(RM_Trigger.RECEIVE)

    def test_is_validated(self):
        assert RmDimension(state=RM.VALID).is_validated()
        assert not RmDimension(state=RM.RECEIVED).is_validated()

    def test_is_accepted(self):
        assert RmDimension(state=RM.ACCEPTED).is_accepted()
        assert not RmDimension(state=RM.START).is_accepted()

    def test_is_closed(self):
        assert RmDimension(state=RM.CLOSED).is_closed()
        assert not RmDimension(state=RM.ACCEPTED).is_closed()

    def test_is_terminal(self):
        assert RmDimension(state=RM.CLOSED).is_terminal()
        assert not RmDimension(state=RM.ACCEPTED).is_terminal()

    def test_serialization_roundtrip(self):
        d = RmDimension(state=RM.ACCEPTED)
        d2 = RmDimension.model_validate_json(d.model_dump_json())
        assert d2.state == RM.ACCEPTED


class TestCaseStatusCarriesNoFlatShim:
    """SDO-03-003 / SDO-03-005: the flat ``em_state`` / ``pxa_state`` are gone."""

    @pytest.mark.spec("SDO-03-003")
    @pytest.mark.parametrize("flat", ["em_state", "pxa_state"])
    def test_case_status_defines_no_flat_property(self, flat):
        """No getter, setter or field survives under the flat name (SDO-03-003)."""
        assert not hasattr(CaseStatus, flat)
        assert flat not in CaseStatus.model_fields
        assert not hasattr(CaseStatus(context="urn:case:1"), flat)

    @pytest.mark.spec("SDO-03-003")
    @pytest.mark.spec("SDO-03-005")
    @pytest.mark.parametrize(
        "flat, value", [("em_state", "ACTIVE"), ("pxa_state", "PXA")]
    )
    def test_flat_input_key_is_refused_by_extra_forbid(self, flat, value):
        """A flat key raises through ``extra="forbid"`` (SDO-03-005)."""
        with pytest.raises(ValidationError) as excinfo:
            CaseStatus.model_validate({"context": "urn:case:1", flat: value})
        assert [e["type"] for e in excinfo.value.errors()] == [
            "extra_forbidden"
        ]
        assert [e["loc"] for e in excinfo.value.errors()] == [(flat,)]

    @pytest.mark.parametrize(
        "key, value, read",
        [
            ("emState", "NONE", lambda s: s.em.state),
            ("em", "NONE", lambda s: s.em.state),
            ("pxaState", "PXA", lambda s: s.pxa.state),
            ("pxa", "PXA", lambda s: s.pxa.state),
        ],
    )
    def test_wire_and_field_spellings_are_accepted(self, key, value, read):
        """``emState``/``em`` and ``pxaState``/``pxa`` stay accepted (AC-2)."""
        status = CaseStatus.model_validate(
            {"context": "urn:case:1", key: value}
        )
        assert read(status).name == value

    @pytest.mark.spec("SDO-03-005")
    def test_no_reject_guard_validator(self):
        """The refusal is ``extra="forbid"``, not a before-validator (SDO-03-005)."""
        validators = CaseStatus.__pydantic_decorators__.model_validators
        own_before = [
            name
            for name, v in validators.items()
            if v.info.mode == "before"
            and getattr(v.func, "__qualname__", "").startswith("CaseStatus.")
        ]
        assert own_before == []
