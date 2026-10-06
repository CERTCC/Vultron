#!/usr/bin/env python

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

"""Tests for as_CaseParticipant model, focusing on the embargo_consents rows (CM-10-001)."""

import unittest
from typing import cast

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.db_record import (
    object_to_record,
    record_to_object,
)
from vultron.core.models.dimensions import (
    RmDimension,
    VfDimension,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    CoordinatorParticipant,
    FinderParticipant,
    VendorParticipant,
    as_CaseParticipant,
)


class TestCaseParticipantEmbargoConsents(unittest.TestCase):
    """Tests for as_CaseParticipant.embargo_consents (CM-10-001, ADR-0120)."""

    def setUp(self):
        self.actor_id = "https://example.org/actors/alice"
        self.case_id = "https://example.org/cases/case-001"
        self.embargo_id_1 = "https://example.org/embargoes/emb-001"
        self.embargo_id_2 = "https://example.org/embargoes/emb-002"
        self.participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
        )

    def _rows(self) -> list[EmbargoConsent]:
        return [
            EmbargoConsent(
                embargo_id=self.embargo_id_1,
                state=EmbargoConsentState.ACCEPTED,
            ),
            EmbargoConsent(
                embargo_id=self.embargo_id_2,
                state=EmbargoConsentState.INVITED,
            ),
        ]

    def test_embargo_consents_default_empty(self):
        """A new as_CaseParticipant has never been asked about any embargo."""
        self.assertEqual([], self.participant.embargo_consents)
        self.assertIsNone(self.participant.consent_for(self.embargo_id_1))

    def test_embargo_consents_can_be_set_at_creation(self):
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            embargo_consents=self._rows(),
        )
        self.assertEqual(
            EmbargoConsentState.ACCEPTED,
            participant.consent_for(self.embargo_id_1),
        )
        self.assertEqual(
            EmbargoConsentState.INVITED,
            participant.consent_for(self.embargo_id_2),
        )

    def test_embargo_consents_serialize_as_camel_case_rows(self):
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            embargo_consents=self._rows(),
        )
        dumped = participant.model_dump(by_alias=True, mode="json")
        self.assertEqual(
            [
                {"embargoId": self.embargo_id_1, "state": "ACCEPTED"},
                {"embargoId": self.embargo_id_2, "state": "INVITED"},
            ],
            dumped["embargoConsents"],
        )
        for retired in (
            "acceptedEmbargoIds",
            "embargoConsentState",
            "embargoAdherence",
        ):
            self.assertNotIn(retired, dumped)

    def test_embargo_consents_round_trip_json(self):
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            embargo_consents=self._rows(),
        )
        restored = as_CaseParticipant.model_validate_json(
            participant.model_dump_json(by_alias=True)
        )
        self.assertEqual(
            participant.embargo_consents, restored.embargo_consents
        )

    def test_embargo_consents_round_trip_object_to_record(self):
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            embargo_consents=self._rows(),
        )
        record = object_to_record(participant)
        restored = cast(as_CaseParticipant, record_to_object(record))
        self.assertEqual(
            participant.embargo_consents, restored.embargo_consents
        )

    def test_empty_embargo_consents_round_trip_object_to_record(self):
        record = object_to_record(self.participant)
        restored = cast(as_CaseParticipant, record_to_object(record))
        self.assertEqual([], restored.embargo_consents)

    def test_retired_scalar_fields_are_refused(self):
        for key, value in (
            ("accepted_embargo_ids", [self.embargo_id_1]),
            ("embargo_consent_state", "SIGNATORY"),
        ):
            with pytest.raises(ValidationError):
                as_CaseParticipant(
                    attributed_to=self.actor_id,
                    context=self.case_id,
                    **{key: value},  # type: ignore[arg-type]
                )

    def test_embargo_consents_present_in_subclasses(self):
        """embargo_consents is inherited by as_CaseParticipant subclasses."""
        for cls in [
            FinderParticipant,
            VendorParticipant,
            CoordinatorParticipant,
        ]:
            participant = cls(
                attributed_to=self.actor_id,
                context=self.case_id,
                embargo_consents=self._rows(),
            )
            self.assertEqual(
                EmbargoConsentState.ACCEPTED,
                participant.consent_for(self.embargo_id_1),
                f"{cls.__name__} should inherit embargo_consents",
            )

    def test_embargo_consents_subclass_round_trip(self):
        """embargo_consents survive the record round-trip for a subclass."""
        vendor = VendorParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            embargo_consents=self._rows(),
        )
        record = object_to_record(vendor)
        restored = cast(VendorParticipant, record_to_object(record))
        self.assertEqual(vendor.embargo_consents, restored.embargo_consents)


class TestCaseParticipantNameField(unittest.TestCase):
    """Tests for as_CaseParticipant.name field empty-string validation (CS-08-001)."""

    def setUp(self):
        self.actor_id = "https://example.org/actors/alice"
        self.case_id = "https://example.org/cases/case-001"

    def test_name_none_accepted(self):
        """name=None is valid when attributed_to is also not set."""
        participant = as_CaseParticipant(context=self.case_id, name=None)
        self.assertIsNone(participant.name)

    def test_name_non_empty_accepted(self):
        """name with a non-empty string is valid."""
        participant = as_CaseParticipant(
            attributed_to=self.actor_id, context=self.case_id, name="Alice"
        )
        self.assertEqual("Alice", participant.name)

    def test_name_empty_string_rejected(self):
        """name must not be an empty string (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_CaseParticipant(
                attributed_to=self.actor_id, context=self.case_id, name=""
            )
        assert "must be a non-empty string" in str(exc_info.value)

    def test_name_whitespace_only_rejected(self):
        """name must not be whitespace-only (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_CaseParticipant(
                attributed_to=self.actor_id, context=self.case_id, name="   "
            )
        assert "must be a non-empty string" in str(exc_info.value)

    def test_participant_case_name_none_accepted(self):
        """participant_case_name=None is valid."""
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            participant_case_name=None,
        )
        self.assertIsNone(participant.participant_case_name)

    def test_participant_case_name_non_empty_accepted(self):
        """participant_case_name with a non-empty string is valid."""
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            participant_case_name="My Case",
        )
        self.assertEqual("My Case", participant.participant_case_name)

    def test_participant_case_name_empty_string_rejected(self):
        """participant_case_name must not be an empty string (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_CaseParticipant(
                attributed_to=self.actor_id,
                context=self.case_id,
                participant_case_name="",
            )
        assert "must be a non-empty string" in str(exc_info.value)


class TestParticipantStatusProperty(unittest.TestCase):
    """Tests for as_CaseParticipant.participant_status selection (bug #659).

    The property must return the most recently *appended* status, which
    represents this replica's current view. Wire-layer timestamps
    (``published``/``updated``) on appended statuses are sender-authored
    and cannot be relied on to order strictly after locally-constructed
    defaults (e.g. the initial vfd status auto-created by
    ``init_participant_status_if_empty``).
    """

    def setUp(self):
        from datetime import datetime, timezone

        from vultron.core.states.cs import CS_vf
        from vultron.core.states.rm import RM
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        self.CS_vf = CS_vf
        self.RM = RM
        self.as_ParticipantStatus = as_ParticipantStatus
        self.dt = datetime
        self.tz = timezone
        self.actor_id = "https://example.org/actors/vendor"
        self.case_id = "https://example.org/cases/case-001"

    def test_returns_last_appended_even_when_earlier_status_has_newer_timestamp(
        self,
    ):
        """Bug #659: tiebreaker must prefer append-order over timestamp.

        Initial vf status is created locally with ``published=now()``.
        A subsequently appended Vf status carries a sender-supplied
        ``published`` that may be *earlier* than the local initial value
        (clock skew, batched processing, etc.). The property must still
        return the appended Vf entry.
        """
        appended = self.as_ParticipantStatus(
            context=self.case_id,
            attributed_to=self.actor_id,
            rm=RmDimension(state=self.RM.ACCEPTED),
            vf=VfDimension(state=self.CS_vf.Vf),
            published=self.dt(2026, 6, 2, 16, 26, 48, tzinfo=self.tz.utc),
            updated=self.dt(2026, 6, 2, 16, 26, 48, tzinfo=self.tz.utc),
        )
        # Construct participant with empty list so the validator creates
        # the initial status with published=now() (which will be > appended's).
        participant = as_CaseParticipant(
            attributed_to=self.actor_id, context=self.case_id
        )
        self.assertEqual(1, len(participant.participant_statuses))
        participant.participant_statuses.append(appended)

        latest = participant.participant_status
        self.assertIsNotNone(latest)
        assert latest is not None  # narrow for type checker
        self.assertEqual(self.CS_vf.Vf, latest.vf_state)
        self.assertEqual(self.RM.ACCEPTED, latest.rm_state)

    def test_returns_none_when_empty(self):
        """participant_status returns None when the list is empty."""
        participant = as_CaseParticipant(
            attributed_to=self.actor_id, context=self.case_id
        )
        # init_participant_status_if_empty populates one status by default;
        # use object.__setattr__ to bypass frozen and exercise the empty branch.
        object.__setattr__(participant, "participant_statuses", [])
        self.assertIsNone(participant.participant_status)

    def test_returns_single_status_when_only_one_present(self):
        only = self.as_ParticipantStatus(
            context=self.case_id,
            attributed_to=self.actor_id,
        )
        participant = as_CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            participant_statuses=[only],
        )
        self.assertIs(only, participant.participant_status)
