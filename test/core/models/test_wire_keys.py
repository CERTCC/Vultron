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

"""The AS2 spelling of a core field is *derived*, never typed (ADR-0099 detail 2).

``wire_keys`` exists so that no core module contains a camelCase spelling of a
core field name. The value of a derivation over a translation table is that it
cannot drift — but only if it refuses to answer for a field that does not exist.
A silent ``to_camel`` fallback would invent a plausible key for a renamed field,
and the callers filter a rendered snapshot with ``if key in rendered``, so the
wrong key drops the dimension it was meant to carry instead of failing.
"""

import pytest

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.wire_keys import input_keys, wire_key, wire_keys


class TestWireKey:
    """``wire_key`` reads the declared serialization alias, else camel-cases."""

    @pytest.mark.parametrize(
        "model, field_name, expected",
        [
            # Declared serialization_alias wins — this is the whole point.
            (ParticipantStatus, "rm", "rmState"),
            (ParticipantStatus, "vf", "vfState"),
            (ParticipantStatus, "d", "dState"),
            (ParticipantStatus, "consent", "emConsentState"),
            (CaseStatus, "em", "emState"),
            (CaseStatus, "pxa", "pxaState"),
            # No explicit alias: the model's alias_generator camel-cases it.
            (CaseStatus, "attributed_to", "attributedTo"),
            (VultronOfferRecord, "offer_id", "offerId"),
        ],
    )
    def test_derives_the_declared_spelling(self, model, field_name, expected):
        assert wire_key(field_name, model) == expected

    def test_without_a_model_it_camel_cases(self):
        """The model-less form is legitimate — `_helpers.py` uses it."""
        assert wire_key("payload_snapshot") == "payloadSnapshot"
        assert wire_key("case_participants") == "caseParticipants"

    def test_a_single_word_is_unchanged(self):
        assert wire_key("context") == "context"

    def test_unknown_field_raises_rather_than_inventing_a_key(self):
        """The regression this module's value depends on.

        Returning ``"noSuchField"`` here would be worse than failing: the patch
        key and twin tables in ``core/behaviors/ledger_patch.py`` are built from
        string field names and filtered with ``if key in rendered``, so a wrong
        key silently drops the adjudicated dimension rather than raising.
        """
        with pytest.raises(KeyError, match="no field 'no_such_field'"):
            wire_key("no_such_field", ParticipantStatus)

    def test_wire_keys_maps_in_order(self):
        assert wire_keys(("rm", "vf", "d"), ParticipantStatus) == (
            "rmState",
            "vfState",
            "dState",
        )

    def test_wire_keys_propagates_the_unknown_field_error(self):
        with pytest.raises(KeyError):
            wire_keys(("rm", "no_such_field"), ParticipantStatus)


class TestInputKeys:
    """``input_keys`` reports every spelling a field is accepted under."""

    @pytest.mark.parametrize(
        "model, field_name, expected",
        [
            (
                ParticipantStatus,
                "rm",
                ("rmState", "rm_state", "rm"),
            ),
            (CaseStatus, "em", ("emState", "em_state", "em")),
            (CaseStatus, "pxa", ("pxaState", "pxa_state", "pxa")),
        ],
    )
    def test_lists_the_alias_choices_then_the_field_name(
        self, model, field_name, expected
    ):
        assert input_keys(model, field_name) == expected

    def test_the_as2_spelling_comes_first(self):
        """Callers take the *first* key present, so the order is a contract.

        Wire-shaped input is where these keys are read from, so the AS2 spelling
        is the authoritative one and must win over the Python field name.
        """
        keys = input_keys(CaseStatus, "em")
        assert keys[0] == "emState"
        assert keys[-1] == "em"

    def test_field_name_is_included_even_without_aliases(self):
        keys = input_keys(CaseStatus, "context")
        assert "context" in keys

    def test_never_duplicates_the_field_name(self):
        for field_name in ("em", "pxa", "context"):
            keys = input_keys(CaseStatus, field_name)
            assert len(keys) == len(set(keys))

    def test_unknown_field_raises(self):
        with pytest.raises(KeyError, match="no field 'no_such_field'"):
            input_keys(ParticipantStatus, "no_such_field")


class TestEveryReportedSpellingActuallyValidates:
    """The derivation is only useful if the model agrees with it.

    A unit test of the helper in isolation would pass even if the helper and
    Pydantic disagreed about which keys a field accepts. These assert against
    the models themselves, so an alias change that breaks an input spelling
    fails here rather than at a call site.
    """

    @pytest.mark.parametrize(
        "model, field_name, sample",
        [
            (CaseStatus, "em", "EXITED"),
            (CaseStatus, "pxa", "Pxa"),
            (ParticipantStatus, "rm", "ACCEPTED"),
        ],
    )
    def test_each_input_key_is_accepted(self, model, field_name, sample):
        for key in input_keys(model, field_name):
            obj = model.model_validate({"context": "urn:case:1", key: sample})
            assert getattr(obj, field_name).state.name == sample, (
                f"{model.__name__} did not accept {key!r},"
                " which input_keys reports as a valid spelling"
            )

    @pytest.mark.parametrize(
        "model, field_name",
        [
            (CaseStatus, "em"),
            (CaseStatus, "pxa"),
            (ParticipantStatus, "rm"),
        ],
    )
    def test_the_wire_key_is_what_the_model_emits(self, model, field_name):
        obj = model.model_validate({"context": "urn:case:1"})
        dumped = obj.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert wire_key(field_name, model) in dumped
