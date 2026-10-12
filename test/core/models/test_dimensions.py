#!/usr/bin/env python
"""Unit tests for vultron/core/models/dimensions.py."""

import pytest
from pydantic import ValidationError

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

    def test_status_em_state_setter_deleted(self):
        """``CaseStatus.em_state`` has no setter (AC-2, SDO-03-006)."""
        assert isinstance(CaseStatus.__dict__["em_state"], property), (
            "em_state must be a property"
        )
        assert CaseStatus.__dict__["em_state"].fset is None, (
            "em_state must have no setter"
        )

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
