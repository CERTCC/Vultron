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
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Tests for the wire-spelled-key guard (issue #2232, ARCH-15-001/002).

The guard is computed *per exact class* rather than from a single module-level
map.  That is the whole point: ``CaseParticipant`` has eight role subclasses, and
a subclass that adds a snake_case-only field would silently drop that field's
camelCase spelling if it inherited a map computed from its base.
"""

import pytest
from pydantic import BaseModel, Field

from vultron.core.models._wire_spelling import (
    clear_cache,
    reject_wire_spelled_keys,
    wire_spelled_keys,
)
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
from vultron.errors import VultronValidationError

_ACTOR = "https://example.org/actors/alice"
_CONTEXT = "https://example.org/cases/case-2232"

#: Every core participant class that can be validated from raw input.  Listed
#: explicitly rather than via ``__subclasses__()`` so that adding a role class
#: without covering it here shows up as a missing entry, not a silently smaller
#: test matrix.
_PARTICIPANT_CLASSES = [
    CaseParticipant,
    FinderParticipant,
    ReporterParticipant,
    FinderReporterParticipant,
    VendorParticipant,
    DeployerParticipant,
    CoordinatorParticipant,
    ObserverParticipant,
    CaseActorParticipant,
]


def test_every_case_participant_subclass_is_covered():
    """The matrix below must not fall behind the class hierarchy."""
    declared = set(_PARTICIPANT_CLASSES)
    actual = {CaseParticipant, *CaseParticipant.__subclasses__()}
    assert actual == declared, (
        "a new CaseParticipant role subclass was added without extending"
        " _PARTICIPANT_CLASSES — its wire-shape guard would be untested"
    )


@pytest.mark.parametrize(
    "model", _PARTICIPANT_CLASSES, ids=lambda c: c.__name__
)
def test_wire_spelled_participant_statuses_raises(model):
    """Each role subclass rejects ``participantStatuses`` in its own right."""
    data = {
        "attributed_to": _ACTOR,
        "context": _CONTEXT,
        "participantStatuses": [],
    }
    with pytest.raises(VultronValidationError, match="participantStatuses"):
        model.model_validate(data)


@pytest.mark.parametrize(
    "model", _PARTICIPANT_CLASSES, ids=lambda c: c.__name__
)
def test_canonical_snake_case_still_validates(model):
    """The guard must not reject the canonical core shape."""
    participant = model.model_validate(
        {
            "attributed_to": _ACTOR,
            "context": _CONTEXT,
            "case_roles": [],
        }
    )
    assert participant.attributed_to == _ACTOR


class TestWireSpelledKeys:
    """``wire_spelled_keys`` maps forbidden camelCase spellings per class."""

    def test_snake_only_field_is_forbidden(self):
        mapping = wire_spelled_keys(CaseParticipant)
        assert mapping["participantStatuses"] == "participant_statuses"

    def test_sanctioned_alias_is_not_forbidden(self):
        """``in_reply_to`` declares ``inReplyTo`` — a deliberate alias."""
        assert "inReplyTo" not in wire_spelled_keys(CaseParticipant)

    def test_trailing_underscore_fields_are_skipped(self):
        """``id_``/``type_`` carry their own aliases and have no camel form."""
        mapping = wire_spelled_keys(CaseParticipant)
        assert not any(key.startswith(("id", "type")) for key in mapping)

    def test_single_word_fields_are_skipped(self):
        """``name``/``context`` camelCase to themselves, so cannot collide."""
        mapping = wire_spelled_keys(CaseParticipant)
        assert "name" not in mapping
        assert "context" not in mapping

    def test_subclass_gets_its_own_map_not_the_base_map(self):
        """A subclass that adds a field must have that field guarded too.

        This is the hole a single shared module-level map would leave open: the
        base's map knows nothing about ``extra_wire_field``, so a payload
        spelling it ``extraWireField`` would be dropped in silence.
        """

        class _WithExtraField(CaseParticipant):
            extra_wire_field: str | None = Field(default=None)

        try:
            base_map = wire_spelled_keys(CaseParticipant)
            sub_map = wire_spelled_keys(_WithExtraField)
            assert "extraWireField" not in base_map
            assert sub_map["extraWireField"] == "extra_wire_field"

            with pytest.raises(VultronValidationError, match="extraWireField"):
                _WithExtraField.model_validate(
                    {
                        "attributed_to": _ACTOR,
                        "context": _CONTEXT,
                        "extraWireField": "dropped-in-silence",
                    }
                )
        finally:
            # The dynamic class would otherwise linger in the per-class cache.
            clear_cache()

    def test_cache_returns_the_same_mapping_object(self):
        assert wire_spelled_keys(CaseParticipant) is wire_spelled_keys(
            CaseParticipant
        )


class TestRejectWireSpelledKeys:
    """``reject_wire_spelled_keys`` is the validator-facing entry point."""

    class _Model(BaseModel):
        some_field: str | None = None

    def test_non_dict_input_passes_through(self):
        """A ``mode="before"`` validator also sees non-dict input."""
        sentinel = object()
        assert (
            reject_wire_spelled_keys(self._Model, sentinel, "hint") is sentinel
        )

    def test_clean_dict_is_returned_unchanged(self):
        data = {"some_field": "ok"}
        assert reject_wire_spelled_keys(self._Model, data, "hint") is data

    def test_error_names_the_boundary_the_caller_should_have_used(self):
        """The message has to say what to do instead, not just what broke."""
        with pytest.raises(VultronValidationError) as exc_info:
            reject_wire_spelled_keys(
                self._Model,
                {"someField": "wire-spelled"},
                "as_Thing.to_core()",
            )
        message = str(exc_info.value)
        assert "someField -> some_field" in message
        assert "as_Thing.to_core()" in message
        assert "#2232" in message

    def test_all_offenders_are_reported_not_just_the_first(self):
        """Fixing one key at a time turns one bad payload into N round trips."""

        class _TwoFields(BaseModel):
            first_field: str | None = None
            second_field: str | None = None

        with pytest.raises(VultronValidationError) as exc_info:
            reject_wire_spelled_keys(
                _TwoFields,
                {"firstField": "a", "secondField": "b"},
                "hint",
            )
        message = str(exc_info.value)
        assert "firstField" in message
        assert "secondField" in message
