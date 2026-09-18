#!/usr/bin/env python
"""Unit tests for vultron/core/models/dimensions.py."""

import pytest

from vultron.core.models.dimensions import (
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
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

    def test_transition_returns_new_object(self):
        d = EmDimension(state=EM.NONE)
        d2 = d.transition(EM_Trigger.PROPOSE)
        assert d2 is not d
        assert d.state == EM.NONE  # original unchanged
        assert d2.state == EM.PROPOSED

    def test_transition_invalid_raises(self):
        d = EmDimension(state=EM.NONE)
        with pytest.raises(VultronInvalidStateTransitionError):
            d.transition(EM_Trigger.TERMINATE)

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


class TestPecDimension:
    def test_default_state(self):
        d = PecDimension()
        assert d.state == PEC.UNBOUND

    def test_construct_from_enum(self):
        d = PecDimension(state=PEC.SIGNATORY)
        assert d.state == PEC.SIGNATORY

    def test_construct_from_string(self):
        d = PecDimension.model_validate({"state": "INVITED"})
        assert d.state == PEC.INVITED

    def test_transition_returns_new_object(self):
        d = PecDimension(state=PEC.UNBOUND)
        d2 = d.transition(PEC_Trigger.INVITE)
        assert d2 is not d
        assert d.state == PEC.UNBOUND
        assert d2.state == PEC.INVITED

    def test_transition_invalid_raises(self):
        # CM-18-004: SIGNATORY → INVITED is still invalid (ADR-0048)
        d = PecDimension(state=PEC.SIGNATORY)
        with pytest.raises(VultronInvalidStateTransitionError):
            d.transition(PEC_Trigger.INVITE)

    def test_is_signatory(self):
        assert PecDimension(state=PEC.SIGNATORY).is_signatory()
        assert not PecDimension(state=PEC.INVITED).is_signatory()

    def test_is_declined(self):
        assert PecDimension(state=PEC.DECLINED).is_declined()
        assert not PecDimension(state=PEC.SIGNATORY).is_declined()

    def test_is_invited(self):
        assert PecDimension(state=PEC.INVITED).is_invited()
        assert not PecDimension(state=PEC.SIGNATORY).is_invited()

    def test_is_lapsed(self):
        assert PecDimension(state=PEC.LAPSED).is_lapsed()
        assert not PecDimension(state=PEC.SIGNATORY).is_lapsed()

    def test_serialization_roundtrip(self):
        d = PecDimension(state=PEC.SIGNATORY)
        d2 = PecDimension.model_validate_json(d.model_dump_json())
        assert d2.state == PEC.SIGNATORY
