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
from vultron.core.models.participant_status import ParticipantStatus
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
def test_wire_spelled_participant_statuses_is_read_not_dropped(model):
    """Each role subclass reads ``participantStatuses`` into the right field.

    This asserted the opposite — that ``participantStatuses`` was *rejected*.
    Rejection was never the goal: core declared no camelCase aliases, so
    Pydantic's ``extra="ignore"`` default made the key vanish and the field
    re-seeded at its start value (#2232 — a silently shortened RM ladder).
    Raising at least made the loss visible.

    ADR-0099 puts the AS2 spelling on the core class, so the key is read into
    ``participant_statuses`` instead of disappearing.  Asserting the value
    *arrives* is strictly stronger than asserting the payload was refused: a
    passing rejection test is still consistent with the data being unreadable,
    whereas this one fails if the mapping is ever lost.
    """
    status = ParticipantStatus(attributed_to=_ACTOR, context=_CONTEXT)
    participant = model.model_validate(
        {
            "attributed_to": _ACTOR,
            "context": _CONTEXT,
            "participantStatuses": [
                status.model_dump(by_alias=True, mode="json")
            ],
        }
    )
    assert len(participant.participant_statuses) == 1, (
        "the wire spelling was dropped — the field re-seeded instead of being"
        " read, which is the #2232 defect"
    )


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

    def test_generator_derived_spellings_are_not_forbidden(self):
        """A model carrying an ``alias_generator`` forbids nothing.

        ``participantStatuses`` used to be in this map, because core declared no
        camelCase aliases and the key would have vanished under
        ``extra="ignore"``.  ADR-0099 puts the AS2 spelling on the core class, so
        every field's camelCase form is now a real alias and the map is empty —
        a deliberate no-op for ``CoreObject`` subclasses, not a broken guard.

        The module is therefore vestigial for core types; its removal is #2940
        AC-6.  It is kept because it still protects models carrying no generator
        (below), and deleting it is not this change's job.
        """
        assert wire_spelled_keys(CaseParticipant) == {}

    def test_guard_still_protects_a_model_without_a_generator(self):
        """Where nothing derives the alias, the silent-drop hazard is still real."""

        class _NoGenerator(BaseModel):
            some_field: str | None = None

        try:
            assert wire_spelled_keys(_NoGenerator)["someField"] == "some_field"
        finally:
            clear_cache()

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

    def test_subclass_field_added_later_is_still_read_not_dropped(self):
        """A field added by a subclass gets its AS2 spelling for free.

        This was the hole a shared module-level map would have left open: the
        base's map knew nothing about ``extra_wire_field``, so a payload spelling
        it ``extraWireField`` was dropped in silence, and the guard's answer was
        to refuse the payload.

        Inheriting the generator closes the hole at the source instead — the new
        field is readable under its AS2 spelling without anyone registering it.
        That is the property worth holding: asserting a refusal only ever proved
        the data was unusable.
        """

        class _WithExtraField(CaseParticipant):
            extra_wire_field: str | None = Field(default=None)

        try:
            assert wire_spelled_keys(_WithExtraField) == {}

            built = _WithExtraField.model_validate(
                {
                    "attributed_to": _ACTOR,
                    "context": _CONTEXT,
                    "extraWireField": "read-not-dropped",
                }
            )
            assert built.extra_wire_field == "read-not-dropped"
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
                "as_Thing",
            )
        message = str(exc_info.value)
        assert "someField -> some_field" in message
        assert "as_Thing" in message
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
